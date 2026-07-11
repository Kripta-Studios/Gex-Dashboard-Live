from __future__ import annotations

import pandas as pd
import pytest

from neural.jepa.analyze_event_phys_td_history import compare_encoder_configs, history_paired_summary


def _metadata(data: str, output_dir: str) -> dict:
    return {
        "effective_data_cutoff_month": "202605",
        "feature_cols": ["feature_a", "feature_b"],
        "args": {
            "data": data,
            "output_dir": output_dir,
            "encoder_input_mode": "flat",
            "start_month": "202505",
            "end_month": "202605",
            "data_cutoff_month": "202605",
            "seed": 20260618,
            "deterministic": True,
            "device": "cuda",
            "epochs": 8,
            "batch_size": 1024,
            "context_len": 6,
            "horizons": "1,3,6,12",
            "entry_start_minute_et": 630,
            "entry_end_minute_et": 870,
            "entry_grid_anchor_minute_et": 600,
            "expected_step_minutes": 5,
            "live_observable_features_only": True,
        },
    }


def test_history_config_comparison_allows_only_data_and_output_paths() -> None:
    comparison = compare_encoder_configs(_metadata("recent.parquet", "recent"), _metadata("long.parquet", "long"))
    assert comparison["declared_factor"] == "encoder_training_history_start"
    assert set(comparison["differences"]) == {"data", "output_dir"}
    assert comparison["identical_feature_count"] == 2


def test_history_config_comparison_rejects_an_extra_factor() -> None:
    recent = _metadata("recent.parquet", "recent")
    long = _metadata("long.parquet", "long")
    long["args"]["epochs"] = 9
    with pytest.raises(RuntimeError, match="outside the declared factor"):
        compare_encoder_configs(recent, long)


def test_history_paired_summary_uses_long_minus_recent_direction() -> None:
    result = history_paired_summary(pd.Series([2.0, 3.0, 4.0]), pd.Series([1.0, 2.0, 3.0]), alternative="less")
    assert result["history_2022_wins"] == 3
    assert result["median_difference_history_2022_minus_history_2025"] == pytest.approx(-1.0)
