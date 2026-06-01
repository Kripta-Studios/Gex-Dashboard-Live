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


# ═══════════════════════════════════════════════════════════════
# FEATURE CLASSIFICATION: DIFFUSION vs REGIME
# ═══════════════════════════════════════════════════════════════
# Regime features: binary, categorical, or low-frequency structural
# indicators that represent discrete market regime (S_t in the paper).
# Diffusion features: continuous variables representing the normal
# flow of the market state (X_t in the paper).

REGIME_FEATURES = {
    "gamma_regime", "vanna_bullish", "charm_bullish", "dgex_sticky",
    "zomma_stabilizing", "vega_elevated", "near_min_vanna",
    "near_ib_high", "near_ib_low", "above_ib", "below_ib", "in_ib_range",
    "wk_gamma_regime", "wk_vanna_bullish", "wk_dgex_sticky", "wk_zomma_stabilizing",
    "vix_regime", "rvol_regime", "gap_direction", "is_opex_week",
    "is_quarterly_opex_week", "wonham_trend_prob",
    # ── Level identity (discrete → regime stream) ──
    "nearest_level_id",         # categorical 0-8, encoded by LevelContextEncoder
}

# ═══════════════════════════════════════════════════════════════
# REGIME CROSS-ATTENTION LAYER
# ═══════════════════════════════════════════════════════════════
class RegimeCrossAttention(nn.Module):
    """
    Cross-Attention where Regime queries Diffusion.
    
    Implements the econometric intuition: "Given the current market regime
    (Query from S_regime), which continuous state variables (Keys from X_diff)
    should the model attend to?"
    
    Q = Linear(regime_embeddings)
    K, V = Linear(diffusion_embeddings)
    """
    
    def __init__(self, n_diff: int, n_regime: int, embed_dim: int = 64,
                 num_heads: int = 4, dropout: float = 0.2):
        super().__init__()
        self.n_diff = n_diff
        self.n_regime = n_regime
        self.embed_dim = embed_dim
        
        # Embed each scalar feature into embed_dim
        self.diff_embed = nn.Linear(1, embed_dim)
        self.regime_embed = nn.Linear(1, embed_dim)
        
        # Learnable type embeddings (positional analog for features)
        self.diff_type_embed = nn.Embedding(n_diff, embed_dim)
        self.regime_type_embed = nn.Embedding(n_regime, embed_dim)
        
        # Cross-attention: Q=regime, K/V=diffusion
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=embed_dim, num_heads=num_heads,
            dropout=dropout, batch_first=True
        )
        
        self.layer_norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
        
        # Importance query for diffusion (learnable probe)
        self.importance_query = nn.Parameter(torch.randn(1, 1, embed_dim))
        
        # Output projection
        self.output_proj = nn.Linear(embed_dim * 2, embed_dim)
        self.output_norm = nn.LayerNorm(embed_dim * 2)
    
    def forward(self, x_diff, x_regime, return_attention=False):
        """
        Args:
            x_diff:   (batch, n_diff) continuous features
            x_regime: (batch, n_regime) regime features
        Returns:
            attended: (batch, embed_dim) cross-attended representation
            attn_weights: optional (batch, n_regime, n_diff) cross-attention map
        """
        batch = x_diff.shape[0]
        
        # Embed diffusion features: (batch, n_diff, embed_dim)
        d_emb = self.diff_embed(x_diff.unsqueeze(-1))
        d_idx = torch.arange(self.n_diff, device=x_diff.device)
        d_emb = d_emb + self.diff_type_embed(d_idx).unsqueeze(0)
        
        # Embed regime features: (batch, n_regime, embed_dim)
        r_emb = self.regime_embed(x_regime.unsqueeze(-1))
        r_idx = torch.arange(self.n_regime, device=x_regime.device)
        r_emb = r_emb + self.regime_type_embed(r_idx).unsqueeze(0)
        
        # Cross-attention: regime queries, diffusion keys/values
        cross_out, cross_weights = self.cross_attn(
            r_emb, d_emb, d_emb, need_weights=True
        )
        r_emb = self.layer_norm(r_emb + self.dropout(cross_out))
        
        # Aggregate: weighted sum via importance query + max pool
        query = self.importance_query.expand(batch, -1, -1)
        _, imp_weights = self.cross_attn(query, r_emb, r_emb, need_weights=True)
        weighted = (r_emb * imp_weights.squeeze(1).unsqueeze(-1)).sum(dim=1)
        pooled = r_emb.max(dim=1)[0]
        
        concat = torch.cat([weighted, pooled], dim=-1)
        output = self.output_proj(self.output_norm(concat))
        
        if return_attention:
            return output, cross_weights
        return output


