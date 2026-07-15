from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa.evaluate_king_gex_exit_v1 import (
    CONFIG_BY_ID,
    DIRECTIONS,
    EXIT_CONFIGS,
    _direction_action,
    _read_source_checkpoint,
    _write_source_checkpoint,
    assert_baseline_parity,
    protocol,
    simulate_quote_path,
)


def _path(points: list[tuple[int, float]]) -> tuple[pd.Timestamp, pd.DataFrame]:
    ts = pd.Timestamp("2023-01-03 10:00")
    return ts, pd.DataFrame(
        {"quote_time": [ts + pd.Timedelta(minutes=m) for m, _ in points], "exit_bid": [v for _, v in points]}
    )


def test_grid_is_exactly_the_frozen_sixteen() -> None:
    assert len(EXIT_CONFIGS) == 16
    assert len(CONFIG_BY_ID) == 16
    assert CONFIG_BY_ID["B00"] == {
        "config_id": "B00",
        "stop_loss": 0.60,
        "trail_activation": 0.50,
        "trail_drawdown": 0.25,
        "horizon_minutes": 180,
        "min_hold_minutes": 30,
        "take_profit": 10.0,
    }
    assert protocol()["directions"] == list(DIRECTIONS)


def test_prehold_peak_can_arm_trail_at_minimum_hold() -> None:
    ts, path = _path([(10, 1.60), (30, 1.30), (180, 1.10)])
    result = simulate_quote_path(path, 1.0, ts, CONFIG_BY_ID["B00"])
    assert result["exit_reason"] == "trail"
    assert result["status"] == 1
    assert result["exit_minutes"] == 30
    assert result["realized_return"] == pytest.approx(0.30)


def test_stop_has_priority_and_executes_at_actual_bid() -> None:
    ts, path = _path([(10, 1.60), (30, 0.30), (180, 1.10)])
    result = simulate_quote_path(path, 1.0, ts, CONFIG_BY_ID["B00"])
    assert result["exit_reason"] == "stop"
    assert result["status"] == -1
    assert result["exit_minutes"] == 30
    assert result["realized_return"] == pytest.approx(-0.70)


def test_short_horizon_uses_observed_bid() -> None:
    ts, path = _path([(30, 0.80), (60, 1.20), (90, 2.00)])
    result = simulate_quote_path(path, 1.0, ts, CONFIG_BY_ID["H60"])
    assert result["exit_reason"] == "horizon"
    assert result["exit_minutes"] == 60
    assert result["realized_return"] == pytest.approx(0.20)


def test_direction_inversion_is_global() -> None:
    frame = pd.DataFrame({"action": ["CALL", "PUT", "CALL"]})
    assert _direction_action(frame, "D0_K1").tolist() == ["CALL", "PUT", "CALL"]
    assert _direction_action(frame, "D1_INVERTED").tolist() == ["PUT", "CALL", "PUT"]


def test_baseline_parity_fails_closed() -> None:
    expected = {"realized_return": 0.1, "exit_minutes": 30, "status": 1, "max_ret": 0.2, "min_ret": -0.1}
    assert_baseline_parity(dict(expected), expected)
    changed = dict(expected, realized_return=0.1001)
    with pytest.raises(AssertionError, match="realized_return"):
        assert_baseline_parity(changed, expected)


def test_source_checkpoint_is_manifest_last_and_detects_corruption(tmp_path: Path) -> None:
    identity = {"schema": "test", "cell": "202301/QQQ"}
    frame = pd.DataFrame({"ticker": ["QQQ"], "realized_return": [0.2]})
    _write_source_checkpoint(tmp_path, identity, frame)
    assert (tmp_path / "manifest.json").is_file()
    loaded = _read_source_checkpoint(tmp_path, identity)
    assert loaded is not None and len(loaded) == 1
    payload = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert payload["atomic_manifest_last"] is True
    (tmp_path / "outcomes.parquet").write_bytes(b"broken")
    assert _read_source_checkpoint(tmp_path, identity) is None


def test_simulation_never_uses_nonfinite_exit() -> None:
    ts, path = _path([(30, 0.7), (180, 1.1)])
    result = simulate_quote_path(path, 1.0, ts, CONFIG_BY_ID["S100"])
    assert np.isfinite(result["realized_return"])
    assert 30 <= result["exit_minutes"] <= 180
