from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_POLICIES = [
    "fixed_delta_0.70_hard",
    "option_value_hold180_select_hard",
    "option_value_rule_select_hard",
    "option_value_best_select_hard",
    "option_value_best_select_learned_exit_5m",
    "oracle_best_delta_hard",
    "oracle_best_delta_oracle_exit",
]


def fmt_pct(value: float) -> str:
    return "n/a" if not np.isfinite(value) else f"{value:.1f}%"


def fmt_num(value: float, digits: int = 3) -> str:
    return "n/a" if not np.isfinite(value) else f"{value:.{digits}f}"


def fmt_money(value: float) -> str:
    if not np.isfinite(value):
        return "n/a"
    return f"{value:+,.0f}"


def metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "max_drawdown": 0.0,
            "avg_delta_abs": float("nan"),
            "avg_hold_minutes": float("nan"),
        }
    pnl = trades["pnl_dollars"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_loss = abs(float(losses.sum()))
    cum = pnl.cumsum()
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0).mean() * 100.0),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "max_drawdown": float((cum - cum.cummax()).min()) if len(cum) else 0.0,
        "avg_delta_abs": float(trades["actual_delta_abs"].astype(float).mean()) if "actual_delta_abs" in trades else float("nan"),
        "avg_hold_minutes": float(trades["hold_minutes"].astype(float).mean()) if "hold_minutes" in trades else float("nan"),
    }


def load_policy(result_dir: Path, policy: str) -> pd.DataFrame:
    candidates = [
        result_dir / f"{policy}_wf_trades.csv",
        result_dir / f"{policy}_trades.csv",
    ]
    for path in candidates:
        if path.exists():
            out = pd.read_csv(path)
            out["policy"] = policy
            return out
    return pd.DataFrame()


def rows_for_metrics(frame: pd.DataFrame, policy: str, ticker: str | None = None) -> dict:
    item = metrics(frame)
    item["policy"] = policy
    item["ticker"] = ticker or "ALL"
    return item


