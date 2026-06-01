from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.train_backtest_option_policy import fmt_float, fmt_money, fmt_pct, trade_metrics


DEFAULT_POLICIES = [
    "fixed_delta_0.70_hard",
    "fixed_delta_0.70_learned_exit_5m",
    "option_value_rule_select_hard",
    "option_value_hold180_select_hard",
    "option_value_best_select_hard",
]


def load_policy_trades(wf_dir: Path, policies: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for policy in policies:
        path = wf_dir / f"{policy}_wf_trades.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing policy trade file: {path}")
        frame = pd.read_csv(path)
        frame["fold_month"] = frame["fold_month"].astype(str).str[:6]
        frame["date"] = frame["date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
        frame["policy"] = policy
        out[policy] = frame
    return out


def order_trades(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    cols = [c for c in ["date", "time", "ticker", "signal_id", "candidate_id"] if c in frame.columns]
    return frame.sort_values(cols).reset_index(drop=True)


def metrics_for(frame: pd.DataFrame) -> dict:
    return trade_metrics(order_trades(frame))


def metric_score(metrics: dict, dd_penalty: float, pf_weight: float, wr_weight: float) -> float:
    pnl = float(metrics.get("pnl_dollars", 0.0))
    dd = abs(float(metrics.get("max_drawdown", 0.0)))
    pf = float(metrics.get("profit_factor", 0.0))
    wr = float(metrics.get("win_rate", 0.0))
    pf_term = math.log(max(pf, 1e-6)) if np.isfinite(pf) else math.log(20.0)
    return pnl - float(dd_penalty) * dd + float(pf_weight) * pf_term + float(wr_weight) * wr


def candidate_history(
    trades_by_policy: dict[str, pd.DataFrame],
    policy: str,
    months: list[str],
    ticker: str | None,
) -> pd.DataFrame:
    frame = trades_by_policy[policy]
    mask = frame["fold_month"].isin(months)
    if ticker is not None:
        mask &= frame["ticker"].astype(str) == str(ticker)
    return frame.loc[mask].copy()


def select_policy(
    trades_by_policy: dict[str, pd.DataFrame],
    policies: list[str],
    month: str,
    ticker: str | None,
    config: dict,
    all_months: list[str],
) -> tuple[str, dict]:
    lookback = int(config["lookback_months"])
    idx = all_months.index(month)
    past = all_months[max(0, idx - lookback) : idx]
    default_policy = str(config["default_policy"])
    if not past:
        return default_policy, {"reason": "no_history", "past_months": ""}

    rows = []
    for policy in policies:
        hist = candidate_history(trades_by_policy, policy, past, ticker)
        metrics = metrics_for(hist)
        score = metric_score(metrics, config["dd_penalty"], config["pf_weight"], config["wr_weight"])
        eligible = (
            int(metrics.get("trades", 0)) >= int(config["min_history_trades"])
            and float(metrics.get("profit_factor", 0.0)) >= float(config["min_history_pf"])
            and float(metrics.get("win_rate", 0.0)) >= float(config["min_history_wr"])
            and float(metrics.get("pnl_dollars", 0.0)) > float(config["min_history_pnl"])
        )
        rows.append({"policy": policy, "eligible": eligible, "score": score, **metrics})

    table = pd.DataFrame(rows)
    fixed_row = table[table["policy"] == default_policy]
    fixed_score = float(fixed_row.iloc[0]["score"]) if not fixed_row.empty else -1e18
    eligible = table[table["eligible"]].copy()
    if eligible.empty:
        return default_policy, {"reason": "no_eligible", "past_months": ",".join(past), "candidates": rows}
    best = eligible.sort_values(["score", "pnl_dollars", "profit_factor"], ascending=False).iloc[0]
    if str(best["policy"]) != default_policy and float(best["score"]) < fixed_score + float(config["switch_margin"]):
        return default_policy, {"reason": "margin_fallback", "past_months": ",".join(past), "candidates": rows}
    return str(best["policy"]), {"reason": "selected", "past_months": ",".join(past), "candidates": rows}


def combine_policy(
    trades_by_policy: dict[str, pd.DataFrame],
    policies: list[str],
    config: dict,
    start_month: str,
    end_month: str | None,
    scope: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_months = sorted(trades_by_policy[str(config["default_policy"])]["fold_month"].unique().tolist())
    months = [m for m in all_months if m >= str(start_month)]
    if end_month:
        months = [m for m in months if m <= str(end_month)]
    tickers = sorted(trades_by_policy[str(config["default_policy"])]["ticker"].astype(str).unique().tolist())

    parts = []
    decisions = []
    for month in months:
        scopes = tickers if scope == "ticker" else [None]
        for ticker in scopes:
            policy, payload = select_policy(trades_by_policy, policies, month, ticker, config, all_months)
            frame = trades_by_policy[policy]
            mask = frame["fold_month"].astype(str) == str(month)
            if ticker is not None:
                mask &= frame["ticker"].astype(str) == str(ticker)
            chosen = frame.loc[mask].copy()
            chosen["switch_policy"] = policy
            chosen["switch_scope"] = "ALL" if ticker is None else str(ticker)
            chosen["switch_reason"] = payload.get("reason", "")
            parts.append(chosen)
            decisions.append(
                {
                    "fold_month": month,
                    "ticker": "ALL" if ticker is None else str(ticker),
                    "selected_policy": policy,
                    "reason": payload.get("reason", ""),
                    "past_months": payload.get("past_months", ""),
                }
            )
    trades = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return order_trades(trades), pd.DataFrame(decisions)


def policy_for_period(trades_by_policy: dict[str, pd.DataFrame], policy: str, start_month: str, end_month: str | None) -> pd.DataFrame:
    frame = trades_by_policy[policy]
    mask = frame["fold_month"].astype(str) >= str(start_month)
    if end_month:
        mask &= frame["fold_month"].astype(str) <= str(end_month)
    return order_trades(frame.loc[mask].copy())


def monthly_ticker_stats(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for (month, ticker), part in frame.groupby(["fold_month", "ticker"], sort=True):
        metrics = metrics_for(part)
        rows.append({"fold_month": month, "ticker": ticker, **metrics})
    return pd.DataFrame(rows)


def row_for(label: str, frame: pd.DataFrame) -> dict:
    metrics = metrics_for(frame)
    metrics["policy"] = label
    metrics["avg_delta_abs"] = float(frame["actual_delta_abs"].astype(float).mean()) if "actual_delta_abs" in frame and not frame.empty else float("nan")
    metrics["avg_hold_minutes"] = float(frame["hold_minutes"].astype(float).mean()) if "hold_minutes" in frame and not frame.empty else float("nan")
    month_ticker = monthly_ticker_stats(frame)
    metrics["min_trades_month_ticker"] = int(month_ticker["trades"].min()) if not month_ticker.empty else 0
    metrics["months_below_15_trades_ticker"] = int((month_ticker["trades"] < 15).sum()) if not month_ticker.empty else 0
    return metrics


def evaluate_config(
    trades_by_policy: dict[str, pd.DataFrame],
    policies: list[str],
    config: dict,
    scope: str,
    start_month: str,
    end_month: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    trades, decisions = combine_policy(trades_by_policy, policies, config, start_month, end_month, scope)
    metrics = row_for("policy_switcher", trades)
    return trades, decisions, metrics


def config_grid(default_policy: str) -> list[dict]:
    rows = []
    for scope in ["ticker", "global"]:
        for lookback in [3, 6, 9, 12]:
            for min_pf in [1.0, 1.20, 1.30]:
                for min_wr in [0.0, 0.45, 0.50]:
                    for dd_penalty in [0.0, 0.10, 0.25]:
                        for switch_margin in [0.0, 500.0, 1500.0]:
                            rows.append(
                                {
                                    "scope": scope,
                                    "default_policy": default_policy,
                                    "lookback_months": lookback,
                                    "min_history_trades": 30 if scope == "global" else 8,
                                    "min_history_pf": min_pf,
                                    "min_history_wr": min_wr,
                                    "min_history_pnl": 0.0,
                                    "dd_penalty": dd_penalty,
                                    "pf_weight": 2500.0,
                                    "wr_weight": 2500.0,
                                    "switch_margin": switch_margin,
                                }
                            )
    return rows


def write_summary(
    output_dir: Path,
    args,
    selected_config: dict,
    rows: list[dict],
    train_rows: list[dict],
    oos_rows: list[dict],
    decisions: pd.DataFrame,
) -> None:
    lines = [
        "# OptionValueJEPA Policy Switcher",
        "",
        f"Walk-forward dir: `{args.walkforward_dir}`",
        f"Meta-train months: `{args.meta_train_start}` to `{args.meta_train_end}`",
        f"OOS months: `{args.oos_start}` to `{args.oos_end}`",
        "",
        "The switcher chooses one full policy per ticker-month using only prior months. It never selects a strike using the current month outcome.",
        "",
        "## Selected Config",
        "",
        "```json",
        json.dumps(selected_config, indent=2),
        "```",
        "",
        "## Meta-Train Comparison",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Min Trades/Ticker-Month | Low-Volume Cells |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in train_rows:
        lines.append(
            f"| {row['policy']} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | {fmt_float(row['profit_factor'])} | "
            f"{fmt_money(row['pnl_dollars'])} | {fmt_money(row['max_drawdown'])} | "
            f"{int(row['min_trades_month_ticker'])} | {int(row['months_below_15_trades_ticker'])} |"
        )
    lines += [
        "",
        "## Apr/May OOS Comparison",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in oos_rows:
        lines.append(
            f"| {row['policy']} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | {fmt_float(row['profit_factor'])} | "
            f"{fmt_money(row['pnl_dollars'])} | {fmt_money(row['max_drawdown'])} | "
            f"{fmt_float(row.get('avg_delta_abs', float('nan')))} | {fmt_float(row.get('avg_hold_minutes', float('nan')), 1)} | "
            f"{int(row['min_trades_month_ticker'])} | {int(row['months_below_15_trades_ticker'])} |"
        )
    lines += [
        "",
        "## OOS Decisions",
        "",
        "| Month | Ticker | Selected Policy | Reason | Past Months |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, row in decisions.iterrows():
        lines.append(
            f"| {row['fold_month']} | {row['ticker']} | {row['selected_policy']} | {row['reason']} | {row['past_months']} |"
        )
    lines += [
        "",
        "## Top Meta-Train Configs",
        "",
        "| Rank | Scope | Lookback | MinPF | MinWR | DD Penalty | Margin | PF | WR | PnL | Score |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(rows[:15], start=1):
        cfg = row["config"]
        lines.append(
            f"| {rank} | {cfg['scope']} | {cfg['lookback_months']} | {cfg['min_history_pf']:.2f} | "
            f"{cfg['min_history_wr']:.2f} | {cfg['dd_penalty']:.2f} | {cfg['switch_margin']:.0f} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_pct(row['win_rate'])} | {fmt_money(row['pnl_dollars'])} | "
            f"{fmt_float(row['score'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Promotion requires Apr/May OOS to beat fixed 0.70 on PF and PnL while maintaining the requested WR/volume gates.",
        "- If the selected switcher only improves meta-train but not Apr/May, it remains research-only.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward policy switcher over OptionValueJEPA policy outputs.")
    parser.add_argument("--walkforward-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    parser.add_argument("--default-policy", default="fixed_delta_0.70_hard")
    parser.add_argument("--meta-train-start", default="202308")
    parser.add_argument("--meta-train-end", default="202603")
    parser.add_argument("--oos-start", default="202604")
    parser.add_argument("--oos-end", default="202605")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    wf_dir = Path(args.walkforward_dir)
    policies = [str(p) for p in args.policies]
    trades_by_policy = load_policy_trades(wf_dir, policies + ["oracle_best_delta_hard", "oracle_best_delta_oracle_exit"])

    grid_rows = []
    best = None
    for config in config_grid(str(args.default_policy)):
        train_trades, _, metrics = evaluate_config(
            trades_by_policy,
            policies,
            config,
            config["scope"],
            str(args.meta_train_start),
            str(args.meta_train_end),
        )
        score = metric_score(metrics, config["dd_penalty"], config["pf_weight"], config["wr_weight"])
        metrics["score"] = score
        grid_rows.append({"config": config, **metrics})
        if best is None or score > best["score"]:
            best = {"config": config, "score": score, "trades": train_trades, "metrics": metrics}
    if best is None:
        raise RuntimeError("No switcher config evaluated.")
    selected_config = dict(best["config"])

    selected_train, train_decisions, _ = evaluate_config(
        trades_by_policy,
        policies,
        selected_config,
        selected_config["scope"],
        str(args.meta_train_start),
        str(args.meta_train_end),
    )
    selected_oos, oos_decisions, _ = evaluate_config(
        trades_by_policy,
        policies,
        selected_config,
        selected_config["scope"],
        str(args.oos_start),
        str(args.oos_end),
    )

    baseline_train = policy_for_period(trades_by_policy, args.default_policy, args.meta_train_start, args.meta_train_end)
    baseline_oos = policy_for_period(trades_by_policy, args.default_policy, args.oos_start, args.oos_end)
    oracle_train = policy_for_period(trades_by_policy, "oracle_best_delta_hard", args.meta_train_start, args.meta_train_end)
    oracle_oos = policy_for_period(trades_by_policy, "oracle_best_delta_hard", args.oos_start, args.oos_end)
    oracle_exit_oos = policy_for_period(trades_by_policy, "oracle_best_delta_oracle_exit", args.oos_start, args.oos_end)

    train_rows = [
        row_for(args.default_policy, baseline_train),
        row_for("policy_switcher", selected_train),
        row_for("oracle_best_delta_hard", oracle_train),
    ]
    oos_rows = [
        row_for(args.default_policy, baseline_oos),
        row_for("policy_switcher", selected_oos),
        row_for("oracle_best_delta_hard", oracle_oos),
        row_for("oracle_best_delta_oracle_exit", oracle_exit_oos),
    ]

    selected_train.to_csv(output_dir / "policy_switcher_meta_train_trades.csv", index=False)
    selected_oos.to_csv(output_dir / "policy_switcher_oos_trades.csv", index=False)
    train_decisions.to_csv(output_dir / "meta_train_decisions.csv", index=False)
    oos_decisions.to_csv(output_dir / "oos_decisions.csv", index=False)
    pd.DataFrame(
        [{k: v for k, v in row.items() if k != "config"} | {f"config_{k}": v for k, v in row["config"].items()} for row in grid_rows]
    ).sort_values("score", ascending=False).to_csv(output_dir / "config_grid.csv", index=False)

    grid_rows = sorted(grid_rows, key=lambda row: row["score"], reverse=True)
    metadata = {
        "args": vars(args),
        "selected_config": selected_config,
        "meta_train": train_rows,
        "oos": oos_rows,
        "top_configs": grid_rows[:20],
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, args, selected_config, grid_rows, train_rows, oos_rows, oos_decisions)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
