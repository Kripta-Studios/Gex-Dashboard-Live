from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations, product
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apply_event_monthly_volume_backfill import apply_backfill
from apply_event_trade_union_config_selector import derive_minute, resolve_trade_file
from apply_event_trade_union_meta_gate import parse_trade_source
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


_WORKER_FRAME: pd.DataFrame | None = None
_WORKER_SELECT_MONTHS: list[str] | None = None
_WORKER_ARGS: argparse.Namespace | None = None
_PRIMARY_CACHE: dict[tuple[int, tuple[str, ...], int, int, float, str], pd.DataFrame] = {}


def load_sources(specs: list[str], ticker: str) -> tuple[pd.DataFrame, list[str], dict[str, str]]:
    parts: list[pd.DataFrame] = []
    names: list[str] = []
    source_paths: dict[str, str] = {}
    for priority, spec in enumerate(specs):
        name, path, source_priority = parse_trade_source(spec, priority)
        path = resolve_trade_file(path)
        if not path.exists():
            raise FileNotFoundError(path)
        names.append(name)
        source_paths[name] = str(path)
        frame = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str}, low_memory=False)
        frame = frame[frame["ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
        if frame.empty:
            continue
        if "test_month" not in frame.columns:
            frame["test_month"] = frame["month"].astype(str)
        if "month" not in frame.columns:
            frame["month"] = frame["test_month"].astype(str)
        frame["ticker"] = frame["ticker"].astype(str).str.upper()
        frame["date"] = frame["date"].astype(str)
        frame["month"] = frame["test_month"].astype(str)
        frame["test_month"] = frame["test_month"].astype(str)
        frame["time"] = frame["time"].astype(str)
        frame["action"] = frame["action"].astype(str).str.upper()
        frame["expiry_mode"] = frame["expiry_mode"].astype(str) if "expiry_mode" in frame.columns else ""
        frame["source_variant"] = name
        frame["source_stream"] = name
        frame["source_priority"] = int(source_priority)
        frame["entry_minute"] = derive_minute(frame)
        frame["minute"] = frame["entry_minute"]
        frame["score"] = pd.to_numeric(frame.get("score"), errors="coerce").fillna(0.0)
        frame["realized_return"] = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
        frame["_source_order"] = np.arange(len(frame), dtype=np.int64)
        parts.append(frame)
    if not parts:
        return pd.DataFrame(), names, source_paths
    return pd.concat(parts, ignore_index=True, sort=False), names, source_paths


def source_groups(names: list[str], max_group_size: int) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    for size in range(1, min(len(names), int(max_group_size)) + 1):
        groups.extend(tuple(group) for group in combinations(names, size))
    return groups


def materialize_primary(frame: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    variants = tuple(str(x) for x in cfg["variants"])
    cache_key = (
        id(frame),
        variants,
        int(cfg.get("max_day", 999)),
        int(cfg.get("cooldown", 0)),
        float(cfg.get("min_score", -math.inf)),
        str(cfg.get("daily_order", "score_desc")),
    )
    cached = _PRIMARY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    work = frame[frame["source_variant"].astype(str).isin(variants)].copy()
    if work.empty:
        _PRIMARY_CACHE[cache_key] = work
        return work
    min_score = float(cfg.get("min_score", -math.inf))
    if math.isfinite(min_score):
        work = work[pd.to_numeric(work["score"], errors="coerce").fillna(float("-inf")) >= min_score].copy()
    if work.empty:
        _PRIMARY_CACHE[cache_key] = work
        return work
    priority = {name: idx for idx, name in enumerate(variants)}
    work["config_priority"] = work["source_variant"].map(priority).astype(int)
    daily_order = str(cfg.get("daily_order", "score_desc"))
    if daily_order == "score_desc":
        work = work.sort_values(
            ["date", "score", "entry_minute", "config_priority", "_source_order"],
            ascending=[True, False, True, True, True],
            kind="stable",
        )
    elif daily_order == "time_asc":
        work = work.sort_values(
            ["date", "entry_minute", "config_priority", "score", "_source_order"],
            ascending=[True, True, True, False, True],
            kind="stable",
        )
    else:
        raise ValueError(f"Unknown daily_order {daily_order!r}")
    dedupe_cols = [col for col in ("date", "time", "action", "expiry_mode") if col in work.columns]
    work = work.drop_duplicates(dedupe_cols, keep="first").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    max_day = int(cfg.get("max_day", 999))
    cooldown = int(cfg.get("cooldown", 0))
    for _, day in work.groupby("date", sort=False):
        taken = 0
        selected_minutes: list[int] = []
        next_allowed = -1
        for row in day.itertuples(index=False):
            minute = int(row.entry_minute)
            if taken >= max_day:
                break
            if daily_order == "score_desc":
                if cooldown > 0 and any(abs(minute - seen) < cooldown for seen in selected_minutes):
                    continue
            elif minute < next_allowed:
                continue
            rows.append(row._asdict())
            selected_minutes.append(minute)
            next_allowed = minute + cooldown
            taken += 1
    if not rows:
        out = work.iloc[0:0].copy()
        _PRIMARY_CACHE[cache_key] = out
        return out
    out = pd.DataFrame(rows)
    out["source_stream"] = "primary_static"
    out["source_file"] = "in_memory_static_union"
    out["_source_order"] = np.arange(len(out), dtype=np.int64)
    _PRIMARY_CACHE[cache_key] = out
    return out


def apply_candidate(frame: pd.DataFrame, cfg: dict[str, Any], months: list[str]) -> pd.DataFrame:
    primary = materialize_primary(frame, cfg)
    fallback_name = str(cfg["fallback"])
    fallback = frame[frame["source_variant"].astype(str).eq(fallback_name)].copy()
    if fallback.empty and primary.empty:
        return pd.DataFrame()
    args = SimpleNamespace(
        start_month=min(months),
        end_month=max(months),
        min_month_trades=int(cfg["target_month_trades"]),
        auto_partial_month_target=False,
        partial_month_observed_floor=0,
        backfill_only_partial_months=False,
        max_day=int(cfg["backfill_max_day"]),
        cooldown_minutes=int(cfg["backfill_cooldown"]),
        primary_name="primary_static",
        fallback_name=fallback_name,
        risk_capital=5000.0,
    )
    selected = apply_backfill(primary, fallback, args)
    if selected.empty:
        return selected
    selected["selected_variants"] = ",".join(str(x) for x in cfg["variants"])
    selected["selected_max_day"] = int(cfg["max_day"])
    selected["selected_cooldown"] = int(cfg["cooldown"])
    selected["selected_min_score"] = float(cfg["min_score"])
    selected["selected_daily_order"] = str(cfg["daily_order"])
    selected["selected_fallback"] = fallback_name
    selected["selected_target_month_trades"] = int(cfg["target_month_trades"])
    selected["selected_backfill_max_day"] = int(cfg["backfill_max_day"])
    selected["selected_backfill_cooldown"] = int(cfg["backfill_cooldown"])
    return selected


def finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def score_metrics_for_selection(row: dict[str, Any], args: argparse.Namespace) -> float:
    trades = int(row.get("trades", 0) or 0)
    min_month = int(row.get("min_month_trades", 0) or 0)
    pf = finite(row.get("profit_factor"), 0.0)
    wr = finite(row.get("win_rate"), 0.0)
    pnl = finite(row.get("pnl_return"), 0.0)
    call_rate = finite(row.get("call_rate"), 0.0)
    pos_month = finite(row.get("positive_month_rate"), 0.0)
    daily_dd = abs(finite(row.get("daily_max_drawdown"), 0.0))
    top5 = finite(row.get("top5_share_of_pnl"), 0.0)
    if trades < int(args.min_select_trades):
        return -1e18 + trades
    if min_month < int(args.min_select_month_trades):
        return -1e18 + trades
    if wr < float(args.min_select_win_rate) or pf < float(args.min_select_profit_factor):
        return -1e18 + trades
    if call_rate < float(args.min_call_rate) or call_rate > float(args.max_call_rate):
        return -1e18 + trades
    if pnl <= 0.0:
        return -1e18 + trades
    if math.isfinite(float(args.max_select_top5_share)) and top5 > float(args.max_select_top5_share):
        return -1e18 + trades
    return (
        min(pf, float(args.score_pf_cap)) * float(args.score_pf_weight)
        + wr * float(args.score_win_weight)
        + pnl * float(args.score_return_weight)
        + pos_month * float(args.score_positive_month_weight)
        + min(float(min_month), 80.0) * float(args.score_volume_weight)
        - daily_dd * float(args.score_daily_dd_penalty)
        - max(top5 - 1.0, 0.0) * float(args.score_top5_penalty)
    )


def score_config(cfg: dict[str, Any], frame: pd.DataFrame, months: list[str], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], float]:
    selected = apply_candidate(frame, cfg, months)
    row = metrics(selected[selected["month"].astype(str).isin(months)].copy() if not selected.empty else selected, months)
    return cfg, row, float(score_metrics_for_selection(row, args))


def init_worker(frame: pd.DataFrame, months: list[str], args_dict: dict[str, Any]) -> None:
    global _WORKER_FRAME, _WORKER_SELECT_MONTHS, _WORKER_ARGS, _PRIMARY_CACHE
    _WORKER_FRAME = frame
    _WORKER_SELECT_MONTHS = list(months)
    _WORKER_ARGS = argparse.Namespace(**args_dict)
    _PRIMARY_CACHE = {}


def score_config_worker(cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], float]:
    if _WORKER_FRAME is None or _WORKER_SELECT_MONTHS is None or _WORKER_ARGS is None:
        raise RuntimeError("Worker not initialized.")
    return score_config(cfg, _WORKER_FRAME, _WORKER_SELECT_MONTHS, _WORKER_ARGS)


def choose_config(frame: pd.DataFrame, months: list[str], configs: list[dict[str, Any]], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], float]:
    workers = max(1, min(int(args.workers), len(configs)))
    best_cfg: dict[str, Any] | None = None
    best_row: dict[str, Any] | None = None
    best_score = -1e30
    if workers <= 1:
        iterator = (score_config(cfg, frame, months, args) for cfg in configs)
        for cfg, row, score in iterator:
            if best_cfg is None or score > best_score:
                best_cfg, best_row, best_score = cfg, row, float(score)
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=init_worker, initargs=(frame, months, vars(args))) as executor:
            for cfg, row, score in executor.map(score_config_worker, configs, chunksize=max(1, int(args.chunksize))):
                if best_cfg is None or score > best_score:
                    best_cfg, best_row, best_score = cfg, row, float(score)
    if best_cfg is None or best_row is None:
        raise RuntimeError("No config scores produced.")
    return best_cfg, best_row, best_score


