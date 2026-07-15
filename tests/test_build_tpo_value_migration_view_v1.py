from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from neural.jepa import build_tpo_value_migration_view_v1 as subject


def _bars(count: int = 61, *, start: str = "2023-01-03 09:30") -> pd.DataFrame:
    index = pd.date_range(start, periods=count, freq="min")
    close = 100.0 + np.linspace(0.0, 3.0, count)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "tick_count": 60.0,
        },
        index=index,
    )


def test_feature_allowlists_match_predeclared_hashes() -> None:
    assert len(subject.PAIRWISE_E0_FEATURES) == 30
    assert len(subject.TPO_FEATURES) == 36
    assert subject.hash_ordered(subject.PAIRWISE_E0_FEATURES) == subject.EXPECTED_X0_SHA256
    assert subject.hash_ordered(subject.TPO_FEATURES) == subject.EXPECTED_TPO_SHA256
    assert subject.hash_ordered([*subject.PAIRWISE_E0_FEATURES, *subject.TPO_FEATURES]) == subject.EXPECTED_X1_SHA256


def test_floor_lattice_counts_both_bins_on_exact_upper_boundary() -> None:
    accumulator = subject.TPOAccumulator(ib_low=100.0, ib_high=120.0)
    accumulator.add_bar(low=100.25, high=101.0, close=100.5)
    assert accumulator.counts == {0: 1, 1: 1}


def test_poc_tie_prefers_ib_midpoint_then_lower_price_and_value_tie_expands_lower() -> None:
    accumulator = subject.TPOAccumulator(ib_low=100.0, ib_high=120.0)
    # Equal maxima at centers 109.5 and 110.5; both are equally close to midpoint 110.
    accumulator.add_bar(low=109.1, high=109.2, close=109.2)
    accumulator.add_bar(low=110.1, high=110.2, close=110.2)
    profile = accumulator.snapshot()
    assert profile.poc == pytest.approx(109.5)
    # Equal adjacent counts resolve toward the lower-price bin first.
    assert profile.val == pytest.approx(109.0)
    assert profile.vah == pytest.approx(111.0)


def test_exact_session_consumes_only_completed_prefix_and_rejects_missing_bar() -> None:
    day = _bars(66)
    event = pd.Timestamp("2023-01-03 10:35")
    consumed = subject.exact_consumed_session(day, trade_date="20230103", maximum_event_timestamp=event)
    assert len(consumed) == 65
    assert consumed.index.max() == event - pd.Timedelta(minutes=1)
    broken = day.drop(pd.Timestamp("2023-01-03 10:00"))
    with pytest.raises(AssertionError, match="missing exact"):
        subject.exact_consumed_session(broken, trade_date="20230103", maximum_event_timestamp=event)


def test_profile_cache_never_consumes_cutoff_bar() -> None:
    bars = _bars(66)
    cache = subject.build_profile_cache(
        bars,
        [pd.Timestamp("2023-01-03 10:30"), pd.Timestamp("2023-01-03 10:35")],
        ib_low=99.5,
        ib_high=103.5,
    )
    assert len(cache[pd.Timestamp("2023-01-03 10:30")].closes) == 60
    assert len(cache[pd.Timestamp("2023-01-03 10:35")].closes) == 65
    assert cache[pd.Timestamp("2023-01-03 10:35")].reference == pytest.approx(
        bars.loc[pd.Timestamp("2023-01-03 10:34"), "close"]
    )


def test_value_location_is_unclipped_and_efficiency_uses_exact_h_transitions() -> None:
    closes = np.arange(31.0)
    assert subject._directional_efficiency(closes, 30) == pytest.approx(1.0)
    assert subject._directional_efficiency(np.ones(31), 30) == 0.0
    with pytest.raises(AssertionError, match="lacks"):
        subject._directional_efficiency(np.ones(30), 30)


def test_cross_rate_counts_entry_and_exit_of_touch() -> None:
    closes = np.asarray([99.0, 100.0, 100.0, 101.0, 99.0])
    assert subject._cross_rate(closes, 100.0) == pytest.approx(3 / 4)


