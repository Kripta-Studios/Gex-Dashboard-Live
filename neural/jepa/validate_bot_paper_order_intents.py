from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bots.tradingbot_wrapper_jepa import JepaFixedDeltaBot, JepaOptionPosition


DEFAULT_OUTPUT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/"
    "bot_paper_order_intent_validation"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} contains a non-object JSONL row")
            rows.append(payload)
    return rows


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Bot Paper Order Intent Validation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Orders: {payload['passed_orders']}/{payload['total_orders']}",
        f"- JSONL: `{payload['jsonl_path']}`",
        "",
        "This validates local paper order intent generation only. It does not submit orders to a broker.",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], indent=2, allow_nan=True),
        "```",
    ]
    if payload["issues"]:
        lines += ["", "## Issues", "", *[f"- {issue}" for issue in payload["issues"]]]
    (output_dir / "BOT_PAPER_ORDER_INTENT_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bot paper order intent JSONL output.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "paper_order_intents_jepa.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()

    bot = JepaFixedDeltaBot.__new__(JepaFixedDeltaBot)
    bot.paper_order_intents = True
    bot.trades_dir = output_dir
    bot.paper_order_intents_path = jsonl_path

    now = datetime(2026, 5, 28, 14, 30, tzinfo=ZoneInfo("America/New_York"))
    pos = JepaOptionPosition(
        ticker="SPY",
        direction="SHORT",
        right="PUT",
        strike=755.0,
        delta=-0.252,
        expiration="20260528",
        entry_time=now.isoformat(),
        entry_spot=755.12,
        entry_premium=0.614075,
        raw_entry_premium=0.60,
        entry_spread_pct=0.0234583333,
        contracts=80,
        confidence=0.44,
        jepa_prob_up=0.38,
        long_threshold=0.12,
        short_threshold=0.62,
        selector_policy="event_option:SPY:base:win_valthr_strict_d25:zero_dte:d25:SPY_DENSE15_BACKFILL18",
    )
    bot._record_paper_order_intent(pos, now=now, side="BUY_TO_OPEN", limit_price=pos.entry_premium, reason="test_entry")
    bot._record_paper_order_intent(pos, now=now, side="SELL_TO_CLOSE", limit_price=0.489, reason="test_exit")
    rows = read_jsonl(jsonl_path)

    checks = {
        "two_orders_written": len(rows) == 2,
        "all_are_paper_only": all(row.get("broker_submission") is False for row in rows),
        "all_have_option_contract": all(isinstance(row.get("option_contract"), dict) for row in rows),
        "all_have_limit_orders": all((row.get("order") or {}).get("order_type") == "LIMIT" for row in rows),
        "bto_side": bool(rows and (rows[0].get("order") or {}).get("side") == "BUY_TO_OPEN"),
        "stc_side": bool(len(rows) > 1 and (rows[1].get("order") or {}).get("side") == "SELL_TO_CLOSE"),
        "bto_limit_ceil_cent": bool(rows and abs(float((rows[0].get("order") or {}).get("limit_price", 0.0)) - 0.62) < 1e-9),
        "stc_limit_floor_cent": bool(len(rows) > 1 and abs(float((rows[1].get("order") or {}).get("limit_price", 0.0)) - 0.48) < 1e-9),
        "bto_max_debit_under_risk": bool(rows and float((rows[0].get("risk") or {}).get("max_debit", 0.0)) <= 5000.0),
        "stc_estimated_credit_positive": bool(len(rows) > 1 and float((rows[1].get("risk") or {}).get("estimated_credit", 0.0)) > 0.0),
    }
    issues = [key for key, value in checks.items() if not bool(value)]
    payload = {
        "schema_version": 1,
        "validation": "bot_paper_order_intents",
        "passed": not issues,
        "jsonl_path": str(jsonl_path),
        "total_orders": len(rows),
        "passed_orders": 0 if issues else len(rows),
        "checks": checks,
        "orders": rows,
        "issues": issues,
    }
    (output_dir / "bot_paper_order_intent_validation.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
