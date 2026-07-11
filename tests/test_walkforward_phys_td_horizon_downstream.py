from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.walkforward_event_option_portfolio_var_jepa import CONTRACT_SUFFIXES
from neural.jepa.walkforward_phys_td_horizon_downstream import build_action_frame, join_exact_h1_rows


def _raw() -> pd.DataFrame:
    rows = []
    for ticker, delta in (("SPXW", 25), ("QQQ", 35), ("SPY", 35)):
        row = {"ticker": ticker, "date": "20260102", "month": "202601", "minute": 660}
        for side, target in (("call", 0.4), ("put", -0.2)):
            row[f"{side}_d{delta}_available"] = 1
            row[f"{side}_d{delta}_opt_exit_ret"] = target
            row[f"{side}_d{delta}_opt_exit_minutes"] = 30
            for suffix in CONTRACT_SUFFIXES:
                row[f"{side}_d{delta}_{suffix}"] = 1.0
        rows.append(row)
    return pd.DataFrame(rows)


def _features() -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon_rows = []
    transition_rows = []
    for ticker in ("SPXW", "QQQ", "SPY"):
        horizon = {"ticker": ticker, "trade_date": "20260102", "minute": 660}
        transition = {"ticker": ticker, "trade_date": "20260102", "minute": 660}
        for dimension in range(32):
            z = 0.01 * dimension
            horizon[f"horizon_z_{dimension:02d}"] = z
            horizon[f"horizon_pred_h1_{dimension:02d}"] = z + 0.1
            horizon[f"horizon_pred_h6_{dimension:02d}"] = z + 0.6
            transition[f"z_t_{dimension:02d}"] = z
            transition[f"pred_z_{dimension:02d}"] = z + 0.1
        horizon_rows.append(horizon)
        transition_rows.append(transition)
    return pd.DataFrame(horizon_rows), pd.DataFrame(transition_rows)


def test_h1_h6_use_identical_rows_labels_and_only_motion_differs() -> None:
    horizon, transitions = _features()
    joined, audit = join_exact_h1_rows(_raw(), horizon, transitions)
    h1, h1_features = build_action_frame(joined, 1)
    h6, h6_features = build_action_frame(joined, 6)
    keys = ["ticker", "date", "minute", "action", "target_return", "exit_minutes"]
    assert h1[keys].equals(h6[keys])
    assert h1_features == h6_features
    assert np.allclose(h1["rep_dz_00"], 0.1)
    assert np.allclose(h6["rep_dz_00"], 0.6)
    assert audit["max_z_parity_abs_diff"] == 0.0
    assert audit["max_h1_prediction_parity_abs_diff"] < 1e-7
    assert not any(token in feature for feature in h1_features for token in ("target", "return", "exit"))


def test_join_rejects_h1_prediction_mismatch() -> None:
    horizon, transitions = _features()
    horizon.loc[0, "horizon_pred_h1_00"] += 0.01
    try:
        join_exact_h1_rows(_raw(), horizon, transitions)
    except RuntimeError as exc:
        assert "parity failed" in str(exc)
    else:
        raise AssertionError("h1 mismatch was not rejected")
