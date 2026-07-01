from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
DEFAULT_OFFLINE_FILL = DEFAULT_RESULT / "offline_fill_simulation" / "offline_fill_simulation.json"
DEFAULT_OUTPUT = DEFAULT_RESULT / "paper_order_validation"
CONTRACT_MULTIPLIER = 100.0


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def normalize_date(value: object) -> str:
    text = "".join(ch for ch in str(value) if ch.isdigit())
    return text[:8]


def normalize_right(value: object) -> str:
    text = str(value).upper()
    if text in {"C", "CALL"}:
        return "CALL"
    if text in {"P", "PUT"}:
        return "PUT"
    return text


def ceil_to_cent(value: float) -> float:
    return float(math.ceil(float(value) * 100.0 - 1e-9) / 100.0)


def build_order(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    date = normalize_date(row.get("date", ""))
    expiration = normalize_date(row.get("expiration", date))
    ticker = str(row.get("ticker", "")).upper()
    symbol = str(row.get("symbol", ticker)).upper()
    right = normalize_right(row.get("right", ""))
    strike = float(row.get("strike", 0.0) or 0.0)
    selected_entry = float(row.get("selected_entry_premium", 0.0) or 0.0)
    entry_ask = float(row.get("entry_ask", 0.0) or 0.0)
    entry_bid = float(row.get("entry_bid", 0.0) or 0.0)
    limit_price = ceil_to_cent(selected_entry)
    max_contracts = math.floor(float(args.risk_capital) / max(limit_price * CONTRACT_MULTIPLIER, 1e-9))
    contracts = int(max_contracts)
    max_debit = float(contracts * limit_price * CONTRACT_MULTIPLIER)
    limit_over_ask_pct = float(limit_price / entry_ask - 1.0) if entry_ask > 0.0 else math.nan

    issues: list[str] = []
    if ticker not in {"SPX", "SPY", "QQQ"}:
        issues.append(f"unsupported ticker {ticker}")
    if not symbol:
        issues.append("missing option root symbol")
    if right not in {"CALL", "PUT"}:
        issues.append(f"unsupported right {right}")
    if strike <= 0.0 or not math.isfinite(strike):
        issues.append("non-positive strike")
    if not date:
        issues.append("missing trade date")
    if expiration != date:
        issues.append(f"not zero-DTE expiration={expiration} date={date}")
    if selected_entry <= 0.0:
        issues.append("non-positive selected entry premium")
    if entry_ask <= 0.0:
        issues.append("missing positive entry ask")
    if entry_bid < 0.0 or (entry_ask > 0.0 and entry_bid > entry_ask):
        issues.append("invalid bid/ask spread")
    if entry_ask > 0.0 and limit_price < entry_ask:
        issues.append(f"limit price {limit_price:.2f} is below ask {entry_ask:.2f}")
    if math.isfinite(limit_over_ask_pct) and limit_over_ask_pct > float(args.max_limit_over_ask_pct):
        issues.append(
            f"limit price is {limit_over_ask_pct:.2%} over ask, above {float(args.max_limit_over_ask_pct):.2%}"
        )
    if contracts <= 0:
        issues.append("risk capital cannot buy one contract at rounded limit")
    if max_debit > float(args.risk_capital) + 1e-9:
        issues.append("max debit exceeds risk capital")
    if not bool(row.get("entry_limit_covers_ask")):
        issues.append("offline entry limit did not cover ask")
    if not bool(row.get("exit_available")):
        issues.append("offline exit path unavailable")
    if not bool(row.get("passed")):
        issues.append("offline fill row did not pass")

    payload = {
        "date": date,
        "cutoff": str(row.get("cutoff", ""))[:5],
        "ticker": ticker,
        "option_root": symbol,
        "option_contract": {
            "root": symbol,
            "expiration": expiration,
            "right": right,
            "strike": strike,
        },
        "order": {
            "side": "BUY_TO_OPEN",
            "quantity": contracts,
            "order_type": "LIMIT",
            "limit_price": limit_price,
            "time_in_force": "DAY",
            "asset_class": "OPTION",
        },
        "risk": {
            "risk_capital": float(args.risk_capital),
            "contract_multiplier": CONTRACT_MULTIPLIER,
            "max_debit": max_debit,
            "unused_risk_capital": float(float(args.risk_capital) - max_debit),
        },
        "market": {
            "entry_bid": entry_bid,
            "entry_ask": entry_ask,
            "selected_entry_premium": selected_entry,
            "rounded_limit_over_ask_pct": limit_over_ask_pct,
        },
        "exit_contract": {
            "take_profit_pct": float(args.take_profit_pct),
            "stop_loss_pct": float(args.stop_loss_pct),
            "max_hold_minutes": int(args.max_hold_minutes),
            "offline_exit_available": bool(row.get("exit_available")),
            "offline_exit_reason": row.get("exit_reason"),
        },
        "source": {
            "source_stream": row.get("source_stream"),
            "monthly_backfill_role": row.get("monthly_backfill_role"),
        },
        "passed": not issues,
        "issues": issues,
    }
    return payload


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Paper Order Validation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Orders: {payload['passed_orders']}/{payload['total_orders']}",
        f"- Risk capital: `${float(payload['risk_capital']):,.0f}`",
        f"- Offline fill source: `{payload['offline_fill_simulation']}`",
        "",
        "This validates deterministic paper order payloads derived from the snapshot-to-order and offline-fill artifacts. It is not broker API acceptance or real exchange fill evidence.",
        "",
        "## Orders",
        "",
        "| Date | Cutoff | Ticker | Contract | Qty | Limit | Ask | Max Debit | Passed | Issues |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["orders"]:
        contract = row["option_contract"]
        order = row["order"]
        market = row["market"]
        risk = row["risk"]
        issues = "; ".join(str(item) for item in row.get("issues", [])[:3])
        lines.append(
            f"| {row['date']} | {row['cutoff']} | {row['ticker']} | "
            f"{contract['root']} {contract['expiration']} {contract['right']} {float(contract['strike']):.2f} | "
            f"{int(order['quantity'])} | {float(order['limit_price']):.2f} | "
            f"{float(market['entry_ask']):.2f} | {float(risk['max_debit']):.2f} | "
            f"{row['passed']} | {issues} |"
        )
    lines += [
        "",
        "## Not Covered",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["not_covered"])
    (output_dir / "PAPER_ORDER_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate paper order payloads for the dense15 candidate.")
    parser.add_argument("--offline-fill-simulation", default=str(DEFAULT_OFFLINE_FILL))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--take-profit-pct", type=float, default=0.50)
    parser.add_argument("--stop-loss-pct", type=float, default=-0.30)
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--max-limit-over-ask-pct", type=float, default=0.10)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    offline_path = Path(args.offline_fill_simulation)
    offline = read_json(offline_path)
    source_orders = offline.get("orders", [])
    if not isinstance(source_orders, list):
        raise ValueError("offline fill simulation orders must be a list")

    orders = [build_order(dict(row), args) for row in source_orders]
    passed_orders = sum(1 for row in orders if bool(row.get("passed")))
    source_passed = bool(
        offline.get("market_data_path_passed", offline.get("passed", False))
        and offline.get("strict_execution_cost_passed", False)
    )
    issues: list[str] = []
    if not source_passed:
        issues.append("offline fill simulation market/cost validation did not pass")
    failed = [row for row in orders if not bool(row.get("passed"))]
    if failed:
        issues.append(f"{len(failed)} paper orders failed validation")
    payload = {
        "schema_version": 1,
        "validation": "dense_candidate_paper_order_payloads",
        "passed": bool(source_orders and source_passed and not failed),
        "offline_fill_simulation": str(offline_path),
        "risk_capital": float(args.risk_capital),
        "total_orders": int(len(orders)),
        "passed_orders": int(passed_orders),
        "min_contracts": int(min((row["order"]["quantity"] for row in orders), default=0)),
        "max_contracts": int(max((row["order"]["quantity"] for row in orders), default=0)),
        "orders": orders,
        "not_covered": [
            "broker API order acceptance",
            "paper broker account submission",
            "real exchange queue position and partial fills",
            "latency between live signal, order submission, and exchange acknowledgement",
            "future 202607+ completed-month performance evidence",
        ],
        "issues": issues,
    }
    (output_dir / "paper_order_validation.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "date": row["date"],
                "cutoff": row["cutoff"],
                "ticker": row["ticker"],
                "option_root": row["option_root"],
                "expiration": row["option_contract"]["expiration"],
                "right": row["option_contract"]["right"],
                "strike": row["option_contract"]["strike"],
                "quantity": row["order"]["quantity"],
                "limit_price": row["order"]["limit_price"],
                "entry_ask": row["market"]["entry_ask"],
                "max_debit": row["risk"]["max_debit"],
                "passed": row["passed"],
                "issues": "; ".join(row["issues"]),
            }
            for row in orders
        ]
    ).to_csv(output_dir / "paper_order_validation_orders.csv", index=False)
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
