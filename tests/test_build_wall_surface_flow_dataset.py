from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.build_wall_surface_flow_dataset import (  # noqa: E402
    build_session,
    evaluate_data_gate,
    filter_manifest,
    sha256_file,
)


def _write_sources(root: Path, *, trade_date: str = "20240102") -> dict[str, str]:
    date_text = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    greeks_path = root / "greeks.parquet"
    ohlc_path = root / "ohlc.parquet"
    underlying_path = root / "underlying.parquet"
    pd.DataFrame(
        {
            "symbol": "SPY",
            "expiration": date_text,
            "trade_date": date_text,
            "interval_used": "1m",
            "timestamp": [f"{date_text} 10:34:00"],
            "underlying_timestamp": [f"{date_text} 10:34:00"],
            "right": ["CALL"],
            "strike": [100.0],
            "bid": [0.9],
            "ask": [1.1],
        }
    ).to_parquet(greeks_path, index=False)
    pd.DataFrame(
        {
            "symbol": "SPY",
            "expiration": date_text,
            "trade_date": date_text,
            "interval_used": "1m",
            "timestamp": [f"{date_text} 10:34:00"],
            "right": ["CALL"],
            "strike": [100.0],
            "close": [1.2],
            "volume": [10],
            "count": [2],
        }
    ).to_parquet(ohlc_path, index=False)
    times = pd.date_range(f"{date_text} 09:30:00", f"{date_text} 15:59:00", freq="1min")
    pd.DataFrame(
        {
            "symbol": "SPY",
            "date": date_text,
            "timestamp": times,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "tick_count": 1,
        }
    ).to_parquet(underlying_path, index=False)
    return {
        "greeks_path": str(greeks_path),
        "ohlc_path": str(ohlc_path),
        "underlying_path": str(underlying_path),
    }


def _manifest_row(paths: dict[str, str], *, trade_date: str = "20240102") -> dict[str, object]:
    return {
        "ticker": "SPY",
        "trade_date": trade_date,
        "expiration": trade_date,
        "dte_days": 0,
        "expiry_mode": "zero_dte",
        "has_greeks": "True",
        "has_ohlc": "True",
        "has_underlying": "True",
        **paths,
    }


def _candidate(trade_date: str = "20240102") -> pd.DataFrame:
    date_text = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    return pd.DataFrame(
        {
            "ticker": ["SPY"],
            "trade_date": [trade_date],
            "minute": [635],
            "decision_dt": [pd.Timestamp(f"{date_text} 10:35:00")],
            "wall_identity": ["call_gamma"],
            "wall_role": ["resistance"],
            "candidate_right": ["CALL"],
            "candidate_wall_strike": [100.0],
            "spot": [100.0],
            "wall_alias_count": [1],
            "episode_sequence": [1],
            "episode_start_minute": [635],
            "episode_id": [f"SPY:{trade_date}:resistance:100.000000:635"],
            "minute_sin": [0.0],
            "minute_cos": [0.0],
            "role_resistance": [1.0],
            "candidate_distance_bps": [0.0],
            "candidate_abs_distance_bps": [0.0],
            "spot_ret_1m_bps": [1.0],
            "spot_abs_ret_1m_bps": [1.0],
            "spot_ret_5m_bps": [2.0],
            "spot_ret_15m_bps": [3.0],
            "spot_ret_30m_bps": [4.0],
            "candidate_distance_change_5m_bps": [2.0],
            "candidate_distance_change_15m_bps": [3.0],
            "candidate_distance_change_30m_bps": [4.0],
            "candidate_approach_5m_bps": [2.0],
            "candidate_approach_15m_bps": [3.0],
            "candidate_approach_30m_bps": [4.0],
        }
    )


def test_filter_manifest_treats_string_false_as_false_and_rejects_2026(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path)
    valid = _manifest_row(paths)
    invalid = {**valid, "trade_date": "20240103", "expiration": "20240103", "has_ohlc": "False"}
    frame = pd.DataFrame([valid, invalid])
    selected = filter_manifest(frame, start_date="20240101", end_date="20241231")
    assert selected["trade_date"].tolist() == ["20240102"]
    with pytest.raises(AssertionError, match="2026"):
        filter_manifest(pd.DataFrame([{**valid, "trade_date": "20260102", "expiration": "20260102"}]), start_date="20260101", end_date="20261231")


def test_filter_manifest_requires_expiration_equal_trade_date(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path)
    row = _manifest_row(paths)
    row["expiration"] = "20240103"
    with pytest.raises(AssertionError, match="expiration == trade_date"):
        filter_manifest(pd.DataFrame([row]), start_date="20240101", end_date="20241231")


