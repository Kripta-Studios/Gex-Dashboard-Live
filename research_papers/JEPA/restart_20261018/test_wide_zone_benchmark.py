"""Synthetic causal/accounting checks; no market data access."""

import importlib.util
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    "wide_zone_benchmark", Path(__file__).with_name("wide_zone_benchmark.py")
)
z = importlib.util.module_from_spec(spec)
spec.loader.exec_module(z)


def test_ib_ignores_current_future_and_invalid_samples():
    times = pd.date_range("2023-01-03 09:30", periods=100, freq="min")
    s = pd.Series(np.arange(100) + 100.0, index=times)
    s.iloc[0] = np.nan
    expected = z.ib_bounds(s, pd.Timestamp("2023-01-03 10:35"))
    s.loc["2023-01-03 10:30":] = 1e10
    assert expected == (101.0, 159.0)
    assert z.ib_bounds(s, pd.Timestamp("2023-01-03 10:35")) == expected
    assert z.ib_bounds(s, pd.Timestamp("2023-01-03 10:29")) is None
    s.iloc[:4] = np.nan
    assert z.ib_bounds(s, pd.Timestamp("2023-01-03 10:35")) is None


def test_contract_selection_no_late_quote_and_tie_strike():
    ts = pd.Timestamp("2023-01-03 10:34")
    f = pd.DataFrame(
        {
            "timestamp": [ts, ts, ts + pd.Timedelta(minutes=1)],
            "right": ["CALL"] * 3,
            "strike": [101.0, 100.0, 99.0],
            "delta": [0.4, 0.4, 0.5],
            "bid": [1.0] * 3,
            "ask": [1.1] * 3,
        }
    )
    assert z.contract_at(f, ts, "CALL").strike == 100.0
    f.loc[2, "delta"] = 0.01
    assert z.contract_at(f, ts, "CALL").strike == 100.0


def test_same_contract_missing_entry_does_not_reselect():
    ts = pd.Timestamp("2023-01-03 10:36")
    candidates = [
        {
            "strike": 100.0,
            "right": "CALL",
            "entry_time": ts,
            "exit_time": ts + pd.Timedelta(minutes=30),
            "event_id": "a",
        }
    ]
    counts = Counter()
    rows = z.labels_for(candidates, {(101.0, "CALL", ts): (1.0, 1.1)}, counts)
    assert np.isnan(rows[0]["net"])
    assert counts["missing_entry"] == 1


def test_missing_exit_zero_and_accounting():
    ts = pd.Timestamp("2023-01-03 10:36")
    candidates = [
        {
            "strike": 100.0,
            "right": "CALL",
            "entry_time": ts,
            "exit_time": ts + pd.Timedelta(minutes=30),
            "event_id": "a",
        }
    ]
    counts = Counter()
    rows = z.labels_for(candidates, {(100.0, "CALL", ts): (1.0, 1.1)}, counts)
    assert rows[0]["missing_exit"]
    assert rows[0]["net"] == pytest.approx(-113.6)
    assert rows[0]["adverse_net"] == pytest.approx(-114.6)
    assert z.payoff(1, 1.2) == pytest.approx(15.4)


def test_no_overlap_next_decision_precedes_existing_exit():
    rows = []
    for i, minute in enumerate((35, 65, 95)):
        d = pd.Timestamp("2023-01-03 10:00") + pd.Timedelta(minutes=minute)
        rows.append(
            {
                "decision": str(d),
                "ticker_name": "SPY",
                "right": "CALL",
                "prediction": 10.0,
                "net": 1.0,
                "exit_time": str(d + pd.Timedelta(minutes=31)),
                "event_id": str(i),
            }
        )
    ledger = z.schedule(pd.DataFrame(rows), 0)
    assert ledger.event_id.tolist() == ["0", "2"]
    assert z.schedule(pd.DataFrame(rows), None).empty
    assert z.schedule(pd.DataFrame(rows), 10).empty


def test_invalid_selected_entry_no_action_replacement():
    d = pd.Timestamp("2023-01-03 10:35")
    f = pd.DataFrame(
        [
            {
                "decision": str(d),
                "ticker_name": "SPY",
                "right": side,
                "prediction": pred,
                "net": net,
                "exit_time": str(d + pd.Timedelta(minutes=31)),
            }
            for side, pred, net in [("CALL", 10, np.nan), ("PUT", 5, 20)]
        ]
    )
    assert z.schedule(f, 0).empty


def test_soft_zone_is_continuous_and_placebo_changes_location():
    a = z.soft_fields([100], [1], 100, 99, 10, "x")
    b = z.soft_fields([100], [1], 100.001, 99, 10, "x")
    p = z.soft_fields([103.7], [1], 100, 99, 10, "x")
    assert abs(a["x_influence10"] - b["x_influence10"]) < 1e-5
    assert p["x_influence10"] < a["x_influence10"]


