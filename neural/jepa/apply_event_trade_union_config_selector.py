from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apply_event_trade_union_meta_gate import apply_cooldown, parse_trade_source
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


_CHOOSE_FRAME: pd.DataFrame | None = None
_CHOOSE_MONTHS: list[str] | None = None
_CHOOSE_ARGS: argparse.Namespace | None = None


def resolve_trade_file(path: Path) -> Path:
    if path.is_file():
        return path
    candidates = [
        "combined_trades.csv",
        "static_union_trades.csv",
        "trade_union_topk_regressor_trades.csv",
        "trade_union_meta_trades.csv",
        "monthly_volume_backfill_trades.csv",
        "nested_volume_backfill_trades.csv",
        "intraday_circuit_trades.csv",
        "event_option_gate_trades.csv",
        "candidate_trade_meta_trades.csv",
        "regime_gate_trades.csv",
    ]
    found = next((path / name for name in candidates if (path / name).exists()), None)
    if found is None:
        raise FileNotFoundError(f"No known trade CSV found in {path}")
    return found


def derive_minute(frame: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for col in ("minute", "minute_x", "minute_y", "entry_minute"):
        if col in frame.columns:
            cand = pd.to_numeric(frame[col], errors="coerce")
            out = out.where(out.notna(), cand)
    missing = out.isna()
    if missing.any() and "time" in frame.columns:
        parsed = pd.to_datetime(frame.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def load_sources(specs: list[str], ticker: str) -> tuple[pd.DataFrame, list[str], dict[str, str]]:
    parts: list[pd.DataFrame] = []
    names: list[str] = []
    source_paths: dict[str, str] = {}
    for priority, spec in enumerate(specs):
        name, path, source_priority = parse_trade_source(spec, priority)
        path = resolve_trade_file(path)
        if not path.exists():
            raise FileNotFoundError(path)
        source_paths[name] = str(path)
        frame = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str}, low_memory=False)
        frame = frame[frame["ticker"].astype(str).str.upper() == str(ticker).upper()].copy()
        if frame.empty:
            continue
        if "test_month" not in frame.columns:
            frame["test_month"] = frame["month"].astype(str)
        if "month" not in frame.columns:
            frame["month"] = frame["test_month"].astype(str)
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame["date"] = frame["date"].astype(str)
        frame["time"] = frame["time"].astype(str)
        frame["expiry_mode"] = frame["expiry_mode"].astype(str) if "expiry_mode" in frame.columns else ""
        frame["source_variant"] = name
        frame["source_priority"] = int(source_priority)
        frame["score"] = pd.to_numeric(frame.get("score"), errors="coerce")
        frame["minute"] = derive_minute(frame)
        frame["realized_return"] = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
        parts.append(frame)
        names.append(name)
    if not parts:
        return pd.DataFrame(), [], source_paths
    return pd.concat(parts, ignore_index=True), names, source_paths


def source_groups(names: list[str], max_group_size: int) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    limit = min(len(names), max(1, int(max_group_size)))
    for size in range(1, limit + 1):
        for combo in combinations(names, size):
            groups.append(tuple(combo))
    return groups


def materialize_score_order(work: pd.DataFrame, max_day: int, cooldown: int) -> pd.DataFrame:
    ordered = work.sort_values(
        ["date", "score", "minute", "source_priority"],
        ascending=[True, False, True, True],
        kind="stable",
    )
    if int(cooldown) <= 0:
        return ordered.groupby("date", group_keys=False).head(int(max_day)).reset_index(drop=True)
    rows: list[dict] = []
    for _, day in ordered.groupby("date", sort=False):
        selected_minutes: list[int] = []
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if any(abs(minute - seen) < int(cooldown) for seen in selected_minutes):
                continue
            rows.append(row._asdict())
            selected_minutes.append(minute)
            taken += 1
            if taken >= int(max_day):
                break
    return pd.DataFrame(rows) if rows else work.iloc[0:0].copy()


