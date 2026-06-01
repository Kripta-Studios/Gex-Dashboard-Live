from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from neural.jepa.features import available_features, load_base_feature_columns


INPUT_FEATURE_CANDIDATES = [
    "gamma_change",
    "vanna_change",
    "dgex_change",
    "delta_change",
    "vega_change",
    "vomma_change",
    "spot_change",
    "gamma_momentum",
    "signal_persistence_5m",
    "momentum_5m_bps",
    "ret_1m_vol_adj",
    "ret_5m_vol_adj",
    "ret_15m_vol_adj",
    "tlt_ret_1m",
    "tlt_ret_5m",
    "tlt_ret_15m",
    "gamma_speed",
    "charm_accel_weighted",
    "gamma_phase_delta",
    "pcr_derivative_5m",
    "rvol_trend",
    "rvol_regime",
    "vol_relative",
    "iv_zscore",
    "iv_percentile",
    "vix_5d_std",
]


@dataclass(frozen=True)
class XInputFeatureSplit:
    state_features: list[str]
    input_features: list[str]

    @property
    def all_features(self) -> list[str]:
        return self.state_features + [c for c in self.input_features if c not in self.state_features]


def build_xinput_feature_split(df: pd.DataFrame) -> XInputFeatureSplit:
    base = available_features(df, load_base_feature_columns())
    input_features = [c for c in INPUT_FEATURE_CANDIDATES if c in df.columns and c in base]
    input_set = set(input_features)
    state_features = [c for c in base if c not in input_set]
    if not input_features:
        raise ValueError("No exogenous input/delta features found for XInputJEPA")
    if not state_features:
        raise ValueError("No state features left after input split")
    return XInputFeatureSplit(state_features=state_features, input_features=input_features)

