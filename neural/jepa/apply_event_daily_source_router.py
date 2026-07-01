from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


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


def parse_source(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw_path.strip())


def resolve_trade_file(path: Path) -> Path:
    if path.is_file():
        return path
    for name in (
        "daily_source_router_trades.csv",
        "monthly_volume_backfill_trades.csv",
        "stream_selector_trades.csv",
        "trade_union_topk_regressor_trades.csv",
        "nested_volume_backfill_trades.csv",
        "intraday_circuit_trades.csv",
        "event_option_gate_trades.csv",
        "volume_backfill_trades.csv",
        "combined_trades.csv",
        "selected_trades.csv",
    ):
        candidate = path / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(path)


def derive_minute(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for col in ("entry_minute", "minute", "minute_x", "minute_y"):
        if col in df.columns:
            cand = pd.to_numeric(df[col], errors="coerce")
            out = out.where(out.notna(), cand)
    missing = out.isna()
    if missing.any() and "time" in df.columns:
        parsed = pd.to_datetime(df.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def normalize_trade_source(
    name: str,
    path: Path,
    ticker: str,
    history_start_month: str,
    end_month: str,
    decision_minute: int,
    priority: int,
) -> pd.DataFrame:
    trade_file = resolve_trade_file(path)
    df = pd.read_csv(trade_file, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str})
    required = {"ticker", "date", "month", "time", "action", "realized_return"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{trade_file} missing required columns {missing}")
    df = df[df["ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
    if df.empty:
        return df
    if "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["date"] = df["date"].astype(str)
    df["month"] = df["month"].astype(str)
    df["test_month"] = df["test_month"].astype(str)
    df["time"] = df["time"].astype(str)
    df["action"] = df["action"].astype(str).str.upper()
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    df["entry_minute"] = derive_minute(df)
    df = df[
        (df["month"] >= str(history_start_month))
        & (df["month"] <= str(end_month))
        & (df["entry_minute"] >= int(decision_minute))
    ].copy()
    df["daily_source"] = name
    df["daily_source_path"] = str(trade_file)
    df["daily_source_priority"] = int(priority)
    df["_daily_source_order"] = np.arange(len(df), dtype=np.int64)
    if "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
    else:
        df["score"] = 0.0
    return df.reset_index(drop=True)


def load_sources(args: argparse.Namespace) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    sources: dict[str, pd.DataFrame] = {}
    source_files: dict[str, str] = {}
    for priority, raw in enumerate(args.source):
        name, path = parse_source(raw)
        frame = normalize_trade_source(
            name,
            path,
            str(args.ticker),
            str(args.history_start_month),
            str(args.end_month),
            int(args.decision_minute),
            priority,
        )
        sources[name] = frame
        source_files[name] = str(resolve_trade_file(path))
    if not sources:
        raise RuntimeError("No sources supplied.")
    if all(frame.empty for frame in sources.values()):
        raise RuntimeError("No source trades after filtering.")
    return sources, source_files


def feature_snapshots(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_parquet(args.data)
    raw = raw[raw["ticker"].astype(str).str.upper().eq(str(args.ticker).upper())].copy()
    raw["date"] = raw["trade_date"].astype(str)
    raw["month"] = raw["date"].str[:6]
    raw["minute"] = pd.to_numeric(raw["minute"], errors="coerce").fillna(-1).astype(int)
    raw = raw[
        (raw["month"] >= str(args.history_start_month))
        & (raw["month"] <= str(args.end_month))
        & (raw["minute"] <= int(args.decision_minute))
    ].copy()
    if raw.empty:
        return raw, []
    raw = raw.sort_values(["date", "minute"], kind="stable").groupby("date", as_index=False).tail(1)
    raw = raw.sort_values("date", kind="stable").reset_index(drop=True)

    cats = [col for col in ("expiry_mode", "nearest_level_name") if col in raw.columns and bool(args.include_categoricals)]
    if cats:
        raw = pd.concat([raw, pd.get_dummies(raw[cats].astype(str), prefix=cats, dtype=float)], axis=1)

    blocked = {
        "ticker",
        "underlying_ticker",
        "trade_date",
        "date",
        "month",
        "expiration",
        "timestamp",
        "time",
        "minute",
        "expiry_mode",
        "nearest_level_name",
    }
    feature_cols: list[str] = []
    dummy_prefixes = tuple(f"{col}_" for col in cats)
    for col in raw.columns:
        low = str(col).lower()
        if col in blocked:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if not bool(args.include_latent_vectors) and (
            str(col).startswith("ptdj_z_")
            or str(col).startswith("ptdj_dz_")
            or str(col).startswith("ptdj_phys_")
            or str(col).startswith("ptdj_phys_delta_")
        ):
            continue
        if str(col).startswith(dummy_prefixes) or pd.api.types.is_numeric_dtype(raw[col]):
            series = pd.to_numeric(raw[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            if series.notna().sum() >= int(args.min_feature_observations) and series.nunique(dropna=True) > 1:
                raw[col] = series
                feature_cols.append(col)
    keep = ["date", "month", "minute"] + feature_cols
    return raw[keep].copy(), feature_cols


def build_daily_training_frame(
    snapshots: pd.DataFrame,
    sources: dict[str, pd.DataFrame],
    base_feature_cols: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    if snapshots.empty:
        return pd.DataFrame(), []
    daily_returns: dict[tuple[str, str], float] = {}
    daily_counts: dict[tuple[str, str], int] = {}
    for source_name, trades in sources.items():
        if trades.empty:
            continue
        grouped = trades.groupby("date")["realized_return"].agg(["sum", "count"])
        for date, row in grouped.iterrows():
            key = (str(date), source_name)
            daily_returns[key] = float(row["sum"])
            daily_counts[key] = int(row["count"])

    parts: list[pd.DataFrame] = []
    source_names = list(sources.keys())
    for priority, source_name in enumerate(source_names):
        part = snapshots.copy()
        part["daily_source"] = source_name
        part["daily_source_priority"] = int(priority)
        part["daily_target_return"] = [daily_returns.get((str(date), source_name), 0.0) for date in part["date"]]
        part["daily_source_trade_count"] = [daily_counts.get((str(date), source_name), 0) for date in part["date"]]
        for other in source_names:
            part[f"source_is_{other}"] = 1.0 if other == source_name else 0.0
        parts.append(part)
    out = pd.concat(parts, ignore_index=True, sort=False)
    source_cols = [f"source_is_{name}" for name in source_names]
    return out, base_feature_cols + source_cols


def source_history(train: pd.DataFrame, args: argparse.Namespace) -> tuple[dict[str, dict[str, float]], set[str]]:
    out: dict[str, dict[str, float]] = {}
    eligible: set[str] = set()
    if train.empty:
        return out, eligible
    for source_name, part in train.groupby("daily_source", sort=True):
        counts = pd.to_numeric(part["daily_source_trade_count"], errors="coerce").fillna(0.0)
        rets = pd.to_numeric(part["daily_target_return"], errors="coerce").fillna(0.0)
        trade_days = int((counts > 0.0).sum())
        trades = int(counts.sum())
        pnl_return = float(rets.sum())
        row = {
            "trade_days": float(trade_days),
            "trades": float(trades),
            "pnl_return": pnl_return,
        }
        out[str(source_name)] = row
        if trade_days >= int(args.min_source_train_days) and trades >= int(args.min_source_train_trades):
            eligible.add(str(source_name))
    if not eligible and bool(args.allow_all_sources_if_none_eligible):
        eligible = set(out.keys())
    return out, eligible


def fit_daily_source_model(
    train: pd.DataFrame,
    feature_cols: list[str],
    args: argparse.Namespace,
) -> tuple[lgb.LGBMRegressor, pd.Series, dict[str, dict[str, float]], set[str], int]:
    train_days = int(train["date"].nunique())
    history, eligible_sources = source_history(train, args)
    if train_days < int(args.min_train_days) or len(train) < int(args.min_train_rows):
        raise RuntimeError(
            f"Insufficient daily-router train rows: train_days={train_days}, rows={len(train)}, "
            f"required_days={args.min_train_days}, required_rows={args.min_train_rows}"
        )
    y = pd.to_numeric(train["daily_target_return"], errors="coerce").fillna(0.0).clip(
        lower=-float(args.clip_target),
        upper=float(args.clip_target),
    )
    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = 1.0 + np.minimum(y.abs().to_numpy(dtype=float), 2.0)
    model = lgb.LGBMRegressor(
        objective=str(args.objective),
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
    model.fit(x_train, y, sample_weight=weights)
    return model, medians, history, eligible_sources, train_days


def score_daily_sources(
    model: lgb.LGBMRegressor,
    medians: pd.Series,
    frame: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    scored = frame.copy()
    x_score = scored[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    scored["daily_router_pred_return"] = model.predict(x_score)
    return scored


def fit_month_router(
    daily: pd.DataFrame,
    feature_cols: list[str],
    test_month: str,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    train_months = sorted(m for m in daily["month"].astype(str).unique() if m < str(test_month))
    test = daily[daily["month"].astype(str).eq(str(test_month))].copy()
    if test.empty:
        return test, test, {
            "ticker": str(args.ticker).upper(),
            "test_month": str(test_month),
            "mode": "EMPTY",
            "train_months": ",".join(train_months),
            "train_days": 0,
            "feature_count": len(feature_cols),
        }
    train = daily[daily["month"].astype(str).isin(train_months)].copy()
    train_days = int(train["date"].nunique())
    history, eligible_sources = source_history(train, args)
    if train_days < int(args.min_train_days) or len(train) < int(args.min_train_rows):
        scored = test.copy()
        scored["daily_router_pred_return"] = np.nan
        scored["daily_router_source_train_days"] = [
            float(history.get(str(source), {}).get("trade_days", 0.0)) for source in scored["daily_source"].astype(str)
        ]
        scored["daily_router_source_train_trades"] = [
            float(history.get(str(source), {}).get("trades", 0.0)) for source in scored["daily_source"].astype(str)
        ]
        scored["daily_router_source_eligible"] = scored["daily_source"].astype(str).isin(eligible_sources)
        scored["_eligible_pred_return"] = np.nan
        out = test.sort_values(["date", "daily_source_priority"], kind="stable").groupby("date", as_index=False).head(1)
        out["daily_router_pred_return"] = np.nan
        return out, scored, {
            "ticker": str(args.ticker).upper(),
            "test_month": str(test_month),
            "mode": "NO_HISTORY",
            "train_months": ",".join(train_months),
            "train_days": train_days,
            "train_rows": int(len(train)),
            "feature_count": len(feature_cols),
            "source_history": json.dumps(history, sort_keys=True),
            "eligible_sources": ",".join(sorted(eligible_sources)),
            "chosen_counts": json.dumps(out["daily_source"].value_counts().to_dict(), sort_keys=True),
        }

    model, medians, history, eligible_sources, train_days = fit_daily_source_model(train, feature_cols, args)
    scored = score_daily_sources(model, medians, test, feature_cols)
    scored["daily_router_source_train_days"] = [
        float(history.get(str(source), {}).get("trade_days", 0.0)) for source in scored["daily_source"].astype(str)
    ]
    scored["daily_router_source_train_trades"] = [
        float(history.get(str(source), {}).get("trades", 0.0)) for source in scored["daily_source"].astype(str)
    ]
    scored["daily_router_source_eligible"] = scored["daily_source"].astype(str).isin(eligible_sources)
    score_col = "daily_router_pred_return"
    if int(args.min_source_train_days) > 0 or int(args.min_source_train_trades) > 0:
        scored["_eligible_pred_return"] = np.where(
            scored["daily_router_source_eligible"],
            pd.to_numeric(scored["daily_router_pred_return"], errors="coerce"),
            -np.inf,
        )
        score_col = "_eligible_pred_return"
    chosen = (
        scored.sort_values(
            ["date", score_col, "daily_source_priority"],
            ascending=[True, False, True],
            kind="stable",
        )
        .groupby("date", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    return chosen, scored, {
        "ticker": str(args.ticker).upper(),
        "test_month": str(test_month),
        "mode": "DAILY_SOURCE_REG",
        "train_months": ",".join(train_months),
        "train_days": train_days,
        "train_rows": int(len(train)),
        "test_days": int(test["date"].nunique()),
        "feature_count": len(feature_cols),
        "source_history": json.dumps(history, sort_keys=True),
        "eligible_sources": ",".join(sorted(eligible_sources)),
        "chosen_counts": json.dumps(chosen["daily_source"].value_counts().to_dict(), sort_keys=True),
    }


def trades_for_choices(
    choices: pd.DataFrame,
    sources: dict[str, pd.DataFrame],
    fold: dict,
    args: argparse.Namespace,
) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    pred_by_key = {
        (str(row.date), str(row.daily_source)): float(row.daily_router_pred_return)
        if pd.notna(row.daily_router_pred_return)
        else np.nan
        for row in choices.itertuples(index=False)
    }
    chosen_dates = {(str(row.date), str(row.daily_source)) for row in choices.itertuples(index=False)}
    for source_name, trades in sources.items():
        if trades.empty:
            continue
        dates = {date for date, source in chosen_dates if source == source_name}
        if not dates:
            continue
        part = trades[trades["date"].astype(str).isin(dates)].copy()
        if part.empty:
            continue
        part = part[part["month"].astype(str).eq(str(fold["test_month"]))].copy()
        if part.empty:
            continue
        part["daily_router_source"] = source_name
        part["daily_router_mode"] = str(fold["mode"])
        part["daily_router_train_months"] = str(fold.get("train_months", ""))
        part["daily_router_feature_count"] = int(fold.get("feature_count", 0))
        part["daily_router_pred_return"] = [
            pred_by_key.get((str(date), source_name), np.nan) for date in part["date"].astype(str)
        ]
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    out = out.sort_values(["date", "entry_minute", "daily_source_priority", "score", "_daily_source_order"], ascending=[True, True, True, False, True], kind="stable")
    return out.reset_index(drop=True)


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work = work[work["dt"].notna()].copy()
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    pd.DataFrame({"date": idx.strftime("%Y%m%d"), "daily_pnl": daily.values, "cum_pnl": daily.cumsum().values}).to_csv(
        output_dir / "daily_source_router_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Daily Source Router Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "daily_source_router_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, choices: pd.DataFrame, source_files: dict[str, str], args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, months)
    monthly = []
    for month in months:
        row = metrics(trades[trades["month"].astype(str).eq(month)].copy() if not trades.empty else trades, [month])
        row["month"] = month
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly.append(row)
    by_source = {
        source: metrics(part, months)
        for source, part in trades.groupby("daily_router_source", sort=True)
    } if not trades.empty and "daily_router_source" in trades.columns else {}
    payload = {
        "overall": overall,
        "monthly": monthly,
        "by_source": by_source,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "sources": source_files,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Daily Source Router",
        "",
        "This result trains one source router per evaluated month using only prior daily OOS source returns and market snapshots available at or before the decision minute.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(args.risk_capital):,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        "",
        "## Monthly",
        "",
        "| Month | Trades | WR | PF | PnL Return | PnL $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in monthly:
        lines.append(
            f"| {row['month']} | {int(row['trades'])} | {float(row['win_rate']):.1%} | "
            f"{float(row['profit_factor']):.3f} | {float(row['pnl_return']):.3f} | "
            f"{float(row['pnl_dollars']):,.0f} |"
        )
    lines += [
        "",
        "## By Selected Source",
        "",
        "```json",
        json.dumps(by_source, indent=2, allow_nan=True),
        "```",
        "",
        "## Folds",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Daily Choices",
        "",
        f"- Rows: {len(choices)}",
        "",
        "Full per-source scored candidates are written to `daily_source_router_scored_candidates.csv`.",
        "",
        "## Sources",
        "",
        "```json",
        json.dumps(source_files, indent=2),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def export_deploy_model(
    output_dir: Path,
    daily: pd.DataFrame,
    feature_cols: list[str],
    source_files: dict[str, str],
    args: argparse.Namespace,
) -> None:
    deploy_month = str(args.deploy_month).strip()
    deploy_train_end_month = str(args.deploy_train_end_month).strip()
    if not deploy_month:
        raise RuntimeError("--export-deploy-model requires --deploy-month")
    if deploy_train_end_month:
        if deploy_train_end_month >= deploy_month:
            raise RuntimeError(
                f"--deploy-train-end-month {deploy_train_end_month} must be earlier than deploy month {deploy_month}"
            )
        train_months = sorted(
            m for m in daily["month"].astype(str).unique() if m < deploy_month and m <= deploy_train_end_month
        )
    else:
        train_months = sorted(m for m in daily["month"].astype(str).unique() if m < deploy_month)
    train = daily[daily["month"].astype(str).isin(train_months)].copy()
    model, medians, history, eligible_sources, train_days = fit_daily_source_model(train, feature_cols, args)
    payload = {
        "schema_version": 1,
        "component": "event_daily_source_router",
        "ticker": str(args.ticker).upper(),
        "deploy_month": deploy_month,
        "deploy_train_end_month": deploy_train_end_month or None,
        "train_months": train_months,
        "train_days": int(train_days),
        "train_rows": int(len(train)),
        "feature_cols": feature_cols,
        "feature_medians": {str(k): float(v) if np.isfinite(float(v)) else 0.0 for k, v in medians.fillna(0.0).items()},
        "source_history": history,
        "eligible_sources": sorted(eligible_sources),
        "source_files": source_files,
        "args": vars(args),
    }
    deploy_dir = output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    with (deploy_dir / "daily_source_router_model.pkl").open("wb") as fh:
        pickle.dump({"model": model, "medians": medians, "feature_cols": feature_cols, "metadata": payload}, fh)
    (deploy_dir / "daily_source_router_model.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal daily router across precomputed event-option source streams.")
    parser.add_argument("--source", action="append", required=True, help="NAME=folder_or_trades.csv")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202507")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--decision-minute", type=int, default=660)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--include-latent-vectors", action="store_true")
    parser.add_argument("--include-categoricals", action="store_true")
    parser.add_argument("--min-feature-observations", type=int, default=50)
    parser.add_argument("--min-train-days", type=int, default=40)
    parser.add_argument("--min-train-rows", type=int, default=80)
    parser.add_argument("--min-source-train-days", type=int, default=0)
    parser.add_argument("--min-source-train-trades", type=int, default=0)
    parser.add_argument("--allow-all-sources-if-none-eligible", action="store_true")
    parser.add_argument("--clip-target", type=float, default=2.5)
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=7)
    parser.add_argument("--min-child-samples", type=int, default=16)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.75)
    parser.add_argument("--reg-lambda", type=float, default=8.0)
    parser.add_argument("--lgb-jobs", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260621)
    parser.add_argument("--deploy-month", default="")
    parser.add_argument(
        "--deploy-train-end-month",
        default="",
        help="Optional latest completed YYYYMM allowed for deploy router training. Use this to exclude partial months.",
    )
    parser.add_argument("--export-deploy-model", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sources, source_files = load_sources(args)
    snapshots, base_feature_cols = feature_snapshots(args)
    daily, feature_cols = build_daily_training_frame(snapshots, sources, base_feature_cols)
    if daily.empty:
        raise RuntimeError("No daily rows available for routing.")

    months = month_range(str(args.start_month), str(args.end_month))
    choice_parts: list[pd.DataFrame] = []
    scored_candidate_parts: list[pd.DataFrame] = []
    trade_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for month in months:
        choices, scored_candidates, fold = fit_month_router(daily, feature_cols, month, args)
        choices["test_month"] = str(month)
        choices["daily_router_mode"] = str(fold["mode"])
        choice_parts.append(choices)
        scored_candidates["test_month"] = str(month)
        scored_candidates["daily_router_mode"] = str(fold["mode"])
        scored_candidate_parts.append(scored_candidates)
        selected = trades_for_choices(choices, sources, fold, args)
        test_metrics = metrics(selected, [str(month)])
        fold.update({f"test_{key}": value for key, value in test_metrics.items()})
        fold["source_files"] = json.dumps(source_files, sort_keys=True)
        fold_rows.append(fold)
        if not selected.empty:
            trade_parts.append(selected)

    choices = pd.concat(choice_parts, ignore_index=True, sort=False) if choice_parts else pd.DataFrame()
    scored_candidates = pd.concat(scored_candidate_parts, ignore_index=True, sort=False) if scored_candidate_parts else pd.DataFrame()
    trades = pd.concat(trade_parts, ignore_index=True, sort=False) if trade_parts else pd.DataFrame()
    if not trades.empty:
        trades = trades.sort_values(["date", "entry_minute", "ticker", "daily_router_source"], kind="stable").reset_index(drop=True)
    folds = pd.DataFrame(fold_rows)

    trades.to_csv(output_dir / "daily_source_router_trades.csv", index=False)
    trades.to_csv(output_dir / "selected_trades.csv", index=False)
    choices.to_csv(output_dir / "daily_source_router_choices.csv", index=False)
    scored_candidates.to_csv(output_dir / "daily_source_router_scored_candidates.csv", index=False)
    folds.to_csv(output_dir / "daily_source_router_folds.csv", index=False)
    folds.to_csv(output_dir / "fold_configs.csv", index=False)
    pd.DataFrame({"feature": feature_cols}).to_csv(output_dir / "daily_source_router_features.csv", index=False)
    pd.DataFrame([vars(args)]).to_csv(output_dir / "daily_source_router_config.csv", index=False)
    if bool(args.export_deploy_model):
        export_deploy_model(output_dir, daily, feature_cols, source_files, args)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, choices, source_files, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
