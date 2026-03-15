"""
RL Data Preprocessing — Episode Index & Options Cache Builder

Runs once before training to:
1. Filter training_df to valid MLP signal events
2. Build compact options cache keyed by (date, time) for fast episode resets
"""

import os
import sys
import pickle
import time
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import time as dt_time

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEURAL_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(NEURAL_DIR)
sys.path.insert(0, NEURAL_DIR)
sys.path.insert(0, PROJECT_ROOT)

from .config import RL_CONFIG, STRIKE_BUCKETS


def generate_episode_index(training_df: pd.DataFrame,
                           mlp_model=None,
                           mlp_normalizer=None,
                           min_confidence: float = None) -> pd.DataFrame:
    """
    Pre-filter training_df to only rows where the MLP would emit a LONG or SHORT
    signal with confidence >= min_confidence.

    If mlp_model is provided, runs inference to compute predictions.
    If not, uses the 'target' column as a proxy (target != 0 means signal).

    Returns: filtered DataFrame with 'episode_id', 'mlp_direction', 'mlp_confidence' added.
    """
    min_confidence = min_confidence or RL_CONFIG["min_confidence"]

    if mlp_model is not None and mlp_normalizer is not None:
        # Run inference on all rows
        import torch
        from hybrid_model import FEATURE_COLUMNS

        # Filter to only columns that exist in the training data
        cols = [c for c in FEATURE_COLUMNS if c in training_df.columns]
        if len(cols) != len(FEATURE_COLUMNS):
            missing = [c for c in FEATURE_COLUMNS if c not in training_df.columns]
            print(f"  [!] {len(missing)} features missing from data (using {len(cols)}/{len(FEATURE_COLUMNS)}): {missing}")
        features = training_df[cols].values.astype(np.float32)
        features_norm = mlp_normalizer.transform(features)

        is_gbt = hasattr(mlp_model, 'predict_proba') and not isinstance(mlp_model, torch.nn.Module)

        if is_gbt:
            # GBT Inference
            probs = mlp_model.predict_proba(features_norm)
            predictions = np.argmax(probs, axis=1)
            confidences = np.max(probs, axis=1)
            time_targets = np.column_stack([np.full(len(probs), 60.0), np.full(len(probs), 0.0)])
        else:
            # PyTorch Inference
            device = next(mlp_model.parameters()).device
            mlp_model.eval()
            with torch.no_grad():
                X = torch.FloatTensor(features_norm).to(device)
                batch_size = 4096
                all_probs = []
                all_time_targets = []
                for i in range(0, len(X), batch_size):
                    batch = X[i:i + batch_size]
                    output = mlp_model(batch)
                    if isinstance(output, tuple):
                        logits, time_pred = output
                    elif isinstance(output, dict):
                        logits = output.get("logits", output.get("class_logits"))
                        time_pred = output.get("time_to_target", None)
                    else:
                        logits = output 
                        time_pred = None
                    batch_probs = torch.softmax(logits, dim=-1).cpu().numpy()
                    all_probs.append(batch_probs)
                    if time_pred is not None:
                        all_time_targets.append(time_pred.cpu().numpy())

                probs = np.concatenate(all_probs, axis=0)
                if all_time_targets:
                    time_targets = np.concatenate(all_time_targets, axis=0)
                else:
                    time_targets = np.full(len(probs), 0.5)
            
            predictions = np.argmax(probs, axis=1)
            confidences = np.max(probs, axis=1)

        # Map: 0=LONG, 1=HOLD, 2=SHORT (standard mapping)
        direction_map = {0: "SHORT", 1: "HOLD", 2: "LONG"}
        directions = [direction_map.get(p, "HOLD") for p in predictions]

        training_df = training_df.copy()
        training_df["mlp_direction"] = directions
        training_df["mlp_confidence"] = confidences
        
        if is_gbt:
            training_df["mlp_time_to_target"] = 0.5
            training_df["mlp_log_sigma"] = 0.0
        else:
            if time_targets.ndim > 1:
                training_df["mlp_time_to_target"] = time_targets[:, 0] / 180.0
                training_df["mlp_log_sigma"] = time_targets[:, 1]
            else:
                training_df["mlp_time_to_target"] = time_targets.flatten() / 180.0
                training_df["mlp_log_sigma"] = 0.5

    else:
        # Proxy: use target column
        training_df = training_df.copy()
        target = training_df.get("target", pd.Series(0, index=training_df.index))
        training_df["mlp_direction"] = target.map({1: "LONG", -1: "SHORT", 0: "HOLD"})
        training_df["mlp_confidence"] = 0.70  # default
        training_df["mlp_time_to_target"] = 0.5
        training_df["mlp_log_sigma"] = 0.5

    # Filter to signal events only
    mask = (
        (training_df["mlp_direction"].isin(["LONG", "SHORT"])) &
        (training_df["mlp_confidence"] >= min_confidence)
    )
    filtered = training_df[mask].copy()
    filtered["episode_id"] = range(len(filtered))

    print(f"[RL] Episode index: {len(filtered)}/{len(training_df)} rows qualify "
          f"({100*len(filtered)/len(training_df):.1f}%)")
    print(f"[RL] Direction split: {filtered['mlp_direction'].value_counts().to_dict()}")

    return filtered.reset_index(drop=True)


