"""
Hybrid Attention-MLP Trading Model - Optimized Architecture

Combines the best of both worlds:
- Feature Attention: Learns which features are important for each prediction
- MLP Classifier: Efficient classification with proper regularization
- Anti-overfitting: Heavy dropout, batch norm, data augmentation ready

Designed for small datasets (10K-100K samples) common in trading.

Model Sizes:
- Micro:  ~50K params  - Minimal overfitting risk
- Small:  ~150K params - Good balance
- Medium: ~500K params - More capacity with regularization
- Large:  ~1M params   - Maximum capacity (needs 50K+ samples)

Key Innovation: Feature Attention Layer
- Instead of treating features as a sequence, we compute attention scores
- Each feature learns to "attend" to other related features
- Output: weighted combination of features → MLP

Usage:
    from hybrid_model import get_hybrid_model
    
    model = get_hybrid_model("small")
    model = model.cuda()
    output = model(features)

El servicio fourier_service_fast.py ya genera los JSONs de Fourier automáticamente. 
Solo asegúrate de descargar la carpeta /fourier/ junto con /json_data/ y /ib_backtest/.
"""

import os
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path


# --- DEVICE CONFIGURATION ---
def get_device():
    """Get the best available device."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"[GPU] Using CUDA: {torch.cuda.get_device_name(0)}")
        print(f"[GPU] Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        device = torch.device("cpu")
        print("[CPU] CUDA not available, using CPU")
    return device


# --- FEATURE ATTENTION LAYER ---
class FeatureAttention(nn.Module):
    """
    Lightweight attention mechanism for feature importance.
    
    Instead of full transformer attention, this uses:
    1. Feature embeddings (each feature gets a learned embedding)
    2. Cross-feature attention (which features should I focus on?)
    3. Weighted feature combination
    
    Output: Attention-weighted feature vector + attention weights for interpretability
    """
    
    def __init__(self, num_features: int = 32, embed_dim: int = 64, num_heads: int = 4, dropout: float = 0.2):
        super().__init__()
        
        self.num_features = num_features
        self.embed_dim = embed_dim
        
        # Feature embedding: project to embed_dim
        self.feature_embed = nn.Linear(1, embed_dim)
        
        # Learnable feature type embeddings (like positional encoding but for feature types)
        self.feature_type_embed = nn.Embedding(num_features, embed_dim)
        
        # Multi-head attention (lightweight)
        self.attention = nn.MultiheadAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Output projection
        # Esta normalización es para el paso intermedio (tamaño embed_dim)
        self.layer_norm_inter = nn.LayerNorm(embed_dim)
        
        # Esta normalización es para el paso final tras la concatenación (tamaño embed_dim * 2)
        self.layer_norm_final = nn.LayerNorm(embed_dim * 2)
        
        # La proyección vuelve al tamaño original para el MLP
        self.output_proj = nn.Linear(embed_dim * 2, embed_dim)
        self.dropout = nn.Dropout(dropout)
        
        # Feature importance query (learnable)
        self.importance_query = nn.Parameter(torch.randn(1, 1, embed_dim))
        
    def forward(self, x, return_attention=False):
        """
        Args:
            x: (batch_size, num_features) - raw feature values
        Returns:
            output: (batch_size, embed_dim * 2) - attention-weighted features
            attention: (batch_size, num_features) - feature importance weights
        """
        batch_size = x.shape[0]
        
        # Shape: (batch, features, 1)
        x_expanded = x.unsqueeze(-1)
        
        # Project each feature value
        x_embed = self.feature_embed(x_expanded)  # (batch, features, embed_dim)
        
        # Add feature type embeddings
        feat_indices = torch.arange(self.num_features, device=x.device)
        type_embed = self.feature_type_embed(feat_indices)  # (features, embed_dim)
        x_embed = x_embed + type_embed.unsqueeze(0)
        
        # Self-attention: each feature attends to all others
        attn_output, attn_weights = self.attention(
            x_embed, x_embed, x_embed, 
            need_weights=True
        )
        
        # Usamos la normalización intermedia (128)
        x_embed = self.layer_norm_inter(x_embed + self.dropout(attn_output))
        
        query = self.importance_query.expand(batch_size, -1, -1)
        _, importance_weights = self.attention(query, x_embed, x_embed, need_weights=True)
        importance_weights = importance_weights.squeeze(1)
        
        weighted_features = (x_embed * importance_weights.unsqueeze(-1)).sum(dim=1)
        max_features = x_embed.max(dim=1)[0]
        
        # Concatenamos (64+64=128 en micro, o 128+128=256 en small/medium)
        concat_features = torch.cat([weighted_features, max_features], dim=-1)
        
        # Usamos la normalización final (tamaño doble) y proyectamos
        output = self.output_proj(self.layer_norm_final(concat_features))

        if return_attention:
            return output, importance_weights
        return output


# --- REGULARIZED MLP BLOCK ---
class RegularizedMLPBlock(nn.Module):
    """
    MLP block with heavy regularization for small datasets.
    
    Features:
    - Batch normalization before activation
    - Dropout after activation
    - Residual connections where possible
    """
    
    def __init__(self, in_features: int, out_features: int, dropout: float = 0.3):
        super().__init__()
        
        self.fc = nn.Linear(in_features, out_features)
        self.bn = nn.BatchNorm1d(out_features)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()
        
        # Residual if dimensions match
        self.use_residual = (in_features == out_features)
        
    def forward(self, x):
        identity = x
        x = self.fc(x)
        x = self.bn(x)
        x = self.activation(x)
        x = self.dropout(x)
        
        if self.use_residual:
            x = x + identity
        
        return x


# --- HYBRID ATTENTION-MLP MODEL ---
class HybridTradingModel(nn.Module):
    """
    Hybrid model combining attention-based feature selection with MLP classification.
    
    Architecture:
    1. Feature Attention: Learn which features matter (interpretable!)
    2. Feature Integration: Combine attended features with original
    3. MLP Classifier: Regularized deep network for classification
    
    Anti-overfitting techniques:
    - Heavy dropout (0.3-0.5)
    - Batch normalization
    - Residual connections
    - Label smoothing ready
    - Weight decay (in optimizer)
    """
    
    def __init__(
        self,
        input_size: int = 32,
        embed_dim: int = 64,
        num_heads: int = 4,
        hidden_dims: list = [256, 128, 64],
        dropout: float = 0.3,
        num_classes: int = 3,
    ):
        super().__init__()
        
        self.input_size = input_size
        
        # Feature attention layer
        self.feature_attention = FeatureAttention(
            num_features=input_size,
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout
        )
        
        # Input integration: attended features + original features
        mlp_input_dim = embed_dim + input_size
        
        # Build MLP layers
        layers = []
        prev_dim = mlp_input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(RegularizedMLPBlock(prev_dim, hidden_dim, dropout))
            prev_dim = hidden_dim
        
        self.mlp = nn.Sequential(*layers)
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.BatchNorm1d(prev_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(prev_dim // 2, num_classes)
        )
        
        # Bayesian time regression head
        # Outputs 2 values: mu (time fraction) and log_sigma (uncertainty)
        self.time_head = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.BatchNorm1d(prev_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(prev_dim // 2, 2),  # 2 outputs: mu, log_sigma
        )
        
        # Initialize weights
        self._init_weights()
        
    def _init_weights(self):
        """Initialize with smaller weights to prevent early overfitting."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight, gain=0.5)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(self, x, return_attention=False):
        """
        Args:
            x: (batch_size, input_size)
        Returns:
            logits: (batch_size, num_classes)
            time_pred: (batch_size, 2) - [mu (0-1), log_sigma]
            attention: optional (batch_size, input_size) feature importance
        """
        # Get attention-weighted features
        if return_attention:
            attended_features, attention_weights = self.feature_attention(x, return_attention=True)
        else:
            attended_features = self.feature_attention(x)
        
        # Combine with original features (skip connection for gradient flow)
        combined = torch.cat([attended_features, x], dim=-1)
        
        # MLP processing
        hidden = self.mlp(combined)
        
        # Classification
        logits = self.classifier(hidden)
        
        # Bayesian Time Regression: mu + log_sigma
        time_params = self.time_head(hidden)
        mu = torch.sigmoid(time_params[:, 0:1])   # [0, 1] fraction of lookahead
        log_sigma = time_params[:, 1:2]            # unbounded for numerical stability
        time_pred = torch.cat([mu, log_sigma], dim=-1)  # (batch, 2)
        
        if return_attention:
            return logits, time_pred, attention_weights
        return logits, time_pred
    
    def predict_proba(self, x):
        logits, _ = self.forward(x)
        return F.softmax(logits, dim=-1)
    
    def predict(self, x):
        """Returns (probabilities, time_fraction)"""
        logits, time_pred = self.forward(x)
        return F.softmax(logits, dim=-1), time_pred
    
    def get_feature_importance(self, x):
        """Get feature importance weights for interpretability."""
        _, _, attention = self.forward(x, return_attention=True)
        return attention


