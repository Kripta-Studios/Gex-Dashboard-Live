from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import LEAKY_PATTERNS
from online_expert_router import (
    add_prior_features,
    expected_metrics,
    load_expert_trades,
    make_daily_frame,
    materialize_trades,
    score_selection,
)


@dataclass(frozen=True)
class ModelConfig:
    target: str
    clip_target: float
    activity_bonus: float
    min_pred_score: float
    experts_per_day: int
    num_leaves: int
    min_child_samples: int

    @property
    def name(self) -> str:
        def fmt(value: float) -> str:
            return str(value).replace(".", "p").replace("-", "m")

        return (
            f"{self.target}_clip{fmt(self.clip_target)}"
            f"_act{fmt(self.activity_bonus)}"
            f"_min{fmt(self.min_pred_score)}"
            f"_k{self.experts_per_day}"
            f"_nl{self.num_leaves}_mcs{self.min_child_samples}"
        )


def nonleaky_numeric_columns(raw: pd.DataFrame, include_prefixes: tuple[str, ...], exclude_prefixes: tuple[str, ...]) -> list[str]:
    blocked = {
        "ticker",
        "underlying_ticker",
        "trade_date",
        "date",
        "expiration",
        "timestamp",
        "time",
        "minute",
        "nearest_level_name",
        "expiry_mode",
    }
    cols: list[str] = []
    for col in raw.columns:
        low = str(col).lower()
        if col in blocked:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if exclude_prefixes and low.startswith(exclude_prefixes):
            continue
        if include_prefixes and not low.startswith(include_prefixes):
            continue
        if pd.api.types.is_numeric_dtype(raw[col]):
            cols.append(col)
    return cols


