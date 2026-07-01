from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bots.tradingbot_wrapper_jepa import JepaFixedDeltaBot


DEFAULT_OUTPUT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/"
    "bot_event_daily_loss_guard_validation"
)


def write_trade_log(path: Path) -> None:
    rows = []
    for idx, date in enumerate(["20260518", "20260519", "20260520", "20260521"], start=1):
        rows.append(
            {
                "date": date,
                "entry_time": "14:30",
                "exit_time": "15:00",
                "ticker": "SPY",
                "direction": "SHORT",
                "right": "PUT",
                "strike": 755.0 + idx,
                "delta": -0.25,
                "entry_premium": 1.0,
                "exit_premium": 0.7,
                "contracts": 10,
                "pnl_pct": -0.3,
                "pnl_dollars": -1500.0,
                "hold_minutes": 30,
                "exit_reason": "test_loss",
                "peak_pnl_pct": 0.0,
                "trough_pnl_pct": -0.3,
                "option_snapshot_suffix": "0dte",
                "exit_contract": "event_option_tp50_sl30_max180",
                "source_model": "event_option:SPY:base:win_valthr_strict_d25:zero_dte:d25:SPY_DENSE15_BACKFILL18",
            }
        )
    rows.append(
        {
            "date": "20260521",
            "entry_time": "14:30",
            "exit_time": "15:00",
            "ticker": "SPX",
            "direction": "LONG",
            "right": "CALL",
            "strike": 6000.0,
            "delta": 0.25,
            "entry_premium": 1.0,
            "exit_premium": 1.5,
            "contracts": 10,
            "pnl_pct": 0.5,
            "pnl_dollars": 2500.0,
            "hold_minutes": 30,
            "exit_reason": "other_ticker",
            "peak_pnl_pct": 0.5,
            "trough_pnl_pct": 0.0,
            "option_snapshot_suffix": "0dte",
            "exit_contract": "event_option_tp50_sl30_max180",
            "source_model": "event_option:SPXW:base:win_valthr_strict_d25:zero_dte:d25:SPXW_DENSE15_BACKFILL18",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Bot Event Daily Loss Guard Validation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Output: `{payload['output_dir']}`",
        "",
        "This validates bot runtime gating only. It does not submit broker orders.",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], indent=2, allow_nan=True),
        "```",
    ]
    if payload["issues"]:
        lines += ["", "## Issues", "", *[f"- {issue}" for issue in payload["issues"]]]
    (output_dir / "BOT_EVENT_DAILY_LOSS_GUARD_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bot runtime daily loss-streak guard behavior.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trade_log_path = output_dir / "trades_jepa.csv"
    state_path = output_dir / "event_option_runtime_state.json"
    write_trade_log(trade_log_path)
    if state_path.exists():
        state_path.unlink()

    bot = JepaFixedDeltaBot.__new__(JepaFixedDeltaBot)
    bot.trades_dir = output_dir
    bot.trade_log_path = trade_log_path
    bot.event_option_state_path = state_path
    bot.event_option_state = {"entries": [], "candidate_ids": []}
    bot.event_option_components = None
    bot.event_option_policy = {
        "runtime_risk_guards": {
            "daily_loss_streak_pause": {
                "enabled": True,
                "trigger_losses": 4,
                "pause_days": 1,
                "loss_threshold_return": 0.0,
                "risk_capital_dollars": 5000.0,
            }
        }
    }

    now = datetime(2026, 5, 22, 14, 30, tzinfo=ZoneInfo("America/New_York"))
    row_block = pd.Series(
        {
            "event_candidate_id": "spy_20260522_1430",
            "policy_ticker": "SPY",
            "date": "20260522",
            "time": "14:30",
            "policy_max_day": 999,
            "policy_cooldown_minutes": 0,
            "monthly_backfill_role": "primary",
            "mtd_source": "base",
            "source_variant": "win_valthr_strict_d25",
            "action": "PUT",
        }
    )
    allowed_first, reason_first = bot._event_candidate_allowed(row_block, now)
    allowed_repeat, reason_repeat = bot._event_candidate_allowed(row_block, now)

    row_next = row_block.copy()
    row_next["event_candidate_id"] = "spy_20260523_1430"
    row_next["date"] = "20260523"
    allowed_next, reason_next = bot._event_candidate_allowed(row_next, now.replace(day=23))

    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    skips = state.get("daily_loss_guard_skips", []) if isinstance(state, dict) else []
    checks = {
        "first_candidate_blocked": allowed_first is False and str(reason_first).startswith("daily_loss_streak_pause_t4_p1"),
        "skip_state_written": len(skips) == 1 and skips[0].get("policy_ticker") == "SPY" and skips[0].get("date") == "20260522",
        "same_day_repeat_blocked": allowed_repeat is False and reason_repeat == "daily_loss_streak_pause_already_active",
        "next_candidate_allowed_after_pause_consumed": allowed_next is True and reason_next == "allowed",
        "other_ticker_trade_ignored": all(skip.get("policy_ticker") != "SPXW" for skip in skips),
    }
    issues = [key for key, value in checks.items() if not bool(value)]
    payload = {
        "schema_version": 1,
        "validation": "bot_event_daily_loss_guard",
        "passed": not issues,
        "output_dir": str(output_dir),
        "checks": checks,
        "first_reason": reason_first,
        "repeat_reason": reason_repeat,
        "next_reason": reason_next,
        "state": state,
        "issues": issues,
    }
    (output_dir / "bot_event_daily_loss_guard_validation.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
