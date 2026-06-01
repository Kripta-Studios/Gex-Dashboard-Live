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
from neural.signal_policy import (
    deployment_context_mask,
    entry_thresholds,
    get_independent_signals,
)


def _time_to_minutes(value) -> int:
    try:
        if hasattr(value, "hour") and hasattr(value, "minute"):
            return int(value.hour) * 60 + int(value.minute)
        text = str(value)
        hour, minute = text.split(":")[:2]
        return int(hour) * 60 + int(minute)
    except Exception:
        return 570


def generate_episode_index(training_df: pd.DataFrame,
                           mlp_model=None,
                           mlp_normalizer=None,
                           min_confidence: float = None,
                           strict_wf: bool = False,
                           min_entry_minute: int = 580,
                           min_short_entry_minute: int | None = None,
                           min_short_price_vs_ib_high: float | None = None,
                           ticker_models: dict = None,
                           ticker_normalizers: dict = None,
                           is_ticker_specific: bool = False) -> pd.DataFrame:
    """
    Pre-filter training_df to only rows where the MLP would emit a LONG or SHORT
    signal with confidence >= min_confidence.
    """
    min_confidence = min_confidence or RL_CONFIG["min_confidence"]

    if mlp_model is not None and mlp_normalizer is not None:
        # Run inference on all rows
        import torch
        from hybrid_model import FEATURE_COLUMNS

        cols = [c for c in FEATURE_COLUMNS if c in training_df.columns]
        features = training_df[cols].values.astype(np.float32)
        features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)

        is_gbt = hasattr(mlp_model, 'predict_proba') and not isinstance(mlp_model, torch.nn.Module)

        if is_gbt:
            if strict_wf:
                print(f"  [i] Using STRICT Walk-Forward inference (date-by-date filtering) for RL Prep...")
                probs = np.zeros((len(training_df), 3), dtype=np.float32)
                unique_dates = sorted(training_df['date'].unique())
                for d_str in unique_dates:
                    mask = training_df['date'] == d_str
                    # Derive is_up_day from gap_direction
                    gap_dir_day = training_df.loc[mask, 'gap_direction'].values if 'gap_direction' in training_df.columns else None
                    is_up_day_day = (gap_dir_day > 0) if gap_dir_day is not None else None

                    for ticker in training_df.loc[mask, 'ticker'].unique():
                        t_mask = mask & (training_df['ticker'] == ticker)
                        idx = np.where(t_mask)[0]
                        if len(idx) == 0:
                            continue
                        
                        is_up_day_t = is_up_day_day[t_mask[mask].values] if is_up_day_day is not None else None

                        if is_ticker_specific and ticker_models and ticker in ticker_models:
                            t_model = ticker_models[ticker]
                            probs[idx] = t_model.predict_proba(features[idx], date=str(d_str), is_up_day=is_up_day_t)
                        else:
                            probs[idx] = mlp_model.predict_proba(features[idx], date=str(d_str), is_up_day=is_up_day_t)
            else:
                probs = np.zeros((len(training_df), 3), dtype=np.float32)
                gap_dir_all = training_df['gap_direction'].values if 'gap_direction' in training_df.columns else None
                is_up_day_all = (gap_dir_all > 0) if gap_dir_all is not None else None

                if is_ticker_specific and ticker_models:
                    for ticker in training_df['ticker'].unique():
                        mask = training_df['ticker'] == ticker
                        idx = np.where(mask)[0]
                        if len(idx) == 0:
                            continue
                        
                        is_up_day_t = is_up_day_all[idx] if is_up_day_all is not None else None

                        if ticker in ticker_models:
                            probs[idx] = ticker_models[ticker].predict_proba(features[idx], is_up_day=is_up_day_t)
                        else:
                            probs[idx] = mlp_model.predict_proba(features[idx], is_up_day=is_up_day_t)
                else:
                    probs = mlp_model.predict_proba(features, is_up_day=is_up_day_all)
                 
            predictions, confidences = get_independent_signals(probs, base_confidence=min_confidence)
        else:
            features_norm = mlp_normalizer.transform(features)
            device = next(mlp_model.parameters()).device
            mlp_model.eval()
            with torch.no_grad():
                X = torch.FloatTensor(features_norm).to(device)
                batch_size = 4096
                all_probs, all_time_targets = [], []
                for i in range(0, len(X), batch_size):
                    batch = X[i:i + batch_size]
                    output = mlp_model(batch)
                    if isinstance(output, tuple):
                        logits, time_pred = output
                    elif isinstance(output, dict):
                        logits = output.get("logits", output.get("class_logits"))
                        time_pred = output.get("time_to_target", None)
                    else:
                        logits, time_pred = output, None
                    all_probs.append(torch.softmax(logits, dim=-1).cpu().numpy())
                    if time_pred is not None:
                        all_time_targets.append(time_pred.cpu().numpy())

                probs = np.concatenate(all_probs, axis=0)
                time_targets = np.concatenate(all_time_targets, axis=0) if all_time_targets else np.full((len(probs), 2), 0.5)
            
            predictions, confidences = get_independent_signals(probs, base_confidence=min_confidence)

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
        training_df = training_df.copy()
        target = training_df.get("target", pd.Series(0, index=training_df.index))
        training_df["mlp_direction"] = target.map({1: "LONG", -1: "SHORT", 0: "HOLD"})
        training_df["mlp_confidence"] = 0.70
        training_df["mlp_time_to_target"] = 0.5
        training_df["mlp_log_sigma"] = 0.5

    long_thresh, short_thresh = entry_thresholds(min_confidence)
    entry_minutes = training_df["time"].apply(_time_to_minutes)
    time_mask = entry_minutes >= int(min_entry_minute)
    short_time_mask = (
        pd.Series(True, index=training_df.index)
        if min_short_entry_minute is None
        else entry_minutes >= int(min_short_entry_minute)
    )
    if min_short_price_vs_ib_high is None:
        short_ib_mask = pd.Series(True, index=training_df.index)
    else:
        price_vs_ib_high = (
            pd.to_numeric(training_df["price_vs_ib_high"], errors="coerce")
            if "price_vs_ib_high" in training_df.columns
            else pd.Series(0.0, index=training_df.index)
        ).fillna(0.0)
        short_ib_mask = price_vs_ib_high >= float(min_short_price_vs_ib_high)

    context_mask = pd.Series(deployment_context_mask(training_df), index=training_df.index)
    mask_long  = context_mask & time_mask & (training_df["mlp_direction"] == "LONG")  & (training_df["mlp_confidence"] >= long_thresh)
    mask_short = context_mask & time_mask & short_time_mask & short_ib_mask & (training_df["mlp_direction"] == "SHORT") & (training_df["mlp_confidence"] >= short_thresh)

    ep_long  = training_df[mask_long].copy()
    ep_short = training_df[mask_short].copy()

    # ── NO OVERSAMPLING (anti-leakage) ──
    # Previously duplicated minority episodes here, which caused the same
    # episode to appear in both RL train and eval splits.
    # The RL trainer handles class balance during collect_episodes().
    if not ep_short.empty and not ep_long.empty:
        n_long, n_short = len(ep_long), len(ep_short)
        ratio = max(n_long, n_short) / max(min(n_long, n_short), 1)
        print(f"  [Balance] No oversampling (anti-leakage). L:S ratio = {ratio:.2f}")

    filtered = pd.concat([ep_long, ep_short]).sort_values(["date", "time"]).reset_index(drop=True)
    filtered["episode_id"] = range(len(filtered))
    return filtered, training_df


