from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


JEPA_DIR = Path(__file__).resolve().parents[1] / "neural" / "jepa"
if str(JEPA_DIR) not in sys.path:
    sys.path.insert(0, str(JEPA_DIR))

from apply_event_static_union_cooldown import apply_static_union  # noqa: E402
from materialize_event_static_union import materialize_union  # noqa: E402
from scan_event_static_union_configs import apply_union  # noqa: E402
from walkforward_event_option_gate import DeployConfig, deploy, metrics  # noqa: E402


def _trade_frame(minutes: list[int], exits: list[float], *, ticker: str = "SPY") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": "20260701",
            "time": [f"{minute // 60:02d}:{minute % 60:02d}" for minute in minutes],
            "minute": minutes,
            "entry_minute": minutes,
            "expiry_mode": "zero_dte",
            "action": "PUT",
            "score": [1.0 - idx * 0.01 for idx in range(len(minutes))],
            "realized_return": 0.1,
            "exit_minutes": exits,
            "static_source": "primary",
            "static_source_priority": 0,
            "union_source": "primary",
            "_source_order": range(len(minutes)),
            "_source_priority": 0,
            "_source_row": range(len(minutes)),
            "_minute": minutes,
            "_score": [1.0 - idx * 0.01 for idx in range(len(minutes))],
        }
    )


def test_walkforward_deploy_waits_for_selected_trade_exit() -> None:
    scored = _trade_frame([600, 620, 630, 660], [30, 5, 20, 5])

    selected = deploy(scored, DeployConfig(-1.0, 999), cooldown_minutes=0)

    assert selected["minute"].tolist() == [600, 630, 660]


def test_walkforward_deploy_combines_cooldown_and_position_lifetime() -> None:
    scored = _trade_frame([600, 620, 630], [10, 5, 5])

    selected = deploy(scored, DeployConfig(-1.0, 999), cooldown_minutes=30)

    assert selected["minute"].tolist() == [600, 630]


def test_walkforward_deploy_tracks_positions_per_ticker() -> None:
    spy = _trade_frame([600, 620], [60, 5], ticker="SPY")
    qqq = _trade_frame([610], [5], ticker="QQQ")

    selected = deploy(pd.concat([spy, qqq], ignore_index=True), DeployConfig(-1.0, 999), cooldown_minutes=0)

    assert set(zip(selected["ticker"], selected["minute"])) == {("SPY", 600), ("QQQ", 610)}


def test_static_union_waits_for_exit_even_when_cooldown_is_shorter() -> None:
    trades = _trade_frame([600, 630, 640], [40, 5, 5])

    selected = apply_static_union(trades, max_day=999, cooldown_minutes=15)

    assert selected["entry_minute"].tolist() == [600, 640]
    assert selected["static_union_position_exit_minute"].tolist() == [640, 645]


def test_materializer_and_config_selector_reject_overlapping_intervals() -> None:
    trades = _trade_frame([600, 620, 660], [60, 5, 5])

    materialized = materialize_union(trades, 999, -1.0, "time_asc")
    configured = apply_union(trades, ("primary",), 999, 0, -1.0, "time_asc")

    assert materialized["entry_minute"].tolist() == [600, 660]
    assert configured["entry_minute"].tolist() == [600, 660]


def test_score_ranked_static_research_order_still_cannot_select_overlapping_intervals() -> None:
    trades = _trade_frame([600, 620, 660], [60, 5, 5])
    trades["_score"] = [0.8, 1.0, 0.7]
    trades["score"] = trades["_score"]

    materialized = materialize_union(trades, 999, -1.0, "score_desc")
    configured = apply_union(trades, ("primary",), 999, 0, -1.0, "score_desc")

    assert materialized["entry_minute"].tolist() == [620, 660]
    assert configured["entry_minute"].tolist() == [620, 660]


@pytest.mark.parametrize(
    ("selector", "kwargs"),
    [
        (deploy, {"cfg": DeployConfig(-1.0, 999), "cooldown_minutes": 0}),
        (apply_static_union, {"max_day": 999, "cooldown_minutes": 0}),
        (materialize_union, {"max_trades_per_day": 999, "min_score": -1.0, "daily_order": "time_asc"}),
    ],
)
def test_live_equivalent_selectors_require_exit_minutes(selector, kwargs) -> None:
    trades = _trade_frame([600, 620], [30, 5]).drop(columns="exit_minutes")

    with pytest.raises(ValueError, match="exit_minutes"):
        selector(trades, **kwargs)


def test_research_override_preserves_legacy_overlapping_replay() -> None:
    scored = _trade_frame([600, 620], [60, 5]).drop(columns="exit_minutes")

    selected = deploy(
        scored,
        DeployConfig(-1.0, 999),
        cooldown_minutes=0,
        allow_overlapping_positions=True,
    )

    assert selected["minute"].tolist() == [600, 620]


def test_metrics_normalizes_mixed_csv_date_and_month_types() -> None:
    trades = pd.DataFrame(
        {
            "date": [20260102, "20260103"],
            "month": [202601, "202601"],
            "realized_return": [0.5, -0.25],
            "action": ["CALL", "PUT"],
        }
    )

    row = metrics(trades, ["202601"])

    assert row["trades"] == 2
    assert row["profit_factor"] == 2.0
    assert row["min_month_trades"] == 2
