from __future__ import annotations

from pathlib import Path

import pandas as pd

import neural.jepa.build_h_ibqdyn1_feasibility as mod


def source_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": "SPY",
        "trade_date": "20240102",
        "expiration": "20240102",
        "dte_days": 0,
        "expiry_mode": "zero_dte",
        "option_price_mode": "executable_quote",
        "timestamp": "2024-01-02 10:35:00",
        "minute": 635,
        "spot": 470.0,
        "nearest_level_name": "ib_low",
        "nearest_level_abs_bps": 5.0,
        "call_d25_available": True,
        "call_d25_strike": 475.0,
        "put_d25_available": True,
        "put_d25_strike": 465.0,
        "call_d35_available": True,
        "call_d35_strike": 472.0,
        "put_d35_available": True,
        "put_d35_strike": 468.0,
    }
    row.update(overrides)
    return row


def test_source_column_allowlist_excludes_outcomes() -> None:
    forbidden = ("future", "target", "status", "win", "exit", "best_side")
    assert not [
        column
        for column in mod.SOURCE_COLUMNS
        if any(token in column.lower() for token in forbidden)
    ]


def test_normalize_source_is_fail_closed_on_2026(monkeypatch) -> None:
    monkeypatch.setattr(mod, "EXPECTED_SOURCE_ROWS", 1)
    good = mod._normalize_source_frame(pd.DataFrame([source_row()]))
    assert good.iloc[0]["decision_dt"] == pd.Timestamp("2024-01-02 10:35:00")
    bad = pd.DataFrame(
        [
            source_row(
                trade_date="20260102",
                expiration="20260102",
                timestamp="2026-01-02 10:35:00",
            )
        ]
    )
    try:
        mod._normalize_source_frame(bad)
    except AssertionError as exc:
        assert "invalid sealed" in str(exc)
    else:
        raise AssertionError("2026 source row was accepted")


def test_universe_uses_first_event_per_fixed_block(monkeypatch) -> None:
    raw = pd.DataFrame(
        [
            source_row(timestamp="2024-01-02 10:35:00", minute=635),
            source_row(timestamp="2024-01-02 10:40:00", minute=640),
            source_row(timestamp="2024-01-02 11:05:00", minute=665),
        ]
    )
    monkeypatch.setattr(mod, "EXPECTED_SOURCE_ROWS", 3)
    monkeypatch.setattr(mod, "EXPECTED_EVENTS", 2)
    monkeypatch.setattr(mod, "EXPECTED_BY_TICKER", {"SPY": 2})
    monkeypatch.setattr(mod, "EXPECTED_SAMPLE", {("SPY", "2024"): ("20240102", 635)})
    monkeypatch.setattr(mod, "sha256_file", lambda _path: mod.EXPECTED_SOURCE_SHA256)
    monkeypatch.setattr(pd, "read_parquet", lambda *_args, **_kwargs: raw.copy())
    universe = mod.load_opportunity_universe("sealed.parquet")
    assert universe["minute"].tolist() == [635, 665]
    assert universe["call_strike"].tolist() == [472.0, 472.0]
    assert universe["preflight_sample"].tolist() == [True, False]


def test_listing_requires_exact_tminus5_contract_not_asof(tmp_path: Path) -> None:
    quotes_path = tmp_path / "quotes.parquet"
    manifest_path = tmp_path / "manifest.json"
    pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "expiration": "20240102",
                "timestamp": "2024-01-02 10:29:00",
                "strike": 472.0,
                "right": "C",
            },
            {
                "symbol": "SPY",
                "expiration": "20240102",
                "timestamp": "2024-01-02 10:29:00",
                "strike": 468.0,
                "right": "P",
            },
            {
                "symbol": "SPY",
                "expiration": "20240102",
                "timestamp": "2024-01-02 10:30:00",
                "strike": 472.0,
                "right": "C",
            },
            {
                "symbol": "SPY",
                "expiration": "20240102",
                "timestamp": "2024-01-02 10:30:00",
                "strike": 467.0,
                "right": "P",
            },
        ]
    ).to_parquet(quotes_path, index=False)
    manifest_path.write_text("{}", encoding="utf-8")
    candidate = pd.DataFrame(
        [
            {
                "event_id": "event",
                "ticker": "SPY",
                "trade_date": "20240102",
                "year": "2024",
                "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
                "subscription_dt": pd.Timestamp("2024-01-02 10:30:00"),
                "minute": 635,
                "nearest_level_name": "ib_low",
                "bucket": "d35",
                "call_strike": 472.0,
                "put_strike": 468.0,
                "preflight_sample": True,
            }
        ]
    )
    source = {
        "ticker": "SPY",
        "trade_date": "20240102",
        "origin": "test",
        "quotes_path": str(quotes_path),
        "quotes_sha256": mod.sha256_file(quotes_path),
        "session_manifest_path": str(manifest_path),
        "session_manifest_sha256": mod.sha256_file(manifest_path),
    }
    proof, _inventory = mod.audit_session(source, candidate)
    assert bool(proof.iloc[0]["exact_call_listed_tminus5m"])
    assert not bool(proof.iloc[0]["exact_put_listed_tminus5m"])
    assert not bool(proof.iloc[0]["causal_subscription_eligible"])
    assert proof.iloc[0]["eligibility_reason"] == "put_execution_contract_not_listed"


def test_frequency_capacity_applies_hold_and_caps() -> None:
    frame = pd.DataFrame(
        [
            {
                "ticker": "SPY",
                "trade_date": "20240102",
                "minute": minute,
                "causal_subscription_eligible": True,
            }
            for minute in (635, 640, 665, 695)
        ]
        + [
            {
                "ticker": "QQQ",
                "trade_date": "20240102",
                "minute": minute,
                "causal_subscription_eligible": True,
            }
            for minute in (635, 640, 665, 695)
        ]
    )
    capacity = mod.frequency_capacity(frame, eligible_only=True).set_index("ticker")
    assert int(capacity.loc["SPY", "max_trades_30m_cap"]) == 1
    assert int(capacity.loc["QQQ", "max_trades_30m_cap"]) == 2


def test_event_id_binds_both_execution_strikes() -> None:
    row = {
        "ticker": "SPY",
        "trade_date": "20240102",
        "decision_dt": pd.Timestamp("2024-01-02 10:35:00"),
        "nearest_level_name": "ib_low",
        "call_strike": 472.0,
        "put_strike": 468.0,
    }
    first = mod.event_id(row)
    second = mod.event_id({**row, "put_strike": 467.0})
    assert len(first) == 24
    assert first != second
