"""Sequential local early-close source diagnostics; no outcomes or cache writes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import build_cache as cache
import level_engine as engine
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
DATES = (
    "20230703",
    "20231124",
    "20240703",
    "20241129",
    "20241224",
    "20250703",
    "20251128",
    "20251224",
)
TICKERS = ("QQQ", "SPXW", "SPY")
WINDOWS = {
    "ib_0930_1029": (0, 60),
    "decision_1030_1245": (60, 196),
    "before_close_0930_1259": (0, 210),
    "close_1300": (210, 211),
    "strict_after_close_1301_1600": (211, 391),
    "tail_including_close_1300_1600": (210, 391),
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def diagnostic(greek, oi, ticker, date):
    """Reuse frozen normalization in memory, then count source fields/missingness."""
    day = pd.Timestamp(date).normalize()
    clock = pd.date_range(
        day + pd.Timedelta(hours=9, minutes=30), periods=391, freq="min"
    )
    frame, bad_identity = cache.identity(greek, ticker, day)
    native = "timestamp" in frame.columns
    quote_time = cache.parse_time(
        frame.timestamp if native else frame.underlying_timestamp
    )
    underlying_time = cache.parse_time(frame.underlying_timestamp)
    valid_time = (
        (quote_time.dt.normalize() == day)
        & (quote_time == quote_time.dt.floor("min"))
        & quote_time.between(clock[0], clock[-1])
    )
    retained = frame.loc[valid_time].copy()
    minute = (
        (
            quote_time.loc[valid_time].astype("int64").to_numpy()
            - clock.as_unit("ns").asi8[0]
        )
        // 60_000_000_000
    ).astype(int)
    spot = pd.to_numeric(retained.underlying_price, errors="coerce").to_numpy(float)
    bid = pd.to_numeric(retained.bid, errors="coerce").to_numpy(float)
    ask = pd.to_numeric(retained.ask, errors="coerce").to_numpy(float)
    age = (
        quote_time.loc[valid_time] - underlying_time.loc[valid_time]
    ).dt.total_seconds().to_numpy(float) * 1000
    quote = np.isfinite(bid) & np.isfinite(ask) & (bid >= 0) & (ask > 0) & (bid <= ask)
    good_spot = (
        np.isfinite(spot) & (spot > 0) & np.isfinite(age) & (age >= 0) & (age <= 60000)
    )
    def count(mask):
        return np.bincount(
            minute[np.asarray(mask, dtype=bool)], minlength=391
        ).astype(np.int64)
    per = pd.DataFrame(
        dict(
            ticker=ticker,
            date=date,
            minute_i=np.arange(391),
            time_et=clock.strftime("%H:%M"),
            present_rows=np.bincount(minute, minlength=391),
            valid_quote_rows=count(quote),
            bid_ask_both_zero_rows=count((bid == 0) & (ask == 0)),
            positive_raw_spot_rows=count(np.isfinite(spot) & (spot > 0)),
            zero_raw_spot_rows=count(spot == 0),
            nonfinite_raw_spot_rows=count(~np.isfinite(spot)),
            valid_spot_age_rows=count(good_spot),
            zero_age_rows=count(age == 0),
            age_over_60s_rows=count(np.isfinite(age) & (age > 60000)),
            negative_age_rows=count(age < 0),
            nonfinite_age_rows=count(~np.isfinite(age)),
        )
    )
    for name in ("delta", "implied_vol", "vega", "theta"):
        values = pd.to_numeric(retained[name], errors="coerce").to_numpy(float)
        per[name + "_finite_rows"] = count(np.isfinite(values))
    iv = pd.to_numeric(retained.implied_vol, errors="coerce").to_numpy(float)
    delta = pd.to_numeric(retained.delta, errors="coerce").to_numpy(float)
    per["valid_quote_finite_delta_positive_iv_rows"] = count(
        quote & np.isfinite(delta) & np.isfinite(iv) & (iv > 0)
    )
    retained["_minute"] = minute
    summary = dict(
        ticker=ticker,
        date=date,
        source_greek_rows=len(greek),
        source_oi_rows=len(oi),
        invalid_greek_identity_rows=int(bad_identity),
        invalid_greek_clock_rows=int((~valid_time).sum()),
        duplicate_greek_identity_clock_rows=int(
            retained.duplicated(["strike", "_right", "_minute"], keep=False).sum()
        ),
        clock_basis="NATIVE_STORED_TIMESTAMP"
        if native
        else "ASSUMED_UNDERLYING_SNAPSHOT_CLOCK",
        clock_pairing_observed=native,
        normalization_status="NOT_RUN",
    )
    try:
        arrays, metadata = cache.normalize_day(greek, oi, ticker, date)
    except (ValueError, TypeError, OverflowError) as error:
        summary.update(
            normalization_status="FAILED",
            normalization_error=str(error),
            future_short_session_candidate=False,
        )
        return per, summary
    summary.update(normalization_status="PASS", normalizer_metadata=metadata)
    flags = arrays["row_flags"]
    present = (flags & 1) > 0
    good_quote = (flags & 2) > 0
    if not np.array_equal(
        per.valid_quote_rows, good_quote.sum(axis=1)
    ) or not np.array_equal(per.valid_spot_age_rows, ((flags & 4) > 0).sum(axis=1)):
        raise AssertionError("Diagnostic validity differs from frozen normalizer")
    keys = {
        (float(strike), int(right)): i
        for i, (strike, right) in enumerate(zip(arrays["strike"], arrays["right"]))
    }
    contracts = np.array(
        [
            keys[(float(strike), int(right))]
            for strike, right in zip(retained.strike, retained._right)
        ],
        dtype=int,
    )
    rawspot = np.full_like(arrays["bid"], np.nan)
    rawspot[minute, contracts] = spot
    positive = np.isfinite(rawspot) & (rawspot > 0) & present
    repeats = np.zeros_like(present)
    repeats[1:] = positive[1:] & positive[:-1] & (rawspot[1:] == rawspot[:-1])
    quote_repeats = np.zeros_like(present)
    quote_repeats[1:] = (
        good_quote[1:]
        & good_quote[:-1]
        & (arrays["bid"][1:] == arrays["bid"][:-1])
        & (arrays["ask"][1:] == arrays["ask"][:-1])
    )
    per["positive_spot_equal_previous_minute_same_contract"] = repeats.sum(axis=1)
    per["valid_quote_equal_previous_minute_same_contract"] = quote_repeats.sum(axis=1)
    per["positive_spot_equal_1300_same_contract"] = (
        positive & positive[210] & (rawspot == rawspot[210])
    ).sum(axis=1)
    per["valid_quote_equal_1300_same_contract"] = (
        good_quote
        & good_quote[210]
        & (arrays["bid"] == arrays["bid"][210])
        & (arrays["ask"] == arrays["ask"][210])
    ).sum(axis=1)
    per["spot_valid"] = arrays["spot_valid"]
    per["spot_consensus"] = arrays["spot"]
    known = engine.known_contract_matrix(arrays)
    availability = engine.available_oi_matrix(arrays)
    per["known_contracts"] = known.sum(axis=1)
    per["known_oi_valid_contracts"] = (known & np.isfinite(availability)).sum(axis=1)
    per["known_oi_positive_contracts"] = (
        known & np.isfinite(availability) & (availability > 0)
    ).sum(axis=1)
    per["known_oi_zero_contracts"] = (known & (availability == 0)).sum(axis=1)
    per["known_oi_missing_contracts"] = (known & ~np.isfinite(availability)).sum(axis=1)
    at = arrays["oi_available_ns"]
    values = arrays["oi_value"]
    valid = arrays["oi_valid"]
    t = arrays["time_ns"]
    masks = dict(
        before_open=at < t[0],
        at_open=at == t[0],
        during_ib=(at >= t[0]) & (at < t[60]),
        by_ib_end=at < t[60],
        by_1300=at <= t[210],
        after_1300=at > t[210],
    )
    summary["oi_availability"] = {
        name: dict(
            valid_records=int((valid & mask).sum()),
            positive_valid_records=int((valid & mask & (values > 0)).sum()),
            zero_valid_records=int((valid & mask & (values == 0)).sum()),
        )
        for name, mask in masks.items()
    }
    summary["oi_clock_basis"] = metadata["oi_clock_basis"]
    summary["oi_invalid_records"] = int((~valid).sum())
    summary["oi_records_without_finite_timestamp"] = int(
        (at == np.iinfo(np.int64).min).sum()
    )
    ibspot = arrays["spot"][:60]
    good = np.isfinite(ibspot) & (ibspot > 0)
    ib_count = int(good.sum())
    ib_range = (
        float(np.max(ibspot[good]) - np.min(ibspot[good])) if good.any() else None
    )
    checks = dict(
        identity_clock_normalization_pass=True,
        ib_valid=bool(ib_count >= 57 and ib_range is not None and ib_range > 0),
        all_decision_spot_minutes_60_195_valid=bool(arrays["spot_valid"][60:196].all()),
        every_minute_61_205_has_some_valid_quote=bool(
            (good_quote[61:206].sum(axis=1) > 0).all()
        ),
        some_oi_known_by_1030=bool(per.known_oi_valid_contracts.iloc[60] > 0),
    )
    summary.update(
        ib_valid_samples=ib_count,
        ib_range=ib_range,
        technical_checks=checks,
        future_short_session_candidate=bool(all(checks.values())),
        candidate_scope="Observed source feasibility under declared clock conventions; not admitted to frozen cache/engine",
    )
    sum_columns = [
        name
        for name in per
        if name.endswith("_rows") or name.endswith("_same_contract")
    ]
    windows = {}
    for name, (low, high) in WINDOWS.items():
        block = per.iloc[low:high]
        windows[name] = dict(
            slots=high - low,
            minutes_with_rows=int((block.present_rows > 0).sum()),
            valid_spot_minutes=int(block.spot_valid.sum()),
            minutes_with_valid_quote=int((block.valid_quote_rows > 0).sum()),
            min_known_oi_valid=int(block.known_oi_valid_contracts.min()),
            max_known_oi_valid=int(block.known_oi_valid_contracts.max()),
            counts={col: int(block[col].sum()) for col in sum_columns},
        )
    summary["windows"] = windows
    summary["paired_clock_rows"] = int(len(age)) if native else None
    summary["paired_clock_nonzero_age_rows"] = (
        int(np.count_nonzero(age != 0)) if native else None
    )
    return per, summary


def main():
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    out = ROOT / "short_session_source_v1"
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    deps = {
        name: sha(Path(__file__).with_name(name))
        for name in (
            "inspect_short_session_sources.py",
            "build_cache.py",
            "level_engine.py",
        )
    }
    calendar = ROOT / "cache_v1/expected_calendar.csv"
    frozen = pd.read_csv(calendar, dtype={"date": str})
    if tuple(frozen.loc[~frozen.full_session, "date"]) != DATES:
        raise AssertionError("Short-session calendar changed")
    sourcehashes = {}
    for ticker in TICKERS:
        for date in DATES:
            for kind in ("greeks", "oi"):
                path = cache.source_path(cache.ROOT, ticker, date, kind)
                sourcehashes[str(path)] = cache.source_record(path)
    (out / "source_hashes_before.json").write_text(
        json.dumps(sourcehashes, indent=2) + "\n", encoding="utf-8"
    )
    summaries = []
    minutes = []
    for ticker in TICKERS:
        for date in DATES:
            frames = []
            for kind, columns in (
                ("greeks", cache.GREEK_COLUMNS),
                ("oi", cache.OI_COLUMNS),
            ):
                path = cache.source_path(cache.ROOT, ticker, date, kind)
                if cache.source_record(path) != sourcehashes[str(path)]:
                    raise AssertionError("Source changed before reading")
                schema = pq.read_schema(path)
                frames.append(
                    pq.read_table(
                        path,
                        columns=[col for col in columns if col in schema.names],
                        use_threads=False,
                    ).to_pandas(use_threads=False)
                )
            per, summary = diagnostic(*frames, ticker, date)
            for kind in ("greeks", "oi"):
                path = cache.source_path(cache.ROOT, ticker, date, kind)
                if cache.source_record(path) != sourcehashes[str(path)]:
                    raise AssertionError("Source changed after diagnostic")
            summaries.append(summary)
            minutes.append(per)
            print(
                json.dumps(
                    dict(
                        ticker=ticker,
                        date=date,
                        normalization=summary["normalization_status"],
                        candidate=summary["future_short_session_candidate"],
                    )
                ),
                flush=True,
            )
    after = {path: cache.source_record(Path(path)) for path in sourcehashes}
    if after != sourcehashes or any(
        sha(Path(__file__).with_name(name)) != digest for name, digest in deps.items()
    ):
        raise AssertionError("Source/dependency changed during run")
    pd.concat(minutes, ignore_index=True).to_csv(
        out / "minute_coverage.csv", index=False
    )
    result = dict(
        status="SHORT_SESSION_SOURCE_DIAGNOSTIC_COMPLETE",
        days=len(summaries),
        sources=len(sourcehashes),
        source_hash_mismatches=0,
        normalization_pass=sum(s["normalization_status"] == "PASS" for s in summaries),
        future_short_session_candidates=sum(
            s["future_short_session_candidate"] for s in summaries
        ),
        calendar_sha256=sha(calendar),
        dependencies=deps,
        summaries=summaries,
        admitted_to_current_engine=False,
        cache_written=False,
        economic_outcomes_read=False,
        network_used=False,
        after_close_quote_fields_do_not_establish_executability=True,
        wall_seconds=time.perf_counter() - started,
        completed_utc=datetime.now(timezone.utc).isoformat(),
    )
    (out / "summary.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (out / "source_hashes_after.json").write_text(
        json.dumps(after, indent=2) + "\n", encoding="utf-8"
    )
    (out / "inspect_short_session_sources.executed.py").write_bytes(
        Path(__file__).read_bytes()
    )
    (out / "artifact_hashes.json").write_text(
        json.dumps({p.name: sha(p) for p in out.iterdir() if p.is_file()}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in result.items() if k != "summaries"}), flush=True)


if __name__ == "__main__":
    main()
