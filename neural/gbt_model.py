"""
GBT Model — LightGBM wrapper with PyTorch-compatible interface.

Provides the same __call__ signature as EnsembleTradingModel so that
RL integration, episode generation, and diagnostics work unchanged.

Interface:
    model(x_tensor) -> (logits_tensor, time_pred_tensor)
    model.predict_proba(X_numpy) -> probabilities [N, 3]
"""

import numpy as np
import torch
import joblib
import os
import lightgbm as lgb
from hybrid_model import FeatureNormalizer


# ═══════════════════════════════════════════════════════════════
# SINGLE GBT MODEL
# ═══════════════════════════════════════════════════════════════
class GBTModel:
    """Wrapper around a single LightGBM classifier with optional metadata."""

    def __init__(self, lgb_model: lgb.LGBMClassifier = None, metadata: dict = None):
        self.model = lgb_model
        self.metadata = metadata or {}

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return class probabilities [N, 3]."""
        return self.model.predict_proba(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return class predictions [N]."""
        return self.model.predict(X)


# ═══════════════════════════════════════════════════════════════
# GBT ENSEMBLE
# ═══════════════════════════════════════════════════════════════
class GBTEnsemble:
    """
    Ensemble of GBT models that mimics PyTorch model interface.

    Averages predicted probabilities across all constituent models,
    then converts to logit-scale tensors for compatibility with
    downstream code expecting (logits, time_pred) tuples.
    """

    def __init__(self, models: list):
        """
        Args:
            models: list of GBTModel instances
        """
        self.models = models
        self._device = torch.device("cpu")

    def predict_proba(self, X: np.ndarray, date: str = None) -> np.ndarray:
        """
        Average probabilities across ensemble. Returns [N, 3].
        
        Args:
            X: Input features
            date: Optional 'YYYYMMDD' string. If provided, only models trained 
                  BEFORE this date (cutoff_date < date) are used.
        """
        import pandas as pd
        
        # Filter models by date if requested
        eligible_models = self.models
        if date is not None:
            # Convert YYYYMMDD string to int for comparison
            d_val = int(date.replace('-', '').replace('/', ''))
            
            # Find all models trained strictly before this date
            past_models = [
                m for m in self.models 
                if m.metadata.get('cutoff_date', 0) < d_val
            ]
            
            if past_models:
                from collections import defaultdict
                # Group models by window_idx
                windows = defaultdict(list)
                for m in past_models:
                    windows[m.metadata.get('window_idx', 0)].append(m)
                
                # Re-calculate rank_score (PF * recency^2) relative to current max_idx
                max_idx = max(windows.keys()) if windows else 1
                if max_idx == 0:
                    max_idx = 1
                scored_windows = []
                for widx, models_in_window in windows.items():
                    avg_pf = models_in_window[0].metadata.get('avg_pf', 0.0)
                    recency = (widx / max_idx) ** 2
                    rank_score = avg_pf * recency
                    scored_windows.append((rank_score, models_in_window))
                
                # Sort descending by rank_score and take Top 10 windows
                scored_windows.sort(key=lambda x: x[0], reverse=True)
                top_10 = scored_windows[:10]
                
                # Flatten the selected models into eligible_models
                eligible_models = [m for w in top_10 for m in w[1]]
            else:
                # Fallback if no models are old enough: use the oldest one available
                oldest_model = min(self.models, key=lambda m: m.metadata.get('cutoff_date', 99999999))
                eligible_models = [oldest_model]

        if not eligible_models:
            raise ValueError("No models available in ensemble.")

        # Convert to DataFrame to avoid LightGBM feature name warnings
        if not isinstance(X, pd.DataFrame):
            try:
                # Extract feature names from the underlying LGBM model
                feature_names = eligible_models[0].model.feature_name_
                X = pd.DataFrame(X, columns=feature_names)
            except (AttributeError, IndexError):
                pass  # Fallback to numpy if feature names aren't available

        probs = np.stack([m.predict_proba(X) for m in eligible_models], axis=0)
        return probs.mean(axis=0)

    def __call__(self, x):
        """
        PyTorch-compatible forward pass.

        Args:
            x: torch.Tensor [N, D] or np.ndarray [N, D]

        Returns:
            (logits, time_pred) tuple of torch.Tensors
            - logits: [N, 3] — log-probabilities (compatible with softmax)
            - time_pred: [N, 2] — dummy (mu=60.0, log_sigma=0.0)

        WARNING: logits are LOG-PROBABILITIES, not raw logits.
        Downstream code should apply softmax() EXACTLY ONCE to recover
        the original probabilities. Applying softmax twice will produce
        a near-uniform distribution and distort predictions.
        For direct probabilities, use predict_proba() instead.
        """
        if isinstance(x, torch.Tensor):
            X_np = x.detach().cpu().numpy()
        else:
            X_np = x

        probs = self.predict_proba(X_np)

        # Convert probabilities → log-probabilities so that downstream
        # softmax(log_probs) recovers the original probabilities.
        # Without this, softmax treats raw probs as logits and
        # distorts e.g. [0, 1, 0] → [0.21, 0.58, 0.21].
        eps = 1e-8
        logits = np.log(np.clip(probs, eps, 1.0))

        # Dummy time predictions (GBT doesn't predict time-to-target)
        # mu=60.0 minutes (neutral), log_sigma=0.0 (moderate uncertainty)
        time_pred = np.column_stack([
            np.full(len(X_np), 60.0),
            np.full(len(X_np), 0.0)
        ])

        logits_t = torch.FloatTensor(logits)
        time_t = torch.FloatTensor(time_pred)

        return logits_t, time_t

    # ── PyTorch compatibility stubs ──────────────────────────────
    def eval(self):
        """No-op for compatibility with PyTorch code."""
        return self

    def train(self, mode=True):
        """No-op for compatibility."""
        return self

    def to(self, device):
        """No-op — GBT runs on CPU. Store device for compatibility."""
        if isinstance(device, str):
            self._device = torch.device(device)
        else:
            self._device = device
        return self

    def parameters(self):
        """Return empty iterator — GBT has no PyTorch parameters."""
        return iter([])

    def state_dict(self):
        """Not applicable for GBT. Raises clear error."""
        raise NotImplementedError("GBT models use joblib, not state_dict")


