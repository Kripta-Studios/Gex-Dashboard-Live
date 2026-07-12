from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import neural.jepa.build_wall_iv_surface_deformation_dataset as mod
from neural.jepa.surface_flow_features import CONTROL_FEATURES


def candidate_frame() -> pd.DataFrame:
    row = {
        "ticker": "QQQ", "trade_date": "20240102", "minute": 650,
        "decision_dt": pd.Timestamp("2024-01-02 10:50"), "wall_identity": "call_gamma",
        "wall_role": "resistance", "candidate_right": "CALL",
        "candidate_wall_strike": 410.0, "spot": 409.5, "wall_alias_count": 1,
        "episode_sequence": 1, "episode_start_minute": 650, "episode_id": "x",
    }
    row.update({column: 0.0 for column in CONTROL_FEATURES})
    return pd.DataFrame([row])


def test_load_candidates_reads_only_frozen_allowlist(tmp_path, monkeypatch):
    frame = candidate_frame()
    frame["future_physical_label"] = 1
    parquet = tmp_path / "candidates.parquet"
    frame.to_parquet(parquet, index=False)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": mod.EXPECTED_CANDIDATE_MANIFEST_SCHEMA, "status": "PASS_DATA_GATE",
        "holdout_2026_used": False, "dataset_sha256": "frozen", "rows": 1,
        "full_session_universe_count": mod.EXPECTED_SESSION_COUNT,
        "full_session_key_sha256": mod.EXPECTED_SESSION_KEY_SHA256,
    }))
    monkeypatch.setattr(mod, "EXPECTED_CANDIDATE_SHA256", "frozen")
    monkeypatch.setattr(mod, "EXPECTED_CANDIDATE_ROWS", 1)
    monkeypatch.setattr(mod, "sha256_file", lambda path: "frozen")
    loaded, _ = mod.load_sealed_candidates(parquet, manifest)
    assert "future_physical_label" not in loaded
    assert list(loaded.columns) == list(mod.CANDIDATE_COLUMNS)


def test_load_candidates_rejects_2026(tmp_path, monkeypatch):
    frame = candidate_frame()
    frame["trade_date"] = "20260102"
    frame["decision_dt"] = pd.Timestamp("2026-01-02 10:50")
    parquet = tmp_path / "candidates.parquet"
    frame.to_parquet(parquet, index=False)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": mod.EXPECTED_CANDIDATE_MANIFEST_SCHEMA, "status": "PASS_DATA_GATE",
        "holdout_2026_used": False, "dataset_sha256": "frozen", "rows": 1,
        "full_session_universe_count": mod.EXPECTED_SESSION_COUNT,
        "full_session_key_sha256": mod.EXPECTED_SESSION_KEY_SHA256,
    }))
    monkeypatch.setattr(mod, "EXPECTED_CANDIDATE_SHA256", "frozen")
    monkeypatch.setattr(mod, "EXPECTED_CANDIDATE_ROWS", 1)
    monkeypatch.setattr(mod, "sha256_file", lambda path: "frozen")
    with pytest.raises(AssertionError, match="future candidate"):
        mod.load_sealed_candidates(parquet, manifest)


def test_profile_retains_invalid_rows_and_reports_missingness():
    rows = []
    for valid in (True, False):
        row = {"ticker": "SPY", "trade_date": "20240102", "minute": 650,
               "surface_both_valid": valid, "surface_call_valid": valid,
               "surface_put_valid": valid}
        for column in mod.IV_SURFACE_ALLOWLIST:
            row.setdefault(column, 1.0 if valid else np.nan)
        rows.append(row)
    coverage, profile = mod.profile_dataset(pd.DataFrame(rows))
    assert len(coverage) == 1
    assert coverage.iloc[0].surface_both_valid == pytest.approx(.5)
    feature = profile[profile.feature.eq(mod.IV_SURFACE_FEATURES[0])].iloc[0]
    assert feature.rows == 2 and feature.finite == 1
    assert feature.missing_rate == pytest.approx(.5)
