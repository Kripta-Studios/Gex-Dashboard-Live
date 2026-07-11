from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import event_option_live_snapshot as snapshot_builder
from neural.jepa.event_option_live_scorer import apply_candidate_universe_filter
from neural.jepa.event_option_live_snapshot import (
    _initial_balance_complete,
    _latest_spot_at,
    _prepare_chain,
    _standardize_spot_frame,
    add_live_cross_index_context_asof,
)
from neural.jepa.event_option_component_live import LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES
from neural.jepa.walkforward_event_option_gate import DeployConfig
from neural.jepa.walkforward_event_option_profile_selector import (
    ProfileConfig,
    build_features as build_profile_features,
    freeze_fold_policy_artifact,
    parse_ticker_int_grid_map,
    parse_ticker_int_map,
    write_policy_selection_provenance,
)


def test_candidate_filter_enforces_training_grid_and_complete_initial_balance() -> None:
    rows = pd.DataFrame(
        {
            "minute": [630, 631, 635, 640],
            "initial_balance_complete": [1, 1, 1, 0],
            "nearest_level_abs_bps": [5.0, 5.0, 5.0, 5.0],
        }
    )
    issues: list[str] = []
    filtered = apply_candidate_universe_filter(
        rows,
        {
            "entry_sample_minutes": 5,
            "entry_sample_anchor_minute_et": "10:00",
            "requires_complete_initial_balance": True,
            "near_level_abs_bps_max": 20.0,
            "min_entry_time_et": "10:30",
        },
        label="test",
        issues=issues,
    )

    assert issues == []
    assert filtered["minute"].tolist() == [630, 635]


def test_nested_profile_selector_excludes_live_inconsistent_intraday_features() -> None:
    row = {
        "ticker": "SPY",
        "expiry_mode": "zero_dte",
        "nearest_level_name": "ib_high",
        "safe_current_feature": 1.0,
        **{name: float(index) for index, name in enumerate(LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)},
    }

    _frame, features = build_profile_features(pd.DataFrame([row]))

    assert "safe_current_feature" in features
    assert not (set(features) & LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)


def test_nested_profile_selector_parses_live_contract_overrides() -> None:
    assert parse_ticker_int_map(
        ["SPXW=0", "QQQ=30", "SPY=0"],
        field_name="cooldown",
    ) == {"SPXW": 0, "QQQ": 30, "SPY": 0}
    assert parse_ticker_int_grid_map(
        ["SPXW=1,2,4", "QQQ=1,2", "SPY=1"],
        field_name="max_day",
    ) == {"SPXW": [1, 2, 4], "QQQ": [1, 2], "SPY": [1]}


def test_nested_profile_selector_freezes_hashed_fold_artifacts(tmp_path: Path) -> None:
    args = argparse.Namespace(
        cooldown_minutes=30,
        ticker_cooldown_map={"SPY": 0},
    )
    artifact = freeze_fold_policy_artifact(
        tmp_path / "202601" / "SPY",
        ticker="SPY",
        test_month="202601",
        profile=ProfileConfig(
            name="target_zero_dte_d35_return",
            delta_bucket=35,
            label_mode="return",
            expiry_modes=("zero_dte",),
            train_scope="target",
        ),
        train_months=["202501", "202502"],
        selection_months=["202511", "202512"],
        deploy_config=DeployConfig(0.1, 1),
        call_model={"kind": "call"},
        put_model={"kind": "put"},
        medians=pd.Series({"safe_feature": 1.0}),
        feature_cols=["safe_feature"],
        args=args,
    )

    manifest_path = Path(artifact["policy_artifact_path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["policy_frozen_before_evaluation"] is True
    assert payload["cooldown_minutes"] == 0
    assert len(artifact["policy_artifact_sha256"]) == 64
    assert len(artifact["model_artifact_sha256"]) == 64


def test_nested_profile_selector_writes_combined_month_provenance(tmp_path: Path) -> None:
    folds = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "month": "202601",
                "selected": True,
                "profile": f"{ticker}_profile",
                "deploy_config": "thr0.100_maxday1",
                "training_months": "202501,202502",
                "selection_months": "202511,202512",
                "policy_artifact_path": f"{ticker}/fold_policy.json",
                "policy_artifact_sha256": ticker.lower().ljust(64, "0"),
            }
            for ticker in ("SPXW", "SPY", "QQQ")
        ]
    )

    provenance = write_policy_selection_provenance(
        tmp_path,
        folds,
        expected_months=["202601"],
        expected_tickers=["SPXW", "SPY", "QQQ"],
    )

    assert provenance["passed"] is True
    assert provenance["mode"] == "nested_walk_forward"
    assert provenance["folds"][0]["policy_frozen_before_evaluation"] is True
    assert len(provenance["folds"][0]["policy_artifact_sha256"]) == 64


