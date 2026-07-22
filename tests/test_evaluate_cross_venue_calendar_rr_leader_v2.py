from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as module


def test_frozen_feature_vector_and_mapping() -> None:
    assert len(module.FEATURE_COLUMNS) == 29
    assert len(set(module.FEATURE_COLUMNS)) == 29
    assert module.SENSOR_MAP == {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}
    assert module.FEATURE_COLUMNS[-3:] == (
        "ticker_QQQ",
        "ticker_SPXW",
        "ticker_SPY",
    )


def test_early_cash_features_use_exact_open_indices() -> None:
    opens = np.exp(np.arange(module.EARLY_CLOCK_COUNT, dtype=float) / 10_000.0)
    features = module.early_cash_features_from_opens(opens)
    assert features["return_0930_1035_bps"] == pytest.approx(65.0)
    assert features["return_1000_1035_bps"] == pytest.approx(35.0)
    assert features["return_1030_1035_bps"] == pytest.approx(5.0)
    assert features["open_return_std_bps"] == pytest.approx(0.0, abs=1e-12)
    assert features["open_range_bps"] == pytest.approx(65.0)
    assert features["positive_open_return_fraction"] == 1.0


def test_missing_early_cash_clock_fails_closed() -> None:
    with pytest.raises(AssertionError, match="opens are invalid"):
        module.early_cash_features_from_opens(np.ones(65))


def test_sealed_ledger_pressure_is_namespaced_before_sensor_join(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trades.csv"
    pd.DataFrame(
        {
            "ticker": ["QQQ", "SPXW", "SPY"],
            "trade_date": ["20240102"] * 3,
            "month": ["202401"] * 3,
            "underlying_return_bps": [1.0, 2.0, 3.0],
            "signal_pressure": [0.1, 0.2, 0.2],
        }
    ).to_csv(path, index=False)
    ledger = module._read_ledger(path, "2024")
    assert "signal_pressure" not in ledger.columns
    assert ledger["sealed_signal_pressure"].tolist() == [0.1, 0.2, 0.2]


def test_model_contract_is_single_fixed_logistic() -> None:
    model = module.make_model()
    classifier = model.named_steps["classifier"]
    assert classifier.C == 0.1
    assert classifier.penalty == "l2"
    assert classifier.solver == "liblinear"
    assert classifier.class_weight is None
    assert classifier.random_state == 0
    assert module.MODEL_THRESHOLD == 0.5


def test_development_blocks_are_disjoint_and_fixed() -> None:
    assert module.BLOCKS == {
        "DEV_A": {
            "train_start": "202301",
            "train_end": "202312",
            "test_start": "202401",
            "test_end": "202406",
        },
        "DEV_B": {
            "train_start": "202301",
            "train_end": "202406",
            "test_start": "202407",
            "test_end": "202412",
        },
    }


def test_cli_cannot_select_model_features_or_year() -> None:
    args = module.parse_args([])
    for forbidden in ("model", "features", "threshold", "year", "cost", "ticker"):
        assert not hasattr(args, forbidden)


def test_direct_cli_imports() -> None:
    script = Path(module.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=module.PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--output-dir" in completed.stdout
    assert "--workers" in completed.stdout
