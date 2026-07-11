from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.walkforward_event_option_portfolio_var_jepa import CONTRACT_SUFFIXES
from neural.jepa.walkforward_phys_td_spot_skip import SPOT_SKIP_FEATURES, build_arm_frames


def _joined() -> pd.DataFrame:
    rows = []
    for ticker, delta in (("SPXW", 25), ("QQQ", 35), ("SPY", 35)):
        row = {
            "ticker": ticker,
            "date": "20260102",
            "month": "202601",
            "minute": 660,
            "ret_5m_bps": 1.0,
            "ret_15m_bps": 2.0,
            "ret_30m_bps": 3.0,
        }
        for dimension in range(32):
            row[f"horizon_z_{dimension:02d}"] = 0.01 * dimension
            row[f"horizon_pred_h1_{dimension:02d}"] = 0.01 * dimension + 0.1
        for side, target in (("call", 0.4), ("put", -0.2)):
            row[f"{side}_d{delta}_available"] = 1
            row[f"{side}_d{delta}_opt_exit_ret"] = target
            row[f"{side}_d{delta}_opt_exit_minutes"] = 30
            for suffix in CONTRACT_SUFFIXES:
                row[f"{side}_d{delta}_{suffix}"] = 1.0
        rows.append(row)
    return pd.DataFrame(rows)


def test_spot_skip_changes_only_feature_allowlist() -> None:
    frames = build_arm_frames(_joined())
    control, control_features = frames["control"]
    variant, variant_features = frames["spot_skip"]
    keys = ["ticker", "date", "minute", "action", "target_return", "exit_minutes"]
    assert control[keys].equals(variant[keys])
    assert variant_features == [*control_features, *SPOT_SKIP_FEATURES]
    assert np.allclose(variant[SPOT_SKIP_FEATURES[0]], 1.0)
    assert np.allclose(variant[SPOT_SKIP_FEATURES[1]], 2.0)
    assert np.allclose(variant[SPOT_SKIP_FEATURES[2]], 3.0)
    assert not any(token in feature for feature in variant_features for token in ("target", "future", "pnl", "exit"))
