from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics, score_metrics


@dataclass(frozen=True)
class CircuitConfig:
    stop_after_loss_streak: int
    daily_loss_limit: float
    total_loss_limit: int
    min_trades_before_halt: int = 0

    @property
    def name(self) -> str:
        streak = "off" if self.stop_after_loss_streak >= 999 else str(self.stop_after_loss_streak)
        day = "off" if self.daily_loss_limit <= -99 else f"{abs(self.daily_loss_limit):.1f}".replace(".", "p")
        total = "off" if self.total_loss_limit >= 999 else str(self.total_loss_limit)
        floor = "" if self.min_trades_before_halt <= 0 else f"_min{self.min_trades_before_halt}"
        return f"streak{streak}_dayloss{day}_losses{total}{floor}"


def parse_delta_map(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --delta-map item: {item!r}")
        key, value = item.split("=", 1)
        out[key.strip().upper()] = int(value)
    return out


def load_trades(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"date": str, "month": str, "test_month": str, "time": str})
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    if "month" not in df.columns:
        df["month"] = df["test_month"].astype(str)
    df["test_month"] = df["test_month"].astype(str)
    df["month"] = df["month"].astype(str)
    df["date"] = df["date"].astype(str)
    df["time"] = df["time"].astype(str)
    if "expiry_mode" in df.columns:
        df["expiry_mode"] = df["expiry_mode"].astype(str)
    else:
        df["expiry_mode"] = ""
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    df["entry_minute"] = derive_entry_minute(df)
    df["_orig_order"] = np.arange(len(df), dtype=np.int64)
    return df