def build_metrics_tables(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall = [rows_for_metrics(frame, policy) for policy, frame in frames.items()]
    per_ticker = []
    for policy, frame in frames.items():
        if frame.empty or "ticker" not in frame:
            continue
        for ticker, group in frame.groupby("ticker", sort=True):
            per_ticker.append(rows_for_metrics(group, policy, str(ticker)))
    return pd.DataFrame(overall), pd.DataFrame(per_ticker)


def compare_to_oracle(frames: dict[str, pd.DataFrame], oracle_policy: str = "oracle_best_delta_hard") -> pd.DataFrame:
    oracle = frames.get(oracle_policy, pd.DataFrame())
    if oracle.empty:
        return pd.DataFrame()
    keys = [c for c in ["signal_id", "ticker", "date"] if c in oracle.columns]
    if "signal_id" not in keys:
        return pd.DataFrame()
    oracle_cols = keys + ["candidate_id", "actual_delta_abs", "pnl_dollars"]
    oracle_slim = oracle[oracle_cols].rename(
        columns={
            "candidate_id": "oracle_candidate_id",
            "actual_delta_abs": "oracle_delta_abs",
            "pnl_dollars": "oracle_pnl_dollars",
        }
    )
    rows = []
    for policy, frame in frames.items():
        if policy.startswith("oracle_") or frame.empty:
            continue
        merged = frame.merge(oracle_slim, on=keys, how="inner")
        if merged.empty:
            continue
        rows.append(
            {
                "policy": policy,
                "matched_trades": int(len(merged)),
                "same_candidate_rate": float((merged["candidate_id"] == merged["oracle_candidate_id"]).mean() * 100.0),
                "avg_abs_delta_gap": float((merged["actual_delta_abs"].astype(float) - merged["oracle_delta_abs"].astype(float)).abs().mean()),
                "selected_avg_delta": float(merged["actual_delta_abs"].astype(float).mean()),
                "oracle_avg_delta": float(merged["oracle_delta_abs"].astype(float).mean()),
                "pnl_capture_pct": float(merged["pnl_dollars"].astype(float).sum() / max(merged["oracle_pnl_dollars"].astype(float).sum(), 1e-9) * 100.0),
                "pnl_gap": float(merged["pnl_dollars"].astype(float).sum() - merged["oracle_pnl_dollars"].astype(float).sum()),
            }
        )
    return pd.DataFrame(rows)


def delta_distribution(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for policy, frame in frames.items():
        if frame.empty or "delta_target" not in frame:
            continue
        counts = frame["delta_target"].astype(float).round(2).value_counts().sort_index()
        total = float(counts.sum())
        for delta, count in counts.items():
            rows.append(
                {
                    "policy": policy,
                    "delta_target": float(delta),
                    "count": int(count),
                    "pct": float(count / total * 100.0) if total else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def learned_exit_delta(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    hard = frames.get("option_value_best_select_hard", pd.DataFrame())
    learned = frames.get("option_value_best_select_learned_exit_5m", pd.DataFrame())
    if hard.empty or learned.empty:
        return pd.DataFrame(), pd.DataFrame()
    keys = [c for c in ["signal_id", "candidate_id", "ticker", "date"] if c in hard.columns and c in learned.columns]
    merged = learned.merge(
        hard[keys + ["hold_minutes", "pnl_dollars", "exit_reason"]].rename(
            columns={
                "hold_minutes": "hard_hold_minutes",
                "pnl_dollars": "hard_pnl_dollars",
                "exit_reason": "hard_exit_reason",
            }
        ),
        on=keys,
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame(), pd.DataFrame()
    merged["hold_minutes_delta"] = merged["hold_minutes"].astype(float) - merged["hard_hold_minutes"].astype(float)
    merged["pnl_delta_vs_hard"] = merged["pnl_dollars"].astype(float) - merged["hard_pnl_dollars"].astype(float)
    rows = []
    for label, group in [("ALL", merged), *[(str(t), g) for t, g in merged.groupby("ticker", sort=True)]]:
        rows.append(
            {
                "ticker": label,
                "matched_trades": int(len(group)),
                "learned_exit_rate": float((group["exit_reason"].astype(str) == "learned_exit").mean() * 100.0),
                "avg_hold_delta": float(group["hold_minutes_delta"].mean()),
                "pnl_delta_vs_hard": float(group["pnl_delta_vs_hard"].sum()),
                "avg_pnl_delta_vs_hard": float(group["pnl_delta_vs_hard"].mean()),
            }
        )
    reason_rows = (
        merged.groupby(["ticker", "exit_reason"], sort=True)
        .size()
        .reset_index(name="count")
        .sort_values(["ticker", "count"], ascending=[True, False])
    )
    return pd.DataFrame(rows), reason_rows


def write_markdown(
    output_dir: Path,
    source_dir: Path,
    overall: pd.DataFrame,
    per_ticker: pd.DataFrame,
    oracle_cmp: pd.DataFrame,
    delta_dist: pd.DataFrame,
    exit_cmp: pd.DataFrame,
) -> None:
    lines = [
        "# OptionValueJEPA Diagnostics",
        "",
        f"Source: `{source_dir}`",
        "",
        "## Overall Metrics",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in overall.iterrows():
        lines.append(
            f"| {row['policy']} | {int(row['trades'])} | {fmt_pct(row['win_rate'])} | "
            f"{fmt_num(row['profit_factor'])} | {fmt_money(row['pnl_dollars'])} | "
            f"{fmt_money(row['max_drawdown'])} | {fmt_num(row['avg_delta_abs'])} | "
            f"{fmt_num(row['avg_hold_minutes'], 1)} |"
        )

    lines += [
        "",
        "## Per Ticker",
        "",
        "| Policy | Ticker | Trades | WR | PF | PnL | Avg Delta | Avg Hold |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in per_ticker.iterrows():
        lines.append(
            f"| {row['policy']} | {row['ticker']} | {int(row['trades'])} | "
            f"{fmt_pct(row['win_rate'])} | {fmt_num(row['profit_factor'])} | "
            f"{fmt_money(row['pnl_dollars'])} | {fmt_num(row['avg_delta_abs'])} | "
            f"{fmt_num(row['avg_hold_minutes'], 1)} |"
        )

    lines += [
        "",
        "## Distance To Oracle Hard-Exit Delta",
        "",
        "| Policy | Matched | Same Candidate | Avg Delta Gap | Selected Avg Delta | Oracle Avg Delta | PnL Capture | PnL Gap |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in oracle_cmp.iterrows():
        lines.append(
            f"| {row['policy']} | {int(row['matched_trades'])} | {fmt_pct(row['same_candidate_rate'])} | "
            f"{fmt_num(row['avg_abs_delta_gap'])} | {fmt_num(row['selected_avg_delta'])} | "
            f"{fmt_num(row['oracle_avg_delta'])} | {fmt_pct(row['pnl_capture_pct'])} | {fmt_money(row['pnl_gap'])} |"
        )

    lines += [
        "",
        "## Delta Target Distribution",
        "",
        "| Policy | Delta | Count | Share |",
        "| --- | ---: | ---: | ---: |",
    ]
    for _, row in delta_dist.iterrows():
        lines.append(
            f"| {row['policy']} | {row['delta_target']:.2f} | {int(row['count'])} | {fmt_pct(row['pct'])} |"
        )

    if not exit_cmp.empty:
        lines += [
            "",
            "## Learned Exit Versus Hard Exit",
            "",
            "| Ticker | Matched | Learned Exit Rate | Avg Hold Delta | PnL Delta Vs Hard | Avg PnL Delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for _, row in exit_cmp.iterrows():
            lines.append(
                f"| {row['ticker']} | {int(row['matched_trades'])} | {fmt_pct(row['learned_exit_rate'])} | "
                f"{fmt_num(row['avg_hold_delta'], 1)} | {fmt_money(row['pnl_delta_vs_hard'])} | "
                f"{fmt_money(row['avg_pnl_delta_vs_hard'])} |"
            )

    lines += [
        "",
        "## Initial Interpretation",
        "",
        "- The learned `best` target over-selects low delta contracts, especially in QQQ/SPY.",
        "- The hard-exit oracle uses lower average delta than fixed 0.70, but it still keeps a large 0.70 allocation; the learned model moves too far toward cheap convexity.",
        "- The learned 5m exit reduces average hold time, but currently destroys more PnL than it saves. It should not be attached to the promoted GBT+JEPA 180m model until a separate OOS exit gate passes.",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose OptionValueJEPA policy results.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--policies", nargs="*", default=DEFAULT_POLICIES)
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir) if args.output_dir else result_dir / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = {policy: load_policy(result_dir, policy) for policy in args.policies}
    frames = {policy: frame for policy, frame in frames.items() if not frame.empty}
    if not frames:
        raise RuntimeError(f"No policy trade files found in {result_dir}")

    overall, per_ticker = build_metrics_tables(frames)
    oracle_cmp = compare_to_oracle(frames)
    delta_dist = delta_distribution(frames)
    exit_cmp, exit_reasons = learned_exit_delta(frames)

    overall.to_csv(output_dir / "overall_metrics.csv", index=False)
    per_ticker.to_csv(output_dir / "per_ticker_metrics.csv", index=False)
    oracle_cmp.to_csv(output_dir / "oracle_distance.csv", index=False)
    delta_dist.to_csv(output_dir / "delta_distribution.csv", index=False)
    exit_cmp.to_csv(output_dir / "learned_exit_vs_hard.csv", index=False)
    exit_reasons.to_csv(output_dir / "learned_exit_reasons.csv", index=False)
    write_markdown(output_dir, result_dir, overall, per_ticker, oracle_cmp, delta_dist, exit_cmp)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
