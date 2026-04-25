# -*- coding: utf-8 -*-
"""
Walk-Forward Training Pipeline — LightGBM Edition

Replaces the PyTorch MLP with LightGBM for tabular data classification.
GBT achieves 72% accuracy on SHORT vs LONG OOS where the MLP got ~0%.

Structure unchanged:
  - Walk-forward splits (train_m/test_m months, step=1 month)
  - Ensemble of N models per window (different random seeds)
  - Cal_df from first 10 test days for policy health checks / collapse detection
  - Collapse detection + min-trades + PF floor for acceptance
  - Top-N windows by rank_score (PF * recency) for production
"""
import os
import sys
import argparse
import time
import json
import numpy as np
import pandas as pd
from pathlib import Path

import lightgbm as lgb

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from hybrid_model import FeatureNormalizer, FEATURE_COLUMNS
from gbt_model import GBTModel, GBTEnsemble, save_gbt_ensemble
from data_utils import walk_forward_splits, add_sample_weights
from neural.rl.config import RL_CONFIG
from neural.signal_policy import entry_thresholds, is_actionable_prediction


def set_seed(seed: int):
    import random
    random.seed(seed)
    np.random.seed(seed)


# ═══════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════
def calculate_trading_metrics(predictions, targets):
    predictions = np.asarray(predictions)
    targets = np.asarray(targets)
    metrics = {"accuracy": float((predictions == targets).mean())}
    trade_mask = (predictions != 1)
    n_trades = trade_mask.sum()
    if n_trades > 0:
        wins = int((predictions[trade_mask] == targets[trade_mask]).sum())
        losses = int(n_trades - wins)
        metrics["win_rate"] = float(wins / n_trades)
        MIN_LOSSES_FOR_PF = 5
        if losses < MIN_LOSSES_FOR_PF:
            metrics["profit_factor"] = float(wins / max(losses, MIN_LOSSES_FOR_PF))
        else:
            metrics["profit_factor"] = float(wins / losses)
        metrics["total_trades"] = int(n_trades)
    else:
        metrics.update({"win_rate": 0.0, "profit_factor": 0.0, "total_trades": 0})
    return metrics


# ═══════════════════════════════════════════════════════════════
# CLASS BALANCING
# ═══════════════════════════════════════════════════════════════
def balance_classes(y_train: np.ndarray,
                    rng: np.random.Generator,
                    hold_ratio: float = 2.0,
                    min_dir_samples: int = 30) -> np.ndarray:
    """
    Balance SHORT / LONG / HOLD independently.
    SHORT and LONG are equalized; HOLD is capped at hold_ratio * directional.
    """
    short_idx = np.where(y_train == 0)[0]
    long_idx  = np.where(y_train == 2)[0]
    hold_idx  = np.where(y_train == 1)[0]

    n_long  = len(long_idx)
    n_short = len(short_idx)

    MAX_DIR_RATIO = 1.0
    n_minority = max(min(n_long, n_short), min_dir_samples)
    n_majority_cap = int(n_minority * MAX_DIR_RATIO)

    if n_long <= n_short:
        n_long_keep  = n_long
        n_short_keep = min(n_short, n_majority_cap)
    else:
        n_short_keep = n_short
        n_long_keep  = min(n_long, n_majority_cap)

    n_long_keep  = max(n_long_keep,  min(min_dir_samples, n_long))
    n_short_keep = max(n_short_keep, min(min_dir_samples, n_short))

    long_sampled  = rng.choice(long_idx,  size=n_long_keep,  replace=False)
    short_sampled = rng.choice(short_idx, size=n_short_keep, replace=False)

    n_signals     = n_long_keep + n_short_keep
    n_hold_target = min(len(hold_idx), int(n_signals * hold_ratio))
    hold_sampled  = rng.choice(hold_idx, size=n_hold_target, replace=False)

    keep_idx = np.sort(np.concatenate([short_sampled, long_sampled, hold_sampled]))
    return keep_idx, n_long_keep, n_short_keep, n_hold_target


