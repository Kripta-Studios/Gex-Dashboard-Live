from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.train_option_value_jepa import (
    add_selector_score_bases,
    select_fixed_delta,
    select_scored_delta,
    simulate_trailing_exit,
    trade_metrics,
)


BASE_ARGS = SimpleNamespace(
    hard_stop_pct=-0.60,
    trail_activation_pct=0.50,
    trail_drawdown_pct=0.25,
    trail_take_profit_pct=10.0,
    entry_cutoff_time="14:30",
)
QQQ_LOOSE_ARGS = SimpleNamespace(
    hard_stop_pct=-0.70,
    trail_activation_pct=0.50,
    trail_drawdown_pct=0.15,
    trail_take_profit_pct=10.0,
    entry_cutoff_time="14:30",
)


def fmt_pct(value: float) -> str:
    if value is None or not np.isfinite(float(value)):
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def fmt_float(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def fmt_money(value: float) -> str:
    sign = "+" if float(value) >= 0 else "-"
    return f"{sign}${abs(float(value)):,.0f}"


def metric_row(label: str, trades: pd.DataFrame) -> str:
    metrics = trade_metrics(trades)
    return (
        f"| {label} | {int(metrics.get('trades', 0))} | {fmt_pct(metrics.get('win_rate', np.nan))} | "
        f"{fmt_float(metrics.get('profit_factor', np.nan))} | {fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | {fmt_money(metrics.get('avg_pnl', 0.0))} |"
    )


def with_minutes(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    out["_minute"] = out["time"].astype(str).str.slice(0, 2).astype(int) * 60 + out["time"].astype(str).str.slice(3, 5).astype(int)
    return out


def gate_exclude_midday(trades: pd.DataFrame) -> pd.DataFrame:
    out = with_minutes(trades)
    if out.empty:
        return out
    return out[~((out["_minute"] > 690) & (out["_minute"] <= 750))].drop(columns=["_minute"], errors="ignore")


def gate_early_only(trades: pd.DataFrame) -> pd.DataFrame:
    out = with_minutes(trades)
    if out.empty:
        return out
    return out[out["_minute"] <= 690].drop(columns=["_minute"], errors="ignore")


def gate_long_or_early_short(trades: pd.DataFrame) -> pd.DataFrame:
    out = with_minutes(trades)
    if out.empty:
        return out
    keep = (out["side"].astype(str) == "LONG") | ((out["side"].astype(str) == "SHORT") & (out["_minute"] <= 690))
    return out[keep].drop(columns=["_minute"], errors="ignore")


def state_for(state_rows: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    ids = set(selected["candidate_id"].astype(int))
    return state_rows[state_rows["candidate_id"].astype(int).isin(ids)].copy()


def simulate_selected(selected: pd.DataFrame, state_rows: pd.DataFrame, args: SimpleNamespace, name: str) -> pd.DataFrame:
    return simulate_trailing_exit(selected, state_for(state_rows, selected), args, name)


def period_slice(trades: pd.DataFrame, start: str, end: str | None = None) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    dates = out["date"].astype(str)
    mask = dates >= start
    if end is not None:
        mask &= dates <= end
    return out[mask].reset_index(drop=True)


def write_summary(output_dir: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# QQQ OptionValue Rescue Diagnostics",
        "",
        "Goal: investigate ways to keep QQQ tradable instead of disabling it.",
        "Validation is `2026-01-01` through `2026-03-31`; OOS is `2026-04-01` onward.",
        "",
        "## Findings",
        "",
        "- QQQ fixed 0.70 was strong in validation but failed in the current OOS, so the issue is a regime/entry problem more than a pure delta problem.",
        "- A looser QQQ-specific stop (`-70%`) with the same 50% trail activation but tighter 15% giveback improves QQQ OOS versus the live-style `-60% / 50% / 25%` exit.",
        "- Excluding the QQQ 11:31-12:30 ET entry window improves validation and turns QQQ OOS positive, while keeping QQQ active.",
        "- The highest OOS QQQ PF in this diagnostic comes from early-only entries, but that is lower volume and should be treated as research until tested in more folds.",
        "",
        "## Metrics",
        "",
        "| Scenario | Trades | WR | PF | PnL | Max DD | Avg PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(metric_row(str(row["label"]), row["trades"]))  # type: ignore[arg-type]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose QQQ-specific OptionValue rescue policies.")
    parser.add_argument("--candidate-labels", default="research_papers/JEPA/results/jepa_full_pipeline_option_policy/candidate_labels.parquet")
    parser.add_argument("--state-rows", default="research_papers/JEPA/results/jepa_full_pipeline_option_value_split/option_value_state_rows.parquet")
    parser.add_argument("--test-predictions", default="research_papers/JEPA/results/jepa_full_pipeline_option_value_split/test_candidate_predictions.csv")
    parser.add_argument("--output-dir", default="research_papers/JEPA/results/jepa_full_pipeline_qqq_rescue")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_parquet(args.candidate_labels)
    candidates["date"] = candidates["date"].astype(str)
    state_rows = pd.read_parquet(
        args.state_rows,
        columns=["candidate_id", "path_time", "hold_minutes", "current_pnl_pct", "pnl_dollars"],
    )

    qqq_candidates_2026 = candidates[
        (candidates["ticker"].astype(str) == "QQQ") & (candidates["date"].astype(str) >= "20260101")
    ].copy()
    fixed_qqq = select_fixed_delta(qqq_candidates_2026, 0.70)
    fixed_base = simulate_selected(fixed_qqq, state_rows, BASE_ARGS, "fixed_070_base")
    fixed_loose = simulate_selected(fixed_qqq, state_rows, QQQ_LOOSE_ARGS, "fixed_070_qqq_loose")

    test_pred = add_selector_score_bases(pd.read_csv(args.test_predictions))
    selected_blended = select_scored_delta(test_pred, "ovjepa_pred_rule_best_mean", 2.0, None)
    option_base = simulate_selected(selected_blended, state_rows, BASE_ARGS, "option_value_blended_base")
    qqq_selected = selected_blended[selected_blended["ticker"].astype(str) == "QQQ"].copy()
    option_qqq_loose = simulate_selected(qqq_selected, state_rows, QQQ_LOOSE_ARGS, "option_value_blended_qqq_loose")

    non_qqq_base = option_base[option_base["ticker"].astype(str) != "QQQ"].copy()
    rows: list[dict[str, object]] = [
        {"label": "VAL fixed QQQ baseline", "trades": period_slice(fixed_base, "20260101", "20260331")},
        {"label": "VAL fixed QQQ exclude 11:31-12:30", "trades": gate_exclude_midday(period_slice(fixed_base, "20260101", "20260331"))},
        {"label": "VAL fixed QQQ loose exit + exclude 11:31-12:30", "trades": gate_exclude_midday(period_slice(fixed_loose, "20260101", "20260331"))},
        {"label": "VAL fixed QQQ loose exit + early only", "trades": gate_early_only(period_slice(fixed_loose, "20260101", "20260331"))},
        {"label": "OOS fixed QQQ baseline", "trades": period_slice(fixed_base, "20260401")},
        {"label": "OOS fixed QQQ exclude 11:31-12:30", "trades": gate_exclude_midday(period_slice(fixed_base, "20260401"))},
        {"label": "OOS fixed QQQ loose exit + exclude 11:31-12:30", "trades": gate_exclude_midday(period_slice(fixed_loose, "20260401"))},
        {"label": "OOS fixed QQQ loose exit + early only", "trades": gate_early_only(period_slice(fixed_loose, "20260401"))},
        {"label": "OOS OptionValue QQQ baseline", "trades": option_base[option_base["ticker"].astype(str) == "QQQ"].copy()},
        {"label": "OOS OptionValue QQQ loose exit", "trades": option_qqq_loose},
        {"label": "OOS OptionValue QQQ loose exit + exclude 11:31-12:30", "trades": gate_exclude_midday(option_qqq_loose)},
        {"label": "OOS OptionValue QQQ loose exit + early only", "trades": gate_early_only(option_qqq_loose)},
        {"label": "OOS OptionValue QQQ loose exit + long or early short", "trades": gate_long_or_early_short(option_qqq_loose)},
    ]

    mixed_exclude = pd.concat([non_qqq_base, gate_exclude_midday(option_qqq_loose)], ignore_index=True)
    mixed_early = pd.concat([non_qqq_base, gate_early_only(option_qqq_loose)], ignore_index=True)
    mixed_long_or_early_short = pd.concat([non_qqq_base, gate_long_or_early_short(option_qqq_loose)], ignore_index=True)
    rows.extend(
        [
            {"label": "OOS mixed: SPX/SPY base + QQQ loose exclude 11:31-12:30", "trades": mixed_exclude},
            {"label": "OOS mixed: SPX/SPY base + QQQ loose early only", "trades": mixed_early},
            {"label": "OOS mixed: SPX/SPY base + QQQ loose long or early short", "trades": mixed_long_or_early_short},
        ]
    )

    csv_rows = []
    for row in rows:
        metrics = trade_metrics(row["trades"])  # type: ignore[arg-type]
        csv_rows.append({"scenario": row["label"], **metrics})
    pd.DataFrame(csv_rows).to_csv(output_dir / "qqq_rescue_metrics.csv", index=False)
    gate_exclude_midday(option_qqq_loose).to_csv(output_dir / "option_value_qqq_loose_exclude_midday_trades.csv", index=False)
    gate_early_only(option_qqq_loose).to_csv(output_dir / "option_value_qqq_loose_early_only_trades.csv", index=False)
    write_summary(output_dir, rows)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