# ═══════════════════════════════════════════════════════════════
# FiLM-CONDITIONED MLP BLOCK (Regime → Bias/Scale Modulation)
# ═══════════════════════════════════════════════════════════════
class RegimeConditionedMLPBlock(nn.Module):
    """
    FiLM (Feature-wise Linear Modulation) block.
    
    Implements the affine model's core equation:
        H_out = Act(γ(S_regime) ⊙ (W · x_hidden) + β(S_regime))
    
    Where:
        W         = static learned weights (diffusion loading B(τ))
        β(S)      = dynamic bias from regime (stochastic intercept A(τ,S))
        γ(S)      = dynamic scale from regime (regime-dependent sensitivity)
    """
    
    def __init__(self, in_features: int, out_features: int,
                 regime_dim: int, dropout: float = 0.3):
        super().__init__()
        
        # Static diffusion transform (analogous to B(τ)·X_t)
        self.fc = nn.Linear(in_features, out_features, bias=False)
        
        # FiLM generators from regime embedding
        self.gamma_gen = nn.Linear(regime_dim, out_features)  # scale γ(S)
        self.beta_gen = nn.Linear(regime_dim, out_features)   # bias β(S)
        
        self.bn = nn.BatchNorm1d(out_features)
        self.activation = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        
        # Residual if dims match
        self.use_residual = (in_features == out_features)
        
        # Initialize FiLM: gamma → 1.0, beta → 0.0 (identity at init)
        nn.init.ones_(self.gamma_gen.weight.data[:, :min(regime_dim, out_features)])
        nn.init.zeros_(self.gamma_gen.bias.data)
        nn.init.zeros_(self.beta_gen.weight.data)
        nn.init.zeros_(self.beta_gen.bias.data)
    
    def forward(self, x_hidden, regime_emb):
        """
        Args:
            x_hidden:   (batch, in_features) hidden state from diffusion stream
            regime_emb: (batch, regime_dim) processed regime vector
        """
        identity = x_hidden
        
        # Static transform: W · x
        out = self.fc(x_hidden)
        
        # FiLM modulation: γ(S) ⊙ (W·x) + β(S)
        gamma = self.gamma_gen(regime_emb)  # (batch, out_features)
        beta = self.beta_gen(regime_emb)    # (batch, out_features)
        out = gamma * out + beta
        
        # Normalization, activation, dropout
        out = self.bn(out)
        out = self.activation(out)
        out = self.dropout(out)
        
        if self.use_residual:
            out = out + identity
        
        return out


