from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from apply_event_monthly_volume_backfill import (
    derive_minute,
    is_partial_month,
    load_trades,
    required_count_by_date,
    target_count_for_month,
)
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FROZEN_RESULT_DIR = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "_diagnostics"
    / "frozen_source_selector_dense15_pre2025_static_202501_202604_v1"
    / "combined"
)
DEFAULT_OUTPUT_DIR = DEFAULT_FROZEN_RESULT_DIR.parent / "runtime_replay_monthly_backfill18"


@dataclass(frozen=True)
class TickerStreams:
    primary: Path
    fallback: Path


def ticker_streams(ticker: str) -> TickerStreams:
    key = ticker.lower()
    primary_variant = "win_valthr_strict_d25" if ticker.upper() == "SPY" else "win_valthr_wr45_d25"
    return TickerStreams(
        primary=(
            PROJECT_ROOT
            / "research_papers"
            / "JEPA"
            / "results"
            / f"event_option_gate_dense15_zero_dte_{primary_variant}_physctx_2023_2026_{key}_v1"
            / "event_option_gate_trades.csv"
        ),
        fallback=(
            PROJECT_ROOT
            / "research_papers"
            / "JEPA"
            / "results"
            / f"event_option_gate_dense15_zero_dte_return_forcedmax3_d50_physctx_2023_2026_{key}_v1"
            / "event_option_gate_trades.csv"
        ),
    )


def normalize_expected(df: pd.DataFrame, months: list[str], tickers: list[str]) -> pd.DataFrame:
    work = df.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    work["month"] = work["month"].astype(str)
    work = work[work["month"].isin(months) & work["ticker"].isin(tickers)].copy()
    if "entry_minute" not in work.columns:
        work["entry_minute"] = derive_minute(work)
    for col in ("date", "time", "action", "expiry_mode", "backfill_mode"):
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].astype(str)
    return work.sort_values(["date", "entry_minute", "ticker", "backfill_mode"], kind="stable").reset_index(drop=True)


