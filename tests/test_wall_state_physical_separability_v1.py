from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

from neural.jepa.evaluate_wall_state_physical_separability_v1 import (
    CURRENT_LEVEL_SPECS,
    WALL_SPECS,
    assert_feature_allowlists,
    label_candidate_session,
    make_wall_candidates,
)


def synthetic_wall_frame() -> pd.DataFrame:
    row = {
        "ticker": "SPY", "trade_date": "20250102", "minute": 660,
        "spot": 100.0, "spot_lag_5m": 99.5, "spot_lag_15m": 99.0, "spot_lag_30m": 98.5,
        "spot_ret_5m_bps": 50.0, "spot_ret_15m_bps": 100.0, "spot_ret_30m_bps": 150.0,
        "ib_range_bps": 50.0,
        "wall_gamma_call_put_balance": 0.1, "wall_delta_call_put_balance": 0.2,
        "wall_gamma_separation_bps": 100.0, "wall_delta_separation_bps": 120.0,
        "wall_net_gamma_total_log": 5.0, "wall_net_delta_total_log": 6.0, "wall_net_dgex_total_log": 4.0,
    }
    for name in CURRENT_LEVEL_SPECS:
        row[f"dist_{name}_bps"] = -50.0 if name.endswith(("high", "up")) else 50.0
    for day in range(1, 6):
        row[f"dist_ib_high_D{day}"] = -100.0 - day
        row[f"dist_ib_low_D{day}"] = 100.0 + day
    suffixes = (
        "magnitude_log", "concentration", "dominance_gap", "active_strikes", "total_log", "hhi",
        "effective_strikes", "family_active_strikes", "age_minutes", "same_5m", "same_15m", "same_30m",
        "move_5m_bps", "move_15m_bps", "move_30m_bps", "magnitude_chg_5m", "magnitude_chg_15m",
        "magnitude_chg_30m",
    )
    strikes = {"call_gamma": 100.5, "put_gamma": 98.0, "call_delta": 102.0, "put_delta": 98.0}
    for identity in WALL_SPECS:
        row[f"wall_{identity}_strike"] = strikes[identity]
        for suffix in suffixes:
            row[f"wall_{identity}_{suffix}"] = 1.0
    return pd.DataFrame([row])


def test_candidate_geometry_selects_only_approaching_defended_wall():
    candidates = make_wall_candidates(synthetic_wall_frame())
    assert candidates["wall_identity"].tolist() == ["call_gamma"]
    assert candidates.iloc[0]["wall_role"] == "resistance"
    assert np.isclose(candidates.iloc[0]["candidate_distance_bps"], -50.0)
    assert candidates.iloc[0]["candidate_approach_15m_bps"] > 0.0


def test_future_labels_use_strict_path_and_resolve_role(tmp_path):
    timestamps = pd.date_range("2025-01-02 10:35", "2025-01-02 11:05", freq="1min")
    path = pd.DataFrame({"timestamp": timestamps, "high": 100.2, "low": 99.8, "close": 100.0})
    path.loc[path["timestamp"].eq(pd.Timestamp("2025-01-02 10:35")), ["high", "low"]] = [102.0, 98.0]
    path.loc[path["timestamp"].eq(pd.Timestamp("2025-01-02 10:50")), "high"] = 100.6
    path.loc[path["timestamp"].eq(pd.Timestamp("2025-01-02 10:50")), "low"] = 99.4
    path.loc[path["timestamp"].eq(pd.Timestamp("2025-01-02 11:05")), "close"] = 101.0
    source = tmp_path / "underlying.parquet"
    path.to_parquet(source, index=False)
    candidates = pd.DataFrame({
        "ticker": ["SPY", "SPY"], "trade_date": ["20250102", "20250102"], "minute": [635, 635],
        "spot": [100.0, 100.0], "wall_role": ["support", "resistance"],
        "candidate_wall_strike": [99.5, 100.5],
    })
    out = label_candidate_session(candidates, source)
    assert out["magnet_hit_30m"].eq(1.0).all()
    assert out.loc[0, "resolved_rejection_30m"] == 1.0
    assert out.loc[1, "resolved_rejection_30m"] == 0.0
    assert np.isnan(out.loc[0, "magnet_hit_60m"])


def test_model_allowlists_contain_no_future_or_outcome():
    assert_feature_allowlists()


def test_script_entrypoint_resolves_repo_package():
    script = Path(__file__).resolve().parents[1] / "neural" / "jepa" / "evaluate_wall_state_physical_separability_v1.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"], cwd=script.parents[2],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "physical separability" in result.stdout