# ═══════════════════════════════════════════════════════════════
# LEGACY BLOCKS (kept for backward checkpoint compatibility)
# ═══════════════════════════════════════════════════════════════
class FeatureAttention(nn.Module):
    """Legacy attention — kept for loading old checkpoints."""
    def __init__(self, num_features=32, embed_dim=64, num_heads=4, dropout=0.2):
        super().__init__()
        self.num_features = num_features
        self.embed_dim = embed_dim
        self.feature_embed = nn.Linear(1, embed_dim)
        self.feature_type_embed = nn.Embedding(num_features, embed_dim)
        self.attention = nn.MultiheadAttention(embed_dim=embed_dim, num_heads=num_heads, dropout=dropout, batch_first=True)
        self.layer_norm_inter = nn.LayerNorm(embed_dim)
        self.layer_norm_final = nn.LayerNorm(embed_dim * 2)
        self.output_proj = nn.Linear(embed_dim * 2, embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.importance_query = nn.Parameter(torch.randn(1, 1, embed_dim))
    def forward(self, x, return_attention=False):
        batch_size = x.shape[0]
        x_expanded = x.unsqueeze(-1)
        x_embed = self.feature_embed(x_expanded)
        feat_indices = torch.arange(self.num_features, device=x.device)
        type_embed = self.feature_type_embed(feat_indices)
        x_embed = x_embed + type_embed.unsqueeze(0)
        attn_output, _ = self.attention(x_embed, x_embed, x_embed, need_weights=True)
        x_embed = self.layer_norm_inter(x_embed + self.dropout(attn_output))
        query = self.importance_query.expand(batch_size, -1, -1)
        _, importance_weights = self.attention(query, x_embed, x_embed, need_weights=True)
        importance_weights = importance_weights.squeeze(1)
        weighted_features = (x_embed * importance_weights.unsqueeze(-1)).sum(dim=1)
        max_features = x_embed.max(dim=1)[0]
        concat_features = torch.cat([weighted_features, max_features], dim=-1)
        output = self.output_proj(self.layer_norm_final(concat_features))
        if return_attention: return output, importance_weights
        return output

class RegularizedMLPBlock(nn.Module):
    """Legacy MLP block — kept for loading old checkpoints."""
    def __init__(self, in_features, out_features, dropout=0.3):
        super().__init__()
        self.fc = nn.Linear(in_features, out_features)
        self.bn = nn.BatchNorm1d(out_features)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()
        self.use_residual = (in_features == out_features)
    def forward(self, x):
        identity = x
        x = self.fc(x)
        x = self.bn(x)
        x = self.activation(x)
        x = self.dropout(x)
        if self.use_residual: x = x + identity
        return x


# ═══════════════════════════════════════════════════════════════
# HYBRID TRADING MODEL — REGIME-SWITCHING AFFINE ARCHITECTURE
# ═══════════════════════════════════════════════════════════════
class HybridTradingModel(nn.Module):
    """
    Dual-stream model based on Regime-Switching Affine framework.
    
    Architecture:
        Stream 1 (Regime S_t):
            regime features → small MLP → regime_emb
        
        Stream 2 (Diffusion X_t):
            diffusion features → CrossAttention(Q=regime, K/V=diffusion)
            → FiLM-conditioned MLP blocks → classifier / time heads
        
    The regime stream acts as a master controller:
        1. Cross-Attention: decides which diffusion features to attend to
        2. FiLM Modulation: shifts bias/scale of each MLP layer
           (implements stochastic intercept A(τ,S_t) + loading B(τ)·X_t)
    """
    
    def __init__(
        self,
        input_size: int = 163,
        embed_dim: int = 64,
        num_heads: int = 4,
        hidden_dims: list = [256, 128, 64],
        dropout: float = 0.3,
        num_classes: int = 3,
    ):
        super().__init__()
        self.input_size = input_size

        # Precompute feature split indices
        self.diffusion_indices = None
        self.regime_indices = None
        self.n_diff = 0
        self.n_regime = 0
        self._build_indices(input_size)

        # ── Level identity encoder (discrete nearest_level_id → embedding) ──
        # nearest_level_id is CATEGORICAL (0-8): there is no ordinal meaning to
        # its integer value, so it must not be treated as a plain float by the
        # regime MLP.  A small Embedding table (16-dim) learns a free vector per
        # level type and is concatenated to regime_emb before the FiLM blocks.
        LEVEL_EMBED_DIM = 16
        self._level_embed_dim = LEVEL_EMBED_DIM  # stored for forward() fallback
        self.level_encoder = nn.Embedding(9, LEVEL_EMBED_DIM)  # 9 level types
        nn.init.normal_(self.level_encoder.weight, std=0.01)

        # Cache the column index of nearest_level_id (set in _build_indices fallback
        # or detected here from FEATURE_COLUMNS).
        self._level_id_feat_idx = -1  # -1 = not found / disabled
        if len(FEATURE_COLUMNS) == input_size:
            try:
                self._level_id_feat_idx = FEATURE_COLUMNS.index("nearest_level_id")
            except ValueError:
                pass  # older dataset — level encoder disabled

        # ── Regime stream: MLP over the scalar regime features ──
        regime_dim_base = max(embed_dim // 2, 16)
        self.regime_mlp = nn.Sequential(
            nn.Linear(self.n_regime, regime_dim_base * 2),
            nn.BatchNorm1d(regime_dim_base * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(regime_dim_base * 2, regime_dim_base),
            nn.BatchNorm1d(regime_dim_base),
            nn.GELU(),
        )

        # Combined regime dim = MLP output + level embedding.
        # THIS is what every FiLM block receives as its conditioning vector.
        regime_dim = regime_dim_base + LEVEL_EMBED_DIM
        self.regime_dim = regime_dim

        # ── Cross-Attention: regime queries diffusion ──
        self.cross_attention = RegimeCrossAttention(
            n_diff=self.n_diff, n_regime=self.n_regime,
            embed_dim=embed_dim, num_heads=num_heads, dropout=dropout
        )

        # ── FiLM-conditioned MLP blocks ──
        # Input: cross-attended features (embed_dim) + raw diffusion (n_diff)
        # Conditioning: regime_dim (= regime_dim_base + LEVEL_EMBED_DIM)
        mlp_input_dim = embed_dim + self.n_diff

        film_blocks = []
        prev_dim = mlp_input_dim
        for hidden_dim in hidden_dims:
            film_blocks.append(
                RegimeConditionedMLPBlock(prev_dim, hidden_dim, regime_dim, dropout)
            )
            prev_dim = hidden_dim
        self.film_mlp = nn.ModuleList(film_blocks)

        # ── Classification head ──
        self.classifier = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.BatchNorm1d(prev_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(prev_dim // 2, num_classes)
        )

        # ── Bayesian time regression head ──
        self.time_head = nn.Sequential(
            nn.Linear(prev_dim, prev_dim // 2),
            nn.BatchNorm1d(prev_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(prev_dim // 2, 2),  # mu, log_sigma
        )

        self._init_weights()
    
    def _build_indices(self, input_size: int):
        """Build diffusion/regime index masks from FEATURE_COLUMNS."""
        diff_idx = []
        reg_idx = []
        
        # Use FEATURE_COLUMNS if available and matching size
        if len(FEATURE_COLUMNS) == input_size:
            for i, col in enumerate(FEATURE_COLUMNS):
                if col in REGIME_FEATURES:
                    reg_idx.append(i)
                else:
                    diff_idx.append(i)
        else:
            # Fallback: last 25% as regime (for dynamic feature filtering)
            n_regime_est = max(4, input_size // 6)
            diff_idx = list(range(input_size - n_regime_est))
            reg_idx = list(range(input_size - n_regime_est, input_size))
        
        self.register_buffer('_diff_idx', torch.tensor(diff_idx, dtype=torch.long))
        self.register_buffer('_reg_idx', torch.tensor(reg_idx, dtype=torch.long))
        self.n_diff = len(diff_idx)
        self.n_regime = len(reg_idx)
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight, gain=0.5)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(self, x, return_attention=False):
        """
        Args:
            x: (batch, input_size) — full feature tensor
        Returns:
            logits: (batch, num_classes)
            time_pred: (batch, 2) — [mu, log_sigma]
            attention: optional cross-attention weights
        """
        # ── Task 1: Bifurcate into diffusion and regime streams ──
        x_diff   = x[:, self._diff_idx]   # (batch, n_diff)
        x_regime = x[:, self._reg_idx]    # (batch, n_regime)

        # ── Regime stream: scalar MLP ──
        regime_emb_base = self.regime_mlp(x_regime)   # (batch, regime_dim_base)

        # ── Level identity: embed discrete nearest_level_id ──
        # If the feature is present (new dataset), look it up in the full feature
        # vector x (not x_regime, since nearest_level_id may be in the diffusion
        # stream depending on classification), clamp to valid range, and embed.
        if self._level_id_feat_idx >= 0:
            level_ids = x[:, self._level_id_feat_idx].long().clamp(0, 8)
            level_emb = self.level_encoder(level_ids)   # (batch, LEVEL_EMBED_DIM)
        else:
            # Fallback: zeros (backward-compat with old checkpoints / old data)
            level_emb = torch.zeros(x.size(0), self._level_embed_dim,
                                    device=x.device, dtype=x.dtype)

        # Concatenate → combined conditioning vector for all FiLM blocks
        regime_emb = torch.cat([regime_emb_base, level_emb], dim=-1)  # (batch, regime_dim)

        # ── Task 2: Cross-Attention (regime queries diffusion) ──
        if return_attention:
            attended, cross_weights = self.cross_attention(
                x_diff, x_regime, return_attention=True)
        else:
            attended = self.cross_attention(x_diff, x_regime)

        # Combine attended representation with raw diffusion (skip connection)
        hidden = torch.cat([attended, x_diff], dim=-1)

        # ── Task 3: FiLM-conditioned MLP ──
        for block in self.film_mlp:
            hidden = block(hidden, regime_emb)

        # ── Output heads ──
        logits = self.classifier(hidden)

        time_params = self.time_head(hidden.detach())
        mu = torch.sigmoid(time_params[:, 0:1])
        log_sigma = time_params[:, 1:2]
        time_pred = torch.cat([mu, log_sigma], dim=-1)

        if return_attention:
            return logits, time_pred, cross_weights
        return logits, time_pred
    
    def predict_proba(self, x):
        logits, _ = self.forward(x)
        return F.softmax(logits, dim=-1)
    
    def predict(self, x):
        logits, time_pred = self.forward(x)
        return F.softmax(logits, dim=-1), time_pred
    
    def get_feature_importance(self, x):
        _, _, attention = self.forward(x, return_attention=True)
        return attention


# --- MODEL CONFIGURATIONS ---
HYBRID_CONFIGS = {
    "micro": {
        "embed_dim": 32,
        "num_heads": 2,
        "hidden_dims": [64, 32],
        "dropout": 0.4,
    },
    "small": {
        "embed_dim": 64,
        "num_heads": 4,
        "hidden_dims": [128, 64, 32],
        "dropout": 0.35,
    },
    "medium": {
        "embed_dim": 128,
        "num_heads": 4,
        "hidden_dims": [256, 128, 64],
        "dropout": 0.3,
    },
    "medium_v2": {
        "embed_dim": 128,
        "num_heads": 8,
        "hidden_dims": [512, 256, 128, 64],
        "dropout": 0.35,
    },
    "medium_optimized": {
        "embed_dim": 128,
        "num_heads": 8,
        "hidden_dims": [256, 128, 64],
        "dropout": 0.40,
    },
    "large": {
        "embed_dim": 256,
        "num_heads": 8,
        "hidden_dims": [512, 256, 128, 64],
        "dropout": 0.25,
    },
}


# --- MODEL FACTORY ---
def get_hybrid_model(model_size: str = "micro", input_size: int = 163) -> HybridTradingModel:
    """Get hybrid model by size name."""
    if model_size not in HYBRID_CONFIGS:
        raise ValueError(f"Unknown size: {model_size}. Choose from: {list(HYBRID_CONFIGS.keys())}")
    
    config = HYBRID_CONFIGS[model_size]
    return HybridTradingModel(input_size=input_size, **config)

def save_hybrid_model(model: nn.Module, normalizer: 'FeatureNormalizer', model_path: str, norm_path: str):
    """Save hybrid model architecture and normalizer state."""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    os.makedirs(os.path.dirname(norm_path), exist_ok=True)
    torch.save(model.state_dict(), model_path)
    if normalizer is not None:
        normalizer.save(norm_path)

class EnsembleTradingModel(nn.Module):
    """Wrapper that averages predictions from multiple identical models trained with different seeds."""
    def __init__(self, models: list):
        super().__init__()
        self.models = nn.ModuleList(models)
        
    def forward(self, x, return_attention=False):
        all_logits = []
        all_times = []
        all_attns = []
        
        for m in self.models:
            if return_attention:
                logits, t_pred, attn = m(x, return_attention=True)
                all_attns.append(attn)
            else:
                logits, t_pred = m(x)
                
            all_logits.append(logits)
            all_times.append(t_pred)
            
        avg_logits = torch.stack(all_logits).mean(dim=0)
        avg_times = torch.stack(all_times).mean(dim=0)
        
        if return_attention:
            avg_attn = torch.stack(all_attns).mean(dim=0)
            return avg_logits, avg_times, avg_attn
        return avg_logits, avg_times

    def predict_proba(self, x):
        logits, _ = self.forward(x)
        return F.softmax(logits, dim=-1)
    
    def predict(self, x):
        logits, time_pred = self.forward(x)
        return F.softmax(logits, dim=-1), time_pred

def save_ensemble(ensemble: EnsembleTradingModel, normalizer: 'FeatureNormalizer', model_path: str, norm_path: str):
    """Save all models in the ensemble and the normalizer."""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    os.makedirs(os.path.dirname(norm_path), exist_ok=True)
    
    state_dicts = [m.state_dict() for m in ensemble.models]
    torch.save(state_dicts, model_path)
    
    if normalizer is not None:
        normalizer.save(norm_path)


def load_hybrid_model(model_path: str, norm_path: str, model_size: str = "micro",
                      device=None) -> tuple:
    """
    Load a single hybrid model and its normalizer.
    Auto-detects if the .pt file is an ensemble (list) and loads only the first model.
    
    Returns:
        (model, normalizer) tuple
    """
    if device is None:
        device = get_device()
    
    normalizer = FeatureNormalizer()
    normalizer.load(norm_path)
    
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Auto-detect: ensemble files are saved as a list of state_dicts
    if isinstance(checkpoint, list):
        print(f"  [!] File contains ensemble ({len(checkpoint)} models). Loading first model.")
        checkpoint = checkpoint[0]
    
    # Detect actual input_size from checkpoint buffers (training may have
    # filtered FEATURE_COLUMNS to only columns present in the parquet)
    cp_input_size = len(checkpoint['_diff_idx']) + len(checkpoint['_reg_idx'])
    if cp_input_size != len(FEATURE_COLUMNS):
        print(f"  [!] Checkpoint input_size={cp_input_size} vs FEATURE_COLUMNS={len(FEATURE_COLUMNS)}. Using checkpoint size.")
    model = get_hybrid_model(model_size, cp_input_size).to(device)
    model.load_state_dict(checkpoint)
    model.eval()
    
    return model, normalizer


def load_ensemble_model(model_path: str, norm_path: str, model_size: str = "micro",
                        device=None) -> tuple:
    """
    Load an ensemble model and its normalizer.
    Auto-detects format:
      - .joblib → GBT ensemble (LightGBM)
      - .pt     → PyTorch MLP ensemble

    Returns:
        (model, normalizer) tuple
    """
    # ── GBT model detection ──
    if model_path.endswith('.joblib'):
        from gbt_model import load_gbt_ensemble
        return load_gbt_ensemble(model_path, norm_path)

    # ── Legacy PyTorch MLP loading ──
    if device is None:
        device = get_device()
    
    normalizer = FeatureNormalizer()
    normalizer.load(norm_path)
    
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Auto-detect: single model files are saved as a dict
    if isinstance(checkpoint, dict):
        print(f"  [!] File contains single model. Wrapping as ensemble of 1.")
        checkpoint = [checkpoint]
    
    # Detect actual input_size from first checkpoint's buffers (training may have
    # filtered FEATURE_COLUMNS to only columns present in the parquet)
    first_sd = checkpoint[0]
    cp_input_size = len(first_sd['_diff_idx']) + len(first_sd['_reg_idx'])
    if cp_input_size != len(FEATURE_COLUMNS):
        print(f"  [!] Checkpoint input_size={cp_input_size} vs FEATURE_COLUMNS={len(FEATURE_COLUMNS)}. Using checkpoint size.")
    
    models = []
    for sd in checkpoint:
        m = get_hybrid_model(model_size, cp_input_size).to(device)
        m.load_state_dict(sd)
        m.eval()
        models.append(m)
    
    ensemble = EnsembleTradingModel(models).to(device)
    ensemble.eval()
    
    return ensemble, normalizer


# --- FEATURE NORMALIZER ---
class FeatureNormalizer:
    """
    Robust Feature Normalizer for 0DTE Trading.
    
    Addresses feature instability and test gaps via:
    1. Log-Transforms: Applies pseudo-log transform (log1p) to large magnitude greeks.
    2. Winsorization: Clips outliers at 1st and 99th percentiles before scaling.
    3. Robust Scaling: Uses Median and IQR (Interquartile Range) instead of Mean/Std.
    4. Causality: Fitted strictly on training window, frozen for test window.
    """
    
    def __init__(self, clip_value: float = 5.0, winsorize_p: tuple = (1.0, 99.0)):
        self.medians = None
        self.iqrs = None
        self.p_low = None
        self.p_high = None
        self.feature_names = None
        self.log_mask = None
        self.clip_value = clip_value
        self.winsorize_p = winsorize_p
    
    def fit(self, features: np.ndarray, feature_names: list = None):
        self.feature_names = feature_names
        
        # Determine which features to log-transform based on magnitude or names
        # NOTE: As of 2026-03, greek features are pre-transformed with safe_log()
        # in collect_training_data_spx_qqq.py. No additional log-transform needed here.
        # Setting log_mask to all-False to avoid double-transforming.
        if feature_names is not None:
            self.log_mask = np.zeros(len(feature_names), dtype=bool)
        else:
            self.log_mask = np.zeros(features.shape[1], dtype=bool)

        features_to_fit = features.copy()
        if self.log_mask is not None and np.any(self.log_mask):
            features_to_fit[:, self.log_mask] = np.sign(features_to_fit[:, self.log_mask]) * np.log1p(np.abs(features_to_fit[:, self.log_mask]))
            
        # 1. Learn 1st and 99th percentiles for Winsorization
        self.p_low = np.percentile(features_to_fit, self.winsorize_p[0], axis=0)
        self.p_high = np.percentile(features_to_fit, self.winsorize_p[1], axis=0)
        
        # Apply winsorization to training data before computing median/IQR
        features_clipped = np.clip(features_to_fit, self.p_low, self.p_high)
        
        # 2. Learn Median and IQR (75th - 25th percentile)
        self.medians = np.median(features_clipped, axis=0)
        q75, q25 = np.percentile(features_clipped, [75, 25], axis=0)
        self.iqrs = q75 - q25
        
        # Prevent division by zero for zero-variance features
        self.iqrs = np.where(self.iqrs == 0, 1.0, self.iqrs)
    
    def transform(self, features: np.ndarray) -> np.ndarray:
        if self.medians is None:
            raise ValueError("Normalizer not fitted")
            
        features_to_transform = features.copy()
        if self.log_mask is not None and np.any(self.log_mask):
            features_to_transform[:, self.log_mask] = np.sign(features_to_transform[:, self.log_mask]) * np.log1p(np.abs(features_to_transform[:, self.log_mask]))
            
        # 1. Winsorize test data using learned training percentiles
        features_clipped = np.clip(features_to_transform, self.p_low, self.p_high)
        
        # 2. Robust Scaling ((X - Median) / IQR)
        scaled = (features_clipped - self.medians) / self.iqrs
        
        # 3. Final safety clip
        normalized = np.clip(scaled, -self.clip_value, self.clip_value)
        
        return normalized
    
    def fit_transform(self, features: np.ndarray, feature_names: list = None) -> np.ndarray:
        self.fit(features, feature_names)
        return self.transform(features)
    
    def save(self, filepath: str):
        np.savez(filepath, 
                 medians=self.medians, 
                 iqrs=self.iqrs,
                 p_low=self.p_low,
                 p_high=self.p_high,
                 log_mask=self.log_mask if self.log_mask is not None else np.array([]),
                 feature_names=np.array(self.feature_names) if self.feature_names else np.array([]))
    
    def load(self, filepath: str):
        data = np.load(filepath, allow_pickle=True)
        # Handle backward compatibility: if old normalizer (means/stds) is loaded, convert or fall back
        if "medians" in data:
            self.medians = data["medians"]
            self.iqrs = data["iqrs"]
            self.p_low = data["p_low"]
            self.p_high = data["p_high"]
            if "log_mask" in data and len(data["log_mask"]) > 0:
                self.log_mask = data["log_mask"]
            else:
                self.log_mask = None
        else:
            # Fallback for old models
            self.medians = data["means"]
            self.iqrs = data["stds"]
            self.p_low = -np.inf * np.ones_like(self.medians)
            self.p_high = np.inf * np.ones_like(self.medians)
            self.log_mask = None
            
        if len(data["feature_names"]) > 0:
            self.feature_names = data["feature_names"].tolist()


FEATURE_COLUMNS = [
    # ── 0DTE Greek exposures (8) ──
    "net_gamma", "net_vanna", "net_charm", "net_dgex", "net_zomma", "net_delta", 
    "signal_persistence_5m", "gamma_regime",
    
    # ── 0DTE Binary / Regime (4) ──
    "vanna_bullish", "charm_bullish", "dgex_sticky", "zomma_stabilizing",
    
    # ── Distances in bps (6) ──
    "dist_to_max_gamma", "dist_to_min_gamma", "dist_to_min_vanna", 
    "dist_to_zero_gamma", "dist_to_max_dgex", "dist_to_min_dgex",
    
    # ── Binary levels (1) ──
    "near_min_vanna",
    
    # ── Weekly features (12) ──
    # NOTE: wk_dist_to_* removed — tautological features (r≈-0.59 with target).
    # They encode (spot - fixed_strike)/spot which is circular with price direction.
    "wk_net_gamma", "wk_net_vanna", "wk_net_charm", "wk_net_dgex", "wk_net_zomma", 
    "wk_net_delta", "wk_net_vega", "wk_net_vomma",
    "wk_gamma_regime", "wk_vanna_bullish", 
    "wk_dgex_sticky", "wk_zomma_stabilizing",
    
    # ── Divergence (6) ──
    "gamma_0dte_vs_wk", "vanna_0dte_vs_wk", "dgex_0dte_vs_wk", 
    "delta_0dte_vs_wk", "charm_0dte_vs_wk", "zomma_0dte_vs_wk",
    "vega_0dte_vs_wk", "vomma_0dte_vs_wk",

    # 📊 Volatility Context Features (3) 📊
    "vix_5d_mean", "vix_5d_std", "atr_5d_norm",
    
    # ── IB & Fibs (14) ──
    "price_vs_ib_high", "price_vs_ib_low", "ib_range_pct", "near_ib_high", 
    "near_ib_low", "above_ib", "below_ib", "in_ib_range",
    "dist_fib_127_up", "dist_fib_161_up", "dist_fib_200_up", 
    "dist_fib_127_dn", "dist_fib_161_dn", "dist_fib_200_dn",
    
    # ── IV / VIX Context (6) ──
    "atm_iv", "iv_zscore", "iv_percentile", "vix_spot", "vix_gamma", "vix_regime",
    
    # ── Technicals (2) ──
    "rsi",
    
    # ── Ratios (6) ──
    "gamma_vanna_ratio", "dgex_gamma_ratio", "charm_vanna_ratio", 
    "delta_gamma_ratio", "vega_gamma_ratio", "vomma_vega_ratio",
    
    # ── Temporal Deltas (9) ──
    "gamma_change", "vanna_change", "dgex_change", "delta_change", 
    "vega_change", "vomma_change", "spot_change", "gamma_momentum", "price_vs_dgex_magnet",
    
    # ── Volatility Griegas (7) ──
    "net_vega", "net_vomma", "vega_elevated", "dist_to_max_vega", 
    "dist_to_min_vega", "dist_to_max_vomma", "dist_to_min_vomma",
    
    # ── Confluences (14) ──
    "confluence_ib_high_max_gamma", "confluence_ib_low_min_gamma", 
    "confluence_ib_high_max_vega", "confluence_ib_low_max_dgex", 
    "confluence_fib127_bull_max_gamma", "confluence_fib161_bull_max_vega", 
    "confluence_fib127_bear_min_gamma", "confluence_fib161_bear_max_vomma", 
    "confluence_fib161_bull_max_vomma", "confluence_fib127_bear_min_vomma", 
    "confluence_fib127_bull_max_dgex", "confluence_fib127_bear_min_dgex", 
    "confluence_fib161_bull_max_dgex", "confluence_fib161_bear_min_dgex",
    
    # ── VRP Regime (3) ──
    "rvol_iv_log", "rvol_trend", "rvol_regime",
    
    # ── Historical IB (15) ──
    "dist_ib_high_D1", "dist_ib_low_D1", "prev_close_vs_ib_D1",
    "dist_ib_high_D2", "dist_ib_low_D2", "prev_close_vs_ib_D2",
    "dist_ib_high_D3", "dist_ib_low_D3", "prev_close_vs_ib_D3",
    "dist_ib_high_D4", "dist_ib_low_D4", "prev_close_vs_ib_D4",
    "dist_ib_high_D5", "dist_ib_low_D5", "prev_close_vs_ib_D5",
    
    # ── Vol-Adjusted Returns (3) ──
    # NOTE: ret_30m_vol_adj removed — correlated r=0.166 with target mostly via
    # autocorrelation (120-min lookahead shares 90/120 bars). Shorter horizons safer.
    "ret_1m_vol_adj", "ret_5m_vol_adj", "ret_15m_vol_adj",
    
    # ── Time & Day Encoding (5) ──
    "time_sin", "time_cos", "minutes_to_close_norm", "dow_sin", "dow_cos",
    
    # ── IB Context & Gap (4) ──
    "ib_range_percentile", "gap_pct", "gap_direction", "overnight_vs_ib_ratio",
    
    # ── OpEx (3) ──
    "days_to_opex_norm", "is_opex_week", "is_quarterly_opex_week",
    
    # ── Greek Dynamics (2) ──
    "charm_accel_weighted", "gamma_speed",
    
    # ── Hilbert Phase (4) ──
    "gamma_phase_sin", "gamma_phase_cos", "gamma_amplitude_ratio", "gamma_phase_delta",
    
    # ── Option Flow (2) ──
    "delta_filtered_pcr", "pcr_derivative_5m",
    
    # ── TLT Proxy (3) ──
    "tlt_ret_1m", "tlt_ret_5m", "tlt_ret_15m",
    
    # ── Historical Confluences (7) ──
    "confluence_d1ibh_max_gamma", "confluence_d1ibl_min_gamma", 
    "confluence_d1ibh_max_dgex", "confluence_d1ibl_min_dgex", 
    "confluence_d1ibh_max_vomma", "confluence_d1ibh_ibh_today", 
    "confluence_d1ibl_ibl_today",
    
    # ── Interactions & Wonham (5) ──
    "speed_x_near_ib_high", "speed_x_near_ib_low",
    "charm_accel_x_near_ib_high", "charm_accel_x_near_ib_low",
    "wonham_trend_prob",

    # ── S/R Price Action (7) ──
    "nearest_level_dist", "level_cluster_density", 
    "momentum_5m_bps", "rejection_bullish", "rejection_bearish",
    "trend_grind_up", "trend_flush_down",

    # ── Explicit S/R state from the collector (8) ──
    # These are current-row support/resistance flags. Do not add max_move,
    # time_to_target or time_to_stop here; those are future outcome fields.
    "bouncing_from_support", "rejecting_resistance",
    "wall_at_fib", "wall_at_ib", "is_touching_fib",
    "is_touching_max_gamma", "is_touching_min_gamma",
    "is_touching_max_dgex",

    # ── Level identity (2) ──
    # nearest_level_id: 0=ib_high, 1=ib_low, 2=fib_127_up, 3=fib_161_up,
    #                   4=fib_200_up, 5=fib_127_dn, 6=fib_161_dn, 7=fib_200_dn, 8=none
    # Encoded by LevelContextEncoder (Embedding table) — NOT treated as a float.
    "nearest_level_id",
    "nearest_level_dist_bps",

    # ── Greek × Level interaction scalars (10) ──
    # greek_value × (1 if near_level else 0): zero except when touching that level.
    # These let the model learn "gamma at fib_up" vs "gamma elsewhere" directly.
    "gamma_x_near_fib_up",
    "gamma_x_near_fib_dn",
    "gamma_x_near_ib",
    "delta_x_near_fib_up",
    "delta_x_near_fib_dn",
    "delta_x_near_ib_high",
    "delta_x_near_ib_low",
    "vanna_x_near_fib_up",
    "vanna_x_near_fib_dn",
    "vanna_x_near_ib",

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
    model = get_hybrid_model("micro", input_size=num_features).to(device)
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
