from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import DeployConfig, deploy, metrics, score_metrics
from walkforward_event_option_profile_selector import ProfileConfig, prepare_profile, load_raw


DEPLOY_RE = re.compile(r"^thr(?P<threshold>-?\d+(?:\.\d+)?)_maxday(?P<maxday>all|\d+)$")


BASE_REGIME_FEATURES = [
    "score",
    "score_margin",
    "minute",
    "dte_days",
    "ib_range_bps",
    "nearest_level_abs_bps",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "dist_fib_127_up_bps",
    "dist_fib_161_up_bps",
    "dist_fib_200_up_bps",
    "dist_fib_127_dn_bps",
    "dist_fib_161_dn_bps",
    "dist_fib_200_dn_bps",
    "underlying_volume",
    "action_abs_delta",
    "action_iv",
    "action_mid_bps",
    "action_spread_pct",
    "action_theta_over_mid",
    "action_vega",
    "action_oi",
    "action_volume",
]


def parse_deploy_config(name: str) -> DeployConfig:
    match = DEPLOY_RE.match(str(name))
    if not match:
        raise ValueError(f"cannot parse deploy_config: {name}")
    max_day = 999 if match.group("maxday") == "all" else int(match.group("maxday"))
    return DeployConfig(float(match.group("threshold")), max_day)


def profile_from_row(row: pd.Series) -> ProfileConfig:
    expiry_raw = str(row.get("expiry_modes", "mixed"))
    expiry_modes = tuple() if expiry_raw in {"", "mixed", "nan"} else tuple(part for part in expiry_raw.split(",") if part)
    return ProfileConfig(
        name=str(row["profile"]),
        delta_bucket=int(row["delta_bucket"]),
        label_mode=str(row["label_mode"]),
        expiry_modes=expiry_modes,
        train_scope=str(row["train_scope"]),
    )


def parse_train_tickers(row: pd.Series) -> list[str]:
    raw = str(row.get("train_tickers", ""))
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def add_action_context(scored: pd.DataFrame, delta_bucket: int) -> pd.DataFrame:
    out = scored.copy()
    call_cols = {
        "action_abs_delta": f"call_d{delta_bucket:02d}_abs_delta",
        "action_iv": f"call_d{delta_bucket:02d}_iv",
        "action_mid_bps": f"call_d{delta_bucket:02d}_mid_bps",
        "action_spread_pct": f"call_d{delta_bucket:02d}_spread_pct",
        "action_theta_over_mid": f"call_d{delta_bucket:02d}_theta_over_mid",
        "action_vega": f"call_d{delta_bucket:02d}_vega",
        "action_oi": f"call_d{delta_bucket:02d}_oi",
        "action_volume": f"call_d{delta_bucket:02d}_volume",
    }
    put_cols = {target: source.replace("call_", "put_", 1) for target, source in call_cols.items()}
    is_call = out["action"].astype(str).eq("CALL")
    for target, call_col in call_cols.items():
        put_col = put_cols[target]
        call_val = pd.to_numeric(out[call_col], errors="coerce") if call_col in out else np.nan
        put_val = pd.to_numeric(out[put_col], errors="coerce") if put_col in out else np.nan
        out[target] = np.where(is_call, call_val, put_val)
    out["score_margin"] = (pd.to_numeric(out["pred_call_return"], errors="coerce") - pd.to_numeric(out["pred_put_return"], errors="coerce")).abs()
    return out


