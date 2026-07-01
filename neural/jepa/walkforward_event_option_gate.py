from __future__ import annotations

import argparse
import json
import math
import pickle
from dataclasses import asdict, dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_add, month_range


LEAKY_PATTERNS = (
    "future",
    "spot_long",
    "spot_short",
    "spot_best",
    "_opt_win",
    "_opt_status",
    "_opt_exit_ret",
    "_opt_exit_minutes",
    "_opt_max_ret",
    "_opt_min_ret",
)


@dataclass(frozen=True)
class DeployConfig:
    threshold: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"thr{self.threshold:.3f}_maxday{max_day}"


def metrics(trades: pd.DataFrame, expected_months: list[str] | None = None) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_return": 0.0,
            "avg_return": float("nan"),
            "max_drawdown": 0.0,
            "call_rate": float("nan"),
            "days_with_trades": 0,
            "daily_win_rate": float("nan"),
            "median_daily_return": float("nan"),
            "daily_max_drawdown": 0.0,
            "top5_day_return": 0.0,
            "top5_share_of_pnl": float("nan"),
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
        }
    ret = trades["realized_return"].astype(float).to_numpy()
    ret = np.nan_to_num(ret, nan=0.0, posinf=0.0, neginf=0.0)
    wins = ret[ret > 0.0]
    losses = ret[ret < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(ret)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    by_month = trades.groupby("month")["realized_return"].agg(["count", "sum"])
    if expected_months is not None:
        by_month = by_month.reindex([str(m) for m in expected_months], fill_value=0)
    daily = trades.groupby("date")["realized_return"].sum().astype(float).sort_index()
    daily_equity = daily.cumsum().to_numpy(dtype=float)
    daily_peak = np.maximum.accumulate(np.insert(daily_equity, 0, 0.0))[1:] if len(daily_equity) else np.array([])
    top5_day_return = float(daily.nlargest(min(5, len(daily))).sum()) if len(daily) else 0.0
    total_return = float(ret.sum())
    return {
        "trades": int(len(trades)),
        "win_rate": float((ret > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_return": total_return,
        "avg_return": float(ret.mean()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "call_rate": float((trades["action"].astype(str) == "CALL").mean()),
        "days_with_trades": int(len(daily)),
        "daily_win_rate": float((daily > 0.0).mean()) if len(daily) else float("nan"),
        "median_daily_return": float(daily.median()) if len(daily) else float("nan"),
        "daily_max_drawdown": float((daily_equity - daily_peak).min()) if len(daily_equity) else 0.0,
        "top5_day_return": top5_day_return,
        "top5_share_of_pnl": float(top5_day_return / total_return) if total_return != 0.0 else float("nan"),
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
    }


def score_metrics(
    row: dict,
    min_trades: int,
    min_month_trades: int,
    min_pf: float = 0.0,
    min_win_rate: float = 0.0,
    min_call_rate: float = 0.20,
    max_call_rate: float = 0.80,
) -> float:
    trades = int(row.get("trades", 0))
    min_month = int(row.get("min_month_trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    win_rate = float(row.get("win_rate", float("nan")))
    call_rate = float(row.get("call_rate", float("nan")))
    if trades < int(min_trades) or min_month < int(min_month_trades):
        return -1e18 + trades
    if not np.isfinite(pf) or not np.isfinite(win_rate) or not np.isfinite(call_rate):
        return -1e18 + trades
    if pf < float(min_pf) or win_rate < float(min_win_rate):
        return -1e18 + trades
    if call_rate < float(min_call_rate) or call_rate > float(max_call_rate):
        return -1e18 + trades
    pnl = float(row.get("pnl_return", 0.0))
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        3.0 * math.log1p(min(max(pf, 0.0), 10.0))
        + 0.45 * math.log1p(trades)
        + pnl / 10.0
        - dd / 5.0
        + positive_month_rate
    )


def score_selection_metrics(row: dict, args: argparse.Namespace) -> float:
    score = score_metrics(
        row,
        int(args.min_val_trades),
        int(args.min_month_trades),
        float(args.min_val_pf),
        float(args.min_val_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if score <= -1e17:
        return float(score)

    positive_month_rate = float(row.get("positive_month_rate", float("nan")))
    if not np.isfinite(positive_month_rate) or positive_month_rate < float(args.min_val_positive_month_rate):
        return -1e18 + int(row.get("trades", 0))

    daily_win_rate = float(row.get("daily_win_rate", float("nan")))
    if not np.isfinite(daily_win_rate) or daily_win_rate < float(args.min_val_daily_win_rate):
        return -1e18 + int(row.get("trades", 0))

    median_daily_return = float(row.get("median_daily_return", float("nan")))
    if (
        np.isfinite(float(args.min_val_median_daily_return))
        and (not np.isfinite(median_daily_return) or median_daily_return < float(args.min_val_median_daily_return))
    ):
        return -1e18 + int(row.get("trades", 0))

    top5_share = float(row.get("top5_share_of_pnl", float("nan")))
    if np.isfinite(float(args.max_val_top5_share)) and np.isfinite(top5_share):
        if top5_share > float(args.max_val_top5_share):
            return -1e18 + int(row.get("trades", 0))

    daily_drawdown = abs(float(row.get("daily_max_drawdown", 0.0)))
    if np.isfinite(float(args.max_val_daily_drawdown)) and daily_drawdown > float(args.max_val_daily_drawdown):
        return -1e18 + int(row.get("trades", 0))

    return float(score)


def prepare_frame(path: str | Path, args: argparse.Namespace) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if getattr(args, "expiry_modes", None):
        allowed_expiry_modes = {str(mode) for mode in args.expiry_modes}
        df = df[df["expiry_mode"].astype(str).isin(allowed_expiry_modes)].copy()
    df["month"] = df["trade_date"].astype(str).str[:6]
    df["date"] = df["trade_date"].astype(str)
    df["call_return"] = pd.to_numeric(df[f"call_d{int(args.delta_bucket):02d}_opt_exit_ret"], errors="coerce")
    df["put_return"] = pd.to_numeric(df[f"put_d{int(args.delta_bucket):02d}_opt_exit_ret"], errors="coerce")
    df = df[np.isfinite(df["call_return"]) & np.isfinite(df["put_return"])].copy()
    if float(args.clip_return) > 0.0:
        df["call_return"] = df["call_return"].clip(-float(args.clip_return), float(args.clip_return))
        df["put_return"] = df["put_return"].clip(-float(args.clip_return), float(args.clip_return))
    return df.reset_index(drop=True)


def build_features(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    work = df.copy()
    cats = [c for c in ["ticker", "expiry_mode", "nearest_level_name"] if c in work.columns]
    if cats:
        work = pd.concat([work, pd.get_dummies(work[cats].astype(str), prefix=cats, dtype=float)], axis=1)
    include_prefixes = tuple(str(x).lower() for x in getattr(args, "feature_include_prefixes", []) if str(x).strip())
    exclude_prefixes = tuple(str(x).lower() for x in getattr(args, "feature_exclude_prefixes", []) if str(x).strip())
    dummy_prefixes = tuple(f"{c}_" for c in cats)
    selected: list[str] = []
    for col in work.columns:
        low = str(col).lower()
        if col in {
            "trade_date",
            "date",
            "expiration",
            "timestamp",
            "time",
            "underlying_ticker",
            "nearest_level_name",
            "expiry_mode",
            "call_return",
            "put_return",
        }:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if exclude_prefixes and low.startswith(exclude_prefixes):
            continue
        if include_prefixes and not (low.startswith(include_prefixes) or low.startswith(dummy_prefixes)):
            continue
        if pd.api.types.is_numeric_dtype(work[col]):
            selected.append(col)
    return work, selected


def deploy(scored: pd.DataFrame, cfg: DeployConfig, cooldown_minutes: int) -> pd.DataFrame:
    candidates = scored[scored["score"].astype(float) >= float(cfg.threshold)].copy()
    if candidates.empty:
        return candidates
    rows: list[dict] = []
    for _, day in candidates.sort_values(["date", "minute", "score"], ascending=[True, True, False]).groupby("date", sort=False):
        next_allowed = -1
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            if taken >= int(cfg.max_trades_per_day):
                break
            values = row._asdict()
            values["deploy_config"] = cfg.name
            rows.append(values)
            taken += 1
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(rows) if rows else candidates.iloc[0:0].copy()


def fit_predict_fold(
    ticker: str,
    test_month: str,
    frame: pd.DataFrame,
    feature_cols: list[str],
    args: argparse.Namespace,
    grid: list[DeployConfig],
) -> tuple[pd.DataFrame, dict] | None:
    val_months = prior_validation_months(test_month, args)
    first_val = val_months[0]
    if bool(args.pooled_train):
        train_tickers = [str(t).upper() for t in getattr(args, "train_tickers", [])]
        train_mask = frame["month"].astype(str) < first_val
        if train_tickers:
            train_mask &= frame["ticker"].astype(str).isin(train_tickers)
        train = frame[train_mask].copy()
        val = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str).isin(val_months))].copy()
        test = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str) == str(test_month))].copy()
    else:
        tdf = frame[frame["ticker"].astype(str) == ticker].copy()
        train = tdf[tdf["month"].astype(str) < first_val].copy()
        val = tdf[tdf["month"].astype(str).isin(val_months)].copy()
        test = tdf[tdf["month"].astype(str) == str(test_month)].copy()
    if len(train) < int(args.min_train_rows) or len(val) < int(args.min_val_rows) or test.empty:
        return None
    train_months = sorted(str(month) for month in train["month"].astype(str).unique())
    fold_identity = {
        "ticker": ticker,
        "month": str(test_month),
        "test_month": str(test_month),
        "train_months": ",".join(train_months),
        "train_month_max": train_months[-1] if train_months else "",
        "first_val_month": str(first_val),
        "val_months": ",".join(val_months),
        "val_month_max": val_months[-1] if val_months else "",
    }

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    label_mode = str(getattr(args, "label_mode", "return")).lower()
    if label_mode == "win":
        y_call = (train["call_return"].astype(float) > 0.0).astype(int)
        y_put = (train["put_return"].astype(float) > 0.0).astype(int)
    else:
        y_call = train["call_return"].astype(float)
        y_put = train["put_return"].astype(float)
    params = dict(
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed) + int(test_month[-2:]),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    if label_mode == "win":
        call_model = lgb.LGBMClassifier(**{**params, "objective": "binary"})
        put_model = lgb.LGBMClassifier(**{**params, "objective": "binary", "random_state": int(params["random_state"]) + 10_000})
    else:
        call_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective)})
        put_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective), "random_state": int(params["random_state"]) + 10_000})
    call_model.fit(x_train, y_call)
    put_model.fit(x_train, y_put)

    def score_part(part: pd.DataFrame) -> pd.DataFrame:
        if part.empty:
            return part.copy()
        x = part[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out = part.copy()
        if label_mode == "win":
            out["pred_call_return"] = call_model.predict_proba(x)[:, 1]
            out["pred_put_return"] = put_model.predict_proba(x)[:, 1]
        else:
            out["pred_call_return"] = call_model.predict(x)
            out["pred_put_return"] = put_model.predict(x)
        call_action = out["pred_call_return"].astype(float) >= out["pred_put_return"].astype(float)
        out["action"] = np.where(call_action, "CALL", "PUT")
        out["score"] = np.where(call_action, out["pred_call_return"], out["pred_put_return"])
        out["realized_return"] = np.where(call_action, out["call_return"], out["put_return"])
        return out

    val_scored = score_part(val)
    test_scored = score_part(test)
    fold_grid = build_fold_grid(val_scored, args)
    best_cfg = fold_grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in fold_grid:
        val_trades = deploy(val_scored, cfg, int(args.cooldown_minutes))
        row = metrics(val_trades, val_months)
        score = score_selection_metrics(row, args)
        if score > best_score:
            best_cfg = cfg
            best_score = score
            best_metrics = row
    valid_val_selection = bool(best_score > -1e17)
    if not valid_val_selection and not bool(args.allow_invalid_val_deploy):
        fold_row = {
            **fold_identity,
            "deploy_config": "ABSTAIN_INVALID_VAL",
            "train_rows": int(len(train)),
            "val_rows": int(len(val)),
            "test_rows": int(len(test)),
            "val_score": float(best_score),
            "abstained_invalid_val": True,
            **{f"val_{k}": v for k, v in best_metrics.items()},
            **{f"test_{k}": v for k, v in metrics(pd.DataFrame(), [str(test_month)]).items()},
        }
        print(
            f"[EVENT_GATE] {ticker} {test_month} abstain invalid_val "
            f"best_cfg={best_cfg.name} val_score={best_score:.1f}",
            flush=True,
        )
        return pd.DataFrame(), fold_row
    test_trades = deploy(test_scored, best_cfg, int(args.cooldown_minutes))
    test_metrics = metrics(test_trades, [str(test_month)])
    if not test_trades.empty:
        test_trades["test_month"] = str(test_month)
    fold_row = {
        **fold_identity,
        "deploy_config": best_cfg.name,
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "val_score": float(best_score),
        "abstained_invalid_val": False,
        **{f"val_{k}": v for k, v in best_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    print(
        f"[EVENT_GATE] {ticker} {test_month} cfg={best_cfg.name} "
        f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_trades={test_metrics.get('trades', 0)} "
        f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_ret={test_metrics.get('pnl_return', 0.0):.2f}",
        flush=True,
    )
    keep_cols = [
        "ticker",
        "date",
        "month",
        "time",
        "minute",
        "expiry_mode",
        "action",
        "score",
        "pred_call_return",
        "pred_put_return",
        "call_return",
        "put_return",
        "realized_return",
        "deploy_config",
        "test_month",
    ]
    return test_trades[[c for c in keep_cols if c in test_trades.columns]].copy(), fold_row


def build_grid(thresholds: list[float], max_days: list[int]) -> list[DeployConfig]:
    return [DeployConfig(float(thr), int(max_day)) for thr in thresholds for max_day in max_days]


def build_fold_grid(scored_val: pd.DataFrame, args: argparse.Namespace) -> list[DeployConfig]:
    thresholds = [float(thr) for thr in args.threshold_grid]
    quantiles = [float(q) for q in getattr(args, "threshold_quantiles", [])]
    if quantiles and not scored_val.empty and "score" in scored_val.columns:
        finite = pd.to_numeric(scored_val["score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(finite):
            thresholds.extend(float(value) for value in np.quantile(finite, quantiles))
    thresholds = sorted(set(round(float(thr), 8) for thr in thresholds if np.isfinite(float(thr))))
    return build_grid(thresholds, [int(max_day) for max_day in args.max_day_grid])


def excluded_months(args: argparse.Namespace) -> set[str]:
    return {str(month) for month in getattr(args, "exclude_months", []) if str(month).strip()}


def prior_validation_months(test_month: str, args: argparse.Namespace) -> list[str]:
    excluded = excluded_months(args)
    out: list[str] = []
    offset = 1
    while len(out) < int(args.val_months):
        month = month_add(test_month, -offset)
        if month not in excluded:
            out.append(month)
        offset += 1
        if offset > 240:
            raise RuntimeError(f"Could not build validation window for {test_month}; exclude_months={sorted(excluded)}")
    return list(reversed(out))


def fit_direction_models(
    train: pd.DataFrame,
    feature_cols: list[str],
    args: argparse.Namespace,
    *,
    seed_offset: int = 0,
) -> tuple[object, object, pd.Series]:
    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    label_mode = str(getattr(args, "label_mode", "return")).lower()
    if label_mode == "win":
        y_call = (train["call_return"].astype(float) > 0.0).astype(int)
        y_put = (train["put_return"].astype(float) > 0.0).astype(int)
    else:
        y_call = train["call_return"].astype(float)
        y_put = train["put_return"].astype(float)
    params = dict(
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed) + int(seed_offset),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    if label_mode == "win":
        call_model = lgb.LGBMClassifier(**{**params, "objective": "binary"})
        put_model = lgb.LGBMClassifier(**{**params, "objective": "binary", "random_state": int(params["random_state"]) + 10_000})
    else:
        call_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective)})
        put_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective), "random_state": int(params["random_state"]) + 10_000})
    call_model.fit(x_train, y_call)
    put_model.fit(x_train, y_put)
    return call_model, put_model, medians


