from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from neural.jepa.build_wall_state_dataset import (
    audit_event_coverage,
    build_session,
    filter_manifest,
    load_wall_chain,
    process_sessions,
    select_preflight_sessions,
)


def manifest_row(tmp_path: Path, ticker: str = "SPY", trade_date: str = "20250102") -> dict:
    greeks_path = tmp_path / f"{ticker}_{trade_date}_greeks.parquet"
    oi_path = tmp_path / f"{ticker}_{trade_date}_oi.parquet"
    greeks = []
    oi = []
    for strike in (99.0, 100.0, 101.0):
        for right in ("CALL", "PUT"):
            greeks.append({
                "timestamp": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} 10:35:15",
                "underlying_timestamp": None,
                "strike": strike,
                "right": right,
                "underlying_price": 100.0,
                "implied_vol": 1.0,
            })
            oi.append({
                "strike": strike,
                "right": right,
                "open_interest": 5000.0 if (strike, right) in {(101.0, "CALL"), (99.0, "PUT")} else 100.0,
            })
    pd.DataFrame(greeks).to_parquet(greeks_path, index=False)
    pd.DataFrame(oi).to_parquet(oi_path, index=False)
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "expiration": trade_date,
        "dte_days": 0,
        "expiry_mode": "zero_dte",
        "has_greeks": True,
        "has_oi": True,
        "greeks_path": str(greeks_path),
        "oi_path": str(oi_path),
    }


def test_filter_manifest_seals_2026_and_keeps_only_true_zero_dte(tmp_path):
    valid = manifest_row(tmp_path)
    future = {**valid, "trade_date": "20260102", "expiration": "20260102"}
    weekly = {**valid, "trade_date": "20250103", "expiration": "20250110", "dte_days": 7, "expiry_mode": "front_weekly"}
    out = filter_manifest(pd.DataFrame([valid, future, weekly]))
    assert out[["ticker", "trade_date"]].to_dict("records") == [{"ticker": "SPY", "trade_date": "20250102"}]
    with pytest.raises(ValueError, match="sealed cutoff"):
        filter_manifest(pd.DataFrame([valid]), end_date="20260101")


def test_real_parquet_loader_joins_daily_oi_and_builds_current_wall(tmp_path):
    row = manifest_row(tmp_path)
    chain = load_wall_chain(row)
    assert len(chain) == 6
    assert chain["open_interest"].gt(0.0).all()
    state = build_session(row)
    assert len(state) == 1
    assert state.loc[0, "ticker"] == "SPY"
    assert state.loc[0, "trade_date"] == "20250102"
    assert state.loc[0, "wall_call_gamma_strike"] == 101.0
    assert state.loc[0, "wall_put_gamma_strike"] == 99.0


def test_preflight_selection_requires_one_session_per_ticker(tmp_path):
    rows = [manifest_row(tmp_path, ticker=ticker) for ticker in ("SPXW", "QQQ", "SPY")]
    selected = select_preflight_sessions(pd.DataFrame(rows))
    assert set(selected["ticker"]) == {"SPXW", "QQQ", "SPY"}
    with pytest.raises(AssertionError, match="QQQ"):
        select_preflight_sessions(pd.DataFrame([rows[0], rows[2]]))


def test_event_coverage_deduplicates_event_profiles(tmp_path):
    event_path = tmp_path / "events.parquet"
    pd.DataFrame({
        "ticker": ["SPY", "SPY", "QQQ"],
        "trade_date": ["20250102", "20250102", "20250102"],
        "minute": [635, 635, 635],
        "spot": [100.0, 100.0, 200.0],
    }).to_parquet(event_path, index=False)
    walls = pd.DataFrame({
        "ticker": ["SPY"], "trade_date": ["20250102"], "minute": [635], "spot": [100.0],
    })
    audit = audit_event_coverage(walls, event_path)
    assert audit["event_unique_keys"] == 2
    assert audit["covered_keys"] == 1
    assert audit["coverage_overall"] == 0.5
    assert audit["spot_diff_bps_max"] == 0.0

    restricted = audit_event_coverage(
        walls,
        event_path,
        session_filter=pd.DataFrame({"ticker": ["SPY"], "trade_date": ["20250102"]}),
    )
    assert restricted["event_unique_keys"] == 1
    assert restricted["coverage_overall"] == 1.0


def test_process_sessions_rejects_oversubscription():
    with pytest.raises(ValueError, match="1..16"):
        process_sessions([], 17)


def test_script_entrypoint_resolves_repo_package():
    script = Path(__file__).resolve().parents[1] / "neural" / "jepa" / "build_wall_state_dataset.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=script.parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "sealed 2022-2025" in result.stdout