def _process_single_date(args_tuple):
    """
    Process a single date's options data for the RL cache.
    Top-level function so it can be pickled by multiprocessing.
    
    Each worker saves its own {date_str}.pkl shard to output_dir,
    avoiding MemoryError from large IPC serialization.
    
    Returns: (processed_count, skipped_count)
    """
    date_str, date_episodes, options_dir, max_forward_minutes, output_dir = args_tuple

    from collect_training_data_spx_qqq import get_parquet_file, calculate_exact_t

    date_str = str(date_str)
    year, month = date_str[:4], date_str[4:6]

    partial_cache = {}
    processed = 0
    skipped = 0

    # Group episodes by ticker
    for ticker_sym, ticker_episodes in date_episodes.groupby("ticker"):
        greek_ticker = "SPXW" if ticker_sym == "SPX" else ticker_sym
        entry_times = ticker_episodes["time"].unique()

        # Load daily greek file
        try:
            daily_file = get_parquet_file(greek_ticker, date_str, is_0dte=True)
            if daily_file is None:
                skipped += len(entry_times)
                continue
            df_daily = pd.read_parquet(daily_file)
            df_daily["dt"] = pd.to_datetime(df_daily["underlying_timestamp"])
        except Exception:
            skipped += len(entry_times)
            continue

        # Load OI data
        oi_dir = Path(options_dir) / greek_ticker / "oi" / year / month
        oi_file = oi_dir / daily_file.name.replace("greeks.parquet", "oi.parquet")
        if not oi_file.exists():
            skipped += len(entry_times)
            continue

        try:
            df_oi = pd.read_parquet(oi_file)
            df_oi_agg = df_oi.groupby(["strike", "right"]).agg(
                {"open_interest": "max"}
            ).reset_index()
        except Exception:
            skipped += len(entry_times)
            continue

        all_timestamps = sorted(df_daily["dt"].unique())
        ts_index = {pd.to_datetime(ts).strftime("%H:%M"): i
                    for i, ts in enumerate(all_timestamps)}

        for entry_time in entry_times:
            entry_time = str(entry_time)
            cache_key = f"{ticker_sym}_{date_str}_{entry_time}"

            if entry_time not in ts_index:
                skipped += 1
                continue

            start_idx = ts_index[entry_time]
            spot = float(ticker_episodes[
                ticker_episodes["time"] == entry_time
            ].iloc[0].get("spot_price", 0))

            # Compute day ATR from surrounding data
            day_atr = _compute_day_atr(df_daily, all_timestamps, start_idx)

            # Build forward-looking minute data
            minutes_data = {}
            for offset in range(min(max_forward_minutes + 1,
                                    len(all_timestamps) - start_idx)):
                ts_np = all_timestamps[start_idx + offset]
                ts = pd.to_datetime(ts_np)

                df_min = df_daily[df_daily["dt"] == ts_np].copy()
                df_pq = pd.merge(df_min, df_oi_agg, on=["strike", "right"], how="inner")
                if df_pq.empty:
                    continue

                minute_spot = float(df_pq["underlying_price"].iloc[0]) if "underlying_price" in df_pq.columns else spot
                atr_range = 5.0 * day_atr

                # Filter to ±5 ATR
                df_pq = df_pq[
                    (df_pq["strike"] >= minute_spot - atr_range) &
                    (df_pq["strike"] <= minute_spot + atr_range)
                ]

                # Filtrar strikes sin datos reales
                if "bid" in df_pq.columns:
                    df_pq = df_pq[
                        (df_pq["delta"].abs() > 0.01) &
                        (df_pq["bid"] > 0)
                    ]
                else:
                    # Fallback in case "bid" is not in the derived columns
                    df_pq = df_pq[df_pq["delta"].abs() > 0.01]

                calls, puts = {}, {}
                for _, row in df_pq.iterrows():
                    strike = float(row["strike"])
                    right = str(row.get("right", "")).upper()
                    
                    bid = float(row.get("bid", 0))
                    ask = float(row.get("ask", 0))
                    mid = (bid + ask) / 2.0 if (bid > 0 or ask > 0) else 0.0
                    
                    data = {
                        "price": mid,
                        "delta": float(row.get("delta", 0)),
                        "iv": float(row.get("implied_vol", 0.15)),
                        "theta": float(row.get("theta", 0)),
                        "gamma": float(row.get("gamma", 0)),
                    }
                    if right == "CALL" or right == "C":
                        calls[strike] = data
                    elif right == "PUT" or right == "P":
                        puts[strike] = data

                minutes_data[offset] = {
                    "spot": minute_spot,
                    "calls": calls,
                    "puts": puts,
                }

            # Entry-level data
            entry_minute = minutes_data.get(0, {})
            partial_cache[cache_key] = {
                "spot": spot,
                "day_atr": day_atr,
                "calls": entry_minute.get("calls", {}),
                "puts": entry_minute.get("puts", {}),
                "minutes": minutes_data,
            }
            processed += 1

    # --- Save shard directly to disk ---
    if partial_cache:
        out_file = Path(output_dir) / f"{date_str}.pkl"
        with open(out_file, "wb") as f:
            pickle.dump(partial_cache, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Only return counters — no large dict over IPC
    return processed, skipped


def preprocess_options_for_rl(episode_index: pd.DataFrame,
                              options_dir: str,
                              output_dir: str,
                              max_forward_minutes: int = 180,
                              num_workers: int = 24):
    """
    Build compact options cache for fast RL episode resets.
    Parallelized across dates using multiprocessing.Pool.

    Each worker saves its own {date}.pkl shard to output_dir,
    avoiding MemoryError from large IPC serialization.

    For each unique (date, time) pair in episode_index:
    1. Load the per-strike Greeks + prices from parquet
    2. Extract strikes within ±5 ATR of spot
    3. Save as compact dict shard per date

    Output format per key:
    {
        "spot": float,
        "day_atr": float,
        "calls": {strike: {price, delta, iv, theta, gamma}},
        "puts":  {strike: {price, delta, iv, theta, gamma}},
        "minutes": {
            0: {"spot": float, "calls": {...}, "puts": {...}},
            1: {"spot": float, "calls": {...}, "puts": {...}},
            ...up to max_forward_minutes
        }
    }
    """
    import multiprocessing
    ctx = multiprocessing.get_context('spawn')

    unique_dates = episode_index["date"].unique()
    print(f"[RL] Pre-processing options for {len(unique_dates)} unique dates with {num_workers} workers...", flush=True)

    # Create the output directory for shards
    os.makedirs(output_dir, exist_ok=True)

    # Build per-date argument tuples (includes output_dir for each worker)
    work_items = []
    for date_str in unique_dates:
        date_episodes = episode_index[episode_index["date"].astype(str) == str(date_str)].copy()
        work_items.append((date_str, date_episodes, options_dir, max_forward_minutes, output_dir))

    print(f"[RL] Dispatching {len(work_items)} work items to pool...", flush=True)

    total_processed = 0
    total_skipped = 0
    total_dates = len(unique_dates)
    t_pool_start = time.time()

    with ctx.Pool(processes=num_workers) as pool:
        # Workers return only (processed, skipped) counters — no large dicts over IPC
        for i, (proc, skip) in enumerate(
            pool.imap_unordered(_process_single_date, work_items)
        ):
            total_processed += proc
            total_skipped += skip

            # Progress every date
            done = i + 1
            pct = done / total_dates * 100
            elapsed = time.time() - t_pool_start
            if done > 1:
                eta = elapsed / done * (total_dates - done)
                eta_str = f"{eta/60:.1f}min" if eta > 60 else f"{eta:.0f}s"
            else:
                eta_str = "..."
            bar_len = 25
            filled = int(bar_len * done / total_dates)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {pct:5.1f}% | {done}/{total_dates} dates | "
                  f"eps: {total_processed:,} | skip: {total_skipped:,} | "
                  f"ETA: {eta_str}   ", end="", flush=True)

    print(flush=True)
    print(f"[RL] Options cache chunks built in: {output_dir}", flush=True)
    print(f"[RL] Total: {total_processed} episodes processed, {total_skipped} skipped", flush=True)
    return None


