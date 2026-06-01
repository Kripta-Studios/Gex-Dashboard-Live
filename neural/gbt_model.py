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
import re
import lightgbm as lgb
from hybrid_model import FeatureNormalizer
from neural.signal_policy import get_independent_signals

MIN_STRICT_WF_AVG_PF = float(os.environ.get("GBT_MIN_STRICT_WF_AVG_PF", "1.25"))
MIN_STRICT_WF_RANK_PF = float(os.environ.get("GBT_MIN_STRICT_WF_RANK_PF", "0.0"))
MIN_STRICT_WF_VALIDATION_TRADES = int(os.environ.get("GBT_MIN_STRICT_WF_VALIDATION_TRADES", "20"))
MAX_STRICT_WF_RANK_PF = float(os.environ.get("GBT_MAX_STRICT_WF_RANK_PF", "5.0"))
STRICT_WF_TOP_N = int(os.environ.get("GBT_STRICT_WF_TOP_N", "10"))
STRICT_WF_RECENCY_POWER = float(os.environ.get("GBT_STRICT_WF_RECENCY_POWER", "2.0"))


def _parse_ticker_overrides(env_name: str) -> dict:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return {}
    overrides = {}
    for part in raw.split(","):
        if ":" not in part:
            continue
        ticker, value = part.split(":", 1)
        ticker = ticker.strip().upper()
        value = value.strip()
        if ticker and value:
            overrides[ticker] = value
    return overrides


def _ticker_float(env_name: str, ticker: str | None, default: float) -> float:
    value = _parse_ticker_overrides(env_name).get((ticker or "").upper())
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _ticker_int(env_name: str, ticker: str | None, default: int) -> int:
    value = _parse_ticker_overrides(env_name).get((ticker or "").upper())
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _infer_ticker_from_model_path(model_path: str) -> str | None:
    name = os.path.basename(str(model_path)).upper()
    match = re.search(r"_(SPX|SPY|QQQ)(?:_HISTORY)?\.JOBLIB$", name)
    return match.group(1) if match else None