def flatten(prefix: str, row: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in row.items()}


def build_configs(names: list[str], args: argparse.Namespace) -> list[dict[str, Any]]:
    groups = source_groups(names, int(args.max_source_group_size))
    fallback_names = list(args.fallback_name) if args.fallback_name else list(names)
    configs: list[dict[str, Any]] = []
    for group, max_day, cooldown, min_score, daily_order, fallback, target, backfill_max_day, backfill_cooldown in product(
        groups,
        args.max_day_grid,
        args.cooldown_grid,
        args.min_score_grid,
        args.daily_order_grid,
        fallback_names,
        args.target_month_trades_grid,
        args.backfill_max_day_grid,
        args.backfill_cooldown_grid,
    ):
        configs.append(
            {
                "variants": tuple(group),
                "max_day": int(max_day),
                "cooldown": int(cooldown),
                "min_score": float(min_score),
                "daily_order": str(daily_order),
                "fallback": str(fallback),
                "target_month_trades": int(target),
                "backfill_max_day": int(backfill_max_day),
                "backfill_cooldown": int(backfill_cooldown),
            }
        )
    return configs


def walkforward_select(base: pd.DataFrame, configs: list[dict[str, Any]], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = month_range(str(args.start_month), str(args.end_month))
    all_months = sorted(base["test_month"].astype(str).unique())
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    for month in months:
        test = base[base["test_month"].astype(str).eq(str(month))].copy()
        previous = [m for m in all_months if m < str(month)]
        if test.empty:
            fold_rows.append({"ticker": str(args.ticker).upper(), "month": str(month), "mode": "EMPTY"})
            continue
        if len(previous) < int(args.select_months):
            fold_rows.append({"ticker": str(args.ticker).upper(), "month": str(month), "mode": "NO_HISTORY"})
            continue
        select_months = previous[-int(args.select_months):]
        select_frame = base[base["test_month"].astype(str).isin(select_months)].copy()
        cfg, select_row, select_score = choose_config(select_frame, select_months, configs, args)
        selected = apply_candidate(test, cfg, [str(month)])
        test_row = metrics(selected, [str(month)])
        if not selected.empty:
            selected["config_selector_mode"] = "SELECTED_BACKFILL"
            selected["config_select_months"] = ",".join(select_months)
            selected["config_select_score"] = float(select_score)
            out_parts.append(selected)
        fold = {
            "ticker": str(args.ticker).upper(),
            "month": str(month),
            "mode": "SELECTED_BACKFILL",
            "variants": ",".join(str(x) for x in cfg["variants"]),
            "selected_source": ",".join(str(x) for x in cfg["variants"]),
            "fallback": str(cfg["fallback"]),
            "max_day": int(cfg["max_day"]),
            "cooldown": int(cfg["cooldown"]),
            "min_score": float(cfg["min_score"]),
            "daily_order": str(cfg["daily_order"]),
            "target_month_trades": int(cfg["target_month_trades"]),
            "backfill_max_day": int(cfg["backfill_max_day"]),
            "backfill_cooldown": int(cfg["backfill_cooldown"]),
            "select_months": ",".join(select_months),
            "select_score": float(select_score),
        }
        fold.update(flatten("select", select_row))
        fold.update(flatten("test", test_row))
        fold_rows.append(fold)
    out = pd.concat(out_parts, ignore_index=True, sort=False) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    return out, folds


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
        output_dir / "backfill_selector_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.2)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Rolling Backfill Selector Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "backfill_selector_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, configs: list[dict[str, Any]], args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    payload = {
        "overall": overall,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "candidate_config_count": len(configs),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Trade Union Backfill Selector",
        "",
        "This result selects a primary source union and deterministic monthly volume fallback walk-forward by test month using only prior OOS months.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${float(args.risk_capital):,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        f"- Candidate configs: {len(configs):,}",
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
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rolling walk-forward selector for source unions with monthly volume backfill.")
    parser.add_argument("--trade-source", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202205")
    parser.add_argument("--start-month", default="202501")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--select-months", type=int, default=12)
    parser.add_argument("--max-source-group-size", type=int, default=2)
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--cooldown-grid", nargs="+", type=int, default=[0])
    parser.add_argument("--min-score-grid", nargs="+", type=float, default=[-999999.0, 0.0])
    parser.add_argument("--daily-order-grid", nargs="+", default=["score_desc"], choices=["time_asc", "score_desc"])
    parser.add_argument("--fallback-name", action="append", default=[])
    parser.add_argument("--target-month-trades-grid", nargs="+", type=int, default=[18, 19, 20])
    parser.add_argument("--backfill-max-day-grid", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--backfill-cooldown-grid", nargs="+", type=int, default=[0, 15])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--chunksize", type=int, default=32)
    parser.add_argument("--min-select-trades", type=int, default=216)
    parser.add_argument("--min-select-month-trades", type=int, default=18)
    parser.add_argument("--min-select-win-rate", type=float, default=0.45)
    parser.add_argument("--min-select-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--max-select-top5-share", type=float, default=float("inf"))
    parser.add_argument("--score-pf-weight", type=float, default=3.0)
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight", type=float, default=20.0)
    parser.add_argument("--score-return-weight", type=float, default=0.10)
    parser.add_argument("--score-positive-month-weight", type=float, default=4.0)
    parser.add_argument("--score-volume-weight", type=float, default=0.10)
    parser.add_argument("--score-daily-dd-penalty", type=float, default=0.05)
    parser.add_argument("--score-top5-penalty", type=float, default=0.25)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base, names, _source_paths = load_sources(args.trade_source, args.ticker)
    if base.empty:
        raise RuntimeError("No input trades after ticker filtering.")
    base = base[
        (base["test_month"].astype(str) >= str(args.history_start_month))
        & (base["test_month"].astype(str) <= str(args.end_month))
    ].copy()
    configs = build_configs(names, args)
    if not configs:
        raise RuntimeError("No candidate configs.")
    trades, folds = walkforward_select(base, configs, args)
    if not trades.empty:
        trades.to_csv(output_dir / "trade_union_backfill_selector_trades.csv", index=False)
    folds.to_csv(output_dir / "trade_union_backfill_selector_folds.csv", index=False)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, configs, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