def _compute_day_atr(df_daily: pd.DataFrame, all_timestamps: list,
                     center_idx: int, window: int = 15) -> float:
    """Compute rolling ATR from surrounding price data."""
    start = max(0, center_idx - window)
    end = min(len(all_timestamps), center_idx + window)

    prices = []
    for i in range(start, end):
        ts_np = all_timestamps[i]
        rows = df_daily[df_daily["dt"] == ts_np]
        if not rows.empty and "underlying_price" in rows.columns:
            prices.append(float(rows["underlying_price"].iloc[0]))

    if len(prices) < 3:
        return 5.0  # fallback

    prices_arr = np.array(prices)
    returns = np.abs(np.diff(prices_arr))
    atr = float(np.mean(returns))
    return max(atr, 0.5)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build RL options cache")
    parser.add_argument("--training-data", type=str, required=True,
                        help="Path to training_data_derived.parquet")
    parser.add_argument("--options-dir", type=str, default="D:/ThetaData/data_options",
                        help="Path to options data directory")
    parser.add_argument("--output", type=str, default="../rl_data/rl_options_cache_chunks",
                        help="Output directory for per-day cache shards (.pkl)")
    parser.add_argument("--mlp-model", type=str, default=None,
                        help="Path to trained MLP model (optional)")
    parser.add_argument("--mlp-normalizer", type=str, default=None,
                        help="Path to trained normalizer (optional)")
    parser.add_argument("--num-workers", type=int, default=24,
                        help="Number of parallel workers (default: 24)")
    args = parser.parse_args()

    print("=" * 70, flush=True)
    print("RL DATA PREPROCESSING — OPTIONS CACHE BUILDER (CHUNKED)", flush=True)
    print("=" * 70, flush=True)

    print(f"Loading training data from: {args.training_data}", flush=True)
    training_df = pd.read_parquet(args.training_data)
    print(f"Loaded training data: {training_df.shape}", flush=True)

    mlp_model = None
    mlp_normalizer = None
    if args.mlp_model and args.mlp_normalizer:
        from hybrid_model import load_ensemble_model
        mlp_model, mlp_normalizer = load_ensemble_model(args.mlp_model, args.mlp_normalizer, model_size="small")

    episode_index = generate_episode_index(training_df, mlp_model, mlp_normalizer)

    # Save episode index alongside the chunks directory
    output_parent = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_parent, exist_ok=True)
    episode_index.to_parquet(
        os.path.join(output_parent, "episode_index.parquet"),
        index=False,
    )

    preprocess_options_for_rl(
        episode_index, args.options_dir, args.output,
        num_workers=args.num_workers,
    )

    print("\n✓ Preprocessing complete!")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    main()