def build_lagged_market_state(args: argparse.Namespace, tickers: list[str]) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_parquet(args.event_dataset)
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw = raw[raw["ticker"].isin(tickers)].copy()
    raw["date"] = raw["trade_date"].astype(str)
    include_prefixes = tuple(str(x).lower() for x in args.raw_feature_include_prefixes if str(x).strip())
    exclude_prefixes = tuple(str(x).lower() for x in args.raw_feature_exclude_prefixes if str(x).strip())
    numeric_cols = nonleaky_numeric_columns(raw, include_prefixes, exclude_prefixes)
    if not numeric_cols:
        raise RuntimeError("No market-state numeric columns selected.")
    raw = raw.sort_values(["ticker", "date", "minute"], kind="stable")
    agg = raw.groupby(["ticker", "date"], sort=False)[numeric_cols].agg(["mean", "last"])
    agg.columns = [f"mkt_{col}_{stat}" for col, stat in agg.columns]
    agg = agg.reset_index()
    count = raw.groupby(["ticker", "date"], sort=False).size().rename("mkt_event_count").reset_index()
    agg = agg.merge(count, on=["ticker", "date"], how="left")
    feature_cols = [col for col in agg.columns if col not in {"ticker", "date"}]
    agg[feature_cols] = agg[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-1e6, 1e6)
    out = agg.sort_values(["ticker", "date"], kind="stable").copy()
    shifted = out.groupby("ticker", sort=False)[feature_cols].shift(1)
    shifted.columns = [f"lag1_{col}" for col in feature_cols]
    out = pd.concat([out[["ticker", "date"]], shifted], axis=1)
    lag_cols = list(shifted.columns)
    for window in args.market_windows:
        roll = (
            agg.sort_values(["ticker", "date"], kind="stable")
            .groupby("ticker", sort=False)[feature_cols]
            .shift(1)
            .groupby(agg.sort_values(["ticker", "date"], kind="stable")["ticker"], sort=False)
            .rolling(window=int(window), min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )
        roll.columns = [f"roll{window}_{col}" for col in feature_cols]
        out = pd.concat([out, roll.reset_index(drop=True)], axis=1)
        lag_cols.extend(list(roll.columns))
    out[lag_cols] = out[lag_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-1e6, 1e6)
    return out, lag_cols


def build_model_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str], list[str]]:
    tickers = [str(t).upper() for t in args.tickers]
    experts, trades = load_expert_trades(args.variant)
    trades = trades[trades["ticker"].isin(tickers)].copy()
    daily = make_daily_frame(trades, experts, tickers)
    daily = add_prior_features(daily, sorted(set(int(w) for w in args.expert_recent_windows)))
    market, market_cols = build_lagged_market_state(args, tickers)
    daily = daily.merge(market, on=["ticker", "date"], how="left")
    daily[market_cols] = daily[market_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    daily["dow"] = pd.to_datetime(daily["date"], format="%Y%m%d", errors="coerce").dt.dayofweek.fillna(0).astype(int)
    daily["day_of_month"] = daily["date"].astype(str).str[6:8].astype(int)
    daily["month_num"] = daily["test_month"].astype(str).str[4:6].astype(int)

    prior_cols = [
        col
        for col in daily.columns
        if col.startswith(("all_", "month_cum_", "same_month_", "recent"))
        and col not in {"daily_R", "daily_trades", "daily_score"}
    ]
    base_cols = ["trading_day_index", "month_num", "dow", "day_of_month"] + prior_cols + market_cols
    cats = pd.get_dummies(daily[["ticker", "expert"]].astype(str), columns=["ticker", "expert"], dtype=float)
    for col in base_cols:
        daily[col] = pd.to_numeric(daily[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-1e6, 1e6)
    feature_frame = pd.concat([daily[base_cols].reset_index(drop=True), cats.reset_index(drop=True)], axis=1)
    feature_cols = list(feature_frame.columns)
    model_frame = pd.concat([daily.reset_index(drop=True), feature_frame.add_prefix("f_")], axis=1)
    feature_cols = [f"f_{col}" for col in feature_cols]
    model_frame[feature_cols] = model_frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return trades, model_frame, feature_cols, experts, tickers


def model_configs(args: argparse.Namespace) -> list[ModelConfig]:
    return [
        ModelConfig(
            str(target),
            float(clip),
            float(activity_bonus),
            float(min_pred),
            int(experts_per_day),
            int(num_leaves),
            int(min_child),
        )
        for target in args.targets
        for clip in args.clip_target_grid
        for activity_bonus in args.activity_bonus_grid
        for min_pred in args.min_pred_score_grid
        for experts_per_day in args.experts_per_day_grid
        for num_leaves in args.num_leaves_grid
        for min_child in args.min_child_samples_grid
    ]


def make_model(cfg: ModelConfig, args: argparse.Namespace):
    common = {
        "n_estimators": int(args.n_estimators),
        "learning_rate": float(args.learning_rate),
        "num_leaves": int(cfg.num_leaves),
        "min_child_samples": int(cfg.min_child_samples),
        "subsample": float(args.subsample),
        "colsample_bytree": float(args.colsample_bytree),
        "reg_lambda": float(args.reg_lambda),
        "n_jobs": int(args.workers),
        "verbosity": -1,
        "random_state": int(args.seed),
    }
    if cfg.target in {"win", "active_win"}:
        return lgb.LGBMClassifier(objective="binary", **common)
    return lgb.LGBMRegressor(objective=str(args.objective), **common)


def fit_predict_month(
    frame: pd.DataFrame,
    feature_cols: list[str],
    cfg: ModelConfig,
    month: str,
    args: argparse.Namespace,
) -> pd.DataFrame:
    train = frame[frame["test_month"].astype(str) < str(month)].copy()
    score = frame[frame["test_month"].astype(str) == str(month)].copy()
    if train["test_month"].nunique() < int(args.min_train_months) or len(train) < int(args.min_train_rows) or score.empty:
        return pd.DataFrame()
    if cfg.target == "win":
        y = (train["daily_R"].astype(float) > 0.0).astype(int)
        if y.nunique() < 2:
            return pd.DataFrame()
    elif cfg.target == "active_win":
        active = train[train["daily_trades"].astype(float) > 0.0].copy()
        if len(active) < int(args.min_train_rows) // 4:
            return pd.DataFrame()
        train = active
        y = (train["daily_R"].astype(float) > 0.0).astype(int)
        if y.nunique() < 2:
            return pd.DataFrame()
    else:
        y = train["daily_R"].astype(float).clip(-float(cfg.clip_target), float(cfg.clip_target))
    sample_weight = 1.0 + train["daily_R"].astype(float).abs().clip(0.0, float(cfg.clip_target))
    if str(args.sample_weight_mode) == "active":
        sample_weight = sample_weight + (train["daily_trades"].astype(float) > 0.0).astype(float)
    model = make_model(cfg, args)
    model.fit(train[feature_cols], y, sample_weight=sample_weight)
    out = score.copy()
    if cfg.target in {"win", "active_win"}:
        out["pred_edge"] = model.predict_proba(out[feature_cols])[:, 1] - 0.5
    else:
        out["pred_edge"] = model.predict(out[feature_cols])
    if float(cfg.activity_bonus) != 0.0:
        out["pred_edge"] += float(cfg.activity_bonus) * np.log1p(out["all_trade_sum"].astype(float).clip(lower=0.0))
    return out


def select_experts(scored: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    ranked = scored.sort_values(["ticker", "date", "pred_edge", "all_R_mean"], ascending=[True, True, False, False], kind="stable")
    selected = ranked.groupby(["ticker", "date"], sort=False).head(int(cfg.experts_per_day)).copy()
    selected = selected[selected["pred_edge"].astype(float) >= float(cfg.min_pred_score)].copy()
    if selected.empty:
        return selected
    selected["router_score"] = selected["pred_edge"].astype(float)
    selected["router_config"] = cfg.name
    return selected[["expert", "ticker", "date", "router_score", "router_config"]]


def materialize_selected_trades(trades: pd.DataFrame, selected_days: pd.DataFrame) -> pd.DataFrame:
    if selected_days.empty:
        return pd.DataFrame()
    selected = selected_days[["expert", "ticker", "date", "router_score", "router_config"]].copy()
    out = trades.merge(selected, on=["expert", "ticker", "date"], how="inner", validate="many_to_one")
    if out.empty:
        return out
    out["selected_expert"] = out["expert"]
    dedupe_cols = [col for col in ["ticker", "date", "minute", "expiry_mode", "action"] if col in out.columns]
    if dedupe_cols:
        out = out.sort_values(
            dedupe_cols + ["router_score", "score"],
            ascending=[True] * len(dedupe_cols) + [False, False],
            kind="stable",
        ).drop_duplicates(dedupe_cols, keep="first")
    return out.reset_index(drop=True)


def evaluate_config(
    trades: pd.DataFrame,
    frame: pd.DataFrame,
    feature_cols: list[str],
    cfg: ModelConfig,
    start_month: str,
    end_month: str,
    tickers: list[str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict, pd.DataFrame, dict]:
    selected_parts: list[pd.DataFrame] = []
    for month in month_range(str(start_month), str(end_month)):
        scored = fit_predict_month(frame, feature_cols, cfg, month, args)
        selected = select_experts(scored, cfg)
        if not selected.empty:
            selected_parts.append(selected)
    selected_days = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    routed = materialize_selected_trades(trades, selected_days) if not selected_days.empty else pd.DataFrame()
    months = month_range(str(start_month), str(end_month))
    overall, per_ticker, monthly, summary = expected_metrics(routed, months, tickers)
    return routed, selected_days, overall, per_ticker, monthly, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal market-state expert router using prior-day raw event features.")
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--event-dataset", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--selection-start-month", default="202401")
    parser.add_argument("--selection-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202606")
    parser.add_argument("--expert-recent-windows", nargs="+", type=int, default=[5, 21])
    parser.add_argument("--market-windows", nargs="+", type=int, default=[5, 21])
    parser.add_argument("--raw-feature-include-prefixes", nargs="*", default=[])
    parser.add_argument("--raw-feature-exclude-prefixes", nargs="*", default=[])
    parser.add_argument("--targets", nargs="+", default=["return"])
    parser.add_argument("--clip-target-grid", nargs="+", type=float, default=[2.0, 5.0])
    parser.add_argument("--activity-bonus-grid", nargs="+", type=float, default=[0.0, 0.01])
    parser.add_argument("--min-pred-score-grid", nargs="+", type=float, default=[-999.0])
    parser.add_argument("--experts-per-day-grid", nargs="+", type=int, default=[1])
    parser.add_argument("--num-leaves-grid", nargs="+", type=int, default=[7, 15])
    parser.add_argument("--min-child-samples-grid", nargs="+", type=int, default=[40, 80])
    parser.add_argument("--min-train-months", type=int, default=12)
    parser.add_argument("--min-train-rows", type=int, default=2000)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.50)
    parser.add_argument("--reg-lambda", type=float, default=25.0)
    parser.add_argument("--sample-weight-mode", choices=["none", "active"], default="active")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260624)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--gate-min-month-trades", type=int, default=18)
    parser.add_argument("--gate-min-pf", type=float, default=1.0)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "args.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    trades, frame, feature_cols, experts, tickers = build_model_frame(args)
    frame.to_parquet(output_dir / "market_state_daily_model_frame.parquet", index=False)
    pd.DataFrame({"feature": feature_cols}).to_csv(output_dir / "feature_cols.csv", index=False)
    (output_dir / "experts.json").write_text(json.dumps(experts, indent=2), encoding="utf-8")
    configs = model_configs(args)
    rows: list[dict] = []
    for idx, cfg in enumerate(configs):
        routed, selected, overall, per_ticker, monthly, summary = evaluate_config(
            trades, frame, feature_cols, cfg, args.selection_start_month, args.selection_end_month, tickers, args
        )
        rows.append(
            {
                "idx": idx,
                "config": cfg.name,
                "score_selection": score_selection(overall, summary, args),
                **asdict(cfg),
                **{f"{key}_selection": value for key, value in overall.items()},
                "pf_min_selection": summary["pf_min"],
                "wr_min_selection": summary["wr_min"],
                "min_month_ticker_selection": summary["min_month_ticker"],
                "pos_min_selection": summary["pos_min"],
                "losing_ticker_months_selection": summary["losing_ticker_months"],
            }
        )
    ranked = pd.DataFrame(rows).sort_values("score_selection", ascending=False)
    ranked.to_csv(output_dir / "config_rank_selection.csv", index=False)
    test_rows: list[dict] = []
    for _, ranked_row in ranked.head(int(args.top_k)).iterrows():
        cfg = ModelConfig(
            str(ranked_row["target"]),
            float(ranked_row["clip_target"]),
            float(ranked_row["activity_bonus"]),
            float(ranked_row["min_pred_score"]),
            int(ranked_row["experts_per_day"]),
            int(ranked_row["num_leaves"]),
            int(ranked_row["min_child_samples"]),
        )
        routed, selected, overall, per_ticker, monthly, summary = evaluate_config(
            trades, frame, feature_cols, cfg, args.test_start_month, args.test_end_month, tickers, args
        )
        subdir = output_dir / cfg.name
        subdir.mkdir(parents=True, exist_ok=True)
        routed.to_csv(subdir / "market_state_expert_trades.csv", index=False)
        selected.to_csv(subdir / "selected_days.csv", index=False)
        monthly.to_csv(subdir / "monthly.csv", index=False)
        (subdir / "metrics.json").write_text(
            json.dumps(
                {
                    "overall": overall,
                    "per_ticker": per_ticker,
                    "monthly_summary": summary,
                    "selection_row": ranked_row.to_dict(),
                    "pnl": float(overall.get("R", 0.0)) * float(args.risk_capital),
                },
                indent=2,
                allow_nan=True,
            ),
            encoding="utf-8",
        )
        test_rows.append(
            {
                **ranked_row.to_dict(),
                **{f"{key}_test": value for key, value in overall.items()},
                "pf_min_test": summary["pf_min"],
                "wr_min_test": summary["wr_min"],
                "min_month_ticker_test": summary["min_month_ticker"],
                "pos_min_test": summary["pos_min"],
                "losing_ticker_months_test": summary["losing_ticker_months"],
                "artifact_dir": str(subdir),
            }
        )
    test = pd.DataFrame(test_rows)
    test.to_csv(output_dir / "top_selection_then_test.csv", index=False)
    cols = [
        "idx",
        "config",
        "score_selection",
        "pf_selection",
        "R_selection",
        "pf_min_selection",
        "min_month_ticker_selection",
        "pos_min_selection",
        "losing_ticker_months_selection",
        "pf_test",
        "wr_test",
        "R_test",
        "pf_min_test",
        "wr_min_test",
        "min_month_ticker_test",
        "pos_min_test",
        "losing_ticker_months_test",
        "artifact_dir",
    ]
    print(test[[c for c in cols if c in test.columns]].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
