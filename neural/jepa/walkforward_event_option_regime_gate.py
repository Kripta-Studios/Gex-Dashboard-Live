"""Regime-conditioned abstention gate for event-option trading."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

REGIME_GATE_QUANTILES = (0.20, 0.40, 0.60, 0.80)
REGIME_GATE_DIRECTIONS = ("above", "below")


@dataclass(frozen=True)
class RegimeGateConfig:
    """A predeclared regime gate that abstains from trading outside a quantile band.

    The percentile thresholds are computed on train data only.
    ``direction='above'`` means: trade only when feature >= threshold.
    ``direction='below'`` means: trade only when feature < threshold.
    """
    feature: str
    direction: str  # 'above' or 'below'
    quantile: float  # e.g. 0.20, 0.40, 0.60, 0.80
    threshold: float  # actual percentile value from train

    @property
    def name(self) -> str:
        return f"rg_{self.feature}_{self.direction}_q{self.quantile:.0%}".replace("%", "pct")


NO_REGIME_GATE = None  # sentinel for "no gate applied"


def build_regime_gates(
    train: pd.DataFrame,
    regime_features: list[str],
    allowed_direction: str = "any",
) -> list[RegimeGateConfig | None]:
    """Build regime gate configurations from train-only percentiles.

    Returns a list starting with None (no gate) followed by all
    (feature × direction × quantile) combinations with finite thresholds.
    """
    gates: list[RegimeGateConfig | None] = [NO_REGIME_GATE]
    for feature in regime_features:
        if feature not in train.columns:
            # Raise KeyError if feature is requested but absent from train
            raise KeyError(f"Regime feature {feature!r} not found in dataset columns.")
        
        values = pd.to_numeric(train[feature], errors="coerce")
        # Handle NaN and inf values by excluding them
        finite_mask = np.isfinite(values)
        if not finite_mask.any():
            continue
        values = values[finite_mask]
        
        # Handle feature constant check: if all values are identical, percentiles are identical,
        # which can result in duplicate thresholds. We use a set of values or drop duplicate thresholds.
        unique_vals = np.unique(values)
        if len(unique_vals) <= 1:
            # Constant feature: produce only one representative gate threshold to avoid redundancy
            threshold = float(unique_vals[0])
            directions = REGIME_GATE_DIRECTIONS
            if allowed_direction in ("above", "below"):
                directions = (allowed_direction,)
            for direction in directions:
                gates.append(RegimeGateConfig(
                    feature=feature,
                    direction=direction,
                    quantile=0.50,
                    threshold=threshold,
                ))
            continue

        seen_thresholds = set()
        for quantile in REGIME_GATE_QUANTILES:
            threshold = float(values.quantile(quantile))
            if not np.isfinite(threshold):
                continue
            # Round slightly to prevent floating point instability in key checks
            threshold = round(threshold, 9)
            if threshold in seen_thresholds:
                continue
            seen_thresholds.add(threshold)
            
            directions = REGIME_GATE_DIRECTIONS
            if allowed_direction in ("above", "below"):
                directions = (allowed_direction,)
            for direction in directions:
                gates.append(RegimeGateConfig(
                    feature=feature,
                    direction=direction,
                    quantile=quantile,
                    threshold=threshold,
                ))
    return gates


def apply_regime_gate(
    scored: pd.DataFrame,
    gate: RegimeGateConfig | None,
) -> pd.DataFrame:
    """Filter candidates by regime gate. Returns the full frame when gate is None."""
    if gate is None:
        return scored
    if gate.feature not in scored.columns:
        raise KeyError(f"Gate feature {gate.feature!r} not found in scored DataFrame.")
    
    values = pd.to_numeric(scored[gate.feature], errors="coerce")
    if gate.direction == "above":
        mask = values >= gate.threshold
    elif gate.direction == "below":
        mask = values < gate.threshold
    else:
        raise ValueError(f"Unknown gate direction: {gate.direction}")
    return scored.loc[mask].copy()
