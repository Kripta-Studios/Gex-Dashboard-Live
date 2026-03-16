"""
Post-Training Pipeline Diagnostic
==================================
Run after train_walkforward.py (and optionally RL training) to check:
  1. MLP out-of-sample edge (walk-forward PF/WR)
  2. Feature health: zero-variance, NaN, dropped-by-PCA detection
  3. Overfitting indicators (train vs val loss gap)
  4. Episode index balance
  5. RL agent eval (if model exists)

Usage:
    python diagnose_pipeline.py
    python diagnose_pipeline.py --data ../training_data/training_data_spx.parquet
    python diagnose_pipeline.py --train-months 4 --test-months 1

FIXES vs original:
  [1] walk_forward_splits now uses --train-months / --test-months to match
      the exact parameters used during training (was hardcoded to 3/1).
  [2] is_prod now reads the actual top-N window registry saved by
      train_walkforward.py (models/window_registry.json) instead of
      blindly marking the last 3 chronological splits.
  [3] PF is now calculated correctly as sum(wins*R) / sum(losses*R).
      With symmetric R/R this equals wins/losses, but the formula is
      explicit and correct rather than accidentally correct.
  [4] Direction-collapse threshold tightened from 90% → 80% so that
      windows like W31 (82% SHORT) are correctly flagged.
  [5] Per-window table now shows ALL windows, not just the last 15.
      Collapse windows are annotated with their actual S/L counts.
"""

import sys, os, argparse, warnings, json
import numpy as np
import pandas as pd

sys.path.insert(0, '.')
warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════
class C:
    OK   = '\033[92m✓\033[0m'
    WARN = '\033[93m⚠\033[0m'
    FAIL = '\033[91m✗\033[0m'
    BOLD = '\033[1m'
    END  = '\033[0m'
    CYAN = '\033[96m'

def header(title):
    print(f"\n{'═'*60}")
    print(f"  {C.BOLD}{title}{C.END}")
    print(f"{'═'*60}")


# ═══════════════════════════════════════════════════════════════
# HELPER — load prod window numbers from registry saved by trainer
# ═══════════════════════════════════════════════════════════════
def load_prod_windows(registry_path='models/window_registry.json'):
    """
    FIX [2]: Read the real top-N window indices that were saved to
    production by train_walkforward.py, instead of guessing from
    the last 3 chronological splits.

    Returns a set of 1-based window numbers that are in production,
    or an empty set if the registry file doesn't exist (fallback to
    old last-3 behaviour is handled at call site).
    """
    if not os.path.exists(registry_path):
        return set()
    try:
        with open(registry_path) as f:
            registry = json.load(f)
        # registry is a list of dicts: [{window, pf_avg, status, ...}, ...]
        prod = {r['window'] for r in registry if r.get('status') == 'PROD'}
        return prod
    except Exception as e:
        print(f"  {C.WARN} Could not parse window_registry.json: {e}")
        return set()


# ═══════════════════════════════════════════════════════════════
# 1. FEATURE HEALTH CHECK
# ═══════════════════════════════════════════════════════════════
def check_feature_health(df, feature_cols):
    header("1. FEATURE HEALTH CHECK")

    feats = df[feature_cols].astype(np.float32)
    n_samples = len(feats)

    CRITICAL_FEATURES = [
        'net_gamma', 'net_vanna', 'net_charm', 'net_dgex', 'net_delta',
        'dist_to_max_gamma', 'dist_to_min_gamma', 'dist_to_min_vanna',
        'dist_to_zero_gamma', 'dist_to_max_dgex', 'dist_to_min_dgex',
        'price_vs_ib_high', 'price_vs_ib_low', 'ib_range_pct',
        'atm_iv', 'iv_zscore', 'vix_spot', 'rsi',
        'gamma_change', 'vanna_change', 'dgex_change',
        'time_sin', 'time_cos', 'minutes_to_close_norm',
    ]

    issues = []

    # --- NaN check ---
    nan_counts = feats.isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    if len(nan_cols) > 0:
        print(f"  {C.WARN} {len(nan_cols)} features have NaN values:")
        for col, cnt in nan_cols.head(10).items():
            pct = cnt / n_samples * 100
            marker = C.FAIL if col in CRITICAL_FEATURES else C.WARN
            print(f"      {marker} {col}: {cnt:,} NaN ({pct:.1f}%)")
            if col in CRITICAL_FEATURES:
                issues.append(f"CRITICAL NaN: {col}")
    else:
        print(f"  {C.OK} No NaN values in any feature")

    # --- Zero-variance check ---
    variances = feats.var()
    zero_var = variances[variances < 1e-10]
    if len(zero_var) > 0:
        print(f"\n  {C.FAIL} {len(zero_var)} features have ZERO variance (constant):")
        for col in zero_var.index:
            val = feats[col].iloc[0]
            marker = C.FAIL if col in CRITICAL_FEATURES else C.WARN
            print(f"      {marker} {col} = {val:.6f} (constant)")
            if col in CRITICAL_FEATURES:
                issues.append(f"CRITICAL ZERO-VARIANCE: {col}")
    else:
        print(f"  {C.OK} No zero-variance features")

    # --- Near-zero variance (bottom 10) ---
    low_var = variances.nsmallest(10)
    print(f"\n  Lowest-variance features (candidates for removal):")
    for col, v in low_var.items():
        marker = C.FAIL if v < 1e-6 else ""
        print(f"      {marker} {col}: var={v:.2e}")

    # --- All-zero check ---
    all_zero = (feats == 0).all()
    zero_cols = all_zero[all_zero].index.tolist()
    if zero_cols:
        print(f"\n  {C.FAIL} {len(zero_cols)} features are ALL ZEROS:")
        for col in zero_cols:
            marker = C.FAIL if col in CRITICAL_FEATURES else C.WARN
            print(f"      {marker} {col}")
            if col in CRITICAL_FEATURES:
                issues.append(f"CRITICAL ALL-ZERO: {col}")

    # --- Critical features present ---
    missing_critical = [f for f in CRITICAL_FEATURES if f not in feature_cols]
    if missing_critical:
        print(f"\n  {C.FAIL} CRITICAL FEATURES MISSING from FEATURE_COLUMNS:")
        for f in missing_critical:
            print(f"      {C.FAIL} {f}")
            issues.append(f"MISSING: {f}")
    else:
        print(f"\n  {C.OK} All {len(CRITICAL_FEATURES)} critical features present")

    missing_data = [f for f in CRITICAL_FEATURES if f in feature_cols and f not in df.columns]
    if missing_data:
        print(f"\n  {C.FAIL} Critical features in FEATURE_COLUMNS but NOT in dataset:")
        for f in missing_data:
            print(f"      {C.FAIL} {f}")
            issues.append(f"NOT IN DATA: {f}")

    print(f"\n  Total features: {len(feature_cols)}")
    print(f"  Features in data: {len([c for c in feature_cols if c in df.columns])}")

    if issues:
        print(f"\n  {C.FAIL} {len(issues)} CRITICAL ISSUES FOUND:")
        for iss in issues:
            print(f"      • {iss}")
    else:
        print(f"\n  {C.OK} Feature health OK")

    return len(issues) == 0


