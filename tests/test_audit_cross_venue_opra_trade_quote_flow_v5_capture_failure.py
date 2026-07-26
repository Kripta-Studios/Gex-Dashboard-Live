from __future__ import annotations

import pandas as pd

import neural.jepa.audit_cross_venue_opra_trade_quote_flow_v5_capture_failure as audit


def frozen_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = pd.DataFrame(
        [
            {
                "capture_id": f"{sensor}-{date}",
                "sensor": sensor,
                "trade_date": date,
                "expiration": date,
                "year": date[:4],
                "month": date[:6],
            }
            for sensor in ("QQQ", "SPY")
            for date in (
                "20230103",
                "20230104",
                "20230105",
                "20230201",
                "20230202",
            )
        ]
    )
    errors = pd.DataFrame(
        [
            {
                "capture_id": "QQQ-20230103",
                "sensor": "QQQ",
                "trade_date": "20230103",
                "error": audit.ERROR_TEXT,
            },
            {
                "capture_id": "SPY-20230202",
                "sensor": "SPY",
                "trade_date": "20230202",
                "error": audit.ERROR_TEXT,
            },
        ]
    )
    return universe, errors


def test_gate_tables_preserve_all_failed_ids_without_exclusion() -> None:
    universe, errors = frozen_frames()
    annual, monthly = audit.gate_tables(universe, errors)
    assert annual["failed_captures"].sum() == 2
    assert not annual["zero_missing_pass"].all()
    assert monthly["failed_captures"].sum() == 2
    assert not monthly["zero_missing_pass"].all()


def test_real_failed_state_has_exact_frozen_partition() -> None:
    universe, errors, contract = audit.load_frozen_state(audit.DEFAULT_CAPTURE_ROOT)
    assert len(universe) == audit.EXPECTED_CAPTURES
    assert len(errors) == audit.EXPECTED_FAILURES
    assert errors["error"].eq(audit.ERROR_TEXT).all()
    assert contract["git_commit"] == audit.EXPECTED_CAPTURE_COMMIT
    assert not (audit.DEFAULT_CAPTURE_ROOT / "_seal").exists()
