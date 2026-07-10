from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics, position_exit_minute


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected NAME=PATH, got {value!r}")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty source name in {value!r}")
    return name, Path(raw_path.strip())


def derive_minute(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for col in ("minute", "minute_x", "minute_y", "entry_minute"):
        if col in df.columns:
            cand = pd.to_numeric(df[col], errors="coerce")
            out = out.where(out.notna(), cand)
    missing = out.isna()
    if missing.any() and "time" in df.columns:
        parsed = pd.to_datetime(df.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def load_trade_source(value: str, ticker: str, priority: int) -> pd.DataFrame:
    name, path = parse_named_path(value)
    if path.is_dir():
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
        found = next((path / item for item in candidates if (path / item).exists()), None)
        if found is None:
            raise FileNotFoundError(f"No known trade CSV found in {path}")
        path = found
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str}, low_memory=False)
    required = {"ticker", "date", "time", "action", "realized_return"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{path} missing required columns {missing}")
    if "test_month" not in df.columns:
        if "month" not in df.columns:
            raise ValueError(f"{path} missing month/test_month")
        df["test_month"] = df["month"].astype(str)
    if "month" not in df.columns:
        df["month"] = df["test_month"].astype(str)

    df = df[df["ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
    if df.empty:
        return df
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["date"] = df["date"].astype(str)
    df["time"] = df["time"].astype(str)
    df["month"] = df["test_month"].astype(str)
    df["test_month"] = df["test_month"].astype(str)
    df["action"] = df["action"].astype(str).str.upper()
    df["expiry_mode"] = df["expiry_mode"].astype(str) if "expiry_mode" in df.columns else ""
    df["realized_return"] = pd.to_numeric(df["realized_return"], errors="coerce").fillna(0.0)
    df["entry_minute"] = derive_minute(df)
    df["static_source"] = name
    df["static_source_file"] = str(path)
    df["static_source_priority"] = int(priority)
    if "score" not in df.columns:
        df["score"] = 0.0
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
    return df


def apply_static_union(
    trades: pd.DataFrame,
    max_day: int,
    cooldown_minutes: int,
    *,
    allow_overlapping_positions: bool = False,
) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    if not bool(allow_overlapping_positions) and "exit_minutes" not in trades.columns:
        raise ValueError(
            "static union requires exit_minutes for live-equivalent one-position replay; "
            "use allow_overlapping_positions=True only for research diagnostics"
        )
    rows: list[dict] = []
    ordered = trades.sort_values(
        ["ticker", "date", "entry_minute", "static_source_priority", "score"],
        ascending=[True, True, True, True, False],
        kind="stable",
    )
    for _, day in ordered.groupby(["ticker", "date"], sort=False):
        next_allowed = -1
        taken = 0
        seen: set[tuple[str, str, str, str]] = set()
        for row in day.itertuples(index=False):
            minute = int(row.entry_minute)
            if minute < next_allowed:
                continue
            if taken >= int(max_day):
                break
            key = (str(row.date), str(row.time), str(row.action), str(row.expiry_mode))
            if key in seen:
                continue
            values = row._asdict()
            values["static_union_max_day"] = int(max_day)
            values["static_union_cooldown_minutes"] = int(cooldown_minutes)
            values["static_union_count_before"] = int(taken)
            position_until = position_exit_minute(
                minute,
                values.get("exit_minutes"),
                allow_overlapping_positions=bool(allow_overlapping_positions),
            )
            values["static_union_position_exit_minute"] = int(position_until)
            rows.append(values)
            seen.add(key)
            taken += 1
            next_allowed = max(minute + int(cooldown_minutes), position_until)
    return pd.DataFrame(rows) if rows else trades.iloc[0:0].copy()


def parse_month_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    text = str(value).strip().replace('"', "")
    if not text or text.lower() == "nan":
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def load_fold_file(value: str) -> pd.DataFrame:
    name, path = parse_named_path(value)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, dtype=str)
    df["source_stream"] = name
    df["source_file"] = str(path)
    if "month" in df.columns and "test_month" not in df.columns:
        df["test_month"] = df["month"].astype(str)
    if "ticker" in df.columns:
        df["ticker"] = df["ticker"].astype(str).str.upper()
    return df


def audit_folds(folds: pd.DataFrame, months: list[str]) -> dict:
    if folds.empty:
        return {"passed": False, "folds_checked": 0, "issues": ["no fold files supplied"]}
    month_cols = [
        "train_months",
        "val_months",
        "select_months",
        "profile_train_months",
        "profile_inner_val_months",
        "inner_val_months",
        "core_months",
    ]
    issues: list[str] = []
    checked = 0
    for idx, row in folds.iterrows():
        test_month = str(row.get("test_month", "")).strip()
        if test_month in months:
            checked += 1
        for col in month_cols:
            if col not in folds.columns:
                continue
            bad = [month for month in parse_month_list(row.get(col)) if month >= test_month]
            if bad:
                issues.append(f"row {idx} {row.get('source_stream', '')} {test_month}: {col} has non-prior months {bad}")
        if len(issues) >= 50:
            break
    return {"passed": bool(checked > 0 and not issues), "folds_checked": int(checked), "issues": issues}


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
        output_dir / "static_union_daily_total.csv", index=False
    )
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(idx, daily.cumsum().values, color="#111827", linewidth=2.4)
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Static Union Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].grid(True, alpha=0.25)
    axes[1].bar(idx, daily.values, color=np.where(daily.values >= 0.0, "#16a34a", "#dc2626"), width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "static_union_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    overall = metrics(trades, months)
    monthly_rows: list[dict] = []
    for month in months:
        row = metrics(trades[trades["month"].astype(str).eq(month)].copy(), [month])
        row["month"] = month
        row["pnl_dollars"] = float(row["pnl_return"]) * float(args.risk_capital)
        monthly_rows.append(row)
    payload = {
        "overall": overall,
        "monthly": monthly_rows,
        "risk_capital": float(args.risk_capital),
        "net_pnl": float(overall["pnl_return"]) * float(args.risk_capital),
        "integrity": audit_folds(folds, months),
        "args": vars(args),
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Static Union Cooldown",
        "",
        "This artifact combines precomputed causal trade streams with fixed priority, same-time deduplication, max-day, and cooldown. It does not train or select inside the evaluated month.",
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
    for row in monthly_rows:
        lines.append(
            f"| {row['month']} | {int(row['trades'])} | {float(row['win_rate']):.1%} | "
            f"{float(row['profit_factor']):.3f} | {float(row['pnl_return']):.3f} | "
            f"{float(row['pnl_dollars']):,.0f} |"
        )
    lines += [
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(payload["integrity"], indent=2, allow_nan=True),
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
    parser = argparse.ArgumentParser(description="Apply a fixed-priority static union and cooldown to event-option streams.")
    parser.add_argument("--trade-source", action="append", required=True, help="NAME=trade_csv_or_result_dir. Repeatable; order defines priority.")
    parser.add_argument("--fold-file", action="append", default=[], help="NAME=fold_csv. Repeatable, used only for integrity audit.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--max-day", type=int, default=999)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument(
        "--allow-overlapping-positions",
        action="store_true",
        help="Research diagnostics only: ignore exit_minutes and permit overlapping same-ticker positions.",
    )
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = month_range(str(args.start_month), str(args.end_month))
    parts = [load_trade_source(item, str(args.ticker), idx) for idx, item in enumerate(args.trade_source)]
    parts = [part for part in parts if not part.empty]
    if not parts:
        raise RuntimeError("No trades after ticker filtering.")
    trades = pd.concat(parts, ignore_index=True, sort=False)
    trades = trades[trades["month"].astype(str).isin(months)].copy()
    selected = apply_static_union(
        trades,
        int(args.max_day),
        int(args.cooldown_minutes),
        allow_overlapping_positions=bool(args.allow_overlapping_positions),
    )
    selected = selected.sort_values(["date", "entry_minute", "ticker", "static_source"], kind="stable").reset_index(drop=True)
    selected.to_csv(output_dir / "static_union_trades.csv", index=False)
    selected.to_csv(output_dir / "combined_trades.csv", index=False)

    folds = pd.concat([load_fold_file(item) for item in args.fold_file], ignore_index=True, sort=False) if args.fold_file else pd.DataFrame()
    if not folds.empty:
        folds.to_csv(output_dir / "static_union_folds.csv", index=False)
        folds.to_csv(output_dir / "combined_folds.csv", index=False)
    write_plot(output_dir, selected, float(args.risk_capital))
    write_summary(output_dir, selected, folds, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