def _process_single_date(args_tuple):
    """
    Process a single date's options data robustly and quickly.
    """
    date_str, date_episodes, options_dir, max_forward_minutes, output_dir, daily_signals = args_tuple
    date_str = str(date_str)
    year, month = date_str[:4], date_str[4:6]
    partial_cache = {}
    processed = 0
    skipped = 0

    from collect_training_data_spx_qqq import get_parquet_file, load_historical_ib_levels
    from services.compute_features import calculate_exact_t, R_RATE, Q_DIV
    from training_data.stats import calc_dp_cdf_pdf

    for ticker_sym, ticker_episodes in date_episodes.groupby("ticker"):
        greek_ticker = "SPXW" if ticker_sym == "SPX" else ticker_sym
        
        # Calculate robust daily ATR without lookahead bias
        hist_ohlc = load_historical_ib_levels(greek_ticker, date_str, n_days=15)
        ranges = [h['ib_high'] - h['ib_low'] for h in hist_ohlc if h is not None]
        if len(ranges) >= 1:
            day_atr = float(np.mean(ranges))
        else:
            day_atr = 70.0 if ticker_sym == "SPX" else 4.0
        day_atr = max(day_atr, 0.5)
        
        # Load daily greek file
        try:
            daily_file = get_parquet_file(greek_ticker, date_str, is_0dte=True)
            if daily_file is None:
                skipped += len(ticker_episodes)
                continue
            df_daily = pd.read_parquet(daily_file)
            df_daily["dt"] = pd.to_datetime(df_daily["underlying_timestamp"])
        except:
            skipped += len(ticker_episodes)
            continue

        # Load OI data
        oi_dir = Path(options_dir) / greek_ticker / "oi" / year / month
        oi_file = oi_dir / daily_file.name.replace("greeks.parquet", "oi.parquet")
        if not oi_file.exists():
            skipped += len(ticker_episodes)
            continue

        try:
            df_oi = pd.read_parquet(oi_file)
            df_oi_agg = df_oi.groupby(["strike", "right"], observed=True).agg({"open_interest": "max"}).reset_index()
        except:
            skipped += len(ticker_episodes)
            continue

        # ── Optimization: Merge & Clean ──
        df_merged = pd.merge(df_daily, df_oi_agg, on=["strike", "right"], how="inner")
        if df_merged.empty:
            skipped += len(ticker_episodes)
            continue
            
        # Robust Column Mapping
        df_merged["right"] = df_merged["right"].str.upper()
        df_merged["mid"] = (df_merged.get("bid", 0).fillna(0) + df_merged.get("ask", 0).fillna(0)) / 2.0
        
        # Skip zero-price options or invalid underlying prices (data gaps)
        df_merged = df_merged[(df_merged["mid"] > 0) & 
                              (df_merged["underlying_price"] > 0) & 
                              (df_merged["strike"] > 0)].copy()
        if df_merged.empty:
            skipped += len(ticker_episodes)
            continue

        # Map IV
        if "implied_vol" in df_merged.columns:
            df_merged["iv"] = df_merged["implied_vol"]
        elif "iv" in df_merged.columns:
            df_merged["iv"] = df_merged["iv"]
        elif "implied_volatility" in df_merged.columns:
            df_merged["iv"] = df_merged["implied_volatility"]
        else:
            df_merged["iv"] = np.nan
            
        df_merged["iv"] = df_merged["iv"].fillna(0.15) # Last resort

        # ── ROBUST GREEKS CALCULATION ──
        greeks_to_check = ["delta", "gamma", "vega", "theta"]
        needs_bs = any(g not in df_merged.columns or df_merged[g].isna().all() for g in greeks_to_check)
        
        if needs_bs:
            S_vec = df_merged["underlying_price"].values.astype(np.float64)
            K_vec = df_merged["strike"].values.astype(np.float64)
            iv_vec = df_merged["iv"].values.astype(np.float64)
            # Ensure IV is safe for division
            iv_vec = np.clip(iv_vec, 0.005, 5.0)
            
            # Ensure T is safe (at least 60s)
            T_vec = calculate_exact_t(pd.to_datetime(df_merged["underlying_timestamp"])).astype(np.float64)
            T_vec = np.clip(T_vec, 1e-7, 1.0)
            
            # Use local error suppression for extreme strikes
            with np.errstate(divide='ignore', invalid='ignore'):
                dp, cdf_dp, pdf_dp = calc_dp_cdf_pdf(S_vec, K_vec, iv_vec, T_vec, R_RATE, Q_DIV)
                is_call = (df_merged["right"] == "CALL").values
                
                if "gamma" not in df_merged.columns or df_merged["gamma"].isna().all():
                    # Formula: exp(-qT) * pdf(d1) / (S * sigma * sqrt(T))
                    denom = S_vec * iv_vec * np.sqrt(T_vec)
                    gamma_vals = (np.exp(-Q_DIV * T_vec) * pdf_dp) / denom
                    df_merged["gamma"] = np.nan_to_num(gamma_vals, nan=0.0, posinf=0.0, neginf=0.0)
                
                if "delta" not in df_merged.columns or df_merged["delta"].isna().all():
                    d_call = np.exp(-Q_DIV * T_vec) * cdf_dp
                    d_put = -np.exp(-Q_DIV * T_vec) * (1.0 - cdf_dp)
                    delta_vals = np.where(is_call, d_call, d_put)
                    df_merged["delta"] = np.nan_to_num(delta_vals, nan=0.0)
                    
                if "vega" not in df_merged.columns or df_merged["vega"].isna().all():
                    vega_vals = S_vec * np.exp(-Q_DIV * T_vec) * np.sqrt(T_vec) * pdf_dp
                    df_merged["vega"] = np.nan_to_num(vega_vals, nan=0.0)

                if "theta" not in df_merged.columns or df_merged["theta"].isna().all():
                    # Simplified BS Theta (ignoring rate effect)
                    term1 = -(S_vec * pdf_dp * iv_vec * np.exp(-Q_DIV * T_vec)) / (2 * np.sqrt(T_vec))
                    term2_call = Q_DIV * S_vec * cdf_dp * np.exp(-Q_DIV * T_vec)
                    term2_put = -Q_DIV * S_vec * (1.0 - cdf_dp) * np.exp(-Q_DIV * T_vec)
                    theta_vals = term1 + np.where(is_call, term2_call, term2_put)
                    df_merged["theta"] = np.nan_to_num(theta_vals, nan=0.0)

        # Final cleanup
        for g in greeks_to_check:
            if g in df_merged.columns:
                df_merged[g] = df_merged[g].fillna(0.0)
            else:
                df_merged[g] = 0.0
        
        # ── Organization into Buckets ──
        underlying_series = df_daily.groupby("dt")["underlying_price"].first().sort_index()
        all_timestamps = underlying_series.index.tolist()
        all_timestamp_strs = [ts.strftime("%H:%M") for ts in all_timestamps]
        
        # Build global minute buckets for this day/ticker
        # We store them in minute_buckets[timestamp_str]
        minute_buckets = {}
        target_cols = ["strike", "right", "mid", "delta", "iv", "theta", "gamma"]
        for ts, group in df_merged.groupby("dt"):
            ts_str = ts.strftime("%H:%M")
            
            calls, puts = {}, {}
            # Pre-filter by a broad range to save RAM in global bucket
            # (We will filter more tightly in the environment anyway)
            spot = group["underlying_price"].iloc[0]
            # Broad filter: ±150 pts for SPX, ±5 for others
            b_range = 150.0 if ticker_sym == "SPX" else 10.0
            
            for _, row in group.iterrows():
                strike = row["strike"]
                if not (spot - b_range <= strike <= spot + b_range):
                    continue
                
                data = {
                    "price": row["mid"],
                    "delta": row["delta"],
                    "iv": row["iv"],
                    "theta": row["theta"],
                    "gamma": row["gamma"]
                }
                if row["right"] == "CALL":
                    calls[strike] = data
                else:
                    puts[strike] = data
            
            # Get ticker-specific signal for this minute.  The previous cache
            # keyed this only by time, so SPX/QQQ/SPY could inherit another
            # ticker's reversal signal when timestamps overlapped.
            sig = daily_signals.get(
                (str(ticker_sym).upper(), ts_str),
                daily_signals.get(ts_str, {"dir": "HOLD", "conf": 0.5}),
            )
            
            minute_buckets[ts_str] = {
                "spot": spot, 
                "calls": calls, 
                "puts": puts,
                "sig_dir": sig["dir"],
                "sig_conf": sig["conf"]
            }

        # Day-wide structures
        if "episodes" not in partial_cache:
            partial_cache = {
                "timestamps": all_timestamp_strs,
                "minute_data": {ticker_sym: minute_buckets},
                "episodes": {}
            }
        else:
            # Shared timestamps, but per-ticker market data
            partial_cache["minute_data"][ticker_sym] = minute_buckets

        for _, ep_row in ticker_episodes.iterrows():
            entry_time_str = str(ep_row["time"])
            cache_key = f"{ticker_sym}_{date_str}_{entry_time_str}"
            
            if entry_time_str not in all_timestamp_strs:
                skipped += 1
                continue

            # Store only entry-minute data and metadata
            # 'minutes' will be reconstructed by ChunkedOptionsCache
            entry_data = minute_buckets.get(entry_time_str, {})
            
            partial_cache["episodes"][cache_key] = {
                "ticker": ticker_sym,
                "date": date_str,
                "time": entry_time_str,
                "spot": ep_row.get("spot_price", 0),
                "day_atr": day_atr,
                "calls": entry_data.get("calls", {}),
                "puts": entry_data.get("puts", {})
            }
            processed += 1

    if partial_cache and processed > 0:
        out_file = Path(output_dir) / f"{date_str}.pkl"
        with open(out_file, "wb") as f:
            pickle.dump(partial_cache, f, protocol=pickle.HIGHEST_PROTOCOL)

    return processed, skipped