# ═══════════════════════════════════════════════════════════════
# DEPLOYED SIGNAL POLICY
# ═══════════════════════════════════════════════════════════════
def apply_deployed_signal_policy(
    val_probs: np.ndarray,
    base_confidence: float | None = None,
) -> np.ndarray:
    """Convert probabilities to deployed predictions {0=SHORT, 1=HOLD, 2=LONG}."""
    val_probs = np.asarray(val_probs, dtype=np.float32)
    argmax_preds = val_probs.argmax(axis=1)
    max_conf = val_probs.max(axis=1)

    preds = np.ones(len(val_probs), dtype=np.int64)  # default HOLD
    for idx, (pred, conf) in enumerate(zip(argmax_preds, max_conf)):
        if is_actionable_prediction(int(pred), float(conf), base_confidence=base_confidence):
            preds[idx] = int(pred)
    return preds


# ═══════════════════════════════════════════════════════════════
# SINGLE WINDOW TRAINING (LightGBM)
# ═══════════════════════════════════════════════════════════════
def train_single_window(train_df, val_df, verbose=True, window_idx=None, seed=42, hold_ratio=2.0):
    """
    Train a single LightGBM model on one walk-forward window.

    Returns:
        (GBTModel, FeatureNormalizer, metrics_dict)
    """
    cols = [c for c in FEATURE_COLUMNS if c in train_df.columns]

    # Capture cutoff date (last date of training)
    if '_date' in train_df.columns:
        last_date = train_df['_date'].max()
    else:
        last_date = pd.to_datetime(train_df['date'], errors='coerce').max()
    
    cutoff_date_int = int(last_date.strftime('%Y%m%d'))

    needs_remapping = False
    if 'target' in train_df.columns and train_df['target'].min() < 0:
        needs_remapping = True

    def prep(df):
        x = np.nan_to_num(df[cols].values.astype(np.float32), nan=0.0, posinf=5.0, neginf=-5.0)
        raw_target = df['target'].values
        if needs_remapping:
            y = (raw_target + 1).astype(np.int64)
        else:
            y = raw_target.astype(np.int64)
        return x, y

    # 1. Chronological ordering
    if '_date' not in train_df.columns and 'date' in train_df.columns:
        train_df = train_df.copy()
        train_df['_date'] = pd.to_datetime(train_df['date'], errors='coerce')

    if '_date' in train_df.columns:
        train_df = train_df.sort_values('_date').reset_index(drop=True)

    # 2. Split test window into CAL and HONEST.
    #    CAL = first 10 days → sanity checks, collapse detection, trade sufficiency
    #    HONEST = remaining days → used for honest_metrics and rank_score
    #    Both are evaluated with the same deployed signal policy as live/backtest.
    if '_date' not in val_df.columns and 'date' in val_df.columns:
        val_df = val_df.copy()
        val_df['_date'] = pd.to_datetime(val_df['date'], errors='coerce')

    if '_date' in val_df.columns:
        val_df = val_df.sort_values('_date').reset_index(drop=True)

    val_dates = sorted(val_df['_date'].dt.date.unique())
    n_cal_from_test = min(10, len(val_dates) // 2)
    cal_dates = set(val_dates[:n_cal_from_test])
    honest_dates = set(val_dates[n_cal_from_test:])  # held-out test days
    cal_mask = val_df['_date'].dt.date.isin(cal_dates)
    honest_mask = val_df['_date'].dt.date.isin(honest_dates)
    cal_df = val_df[cal_mask].reset_index(drop=True)
    honest_df = val_df[honest_mask].reset_index(drop=True)

    min_trades_req = 10
    n_cal = len(cal_df)
    n_cal_short = (cal_df['target'] == (-1 if needs_remapping else 0)).sum()
    n_cal_long  = (cal_df['target'] == (1 if needs_remapping else 2)).sum()
    n_cal_hold  = n_cal - n_cal_short - n_cal_long
    print(f"  [CAL_DF] first {n_cal_from_test} test days | rows={n_cal} | "
          f"Short={n_cal_short} Long={n_cal_long} Hold={n_cal_hold}")
    print(f"  [HONEST_DF] remaining {len(honest_dates)} test days | rows={len(honest_df)}")
    print(f"  [CAL] min_trades_req={min_trades_req}")

    # 3. Prep data
    X_train_raw, y_train = prep(train_df)
    X_train_raw_full = X_train_raw.copy()  # keep FULL for normalizer fit

    # 4. Balance classes
    rng = np.random.default_rng(seed=seed)
    keep_idx, n_long_k, n_short_k, n_hold_k = balance_classes(
        y_train, rng, hold_ratio=hold_ratio, min_dir_samples=30
    )

    X_train_raw = X_train_raw[keep_idx]
    y_train     = y_train[keep_idx]

    dist_train = np.bincount(y_train, minlength=3).tolist()
    print(f"      [Balance] Long={n_long_k} | Short={n_short_k} | Hold={n_hold_k} | "
          f"Ratio L:S={n_long_k/max(n_short_k,1):.2f}")
    print(f"      [Dist train] {dist_train}")

    # Min directional samples
    MIN_DIR_TRAIN = 100
    if n_long_k < MIN_DIR_TRAIN or n_short_k < MIN_DIR_TRAIN:
        print(f"      [SKIP] Insufficient directional samples: Long={n_long_k}, Short={n_short_k} < {MIN_DIR_TRAIN}")
        return None, None, {"accuracy": 0, "win_rate": 0, "profit_factor": 0, "total_trades": 0, "min_trades_req": min_trades_req}

    # 5. Normalize features
    norm = FeatureNormalizer()
    norm.fit(X_train_raw_full, cols)
    X_train = norm.transform(X_train_raw)

    # 6. Train LightGBM
    model = lgb.LGBMClassifier(
        objective='multiclass',
        n_estimators=300,
        max_depth=4,         # REDUCED from 6 to 4
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=100, # INCREASED from 50 to 100
        reg_alpha=0.2,       # INCREASED from 0.1
        reg_lambda=5.0,      # INCREASED from 1.0
        num_class=3,
        random_state=seed,
        class_weight='balanced',
        verbose=-1,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 7. Evaluate with the deployed entry policy on cal_df
    X_cal, y_cal = prep(cal_df)
    X_cal_norm = norm.transform(X_cal)
    
    # Wrap in DataFrame to avoid LightGBM feature names warning
    X_cal_df = pd.DataFrame(X_cal_norm, columns=cols)
    val_probs = model.predict_proba(X_cal_df)
    val_targets = y_cal

    print(f"  [CAL] target distribution: {np.bincount(val_targets, minlength=3)}")

    # Confidence diagnostics
    argmax_preds = val_probs.argmax(axis=1)
    max_conf = val_probs.max(axis=1)
    for cls_id, cls_name in [(0, 'SHORT'), (2, 'LONG')]:
        mask = argmax_preds == cls_id
        if mask.sum() > 0:
            conf_vals = max_conf[mask]
            print(f"      [Conf] {cls_name}: n={mask.sum()} | "
                  f"mean={conf_vals.mean():.3f} median={np.median(conf_vals):.3f} | "
                  f">=0.60: {(conf_vals >= 0.60).sum()} ({(conf_vals >= 0.60).mean():.0%}) | "
                  f">=0.65: {(conf_vals >= 0.65).sum()} ({(conf_vals >= 0.65).mean():.0%})")
        else:
            print(f"      [Conf] {cls_name}: n=0 (no predictions)")

    deployed_base_confidence = float(RL_CONFIG["min_confidence"])
    deployed_long_threshold, deployed_short_threshold = entry_thresholds(
        deployed_base_confidence
    )
    cal_preds = apply_deployed_signal_policy(
        val_probs,
        base_confidence=deployed_base_confidence,
    )

    n_final_short = int((cal_preds == 0).sum())
    n_final_long  = int((cal_preds == 2).sum())
    n_final_dir   = n_final_short + n_final_long

    print(
        f"      [Policy] live/backtest thresholds | "
        f"Long>={deployed_long_threshold:.2f} Short>={deployed_short_threshold:.2f} | "
        f"Pred Long={n_final_long} Short={n_final_short}"
    )

    # Collapse detection (on cal predictions)
    collapsed = False
    if n_final_dir > 0:
        long_ratio  = n_final_long  / n_final_dir
        short_ratio = n_final_short / n_final_dir
        is_collapsed = (long_ratio > 0.80) or (short_ratio > 0.80)
        if is_collapsed:
            direction = "LONG" if long_ratio > 0.80 else "SHORT"
            print(f"      [!!] COLLAPSE -> {direction} ({max(long_ratio, short_ratio):.0%} one-sided)")
            collapsed = True
    else:
        collapsed = True

    # ── HONEST METRICS: evaluate on HELD-OUT test days (NOT used for calibration) ──
    # This is the anti-snooping fix: rank_score is based on genuinely unseen data.
    if len(honest_df) >= 10:
        X_honest, y_honest = prep(honest_df)
        X_honest_norm = norm.transform(X_honest)
        X_honest_df_lgb = pd.DataFrame(X_honest_norm, columns=cols)
        honest_probs = model.predict_proba(X_honest_df_lgb)
        honest_preds = apply_deployed_signal_policy(
            honest_probs,
            base_confidence=deployed_base_confidence,
        )
        honest_metrics = calculate_trading_metrics(honest_preds, y_honest)
        print(f"      [HONEST OOS] PF={honest_metrics['profit_factor']:.2f} "
              f"WR={honest_metrics['win_rate']:.1%} "
              f"Trades={honest_metrics['total_trades']} "
              f"(on {len(honest_dates)} held-out test days)")
    else:
        # Fallback: not enough honest days, use cal_df metrics with warning
        honest_metrics = calculate_trading_metrics(cal_preds, val_targets)
        print(f"      [!] Only {len(honest_df)} honest days available, using cal_df metrics as fallback")

    honest_metrics['min_trades_req'] = min_trades_req
    honest_metrics['collapsed'] = collapsed

    # Wrap as GBTModel with metadata
    from gbt_model import GBTModel
    gbt_model = GBTModel(
        model,
        metadata={'cutoff_date': cutoff_date_int},
        normalizer=norm,
    )

    return gbt_model, norm, honest_metrics


# ═══════════════════════════════════════════════════════════════
# WALK-FORWARD ENGINE
# ═══════════════════════════════════════════════════════════════
def walk_forward_train(data_path, model_path, norm_path, model_size,
                       train_m, test_m, epochs, batch_size, lr, n_ensemble=3,
                       top_n_windows=10, min_window=0, hold_ratio=2.0):
    print("=" * 70 + f"\nWALK-FORWARD TRAINING (GBT ENSEMBLE x{n_ensemble})\n" + "=" * 70)

    # Load data
    if data_path.endswith('.parquet'):
        df = pd.read_parquet(data_path)
    else:
        df = pd.read_csv(data_path)

    # Parse dates
    if 'date' in df.columns:
        df['_date'] = pd.to_datetime(df['date'], errors='coerce')
        n_bad = df['_date'].isna().sum()
        if n_bad > 0:
            print(f"  [!] {n_bad} rows with invalid date removed.")
        df = df.dropna(subset=['_date'])
    else:
        raise KeyError("Column 'date' not found in data.")

    try:
        df = add_sample_weights(df, decay_days=30)
    except Exception as e:
        print(f"  [!] Warning in add_sample_weights: {e}. Continuing.")

    if '_date' not in df.columns:
        df['_date'] = pd.to_datetime(df['date'], errors='coerce')

    # Global distribution log
    raw_target = df['target'].values
    y_global = (raw_target + 1).astype(int) if raw_target.min() < 0 else raw_target.astype(int)
    dist_global = np.bincount(y_global, minlength=3)
    print(f"\n  [Dataset global] Short={dist_global[0]:,} | Hold={dist_global[1]:,} | "
          f"Long={dist_global[2]:,} | Ratio L:S={dist_global[2]/max(dist_global[0],1):.2f}")

    # Walk-forward splits
    splits = walk_forward_splits(df, train_window_months=train_m,
                                 test_window_months=test_m, step_months=1)
    print(f"[OK] Generated {len(splits)} windows\n")

    production_norm = None
    window_registry = []

    # ── PF floor: reject models with PF < 0.30 ──
    MIN_PF_FLOOR = 0.30

    for i, (tr_df, ts_df) in enumerate(splits):
        print(f"\n--- Window {i+1}/{len(splits)} | Train: {len(tr_df):,} | Test: {len(ts_df):,} ---")
        window_ensemble  = []
        window_model_pfs = []

        for s in range(n_ensemble):
            seed = 42 + s
            set_seed(seed)
            mod, nr, met = train_single_window(
                tr_df, ts_df, verbose=True, window_idx=i+1, seed=seed, hold_ratio=hold_ratio
            )
            min_trades_req = met.get('min_trades_req', 20)
            print(f"      Model {s+1}: Acc={met['accuracy']:.1%} | "
                  f"WR={met['win_rate']:.1%} | PF={met['profit_factor']:.2f} | "
                  f"Trades={met['total_trades']}")

            if mod is None:
                print(f"      Model {s+1}: SKIPPED (insufficient data)")
                continue

            n_trades  = met['total_trades']
            pf        = met['profit_factor']
            collapsed = met.get('collapsed', False)

            if collapsed:
                print(f"      [Select] RECHAZADO (COLLAPSE >80% one-sided)")
                if production_norm is None or i == len(splits) - 1:
                    production_norm = nr
                continue

            if n_trades < min_trades_req:
                sel_reason = f"RECHAZADO (trades={n_trades} < min={min_trades_req})"
            elif n_trades >= 30 and pf < MIN_PF_FLOOR:
                sel_reason = f"RECHAZADO (PF={pf:.2f} < floor={MIN_PF_FLOOR}, n={n_trades})"
            else:
                window_ensemble.append(mod)
                window_model_pfs.append(pf)
                sel_reason = f"ACEPTADO (trades={n_trades}, PF={pf:.2f}, WR={met['win_rate']:.1%})"
            print(f"      [Select] {sel_reason}")

            # Overwriting here is fine as long as we select top_windows[0]['norm'] later
            # It only acts as a fallback for 0 valid windows.
            if production_norm is None or i == len(splits) - 1:
                production_norm = nr

        if window_ensemble:
            avg_pf = float(np.mean(window_model_pfs))
            ensemble_obj = GBTEnsemble(window_ensemble)
            window_registry.append({
                "window_idx":   i + 1,
                "ensemble_obj": ensemble_obj,
                "avg_pf":       avg_pf,
                "n_models":     len(window_ensemble),
                "norm":         nr,
            })
            print(f"      [Window {i+1}] Registrado: {len(window_ensemble)} modelos | "
                  f"PF_avg={avg_pf:.3f}")
        else:
            print(f"      [!] Window {i+1} sin modelos validos -- omitted.")

    # ── Select top-N windows by rank_score ──
    if window_registry:
        total_splits = len(splits)
        
        eligible = [w for w in window_registry if w['window_idx'] >= min_window]
        
        # Use max eligible window_idx for recency normalization (not total_splits)
        # to avoid distortion when many windows are skipped
        max_idx = max(w['window_idx'] for w in eligible) if eligible else 1
        for w in eligible:
            recency = (w['window_idx'] / max_idx) ** 2
            w['rank_score'] = w['avg_pf'] * recency

        eligible.sort(key=lambda w: w['rank_score'], reverse=True)

        print(f"\n{'='*60}")
        print(f"  WINDOW REGISTRY -- {len(eligible)} valid/eligible windows")
        print(f"  Selecting top {top_n_windows} by rank_score (PF * recency²)")
        print(f"{'='*70}")
        print(f"  {'Rank':>4}  {'Win':>4}  {'Models':>6}  {'PF_avg':>8}  {'Score':>8}  {'Status'}")
        print(f"  {'-'*60}")
        for rank, w in enumerate(eligible, 1):
            status = "OK PROD" if rank <= top_n_windows else "  skip"
            print(f"  {rank:>4}  {w['window_idx']:>4}  {w['n_models']:>6}  "
                  f"{w['avg_pf']:>8.3f}  {w['rank_score']:>8.3f}  {status}")

        top_windows = eligible[:top_n_windows]

        # ── INJECT METADATA before any ensemble is created ──
        for w in eligible:
            for m in w["ensemble_obj"].models:
                m.metadata["window_idx"] = w["window_idx"]
                m.metadata["avg_pf"] = w["avg_pf"]

        # Flatten all GBTModels from top windows into one ensemble
        all_final = [m for w in top_windows for m in w["ensemble_obj"].models]
        # Use the MOST RECENT window's normalizer (not highest-ranked)
        # to ensure feature distributions match current market conditions.
        most_recent_window = max(top_windows, key=lambda w: w['window_idx'])
        production_norm = most_recent_window["norm"]
        print(f"  [Norm] Using normalizer from window {most_recent_window['window_idx']} (most recent in top-{top_n_windows})")

        final_ensemble = GBTEnsemble(all_final)
        save_gbt_ensemble(final_ensemble, production_norm, model_path, norm_path)

        # ── NEW: Save ALL windows for strict Walk-Forward backtest ──
        all_history = [m for w in eligible for m in w["ensemble_obj"].models]
        history_ensemble = GBTEnsemble(all_history)
        history_path = str(model_path).replace(".joblib", "_history.joblib")
        save_gbt_ensemble(history_ensemble, production_norm, history_path, norm_path)

        # Export registry to JSON
        import pathlib
        registry_export = [
            {
                "window":     w["window_idx"],
                "n_models":   w["n_models"],
                "pf_avg":     round(w["avg_pf"], 4),
                "rank_score": round(w["rank_score"], 4),
                "status":     "PROD" if rank_idx < top_n_windows else "skip",
            }
            for rank_idx, w in enumerate(eligible)
        ]
        # Include pre-min_window entries for transparency
        excluded_entries = [
            {
                "window":     w["window_idx"],
                "n_models":   w["n_models"],
                "pf_avg":     round(w["avg_pf"], 4),
                "rank_score": 0.0,
                "status":     "excluded (< min_window)",
            }
            for w in window_registry if w['window_idx'] < min_window
        ]
        registry_export = excluded_entries + registry_export
        registry_path = pathlib.Path(model_path).parent / "window_registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(registry_path, "w") as f:
            json.dump(registry_export, f, indent=2)
        print(f"  Registry saved: {registry_path}")

        total_win_models = sum(w["n_models"] for w in top_windows)
        best_pf  = top_windows[0]["avg_pf"]
        worst_pf = top_windows[-1]["avg_pf"]
        print(f"\nOK Saved Production Ensemble (GBT)")
        print(f"  Windows: {len(top_windows)} (of {len(window_registry)} valid)")
        print(f"  Models: {total_win_models} total")
        print(f"  PF range: {worst_pf:.3f} - {best_pf:.3f}")
    else:
        print("\n[!] No production models generated. "
              "Check selection criteria or data quality.")
        if production_norm is not None:
            print("  [WARNING] Using emergency fallback normalizer from last trained model.")
            print("  This normalizer may come from a rejected window — verify consistency.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",         required=True)
    parser.add_argument("--model-size",   default="small",  help="Unused (legacy), kept for CLI compat")
    parser.add_argument("--train-months", type=int,   default=6)
    parser.add_argument("--test-months",  type=int,   default=1)
    parser.add_argument("--epochs",       type=int,   default=80,  help="Unused (legacy)")
    parser.add_argument("--batch-size",   type=int,   default=512, help="Unused (legacy)")
    parser.add_argument("--lr",           type=float, default=0.0003, help="Unused (legacy)")
    parser.add_argument("--weight-decay", type=float, default=0.05,   help="Unused (legacy)")
    parser.add_argument("--ensemble",        type=int,   default=3)
    parser.add_argument("--top-n-windows",   type=int,   default=10,
                        help="N. top-PF windows to include in production ensemble")
    parser.add_argument("--min-window",      type=int,   default=0,
                        help="Ignorar ventanas anteriores a este indice para produccion")
    parser.add_argument("--hold-ratio",      type=float, default=1.5,
                        help="Ratio de muestras HOLD respecto al total de direccionales (2.0 = fuerte supresion del ruido)")
    parser.add_argument("--model_path", default="models/trading_hybrid_wf.joblib")
    parser.add_argument("--norm_path",  default="models/hybrid_normalizer_wf.npz")
    args = parser.parse_args()

    model_path = args.model_path
    norm_path  = args.norm_path

    walk_forward_train(
        args.data,
        model_path,
        norm_path,
        args.model_size,
        args.train_months,
        args.test_months,
        args.epochs,
        args.batch_size,
        args.lr,
        args.ensemble,
        args.top_n_windows,
        args.min_window,
        args.hold_ratio
    )
