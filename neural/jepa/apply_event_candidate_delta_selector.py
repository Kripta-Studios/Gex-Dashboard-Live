from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range


LEAKY_PATTERNS = (
    "future",
    "target",
    "label",
    "outcome",
    "_opt_exit_ret",
    "_opt_exit_minutes",
    "spot_long",
    "spot_short",
    "oracle",
    "pnl",
    "return",
)

BASE_FEATURES = [
    "score",
    "pred_call_return",
    "pred_put_return",
    "score_margin",
    "entry_minute",
    "weekday",
    "candidate_seq_in_day",
    "prior_meta_score",
]

OPTION_FIELDS = [
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
]


def parse_clock_minutes(value: object) -> float:
    text = str(value)
    if ":" not in text:
        return float("nan")
    try:
        hour, minute = text[:5].split(":")
        return float(int(hour) * 60 + int(minute))
    except Exception:
        return float("nan")


def first_valid_numeric(frame: pd.DataFrame, names: list[str]) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for name in names:
        if name not in frame.columns:
            continue
        values = pd.to_numeric(frame[name], errors="coerce")
        out = out.where(out.notna(), values)
    return out


def normalize_trades(path: Path, role: str, tickers: list[str]) -> pd.DataFrame:
    trades = pd.read_csv(path, dtype={"date": str, "month": str, "test_month": str, "time": str})
    trades["ticker"] = trades["ticker"].astype(str).str.upper()
    if tickers:
        trades = trades[trades["ticker"].isin([t.upper() for t in tickers])].copy()
    trades["date"] = trades["date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if "test_month" in trades.columns:
        trades["test_month"] = trades["test_month"].astype(str).str.replace(r"\D", "", regex=True).str[:6]
    else:
        trades["test_month"] = trades["date"].str[:6]
    trades["month"] = trades["test_month"]
    trades["time"] = trades["time"].astype(str).str[:5]
    trades["expiry_mode"] = trades["expiry_mode"].astype(str)
    trades["action"] = trades["action"].astype(str).str.upper().str.replace("LONG", "CALL").str.replace("SHORT", "PUT")
    trades = trades[trades["action"].isin(["CALL", "PUT"])].copy()
    trades["entry_minute"] = first_valid_numeric(trades, ["minute", "minute_x", "minute_y", "entry_minute"])
    parsed = trades["time"].map(parse_clock_minutes)
    trades["entry_minute"] = trades["entry_minute"].where(trades["entry_minute"].notna(), parsed)
    trades["entry_minute"] = trades["entry_minute"].fillna(0.0).astype(float)
    trades["weekday"] = pd.to_datetime(trades["date"], format="%Y%m%d", errors="coerce").dt.weekday.fillna(-1).astype(float)
    trades["candidate_seq_in_day"] = trades.groupby(["ticker", "date"]).cumcount().astype(float)
    if "score_margin" not in trades.columns:
        trades["score_margin"] = (
            pd.to_numeric(trades.get("pred_call_return", 0.0), errors="coerce").fillna(0.0)
            - pd.to_numeric(trades.get("pred_put_return", 0.0), errors="coerce").fillna(0.0)
        ).abs()
    if "prior_meta_score" not in trades.columns:
        trades["prior_meta_score"] = pd.to_numeric(trades.get("meta_score", np.nan), errors="coerce")
    trades["source_file"] = path.parent.name
    trades["row_role"] = role
    keep = [
        "ticker",
        "date",
        "month",
        "test_month",
        "time",
        "expiry_mode",
        "action",
        "entry_minute",
        "weekday",
        "candidate_seq_in_day",
        "source_file",
        "row_role",
        *[c for c in BASE_FEATURES if c in trades.columns],
        *[c for c in ["source_variant", "selected_model", "deploy_config"] if c in trades.columns],
    ]
    keep = list(dict.fromkeys(keep))
    return trades[keep].copy()


def load_raw_features(data_path: Path, tickers: list[str], deltas: list[int]) -> pd.DataFrame:
    raw = pd.read_parquet(data_path)
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    if tickers:
        raw = raw[raw["ticker"].isin([t.upper() for t in tickers])].copy()
    raw["date"] = raw["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    raw["time"] = raw["time"].astype(str).str[:5]
    raw["expiry_mode"] = raw["expiry_mode"].astype(str)
    return raw.reset_index(drop=True)


def build_raw_history_trades(raw: pd.DataFrame, tickers: list[str], start_month: str, end_month: str) -> pd.DataFrame:
    base_cols = ["ticker", "date", "time", "expiry_mode", "minute"]
    base = raw[base_cols].copy()
    base["ticker"] = base["ticker"].astype(str).str.upper()
    if tickers:
        base = base[base["ticker"].isin([t.upper() for t in tickers])].copy()
    base["month"] = base["date"].astype(str).str[:6]
    base = base[(base["month"] >= str(start_month)) & (base["month"] <= str(end_month))].copy()
    base["test_month"] = base["month"]
    base["entry_minute"] = pd.to_numeric(base["minute"], errors="coerce").fillna(base["time"].map(parse_clock_minutes)).fillna(0.0)
    base["weekday"] = pd.to_datetime(base["date"], format="%Y%m%d", errors="coerce").dt.weekday.fillna(-1).astype(float)
    parts: list[pd.DataFrame] = []
    for action in ("CALL", "PUT"):
        part = base.copy()
        part["action"] = action
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    out["score"] = 0.0
    out["pred_call_return"] = 0.0
    out["pred_put_return"] = 0.0
    out["score_margin"] = 0.0
    out["prior_meta_score"] = np.nan
    out["candidate_seq_in_day"] = out.groupby(["ticker", "date", "expiry_mode", "action"]).cumcount().astype(float)
    out["source_file"] = "raw_event_history"
    out["row_role"] = "history"
    return out[
        [
            "ticker",
            "date",
            "month",
            "test_month",
            "time",
            "expiry_mode",
            "action",
            "entry_minute",
            "weekday",
            "candidate_seq_in_day",
            "source_file",
            "row_role",
            "score",
            "pred_call_return",
            "pred_put_return",
            "score_margin",
            "prior_meta_score",
        ]
    ].copy()


def general_feature_columns(raw: pd.DataFrame, args: argparse.Namespace) -> list[str]:
    prefixes = tuple(str(p) for p in args.feature_prefixes)
    exclude_prefixes = tuple(str(p) for p in args.feature_exclude_prefixes)
    selected: list[str] = []
    skip_names = {
        "trade_date",
        "date",
        "expiration",
        "timestamp",
        "time",
        "ticker",
        "underlying_ticker",
        "expiry_mode",
        "nearest_level_name",
    }
    for col in raw.columns:
        low = str(col).lower()
        if col in skip_names:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if str(col).startswith(("call_d", "put_d")):
            continue
        if str(col).startswith(exclude_prefixes):
            continue
        if prefixes and not str(col).startswith(prefixes):
            continue
        if not bool(args.include_latent_vectors) and (
            str(col).startswith("tdvp_z_")
            or str(col).startswith("tdvp_dz_")
            or str(col).startswith("ptdj_z_")
            or str(col).startswith("ptdj_dz_")
        ):
            continue
        if pd.api.types.is_numeric_dtype(raw[col]):
            selected.append(col)
    return selected


def expand_delta_candidates(trades: pd.DataFrame, raw: pd.DataFrame, raw_feature_cols: list[str], deltas: list[int], risk_capital: float) -> tuple[pd.DataFrame, list[str]]:
    join_cols = ["ticker", "date", "time", "expiry_mode"]
    merged = trades.merge(
        raw[join_cols + raw_feature_cols + [c for c in raw.columns if c.startswith(("call_d", "put_d"))]],
        on=join_cols,
        how="left",
        suffixes=("", "_raw"),
    )
    expanded_parts: list[pd.DataFrame] = []
    for delta in deltas:
        part = merged.copy()
        part["delta_bucket"] = int(delta)
        prefixes = np.where(part["action"].astype(str).eq("CALL"), f"call_d{int(delta):02d}", f"put_d{int(delta):02d}")
        returns = []
        option_values: dict[str, list[float]] = {f"opt_{field}": [] for field in OPTION_FIELDS}
        for idx, prefix in enumerate(prefixes):
            ret_col = f"{prefix}_opt_exit_ret"
            returns.append(part.iloc[idx].get(ret_col, np.nan))
            for field in OPTION_FIELDS:
                option_values[f"opt_{field}"].append(part.iloc[idx].get(f"{prefix}_{field}", np.nan))
        part["target_return"] = pd.to_numeric(pd.Series(returns, index=part.index), errors="coerce")
        for name, values in option_values.items():
            part[name] = pd.to_numeric(pd.Series(values, index=part.index), errors="coerce")
        expanded_parts.append(part)
    expanded = pd.concat(expanded_parts, ignore_index=True)
    expanded = expanded[np.isfinite(pd.to_numeric(expanded["target_return"], errors="coerce"))].copy()
    expanded["target_return"] = expanded["target_return"].astype(float)
    expanded["target_pnl"] = expanded["target_return"] * float(risk_capital)
    expanded["signal_id"] = (
        expanded["row_role"].astype(str)
        + "|"
        + expanded["ticker"].astype(str)
        + "|"
        + expanded["date"].astype(str)
        + "|"
        + expanded["time"].astype(str)
        + "|"
        + expanded["expiry_mode"].astype(str)
        + "|"
        + expanded["action"].astype(str)
        + "|"
        + expanded["candidate_seq_in_day"].astype(int).astype(str)
    )

    for delta in deltas:
        expanded[f"delta_is_{int(delta):02d}"] = (expanded["delta_bucket"].astype(int) == int(delta)).astype(float)
    dummy_cols = []
    cats = [c for c in ["ticker", "action", "expiry_mode", "source_variant", "selected_model", "deploy_config", "source_file"] if c in expanded.columns]
    if cats:
        dummies = pd.get_dummies(expanded[cats].fillna("NA").astype(str), prefix=cats, dtype=float)
        dummy_cols = list(dummies.columns)
        expanded = pd.concat([expanded, dummies], axis=1)

    feature_cols: list[str] = []
    for col in BASE_FEATURES:
        if col in expanded.columns and pd.api.types.is_numeric_dtype(expanded[col]):
            feature_cols.append(col)
    feature_cols.extend(raw_feature_cols)
    feature_cols.extend([f"opt_{field}" for field in OPTION_FIELDS])
    feature_cols.append("delta_bucket")
    feature_cols.extend([f"delta_is_{int(delta):02d}" for delta in deltas])
    feature_cols.extend(dummy_cols)
    feature_cols = [c for c in dict.fromkeys(feature_cols) if c in expanded.columns and pd.api.types.is_numeric_dtype(expanded[c])]
    return expanded, feature_cols


def compute_metrics(
    trades: pd.DataFrame,
    pnl_col: str = "pnl",
    expected_months: list[str] | None = None,
    risk_capital: float = 5000.0,
) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "return_on_risk": 0.0,
            "max_drawdown": 0.0,
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
            "long_rate": float("nan"),
        }
    pnl = pd.to_numeric(trades[pnl_col], errors="coerce").fillna(0.0)
    wins = pnl[pnl > 0.0].sum()
    losses = -pnl[pnl < 0.0].sum()
    equity = pnl.cumsum()
    peak = equity.cummax()
    by_month = trades.assign(_pnl=pnl).groupby("month")["_pnl"].agg(["count", "sum"])
    if expected_months is not None:
        by_month = by_month.reindex([str(m) for m in expected_months], fill_value=0)
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(wins / losses) if losses > 0.0 else (float("inf") if wins > 0 else float("nan")),
        "pnl_dollars": float(pnl.sum()),
        "return_on_risk": float(pnl.sum() / max(1e-9, float(risk_capital))),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
        "long_rate": float((trades["action"].astype(str).eq("CALL")).mean()) if "action" in trades.columns else float("nan"),
    }


