from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_add, month_range
from walkforward_event_option_gate import metrics, score_metrics


@dataclass(frozen=True)
class Variant:
    name: str
    path: Path
    fold_file: Path
    trade_file: Path
    fold_kind: str


def parse_variant(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        path = Path(spec)
        return path.name, path
    name, raw_path = spec.split("=", 1)
    return name.strip(), Path(raw_path.strip())


def resolve_variant(spec: str) -> Variant:
    name, path = parse_variant(spec)
    if not path.exists():
        raise FileNotFoundError(f"Variant path does not exist: {path}")
    if (path / "fold_configs.csv").exists():
        fold_file = path / "fold_configs.csv"
        trade_file = path / "event_option_gate_trades.csv"
        fold_kind = "event_gate"
    elif (path / "meta_gate_folds.csv").exists():
        fold_file = path / "meta_gate_folds.csv"
        trade_file = path / "meta_gate_trades.csv"
        fold_kind = "meta_gate"
    else:
        raise FileNotFoundError(f"No supported fold file in {path}")
    if not trade_file.exists():
        raise FileNotFoundError(f"No supported trade file in {path}")
    return Variant(name=name, path=path, fold_file=fold_file, trade_file=trade_file, fold_kind=fold_kind)


def as_float(value: object, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out


def normalized_val_metrics(row: pd.Series, kind: str) -> dict:
    prefix = "meta_select_" if kind == "meta_gate" and "meta_select_trades" in row else "val_"
    return {
        "trades": int(as_float(row.get(f"{prefix}trades"), 0.0)),
        "win_rate": as_float(row.get(f"{prefix}win_rate")),
        "profit_factor": as_float(row.get(f"{prefix}profit_factor")),
        "pnl_return": as_float(row.get(f"{prefix}pnl_return"), 0.0),
        "avg_return": as_float(row.get(f"{prefix}avg_return")),
        "max_drawdown": as_float(row.get(f"{prefix}max_drawdown"), 0.0),
        "call_rate": as_float(row.get(f"{prefix}call_rate")),
        "days_with_trades": int(as_float(row.get(f"{prefix}days_with_trades"), 0.0)),
        "daily_win_rate": as_float(row.get(f"{prefix}daily_win_rate")),
        "median_daily_return": as_float(row.get(f"{prefix}median_daily_return")),
        "daily_max_drawdown": as_float(row.get(f"{prefix}daily_max_drawdown"), 0.0),
        "top5_day_return": as_float(row.get(f"{prefix}top5_day_return"), 0.0),
        "top5_share_of_pnl": as_float(row.get(f"{prefix}top5_share_of_pnl")),
        "min_month_trades": int(as_float(row.get(f"{prefix}min_month_trades"), 0.0)),
        "positive_month_rate": as_float(row.get(f"{prefix}positive_month_rate")),
    }


def normalized_test_metrics(row: pd.Series) -> dict:
    return {
        "trades": int(as_float(row.get("test_trades"), 0.0)),
        "win_rate": as_float(row.get("test_win_rate")),
        "profit_factor": as_float(row.get("test_profit_factor")),
        "pnl_return": as_float(row.get("test_pnl_return"), 0.0),
        "avg_return": as_float(row.get("test_avg_return")),
        "max_drawdown": as_float(row.get("test_max_drawdown"), 0.0),
        "call_rate": as_float(row.get("test_call_rate")),
        "days_with_trades": int(as_float(row.get("test_days_with_trades"), 0.0)),
        "daily_win_rate": as_float(row.get("test_daily_win_rate")),
        "median_daily_return": as_float(row.get("test_median_daily_return")),
        "daily_max_drawdown": as_float(row.get("test_daily_max_drawdown"), 0.0),
        "top5_day_return": as_float(row.get("test_top5_day_return"), 0.0),
        "top5_share_of_pnl": as_float(row.get("test_top5_share_of_pnl")),
        "min_month_trades": int(as_float(row.get("test_min_month_trades"), 0.0)),
        "positive_month_rate": as_float(row.get("test_positive_month_rate")),
    }


def adjusted_score(row: dict, args: argparse.Namespace, prefix: str) -> float:
    score = score_metrics(
        row,
        int(getattr(args, f"{prefix}_min_trades")),
        int(getattr(args, f"{prefix}_min_month_trades")),
        float(getattr(args, f"{prefix}_min_pf")),
        float(getattr(args, f"{prefix}_min_win_rate")),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if score <= -1e17:
        return float(score)
    daily_wr = row.get("daily_win_rate", float("nan"))
    if np.isfinite(float(daily_wr)):
        score += float(args.daily_win_weight) * float(daily_wr)
    top5_share = row.get("top5_share_of_pnl", float("nan"))
    if np.isfinite(float(top5_share)):
        score -= float(args.top5_share_penalty) * max(float(top5_share) - 1.0, 0.0)
    call_rate = row.get("call_rate", float("nan"))
    if np.isfinite(float(call_rate)):
        score -= float(args.direction_balance_penalty) * abs(float(call_rate) - 0.5)
    return float(score)


def load_variants(specs: list[str]) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    fold_rows: list[dict] = []
    trades_by_variant: dict[tuple[str, str], pd.DataFrame] = {}
    for spec in specs:
        variant = resolve_variant(spec)
        folds = pd.read_csv(variant.fold_file)
        trades = pd.read_csv(variant.trade_file)
        folds["ticker"] = folds["ticker"].astype(str).str.upper()
        folds["month"] = folds["month"].astype(str)
        trades["ticker"] = trades["ticker"].astype(str).str.upper()
        if "test_month" in trades.columns:
            trades["test_month"] = trades["test_month"].astype(str)
        else:
            trades["test_month"] = trades["month"].astype(str)
        trades["month"] = trades.get("month", trades["test_month"]).astype(str)
        trades["variant"] = variant.name
        trades["variant_path"] = str(variant.path)
        trades["variant_kind"] = variant.fold_kind
        trades_by_variant[(variant.name, variant.fold_kind)] = trades
        for _, row in folds.iterrows():
            val = normalized_val_metrics(row, variant.fold_kind)
            test = normalized_test_metrics(row)
            record = {
                "variant": variant.name,
                "variant_path": str(variant.path),
                "variant_kind": variant.fold_kind,
                "ticker": str(row["ticker"]).upper(),
                "month": str(row["month"]),
                "deploy_config": row.get("deploy_config", ""),
                "val_months": row.get("val_months", ""),
                "source_fold_file": str(variant.fold_file),
                "source_trade_file": str(variant.trade_file),
            }
            if variant.fold_kind == "meta_gate":
                record.update(
                    {
                        "meta_mode": row.get("meta_mode", ""),
                        "meta_threshold": row.get("meta_threshold", ""),
                        "meta_train_months": row.get("meta_train_months", ""),
                        "meta_select_months": row.get("meta_select_months", ""),
                    }
                )
            record.update({f"val_{k}": v for k, v in val.items()})
            record.update({f"test_{k}": v for k, v in test.items()})
            fold_rows.append(record)
    return pd.DataFrame(fold_rows), trades_by_variant


def prior_months_for(fold_rows: pd.DataFrame, ticker: str, variant: str, month: str, lookback: int) -> list[str]:
    available = sorted(
        set(
            fold_rows[
                (fold_rows["ticker"].astype(str) == ticker)
                & (fold_rows["variant"].astype(str) == variant)
                & (fold_rows["month"].astype(str) < str(month))
            ]["month"].astype(str)
        )
    )
    if lookback > 0:
        available = available[-int(lookback) :]
    return available


def variant_month_trades(
    trades_by_variant: dict[tuple[str, str], pd.DataFrame],
    variant: str,
    kind: str,
    ticker: str,
    months: list[str],
) -> pd.DataFrame:
    trades = trades_by_variant.get((variant, kind))
    if trades is None or trades.empty or not months:
        return pd.DataFrame()
    return trades[
        (trades["ticker"].astype(str) == ticker)
        & (trades["test_month"].astype(str).isin([str(m) for m in months]))
    ].copy()


def select_rows(fold_rows: pd.DataFrame, trades_by_variant: dict[tuple[str, str], pd.DataFrame], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected: list[dict] = []
    candidates: list[dict] = []
    months = month_range(str(args.start_month), str(args.end_month))
    tickers = [str(t).upper() for t in args.tickers]
    for ticker in tickers:
        for month in months:
            sub = fold_rows[
                (fold_rows["ticker"].astype(str) == ticker)
                & (fold_rows["month"].astype(str) == str(month))
            ].copy()
            if sub.empty:
                continue
            best: dict | None = None
            for _, row in sub.iterrows():
                val_row = {k[4:]: row[k] for k in row.index if str(k).startswith("val_")}
                val_score = adjusted_score(val_row, args, "val")
                hist_months = prior_months_for(
                    fold_rows,
                    ticker,
                    str(row["variant"]),
                    str(month),
                    int(args.history_lookback_months),
                )
                hist_trades = variant_month_trades(
                    trades_by_variant,
                    str(row["variant"]),
                    str(row["variant_kind"]),
                    ticker,
                    hist_months,
                )
                history_metrics = metrics(hist_trades, hist_months) if hist_months else metrics(pd.DataFrame(), [])
                history_score = adjusted_score(history_metrics, args, "history") if len(hist_months) >= int(args.min_history_months) else float("nan")
                if np.isfinite(history_score):
                    final_score = float(args.validation_weight) * float(val_score) + float(args.history_weight) * float(history_score)
                else:
                    final_score = float(val_score)
                record = row.to_dict()
                record.update(
                    {
                        "selection_ticker": ticker,
                        "selection_month": str(month),
                        "selection_val_score": float(val_score),
                        "selection_history_score": float(history_score) if np.isfinite(history_score) else float("nan"),
                        "selection_final_score": float(final_score),
                        "history_months": ",".join(hist_months),
                        **{f"history_{k}": v for k, v in history_metrics.items()},
                    }
                )
                candidates.append(record)
                if best is None or final_score > float(best["selection_final_score"]):
                    best = record
            if best is not None:
                selected.append(best)
    return pd.DataFrame(selected), pd.DataFrame(candidates)


def selected_trades(selected: pd.DataFrame, trades_by_variant: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, row in selected.iterrows():
        trades = variant_month_trades(
            trades_by_variant,
            str(row["variant"]),
            str(row["variant_kind"]),
            str(row["ticker"]),
            [str(row["month"])],
        )
        if trades.empty:
            continue
        trades = trades.copy()
        trades["selection_final_score"] = float(row["selection_final_score"])
        trades["selection_val_score"] = float(row["selection_val_score"])
        trades["selection_history_score"] = as_float(row.get("selection_history_score"))
        trades["selected_variant"] = str(row["variant"])
        parts.append(trades)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    if "date" in out.columns:
        out = out.sort_values(["date", "ticker", "minute", "selected_variant"], kind="stable").reset_index(drop=True)
    return out


def write_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(daily.index, daily.cumsum(), color="#111827", linewidth=2.4, label="TOTAL")
    for ticker, part in work.groupby("ticker"):
        curve = part.groupby("dt")["pnl"].sum().sort_index().reindex(idx).fillna(0.0).cumsum()
        axes[0].plot(curve.index, curve.values, linewidth=1.6, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Nested Variant Selector Net PnL, risk_capital={risk_capital:g}")
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
    fig.savefig(output_dir / "selected_variant_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, selected: pd.DataFrame, candidates: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    risk_capital = float(args.risk_capital)
    daily = pd.DataFrame()
    if not trades.empty:
        work = trades.copy()
        work["pnl"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0) * risk_capital
        daily = work.groupby("date", as_index=False)["pnl"].sum().rename(columns={"pnl": "net_pnl"})
        daily["cum_net_pnl"] = daily["net_pnl"].cumsum()
        daily.to_csv(output_dir / f"daily_total_risk{int(risk_capital)}.csv", index=False)
        ticker_rows = []
        for ticker, part in work.groupby("ticker", sort=True):
            row = metrics(part, expected)
            row["ticker"] = ticker
            row["net_pnl"] = float(part["pnl"].sum())
            ticker_rows.append(row)
        pd.DataFrame(ticker_rows).to_csv(output_dir / f"ticker_metrics_risk{int(risk_capital)}.csv", index=False)
    payload = {
        "overall": overall,
        "per_ticker": per_ticker,
        "risk_capital": risk_capital,
        "net_pnl": float(trades["realized_return"].astype(float).sum() * risk_capital) if not trades.empty else 0.0,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Nested Event Option Variant Selector",
        "",
        "This selector chooses among precomputed causal event-gate variants per ticker-month. The selection score uses only the current fold validation metrics and optional out-of-sample history from months before the selected month.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        f"- Risk capital: ${risk_capital:,.0f}",
        f"- Net PnL: ${payload['net_pnl']:,.0f}",
        f"- Selected folds: {len(selected)}",
        f"- Candidate rows scored: {len(candidates)}",
        "",
        "## Per Ticker",
        "",
        "```json",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Selection Rows",
        "",
        "```csv",
        selected.to_csv(index=False),
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
    parser = argparse.ArgumentParser(description="Nested no-lookahead selector over precomputed event option variants.")
    parser.add_argument("--candidate", action="append", required=True, help="NAME=path to a variant result folder. Repeatable.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--validation-weight", type=float, default=0.60)
    parser.add_argument("--history-weight", type=float, default=0.40)
    parser.add_argument("--min-history-months", type=int, default=2)
    parser.add_argument("--history-lookback-months", type=int, default=6)
    parser.add_argument("--val-min-trades", type=int, default=40)
    parser.add_argument("--val-min-month-trades", type=int, default=18)
    parser.add_argument("--val-min-pf", type=float, default=0.0)
    parser.add_argument("--val-min-win-rate", type=float, default=0.0)
    parser.add_argument("--history-min-trades", type=int, default=40)
    parser.add_argument("--history-min-month-trades", type=int, default=12)
    parser.add_argument("--history-min-pf", type=float, default=0.0)
    parser.add_argument("--history-min-win-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.15)
    parser.add_argument("--max-call-rate", type=float, default=0.85)
    parser.add_argument("--daily-win-weight", type=float, default=0.50)
    parser.add_argument("--top5-share-penalty", type=float, default=0.25)
    parser.add_argument("--direction-balance-penalty", type=float, default=0.75)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fold_rows, trades_by_variant = load_variants(args.candidate)
    selected, candidates = select_rows(fold_rows, trades_by_variant, args)
    trades = selected_trades(selected, trades_by_variant)
    if not trades.empty:
        trades.to_csv(output_dir / "selected_variant_trades.csv", index=False)
    selected.to_csv(output_dir / "selected_variant_folds.csv", index=False)
    candidates.to_csv(output_dir / "candidate_variant_scores.csv", index=False)
    write_plot(output_dir, trades, float(args.risk_capital))
    write_summary(output_dir, trades, selected, candidates, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