# --- MODEL CONFIGURATIONS ---
HYBRID_CONFIGS = {
    "micro": {
        "embed_dim": 32,
        "num_heads": 2,
        "hidden_dims": [64, 32],
        "dropout": 0.4,
        # ~50K params - Very resistant to overfitting
    },
    "small": {
        "embed_dim": 64,
        "num_heads": 4,
        "hidden_dims": [128, 64, 32],
        "dropout": 0.35,
        # ~150K params - Good balance
    },
    "medium": {
        "embed_dim": 128,
        "num_heads": 4,
        "hidden_dims": [256, 128, 64],
        "dropout": 0.3,
        # ~500K params - More capacity
    },
    "large": {
        "embed_dim": 256,
        "num_heads": 8,
        "hidden_dims": [512, 256, 128, 64],
        "dropout": 0.25,
        # ~1M params - Maximum capacity
    },
}


# --- MODEL FACTORY ---
def get_hybrid_model(model_size: str = "small", input_size: int = 32) -> HybridTradingModel:
    """Get hybrid model by size name."""
    if model_size not in HYBRID_CONFIGS:
        raise ValueError(f"Unknown size: {model_size}. Choose from: {list(HYBRID_CONFIGS.keys())}")
    
    config = HYBRID_CONFIGS[model_size]
    return HybridTradingModel(input_size=input_size, **config)


