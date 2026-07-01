from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
DEFAULT_PAPER_ORDER_VALIDATION = DEFAULT_RESULT / "paper_order_validation" / "paper_order_validation.json"
DEFAULT_BOT_PAPER_INTENTS = DEFAULT_RESULT / "bot_paper_order_intent_validation" / "bot_paper_order_intent_validation.json"
DEFAULT_OUTPUT = DEFAULT_RESULT / "broker_order_contract_validation"
CONTRACT_MULTIPLIER = 100.0
SUPPORTED_ROOTS = {"SPXW", "SPY", "QQQ"}
TICKER_ROOT = {"SPX": "SPXW", "SPXW": "SPXW", "SPY": "SPY", "QQQ": "QQQ"}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def normalize_date(value: object) -> str:
    text = "".join(ch for ch in str(value) if ch.isdigit())
    return text[:8]


def date_from_generated_at(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%Y%m%d")
    except Exception:
        return normalize_date(text)


def normalize_right(value: object) -> str:
    text = str(value).upper()
    if text in {"C", "CALL"}:
        return "CALL"
    if text in {"P", "PUT"}:
        return "PUT"
    return text


def cents(value: object) -> int:
    return int(round(float(value) * 100.0))


def is_cent_price(value: float) -> bool:
    return abs(float(value) * 100.0 - round(float(value) * 100.0)) < 1e-9


def occ_key(root: str, expiration: str, right: str, strike: float) -> str:
    cp = "C" if right == "CALL" else "P"
    yy_mm_dd = str(expiration)[2:]
    strike_int = int(round(float(strike) * 1000.0))
    return f"{root}{yy_mm_dd}{cp}{strike_int:08d}"


def stable_client_order_id(*, source: str, side: str, root: str, expiration: str, right: str, strike: float, quantity: int, limit_price: float) -> str:
    raw = f"{source}|{side}|{root}|{expiration}|{right}|{strike:.3f}|{quantity}|{limit_price:.2f}"
    return "jepa_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def validate_order(row: dict[str, Any], *, source: str, index: int, risk_capital_default: float) -> dict[str, Any]:
    contract = row.get("option_contract") if isinstance(row.get("option_contract"), dict) else {}
    order = row.get("order") if isinstance(row.get("order"), dict) else {}
    risk = row.get("risk") if isinstance(row.get("risk"), dict) else {}
    ticker = str(row.get("ticker", "")).upper()
    root = str(contract.get("root", row.get("option_root", ""))).upper()
    expiration = normalize_date(contract.get("expiration", row.get("expiration", "")))
    trade_date = normalize_date(row.get("date", "")) or date_from_generated_at(row.get("generated_at", ""))
    right = normalize_right(contract.get("right", ""))
    strike = float(contract.get("strike", 0.0) or 0.0)
    side = str(order.get("side", "")).upper()
    order_type = str(order.get("order_type", "")).upper()
    time_in_force = str(order.get("time_in_force", "")).upper()
    asset_class = str(order.get("asset_class", "")).upper()
    quantity = int(order.get("quantity", 0) or 0)
    limit_price = float(order.get("limit_price", 0.0) or 0.0)
    risk_capital = float(risk.get("risk_capital", risk_capital_default) or risk_capital_default)
    max_debit = float(risk.get("max_debit", 0.0) or 0.0)
    estimated_credit = float(risk.get("estimated_credit", 0.0) or 0.0)
    multiplier = float(risk.get("contract_multiplier", CONTRACT_MULTIPLIER) or CONTRACT_MULTIPLIER)
    expected_max_debit = float(quantity * limit_price * multiplier) if side == "BUY_TO_OPEN" else 0.0
    expected_credit = float(quantity * limit_price * multiplier) if side == "SELL_TO_CLOSE" else 0.0

    issues: list[str] = []
    if root not in SUPPORTED_ROOTS:
        issues.append(f"unsupported option root {root}")
    expected_root = TICKER_ROOT.get(ticker)
    if expected_root and root != expected_root:
        issues.append(f"ticker {ticker} maps to {expected_root}, not {root}")
    if not expiration:
        issues.append("missing expiration")
    if trade_date and expiration != trade_date:
        issues.append(f"not zero-DTE expiration={expiration} trade_date={trade_date}")
    if right not in {"CALL", "PUT"}:
        issues.append(f"unsupported right {right}")
    if strike <= 0.0 or not math.isfinite(strike):
        issues.append("non-positive strike")
    if side not in {"BUY_TO_OPEN", "SELL_TO_CLOSE"}:
        issues.append(f"unsupported side {side}")
    if order_type != "LIMIT":
        issues.append(f"unsupported order_type {order_type}")
    if time_in_force != "DAY":
        issues.append(f"unsupported time_in_force {time_in_force}")
    if asset_class != "OPTION":
        issues.append(f"unsupported asset_class {asset_class}")
    if quantity <= 0:
        issues.append("quantity must be positive")
    if limit_price <= 0.0 or not math.isfinite(limit_price):
        issues.append("limit price must be positive")
    elif not is_cent_price(limit_price):
        issues.append(f"limit price {limit_price} is not cent-rounded")
    if abs(multiplier - CONTRACT_MULTIPLIER) > 1e-9:
        issues.append(f"unexpected contract multiplier {multiplier}")
    if risk_capital <= 0.0:
        issues.append("risk capital must be positive")
    if side == "BUY_TO_OPEN":
        if abs(max_debit - expected_max_debit) > 1e-6:
            issues.append(f"max_debit {max_debit:.2f} != qty*limit*100 {expected_max_debit:.2f}")
        if max_debit > risk_capital + 1e-9:
            issues.append(f"max_debit {max_debit:.2f} exceeds risk_capital {risk_capital:.2f}")
    if side == "SELL_TO_CLOSE":
        if max_debit != 0.0:
            issues.append(f"SELL_TO_CLOSE max_debit should be 0, got {max_debit:.2f}")
        if estimated_credit <= 0.0:
            issues.append("SELL_TO_CLOSE estimated_credit must be positive")
        elif abs(estimated_credit - expected_credit) > 1e-6:
            issues.append(f"estimated_credit {estimated_credit:.2f} != qty*limit*100 {expected_credit:.2f}")
    if row.get("passed") is False:
        issues.append("source order row is marked failed")
    if row.get("broker_submission") is True:
        issues.append("source intent unexpectedly claims broker_submission=true")

    key = occ_key(root, expiration, right, strike) if root and expiration and right in {"CALL", "PUT"} and strike > 0.0 else ""
    broker_payload = {
        "client_order_id": stable_client_order_id(
            source=f"{source}:{index}",
            side=side,
            root=root,
            expiration=expiration,
            right=right,
            strike=strike,
            quantity=quantity,
            limit_price=limit_price,
        ),
        "broker_submission": False,
        "asset_class": "OPTION",
        "side": side,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "quantity": quantity,
        "limit_price": limit_price,
        "occ_key": key,
        "option_contract": {
            "root": root,
            "expiration": expiration,
            "right": right,
            "strike": strike,
        },
        "risk": {
            "risk_capital": risk_capital,
            "contract_multiplier": multiplier,
            "max_debit": max_debit,
            "estimated_credit": estimated_credit,
        },
    }
    return {
        "source": source,
        "source_index": index,
        "ticker": ticker,
        "trade_date": trade_date,
        "occ_key": key,
        "broker_payload": broker_payload,
        "passed": not issues,
        "issues": issues,
    }


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Broker Order Contract Validation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Orders: {payload['passed_orders']}/{payload['total_orders']}",
        f"- Broker submission performed: `{payload['broker_submission_performed']}`",
        f"- Live fill evidence: `{payload['live_fill_evidence']}`",
        "",
        "This is a local preflight for broker-shaped option order payloads. It does not submit orders or prove broker acceptance/fills.",
        "",
        "## Source Counts",
        "",
        "```json",
        json.dumps(payload["source_counts"], indent=2, allow_nan=True),
        "```",
    ]
    if payload["issues"]:
        lines += ["", "## Issues", "", *[f"- {issue}" for issue in payload["issues"][:50]]]
    lines += ["", "## Not Covered", ""]
    lines.extend(f"- {item}" for item in payload["not_covered"])
    (output_dir / "BROKER_ORDER_CONTRACT_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate broker-order contract shape for dense15 candidate paper orders.")
    parser.add_argument("--paper-order-validation", default=str(DEFAULT_PAPER_ORDER_VALIDATION))
    parser.add_argument("--bot-paper-intents", default=str(DEFAULT_BOT_PAPER_INTENTS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paper = read_json(Path(args.paper_order_validation))
    bot_intents = read_json(Path(args.bot_paper_intents))
    paper_orders = paper.get("orders", []) if isinstance(paper.get("orders"), list) else []
    bot_orders = bot_intents.get("orders", []) if isinstance(bot_intents.get("orders"), list) else []

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(paper_orders):
        rows.append(validate_order(dict(row), source="paper_order_validation", index=idx, risk_capital_default=float(args.risk_capital)))
    for idx, row in enumerate(bot_orders):
        rows.append(validate_order(dict(row), source="bot_paper_order_intent", index=idx, risk_capital_default=float(args.risk_capital)))

    issues: list[str] = []
    if not bool(paper.get("passed")):
        issues.append("paper_order_validation source did not pass")
    if not bool(bot_intents.get("passed")):
        issues.append("bot_paper_order_intents source did not pass")
    if not paper_orders:
        issues.append("no paper validation orders found")
    if not bot_orders:
        issues.append("no bot paper intent orders found")
    failed = [row for row in rows if not bool(row.get("passed"))]
    for row in failed[:50]:
        issues.append(f"{row['source']}[{row['source_index']}] failed: " + "; ".join(row.get("issues", [])))

    payload = {
        "schema_version": 1,
        "validation": "dense_candidate_broker_order_contract",
        "passed": bool(rows and not issues),
        "paper_order_validation": str(Path(args.paper_order_validation)),
        "bot_paper_intents": str(Path(args.bot_paper_intents)),
        "broker_submission_performed": False,
        "live_fill_evidence": False,
        "total_orders": len(rows),
        "passed_orders": sum(1 for row in rows if bool(row.get("passed"))),
        "source_counts": {
            "paper_order_validation": len(paper_orders),
            "bot_paper_order_intent": len(bot_orders),
            "buy_to_open": sum(1 for row in rows if row.get("broker_payload", {}).get("side") == "BUY_TO_OPEN"),
            "sell_to_close": sum(1 for row in rows if row.get("broker_payload", {}).get("side") == "SELL_TO_CLOSE"),
        },
        "orders": rows,
        "not_covered": [
            "broker API authentication",
            "broker account buying-power checks",
            "broker API order acceptance",
            "paper or live broker order submission",
            "exchange queue position, partial fills, cancellations, or replacements",
            "live acknowledgement latency",
            "future completed-month trading performance",
        ],
        "issues": issues,
    }
    (output_dir / "broker_order_contract_validation.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
