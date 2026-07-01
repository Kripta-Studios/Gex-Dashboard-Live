from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


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
        "combined_trades.csv",
        "trade_union_topk_regressor_trades.csv",
        "nested_volume_backfill_trades.csv",
        "intraday_circuit_trades.csv",
        "event_option_gate_trades.csv",
        "volume_backfill_trades.csv",
        "selected_trades.csv",
    ):
        candidate = path / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(path)


def month_col(frame: pd.DataFrame) -> str:
    if "test_month" in frame.columns:
        return "test_month"
    if "month" in frame.columns:
        return "month"
    raise ValueError("Trade stream needs month or test_month column.")


def load_stream(path: Path, name: str, ticker: str, history_start_month: str, end_month: str) -> pd.DataFrame:
    trade_file = resolve_trade_file(path)
    frame = pd.read_csv(trade_file, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str})
    if "ticker" in frame.columns:
        frame = frame[frame["ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
    col = month_col(frame)
    if "test_month" not in frame.columns:
        frame["test_month"] = frame[col].astype(str)
    if "month" not in frame.columns:
        frame["month"] = frame["test_month"].astype(str)
    frame["test_month"] = frame["test_month"].astype(str)
    frame["month"] = frame["month"].astype(str)
    frame = frame[
        (frame["test_month"] >= str(history_start_month))
        & (frame["test_month"] <= str(end_month))
    ].copy()
    frame["selector_source"] = str(name)
    frame["selector_source_path"] = str(path)
    return frame


def score_row(row: dict, args: argparse.Namespace) -> float:
    trades = int(row.get("trades", 0) or 0)
    min_month = int(row.get("min_month_trades", 0) or 0)
    wr = float(row.get("win_rate", float("nan")))
    pf = float(row.get("profit_factor", float("nan")))
    pnl = float(row.get("pnl_return", 0.0) or 0.0)
    call_rate = float(row.get("call_rate", float("nan")))
    pos_months = float(row.get("positive_month_rate", 0.0) or 0.0)
    max_select_top5_share = float(args.max_select_top5_share)
    max_select_drawdown_to_pnl = float(args.max_select_drawdown_to_pnl)
    score = 0.0
    if trades < int(args.min_select_trades):
        score -= 1_000_000.0 + float(int(args.min_select_trades) - trades)
    if min_month < int(args.min_select_month_trades):
        score -= 1_000_000.0 + float(int(args.min_select_month_trades) - min_month)
    if not np.isfinite(wr) or wr < float(args.min_select_win_rate):
        score -= 1_000_000.0 + 100.0 * max(float(args.min_select_win_rate) - (wr if np.isfinite(wr) else 0.0), 0.0)
    if not np.isfinite(pf) or pf < float(args.min_select_pf):
        score -= 1_000_000.0 + 100.0 * max(float(args.min_select_pf) - (pf if np.isfinite(pf) else 0.0), 0.0)
    if not np.isfinite(call_rate) or call_rate < float(args.min_call_rate) or call_rate > float(args.max_call_rate):
        score -= 1_000_000.0
    if bool(args.require_select_positive_months) and pos_months < 1.0:
        score -= 1_000_000.0 + 1000.0 * (1.0 - pos_months)
    if np.isfinite(max_select_top5_share):
        top5_share = float(row.get("top5_share_of_pnl", float("nan")))
        if not np.isfinite(top5_share) or top5_share < 0.0 or top5_share > max_select_top5_share:
            score -= 1_000_000.0
    if np.isfinite(max_select_drawdown_to_pnl):
        pnl = float(row.get("pnl_return", 0.0) or 0.0)
        drawdown = abs(float(row.get("max_drawdown", 0.0) or 0.0))
        drawdown_to_pnl = drawdown / pnl if pnl > 0.0 else float("inf")
        if not np.isfinite(drawdown_to_pnl) or drawdown_to_pnl > max_select_drawdown_to_pnl:
            score -= 1_000_000.0
    score += min(max(pf if np.isfinite(pf) else 0.0, 0.0), float(args.score_pf_cap)) * float(args.score_pf_weight)
    score += (wr if np.isfinite(wr) else 0.0) * float(args.score_win_weight)
    score += pnl * float(args.score_return_weight)
    score += pos_months * float(args.score_positive_month_weight)
    score += min(float(min_month), 60.0) * float(args.score_volume_weight)
    return float(score)


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
        output_dir / "stream_selector_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Event Stream Selector Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "stream_selector_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    by_ticker = {ticker: metrics(part, expected) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "risk_capital": float(args.risk_capital),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Stream Selector",
        "",
        "This result selects one precomputed causal OOS stream per evaluated month using only prior OOS months.",
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
        "## Config",
        "",
        "```json",
        json.dumps(vars(args), indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def flatten(prefix: str, row: dict) -> dict:
    return {f"{prefix}_{key}": value for key, value in row.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal monthly selector across precomputed event-option trade streams.")
    parser.add_argument("--source", action="append", required=True, help="NAME=path")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--history-start-month", default="202510")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--select-months", type=int, default=2)
    parser.add_argument(
        "--exclude-select-months",
        nargs="*",
        default=[],
        help="Months to exclude from source-selection windows, e.g. raw partial months.",
    )
    parser.add_argument(
        "--frozen-select-start-month",
        default="",
        help="If set with --frozen-select-end-month, select one source from this fixed pre-test window.",
    )
    parser.add_argument(
        "--frozen-select-end-month",
        default="",
        help="If set with --frozen-select-start-month, apply the selected source to every evaluated month.",
    )
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-select-trades", type=int, default=38)
    parser.add_argument("--min-select-month-trades", type=int, default=19)
    parser.add_argument("--min-select-win-rate", type=float, default=0.45)
    parser.add_argument("--min-select-pf", type=float, default=1.30)
    parser.add_argument("--require-select-positive-months", action="store_true")
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--score-pf-weight", type=float, default=3.0)
    parser.add_argument("--score-pf-cap", type=float, default=4.0)
    parser.add_argument("--score-win-weight", type=float, default=20.0)
    parser.add_argument("--score-return-weight", type=float, default=0.10)
    parser.add_argument("--score-positive-month-weight", type=float, default=4.0)
    parser.add_argument("--score-volume-weight", type=float, default=0.10)
    parser.add_argument("--max-select-top5-share", type=float, default=float("inf"))
    parser.add_argument("--max-select-drawdown-to-pnl", type=float, default=float("inf"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    streams: dict[str, pd.DataFrame] = {}
    source_specs: dict[str, str] = {}
    for spec in args.source:
        name, path = parse_source(spec)
        streams[name] = load_stream(path, name, args.ticker, args.history_start_month, args.end_month)
        source_specs[name] = str(path)
    if not streams or all(frame.empty for frame in streams.values()):
        raise RuntimeError("No rows loaded from sources.")

    all_months = sorted(set().union(*[set(frame["test_month"].astype(str).unique()) for frame in streams.values()]))
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, object]] = []
    frozen_select_months: list[str] = []
    frozen_selected_name = ""
    frozen_selected_score = -1e30
    frozen_selected_metrics = metrics(pd.DataFrame(), [])
    if str(args.frozen_select_start_month).strip() or str(args.frozen_select_end_month).strip():
        if not str(args.frozen_select_start_month).strip() or not str(args.frozen_select_end_month).strip():
            raise ValueError("Both --frozen-select-start-month and --frozen-select-end-month are required for frozen selection.")
        excluded_select_months = {str(month) for month in args.exclude_select_months}
        frozen_select_months = [
            month
            for month in month_range(str(args.frozen_select_start_month), str(args.frozen_select_end_month))
            if month not in excluded_select_months
        ]
        if any(month >= str(args.start_month) for month in frozen_select_months):
            raise ValueError("Frozen select months must be earlier than start-month.")
        for name, frame in streams.items():
            select_frame = frame[frame["test_month"].astype(str).isin(frozen_select_months)].copy()
            row = metrics(select_frame, frozen_select_months)
            score = score_row(row, args)
            if score > frozen_selected_score:
                frozen_selected_name = name
                frozen_selected_score = score
                frozen_selected_metrics = row
        if not frozen_selected_name:
            raise RuntimeError("Frozen selection did not choose a source.")

    for month in month_range(str(args.start_month), str(args.end_month)):
        excluded_select_months = {str(item) for item in args.exclude_select_months}
        previous = [m for m in all_months if m < str(month) and m not in excluded_select_months]
        select_months = previous[-int(args.select_months):]
        selected_name = next(iter(streams))
        selected_score = -1e30
        selected_metrics = metrics(pd.DataFrame(), select_months)
        mode = "NO_HISTORY"
        if frozen_select_months:
            mode = "FROZEN_SELECTED"
            select_months = list(frozen_select_months)
            selected_name = frozen_selected_name
            selected_score = frozen_selected_score
            selected_metrics = frozen_selected_metrics
        elif len(select_months) >= int(args.select_months):
            mode = "SELECTED"
            for name, frame in streams.items():
                select_frame = frame[frame["test_month"].astype(str).isin(select_months)].copy()
                row = metrics(select_frame, select_months)
                score = score_row(row, args)
                if score > selected_score:
                    selected_name = name
                    selected_score = score
                    selected_metrics = row
        test = streams[selected_name][streams[selected_name]["test_month"].astype(str).eq(str(month))].copy()
        if not test.empty:
            test["stream_selector_mode"] = mode
            test["stream_selector_source"] = selected_name
            test["stream_selector_select_months"] = ",".join(select_months)
            out_parts.append(test)
        test_metrics = metrics(test, [str(month)])
        row = {
            "ticker": str(args.ticker).upper(),
            "test_month": str(month),
            "mode": mode,
            "selected_source": selected_name,
            "source_path": source_specs.get(selected_name, ""),
            "train_months": ",".join([m for m in previous if m not in select_months]),
            "select_months": ",".join(select_months),
            "select_score": float(selected_score),
        }
        row.update(flatten("select", selected_metrics))
        row.update(flatten("test", test_metrics))
        fold_rows.append(row)

    trades = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "stream_selector_trades.csv", index=False)
    folds.to_csv(output_dir / "stream_selector_folds.csv", index=False)
    payload = {
        "args": vars(args),
        "sources": source_specs,
        "overall": metrics(trades, month_range(str(args.start_month), str(args.end_month))),
        "risk_capital": float(args.risk_capital),
    }
    payload["net_pnl"] = float(payload["overall"]["pnl_return"]) * float(args.risk_capital)
    (output_dir / "selector_metadata.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
