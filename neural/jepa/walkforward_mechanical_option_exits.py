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

from neural.jepa.train_backtest_option_policy import trade_metrics


def normalize_months(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = out["date"].astype(str).str.replace("-", "", regex=False)
    if "month" not in out.columns:
        out["month"] = out["date"].str.slice(0, 6)
    else:
        out["month"] = out["month"].astype(str)
    return out


def time_to_minutes(value: str) -> int:
    parts = str(value).split(":")
    if len(parts) < 2:
        return 0
    return int(parts[0]) * 60 + int(parts[1])


def apply_time_gate(candidates: pd.DataFrame, gate: str) -> pd.DataFrame:
    if candidates.empty or gate == "all":
        return candidates.copy()
    minutes = candidates["time"].astype(str).map(time_to_minutes)
    if gate == "early_only":
        return candidates[minutes <= time_to_minutes("11:30")].copy()
    if gate == "exclude_1131_1230":
        return candidates[~((minutes > time_to_minutes("11:30")) & (minutes <= time_to_minutes("12:30")))].copy()
    if gate == "exclude_late":
        return candidates[minutes <= time_to_minutes("14:30")].copy()
    raise ValueError(f"Unsupported gate: {gate}")


def select_fixed_delta(candidates: pd.DataFrame, delta_target: float, gate: str) -> pd.DataFrame:
    filtered = candidates[np.isclose(candidates["delta_target"].astype(float), float(delta_target))].copy()
    filtered = apply_time_gate(filtered, gate)
    return filtered.sort_values(["date", "time", "signal_id", "candidate_id"]).reset_index(drop=True)


def build_state_groups(state_rows: pd.DataFrame) -> dict[int, pd.DataFrame]:
    work = state_rows.copy()
    work["candidate_id"] = work["candidate_id"].astype(int)
    return {
        int(candidate_id): group.sort_values("hold_minutes").reset_index(drop=True)
        for candidate_id, group in work.groupby("candidate_id", sort=False)
    }


def simulate_selected(
    selected: pd.DataFrame,
    state_groups: dict[int, pd.DataFrame],
    config: dict,
    policy_name: str,
) -> pd.DataFrame:
    trades: list[dict] = []
    hard_stop = float(config["hard_stop_pct"])
    take_profit = float(config["take_profit_pct"])
    activation = float(config["trail_activation_pct"])
    drawdown = float(config["trail_drawdown_pct"])
    use_trail = np.isfinite(activation) and np.isfinite(drawdown)
    for _, candidate in selected.iterrows():
        path = state_groups.get(int(candidate["candidate_id"]))
        if path is None or path.empty:
            continue
        exit_point = path.iloc[-1]
        exit_reason = "max_time"
        peak = -float("inf")
        for path_idx, (_, point) in enumerate(path.iterrows()):
            pnl_pct = float(point["current_pnl_pct"])
            peak = max(peak, pnl_pct)
            if pnl_pct <= hard_stop:
                exit_point = path.iloc[path_idx]
                exit_reason = "hard_stop"
                break
            if pnl_pct >= take_profit:
                exit_point = path.iloc[path_idx]
                exit_reason = "take_profit"
                break
            if use_trail and peak >= activation and pnl_pct <= peak - drawdown:
                exit_point = path.iloc[path_idx]
                exit_reason = "trail_stop"
                break
        trades.append(
            {
                "policy": policy_name,
                "candidate_id": int(candidate["candidate_id"]),
                "signal_id": int(candidate["signal_id"]),
                "ticker": str(candidate["ticker"]),
                "date": str(candidate["date"]),
                "month": str(candidate["month"]),
                "time": str(candidate["time"]),
                "side": str(candidate["side"]),
                "delta_target": float(candidate["delta_target"]),
                "actual_delta_abs": float(candidate["actual_delta_abs"]),
                "actual_strike": float(candidate["actual_strike"]),
                "entry_premium": float(candidate["entry_premium"]),
                "contracts": int(candidate["contracts"]),
                "exit_reason": exit_reason,
                "exit_time": str(exit_point["path_time"]),
                "hold_minutes": int(exit_point["hold_minutes"]),
                "pnl_pct": float(exit_point["current_pnl_pct"]),
                "pnl_dollars": float(exit_point["pnl_dollars"]),
                "hard_stop_pct": hard_stop,
                "take_profit_pct": take_profit,
                "trail_activation_pct": activation,
                "trail_drawdown_pct": drawdown,
                "time_gate": str(config["time_gate"]),
            }
        )
    return pd.DataFrame(trades).sort_values(["date", "time", "candidate_id"]).reset_index(drop=True)


def score(metrics: dict, min_trades: int) -> float:
    trades = int(metrics.get("trades", 0))
    pnl = float(metrics.get("pnl_dollars", 0.0))
    pf = float(metrics.get("profit_factor", 0.0))
    wr = float(metrics.get("win_rate", 0.0))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    if trades < min_trades or pnl <= 0.0 or not np.isfinite(pf) or pf <= 0.0:
        return -1e9 + pnl
    return pnl / 1000.0 + 80.0 * wr + 60.0 * np.log(max(pf, 1e-6)) + trades / 20.0 - dd / 1500.0


def config_key(config: dict) -> str:
    return (
        f"d{config['delta_target']:.2f}_hs{config['hard_stop_pct']:.2f}_"
        f"tp{config['take_profit_pct']:.2f}_ta{config['trail_activation_pct']:.2f}_"
        f"td{config['trail_drawdown_pct']:.2f}_{config['time_gate']}"
    )


def build_grid(args) -> list[dict]:
    grid: list[dict] = []
    no_trail = [(float("nan"), float("nan"))]
    trail_pairs = [(float(a), float(d)) for a in args.trail_activations for d in args.trail_drawdowns]
    for delta in args.delta_targets:
        for hard_stop in args.hard_stops:
            for take_profit in args.take_profits:
                for activation, drawdown in no_trail + trail_pairs:
                    for gate in args.time_gates:
                        grid.append(
                            {
                                "delta_target": float(delta),
                                "hard_stop_pct": float(hard_stop),
                                "take_profit_pct": float(take_profit),
                                "trail_activation_pct": float(activation),
                                "trail_drawdown_pct": float(drawdown),
                                "time_gate": str(gate),
                            }
                        )
    return grid


def main() -> int:
    parser = argparse.ArgumentParser(description="Monthly walk-forward for simple fixed-delta mechanical option exits.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--state-rows", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--delta-targets", nargs="+", type=float, default=[0.40, 0.50, 0.60, 0.70])
    parser.add_argument("--hard-stops", nargs="+", type=float, default=[-0.30, -0.50, -0.70])
    parser.add_argument("--take-profits", nargs="+", type=float, default=[0.15, 0.30, 0.50, 1.00, 2.50, 10.00])
    parser.add_argument("--trail-activations", nargs="+", type=float, default=[0.15, 0.25, 0.50, 0.75, 1.00])
    parser.add_argument("--trail-drawdowns", nargs="+", type=float, default=[0.05, 0.10, 0.15, 0.25, 0.35])
    parser.add_argument("--time-gates", nargs="+", default=["all", "exclude_1131_1230", "early_only", "exclude_late"])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = normalize_months(pd.read_parquet(args.candidate_labels))
    candidates = candidates[candidates["date"].astype(str) >= str(args.train_start_date)].copy()
    state_rows = pd.read_parquet(args.state_rows)
    state_groups = build_state_groups(state_rows)
    months = sorted(candidates["month"].astype(str).unique().tolist())
    test_months = [m for m in months if m >= str(args.start_month) and m <= str(args.end_month)]
    grid = build_grid(args)

    all_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    selected_rows: list[dict] = []

    for test_month in test_months:
        prior_months = [m for m in months if m < test_month]
        val_months = prior_months[-int(args.val_months) :]
        if not val_months:
            continue
        val_candidates = candidates[candidates["month"].isin(val_months)].copy()
        test_candidates = candidates[candidates["month"].astype(str) == test_month].copy()
        if val_candidates.empty or test_candidates.empty:
            continue

        best: dict | None = None
        best_score = -float("inf")
        for config in grid:
            selected_val = select_fixed_delta(val_candidates, float(config["delta_target"]), str(config["time_gate"]))
            val_trades = simulate_selected(selected_val, state_groups, config, "validation_mechanical")
            metrics = trade_metrics(val_trades)
            s = score(metrics, int(args.min_val_trades))
            if s > best_score:
                best_score = s
                best = {**config, "score": float(s), "validation_metrics": metrics}
        if best is None:
            continue
        selected_test = select_fixed_delta(test_candidates, float(best["delta_target"]), str(best["time_gate"]))
        policy_name = "mechanical_wf_" + config_key(best)
        test_trades = simulate_selected(selected_test, state_groups, best, policy_name)
        test_trades["fold_month"] = test_month
        all_trades.append(test_trades)
        metrics = trade_metrics(test_trades)
        fold_rows.append({"fold_month": test_month, **best, **metrics})
        selected_rows.append({"fold_month": test_month, "val_months": ",".join(val_months), **best})
        print(
            f"[MECH_WF] month={test_month} config={config_key(best)} "
            f"trades={metrics.get('trades', 0)} pf={metrics.get('profit_factor', float('nan')):.3f} "
            f"pnl={metrics.get('pnl_dollars', 0.0):.0f}",
            flush=True,
        )

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    fold_metrics = pd.DataFrame(fold_rows)
    selected = pd.DataFrame(selected_rows)
    overall = trade_metrics(trades)
    per_ticker = {str(k): trade_metrics(v) for k, v in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    by_month = {str(k): trade_metrics(v) for k, v in trades.groupby("fold_month", sort=True)} if not trades.empty else {}
    trades.to_csv(output_dir / "mechanical_wf_trades.csv", index=False)
    fold_metrics.to_csv(output_dir / "fold_metrics.csv", index=False)
    selected.to_csv(output_dir / "selected_configs.csv", index=False)
    metadata = {
        "args": vars(args),
        "overall": overall,
        "per_ticker": per_ticker,
        "by_month": by_month,
        "grid_size": len(grid),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Mechanical Option Exit Walk-Forward",
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"State rows: `{args.state_rows}`",
        f"Folds: `{args.start_month}`..`{args.end_month}`, validation months `{args.val_months}`",
        f"Grid size: `{len(grid)}`",
        "",
        "## Overall",
        "",
        json.dumps(overall, indent=2, allow_nan=True),
        "",
        "## Per Ticker",
        "",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
