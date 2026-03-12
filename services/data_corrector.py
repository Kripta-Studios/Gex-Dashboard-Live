"""
Data Corrector — Replaces D:/ThetaData/script8_corrector.py

Batch zero-repair for all parquet files in a directory tree.
Uses thetadata_api.corrector.fix_ohlc_files() and fix_dataframe().

Usage:
    python services/data_corrector.py --data-dir D:/ThetaData/data_underlying_derived --symbols SPXW SPY QQQ VIX TLT
"""

import sys
import os
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THETADATA_API = os.path.join(PROJECT_ROOT, "thetadata-api")
sys.path.insert(0, THETADATA_API)

from thetadata_api.corrector import fix_ohlc_files, fix_dataframe
from thetadata_api.utils import get_logger

logger = get_logger("DataCorrector")

DEFAULT_DATA_DIR = "D:/ThetaData/data_underlying_derived"
DEFAULT_SYMBOLS = ["SPXW", "SPY", "QQQ", "VIX", "TLT"]


def main():
    parser = argparse.ArgumentParser(description="Fix zero-gaps in OHLC data")
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR,
                        help=f"Data directory (default: {DEFAULT_DATA_DIR})")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Symbols to process (default: {DEFAULT_SYMBOLS})")
    args = parser.parse_args()

    print("=" * 70)
    print("DATA CORRECTOR — Zero-Repair Batch Process")
    print("=" * 70)
    print(f"  Directory: {args.data_dir}")
    print(f"  Symbols:   {args.symbols}")
    print("=" * 70)

    fix_ohlc_files(args.data_dir, args.symbols)

    print("\nCorrection complete.")


if __name__ == "__main__":
    main()
