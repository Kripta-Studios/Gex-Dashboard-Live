from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_add, month_range
from walkforward_event_option_gate import LEAKY_PATTERNS, metrics, score_metrics


@dataclass(frozen=True)
class FilterConfig:
    quantile: float
    max_trades_per_day: int
    cooldown_minutes: int
    max_side_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        max_side = "all" if self.max_side_trades_per_day >= 999 else str(self.max_side_trades_per_day)
        return f"q{self.quantile:.2f}_maxday{max_day}_cool{self.cooldown_minutes}_maxside{max_side}"


def parse_variant(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        path = Path(spec)
        return path.name, path
    name, raw = spec.split("=", 1)
    return name.strip(), Path(raw.strip())


def parse_deploy_config(value: object) -> tuple[float, float]:
    text = str(value)
    threshold = 0.0
    max_day = 999.0
    match = re.search(r"thr([-+]?[0-9]*\.?[0-9]+)", text)
    if match:
        threshold = float(match.group(1))
    match = re.search(r"maxday([0-9]+|all)", text)
    if match:
        max_day = 999.0 if match.group(1) == "all" else float(match.group(1))
    return threshold, max_day


def load_variant_trades(variant_specs: list[str]) -> tuple[list[str], pd.DataFrame]:
    variants: list[str] = []
    parts: list[pd.DataFrame] = []
    for spec in variant_specs:
        name, path = parse_variant(spec)
        trade_file = path / "event_option_gate_trades.csv"
        if not trade_file.exists():
            raise FileNotFoundError(f"Missing trades for variant {name}: {trade_file}")
        trades = pd.read_csv(trade_file, dtype={"ticker": str, "date": str, "month": str, "test_month": str})
        trades["variant"] = name
        trades["source_variant_dir"] = str(path)
        variants.append(name)
        parts.append(trades)
    out = pd.concat(parts, ignore_index=True)
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["date"] = out["date"].astype(str)
    out["month"] = out["month"].astype(str)
    out["test_month"] = out["test_month"].astype(str)
    out["minute"] = pd.to_numeric(out["minute"], errors="coerce").fillna(-1).astype(int)
    out["score"] = pd.to_numeric(out["score"], errors="coerce").fillna(0.0)
    out["pred_call_return"] = pd.to_numeric(out["pred_call_return"], errors="coerce").fillna(0.0)
    out["pred_put_return"] = pd.to_numeric(out["pred_put_return"], errors="coerce").fillna(0.0)
    out["realized_return"] = pd.to_numeric(out["realized_return"], errors="coerce").fillna(0.0)
    out["month_num"] = out["test_month"].str[4:6].astype(int)
    out["pred_edge"] = out["pred_call_return"] - out["pred_put_return"]
    out["pred_abs_edge"] = out["pred_edge"].abs()
    parsed = out["deploy_config"].map(parse_deploy_config)
    out["deploy_threshold"] = [item[0] for item in parsed]
    out["deploy_max_day"] = [item[1] for item in parsed]
    out["score_rank_day_variant"] = out.groupby(["ticker", "date", "variant"])["score"].rank(method="first", ascending=False)

    group_cols = ["ticker", "date", "minute", "expiry_mode"]
    action_cols = group_cols + ["action"]
    out["same_event_total_votes"] = out.groupby(group_cols)["variant"].transform("count")
    out["same_event_action_votes"] = out.groupby(action_cols)["variant"].transform("count")
    out["same_event_action_score_mean"] = out.groupby(action_cols)["score"].transform("mean")
    out["same_event_action_score_max"] = out.groupby(action_cols)["score"].transform("max")
    call_votes = out[out["action"].astype(str) == "CALL"].groupby(group_cols)["variant"].count().rename("same_event_call_votes")
    put_votes = out[out["action"].astype(str) == "PUT"].groupby(group_cols)["variant"].count().rename("same_event_put_votes")
    out = out.merge(call_votes, on=group_cols, how="left").merge(put_votes, on=group_cols, how="left")
    out["same_event_call_votes"] = out["same_event_call_votes"].fillna(0.0)
    out["same_event_put_votes"] = out["same_event_put_votes"].fillna(0.0)
    out["same_event_action_vote_share"] = out["same_event_action_votes"] / out["same_event_total_votes"].clip(lower=1)
    out["same_event_side_vote_diff"] = out["same_event_call_votes"] - out["same_event_put_votes"]
    return variants, out


def raw_feature_columns(raw: pd.DataFrame, include_prefixes: tuple[str, ...], exclude_prefixes: tuple[str, ...]) -> list[str]:
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
        "call_return",
        "put_return",
        "realized_return",
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


def source_delta_bucket(frame: pd.DataFrame) -> pd.Series:
    """Resolve the actual option delta used by a base or consensus trade stream."""
    source = frame.get("source_variant", pd.Series("", index=frame.index)).astype(str)
    fallback = frame.get("variant", pd.Series("", index=frame.index)).astype(str)
    source = source.where(source.str.contains(r"d(?:15|25|35|50|65|80)", case=False, regex=True), fallback)
    extracted = source.str.extract(r"d(15|25|35|50|65|80)", expand=False)
    return pd.to_numeric(extracted, errors="coerce").fillna(0).astype(int)


def add_action_projected_option_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Expose the entry-time option state of the action's own contract.

    The raw event table stores call and put values in separate columns. Leaving
    that interaction to a shallow tree model is unnecessarily difficult,
    especially because consensus rows can switch delta buckets. These features
    select the relevant side using only the proposed action and the source
    stream's declared delta bucket. Outcome/exit fields are never read here.
    """
    out = frame.copy()
    bucket = source_delta_bucket(out)
    is_call = out["action"].astype(str).str.upper().eq("CALL")
    out["selected_delta_bucket"] = bucket.astype(float)
    out["selected_is_call"] = is_call.astype(float)

    suffixes = (
        "available",
        "strike_bps",
        "abs_delta",
        "iv",
        "mid_bps",
        "spread_pct",
        "theta_over_mid",
        "vega",
        "oi",
        "volume",
    )
    created = ["selected_delta_bucket", "selected_is_call"]
    for suffix in suffixes:
        selected = pd.Series(np.nan, index=out.index, dtype=float)
        opposite = pd.Series(np.nan, index=out.index, dtype=float)
        for delta in (15, 25, 35, 50, 65, 80):
            mask = bucket.eq(delta)
            if not mask.any():
                continue
            call_col = f"call_d{delta}_{suffix}"
            put_col = f"put_d{delta}_{suffix}"
            if call_col not in out.columns or put_col not in out.columns:
                continue
            call_values = pd.to_numeric(out[call_col], errors="coerce")
            put_values = pd.to_numeric(out[put_col], errors="coerce")
            selected.loc[mask] = np.where(is_call.loc[mask], call_values.loc[mask], put_values.loc[mask])
            opposite.loc[mask] = np.where(is_call.loc[mask], put_values.loc[mask], call_values.loc[mask])
        own_name = f"selected_option_{suffix}"
        other_name = f"opposite_option_{suffix}"
        diff_name = f"selected_minus_opposite_{suffix}"
        out[own_name] = selected
        out[other_name] = opposite
        out[diff_name] = selected - opposite
        created.extend([own_name, other_name, diff_name])

    for name in ("selected_option_oi", "selected_option_volume", "opposite_option_oi", "opposite_option_volume"):
        log_name = f"log1p_{name}"
        out[log_name] = np.log1p(pd.to_numeric(out[name], errors="coerce").clip(lower=0.0))
        created.append(log_name)
    return out, created


def build_model_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str], list[str]]:
    variants, trades = load_variant_trades(args.variant)
    tickers = {str(t).upper() for t in args.tickers}
    trades = trades[trades["ticker"].isin(tickers)].copy()
    raw = pd.read_parquet(args.event_dataset)
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw = raw[raw["ticker"].isin(tickers)].copy()
    raw["date"] = raw["trade_date"].astype(str)
    key_cols = ["ticker", "date", "time", "minute", "expiry_mode"]
    raw = raw.sort_values(key_cols, kind="stable").drop_duplicates(key_cols, keep="first")
    available_months = raw["date"].astype(str).str[:6]
    if available_months.empty:
        raise RuntimeError("No raw event rows remain after ticker filtering.")
    first_available_month = str(available_months.min())
    last_available_month = str(available_months.max())
    trades = trades[(trades["test_month"].astype(str) >= first_available_month) & (trades["test_month"].astype(str) <= last_available_month)].copy()
    if trades.empty:
        raise RuntimeError(f"No variant trades overlap raw event range {first_available_month}..{last_available_month}.")

    include_prefixes = tuple(str(x).lower() for x in args.raw_feature_include_prefixes if str(x).strip())
    exclude_prefixes = tuple(str(x).lower() for x in args.raw_feature_exclude_prefixes if str(x).strip())
    raw_cols = raw_feature_columns(raw, include_prefixes, exclude_prefixes)
    keep_raw = key_cols + ["nearest_level_name"] + raw_cols
    merged = trades.merge(raw[keep_raw], on=key_cols, how="left", validate="many_to_one")
    missing_rate = float(merged[raw_cols[0]].isna().mean()) if raw_cols else 1.0
    if missing_rate > float(args.max_raw_missing_rate):
        raise RuntimeError(f"Raw feature merge missing rate too high: {missing_rate:.3f}")

    merged, projected_cols = add_action_projected_option_features(merged)
    base_numeric = [
        "minute",
        "month_num",
        "score",
        "pred_call_return",
        "pred_put_return",
        "pred_edge",
        "pred_abs_edge",
        "deploy_threshold",
        "deploy_max_day",
        "score_rank_day_variant",
        "same_event_total_votes",
        "same_event_action_votes",
        "same_event_action_score_mean",
        "same_event_action_score_max",
        "same_event_call_votes",
        "same_event_put_votes",
        "same_event_action_vote_share",
        "same_event_side_vote_diff",
    ]
    mode = str(args.raw_feature_mode)
    raw_feature_set = raw_cols if mode in {"all", "all_and_projected"} else []
    projected_feature_set = projected_cols if mode in {"projected", "all_and_projected"} else []
    numeric_cols = [col for col in base_numeric + raw_feature_set + projected_feature_set if col in merged.columns]
    cats = [col for col in ["ticker", "expiry_mode", "action", "variant", "nearest_level_name"] if col in merged.columns]
    work = merged[numeric_cols + cats].copy()
    for col in numeric_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-1e6, 1e6)
    work = pd.get_dummies(work, columns=cats, dtype=float)
    feature_cols = list(work.columns)
    model_frame = pd.concat([merged.reset_index(drop=True), work.reset_index(drop=True).add_prefix("f_")], axis=1)
    feature_cols = [f"f_{col}" for col in feature_cols]
    model_frame[feature_cols] = model_frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return model_frame, feature_cols, variants


def make_model(kind: str, args: argparse.Namespace):
    common = {
        "n_estimators": int(args.n_estimators),
        "learning_rate": float(args.learning_rate),
        "num_leaves": int(args.num_leaves),
        "min_child_samples": int(args.min_child_samples),
        "subsample": float(args.subsample),
        "colsample_bytree": float(args.colsample_bytree),
        "reg_lambda": float(args.reg_lambda),
        "random_state": int(args.seed),
        "n_jobs": int(args.workers),
        "verbosity": -1,
    }
    if kind == "win":
        return lgb.LGBMClassifier(objective="binary", **common)
    if kind == "return":
        return lgb.LGBMRegressor(objective=str(args.objective), **common)
    raise ValueError(kind)


def score_model(model, kind: str, frame: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = frame.copy()
    if kind == "win":
        out["meta_score"] = model.predict_proba(out[feature_cols])[:, 1]
    else:
        out["meta_score"] = model.predict(out[feature_cols])
    return out


def deploy(scored: pd.DataFrame, threshold: float, cfg: FilterConfig) -> pd.DataFrame:
    candidates = scored[scored["meta_score"].astype(float) >= float(threshold)].copy()
    if candidates.empty:
        return candidates
    rows: list[pd.Series] = []
    for (_, _), day in candidates.sort_values(
        ["ticker", "date", "meta_score", "score"], ascending=[True, True, False, False], kind="stable"
    ).groupby(["ticker", "date"], sort=False):
        next_allowed = -1
        taken = 0
        side_taken = {"CALL": 0, "PUT": 0}
        seen: set[tuple[int, str]] = set()
        for _, row in day.iterrows():
            minute = int(row["minute"])
            side = str(row["action"])
            key = (minute, side)
            if key in seen:
                continue
            if minute < next_allowed:
                continue
            if cfg.max_trades_per_day < 999 and taken >= cfg.max_trades_per_day:
                break
            if cfg.max_side_trades_per_day < 999 and side_taken.get(side, 0) >= cfg.max_side_trades_per_day:
                continue
            rows.append(row)
            seen.add(key)
            taken += 1
            side_taken[side] = side_taken.get(side, 0) + 1
            next_allowed = minute + int(cfg.cooldown_minutes)
    return pd.DataFrame(rows) if rows else candidates.iloc[0:0].copy()


def selection_score(row: dict, args: argparse.Namespace) -> float:
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
    pnl = float(row.get("pnl_return", 0.0))
    pf = float(row.get("profit_factor", 0.0))
    return float(score + 0.08 * pnl + 0.75 * min(max(pf, 0.0), 3.0))


def candidate_configs(args: argparse.Namespace) -> list[FilterConfig]:
    return [
        FilterConfig(float(q), int(max_day), int(cooldown), int(max_side))
        for q in args.quantiles
        for max_day in args.max_trades_per_day_grid
        for cooldown in args.cooldown_grid
        for max_side in args.max_side_trades_per_day_grid
    ]


def fit_month(
    month: str,
    frame: pd.DataFrame,
    feature_cols: list[str],
    configs: list[FilterConfig],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    val_months = [month_add(month, -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    train = frame[frame["test_month"].astype(str) < first_val].copy()
    val = frame[frame["test_month"].astype(str).isin(val_months)].copy()
    test = frame[frame["test_month"].astype(str) == str(month)].copy()
    if len(train) < int(args.min_train_rows) or val.empty or test.empty:
        return pd.DataFrame(), pd.DataFrame()

    target = (train["realized_return"].astype(float) > 0.0).astype(int) if args.model_kind == "win" else train["realized_return"].astype(float).clip(-1.0, 1.0)
    if args.model_kind == "win" and target.nunique() < 2:
        return pd.DataFrame(), pd.DataFrame()
    model = make_model(str(args.model_kind), args)
    sample_weight = None
    if str(args.sample_weight_mode) == "abs_return":
        sample_weight = 1.0 + train["realized_return"].astype(float).abs().clip(0.0, 1.0)
    model.fit(train[feature_cols], target, sample_weight=sample_weight)
    val_scored = score_model(model, str(args.model_kind), val, feature_cols)
    test_scored = score_model(model, str(args.model_kind), test, feature_cols)

    tickers = [str(t).upper() for t in args.tickers]
    fold_rows: list[dict] = []
    trade_parts: list[pd.DataFrame] = []
    for ticker in tickers:
        val_ticker = val_scored[val_scored["ticker"].astype(str).str.upper() == ticker].copy()
        test_ticker = test_scored[test_scored["ticker"].astype(str).str.upper() == ticker].copy()
        if val_ticker.empty or test_ticker.empty:
            continue
        best: tuple[float, float, FilterConfig, dict] | None = None
        for cfg in configs:
            threshold = float(val_ticker["meta_score"].quantile(float(cfg.quantile)))
            val_trades = deploy(val_ticker, threshold, cfg)
            row = metrics(val_trades, val_months)
            score = selection_score(row, args)
            if best is None or score > best[0]:
                best = (score, threshold, cfg, row)
        if best is None:
            continue
        best_score, threshold, cfg, val_metrics = best
        valid = bool(best_score > -1e17)
        if not valid and not bool(args.allow_invalid_val_deploy):
            fold_rows.append(
                {
                    "ticker": ticker,
                    "month": str(month),
                    "config": "ABSTAIN_INVALID_VAL",
                    "valid_val_selection": False,
                    "val_score": float(best_score),
                    "threshold": float(threshold),
                    **{f"val_{key}": value for key, value in val_metrics.items()},
                    **{f"test_{key}": value for key, value in metrics(pd.DataFrame(), [str(month)]).items()},
                }
            )
            continue
        test_trades = deploy(test_ticker, threshold, cfg)
        if not test_trades.empty:
            test_trades = test_trades.copy()
            test_trades["quality_filter_config"] = cfg.name
            test_trades["quality_filter_threshold"] = float(threshold)
            test_trades["quality_filter_val_score"] = float(best_score)
            trade_parts.append(test_trades)
        test_metrics = metrics(test_trades, [str(month)])
        fold_rows.append(
            {
                "ticker": ticker,
                "month": str(month),
                "config": cfg.name,
                "valid_val_selection": valid,
                "val_score": float(best_score),
                "threshold": float(threshold),
                "train_rows": int(len(train)),
                "val_rows": int(len(val_ticker)),
                "test_rows": int(len(test_ticker)),
                **{f"val_{key}": value for key, value in val_metrics.items()},
                **{f"test_{key}": value for key, value in test_metrics.items()},
            }
        )
    trades = pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame()
    return trades, pd.DataFrame(fold_rows)


def summarize_outputs(trades: pd.DataFrame, months: list[str], tickers: list[str], output_dir: Path, args: argparse.Namespace) -> None:
    overall = metrics(trades, months)
    monthly_rows: list[dict] = []
    per_ticker_rows: list[dict] = []
    for ticker in tickers:
        part = trades[trades["ticker"].astype(str).str.upper() == ticker] if not trades.empty else pd.DataFrame()
        row = metrics(part, months)
        per_ticker_rows.append({"ticker": ticker, **row})
        if not part.empty:
            for (month, _ticker), mpart in part.groupby(["test_month", "ticker"]):
                mrow = metrics(mpart, [str(month)])
                monthly_rows.append({"ticker": str(_ticker), "month": str(month), **mrow})
    monthly = pd.DataFrame(monthly_rows)
    per_ticker = pd.DataFrame(per_ticker_rows)
    per_ticker.to_csv(output_dir / "per_ticker_metrics.csv", index=False)
    monthly.to_csv(output_dir / "monthly_metrics.csv", index=False)
    summary = {
        "overall": overall,
        "per_ticker": per_ticker_rows,
        "months": months,
        "risk_capital": float(args.risk_capital),
        "pnl": float(overall.get("pnl_return", 0.0)) * float(args.risk_capital),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal walk-forward trade-level quality filter over event-option variant streams.")
    parser.add_argument("--variant", action="append", required=True, help="NAME=variant_result_dir. Repeatable.")
    parser.add_argument("--event-dataset", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202501")
    parser.add_argument("--end-month", default="202512")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--model-kind", choices=["win", "return"], default="win")
    parser.add_argument("--sample-weight-mode", choices=["none", "abs_return"], default="abs_return")
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.35, 0.45, 0.55, 0.65, 0.75, 0.85])
    parser.add_argument("--max-trades-per-day-grid", nargs="+", type=int, default=[2, 3, 999])
    parser.add_argument("--cooldown-grid", nargs="+", type=int, default=[30, 45, 60])
    parser.add_argument("--max-side-trades-per-day-grid", nargs="+", type=int, default=[1, 2, 999])
    parser.add_argument("--min-train-rows", type=int, default=3000)
    parser.add_argument("--min-val-trades", type=int, default=18)
    parser.add_argument("--min-month-trades", type=int, default=6)
    parser.add_argument("--min-val-pf", type=float, default=1.0)
    parser.add_argument("--min-val-win-rate", type=float, default=0.40)
    parser.add_argument("--min-val-positive-month-rate", type=float, default=0.34)
    parser.add_argument("--min-val-daily-win-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--raw-feature-include-prefixes", nargs="*", default=[])
    parser.add_argument("--raw-feature-exclude-prefixes", nargs="*", default=[])
    parser.add_argument(
        "--raw-feature-mode",
        choices=["all", "projected", "all_and_projected"],
        default="all",
        help="Use all raw fields, action-aligned option fields, or their union. All are entry-time only.",
    )
    parser.add_argument("--max-raw-missing-rate", type=float, default=0.02)
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=15)
    parser.add_argument("--min-child-samples", type=int, default=50)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.65)
    parser.add_argument("--reg-lambda", type=float, default=20.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260624)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    folds_dir = output_dir / "folds"
    trades_dir = output_dir / "trades"
    folds_dir.mkdir(parents=True, exist_ok=True)
    trades_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "args.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")

    frame, feature_cols, variants = build_model_frame(args)
    pd.DataFrame({"feature": feature_cols}).to_csv(output_dir / "feature_cols.csv", index=False)
    (output_dir / "variants.json").write_text(json.dumps(variants, indent=2), encoding="utf-8")
    configs = candidate_configs(args)
    months = month_range(str(args.start_month), str(args.end_month))
    tickers = [str(t).upper() for t in args.tickers]
    all_fold_parts: list[pd.DataFrame] = []
    all_trade_parts: list[pd.DataFrame] = []

    for month in months:
        fold_file = folds_dir / f"fold_{month}.csv"
        trade_file = trades_dir / f"trades_{month}.parquet"
        if bool(args.resume) and fold_file.exists() and trade_file.exists():
            print(f"[QUALITY_FILTER] {month} resume existing", flush=True)
            folds = pd.read_csv(fold_file, dtype={"ticker": str, "month": str})
            trades = pd.read_parquet(trade_file)
        else:
            print(f"[QUALITY_FILTER] {month} fit/evaluate", flush=True)
            trades, folds = fit_month(month, frame, feature_cols, configs, args)
            folds.to_csv(fold_file, index=False)
            trades.to_parquet(trade_file, index=False)
        if not folds.empty:
            all_fold_parts.append(folds)
        if not trades.empty:
            all_trade_parts.append(trades)

    all_folds = pd.concat(all_fold_parts, ignore_index=True) if all_fold_parts else pd.DataFrame()
    all_trades = pd.concat(all_trade_parts, ignore_index=True) if all_trade_parts else pd.DataFrame()
    all_folds.to_csv(output_dir / "fold_configs.csv", index=False)
    all_trades.to_csv(output_dir / "trade_quality_filter_trades.csv", index=False)
    summarize_outputs(all_trades, months, tickers, output_dir, args)

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    print(json.dumps(summary, indent=2, allow_nan=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