# --- FEATURE NORMALIZER ---
class FeatureNormalizer:
    """Normalizes features using Z-score normalization."""
    
    def __init__(self, clip_value: float = 5.0):
        self.means = None
        self.stds = None
        self.feature_names = None
        self.clip_value = clip_value
    
    def fit(self, features: np.ndarray, feature_names: list = None):
        self.means = np.mean(features, axis=0)
        self.stds = np.std(features, axis=0)
        self.stds = np.where(self.stds == 0, 1.0, self.stds)
        self.feature_names = feature_names
    
    def transform(self, features: np.ndarray) -> np.ndarray:
        if self.means is None:
            raise ValueError("Normalizer not fitted")

        z_scored = (features - self.means) / self.stds
        normalized = np.clip(z_scored, -self.clip_value, self.clip_value)
        
        return normalized
    
    def fit_transform(self, features: np.ndarray, feature_names: list = None) -> np.ndarray:
        self.fit(features, feature_names)
        return self.transform(features)
    
    def save(self, filepath: str):
        np.savez(filepath, means=self.means, stds=self.stds,
                 feature_names=np.array(self.feature_names) if self.feature_names else np.array([]))
    
    def load(self, filepath: str):
        data = np.load(filepath, allow_pickle=True)
        self.means = data['means']
        self.stds = data['stds']
        if len(data['feature_names']) > 0:
            self.feature_names = data['feature_names'].tolist()


# --- SAVE/LOAD ---
def save_hybrid_model(model: HybridTradingModel, normalizer: FeatureNormalizer,
                      model_path: str, normalizer_path: str):
    """Save model and normalizer."""
    torch.save({
        'model_state_dict': model.state_dict(),
        'input_size': model.input_size,
    }, model_path)
    normalizer.save(normalizer_path)
    print(f"Hybrid model saved to {model_path}")


def load_hybrid_model(model_path: str, normalizer_path: str, 
                      model_size: str = "small", device: torch.device = None):
    """Load model and normalizer."""
    if device is None:
        device = get_device()
    
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    model = get_hybrid_model(model_size, input_size=checkpoint['input_size'])
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()
    
    normalizer = FeatureNormalizer()
    normalizer.load(normalizer_path)
    
    return model, normalizer


