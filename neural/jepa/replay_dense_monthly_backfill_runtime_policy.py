from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apply_event_monthly_volume_backfill import (
    is_partial_month,
    load_trades,
    required_count_by_date,
    target_count_for_month,
)
from bots.tradingbot_wrapper_jepa import JepaFixedDeltaBot
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"empty config: {path}")
    return frame.iloc[0].to_dict()


def _args_from_config(cfg: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        primary_name=str(cfg["primary_name"]),
        fallback_name=str(cfg["fallback_name"]),
        start_month=str(cfg["start_month"]),
        end_month=str(cfg["end_month"]),
        min_month_trades=int(cfg["min_month_trades"]),
        auto_partial_month_target=_as_bool(cfg.get("auto_partial_month_target", False)),
        partial_month_observed_floor=int(cfg.get("partial_month_observed_floor", 0)),
        backfill_only_partial_months=_as_bool(cfg.get("backfill_only_partial_months", False)),
        max_day=int(cfg["max_day"]),
        cooldown_minutes=int(cfg["cooldown_minutes"]),
        min_entry_minute=int(cfg.get("min_entry_minute", 0)),
        risk_capital=float(cfg.get("risk_capital", 5000.0)),
    )


def _event_candidate_id(row: pd.Series) -> str:
    return "|".join(
        [
            str(row.get("policy_ticker", row.get("ticker", ""))).upper(),
            str(row.get("date", "")),
            str(row.get("time", "")),
            str(row.get("expiry_mode", "")),
            str(row.get("action", "")).upper(),
        ]
    )


def _bot_for_replay() -> JepaFixedDeltaBot:
    bot = object.__new__(JepaFixedDeltaBot)
    bot.event_option_state = {"entries": [], "candidate_ids": []}
    bot.event_option_policy = {}
    bot.event_option_components = None
    bot.trade_log_path = Path("__dense_monthly_backfill_runtime_replay_no_trade_log__.csv")
    return bot


def _record_entry(bot: JepaFixedDeltaBot, row: pd.Series, now: datetime) -> None:
    entries = bot.event_option_state.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    entries.append(
        {
            "entry_time": now.isoformat(),
            "date": str(row.get("date", "")),
            "time": str(row.get("time", "")),
            "policy_ticker": str(row.get("policy_ticker", row.get("ticker", ""))).upper(),
            "event_candidate_id": str(row.get("event_candidate_id", "")),
            "monthly_backfill_role": str(row.get("monthly_backfill_role", "")),
            "source_stream": str(row.get("source_stream", "")),
            "expiry_mode": str(row.get("expiry_mode", "")),
            "action": str(row.get("action", "")).upper(),
        }
    )
    ids = bot.event_option_state.get("candidate_ids", [])
    if not isinstance(ids, list):
        ids = []
    candidate_id = str(row.get("event_candidate_id", ""))
    if candidate_id:
        ids.append(candidate_id)
    bot.event_option_state["entries"] = entries
    bot.event_option_state["candidate_ids"] = ids


def _candidate_time(row: pd.Series) -> datetime:
    date_value = str(row.get("date", ""))
    time_value = str(row.get("time", "09:30"))[:5]
    return datetime.strptime(f"{date_value} {time_value}", "%Y%m%d %H:%M")


def _prepare_streams(cfg: dict[str, Any], args: SimpleNamespace) -> tuple[pd.DataFrame, str]:
    primary = load_trades(Path(str(cfg["primary_trades"])), str(cfg["primary_name"]))
    fallback = load_trades(Path(str(cfg["fallback_trades"])), str(cfg["fallback_name"]))
    ticker = str(cfg.get("ticker", "")).upper()
    if ticker:
        primary = primary[primary["ticker"].astype(str).str.upper().eq(ticker)].copy()
        fallback = fallback[fallback["ticker"].astype(str).str.upper().eq(ticker)].copy()
    months = set(month_range(str(args.start_month), str(args.end_month)))
    primary = primary[primary["month"].astype(str).isin(months)].copy()
    fallback = fallback[fallback["month"].astype(str).isin(months)].copy()
    combined = pd.concat([primary, fallback], ignore_index=True, sort=False)
    if combined.empty:
        return combined, ticker
    combined["_priority"] = np.where(combined["source_stream"].astype(str).eq(str(args.primary_name)), 0, 1)
    combined = combined.sort_values(
        ["ticker", "month", "date", "entry_minute", "_priority", "score", "_source_order"],
        ascending=[True, True, True, True, True, False, True],
        kind="stable",
    ).reset_index(drop=True)
    return combined, ticker