def test_nested_profile_selector_provenance_accepts_frozen_abstentions(tmp_path: Path) -> None:
    folds = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "month": "202601",
                "selected": False,
                "profile": "ABSTAIN_NO_VALID_PROFILE",
                "training_months": "202501,202502",
                "selection_months": "202511,202512",
            }
            for ticker in ("SPXW", "SPY", "QQQ")
        ]
    )

    provenance = write_policy_selection_provenance(
        tmp_path,
        folds,
        expected_months=["202601"],
        expected_tickers=["SPXW", "SPY", "QQQ"],
    )

    assert provenance["passed"] is True
    assert provenance["folds"][0]["policy_frozen_before_evaluation"] is True


def test_candidate_filter_fails_closed_when_required_ib_flag_is_missing() -> None:
    issues: list[str] = []
    filtered = apply_candidate_universe_filter(
        pd.DataFrame({"minute": [630]}),
        {"requires_complete_initial_balance": True},
        label="test",
        issues=issues,
    )

    assert filtered.empty
    assert issues == ["test: initial_balance_complete missing for required IB contract"]


def test_prepare_chain_selects_complete_minute_anchor_cross_section() -> None:
    strikes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    contracts = [(strike, right) for strike in strikes for right in ("CALL", "PUT")]
    first = pd.Timestamp("2026-07-08 10:30:00")
    complete = pd.Timestamp("2026-07-08 10:30:01")
    partial = pd.Timestamp("2026-07-08 10:30:02")
    prior_bar = pd.Timestamp("2026-07-08 10:29:00")

    greek_rows: list[dict[str, object]] = []
    for timestamp, marker, subset in (
        (first, 1.0, contracts),
        (complete, 2.0, contracts),
        (partial, 3.0, contracts[:4]),
    ):
        for strike, right in subset:
            greek_rows.append(
                {
                    "underlying_timestamp": timestamp,
                    "strike": strike,
                    "right": right,
                    "underlying_price": 100.0,
                    "delta": 0.35 if right == "CALL" else -0.35,
                    "implied_vol": 0.2,
                    "theta": -0.1,
                    "vega": 0.1,
                    "bid": marker,
                    "ask": marker + 0.1,
                    "expiration": "20260708",
                }
            )
    oi = pd.DataFrame(
        [{"strike": strike, "right": right, "open_interest": 100.0} for strike, right in contracts]
    )
    ohlc_rows: list[dict[str, object]] = []
    for strike, right in contracts:
        ohlc_rows.extend(
            [
                {
                    "timestamp": prior_bar,
                    "strike": strike,
                    "right": right,
                    "close": 1.8,
                    "volume": 1.0,
                    "count": 1.0,
                },
                {
                    "timestamp": prior_bar + pd.Timedelta(seconds=30),
                    "strike": strike,
                    "right": right,
                    "close": 1.9,
                    "volume": 2.0,
                    "count": 2.0,
                },
                {
                    "timestamp": partial,
                    "strike": strike,
                    "right": right,
                    "close": 999.0,
                    "volume": 999.0,
                    "count": 999.0,
                },
            ]
        )

    chain = _prepare_chain(pd.DataFrame(greek_rows), oi, pd.DataFrame(ohlc_rows), require_open_interest=True)

    assert len(chain) == len(contracts)
    assert chain[["strike", "right"]].drop_duplicates().shape[0] == len(contracts)
    assert chain["dt"].nunique() == 1
    assert chain["dt"].iloc[0] == first
    assert np.allclose(chain["bid"], 1.0)
    assert np.allclose(chain["opt_close"], 1.9)
    assert np.allclose(chain["opt_volume"], 3.0)
    assert np.allclose(chain["opt_count"], 3.0)