# --- FEATURE COLUMNS (93 features - 0DTE + Weekly + Divergence + Market + Vega/Vomma + Confluences) ---
FEATURE_COLUMNS = [
    # ===== 0DTE GREEKS (26 features) =====
    # Net exposures (8) — now includes Vega and Vomma
    "net_gamma", "net_vanna", "net_charm", "net_dgex", "net_zomma", "net_delta",
    "net_vega", "net_vomma",
    # Regime signals (6)
    "gamma_regime", "vanna_bullish", "charm_bullish", "dgex_sticky", "zomma_stabilizing",
    "vega_elevated",
    # Key level distances (10) — includes DGEX + Vega + Vomma levels
    "dist_to_max_gamma", "dist_to_min_gamma", "dist_to_min_vanna",
    "dist_to_zero_gamma", "dist_to_max_dgex", "dist_to_min_dgex",
    "dist_to_max_vega", "dist_to_min_vega",
    "dist_to_max_vomma", "dist_to_min_vomma",
    # Near level flags (2)
    "near_max_gamma", "near_min_gamma",

    # ===== WEEKLY GREEKS (19 features) =====
    # Net exposures (8) — includes Vega and Vomma
    "wk_net_gamma", "wk_net_vanna", "wk_net_charm",
    "wk_net_dgex", "wk_net_zomma", "wk_net_delta",
    "wk_net_vega", "wk_net_vomma",
    # Key level distances (6)
    "wk_dist_to_max_gamma", "wk_dist_to_min_gamma",
    "wk_dist_to_max_dgex", "wk_dist_to_min_dgex",
    "wk_dist_to_max_vega", "wk_dist_to_min_vega",
    # Regime signals (5)
    "wk_gamma_regime", "wk_vanna_bullish", "wk_dgex_sticky", "wk_zomma_stabilizing",
    "wk_vega_elevated",

    # ===== CROSS-EXPIRY DIVERGENCE (6 features) =====
    "gamma_0dte_vs_wk",    # sign(0dte) != sign(wk) → breakout potential
    "vanna_0dte_vs_wk",    # flow direction mismatch
    "dgex_0dte_vs_wk",     # stability vs instability mismatch
    "delta_0dte_vs_wk",    # directional bias conflict
    "vega_0dte_vs_wk",     # vega exposure mismatch
    "vomma_0dte_vs_wk",    # vomma convexity mismatch

    # ===== IB + MARKET CONTEXT (22 features) =====
    # IB features (8)
    "price_vs_ib_high", "price_vs_ib_low", "ib_range_pct",
    "near_ib_high", "near_ib_low", "above_ib", "below_ib", "in_ib_range",
    # Fibonacci extensions (6) — bullish + bearish
    "dist_fib_127_up", "dist_fib_161_up", "dist_fib_200_up",
    "dist_fib_127_dn", "dist_fib_161_dn", "dist_fib_200_dn",
    # IV features (3)
    "atm_iv", "iv_zscore", "iv_percentile",
    # VIX (3)
    "vix_spot", "vix_gamma", "vix_regime",
    # Market context (2)
    "rsi", "vol_relative",

    # ===== RBF CONFLUENCES (7 features) =====
    "confluence_ib_high_max_gamma",     # IB high near max gamma wall
    "confluence_ib_low_min_gamma",      # IB low near min gamma
    "confluence_ib_high_max_vega",      # IB high near max vega
    "confluence_ib_low_max_dgex",       # IB low near max DGEX
    "confluence_fib127_bull_max_gamma",  # Fib 1.272 up near max gamma
    "confluence_fib161_bull_max_vega",   # Fib 1.618 up near max vega
    "confluence_fib127_bear_min_gamma",  # Fib 1.272 dn near min gamma
    "confluence_fib161_bear_max_vomma",  # Fib 1.618 dn near max vomma
    "confluence_fib161_bull_max_vomma",  # Fib 1.618 up near max vomma
    "confluence_fib127_bear_min_dgex",   # Fib 1.272 dn near min DGEX
    "confluence_fib127_bull_max_dgex",   # Fib 1.272 up near max DGEX
    "confluence_fib161_bear_min_dgex",   # Fib 1.618 dn near min DGEX
    "confluence_fib161_bull_max_dgex",   # Fib 1.618 up near max DGEX

    # ===== ENGINEERED FEATURES (13 features) =====
    # Ratios (6) — includes Vega/Vomma ratios
    "gamma_vanna_ratio",   # net_gamma / |net_vanna|
    "dgex_gamma_ratio",    # net_dgex / |net_gamma|
    "charm_vanna_ratio",   # net_charm / |net_vanna|
    "delta_gamma_ratio",   # net_delta / |net_gamma|
    "vega_gamma_ratio",    # net_vega / |net_gamma|
    "vomma_vega_ratio",    # net_vomma / |net_vega|
    # Temporal Deltas (7) — includes Vega/Vomma changes
    "gamma_change",        # Change in net_gamma
    "vanna_change",        # Change in net_vanna
    "dgex_change",         # Change in net_dgex
    "delta_change",        # Change in net_delta
    "spot_change",         # Price momentum
    "vega_change",         # Change in net_vega
    "vomma_change",        # Change in net_vomma
    # Cross-Features (2 — unchanged)
    "gamma_momentum",      # gamma_change * sign(net_gamma)
    "price_vs_dgex_magnet" # spot_change * sign(dist_to_max_dgex)
]


