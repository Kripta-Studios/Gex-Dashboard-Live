"""Fixed expanded exploratory causal zone benchmark; see WIDE_BENCHMARK_SPEC.md."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import time

import exchange_calendars as xc
import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("D:/ThetaData/data_options")
OUT = Path("D:/GexResearchArtifacts/restart_20261018/wide_zone_benchmark")
TICKERS = ("SPXW", "SPY", "QQQ")
RATIOS = np.array(
    [-1, -0.618, -0.272, 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.272, 1.618, 2]
)
SEED = 20261018
GREEK_COLS = [
    "symbol",
    "expiration",
    "trade_date",
    "strike",
    "right",
    "timestamp",
    "underlying_timestamp",
    "underlying_price",
    "delta",
    "bid",
    "ask",
    "implied_vol",
    "vega",
    "theta",
]
OI_COLS = [
    "symbol",
    "expiration",
    "trade_date",
    "strike",
    "right",
    "timestamp",
    "open_interest",
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def placebo_shift(ticker, date):
    digest = hashlib.sha256(f"{SEED}|{ticker}|{date}".encode()).digest()
    magnitude = 0.2 + 0.6 * int.from_bytes(digest[1:9], "big") / (2**64 - 1)
    return magnitude if digest[0] % 2 == 0 else -magnitude


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, allow_nan=False, default=str), encoding="utf-8"
    )


def parse_time(v):
    result = pd.to_datetime(v, format="ISO8601", errors="coerce")
    if result.dt.tz is not None:
        raise ValueError("Expected naive America/New_York source clocks")
    return result


def valid_quote(df):
    return (
        np.isfinite(df.bid)
        & np.isfinite(df.ask)
        & (df.bid >= 0)
        & (df.ask > 0)
        & (df.bid <= df.ask)
    )


def ib_bounds(spot, decision):
    day = pd.Timestamp(decision).normalize()
    if pd.Timestamp(decision) < day + pd.Timedelta(hours=10, minutes=30):
        return None
    s = spot.loc[
        (spot.index >= day + pd.Timedelta(hours=9, minutes=30))
        & (spot.index < day + pd.Timedelta(hours=10, minutes=30))
        & (spot.index < pd.Timestamp(decision))
    ].dropna()
    if len(s) < 57:
        return None
    lo, hi = float(s.min()), float(s.max())
    return (lo, hi) if hi > lo else None


def contract_at(frame, stamp, right):
    f = frame.loc[
        (frame.timestamp == stamp)
        & (frame.right == right)
        & valid_quote(frame)
        & np.isfinite(frame.delta)
        & (frame.delta.abs() <= 1)
    ].copy()
    if f.empty:
        return None
    f["dist"] = (f.delta.abs() - 0.5).abs()
    return f.sort_values(["dist", "strike"], kind="stable").iloc[0]


def payoff(entry, exit_bid, slip=0.01):
    return (max(float(exit_bid) - slip, 0.0) - float(entry) - slip) * 100 - 2 * 1.30


def labels_for(candidates, quotes, counters):
    rows = []
    for c in candidates:
        key = (c["strike"], c["right"], pd.Timestamp(c["entry_time"]))
        ent = quotes.get(key)
        if ent is None:
            counters["missing_entry"] += 1
            rows.append(
                {
                    "event_id": c["event_id"],
                    "right": c["right"],
                    "net": np.nan,
                    "adverse_net": np.nan,
                    "entry_ask": np.nan,
                    "exit_bid": np.nan,
                    "missing_exit": False,
                }
            )
            continue
        ex = quotes.get((c["strike"], c["right"], pd.Timestamp(c["exit_time"])))
        missing = ex is None
        if missing:
            counters["missing_exit_zero_liquidation"] += 1
        bid = 0.0 if missing else ex[0]
        rows.append(
            {
                "event_id": c["event_id"],
                "right": c["right"],
                "net": payoff(ent[1], bid),
                "adverse_net": payoff(ent[1], bid, 0.02),
                "entry_ask": ent[1],
                "exit_bid": bid,
                "missing_exit": missing,
            }
        )
    return rows


def clean_identity(f, ticker, day, name, counts):
    f["right"] = f.right.astype(str).str.upper().replace({"C": "CALL", "P": "PUT"})
    f["strike"] = pd.to_numeric(f.strike, errors="coerce")
    f["timestamp"] = parse_time(f.timestamp)
    f["expiration"] = parse_time(f.expiration.astype(str)).dt.normalize()
    f["trade_date"] = parse_time(f.trade_date.astype(str)).dt.normalize()
    valid = (
        (f.symbol == ticker)
        & (f.expiration == day)
        & (f.trade_date == day)
        & (f.timestamp.dt.normalize() == day)
        & f.right.isin(["CALL", "PUT"])
        & np.isfinite(f.strike)
        & (f.strike > 0)
    )
    if name == "greek":
        valid &= (
            (f.timestamp == f.timestamp.dt.floor("min"))
            & (f.timestamp >= day + pd.Timedelta(hours=9, minutes=30))
            & (f.timestamp <= day + pd.Timedelta(hours=16))
        )
    counts[name + "_invalid_identity"] += int((~valid).sum())
    f.drop(f.index[~valid], inplace=True)
    dup = f.duplicated(["strike", "right", "timestamp"], keep=False)
    counts[name + "_duplicate_keys"] += int(dup.sum())
    f.drop(f.index[dup], inplace=True)


def clean_sources(g, oi, ticker, day, counts):
    day = pd.Timestamp(day)
    for name, f in [("greek", g), ("oi", oi)]:
        clean_identity(f, ticker, day, name, counts)
    g["underlying_timestamp"] = parse_time(g.underlying_timestamp)
    age = (g.timestamp - g.underlying_timestamp).dt.total_seconds()
    good = (
        (g.underlying_price > 0) & np.isfinite(g.underlying_price) & age.between(0, 60)
    )
    counts["invalid_spot_rows"] += int((~good).sum())
    g.loc[~good, "underlying_price"] = np.nan
    grouped = g.groupby("timestamp").underlying_price
    incons = grouped.nunique(dropna=True) > 1
    counts["inconsistent_spot_minutes"] += int(incons.sum())
    spot = grouped.first()
    spot.loc[incons] = np.nan
    oi["open_interest"] = pd.to_numeric(oi.open_interest, errors="coerce")
    bad_oi = (
        (~np.isfinite(oi.open_interest))
        | (oi.open_interest < 0)
        | (oi.open_interest % 1 != 0)
    )
    counts["invalid_oi_rows"] += int(bad_oi.sum())
    oi = oi.loc[~bad_oi].copy()
    counts["invalid_quote_rows"] += int((~valid_quote(g)).sum())
    return g, oi, spot


def oi_snapshot(oi, stamp):
    return (
        oi.loc[oi.timestamp <= stamp]
        .sort_values("timestamp")
        .drop_duplicates(["strike", "right"], keep="last")
    )


def chain_context(g, oi, stamp, spot, counts):
    chain = g.loc[g.timestamp == stamp].copy()
    available = oi_snapshot(oi, stamp)
    chain = chain.merge(
        available[["strike", "right", "open_interest"]],
        on=["strike", "right"],
        how="left",
        validate="one_to_one",
    )
    counts["event_contracts_missing_oi"] += int(chain.open_interest.isna().sum())
    missing_oi = chain.open_interest.isna()
    chain["open_interest"] = chain.open_interest.fillna(0.0)
    iv = pd.to_numeric(chain.implied_vol, errors="coerce")
    valid = (iv > 0) & (iv <= 5) & np.isfinite(iv)
    counts["event_invalid_iv_rows"] += int((~valid).sum())
    expiry = stamp.normalize() + pd.Timedelta(hours=16)
    tau = max((expiry - stamp).total_seconds() / (365 * 86400), 1e-10)
    sigma = iv.where(valid)
    d1 = (np.log(spot / chain.strike) + 0.5 * sigma * sigma * tau) / (
        sigma * np.sqrt(tau)
    )
    chain["gamma_proxy"] = np.exp(-0.5 * d1 * d1) / (
        math.sqrt(2 * math.pi) * spot * sigma * np.sqrt(tau)
    )
    chain["gamma_density_proxy"] = (
        chain.gamma_proxy * chain.open_interest * 100 * spot * spot * 0.01
    )
    context = {
        "oi_missing_count": int(missing_oi.sum()),
        "oi_missing_fraction": float(missing_oi.mean()) if len(chain) else 1.0,
    }
    for side in ("CALL", "PUT"):
        sub = chain.loc[chain.right == side]
        weights = sub.open_interest.to_numpy(float)
        context["oi_total_" + side] = float(weights.sum())
        for field in ("delta", "vega", "theta", "implied_vol"):
            vals = sub[field].to_numpy(float)
            good = np.isfinite(vals)
            if field == "implied_vol":
                good &= (vals > 0) & (vals <= 5)
            den = weights[good].sum()
            context[field + "_oi_mean_" + side] = (
                float(np.dot(weights[good], vals[good]) / den) if den > 0 else np.nan
            )
        context["gamma_density_total_proxy_" + side] = float(
            sub.gamma_density_proxy.sum()
        )
    return chain, context


def soft_fields(levels, weights, spot, prev, width, prefix):
    levels = np.asarray(levels, float)
    weights = np.asarray(weights, float)
    good = np.isfinite(levels) & np.isfinite(weights) & (weights > 0)
    levels, weights = levels[good], weights[good]
    result = {
        prefix + "_nearest": np.nan,
        prefix + "_approach": np.nan,
        prefix + "_rejection": np.nan,
        prefix + "_influence10": 0.0,
        prefix + "_influence25": 0.0,
        prefix + "_below10": 0.0,
        prefix + "_above10": 0.0,
        prefix + "_top_distance": np.nan,
        prefix + "_concentration": 0.0,
    }
    if not len(levels):
        return result
    w = weights / weights.sum()
    distances = (spot - levels) / width
    near = int(np.argmin(abs(distances)))
    old = (prev - levels[near]) / width
    result[prefix + "_nearest"] = float(distances[near])
    result[prefix + "_approach"] = float(abs(old) - abs(distances[near]))
    result[prefix + "_rejection"] = float((spot - prev) / width * np.sign(old))
    result[prefix + "_top_distance"] = float(distances[np.argmax(w)])
    result[prefix + "_concentration"] = float(np.max(w))
    for scale, label in ((0.1, "10"), (0.25, "25")):
        kernel = np.exp(-0.5 * (distances / scale) ** 2)
        result[prefix + "_influence" + label] = float(np.dot(w, kernel))
        if label == "10":
            result[prefix + "_below10"] = float(np.dot(w, kernel * (distances >= 0)))
            result[prefix + "_above10"] = float(np.dot(w, kernel * (distances < 0)))
    return result


def features_for(
    spot, chain, previous_chain, stamp, decision, ticker, bounds, context, shift
):
    lo, hi = bounds
    width = hi - lo
    current = float(spot.loc[stamp])
    past = spot.loc[:stamp]
    result = {
        "ticker": TICKERS.index(ticker),
        "clock": decision.hour * 60 + decision.minute,
        "ib_width_fraction": width / current,
        "realized_vol": float(np.log(past / past.shift(1)).std()),
        **context,
    }
    ib_start = stamp.normalize() + pd.Timedelta(hours=9, minutes=30)
    result["ib_observed_minutes"] = int(
        spot.loc[
            (spot.index >= ib_start) & (spot.index < ib_start + pd.Timedelta(hours=1))
        ]
        .notna()
        .sum()
    )
    for interval, n in ((5, 12), (15, 8)):
        for k in range(n):
            a = past.get(stamp - pd.Timedelta(minutes=k * interval), np.nan)
            b = past.get(stamp - pd.Timedelta(minutes=(k + 1) * interval), np.nan)
            result[f"ret{interval}_{k}"] = (
                float(np.log(a / b)) if a > 0 and b > 0 else np.nan
            )
        window = past.loc[stamp - pd.Timedelta(minutes=interval - 1) : stamp].dropna()
        result[f"candle{interval}_observed_fraction"] = len(window) / interval
        for label, val in [
            ("range", window.max() - window.min()),
            ("body", window.iloc[-1] - window.iloc[0]),
            ("upper", window.max() - max(window.iloc[0], window.iloc[-1])),
            ("lower", min(window.iloc[0], window.iloc[-1]) - window.min()),
        ]:
            result[f"candle{interval}_{label}"] = float(val / width)
    prev = past.get(stamp - pd.Timedelta(minutes=5), np.nan)
    z = {"ib_position": (current - lo - shift * width) / width}
    z.update(
        soft_fields(
            lo + RATIOS * width + shift * width,
            np.ones(len(RATIOS)),
            current,
            prev,
            width,
            "fib",
        )
    )
    for side in ("CALL", "PUT"):
        sub = chain.loc[chain.right == side]
        for field, prefix in [
            ("open_interest", "oi"),
            ("gamma_density_proxy", "gamma_proxy"),
        ]:
            name = prefix + "_" + side
            z.update(
                soft_fields(
                    sub.strike.to_numpy() + shift * width,
                    sub[field],
                    current,
                    prev,
                    width,
                    name,
                )
            )
            z[name + "_migration"] = np.nan
            if previous_chain is not None:
                old = previous_chain.loc[previous_chain.right == side]
                now = sub.loc[np.isfinite(sub[field]) & (sub[field] > 0)]
                old = old.loc[np.isfinite(old[field]) & (old[field] > 0)]
                if len(now) and len(old):
                    z[name + "_migration"] = float(
                        (
                            now.loc[now[field].idxmax(), "strike"]
                            - old.loc[old[field].idxmax(), "strike"]
                        )
                        / width
                    )
    return result, z


def session_calendar():
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-01":"2026-06-30"].copy()
    schedule["date"] = schedule.index.strftime("%Y%m%d")
    schedule["full_session"] = (schedule["close"] - schedule["open"]) == pd.Timedelta(
        hours=6, minutes=30
    )
    return schedule


def source_path(ticker, date, kind):
    return (
        ROOT
        / ticker
        / kind
        / date[:4]
        / date[4:6]
        / f"{ticker}_{date}_{date}_{kind}.parquet"
    )


def apply_clock(frame, kind):
    if "timestamp" in frame.columns:
        return "NATIVE_TIMESTAMP"
    if kind == "greek":
        if "underlying_timestamp" not in frame.columns:
            raise ValueError("Missing both Greek clocks")
        frame["timestamp"] = frame["underlying_timestamp"]
        return "UNDERLYING_TIMESTAMP_PROXY"
    frame["timestamp"] = parse_time(
        frame.trade_date.astype(str)
    ).dt.normalize() + pd.Timedelta(hours=9, minutes=30)
    return "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT"


def read_day(path, ticker, counts, hashes):
    parts = path.stem.split("_")
    if len(parts) < 4 or parts[1] != parts[2]:
        return None
    date = parts[1]
    oi = source_path(ticker, date, "oi")
    if not oi.exists():
        counts["missing_oi_file"] += 1
        return None
    for p in (path, oi):
        if str(p) not in hashes:
            hashes[str(p)] = {"sha256": sha(p), "bytes": p.stat().st_size}
    schemas = {str(p): set(pq.read_schema(p).names) for p in (path, oi)}
    for p, columns in [(path, GREEK_COLS), (oi, OI_COLS)]:
        missing = set(columns) - schemas[str(p)] - {"timestamp"}
        if missing:
            hashes[str(p)]["schema_missing_columns"] = sorted(missing)
            counts["schema_excluded_days"] += 1
            return None
    g = pq.read_table(
        path, columns=[c for c in GREEK_COLS if c in schemas[str(path)]]
    ).to_pandas()
    o = pq.read_table(
        oi, columns=[c for c in OI_COLS if c in schemas[str(oi)]]
    ).to_pandas()
    paired_mismatch = (
        int((parse_time(g.timestamp) != parse_time(g.underlying_timestamp)).sum())
        if "timestamp" in g
        else None
    )
    greek_clock = apply_clock(g, "greek")
    oi_clock = apply_clock(o, "oi")
    hashes[str(path)].update(
        clock_source=greek_clock,
        paired_clock_mismatch_rows=paired_mismatch,
        rows=len(g),
    )
    hashes[str(oi)].update(clock_source=oi_clock, rows=len(o))
    counts["greek_clock_" + greek_clock] += 1
    counts["oi_clock_" + oi_clock] += 1
    result = clean_sources(g, o, ticker, pd.Timestamp(date), counts)
    result[0].attrs["clock_source"] = greek_clock
    result[1].attrs["clock_source"] = oi_clock
    return (*result, date)


def quote_dict(g, candidates=None):
    if candidates is not None:
        stamps = {
            pd.Timestamp(c[field])
            for c in candidates
            for field in ("entry_time", "exit_time")
        }
        g = g.loc[g.timestamp.isin(stamps)]
    q = g.loc[valid_quote(g)]
    return {
        (r.strike, r.right, r.timestamp): (r.bid, r.ask)
        for r in q[["strike", "right", "timestamp", "bid", "ask"]].itertuples(
            index=False
        )
    }


def process_day(task):
    pa.set_cpu_count(1)
    ticker, path, coverage_record = task
    events = []
    candidates = []
    labels = []
    hashes = {}
    counts = Counter()
    iv_examples = []
    item = read_day(path, ticker, counts, hashes)
    if item is None:
        coverage_record["status"] = "SCHEMA_EXCLUDED"
        return events, candidates, labels, hashes, counts, iv_examples, coverage_record
    g, oi, spot, date = item
    day = pd.Timestamp(date)
    day_candidates = []
    previous = None
    shift = placebo_shift(ticker, date)
    vals = g.implied_vol[
        np.isfinite(g.implied_vol) & (g.implied_vol > 0) & (g.implied_vol <= 5)
    ]
    if len(vals):
        iv_examples.append(
            {
                "ticker": ticker,
                "date": date,
                "q10": float(vals.quantile(0.1)),
                "median": float(vals.median()),
                "q90": float(vals.quantile(0.9)),
            }
        )
    counts["days_read_" + ticker] += 1
    coverage_record.update(
        status="READ",
        greek_clock=g.attrs["clock_source"],
        oi_clock=oi.attrs["clock_source"],
    )
    for minute in range(10 * 60 + 35, 15 * 60 + 6, 30):
        decision = day + pd.Timedelta(minutes=minute)
        stamp = decision - pd.Timedelta(minutes=1)
        counts["decision_candidates_" + ticker] += 1
        bounds = ib_bounds(spot, decision)
        if bounds is None:
            counts["invalid_ib_" + ticker] += 1
            continue
        if stamp not in spot.index or not np.isfinite(spot.loc[stamp]):
            counts["missing_feature_spot_" + ticker] += 1
            continue
        chain, context = chain_context(g, oi, stamp, float(spot.loc[stamp]), counts)
        if chain.empty:
            counts["missing_feature_chain_" + ticker] += 1
            continue
        base, auth = features_for(
            spot, chain, previous, stamp, decision, ticker, bounds, context, 0.0
        )
        _, placebo = features_for(
            spot, chain, previous, stamp, decision, ticker, bounds, context, shift
        )
        previous = chain
        event_id = f"{ticker}_{date}_{minute}"
        coverage_record["events"] += 1
        events.append(
            {
                "event_id": event_id,
                "date": date,
                "ticker_name": ticker,
                "decision": str(decision),
                "greek_clock_source": g.attrs["clock_source"],
                "oi_clock_source": oi.attrs["clock_source"],
                **{"p_" + k: v for k, v in base.items()},
                **{"a_" + k: v for k, v in auth.items()},
                **{"z_" + k: v for k, v in placebo.items()},
            }
        )
        for side in ("CALL", "PUT"):
            selected = contract_at(chain, stamp, side)
            if selected is None:
                counts["missing_feature_contract_" + ticker + "_" + side] += 1
                continue
            c = {
                "event_id": event_id,
                "date": date,
                "ticker_name": ticker,
                "right": side,
                "strike": float(selected.strike),
                "decision": str(decision),
                "feature_time": str(stamp),
                "entry_time": str(decision + pd.Timedelta(minutes=1)),
                "exit_time": str(decision + pd.Timedelta(minutes=31)),
                "selected_delta": float(selected.delta),
                "placebo_shift_ib_units_diagnostic_only": shift,
            }
            candidates.append(c)
            day_candidates.append(c)
    # Explicit stage boundary: no test payoff construction during feature build.
    if date < "20260101":
        labels.extend(labels_for(day_candidates, quote_dict(g, day_candidates), counts))
    return events, candidates, labels, hashes, counts, iv_examples, coverage_record


def build(out):
    events = []
    candidates = []
    labels = []
    hashes = {}
    counts = Counter()
    iv_examples = []
    calendar = session_calendar()
    calendar.to_csv(out / "expected_calendar.csv", index=False)
    days = calendar.loc[calendar.full_session, "date"].tolist()
    coverage = []
    files = []
    for ticker in TICKERS:
        for date in days:
            greek = source_path(ticker, date, "greeks")
            oi = source_path(ticker, date, "oi")
            record = {
                "ticker": ticker,
                "date": date,
                "greek_exists": greek.exists(),
                "oi_exists": oi.exists(),
                "events": 0,
            }
            coverage.append(record)
            if not greek.exists():
                counts["missing_greek_file_" + ticker] += 1
            if not oi.exists():
                counts["missing_oi_file_" + ticker] += 1
            if greek.exists() and oi.exists():
                files.append((ticker, greek, record))
    counts["expected_full_sessions_per_ticker"] = len(days)
    counts["excluded_early_close_dates"] = int((~calendar.full_session).sum())
    coverage_by_key = {(r["ticker"], r["date"]): r for r in coverage}
    with ProcessPoolExecutor(max_workers=6) as pool:
        for idx, result in enumerate(pool.map(process_day, files, chunksize=1)):
            ev, ca, la, ha, co, iv, record = result
            events.extend(ev)
            candidates.extend(ca)
            labels.extend(la)
            hashes.update(ha)
            counts.update(co)
            iv_examples.extend(iv)
            coverage_by_key[(record["ticker"], record["date"])].update(record)
            if idx % 25 == 0 or idx == len(files) - 1:
                progress = {
                    "stage": "features",
                    "file": idx + 1,
                    "total": len(files),
                    "ticker": record["ticker"],
                    "date": record["date"],
                    "events": len(events),
                }
                print(json.dumps(progress), flush=True)
                write_json(out / "progress.json", progress)
    pd.DataFrame(events).to_parquet(out / "features.parquet", index=False)
    pd.DataFrame(candidates).to_parquet(out / "candidates.parquet", index=False)
    pd.DataFrame(labels).to_parquet(
        out / "train_validation_labels.parquet", index=False
    )
    write_json(out / "sources.json", hashes)
    write_json(out / "coverage.json", dict(counts))
    write_json(out / "iv_unit_plausibility.json", iv_examples)
    pd.DataFrame(coverage).to_csv(out / "session_coverage.csv", index=False)
    return counts, hashes


def schedule(frame, threshold):
    if threshold is None:
        return frame.iloc[:0].copy()
    rows = []
    until = {}
    for _, group in frame.sort_values(["decision", "ticker_name", "right"]).groupby(
        ["decision", "ticker_name"], sort=True
    ):
        row = group.sort_values(
            ["prediction", "right"], ascending=[False, True], kind="stable"
        ).iloc[0]
        decision = pd.Timestamp(row.decision)
        ticker = row.ticker_name
        if (
            decision < until.get(ticker, pd.Timestamp.min)
            or row.prediction <= threshold
        ):
            continue
        if not np.isfinite(row.net):
            continue
        rows.append(row.to_dict())
        until[ticker] = pd.Timestamp(row.exit_time)
    return pd.DataFrame(rows, columns=frame.columns)


def fit_freeze(out):
    f = pd.read_parquet(out / "features.parquet")
    c = pd.read_parquet(out / "candidates.parquet")
    y = pd.read_parquet(out / "train_validation_labels.parquet")
    joined = c.merge(
        f, on=["event_id", "date", "ticker_name", "decision"], validate="many_to_one"
    ).merge(y, on=["event_id", "right"], how="left", validate="one_to_one")
    train = joined.date < "20250101"
    validation = (joined.date >= "20250101") & (joined.date < "20260101")
    config = dict(
        n_estimators=150,
        num_leaves=15,
        max_depth=5,
        min_child_samples=80,
        learning_rate=0.04,
        reg_lambda=10,
        n_jobs=2,
        random_state=SEED,
        verbosity=-1,
        deterministic=True,
        force_col_wise=True,
    )
    frozen = {}
    predictions = []
    common = [v for v in f.columns if v.startswith("p_")]
    for name, prefix in [("price", None), ("authentic", "a_"), ("placebo", "z_")]:
        columns = common + (
            [v for v in f.columns if v.startswith(prefix)] if prefix else []
        )
        output = joined[
            c.columns.tolist()
            + ["net", "adverse_net", "entry_ask", "exit_bid", "missing_exit"]
        ].copy()
        output["prediction"] = np.nan
        for side in ("CALL", "PUT"):
            mask = train & (joined.right == side) & joined.net.notna()
            if mask.sum() < 80:
                raise RuntimeError(f"Insufficient train {name} {side}: {mask.sum()}")
            model = lgb.LGBMRegressor(**config)
            model.fit(
                joined.loc[mask, columns].to_numpy(float), joined.loc[mask, "net"]
            )
            model.booster_.save_model(str(out / f"model_{name}_{side}.txt"))
            side_mask = joined.right == side
            output.loc[side_mask, "prediction"] = model.predict(
                joined.loc[side_mask, columns].to_numpy(float)
            )
        choices = []
        for threshold in (0, 5, 10):
            ledger = schedule(output.loc[validation], threshold)
            counts = ledger.groupby("ticker_name").size().to_dict()
            choices.append(
                {
                    "threshold": threshold,
                    "net": float(ledger.net.sum()),
                    "counts": counts,
                    "qualifies": all(counts.get(t, 0) >= 10 for t in TICKERS),
                }
            )
        qualified = [v for v in choices if v["qualifies"]]
        winner = (
            sorted(qualified, key=lambda v: (-v["net"], v["threshold"]))[0]
            if qualified
            else {"threshold": None}
        )
        frozen[name] = {
            "threshold": winner["threshold"],
            "validation_count_gate": bool(qualified),
            "validation_choices": choices,
            "features": columns,
        }
        output["representation"] = name
        # Prediction artifact excludes every payoff field, including missingness.
        predictions.append(
            output.drop(
                columns=["net", "adverse_net", "entry_ask", "exit_bid", "missing_exit"]
            )
        )
    predictions = pd.concat(predictions, ignore_index=True)
    predictions.to_parquet(out / "frozen_predictions.parquet", index=False)
    write_json(
        out / "freeze.json",
        {
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": config,
            "representations": frozen,
            "test_payoffs_constructed": False,
            "prediction_sha256": sha(out / "frozen_predictions.parquet"),
            "models": {p.name: sha(p) for p in out.glob("model_*.txt")},
            "features_sha256": sha(out / "features.parquet"),
            "candidates_sha256": sha(out / "candidates.parquet"),
            "sources_sha256": sha(out / "sources.json"),
            "script_sha256": sha(__file__),
            "spec_sha256": sha(Path(__file__).with_name("WIDE_BENCHMARK_SPEC.md")),
            "train_validation_labels_sha256": sha(
                out / "train_validation_labels.parquet"
            ),
        },
    )
    return frozen


def verify_freeze(out):
    frozen = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
    for filename, key in [
        ("frozen_predictions.parquet", "prediction_sha256"),
        ("features.parquet", "features_sha256"),
        ("candidates.parquet", "candidates_sha256"),
        ("sources.json", "sources_sha256"),
        ("train_validation_labels.parquet", "train_validation_labels_sha256"),
    ]:
        if sha(out / filename) != frozen[key]:
            raise RuntimeError("Frozen artifact changed: " + filename)
    for name, digest in frozen["models"].items():
        if sha(out / name) != digest:
            raise RuntimeError("Frozen model changed: " + name)
    if (
        sha(__file__) != frozen["script_sha256"]
        or sha(Path(__file__).with_name("WIDE_BENCHMARK_SPEC.md"))
        != frozen["spec_sha256"]
    ):
        raise RuntimeError("Frozen code/spec changed")
    return frozen


def test_labels(out, counts, hashes):
    verify_freeze(out)
    c = pd.read_parquet(out / "candidates.parquet")
    c = c.loc[c.date >= "20260101"]
    rows = []
    sensitivity = []
    for idx, ((ticker, date), subset) in enumerate(c.groupby(["ticker_name", "date"])):
        p = source_path(ticker, date, "greeks")
        if sha(p) != hashes[str(p)]["sha256"]:
            raise RuntimeError("Source changed before test opening: " + str(p))
        columns = [
            "symbol",
            "expiration",
            "trade_date",
            "strike",
            "right",
            "bid",
            "ask",
        ]
        schema = set(pq.read_schema(p).names)
        columns += ["timestamp"] if "timestamp" in schema else ["underlying_timestamp"]
        g = pq.read_table(p, columns=columns).to_pandas()
        apply_clock(g, "greek")
        clean_identity(g, ticker, pd.Timestamp(date), "greek", Counter())
        candidates = subset.to_dict("records")
        rows.extend(labels_for(candidates, quote_dict(g, candidates), counts))
        for delay in (2, 5):
            delayed = delayed_candidates(subset, delay).to_dict("records")
            delay_counts = Counter()
            sensitivity.extend(
                [
                    {**r, "entry_delay_minutes": delay}
                    for r in labels_for(delayed, quote_dict(g, delayed), delay_counts)
                ]
            )
            counts.update({f"delay{delay}_" + k: v for k, v in delay_counts.items()})
        if idx % 25 == 0:
            print(
                json.dumps(
                    {
                        "stage": "test_payoffs",
                        "day": idx,
                        "ticker": ticker,
                        "date": date,
                    }
                ),
                flush=True,
            )
    pd.DataFrame(rows).to_parquet(out / "test_labels.parquet", index=False)
    pd.DataFrame(sensitivity).to_parquet(
        out / "test_latency_labels.parquet", index=False
    )
    write_json(out / "coverage.json", dict(counts))


def delayed_candidates(frame, delay):
    if delay not in (1, 2, 5):
        raise ValueError("Undeclared delay")
    result = frame.copy()
    result["entry_time"] = (
        pd.to_datetime(result.decision) + pd.Timedelta(minutes=delay)
    ).astype(str)
    result["exit_time"] = (
        pd.to_datetime(result.entry_time) + pd.Timedelta(minutes=30)
    ).astype(str)
    if (
        pd.to_datetime(result.exit_time).dt.hour * 60
        + pd.to_datetime(result.exit_time).dt.minute
        > 15 * 60 + 40
    ).any():
        raise ValueError("Exit later than fixed deadline")
    return result


def metrics(frame):
    result = {"trades": len(frame)}
    for field, prefix in [("net", "base"), ("adverse_net", "adverse")]:
        vals = frame[field] if len(frame) else pd.Series(dtype=float)
        gains = float(vals[vals > 0].sum())
        loss = float(-vals[vals < 0].sum())
        result[prefix + "_net_usd"] = float(vals.sum())
        result[prefix + "_win_rate"] = float((vals > 0).mean()) if len(vals) else None
        result[prefix + "_profit_factor"] = gains / loss if loss > 0 else None
    return result


def report(out, frozen, counts):
    pred = pd.read_parquet(out / "frozen_predictions.parquet")
    labels = pd.concat(
        [
            pd.read_parquet(out / "train_validation_labels.parquet"),
            pd.read_parquet(out / "test_labels.parquet"),
        ]
    )
    joined = pred.merge(labels, on=["event_id", "right"], validate="many_to_one")
    results = {}
    ledgers = []
    for name, settings in frozen.items():
        result = {}
        for period, lo, hi in [
            ("validation", "20250101", "20260101"),
            ("test", "20260101", "20260701"),
        ]:
            subset = joined.loc[
                (joined.representation == name)
                & (joined.date >= lo)
                & (joined.date < hi)
            ]
            ledger = schedule(subset, settings["threshold"])
            ledger["period"] = period
            ledgers.append(ledger)
            result[period] = {
                "pooled": metrics(ledger),
                "tickers": {
                    t: metrics(ledger.loc[ledger.ticker_name == t]) for t in TICKERS
                },
                "months": {},
            }
            for t in TICKERS:
                result[period]["months"][t] = {}
                for month in pd.period_range(
                    pd.Timestamp(lo), pd.Timestamp(hi) - pd.Timedelta(days=1), freq="M"
                ).strftime("%Y%m"):
                    result[period]["months"][t][month] = metrics(
                        ledger.loc[
                            (ledger.ticker_name == t)
                            & ledger.date.str.startswith(month)
                        ]
                    )
        results[name] = result
    all_ledgers = pd.concat(ledgers, ignore_index=True)
    all_ledgers.to_parquet(out / "ledger.parquet", index=False)
    test = all_ledgers.loc[all_ledgers.period == "test"]
    calendar = session_calendar()
    days = calendar.loc[
        calendar.full_session & (calendar.date >= "20260101"), "date"
    ].tolist()
    daily = (
        test.groupby(["date", "representation"])
        .net.sum()
        .unstack(fill_value=0)
        .reindex(index=days, columns=list(frozen), fill_value=0)
        .fillna(0)
    )
    daily.to_csv(out / "test_daily_net.csv")
    rng = np.random.default_rng(SEED)
    ci = {}
    starts = rng.integers(0, len(days), size=(2000, math.ceil(len(days) / 5)))
    indices = ((starts[:, :, None] + np.arange(5)) % len(days)).reshape(2000, -1)[
        :, : len(days)
    ]
    for control in ("price", "placebo"):
        delta = (daily.authentic - daily[control]).to_numpy(float)
        samples = delta[indices].sum(axis=1)
        ci["authentic_minus_" + control] = {
            "observed_net_difference": float(delta.sum()),
            "paired_circular_5session_block_bootstrap_95ci_total_usd": [
                float(v) for v in np.quantile(samples, [0.025, 0.975])
            ],
            "days": len(delta),
            "block_sessions": 5,
            "resamples": 2000,
        }
    sensitivity = {}
    sensitivity_ledgers = []
    sensitivity_labels = pd.read_parquet(out / "test_latency_labels.parquet")
    for delay in (2, 5):
        delayed = delayed_candidates(pred.loc[pred.date >= "20260101"], delay)
        delayed = delayed.merge(
            sensitivity_labels.loc[sensitivity_labels.entry_delay_minutes == delay],
            on=["event_id", "right"],
            validate="many_to_one",
        )
        sensitivity[str(delay)] = {}
        for name, settings in frozen.items():
            ledger = schedule(
                delayed.loc[delayed.representation == name], settings["threshold"]
            )
            sensitivity_ledgers.append(ledger)
            sensitivity[str(delay)][name] = {
                "pooled": metrics(ledger),
                "tickers": {
                    t: metrics(ledger.loc[ledger.ticker_name == t]) for t in TICKERS
                },
                "months": {
                    t: {
                        month: metrics(
                            ledger.loc[
                                (ledger.ticker_name == t)
                                & ledger.date.str.startswith(month)
                            ]
                        )
                        for month in [
                            "202601",
                            "202602",
                            "202603",
                            "202604",
                            "202605",
                            "202606",
                        ]
                    }
                    for t in TICKERS
                },
            }
    pd.concat(sensitivity_ledgers, ignore_index=True).to_parquet(
        out / "latency_ledger.parquet", index=False
    )
    summary = {
        "status": "COMPLETED_EXPLORATORY_DEVELOPMENT",
        "untouched_outer": False,
        "live_parity_verified": False,
        "dealer_exposure_verified": False,
        "prior_close_semantics_verified": False,
        "technical_ready": False,
        "promotion_approved": False,
        "results": results,
        "entry_delay_sensitivity_minutes": sensitivity,
        "paired_test_comparisons": ci,
        "coverage": dict(counts),
        "thresholds": frozen,
        "source_clock_policy": "NATIVE_OR_STORED_UNDERLYING_PROXY",
        "missing_oi_clock_policy": "ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT",
    }
    write_json(out / "summary.json", summary)
    lines = [
        "# Zone benchmark result â€” exploratory development",
        "",
        "Completed one fixed 2023–2024 train / 2025 validation / 2026 H1 test experiment. This is previously seen development history, not untouched outer or live evidence.",
        "",
        "| Representation | Test trades | Base net USD | Adverse net USD | Base PF | Win rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in frozen:
        m = results[name]["test"]["pooled"]
        wr = m["base_win_rate"]
        pf = m["base_profit_factor"]
        lines.append(
            f"| {name} | {m['trades']} | {m['base_net_usd']:.2f} | {m['adverse_net_usd']:.2f} | {pf if pf is None else round(pf, 3)} | {wr if wr is None else round(wr * 100, 2)}% |"
        )
    lines += [
        "",
        "Per-ticker test results:",
        "",
        "| Representation | Ticker | Trades | Base net USD | Adverse net USD | Base PF |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name in frozen:
        for ticker, m in results[name]["test"]["tickers"].items():
            lines.append(
                f"| {name} | {ticker} | {m['trades']} | {m['base_net_usd']:.2f} | {m['adverse_net_usd']:.2f} | {m['base_profit_factor']} |"
            )
    lines += [
        "",
        "Frozen-policy entry delay sensitivity (no refitting or threshold selection):",
        "",
        "| Delay minutes | Representation | Trades | Base net USD | Adverse net USD | Base PF |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for delay, representations in sensitivity.items():
        for name, value in representations.items():
            m = value["pooled"]
            lines.append(
                f"| {delay} | {name} | {m['trades']} | {m['base_net_usd']:.2f} | {m['adverse_net_usd']:.2f} | {m['base_profit_factor']} |"
            )
    lines += [
        "",
        "Paired circular five-session block bootstrap comparisons (2000 resamples):",
        "",
        json.dumps(ci, indent=2),
        "",
        "Full month/ticker coverage, validation selection, source hashes, models and ledgers are preserved under "
        + str(out)
        + ".",
        "",
        "Limitations: sampled spot extrema are not OHLC; the stored underlying_timestamp is an explicitly assumed quote clock when native timestamp is absent, not observed arrival time; OI without timestamp assumes prior-close availability at 09:30, unverified for this vintage; per-file and per-event clock flags and missing OI masks are retained. Entry-delay sensitivities do not certify feature arrival. BS gamma is a formula proxy with r=q=0, not measured dealer inventory; missing entries are excluded after fixed contract selection, missing exits liquidate at zero; no independent economic auditor or prospective shadow is completed. No profitability or promotion claim follows from this trial.",
    ]
    (Path(__file__).parent / "WIDE_BENCHMARK_RESULT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out / "wide_zone_benchmark.py")
    shutil.copy2(
        Path(__file__).with_name("WIDE_BENCHMARK_SPEC.md"),
        out / "WIDE_BENCHMARK_SPEC.md",
    )
    write_json(
        out / "run_identity.json",
        {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "script_sha256": sha(__file__),
            "spec_sha256": sha(Path(__file__).with_name("WIDE_BENCHMARK_SPEC.md")),
            "test_outcome_access": "deferred_until_freeze",
            "versions": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "lightgbm": lgb.__version__,
                "exchange_calendars": xc.__version__,
            },
        },
    )
    start = time.monotonic()
    counts, hashes = build(out)
    frozen = fit_freeze(out)
    print("FROZEN_BEFORE_TEST_PAYOFFS", flush=True)
    test_labels(out, counts, hashes)
    rehash = {p: sha(p) == v["sha256"] for p, v in hashes.items()}
    write_json(out / "source_rehash.json", rehash)
    if not all(rehash.values()):
        raise RuntimeError("Source integrity failure at completion")
    report(out, frozen, counts)
    write_json(
        out / "completion.json",
        {
            "seconds": time.monotonic() - start,
            "source_count": len(hashes),
            "summary_sha256": sha(out / "summary.json"),
        },
    )
    print("COMPLETED_EXPLORATORY_DEVELOPMENT", flush=True)


if __name__ == "__main__":
    main()
