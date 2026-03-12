"""
Underlying Downloader — Replaces D:/ThetaData/script4_underlying_from_options.py

Derives 1-minute OHLC from options Greeks (spot proxy) using thetadata-api.
Auto-applies zero-repair via corrector.fix_dataframe().

Usage:
    python services/underlying_downloader.py --symbols SPXW SPX SPY QQQ VIX TLT --start 2024-01-01 --end 2026-02-28
"""

import sys
import os
import asyncio
import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THETADATA_API = os.path.join(PROJECT_ROOT, "thetadata-api")
sys.path.insert(0, THETADATA_API)

from thetadata_api.client import ThetaClient
from thetadata_api.corrector import fix_dataframe
from thetadata_api.utils import get_logger, fetch_with_interval_fallback, parse_response

logger = get_logger("UnderlyingDownloader")

DEFAULT_SYMBOLS = ["SPXW", "SPX", "SPY", "QQQ", "VIX", "TLT"]
DEFAULT_OUTPUT = "D:/ThetaData/data_underlying_derived"


async def download_underlying(symbol: str, start: date, end: date, output_dir: Path):
    """Download and derive underlying OHLC for a single symbol across date range."""
    client = ThetaClient()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get holidays
    closed_dates = set()
    for year in range(start.year, end.year + 1):
        try:
            resp, _ = await fetch_with_interval_fallback(
                client.session, f"{client.base_url}/calendar/year_holidays",
                {"year": str(year), "format": "json"},
                client.logger, client.audit, client.stats, "calendar"
            )
            if resp and resp.status_code == 200:
                entries = parse_response(resp.json())
                for entry in entries:
                    if isinstance(entry, dict) and entry.get("type") == "full_close":
                        try:
                            closed_dates.add(date.fromisoformat(entry["date"]))
                        except:
                            pass
        except:
            pass

    logger.info(f"[{symbol}] {len(closed_dates)} holidays loaded")

    # Build trading day list
    d = start
    trading_days = []
    while d <= end:
        if d.weekday() < 5 and d not in closed_dates:
            trading_days.append(d)
        d += timedelta(days=1)

    logger.info(f"[{symbol}] Processing {len(trading_days)} trading days...")

    processed = 0
    skipped = 0

    for day in trading_days:
        day_str = day.strftime("%Y%m%d")
        save_dir = output_dir / symbol / str(day.year) / f"{day.month:02d}"
        save_path = save_dir / f"{symbol}_{day_str}_ohlc_1m.parquet"

        if save_path.exists():
            processed += 1
            continue

        try:
            result = await client.fetch_underlying_ohlc(symbol, day.strftime("%Y-%m-%d"))
            df = result.data

            if df.empty:
                skipped += 1
                continue

            # Apply zero-repair
            df = fix_dataframe(df)

            # Add metadata columns
            df["date"] = day_str
            df["symbol"] = symbol

            save_dir.mkdir(parents=True, exist_ok=True)
            pq.write_table(
                pa.Table.from_pandas(df, preserve_index=False),
                save_path, compression="snappy"
            )
            processed += 1

            if processed % 50 == 0:
                logger.info(f"  [{symbol}] {processed} days processed, {skipped} skipped")

        except Exception as e:
            skipped += 1
            if "No expirations" not in str(e):
                logger.warning(f"  [{symbol}] {day_str}: {e}")

    await client.close()
    logger.info(f"[{symbol}] Done: {processed} processed, {skipped} skipped")


def run_symbol(args_tuple):
    """Bridge for multiprocessing."""
    symbol, start, end, output_dir = args_tuple
    asyncio.run(download_underlying(symbol, start, end, output_dir))


def main():
    parser = argparse.ArgumentParser(description="Derive underlying OHLC from options")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    from datetime import datetime
    s_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    e_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    out_dir = Path(args.output)

    print("=" * 70)
    print("UNDERLYING DOWNLOADER — Spot OHLC from Options Greeks")
    print("=" * 70)
    print(f"  Symbols:  {args.symbols}")
    print(f"  Range:    {s_date} to {e_date}")
    print(f"  Output:   {out_dir}")
    print("=" * 70)

    import multiprocessing
    tasks = [(sym, s_date, e_date, out_dir) for sym in args.symbols]
    num_procs = min(len(args.symbols), 4)

    with multiprocessing.Pool(processes=num_procs) as pool:
        pool.map(run_symbol, tasks)

    print("\nAll symbols processed.")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
