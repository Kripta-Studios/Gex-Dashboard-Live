from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from walkforward_event_option_gate import metrics


def parse_variant(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        path = Path(spec)
        return path.name, path
    name, raw = spec.split("=", 1)
    return name.strip(), Path(raw.strip())


def load_trades(variant_specs: list[str]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for spec in variant_specs:
        name, path = parse_variant(spec)
        trade_file = path / "event_option_gate_trades.csv"
        if not trade_file.exists():
            raise FileNotFoundError(f"Missing trades for {name}: {trade_file}")
        trades = pd.read_csv(trade_file, dtype={"ticker": str, "date": str, "month": str, "test_month": str})
        trades["source_variant"] = name
        parts.append(trades)
    out = pd.concat(parts, ignore_index=True)
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["date"] = out["date"].astype(str)
    out["month"] = out["month"].astype(str)
    out["test_month"] = out["test_month"].astype(str)
    out["minute"] = pd.to_numeric(out["minute"], errors="coerce").fillna(-1).astype(int)
    for col in ("score", "realized_return"):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def add_consensus_features(trades: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["ticker", "date", "minute", "expiry_mode"]
    action_cols = group_cols + ["action"]
    out = trades.copy()
    out["total_votes"] = out.groupby(group_cols)["source_variant"].transform("count")
    out["action_votes"] = out.groupby(action_cols)["source_variant"].transform("count")
    out["action_score_mean"] = out.groupby(action_cols)["score"].transform("mean")
    out["action_score_max"] = out.groupby(action_cols)["score"].transform("max")
    out = out.sort_values(
        ["ticker", "date", "minute", "action", "action_votes", "action_score_mean", "score"],
        ascending=[True, True, True, True, False, False, False],
        kind="stable",
    )
    return out.drop_duplicates(action_cols, keep="first").reset_index(drop=True)


def deploy(candidates: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    selected = candidates[candidates["action_votes"].astype(float) >= float(args.min_action_votes)].copy()
    if float(args.min_action_score_mean) > 0.0:
        selected = selected[selected["action_score_mean"].astype(float) >= float(args.min_action_score_mean)].copy()
    if selected.empty:
        return selected
    rows: list[pd.Series] = []
    for (_, _), day in selected.sort_values(
        ["ticker", "date", "action_votes", "action_score_mean", "score"],
        ascending=[True, True, False, False, False],
        kind="stable",
    ).groupby(["ticker", "date"], sort=False):
        next_allowed = -1
        taken = 0
        side_taken = {"CALL": 0, "PUT": 0}
        seen: set[tuple[int, str]] = set()
        for _, row in day.iterrows():
            minute = int(row["minute"])
            side = str(row["action"])
            key = (minute, side)
            if key in seen or minute < next_allowed:
                continue
            if int(args.max_trades_per_day) < 999 and taken >= int(args.max_trades_per_day):
                break
            if int(args.max_side_trades_per_day) < 999 and side_taken.get(side, 0) >= int(args.max_side_trades_per_day):
                continue
            rows.append(row)
            seen.add(key)
            taken += 1
            side_taken[side] = side_taken.get(side, 0) + 1
            next_allowed = minute + int(args.cooldown_minutes)
    return pd.DataFrame(rows) if rows else selected.iloc[0:0].copy()


def fold_rows(trades: pd.DataFrame, tickers: list[str], months: list[str], config_name: str) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in tickers:
        for month in months:
            part = trades[(trades["ticker"].astype(str).str.upper() == ticker) & (trades["test_month"].astype(str) == month)].copy()
            row = metrics(part, [month])
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "deploy_config": config_name,
                    "val_months": "",
                    "train_rows": 0,
                    "val_rows": 0,
                    "test_rows": int(len(part)),
                    "val_score": 0.0,
                    "abstained_invalid_val": False,
                    **{f"val_{key}": np.nan for key in row},
                    **{f"test_{key}": value for key, value in row.items()},
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a fixed consensus pseudo-variant from multiple event-option variant streams.")
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202205")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--min-action-votes", type=int, default=1)
    parser.add_argument("--min-action-score-mean", type=float, default=0.0)
    parser.add_argument("--max-trades-per-day", type=int, default=3)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--max-side-trades-per-day", type=int, default=2)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tickers = [str(t).upper() for t in args.tickers]
    months = []
    year = int(str(args.start_month)[:4])
    month = int(str(args.start_month)[4:6])
    while True:
        current = f"{year:04d}{month:02d}"
        months.append(current)
        if current == str(args.end_month):
            break
        month += 1
        if month == 13:
            year += 1
            month = 1

    trades = load_trades(args.variant)
    trades = trades[trades["ticker"].isin(tickers) & trades["test_month"].isin(months)].copy()
    candidates = add_consensus_features(trades)
    selected = deploy(candidates, args)
    config_name = (
        f"cons_votes{args.min_action_votes}_score{args.min_action_score_mean:.2f}"
        f"_maxday{args.max_trades_per_day}_cool{args.cooldown_minutes}_maxside{args.max_side_trades_per_day}"
    )
    if not selected.empty:
        selected = selected.copy()
        selected["variant"] = config_name
        selected["deploy_config"] = config_name
        selected["score"] = selected["action_score_mean"].astype(float)
    folds = fold_rows(selected, tickers, months, config_name)
    selected.to_csv(output_dir / "event_option_gate_trades.csv", index=False)
    folds.to_csv(output_dir / "fold_configs.csv", index=False)
    (output_dir / "args.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    print(json.dumps({"config": config_name, "trades": int(len(selected)), "folds": int(len(folds))}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
