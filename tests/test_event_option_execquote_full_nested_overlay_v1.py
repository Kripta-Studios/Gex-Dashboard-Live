from __future__ import annotations

import pandas as pd

from neural.jepa.audit_event_option_execquote_full_nested_overlay_v1 import (
    no_overlap_issues,
)
from neural.jepa.evaluate_event_option_execquote_full_nested_overlay_v1 import (
    BASE_CONFIGS,
    FULL_CONFIGS,
    OverlayConfig,
    economic_metrics,
    passes_final_gates,
    replay_config,
    scan_grid,
    selection_months,
)


def _row(
    *,
    ticker: str,
    trade_date: str,
    month: str,
    minute: int,
    realized_return: float,
    exit_minutes: int = 30,
    exit_status: int = 0,
    score: float = 0.2,
) -> dict:
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "date": trade_date,
        "month": month,
        "minute": minute,
        "score": score,
        "edge_abs": 0.1,
        "action": "CALL",
        "nearest_level_abs_bps": 5.0,
        "ret_5m_bps": 1.0,
        "ctx_spx_ret_5m_bps": 1.0,
        "ctx_qqq_ret_5m_bps": 1.0,
        "realized_return": realized_return,
        "exit_minutes": exit_minutes,
        "exit_status": exit_status,
        "test_month": "202601",
    }


def test_frozen_grid_has_exact_legacy_cardinality() -> None:
    assert BASE_CONFIGS == 70_560
    assert FULL_CONFIGS == 1_128_960


def test_selection_window_never_contains_its_test_month() -> None:
    assert selection_months("202601") == [
        "202507",
        "202508",
        "202509",
        "202510",
        "202511",
        "202512",
    ]
    assert selection_months("202602")[-1] == "202601"


def test_full_grid_deterministically_selects_lowest_index_on_exact_tie() -> None:
    rows = []
    for month in selection_months("202601"):
        for day in range(1, 14):
            rows.append(
                _row(
                    ticker="QQQ",
                    trade_date=f"{month}{day:02d}",
                    month=month,
                    minute=700,
                    realized_return=0.1,
                )
            )
    config, scan = scan_grid(pd.DataFrame(rows), "QQQ")
    assert config is not None
    assert config.grid_index == 0
    assert config.max_day == 1
    assert config.cooldown == 0
    assert scan["evaluated_configurations"] == 1_128_960
    assert scan["rank"]["positive_months"] == 6
    assert scan["rank"]["min_month_trades"] == 13


def test_replay_waits_for_physical_exit_not_only_cooldown() -> None:
    frame = pd.DataFrame(
        [
            _row(
                ticker="QQQ",
                trade_date="20260105",
                month="202601",
                minute=630,
                realized_return=0.1,
            ),
            _row(
                ticker="QQQ",
                trade_date="20260105",
                month="202601",
                minute=640,
                realized_return=0.2,
            ),
            _row(
                ticker="QQQ",
                trade_date="20260105",
                month="202601",
                minute=660,
                realized_return=0.3,
            ),
        ]
    )
    config = OverlayConfig(-0.1, 0.0, "BOTH", 630, 870, 10.0, "NONE", 4, 0, 0)
    selected = replay_config(frame, config, "QQQ")
    assert selected["minute"].tolist() == [630, 660]
    assert not no_overlap_issues(selected)


def test_spxw_stop_pause_blocks_reentry_after_observed_stop() -> None:
    frame = pd.DataFrame(
        [
            _row(
                ticker="SPXW",
                trade_date="20260105",
                month="202601",
                minute=630,
                realized_return=-0.6,
                exit_status=-1,
            ),
            _row(
                ticker="SPXW",
                trade_date="20260105",
                month="202601",
                minute=660,
                realized_return=0.4,
            ),
        ]
    )
    config = OverlayConfig(-0.1, 0.0, "BOTH", 630, 870, 10.0, "NONE", 4, 0, 0)
    selected = replay_config(frame, config, "SPXW")
    assert selected["minute"].tolist() == [630]


def test_final_gate_requires_positive_pnl_in_every_month() -> None:
    rows = []
    for month in ("202601", "202602", "202603", "202604", "202605", "202606"):
        for day in range(1, 14):
            rows.append(
                {
                    "ticker": "QQQ",
                    "trade_date": f"{month}{day:02d}",
                    "month": month,
                    "minute": 630,
                    "realized_return": 0.2 if day <= 8 else -0.1,
                }
            )
    metrics = economic_metrics(pd.DataFrame(rows), sorted({row["month"] for row in rows}))
    assert passes_final_gates(metrics)
    for row in rows:
        if row["month"] == "202603":
            row["realized_return"] -= 0.2
    failed = economic_metrics(pd.DataFrame(rows), sorted({row["month"] for row in rows}))
    assert not passes_final_gates(failed)
