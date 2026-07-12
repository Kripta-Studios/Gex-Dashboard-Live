from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.audit_wall_spot_semantics_v1 import (  # noqa: E402
    audit_session,
    evaluate_contract,
    read_wall_view,
    run_census,
    select_manifest_sessions,
    sha256_file,
)


def _underlying(path: Path, trade_date: str, ticker: str, *, base: float) -> Path:
    day = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    times = pd.date_range(f"{day} 09:30:00", f"{day} 15:59:00", freq="1min")
    opens = base + pd.Series(range(len(times)), dtype=float).to_numpy() / 100.0
    pd.DataFrame(
        {
            "symbol": ticker,
            "date": day,
            "timestamp": times,
            "open": opens,
            "high": opens + 0.01,
            "low": opens - 0.01,
            "close": opens,
            "tick_count": 60,
        }
    ).to_parquet(path, index=False)
    return path


def _wall_rows(path: Path, sessions: list[tuple[str, str, str, Path]]) -> Path:
    rows: list[dict[str, object]] = []
    for ticker, trade_date, semantics, underlying_path in sessions:
        underlying = pd.read_parquet(underlying_path)
        indexed = underlying.set_index(pd.to_datetime(underlying["timestamp"]))["open"]
        day = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        for minute in (635, 640):
            dt = pd.Timestamp(day) + pd.Timedelta(minutes=minute)
            source_dt = dt if semantics == "exact_t" else dt - pd.Timedelta(minutes=1)
            spot = float(indexed.loc[source_dt])
            if semantics == "unresolved" and minute == 640:
                spot += 1.0
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "dt": dt,
                    "minute": minute,
                    "spot": spot,
                }
            )
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _manifest(path: Path, sessions: list[tuple[str, str, str, Path]], *, include_2026: bool = True) -> Path:
    rows = [
        {
            "ticker": ticker,
            "trade_date": trade_date,
            "expiration": trade_date,
            "dte_days": 0,
            "expiry_mode": "zero_dte",
            "has_underlying": "True",
            "underlying_path": str(underlying_path),
        }
        for ticker, trade_date, _, underlying_path in sessions
    ]
    if include_2026:
        rows.append(
            {
                "ticker": "SPY",
                "trade_date": "20260102",
                "expiration": "20260102",
                "dte_days": 0,
                "expiry_mode": "zero_dte",
                "has_underlying": "True",
                "underlying_path": "must-not-be-read.parquet",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_audit_session_classifies_exact_hybrid_and_unresolved(tmp_path: Path) -> None:
    cases = [
        ("SPXW", "20240102", "exact_t", _underlying(tmp_path / "spxw.parquet", "20240102", "SPXW", base=4700.0)),
        ("QQQ", "20240103", "hybrid_spot_tm1", _underlying(tmp_path / "qqq.parquet", "20240103", "QQQ", base=400.0)),
        ("SPY", "20240104", "unresolved", _underlying(tmp_path / "spy.parquet", "20240104", "SPY", base=475.0)),
    ]
    wall_path = _wall_rows(tmp_path / "walls.parquet", cases)
    walls = read_wall_view(wall_path)
    observed = {}
    for ticker, trade_date, _, underlying_path in cases:
        part = walls[(walls["ticker"] == ticker) & (walls["trade_date"] == trade_date)]
        row = audit_session(
            {"ticker": ticker, "trade_date": trade_date, "underlying_path": str(underlying_path)},
            part,
        )
        observed[ticker] = row
    assert observed["SPXW"]["classification"] == "exact_t"
    assert observed["SPXW"]["exact_t_rows"] == 2
    assert observed["QQQ"]["classification"] == "hybrid_spot_tm1"
    assert observed["QQQ"]["mismatched_t_rows"] == 2
    assert observed["SPY"]["classification"] == "unresolved"
    assert observed["SPY"]["exact_tm1_rows"] == 1
    assert all(len(row["underlying_sha256"]) == 64 for row in observed.values())


def test_exact_t_precedes_tm1_when_price_is_unchanged(tmp_path: Path) -> None:
    path = _underlying(tmp_path / "flat.parquet", "20240102", "SPY", base=100.0)
    frame = pd.read_parquet(path)
    frame.loc[:, ["open", "high", "low", "close"]] = 100.0
    frame.to_parquet(path, index=False)
    walls = pd.DataFrame(
        {
            "ticker": ["SPY"],
            "trade_date": ["20240102"],
            "dt": [pd.Timestamp("2024-01-02 10:35:00")],
            "minute": [635],
            "spot": [100.0],
        }
    )
    row = audit_session(
        {"ticker": "SPY", "trade_date": "20240102", "underlying_path": str(path)},
        walls,
    )
    assert row["classification"] == "exact_t"
    assert row["exact_both_rows"] == 1


def test_manifest_filters_2026_without_accessing_its_path(tmp_path: Path) -> None:
    source = _underlying(tmp_path / "spy.parquet", "20240102", "SPY", base=475.0)
    sessions = [("SPY", "20240102", "exact_t", source)]
    manifest_path = _manifest(tmp_path / "manifest.csv", sessions, include_2026=True)
    selected = select_manifest_sessions(manifest_path)
    assert selected[["ticker", "trade_date"]].to_dict("records") == [
        {"ticker": "SPY", "trade_date": "20240102"}
    ]


def test_wall_view_rejects_duplicate_and_2026_keys(tmp_path: Path) -> None:
    valid = {
        "ticker": "SPY",
        "trade_date": "20240102",
        "dt": pd.Timestamp("2024-01-02 10:35:00"),
        "minute": 635,
        "spot": 100.0,
    }
    duplicate_path = tmp_path / "duplicate.parquet"
    pd.DataFrame([valid, valid]).to_parquet(duplicate_path, index=False)
    with pytest.raises(AssertionError, match="duplicate"):
        read_wall_view(duplicate_path)
    mixed_path = tmp_path / "mixed_scope.parquet"
    old = {
        **valid,
        "trade_date": "20220103",
        "dt": pd.Timestamp("2022-01-03 10:35:00"),
    }
    pd.DataFrame([old, valid]).to_parquet(mixed_path, index=False)
    assert read_wall_view(mixed_path)["trade_date"].tolist() == ["20240102"]
    future_path = tmp_path / "future.parquet"
    pd.DataFrame(
        [{**valid, "trade_date": "20260102", "dt": pd.Timestamp("2026-01-02 10:35:00")}]
    ).to_parquet(future_path, index=False)
    with pytest.raises(AssertionError, match="outside|2026"):
        read_wall_view(future_path)


def test_contract_requires_exact_expected_hybrid_keys() -> None:
    census = pd.DataFrame(
        {
            "ticker": ["QQQ", "SPY"],
            "trade_date": ["20221230", "20221230"],
            "classification": ["hybrid_spot_tm1", "hybrid_spot_tm1"],
            "wall_rows": [67560, 67560],
            "underlying_required_window_minutes": [390, 390],
            "expected_underlying_required_window_minutes": [390, 390],
        }
    )
    gate = evaluate_contract(census, manifest_sessions=2519, wall_rows=135120)
    assert gate["hybrid_keys"] == [["QQQ", "20221230"], ["SPY", "20221230"]]
    assert gate["passed"] is False  # session/class totals remain deliberately synthetic


def test_run_census_writes_hashed_immutable_outcome_free_artifacts(tmp_path: Path) -> None:
    source = _underlying(tmp_path / "spy.parquet", "20240102", "SPY", base=475.0)
    sessions = [("SPY", "20240102", "exact_t", source)]
    walls_path = _wall_rows(tmp_path / "walls.parquet", sessions)
    manifest_path = _manifest(tmp_path / "source_manifest.csv", sessions, include_2026=True)
    output_dir = tmp_path / "audit"
    manifest = run_census(
        walls_path=walls_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        workers=1,
        enforce_input_hashes=False,
        enforce_clean_code=False,
        enforce_expected_contract=False,
    )
    census = pd.read_csv(output_dir / "census.csv", dtype={"trade_date": str})
    stored = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == stored
    assert stored["outcome_free"] is True
    assert stored["holdout_2026_used"] is False
    assert stored["census_sha256"] == sha256_file(output_dir / "census.csv")
    assert census["classification"].tolist() == ["exact_t"]
    assert len(stored["underlying_source_inventory_sha256"]) == 64
    assert all(len(value) == 64 for value in stored["code_hashes"].values())
    with pytest.raises(FileExistsError, match="immutable"):
        run_census(
            walls_path=walls_path,
            manifest_path=manifest_path,
            output_dir=output_dir,
            workers=1,
            enforce_input_hashes=False,
            enforce_clean_code=False,
            enforce_expected_contract=False,
        )
