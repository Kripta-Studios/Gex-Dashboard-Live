from __future__ import annotations

import numpy as np
import pandas as pd
from types import SimpleNamespace

from neural.jepa.walkforward_event_option_patchcore_abstention import (
    add_patchcore_distance,
    fit_patchcore_bank,
    select_policy,
)


def test_patchcore_bank_is_deterministic_and_train_only() -> None:
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0, 9.0], "y": [0.0, 0.0, 1.0, 9.0]})
    first = fit_patchcore_bank(train, ["x", "y"], 2)
    second = fit_patchcore_bank(train, ["x", "y"], 2)
    assert np.array_equal(first.source_indices, second.source_indices)
    assert np.allclose(first.centers, second.centers)
    before = first.means.copy()
    first.distances(pd.DataFrame({"x": [1000.0], "y": [1000.0]}))
    assert np.array_equal(first.means, before)


def test_patchcore_distance_only_adds_an_abstention_feature() -> None:
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0], "ticker": ["SPXW"] * 3})
    bank = fit_patchcore_bank(train, ["x"], 2)
    scored = pd.DataFrame(
        {"ticker": ["SPXW", "SPXW"], "x": [0.5, 20.0], "action": ["CALL", "PUT"], "score": [0.2, 0.4]}
    )
    output = add_patchcore_distance(scored, {"SPXW": bank})
    assert output["action"].tolist() == scored["action"].tolist()
    assert output["score"].tolist() == scored["score"].tolist()
    assert output.loc[1, "patchcore_distance"] > output.loc[0, "patchcore_distance"]


def test_invalid_small_spy_policy_preserves_diagnostics_but_abstains() -> None:
    rows = []
    for month in ("202510", "202511", "202512"):
        for day in range(1, 6):
            rows.append(
                {
                    "ticker": "SPY",
                    "month": month,
                    "date": f"{month}{day:02d}",
                    "minute": 630,
                    "score": 0.1,
                    "realized_return": -0.1,
                    "action": "CALL",
                    "exit_minutes": 30.0,
                    "patchcore_distance": 1.0,
                }
            )
    args = SimpleNamespace(
        threshold_grid=[-1e9],
        threshold_quantiles=[],
        distance_quantiles=[1.0],
        min_val_trades=54,
        min_month_trades=18,
        min_val_pf=1.3,
        min_val_win_rate=0.5,
        min_call_rate=0.0,
        max_call_rate=1.0,
        min_val_positive_month_rate=1.0,
        daily_win_weight=0.25,
        top5_share_penalty=0.1,
    )
    cfg, cap, diagnostics, _ = select_policy(
        pd.DataFrame(rows), "SPY", ["202510", "202511", "202512"], args, use_patchcore=False
    )
    assert cfg is None and cap is None
    assert diagnostics["trades"] == 15
