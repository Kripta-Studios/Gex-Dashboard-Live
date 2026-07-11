from __future__ import annotations

import pytest
import pandas as pd

from neural.jepa.analyze_exact_objective_ablation import _months, passes, ticker_summary
from neural.jepa.walkforward_event_option_profile_selector import (
    default_profiles,
    filter_profiles,
)


def test_filter_profiles_keeps_exact_names_in_canonical_order() -> None:
    profiles = default_profiles("production_zero_dte", ["SPXW", "QQQ", "SPY"])
    selected = filter_profiles(
        profiles,
        ["target_zero_dte_d35_win", "target_zero_dte_d25_return"],
    )
    assert [profile.name for profile in selected] == [
        "target_zero_dte_d25_return",
        "target_zero_dte_d35_win",
    ]


def test_filter_profiles_empty_allowlist_preserves_all_profiles() -> None:
    profiles = default_profiles("production_zero_dte", ["SPXW", "QQQ", "SPY"])
    assert filter_profiles(profiles, []) == profiles


def test_filter_profiles_rejects_unknown_name() -> None:
    profiles = default_profiles("production_zero_dte", ["SPXW", "QQQ", "SPY"])
    with pytest.raises(ValueError, match="unknown --profile-allowlist"):
        filter_profiles(profiles, ["target_zero_dte_d99_win"])


def test_exact_objective_gate_requires_every_month_and_minimum_hold() -> None:
    rows = []
    for month in ("202601", "202602", "202603", "202604", "202605"):
        for index in range(18):
            rows.append(
                {
                    "date": f"{month}{index + 1:02d}",
                    "month": month,
                    "action": "CALL" if index % 2 else "PUT",
                    "realized_return": 0.5 if index < 10 else -0.3,
                    "exit_minutes": 30,
                }
            )
    summary = ticker_summary(pd.DataFrame(rows))
    assert passes(summary)
    rows[0]["exit_minutes"] = 29
    assert not passes(ticker_summary(pd.DataFrame(rows)))


def test_abstained_fold_nan_month_lists_are_empty() -> None:
    assert _months(float("nan")) == []
    assert _months("") == []
