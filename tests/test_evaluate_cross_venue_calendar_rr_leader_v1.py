from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v1 as module


def _profitable_ledger() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in module.TICKERS:
        for month in pd.period_range("2024-01", "2024-12", freq="M"):
            for index in range(13):
                gross = 4.0 if index < 7 else -1.0
                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": f"{month.year:04d}{month.month:02d}{index + 1:02d}",
                        "month": f"{month.year:04d}{month.month:02d}",
                        "gross_bps": gross,
                        "net_bps_1bp": gross - 1.0,
                        "net_bps_2bp": gross - 2.0,
                        "net_bps_3bp": gross - 3.0,
                        "net_bps": gross - 1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_trade_translation_uses_frozen_sign_and_costs() -> None:
    row = module.make_trade_row(
        ticker="SPXW",
        trade_date="20240102",
        sensor_ticker="SPY",
        pressure=0.1,
        frozen_action=1,
        entry_open=100.0,
        exit_open=101.0,
    )
    assert row["side"] == 1
    assert row["sensor_ticker"] == "SPY"
    assert row["hold_minutes"] == 180
    assert row["net_bps_1bp"] == pytest.approx(row["gross_bps"] - 1.0)
    assert row["net_bps_3bp"] == pytest.approx(row["gross_bps"] - 3.0)


def test_frozen_action_mismatch_fails_closed() -> None:
    with pytest.raises(AssertionError, match="does not match"):
        module.make_trade_row(
            ticker="SPXW",
            trade_date="20240102",
            sensor_ticker="SPY",
            pressure=0.1,
            frozen_action=-1,
            entry_open=100.0,
            exit_open=101.0,
        )


def test_incremental_and_promotion_gates_are_separate() -> None:
    ledger = _profitable_ledger()
    monthly = module.summarize_monthly(ledger)
    summary = module.summarize_tickers(ledger, monthly)
    assert summary["incremental_gate_pass"].all()
    assert summary["promotion_gate_pass"].all()
    assert module.classify_status(True, True, summary).startswith("PASS_OUTER_2024")

    weakened = summary.copy()
    weakened.loc[weakened["ticker"].eq("SPXW"), "profit_factor"] = 1.1
    weakened.loc[weakened["ticker"].eq("SPXW"), "promotion_gate_pass"] = False
    assert module.classify_status(True, False, weakened) == (
        "PASS_OUTER_2024_INCREMENTAL_GATE_2025_NOT_OPENED"
    )


def test_frequency_is_strictly_greater_than_twelve() -> None:
    ledger = _profitable_ledger()
    mask = (
        ledger["ticker"].eq("QQQ")
        & ledger["month"].eq("202401")
        & ledger["trade_date"].str[-2:].eq("13")
    )
    ledger = ledger.loc[~mask].copy()
    monthly = module.summarize_monthly(ledger)
    summary = module.summarize_tickers(ledger, monthly)
    qqq = summary.loc[summary["ticker"].eq("QQQ")].iloc[0]
    assert qqq["min_month_trades"] == 12
    assert not bool(qqq["incremental_gate_pass"])
    assert not bool(qqq["promotion_gate_pass"])


def test_cost_sensitivity_does_not_change_primary_column() -> None:
    ledger = _profitable_ledger()
    primary_before = ledger["net_bps"].copy()
    sensitivity = module.summarize_cost_sensitivity(ledger)
    pd.testing.assert_series_equal(ledger["net_bps"], primary_before)
    assert set(sensitivity["cost_bps"]) == {1.0, 2.0, 3.0}
    assert len(sensitivity) == 12


def test_return_reader_filters_only_two_frozen_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "underlying.parquet"
    source.touch()
    monkeypatch.setattr(
        module.pq,
        "read_schema",
        lambda _path: type(
            "Schema", (), {"names": ["symbol", "date", "timestamp", "open"]}
        )(),
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
                "timestamp": ["2024-01-02 10:36:00", "2024-01-02 13:36:00"],
                "open": [400.0, 401.0],
            }
        )

    monkeypatch.setattr(module.pd, "read_parquet", fake_read_parquet)
    assert module.read_exact_return_opens(source, "QQQ", "20240102") == (
        400.0,
        401.0,
    )
    expected_values = module._timestamp_values(  # noqa: SLF001
        "20240102", module.ENTRY_TIME
    ) + module._timestamp_values("20240102", module.EXIT_TIME)  # noqa: SLF001
    assert observed["filters"] == [("timestamp", "in", expected_values)]


def test_data_gate_is_required_before_any_outcome(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        module.validate_data_gate(tmp_path)


def test_default_data_gate_is_the_versioned_composite_v1r1_pass() -> None:
    assert module.DATA_GATE_DIR.name == (
        "cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1r1"
    )


def test_cli_has_no_year_outcome_or_policy_arguments() -> None:
    assert module.OUTER_YEAR == "2024"
    assert module.POLICY["sensor_map"] == {
        "QQQ": "QQQ",
        "SPXW": "SPY",
        "SPY": "SPY",
    }
    args = module.parse_args([])
    for forbidden in ("year", "outcome", "policy", "cost", "sensor"):
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
    assert "--frozen-manifest" in completed.stdout