def preprocess_options_for_rl(episode_index, options_dir, output_dir, max_forward_minutes=180, num_workers=24, **kwargs):
    import multiprocessing
    ctx = multiprocessing.get_context('spawn')
    unique_dates = sorted(episode_index["date"].unique())
    os.makedirs(output_dir, exist_ok=True)

    work_items = []
    for date_str in unique_dates:
        mask = episode_index["date"].astype(str) == str(date_str)
        
        # Prepare daily signals dict for fast lookup
        # We use the full training_df (if provided) to get signals for every minute
        from .config import RL_CONFIG
        daily_signals = {}
        if "training_df" in kwargs:
            df_full = kwargs["training_df"]
            df_date = df_full[df_full["date"].astype(str) == str(date_str)]
            for _, row in df_date.iterrows():
                ticker_key = str(row.get("ticker", "")).upper()
                time_key = str(row["time"])
                daily_signals[(ticker_key, time_key)] = {
                    "dir": row.get("mlp_direction", "HOLD"),
                    "conf": float(row.get("mlp_confidence", 0.5))
                }
        
        work_items.append((date_str, episode_index[mask].copy(), options_dir, max_forward_minutes, output_dir, daily_signals))

    total_processed, total_skipped = 0, 0
    total_dates = len(unique_dates)
    t_start = time.time()

    with ctx.Pool(processes=num_workers) as pool:
        for i, (proc, skip) in enumerate(pool.imap_unordered(_process_single_date, work_items)):
            total_processed += proc
            total_skipped += skip
            done = i + 1
            pct = done / total_dates * 100
            elapsed = time.time() - t_start
            eta = (elapsed / done) * (total_dates - done) if done > 0 else 0
            eta_str = f"{int(eta//60)}m {int(eta%60)}s" if eta > 60 else f"{int(eta)}s"
            
            bar = "=" * int(25 * done / total_dates) + "." * (25 - int(25 * done / total_dates))
            print(f"\r  [{bar}] {pct:5.1f}% | {done}/{total_dates} dates | eps: {total_processed:,} | ETA: {eta_str}   ", end="", flush=True)

    print(f"\n[RL] Options cache built in: {output_dir}")
    return total_processed, total_skipped


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build RL options cache")
    parser.add_argument("--training-data", type=str, required=True)
    parser.add_argument("--options-dir", type=str, default="D:/ThetaData/data_options")
    parser.add_argument("--output", type=str, default="../rl_data/rl_options_cache_chunks")
    parser.add_argument("--mlp-model", type=str, default=None)
    parser.add_argument("--mlp-normalizer", type=str, default=None)
    parser.add_argument("--num-workers", type=int, default=32)
    parser.add_argument("--strict-wf", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=None)
    parser.add_argument("--min-entry-minute", type=int, default=580)
    parser.add_argument("--min-short-entry-minute", type=int, default=None)
    parser.add_argument("--min-short-price-vs-ib-high", type=float, default=None)
    args = parser.parse_args()

    print("=" * 70)
    print("RL DATA PREPROCESSING — OPTIONS CACHE BUILDER (CHUNKED)")
    print("=" * 70)

    training_df = pd.read_parquet(args.training_data)
    mlp_model, mlp_normalizer = None, None
    ticker_models = {}
    ticker_normalizers = {}
    is_ticker_specific = False

    if args.mlp_model and args.mlp_normalizer:
        if args.strict_wf and args.mlp_model.endswith('.joblib') and not args.mlp_model.endswith('_history.joblib'):
            args.mlp_model = args.mlp_model.replace('.joblib', '_history.joblib')
            
        from hybrid_model import load_ensemble_model
        from pathlib import Path
        
        model_path = str(Path(args.mlp_model).resolve())
        normalizer_path = str(Path(args.mlp_normalizer).resolve())

        for ticker in ["SPX", "QQQ", "SPY"]:
            if "_history.joblib" in model_path:
                t_model_path = model_path.replace("_history.joblib", f"_{ticker}_history.joblib")
            else:
                t_model_path = model_path.replace(".joblib", f"_{ticker}.joblib")
            t_norm_path = normalizer_path.replace(".npz", f"_{ticker}.npz")

            if os.path.exists(t_model_path) and os.path.exists(t_norm_path):
                print(f"  [i] Ticker-specific model found for {ticker} in RL Prep")
                try:
                    t_model, t_normalizer = load_ensemble_model(t_model_path, t_norm_path, model_size="small")
                    ticker_models[ticker] = t_model
                    ticker_normalizers[ticker] = t_normalizer
                    is_ticker_specific = True
                except Exception as e:
                    print(f"  [WARNING] Failed to load ticker-specific model for {ticker}: {e}")

        if is_ticker_specific:
            print(f"  [OK] Loaded ticker-specific models for: {list(ticker_models.keys())}")
            any_model = next(iter(ticker_models.values()))
            mlp_model = any_model
            mlp_normalizer = next(iter(ticker_normalizers.values()))
        else:
            try:
                mlp_model, mlp_normalizer = load_ensemble_model(model_path, normalizer_path, model_size="small")
                print(f"  [OK] Ensemble model loaded")
            except Exception as e:
                print(f"  [ERROR] Error loading model: {e}")

    episode_index, training_df_with_signals = generate_episode_index(
        training_df,
        mlp_model,
        mlp_normalizer,
        min_confidence=args.min_confidence,
        strict_wf=args.strict_wf,
        min_entry_minute=args.min_entry_minute,
        min_short_entry_minute=args.min_short_entry_minute,
        min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
        ticker_models=ticker_models,
        ticker_normalizers=ticker_normalizers,
        is_ticker_specific=is_ticker_specific,
    )
    
    output_parent = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_parent, exist_ok=True)
    episode_index.to_parquet(os.path.join(output_parent, "episode_index.parquet"), index=False)

    preprocess_options_for_rl(episode_index, args.options_dir, args.output, num_workers=args.num_workers, training_df=training_df_with_signals)
    print("\n[OK] Preprocessing complete!")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    main()