def score_direction_models(
    frame: pd.DataFrame,
    feature_cols: list[str],
    args: argparse.Namespace,
    call_model: object,
    put_model: object,
    medians: pd.Series,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    x = frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    out = frame.copy()
    label_mode = str(getattr(args, "label_mode", "return")).lower()
    if label_mode == "win":
        out["pred_call_return"] = call_model.predict_proba(x)[:, 1]
        out["pred_put_return"] = put_model.predict_proba(x)[:, 1]
    else:
        out["pred_call_return"] = call_model.predict(x)
        out["pred_put_return"] = put_model.predict(x)
    call_action = out["pred_call_return"].astype(float) >= out["pred_put_return"].astype(float)
    out["action"] = np.where(call_action, "CALL", "PUT")
    out["score"] = np.where(call_action, out["pred_call_return"], out["pred_put_return"])
    if {"call_return", "put_return"}.issubset(out.columns):
        out["realized_return"] = np.where(call_action, out["call_return"], out["put_return"])
    return out


def choose_deploy_config(scored_select: pd.DataFrame, select_months: list[str], args: argparse.Namespace) -> tuple[DeployConfig, dict, float]:
    fold_grid = build_fold_grid(scored_select, args)
    best_cfg = fold_grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in fold_grid:
        trades = deploy(scored_select, cfg, int(args.cooldown_minutes))
        row = metrics(trades, select_months)
        score = score_selection_metrics(row, args)
        if score > best_score:
            best_cfg = cfg
            best_score = float(score)
            best_metrics = row
    return best_cfg, best_metrics, float(best_score)


def export_deploy_model(output_dir: Path, frame: pd.DataFrame, feature_cols: list[str], args: argparse.Namespace) -> None:
    deploy_month = str(args.deploy_month).strip()
    if not deploy_month:
        raise RuntimeError("--export-deploy-model requires --deploy-month")
    deploy_select_end_month = str(args.deploy_select_end_month).strip()
    if deploy_select_end_month and deploy_select_end_month >= deploy_month:
        raise RuntimeError(f"--deploy-select-end-month {deploy_select_end_month} must be earlier than deploy month {deploy_month}")

    excluded = excluded_months(args)
    all_months = [month for month in sorted(frame["month"].astype(str).unique().tolist()) if month not in excluded]
    previous = [m for m in all_months if m < deploy_month and (not deploy_select_end_month or m <= deploy_select_end_month)]
    select_n = int(args.val_months)
    if len(previous) <= select_n:
        raise RuntimeError(f"Not enough prior months to export deploy model for {deploy_month}: {previous}")
    train_months = previous[:-select_n]
    select_months = previous[-select_n:]
    test_tickers = [str(t).upper() for t in args.tickers]
    train_tickers = [str(t).upper() for t in args.train_tickers] if args.train_tickers else test_tickers
    if bool(args.pooled_train):
        train = frame[(frame["month"].astype(str).isin(train_months)) & (frame["ticker"].astype(str).isin(train_tickers))].copy()
    else:
        train = frame[(frame["month"].astype(str).isin(train_months)) & (frame["ticker"].astype(str).isin(test_tickers))].copy()
    select = frame[(frame["month"].astype(str).isin(select_months)) & (frame["ticker"].astype(str).isin(test_tickers))].copy()
    if len(train) < int(args.min_train_rows):
        raise RuntimeError(f"Deploy train rows {len(train)} < min_train_rows {args.min_train_rows}")
    if len(select) < int(args.min_val_rows):
        raise RuntimeError(f"Deploy select rows {len(select)} < min_val_rows {args.min_val_rows}")

    call_model, put_model, medians = fit_direction_models(train, feature_cols, args, seed_offset=int(deploy_month[-2:]))
    scored_select = score_direction_models(select, feature_cols, args, call_model, put_model, medians)
    cfg, select_metrics, select_score = choose_deploy_config(scored_select, select_months, args)
    if float(select_score) <= -1e17 and not bool(args.allow_invalid_val_deploy):
        raise RuntimeError(
            "Deploy event-option gate selection failed validation for "
            f"{deploy_month} using select_months={select_months}; "
            "pass --allow-invalid-val-deploy only for diagnostics."
        )

    payload = {
        "schema_version": 1,
        "component": "event_option_gate_direction_model",
        "deploy_month": deploy_month,
        "deploy_select_end_month": deploy_select_end_month or None,
        "tickers": test_tickers,
        "train_tickers": train_tickers,
        "train_months": train_months,
        "select_months": select_months,
        "deploy_config": asdict(cfg),
        "deploy_config_name": cfg.name,
        "select_score": float(select_score),
        "select_metrics": select_metrics,
        "feature_cols": feature_cols,
        "feature_medians": {str(k): float(v) if np.isfinite(float(v)) else 0.0 for k, v in medians.fillna(0.0).items()},
        "args": vars(args),
    }
    deploy_dir = output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    with (deploy_dir / "event_option_gate_direction_model.pkl").open("wb") as fh:
        pickle.dump(
            {
                "call_model": call_model,
                "put_model": put_model,
                "medians": medians,
                "feature_cols": feature_cols,
                "metadata": payload,
            },
            fh,
        )
    (deploy_dir / "event_option_gate_direction_model.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    scored_select.to_csv(deploy_dir / "deploy_select_scored_rows.csv", index=False)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, metadata: dict) -> None:
    args_meta = metadata.get("args", {})
    excluded = {str(month) for month in args_meta.get("exclude_months", []) if str(month).strip()}
    expected = [month for month in month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month"))) if month not in excluded]
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# Event Option Gate Walk-Forward",
        "",
        "Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## Per Ticker",
        "",
        "```json",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Fold Configs",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (output_dir / "metrics.json").write_text(
        json.dumps({"overall": overall, "per_ticker": per_ticker, "metadata": metadata}, indent=2, allow_nan=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward event-level option return gate.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument(
        "--train-tickers",
        nargs="+",
        default=[],
        help="Optional pooled-training ticker universe. Validation/test still use --tickers only.",
    )
    parser.add_argument(
        "--expiry-modes",
        nargs="+",
        default=[],
        help="Optional causal filter on known expiry_mode values, e.g. zero_dte or front_weekly.",
    )
    parser.add_argument("--start-month", default="202510")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=2)
    parser.add_argument("--pooled-train", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--delta-bucket", type=int, default=25)
    parser.add_argument(
        "--label-mode",
        choices=["return", "win"],
        default="return",
        help="Train return regressors or win-probability classifiers for CALL/PUT selection.",
    )
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--min-train-rows", type=int, default=500)
    parser.add_argument("--min-val-rows", type=int, default=30)
    parser.add_argument("--min-val-trades", type=int, default=20)
    parser.add_argument("--min-month-trades", type=int, default=3)
    parser.add_argument("--min-val-pf", type=float, default=0.0)
    parser.add_argument("--min-val-win-rate", type=float, default=0.0)
    parser.add_argument("--min-val-positive-month-rate", type=float, default=0.0)
    parser.add_argument("--min-val-daily-win-rate", type=float, default=0.0)
    parser.add_argument("--min-val-median-daily-return", type=float, default=float("-inf"))
    parser.add_argument("--max-val-top5-share", type=float, default=float("inf"))
    parser.add_argument("--max-val-daily-drawdown", type=float, default=float("inf"))
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=240)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-0.05, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 8, 4, 2, 1])
    parser.add_argument("--feature-include-prefixes", nargs="*", default=[], help="If set, keep only feature columns with these prefixes plus categorical one-hot columns.")
    parser.add_argument("--feature-exclude-prefixes", nargs="*", default=[], help="Drop feature columns with these prefixes.")
    parser.add_argument("--allow-invalid-val-deploy", action="store_true", help="Deploy the best validation config even if it fails validation constraints.")
    parser.add_argument("--deploy-month", default="")
    parser.add_argument(
        "--deploy-select-end-month",
        default="",
        help="Optional latest completed YYYYMM allowed for deploy validation selection. Use this to exclude partial months.",
    )
    parser.add_argument("--export-deploy-model", action="store_true")
    parser.add_argument("--exclude-months", nargs="*", default=[], help="Months to remove from train/validation/test windows, e.g. raw-partial months.")
    parser.add_argument("--skip-walkforward", action="store_true", help="Only build features/export deploy model; skip historical fold replay.")
    parser.add_argument("--resume", action="store_true", help="Skip ticker/month folds already present in output fold_configs.csv.")
    parser.add_argument("--seed", type=int, default=20260617)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = prepare_frame(args.data, args)
    test_tickers = [str(t).upper() for t in args.tickers]
    train_tickers = [str(t).upper() for t in args.train_tickers] if args.train_tickers else test_tickers
    raw = raw[raw["ticker"].isin(sorted(set(test_tickers) | set(train_tickers)))].copy()
    excluded = excluded_months(args)
    if excluded:
        raw = raw[~raw["month"].astype(str).isin(excluded)].copy()
    frame, feature_cols = build_features(raw, args)
    months = [m for m in sorted(frame["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]
    grid = build_grid(args.threshold_grid, args.max_day_grid)
    metadata = {
        "args": vars(args),
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "grid": [asdict(cfg) for cfg in grid],
        "data_rows": int(len(frame)),
    }
    all_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    completed_folds: set[tuple[str, str]] = set()
    fold_file = output_dir / "fold_configs.csv"
    trade_file = output_dir / "event_option_gate_trades.csv"
    if bool(args.resume) and fold_file.exists():
        existing_folds = pd.read_csv(fold_file, dtype={"ticker": str, "month": str})
        if not existing_folds.empty and {"ticker", "month"}.issubset(existing_folds.columns):
            existing_folds["ticker"] = existing_folds["ticker"].astype(str).str.upper()
            existing_folds["month"] = existing_folds["month"].astype(str)
            fold_rows = existing_folds.to_dict("records")
            completed_folds = set(zip(existing_folds["ticker"], existing_folds["month"]))
        if trade_file.exists():
            existing_trades = pd.read_csv(trade_file, dtype={"ticker": str, "month": str, "test_month": str, "date": str})
            if not existing_trades.empty:
                all_trades.append(existing_trades)
        if completed_folds:
            print(f"[resume] loaded {len(completed_folds)} completed folds from {fold_file}")
    if not bool(args.skip_walkforward):
        for ticker in test_tickers:
            for test_month in months:
                if (str(ticker).upper(), str(test_month)) in completed_folds:
                    print(f"[resume] skip ticker={ticker} month={test_month}")
                    continue
                result = fit_predict_fold(ticker, str(test_month), frame, feature_cols, args, grid)
                if result is None:
                    continue
                trades, fold = result
                if not trades.empty:
                    all_trades.append(trades)
                fold_rows.append(fold)
                trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
                fold_df = pd.DataFrame(fold_rows)
                if not trade_df.empty:
                    trade_df.to_csv(output_dir / "event_option_gate_trades.csv", index=False)
                fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
                write_summary(output_dir, trade_df, fold_df, metadata)
    trade_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    fold_df = pd.DataFrame(fold_rows)
    if not trade_df.empty:
        trade_df.to_csv(output_dir / "event_option_gate_trades.csv", index=False)
    fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
    write_summary(output_dir, trade_df, fold_df, metadata)
    if bool(args.export_deploy_model):
        export_deploy_model(output_dir, frame, feature_cols, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
