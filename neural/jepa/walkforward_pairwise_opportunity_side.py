"""
PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1
Walk-forward evaluation: hierarchical opportunity + side classifier vs absolute baseline.

Arms:
  C0 — In-protocol nested absolute-head baseline (call_win + put_win classifiers)
  P1 — opportunity classifier + pairwise side classifier

C0 is NOT a frozen production artifact. It is trained within each fold with
exactly the same data, features, hyperparameters, scheduler, and protocol as P1.
The only difference is label definition and scoring policy.

Usage:
  python neural/jepa/walkforward_pairwise_opportunity_side.py \
    --dataset tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet \
    --output-dir research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

# ── Imports from existing codebase ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkforward_event_option_gate import DeployConfig, deploy, metrics

warnings.filterwarnings("ignore", category=UserWarning)

# ═══════════════════════════════════════════════════════════════════════
# FROZEN HYPERPARAMETERS — do not modify after predeclaration
# ═══════════════════════════════════════════════════════════════════════
FROZEN_LGB_PARAMS: dict[str, Any] = dict(
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    min_child_samples=20,
    subsample=0.8,
    subsample_freq=1,  # makes subsample=0.8 effective
    colsample_bytree=0.8,
    reg_lambda=1.0,
    # One fold runs at a time; use the Ryzen's available CPU parallelism.
    n_jobs=28,
    verbose=-1,
    objective="binary",
    importance_type="gain",
    deterministic=True,
    force_col_wise=True,
)
FROZEN_SEED = 42
FROZEN_CLIP_RETURN = 10.0  # not used for classification but kept for parity

# ── Head seed offsets ───────────────────────────────────────────────────
# base_seed = FROZEN_SEED + int(test_month) + ticker_offset
# C0 CALL        = base_seed + 1
# C0 PUT         = base_seed + 2
# P1 opportunity = base_seed + 3
# P1 side        = base_seed + 4
HEAD_OFFSET_C0_CALL = 1
HEAD_OFFSET_C0_PUT = 2
HEAD_OFFSET_P1_OPP = 3
HEAD_OFFSET_P1_SIDE = 4

# ── Ticker configuration ────────────────────────────────────────────────
TICKER_CONFIG: dict[str, dict[str, Any]] = {
    "SPXW": {"bucket": 25, "max_trades_per_day": 4, "cooldown_minutes": 0, "ticker_offset": 100},
    "QQQ":  {"bucket": 35, "max_trades_per_day": 2, "cooldown_minutes": 30, "ticker_offset": 200},
    "SPY":  {"bucket": 35, "max_trades_per_day": 1, "cooldown_minutes": 0, "ticker_offset": 300},
}

# ── Threshold grid (predeclared — shared C0 and P1) ────────────────────
TRADE_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
SIDE_MARGINS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

# ── Walk-forward configuration ──────────────────────────────────────────
TRAIN_MONTHS_COUNT = 12
VAL_MONTHS_COUNT = 3
FIRST_TEST_MONTH = "202304"
LAST_TEST_MONTH = "202512"
MIN_TRAIN_ROWS = 500
MIN_VAL_ROWS = 50

# ── First allowed minute ───────────────────────────────────────────────
# With minute > 630 and a 5-minute grid, the first allowed candidate is
# minute == 635 (10:35 ET). minute == 630 is excluded.
FIRST_ALLOWED_MINUTE = 635

# ── Inner validation gates ──────────────────────────────────────────────
INNER_MIN_PF = 1.3
INNER_MIN_WR = 0.50
INNER_MIN_TRADES_PER_MONTH = 18
INNER_MIN_HOLD_MINUTES = 30

# ── Common causal feature allowlist ─────────────────────────────────────
COMMON_FEATURES = [
    "minute",
    "ib_range_bps",
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "nearest_level_abs_bps",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
]
# NOTE: dte_days, spot, underlying_volume excluded per user instruction
# underlying_volume has only 1 distinct value (constant 60.0)

DIFF_METRICS = ["iv", "spread_pct", "volume", "oi", "abs_delta", "vega"]
CHANGE_LAGS = [(1, "5m"), (3, "15m"), (5, "25m")]

# ── Tie thresholds ──────────────────────────────────────────────────────
SIDE_TIE_THRESHOLD_TRAINING = 1e-9   # abs(side_advantage) <= this → exclude from side training
C0_TIE_THRESHOLD_EXECUTION = 1e-12   # abs(p_call_win - p_put_win) <= this → ABSTAIN


# ═══════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def month_add(month: str, offset: int) -> str:
    """Add offset months to a YYYYMM string."""
    y, m = divmod(int(month[:4]) * 12 + int(month[4:6]) - 1 + offset, 12)
    return f"{y}{m + 1:02d}"


def generate_folds(first_test: str, last_test: str) -> list[dict]:
    """Generate all walk-forward folds from first_test to last_test."""
    folds = []
    current = first_test
    while current <= last_test:
        inner_months = [month_add(current, -i) for i in range(VAL_MONTHS_COUNT, 0, -1)]
        first_train = month_add(inner_months[0], -TRAIN_MONTHS_COUNT)
        train_months = [month_add(first_train, i) for i in range(TRAIN_MONTHS_COUNT)]

        # Assertions
        assert len(train_months) == TRAIN_MONTHS_COUNT, f"Expected {TRAIN_MONTHS_COUNT} train months, got {len(train_months)}"
        assert len(inner_months) == VAL_MONTHS_COUNT, f"Expected {VAL_MONTHS_COUNT} inner months, got {len(inner_months)}"
        assert max(train_months) < min(inner_months), f"Train/inner overlap: {max(train_months)} >= {min(inner_months)}"
        assert max(inner_months) < current, f"Inner/outer overlap: {max(inner_months)} >= {current}"

        folds.append({
            "test_month": current,
            "inner_months": inner_months,
            "train_months": train_months,
        })
        current = month_add(current, 1)
    return folds


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def compute_feature_hash(feature_cols: list[str]) -> str:
    """Deterministic hash of the sorted feature list."""
    sorted_features = sorted(feature_cols)
    feat_bytes = ",".join(sorted_features).encode("utf-8")
    return hashlib.sha256(feat_bytes).hexdigest()


def make_lgb_params(base_seed: int, head_offset: int) -> dict[str, Any]:
    """Create LightGBM params with deterministic per-head seeds."""
    seed = base_seed + head_offset
    return {
        **FROZEN_LGB_PARAMS,
        "random_state": seed,
        "bagging_seed": seed,
        "feature_fraction_seed": seed,
        "data_random_seed": seed,
    }


def build_diff_features(df: pd.DataFrame, ticker: str, bucket: int) -> tuple[pd.DataFrame, list[str]]:
    """Build call-put difference features and backward-looking changes.

    Differences are computed per-row. Changes use shift grouped by
    (ticker, trade_date, bucket) to avoid cross-session contamination.
    Sort by minute within each group before computing shifts.
    NaN initial values are left as NaN (filled with train median at fit time).
    """
    work = df.copy()
    work["bucket"] = bucket
    diff_cols = []

    for metric in DIFF_METRICS:
        call_col = f"call_d{bucket:02d}_{metric}"
        put_col = f"put_d{bucket:02d}_{metric}"
        if call_col not in work.columns or put_col not in work.columns:
            raise KeyError(f"Missing source column: {call_col} or {put_col}")
        diff_name = f"{metric}_diff"
        work[diff_name] = pd.to_numeric(work[call_col], errors="coerce") - pd.to_numeric(work[put_col], errors="coerce")
        diff_cols.append(diff_name)

    # Backward-looking changes grouped by (ticker, trade_date, bucket) — no cross-session
    change_cols = []
    # Must sort by minute within each day for correct shift
    work = work.sort_values(["trade_date", "minute"]).copy()
    for diff_name in diff_cols:
        # Exclude OI change columns from features as requested
        if diff_name == "oi_diff":
            continue
        grouped = work.groupby(["ticker", "trade_date", "bucket"])[diff_name]
        for lag, label in CHANGE_LAGS:
            chg_name = f"{diff_name}_chg_{label}"
            work[chg_name] = work[diff_name] - grouped.shift(lag)
            change_cols.append(chg_name)

    all_feature_cols = COMMON_FEATURES + diff_cols + change_cols
    return work, all_feature_cols


def build_labels(df: pd.DataFrame, bucket: int) -> pd.DataFrame:
    """Build opportunity, side, call_win, and put_win labels from call/put exit returns.

    Labels:
      - opportunity_label = int(max(call_return, put_return) > 0)
      - side_advantage = call_return - put_return
      - side_label = int(side_advantage > 0)
      - call_win_label = int(call_return > 0)   [C0]
      - put_win_label = int(put_return > 0)     [C0]

    Filters out rows where target labels are non-finite (NaN, inf) before modeling.
    """
    work = df.copy()
    call_ret_col = f"call_d{bucket:02d}_opt_exit_ret"
    put_ret_col = f"put_d{bucket:02d}_opt_exit_ret"
    call_exit_min_col = f"call_d{bucket:02d}_opt_exit_minutes"
    put_exit_min_col = f"put_d{bucket:02d}_opt_exit_minutes"

    # Strict finite label filtering
    work = work[pd.to_numeric(work[call_ret_col], errors="coerce").notna() & np.isfinite(pd.to_numeric(work[call_ret_col], errors="coerce"))].copy()
    work = work[pd.to_numeric(work[put_ret_col], errors="coerce").notna() & np.isfinite(pd.to_numeric(work[put_ret_col], errors="coerce"))].copy()

    call_ret = pd.to_numeric(work[call_ret_col], errors="coerce")
    put_ret = pd.to_numeric(work[put_ret_col], errors="coerce")

    work["call_return"] = call_ret
    work["put_return"] = put_ret

    # P1 labels
    work["opportunity_label"] = (np.maximum(call_ret, put_ret) > 0.0).astype(int)
    work["side_advantage"] = call_ret - put_ret
    work["side_label"] = (work["side_advantage"] > 0.0).astype(int)

    # C0 labels — in-protocol absolute head baseline
    work["call_win_label"] = (call_ret > 0.0).astype(int)
    work["put_win_label"] = (put_ret > 0.0).astype(int)

    # exit_minutes for deploy (non-overlap logic)
    if call_exit_min_col in work.columns and put_exit_min_col in work.columns:
        call_exit = pd.to_numeric(work[call_exit_min_col], errors="coerce")
        put_exit = pd.to_numeric(work[put_exit_min_col], errors="coerce")
        work["call_exit_minutes"] = call_exit
        work["put_exit_minutes"] = put_exit

    return work


# ═══════════════════════════════════════════════════════════════════════
# SCORING AND SIMULATION
# ═══════════════════════════════════════════════════════════════════════

def apply_pairwise_policy(
    scored: pd.DataFrame,
    trade_threshold: float,
    side_margin: float,
    bucket: int,
) -> pd.DataFrame:
    """Apply P1 pairwise policy: opportunity threshold + side margin.

    Sets score, action, realized_return, exit_minutes columns for deploy().
    ABSTAIN if p_call is within the central band [0.5 - side_margin, 0.5 + side_margin].
    """
    work = scored.copy()
    p_trade = work["p_trade"].astype(float)
    p_call = work["p_call"].astype(float)

    # Determine action
    trade_mask = p_trade >= trade_threshold
    call_mask = trade_mask & (p_call >= 0.5 + side_margin)
    put_mask = trade_mask & (p_call <= 0.5 - side_margin)
    active_mask = call_mask | put_mask

    if not active_mask.any():
        return work.iloc[0:0].copy()

    work = work[active_mask].copy()
    is_call = work["p_call"].astype(float) >= 0.5 + side_margin

    work["action"] = np.where(is_call, "CALL", "PUT")
    work["score"] = work["p_trade"].astype(float)  # score for ranking = opportunity probability
    work["realized_return"] = np.where(is_call, work["call_return"], work["put_return"])

    call_exit_col = f"call_d{bucket:02d}_opt_exit_minutes"
    put_exit_col = f"put_d{bucket:02d}_opt_exit_minutes"
    if call_exit_col in work.columns and put_exit_col in work.columns:
        work["exit_minutes"] = np.where(
            is_call,
            pd.to_numeric(work[call_exit_col], errors="coerce"),
            pd.to_numeric(work[put_exit_col], errors="coerce"),
        )

    return work


def apply_c0_policy(
    scored: pd.DataFrame,
    trade_threshold: float,
    side_margin: float,
    bucket: int,
) -> pd.DataFrame:
    """Apply C0 in-protocol nested baseline policy.

    C0 policy:
      trade_score = max(p_call_win, p_put_win)
      side_gap = abs(p_call_win - p_put_win)

      CALL if trade_score >= trade_threshold AND side_gap >= side_margin AND p_call_win > p_put_win
      PUT  if trade_score >= trade_threshold AND side_gap >= side_margin AND p_put_win > p_call_win
      ABSTAIN otherwise (including ties: abs(p_call_win - p_put_win) <= 1e-12)

    Sets score, action, realized_return, exit_minutes columns for deploy().
    """
    work = scored.copy()
    p_call_win = work["p_call_win"].astype(float)
    p_put_win = work["p_put_win"].astype(float)

    trade_score = np.maximum(p_call_win, p_put_win)
    side_gap = np.abs(p_call_win - p_put_win)

    # Tie check: abs(p_call_win - p_put_win) <= 1e-12 → ABSTAIN
    not_tied = side_gap > C0_TIE_THRESHOLD_EXECUTION

    # Active conditions
    score_ok = trade_score >= trade_threshold
    gap_ok = side_gap >= side_margin
    is_call = p_call_win > p_put_win

    active_mask = score_ok & gap_ok & not_tied

    if not active_mask.any():
        return work.iloc[0:0].copy()

    work = work[active_mask].copy()
    is_call_active = work["p_call_win"].astype(float) > work["p_put_win"].astype(float)

    work["action"] = np.where(is_call_active, "CALL", "PUT")
    work["score"] = np.maximum(work["p_call_win"].astype(float), work["p_put_win"].astype(float))
    work["realized_return"] = np.where(is_call_active, work["call_return"], work["put_return"])

    call_exit_col = f"call_d{bucket:02d}_opt_exit_minutes"
    put_exit_col = f"put_d{bucket:02d}_opt_exit_minutes"
    if call_exit_col in work.columns and put_exit_col in work.columns:
        work["exit_minutes"] = np.where(
            is_call_active,
            pd.to_numeric(work[call_exit_col], errors="coerce"),
            pd.to_numeric(work[put_exit_col], errors="coerce"),
        )

    return work


def compute_monthly_inner_gates(
    trades: pd.DataFrame,
    inner_months: list[str],
) -> tuple[bool, dict]:
    """Check per-month inner validation gates. Returns (passes, details)."""
    if trades.empty:
        return False, {"reason": "no_trades", "months": {}}

    work = trades.copy()
    work["month"] = work["month"].astype(str)

    month_details = {}
    all_pass = True
    for m in inner_months:
        m_trades = work[work["month"] == m]
        n = len(m_trades)
        if n == 0:
            month_details[m] = {"trades": 0, "pass": False, "reason": "no_trades"}
            all_pass = False
            continue

        ret = m_trades["realized_return"].astype(float).to_numpy()
        wins = ret[ret > 0]
        losses = ret[ret < 0]
        pf = float(wins.sum() / (-losses.sum())) if len(losses) > 0 and losses.sum() < 0 else float("inf")
        wr = float((ret > 0).mean())
        pnl = float(ret.sum())

        # Check duration >= 30m
        if "exit_minutes" in m_trades.columns and "minute" in m_trades.columns:
            durations = pd.to_numeric(m_trades["exit_minutes"], errors="coerce") - pd.to_numeric(m_trades["minute"], errors="coerce")
            min_dur = float(durations.min())
        else:
            min_dur = 30.0

        passes = (
            n >= INNER_MIN_TRADES_PER_MONTH
            and pf >= INNER_MIN_PF
            and wr >= INNER_MIN_WR
            and pnl > 0.0
            and min_dur >= 30.0
        )
        month_details[m] = {
            "trades": n, "pf": round(pf, 4), "wr": round(wr, 4),
            "pnl": round(pnl, 4), "min_hold_minutes": min_dur, "pass": passes,
        }
        if not passes:
            all_pass = False

    return all_pass, {"months": month_details}


def _sweep_configs(
    scored_val: pd.DataFrame,
    inner_months: list[str],
    config: dict,
    bucket: int,
    apply_fn,
) -> list[dict]:
    """Sweep trade_threshold × side_margin for a given policy. Returns candidate list."""
    cooldown = config["cooldown_minutes"]
    max_day = config["max_trades_per_day"]

    candidates = []
    for tt in TRADE_THRESHOLDS:
        for sm in SIDE_MARGINS:
            applied = apply_fn(scored_val, tt, sm, bucket)
            if applied.empty:
                continue
            cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
            traded = deploy(applied, cfg, cooldown)
            if traded.empty:
                continue

            passes, gate_details = compute_monthly_inner_gates(traded, inner_months)
            if not passes:
                continue

            # Compute per-month metrics for lexicographic ranking
            traded_work = traded.copy()
            traded_work["month"] = traded_work["month"].astype(str)
            monthly_pnl = []
            monthly_pf = []
            monthly_wr = []
            monthly_trades = []
            for m in inner_months:
                mt = traded_work[traded_work["month"] == m]
                ret = mt["realized_return"].astype(float).to_numpy() if not mt.empty else np.array([])
                monthly_pnl.append(float(ret.sum()) if len(ret) > 0 else 0.0)
                wins = ret[ret > 0] if len(ret) > 0 else np.array([])
                losses = ret[ret < 0] if len(ret) > 0 else np.array([])
                pf = float(wins.sum() / (-losses.sum())) if len(losses) > 0 and losses.sum() < 0 else float("inf")
                monthly_pf.append(pf)
                monthly_wr.append(float((ret > 0).mean()) if len(ret) > 0 else 0.0)
                monthly_trades.append(int(len(mt)))

            total_pnl = float(traded["realized_return"].astype(float).sum())
            total_trades = int(len(traded))

            rank_key = (
                min(monthly_pnl),       # 1. max min monthly PnL
                min(monthly_pf),        # 2. max min monthly PF
                min(monthly_wr),        # 3. max min monthly WR
                min(monthly_trades),    # 4. max min monthly trades
                total_pnl,             # 5. max total PnL
                total_trades,          # 6. max total trades
                sm,                    # 7. max side_margin
                tt,                    # 8. max trade_threshold
            )

            candidates.append({
                "trade_threshold": tt,
                "side_margin": sm,
                "rank_key": rank_key,
                "total_trades": total_trades,
                "total_pnl": total_pnl,
                "gate_details": gate_details,
            })

    return candidates


def select_best_config_p1(
    scored_val: pd.DataFrame,
    inner_months: list[str],
    config: dict,
    bucket: int,
) -> tuple[float, float, bool, dict]:
    """Sweep trade_threshold × side_margin for P1. Return best (trade_thr, side_margin, valid, details)."""
    candidates = _sweep_configs(scored_val, inner_months, config, bucket, apply_pairwise_policy)

    if not candidates:
        return 0.5, 0.0, False, {"reason": "no_valid_config"}

    # Sort descending by rank_key (lexicographic max)
    candidates.sort(key=lambda c: c["rank_key"], reverse=True)
    best = candidates[0]
    return best["trade_threshold"], best["side_margin"], True, best


def select_best_config_c0(
    scored_val: pd.DataFrame,
    inner_months: list[str],
    config: dict,
    bucket: int,
) -> tuple[float, float, bool, dict]:
    """Sweep trade_threshold × side_margin for C0. Return best (trade_thr, side_margin, valid, details).

    C0 now uses the same grid and lexicographic selection as P1.
    """
    candidates = _sweep_configs(scored_val, inner_months, config, bucket, apply_c0_policy)

    if not candidates:
        return 0.5, 0.0, False, {"reason": "no_valid_config"}

    candidates.sort(key=lambda c: c["rank_key"], reverse=True)
    best = candidates[0]
    return best["trade_threshold"], best["side_margin"], True, best


# ═══════════════════════════════════════════════════════════════════════
# DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════

def compute_diagnostics(
    scored: pd.DataFrame,
    traded: pd.DataFrame,
    arm: str,
    bucket: int,
) -> dict:
    """Compute pre-PnL and post-PnL diagnostics."""
    diag: dict[str, Any] = {"arm": arm}

    call_ret = scored["call_return"].astype(float)
    put_ret = scored["put_return"].astype(float)
    opp_label = (np.maximum(call_ret, put_ret) > 0).astype(int)
    side_label = (call_ret > put_ret).astype(int)
    side_adv = call_ret - put_ret

    # Pre-PnL diagnostics
    diag["opportunity_prevalence"] = round(float(opp_label.mean()), 4)
    opp_positive = scored[opp_label == 1]
    if len(opp_positive) > 0:
        diag["call_prevalence_in_opp_positive"] = round(float((opp_positive["call_return"].astype(float) > opp_positive["put_return"].astype(float)).mean()), 4)
    else:
        diag["call_prevalence_in_opp_positive"] = float("nan")

    tie_mask = side_adv.abs() <= SIDE_TIE_THRESHOLD_TRAINING
    diag["tie_rate"] = round(float(tie_mask.mean()), 4)

    if arm == "P1" and "p_trade" in scored.columns and "p_call" in scored.columns:
        # Opportunity metrics (all rows)
        p_trade = scored["p_trade"].astype(float)
        finite_mask = np.isfinite(p_trade) & np.isfinite(opp_label.astype(float))
        if finite_mask.sum() > 10:
            try:
                diag["opportunity_auc"] = round(float(roc_auc_score(opp_label[finite_mask], p_trade[finite_mask])), 4)
            except Exception:
                diag["opportunity_auc"] = float("nan")
            try:
                diag["opportunity_pr_auc"] = round(float(average_precision_score(opp_label[finite_mask], p_trade[finite_mask])), 4)
            except Exception:
                diag["opportunity_pr_auc"] = float("nan")

        # Side metrics — A: over all opportunity-positive events
        opp_pos_mask = (opp_label == 1) & (~tie_mask)
        if opp_pos_mask.sum() > 10:
            p_call_opp = scored.loc[opp_pos_mask, "p_call"].astype(float)
            side_true = side_label[opp_pos_mask]
            pred_side = (p_call_opp >= 0.5).astype(int)
            try:
                diag["side_accuracy_A"] = round(float((pred_side == side_true).mean()), 4)
                diag["side_balanced_accuracy_A"] = round(float(balanced_accuracy_score(side_true, pred_side)), 4)
                diag["side_roc_auc_A"] = round(float(roc_auc_score(side_true, p_call_opp)), 4)
            except Exception:
                pass

            side_adv_opp = side_adv[opp_pos_mask]
            finite_spearman = np.isfinite(p_call_opp) & np.isfinite(side_adv_opp)
            if finite_spearman.sum() > 10:
                sp, sp_p = spearmanr(p_call_opp[finite_spearman], side_adv_opp[finite_spearman])
                diag["spearman_side_advantage_A"] = round(float(sp), 4)
                diag["spearman_side_advantage_p_A"] = round(float(sp_p), 6)

    if arm == "C0" and "p_call_win" in scored.columns and "p_put_win" in scored.columns:
        # C0 balanced accuracy diagnostics
        p_call_win = scored["p_call_win"].astype(float)
        p_put_win = scored["p_put_win"].astype(float)
        opp_pos_mask = (opp_label == 1) & (~tie_mask)
        if opp_pos_mask.sum() > 10:
            pred_side_c0 = (p_call_win[opp_pos_mask] > p_put_win[opp_pos_mask]).astype(int)
            side_true = side_label[opp_pos_mask]
            try:
                diag["side_balanced_accuracy_A"] = round(float(balanced_accuracy_score(side_true, pred_side_c0)), 4)
            except Exception:
                pass

    # Post-PnL diagnostics (from traded)
    if not traded.empty:
        ret = traded["realized_return"].astype(float).to_numpy()
        diag["executed_trades"] = int(len(traded))
        diag["wr"] = round(float((ret > 0).mean()), 4)
        wins = ret[ret > 0]
        losses = ret[ret < 0]
        diag["gross_profit"] = float(wins.sum()) if len(wins) else 0.0
        diag["gross_loss"] = float(-losses.sum()) if len(losses) else 0.0
        diag["pf"] = round(float(wins.sum() / (-losses.sum())), 4) if len(losses) > 0 and losses.sum() < 0 else float("inf")
        diag["pnl"] = round(float(ret.sum()), 4)
        equity = np.cumsum(ret)
        peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
        diag["max_drawdown"] = round(float((equity - peak).min()), 4) if len(equity) > 0 else 0.0
        diag["call_rate"] = round(float((traded["action"].astype(str) == "CALL").mean()), 4)
        diag["abstention_rate"] = round(1.0 - len(traded) / max(1, len(scored)), 4)

        if "exit_minutes" in traded.columns:
            exits = pd.to_numeric(traded["exit_minutes"], errors="coerce").dropna()
            diag["min_hold_minutes"] = round(float(exits.min()), 1) if len(exits) > 0 else float("nan")

        # Monthly breakdown
        traded_m = traded.copy()
        traded_m["month"] = traded_m["month"].astype(str)
        months = sorted(traded_m["month"].unique())
        month_pfs = []
        month_pnls = []
        month_trades = []
        for m in months:
            mt = traded_m[traded_m["month"] == m]
            mr = mt["realized_return"].astype(float).to_numpy()
            mw = mr[mr > 0]
            ml = mr[mr < 0]
            mpf = float(mw.sum() / (-ml.sum())) if len(ml) > 0 and ml.sum() < 0 else float("inf")
            month_pfs.append(mpf)
            month_pnls.append(float(mr.sum()))
            month_trades.append(int(len(mt)))
        diag["worst_monthly_pf"] = round(min(month_pfs), 4) if month_pfs else float("nan")
        diag["worst_monthly_pnl"] = round(min(month_pnls), 4) if month_pnls else float("nan")
        diag["min_monthly_trades"] = min(month_trades) if month_trades else 0
        diag["positive_month_rate"] = round(sum(1 for p in month_pnls if p > 0) / max(1, len(month_pnls)), 4)
        diag["pooled_pf"] = diag["pf"]
        diag["outer_trade_records"] = [
            {
                "date": str(row["date"]),
                "minute": int(row["minute"]),
                "ticker": str(row.get("ticker", "")),
                "realized_return": float(row["realized_return"]),
            }
            for _, row in traded.sort_values(["date", "minute"]).iterrows()
        ]
    else:
        diag["executed_trades"] = 0
        diag["wr"] = float("nan")
        diag["pf"] = float("nan")
        diag["pnl"] = 0.0
        diag["abstention_rate"] = 1.0
        diag["gross_profit"] = 0.0
        diag["gross_loss"] = 0.0
        diag["max_drawdown"] = 0.0
        diag["min_hold_minutes"] = float("nan")
        diag["outer_trade_records"] = []

    return diag


def compute_lr_diagnostics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    label_name: str,
) -> dict:
    """Compute diagnostic-only metrics for Logistic Regression.

    Reports only: ROC-AUC, PR-AUC, balanced accuracy (threshold=0.5), Spearman.
    LR does NOT select thresholds, produce economic policies, enter the scheduler,
    substitute LightGBM, participate in ensembles, or get selected retrospectively.
    """
    diag = {"label": label_name}
    finite = np.isfinite(y_prob) & np.isfinite(y_true.astype(float))
    if finite.sum() < 10:
        return diag

    y_t = y_true[finite]
    y_p = y_prob[finite]

    try:
        diag["roc_auc"] = round(float(roc_auc_score(y_t, y_p)), 4)
    except Exception:
        diag["roc_auc"] = float("nan")

    try:
        diag["pr_auc"] = round(float(average_precision_score(y_t, y_p)), 4)
    except Exception:
        diag["pr_auc"] = float("nan")

    try:
        pred = (y_p >= 0.5).astype(int)
        diag["balanced_accuracy"] = round(float(balanced_accuracy_score(y_t, pred)), 4)
    except Exception:
        diag["balanced_accuracy"] = float("nan")

    try:
        sp, _ = spearmanr(y_p, y_t)
        diag["spearman"] = round(float(sp), 4)
    except Exception:
        diag["spearman"] = float("nan")

    return diag


def compute_scientific_side_metrics(
    call_return: np.ndarray,
    put_return: np.ndarray,
    c0_side_score: np.ndarray,
    p1_side_score: np.ndarray,
) -> dict[str, Any]:
    """Evaluate C0 and P1 side scores on one immutable outer-test mask.

    This is deliberately model-level: no policy threshold, scheduler output,
    or executed-trade mask is accepted by the function.
    """
    call_return = np.asarray(call_return, dtype=float)
    put_return = np.asarray(put_return, dtype=float)
    c0_side_score = np.asarray(c0_side_score, dtype=float)
    p1_side_score = np.asarray(p1_side_score, dtype=float)
    lengths = {len(call_return), len(put_return), len(c0_side_score), len(p1_side_score)}
    if len(lengths) != 1:
        raise ValueError("Scientific side arrays must have identical lengths")

    side_advantage = call_return - put_return
    opportunity_label = (np.maximum(call_return, put_return) > 0.0).astype(int)
    side_label = (side_advantage > 0.0).astype(int)
    finite = (
        np.isfinite(call_return)
        & np.isfinite(put_return)
        & np.isfinite(c0_side_score)
        & np.isfinite(p1_side_score)
    )
    mask = (
        finite
        & (opportunity_label == 1)
        & (np.abs(side_advantage) > SIDE_TIE_THRESHOLD_TRAINING)
    )
    mask_hash = hashlib.sha256(mask.astype(np.uint8).tobytes()).hexdigest()
    result: dict[str, Any] = {
        "scientific_mask_rows": int(mask.sum()),
        "scientific_mask_sha256": mask_hash,
        "sci_cell_degenerate": False,
        "sci_cell_degenerate_reason": "",
    }

    y_true = side_label[mask]
    advantage = side_advantage[mask]
    c0_score = c0_side_score[mask]
    p1_score = p1_side_score[mask]
    if len(y_true) < 2 or len(np.unique(y_true)) < 2:
        result.update({
            "sci_cell_degenerate": True,
            "sci_cell_degenerate_reason": (
                f"SCIENTIFIC_CELL_DEGENERATE: rows={len(y_true)}, "
                f"classes={len(np.unique(y_true)) if len(y_true) else 0}"
            ),
        })
        for arm in ("c0", "p1"):
            for metric_name in ("accuracy", "balanced_accuracy", "roc_auc", "spearman"):
                result[f"sci_{arm}_{metric_name}"] = float("nan")
        result["sci_ba_delta"] = float("nan")
        return result

    for arm, score in (("c0", c0_score), ("p1", p1_score)):
        pred = (score >= 0.0).astype(int)
        result[f"sci_{arm}_accuracy"] = float(accuracy_score(y_true, pred))
        result[f"sci_{arm}_balanced_accuracy"] = float(balanced_accuracy_score(y_true, pred))
        result[f"sci_{arm}_roc_auc"] = float(roc_auc_score(y_true, score))
        correlation, _ = spearmanr(score, advantage)
        result[f"sci_{arm}_spearman"] = float(correlation)

    required = [
        result[f"sci_{arm}_{metric_name}"]
        for arm in ("c0", "p1")
        for metric_name in ("accuracy", "balanced_accuracy", "roc_auc", "spearman")
    ]
    if not np.isfinite(required).all():
        result["sci_cell_degenerate"] = True
        result["sci_cell_degenerate_reason"] = "SCIENTIFIC_CELL_DEGENERATE: nonfinite_model_metric"
        result["sci_ba_delta"] = float("nan")
    else:
        result["sci_ba_delta"] = (
            result["sci_p1_balanced_accuracy"] - result["sci_c0_balanced_accuracy"]
        )
    return result


# ═══════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════

def run_fold(
    ticker: str,
    fold: dict,
    prepared: pd.DataFrame,
    feature_cols: list[str],
    feature_hash: str,
    config: dict,
    output_dir: Path,
) -> dict:
    """Run a single fold for both C0 and P1 arms."""
    bucket = config["bucket"]
    test_month = fold["test_month"]
    inner_months = fold["inner_months"]
    train_months = fold["train_months"]
    cooldown = config["cooldown_minutes"]
    max_day = config["max_trades_per_day"]
    ticker_offset = config["ticker_offset"]

    fold_id = f"{ticker}_{test_month}"
    fold_dir = output_dir / fold_id
    fold_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [{fold_id}] train={train_months[0]}..{train_months[-1]} inner={inner_months[0]}..{inner_months[-1]} test={test_month}")

    # Split data
    work = prepared.copy()
    work["month"] = work["trade_date"].astype(str).str[:6]
    work["date"] = work["trade_date"].astype(str)

    train = work[work["month"].isin(train_months)].copy()
    val = work[work["month"].isin(inner_months)].copy()
    test = work[work["month"] == test_month].copy()

    result = {
        "ticker": ticker, "test_month": test_month,
        "train_months": ",".join(train_months),
        "inner_months": ",".join(inner_months),
        "train_rows": len(train), "val_rows": len(val), "test_rows": len(test),
        "feature_hash": feature_hash,
        "first_allowed_minute": FIRST_ALLOWED_MINUTE,
    }

    if len(train) < MIN_TRAIN_ROWS or len(val) < MIN_VAL_ROWS or test.empty:
        result["status"] = "insufficient_rows"
        result["c0"] = {"status": "insufficient_rows"}
        result["p1"] = {"status": "insufficient_rows"}
        result["sci_cell_degenerate"] = True
        result["sci_cell_degenerate_reason"] = "insufficient_rows"
        result["sci_c0_balanced_accuracy"] = float("nan")
        result["sci_c0_roc_auc"] = float("nan")
        result["sci_c0_spearman"] = float("nan")
        result["sci_p1_balanced_accuracy"] = float("nan")
        result["sci_p1_roc_auc"] = float("nan")
        result["sci_p1_spearman"] = float("nan")
        result["sci_ba_delta"] = float("nan")
        return result

    # Prepare features — same for both C0 and P1
    train_medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)

    def fill_features(df: pd.DataFrame) -> pd.DataFrame:
        return df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(train_medians).fillna(0.0)

    X_train = fill_features(train)
    X_val = fill_features(val)
    X_test = fill_features(test)

    # Deterministic seed calculation (no python hash())
    base_seed = int(FROZEN_SEED) + int(test_month) + ticker_offset
    result["base_seed"] = base_seed

    # ── y arrays for training ──────────────────────────────────────────
    # C0 labels
    y_call_win_train = train["call_win_label"].astype(int)
    y_put_win_train = train["put_win_label"].astype(int)

    # P1 labels
    y_opp_train = train["opportunity_label"].astype(int)
    side_train_mask = (
        (train["opportunity_label"] == 1)
        & (train["side_advantage"].astype(float).abs() > SIDE_TIE_THRESHOLD_TRAINING)
    )
    side_train = train[side_train_mask]
    X_side_train = fill_features(side_train)
    y_side_train = side_train["side_label"].astype(int)

    # Prevalences
    opp_prevalence = float(y_opp_train.mean()) if len(y_opp_train) > 0 else 0.0
    side_prevalence = float(y_side_train.mean()) if len(y_side_train) > 0 else 0.0
    result["opportunity_prevalence"] = opp_prevalence
    result["side_prevalence"] = side_prevalence
    result["call_win_prevalence"] = float(y_call_win_train.mean()) if len(y_call_win_train) > 0 else 0.0
    result["put_win_prevalence"] = float(y_put_win_train.mean()) if len(y_put_win_train) > 0 else 0.0

    # Class degeneracy checks
    is_degenerate = (
        len(np.unique(y_call_win_train)) < 2 or
        len(np.unique(y_put_win_train)) < 2 or
        len(np.unique(y_opp_train)) < 2 or
        len(np.unique(y_side_train)) < 2
    )

    if is_degenerate:
        result["status"] = "ABSTAIN_MODEL_DEGENERATE"
        result["c0"] = {"status": "ABSTAIN_MODEL_DEGENERATE"}
        result["p1"] = {"status": "ABSTAIN_MODEL_DEGENERATE"}
        result["sci_cell_degenerate"] = True
        result["sci_cell_degenerate_reason"] = "train_labels_degenerate"
        result["sci_c0_balanced_accuracy"] = float("nan")
        result["sci_c0_roc_auc"] = float("nan")
        result["sci_c0_spearman"] = float("nan")
        result["sci_p1_balanced_accuracy"] = float("nan")
        result["sci_p1_roc_auc"] = float("nan")
        result["sci_p1_spearman"] = float("nan")
        result["sci_ba_delta"] = float("nan")
        with open(fold_dir / "fold_summary.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        return result

    # ── C0: In-protocol nested absolute-head baseline ───────────────────
    lgb_params_c0_call = make_lgb_params(base_seed, HEAD_OFFSET_C0_CALL)
    lgb_params_c0_put = make_lgb_params(base_seed, HEAD_OFFSET_C0_PUT)

    c0_call_model = lgb.LGBMClassifier(**lgb_params_c0_call)
    c0_put_model = lgb.LGBMClassifier(**lgb_params_c0_put)
    c0_call_model.fit(X_train, y_call_win_train)
    c0_put_model.fit(X_train, y_put_win_train)

    # Score validation and test
    val_c0 = val.copy()
    val_c0["p_call_win"] = c0_call_model.predict_proba(X_val)[:, 1]
    val_c0["p_put_win"] = c0_put_model.predict_proba(X_val)[:, 1]

    test_c0 = test.copy()
    test_c0["p_call_win"] = c0_call_model.predict_proba(X_test)[:, 1]
    test_c0["p_put_win"] = c0_put_model.predict_proba(X_test)[:, 1]

    # Select best threshold + side_margin for C0
    best_thr_c0, best_sm_c0, valid_c0, c0_sel_details = select_best_config_c0(
        val_c0, inner_months, config, bucket,
    )

    # Deploy C0 on test
    if valid_c0:
        test_c0_applied = apply_c0_policy(test_c0, best_thr_c0, best_sm_c0, bucket)
        c0_cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
        test_c0_traded = deploy(test_c0_applied, c0_cfg, cooldown) if not test_c0_applied.empty else test_c0_applied
        c0_test_metrics = metrics(test_c0_traded, [test_month])
        c0_diag = compute_diagnostics(test_c0, test_c0_traded, "C0", bucket)
    else:
        test_c0_traded = pd.DataFrame()
        c0_test_metrics = metrics(pd.DataFrame(), [test_month])
        c0_diag = {"arm": "C0", "status": "abstain", "reason": "no_valid_inner_config"}

    result["c0"] = {
        "trade_threshold": best_thr_c0,
        "side_margin": best_sm_c0,
        "valid_inner": valid_c0,
        "test_metrics": c0_test_metrics,
        "diagnostics": c0_diag,
        "selection_details": c0_sel_details if isinstance(c0_sel_details, dict) else {},
        "model_labels": {"call": "call_win_label = int(call_return > 0)", "put": "put_win_label = int(put_return > 0)"},
        "seed_call": base_seed + HEAD_OFFSET_C0_CALL,
        "seed_put": base_seed + HEAD_OFFSET_C0_PUT,
    }

    # ── P1: Pairwise opportunity + side ─────────────────────────────────
    lgb_params_p1_opp = make_lgb_params(base_seed, HEAD_OFFSET_P1_OPP)
    lgb_params_p1_side = make_lgb_params(base_seed, HEAD_OFFSET_P1_SIDE)

    p1_opp_model = lgb.LGBMClassifier(**lgb_params_p1_opp)
    p1_side_model = lgb.LGBMClassifier(**lgb_params_p1_side)

    p1_opp_model.fit(X_train, y_opp_train)

    if len(X_side_train) < 50:
        result["p1"] = {"status": "insufficient_side_train_rows", "side_train_rows": len(X_side_train)}
        result["sci_cell_degenerate"] = True
        result["sci_cell_degenerate_reason"] = "insufficient_side_train_rows"
        result["sci_c0_balanced_accuracy"] = float("nan")
        result["sci_c0_roc_auc"] = float("nan")
        result["sci_c0_spearman"] = float("nan")
        result["sci_p1_balanced_accuracy"] = float("nan")
        result["sci_p1_roc_auc"] = float("nan")
        result["sci_p1_spearman"] = float("nan")
        result["sci_ba_delta"] = float("nan")
        with open(fold_dir / "fold_summary.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        return result

    p1_side_model.fit(X_side_train, y_side_train)

    # Score validation and test
    val_p1 = val.copy()
    val_p1["p_trade"] = p1_opp_model.predict_proba(X_val)[:, 1]
    val_p1["p_call"] = p1_side_model.predict_proba(X_val)[:, 1]

    test_p1 = test.copy()
    test_p1["p_trade"] = p1_opp_model.predict_proba(X_test)[:, 1]
    test_p1["p_call"] = p1_side_model.predict_proba(X_test)[:, 1]

    # Select best config for P1
    best_tt, best_sm, valid_p1, p1_sel_details = select_best_config_p1(
        val_p1, inner_months, config, bucket,
    )

    # Deploy P1 on test
    if valid_p1:
        test_p1_applied = apply_pairwise_policy(test_p1, best_tt, best_sm, bucket)
        p1_cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
        test_p1_traded = deploy(test_p1_applied, p1_cfg, cooldown) if not test_p1_applied.empty else test_p1_applied
        p1_test_metrics = metrics(test_p1_traded, [test_month])
        p1_diag = compute_diagnostics(test_p1, test_p1_traded, "P1", bucket)
    else:
        test_p1_traded = pd.DataFrame()
        p1_test_metrics = metrics(pd.DataFrame(), [test_month])
        p1_diag = {"arm": "P1", "status": "abstain", "reason": "no_valid_inner_config"}

    result["p1"] = {
        "trade_threshold": best_tt,
        "side_margin": best_sm,
        "valid_inner": valid_p1,
        "test_metrics": p1_test_metrics,
        "diagnostics": p1_diag,
        "selection_details": p1_sel_details if isinstance(p1_sel_details, dict) else {},
        "side_train_rows": int(len(X_side_train)),
        "model_labels": {"opp": "opportunity_label = int(max(call_return, put_return) > 0)", "side": "side_label = int(call_return > put_return)"},
        "seed_opp": base_seed + HEAD_OFFSET_P1_OPP,
        "seed_side": base_seed + HEAD_OFFSET_P1_SIDE,
    }

    # ── Scientific model-level side metrics (outer test; policy-independent) ──
    call_ret_test = test["call_return"].astype(float).to_numpy()
    put_ret_test = test["put_return"].astype(float).to_numpy()
    c0_side_score_test = (test_c0["p_call_win"].astype(float) - test_c0["p_put_win"].astype(float)).to_numpy()
    p1_side_score_test = (2 * test_p1["p_call"].astype(float) - 1.0).to_numpy()
    result.update(compute_scientific_side_metrics(
        call_ret_test,
        put_ret_test,
        c0_side_score_test,
        p1_side_score_test,
    ))

    # ── Logistic Regression diagnostic (no trades, no policy) ──────────
    try:
        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        X_train_imp = imputer.fit_transform(X_train)
        X_train_scaled = scaler.fit_transform(X_train_imp)
        X_val_imp = imputer.transform(X_val)
        X_val_scaled = scaler.transform(X_val_imp)
        X_test_imp = imputer.transform(X_test)
        X_test_scaled = scaler.transform(X_test_imp)

        lr_diag_results = {}

        # C0 heads
        lr_call = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", class_weight=None, max_iter=1000, random_state=base_seed)
        lr_put = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", class_weight=None, max_iter=1000, random_state=base_seed)
        lr_call.fit(X_train_scaled, y_call_win_train)
        lr_put.fit(X_train_scaled, y_put_win_train)
        lr_diag_results["call_win"] = compute_lr_diagnostics(y_call_win_train.to_numpy(), lr_call.predict_proba(X_train_scaled)[:, 1], "call_win_train")
        lr_diag_results["put_win"] = compute_lr_diagnostics(y_put_win_train.to_numpy(), lr_put.predict_proba(X_train_scaled)[:, 1], "put_win_train")
        lr_diag_results["call_win_test"] = compute_lr_diagnostics(
            test["call_win_label"].astype(int).to_numpy(), lr_call.predict_proba(X_test_scaled)[:, 1], "call_win_test"
        )
        lr_diag_results["put_win_test"] = compute_lr_diagnostics(
            test["put_win_label"].astype(int).to_numpy(), lr_put.predict_proba(X_test_scaled)[:, 1], "put_win_test"
        )

        # P1 heads
        lr_opp = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", class_weight=None, max_iter=1000, random_state=base_seed)
        lr_opp.fit(X_train_scaled, y_opp_train)
        lr_diag_results["opportunity_test"] = compute_lr_diagnostics(
            test["opportunity_label"].astype(int).to_numpy(), lr_opp.predict_proba(X_test_scaled)[:, 1], "opportunity_test"
        )

        if len(X_side_train) >= 50:
            X_side_imp = imputer.transform(X_side_train)
            X_side_scaled = scaler.transform(X_side_imp)
            lr_side = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", class_weight=None, max_iter=1000, random_state=base_seed)
            lr_side.fit(X_side_scaled, y_side_train)
            # Test-set side diagnostics (on opp-positive non-tie subset)
            test_side_mask = (test["opportunity_label"] == 1) & (test["side_advantage"].astype(float).abs() > SIDE_TIE_THRESHOLD_TRAINING)
            if test_side_mask.sum() >= 10:
                X_test_side = X_test_scaled[test_side_mask.values]
                y_test_side = test.loc[test_side_mask, "side_label"].astype(int).to_numpy()
                lr_diag_results["side_test"] = compute_lr_diagnostics(
                    y_test_side, lr_side.predict_proba(X_test_side)[:, 1], "side_test"
                )

        result["logistic_regression"] = lr_diag_results

    except Exception as e:
        result["logistic_regression"] = {"status": "error", "error": str(e)}

    # ── Save feature importances ────────────────────────────────────────
    opp_imp = pd.DataFrame({
        "feature": feature_cols,
        "importance": p1_opp_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    opp_imp.to_csv(fold_dir / "opportunity_model_importances.csv", index=False)

    side_imp = pd.DataFrame({
        "feature": feature_cols,
        "importance": p1_side_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    side_imp.to_csv(fold_dir / "side_model_importances.csv", index=False)

    c0_call_imp = pd.DataFrame({
        "feature": feature_cols,
        "importance": c0_call_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    c0_call_imp.to_csv(fold_dir / "c0_call_model_importances.csv", index=False)

    c0_put_imp = pd.DataFrame({
        "feature": feature_cols,
        "importance": c0_put_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    c0_put_imp.to_csv(fold_dir / "c0_put_model_importances.csv", index=False)

    # Save fold trades
    trade_export_cols = ["date", "month", "minute", "action", "score", "realized_return"]
    if not test_p1_traded.empty:
        cols = [c for c in trade_export_cols if c in test_p1_traded.columns]
        test_p1_traded[cols].to_csv(fold_dir / "p1_trades.csv", index=False)
    if not test_c0_traded.empty:
        cols = [c for c in trade_export_cols if c in test_c0_traded.columns]
        test_c0_traded[cols].to_csv(fold_dir / "c0_trades.csv", index=False)

    # Save fold summary
    with open(fold_dir / "fold_summary.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    result["status"] = "completed"
    return result


def compute_scientific_criteria(all_results: list[dict]) -> dict:
    """Compute predeclared scientific success criteria.

    Denominator is strictly 99 cells (3 tickers × 33 outer months).
    Cells that are degenerate or not completed are counted as degenerate and NOT favorable.

    Requirements:
    1. balanced accuracy delta (sci_ba_delta) > 0 in >= 60% of 99 cells.
    2. median of delta > 0.
    3. sci_p1_spearman > 0 in >= 60% of 99 cells.
    4. median of Spearman > 0.
    5. median delta > 0 in each year: 2023, 2024, 2025.
    """
    total_denominator = 99
    observed_cells = len(all_results)
    missing_cells = max(0, total_denominator - observed_cells)
    if observed_cells > total_denominator:
        raise ValueError(f"Expected at most 99 scientific cells, got {observed_cells}")

    valid_cells = 0
    degenerate_cells = missing_cells
    favorable_cells = 0
    spearman_positive_cells = 0

    ba_deltas = []
    spearman_values = []
    year_deltas = {}  # year -> list of deltas (only valid ones)

    for r in all_results:
        # A cell is defined by a ticker and outer test month
        # Let's extract year
        test_month = r.get("test_month", "")
        year = test_month[:4] if test_month else ""

        is_cell_degen = r.get("sci_cell_degenerate", True)

        if is_cell_degen or r.get("status") != "completed":
            degenerate_cells += 1
            # Degenerate cell is NOT favorable, and delta is not recorded in the medians
        else:
            valid_cells += 1
            delta = r.get("sci_ba_delta", 0.0)
            if not np.isnan(delta):
                ba_deltas.append(delta)
                if year:
                    year_deltas.setdefault(year, []).append(delta)
                if delta > 0.0:
                    favorable_cells += 1

            sp = r.get("sci_p1_spearman", 0.0)
            if not np.isnan(sp):
                spearman_values.append(sp)
                if sp > 0.0:
                    spearman_positive_cells += 1

    # Wilcoxon signed-rank test on paired deltas (excluding zeros)
    wilcoxon_stat = float("nan")
    wilcoxon_pval = float("nan")
    wilcoxon_n = 0
    wilcoxon_status = "no_data"

    if ba_deltas:
        try:
            ba_arr = np.array(ba_deltas)
            nonzero = ba_arr[ba_arr != 0.0]
            wilcoxon_n = len(nonzero)
            if wilcoxon_n >= 10:
                stat, pval = wilcoxon(nonzero)
                wilcoxon_stat = float(stat)
                wilcoxon_pval = float(pval)
                wilcoxon_status = "success"
            else:
                wilcoxon_status = "insufficient_nonzero_pairs"
        except Exception as e:
            wilcoxon_status = f"error: {e}"

    sci = {
        "observed_scientific_cells": observed_cells,
        "missing_scientific_cells": missing_cells,
        "valid_scientific_cells": valid_cells,
        "degenerate_scientific_cells": degenerate_cells,
        "favorable_cells": favorable_cells,
        "total_denominator": total_denominator,
        "ba_delta_positive_rate": round(favorable_cells / total_denominator, 4),
        "ba_delta_median": round(float(np.median(ba_deltas)), 4) if ba_deltas else float("nan"),
        "ba_delta_mean": round(float(np.mean(ba_deltas)), 4) if ba_deltas else float("nan"),
        "spearman_positive_rate": round(spearman_positive_cells / total_denominator, 4),
        "spearman_median": round(float(np.median(spearman_values)), 4) if spearman_values else float("nan"),
        "wilcoxon_statistic": wilcoxon_stat,
        "wilcoxon_pvalue": wilcoxon_pval,
        "wilcoxon_n_nonzero": wilcoxon_n,
        "wilcoxon_status": wilcoxon_status,
    }

    # Per-year evidence
    favorable_years = 0
    for y in ["2023", "2024", "2025"]:
        deltas = year_deltas.get(y, [])
        y_median = float(np.median(deltas)) if deltas else float("nan")
        sci[f"year_{y}_ba_delta_median"] = round(y_median, 4) if deltas else float("nan")
        y_denom = 27 if y == "2023" else 36
        y_fav = sum(1 for d in deltas if d > 0.0)
        sci[f"year_{y}_ba_delta_positive_rate"] = round(y_fav / y_denom, 4)
        sci[f"year_{y}_cells"] = y_denom
        sci[f"year_{y}_valid_cells"] = len(deltas)
        if deltas and y_median > 0.0:
            favorable_years += 1

    sci["favorable_years"] = favorable_years
    sci["favorable_years_required"] = 3

    sci["scientific_pass"] = (
        sci["ba_delta_positive_rate"] >= 0.60
        and sci["ba_delta_median"] > 0.0
        and sci["spearman_positive_rate"] >= 0.60
        and sci["spearman_median"] > 0.0
        and favorable_years >= 3
    )

    return sci


def compute_economic_criteria(all_results: list[dict]) -> dict:
    """Compute predeclared economic success criteria.

    Per ticker × outer month, P1 must achieve:
      PF >= 1.3, WR >= 50%, trades >= 18, PnL > 0, each hold >= 30m.

    Reports: pooled PF, worst-month PF, worst-month PnL, minimum monthly trades,
    positive-month rate, max drawdown.
    Does NOT average monthly PFs as primary criterion.
    """
    econ = {}
    for arm in ["c0", "p1"]:
        arm_cells = []
        for r in all_results:
            if r.get("status") != "completed":
                arm_cells.append({
                    "ticker": r.get("ticker", ""), "month": r.get("test_month", ""),
                    "pf": float("nan"), "wr": float("nan"), "trades": 0, "pnl": 0.0,
                    "min_hold": float("nan"), "gross_profit": 0.0, "gross_loss": 0.0,
                    "trade_records": [], "pass": False, "reason": "not_completed",
                })
                continue
            arm_data = r.get(arm, {})
            if not arm_data.get("valid_inner", False):
                arm_cells.append({
                    "ticker": r["ticker"], "month": r["test_month"],
                    "pf": float("nan"), "wr": float("nan"), "trades": 0, "pnl": 0.0,
                    "min_hold": float("nan"), "gross_profit": 0.0, "gross_loss": 0.0,
                    "trade_records": [], "pass": False, "reason": "abstain",
                })
                continue

            tm = arm_data.get("test_metrics", {})
            diag = arm_data.get("diagnostics", {})
            pf = tm.get("profit_factor", 0)
            wr = tm.get("win_rate", 0)
            trades = tm.get("trades", 0)
            pnl = diag.get("pnl", 0)
            min_hold = diag.get("min_hold_minutes", 0)

            cell_pass = (
                (pf >= 1.3 or pf == float("inf"))
                and wr >= 0.50
                and trades >= 18
                and pnl > 0.0
                and min_hold >= 30.0
            )
            arm_cells.append({
                "ticker": r["ticker"], "month": r["test_month"],
                "pf": pf, "wr": wr, "trades": trades, "pnl": pnl,
                "min_hold": min_hold,
                "gross_profit": float(diag.get("gross_profit", 0.0)),
                "gross_loss": float(diag.get("gross_loss", 0.0)),
                "trade_records": list(diag.get("outer_trade_records", [])),
                "pass": cell_pass,
            })

        passing = [c for c in arm_cells if c.get("pass", False)]
        # Abstentions have undefined mathematical PF, but are an economic
        # failure; the effective worst-month PF is therefore reported as 0.
        effective_pfs = [float(c["pf"]) if np.isfinite(c["pf"]) else 0.0 for c in arm_cells]
        pnls_valid = [float(c["pnl"]) for c in arm_cells]
        trades_valid = [int(c["trades"]) for c in arm_cells]

        econ[f"{arm}_total_cells"] = len(arm_cells)
        econ[f"{arm}_passing_cells"] = len(passing)
        econ[f"{arm}_pass_rate"] = round(len(passing) / max(1, len(arm_cells)), 4)
        econ[f"{arm}_worst_month_pf"] = round(min(effective_pfs), 4) if effective_pfs else float("nan")
        econ[f"{arm}_worst_month_pnl"] = round(min(pnls_valid), 4) if pnls_valid else float("nan")
        econ[f"{arm}_min_monthly_trades"] = min(trades_valid) if trades_valid else 0
        econ[f"{arm}_positive_month_rate"] = round(sum(1 for p in pnls_valid if p > 0) / max(1, len(pnls_valid)), 4)

        # Pooled PF uses gross trade profits/losses, never monthly net PnL.
        gross_profit = sum(float(c["gross_profit"]) for c in arm_cells)
        gross_loss = sum(float(c["gross_loss"]) for c in arm_cells)
        records = [record for cell in arm_cells for record in cell["trade_records"]]
        records.sort(key=lambda x: (str(x["date"]), int(x["minute"]), str(x["ticker"])))
        if not records:
            econ[f"{arm}_pooled_pf"] = None
        elif gross_loss > 0:
            econ[f"{arm}_pooled_pf"] = round(gross_profit / gross_loss, 4)
        else:
            econ[f"{arm}_pooled_pf"] = float("inf")
        returns = np.asarray([float(record["realized_return"]) for record in records], dtype=float)
        if len(returns):
            equity = np.cumsum(returns)
            peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
            econ[f"{arm}_max_drawdown"] = round(float((equity - peak).min()), 4)
        else:
            econ[f"{arm}_max_drawdown"] = 0.0

    return econ


def main() -> int:
    parser = argparse.ArgumentParser(description="Pairwise Opportunity & Side Selection V1")
    parser.add_argument("--dataset", type=str, required=True, help="Path to sealed parquet")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "QQQ", "SPY"])
    parser.add_argument("--dry-run", action="store_true", help="Just validate setup without running")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load and validate dataset ───────────────────────────────────────
    print(f"Loading dataset: {dataset_path}")
    df = pd.read_parquet(dataset_path)
    df["trade_date"] = df["trade_date"].astype(str)

    # 2026 seal assertion
    assert (df["trade_date"] <= "20251231").all(), "FATAL: 2026 data in sealed dataset"
    assert (df["trade_date"] >= "20220101").all(), "FATAL: pre-2022 data"
    print(f"  Rows: {len(df):,}, range: {df['trade_date'].min()}..{df['trade_date'].max()}")

    # SHA-256
    dataset_sha = sha256_file(dataset_path)
    print(f"  SHA-256: {dataset_sha}")

    # ── Generate folds ──────────────────────────────────────────────────
    folds = generate_folds(FIRST_TEST_MONTH, LAST_TEST_MONTH)
    print(f"  Folds: {len(folds)} ({folds[0]['test_month']}..{folds[-1]['test_month']})")

    # ── Feature allowlist audit ─────────────────────────────────────────
    expected_diff = len(DIFF_METRICS)  # 6
    expected_changes = (len(DIFF_METRICS) - 1) * len(CHANGE_LAGS)  # 5 metrics * 3 lags = 15 (oi excluded)
    expected_total = len(COMMON_FEATURES) + expected_diff + expected_changes
    print(f"  Feature allowlist: {len(COMMON_FEATURES)} common + {expected_diff} diffs + {expected_changes} changes = {expected_total}")
    print(f"  First allowed minute: {FIRST_ALLOWED_MINUTE} (minute > 630, 5m grid)")

    if args.dry_run:
        print("\n[DRY RUN] Setup validated. Exiting without running folds.")
        # Write config
        config = {
            "dataset": str(dataset_path),
            "dataset_sha256": dataset_sha,
            "folds": len(folds),
            "tickers": args.tickers,
            "lgb_params": FROZEN_LGB_PARAMS,
            "seed": FROZEN_SEED,
            "head_offsets": {
                "C0_CALL": HEAD_OFFSET_C0_CALL,
                "C0_PUT": HEAD_OFFSET_C0_PUT,
                "P1_OPP": HEAD_OFFSET_P1_OPP,
                "P1_SIDE": HEAD_OFFSET_P1_SIDE,
            },
            "trade_thresholds": TRADE_THRESHOLDS,
            "side_margins": SIDE_MARGINS,
            "inner_gates": {
                "min_pf": INNER_MIN_PF, "min_wr": INNER_MIN_WR,
                "min_trades_per_month": INNER_MIN_TRADES_PER_MONTH,
                "min_hold_minutes": INNER_MIN_HOLD_MINUTES,
            },
            "ticker_config": TICKER_CONFIG,
            "common_features": COMMON_FEATURES,
            "diff_metrics": DIFF_METRICS,
            "change_lags": CHANGE_LAGS,
            "first_allowed_minute": FIRST_ALLOWED_MINUTE,
            "c0_definition": "In-protocol nested absolute-head baseline. Labels: call_win_label=int(call_return>0), put_win_label=int(put_return>0).",
            "p1_definition": "Pairwise opportunity + side classifier. Labels: opportunity_label=int(max(call_return,put_return)>0), side_label=int(call_return>put_return).",
            "scientific_criteria": {
                "ba_delta_positive_rate >= 0.60": True,
                "ba_delta_median > 0": True,
                "spearman_positive_rate >= 0.60": True,
                "spearman_median > 0": True,
                "favorable_evidence_2023_2024_2025": True,
            },
            "economic_criteria": {
                "per_ticker_per_month": "PF>=1.3, WR>=50%, trades>=18, PnL>0, hold>=30m",
                "no_averaged_monthly_pf": True,
            },
        }
        with open(output_dir / "run_config.json", "w") as f:
            json.dump(config, f, indent=2, default=str)
        print(f"  Config written to: {output_dir / 'run_config.json'}")
        return 0

    # ── Run all folds ───────────────────────────────────────────────────
    all_results = []
    global_feature_hash = None
    global_feature_cols: list[str] = []

    for ticker in args.tickers:
        tcfg = TICKER_CONFIG[ticker]
        bucket = tcfg["bucket"]
        print(f"\n{'='*60}")
        print(f"TICKER: {ticker} (bucket=d{bucket}, cap={tcfg['max_trades_per_day']}, cooldown={tcfg['cooldown_minutes']}m)")
        print(f"{'='*60}")

        # Filter to ticker
        tdf = df[df["ticker"] == ticker].copy()
        if tdf.empty:
            print(f"  No data for {ticker}, skipping")
            continue

        # Entry window filter: minute > 630 (first candidate = 635 on 5m grid)
        tdf["minute"] = pd.to_numeric(tdf["minute"], errors="coerce")
        tdf = tdf[tdf["minute"] > 630].copy()

        # Build features and labels
        tdf, feature_cols = build_diff_features(tdf, ticker, bucket)
        tdf = build_labels(tdf, bucket)

        # Feature hash — assert parity across tickers (same allowlist)
        feature_hash = compute_feature_hash(feature_cols)
        if global_feature_hash is None:
            global_feature_hash = feature_hash
            global_feature_cols = list(feature_cols)
        else:
            assert feature_hash == global_feature_hash, (
                f"Feature hash mismatch across tickers! "
                f"Expected {global_feature_hash}, got {feature_hash} for {ticker}. "
                f"C0 and P1 must receive exactly the same feature allowlist."
            )

        print(f"  Prepared: {len(tdf):,} rows, {len(feature_cols)} features")
        print(f"  Feature hash: {feature_hash}")
        print(f"  Features: {feature_cols[:5]} ... ({len(feature_cols)} total)")

        for fold in folds:
            result = run_fold(ticker, fold, tdf, feature_cols, feature_hash, tcfg, output_dir)
            all_results.append(result)

            # Print summary
            c0_s = result.get("c0", {})
            p1_s = result.get("p1", {})
            c0_pnl = c0_s.get("test_metrics", {}).get("pnl_return", 0) if isinstance(c0_s, dict) else 0
            p1_pnl = p1_s.get("test_metrics", {}).get("pnl_return", 0) if isinstance(p1_s, dict) else 0
            c0_valid = c0_s.get("valid_inner", False) if isinstance(c0_s, dict) else False
            p1_valid = p1_s.get("valid_inner", False) if isinstance(p1_s, dict) else False
            print(f"    C0: valid={c0_valid} pnl={c0_pnl:.3f} | P1: valid={p1_valid} pnl={p1_pnl:.3f}")

    # ── Write aggregate results ─────────────────────────────────────────
    all_folds_df = pd.json_normalize(all_results, sep="_")
    all_folds_df.to_csv(output_dir / "all_folds.csv", index=False)

    selected_rows = []
    outer_metric_rows = []
    diagnostic_rows = []
    prevalence_rows = []
    outer_trade_rows = []
    selected_policies: list[dict[str, Any]] = []
    threshold_rows = []
    for result in all_results:
        common = {"ticker": result.get("ticker"), "test_month": result.get("test_month")}
        prevalence_rows.append({
            **common,
            "opportunity_prevalence": result.get("opportunity_prevalence"),
            "side_prevalence": result.get("side_prevalence"),
            "call_win_prevalence": result.get("call_win_prevalence"),
            "put_win_prevalence": result.get("put_win_prevalence"),
        })
        diagnostic_rows.append({
            **common,
            **{key: value for key, value in result.items() if key.startswith("sci_") or key.startswith("scientific_mask_")},
        })
        for arm in ("c0", "p1"):
            arm_result = result.get(arm, {}) if isinstance(result.get(arm), dict) else {}
            selected = {
                **common,
                "arm": arm.upper(),
                "status": result.get("status"),
                "valid_inner": bool(arm_result.get("valid_inner", False)),
                "trade_threshold": arm_result.get("trade_threshold"),
                "side_margin": arm_result.get("side_margin"),
            }
            selected_rows.append(selected)
            selected_policies.append({
                **selected,
                "train_months": result.get("train_months"),
                "inner_months": result.get("inner_months"),
                "feature_hash": result.get("feature_hash"),
                "seed_call": arm_result.get("seed_call"),
                "seed_put": arm_result.get("seed_put"),
                "seed_opp": arm_result.get("seed_opp"),
                "seed_side": arm_result.get("seed_side"),
            })
            test_metrics = arm_result.get("test_metrics", {}) if isinstance(arm_result.get("test_metrics"), dict) else {}
            diagnostics = arm_result.get("diagnostics", {}) if isinstance(arm_result.get("diagnostics"), dict) else {}
            outer_metric_rows.append({
                **common, "arm": arm.upper(), "valid_inner": selected["valid_inner"],
                **{f"metric_{key}": value for key, value in test_metrics.items()},
                **{f"diagnostic_{key}": value for key, value in diagnostics.items() if key != "outer_trade_records"},
            })
            details = arm_result.get("selection_details", {}) if isinstance(arm_result.get("selection_details"), dict) else {}
            threshold_rows.append({
                **selected,
                "rank_key": json.dumps(details.get("rank_key"), default=str),
                "inner_total_trades": details.get("total_trades"),
                "inner_total_pnl": details.get("total_pnl"),
                "gate_details": json.dumps(details.get("gate_details", {}), sort_keys=True, default=str),
            })
            for record in diagnostics.get("outer_trade_records", []):
                outer_trade_rows.append({**common, "arm": arm.upper(), **record})

    pd.DataFrame(selected_rows).to_csv(output_dir / "selected_folds.csv", index=False)
    pd.DataFrame(outer_metric_rows).to_csv(output_dir / "outer_metrics.csv", index=False)
    pd.DataFrame(diagnostic_rows).to_csv(output_dir / "diagnostic_metrics.csv", index=False)
    pd.DataFrame(prevalence_rows).to_csv(output_dir / "class_prevalence.csv", index=False)
    pd.DataFrame(threshold_rows).to_csv(output_dir / "threshold_grid_results.csv", index=False)
    pd.DataFrame(outer_trade_rows).to_csv(output_dir / "outer_trades.csv", index=False)
    with open(output_dir / "selected_policies.json", "w") as f:
        json.dump(selected_policies, f, indent=2, default=str)
    with open(output_dir / "feature_manifest.json", "w") as f:
        json.dump({
            "feature_hash": global_feature_hash,
            "features": global_feature_cols,
            "c0_p1_identical_matrix": True,
            "first_allowed_minute": FIRST_ALLOWED_MINUTE,
        }, f, indent=2)
    with open(output_dir / "fold_manifest.json", "w") as f:
        json.dump({
            "scientific_cells_expected": 99,
            "folds": [
                {
                    "ticker": r.get("ticker"), "test_month": r.get("test_month"),
                    "train_months": r.get("train_months"), "inner_months": r.get("inner_months"),
                    "status": r.get("status"), "sci_cell_degenerate": r.get("sci_cell_degenerate", True),
                }
                for r in all_results
            ],
        }, f, indent=2, default=str)

    # Scientific criteria
    sci = compute_scientific_criteria(all_results)
    with open(output_dir / "scientific_criteria.json", "w") as f:
        json.dump(sci, f, indent=2, default=str)

    # Economic criteria
    econ = compute_economic_criteria(all_results)
    with open(output_dir / "economic_criteria.json", "w") as f:
        json.dump(econ, f, indent=2, default=str)

    # Aggregate report
    agg = {
        "dataset_sha256": dataset_sha,
        "feature_hash": global_feature_hash,
        "first_allowed_minute": FIRST_ALLOWED_MINUTE,
        "total_folds": len(all_results),
        "folds_completed": sum(1 for r in all_results if r.get("status") == "completed"),
        "scientific_criteria": sci,
        "economic_criteria": econ,
    }
    for arm in ["c0", "p1"]:
        valid_folds = [r for r in all_results if r.get(arm, {}).get("valid_inner", False)]
        if valid_folds:
            pnls = [r[arm]["test_metrics"]["pnl_return"] for r in valid_folds]
            pfs = [r[arm]["test_metrics"]["profit_factor"] for r in valid_folds if np.isfinite(r[arm]["test_metrics"]["profit_factor"])]
            wrs = [r[arm]["test_metrics"]["win_rate"] for r in valid_folds if np.isfinite(r[arm]["test_metrics"]["win_rate"])]
            trades = [r[arm]["test_metrics"]["trades"] for r in valid_folds]
            agg[f"{arm}_valid_folds"] = len(valid_folds)
            agg[f"{arm}_median_pnl"] = round(float(np.median(pnls)), 4)
            agg[f"{arm}_total_trades"] = int(sum(trades))
            agg[f"{arm}_pass_rate"] = round(len(valid_folds) / max(1, len(all_results)), 4)
        else:
            agg[f"{arm}_valid_folds"] = 0
            agg[f"{arm}_pass_rate"] = 0.0

    with open(output_dir / "aggregate_report.json", "w") as f:
        json.dump(agg, f, indent=2, default=str)

    report_lines = [
        "# PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1 — Results",
        "",
        f"- Dataset SHA-256: `{dataset_sha}`",
        f"- Feature hash: `{global_feature_hash}`",
        f"- Scientific cells: `{sci['total_denominator']}`",
        f"- Degenerate scientific cells: `{sci['degenerate_scientific_cells']}`",
        f"- Scientific pass: `{sci['scientific_pass']}`",
        f"- C0 economic passing cells: `{econ['c0_passing_cells']}/99`",
        f"- P1 economic passing cells: `{econ['p1_passing_cells']}/99`",
        f"- C0 pooled PF: `{econ['c0_pooled_pf']}`",
        f"- P1 pooled PF: `{econ['p1_pooled_pf']}`",
        "- Production modified: `false`",
        "- 2026 opened: `false`",
    ]
    (output_dir / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"\n{'='*60}")
    print("AGGREGATE SUMMARY")
    print(f"{'='*60}")
    for key, val in agg.items():
        if isinstance(val, dict):
            print(f"  {key}:")
            for k2, v2 in val.items():
                print(f"    {k2}: {v2}")
        else:
            print(f"  {key}: {val}")

    print(f"\nResults written to: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
