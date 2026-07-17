from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import audit_cross_venue_calendar_rr_leader_v1_data_gate as module


def _mapping_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "trade_date": "20240102",
                "calendar_rr_pressure": 1.0,
                "local_feature_valid": True,
                "sensor_ticker": "QQQ",
                "signal_pressure": 1.0,
                "signal_action": 1,
                "mapped_feature_valid": True,
            },
            {
                "ticker": "SPXW",
                "trade_date": "20240102",
                "calendar_rr_pressure": -3.0,
                "local_feature_valid": True,
                "sensor_ticker": "SPY",
                "signal_pressure": 2.0,
                "signal_action": 1,
                "mapped_feature_valid": True,
            },
            {
                "ticker": "SPY",
                "trade_date": "20240102",
                "calendar_rr_pressure": 2.0,
                "local_feature_valid": True,
                "sensor_ticker": "SPY",
                "signal_pressure": 2.0,
                "signal_action": 1,
                "mapped_feature_valid": True,
            },
        ]
    )


def test_exact_date_mapping_parity_accepts_spy_leader() -> None:
    audit = module.verify_mapping_parity(_mapping_frame())
    spxw = audit.loc[audit["ticker"].eq("SPXW")].iloc[0]
    assert spxw["sensor_ticker"] == "SPY"
    assert spxw["maximum_abs_pressure_difference"] == 0.0
    assert spxw["action_mismatches"] == 0


def test_mapping_parity_rejects_local_spxw_substitution() -> None:
    frame = _mapping_frame()
    frame.loc[frame["ticker"].eq("SPXW"), "signal_pressure"] = -3.0
    frame.loc[frame["ticker"].eq("SPXW"), "signal_action"] = -1
    with pytest.raises(AssertionError, match="mapping parity"):
        module.verify_mapping_parity(frame)


def test_outcome_columns_fail_closed() -> None:
    module.assert_outcome_free_schema(pd.DataFrame({"signal_pressure": [1.0]}))
    with pytest.raises(AssertionError, match="outcome-like"):
        module.assert_outcome_free_schema(
            pd.DataFrame({"signal_pressure": [1.0], "net_bps": [2.0]})
        )
    with pytest.raises(AssertionError, match="outcome-like"):
        module.assert_outcome_free_schema(
            pd.DataFrame({"signal_pressure": [1.0], "future_return": [2.0]})
        )


def test_cli_cannot_open_outcomes_or_change_scope() -> None:
    args = module.parse_args([])
    for forbidden in ("outcome", "label", "year", "start_date", "end_date"):
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
    assert "--data-gate-dir" in completed.stdout
    assert "--sidecar-root" in completed.stdout
