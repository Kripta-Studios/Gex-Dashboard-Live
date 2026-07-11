"""Create a physically sealed view of the 202501-202605 dataset, excluding June 2026."""
from __future__ import annotations

import hashlib
from pathlib import Path
import pandas as pd

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def main() -> int:
    src_path = Path("tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet")
    dest_dir = Path("tmp")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "event_option_dataset_execquote_causal1030_202501_202605_regime_v1.parquet"

    print(f"Reading source dataset from {src_path}...")
    df = pd.read_parquet(src_path)
    print(f"Original shape: {df.shape}")
    print(f"Original date range: {df['trade_date'].min()} to {df['trade_date'].max()}")

    # Filter to exclude any date > 20260531
    df_filtered = df[df["trade_date"].astype(int) <= 20260531].copy()
    print(f"Filtered shape: {df_filtered.shape}")
    print(f"Filtered date range: {df_filtered['trade_date'].min()} to {df_filtered['trade_date'].max()}")

    # Assert that no June 2026 data exists in the filtered dataset
    max_date = int(df_filtered["trade_date"].max())
    assert max_date <= 20260531, f"Sealing assertion failed: max date is {max_date} > 20260531"

    df_filtered.to_parquet(dest_path)
    file_hash = sha256_file(dest_path)
    print(f"Sealed dataset written to {dest_path}")
    print(f"SHA-256 hash: {file_hash}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
