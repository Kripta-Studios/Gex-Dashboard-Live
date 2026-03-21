import os
import sys
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from neural.rl.utils import get_delta_bucket, get_iv_bucket, get_pnl_bucket


def main():
    # Get absolute path to project root (Gex-Dashboard-Live/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    index_path = os.path.join(project_root, "rl_data", "episode_index.parquet")
    cache_dir = os.path.join(project_root, "rl_data", "rl_options_cache_chunks")
    output_path = os.path.join(project_root, "rl_data", "recovery_stats.pkl")
    
    if not os.path.exists(index_path):
        print(f"Index not found at {index_path}")
        return

    df = pd.read_parquet(index_path)
    # Use a subset if testing, but for production let's use all
    # df = df.sample(2000) 
    
    print(f"Processing {len(df)} episodes...")
    
    # stats[delta_b][iv_b][pnl_b] = [recovered_count, total_count]
    stats = {}
    
    # Delta targets from STRIKE_BUCKETS
    delta_targets = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]
    
    # Cache for loaded days to avoid redundant disk I/O
    loaded_cache = {}
    
    for _, row in tqdm(df.iterrows(), total=len(df)):
        ticker = row.get("ticker", "SPX")
        date_str = str(row.get("date"))
        time_str = str(row.get("time"))
        direction = row.get("mlp_direction", "LONG")
        
        # Load cache for this day
        if date_str not in loaded_cache:
            if len(loaded_cache) >= 5:
                # LRU: remove oldest before loading new
                oldest_key = next(iter(loaded_cache))
                loaded_cache.pop(oldest_key, None)
                
            cache_file = os.path.join(cache_dir, f"{date_str}.pkl")
            if not os.path.exists(cache_file):
                continue
            with open(cache_file, "rb") as f:
                loaded_cache[date_str] = pickle.load(f)
        
        day_cache = loaded_cache[date_str]
        signal_key = f"{ticker}_{date_str}_{time_str}"
        
        # New format has 'episodes' and 'minute_data'
        if "episodes" not in day_cache or signal_key not in day_cache["episodes"]:
            continue
            
        entry_data = day_cache["episodes"][signal_key]
        
        # Reconstruct future minutes from minute_data[ticker][ts]
        ticker_minutes = day_cache.get("minute_data", {}).get(ticker, {})
        all_timestamps = day_cache.get("timestamps", [])
        
        if not ticker_minutes or not all_timestamps:
            continue

        try:
            start_idx = all_timestamps.index(time_str)
        except ValueError:
            continue

        future_minutes = {}
        for offset in range(181): # Up to 180 min
            idx = start_idx + offset
            if idx >= len(all_timestamps): break
            ts = all_timestamps[idx]
            if ts in ticker_minutes:
                future_minutes[offset] = ticker_minutes[ts]
            
        if not future_minutes:
            continue
            
        right = "calls" if direction == "LONG" else "puts"
        available_strikes = entry_data.get(right, {})
        if not available_strikes: continue
        
        # Simulate each possible delta bucket entry
        for target in delta_targets:
            # Find closest strike to target delta
            best_strike = None
            min_diff = 999
            for strike, s_data in available_strikes.items():
                diff = abs(abs(s_data["delta"]) - target)
                if diff < min_diff:
                    min_diff = diff
                    best_strike = strike
            
            if best_strike is None: continue
            
            entry_price = available_strikes[best_strike]["price"]
            if entry_price <= 0: continue
            
            # Trace PnL
            pnls = []
            deltas = []
            ivs = []
            
            # future_minutes is a dict: {offset: {spot, calls, puts}}
            sorted_offsets = sorted(future_minutes.keys())
            for offset in sorted_offsets:
                m_data = future_minutes[offset]
                strike_data = m_data.get(right, {}).get(best_strike)
                if strike_data:
                    pnls.append((strike_data["price"] - entry_price) / entry_price)
                    deltas.append(strike_data.get("delta", 0.0))
                    ivs.append(strike_data.get("iv", 0.0))
                else:
                    pnls.append(-1.0) # Expired worthless or strike missing
                    deltas.append(0.0)
                    ivs.append(0.0)
            
            # Record state starting from minute 10 and check recovery (Issue 4)
            for i in range(len(pnls)):
                if i < 10: continue
                if -0.50 < pnls[i] < 0:
                    db = get_delta_bucket(deltas[i])
                    ib = get_iv_bucket(ivs[i])
                    pb = get_pnl_bucket(pnls[i])
                    
                    key = (db, ib, pb)
                    if key not in stats:
                        stats[key] = [0, 0]
                    
                    stats[key][1] += 1
                    # Recovery: reaches PnL > 0.03 within next 120 mins
                    if any(p > 0.03 for p in pnls[i+1 : i+121]):
                        stats[key][0] += 1
                    
    # Finalize lookup table with Bayesian smoothing
    # Prior = 0.35 (more optimistic as agent holds longer), Weight = 20
    prior_p = 0.35
    prior_w = 20
    lookup = {}
    for key, (recovered, total) in stats.items():
        smoothed_rate = (recovered + prior_w * prior_p) / (total + prior_w)
        lookup[key] = float(smoothed_rate)
            
    with open(output_path, "wb") as f:
        pickle.dump(lookup, f)
    
    print(f"Saved lookup table with {len(lookup)} buckets to {output_path}")

if __name__ == "__main__":
    main()