def materialize_config(frame: pd.DataFrame, variants: tuple[str, ...], max_day: int, cooldown: int, daily_order: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame[frame["source_variant"].astype(str).isin(variants)].copy()
    if work.empty:
        return work
    if str(daily_order) == "score_desc":
        work = work.sort_values(
            ["date", "score", "minute", "source_priority"],
            ascending=[True, False, True, True],
            kind="stable",
        )
    elif str(daily_order) == "time_asc":
        work = work.sort_values(
            ["date", "minute", "source_priority", "score"],
            ascending=[True, True, True, False],
            kind="stable",
        )
    else:
        raise ValueError(f"Unknown daily_order {daily_order!r}")
    dedupe_cols = [col for col in ("date", "time", "action", "expiry_mode") if col in work.columns]
    if not dedupe_cols:
        dedupe_cols = ["date", "minute", "action", "expiry_mode"]
    work = work.drop_duplicates(dedupe_cols, keep="first").reset_index(drop=True)
    if str(daily_order) == "score_desc":
        return materialize_score_order(work, int(max_day), int(cooldown))
    return apply_cooldown(work, int(max_day), int(cooldown))


def score_row(row: dict, args: argparse.Namespace) -> float:
    if int(row.get("trades", 0)) < int(args.min_select_trades):
        return -1e18
    if int(row.get("min_month_trades", 0)) < int(args.min_select_month_trades):
        return -1e18
    pf = float(row.get("profit_factor", 0.0))
    wr = float(row.get("win_rate", 0.0))
    pnl_return = float(row.get("pnl_return", 0.0))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    daily_dd = abs(float(row.get("daily_max_drawdown", 0.0)))
    top5 = float(row.get("top5_share_of_pnl", 0.0))
    min_month = float(row.get("min_month_trades", 0.0))
    if not np.isfinite(pf):
        pf = float(args.score_pf_cap)
    if not np.isfinite(top5):
        top5 = 0.0
    return (
        min(pf, float(args.score_pf_cap)) * float(args.score_pf_weight)
        + wr * float(args.score_win_weight)
        + pnl_return * float(args.score_return_weight)
        + positive_month_rate * float(args.score_positive_month_weight)
        + min(min_month, 60.0) * float(args.score_volume_weight)
        - daily_dd * float(args.score_daily_dd_penalty)
        - max(top5 - 1.0, 0.0) * float(args.score_top5_penalty)
    )


def choose_config(select_frame: pd.DataFrame, select_months: list[str], configs: list[dict], args: argparse.Namespace) -> tuple[dict, dict, float]:
    workers = max(1, min(int(getattr(args, "workers", 1)), len(configs)))
    if workers > 1:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=init_choose_worker,
            initargs=(select_frame, list(select_months), vars(args)),
        ) as executor:
            scored = executor.map(
                score_config_worker,
                configs,
                chunksize=max(1, int(getattr(args, "chunksize", 8))),
            )
            best_cfg: dict | None = None
            best_metrics: dict | None = None
            best_score = -1e18
            for cfg, row, score in scored:
                if best_cfg is None or float(score) > best_score:
                    best_cfg = cfg
                    best_metrics = row
                    best_score = float(score)
            if best_cfg is None or best_metrics is None:
                raise RuntimeError("No config scores produced.")
            return best_cfg, best_metrics, float(best_score)

    best_cfg = configs[0]
    best_trades = materialize_config(
        select_frame,
        best_cfg["variants"],
        best_cfg["max_day"],
        best_cfg["cooldown"],
        best_cfg["daily_order"],
    )
    best_metrics = metrics(best_trades, select_months)
    best_score = score_row(best_metrics, args)
    for cfg in configs[1:]:
        trades = materialize_config(select_frame, cfg["variants"], cfg["max_day"], cfg["cooldown"], cfg["daily_order"])
        row = metrics(trades, select_months)
        score = score_row(row, args)
        if score > best_score:
            best_cfg = cfg
            best_metrics = row
            best_score = score
    return best_cfg, best_metrics, float(best_score)


def init_choose_worker(select_frame: pd.DataFrame, select_months: list[str], args_dict: dict) -> None:
    global _CHOOSE_FRAME, _CHOOSE_MONTHS, _CHOOSE_ARGS
    _CHOOSE_FRAME = select_frame
    _CHOOSE_MONTHS = select_months
    _CHOOSE_ARGS = argparse.Namespace(**args_dict)


def score_config_worker(cfg: dict) -> tuple[dict, dict, float]:
    if _CHOOSE_FRAME is None or _CHOOSE_MONTHS is None or _CHOOSE_ARGS is None:
        raise RuntimeError("Choose worker not initialized.")
    trades = materialize_config(
        _CHOOSE_FRAME,
        cfg["variants"],
        cfg["max_day"],
        cfg["cooldown"],
        cfg["daily_order"],
    )
    row = metrics(trades, _CHOOSE_MONTHS)
    return cfg, row, float(score_row(row, _CHOOSE_ARGS))


def flatten(prefix: str, row: dict | None) -> dict:
    return {f"{prefix}_{k}": v for k, v in (row or {}).items()}


