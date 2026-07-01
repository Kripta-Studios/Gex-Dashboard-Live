from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from apply_event_trade_union_meta_gate import apply_cooldown, parse_trade_source
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


TRADE_FILES = [
    "event_option_gate_trades.csv",
    "combined_trades.csv",
    "trade_union_backfill_selector_trades.csv",
    "trade_union_config_selector_trades.csv",
    "static_union_trades.csv",
]


@dataclass(frozen=True)
class FilterConfig:
    source: str
    ticker: str
    action: str
    expiry_mode: str
    minute_start: int
    minute_end: int
    score_quantile: float
    score_threshold: float
    max_day: int
    cooldown: int

    @property
    def name(self) -> str:
        q = "none" if self.score_quantile < 0.0 else f"q{self.score_quantile:.2f}".replace(".", "p")
        max_day = "all" if self.max_day >= 999 else str(self.max_day)
        start = "all" if self.minute_start <= 0 and self.minute_end >= 9999 else f"{self.minute_start}-{self.minute_end}"
        return (
            f"{self.source}_{self.ticker}_{self.action}_{self.expiry_mode}_"
            f"m{start}_{q}_maxday{max_day}_cd{self.cooldown}"
        )


def resolve_trade_file(path: Path) -> Path:
    if path.is_file():
        return path
    found = next((path / name for name in TRADE_FILES if (path / name).exists()), None)
    if found is None:
        raise FileNotFoundError(f"No known trade CSV found in {path}")
    return found


