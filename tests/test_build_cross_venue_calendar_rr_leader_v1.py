from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import build_cross_venue_calendar_rr_leader_v1 as module


def _feature_rows(events_per_month: int = 13) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    value = 1.0
    for ticker in module.TICKERS:
        for month in pd.period_range("2024-01", "2025-12", freq="M"):
            for day in range(1, events_per_month + 1):
                trade_date = f"{month.year:04d}{month.month:02d}{day:02d}"
                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": trade_date,
                        "year": f"{month.year:04d}",
                        "month": f"{month.year:04d}{month.month:02d}",
                        "calendar_rr_pressure": value,
                        "calendar_half_day": False,
                        "economic_clock_eligible": True,
                        "local_feature_valid": True,
                        "local_invalid_reason": "",
                    }
                )
                value += 1.0
    return pd.DataFrame(rows)


def test_cross_venue_mapping_is_exact_and_uses_spy_for_spxw() -> None:
    local = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "trade_date": "20240102",
                "year": "2024",
                "month": "202401",
                "calendar_rr_pressure": 1.0,
                "calendar_half_day": False,
                "economic_clock_eligible": True,
                "local_feature_valid": True,
                "local_invalid_reason": "",
            },
            {
                "ticker": "SPXW",
                "trade_date": "20240102",
                "year": "2024",
                "month": "202401",
                "calendar_rr_pressure": -9.0,
                "calendar_half_day": False,
                "economic_clock_eligible": True,
                "local_feature_valid": True,
                "local_invalid_reason": "",
            },
            {
                "ticker": "SPY",
                "trade_date": "20240102",
                "year": "2024",
                "month": "202401",
                "calendar_rr_pressure": 2.5,
                "calendar_half_day": False,
                "economic_clock_eligible": True,
                "local_feature_valid": True,
                "local_invalid_reason": "",
            },
        ]
    )
    mapped = module.apply_cross_venue_mapping(local).set_index("ticker")
    assert mapped.loc["QQQ", "signal_pressure"] == 1.0
    assert mapped.loc["SPY", "signal_pressure"] == 2.5
    assert mapped.loc["SPXW", "signal_pressure"] == 2.5
    assert mapped.loc["SPXW", "sensor_ticker"] == "SPY"
    assert mapped.loc["SPXW", "signal_action"] == 1


def test_spxw_requires_its_local_row_and_same_date_spy() -> None:
    local = pd.DataFrame(
        [
            {
                "ticker": "SPXW",
                "trade_date": "20240102",
                "year": "2024",
                "month": "202401",
                "calendar_rr_pressure": -1.0,
                "calendar_half_day": False,
                "economic_clock_eligible": True,
                "local_feature_valid": False,
                "local_invalid_reason": "local failed",
            },
            {
                "ticker": "SPY",
                "trade_date": "20240102",
                "year": "2024",
                "month": "202401",
                "calendar_rr_pressure": 1.0,
                "calendar_half_day": False,
                "economic_clock_eligible": True,
                "local_feature_valid": True,
                "local_invalid_reason": "",
            },
        ]
    )
    mapped = module.apply_cross_venue_mapping(local).set_index("ticker")
    assert not bool(mapped.loc["SPXW", "mapped_feature_valid"])
    assert mapped.loc["SPXW", "signal_action"] == 0


def test_native_clock_certification_never_replaces_vintage_values() -> None:
    keys = pd.DataFrame(
        {
            "symbol": ["QQQ", "QQQ"],
            "expiration": ["20240102", "20240102"],
            "trade_date": ["20240102", "20240102"],
            "timestamp": pd.to_datetime(
                ["2024-01-02 10:30:00", "2024-01-02 10:35:00"]
            ),
            "strike": [400.0, 400.0],
            "right": ["CALL", "CALL"],
        }
    )
    vintage = keys.assign(delta=[0.25, 0.27], bid=[1.0, 1.2], ask=[1.1, 1.3])
    native = pd.concat(
        [
            keys,
            keys.assign(strike=[405.0, 405.0]),
        ],
        ignore_index=True,
    )
    before = vintage.copy(deep=True)
    audit = module.certify_vintage_clock(vintage, native)
    pd.testing.assert_frame_equal(vintage, before)
    assert audit["clock_key_coverage_exact"] is True
    assert audit["native_extra_target_rows"] == 2


def test_missing_native_key_fails_closed() -> None:
    vintage = pd.DataFrame(
        {
            "symbol": ["QQQ"],
            "expiration": ["20240102"],
            "trade_date": ["20240102"],
            "timestamp": pd.to_datetime(["2024-01-02 10:30:00"]),
            "strike": [400.0],
            "right": ["CALL"],
            "delta": [0.25],
            "bid": [1.0],
            "ask": [1.1],
        }
    )
    native = vintage.loc[:, module.KEY_COLUMNS].assign(strike=405.0)
    with pytest.raises(AssertionError, match="certify every vintage"):
        module.certify_vintage_clock(vintage, native)


def test_data_gate_passes_only_with_strict_monthly_capacity() -> None:
    mapped = module.apply_cross_venue_mapping(_feature_rows(13))
    coverage, distinctness, monthly, gate = module.evaluate_data_gate(mapped)
    assert coverage["local_coverage"].eq(1.0).all()
    assert coverage["mapped_coverage"].eq(1.0).all()
    assert distinctness["distinct_states"].ge(module.MIN_DISTINCT_STATES).all()
    assert monthly["valid_events"].eq(13).all()
    assert gate["passed"] is True

    failed = mapped.loc[
        ~(
            mapped["ticker"].eq("SPY")
            & mapped["month"].eq("202401")
            & mapped["trade_date"].str[-2:].eq("13")
        )
    ].copy()
    _, _, monthly_failed, failed_gate = module.evaluate_data_gate(failed)
    spy_january = monthly_failed.loc[
        monthly_failed["ticker"].eq("SPY") & monthly_failed["month"].eq("202401"),
        "valid_events",
    ].item()
    assert spy_january == 12
    assert failed_gate["frequency_pass"] is False
    assert failed_gate["passed"] is False