def fit_predict_fold(expanded: pd.DataFrame, feature_cols: list[str], ticker: str, month: str, args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    train = expanded[
        (expanded["ticker"].astype(str) == str(ticker))
        & (expanded["month"].astype(str) < str(month))
        & (expanded["row_role"].astype(str).isin(["history", "test"]))
    ].copy()
    test = expanded[
        (expanded["ticker"].astype(str) == str(ticker))
        & (expanded["month"].astype(str) == str(month))
        & (expanded["row_role"].astype(str) == "test")
    ].copy()
    base = {
        "ticker": str(ticker),
        "month": str(month),
        "train_months": ",".join(sorted(train["month"].astype(str).unique())),
        "test_rows": int(len(test)),
        "train_rows": int(len(train)),
        "feature_count": int(len(feature_cols)),
    }
    if test.empty:
        return test, {**base, "mode": "NO_TEST"}
    if len(train) < int(args.min_train_rows) or train["target_return"].nunique() < 2:
        baseline = test.sort_values(["signal_id", "delta_bucket"]).groupby("signal_id", sort=False).head(1).copy()
        baseline["selected_delta_return"] = baseline["target_return"].astype(float)
        baseline["pnl"] = baseline["target_pnl"].astype(float)
        baseline["selector_mode"] = "INSUFFICIENT_HISTORY"
        return baseline, {**base, "mode": "INSUFFICIENT_HISTORY", "metrics": compute_metrics(baseline, risk_capital=float(args.risk_capital))}

    if bool(args.pooled_train):
        train = expanded[
            (expanded["month"].astype(str) < str(month))
            & (expanded["row_role"].astype(str).isin(["history", "test"]))
        ].copy()
    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    y_train = train["target_return"].astype(float).clip(-float(args.clip_target), float(args.clip_target))
    weights = 1.0 + np.minimum(np.abs(train["target_return"].astype(float).to_numpy()), float(args.max_abs_weight_return))
    common_params = dict(
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed) + int(str(month)[-2:]),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    if str(args.model_type) == "ranker":
        train_sorted = train.sort_values(["signal_id", "delta_bucket"]).reset_index(drop=True)
        x_train = train_sorted[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        relevance = (
            train_sorted.groupby("signal_id")["target_return"]
            .rank(method="first", ascending=True)
            .sub(1)
            .astype(int)
        )
        group_sizes = train_sorted.groupby("signal_id", sort=False).size().astype(int).tolist()
        model = lgb.LGBMRanker(objective="lambdarank", **common_params)
        model.fit(x_train, relevance, group=group_sizes)
    else:
        model = lgb.LGBMRegressor(objective=str(args.objective), **common_params)
        model.fit(x_train, y_train, sample_weight=weights)
    scored = test.copy()
    x_test = scored[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    scored["pred_return"] = model.predict(x_test).astype(float)
    selected = scored.sort_values(["signal_id", "pred_return", "delta_bucket"], ascending=[True, False, True]).groupby("signal_id", sort=False).head(1).copy()
    selected["selected_delta_return"] = selected["target_return"].astype(float)
    selected["pnl"] = selected["target_pnl"].astype(float)
    selected["selector_mode"] = "MODEL"
    row = {**base, "mode": "MODEL", "metrics": compute_metrics(selected, risk_capital=float(args.risk_capital))}
    return selected, row


def flatten(prefix: str, row: dict) -> dict:
    return {f"{prefix}_{k}": v for k, v in row.items()}


def write_plot(out_dir: Path, trades: pd.DataFrame) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["date_dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    daily = work.groupby("date_dt", as_index=False)["pnl"].sum().sort_values("date_dt")
    daily["cum_pnl"] = daily["pnl"].cumsum()
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(daily["date_dt"], daily["cum_pnl"], label="delta_selector", linewidth=2.0)
    ax.axhline(0.0, color="black", linewidth=0.9)
    ax.set_title("Cumulative daily net PnL - same-side delta selector")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative net PnL")
    ax.legend(loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_dir / "delta_selector_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal same-side delta selector over prebuilt event option candidate signals.")
    parser.add_argument("--history-trades", nargs="*", default=[])
    parser.add_argument("--test-trades", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--history-start-month", default="202507")
    parser.add_argument("--history-end-month", default="202512")
    parser.add_argument("--use-raw-history", action="store_true")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--deltas", nargs="+", type=int, default=[15, 25, 35, 50, 65, 80])
    parser.add_argument("--feature-prefixes", nargs="*", default=["dist_", "ib_", "ret_", "phys_", "ctx_", "tdvp_"])
    parser.add_argument("--feature-exclude-prefixes", nargs="*", default=[])
    parser.add_argument("--include-latent-vectors", action="store_true")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--pooled-train", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--min-train-rows", type=int, default=180)
    parser.add_argument("--clip-target", type=float, default=2.0)
    parser.add_argument("--max-abs-weight-return", type=float, default=2.0)
    parser.add_argument("--model-type", choices=["regressor", "ranker"], default="regressor")
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=280)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=45)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=8.0)
    parser.add_argument("--lgb-jobs", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260619)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tickers = [str(t).upper() for t in args.tickers]

    raw = load_raw_features(Path(args.data), tickers, [int(d) for d in args.deltas])
    history_parts = []
    if bool(args.use_raw_history):
        history_parts.append(build_raw_history_trades(raw, tickers, str(args.history_start_month), str(args.history_end_month)))
    for item in args.history_trades:
        frame = normalize_trades(Path(item), "history", tickers)
        frame = frame[
            (frame["month"].astype(str) >= str(args.history_start_month))
            & (frame["month"].astype(str) <= str(args.history_end_month))
        ].copy()
        history_parts.append(frame)
    test_frame = normalize_trades(Path(args.test_trades), "test", tickers)
    test_frame = test_frame[
        (test_frame["month"].astype(str) >= str(args.start_month))
        & (test_frame["month"].astype(str) <= str(args.end_month))
    ].copy()
    trades = pd.concat([*history_parts, test_frame], ignore_index=True) if history_parts else test_frame
    trades = trades.drop_duplicates(["row_role", "ticker", "date", "time", "expiry_mode", "action", "candidate_seq_in_day", "source_file"]).reset_index(drop=True)

    raw_feature_cols = general_feature_columns(raw, args)
    expanded, feature_cols = expand_delta_candidates(trades, raw, raw_feature_cols, [int(d) for d in args.deltas], float(args.risk_capital))

    all_selected: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    expected = month_range(str(args.start_month), str(args.end_month))
    for ticker in tickers:
        for month in expected:
            selected, fold = fit_predict_fold(expanded, feature_cols, ticker, str(month), args)
            if not selected.empty:
                all_selected.append(selected)
            row = {
                "ticker": ticker,
                "month": str(month),
                "mode": fold.get("mode", ""),
                "train_months": fold.get("train_months", ""),
                "train_rows": fold.get("train_rows", 0),
                "test_rows": fold.get("test_rows", 0),
                "feature_count": fold.get("feature_count", len(feature_cols)),
                "leak_ok": all((not m or m < str(month)) for m in str(fold.get("train_months", "")).split(",")),
            }
            row.update(flatten("test", fold.get("metrics", compute_metrics(pd.DataFrame(), risk_capital=float(args.risk_capital)))))
            fold_rows.append(row)
            print(
                f"[DELTA_SELECTOR] {ticker} {month} mode={row['mode']} "
                f"trades={row.get('test_trades', 0)} pf={row.get('test_profit_factor', float('nan')):.3f} "
                f"pnl={row.get('test_pnl_dollars', 0.0):.0f}",
                flush=True,
            )

    selected_df = pd.concat(all_selected, ignore_index=True) if all_selected else pd.DataFrame()
    if not selected_df.empty:
        selected_df.attrs["risk_capital"] = float(args.risk_capital)
        selected_df.to_csv(out_dir / "delta_selector_trades.csv", index=False)
    fold_df = pd.DataFrame(fold_rows)
    fold_df.to_csv(out_dir / "delta_selector_folds.csv", index=False)
    pd.Series(feature_cols, name="feature").to_csv(out_dir / "delta_selector_features.csv", index=False)
    expanded.iloc[0:0].to_csv(out_dir / "delta_selector_expanded_schema.csv", index=False)
    write_plot(out_dir, selected_df)

    overall = compute_metrics(selected_df, expected_months=expected, risk_capital=float(args.risk_capital))
    per_ticker = {
        ticker: compute_metrics(
            selected_df[selected_df["ticker"].astype(str).eq(ticker)].copy(),
            expected_months=expected,
            risk_capital=float(args.risk_capital),
        )
        for ticker in tickers
    } if not selected_df.empty else {}
    metrics_payload = {
        "overall": overall,
        "per_ticker": per_ticker,
        "folds": fold_rows,
        "args": vars(args),
        "feature_count": len(feature_cols),
        "raw_feature_count": len(raw_feature_cols),
        "history_rows": int(sum(len(x) for x in history_parts)),
        "test_rows": int(len(test_frame)),
        "expanded_rows": int(len(expanded)),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics_payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Same-Side Delta Selector",
        "",
        "Causal diagnostic: for each locked signal, keep the side and expiry fixed, then choose a delta bucket using a model trained only on earlier months.",
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
        "## Integrity",
        "",
        f"- Folds leak-ok: `{bool(fold_df['leak_ok'].all()) if not fold_df.empty else False}`",
        f"- History rows: `{metrics_payload['history_rows']}`",
        f"- Test rows: `{metrics_payload['test_rows']}`",
        f"- Expanded rows: `{metrics_payload['expanded_rows']}`",
        f"- Feature count: `{len(feature_cols)}`",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"overall": overall, "per_ticker": per_ticker}, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