def load_source(spec: str, priority: int) -> pd.DataFrame:
    name, raw_path, _source_priority = parse_trade_source(spec, priority)
    path = resolve_trade_file(raw_path)
    frame = pd.read_csv(
        path,
        dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str},
        low_memory=False,
    )
    if "month" not in frame.columns and "test_month" in frame.columns:
        frame["month"] = frame["test_month"].astype(str)
    if "test_month" not in frame.columns and "month" in frame.columns:
        frame["test_month"] = frame["month"].astype(str)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["date"] = frame["date"].astype(str)
    frame["month"] = frame["month"].astype(str)
    frame["test_month"] = frame["test_month"].astype(str)
    frame["source"] = name
    frame["source_priority"] = int(priority)
    frame["minute"] = pd.to_numeric(frame.get("minute"), errors="coerce")
    if frame["minute"].isna().any() and "time" in frame.columns:
        missing = frame["minute"].isna()
        parsed = pd.to_datetime(frame.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        frame.loc[missing, "minute"] = parsed.dt.hour * 60 + parsed.dt.minute
    frame["minute"] = frame["minute"].fillna(0).astype(int)
    frame["score"] = pd.to_numeric(frame.get("score"), errors="coerce")
    frame["action"] = frame["action"].astype(str).str.upper()
    frame["expiry_mode"] = frame["expiry_mode"].astype(str) if "expiry_mode" in frame.columns else "all"
    frame["realized_return"] = pd.to_numeric(frame["realized_return"], errors="coerce").fillna(0.0)
    return frame


def pass_gate(row: dict, args: argparse.Namespace, months: list[str]) -> bool:
    if int(row.get("trades", 0)) < int(args.min_month_trades) * len(months):
        return False
    if int(row.get("min_month_trades", 0)) < int(args.min_month_trades):
        return False
    wr = float(row.get("win_rate", float("nan")))
    pf = float(row.get("profit_factor", float("nan")))
    pnl = float(row.get("pnl_return", 0.0))
    call_rate = float(row.get("call_rate", float("nan")))
    return bool(
        np.isfinite(wr)
        and np.isfinite(pf)
        and np.isfinite(call_rate)
        and wr >= float(args.min_win_rate)
        and pf >= float(args.min_profit_factor)
        and pnl > 0.0
        and call_rate >= float(args.min_call_rate)
        and call_rate <= float(args.max_call_rate)
    )


def score_row(row: dict, args: argparse.Namespace, months: list[str]) -> float:
    trades = int(row.get("trades", 0))
    if trades <= 0:
        return -1e18
    pf = float(row.get("profit_factor", 0.0))
    wr = float(row.get("win_rate", 0.0))
    pnl = float(row.get("pnl_return", 0.0))
    min_month = float(row.get("min_month_trades", 0.0))
    dd = abs(float(row.get("daily_max_drawdown", row.get("max_drawdown", 0.0))))
    top5 = float(row.get("top5_share_of_pnl", 0.0))
    if not np.isfinite(pf):
        pf = 0.0
    if not np.isfinite(wr):
        wr = 0.0
    if not np.isfinite(top5):
        top5 = 0.0
    gate_bonus = 1000.0 if pass_gate(row, args, months) else 0.0
    return (
        gate_bonus
        + min(pf, 3.0) * 8.0
        + wr * 30.0
        + pnl * 0.35
        + min(min_month, 80.0) * 0.20
        - dd * 0.08
        - max(top5 - 1.0, 0.0) * 0.5
    )


def apply_filter(frame: pd.DataFrame, cfg: FilterConfig) -> pd.DataFrame:
    mask = (
        (frame["minute"].astype(int) >= int(cfg.minute_start))
        & (frame["minute"].astype(int) <= int(cfg.minute_end))
        & (frame["score"].astype(float) >= float(cfg.score_threshold))
    )
    if cfg.action != "both":
        mask &= frame["action"].astype(str).str.upper().eq(cfg.action)
    if cfg.expiry_mode != "both":
        mask &= frame["expiry_mode"].astype(str).eq(cfg.expiry_mode)
    work = frame.loc[mask].copy()
    if work.empty:
        return work
    work = work.sort_values(["date", "minute", "score"], ascending=[True, True, False])
    if int(cfg.max_day) >= 999 and int(cfg.cooldown) <= 0:
        return work
    return apply_cooldown(work, int(cfg.max_day), int(cfg.cooldown))


def candidate_configs(select: pd.DataFrame, args: argparse.Namespace) -> list[FilterConfig]:
    configs: list[FilterConfig] = []
    windows = [(int(s), int(e)) for raw in args.minute_windows for s, e in [raw.split("-", 1)]]
    for source in sorted(select["source"].astype(str).unique()):
        source_frame = select[select["source"].astype(str).eq(source)]
        for ticker in [str(t).upper() for t in args.tickers]:
            tdf = source_frame[source_frame["ticker"].astype(str).str.upper().eq(ticker)]
            if tdf.empty:
                continue
            expiry_modes = ["both"] + sorted(tdf["expiry_mode"].astype(str).dropna().unique().tolist())
            scores = pd.to_numeric(tdf["score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            thresholds: dict[float, float] = {-1.0: float("-inf")}
            for quantile in args.score_quantiles:
                if scores.empty:
                    continue
                threshold = float(scores.quantile(float(quantile)))
                if math.isfinite(threshold):
                    thresholds[float(quantile)] = threshold
            for action in args.action_grid:
                for expiry_mode in expiry_modes:
                    for minute_start, minute_end in windows:
                        for quantile, threshold in thresholds.items():
                            for max_day in args.max_day_grid:
                                for cooldown in args.cooldown_grid:
                                    configs.append(
                                        FilterConfig(
                                            source=source,
                                            ticker=ticker,
                                            action=str(action),
                                            expiry_mode=str(expiry_mode),
                                            minute_start=int(minute_start),
                                            minute_end=int(minute_end),
                                            score_quantile=float(quantile),
                                            score_threshold=float(threshold),
                                            max_day=int(max_day),
                                            cooldown=int(cooldown),
                                        )
                                    )
    return configs


def evaluate_configs(frame: pd.DataFrame, configs: list[FilterConfig], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    test1_months = month_range(str(args.test1_start_month), str(args.test1_end_month))
    test2_months = month_range(str(args.test2_start_month), str(args.test2_end_month))
    groups = {
        (str(source), str(ticker)): part.copy()
        for (source, ticker), part in frame.groupby(["source", "ticker"], sort=False)
    }
    rows: list[dict] = []
    best_trades: list[pd.DataFrame] = []
    best_by_ticker: dict[str, tuple[float, FilterConfig, pd.DataFrame]] = {}
    for idx, cfg in enumerate(configs):
        base = groups.get((cfg.source, cfg.ticker))
        if base is None or base.empty:
            selected = pd.DataFrame()
        else:
            selected = apply_filter(base, cfg)
        select = selected[selected["month"].astype(str).isin(select_months)].copy()
        test1 = selected[selected["month"].astype(str).isin(test1_months)].copy()
        test2 = selected[selected["month"].astype(str).isin(test2_months)].copy()
        select_m = metrics(select, select_months)
        test1_m = metrics(test1, test1_months)
        test2_m = metrics(test2, test2_months)
        select_score = score_row(select_m, args, select_months)
        row = {
            "config_id": idx,
            "name": cfg.name,
            **asdict(cfg),
            "select_passed": pass_gate(select_m, args, select_months),
            "test1_passed": pass_gate(test1_m, args, test1_months),
            "test2_passed": pass_gate(test2_m, args, test2_months),
            "select_score": select_score,
            **{f"select_{k}": v for k, v in select_m.items()},
            **{f"test1_{k}": v for k, v in test1_m.items()},
            **{f"test2_{k}": v for k, v in test2_m.items()},
        }
        rows.append(row)
        current = best_by_ticker.get(cfg.ticker)
        if current is None or select_score > current[0]:
            best_by_ticker[cfg.ticker] = (select_score, cfg, selected)
    for ticker, (_score, cfg, selected) in best_by_ticker.items():
        if not selected.empty:
            out = selected.copy()
            out["selected_filter_config"] = cfg.name
            out["selected_filter_source"] = cfg.source
            best_trades.append(out)
    return pd.DataFrame(rows), pd.concat(best_trades, ignore_index=True, sort=False) if best_trades else pd.DataFrame()


def write_summary(output_dir: Path, scan: pd.DataFrame, best_trades: pd.DataFrame, args: argparse.Namespace) -> None:
    select_months = month_range(str(args.select_start_month), str(args.select_end_month))
    test1_months = month_range(str(args.test1_start_month), str(args.test1_end_month))
    test2_months = month_range(str(args.test2_start_month), str(args.test2_end_month))
    best_rows = scan.sort_values(["select_score", "select_profit_factor", "select_pnl_return"], ascending=False).groupby("ticker", sort=True).head(1)
    summary = {
        "rules_scanned": int(len(scan)),
        "select_pass_configs": int(scan["select_passed"].sum()) if not scan.empty else 0,
        "test1_pass_configs": int(scan["test1_passed"].sum()) if not scan.empty else 0,
        "test2_pass_configs": int(scan["test2_passed"].sum()) if not scan.empty else 0,
        "best_by_ticker": best_rows.to_dict("records"),
        "best_trades": {
            "select": metrics(best_trades[best_trades["month"].astype(str).isin(select_months)].copy(), select_months),
            "test1": metrics(best_trades[best_trades["month"].astype(str).isin(test1_months)].copy(), test1_months),
            "test2": metrics(best_trades[best_trades["month"].astype(str).isin(test2_months)].copy(), test2_months),
        },
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Stream Trade Filter Scan",
        "",
        f"- Configs scanned: {summary['rules_scanned']}",
        f"- Select-pass configs: {summary['select_pass_configs']}",
        f"- Test1-pass configs: {summary['test1_pass_configs']}",
        f"- Test2-pass configs: {summary['test2_pass_configs']}",
        "",
        "## Best By Ticker",
        "",
        "| Ticker | Config | Select WR | Select PF | Select MinM | Test1 WR | Test1 PF | Test1 MinM | Test2 WR | Test2 PF | Test2 MinM |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in best_rows.itertuples(index=False):
        lines.append(
            f"| {row.ticker} | `{row.name}` | {float(row.select_win_rate):.2%} | {float(row.select_profit_factor):.3f} | "
            f"{int(row.select_min_month_trades)} | {float(row.test1_win_rate):.2%} | {float(row.test1_profit_factor):.3f} | "
            f"{int(row.test1_min_month_trades)} | {float(row.test2_win_rate):.2%} | {float(row.test2_profit_factor):.3f} | "
            f"{int(row.test2_min_month_trades)} |"
        )
    lines += ["", "## JSON", "", "```json", json.dumps(summary, indent=2, allow_nan=True), "```"]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan causal trade filters over precomputed OOS event-option streams.")
    parser.add_argument("--trade-source", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--select-start-month", default="202401")
    parser.add_argument("--select-end-month", default="202412")
    parser.add_argument("--test1-start-month", default="202501")
    parser.add_argument("--test1-end-month", default="202512")
    parser.add_argument("--test2-start-month", default="202601")
    parser.add_argument("--test2-end-month", default="202606")
    parser.add_argument("--action-grid", nargs="+", default=["both", "CALL", "PUT"])
    parser.add_argument("--minute-windows", nargs="+", default=["0-9999", "570-720", "570-780", "600-840", "660-900", "720-900", "570-870"])
    parser.add_argument("--score-quantiles", nargs="+", type=float, default=[0.25, 0.50, 0.65, 0.80])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 8, 4, 2])
    parser.add_argument("--cooldown-grid", nargs="+", type=int, default=[0])
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = [load_source(spec, idx) for idx, spec in enumerate(args.trade_source)]
    frame = pd.concat(frames, ignore_index=True, sort=False)
    useful_months = set(
        month_range(str(args.select_start_month), str(args.select_end_month))
        + month_range(str(args.test1_start_month), str(args.test1_end_month))
        + month_range(str(args.test2_start_month), str(args.test2_end_month))
    )
    frame = frame[frame["month"].astype(str).isin(useful_months)].copy()
    select = frame[frame["month"].astype(str).isin(month_range(str(args.select_start_month), str(args.select_end_month)))].copy()
    configs = candidate_configs(select, args)
    scan, best_trades = evaluate_configs(frame, configs, args)
    scan.to_csv(output_dir / "stream_trade_filter_scan.csv", index=False)
    if not best_trades.empty:
        best_trades.to_csv(output_dir / "stream_trade_filter_best_trades.csv", index=False)
        best_trades.to_csv(output_dir / "combined_trades.csv", index=False)
    write_summary(output_dir, scan, best_trades, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