def test_oi_future_report_not_visible():
    ts = pd.Timestamp("2023-01-03 10:34")
    oi = pd.DataFrame(
        {
            "strike": [100.0, 100.0],
            "right": ["CALL", "CALL"],
            "timestamp": [ts - pd.Timedelta(minutes=1), ts + pd.Timedelta(minutes=1)],
            "open_interest": [10.0, 999.0],
        }
    )
    assert z.oi_snapshot(oi, ts).open_interest.iloc[0] == 10.0


def test_features_unaffected_by_future_spot_perturbation_and_expose_missingness():
    ts = pd.Timestamp("2023-01-03 10:34")
    decision = ts + pd.Timedelta(minutes=1)
    s = pd.Series(
        np.arange(120) * 0.01 + 100.0,
        index=pd.date_range("2023-01-03 09:30", periods=120, freq="min"),
    )
    s.loc["2023-01-03 10:32"] = np.nan
    chain = pd.DataFrame(
        {
            "right": ["CALL", "PUT"],
            "strike": [100.0, 101.0],
            "open_interest": [10.0, 20.0],
            "gamma_density_proxy": [20.0, 40.0],
        }
    )
    a = z.features_for(
        s, chain, None, ts, decision, "SPY", z.ib_bounds(s, decision), {}, 0.0
    )
    s.loc[ts + pd.Timedelta(minutes=1) :] = 1e9
    b = z.features_for(
        s, chain, None, ts, decision, "SPY", z.ib_bounds(s, decision), {}, 0.0
    )
    for original, changed in zip(a, b):
        assert original.keys() == changed.keys()
        for key in original:
            assert original[key] == pytest.approx(changed[key], nan_ok=True)
    assert a[0]["candle5_observed_fraction"] == 0.8
    assert a[0]["ib_observed_minutes"] == 60


def test_identity_normalization_before_duplicates_and_off_grid():
    day = pd.Timestamp("2023-01-03")
    f = pd.DataFrame(
        {
            "symbol": ["SPY"] * 3,
            "expiration": ["2023-01-03"] * 3,
            "trade_date": ["2023-01-03"] * 3,
            "right": ["C", "CALL", "PUT"],
            "strike": ["100", 100.0, 101.0],
            "timestamp": [
                "2023-01-03T10:34:00",
                "2023-01-03T10:34:00",
                "2023-01-03T10:34:01",
            ],
        }
    )
    counts = Counter()
    z.clean_identity(f, "SPY", day, "greek", counts)
    assert f.empty
    assert counts["greek_duplicate_keys"] == 2
    assert counts["greek_invalid_identity"] == 1


def test_placebo_shift_is_reproducible_varied_and_not_feature():
    vals = [z.placebo_shift("SPY", f"202301{k:02d}") for k in range(1, 31)]
    assert vals[0] == z.placebo_shift("SPY", "20230101")
    assert all(0.2 <= abs(v) <= 0.8 for v in vals)
    assert len(set(vals)) == 30 and min(vals) < 0 < max(vals)
    assert z.placebo_shift("SPXW", "20230101") != vals[0]


def test_proxy_clock_preserves_exact_values_and_native_precedence():
    f = pd.DataFrame(
        {"underlying_timestamp": ["2025-01-03T09:30:01", "2025-01-03T10:34:00"]}
    )
    assert z.apply_clock(f, "greek") == "UNDERLYING_TIMESTAMP_PROXY"
    assert f.timestamp.equals(f.underlying_timestamp)
    assert z.apply_clock(f, "greek") == "NATIVE_TIMESTAMP"
    with pytest.raises(ValueError):
        z.apply_clock(pd.DataFrame({"x": [1]}), "greek")


def test_missing_oi_clock_assumption_flag_and_cutoff():
    f = pd.DataFrame(
        {
            "trade_date": ["2025-01-03"],
            "strike": [100.0],
            "right": ["CALL"],
            "open_interest": [25.0],
        }
    )
    assert z.apply_clock(f, "oi") == "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
    assert f.timestamp.iloc[0] == pd.Timestamp("2025-01-03 09:30")
    assert z.oi_snapshot(f, pd.Timestamp("2025-01-03 09:29")).empty
    assert len(z.oi_snapshot(f, pd.Timestamp("2025-01-03 09:30"))) == 1