def selected_source_paths(cfg: dict, source_paths: dict[str, str]) -> str:
    return "|".join(source_paths.get(str(name), "") for name in cfg["variants"] if source_paths.get(str(name), ""))


def walkforward_select(
    base: pd.DataFrame,
    configs: list[dict],
    source_paths: dict[str, str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = month_range(str(args.start_month), str(args.end_month))
    all_months = sorted(base["test_month"].astype(str).unique())
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for month in months:
        test = base[base["test_month"].astype(str) == str(month)].copy()
        previous = [m for m in all_months if m < str(month)]
        if test.empty:
            fold_rows.append({"month": str(month), "mode": "EMPTY"})
            continue
        if len(previous) < int(args.select_months):
            cfg = configs[0]
            select_months: list[str] = []
            select_metrics = metrics(pd.DataFrame(), [])
            select_score = float("nan")
            mode = "NO_HISTORY"
        else:
            select_months = previous[-int(args.select_months):]
            select = base[base["test_month"].astype(str).isin(select_months)].copy()
            cfg, select_metrics, select_score = choose_config(select, select_months, configs, args)
            mode = "SELECTED"
        selected = materialize_config(test, cfg["variants"], cfg["max_day"], cfg["cooldown"], cfg["daily_order"])
        if not selected.empty:
            selected["config_selector_mode"] = mode
            selected["selected_variants"] = ",".join(cfg["variants"])
            selected["selected_max_day"] = int(cfg["max_day"])
            selected["selected_cooldown"] = int(cfg["cooldown"])
            selected["selected_daily_order"] = str(cfg["daily_order"])
            out_parts.append(selected)
        row = {
            "ticker": str(args.ticker).upper(),
            "month": str(month),
            "mode": mode,
            "variants": ",".join(cfg["variants"]),
            "selected_source": ",".join(cfg["variants"]),
            "source_stream": "event_trade_union_config_selector",
            "source_path": selected_source_paths(cfg, source_paths),
            "max_day": int(cfg["max_day"]),
            "cooldown": int(cfg["cooldown"]),
            "daily_order": str(cfg["daily_order"]),
            "select_months": ",".join(select_months),
            "select_score": select_score,
        }
        row.update(flatten("select", select_metrics))
        row.update(flatten("test", metrics(selected, [str(month)])))
        fold_rows.append(row)
    out = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
    return out, pd.DataFrame(fold_rows)


def export_deploy_config(output_dir: Path, base: pd.DataFrame, names: list[str], configs: list[dict], args: argparse.Namespace) -> None:
    deploy_month = str(args.deploy_month).strip()
    if not deploy_month:
        raise RuntimeError("--export-deploy-config requires --deploy-month")
    deploy_select_end_month = str(args.deploy_select_end_month).strip()
    if deploy_select_end_month and deploy_select_end_month >= deploy_month:
        raise RuntimeError(
            f"--deploy-select-end-month {deploy_select_end_month} must be earlier than deploy month {deploy_month}"
        )
    all_months = sorted(base["test_month"].astype(str).unique())
    previous = [
        m
        for m in all_months
        if m < deploy_month and (not deploy_select_end_month or m <= deploy_select_end_month)
    ]
    if len(previous) < int(args.select_months):
        raise RuntimeError(f"Not enough prior months to export deploy config for {deploy_month}: {previous}")
    select_months = previous[-int(args.select_months):]
    select_frame = base[base["test_month"].astype(str).isin(select_months)].copy()
    if select_frame.empty:
        raise RuntimeError(f"No deploy selection rows in months {select_months}")
    cfg, select_metrics, select_score = choose_config(select_frame, select_months, configs, args)
    if float(select_score) <= -1e17 and not bool(args.allow_invalid_deploy_selection):
        raise RuntimeError(
            "Deploy union config selection failed validation for "
            f"{deploy_month} using select_months={select_months}; "
            "pass --allow-invalid-deploy-selection only for diagnostics."
        )
    selected = materialize_config(select_frame, cfg["variants"], cfg["max_day"], cfg["cooldown"], cfg["daily_order"])
    payload = {
        "schema_version": 1,
        "component": "event_trade_union_config_selector",
        "ticker": str(args.ticker).upper(),
        "deploy_month": deploy_month,
        "deploy_select_end_month": deploy_select_end_month or None,
        "select_months": select_months,
        "selected_variants": list(cfg["variants"]),
        "selected_max_day": int(cfg["max_day"]),
        "selected_cooldown": int(cfg["cooldown"]),
        "selected_daily_order": str(cfg["daily_order"]),
        "select_score": float(select_score),
        "select_metrics": select_metrics,
        "source_variants": names,
        "trade_sources": [str(x) for x in args.trade_source],
        "candidate_config_count": len(configs),
        "candidate_configs": configs,
        "args": vars(args),
    }
    deploy_dir = output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    (deploy_dir / "trade_union_config_selector.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )
    if not selected.empty:
        selected.to_csv(deploy_dir / "deploy_select_materialized_trades.csv", index=False)


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    pd.DataFrame({"date": idx.strftime("%Y%m%d"), "daily_pnl": daily.values, "cum_pnl": daily.cumsum().values}).to_csv(
        output_dir / "config_selector_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Trade Union Config Selector Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "config_selector_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, configs: list[dict], args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    by_ticker = {ticker: metrics(part, expected) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "candidate_configs": configs,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Trade Union Config Selector",
        "",
        "This result selects source variants, max trades per day, and cooldown walk-forward by test month using only prior out-of-sample months.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(by_ticker, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(args.risk_capital):,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        "",
        "## Folds",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Candidate Configs",
        "",
        "```json",
        json.dumps(configs, indent=2, allow_nan=True),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested walk-forward selector for event trade source/max-day/cooldown configurations.")
    parser.add_argument("--trade-source", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202507")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--max-source-group-size", type=int, default=3)
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[4, 6, 8, 12, 999])
    parser.add_argument("--cooldown-grid", nargs="+", type=int, default=[30, 45, 60])
    parser.add_argument("--daily-order-grid", nargs="+", default=["time_asc"], choices=["time_asc", "score_desc"])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--chunksize", type=int, default=8)
    parser.add_argument("--select-months", type=int, default=3)
    parser.add_argument("--min-select-trades", type=int, default=54)
    parser.add_argument("--min-select-month-trades", type=int, default=19)
    parser.add_argument("--score-pf-weight", type=float, default=3.0)
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight", type=float, default=20.0)
    parser.add_argument("--score-return-weight", type=float, default=0.10)
    parser.add_argument("--score-positive-month-weight", type=float, default=4.0)
    parser.add_argument("--score-volume-weight", type=float, default=0.10)
    parser.add_argument("--score-daily-dd-penalty", type=float, default=0.05)
    parser.add_argument("--score-top5-penalty", type=float, default=0.25)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--deploy-month", default="")
    parser.add_argument(
        "--deploy-select-end-month",
        default="",
        help="Optional latest completed YYYYMM allowed for deploy selection. Use this to exclude partial months.",
    )
    parser.add_argument("--export-deploy-config", action="store_true")
    parser.add_argument("--skip-walkforward", action="store_true", help="Only export deploy config; skip historical fold replay.")
    parser.add_argument(
        "--allow-invalid-deploy-selection",
        action="store_true",
        help="Write deploy config even when the selected validation window fails selection gates. Diagnostics only.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base, names, source_paths = load_sources(args.trade_source, args.ticker)
    if base.empty:
        raise RuntimeError("No input trades after ticker filtering.")
    base = base[
        (base["test_month"].astype(str) >= str(args.history_start_month))
        & (base["test_month"].astype(str) <= str(args.end_month))
    ].copy()
    groups = source_groups(names, int(args.max_source_group_size))
    configs = [
        {
            "variants": group,
            "max_day": int(max_day),
            "cooldown": int(cooldown),
            "daily_order": str(daily_order),
        }
        for group in groups
        for max_day in args.max_day_grid
        for cooldown in args.cooldown_grid
        for daily_order in args.daily_order_grid
    ]
    if not configs:
        raise RuntimeError("No candidate configs.")
    trades = pd.DataFrame()
    folds = pd.DataFrame()
    if not bool(args.skip_walkforward):
        trades, folds = walkforward_select(base, configs, source_paths, args)
        if not trades.empty:
            trades.to_csv(output_dir / "trade_union_config_selector_trades.csv", index=False)
        folds.to_csv(output_dir / "trade_union_config_selector_folds.csv", index=False)
        write_plot(output_dir, trades, float(args.risk_capital))
        write_summary(output_dir, trades, folds, configs, args)
    if bool(args.export_deploy_config):
        export_deploy_config(output_dir, base, names, configs, args)
    if (output_dir / "SUMMARY.md").exists():
        print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    else:
        print(json.dumps({"exported": bool(args.export_deploy_config), "output_dir": str(output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
