from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import neural.jepa.audit_cross_venue_opra_trade_quote_flow_v5 as auditor
import neural.jepa.build_cross_venue_opra_trade_quote_flow_v5 as builder
import neural.jepa.capture_cross_venue_opra_trade_quote_flow_v5 as capture


def trade_row(
    *,
    right: str,
    timestamp: str,
    sequence: int,
    price: float,
    bid: float,
    ask: float,
    size: int = 10,
    condition: int = 0,
) -> dict[str, object]:
    return {
        "symbol": "SPY",
        "expiration": "2024-01-02",
        "strike": 470.0 if right == "call" else 469.0,
        "right": right,
        "trade_timestamp": timestamp,
        "quote_timestamp": "2024-01-02T10:30:59.999",
        "sequence": sequence,
        "ext_condition1": 0,
        "ext_condition2": 0,
        "ext_condition3": 0,
        "ext_condition4": 0,
        "condition": condition,
        "size": size,
        "exchange": 5,
        "price": price,
        "bid_size": 20,
        "bid_exchange": 1,
        "bid": bid,
        "bid_condition": 0,
        "ask_size": 30,
        "ask_exchange": 2,
        "ask": ask,
        "ask_condition": 0,
    }


def raw_bytes() -> bytes:
    rows = [
        trade_row(
            right="call",
            timestamp="2024-01-02T10:31:00.000",
            sequence=1,
            price=1.2,
            bid=1.0,
            ask=1.2,
        ),
        trade_row(
            right="call",
            timestamp="2024-01-02T10:31:01.000",
            sequence=2,
            price=1.0,
            bid=1.0,
            ask=1.2,
        ),
        trade_row(
            right="put",
            timestamp="2024-01-02T10:31:02.000",
            sequence=3,
            price=1.3,
            bid=1.1,
            ask=1.3,
        ),
        trade_row(
            right="put",
            timestamp="2024-01-02T10:31:03.000",
            sequence=4,
            price=1.1,
            bid=1.1,
            ask=1.3,
            condition=18,
        ),
    ]
    return b"".join(
        json.dumps(row, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )


def spec() -> dict[str, str]:
    return {
        "capture_id": "capture",
        "sensor": "SPY",
        "trade_date": "20240102",
        "expiration": "20240102",
    }


class FakeResponse:
    status_code = 200
    headers = {"Content-Type": "application/x-ndjson"}

    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def test_real_filename_metadata_freezes_752_dates_per_sensor() -> None:
    sessions, audit = capture.discover_sessions()
    assert len(sessions) == 1_504
    assert sessions.groupby("sensor").size().to_dict() == {"QQQ": 752, "SPY": 752}
    assert audit["dates_by_year"] == {"2023": 250, "2024": 252, "2025": 250}
    assert audit["date_sha256"] == capture.EXPECTED_DATE_SHA256
    assert audit["no_source_file_values_read"] is True


def test_parser_injects_request_date_and_requires_strict_prior_quote() -> None:
    frame = capture.normalize_trade_quote(raw_bytes(), spec())
    assert list(frame.columns) == list(capture.TRADE_COLUMNS)
    assert frame["trade_date"].eq("20240102").all()
    assert frame["quote_timestamp"].lt(frame["trade_timestamp"]).all()
    assert set(frame["right"]) == {"C", "P"}
    bad = trade_row(
        right="call",
        timestamp="2024-01-02T10:30:59.999",
        sequence=99,
        price=1.2,
        bid=1.0,
        ask=1.2,
    )
    raw = json.dumps(bad).encode("utf-8") + b"\n"
    with pytest.raises(AssertionError, match="invalid or duplicate"):
        capture.normalize_trade_quote(raw, spec())


def test_features_are_fixed_and_independent_auditor_reproduces_them() -> None:
    trades = capture.normalize_trade_quote(raw_bytes(), spec())
    features, session_audit = builder.compute_session_features(
        trades, sensor="SPY", trade_date="20240102"
    )
    independent, independent_audit = auditor.recompute_session(
        trades, sensor="SPY", trade_date="20240102"
    )
    assert features["event_valid"] is True
    assert session_audit["rows_alpha_valid"] == 4
    assert np.isfinite([features[column] for column in builder.FEATURE_COLUMNS]).all()
    assert features == independent
    assert session_audit == independent_audit
    auditor_source = Path(auditor.__file__).read_text(encoding="utf-8")
    assert "import build_cross_venue_opra" not in auditor_source
    assert "from neural.jepa.build_cross_venue_opra" not in auditor_source


def passing_gate_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    audit_rows = []
    counter = 0
    for sensor in capture.SENSORS:
        for year in capture.YEARS:
            for month in range(1, 13):
                for day in range(1, 14):
                    counter += 1
                    trade_date = f"{year}{month:02d}{day:02d}"
                    row: dict[str, object] = {
                        "sensor": sensor,
                        "trade_date": trade_date,
                        "year": year,
                        "month": trade_date[:6],
                        "calendar_half_day": False,
                        "event_valid": True,
                    }
                    row.update(
                        {
                            column: float(counter + offset) / 10_000.0
                            for offset, column in enumerate(builder.FEATURE_COLUMNS)
                        }
                    )
                    feature_rows.append(row)
                    audit_rows.append(
                        {
                            "sensor": sensor,
                            "trade_date": trade_date,
                            "year": year,
                            "month": trade_date[:6],
                            "alpha_premium": 100.0,
                            "alpha_contracts": 100.0,
                            "firmable_premium": 90.0,
                            "firmable_contracts": 90.0,
                        }
                    )
    return pd.DataFrame(feature_rows), pd.DataFrame(audit_rows)


def test_gate_requires_every_sensor_year_month_and_feature() -> None:
    features, audits = passing_gate_frames()
    annual, monthly, quality, gate = builder.evaluate_gate(features, audits)
    assert gate["status"] == "PASS_OUTCOME_FREE_DATA_GATE"
    assert annual[["coverage_pass", "firmable_premium_pass"]].to_numpy().all()
    assert len(monthly) == 72 and monthly["minimum_pass"].all()
    assert quality[["distinct_pass", "modal_pass"]].to_numpy().all()
    features.loc[features.index[0:13], "event_valid"] = False
    _, failed_months, _, failed = builder.evaluate_gate(features, audits)
    assert failed["status"] == "FAILED_OUTCOME_FREE_DATA_GATE"
    assert not failed_months["minimum_pass"].all()


def test_capture_is_atomic_and_raw_reconstructs(tmp_path: Path) -> None:
    calls = 0

    def requester(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(raw_bytes())

    output = tmp_path / "capture"
    row = capture.capture_one(
        spec(),
        output=output,
        base_url="http://example/v3",
        provenance={"kind": "test"},
        runtime={"lock_sha256": "lock", "environment_sha256": "env"},
        code_hashes={"capture.py": "hash"},
        timeout=1.0,
        requester=requester,
    )
    directory = output / "SPY" / "20240102"
    assert calls == 1 and row["rows"] == 4
    assert directory.is_dir()
    assert not directory.with_name("20240102.staging").exists()
    stored = pd.read_parquet(directory / "trades.parquet")
    rebuilt = capture.normalize_trade_quote(
        (directory / "response.ndjson").read_bytes(), spec()
    )
    pd.testing.assert_frame_equal(stored, rebuilt)