# --- TEST ---
if __name__ == "__main__":
    print("=" * 70)
    print("HYBRID ATTENTION-MLP TRADING MODEL TEST")
    print("=" * 70)
    
    device = get_device()
    
    num_features = len(FEATURE_COLUMNS)
    print(f"Total features detected: {num_features}")

    for name, config in HYBRID_CONFIGS.items():
        print(f"\n{'='*50}")
        print(f"  {name.upper()} Hybrid Model")
        print(f"{'='*50}")
        
        # Usamos el tamaño real de tu array de features
        model = get_hybrid_model(name, input_size=num_features)  
        model.to(device)
        
        # Count parameters
        total_params = sum(p.numel() for p in model.parameters())
        
        print(f"  embed_dim:   {config['embed_dim']}")
        print(f"  num_heads:   {config['num_heads']}")
        print(f"  hidden:      {config['hidden_dims']}")
        print(f"  dropout:     {config['dropout']}")
        print(f"  Parameters:  {total_params:,} ({total_params/1e3:.0f}K)")
        
        # Test forward pass (Tensor del tamaño exacto)
        test_input = torch.randn(64, num_features).to(device)
        
        model.eval()
        with torch.no_grad():
            output, time_pred, attention = model(test_input, return_attention=True)
            probs = F.softmax(output, dim=-1)
        
        print(f"  Input:       {test_input.shape}")
        print(f"  Output:      {output.shape}")
        print(f"  Time Pred:   {time_pred.shape}")
        print(f"  Attention:   {attention.shape}")
        print(f"  Probs sum:   {probs[0].sum().item():.4f}")
        
        # Show top attended features for first sample
        top_features = attention[0].argsort(descending=True)[:5]
        print(f"  Top 5 features (sample 1): {top_features.tolist()}")

    print("\n" + "=" * 70)
    print("All Hybrid models working!")
    print("=" * 70)
    
    # Feature importance visualization
    print("\n--- Feature Importance Example ---")
    model = get_hybrid_model("small", input_size=num_features).to(device)
    model.eval()
    
    # Simulate a sample with high gamma and near IB high
    sample = torch.zeros(1, num_features).to(device)
    # Buscamos los índices dinámicamente por si cambias el orden de FEATURE_COLUMNS
    idx_gamma = FEATURE_COLUMNS.index("net_gamma")
    idx_price_ib = FEATURE_COLUMNS.index("price_vs_ib_high")
    idx_near_ib = FEATURE_COLUMNS.index("near_ib_high")
    
    sample[0, idx_gamma] = 2.0   # net_gamma high
    sample[0, idx_price_ib] = 0.5  # price_vs_ib_high
    sample[0, idx_near_ib] = 1.0  # near_ib_high
    
    with torch.no_grad():
        _, _, attention = model(sample, return_attention=True)
    
    print("Feature attention for high gamma + near IB high sample:")
    for i, (feat, weight) in enumerate(zip(FEATURE_COLUMNS, attention[0].cpu().numpy())):
        if weight > 0.04:  # Only show significant
            print(f"  {feat:20s}: {weight:.3f}")