def test_latest_spot_refuses_future_fallback() -> None:
    spot = pd.DataFrame(
        {
            "dt": pd.to_datetime(["2026-07-08 10:31:00"]),
            "minute": [631],
            "close": [100.0],
        }
    )

    value, minute = _latest_spot_at(spot, pd.Timestamp("2026-07-08 10:30:59"))

    assert np.isnan(value)
    assert minute == -1


def test_live_spot_volume_maps_to_historical_tick_count_feature() -> None:
    spot = _standardize_spot_frame(
        pd.DataFrame(
            {
                "timestamp": ["2026-07-08 10:29:00"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [60],
            }
        )
    )

    assert spot["tick_count"].tolist() == [60.0]


def test_initial_balance_requires_every_minute() -> None:
    complete = pd.DataFrame({"minute": list(range(570, 630))})
    missing = complete[complete["minute"] != 601]

    assert _initial_balance_complete(complete)
    assert not _initial_balance_complete(missing)


def test_snapshot_rejects_complete_initial_balance_from_previous_day(monkeypatch, tmp_path) -> None:
    chain_dt = pd.Timestamp("2026-07-08 10:30:00")
    monkeypatch.setattr(
        snapshot_builder,
        "latest_chain_snapshot",
        lambda *_args, **_kwargs: pd.DataFrame(
            {"dt": [chain_dt], "underlying_price": [100.0], "expiration": ["20260708"]}
        ),
    )
    prior_day = pd.Timestamp("2026-07-07")
    stale_spot = pd.DataFrame(
        {
            "dt": [prior_day + pd.Timedelta(minutes=minute) for minute in range(570, 630)],
            "minute": list(range(570, 630)),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "tick_count": 60.0,
        }
    )
    monkeypatch.setattr(snapshot_builder, "load_spot_history", lambda *_args, **_kwargs: stale_spot)

    row = snapshot_builder.build_snapshot_row(day_dir=tmp_path, ticker="SPY", suffix="0dte")

    assert row is None


def test_live_context_prefers_zero_dte_over_front_weekly() -> None:
    frame = pd.DataFrame(
        [
            {
                "ticker": "SPXW",
                "trade_date": "20260708",
                "minute": 630,
                "expiry_mode": "front_weekly",
                "timestamp": "2026-07-08T10:30:00",
                "spot": 999.0,
                "ret_5m_bps": 99.0,
            },
            {
                "ticker": "SPXW",
                "trade_date": "20260708",
                "minute": 630,
                "expiry_mode": "zero_dte",
                "timestamp": "2026-07-08T10:30:00",
                "spot": 100.0,
                "ret_5m_bps": 10.0,
            },
            {
                "ticker": "SPY",
                "trade_date": "20260708",
                "minute": 631,
                "expiry_mode": "zero_dte",
                "timestamp": "2026-07-08T10:31:00",
                "spot": 50.0,
                "ret_5m_bps": 5.0,
            },
        ]
    )

    enriched = add_live_cross_index_context_asof(frame, max_context_age_minutes=3)
    spy = enriched[enriched["ticker"] == "SPY"].iloc[0]

    assert spy["ctx_spx_spot"] == 100.0
    assert spy["ctx_spx_ret_5m_bps"] == 10.0
