from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1"
)
DEFAULT_EXPECTED_ORDERS = DEFAULT_RESULT / "broker_order_contract_validation" / "broker_order_contract_validation.json"
DEFAULT_FILLS = DEFAULT_RESULT / "broker_fill_validation" / "broker_fills.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_RESULT / "broker_fill_validation"
FILLED_STATUSES = {"filled", "fill", "executed", "done"}
PARTIAL_STATUSES = {"partially_filled", "partial_fill", "partial"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, allow_nan=True) + "\n", encoding="utf-8")


def load_json_or_jsonl(path: Path) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        rows = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
        return rows
    payload = json.loads(text)
    if isinstance(payload, dict) and isinstance(payload.get("fills"), list):
        return payload["fills"]
    if isinstance(payload, list):
        return payload
    return payload


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def first_present(row: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def load_expected_orders(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    issues: list[str] = []
    if not path.exists():
        return {}, [f"missing expected broker order contract artifact: {path}"]
    payload = read_json(path)
    orders = payload.get("orders") if isinstance(payload, dict) else None
    if not isinstance(orders, list):
        return {}, [f"{path} missing orders list"]
    expected: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(orders):
        if not isinstance(item, dict):
            issues.append(f"expected order {idx} is not an object")
            continue
        broker_payload = item.get("broker_payload") if isinstance(item.get("broker_payload"), dict) else {}
        client_order_id = str(broker_payload.get("client_order_id") or "").strip()
        if not client_order_id:
            issues.append(f"expected order {idx} missing client_order_id")
            continue
        if client_order_id in expected:
            issues.append(f"duplicate expected client_order_id {client_order_id}")
            continue
        expected[client_order_id] = {
            "source": item.get("source"),
            "source_index": item.get("source_index"),
            "ticker": item.get("ticker"),
            "trade_date": item.get("trade_date"),
            "client_order_id": client_order_id,
            "occ_key": str(broker_payload.get("occ_key") or ""),
            "side": str(broker_payload.get("side") or "").upper(),
            "quantity": as_int(broker_payload.get("quantity")),
            "limit_price": as_float(broker_payload.get("limit_price")),
            "asset_class": str(broker_payload.get("asset_class") or "").upper(),
            "option_contract": broker_payload.get("option_contract", {}),
        }
    return expected, issues


def normalize_fill(raw: dict[str, Any]) -> dict[str, Any]:
    order = raw.get("order") if isinstance(raw.get("order"), dict) else {}
    contract = raw.get("option_contract") if isinstance(raw.get("option_contract"), dict) else {}
    return {
        "raw": raw,
        "client_order_id": str(first_present(raw, ["client_order_id", "clientOrderId", "client_orderid"]) or "").strip(),
        "broker_order_id": str(first_present(raw, ["broker_order_id", "order_id", "id", "brokerOrderId"]) or "").strip(),
        "occ_key": str(first_present(raw, ["occ_key", "symbol", "option_symbol"]) or order.get("occ_key") or "").strip(),
        "side": str(first_present(raw, ["side", "order_side"]) or order.get("side") or "").upper().strip(),
        "status": normalize_status(first_present(raw, ["status", "order_status", "fill_status"])),
        "filled_qty": as_int(first_present(raw, ["filled_qty", "filled_quantity", "filledQuantity", "quantity_filled", "qty"]) or raw.get("quantity")),
        "avg_fill_price": as_float(first_present(raw, ["avg_fill_price", "average_fill_price", "filled_avg_price", "fill_price", "price"])),
        "limit_price": as_float(first_present(raw, ["limit_price", "limitPrice"]) or order.get("limit_price")),
        "filled_at": str(first_present(raw, ["filled_at", "fill_time", "timestamp", "updated_at", "executed_at"]) or "").strip(),
        "broker": str(first_present(raw, ["broker", "venue", "provider"]) or "").strip(),
        "account_mode": str(first_present(raw, ["account_mode", "environment", "mode"]) or "").strip().lower(),
        "asset_class": str(first_present(raw, ["asset_class"]) or order.get("asset_class") or "OPTION").upper(),
        "contract": contract,
    }


def validate_fill(fill: dict[str, Any], expected: dict[str, dict[str, Any]], tolerance: float) -> dict[str, Any]:
    issues: list[str] = []
    client_order_id = fill["client_order_id"]
    expected_order = expected.get(client_order_id)
    if not client_order_id:
        issues.append("missing client_order_id")
    elif expected_order is None:
        issues.append(f"client_order_id {client_order_id} not found in expected broker payloads")
    status = fill["status"]
    full_or_partial = status in FILLED_STATUSES or status in PARTIAL_STATUSES
    if not full_or_partial:
        issues.append(f"status {status!r} is not a filled/partial-fill status")
    if fill["filled_qty"] <= 0:
        issues.append("filled quantity must be positive")
    if not math.isfinite(fill["avg_fill_price"]) or fill["avg_fill_price"] <= 0.0:
        issues.append("avg fill price must be positive")
    if not fill["filled_at"]:
        issues.append("filled_at/fill timestamp missing")
    if fill["asset_class"] != "OPTION":
        issues.append(f"asset_class {fill['asset_class']!r} != OPTION")
    if expected_order is not None:
        if fill["occ_key"] and fill["occ_key"] != expected_order["occ_key"]:
            issues.append(f"occ_key {fill['occ_key']} != expected {expected_order['occ_key']}")
        if fill["side"] and fill["side"] != expected_order["side"]:
            issues.append(f"side {fill['side']} != expected {expected_order['side']}")
        if fill["filled_qty"] > expected_order["quantity"]:
            issues.append(f"filled quantity {fill['filled_qty']} > expected {expected_order['quantity']}")
        expected_limit = expected_order["limit_price"]
        if fill["side"] == "BUY_TO_OPEN" or expected_order["side"] == "BUY_TO_OPEN":
            if fill["avg_fill_price"] > expected_limit + tolerance:
                issues.append(f"buy fill price {fill['avg_fill_price']:.4f} > limit {expected_limit:.4f}")
        if fill["side"] == "SELL_TO_CLOSE" or expected_order["side"] == "SELL_TO_CLOSE":
            if fill["avg_fill_price"] < expected_limit - tolerance:
                issues.append(f"sell fill price {fill['avg_fill_price']:.4f} < limit {expected_limit:.4f}")
    out = {k: v for k, v in fill.items() if k != "raw"}
    out["expected_order"] = expected_order
    out["passed"] = not issues
    out["issues"] = issues
    return out


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Broker Fill Evidence Validation",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Expected orders: `{payload['expected_orders']}`",
        f"- Fills checked: `{payload['fills_checked']}`",
        f"- Fills passed: `{payload['fills_passed']}`",
        f"- Broker submission evidence: `{payload['broker_submission_evidence']}`",
        f"- Require all expected orders: `{payload['require_all_expected']}`",
        "",
        "This validates broker/paper/live execution reports against local canonical option order payloads. It does not simulate exchange queue position or future performance.",
        "",
    ]
    if payload["issues"]:
        lines.extend(["## Issues", ""])
        for issue in payload["issues"]:
            lines.append(f"- {issue}")
            if len(lines) > 80:
                lines.append("- ...")
                break
    output_dir.joinpath("BROKER_FILL_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    expected_orders, issues = load_expected_orders(Path(args.expected_orders))
    fills_path = Path(args.fills)
    fills: list[Any] = []
    if not fills_path.exists():
        issues.append(f"missing broker fill evidence file: {fills_path}")
    else:
        loaded = load_json_or_jsonl(fills_path)
        if not isinstance(loaded, list):
            issues.append(f"broker fill evidence must be a JSON list or JSONL rows: {fills_path}")
        else:
            fills = loaded
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(fills):
        if not isinstance(raw, dict):
            normalized.append({"source_index": idx, "passed": False, "issues": ["fill row is not an object"]})
            continue
        row = validate_fill(normalize_fill(raw), expected_orders, float(args.price_tolerance))
        row["source_index"] = idx
        normalized.append(row)
    matched_ids = {row.get("client_order_id") for row in normalized if row.get("passed") and row.get("client_order_id")}
    expected_ids = set(expected_orders.keys())
    missing_expected = sorted(expected_ids.difference(matched_ids)) if bool(args.require_all_expected) else []
    if bool(args.require_all_expected) and missing_expected:
        issues.append(f"missing fills for expected client_order_ids: {missing_expected[:20]}")
    passed_fills = [row for row in normalized if row.get("passed")]
    if len(passed_fills) < int(args.min_filled_orders):
        issues.append(f"passed fills {len(passed_fills)} < min_filled_orders {args.min_filled_orders}")
    if bool(args.require_entry_and_exit):
        sides = {str(row.get("side")) for row in passed_fills}
        if "BUY_TO_OPEN" not in sides:
            issues.append("no passed BUY_TO_OPEN fill evidence")
        if "SELL_TO_CLOSE" not in sides:
            issues.append("no passed SELL_TO_CLOSE fill evidence")
    if bool(args.require_live):
        non_live = [row.get("client_order_id") for row in passed_fills if str(row.get("account_mode", "")).lower() != "live"]
        if non_live:
            issues.append(f"non-live fill evidence found while --require-live is set: {non_live[:20]}")
    broker_submission_evidence = bool(passed_fills)
    row_issues = [f"fill[{row.get('source_index')}]: " + "; ".join(row.get("issues", [])) for row in normalized if row.get("issues")]
    all_issues = issues + row_issues
    return {
        "schema_version": 1,
        "validation": "dense_candidate_broker_fill_evidence",
        "passed": bool(not all_issues and broker_submission_evidence),
        "expected_orders_path": str(args.expected_orders),
        "fills_path": str(args.fills),
        "expected_orders": len(expected_orders),
        "fills_checked": len(normalized),
        "fills_passed": len(passed_fills),
        "broker_submission_evidence": broker_submission_evidence,
        "live_fill_evidence": bool(broker_submission_evidence and bool(args.require_live)),
        "require_live": bool(args.require_live),
        "require_all_expected": bool(args.require_all_expected),
        "require_entry_and_exit": bool(args.require_entry_and_exit),
        "min_filled_orders": int(args.min_filled_orders),
        "matched_expected_orders": len(matched_ids),
        "missing_expected_orders": missing_expected,
        "fills": normalized,
        "not_covered": [
            "exchange queue position",
            "market impact",
            "future completed-month trading performance",
        ],
        "issues": all_issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate broker/paper/live fill reports against dense candidate option orders.")
    parser.add_argument("--expected-orders", default=str(DEFAULT_EXPECTED_ORDERS))
    parser.add_argument("--fills", default=str(DEFAULT_FILLS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--min-filled-orders", type=int, default=1)
    parser.add_argument("--price-tolerance", type=float, default=1e-9)
    parser.add_argument("--require-all-expected", action="store_true")
    parser.add_argument("--require-entry-and-exit", action="store_true", default=True)
    parser.add_argument("--no-require-entry-and-exit", dest="require_entry_and_exit", action="store_false")
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args)
    write_json(output_dir / "broker_fill_validation.json", payload)
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    if payload["passed"] or bool(args.exit_zero_on_fail):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
