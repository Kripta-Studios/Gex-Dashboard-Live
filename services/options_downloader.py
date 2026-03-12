"""
Options Downloader — Replaces D:/ThetaData/options_bulk.py

Uses thetadata-api package for bulk historical options download (OHLC + Greeks).
Supports: SPXW, SPX, SPY, QQQ, VIX, TLT

Usage:
    python services/options_downloader.py --symbols SPXW SPX SPY QQQ --start 2024-01-01 --end 2026-02-28
    python services/options_downloader.py --symbols SPXW --start 2026-02-18 --end 2026-02-18
"""

import sys
import os
import argparse
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THETADATA_API = os.path.join(PROJECT_ROOT, "thetadata-api")
sys.path.insert(0, THETADATA_API)

from thetadata_api.bulk import download_historical_options
from thetadata_api.utils import get_logger

logger = get_logger("OptionsDownloader")

DEFAULT_SYMBOLS = ["SPXW", "SPX", "SPY", "QQQ", "VIX", "TLT"]
DEFAULT_OUTPUT = "D:/ThetaData/data_options"


def main():
    parser = argparse.ArgumentParser(description="Bulk download historical options data")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Symbols to download (default: {DEFAULT_SYMBOLS})")
    parser.add_argument("--start", type=str, required=True,
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True,
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT,
                        help=f"Output directory (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    print("=" * 70)
    print("OPTIONS DOWNLOADER — Bulk OHLC + Greeks")
    print("=" * 70)
    print(f"  Symbols:  {args.symbols}")
    print(f"  Range:    {args.start} to {args.end}")
    print(f"  Output:   {args.output}")
    print("=" * 70)

    download_historical_options(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end,
        output_path=args.output,
    )

    print("\nDownload complete.")


if __name__ == "__main__":
    main()