def replay_ticker_month(candidates: pd.DataFrame, month: str, args: argparse.Namespace) -> pd.DataFrame:
    combined = candidates[candidates["month"].astype(str).eq(str(month))].copy()
    if combined.empty:
        return pd.DataFrame()

    target = target_count_for_month(month, combined["date"], args)
    partial_month = is_partial_month(month, combined["date"])
    combined["_priority"] = np.where(combined["source_stream"].astype(str).eq(str(args.primary_name)), 0, 1)
    combined["monthly_backfill_role"] = np.where(combined["_priority"].eq(0), "primary", "fallback")
    combined["backfill_min_month_trades"] = int(target)
    combined = combined.sort_values(
        ["date", "entry_minute", "_priority", "score", "_source_order"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )

    selected: list[pd.Series] = []
    selected_keys: set[tuple[str, str, str, str]] = set()
    selected_count = 0
    day_counts: dict[str, int] = {}
    next_allowed_by_day: dict[str, int] = {}

    for _, row in combined.iterrows():
        date = str(row["date"])
        time = str(row["time"])
        action = str(row["action"])
        expiry_mode = str(row.get("expiry_mode", ""))
        key = (date, time, action, expiry_mode)
        if key in selected_keys:
            continue

        day_taken = int(day_counts.get(date, 0))
        if day_taken >= int(args.max_day):
            continue

        minute = int(row["entry_minute"])
        if minute < int(next_allowed_by_day.get(date, -1)):
            continue

        role = str(row["monthly_backfill_role"])
        required = required_count_by_date(str(month), date, target)
        if role == "fallback" and selected_count >= required:
            continue

        out = row.copy()
        out["backfill_required_count"] = required
        out["backfill_count_before"] = selected_count
        out["backfill_month_target"] = target
        out["backfill_partial_month"] = partial_month
        out["backfill_mode"] = "primary" if role == "primary" else "fallback_volume_pace"
        out["runtime_replay_role"] = role
        selected.append(out)

        selected_keys.add(key)
        selected_count += 1
        day_counts[date] = day_taken + 1
        next_allowed_by_day[date] = minute + int(args.cooldown_minutes)

    return pd.DataFrame(selected) if selected else pd.DataFrame()


def replay_runtime_policy(args: argparse.Namespace) -> pd.DataFrame:
    months = month_range(str(args.start_month), str(args.end_month))
    frames: list[pd.DataFrame] = []
    for ticker in args.tickers:
        paths = ticker_streams(ticker)
        primary = load_trades(paths.primary, str(args.primary_name))
        fallback = load_trades(paths.fallback, str(args.fallback_name))
        candidates = pd.concat([primary, fallback], ignore_index=True, sort=False)
        candidates = candidates[candidates["ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
        for month in months:
            out = replay_ticker_month(candidates, month, args)
            if not out.empty:
                frames.append(out)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    return out.sort_values(["date", "entry_minute", "ticker", "backfill_mode"], kind="stable").reset_index(drop=True)


def key_counter(df: pd.DataFrame) -> Counter[str]:
    if df.empty:
        return Counter()
    cols = ["ticker", "date", "time", "action", "expiry_mode", "backfill_mode"]
    work = df.copy()
    for col in cols:
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].astype(str)
    return Counter("|".join(row) for row in work[cols].itertuples(index=False, name=None))


def compare_frames(expected: pd.DataFrame, replayed: pd.DataFrame) -> dict[str, Any]:
    expected_counter = key_counter(expected)
    replayed_counter = key_counter(replayed)
    missing = list((expected_counter - replayed_counter).elements())
    extra = list((replayed_counter - expected_counter).elements())
    by_ticker: dict[str, Any] = {}
    for ticker in sorted(set(expected["ticker"].astype(str).str.upper()) | set(replayed["ticker"].astype(str).str.upper())):
        exp_t = expected[expected["ticker"].astype(str).str.upper().eq(ticker)]
        rep_t = replayed[replayed["ticker"].astype(str).str.upper().eq(ticker)]
        missing_t = list((key_counter(exp_t) - key_counter(rep_t)).elements())
        extra_t = list((key_counter(rep_t) - key_counter(exp_t)).elements())
        by_ticker[ticker] = {
            "expected_rows": int(len(exp_t)),
            "replayed_rows": int(len(rep_t)),
            "missing_count": int(len(missing_t)),
            "extra_count": int(len(extra_t)),
            "passed": not missing_t and not extra_t,
        }
    return {
        "passed": not missing and not extra,
        "expected_rows": int(len(expected)),
        "replayed_rows": int(len(replayed)),
        "missing_count": int(len(missing)),
        "extra_count": int(len(extra)),
        "missing_examples": missing[:20],
        "extra_examples": extra[:20],
        "by_ticker": by_ticker,
    }


def write_summary(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Frozen Pre-2025 Monthly Backfill Runtime Replay",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Months: `{payload['start_month']}`-`{payload['end_month']}`",
        f"- Expected rows: `{payload['comparison']['expected_rows']}`",
        f"- Replayed rows: `{payload['comparison']['replayed_rows']}`",
        f"- Missing keys: `{payload['comparison']['missing_count']}`",
        f"- Extra keys: `{payload['comparison']['extra_count']}`",
        "",
        "## Scope",
        "",
        "This replay validates the deterministic monthly_backfill18 runtime state machine using the same causal primary/fallback candidate streams selected by the frozen pre-2025 research manifest. It is a policy-equivalence check, not new performance evidence and not broker-fill evidence.",
        "",
        "## By Ticker",
        "",
        "| Ticker | Expected | Replayed | Missing | Extra | Passed |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, row in sorted(payload["comparison"]["by_ticker"].items()):
        lines.append(
            f"| {ticker} | {row['expected_rows']} | {row['replayed_rows']} | {row['missing_count']} | {row['extra_count']} | {str(row['passed']).lower()} |"
        )
    lines.append("")
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay the frozen pre-2025 monthly_backfill18 policy with bot-like state and compare to frozen OOS selections."
    )
    parser.add_argument("--frozen-result-dir", default=str(DEFAULT_FROZEN_RESULT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--start-month", default="202501")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--primary-name", default="win_valthr_wr45_d25")
    parser.add_argument("--fallback-name", default="forcedmax3_d50")
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--max-day", type=int, default=3)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--auto-partial-month-target", action="store_true")
    parser.add_argument("--partial-month-observed-floor", type=int, default=0)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    months = month_range(str(args.start_month), str(args.end_month))
    tickers = [str(t).upper() for t in args.tickers]
    result_dir = Path(args.frozen_result_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_path = result_dir / "combined_trades.csv"
    expected = normalize_expected(pd.read_csv(expected_path, dtype={"date": str, "month": str, "time": str}), months, tickers)
    replayed = replay_runtime_policy(args)
    replayed = normalize_expected(replayed, months, tickers)
    comparison = compare_frames(expected, replayed)

    replayed.to_csv(output_dir / "runtime_replay_trades.csv", index=False)
    comparison_df = pd.DataFrame(
        [
            {"ticker": ticker, **row}
            for ticker, row in sorted(comparison["by_ticker"].items())
        ]
    )
    comparison_df.to_csv(output_dir / "runtime_replay_comparison_by_ticker.csv", index=False)

    payload = {
        "schema_version": 1,
        "check": "frozen_pre2025_monthly_backfill18_runtime_policy_replay",
        "passed": bool(comparison["passed"]),
        "start_month": str(args.start_month),
        "end_month": str(args.end_month),
        "tickers": tickers,
        "candidate_streams": {
            ticker: {
                "primary": str(ticker_streams(ticker).primary.relative_to(PROJECT_ROOT)),
                "fallback": str(ticker_streams(ticker).fallback.relative_to(PROJECT_ROOT)),
            }
            for ticker in tickers
        },
        "expected_trades": str(expected_path.relative_to(PROJECT_ROOT)),
        "output_trades": str((output_dir / "runtime_replay_trades.csv").relative_to(PROJECT_ROOT)),
        "policy_parameters": {
            "primary_name": str(args.primary_name),
            "fallback_name": str(args.fallback_name),
            "min_month_trades": int(args.min_month_trades),
            "max_day": int(args.max_day),
            "cooldown_minutes": int(args.cooldown_minutes),
        },
        "comparison": comparison,
        "metrics": {
            "overall": metrics(replayed, months),
            "by_ticker": {ticker: metrics(part, months) for ticker, part in replayed.groupby("ticker", sort=True)}
            if not replayed.empty
            else {},
        },
        "scope_note": (
            "This is a deterministic runtime-policy replay using historical causal candidate streams. "
            "It does not use the 202607 deploy scorer to recreate historical fold scores, and it does not "
            "constitute paper/broker fill evidence."
        ),
    }
    (output_dir / "runtime_replay_summary.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, payload)
    print(json.dumps({"passed": payload["passed"], "comparison": comparison}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
