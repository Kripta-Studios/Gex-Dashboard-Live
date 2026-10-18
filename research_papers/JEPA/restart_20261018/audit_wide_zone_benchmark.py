"""Independent audit of the fixed wide zone benchmark; no producer imports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import exchange_calendars as xc
import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

TICKERS = ("SPXW", "SPY", "QQQ")
ARMS = ("price", "authentic", "placebo")
DELAYS = (1, 2, 5)
SEED = 20261018


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for data in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, message):
    require(
        bool(np.isclose(float(actual), float(expected), rtol=0, atol=1e-7, equal_nan=True)),
        message,
    )


def parse_time(values):
    result = pd.to_datetime(values, format="ISO8601", errors="coerce")
    require(result.dt.tz is None, "Unexpected timezone in raw source")
    return result


def expected_calendar():
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-01":"2026-06-30"].copy()
    schedule["date"] = schedule.index.strftime("%Y%m%d")
    schedule["full_session"] = (
        schedule["close"] - schedule["open"]
    ) == pd.Timedelta(hours=6, minutes=30)
    return schedule


def clean_identity(frame, ticker, date, greek):
    day = pd.Timestamp(date)
    frame = frame.copy()
    frame["right"] = frame.right.astype(str).str.upper().replace({"C": "CALL", "P": "PUT"})
    frame["strike"] = pd.to_numeric(frame.strike, errors="coerce")
    frame["timestamp"] = parse_time(frame.timestamp)
    frame["expiration"] = parse_time(frame.expiration.astype(str)).dt.normalize()
    frame["trade_date"] = parse_time(frame.trade_date.astype(str)).dt.normalize()
    keep = (
        (frame.symbol == ticker)
        & (frame.expiration == day)
        & (frame.trade_date == day)
        & (frame.timestamp.dt.normalize() == day)
        & frame.right.isin(["CALL", "PUT"])
        & np.isfinite(frame.strike)
        & (frame.strike > 0)
    )
    if greek:
        keep &= (
            (frame.timestamp == frame.timestamp.dt.floor("min"))
            & (frame.timestamp >= day + pd.Timedelta(hours=9, minutes=30))
            & (frame.timestamp <= day + pd.Timedelta(hours=16))
        )
    frame = frame.loc[keep].copy()
    return frame.loc[
        ~frame.duplicated(["strike", "right", "timestamp"], keep=False)
    ].copy()


def load_greek(path, ticker, date):
    schema = set(pq.read_schema(path).names)
    clock = "NATIVE_TIMESTAMP" if "timestamp" in schema else "UNDERLYING_TIMESTAMP_PROXY"
    cols = [
        "symbol", "expiration", "trade_date", "strike", "right", "bid", "ask", "delta"
    ]
    cols += ["timestamp"] if "timestamp" in schema else ["underlying_timestamp"]
    if "timestamp" in schema and "underlying_timestamp" in schema:
        cols.append("underlying_timestamp")
    frame = pq.read_table(path, columns=list(dict.fromkeys(cols))).to_pandas()
    mismatch = None
    if "timestamp" in frame and "underlying_timestamp" in frame:
        mismatch = int((parse_time(frame.timestamp) != parse_time(frame.underlying_timestamp)).sum())
    if "timestamp" not in frame:
        frame["timestamp"] = frame.underlying_timestamp
    frame = clean_identity(frame, ticker, date, True)
    valid = (
        np.isfinite(frame.bid)
        & np.isfinite(frame.ask)
        & (frame.bid >= 0)
        & (frame.ask > 0)
        & (frame.bid <= frame.ask)
    )
    return frame, frame.loc[valid].copy(), clock, mismatch


def load_oi(path, ticker, date):
    schema = set(pq.read_schema(path).names)
    cols = ["symbol", "expiration", "trade_date", "strike", "right", "open_interest"]
    if "timestamp" in schema:
        cols.append("timestamp")
        clock = "NATIVE_TIMESTAMP"
    else:
        clock = "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
    frame = pq.read_table(path, columns=cols).to_pandas()
    if "timestamp" not in frame:
        frame["timestamp"] = (
            parse_time(frame.trade_date.astype(str)).dt.normalize()
            + pd.Timedelta(hours=9, minutes=30)
        )
    frame = clean_identity(frame, ticker, date, False)
    frame["open_interest"] = pd.to_numeric(frame.open_interest, errors="coerce")
    valid = (
        np.isfinite(frame.open_interest)
        & (frame.open_interest >= 0)
        & (frame.open_interest % 1 == 0)
    )
    return frame.loc[valid].copy(), clock


def net_dollars(ask, bid, delay_adverse=False):
    slip = Decimal(".02" if delay_adverse else ".01")
    proceeds = max(Decimal(str(bid)) - slip, Decimal(0))
    return float((proceeds - Decimal(str(ask)) - slip) * 100 - Decimal("2.60"))


def independent_schedule(rows, threshold, delay):
    if threshold is None:
        return rows.iloc[:0].copy()
    keep = []
    released = {}
    groups = {}
    for row in rows.to_dict("records"):
        groups.setdefault((row["decision"], row["ticker_name"]), []).append(row)
    for event in sorted(groups):
        choices = groups[event]
        require(all(np.isfinite(r["prediction"]) for r in choices), "Nonfinite prediction")
        selected = min(choices, key=lambda r: (-r["prediction"], r["right"]))
        decision = pd.Timestamp(selected["decision"])
        ticker = selected["ticker_name"]
        if selected["prediction"] <= threshold or decision < released.get(ticker, pd.Timestamp.min):
            continue
        if not np.isfinite(selected["net"]):
            continue
        entry = pd.Timestamp(selected["entry_time"])
        exit_time = pd.Timestamp(selected["exit_time"])
        require(entry == decision + pd.Timedelta(minutes=delay), "Entry delay mismatch")
        require(exit_time == entry + pd.Timedelta(minutes=30), "Hold mismatch")
        keep.append(selected)
        released[ticker] = exit_time
    return pd.DataFrame(keep, columns=rows.columns)


def metrics(rows):
    result = {"trades": len(rows)}
    for field, name in (("net", "base"), ("adverse_net", "adverse")):
        values = rows[field].to_numpy(float)
        gains = values[values > 0].sum()
        losses = -values[values < 0].sum()
        result[name + "_net_usd"] = float(values.sum())
        result[name + "_win_rate"] = float(np.mean(values > 0)) if len(values) else None
        result[name + "_profit_factor"] = float(gains / losses) if losses > 0 else None
    return result


def compare_metrics(actual, reported, context):
    require(actual.keys() == reported.keys(), "Metric keys differ " + context)
    for key, value in actual.items():
        if value is None:
            require(reported[key] is None, f"{context} {key}")
        else:
            close(value, reported[key], f"{context} {key}")


def compare_frames(left, right, keys, context):
    left = left.sort_values(keys).reset_index(drop=True)
    right = right.sort_values(keys).reset_index(drop=True)
    require(left.columns.tolist() == right.columns.tolist(), context + " columns")
    require(len(left) == len(right), context + " rows")
    for col in left:
        if pd.api.types.is_numeric_dtype(left[col]):
            require(
                np.allclose(
                    left[col].to_numpy(float), right[col].to_numpy(float),
                    rtol=0, atol=1e-7, equal_nan=True,
                ),
                f"{context} {col}",
            )
        else:
            require(
                left[col].fillna("<NA>").equals(right[col].fillna("<NA>")),
                f"{context} {col}",
            )


def audit(root, output):
    freeze = json.loads((root / "freeze.json").read_text(encoding="utf-8"))
    identity = json.loads((root / "run_identity.json").read_text(encoding="utf-8"))
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    completion = json.loads((root / "completion.json").read_text(encoding="utf-8"))
    sources = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    coverage = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
    require(completion["summary_sha256"] == digest(root / "summary.json"), "Summary seal")
    require(completion["source_count"] == len(sources), "Source count")
    require(freeze["test_payoffs_constructed"] is False, "Freeze stage claim")
    seals = [
        ("frozen_predictions.parquet", "prediction_sha256"),
        ("features.parquet", "features_sha256"),
        ("candidates.parquet", "candidates_sha256"),
        ("sources.json", "sources_sha256"),
        ("train_validation_labels.parquet", "train_validation_labels_sha256"),
        ("wide_zone_benchmark.py", "script_sha256"),
        ("WIDE_BENCHMARK_SPEC.md", "spec_sha256"),
    ]
    for filename, key in seals:
        require(digest(root / filename) == freeze[key], "Frozen hash " + filename)
    require(identity["script_sha256"] == freeze["script_sha256"], "Run code identity")
    require(identity["spec_sha256"] == freeze["spec_sha256"], "Run spec identity")
    for filename, expected in freeze["models"].items():
        require(digest(root / filename) == expected, "Model seal " + filename)
    require(
        datetime.fromisoformat(freeze["frozen_at_utc"]).timestamp()
        <= (root / "test_labels.parquet").stat().st_mtime,
        "Test labels predate freeze",
    )

    source_results = {}
    for n, (path, metadata) in enumerate(sources.items()):
        source = Path(path)
        require(source.stat().st_size == metadata["bytes"], "Source size " + path)
        actual = digest(source)
        require(actual == metadata["sha256"], "Source hash " + path)
        schema = set(pq.read_schema(source).names)
        if source.stem.endswith("_greeks"):
            clock = "NATIVE_TIMESTAMP" if "timestamp" in schema else "UNDERLYING_TIMESTAMP_PROXY"
            require(metadata["clock_source"] == clock, "Greek clock metadata " + path)
            require("paired_clock_mismatch_rows" in metadata, "Greek pair metadata " + path)
        else:
            clock = "NATIVE_TIMESTAMP" if "timestamp" in schema else "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"
            require(metadata["clock_source"] == clock, "OI clock metadata " + path)
        source_results[path] = actual
        if n % 100 == 0:
            print(json.dumps({"audit_stage": "source_rehash", "done": n + 1, "total": len(sources)}), flush=True)
    completion_rehash = json.loads((root / "source_rehash.json").read_text(encoding="utf-8"))
    require(set(completion_rehash) == set(sources), "Completion source rehash keys")
    require(all(completion_rehash.values()), "Producer final source rehash")

    calendar = expected_calendar()
    saved_calendar = pd.read_csv(root / "expected_calendar.csv", dtype={"date": str})
    require(saved_calendar.date.tolist() == calendar.date.tolist(), "Calendar dates")
    require(saved_calendar.full_session.astype(bool).tolist() == calendar.full_session.tolist(), "Calendar sessions")
    full_days = calendar.loc[calendar.full_session, "date"].tolist()
    test_days = [d for d in full_days if d >= "20260101"]
    require(len(test_days) == 123, "Expected H1 full-session count")
    require(
        coverage["expected_full_sessions_per_ticker"] == len(full_days),
        "Coverage expected-session count",
    )
    session_coverage = pd.read_csv(root / "session_coverage.csv", dtype={"date": str})
    require(len(session_coverage) == len(full_days) * len(TICKERS), "Session coverage rows")
    require(
        set(zip(session_coverage.ticker, session_coverage.date, strict=True))
        == {(ticker, day) for ticker in TICKERS for day in full_days},
        "Session coverage membership",
    )

    features = pd.read_parquet(root / "features.parquet")
    candidates = pd.read_parquet(root / "candidates.parquet")
    predictions = pd.read_parquet(root / "frozen_predictions.parquet")
    train_labels = pd.read_parquet(root / "train_validation_labels.parquet")
    test_labels = pd.read_parquet(root / "test_labels.parquet")
    latency_labels = pd.read_parquet(root / "test_latency_labels.parquet")
    require(not features.event_id.duplicated().any(), "Feature duplicates")
    require(not candidates.duplicated(["event_id", "right"]).any(), "Candidate duplicates")
    require(not predictions.duplicated(["representation", "event_id", "right"]).any(), "Prediction duplicates")
    require(not train_labels.duplicated(["event_id", "right"]).any(), "Train label duplicates")
    require(not test_labels.duplicated(["event_id", "right"]).any(), "Test label duplicates")
    require((train_labels.event_id.str.split("_").str[1] < "20260101").all(), "Future pretest label")
    require((test_labels.event_id.str.split("_").str[1] >= "20260101").all(), "Earlier test label")
    require(set(latency_labels.entry_delay_minutes.unique()) == {2, 5}, "Latency labels")
    require(not set(("net", "entry_ask", "exit_bid", "missing_exit")).intersection(predictions), "Outcome in predictions")
    labels = pd.concat([train_labels, test_labels], ignore_index=True)
    require(len(labels) == len(candidates), "Candidate/label cardinality")
    require(len(predictions) == len(candidates) * 3, "Prediction cardinality")
    labeled = candidates.merge(labels, on=["event_id", "right"], validate="one_to_one")
    for row in labeled.itertuples(index=False):
        if pd.isna(row.entry_ask):
            require(pd.isna(row.net) and pd.isna(row.adverse_net), "Missing entry payoff")
        else:
            close(net_dollars(row.entry_ask, row.exit_bid), row.net, "Base accounting")
            close(net_dollars(row.entry_ask, row.exit_bid, True), row.adverse_net, "Adverse accounting")
            require(not row.missing_exit or row.exit_bid == 0, "Missing exit proceeds")
    for row in latency_labels.itertuples(index=False):
        if pd.isna(row.entry_ask):
            require(pd.isna(row.net) and pd.isna(row.adverse_net), "Latency missing entry payoff")
        else:
            close(net_dollars(row.entry_ask, row.exit_bid), row.net, "Latency base accounting")
            close(net_dollars(row.entry_ask, row.exit_bid, True), row.adverse_net, "Latency adverse accounting")

    matrix = labeled.merge(features, on=["event_id", "date", "ticker_name", "decision"], validate="many_to_one")
    refits = []
    for arm in ARMS:
        cols = freeze["representations"][arm]["features"]
        expected_prefix = {"price": "p_", "authentic": "a_", "placebo": "z_"}[arm]
        require(all(c.startswith("p_") or c.startswith(expected_prefix) for c in cols), "Feature family " + arm)
        for side in ("CALL", "PUT"):
            train = matrix.loc[(matrix.date < "20250101") & (matrix.right == side) & matrix.net.notna()]
            all_side = matrix.loc[matrix.right == side]
            saved = lgb.Booster(model_file=str(root / f"model_{arm}_{side}.txt"))
            saved_prediction = saved.predict(all_side[cols].to_numpy(float))
            actual = predictions.loc[(predictions.representation == arm) & (predictions.right == side)]
            aligned = all_side[["event_id", "right"]].merge(
                actual[["event_id", "right", "prediction"]],
                on=["event_id", "right"], validate="one_to_one",
            )
            require(np.array_equal(saved_prediction, aligned.prediction.to_numpy(float)), "Saved predictions " + arm + side)
            model = lgb.LGBMRegressor(**freeze["config"])
            model.fit(train[cols].to_numpy(float), train.net)
            independent = model.predict(all_side[cols].to_numpy(float))
            require(np.array_equal(independent, saved_prediction), "Independent refit " + arm + side)
            refits.append({"arm": arm, "side": side, "train_rows": len(train), "prediction_rows": len(all_side), "exact": True})
            print(json.dumps({"audit_stage": "independent_refit", "arm": arm, "side": side}), flush=True)

    joined = predictions.merge(labels, on=["event_id", "right"], validate="many_to_one")
    rebuilt_primary = []
    thresholds = {}
    for arm in ARMS:
        rows = joined.loc[joined.representation == arm]
        validation = rows.loc[rows.date.between("20250101", "20251231")]
        choices = []
        for threshold in (0, 5, 10):
            ledger = independent_schedule(validation, threshold, 1)
            counts = ledger.groupby("ticker_name").size().to_dict()
            choices.append({"threshold": threshold, "net": float(ledger.net.sum()), "counts": counts,
                            "qualifies": all(counts.get(t, 0) >= 10 for t in TICKERS)})
        for actual, expected in zip(choices, freeze["representations"][arm]["validation_choices"], strict=True):
            require(actual["threshold"] == expected["threshold"] and actual["counts"] == expected["counts"]
                    and actual["qualifies"] == expected["qualifies"], "Validation choice " + arm)
            close(actual["net"], expected["net"], "Validation net " + arm)
        qualified = [choice for choice in choices if choice["qualifies"]]
        threshold = min(qualified, key=lambda x: (-x["net"], x["threshold"]))["threshold"] if qualified else None
        require(threshold == freeze["representations"][arm]["threshold"], "Threshold " + arm)
        thresholds[arm] = threshold
        for period, lo, hi in (("validation", "20250101", "20260101"), ("test", "20260101", "20260701")):
            ledger = independent_schedule(rows.loc[(rows.date >= lo) & (rows.date < hi)], threshold, 1)
            ledger["period"] = period
            rebuilt_primary.append(ledger)
            reported = summary["results"][arm][period]
            compare_metrics(metrics(ledger), reported["pooled"], arm + period)
            for ticker in TICKERS:
                ticker_rows = ledger.loc[ledger.ticker_name == ticker]
                compare_metrics(metrics(ticker_rows), reported["tickers"][ticker], arm + period + ticker)
                for month, expected in reported["months"][ticker].items():
                    compare_metrics(metrics(ticker_rows.loc[ticker_rows.date.str.startswith(month)]), expected, arm + ticker + month)
    rebuilt_primary = pd.concat(rebuilt_primary, ignore_index=True)
    compare_frames(rebuilt_primary, pd.read_parquet(root / "ledger.parquet"),
                   ["representation", "period", "event_id", "right"], "Primary ledger")

    rebuilt_latency = []
    test_predictions = predictions.loc[predictions.date >= "20260101"].copy()
    for delay in (2, 5):
        delayed = test_predictions.copy()
        delayed["entry_time"] = (pd.to_datetime(delayed.decision) + pd.Timedelta(minutes=delay)).astype(str)
        delayed["exit_time"] = (pd.to_datetime(delayed.entry_time) + pd.Timedelta(minutes=30)).astype(str)
        delayed = delayed.merge(
            latency_labels.loc[latency_labels.entry_delay_minutes == delay],
            on=["event_id", "right"], validate="many_to_one",
        )
        for arm in ARMS:
            ledger = independent_schedule(delayed.loc[delayed.representation == arm], thresholds[arm], delay)
            rebuilt_latency.append(ledger)
            reported = summary["entry_delay_sensitivity_minutes"][str(delay)][arm]
            compare_metrics(metrics(ledger), reported["pooled"], f"delay{delay}{arm}")
            for ticker in TICKERS:
                ticker_rows = ledger.loc[ledger.ticker_name == ticker]
                compare_metrics(metrics(ticker_rows), reported["tickers"][ticker], f"delay{delay}{arm}{ticker}")
                for month, expected in reported["months"][ticker].items():
                    compare_metrics(metrics(ticker_rows.loc[ticker_rows.date.str.startswith(month)]), expected,
                                    f"delay{delay}{arm}{ticker}{month}")
    rebuilt_latency = pd.concat(rebuilt_latency, ignore_index=True)
    compare_frames(rebuilt_latency, pd.read_parquet(root / "latency_ledger.parquet"),
                   ["entry_delay_minutes", "representation", "event_id", "right"], "Latency ledger")

    selected = pd.concat(
        [rebuilt_primary.loc[rebuilt_primary.period == "test"], rebuilt_latency],
        ignore_index=True,
    ).drop_duplicates(["event_id", "right", "entry_time", "exit_time"])
    feature_index = features.set_index("event_id")
    raw_checked = 0
    mask_checked = 0
    fallback_checked = 0
    for (ticker, date), rows in selected.groupby(["ticker_name", "date"]):
        greek_paths = [Path(p) for p in sources if Path(p).name == f"{ticker}_{date}_{date}_greeks.parquet"]
        oi_paths = [Path(p) for p in sources if Path(p).name == f"{ticker}_{date}_{date}_oi.parquet"]
        require(len(greek_paths) == len(oi_paths) == 1, "Raw source mapping")
        greek_all, greek_quotes, greek_clock, mismatch = load_greek(greek_paths[0], ticker, date)
        oi, oi_clock = load_oi(oi_paths[0], ticker, date)
        metadata = sources[str(greek_paths[0])]
        require(metadata["clock_source"] == greek_clock, "Selected Greek clock")
        require(metadata["paired_clock_mismatch_rows"] == mismatch, "Selected paired mismatch")
        require(sources[str(oi_paths[0])]["clock_source"] == oi_clock, "Selected OI clock")
        if greek_clock == "UNDERLYING_TIMESTAMP_PROXY":
            fallback_checked += 1
        indexed = greek_quotes.set_index(["strike", "right", "timestamp"])
        for row in rows.itertuples(index=False):
            stamp = pd.Timestamp(row.feature_time)
            chain = greek_all.loc[greek_all.timestamp == stamp]
            side = greek_quotes.loc[(greek_quotes.timestamp == stamp) & (greek_quotes.right == row.right)
                                    & np.isfinite(greek_quotes.delta) & (greek_quotes.delta.abs() <= 1)].copy()
            require(len(side) > 0, "Raw selected side absent")
            side["distance"] = (side.delta.abs() - .5).abs()
            chosen = side.sort_values(["distance", "strike"], kind="stable").iloc[0]
            close(chosen.strike, row.strike, "Raw strike")
            close(chosen.delta, row.selected_delta, "Raw delta")
            entry = indexed.loc[(row.strike, row.right, pd.Timestamp(row.entry_time))]
            close(entry.ask, row.entry_ask, "Raw entry ask")
            exit_key = (row.strike, row.right, pd.Timestamp(row.exit_time))
            if exit_key not in indexed.index:
                require(row.missing_exit and row.exit_bid == 0, "Raw missing exit")
            else:
                require(not row.missing_exit, "Raw exit flag")
                close(indexed.loc[exit_key].bid, row.exit_bid, "Raw exit bid")
            event = feature_index.loc[row.event_id]
            require(event.greek_clock_source == greek_clock and event.oi_clock_source == oi_clock, "Event clocks")
            available = oi.loc[oi.timestamp <= stamp].sort_values("timestamp").drop_duplicates(["strike", "right"], keep="last")
            merged = chain[["strike", "right"]].merge(available[["strike", "right", "open_interest"]],
                                                       on=["strike", "right"], how="left", validate="one_to_one")
            missing = merged.open_interest.isna()
            require(int(event.p_oi_missing_count) == int(missing.sum()), "OI missing count")
            close(event.p_oi_missing_fraction, float(missing.mean()) if len(merged) else 1.0, "OI missing fraction")
            require((available.timestamp <= stamp).all(), "OI cutoff")
            raw_checked += 1
            mask_checked += 1

    test_primary = rebuilt_primary.loc[rebuilt_primary.period == "test"]
    daily = test_primary.groupby(["date", "representation"]).net.sum().unstack(fill_value=0)
    daily = daily.reindex(index=test_days, columns=ARMS, fill_value=0).fillna(0)
    saved_daily = pd.read_csv(root / "test_daily_net.csv", dtype={"date": str}).set_index("date")
    require(saved_daily.index.tolist() == test_days, "Daily calendar")
    require(np.allclose(saved_daily[list(ARMS)], daily, rtol=0, atol=1e-7), "Daily totals")
    rng = np.random.default_rng(SEED)
    starts = rng.integers(0, len(test_days), size=(2000, (len(test_days) + 4) // 5))
    picks = ((starts[:, :, None] + np.arange(5)) % len(test_days)).reshape(2000, -1)[:, :len(test_days)]
    for control in ("price", "placebo"):
        difference = (daily.authentic - daily[control]).to_numpy(float)
        samples = difference[picks].sum(axis=1)
        reported = summary["paired_test_comparisons"]["authentic_minus_" + control]
        close(difference.sum(), reported["observed_net_difference"], "Paired difference")
        require(np.allclose(np.quantile(samples, [.025, .975]),
                            reported["paired_circular_5session_block_bootstrap_95ci_total_usd"],
                            rtol=0, atol=1e-7), "Bootstrap interval")

    rebuilt_primary.to_parquet(output / "independent_primary_ledger.parquet", index=False)
    rebuilt_latency.to_parquet(output / "independent_latency_ledger.parquet", index=False)
    (output / "source_rehash.json").write_text(json.dumps(source_results, indent=2), encoding="utf-8")
    result = {
        "status": "PASS_INDEPENDENT_WIDE_EXPLORATORY_BENCHMARK_AUDIT",
        "source_files_rehashed": len(source_results),
        "source_hash_mismatch": 0,
        "accounting_rows": len(labeled) + len(latency_labels),
        "primary_ledger_rows": len(rebuilt_primary),
        "latency_ledger_rows": len(rebuilt_latency),
        "selected_raw_test_rows_checked": raw_checked,
        "selected_oi_missing_masks_checked": mask_checked,
        "selected_fallback_clock_days_checked": fallback_checked,
        "model_refits": refits,
        "calendar_test_days": len(test_days),
        "bootstrap_comparisons_rebuilt": 2,
        "summary_sha256": digest(root / "summary.json"),
        "audit_script_sha256": digest(Path(__file__)),
        "untouched_outer": False,
        "live_parity_verified": False,
        "original_receipt_times_verified": False,
        "prior_close_receipt_verified": False,
        "full_raw_feature_reconstruction": False,
        "technical_ready": False,
        "promotion_approved": False,
        "audit_finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        audit(args.root, args.output)
    except Exception as exc:
        (args.output / "audit_failure.json").write_text(
            json.dumps({"status": "AUDIT_FAILED", "error": repr(exc)}, indent=2),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