# ═══════════════════════════════════════════════════════════════
# SAVE / LOAD
# ═══════════════════════════════════════════════════════════════
def save_gbt_ensemble(ensemble: GBTEnsemble, normalizer: FeatureNormalizer,
                      model_path: str, norm_path: str):
    """
    Save GBT ensemble and normalizer.

    Model is saved as .joblib (list of LGBMClassifier objects).
    Normalizer is saved as .npz (same as before).
    """
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    os.makedirs(os.path.dirname(norm_path), exist_ok=True)

    # Save as list of dictionaries { 'model': classifier, 'metadata': dict }
    # This remains compatible with joblib but allows rich metadata
    serialized = []
    for m in ensemble.models:
        serialized.append({
            'model': m.model,
            'metadata': m.metadata
        })
        
    joblib.dump(serialized, model_path)

    if normalizer is not None:
        normalizer.save(norm_path)

    print(f"  [GBT] Saved {len(serialized)} models with metadata to {model_path}")


def load_gbt_ensemble(model_path: str, norm_path: str) -> tuple:
    """
    Load GBT ensemble and normalizer.

    Returns:
        (GBTEnsemble, FeatureNormalizer) tuple
    """
    normalizer = FeatureNormalizer()
    normalizer.load(norm_path)

    objs = joblib.load(model_path)

    if not isinstance(objs, list):
        objs = [objs]

    models = []
    for o in objs:
        if isinstance(o, dict) and 'model' in o:
            # Modern format with metadata
            models.append(GBTModel(o['model'], o.get('metadata')))
        else:
            # Legacy format (just the classifier)
            models.append(GBTModel(o))
            
    ensemble = GBTEnsemble(models)

    print(f"  [GBT] Loaded {len(models)} models from {model_path}")

    return ensemble, normalizer
