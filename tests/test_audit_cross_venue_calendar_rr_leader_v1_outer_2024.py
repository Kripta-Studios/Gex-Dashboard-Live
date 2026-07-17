from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import audit_cross_venue_calendar_rr_leader_v1_outer_2024 as module


def _trade() -> dict[str, object]:
    entry = 100.0
    exit_value = 101.0
    underlying = math.log(exit_value / entry) * 10_000.0
    gross = underlying
    return {
        "ticker": "SPXW",
        "trade_date": "20240102",
        "month": "202401",
        "sensor_ticker": "SPY",
        "decision_time": "10:35:00",
        "entry_time": "10:36:00",
        "exit_time": "13:36:00",
        "hold_minutes": 180,
        "signal_pressure": 0.1,
        "side": 1,
        "entry_open": entry,
        "exit_open": exit_value,
        "underlying_return_bps": underlying,
        "gross_bps": gross,
        "net_bps_1bp": gross - 1.0,
        "net_bps_2bp": gross - 2.0,
        "net_bps_3bp": gross - 3.0,
        "net_bps": gross - 1.0,
    }


def test_trade_economics_recompute_exactly() -> None:
    audited = module.validate_and_recompute_trades(pd.DataFrame([_trade()]))
    assert len(audited) == 1
    assert audited.iloc[0]["net_bps"] == pytest.approx(
        audited.iloc[0]["gross_bps"] - 1.0
    )


def test_tampered_trade_cost_fails_closed() -> None:
    row = _trade()
    row["net_bps"] = float(row["net_bps"]) + 1.0
    with pytest.raises(AssertionError, match="economic recomputation"):
        module.validate_and_recompute_trades(pd.DataFrame([row]))


def test_wrong_spxw_sensor_fails_closed() -> None:
    row = _trade()
    row["sensor_ticker"] = "SPXW"
    with pytest.raises(AssertionError, match="scope/policy"):
        module.validate_and_recompute_trades(pd.DataFrame([row]))


def test_cli_cannot_change_year_policy_or_cost() -> None:
    args = module.parse_args([])
    for forbidden in ("year", "policy", "cost", "sensor", "outcome"):
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
    assert "--input-dir" in completed.stdout
    assert "--workers" in completed.stdout