def derive_entry_minute(df: pd.DataFrame) -> pd.Series:
    candidates = []
    for col in ("minute", "minute_x", "minute_y"):
        if col in df.columns:
            candidates.append(pd.to_numeric(df[col], errors="coerce"))
    if candidates:
        out = candidates[0].copy()
        for cand in candidates[1:]:
            out = out.where(out.notna(), cand)
    else:
        out = pd.Series(np.nan, index=df.index, dtype=float)
    missing = out.isna()
    if missing.any() and "time" in df.columns:
        parsed = pd.to_datetime(df.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def nearest_delta_bucket(value: object, buckets: list[int], default_delta: int) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return int(default_delta)
    if not np.isfinite(numeric):
        return int(default_delta)
    if abs(numeric) <= 1.0:
        numeric *= 100.0
    return int(min(buckets, key=lambda bucket: abs(float(bucket) - abs(numeric))))


def load_exit_minutes(
    label_data: Path,
    trades: pd.DataFrame,
    delta_map: dict[str, int],
    default_delta: int,
    row_delta_column: str = "",
) -> pd.DataFrame:
    available_buckets = [15, 25, 35, 50, 65, 80]
    use_row_delta = bool(row_delta_column) and row_delta_column in trades.columns
    needed = available_buckets if use_row_delta else sorted(set(delta_map.values()) | {int(default_delta)})
    cols = ["ticker", "trade_date", "time", "expiry_mode"]
    for delta in needed:
        label = f"d{int(delta):02d}"
        cols.extend([f"call_{label}_opt_exit_minutes", f"put_{label}_opt_exit_minutes"])
    raw = pd.read_parquet(label_data, columns=[c for c in cols if c])
    raw["ticker"] = raw["ticker"].astype(str).str.upper()
    raw["date"] = raw["trade_date"].astype(str)
    raw["time"] = raw["time"].astype(str)
    raw["expiry_mode"] = raw["expiry_mode"].astype(str)
    keep = ["ticker", "date", "time", "expiry_mode"] + [c for c in raw.columns if c.endswith("_opt_exit_minutes")]
    raw = raw[keep].drop_duplicates(["ticker", "date", "time", "expiry_mode"], keep="first")
    merged = trades.merge(raw, on=["ticker", "date", "time", "expiry_mode"], how="left")
    exit_minutes: list[float] = []
    for row in merged.itertuples(index=False):
        ticker = str(getattr(row, "ticker")).upper()
        if use_row_delta:
            delta = nearest_delta_bucket(getattr(row, row_delta_column, np.nan), available_buckets, int(delta_map.get(ticker, default_delta)))
        else:
            delta = int(delta_map.get(ticker, default_delta))
        side = str(getattr(row, "action", "")).upper()
        prefix = "call" if side == "CALL" else "put"
        col = f"{prefix}_d{delta:02d}_opt_exit_minutes"
        value = getattr(row, col, np.nan)
        exit_minutes.append(float(value) if pd.notna(value) else np.nan)
    merged["exit_minutes"] = pd.Series(exit_minutes, index=merged.index).fillna(9999.0).clip(lower=0.0)
    merged["known_minute"] = merged["entry_minute"].astype(float) + merged["exit_minutes"].astype(float)
    return merged


def apply_config(frame: pd.DataFrame, cfg: CircuitConfig, side_specific: bool = False) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    kept_indices: list[int] = []
    ordered = frame.sort_values(["ticker", "date", "entry_minute", "_orig_order"], kind="stable")
    for (_ticker, _date), day in ordered.groupby(["ticker", "date"], sort=False):
        state: dict[str, dict[str, object]] = {}

        def get_state(key: str) -> dict[str, object]:
            if key not in state:
                state[key] = {
                    "pending": [],
                    "known_day_return": 0.0,
                    "known_loss_streak": 0,
                    "known_total_losses": 0,
                    "halted": False,
                    "seq": 0,
                    "taken": 0,
                }
            return state[key]

        for row in day.itertuples(index=True):
            side_key = str(getattr(row, "action", "")).upper() if side_specific else "__ALL__"
            current = get_state(side_key)
            now = float(getattr(row, "entry_minute"))
            pending = current["pending"]
            due = [item for item in pending if item[0] <= now]
            current["pending"] = [item for item in pending if item[0] > now]
            for _known_minute, _seq, ret in sorted(due, key=lambda item: (item[0], item[1])):
                current["known_day_return"] = float(current["known_day_return"]) + float(ret)
                if float(ret) < 0.0:
                    current["known_loss_streak"] = int(current["known_loss_streak"]) + 1
                    current["known_total_losses"] = int(current["known_total_losses"]) + 1
                elif float(ret) > 0.0:
                    current["known_loss_streak"] = 0
                triggered = (
                    int(current["known_loss_streak"]) >= int(cfg.stop_after_loss_streak)
                    or float(current["known_day_return"]) <= float(cfg.daily_loss_limit)
                    or int(current["known_total_losses"]) >= int(cfg.total_loss_limit)
                )
                if triggered and int(current["taken"]) >= int(cfg.min_trades_before_halt):
                    current["halted"] = True
            if bool(current["halted"]):
                continue
            kept_indices.append(row.Index)
            seq = int(current["seq"])
            current["pending"].append((float(getattr(row, "known_minute")), seq, float(getattr(row, "realized_return"))))
            current["seq"] = seq + 1
            current["taken"] = int(current["taken"]) + 1
    if not kept_indices:
        return frame.iloc[0:0].copy()
    out = frame.loc[kept_indices].copy()
    out["circuit_config"] = cfg.name
    out["circuit_side_specific"] = bool(side_specific)
    return out


def candidate_configs(args: argparse.Namespace) -> list[CircuitConfig]:
    configs: list[CircuitConfig] = []
    for streak in [int(x) for x in args.stop_after_loss_streak_grid]:
        for day_loss in [float(x) for x in args.daily_loss_limit_grid]:
            for total_losses in [int(x) for x in args.total_loss_limit_grid]:
                for min_trades in [int(x) for x in args.min_trades_before_halt_grid]:
                    cfg = CircuitConfig(streak, day_loss, total_losses, min_trades)
                    if cfg not in configs:
                        configs.append(cfg)
    off = CircuitConfig(999, -999.0, 999, 0)
    if off not in configs:
        configs.insert(0, off)
    return configs


def selection_score(row: dict, args: argparse.Namespace) -> float:
    score = score_metrics(
        row,
        int(args.min_select_trades),
        int(args.min_select_month_trades),
        float(args.min_select_pf),
        float(args.min_select_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
        score += float(args.daily_win_weight) * float(row["daily_win_rate"])
    if np.isfinite(float(row.get("daily_max_drawdown", float("nan")))):
        score -= abs(float(row["daily_max_drawdown"])) * float(args.daily_dd_weight)
    return float(score)


def select_config(frame: pd.DataFrame, select_months: list[str], configs: list[CircuitConfig], args: argparse.Namespace) -> tuple[CircuitConfig, dict, float]:
    best_cfg = configs[0]
    best_metrics = metrics(apply_config(frame, best_cfg, bool(args.side_specific)), select_months)
    best_score = selection_score(best_metrics, args)
    for cfg in configs[1:]:
        filtered = apply_config(frame, cfg, bool(args.side_specific))
        row = metrics(filtered, select_months)
        score = selection_score(row, args)
        if score > best_score:
            best_cfg = cfg
            best_metrics = row
            best_score = score
    return best_cfg, best_metrics, best_score


def walkforward_apply(trades: pd.DataFrame, configs: list[CircuitConfig], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = month_range(str(args.start_month), str(args.end_month))
    all_months = sorted(trades["test_month"].astype(str).unique())
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for ticker in [str(x).upper() for x in args.tickers]:
        tdf = trades[trades["ticker"].astype(str).str.upper() == ticker].copy()
        for month in months:
            test = tdf[tdf["test_month"].astype(str) == str(month)].copy()
            if test.empty:
                continue
            previous = [m for m in all_months if m < str(month)]
            if len(previous) < int(args.select_months):
                cfg = CircuitConfig(999, -999.0, 999)
                select_months: list[str] = []
                select_row = metrics(pd.DataFrame(), [])
                select_score = float("nan")
                mode = "NO_HISTORY"
            else:
                select_months = previous[-int(args.select_months):]
                select_frame = tdf[tdf["test_month"].astype(str).isin(select_months)].copy()
                cfg, select_row, select_score = select_config(select_frame, select_months, configs, args)
                mode = "SELECTED"
            kept = apply_config(test, cfg, bool(args.side_specific))
            if not kept.empty:
                kept["circuit_mode"] = mode
                out_parts.append(kept)
            test_row = metrics(kept, [str(month)])
            row = {
                "ticker": ticker,
                "month": str(month),
                "mode": mode,
                "config": cfg.name,
                "stop_after_loss_streak": cfg.stop_after_loss_streak,
                "daily_loss_limit": cfg.daily_loss_limit,
                "total_loss_limit": cfg.total_loss_limit,
                "min_trades_before_halt": cfg.min_trades_before_halt,
                "select_months": ",".join(select_months),
                "select_score": select_score,
            }
            row.update({f"select_{k}": v for k, v in select_row.items()})
            row.update({f"test_{k}": v for k, v in test_row.items()})
            fold_rows.append(row)
    out = pd.concat(out_parts, ignore_index=True) if out_parts else pd.DataFrame()
    return out, pd.DataFrame(fold_rows)


def export_deploy_config(output_dir: Path, trades: pd.DataFrame, configs: list[CircuitConfig], args: argparse.Namespace) -> None:
    deploy_month = str(args.deploy_month).strip()
    if not deploy_month:
        raise RuntimeError("--export-deploy-config requires --deploy-month")
    deploy_select_end_month = str(args.deploy_select_end_month).strip()
    if deploy_select_end_month and deploy_select_end_month >= deploy_month:
        raise RuntimeError(
            f"--deploy-select-end-month {deploy_select_end_month} must be earlier than deploy month {deploy_month}"
        )
    all_months = sorted(trades["test_month"].astype(str).unique())
    previous = [
        m
        for m in all_months
        if m < deploy_month and (not deploy_select_end_month or m <= deploy_select_end_month)
    ]
    if len(previous) < int(args.select_months):
        raise RuntimeError(f"Not enough prior months to export deploy config for {deploy_month}: {previous}")
    select_months = previous[-int(args.select_months):]
    ticker_rows: list[dict] = []
    for ticker in [str(x).upper() for x in args.tickers]:
        select_frame = trades[
            (trades["ticker"].astype(str).str.upper() == ticker)
            & (trades["test_month"].astype(str).isin(select_months))
        ].copy()
        if select_frame.empty:
            raise RuntimeError(f"No deploy selection rows for {ticker} in months {select_months}")
        cfg, select_row, select_score = select_config(select_frame, select_months, configs, args)
        if float(select_score) <= -1e17 and not bool(args.allow_invalid_deploy_selection):
            raise RuntimeError(
                "Deploy circuit selection failed validation for "
                f"{ticker} {deploy_month} using select_months={select_months}; "
                "pass --allow-invalid-deploy-selection only for diagnostics."
            )
        ticker_rows.append(
            {
                "ticker": ticker,
                "config": cfg.name,
                "stop_after_loss_streak": int(cfg.stop_after_loss_streak),
                "daily_loss_limit": float(cfg.daily_loss_limit),
                "total_loss_limit": int(cfg.total_loss_limit),
                "min_trades_before_halt": int(cfg.min_trades_before_halt),
                "select_score": float(select_score),
                "select_metrics": select_row,
            }
        )
    payload = {
        "schema_version": 1,
        "component": "event_intraday_circuit_breaker_config",
        "deploy_month": deploy_month,
        "deploy_select_end_month": deploy_select_end_month or None,
        "select_months": select_months,
        "side_specific": bool(args.side_specific),
        "tickers": ticker_rows,
        "candidate_configs": [
            {
                "config": cfg.name,
                "stop_after_loss_streak": int(cfg.stop_after_loss_streak),
                "daily_loss_limit": float(cfg.daily_loss_limit),
                "total_loss_limit": int(cfg.total_loss_limit),
                "min_trades_before_halt": int(cfg.min_trades_before_halt),
            }
            for cfg in configs
        ],
        "args": vars(args),
    }
    deploy_dir = output_dir / "deploy_model"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    (deploy_dir / "intraday_circuit_config.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )


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
        axes[0].plot(curve.index, curve.values, linewidth=1.5, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Intraday Circuit Breaker Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(daily.index, daily.values, color=np.where(daily >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "intraday_circuit_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    expected = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, expected)
    by_ticker = {
        ticker: metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    risk_capital = float(args.risk_capital)
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "net_pnl": float(overall["pnl_return"]) * risk_capital,
        "risk_capital": risk_capital,
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Intraday Circuit Breaker",
        "",
        "This result applies a stateful intraday risk circuit selected walk-forward by ticker-month. A prior trade only affects later entries after its option-label exit minute has elapsed.",
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
        f"- Risk capital: ${risk_capital:,.0f}",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a causal intraday circuit breaker to event-option trades.")
    parser.add_argument("--trades", required=True)
    parser.add_argument("--label-data", required=True, help="Event-option parquet with *_opt_exit_minutes columns.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--history-start-month", default="", help="Earliest OOS month kept for walk-forward selection history. Defaults to --start-month.")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--default-delta", type=int, default=35)
    parser.add_argument("--delta-map", nargs="*", default=["SPXW=35", "SPY=35", "QQQ=80"])
    parser.add_argument("--row-delta-column", default="", help="Optional per-trade delta column; values are mapped to the nearest available label bucket.")
    parser.add_argument("--select-months", type=int, default=2)
    parser.add_argument("--stop-after-loss-streak-grid", nargs="+", type=int, default=[999, 1, 2, 3])
    parser.add_argument("--daily-loss-limit-grid", nargs="+", type=float, default=[-999.0, -0.3, -0.6, -0.9, -1.2, -1.5])
    parser.add_argument("--total-loss-limit-grid", nargs="+", type=int, default=[999, 2, 3, 4])
    parser.add_argument("--min-trades-before-halt-grid", nargs="+", type=int, default=[0])
    parser.add_argument("--min-select-trades", type=int, default=18)
    parser.add_argument("--min-select-month-trades", type=int, default=8)
    parser.add_argument("--min-select-pf", type=float, default=0.0)
    parser.add_argument("--min-select-win-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.10)
    parser.add_argument("--max-call-rate", type=float, default=0.90)
    parser.add_argument("--daily-win-weight", type=float, default=0.50)
    parser.add_argument("--daily-dd-weight", type=float, default=0.05)
    parser.add_argument("--side-specific", action="store_true", help="Track circuit halt state separately for CALL and PUT trades.")
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
    delta_map = parse_delta_map([str(x) for x in args.delta_map])
    trades = load_trades(Path(args.trades))
    trades = load_exit_minutes(Path(args.label_data), trades, delta_map, int(args.default_delta), str(args.row_delta_column))
    keep_months = month_range(str(args.start_month), str(args.end_month))
    history_start = str(args.history_start_month or args.start_month)
    history_months = month_range(history_start, str(args.end_month))
    trades = trades[trades["test_month"].astype(str).isin(history_months)].copy()
    configs = candidate_configs(args)
    filtered = pd.DataFrame()
    folds = pd.DataFrame()
    if not bool(args.skip_walkforward):
        filtered, folds = walkforward_apply(trades, configs, args)
        filtered.to_csv(output_dir / "intraday_circuit_trades.csv", index=False)
        folds.to_csv(output_dir / "intraday_circuit_folds.csv", index=False)
        write_plot(output_dir, filtered, float(args.risk_capital))
        write_summary(output_dir, filtered, folds, args)
    if bool(args.export_deploy_config):
        export_deploy_config(output_dir, trades, configs, args)
    print(json.dumps({"overall": metrics(filtered, keep_months), "trades": int(len(filtered))}, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