def test_zero_pressure_is_not_counted_as_a_trade() -> None:
    mapped = module.apply_cross_venue_mapping(_feature_rows(13))
    mask = mapped["ticker"].eq("QQQ") & mapped["month"].eq("202401")
    index = mapped.loc[mask].index[0]
    mapped.loc[index, "signal_pressure"] = 0.0
    mapped.loc[index, "signal_action"] = 0
    mapped.loc[index, "economic_event_valid"] = False
    _, _, monthly, gate = module.evaluate_data_gate(mapped)
    count = monthly.loc[
        monthly["ticker"].eq("QQQ") & monthly["month"].eq("202401"),
        "valid_events",
    ].item()
    assert count == 12
    assert gate["frequency_pass"] is False


def test_full_seal_is_mandatory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="PASS artifact missing"):
        module.validate_full_capture_seal(tmp_path)


def test_real_composite_seal_and_roots_are_frozen() -> None:
    contract, seal, index = module.validate_full_capture_seal(
        module.DEFAULT_SIDECAR_ROOT
    )
    assert seal["status"] == (
        "PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_COMPOSITE_V1R1"
    )
    assert len(index) == module.EXPECTED_CAPTURES
    assert index["storage_generation"].value_counts().to_dict() == {
        "V1": 3_008,
        "V1R1_REPAIR": 4,
    }
    assert set(index.loc[index["storage_generation"].eq("V1"), "storage_root"]) == {
        contract["v1_root"]
    }
    assert set(
        index.loc[index["storage_generation"].eq("V1R1_REPAIR"), "storage_root"]
    ) == {contract["repair_root"]}


def test_v1r1_alignment_excludes_only_frozen_unilateral_keys() -> None:
    shared_keys = pd.DataFrame(
        {
            "symbol": ["QQQ", "QQQ"],
            "expiration": ["20240102", "20240102"],
            "trade_date": ["20240102", "20240102"],
            "timestamp": pd.to_datetime(
                ["2024-01-02 10:30:00", "2024-01-02 10:35:00"]
            ),
            "strike": [400.0, 400.0],
            "right": ["CALL", "CALL"],
        }
    )
    unilateral = shared_keys.assign(strike=[405.0, 405.0])
    greeks = pd.concat([shared_keys, unilateral], ignore_index=True).assign(
        delta=0.25, bid=1.0, ask=1.1
    )
    iv = shared_keys.assign(
        bid=1.0,
        ask=1.1,
        bid_implied_vol=0.2,
        ask_implied_vol=0.21,
    )
    aligned_greeks, aligned_iv, audit = module.align_vintage_modalities(
        greeks,
        iv,
        storage_generation="V1R1_REPAIR",
        expected_shared_key_rows=2,
        expected_greek_only_key_rows=2,
        expected_iv_only_key_rows=0,
    )
    assert len(aligned_greeks) == len(aligned_iv) == 2
    assert aligned_greeks["strike"].eq(400.0).all()
    assert audit == {
        "shared_key_rows": 2,
        "greek_only_key_rows": 2,
        "iv_only_key_rows": 0,
    }
    with pytest.raises(AssertionError, match="V1 capture lost"):
        module.align_vintage_modalities(
            greeks,
            iv,
            storage_generation="V1",
            expected_shared_key_rows=2,
            expected_greek_only_key_rows=2,
            expected_iv_only_key_rows=0,
        )


def test_scope_and_cli_cannot_open_outcomes_or_2026() -> None:
    assert module.YEARS == ("2024", "2025")
    assert "2026" not in module.YEARS
    assert module.SENSOR_MAP == {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}
    args = module.parse_args([])
    for forbidden in ("outcome", "label", "start_date", "end_date", "year"):
        assert not hasattr(args, forbidden)


def test_target_spot_reader_filters_only_two_preoutcome_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "spot.parquet"
    source.touch()
    monkeypatch.setattr(
        module.pq,
        "read_schema",
        lambda _path: type("Schema", (), {"names": ["symbol", "date", "timestamp", "open"]})(),
    )
    observed: dict[str, object] = {}

    def fake_read_parquet(path: Path, *, columns: list[str], filters: list[tuple]) -> pd.DataFrame:
        observed["path"] = path
        observed["columns"] = columns
        observed["filters"] = filters
        return pd.DataFrame(
            {
                "symbol": ["QQQ", "QQQ"],
                "date": ["2024-01-02", "2024-01-02"],
                "timestamp": ["2024-01-02 10:30:00", "2024-01-02 10:35:00"],
                "open": [400.0, 401.0],
            }
        )

    monkeypatch.setattr(module.pd, "read_parquet", fake_read_parquet)
    assert module.read_target_spots(source, "QQQ", "20240102") == (400.0, 401.0)
    assert observed["columns"] == ["symbol", "date", "timestamp", "open"]
    assert observed["filters"] == [
        ("timestamp", "in", module.target_timestamp_values("20240102"))
    ]


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
    assert "--sidecar-root" in completed.stdout
    assert "--output-dir" in completed.stdout
