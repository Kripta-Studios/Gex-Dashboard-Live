from __future__ import annotations

import pandas as pd

from neural.jepa.walkforward_adajepa_downstream import build_action_frame
from neural.jepa.walkforward_event_option_portfolio_var_jepa import CONTRACT_SUFFIXES


def test_downstream_arms_have_identical_rows_labels_and_no_outcome_features() -> None:
    rows = []
    for ticker, delta in (("SPXW", 25), ("QQQ", 35), ("SPY", 35)):
        row = {"ticker": ticker, "date": "20260102", "month": "202601", "minute": 660}
        for index in range(32):
            row[f"ada_z_{index:02d}"] = 0.1
            row[f"ada_frozen_dz_{index:02d}"] = 0.2
            row[f"ada_adapted_dz_{index:02d}"] = 0.3
        for side, target in (("call", 0.4), ("put", -0.2)):
            row[f"{side}_d{delta}_available"] = 1
            row[f"{side}_d{delta}_opt_exit_ret"] = target
            row[f"{side}_d{delta}_opt_exit_minutes"] = 30
            for suffix in CONTRACT_SUFFIXES:
                row[f"{side}_d{delta}_{suffix}"] = 1.0
        rows.append(row)
    frame = pd.DataFrame(rows)
    frozen, frozen_features = build_action_frame(frame, "frozen")
    adapted, adapted_features = build_action_frame(frame, "adapted")
    keys = ["ticker", "date", "minute", "action", "target_return", "exit_minutes"]
    assert frozen[keys].equals(adapted[keys])
    assert frozen_features == adapted_features
    assert not any(token in feature.lower() for feature in frozen_features for token in ("target", "error", "future", "return", "exit"))
