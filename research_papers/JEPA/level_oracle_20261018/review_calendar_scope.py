"""Frozen calendar comparison and early-close Greek/OI filename/footer census."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import exchange_calendars as xc
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SOURCE = Path("D:/ThetaData/data_options")
TICKERS = ("QQQ", "SPXW", "SPY")


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    started = time.perf_counter()
    out = ROOT / "calendar_scope_review_v1"
    out.mkdir(parents=True, exist_ok=False)
    path = ROOT / "cache_v1/expected_calendar.csv"
    frozen = pd.read_csv(path, dtype={"date": str})
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"].copy()
    schedule["date"] = schedule.index.strftime("%Y%m%d")
    if frozen.date.tolist() != schedule.date.tolist():
        raise ValueError("Frozen/live-installed-library session identities differ")
    for field in ("open", "close"):
        if not (
            pd.to_datetime(frozen[field], utc=True).to_numpy()
            == schedule[field].to_numpy()
        ).all():
            raise ValueError("Frozen/installed-library clock differs: " + field)
    durations = (
        pd.to_datetime(frozen.close, utc=True) - pd.to_datetime(frozen.open, utc=True)
    ).dt.total_seconds() / 60
    if not (frozen.full_session == (durations == 390)).all():
        raise ValueError("Full-session flag differs")
    short = frozen.loc[~frozen.full_session].copy()
    short["open_et"] = (
        pd.to_datetime(short.open, utc=True)
        .dt.tz_convert("America/New_York")
        .dt.strftime("%H:%M")
    )
    short["close_et"] = (
        pd.to_datetime(short.close, utc=True)
        .dt.tz_convert("America/New_York")
        .dt.strftime("%H:%M")
    )
    short["minutes"] = durations.loc[short.index].astype(int)
    short["ticker_days"] = len(TICKERS)
    index_path = ROOT / "engine_v1/index.parquet"
    index = pd.read_parquet(index_path, columns=["ticker", "date", "status"])
    index["date"] = index.date.astype(str)
    planned = {(ticker, date) for ticker in TICKERS for date in short.date}
    indexed = set(index[["ticker", "date"]].itertuples(index=False, name=None))
    if planned & indexed:
        raise ValueError("Short days unexpectedly entered frozen engine index")
    records = []
    for ticker, date in sorted(planned):
        for family in ("greeks", "oi"):
            source = (
                SOURCE
                / ticker
                / family
                / date[:4]
                / date[4:6]
                / f"{ticker}_{date}_{date}_{family}.parquet"
            )
            record = dict(
                ticker=ticker,
                date=date,
                family=family,
                path=str(source),
                exists=source.exists(),
                source_values_read=False,
                full_source_bytes_hashed=False,
            )
            if source.exists():
                footer = pq.ParquetFile(source)
                schema = footer.schema_arrow
                record.update(
                    bytes=source.stat().st_size,
                    mtime_ns=source.stat().st_mtime_ns,
                    rows=footer.metadata.num_rows,
                    row_groups=footer.metadata.num_row_groups,
                    fields=[(field.name, str(field.type)) for field in schema],
                    schema_sha256=hashlib.sha256(
                        schema.serialize().to_pybytes()
                    ).hexdigest(),
                    has_quote_timestamp="timestamp" in schema.names,
                    has_underlying_timestamp="underlying_timestamp" in schema.names,
                    has_underlying_price="underlying_price" in schema.names,
                    has_bid_ask=all(name in schema.names for name in ("bid", "ask")),
                    has_delta_iv=all(
                        name in schema.names for name in ("delta", "implied_vol")
                    ),
                    has_oi="open_interest" in schema.names,
                )
            records.append(record)
    short.to_csv(out / "excluded_sessions.csv", index=False)
    pd.DataFrame(
        [
            {key: value for key, value in item.items() if key != "fields"}
            for item in records
        ]
    ).to_csv(out / "source_footers.csv", index=False)
    years = []
    for year, frame in frozen.groupby(frozen.date.str[:4]):
        full = int(frame.full_session.sum())
        years.append(
            dict(
                year=year,
                all_sessions=len(frame),
                full_sessions=full,
                short_sessions=len(frame) - full,
                expected_all_ticker_days=3 * len(frame),
                planned_short_exclusions=3 * (len(frame) - full),
            )
        )
    result = dict(
        status="CALENDAR_SCOPE_METADATA_REVIEW_COMPLETE",
        calendar_sha256=sha(path),
        engine_index_sha256=sha(index_path),
        code_sha256=sha(Path(__file__)),
        calendar_library=xc.__version__,
        installed_calendar_matches_frozen=True,
        all_sessions=len(frozen),
        full_sessions=int(frozen.full_session.sum()),
        short_sessions=len(short),
        all_ticker_days=3 * len(frozen),
        full_ticker_days=len(index),
        full_available=int((index.status == "COMPLETE").sum()),
        full_missing=int((index.status == "MISSING_SOURCE").sum()),
        planned_short_excluded_ticker_days=len(planned),
        short_dates=short.date.tolist(),
        by_year=years,
        source_files_expected=len(records),
        source_files_present=sum(item["exists"] for item in records),
        sources=records,
        source_values_read=False,
        economics_read=False,
        cache_modified=False,
        network_used=False,
        note="Filename/footer presence only; no intraday quote coverage, row-value validity or source admission established",
        completed_utc=datetime.now(timezone.utc).isoformat(),
        wall_seconds=time.perf_counter() - started,
    )
    (out / "summary.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (out / "review_calendar_scope.executed.py").write_bytes(Path(__file__).read_bytes())
    hashes = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    (out / "artifact_hashes.json").write_text(
        json.dumps(
            dict(scope="Prior files only; manifest excludes itself", files=hashes),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps({key: value for key, value in result.items() if key != "sources"}),
        flush=True,
    )


if __name__ == "__main__":
    main()
