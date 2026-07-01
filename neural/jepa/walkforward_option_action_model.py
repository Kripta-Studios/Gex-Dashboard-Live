from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_add, month_range
from walkforward_option_delta_from_candidates import metrics


LEAKY_PATTERNS = (
    "rule_exit",
    "rule_hold",
    "rule_pnl",
    "rule_return",
    "hold180",
    "oracle",
    "future",
    "label",
    "outcome",
    "path_points",
)


@dataclass(frozen=True)
class DeployConfig:
    threshold: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"thr{self.threshold:.4f}_maxday{max_day}"


def add_targets(df: pd.DataFrame, clip_return: float) -> pd.DataFrame:
    out = df.copy()
    out["target_return"] = pd.to_numeric(out["rule_return_on_risk"], errors="coerce").astype(float)
    if float(clip_return) > 0.0:
        out["target_return_clipped"] = out["target_return"].clip(-float(clip_return), float(clip_return))
    else:
        out["target_return_clipped"] = out["target_return"]
    signal_mean = out.groupby("signal_id")["target_return"].transform("mean")
    signal_max = out.groupby("signal_id")["target_return"].transform("max")
    out["target_advantage"] = (out["target_return"] - signal_mean).astype(float)
    if float(clip_return) > 0.0:
        out["target_advantage_clipped"] = out["target_advantage"].clip(-float(clip_return), float(clip_return))
    else:
        out["target_advantage_clipped"] = out["target_advantage"]
    out["target_is_best_delta"] = np.isclose(out["target_return"], signal_max).astype(np.int8)
    out["target_win"] = (out["target_return"] > 0.0).astype(np.int8)
    out["target_signal_best_return"] = signal_max.astype(float)
    return out


def feature_columns(df: pd.DataFrame) -> list[str]:
    selected: list[str] = []
    skip = {
        "candidate_id",
        "signal_id",
        "ticker",
        "date",
        "month",
        "time",
        "side",
        "level_config",
        "target_return",
        "target_return_clipped",
        "target_advantage",
        "target_advantage_clipped",
        "target_is_best_delta",
        "target_win",
        "target_signal_best_return",
    }
    for col in df.columns:
        low = str(col).lower()
        if col in skip:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            selected.append(col)
    return selected


def apply_max_day(trades: pd.DataFrame, max_day: int) -> pd.DataFrame:
    if trades.empty or int(max_day) >= 999:
        return trades.copy()
    rows: list[dict] = []
    for _, day in trades.sort_values(["date", "time", "score"], ascending=[True, True, False]).groupby("date", sort=False):
        rows.extend([row._asdict() for row in day.itertuples(index=False)][: int(max_day)])
    return pd.DataFrame(rows) if rows else trades.iloc[0:0].copy()


def candidate_to_trades(selected: pd.DataFrame, policy: str) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "policy": policy,
            "candidate_id": selected["candidate_id"].astype(int),
            "signal_id": selected["signal_id"].astype(int),
            "ticker": selected["ticker"].astype(str),
            "date": selected["date"].astype(str),
            "month": selected["month"].astype(str),
            "time": selected["time"].astype(str),
            "side": selected["side"].astype(str),
            "delta_target": selected["delta_target"].astype(float),
            "actual_delta_abs": selected["actual_delta_abs"].astype(float),
            "actual_strike": selected["actual_strike"].astype(float),
            "entry_premium": selected["entry_premium"].astype(float),
            "contracts": selected["contracts"].astype(int),
            "rule_exit_reason": selected["rule_exit_reason"].astype(str),
            "rule_exit_time": selected["rule_exit_time"].astype(str),
            "rule_hold_minutes": selected["rule_hold_minutes"].astype(int),
            "rule_pnl_pct": selected["rule_pnl_pct"].astype(float),
            "rule_pnl_dollars": selected["rule_pnl_dollars"].astype(float),
            "rule_return_on_risk": selected["rule_return_on_risk"].astype(float),
            "score": selected["score"].astype(float),
            "pred_return": selected.get("pred_return", np.nan),
            "pred_advantage": selected.get("pred_advantage", np.nan),
            "pred_win": selected.get("pred_win", np.nan),
            "pred_best": selected.get("pred_best", np.nan),
        }
    )
    return out


def select_by_score(scored: pd.DataFrame, cfg: DeployConfig, policy: str) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    work = scored.sort_values(["signal_id", "score"]).groupby("signal_id", sort=False).tail(1)
    work = work[work["score"].astype(float) >= float(cfg.threshold)].copy()
    work = apply_max_day(work, int(cfg.max_trades_per_day))
    if not work.empty:
        work["deploy_config"] = cfg.name
    return candidate_to_trades(work, policy)