def fit_and_score_fold(
    prepared,
    row: pd.Series,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    profile = prepared.config
    frame = prepared.frame
    feature_cols = prepared.feature_cols
    ticker = str(row["ticker"]).upper()
    month = str(row["month"])
    val_months = [part for part in str(row["val_months"]).split(",") if part]
    train_tickers = parse_train_tickers(row)
    first_val = val_months[0]
    train = frame[(frame["month"].astype(str) < first_val) & (frame["ticker"].astype(str).isin(train_tickers))].copy()
    val = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str).isin(val_months))].copy()
    test = frame[(frame["ticker"].astype(str) == ticker) & (frame["month"].astype(str) == month)].copy()
    if train.empty or val.empty or test.empty:
        return pd.DataFrame(), pd.DataFrame()

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    if profile.label_mode == "win":
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
        random_state=int(args.seed) + int(month[-2:]),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    if profile.label_mode == "win":
        call_model = lgb.LGBMClassifier(**{**params, "objective": "binary"})
        put_model = lgb.LGBMClassifier(**{**params, "objective": "binary", "random_state": int(params["random_state"]) + 10_000})
    else:
        call_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective)})
        put_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective), "random_state": int(params["random_state"]) + 10_000})
    call_model.fit(x_train, y_call)
    put_model.fit(x_train, y_put)

    def score(part: pd.DataFrame) -> pd.DataFrame:
        x = part[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out = part.copy()
        if profile.label_mode == "win":
            out["pred_call_return"] = call_model.predict_proba(x)[:, 1]
            out["pred_put_return"] = put_model.predict_proba(x)[:, 1]
        else:
            out["pred_call_return"] = call_model.predict(x)
            out["pred_put_return"] = put_model.predict(x)
        is_call = out["pred_call_return"].astype(float) >= out["pred_put_return"].astype(float)
        out["action"] = np.where(is_call, "CALL", "PUT")
        out["score"] = np.where(is_call, out["pred_call_return"], out["pred_put_return"])
        out["realized_return"] = np.where(is_call, out["call_return"], out["put_return"])
        return add_action_context(out, int(profile.delta_bucket))

    cfg = parse_deploy_config(str(row["deploy_config"]))
    val_trades = deploy(score(val), cfg, int(args.cooldown_minutes))
    test_trades = deploy(score(test), cfg, int(args.cooldown_minutes))
    for part in (val_trades, test_trades):
        if part.empty:
            continue
        part["profile"] = profile.name
        part["profile_deploy_config"] = cfg.name
        part["delta_bucket"] = int(profile.delta_bucket)
        part["label_mode"] = profile.label_mode
        part["profile_expiry_modes"] = ",".join(profile.expiry_modes) if profile.expiry_modes else "mixed"
        part["train_scope"] = profile.train_scope
        part["test_month"] = month
    return val_trades, test_trades


def gate_mask(df: pd.DataFrame, feature: str, lower: float, upper: float) -> pd.Series:
    if feature == "NONE":
        return pd.Series(True, index=df.index)
    values = pd.to_numeric(df[feature], errors="coerce")
    return values.between(float(lower), float(upper), inclusive="both")


def choose_gate(val_trades: pd.DataFrame, val_months: list[str], args: argparse.Namespace) -> dict:
    none_metrics = metrics(val_trades, val_months)
    best = {
        "feature": "NONE",
        "lower": float("-inf"),
        "upper": float("inf"),
        "score": score_metrics(
            none_metrics,
            int(args.gate_min_val_trades),
            int(args.gate_min_month_trades),
            float(args.gate_min_val_pf),
            float(args.gate_min_val_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        ),
        "metrics": none_metrics,
    }
    features = [f for f in BASE_REGIME_FEATURES if f in val_trades.columns]
    quantile_pairs = [
        (0.0, 0.80),
        (0.0, 0.90),
        (0.10, 1.0),
        (0.20, 1.0),
        (0.10, 0.90),
        (0.20, 0.80),
        (0.0, 0.50),
        (0.50, 1.0),
        (0.0, 0.33),
        (0.33, 0.67),
        (0.67, 1.0),
    ]
    for feature in features:
        values = pd.to_numeric(val_trades[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if values.nunique() < 5:
            continue
        for q_low, q_high in quantile_pairs:
            lower = float(values.quantile(q_low))
            upper = float(values.quantile(q_high))
            if not np.isfinite(lower) or not np.isfinite(upper) or lower > upper:
                continue
            filtered = val_trades[gate_mask(val_trades, feature, lower, upper)].copy()
            row = metrics(filtered, val_months)
            score = score_metrics(
                row,
                int(args.gate_min_val_trades),
                int(args.gate_min_month_trades),
                float(args.gate_min_val_pf),
                float(args.gate_min_val_win_rate),
                float(args.min_call_rate),
                float(args.max_call_rate),
            )
            if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
                score += float(args.daily_win_weight) * float(row["daily_win_rate"])
            if score > float(best["score"]):
                best = {"feature": feature, "lower": lower, "upper": upper, "score": float(score), "metrics": row}
    return best


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = work["realized_return"].astype(float) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(daily.index, daily.cumsum(), color="#111827", linewidth=2.4, label="TOTAL")
    for ticker, part in work.groupby("ticker"):
        curve = part.groupby("dt")["pnl"].sum().sort_index().reindex(idx).fillna(0.0).cumsum()
        axes[0].plot(curve.index, curve.values, linewidth=1.6, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Selected Event Profiles + Regime Gate, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    colors = np.where(daily >= 0.0, "#16a34a", "#dc2626")
    axes[1].bar(daily.index, daily.values, color=colors, width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "regime_gate_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, metadata: dict) -> None:
    expected = month_range(str(metadata["args"]["start_month"]), str(metadata["args"]["end_month"]))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    payload = {"overall": overall, "per_ticker": per_ticker, "metadata": metadata}
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Profile Regime Gate",
        "",
        "Uses selected event-profile folds as input. For each ticker-month, model/profile/threshold are fixed from the upstream selected fold; this script only chooses a simple one-feature regime gate on validation trades and applies it to the test-month deployed trades.",
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
        "## Folds",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply causal validation-only regime gates to selected event profile folds.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--selected-folds", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument("--gate-min-val-trades", type=int, default=45)
    parser.add_argument("--gate-min-month-trades", type=int, default=12)
    parser.add_argument("--gate-min-val-pf", type=float, default=1.20)
    parser.add_argument("--gate-min-val-win-rate", type=float, default=0.42)
    parser.add_argument("--min-call-rate", type=float, default=0.15)
    parser.add_argument("--max-call-rate", type=float, default=0.85)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--seed", type=int, default=20260618)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = pd.read_csv(args.selected_folds)
    selected = selected[(selected["month"].astype(str) >= str(args.start_month)) & (selected["month"].astype(str) <= str(args.end_month))].copy()
    all_tickers = sorted({t for raw in selected["train_tickers"].astype(str) for t in raw.split(",") if t} | set(selected["ticker"].astype(str)))
    raw = load_raw(args.data, all_tickers)
    prepared_cache: dict[str, object] = {}
    all_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []

    for _, row in selected.iterrows():
        profile = profile_from_row(row)
        if profile.name not in prepared_cache:
            prepared_cache[profile.name] = prepare_profile(raw, profile, float(args.clip_return))
        val_trades, test_trades = fit_and_score_fold(prepared_cache[profile.name], row, args)
        val_months = [part for part in str(row["val_months"]).split(",") if part]
        gate = choose_gate(val_trades, val_months, args)
        if test_trades.empty:
            gated_test = test_trades
        else:
            gated_test = test_trades[gate_mask(test_trades, str(gate["feature"]), float(gate["lower"]), float(gate["upper"]))].copy()
            gated_test["regime_gate"] = str(gate["feature"])
            gated_test["regime_gate_lower"] = float(gate["lower"])
            gated_test["regime_gate_upper"] = float(gate["upper"])
        test_metrics = metrics(gated_test, [str(row["month"])])
        if not gated_test.empty:
            all_trades.append(gated_test)
        fold = {
            "ticker": str(row["ticker"]),
            "month": str(row["month"]),
            "profile": profile.name,
            "deploy_config": str(row["deploy_config"]),
            "val_months": str(row["val_months"]),
            "gate_feature": str(gate["feature"]),
            "gate_lower": float(gate["lower"]),
            "gate_upper": float(gate["upper"]),
            "gate_score": float(gate["score"]),
            **{f"gate_val_{k}": v for k, v in dict(gate["metrics"]).items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        }
        fold_rows.append(fold)
        print(
            f"[REGIME_GATE] {fold['ticker']} {fold['month']} profile={profile.name} "
            f"gate={fold['gate_feature']} test_trades={fold['test_trades']} "
            f"test_pf={fold['test_profit_factor']:.3f} test_ret={fold['test_pnl_return']:.2f}",
            flush=True,
        )

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "regime_gate_trades.csv", index=False)
        write_plot(output_dir, trades, float(args.risk_capital))
    folds.to_csv(output_dir / "regime_gate_folds.csv", index=False)
    metadata = {"args": vars(args), "selected_folds_rows": int(len(selected)), "profiles": sorted(prepared_cache.keys())}
    write_summary(output_dir, trades, folds, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
