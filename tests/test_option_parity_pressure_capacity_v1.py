from pathlib import Path

import pytest

from neural.jepa.audit_option_parity_pressure_capacity_v1 import (
    HALF_DAYS,
    TICKERS,
    discover_zero_dte_files,
    evaluate_capacity,
    expected_months,
)


def touch_source(root: Path, ticker: str, expiration: str, trade_date: str) -> None:
    path = root / ticker / "greeks" / trade_date[:4] / trade_date[4:6]
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{ticker}_{expiration}_{trade_date}_greeks.parquet").write_bytes(b"fixture")


def test_expected_month_axis_is_frozen() -> None:
    months = expected_months()
    assert months[0] == "202301"
    assert months[-1] == "202512"
    assert len(months) == 36


def test_discovery_keeps_only_exact_zero_dte(tmp_path: Path) -> None:
    for ticker in TICKERS:
        touch_source(tmp_path, ticker, "20230103", "20230103")
        touch_source(tmp_path, ticker, "20230106", "20230103")
    rows = discover_zero_dte_files(tmp_path)
    assert len(rows) == 3
    assert {row["trade_date"] for row in rows} == {"20230103"}


def test_exactly_twelve_sessions_fails_strict_frequency() -> None:
    rows = []
    for ticker in TICKERS:
        for day in range(1, 13):
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": f"202302{day:02d}",
                    "month": "202302",
                    "eligible_fixed_180m_clock": True,
                }
            )
    monthly, failures = evaluate_capacity(rows, months=["202302"])
    assert len(monthly) == 3
    assert len(failures) == 3
    assert all(row["eligible_zero_dte_sessions"] == 12 for row in failures)


def test_thirteen_sessions_pass_strict_frequency() -> None:
    rows = []
    for ticker in TICKERS:
        for day in range(1, 14):
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": f"202203{day:02d}",
                    "month": "202203",
                    "eligible_fixed_180m_clock": True,
                }
            )
    _, failures = evaluate_capacity(rows, months=["202203"])
    assert failures == []


def test_half_days_are_frozen_and_ineligible(tmp_path: Path) -> None:
    assert HALF_DAYS == frozenset(
        {
            "20230703",
            "20231124",
            "20240703",
            "20241129",
            "20241224",
            "20250703",
            "20251128",
            "20251224",
        }
    )
    for ticker in TICKERS:
        touch_source(tmp_path, ticker, "20231124", "20231124")
    rows = discover_zero_dte_files(tmp_path)
    assert rows
    assert not any(row["eligible_fixed_180m_clock"] for row in rows)


def test_duplicate_exact_source_fails_closed(tmp_path: Path) -> None:
    for ticker in TICKERS:
        touch_source(tmp_path, ticker, "20230103", "20230103")
    duplicate = tmp_path / "QQQ" / "greeks" / "2023" / "02"
    duplicate.mkdir(parents=True)
    (duplicate / "QQQ_20230103_20230103_greeks.parquet").write_bytes(b"duplicate")
    with pytest.raises(AssertionError, match="duplicate exact-0DTE"):
        discover_zero_dte_files(tmp_path)