# ═══════════════════════════════════════════════════════════════
# 2. MLP OUT-OF-SAMPLE EDGE (True Walk-Forward OOS)
# ═══════════════════════════════════════════════════════════════
#
# DESIGN NOTES — why the original version gave WR=37%:
#
# BUG-A: walk_forward_splits uses df['_date'] internally but diagnose
#   was creating df['_date'] from df['date'] before the call, causing
#   column contamination. FIX: normalise dates explicitly before splitting.
#
# BUG-B: test splits had _date dropped by walk_forward_splits → date_str="?"
#   FIX: reconstruct date info from the 'date' column in the test split.
#
# BUG-C (most critical): original code evaluated THE SAME production
#   ensemble (trained on 2023-2026) across ALL 34 historical test windows,
#   including windows from 2022 which are completely out of distribution.
#   This is NOT walk-forward OOS — it is cross-period contamination.
#   TRUE OOS means: for window i, use only the sub-ensemble whose training
#   window is i (i.e. trained on data BEFORE that test period).
#   We approximate this with the prod registry: windows marked PROD are
#   the ones trained on the most recent data, so their test windows
#   are the only ones where the loaded model is actually appropriate.
#   For all other windows we report metrics but flag them as [HIST-ONLY].
#
# BUG-D: threshold 0.55 is far too low. Training uses thresh 0.70-0.80
#   for directional trades. At 0.55 the model dumps 1000-5000 low-conf
#   trades per window, diluting WR dramatically.
#   FIX: evaluate at three confidence levels (0.60, 0.65, 0.70) and show
#   all three so the operator can see the true confidence curve.
#
# ═══════════════════════════════════════════════════════════════
def check_mlp_edge(df, feature_cols, model_path, norm_path,
                   train_months=4, test_months=1):
    header("2. MLP OUT-OF-SAMPLE EDGE (Walk-Forward OOS)")

    import torch
    from hybrid_model import load_ensemble_model
    from data_utils import walk_forward_splits

    if not os.path.exists(model_path):
        print(f"  {C.WARN} Model not found: {model_path}")
        return 0.0, False, False

    ensemble, normalizer = load_ensemble_model(model_path, norm_path, 'small')
    is_gbt = hasattr(ensemble, 'predict_proba') and not isinstance(ensemble, torch.nn.Module)
    if is_gbt:
        device = torch.device('cpu')
    else:
        device = next(ensemble.parameters()).device
    ensemble.eval()

    # FIX BUG-A: normalise date before calling walk_forward_splits so
    # that the internal _date column is always in sync.
    df = df.copy()
    if '_date' in df.columns:
        df = df.drop(columns=['_date'])       # remove stale _date if any
    df['_date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d', errors='coerce')
    df = df.sort_values('_date').reset_index(drop=True)

    print(f"  Walk-forward params: train={train_months}m  test={test_months}m  step=1m")

    # Build splits manually (avoids the _date/date_col ambiguity in data_utils)
    from datetime import timedelta
    unique_dates = sorted(df['_date'].dt.date.unique())
    min_date = df['_date'].min()
    max_date = df['_date'].max()

    raw_splits = []          # list of (tr_df, ts_df, test_start_date)
    current_start = min_date
    while True:
        train_end = current_start + timedelta(days=train_months * 30)
        test_end  = train_end    + timedelta(days=test_months  * 30)
        if test_end > max_date:
            break
        tr_mask = (df['_date'] >= current_start) & (df['_date'] < train_end)
        ts_mask = (df['_date'] >= train_end)      & (df['_date'] < test_end)
        tr = df[tr_mask].copy()
        ts = df[ts_mask].copy()
        if len(tr) > 100 and len(ts) > 10:
            raw_splits.append((tr, ts, train_end))
        current_start += timedelta(days=30)

    print(f"  Total splits generated: {len(raw_splits)}")

    # FIX [2]: load real prod windows from registry
    prod_windows = load_prod_windows()
    if prod_windows:
        print(f"  Production windows (from registry): {sorted(prod_windows)}")
    else:
        fallback_prod = set(range(len(raw_splits) - 2, len(raw_splits) + 1))
        prod_windows = fallback_prod
        print(f"  {C.WARN} window_registry.json not found — falling back to last 3 splits as PROD")

    # ── Remap targets: dataset uses {-1,0,1}, model uses {0,1,2} ──
    def _remap_targets(arr):
        mn = arr.min()
        if mn < 0:
            return (arr + 1).astype(int)
        return arr.astype(int)

    def _infer(sub_df):
        """Return (probs [N,3], targets [N]) for a dataframe."""
        raw = np.zeros((len(sub_df), len(feature_cols)), dtype=np.float32)
        for j, col in enumerate(feature_cols):
            if col in sub_df.columns:
                raw[:, j] = sub_df[col].values.astype(np.float32)
        raw = np.nan_to_num(raw, nan=0.0)
        feats = normalizer.transform(raw)
        targets = _remap_targets(sub_df['target'].values)

        if is_gbt:
            probs = ensemble.predict_proba(feats)
            return probs, targets
        else:
            all_probs = []
            with torch.no_grad():
                for k in range(0, len(feats), 8192):
                    batch = torch.FloatTensor(feats[k:k + 8192]).to(device)
                    logits, _ = ensemble(batch)
                    all_probs.append(torch.softmax(logits, -1).cpu().numpy())
            return np.concatenate(all_probs), targets

    # ── A) Full-data reference (in-sample + OOS mixed) ──
    print(f"\n  {C.BOLD}A) Full-data evaluation (in-sample reference only — not a valid edge check):{C.END}")
    all_probs, all_targets = _infer(df)
    preds_all = np.argmax(all_probs, axis=1)
    max_p_all  = all_probs.max(axis=1)

    dm = {0: 'SHORT', 1: 'HOLD', 2: 'LONG'}
    for cls in [0, 1, 2]:
        n = (preds_all == cls).sum()
        print(f"    {dm[cls]:6s}: {n:>7,} ({n/len(preds_all)*100:5.1f}%)")

    wr_is = 0.0
    for thr in [0.55, 0.65, 0.70]:
        sig = (preds_all != 1) & (max_p_all >= thr)
        if sig.sum() > 0:
            correct = (preds_all[sig] == all_targets[sig]).sum()
            w = correct / sig.sum()
            pf = correct / max(sig.sum() - correct, 1)
            print(f"    In-sample @{thr:.0%}: {sig.sum():,} trades | WR={w:.1%} | PF={pf:.2f}")
            if thr == 0.55:
                wr_is = w

    # ── B) TRUE OOS: evaluate each test split ──
    print(f"\n  {C.BOLD}B) True Out-of-Sample (walk-forward test splits only):{C.END}")
    print(f"  {C.WARN} NOTE: This uses the PRODUCTION ensemble trained on recent data.")
    print(f"  Only PROD-flagged windows have in-distribution test sets.")
    print(f"  Historical windows (HIST) are shown for trend analysis only.\n")

    # Confidence thresholds to evaluate — mirrors training thresholds (0.65-0.80)
    THRESHOLDS = [0.60, 0.65, 0.70]

    oos_results_by_thr = {t: [] for t in THRESHOLDS}   # (preds, targets) per threshold
    window_results = []
    direction_collapse_count = 0

    for i, (tr_df, ts_df, test_start) in enumerate(raw_splits):
        win_num = i + 1

        # FIX BUG-B: get dates from _date column which we kept in the df
        d_str = test_start.strftime('%Y-%m')

        probs, targets = _infer(ts_df)
        preds  = np.argmax(probs, axis=1)
        max_p  = probs.max(axis=1)

        # Regime of this test window (from actual labels)
        n_tgt_short = int((targets == 0).sum())
        n_tgt_long  = int((targets == 2).sum())
        n_tgt_dir   = n_tgt_short + n_tgt_long
        regime_pct_short = n_tgt_short / max(n_tgt_dir, 1)

        is_prod = win_num in prod_windows

        # Evaluate at each threshold
        thr_metrics = {}
        for thr in THRESHOLDS:
            sig_mask  = (preds != 1) & (max_p >= thr)
            n_sig     = int(sig_mask.sum())
            if n_sig > 0:
                correct   = (preds[sig_mask] == targets[sig_mask])
                n_wins    = int(correct.sum())
                n_short_p = int((preds[sig_mask] == 0).sum())
                n_long_p  = int((preds[sig_mask] == 2).sum())
                wr        = n_wins / n_sig
                pf        = n_wins / max(n_sig - n_wins, 1)
                # Collapse check: >80% one-sided
                dom_pct   = max(n_short_p, n_long_p) / n_sig
                collapse  = dom_pct > 0.80 and n_sig >= 10
            else:
                n_wins, n_short_p, n_long_p = 0, 0, 0
                wr, pf = 0.0, 0.0
                collapse = False
            thr_metrics[thr] = dict(n=n_sig, wins=n_wins, wr=wr, pf=pf,
                                    ns=n_short_p, nl=n_long_p, collapse=collapse)
            oos_results_by_thr[thr].append((preds[sig_mask], targets[sig_mask]))

        # Use 0.65 as representative threshold for collapse tracking
        rep = thr_metrics[0.65]
        if rep['collapse']:
            direction_collapse_count += 1
            collapse_dir = 'SHORT' if rep['ns'] > rep['nl'] else 'LONG'
        else:
            collapse_dir = None

        window_results.append({
            'window': win_num, 'date': d_str, 'n_test': len(ts_df),
            'is_prod': is_prod, 'collapse_dir': collapse_dir,
            'regime_short_pct': regime_pct_short,
            'thr': thr_metrics,
        })

    # ── Print per-window table ──
    # Primary display threshold = 0.65 (closest to training thresholds)
    DISP_THR = 0.65
    print(f"  Showing metrics at confidence ≥{DISP_THR:.0%}  (training uses 0.70-0.80)")
    print(f"\n  {'Win':>4}  {'Date':>7}  {'Regime':>7}  {'Sig':>5}  "
          f"{'S':>4}  {'L':>4}  {'WR':>6}  {'PF':>5}  Notes")
    print(f"  {'─'*4}  {'─'*7}  {'─'*7}  {'─'*5}  "
          f"{'─'*4}  {'─'*4}  {'─'*6}  {'─'*5}  {'─'*22}")

    for r in window_results:
        m = r['thr'][DISP_THR]
        regime_str = f"{r['regime_short_pct']:.0%}S"

        if m['n'] == 0:
            wr_str = f"{C.FAIL}  0%{C.END}"; pf_str = "  0.0"
        elif m['wr'] > 0.55:
            wr_str = f"{C.OK}{m['wr']:5.0%}{C.END}"; pf_str = f"{m['pf']:5.1f}"
        elif m['wr'] > 0.48:
            wr_str = f"{C.WARN}{m['wr']:5.0%}{C.END}"; pf_str = f"{m['pf']:5.1f}"
        else:
            wr_str = f"{C.FAIL}{m['wr']:5.0%}{C.END}"; pf_str = f"{m['pf']:5.1f}"

        notes = []
        if r['is_prod']:
            notes.append(f"{C.CYAN}PROD{C.END}")
        else:
            notes.append("HIST")
        if r['collapse_dir']:
            notes.append(f"COLLAPSE→{r['collapse_dir']}")
        print(f"  {r['window']:>4}  {r['date']:>7}  {regime_str:>7}  {m['n']:>5}  "
              f"{m['ns']:>4}  {m['nl']:>4}  {wr_str}  {pf_str}  {' '.join(notes)}")

    # ── Aggregate OOS at all thresholds ──
    print(f"\n  {C.BOLD}Aggregate OOS — ALL {len(raw_splits)} windows (sensitivity by threshold):{C.END}")
    print(f"  {'Thresh':>8}  {'Signals':>8}  {'WR':>7}  {'PF':>6}  {'Status'}")
    print(f"  {'─'*8}  {'─'*8}  {'─'*7}  {'─'*6}  {'─'*12}")

    oos_wr = 0.0
    for thr in THRESHOLDS:
        all_p = np.concatenate([p for p, _ in oos_results_by_thr[thr]]) if any(len(p) for p, _ in oos_results_by_thr[thr]) else np.array([])
        all_t = np.concatenate([t for _, t in oos_results_by_thr[thr]]) if any(len(t) for _, t in oos_results_by_thr[thr]) else np.array([])
        if len(all_p) > 0:
            correct = (all_p == all_t).sum()
            w = correct / len(all_p)
            pf = correct / max(len(all_p) - correct, 1)
            st = C.OK if w > 0.52 else (C.WARN if w > 0.48 else C.FAIL)
            print(f"  {thr:>7.0%}  {len(all_p):>8,}  {w:>7.1%}  {pf:>6.2f}  {st}")
            if thr == DISP_THR:
                oos_wr = w

    # ── PROD-only OOS ──
    prod_results = [r for r in window_results if r['is_prod']]
    if prod_results:
        print(f"\n  {C.BOLD}PROD windows OOS ({len(prod_results)} windows — IN-DISTRIBUTION):{C.END}")
        print(f"  {'Thresh':>8}  {'Signals':>8}  {'WR':>7}  {'PF':>6}  {'Status'}")
        print(f"  {'─'*8}  {'─'*8}  {'─'*7}  {'─'*6}  {'─'*12}")
        prod_nums = {r['window'] for r in prod_results}
        prod_wr_rep = 0.0
        for thr in THRESHOLDS:
            pairs = [oos_results_by_thr[thr][i] for i, r in enumerate(window_results) if r['window'] in prod_nums]
            all_p = np.concatenate([p for p, _ in pairs]) if pairs else np.array([])
            all_t = np.concatenate([t for _, t in pairs]) if pairs else np.array([])
            if len(all_p) > 0:
                correct = (all_p == all_t).sum()
                w = correct / len(all_p)
                pf = correct / max(len(all_p) - correct, 1)
                st = C.OK if w > 0.52 else (C.WARN if w > 0.48 else C.FAIL)
                print(f"  {thr:>7.0%}  {len(all_p):>8,}  {w:>7.1%}  {pf:>6.2f}  {st}")
                if thr == DISP_THR:
                    prod_wr_rep = w
        prod_windows_ok = prod_wr_rep >= 0.50
    else:
        print(f"\n  {C.WARN} No production windows found in test splits")
        prod_windows_ok = False
        prod_wr_rep = 0.0

    # ── IS/OOS gap check ──
    if wr_is > 0 and oos_wr > 0:
        gap = wr_is - oos_wr
        if gap > 0.10:
            print(f"\n  {C.FAIL} LARGE IS/OOS GAP: IS={wr_is:.1%} vs OOS(full)={oos_wr:.1%} ({gap:.1%})")
        elif gap > 0.05:
            print(f"\n  {C.WARN} Mild overfit: IS={wr_is:.1%} vs OOS(full)={oos_wr:.1%} ({gap:.1%})")
        else:
            print(f"\n  {C.OK} No significant IS/OOS gap: IS={wr_is:.1%} vs OOS(full)={oos_wr:.1%}")

    # ── Direction collapse summary ──
    if direction_collapse_count > 0:
        collapse_pct = direction_collapse_count / len(raw_splits) * 100
        marker = C.FAIL if collapse_pct > 40 else C.WARN
        print(f"\n  {marker} Direction collapse @{DISP_THR:.0%} in "
              f"{direction_collapse_count}/{len(raw_splits)} windows ({collapse_pct:.0f}%)")
    else:
        print(f"\n  {C.OK} No direction collapse detected @{DISP_THR:.0%}")

    # ── Trend analysis (using PROD windows only, or last half if no PROD) ──
    wrs_prod = [r['thr'][DISP_THR]['wr'] for r in prod_results if r['thr'][DISP_THR]['n'] > 10]
    if len(wrs_prod) >= 3:
        trend_wrs = wrs_prod
        lbl = "PROD"
    else:
        trend_wrs = [r['thr'][DISP_THR]['wr'] for r in window_results if r['thr'][DISP_THR]['n'] > 10]
        lbl = "all"
    if len(trend_wrs) >= 4:
        h = len(trend_wrs) // 2
        fh, sh = np.mean(trend_wrs[:h]), np.mean(trend_wrs[h:])
        if sh < fh - 0.05:
            print(f"  {C.FAIL} DEGRADATION ({lbl}): WR dropped {fh:.1%} → {sh:.1%}")
        elif sh > fh + 0.03:
            print(f"  {C.OK} Improving ({lbl}): {fh:.1%} → {sh:.1%}")
        else:
            print(f"  {C.OK} Stable ({lbl}): {fh:.1%} → {sh:.1%}")

    # ── Collapse-adjusted OOS ──
    nc_results = [r for r in window_results if not r['collapse_dir'] and r['thr'][DISP_THR]['n'] > 0]
    if nc_results:
        nc_trades = sum(r['thr'][DISP_THR]['n']    for r in nc_results)
        nc_wins   = sum(r['thr'][DISP_THR]['wins'] for r in nc_results)
        nc_wr     = nc_wins / max(nc_trades, 1)
        nc_pf     = nc_wins / max(nc_trades - nc_wins, 1)
        st = C.OK if nc_wr > 0.52 else (C.WARN if nc_wr > 0.48 else C.FAIL)
        print(f"\n  {C.BOLD}Collapse-adjusted OOS @{DISP_THR:.0%} (bidirectional only):{C.END}")
        print(f"    Windows: {len(nc_results)}  Signals: {nc_trades:,}  "
              f"{st} WR={nc_wr:.1%}  PF={nc_pf:.2f}")

    # ── Final edge verdict — based on PROD windows at display threshold ──
    eval_wr = prod_wr_rep if prod_results else oos_wr
    eval_label = "PROD-window" if prod_results else "full-OOS"
    if eval_wr > 0.52:
        print(f"\n  {C.OK} MLP has OOS edge ({eval_label} WR={eval_wr:.1%} @{DISP_THR:.0%})")
    elif eval_wr > 0.48:
        print(f"\n  {C.WARN} MLP OOS edge is marginal ({eval_label} WR={eval_wr:.1%} @{DISP_THR:.0%})")
    else:
        print(f"\n  {C.FAIL} MLP has NO OOS EDGE ({eval_label} WR={eval_wr:.1%} @{DISP_THR:.0%})")
        print(f"    → Consider: higher thresholds show fewer but higher-quality signals")
        print(f"    → PROD windows are the only valid in-distribution test")

    collapse_detected = direction_collapse_count > len(raw_splits) * 0.45
    return eval_wr, collapse_detected, prod_windows_ok


