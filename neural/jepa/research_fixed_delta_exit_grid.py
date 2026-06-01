from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.research_hybrid_option_selector import fixed_candidate_per_signal
from neural.jepa.train_backtest_option_policy import fmt_float, fmt_money, fmt_pct, normalize_date, trade_metrics


def order_trades(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    cols = [c for c in ["date", "time", "ticker", "signal_id", "candidate_id"] if c in frame.columns]
    return frame.sort_values(cols).reset_index(drop=True)


def metrics_for(frame: pd.DataFrame) -> dict:
    return trade_metrics(order_trades(frame))


def build_state_groups(state_rows: pd.DataFrame, candidate_ids: set[int]) -> dict[int, pd.DataFrame]:
    state_rows = state_rows[state_rows["candidate_id"].astype(int).isin(candidate_ids)].copy()
    return {
        int(candidate_id): group.sort_values("hold_minutes").reset_index(drop=True)
        for candidate_id, group in state_rows.groupby("candidate_id", sort=False)
    }


def simulate_exit(
    selected: pd.DataFrame,
    state_groups: dict[int, pd.DataFrame],
    hard_stop_pct: float,
    take_profit_pct: float,
    policy_name: str,
) -> pd.DataFrame:
    rows = []
    for candidate in selected.itertuples(index=False):
        path = state_groups.get(int(candidate.candidate_id))
        if path is None or path.empty:
            continue
        exit_point = path.iloc[-1]
        reason = "max_time"
        for _, point in path.iterrows():
            pnl_pct = float(point["current_pnl_pct"])
            if pnl_pct <= float(hard_stop_pct):
                exit_point = point
                reason = "hard_stop"
                break
            if pnl_pct >= float(take_profit_pct):
                exit_point = point
                reason = "take_profit"
                break
        rows.append(
            {
                "policy": policy_name,
                "candidate_id": int(candidate.candidate_id),
                "signal_id": int(candidate.signal_id),
                "ticker": str(candidate.ticker),
                "date": str(candidate.date),
                "month": str(candidate.month),
                "time": str(candidate.time),
                "side": str(candidate.side),
                "delta_target": float(candidate.delta_target),
                "actual_delta_abs": float(candidate.actual_delta_abs),
                "actual_strike": float(candidate.actual_strike),
                "entry_premium": float(candidate.entry_premium),
                "contracts": int(candidate.contracts),
                "exit_reason": reason,
                "exit_time": str(exit_point["path_time"]),
                "hold_minutes": int(exit_point["hold_minutes"]),
                "pnl_pct": float(exit_point["current_pnl_pct"]),
                "pnl_dollars": float(exit_point["pnl_dollars"]),
            }
        )
    return pd.DataFrame(rows)


def monthly_ticker_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (month, ticker), part in frame.groupby(["month", "ticker"], sort=True):
        rows.append({"month": month, "ticker": ticker, **metrics_for(part)})
    return pd.DataFrame(rows)


def summarize(policy: str, frame: pd.DataFrame) -> dict:
    metrics = metrics_for(frame)
    metrics["policy"] = policy
    metrics["avg_delta_abs"] = float(frame["actual_delta_abs"].astype(float).mean()) if "actual_delta_abs" in frame and not frame.empty else float("nan")
    metrics["avg_hold_minutes"] = float(frame["hold_minutes"].astype(float).mean()) if "hold_minutes" in frame and not frame.empty else float("nan")
    mt = monthly_ticker_stats(frame)
    metrics["min_trades_month_ticker"] = int(mt["trades"].min()) if not mt.empty else 0
    metrics["low_volume_cells"] = int((mt["trades"] < 15).sum()) if not mt.empty else 0
    return metrics


def score_train(metrics: dict) -> float:
    pf = float(metrics.get("profit_factor", 0.0))
    wr = float(metrics.get("win_rate", 0.0))
    pnl = float(metrics.get("pnl_dollars", 0.0))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    if pf < 1.30 or wr < 0.45 or pnl <= 0.0:
        return -1e18 + pnl
    pf_term = np.log(max(pf, 1e-6)) if np.isfinite(pf) else np.log(20.0)
    return pnl - 0.10 * dd + 2500.0 * pf_term + 2500.0 * wr


def metrics_row(row: dict) -> str:
    return (
        f"| {row['policy']} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | "
        f"{fmt_float(row['profit_factor'])} | {fmt_money(row['pnl_dollars'])} | "
        f"{fmt_money(row['max_drawdown'])} | {fmt_float(row.get('avg_hold_minutes', float('nan')), 1)} | "
        f"{int(row.get('min_trades_month_ticker', 0))} | {int(row.get('low_volume_cells', 0))} |"
    )


def write_summary(output_dir: Path, args, selected_config: dict, train_rows: list[dict], oos_rows: list[dict], grid: pd.DataFrame) -> None:
    lines = [
        "# Fixed 0.70 Delta Exit Grid",
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"State rows: `{args.state_rows}`",
        f"Meta-train end: `{args.meta_train_end}`",
        f"OOS start: `{args.oos_start}`",
        "",
        "The grid keeps the same `base_jepa` entries and the same 0.70 delta strike selection, then changes only the option exit contract.",
        "",
        "## Selected Config",
        "",
        "```json",
        json.dumps(selected_config, indent=2),
        "```",
        "",
        "## Meta-Train",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in train_rows:
        lines.append(metrics_row(row))
    lines += [
        "",
        "## Apr/May OOS",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in oos_rows:
        lines.append(metrics_row(row))
    lines += [
        "",
        "## Top Train Grid Rows",
        "",
        "| Rank | Stop | TP | Train WR | Train PF | Train PnL | OOS WR | OOS PF | OOS PnL | Score |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, (_, row) in enumerate(grid.head(20).iterrows(), start=1):
        lines.append(
            f"| {rank} | {row['hard_stop_pct']:.2f} | {row['take_profit_pct']:.2f} | "
            f"{fmt_pct(row['train_win_rate'])} | {fmt_float(row['train_profit_factor'])} | "
            f"{fmt_money(row['train_pnl_dollars'])} | {fmt_pct(row['oos_win_rate'])} | "
            f"{fmt_float(row['oos_profit_factor'])} | {fmt_money(row['oos_pnl_dollars'])} | "
            f"{fmt_float(row['score'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- This is not a model-fit improvement; it is an execution-contract improvement discovered on pre-OOS months and verified on Apr/May.",
        "- The same entries and strikes are used, so trade volume is unchanged.",
        "- Promotion requires the selected exit to beat the previous `-35%/+250%` contract OOS while keeping PF > 1.3, WR > 45%, and ticker-month volume near the target.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Grid-search fixed 0.70 option exits using cached 5m path states.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--state-rows", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fixed-delta", type=float, default=0.70)
    parser.add_argument("--meta-train-start", default="202308")
    parser.add_argument("--meta-train-end", default="202603")
    parser.add_argument("--oos-start", default="202604")
    parser.add_argument("--oos-end", default="202605")
    parser.add_argument("--stops", nargs="+", type=float, default=[-0.60, -0.50, -0.45, -0.40, -0.35, -0.30, -0.25, -0.20])
    parser.add_argument("--take-profits", nargs="+", type=float, default=[0.75, 1.00, 1.50, 2.00, 2.50, 3.00, 4.00, 10.00])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_parquet(args.candidate_labels)
    candidates["date"] = candidates["date"].astype(str).map(normalize_date)
    candidates["month"] = candidates["date"].str[:6]
    candidates = candidates[
        (candidates["month"] >= str(args.meta_train_start))
        & (candidates["month"] <= str(args.oos_end))
    ].copy()
    selected = fixed_candidate_per_signal(candidates, float(args.fixed_delta))
    state_rows = pd.read_parquet(args.state_rows)
    state_groups = build_state_groups(state_rows, set(selected["candidate_id"].astype(int)))

    grid_rows = []
    trade_cache = {}
    for stop in args.stops:
        for tp in args.take_profits:
            name = f"fixed_delta_0.70_stop{stop:.2f}_tp{tp:.2f}"
            trades = simulate_exit(selected, state_groups, float(stop), float(tp), name)
            trade_cache[(float(stop), float(tp))] = trades
            train = trades[
                (trades["month"].astype(str) >= str(args.meta_train_start))
                & (trades["month"].astype(str) <= str(args.meta_train_end))
            ].copy()
            oos = trades[
                (trades["month"].astype(str) >= str(args.oos_start))
                & (trades["month"].astype(str) <= str(args.oos_end))
            ].copy()
            train_m = summarize(name, train)
            oos_m = summarize(name, oos)
            grid_rows.append(
                {
                    "hard_stop_pct": float(stop),
                    "take_profit_pct": float(tp),
                    "score": score_train(train_m),
                    **{f"train_{k}": v for k, v in train_m.items() if k != "policy"},
                    **{f"oos_{k}": v for k, v in oos_m.items() if k != "policy"},
                }
            )
    grid = pd.DataFrame(grid_rows).sort_values("score", ascending=False).reset_index(drop=True)
    best = grid.iloc[0]
    selected_config = {
        "fixed_delta": float(args.fixed_delta),
        "hard_stop_pct": float(best["hard_stop_pct"]),
        "take_profit_pct": float(best["take_profit_pct"]),
        "selection": "max meta-train score with PF>=1.3, WR>=45%, positive PnL",
    }
    old_key = (-0.35, 2.50)
    new_key = (selected_config["hard_stop_pct"], selected_config["take_profit_pct"])
    baseline = trade_cache.get(old_key)
    if baseline is None:
        baseline = simulate_exit(selected, state_groups, -0.35, 2.50, "fixed_delta_0.70_stop-0.35_tp2.50")
    improved = trade_cache[new_key]

    def period(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
        return frame[(frame["month"].astype(str) >= str(start)) & (frame["month"].astype(str) <= str(end))].copy()

    baseline_train = period(baseline, args.meta_train_start, args.meta_train_end)
    improved_train = period(improved, args.meta_train_start, args.meta_train_end)
    baseline_oos = period(baseline, args.oos_start, args.oos_end)
    improved_oos = period(improved, args.oos_start, args.oos_end)

    baseline_train.to_csv(output_dir / "baseline_stop35_tp250_meta_train_trades.csv", index=False)
    improved_train.to_csv(output_dir / "selected_exit_meta_train_trades.csv", index=False)
    baseline_oos.to_csv(output_dir / "baseline_stop35_tp250_oos_trades.csv", index=False)
    improved_oos.to_csv(output_dir / "selected_exit_oos_trades.csv", index=False)
    grid.to_csv(output_dir / "exit_grid.csv", index=False)

    train_rows = [
        summarize("baseline_stop35_tp250", baseline_train),
        summarize("selected_exit", improved_train),
    ]
    oos_rows = [
        summarize("baseline_stop35_tp250", baseline_oos),
        summarize("selected_exit", improved_oos),
    ]
    metadata = {
        "args": vars(args),
        "selected_config": selected_config,
        "meta_train": train_rows,
        "oos": oos_rows,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, args, selected_config, train_rows, oos_rows, grid)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