# ═══════════════════════════════════════════════════════════════
# SINGLE GBT MODEL
# ═══════════════════════════════════════════════════════════════
class GBTModel:
    """Wrapper around LightGBM classifiers (LONG and SHORT) with optional metadata and calibrators."""

    def __init__(self, model_long: lgb.LGBMClassifier = None, model_short: lgb.LGBMClassifier = None,
                 metadata: dict = None, normalizer: FeatureNormalizer = None, calibrators: dict = None,
                 model: lgb.LGBMClassifier = None):
        self.model_long = model_long
        self.model_short = model_short
        self.model = model
        self.metadata = metadata or {}
        self.normalizer = normalizer
        self.calibrators = calibrators or {}

    def predict_proba(self, X: np.ndarray, is_up_day: np.ndarray = None) -> np.ndarray:
        """
        Return class probabilities [N, 3].
        Index 0: SHORT, Index 1: HOLD, Index 2: LONG
        """
        if getattr(self, 'model', None) is not None:
            return self.model.predict_proba(X)

        import pandas as pd
        # LightGBM predict_proba returns [N, 2] for binary classification. Index 1 is the positive class.
        p_long_raw = self.model_long.predict_proba(X)[:, 1]
        p_short_raw = self.model_short.predict_proba(X)[:, 1]

        p_long = p_long_raw.copy()
        p_short = p_short_raw.copy()

        # Apply global calibration if available. These calibrators are fitted on
        # the walk-forward calibration split, before the honest selection split.
        cal_long_global = self.calibrators.get("long") if self.calibrators else None
        cal_short_global = self.calibrators.get("short") if self.calibrators else None
        if cal_long_global:
            p_long = cal_long_global.predict(p_long)
        if cal_short_global:
            p_short = cal_short_global.predict(p_short)

        # Apply regime-specific calibration if available.
        if self.calibrators and is_up_day is not None and not (cal_long_global or cal_short_global):
            # Calibrate LONG
            cal_long_up = self.calibrators.get("long_up")
            cal_long_down = self.calibrators.get("long_down")
            if cal_long_up and cal_long_down:
                if is_up_day.any():
                    p_long[is_up_day] = cal_long_up.predict(p_long[is_up_day])
                if (~is_up_day).any():
                    p_long[~is_up_day] = cal_long_down.predict(p_long[~is_up_day])
            elif cal_long_up: # Fallback if only one calibrator
                if len(p_long) > 0:
                    p_long = cal_long_up.predict(p_long)

            # Calibrate SHORT
            cal_short_up = self.calibrators.get("short_up")
            cal_short_down = self.calibrators.get("short_down")
            if cal_short_up and cal_short_down:
                if is_up_day.any():
                    p_short[is_up_day] = cal_short_up.predict(p_short[is_up_day])
                if (~is_up_day).any():
                    p_short[~is_up_day] = cal_short_down.predict(p_short[~is_up_day])
            elif cal_short_up:
                if len(p_short) > 0:
                    p_short = cal_short_up.predict(p_short)

        # Fill missing with 0 and cap at 1.0
        p_long = np.nan_to_num(p_long, nan=0.0)
        p_short = np.nan_to_num(p_short, nan=0.0)
        p_long = np.clip(p_long, 0.0, 1.0)
        p_short = np.clip(p_short, 0.0, 1.0)

        # Convert to 3-class distribution
        p_hold = np.maximum(0.0, 1.0 - (p_long + p_short))

        # Normalize to ensure sum is 1
        total = p_short + p_hold + p_long + 1e-8
        return np.column_stack([p_short / total, p_hold / total, p_long / total])

    def predict(self, X: np.ndarray, is_up_day: np.ndarray = None) -> np.ndarray:
        """Return class predictions [N] (0=SHORT, 1=HOLD, 2=LONG)."""
        probs = self.predict_proba(X, is_up_day)
        preds, _ = get_independent_signals(probs, base_confidence=None)
        return preds


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

    def __init__(self, models: list, ticker: str | None = None):
        """
        Args:
            models: list of GBTModel instances
        """
        self.models = models
        self.ticker = ticker
        self.min_strict_wf_avg_pf = _ticker_float(
            "GBT_TICKER_MIN_STRICT_WF_AVG_PF", ticker, MIN_STRICT_WF_AVG_PF
        )
        self.min_strict_wf_rank_pf = _ticker_float(
            "GBT_TICKER_MIN_STRICT_WF_RANK_PF", ticker, MIN_STRICT_WF_RANK_PF
        )
        self.min_strict_wf_validation_trades = _ticker_int(
            "GBT_TICKER_MIN_STRICT_WF_VALIDATION_TRADES", ticker, MIN_STRICT_WF_VALIDATION_TRADES
        )
        self.max_strict_wf_rank_pf = _ticker_float(
            "GBT_TICKER_MAX_STRICT_WF_RANK_PF", ticker, MAX_STRICT_WF_RANK_PF
        )
        self.strict_wf_top_n = _ticker_int(
            "GBT_TICKER_STRICT_WF_TOP_N", ticker, STRICT_WF_TOP_N
        )
        self.strict_wf_recency_power = _ticker_float(
            "GBT_TICKER_STRICT_WF_RECENCY_POWER", ticker, STRICT_WF_RECENCY_POWER
        )
        self._device = torch.device("cpu")

    @staticmethod
    def _to_feature_frame(X: np.ndarray, model):
        import pandas as pd

        if isinstance(X, pd.DataFrame):
            return X

        if isinstance(X, np.ndarray):
            try:
                from hybrid_model import FEATURE_COLUMNS
                # Handle case where X was passed as full array
                if X.shape[1] == len(FEATURE_COLUMNS):
                    X_df = pd.DataFrame(X, columns=FEATURE_COLUMNS)
                    
                    if hasattr(model, 'metadata') and model.metadata and "cols" in model.metadata:
                        return X_df[model.metadata["cols"]]
                    
                    if hasattr(model, 'normalizer') and model.normalizer and getattr(model.normalizer, 'feature_names', None):
                        return X_df[model.normalizer.feature_names]
                        
                    if hasattr(model, 'model_long') and model.model_long and hasattr(model.model_long, 'feature_name_'):
                        return X_df[model.model_long.feature_name_]
                        
                    return X_df
            except Exception:
                pass
                
        return X

    def _group_models_by_normalizer(self, eligible_models: list):
        grouped = {}
        for idx, model in enumerate(eligible_models):
            window_idx = model.metadata.get("window_idx")
            if window_idx is not None:
                key = ("window", int(window_idx))
            elif model.normalizer is None:
                key = ("raw", idx)
            else:
                key = ("model", idx)

            if key not in grouped:
                grouped[key] = {
                    "normalizer": model.normalizer,
                    "models": [],
                }
            grouped[key]["models"].append(model)
        return grouped.values()

    def predict_proba(self, X: np.ndarray, date: str = None, is_up_day: np.ndarray = None) -> np.ndarray:
        """
        Average probabilities across ensemble. Returns [N, 3].

        Args:
            X: Raw feature matrix. Each eligible model applies its own frozen
               walk-forward normalizer before inference.
            date: Optional 'YYYYMMDD' string. If provided, only models trained
                  BEFORE this date (cutoff_date < date) are used.
            is_up_day: Boolean array [N] indicating if the day is an UP day for calibration.
        """
        X_np = np.asarray(X, dtype=np.float32)

        # Filter models by date if requested
        eligible_models = self.models
        if date is not None:
            # Convert YYYYMMDD string to int for comparison
            d_val = int(date.replace('-', '').replace('/', ''))

            # Find all models whose selection data was available strictly before
            # this date. Newer ensembles set available_date to the end of the
            # validation/test window used for ranking. Older model artifacts do
            # not have that metadata, so they fall back to cutoff_date for
            # backwards compatibility.
            past_models = []
            for m in self.models:
                metadata = m.metadata or {}
                if metadata.get('available_date', metadata.get('cutoff_date', 0)) >= d_val:
                    continue
                if metadata.get('is_fallback', False):
                    continue

                avg_pf = float(metadata.get('avg_pf', metadata.get('rank_pf', 0.0)))
                rank_pf = float(metadata.get('rank_pf', min(avg_pf, self.max_strict_wf_rank_pf)))
                validation_trades = int(metadata.get('total_validation_trades', self.min_strict_wf_validation_trades))
                if validation_trades < self.min_strict_wf_validation_trades:
                    continue
                if avg_pf < self.min_strict_wf_avg_pf:
                    continue
                if rank_pf < self.min_strict_wf_rank_pf:
                    continue
                past_models.append(m)

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
                    avg_pf = models_in_window[0].metadata.get('rank_pf', models_in_window[0].metadata.get('avg_pf', 0.0))
                    avg_pf = min(float(avg_pf), self.max_strict_wf_rank_pf)
                    recency = (widx / max_idx) ** self.strict_wf_recency_power
                    rank_score = avg_pf * recency
                    scored_windows.append((rank_score, models_in_window))

                # Sort descending by rank_score and take the configured top-N windows.
                scored_windows.sort(key=lambda x: x[0], reverse=True)
                top_n = max(1, self.strict_wf_top_n)
                top_windows = scored_windows[:top_n]

                # Flatten the selected models into eligible_models
                eligible_models = [m for w in top_windows for m in w[1]]
            else:
                # Strict walk-forward means no deployed model was available yet.
                # Return HOLD instead of leaking the oldest future model backward.
                return np.tile(np.array([0.0, 1.0, 0.0], dtype=np.float32), (len(X_np), 1))

        if not eligible_models:
            raise ValueError("No models available in ensemble.")

        # Determine is_up_day if not provided. We might need a heuristic if not provided.
        # But we'll assume the caller (hybrid_model.py or predict wrapper) will pass it,
        # or we default to False.
        if is_up_day is None:
            is_up_day = np.zeros(len(X_np), dtype=bool)

        probs_per_model = []
        for group in self._group_models_by_normalizer(eligible_models):
            normalizer = group["normalizer"]
            
            # Filter features BEFORE normalizing to avoid broadcasting mismatch
            X_group = self._to_feature_frame(X_np, group["models"][0])
            import pandas as pd
            if isinstance(X_group, pd.DataFrame):
                X_group = X_group.values

            if normalizer is not None:
                X_group = normalizer.transform(X_group)

            for model in group["models"]:
                probs_per_model.append(model.predict_proba(X_group, is_up_day=is_up_day))

        probs = np.stack(probs_per_model, axis=0)
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
            'model': getattr(m, 'model', None),
            'model_long': m.model_long,
            'model_short': m.model_short,
            'calibrators': m.calibrators,
            'metadata': m.metadata,
            'normalizer_state': _serialize_normalizer_state(m.normalizer or normalizer),
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
        if isinstance(o, dict) and ('model_long' in o or 'model' in o):
            # Modern format with metadata
            model_normalizer = _deserialize_normalizer_state(o.get('normalizer_state'))

            # Compatibility with older format (single model)
            if 'model_long' in o and o['model_long'] is not None:
                models.append(GBTModel(o['model_long'] if o.get('model_short') is not None else None, o.get('model_short'), o.get('metadata'), model_normalizer or normalizer, o.get('calibrators'), o.get('model') or (o['model_long'] if o.get('model_short') is None else None)))
            elif 'model' in o and o['model'] is not None:
                models.append(GBTModel(model=o['model'], metadata=o.get('metadata'), normalizer=model_normalizer or normalizer))
            else:
                # Old format
                old_gbt = GBTModel(None, None, o.get('metadata'), model_normalizer or normalizer)
                old_gbt.model = o['model']
                old_gbt.predict_proba = lambda X, is_up_day=None: old_gbt.model.predict_proba(X)
                old_gbt.predict = lambda X, is_up_day=None: old_gbt.model.predict(X)
                models.append(old_gbt)
        else:
            # Legacy format (just the classifier)
            old_gbt = GBTModel(None, None, None, normalizer)
            old_gbt.model = o
            old_gbt.predict_proba = lambda X, is_up_day=None: old_gbt.model.predict_proba(X)
            old_gbt.predict = lambda X, is_up_day=None: old_gbt.model.predict(X)
            models.append(old_gbt)

    ticker = _infer_ticker_from_model_path(model_path)
    ensemble = GBTEnsemble(models, ticker=ticker)

    ticker_suffix = f" for {ticker}" if ticker else ""
    print(f"  [GBT] Loaded {len(models)} models{ticker_suffix} from {model_path}")

    return ensemble, normalizer