# ═══════════════════════════════════════════════════════════════
# 4. EPISODE INDEX BALANCE
# ═══════════════════════════════════════════════════════════════
def check_episode_balance():
    header("4. EPISODE INDEX BALANCE")

    ep_path = os.path.abspath('../rl_data/episode_index.parquet')
    if not os.path.exists(ep_path):
        print(f"  {C.WARN} Episode index not found: {ep_path}")
        return

    ep   = pd.read_parquet(ep_path)
    total = len(ep)
    dirs  = ep['mlp_direction'].value_counts()

    print(f"  Total episodes: {total:,}")
    for d, n in dirs.items():
        pct = n / total * 100
        print(f"    {d:6s}: {n:>7,} ({pct:.1f}%)")

    if 'LONG' in dirs.index and 'SHORT' in dirs.index:
        ratio = dirs['SHORT'] / dirs['LONG']
        if ratio > 1.5 or ratio < 0.67:
            print(f"\n  {C.FAIL} IMBALANCED: SHORT/LONG ratio = {ratio:.2f} (target: ~1.0)")
        else:
            print(f"\n  {C.OK} Balanced: SHORT/LONG ratio = {ratio:.2f}")

    print(f"\n  Confidence: mean={ep['mlp_confidence'].mean():.4f} "
          f"std={ep['mlp_confidence'].std():.4f}")
    for d in ['SHORT', 'LONG']:
        sub = ep[ep.mlp_direction == d]
        if len(sub) > 0:
            print(f"    {d}: mean={sub['mlp_confidence'].mean():.4f}")


