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
    """Wrapper around a single LightGBM classifier."""

    def __init__(self, lgb_model: lgb.LGBMClassifier = None):
        self.model = lgb_model

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

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Average probabilities across ensemble. Returns [N, 3]."""
        import pandas as pd
        
        # Convert to DataFrame to avoid LightGBM feature name warnings
        if not isinstance(X, pd.DataFrame):
            try:
                # Extract feature names from the underlying LGBM model
                feature_names = self.models[0].model.feature_name_
                X = pd.DataFrame(X, columns=feature_names)
            except AttributeError:
                pass  # Fallback to numpy if feature names aren't available

        probs = np.stack([m.predict_proba(X) for m in self.models], axis=0)
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

    # Save list of raw LGBMClassifier objects
    lgb_models = [m.model for m in ensemble.models]
    joblib.dump(lgb_models, model_path)

    if normalizer is not None:
        normalizer.save(norm_path)

    print(f"  [GBT] Saved {len(lgb_models)} models to {model_path}")


def load_gbt_ensemble(model_path: str, norm_path: str) -> tuple:
    """
    Load GBT ensemble and normalizer.

    Returns:
        (GBTEnsemble, FeatureNormalizer) tuple
    """
    normalizer = FeatureNormalizer()
    normalizer.load(norm_path)

    lgb_models = joblib.load(model_path)

    if not isinstance(lgb_models, list):
        lgb_models = [lgb_models]

    models = [GBTModel(m) for m in lgb_models]
    ensemble = GBTEnsemble(models)

    print(f"  [GBT] Loaded {len(models)} models from {model_path}")

    return ensemble, normalizer