def test_tpo_event_feature_contract_is_complete_finite_and_state_fractions_sum() -> None:
    bars = _bars(66)
    event = pd.Timestamp("2023-01-03 10:35")
    cutoffs = [event - pd.Timedelta(minutes=lag) for lag in (0, 5, 15, 30)]
    profiles = subject.build_profile_cache(bars, cutoffs, ib_low=99.5, ib_high=103.5)
    features = subject.tpo_features_for_event(
        profiles,
        event_timestamp=event,
        ib_low=99.5,
        ib_high=103.5,
    )
    assert tuple(features) == subject.TPO_FEATURES
    assert np.isfinite(np.asarray(list(features.values()))).all()
    assert (
        features["tpo_last3_inside_value_fraction"]
        + features["tpo_last3_above_value_fraction"]
        + features["tpo_last3_below_value_fraction"]
    ) == pytest.approx(1.0)


def test_distinctness_gate_rejects_constant_feature_cell() -> None:
    rows = []
    for ticker in ("QQQ", "SPXW", "SPY"):
        for year in ("2022", "2023", "2024", "2025"):
            for number in range(2):
                row = {"ticker": ticker, "trade_date": f"{year}010{number + 1}"}
                row.update({feature: float(number) for feature in subject.TPO_FEATURES})
                rows.append(row)
    frame = pd.DataFrame(rows)
    passing = subject.distinctness_audit(frame)
    assert passing["pass"].all()
    frame.loc[frame["ticker"].eq("SPXW") & frame["trade_date"].str.startswith("2024"), subject.TPO_FEATURES[0]] = 0.0
    rejected = subject.distinctness_audit(frame)
    cell = rejected.loc[
        rejected["ticker"].eq("SPXW")
        & rejected["year"].eq("2024")
        & rejected["feature"].eq(subject.TPO_FEATURES[0])
    ].iloc[0]
    assert not bool(cell["pass"])


def test_output_paths_are_confined_to_frozen_tmp_root(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="output must remain"):
        subject._assert_output_path(tmp_path / "outside.parquet")


def test_session_checkpoint_roundtrip_and_source_hash_guard(tmp_path: Path) -> None:
    ticker = "SPY"
    trade_date = "20230103"
    events = pd.DataFrame(
        {
            "ticker": [ticker],
            "trade_date": [trade_date],
            "timestamp": [pd.Timestamp("2023-01-03 10:35")],
            "minute": [635],
        }
    )
    frame = events.copy()
    for index, feature in enumerate(subject.TPO_FEATURES):
        frame[feature] = float(index)
    source = tmp_path / "source.parquet"
    source.write_bytes(b"source")
    parquet = tmp_path / "checkpoint.parquet"
    manifest = tmp_path / "checkpoint.json"
    written = subject._write_session_checkpoint(
        frame=frame,
        parquet_path=parquet,
        manifest_path=manifest,
        source_path=source,
        source_sha256=subject.sha256_file(source),
        source_bytes=source.stat().st_size,
        source_rows=391,
        consumed_rows=65,
        first_consumed_timestamp="2023-01-03T09:30:00",
        last_consumed_timestamp="2023-01-03T10:34:00",
        event_keys_sha256=subject._event_key_sha256(events),
        builder_sha256="builder",
        protocol_sha256="protocol",
    )
    loaded = subject._load_valid_checkpoint(
        parquet_path=parquet,
        manifest_path=manifest,
        events=events,
        source_path=source,
        source_sha256=subject.sha256_file(source),
        builder_sha256="builder",
        protocol_sha256="protocol",
    )
    assert loaded is not None
    assert loaded[1] == written
    source.write_bytes(b"changed")
    assert (
        subject._load_valid_checkpoint(
            parquet_path=parquet,
            manifest_path=manifest,
            events=events,
            source_path=source,
            source_sha256=subject.sha256_file(source),
            builder_sha256="builder",
            protocol_sha256="protocol",
        )
        is None
    )


def test_checkpoint_manifest_is_committed_after_parquet(tmp_path: Path) -> None:
    manifest = tmp_path / "checkpoint.json"
    manifest.write_text(json.dumps({"status": "partial"}), encoding="utf-8")
    parquet = tmp_path / "checkpoint.parquet"
    assert (
        subject._load_valid_checkpoint(
            parquet_path=parquet,
            manifest_path=manifest,
            events=pd.DataFrame(columns=subject.KEY),
            source_path=tmp_path / "missing",
            source_sha256="missing",
            builder_sha256="builder",
            protocol_sha256="protocol",
        )
        is None
    )