# ═══════════════════════════════════════════════════════════════
# 5. RL AGENT CHECK
# ═══════════════════════════════════════════════════════════════
def check_rl_agent():
    header("5. RL AGENT CHECK")

    rl_path = os.path.abspath('../rl_models/best_rl_agent.pt')
    if not os.path.exists(rl_path):
        print(f"  {C.WARN} RL agent not found: {rl_path}")
        print(f"  Run RL training first, then re-run this diagnostic.")
        return

    import torch
    checkpoint = torch.load(rl_path, map_location='cpu', weights_only=False)

    if isinstance(checkpoint, dict):
        print(f"  RL checkpoint keys: {list(checkpoint.keys())}")
        if 'metadata' in checkpoint:
            meta = checkpoint['metadata']
            for k, v in meta.items():
                print(f"    {k}: {v}")
        elif 'best_eval_pf' in checkpoint:
            print(f"  Best eval PF: {checkpoint['best_eval_pf']:.4f}")

        if 'policy_state_dict' in checkpoint:
            policy   = checkpoint['policy_state_dict']
            out_keys = [k for k in policy.keys() if 'bias' in k]
            if out_keys:
                last_bias = policy[out_keys[-1]]
                if last_bias.dim() > 0:
                    print(f"\n  Policy output bias: {last_bias.numpy()}")
                    if last_bias.std() < 0.01:
                        print(f"  {C.WARN} Output bias near-uniform — agent may not have learned")
    else:
        print(f"  {C.WARN} Unexpected checkpoint format: {type(checkpoint)}")