def score_metrics(row: dict, min_trades: int, min_month_trades: int) -> float:
    trades = int(row.get("trades", 0))
    min_month = int(row.get("min_month_trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    long_rate = float(row.get("long_rate", float("nan")))
    if trades < int(min_trades) or min_month < int(min_month_trades):
        return -1e18 + trades
    if not np.isfinite(pf) or not np.isfinite(long_rate):
        return -1e18 + trades
    if long_rate < 0.20 or long_rate > 0.80:
        return -1e18 + trades
    pnl = float(row.get("pnl_dollars", 0.0))
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        3.5 * math.log1p(min(max(pf, 0.0), 10.0))
        + 0.45 * math.log1p(trades)
        + pnl / 15_000.0
        - dd / 15_000.0
        + positive_month_rate
    )


def build_deploy_grid(scored_val: pd.DataFrame, args: argparse.Namespace) -> list[DeployConfig]:
    finite = scored_val["score"].astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    thresholds = list(args.threshold_grid)
    if len(finite):
        thresholds.extend([float(x) for x in np.quantile(finite, [0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80])])
    thresholds = sorted(set(round(float(t), 8) for t in thresholds))
    return [DeployConfig(float(thr), int(max_day)) for thr in thresholds for max_day in args.max_day_grid]


def fit_models(train: pd.DataFrame, features: list[str], args: argparse.Namespace):
    medians = train[features].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[features].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    params = dict(
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    ret_model = None
    adv_model = None
    win_model = None
    best_model = None
    if "return" in args.score_components:
        ret_model = lgb.LGBMRegressor(objective=str(args.regression_objective), **params)
        ret_model.fit(x_train, train["target_return_clipped"].astype(float))
    if "advantage" in args.score_components:
        adv_model = lgb.LGBMRegressor(objective=str(args.regression_objective), **{**params, "random_state": int(args.seed) + 101})
        adv_model.fit(x_train, train["target_advantage_clipped"].astype(float))
    if "win" in args.score_components and train["target_win"].nunique() > 1:
        win_model = lgb.LGBMClassifier(objective="binary", class_weight="balanced", **{**params, "random_state": int(args.seed) + 202})
        win_model.fit(x_train, train["target_win"].astype(int))
    if "best" in args.score_components and train["target_is_best_delta"].nunique() > 1:
        best_model = lgb.LGBMClassifier(objective="binary", class_weight="balanced", **{**params, "random_state": int(args.seed) + 303})
        best_model.fit(x_train, train["target_is_best_delta"].astype(int))
    return medians, ret_model, adv_model, win_model, best_model


def score_part(part: pd.DataFrame, features: list[str], medians: pd.Series, models, args: argparse.Namespace) -> pd.DataFrame:
    if part.empty:
        return part.copy()
    ret_model, adv_model, win_model, best_model = models
    x = part[features].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    out = part.copy()
    out["pred_return"] = ret_model.predict(x) if ret_model is not None else 0.0
    out["pred_advantage"] = adv_model.predict(x) if adv_model is not None else 0.0
    out["pred_win"] = win_model.predict_proba(x)[:, 1] if win_model is not None else 0.5
    out["pred_best"] = best_model.predict_proba(x)[:, 1] if best_model is not None else 0.5
    out["score"] = (
        float(args.return_weight) * out["pred_return"].astype(float)
        + float(args.advantage_weight) * out["pred_advantage"].astype(float)
        + float(args.win_weight) * (out["pred_win"].astype(float) - 0.5)
        + float(args.best_weight) * (out["pred_best"].astype(float) - 0.5)
    )
    return out


def run_fold(ticker: str, test_month: str, frame: pd.DataFrame, features: list[str], args: argparse.Namespace) -> tuple[pd.DataFrame, dict] | None:
    val_months = [month_add(str(test_month), -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    if bool(args.pooled_train):
        train = frame[frame["month"].astype(str) < first_val].copy()
    else:
        train = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str) < first_val)].copy()
    val = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str).isin(val_months))].copy()
    test = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str) == str(test_month))].copy()
    if len(train) < int(args.min_train_rows) or len(val) < int(args.min_val_rows) or test.empty:
        return None

    medians, ret_model, adv_model, win_model, best_model = fit_models(train, features, args)
    models = (ret_model, adv_model, win_model, best_model)
    val_scored = score_part(val, features, medians, models, args)
    test_scored = score_part(test, features, medians, models, args)
    grid = build_deploy_grid(val_scored, args)
    best_cfg = grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in grid:
        trades = select_by_score(val_scored, cfg, "validation")
        row = metrics(trades, val_months)
        cfg_score = score_metrics(row, int(args.min_val_trades), int(args.min_month_trades))
        if cfg_score > best_score:
            best_cfg = cfg
            best_score = cfg_score
            best_metrics = row

    if best_score <= -1e17 and not bool(args.allow_invalid_val_deploy):
        test_trades = pd.DataFrame()
        test_metrics = metrics(test_trades, [str(test_month)])
        deploy_name = "ABSTAIN_INVALID_VAL"
        abstained = True
    else:
        test_trades = select_by_score(test_scored, best_cfg, "option_action_model")
        test_metrics = metrics(test_trades, [str(test_month)])
        deploy_name = best_cfg.name
        abstained = False
        if not test_trades.empty:
            test_trades["test_month"] = str(test_month)
            test_trades["deploy_config"] = deploy_name
    fold = {
        "ticker": ticker,
        "month": str(test_month),
        "deploy_config": deploy_name,
        "val_months": ",".join(val_months),
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "val_score": float(best_score),
        "abstained_invalid_val": bool(abstained),
        **{f"val_{k}": v for k, v in best_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    print(
        f"[OPTION_ACTION] {ticker} {test_month} cfg={deploy_name} "
        f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_trades={test_metrics.get('trades', 0)} "
        f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
        f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}",
        flush=True,
    )
    return test_trades, fold


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, metadata: dict) -> None:
    args_meta = metadata.get("args", {})
    expected = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    lines = [
        "# Option Action Model Walk-Forward",
        "",
        "Causal diagnostic: train option candidate scorer on prior months, choose skip threshold/max-day on validation months, test one ticker/month.",
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
    parser = argparse.ArgumentParser(description="Walk-forward option skip+delta action model over prebuilt candidates.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202510")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--pooled-train", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--min-train-rows", type=int, default=1000)
    parser.add_argument("--min-val-rows", type=int, default=300)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--score-components", nargs="+", default=["return", "advantage", "win", "best"])
    parser.add_argument("--return-weight", type=float, default=1.0)
    parser.add_argument("--advantage-weight", type=float, default=2.0)
    parser.add_argument("--win-weight", type=float, default=0.35)
    parser.add_argument("--best-weight", type=float, default=0.25)
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--regression-objective", default="regression_l1")
    parser.add_argument("--lgb-jobs", type=int, default=32)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-1e9, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 4, 2, 1])
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--seed", type=int, default=20260617)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_parquet(args.candidate_labels)
    candidates["ticker"] = candidates["ticker"].astype(str).str.upper()
    candidates["date"] = candidates["date"].astype(str).str.replace("-", "", regex=False).str[:8]
    candidates["month"] = candidates["date"].str[:6]
    candidates = candidates[candidates["ticker"].isin([str(t).upper() for t in args.tickers])].copy()
    candidates = add_targets(candidates, float(args.clip_return))
    features = feature_columns(candidates)
    metadata = {"args": vars(args), "feature_count": len(features), "features": features, "candidate_rows": int(len(candidates))}
    trades_list: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    months = [m for m in sorted(candidates["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]
    for ticker in [str(t).upper() for t in args.tickers]:
        for month in months:
            result = run_fold(ticker, str(month), candidates, features, args)
            if result is None:
                continue
            trades, fold = result
            if not trades.empty:
                trades_list.append(trades)
            fold_rows.append(fold)
            trade_df = pd.concat(trades_list, ignore_index=True) if trades_list else pd.DataFrame()
            fold_df = pd.DataFrame(fold_rows)
            if not trade_df.empty:
                trade_df.to_csv(output_dir / "option_action_model_trades.csv", index=False)
            fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
            write_summary(output_dir, trade_df, fold_df, metadata)

    trade_df = pd.concat(trades_list, ignore_index=True) if trades_list else pd.DataFrame()
    fold_df = pd.DataFrame(fold_rows)
    if not trade_df.empty:
        trade_df.to_csv(output_dir / "option_action_model_trades.csv", index=False)
    fold_df.to_csv(output_dir / "fold_configs.csv", index=False)
    write_summary(output_dir, trade_df, fold_df, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