def test_build_session_hashes_sources_and_preserves_exact_completed_bar(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path)
    record = _manifest_row(paths)
    output, audit, inventory = build_session(record, _candidate())
    assert len(output) == 1
    assert output["surface_call_volume_w1m"].iloc[0] == 10.0
    assert output["flow_latest_bar_end"].iloc[0] == pd.Timestamp("2024-01-02 10:35:00")
    assert audit["candidate_rows"] == 1
    assert {row["source_kind"] for row in inventory} == {"greeks", "ohlc", "underlying"}
    assert all(len(row["sha256"]) == 64 for row in inventory)
    assert all(row["rows"] > 0 for row in inventory)


def test_build_session_replaces_missing_greek_clock_with_sealed_native_quote(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path)
    greeks_path = Path(paths["greeks_path"])
    greeks = pd.read_parquet(greeks_path)
    greeks.drop(columns=["timestamp"]).to_parquet(greeks_path, index=False)
    quote_path = tmp_path / "native_quotes.parquet"
    pd.DataFrame(
        {
            "symbol": greeks["symbol"],
            "expiration": greeks["expiration"],
            "trade_date": greeks["trade_date"],
            "timestamp": greeks["underlying_timestamp"],
            "right": greeks["right"],
            "strike": greeks["strike"],
            "bid": greeks["bid"],
            "ask": greeks["ask"],
        }
    ).to_parquet(quote_path, index=False)
    record = {
        **_manifest_row(paths),
        "native_quote_path": str(quote_path),
        "expected_native_quote_sha256": sha256_file(quote_path),
        "expected_greeks_sha256": sha256_file(greeks_path),
    }
    output, audit, inventory = build_session(record, _candidate())
    assert len(output) == 1
    assert audit["option_timestamp_fallback_used"] is False
    assert {row["source_kind"] for row in inventory} == {
        "greeks", "ohlc", "underlying", "native_quote"
    }


def test_data_gate_uses_schedule_aware_grid_and_blocks_timestamp_fallback() -> None:
    rows: list[dict[str, object]] = []
    cells = [(ticker, year) for ticker in ("SPXW", "QQQ", "SPY") for year in ("2022", "2023", "2024", "2025")]
    for cell_index, (ticker, year) in enumerate(cells):
        count = 209 if cell_index == len(cells) - 1 else 210
        for index in range(count):
            expected = 155 if index == 0 and year != "2022" else 250
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": f"{year}{index // 28 + 1:02d}{index % 28 + 1:02d}",
                    "active_rows": 100,
                    "active_volume": 100.0,
                    "valid_quote_rows": 100,
                    "valid_quote_volume": 100.0,
                    "priced_active_volume": 100.0,
                    "signable_volume": 100.0,
                    "candidate_rows": 1,
                    "greeks_required_window_minutes": expected,
                    "ohlc_required_window_minutes": expected,
                    "expected_required_window_minutes": expected,
                    "underlying_required_window_minutes": 390,
                    "expected_underlying_required_window_minutes": 390,
                    "candidate_underlying_spot_max_bps": 0.0,
                    "option_timestamp_fallback_used": False,
                }
            )
    audit = pd.DataFrame(rows)
    profile_rows: list[dict[str, object]] = []
    core = [
        "surface_directional_pressure_w1m", "surface_directional_pressure_w5m",
        "surface_directional_pressure_w15m", "role_break_pressure_w1m",
        "role_break_pressure_w5m", "role_break_pressure_w15m",
    ]
    for ticker, year in cells:
        for feature in core:
            profile_rows.append(
                {"ticker": ticker, "year": year, "feature": feature, "distinct_values": 10, "zero_rate": 0.1, "missing_rate": 0.0}
            )
        for feature in ("realized_vol_5m_bps", "realized_vol_15m_bps"):
            profile_rows.append(
                {"ticker": ticker, "year": year, "feature": feature, "distinct_values": 10, "zero_rate": 0.0, "missing_rate": 0.0}
            )
    profile = pd.DataFrame(profile_rows)
    gate = evaluate_data_gate(audit, profile, authoritative_inputs=True, authoritative_code=True)
    assert gate["incomplete_greeks_grid_sessions"] == 0
    assert gate["incomplete_ohlc_grid_sessions"] == 0
    assert gate["option_timestamp_fallback_sessions"] == 0
    assert gate["passed"] is True
    audit.loc[0, "option_timestamp_fallback_used"] = True
    blocked = evaluate_data_gate(audit, profile, authoritative_inputs=True, authoritative_code=True)
    assert blocked["option_timestamp_fallback_sessions"] == 1
    assert blocked["passed"] is False
