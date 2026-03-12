"""
diagnose_trades.py — Diagnóstico completo de por qué hay pocos trades

Ejecutar desde el directorio raíz del proyecto:
    python diagnose_trades.py --data training_data/training_data_spx_qqq.parquet
    python diagnose_trades.py --data training_data/training_data_spx_qqq_march.parquet --focus-2026
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import os

# ── Try to load GBT model if available ──────────────────────────────────
def try_load_model(model_path, norm_path):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "neural"))
        from hybrid_model import FeatureNormalizer, FEATURE_COLUMNS
        from gbt_model import load_gbt_ensemble
        model, norm = load_gbt_ensemble(model_path, norm_path)
        print(f"  [OK] Model loaded: {model_path}")
        return model, norm, FEATURE_COLUMNS
    except Exception as e:
        print(f"  [SKIP] Could not load model: {e}")
        return None, None, None


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def analyze(df: pd.DataFrame, label: str = ""):
    section(f"DATASET OVERVIEW  {label}")
    print(f"  Rows          : {len(df):,}")
    print(f"  Unique dates  : {df['date'].nunique()}")
    print(f"  Tickers       : {df['ticker'].unique().tolist()}")
    if 'time' in df.columns:
        print(f"  Times         : {df['time'].min()} → {df['time'].max()}")

    # ── 1. Label distribution ────────────────────────────────────────────
    section("1. TARGET LABEL DISTRIBUTION")
    vc = df['target'].value_counts().sort_index()
    total = len(df)
    for val, cnt in vc.items():
        name = {-1: "SHORT", 0: "HOLD", 1: "LONG"}.get(val, str(val))
        print(f"  {name:6s} ({val:+d}): {cnt:7,}  ({cnt/total*100:.1f}%)")

    directional = (df['target'] != 0).sum()
    print(f"\n  Directional total : {directional:,}  ({directional/total*100:.1f}%)")
    print(f"  → Expected trades per day (raw): {directional / df['date'].nunique():.1f}")

    # ── 2. Label distribution by year-month ─────────────────────────────
    section("2. DIRECTIONAL SIGNALS BY MONTH")
    df['_ym'] = df['date'].astype(str).str[:6]
    monthly = df.groupby('_ym').agg(
        total=('target', 'count'),
        longs=('target', lambda x: (x == 1).sum()),
        shorts=('target', lambda x: (x == -1).sum()),
        holds=('target', lambda x: (x == 0).sum()),
        n_days=('date', 'nunique'),
    )
    monthly['dir_pct'] = (monthly['longs'] + monthly['shorts']) / monthly['total'] * 100
    monthly['sig_per_day'] = (monthly['longs'] + monthly['shorts']) / monthly['n_days']
    print(f"  {'Month':>8}  {'Days':>5}  {'Longs':>6}  {'Shorts':>7}  {'Dir%':>6}  {'Sig/Day':>8}")
    print(f"  {'-'*55}")
    for ym, row in monthly.iterrows():
        flag = " ◄ LOW" if row['sig_per_day'] < 3 else ""
        print(f"  {ym:>8}  {int(row['n_days']):>5}  {int(row['longs']):>6}  "
              f"{int(row['shorts']):>7}  {row['dir_pct']:>5.1f}%  {row['sig_per_day']:>7.1f}{flag}")

    # ── 3. Time-of-day distribution of signals ───────────────────────────
    section("3. SIGNALS BY TIME OF DAY")
    dir_df = df[df['target'] != 0].copy()
    if 'time' in dir_df.columns:
        dir_df['_hour'] = dir_df['time'].str[:2].astype(int)
        by_hour = dir_df.groupby('_hour').agg(
            signals=('target', 'count'),
            longs=('target', lambda x: (x == 1).sum()),
            shorts=('target', lambda x: (x == -1).sum()),
        )
        print(f"  {'Hour':>6}  {'Signals':>8}  {'Longs':>6}  {'Shorts':>7}")
        for h, row in by_hour.iterrows():
            print(f"  {h:02d}:xx  {int(row['signals']):>8}  {int(row['longs']):>6}  {int(row['shorts']):>7}")

    # ── 4. Cooldown simulation (10 min) ──────────────────────────────────
    section("4. COOLDOWN SIMULATION (how many signals survive)")
    def simulate_cooldown(group_df, cooldown_min=10):
        """Simulate cooldown filter on directional signals, per (ticker, date)."""
        taken, blocked = 0, 0
        last_min = {}
        for _, row in group_df.sort_values('_min').iterrows():
            key = (row['ticker'], row['date'])
            lm = last_min.get(key, -9999)
            if row['_min'] - lm >= cooldown_min:
                taken += 1
                last_min[key] = row['_min']
            else:
                blocked += 1
        return taken, blocked

    if 'time' in df.columns:
        dir_df['_min'] = dir_df['time'].apply(
            lambda t: int(t[:2]) * 60 + int(t[3:5]) if isinstance(t, str) and ':' in t else 0)
        for cd in [5, 10, 15, 20]:
            t, b = simulate_cooldown(dir_df, cd)
            print(f"  Cooldown {cd:2d} min → taken: {t:5,}  blocked: {b:5,}  "
                  f"survival: {t/(t+b)*100:.1f}%  per day: {t/df['date'].nunique():.1f}")

    # ── 5. Threshold sensitivity (if probabilities available) ────────────
    section("5. THRESHOLD SENSITIVITY (raw label-based proxy)")
    # We don't have model probs here, but we can show how many HOLD rows
    # are "near" being directional using time_to_target as proxy
    if 'time_to_target' in df.columns:
        print("  [time_to_target] Distribution for HOLD rows (these were forced to 0)")
        hold_df = df[df['target'] == 0]
        near_miss = hold_df[hold_df['time_to_target'] > 0]
        print(f"  HOLD rows with time_to_target > 0 : {len(near_miss):,} "
              f"({len(near_miss)/len(hold_df)*100:.1f}% of all HOLDs)")
        print(f"  → These are rows where price DID move but proximity gate blocked labeling")

    # ── 6. Open-position lock simulation ─────────────────────────────────
    section("6. OPEN POSITION LOCK SIMULATION (avg hold 135 min)")
    if 'time' in df.columns:
        avg_hold = 135
        dir_df['_min'] = dir_df['time'].apply(
            lambda t: int(t[:2]) * 60 + int(t[3:5]) if isinstance(t, str) and ':' in t else 0)

        def simulate_full(group_df, cooldown=10, hold_min=135):
            taken, blocked_cd, blocked_pos = 0, 0, 0
            last_min = {}
            pos_end = {}
            for _, row in group_df.sort_values(['date', '_min']).iterrows():
                key = (row['ticker'], str(row['date']))
                cur = row['_min']
                # Open position check
                if pos_end.get(key, -1) > cur:
                    blocked_pos += 1
                    continue
                # Cooldown check
                lm = last_min.get(key, -9999)
                if cur - lm < cooldown:
                    blocked_cd += 1
                    continue
                taken += 1
                last_min[key] = cur
                pos_end[key] = cur + hold_min
            return taken, blocked_cd, blocked_pos

        t, bcd, bpos = simulate_full(dir_df, cooldown=10, hold_min=avg_hold)
        total_sig = len(dir_df)
        print(f"  Raw directional signals      : {total_sig:,}")
        print(f"  After cooldown (10min) + lock: {t:,}  per day: {t/df['date'].nunique():.1f}")
        print(f"  Blocked by cooldown          : {bcd:,}  ({bcd/total_sig*100:.1f}%)")
        print(f"  Blocked by open position     : {bpos:,}  ({bpos/total_sig*100:.1f}%)")
        print()

        # Now simulate with relaxed params
        print(f"  {'Cooldown':>10}  {'Hold':>6}  {'Trades':>8}  {'Per Day':>8}")
        print(f"  {'-'*40}")
        for cd in [5, 10]:
            for hold in [60, 90, 135]:
                t2, _, _ = simulate_full(dir_df, cooldown=cd, hold_min=hold)
                per_day = t2 / df['date'].nunique()
                flag = " ◄ CURRENT" if cd == 10 and hold == 135 else ""
                print(f"  {cd:>10}  {hold:>6}  {t2:>8,}  {per_day:>7.1f}{flag}")

    # ── 7. Per-ticker breakdown ───────────────────────────────────────────
    section("7. PER-TICKER SIGNAL DENSITY")
    for ticker in df['ticker'].unique():
        t_df = df[df['ticker'] == ticker]
        dir_t = (t_df['target'] != 0).sum()
        n_days = t_df['date'].nunique()
        print(f"  {ticker:6s}: {dir_t:5,} signals | {n_days} days | "
              f"{dir_t/n_days:.1f} sig/day | {dir_t/len(t_df)*100:.1f}% directional")

    # ── 8. Near-SR analysis ───────────────────────────────────────────────
    section("8. PROXIMITY GATE ANALYSIS")
    # Reconstruct near_sr from distance features
    dist_cols = [c for c in df.columns if c.startswith('dist_to_') or c.startswith('dist_fib')]
    if dist_cols:
        # A row was "near" a level if ANY distance feature is close to 0 (small bps)
        # near = abs distance < 10 bps
        near_count = (df[dist_cols].abs() < 10).any(axis=1).sum()
        print(f"  Rows within 10 bps of any tracked level: {near_count:,} ({near_count/len(df)*100:.1f}%)")
        near_count2 = (df[dist_cols].abs() < 20).any(axis=1).sum()
        print(f"  Rows within 20 bps of any tracked level: {near_count2:,} ({near_count2/len(df)*100:.1f}%)")

    print(f"\n{'='*70}")
    print("  SUMMARY: ROOT CAUSES OF LOW TRADE COUNT")
    print(f"{'='*70}")
    dir_pct = directional / total * 100
    if dir_pct < 15:
        print(f"  ❌ CRITICAL: Only {dir_pct:.1f}% of rows have directional labels")
        print(f"     → Proximity gate + failed profit target = 87%+ HOLDs")
        print(f"     → Fix: lower LEVEL_PROXIMITY_THRESHOLD further OR")
        print(f"            label ALL rows and let model learn the filter")
    if 'time' in df.columns:
        spd = directional / df['date'].nunique()
        if spd < 5:
            print(f"  ❌ CRITICAL: Only {spd:.1f} signals/day before any backtest filter")
        print(f"  → With cooldown=10 + hold=135, expected trades/day: ~{t/df['date'].nunique():.1f}")
        print(f"  → With cooldown=5  + hold=60,  expected trades/day: ~{t2/df['date'].nunique():.1f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to training parquet")
    parser.add_argument("--model", default="neural/models/trading_hybrid_wf.joblib")
    parser.add_argument("--normalizer", default="neural/models/hybrid_normalizer_wf.npz")
    parser.add_argument("--focus-2026", action="store_true", help="Show 2026 subset separately")
    args = parser.parse_args()

    print(f"\nLoading: {args.data}")
    df = pd.read_parquet(args.data)
    df['date'] = df['date'].astype(str)

    analyze(df, label=f"({Path(args.data).name})")

    if args.focus_2026:
        df_2026 = df[df['date'].str.startswith('2026')]
        if not df_2026.empty:
            analyze(df_2026, label="[2026 ONLY]")
        else:
            print("\n  [!] No 2026 data found in this file.")


if __name__ == "__main__":
    main()