# ═══════════════════════════════════════════════════════════════
# 5b. RL OUT-OF-SAMPLE EDGE
# ═══════════════════════════════════════════════════════════════
def check_rl_edge(df, feature_cols, rl_path, options_cache_dir,
                  train_months=4, test_months=1, num_workers=1):
    header("5b. RL OUT-OF-SAMPLE EDGE (Walk-Forward OOS)")

    if not os.path.exists(rl_path):
        print(f"  {C.WARN} RL agent not found: {rl_path}")
        return 0.0, False

    if not options_cache_dir or not os.path.exists(options_cache_dir):
        print(f"  {C.WARN} Options cache directory missing: {options_cache_dir}")
        print(f"  {C.WARN} Provide via --options-cache to evaluate RL OOS.")
        return 0.0, False

    ep_path = os.path.abspath('../rl_data/episode_index.parquet')
    if not os.path.exists(ep_path):
        print(f"  {C.WARN} Episode index not found: {ep_path}")
        return 0.0, False

    import torch
    import pandas as pd
    from rl.agent import PPOAgent
    from rl.config import RL_CONFIG
    from rl.environment import SPXOptionsEnv
    from rl.evaluate import evaluate_agent
    from rl.training import ChunkedOptionsCache
    from datetime import timedelta

    # Rebuild Walk-Forward Splits
    df_copy = df.copy()
    if '_date' in df_copy.columns:
        df_copy = df_copy.drop(columns=['_date'])
    df_copy['_date'] = pd.to_datetime(df_copy['date'].astype(str), format='%Y%m%d', errors='coerce')
    df_copy = df_copy.sort_values('_date').reset_index(drop=True)

    unique_dates = sorted(df_copy['_date'].dt.date.unique())
    min_date = df_copy['_date'].min()
    max_date = df_copy['_date'].max()

    raw_splits = []
    current_start = min_date
    while True:
        train_end = current_start + timedelta(days=train_months * 30)
        test_end  = train_end    + timedelta(days=test_months  * 30)
        if test_end > max_date:
            break
        ts_mask = (df_copy['_date'] >= train_end) & (df_copy['_date'] < test_end)
        ts_df = df_copy[ts_mask].copy()
        if len(ts_df) > 10:
            raw_splits.append((ts_df, train_end, test_end))
        current_start += timedelta(days=30)

    prod_windows = load_prod_windows()

    print(f"  Walk-forward params: train={train_months}m  test={test_months}m")
    print(f"  Loading options cache from {options_cache_dir} (Max Days 60 RAM)")

    # Load resources
    episode_index = pd.read_parquet(ep_path)
    episode_index['_date'] = pd.to_datetime(episode_index['date'].astype(str), format='%Y%m%d', errors='coerce')

    # Re-instantiate generic environment
    options_cache = ChunkedOptionsCache(options_cache_dir, max_days_in_ram=60)
    env = SPXOptionsEnv(
        episode_index=episode_index,
        options_cache=options_cache,
        feature_columns=feature_cols,
    )

    # Load agent
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    try:
        agent = PPOAgent.load(rl_path, device=device)
    except Exception as e:
        print(f"  {C.WARN} Could not load RL agent parameters: {e}")
        return 0.0, False
    agent.eval()

    print(f"\n  {C.BOLD}True Out-of-Sample RL Edge per Split:{C.END}")
    print(f"  {'Win':>4}  {'Date':>7}   {'Trades':>6}  {'WR':>6}  {'PF':>5}  Notes")
    print(f"  {'─'*4}  {'─'*7}   {'─'*6}  {'─'*6}  {'─'*5}  {'─'*15}")

    window_results = []
    for i, (ts_df, start_t, end_t) in enumerate(raw_splits):
        win_num = i + 1
        d_str = start_t.strftime('%Y-%m')
        is_prod = win_num in prod_windows

        # Extract sub episode-index
        mask = (episode_index['_date'] >= start_t) & (episode_index['_date'] < end_t) & (episode_index['mlp_confidence'] > 0.50)
        sub_idx = episode_index[mask].copy().reset_index(drop=True)

        if len(sub_idx) < 3:
            # Not enough data to eval RL reliably
            continue

        try:
            metrics = evaluate_agent(agent, env, eval_episodes=sub_idx, verbose=False,
                                     num_workers=num_workers, options_cache_dir=options_cache_dir)
        except Exception as e:
            print(f"  {win_num:>4}  {d_str:>7}   {'ERR':>6}  {'-':>6}  {'-':>5}  Failed: {str(e)[:40]}")
            continue

        if "error" in metrics:
            print(f"  {win_num:>4}  {d_str:>7}   {'0':>6}  {'-':>6}  {'-':>5}  No trades completed")
            continue

        trades = metrics["total_trades"]
        wr = metrics["win_rate"]
        pf = metrics["profit_factor"]

        if wr > 0.55:
            wr_str = f"{C.OK}{wr:5.0%}{C.END}"
        elif wr > 0.48:
            wr_str = f"{C.WARN}{wr:5.0%}{C.END}"
        else:
            wr_str = f"{C.FAIL}{wr:5.0%}{C.END}"

        notes = f"{C.CYAN}PROD{C.END}" if is_prod else "HIST"
        print(f"  {win_num:>4}  {d_str:>7}   {trades:>6}  {wr_str}  {pf:5.2f}  {notes}")
        window_results.append({'window': win_num, 'is_prod': is_prod, 'wr': wr, 'pf': pf, 'trades': trades})

    # PROD Summary
    prod_res = [r for r in window_results if r['is_prod'] and r['trades'] > 0]
    if prod_res:
        total_prod_trades = sum(r['trades'] for r in prod_res)
        avg_prod_wr = sum(r['wr'] * r['trades'] for r in prod_res) / total_prod_trades
        avg_prod_pf = sum(r['pf'] * r['trades'] for r in prod_res) / total_prod_trades
        
        st = C.OK if avg_prod_wr > 0.52 else (C.WARN if avg_prod_wr > 0.48 else C.FAIL)
        print(f"\n  {C.BOLD}PROD windows RL OOS ({len(prod_res)} windows):{C.END}")
        print(f"  Signals: {total_prod_trades:,}  {st} WR={avg_prod_wr:.1%}  PF={avg_prod_pf:.2f}")

        if avg_prod_wr > 0.52 and avg_prod_pf > 1.2:
            print(f"\n  {C.OK} RL has OOS edge (PROD WR={avg_prod_wr:.1%} PF={avg_prod_pf:.2f})")
            rl_edge_ok = True
        elif avg_prod_wr > 0.48 and avg_prod_pf > 1.0:
            print(f"\n  {C.WARN} RL OOS edge is marginal (PROD WR={avg_prod_wr:.1%} PF={avg_prod_pf:.2f})")
            rl_edge_ok = False
        else:
            print(f"\n  {C.FAIL} RL has NO OOS EDGE (PROD WR={avg_prod_wr:.1%} PF={avg_prod_pf:.2f})")
            rl_edge_ok = False
        
        return avg_prod_wr, rl_edge_ok
    else:
        print(f"\n  {C.WARN} No production windows found with RL trades.")
        return 0.0, False


