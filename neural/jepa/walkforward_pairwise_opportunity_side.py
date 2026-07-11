"""
PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1
Walk-forward evaluation: hierarchical opportunity + side classifier vs absolute baseline.

Arms:
  C0 — absolute CALL/PUT classifiers (current production logic)
  P1 — opportunity classifier + pairwise side classifier

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
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
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
    colsample_bytree=0.8,
    reg_lambda=1.0,
    n_jobs=4,
    verbose=-1,
    objective="binary",
    importance_type="gain",
)
FROZEN_SEED = 42
FROZEN_CLIP_RETURN = 10.0  # not used for classification but kept for parity

# ── Ticker configuration ────────────────────────────────────────────────
TICKER_CONFIG: dict[str, dict[str, Any]] = {
    "SPXW": {"bucket": 25, "max_trades_per_day": 4, "cooldown_minutes": 0},
    "QQQ":  {"bucket": 35, "max_trades_per_day": 2, "cooldown_minutes": 30},
    "SPY":  {"bucket": 35, "max_trades_per_day": 1, "cooldown_minutes": 0},
}

# ── Threshold grid (predeclared) ────────────────────────────────────────
TRADE_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
SIDE_MARGINS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

# ── Walk-forward configuration ──────────────────────────────────────────
TRAIN_MONTHS_COUNT = 12
VAL_MONTHS_COUNT = 3
FIRST_TEST_MONTH = "202304"
LAST_TEST_MONTH = "202512"
MIN_TRAIN_ROWS = 500
MIN_VAL_ROWS = 50

# ── Inner validation gates ──────────────────────────────────────────────
INNER_MIN_PF = 1.3
INNER_MIN_WR = 0.50
INNER_MIN_TRADES_PER_MONTH = 18
INNER_MIN_HOLD_MINUTES = 30  # not applicable to classifier but documented

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


def build_diff_features(df: pd.DataFrame, ticker: str, bucket: int) -> tuple[pd.DataFrame, list[str]]:
    """Build call-put difference features and backward-looking changes.
    
    Differences are computed per-row. Changes use shift grouped by
    (ticker, trade_date) to avoid cross-session contamination.
    NaN initial values are left as NaN (filled with train median at fit time).
    """
    work = df.copy()
    diff_cols = []

    for metric in DIFF_METRICS:
        call_col = f"call_d{bucket:02d}_{metric}"
        put_col = f"put_d{bucket:02d}_{metric}"
        if call_col not in work.columns or put_col not in work.columns:
            raise KeyError(f"Missing source column: {call_col} or {put_col}")
        diff_name = f"{metric}_diff"
        work[diff_name] = pd.to_numeric(work[call_col], errors="coerce") - pd.to_numeric(work[put_col], errors="coerce")
        diff_cols.append(diff_name)

    # Backward-looking changes grouped by (ticker, trade_date) — no cross-session
    change_cols = []
    # Must sort by minute within each day for correct shift
    work = work.sort_values(["trade_date", "minute"]).copy()
    for diff_name in diff_cols:
        grouped = work.groupby(["trade_date"])[diff_name]
        for lag, label in CHANGE_LAGS:
            chg_name = f"{diff_name}_chg_{label}"
            work[chg_name] = work[diff_name] - grouped.shift(lag)
            change_cols.append(chg_name)

    all_feature_cols = COMMON_FEATURES + diff_cols + change_cols
    return work, all_feature_cols


def build_labels(df: pd.DataFrame, bucket: int) -> pd.DataFrame:
    """Build opportunity and side labels from call/put exit returns."""
    work = df.copy()
    call_ret_col = f"call_d{bucket:02d}_opt_exit_ret"
    put_ret_col = f"put_d{bucket:02d}_opt_exit_ret"
    call_exit_min_col = f"call_d{bucket:02d}_opt_exit_minutes"
    put_exit_min_col = f"put_d{bucket:02d}_opt_exit_minutes"

    call_ret = pd.to_numeric(work[call_ret_col], errors="coerce")
    put_ret = pd.to_numeric(work[put_ret_col], errors="coerce")

    work["call_return"] = call_ret
    work["put_return"] = put_ret
    work["opportunity_label"] = (np.maximum(call_ret, put_ret) > 0).astype(int)
    work["side_advantage"] = call_ret - put_ret
    work["side_label"] = (work["side_advantage"] > 0).astype(int)

    # exit_minutes for deploy (non-overlap logic)
    if call_exit_min_col in work.columns and put_exit_min_col in work.columns:
        call_exit = pd.to_numeric(work[call_exit_min_col], errors="coerce")
        put_exit = pd.to_numeric(work[put_exit_min_col], errors="coerce")
        # Will be assigned per-trade based on chosen side
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


def apply_absolute_policy(
    scored: pd.DataFrame,
    threshold: float,
    bucket: int,
) -> pd.DataFrame:
    """Apply C0 absolute policy: pick side with higher predicted return, threshold on score.
    
    Sets score, action, realized_return, exit_minutes columns for deploy().
    """
    work = scored.copy()
    pred_call = work["pred_call_return"].astype(float)
    pred_put = work["pred_put_return"].astype(float)
    is_call = pred_call >= pred_put

    work["action"] = np.where(is_call, "CALL", "PUT")
    work["score"] = np.where(is_call, pred_call, pred_put)
    work["realized_return"] = np.where(is_call, work["call_return"], work["put_return"])

    call_exit_col = f"call_d{bucket:02d}_opt_exit_minutes"
    put_exit_col = f"put_d{bucket:02d}_opt_exit_minutes"
    if call_exit_col in work.columns and put_exit_col in work.columns:
        work["exit_minutes"] = np.where(
            is_call,
            pd.to_numeric(work[call_exit_col], errors="coerce"),
            pd.to_numeric(work[put_exit_col], errors="coerce"),
        )

    # Filter by threshold
    work = work[work["score"].astype(float) >= threshold].copy()
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

        passes = (
            n >= INNER_MIN_TRADES_PER_MONTH
            and pf >= INNER_MIN_PF
            and wr >= INNER_MIN_WR
            and pnl > 0
        )
        month_details[m] = {
            "trades": n, "pf": round(pf, 4), "wr": round(wr, 4),
            "pnl": round(pnl, 4), "pass": passes,
        }
        if not passes:
            all_pass = False

    return all_pass, {"months": month_details}


def select_best_config_p1(
    scored_val: pd.DataFrame,
    inner_months: list[str],
    config: dict,
    bucket: int,
) -> tuple[float, float, bool, dict]:
    """Sweep trade_threshold × side_margin for P1. Return best (trade_thr, side_margin, valid, details)."""
    cooldown = config["cooldown_minutes"]
    max_day = config["max_trades_per_day"]
    
    candidates = []
    for tt in TRADE_THRESHOLDS:
        for sm in SIDE_MARGINS:
            applied = apply_pairwise_policy(scored_val, tt, sm, bucket)
            if applied.empty:
                continue
            cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
            # Score is already set; deploy uses it for ranking/filtering
            # Set threshold to 0 since we already filtered by p_trade >= tt
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
) -> tuple[float, bool, dict]:
    """Sweep threshold for C0 baseline. Return best (threshold, valid, details)."""
    cooldown = config["cooldown_minutes"]
    max_day = config["max_trades_per_day"]
    
    # C0 uses the same threshold grid as trade_threshold
    candidates = []
    for thr in TRADE_THRESHOLDS:
        applied = apply_absolute_policy(scored_val, thr, bucket)
        if applied.empty:
            continue
        cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
        traded = deploy(applied, cfg, cooldown)
        if traded.empty:
            continue
        
        passes, gate_details = compute_monthly_inner_gates(traded, inner_months)
        if not passes:
            continue
        
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
            min(monthly_pnl),
            min(monthly_pf),
            min(monthly_wr),
            min(monthly_trades),
            total_pnl,
            total_trades,
            thr,
        )

        candidates.append({
            "threshold": thr,
            "rank_key": rank_key,
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "gate_details": gate_details,
        })
    
    if not candidates:
        return 0.5, False, {"reason": "no_valid_config"}

    candidates.sort(key=lambda c: c["rank_key"], reverse=True)
    best = candidates[0]
    return best["threshold"], True, best


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

    tie_mask = side_adv.abs() <= 1e-9
    diag["tie_rate"] = round(float(tie_mask.mean()), 4)

    if arm == "P1" and "p_trade" in scored.columns and "p_call" in scored.columns:
        from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score, balanced_accuracy_score

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

        # Side metrics — B: over traded candidates only
        if not traded.empty and "p_call" in traded.columns:
            traded_opp_pos = traded[
                (np.maximum(traded["call_return"].astype(float), traded["put_return"].astype(float)) > 0)
                & (traded["call_return"].astype(float) - traded["put_return"].astype(float)).abs() > 1e-9
            ] if len(traded) > 0 else pd.DataFrame()
            if len(traded_opp_pos) > 5:
                p_call_traded = traded_opp_pos["p_call"].astype(float)
                side_true_traded = (traded_opp_pos["call_return"].astype(float) > traded_opp_pos["put_return"].astype(float)).astype(int)
                pred_side_traded = (p_call_traded >= 0.5).astype(int)
                try:
                    diag["side_accuracy_B"] = round(float((pred_side_traded == side_true_traded).mean()), 4)
                    diag["side_balanced_accuracy_B"] = round(float(balanced_accuracy_score(side_true_traded, pred_side_traded)), 4)
                except Exception:
                    pass

    # Post-PnL diagnostics (from traded)
    if not traded.empty:
        ret = traded["realized_return"].astype(float).to_numpy()
        diag["executed_trades"] = int(len(traded))
        diag["wr"] = round(float((ret > 0).mean()), 4)
        wins = ret[ret > 0]
        losses = ret[ret < 0]
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
    else:
        diag["executed_trades"] = 0
        diag["wr"] = float("nan")
        diag["pf"] = float("nan")
        diag["pnl"] = 0.0
        diag["abstention_rate"] = 1.0

    return diag


# ═══════════════════════════════════════════════════════════════════════
# CONSTANT-SIDE AND ORACLE-SIDE BASELINES
# ═══════════════════════════════════════════════════════════════════════

def constant_side_baseline(
    scored: pd.DataFrame,
    train_data: pd.DataFrame,
    threshold: float,
    config: dict,
    bucket: int,
) -> pd.DataFrame:
    """Constant-side baseline: fit best side from train data, apply to scored."""
    # Determine dominant side from training data
    call_wr_train = float((train_data["call_return"].astype(float) > 0).mean())
    put_wr_train = float((train_data["put_return"].astype(float) > 0).mean())
    best_side = "CALL" if call_wr_train >= put_wr_train else "PUT"
    
    work = scored.copy()
    work["action"] = best_side
    if best_side == "CALL":
        work["score"] = work.get("p_trade", work.get("pred_call_return", pd.Series(0.5, index=work.index))).astype(float)
        work["realized_return"] = work["call_return"]
        exit_col = f"call_d{bucket:02d}_opt_exit_minutes"
    else:
        work["score"] = work.get("p_trade", work.get("pred_put_return", pd.Series(0.5, index=work.index))).astype(float)
        work["realized_return"] = work["put_return"]
        exit_col = f"put_d{bucket:02d}_opt_exit_minutes"
    
    if exit_col in work.columns:
        work["exit_minutes"] = pd.to_numeric(work[exit_col], errors="coerce")
    
    work = work[work["score"].astype(float) >= threshold].copy()
    return work


def oracle_side_baseline(
    scored: pd.DataFrame,
    threshold: float,
    config: dict,
    bucket: int,
) -> pd.DataFrame:
    """Oracle-side baseline: always pick the better side (diagnostic only)."""
    work = scored.copy()
    is_call = work["call_return"].astype(float) >= work["put_return"].astype(float)
    work["action"] = np.where(is_call, "CALL", "PUT")
    work["score"] = work.get("p_trade", pd.Series(0.5, index=work.index)).astype(float)
    work["realized_return"] = np.where(is_call, work["call_return"], work["put_return"])
    
    call_exit = f"call_d{bucket:02d}_opt_exit_minutes"
    put_exit = f"put_d{bucket:02d}_opt_exit_minutes"
    if call_exit in work.columns and put_exit in work.columns:
        work["exit_minutes"] = np.where(
            is_call,
            pd.to_numeric(work[call_exit], errors="coerce"),
            pd.to_numeric(work[put_exit], errors="coerce"),
        )
    
    work = work[work["score"].astype(float) >= threshold].copy()
    return work


# ═══════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════

def run_fold(
    ticker: str,
    fold: dict,
    prepared: pd.DataFrame,
    feature_cols: list[str],
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
    }

    if len(train) < MIN_TRAIN_ROWS or len(val) < MIN_VAL_ROWS or test.empty:
        result["status"] = "insufficient_rows"
        result["c0"] = {"status": "insufficient_rows"}
        result["p1"] = {"status": "insufficient_rows"}
        return result

    # Prepare features
    train_medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    
    def fill_features(df: pd.DataFrame) -> pd.DataFrame:
        return df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(train_medians).fillna(0.0)

    X_train = fill_features(train)
    X_val = fill_features(val)
    X_test = fill_features(test)

    seed_offset = int(test_month[-2:]) + hash(ticker) % 10000
    lgb_seed = FROZEN_SEED + seed_offset

    # ── C0: Absolute baseline ───────────────────────────────────────────
    # Train call and put classifiers
    y_call_train = (train["call_return"].astype(float) > 0).astype(int)
    y_put_train = (train["put_return"].astype(float) > 0).astype(int)

    c0_call_model = lgb.LGBMClassifier(**{**FROZEN_LGB_PARAMS, "random_state": lgb_seed})
    c0_put_model = lgb.LGBMClassifier(**{**FROZEN_LGB_PARAMS, "random_state": lgb_seed + 10000})
    c0_call_model.fit(X_train, y_call_train)
    c0_put_model.fit(X_train, y_put_train)

    # Score validation and test
    val_c0 = val.copy()
    val_c0["pred_call_return"] = c0_call_model.predict_proba(X_val)[:, 1]
    val_c0["pred_put_return"] = c0_put_model.predict_proba(X_val)[:, 1]

    test_c0 = test.copy()
    test_c0["pred_call_return"] = c0_call_model.predict_proba(X_test)[:, 1]
    test_c0["pred_put_return"] = c0_put_model.predict_proba(X_test)[:, 1]

    # Select best threshold for C0
    best_thr_c0, valid_c0, c0_sel_details = select_best_config_c0(
        val_c0, inner_months, config, bucket,
    )

    # Deploy C0 on test
    if valid_c0:
        test_c0_applied = apply_absolute_policy(test_c0, best_thr_c0, bucket)
        c0_cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
        test_c0_traded = deploy(test_c0_applied, c0_cfg, cooldown) if not test_c0_applied.empty else test_c0_applied
        c0_test_metrics = metrics(test_c0_traded, [test_month])
        c0_diag = compute_diagnostics(test_c0, test_c0_traded, "C0", bucket)
    else:
        test_c0_traded = pd.DataFrame()
        c0_test_metrics = metrics(pd.DataFrame(), [test_month])
        c0_diag = {"arm": "C0", "status": "abstain", "reason": "no_valid_inner_config"}

    result["c0"] = {
        "threshold": best_thr_c0,
        "valid_inner": valid_c0,
        "test_metrics": c0_test_metrics,
        "diagnostics": c0_diag,
        "selection_details": c0_sel_details if isinstance(c0_sel_details, dict) else {},
    }

    # ── P1: Pairwise opportunity + side ─────────────────────────────────
    # Train opportunity classifier (all rows)
    y_opp_train = train["opportunity_label"].astype(int)

    # Train side classifier (only opportunity-positive, no ties)
    side_train_mask = (
        (train["opportunity_label"] == 1)
        & (train["side_advantage"].astype(float).abs() > 1e-9)
    )
    side_train = train[side_train_mask]
    X_side_train = fill_features(side_train)
    y_side_train = side_train["side_label"].astype(int)

    p1_opp_model = lgb.LGBMClassifier(**{**FROZEN_LGB_PARAMS, "random_state": lgb_seed + 20000})
    p1_side_model = lgb.LGBMClassifier(**{**FROZEN_LGB_PARAMS, "random_state": lgb_seed + 30000})
    p1_opp_model.fit(X_train, y_opp_train)

    if len(X_side_train) < 50:
        result["p1"] = {"status": "insufficient_side_train_rows", "side_train_rows": len(X_side_train)}
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
    }

    # ── Diagnostic baselines ────────────────────────────────────────────
    # Constant-side (using C0 threshold if valid, else 0.5)
    cs_thr = best_thr_c0 if valid_c0 else 0.5
    cs_applied = constant_side_baseline(test_c0, train, cs_thr, config, bucket)
    cs_cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
    cs_traded = deploy(cs_applied, cs_cfg, cooldown) if not cs_applied.empty else cs_applied
    cs_metrics_val = metrics(cs_traded, [test_month])
    result["constant_side"] = cs_metrics_val

    # Oracle-side (diagnostic)
    oracle_thr = best_tt if valid_p1 else (best_thr_c0 if valid_c0 else 0.5)
    oracle_applied = oracle_side_baseline(test_p1 if valid_p1 else test_c0, oracle_thr, config, bucket)
    oracle_cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
    oracle_traded = deploy(oracle_applied, oracle_cfg, cooldown) if not oracle_applied.empty else oracle_applied
    oracle_metrics_val = metrics(oracle_traded, [test_month])
    result["oracle_side"] = oracle_metrics_val

    # ── Logistic Regression diagnostic ──────────────────────────────────
    try:
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        X_test_scaled = scaler.transform(X_test)

        lr_opp = LogisticRegression(max_iter=1000, random_state=lgb_seed + 40000, C=1.0)
        lr_side = LogisticRegression(max_iter=1000, random_state=lgb_seed + 50000, C=1.0)

        lr_opp.fit(X_train_scaled, y_opp_train)
        if len(X_side_train) >= 50:
            X_side_scaled = scaler.transform(X_side_train)
            lr_side.fit(X_side_scaled, y_side_train)

            test_lr = test.copy()
            test_lr["p_trade"] = lr_opp.predict_proba(X_test_scaled)[:, 1]
            test_lr["p_call"] = lr_side.predict_proba(X_test_scaled)[:, 1]

            # Use P1's selected thresholds for LR diagnostic
            if valid_p1:
                lr_applied = apply_pairwise_policy(test_lr, best_tt, best_sm, bucket)
                lr_cfg = DeployConfig(threshold=0.0, max_trades_per_day=max_day)
                lr_traded = deploy(lr_applied, lr_cfg, cooldown) if not lr_applied.empty else lr_applied
                lr_metrics_val = metrics(lr_traded, [test_month])
                result["logistic_regression"] = lr_metrics_val
            else:
                result["logistic_regression"] = {"status": "p1_abstained"}
        else:
            result["logistic_regression"] = {"status": "insufficient_side_train"}
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

    # Save fold trades
    if not test_p1_traded.empty:
        trade_export_cols = ["date", "month", "minute", "action", "score", "realized_return"]
        trade_export_cols = [c for c in trade_export_cols if c in test_p1_traded.columns]
        test_p1_traded[trade_export_cols].to_csv(fold_dir / "p1_trades.csv", index=False)
    if not test_c0_traded.empty:
        trade_export_cols = ["date", "month", "minute", "action", "score", "realized_return"]
        trade_export_cols = [c for c in trade_export_cols if c in test_c0_traded.columns]
        test_c0_traded[trade_export_cols].to_csv(fold_dir / "c0_trades.csv", index=False)

    # Save fold summary
    with open(fold_dir / "fold_summary.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    result["status"] = "completed"
    return result


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
    print(f"  Feature allowlist: {len(COMMON_FEATURES)} common + 6 diffs + 18 changes = {len(COMMON_FEATURES) + 24}")

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
            "trade_thresholds": TRADE_THRESHOLDS,
            "side_margins": SIDE_MARGINS,
            "inner_gates": {
                "min_pf": INNER_MIN_PF, "min_wr": INNER_MIN_WR,
                "min_trades_per_month": INNER_MIN_TRADES_PER_MONTH,
            },
            "ticker_config": TICKER_CONFIG,
            "common_features": COMMON_FEATURES,
            "diff_metrics": DIFF_METRICS,
            "change_lags": CHANGE_LAGS,
        }
        with open(output_dir / "run_config.json", "w") as f:
            json.dump(config, f, indent=2, default=str)
        print(f"  Config written to: {output_dir / 'run_config.json'}")
        return 0

    # ── Run all folds ───────────────────────────────────────────────────
    all_results = []
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

        # Entry window filter: minute > 630 (after 10:30 ET)
        tdf["minute"] = pd.to_numeric(tdf["minute"], errors="coerce")
        tdf = tdf[tdf["minute"] > 630].copy()

        # Build features and labels
        tdf, feature_cols = build_diff_features(tdf, ticker, bucket)
        tdf = build_labels(tdf, bucket)

        print(f"  Prepared: {len(tdf):,} rows, {len(feature_cols)} features")
        print(f"  Features: {feature_cols[:5]} ... ({len(feature_cols)} total)")

        for fold in folds:
            result = run_fold(ticker, fold, tdf, feature_cols, tcfg, output_dir)
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

    # Aggregate report
    agg = {
        "dataset_sha256": dataset_sha,
        "total_folds": len(all_results),
        "folds_completed": sum(1 for r in all_results if r.get("status") == "completed"),
    }
    for arm in ["c0", "p1"]:
        valid_folds = [r for r in all_results if r.get(arm, {}).get("valid_inner", False)]
        if valid_folds:
            pnls = [r[arm]["test_metrics"]["pnl_return"] for r in valid_folds]
            pfs = [r[arm]["test_metrics"]["profit_factor"] for r in valid_folds if np.isfinite(r[arm]["test_metrics"]["profit_factor"])]
            wrs = [r[arm]["test_metrics"]["win_rate"] for r in valid_folds if np.isfinite(r[arm]["test_metrics"]["win_rate"])]
            trades = [r[arm]["test_metrics"]["trades"] for r in valid_folds]
            agg[f"{arm}_valid_folds"] = len(valid_folds)
            agg[f"{arm}_mean_pnl"] = round(float(np.mean(pnls)), 4)
            agg[f"{arm}_median_pnl"] = round(float(np.median(pnls)), 4)
            agg[f"{arm}_mean_pf"] = round(float(np.mean(pfs)), 4) if pfs else float("nan")
            agg[f"{arm}_mean_wr"] = round(float(np.mean(wrs)), 4) if wrs else float("nan")
            agg[f"{arm}_total_trades"] = int(sum(trades))
            agg[f"{arm}_pass_rate"] = round(len(valid_folds) / max(1, len(all_results)), 4)
        else:
            agg[f"{arm}_valid_folds"] = 0
            agg[f"{arm}_pass_rate"] = 0.0

    with open(output_dir / "aggregate_report.json", "w") as f:
        json.dump(agg, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print("AGGREGATE SUMMARY")
    print(f"{'='*60}")
    for key, val in agg.items():
        print(f"  {key}: {val}")

    print(f"\nResults written to: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