def test_exchange_calendar_holidays_early_closes_and_h1_months():
    cal = z.session_calendar()
    full = cal.loc[cal.full_session, "date"].tolist()
    assert "20230102" not in full and "20260101" not in full
    assert "20250331" in full and "20260630" in full
    assert set(cal.loc[~cal.full_session, "date"]) == {
        "20230703",
        "20231124",
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
    assert sum(d >= "20260101" for d in full) == 123


def test_latency_preserves_action_prediction_and_uses_same_decision():
    f = pd.DataFrame(
        {
            "decision": ["2026-01-05 15:05:00"],
            "entry_time": ["2026-01-05 15:06:00"],
            "exit_time": ["2026-01-05 15:36:00"],
            "prediction": [19.0],
            "strike": [550.0],
            "right": ["CALL"],
        }
    )
    delayed = z.delayed_candidates(f, 5)
    assert delayed.entry_time.iloc[0] == "2026-01-05 15:10:00"
    assert delayed.exit_time.iloc[0] == "2026-01-05 15:40:00"
    for field in ("prediction", "strike", "right", "decision"):
        assert delayed[field].equals(f[field])
    with pytest.raises(ValueError):
        z.delayed_candidates(f, 6)


def test_loader_proxy_oi_schema_masks_and_identity(tmp_path, monkeypatch):
    ticker = "SPY"
    date = "20250103"
    monkeypatch.setattr(z, "ROOT", tmp_path)
    stamp = "2025-01-03T10:34:00"
    greek = pd.DataFrame(
        {
            "symbol": [ticker, ticker],
            "expiration": ["2025-01-03"] * 2,
            "trade_date": ["2025-01-03"] * 2,
            "strike": [100.0, 101.0],
            "right": ["CALL", "PUT"],
            "underlying_timestamp": [stamp, stamp],
            "underlying_price": [100.5, 100.5],
            "delta": [0.5, -0.5],
            "bid": [1.0, 1.0],
            "ask": [1.1, 1.1],
            "implied_vol": [0.2, 0.2],
            "vega": [1.0, 1.0],
            "theta": [-0.1, -0.1],
        }
    )
    oi = pd.DataFrame(
        {
            "symbol": [ticker],
            "expiration": ["2025-01-03"],
            "trade_date": ["2025-01-03"],
            "strike": [100.0],
            "right": ["CALL"],
            "open_interest": [10.0],
        }
    )
    gp = z.source_path(ticker, date, "greeks")
    op = z.source_path(ticker, date, "oi")
    gp.parent.mkdir(parents=True)
    op.parent.mkdir(parents=True)
    greek.to_parquet(gp)
    oi.to_parquet(op)
    hashes = {}
    counts = Counter()
    g, o, spot, actual = z.read_day(gp, ticker, counts, hashes)
    assert actual == date and len(g) == 2 and spot.iloc[0] == 100.5
    assert hashes[str(gp)]["clock_source"] == "UNDERLYING_TIMESTAMP_PROXY"
    assert hashes[str(op)]["clock_source"] == "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
    chain, context = z.chain_context(g, o, pd.Timestamp(stamp), 100.5, counts)
    assert context["oi_missing_count"] == 1 and context["oi_missing_fraction"] == 0.5
    assert chain.open_interest.sum() == 10.0


def test_testyear_day_worker_produces_features_but_no_payoffs(tmp_path, monkeypatch):
    monkeypatch.setattr(z, "ROOT", tmp_path)
    ticker, date = "SPY", "20260105"
    times = pd.date_range("2026-01-05 09:30", periods=391, freq="min")
    rows = []
    for i, stamp in enumerate(times):
        for side, delta in [("CALL", 0.5), ("PUT", -0.5)]:
            rows.append(
                {
                    "symbol": ticker,
                    "expiration": "2026-01-05",
                    "trade_date": "2026-01-05",
                    "strike": 100.0,
                    "right": side,
                    "underlying_timestamp": stamp,
                    "underlying_price": 100.0 + 0.01 * i,
                    "delta": delta,
                    "bid": 1.0,
                    "ask": 1.1,
                    "implied_vol": 0.2,
                    "vega": 1.0,
                    "theta": -0.1,
                }
            )
    greek = pd.DataFrame(rows)
    oi = pd.DataFrame(
        {
            "symbol": [ticker] * 2,
            "expiration": ["2026-01-05"] * 2,
            "trade_date": ["2026-01-05"] * 2,
            "strike": [100.0] * 2,
            "right": ["CALL", "PUT"],
            "open_interest": [10.0, 20.0],
        }
    )
    gp, op = z.source_path(ticker, date, "greeks"), z.source_path(ticker, date, "oi")
    gp.parent.mkdir(parents=True)
    op.parent.mkdir(parents=True)
    greek.to_parquet(gp)
    oi.to_parquet(op)
    events, candidates, labels, hashes, counts, iv, coverage = z.process_day(
        (ticker, gp, {"date": date, "ticker": ticker, "events": 0})
    )
    assert len(events) == 10 and len(candidates) == 20 and labels == []
    assert coverage["events"] == 10
    assert all(
        r["oi_clock_source"] == "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT" for r in events
    )
    assert all(
        pd.Timestamp(r["feature_time"])
        < pd.Timestamp(r["decision"])
        < pd.Timestamp(r["entry_time"])
        for r in candidates
    )