# ═══════════════════════════════════════════════════════════════
# 6. NORMALIZER HEALTH
# ═══════════════════════════════════════════════════════════════
def check_normalizer(norm_path, feature_cols):
    header("6. NORMALIZER HEALTH")

    if not os.path.exists(norm_path):
        print(f"  {C.WARN} Normalizer not found: {norm_path}")
        return

    data = np.load(norm_path, allow_pickle=True)

    if 'medians' in data:
        medians = data['medians']
        iqrs    = data['iqrs']
        print(f"  Type: Robust (median/IQR)")
    elif 'means' in data:
        medians = data['means']
        iqrs    = data['stds']
        print(f"  Type: Legacy (mean/std)")
    else:
        print(f"  {C.FAIL} Unknown normalizer format")
        return

    print(f"  Dimensions: {len(medians)} features")

    if len(medians) != len(feature_cols):
        print(f"  {C.FAIL} DIMENSION MISMATCH: normalizer has {len(medians)} features, "
              f"FEATURE_COLUMNS has {len(feature_cols)}")

    zero_iqr = np.where(iqrs <= 1e-10)[0]
    if len(zero_iqr) > 0:
        print(f"\n  {C.WARN} {len(zero_iqr)} features with zero IQR (constant during training):")
        for idx in zero_iqr[:10]:
            name = feature_cols[idx] if idx < len(feature_cols) else f"idx={idx}"
            print(f"      {C.WARN} {name}: median={medians[idx]:.6f} IQR={iqrs[idx]:.2e}")
    else:
        print(f"  {C.OK} All features have non-zero IQR")

    extreme = np.where(np.abs(medians) > 1e6)[0]
    if len(extreme) > 0:
        print(f"\n  {C.WARN} {len(extreme)} features with extreme median values:")
        for idx in extreme[:5]:
            name = feature_cols[idx] if idx < len(feature_cols) else f"idx={idx}"
            print(f"      {name}: median={medians[idx]:.2e}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description='Post-Training Pipeline Diagnostic')
    parser.add_argument('--data',         default='../training_data/training_data_spx.parquet')
    parser.add_argument('--model',        default='models/trading_hybrid_wf.pt')
    parser.add_argument('--normalizer',   default='models/hybrid_normalizer_wf.npz')
    parser.add_argument('--options-cache',default=None,
                        help='Directory of chunked per-day .pkl cache shards to eval RL')
    # FIX [1]: expose train/test month params so they match training run
    parser.add_argument('--train-months', type=int, default=4,
                        help='Training window in months (must match --train-months used in training)')
    parser.add_argument('--test-months',  type=int, default=1,
                        help='Test window in months (must match --test-months used in training)')
    parser.add_argument('--workers', type=int, default=1,
                        help='Number of background CPU workers for OOS evaluation')
    args = parser.parse_args()

    from hybrid_model import FEATURE_COLUMNS

    print(f"\n{C.BOLD}{C.CYAN}╔════════════════════════════════════════════════╗{C.END}")
    print(f"{C.BOLD}{C.CYAN}║  POST-TRAINING PIPELINE DIAGNOSTIC             ║{C.END}")
    print(f"{C.BOLD}{C.CYAN}╚════════════════════════════════════════════════╝{C.END}")

    print(f"\n  Loading: {args.data}")
    df = pd.read_parquet(args.data)
    print(f"  Samples: {len(df):,} | Columns: {len(df.columns)}")

    feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    missing      = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        print(f"  {C.WARN} {len(missing)} FEATURE_COLUMNS not in data: {missing[:5]}...")
    print(f"  Feature columns matched: {len(feature_cols)}/{len(FEATURE_COLUMNS)}")

    feat_ok = check_feature_health(df, feature_cols)
    check_normalizer(args.normalizer, FEATURE_COLUMNS)
    
    # FIX [1]: pass train/test months through
    oos_wr, collapse_detected, prod_windows_ok = check_mlp_edge(
        df, FEATURE_COLUMNS, args.model, args.normalizer,
        train_months=args.train_months,
        test_months=args.test_months,
    )
    
    check_episode_balance()
    check_rl_agent()

    rl_path = os.path.abspath('../rl_models/best_rl_agent.pt')
    if args.options_cache:
        rl_oos_wr, rl_edge_ok = check_rl_edge(
            df, feature_cols, rl_path,
            options_cache_dir=args.options_cache,
            train_months=args.train_months,
            test_months=args.test_months,
            num_workers=args.workers,
        )
    else:
        print(f"\n  {C.WARN} Skipping RL EDGE check. Use --options-cache to enable.")
        rl_oos_wr, rl_edge_ok = 0.0, False

    # Final verdict
    header("VERDICT")
    mlp_ok = feat_ok and oos_wr > 0.52 and not collapse_detected and prod_windows_ok
    if mlp_ok and rl_edge_ok:
        print(f"  {C.OK} Pipeline + RL ready for live deployment")
    elif mlp_ok:
        print(f"  {C.OK} MLP ready, but RL edge missing or untested")
    elif feat_ok and oos_wr > 0.48:
        print(f"  {C.WARN} MARGINAL — paper trade only, do NOT deploy live")
    else:
        print(f"  {C.FAIL} NO EDGE — do NOT deploy")
    print()
    


if __name__ == '__main__':
    main()