from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa.analyze_event_phys_td_flat_modal import (
    acceptance_gate,
    compare_encoder_configs,
    max_day_from_config,
    paired_summary,
)


def encoder_metadata(mode: str) -> dict:
    args = {
        "encoder_input_mode": mode,
        "output_dir": f"out/{mode}",
        "seed": 20260618,
        "device": "cpu",
        "epochs": 8,
        "horizons": "1,3,6,12",
        "entry_start_minute_et": 630,
        "entry_end_minute_et": 870,
        "entry_grid_anchor_minute_et": 600,
        "expected_step_minutes": 5,
        "live_observable_features_only": True,
        "batch_size": 1024,
    }
    return {
        "args": args,
        "effective_data_cutoff_month": "202605",
        "feature_cols": ["observable_a", "observable_b"],
    }


def test_compare_encoder_configs_allows_only_declared_factor_and_output_path() -> None:
    result = compare_encoder_configs(encoder_metadata("flat"), encoder_metadata("modal"))

    assert result["same_budget_and_seed"] is True
    assert set(result["differences"]) == {"encoder_input_mode", "output_dir"}


def test_compare_encoder_configs_rejects_budget_change() -> None:
    flat = encoder_metadata("flat")
    modal = encoder_metadata("modal")
    modal["args"]["epochs"] = 9

    with pytest.raises(RuntimeError, match="outside the declared factor"):
        compare_encoder_configs(flat, modal)


def test_paired_summary_counts_wins_in_requested_direction() -> None:
    flat = pd.Series([1.0, 2.0, 3.0])
    modal = pd.Series([0.5, 1.5, 4.0])

    lower = paired_summary(flat, modal, alternative="less")

    assert lower["modal_wins"] == 2
    assert lower["modal_losses"] == 1
    assert lower["cells"] == 3


@pytest.mark.parametrize(("value", "expected"), [("thr0.5_maxday4", 4), ("thr0.5_maxdayall", 999)])
def test_max_day_from_config(value: str, expected: int) -> None:
    assert max_day_from_config(value) == expected


def test_acceptance_gate_requires_every_ticker_month_cell() -> None:
    rows = []
    for ticker in ("SPXW", "QQQ", "SPY"):
        for month in ("202601", "202602"):
            rows.append(
                {
                    "arm": "flat",
                    "scope": "ticker_month",
                    "ticker": ticker,
                    "month": month,
                    "trades": 18,
                    "win_rate": 0.50,
                    "profit_factor": 1.30,
                    "pnl_return": 0.01,
                }
            )
    frame = pd.DataFrame(rows)
    assert acceptance_gate(frame, "flat")["passed"] is True

    frame.loc[(frame["ticker"] == "SPY") & (frame["month"] == "202602"), "pnl_return"] = 0.0
    failed = acceptance_gate(frame, "flat")
    assert failed["passed"] is False
    assert failed["failed_cells"] == [{"ticker": "SPY", "month": "202602"}]