def replay_config(config_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    cfg = _read_config(config_path)
    args = _args_from_config(cfg)
    combined, ticker = _prepare_streams(cfg, args)
    bot = _bot_for_replay()
    frames: list[pd.Series] = []
    months = month_range(str(args.start_month), str(args.end_month))

    for month in months:
        work = combined[combined["month"].astype(str).eq(str(month))].copy()
        if work.empty:
            continue
        target = target_count_for_month(str(month), work["date"], args)
        partial_month = is_partial_month(str(month), work["date"])
        for _, raw in work.iterrows():
            row = raw.copy()
            is_primary = str(row["source_stream"]) == str(args.primary_name)
            date_value = str(row["date"])
            selected_count = bot._event_monthly_entry_count(str(row["ticker"]).upper(), str(month))
            required = required_count_by_date(str(month), date_value, target)
            row["policy_ticker"] = str(row["ticker"]).upper()
            row["bot_ticker"] = "SPX" if str(row["ticker"]).upper() == "SPXW" else str(row["ticker"]).upper()
            row["policy_max_day"] = int(args.max_day)
            row["policy_cooldown_minutes"] = int(args.cooldown_minutes)
            row["monthly_backfill_role"] = "primary" if is_primary else "fallback"
            row["backfill_min_month_trades"] = int(target)
            row["event_candidate_id"] = _event_candidate_id(row)
            row["backfill_required_count"] = int(required)
            row["backfill_count_before"] = int(selected_count)
            row["backfill_month_target"] = int(target)
            row["backfill_partial_month"] = bool(partial_month)
            row["backfill_mode"] = "primary" if is_primary else "fallback_volume_pace"
            if bool(args.backfill_only_partial_months) and not partial_month and not is_primary:
                continue
            now = _candidate_time(row)
            allowed, reason = bot._event_candidate_allowed(row, now)
            if not allowed:
                continue
            row["runtime_allow_reason"] = reason
            frames.append(row)
            _record_entry(bot, row, now)

    out = pd.DataFrame(frames) if frames else combined.iloc[0:0].copy()
    if not out.empty:
        out = out.sort_values(["date", "entry_minute", "ticker", "source_stream"], kind="stable").reset_index(drop=True)
    summary = {
        "config": str(config_path),
        "ticker": ticker,
        "rows": int(len(out)),
        "state_entries": int(len(bot.event_option_state.get("entries", []))),
    }
    return out, summary


def canonical(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in ["ticker", "date", "time", "action", "expiry_mode"]:
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].astype(str)
    out["ticker"] = out["ticker"].str.upper()
    out["action"] = out["action"].str.upper()
    if "entry_minute" not in out.columns:
        parsed = pd.to_datetime(out["time"].str[:5], format="%H:%M", errors="coerce")
        out["entry_minute"] = parsed.dt.hour * 60 + parsed.dt.minute
    out["entry_minute"] = pd.to_numeric(out["entry_minute"], errors="coerce").fillna(0).astype(int)
    out = out.sort_values(["ticker", "date", "entry_minute", "time", "action", "expiry_mode"], kind="stable").reset_index(drop=True)
    key_cols = ["ticker", "date", "time", "action", "expiry_mode"]
    out["_key_occurrence"] = out.groupby(key_cols, sort=False).cumcount()
    return out


def compare(name: str, actual: pd.DataFrame, expected: pd.DataFrame) -> dict[str, Any]:
    a = canonical(actual)
    e = canonical(expected)
    key_cols = ["ticker", "date", "time", "action", "expiry_mode", "_key_occurrence"]
    a_keys = a[key_cols].astype(str).agg("|".join, axis=1)
    e_keys = e[key_cols].astype(str).agg("|".join, axis=1)
    missing = sorted(set(e_keys).difference(set(a_keys)))
    extra = sorted(set(a_keys).difference(set(e_keys)))
    merged = e.assign(_cmp_key=e_keys).merge(
        a.assign(_cmp_key=a_keys),
        on="_cmp_key",
        how="inner",
        suffixes=("_expected", "_actual"),
    )
    diffs: dict[str, float] = {}
    for col in ["realized_return", "score", "backfill_count_before", "backfill_required_count"]:
        left = f"{col}_expected"
        right = f"{col}_actual"
        if left in merged.columns and right in merged.columns:
            diff = (
                pd.to_numeric(merged[left], errors="coerce").fillna(0.0)
                - pd.to_numeric(merged[right], errors="coerce").fillna(0.0)
            ).abs()
            diffs[f"max_abs_{col}_diff"] = float(diff.max()) if not diff.empty else 0.0
    passed = (
        int(len(a)) == int(len(e))
        and not missing
        and not extra
        and all(value <= 1e-9 for value in diffs.values())
    )
    return {
        "name": name,
        "passed": bool(passed),
        "actual_rows": int(len(a)),
        "expected_rows": int(len(e)),
        "matched_rows": int(len(merged)),
        "missing_rows": int(len(missing)),
        "extra_rows": int(len(extra)),
        **diffs,
        "missing_preview": missing[:10],
        "extra_preview": extra[:10],
    }


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Monthly Backfill Runtime Replay",
        "",
        "This replay feeds the historical OOS primary/fallback trade streams through the bot's stateful event-option gating logic. It verifies monthly volume pacing, per-day max, cooldown, and candidate de-duplication without fitting or scoring any model.",
        "",
        f"- Passed: {payload['passed']}",
        f"- Combined rows: {payload['overall']['trades']}",
        f"- WR: {payload['overall']['win_rate']:.2%}",
        f"- PF: {payload['overall']['profit_factor']:.3f}",
        f"- PnL return: {payload['overall']['pnl_return']:.3f}R",
        "",
        "## Comparisons",
        "",
        "| Name | Passed | Actual | Expected | Matched | Missing | Extra |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["comparisons"]:
        lines.append(
            f"| {row['name']} | {row['passed']} | {row['actual_rows']} | {row['expected_rows']} | "
            f"{row['matched_rows']} | {row['missing_rows']} | {row['extra_rows']} |"
        )
    lines += [
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(payload["by_ticker"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay dense monthly-backfill event-option policy through bot state gates.")
    parser.add_argument("--config", action="append", required=True, help="monthly_volume_backfill_config.csv")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="")
    parser.add_argument("--end-month", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    replayed_parts: list[pd.DataFrame] = []
    expected_parts: list[pd.DataFrame] = []
    comparisons: list[dict[str, Any]] = []
    replay_summaries: list[dict[str, Any]] = []

    for raw_config in args.config:
        config_path = Path(raw_config)
        cfg = _read_config(config_path)
        replayed, replay_summary = replay_config(config_path)
        expected_path = Path(str(cfg["output_dir"])) / "monthly_volume_backfill_trades.csv"
        expected = pd.read_csv(expected_path, dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str})
        if args.start_month or args.end_month:
            start = str(args.start_month or cfg["start_month"])
            end = str(args.end_month or cfg["end_month"])
            months = set(month_range(start, end))
            replayed = replayed[replayed["month"].astype(str).isin(months)].copy()
            expected = expected[expected["month"].astype(str).isin(months)].copy()
        ticker = str(cfg.get("ticker", Path(raw_config).parent.name)).upper()
        replayed.to_csv(output_dir / f"runtime_replayed_{ticker.lower()}_trades.csv", index=False)
        comparisons.append(compare(ticker, replayed, expected))
        replay_summaries.append(replay_summary)
        replayed_parts.append(replayed)
        expected_parts.append(expected)

    combined = pd.concat(replayed_parts, ignore_index=True, sort=False) if replayed_parts else pd.DataFrame()
    combined_expected = pd.concat(expected_parts, ignore_index=True, sort=False) if expected_parts else pd.DataFrame()
    combined.to_csv(output_dir / "runtime_replayed_combined_trades.csv", index=False)
    comparisons.append(compare("COMBINED", combined, combined_expected))

    if args.start_month or args.end_month:
        months = month_range(str(args.start_month or combined["month"].min()), str(args.end_month or combined["month"].max()))
    else:
        months = sorted(combined["month"].astype(str).unique().tolist()) if not combined.empty else []
    overall = metrics(combined, months)
    by_ticker = {
        ticker: metrics(part, months)
        for ticker, part in combined.groupby("ticker", sort=True)
    } if not combined.empty else {}
    payload = {
        "schema_version": 1,
        "replay": "dense_monthly_backfill_runtime_policy",
        "passed": bool(all(row["passed"] for row in comparisons)),
        "output_dir": str(output_dir),
        "configs": [str(Path(item)) for item in args.config],
        "months": months,
        "overall": overall,
        "by_ticker": by_ticker,
        "comparisons": comparisons,
        "replay_summaries": replay_summaries,
        "runtime_equivalence_scope": "stream-level bot state gates: monthly fallback pace, per-day max, cooldown, candidate de-duplication",
        "not_covered": [
            "ThetaData live snapshot construction",
            "future 202607+ deploy-model prediction quality",
            "broker/order execution fills",
        ],
    }
    (output_dir / "runtime_policy_replay_summary.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
