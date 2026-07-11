from __future__ import annotations

import pandas as pd

from neural.jepa.audit_early_cadence_pair import compare_frames


def test_one_minute_candidate_is_strict_expansion_of_control(tmp_path) -> None:
    minutes = list(range(600, 626))
    candidate = pd.DataFrame(
        {
            "ticker": ["SPY"] * len(minutes),
            "trade_date": ["20260102"] * len(minutes),
            "minute": minutes,
            "expiry_mode": ["zero_dte"] * len(minutes),
            "feature": [float(value) for value in minutes],
        }
    )
    control = candidate[candidate["minute"].mod(5).eq(0)].copy()
    control_path = tmp_path / "control.parquet"
    candidate_path = tmp_path / "candidate.parquet"
    control.to_parquet(control_path, index=False)
    candidate.to_parquet(candidate_path, index=False)
    payload, issues = compare_frames(control_path, candidate_path)
    assert not issues
    assert payload["key_parity"]
    assert payload["candidate_extra_rows"] == 20


def test_pair_auditor_rejects_changed_common_row(tmp_path) -> None:
    minutes = list(range(600, 626))
    candidate = pd.DataFrame(
        {
            "ticker": ["SPY"] * len(minutes),
            "trade_date": ["20260102"] * len(minutes),
            "minute": minutes,
            "expiry_mode": ["zero_dte"] * len(minutes),
            "feature": [float(value) for value in minutes],
        }
    )
    control = candidate[candidate["minute"].mod(5).eq(0)].copy()
    candidate.loc[candidate["minute"].eq(600), "feature"] = 9.0
    control_path = tmp_path / "control.parquet"
    candidate_path = tmp_path / "candidate.parquet"
    control.to_parquet(control_path, index=False)
    candidate.to_parquet(candidate_path, index=False)
    payload, issues = compare_frames(control_path, candidate_path)
    assert issues
    assert payload["differing_columns"] == ["feature"]