def _serialize_normalizer_state(normalizer: FeatureNormalizer) -> dict | None:
    if normalizer is None or normalizer.medians is None:
        return None

    return {
        "medians": np.asarray(normalizer.medians),
        "iqrs": np.asarray(normalizer.iqrs),
        "p_low": np.asarray(normalizer.p_low),
        "p_high": np.asarray(normalizer.p_high),
        "log_mask": np.asarray(normalizer.log_mask) if normalizer.log_mask is not None else np.array([]),
        "feature_names": np.asarray(normalizer.feature_names if normalizer.feature_names is not None else []),
        "clip_value": float(getattr(normalizer, "clip_value", 5.0)),
        "winsorize_p": tuple(getattr(normalizer, "winsorize_p", (1.0, 99.0))),
    }


def _deserialize_normalizer_state(state: dict | None) -> FeatureNormalizer | None:
    if not state:
        return None

    normalizer = FeatureNormalizer(
        clip_value=float(state.get("clip_value", 5.0)),
        winsorize_p=tuple(state.get("winsorize_p", (1.0, 99.0))),
    )
    normalizer.medians = np.asarray(state["medians"])
    normalizer.iqrs = np.asarray(state["iqrs"])
    normalizer.p_low = np.asarray(state["p_low"])
    normalizer.p_high = np.asarray(state["p_high"])
    
    log_mask = state.get("log_mask")
    if log_mask is not None and len(log_mask) > 0:
        normalizer.log_mask = np.asarray(log_mask)
    else:
        normalizer.log_mask = None

    feature_names = state.get("feature_names")
    if feature_names is not None and len(feature_names) > 0:
        normalizer.feature_names = np.asarray(feature_names).tolist()
    else:
        normalizer.feature_names = None

    return normalizer
