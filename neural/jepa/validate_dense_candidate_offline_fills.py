from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_BATCH = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/"
    "snapshot_to_order_batch_smoke/snapshot_to_order_batch_smoke.json"
)
DEFAULT_OUTPUT = Path(
    "research_papers/JEPA/results/"
    "event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/"
    "offline_fill_simulation"
)
OPTIONS_ROOT = Path(r"D:\ThetaData\data_options")
BOT_TO_OPTION_SYMBOL = {"SPX": "SPXW", "SPY": "SPY", "QQQ": "QQQ"}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def normalize_right(value: object) -> str:
    text = str(value).upper()
    if text.startswith("C"):
        return "CALL"
    if text.startswith("P"):
        return "PUT"
    return text


def normalize_date(value: object) -> str:
    text = str(value).replace("-", "").strip()
    return text[:8]


def month_parts(date: str) -> tuple[str, str]:
    return date[:4], date[4:6]


def option_file(root: Path, symbol: str, kind: str, date: str, expiration: str) -> Path:
    year, month = month_parts(date)
    return root / symbol / kind / year / month / f"{symbol}_{expiration}_{date}_{kind}.parquet"


def add_dt(frame: pd.DataFrame, preferred: str) -> pd.DataFrame:
    out = frame.copy()
    source = preferred if preferred in out.columns else "timestamp" if "timestamp" in out.columns else ""
    if not source:
        out["dt"] = pd.NaT
        return out
    out["dt"] = pd.to_datetime(out[source], format="mixed", errors="coerce").dt.floor("min")
    return out.dropna(subset=["dt"])


def mid_price(row: pd.Series) -> float:
    bid = float(row.get("bid", 0.0) or 0.0)
    ask = float(row.get("ask", 0.0) or 0.0)
    if bid > 0.0 and ask > 0.0:
        return float((bid + ask) / 2.0)
    for col in ["close", "open", "vwap", "high", "low"]:
        value = float(row.get(col, 0.0) or 0.0)
        if value > 0.0:
            return value
    return 0.0


def exit_quote(row: pd.Series) -> float:
    bid = float(row.get("bid", 0.0) or 0.0)
    if bid > 0.0:
        return bid
    for col in ["close", "vwap", "open", "low", "high"]:
        value = float(row.get(col, 0.0) or 0.0)
        if value > 0.0:
            return value
    return 0.0


def load_contract_frame(
    *,
    root: Path,
    symbol: str,
    date: str,
    expiration: str,
    right: str,
    strike: float,
) -> tuple[pd.DataFrame, list[str]]:
    issues: list[str] = []
    greeks_path = option_file(root, symbol, "greeks", date, expiration)
    ohlc_path = option_file(root, symbol, "ohlc", date, expiration)
    if not greeks_path.exists():
        return pd.DataFrame(), [f"missing greeks {greeks_path}"]
    if not ohlc_path.exists():
        return pd.DataFrame(), [f"missing ohlc {ohlc_path}"]

    greeks_cols = [
        "strike",
        "right",
        "bid",
        "ask",
        "delta",
        "underlying_timestamp",
        "timestamp",
    ]
    ohlc_cols = ["strike", "right", "timestamp", "open", "high", "low", "close", "vwap", "volume", "count"]
    greeks = pd.read_parquet(greeks_path, columns=[col for col in greeks_cols if col])
    ohlc = pd.read_parquet(ohlc_path, columns=[col for col in ohlc_cols if col])
    greeks = add_dt(greeks, "underlying_timestamp")
    ohlc = add_dt(ohlc, "timestamp")
    for frame in [greeks, ohlc]:
        if not frame.empty:
            frame["right"] = frame["right"].map(normalize_right)
            frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    greeks = greeks[
        greeks["right"].eq(right)
        & np.isclose(pd.to_numeric(greeks["strike"], errors="coerce"), float(strike), rtol=0.0, atol=1e-6)
    ].copy()
    ohlc = ohlc[
        ohlc["right"].eq(right)
        & np.isclose(pd.to_numeric(ohlc["strike"], errors="coerce"), float(strike), rtol=0.0, atol=1e-6)
    ].copy()
    if greeks.empty:
        issues.append("selected contract missing in greeks")
    if ohlc.empty:
        issues.append("selected contract missing in ohlc")
    if greeks.empty and ohlc.empty:
        return pd.DataFrame(), issues

    for col in ["bid", "ask", "delta"]:
        if col in greeks.columns:
            greeks[col] = pd.to_numeric(greeks[col], errors="coerce")
    for col in ["open", "high", "low", "close", "vwap", "volume", "count"]:
        if col in ohlc.columns:
            ohlc[col] = pd.to_numeric(ohlc[col], errors="coerce")
    merged = greeks.merge(
        ohlc.drop(columns=["right", "strike"], errors="ignore"),
        on="dt",
        how="outer",
        suffixes=("", "_ohlc"),
    ).sort_values("dt", kind="stable")
    return merged.reset_index(drop=True), issues


def simulate_exit(
    frame: pd.DataFrame,
    *,
    entry_dt: pd.Timestamp,
    entry_premium: float,
    take_profit_pct: float,
    stop_loss_pct: float,
    max_hold_minutes: int,
) -> dict[str, Any]:
    end_dt = entry_dt + pd.Timedelta(minutes=int(max_hold_minutes))
    future = frame[(frame["dt"] > entry_dt) & (frame["dt"] <= end_dt)].copy()
    if future.empty:
        return {
            "exit_available": False,
            "exit_reason": "no_future_quotes",
            "exit_price": 0.0,
            "exit_time": None,
            "pnl_pct_on_model_entry": math.nan,
        }
    take_profit = float(entry_premium) * (1.0 + float(take_profit_pct))
    stop_loss = float(entry_premium) * (1.0 + float(stop_loss_pct))
    last_price = 0.0
    last_dt = None
    for row in future.itertuples(index=False):
        item = pd.Series(row._asdict())
        price = exit_quote(item)
        if price <= 0.0:
            continue
        last_price = price
        last_dt = item["dt"]
        if price <= stop_loss:
            return {
                "exit_available": True,
                "exit_reason": "stop_loss",
                "exit_price": float(price),
                "exit_time": pd.Timestamp(last_dt).strftime("%H:%M"),
                "pnl_pct_on_model_entry": float(price / max(entry_premium, 1e-9) - 1.0),
            }
        if price >= take_profit:
            return {
                "exit_available": True,
                "exit_reason": "take_profit",
                "exit_price": float(price),
                "exit_time": pd.Timestamp(last_dt).strftime("%H:%M"),
                "pnl_pct_on_model_entry": float(price / max(entry_premium, 1e-9) - 1.0),
            }
    if last_price <= 0.0 or last_dt is None:
        return {
            "exit_available": False,
            "exit_reason": "no_positive_future_quote",
            "exit_price": 0.0,
            "exit_time": None,
            "pnl_pct_on_model_entry": math.nan,
        }
    return {
        "exit_available": True,
        "exit_reason": "max_hold",
        "exit_price": float(last_price),
        "exit_time": pd.Timestamp(last_dt).strftime("%H:%M"),
        "pnl_pct_on_model_entry": float(last_price / max(entry_premium, 1e-9) - 1.0),
    }


def validate_selection(case: dict[str, Any], selection: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    date = normalize_date(case["date"])
    cutoff = str(case["cutoff"])[:5]
    entry_dt = pd.Timestamp(f"{date[:4]}-{date[4:6]}-{date[6:8]} {cutoff}")
    ticker = str(selection.get("ticker", "")).upper()
    symbol = BOT_TO_OPTION_SYMBOL.get(ticker, ticker)
    right = normalize_right(selection.get("action", ""))
    expiration = normalize_date(selection.get("expiration", date)) or date
    strike = float(selection.get("strike", 0.0) or 0.0)
    selected_raw = float(selection.get("raw_entry_premium", 0.0) or 0.0)
    selected_entry = float(selection.get("entry_premium", 0.0) or 0.0)
    issues: list[str] = []
    frame, load_issues = load_contract_frame(
        root=Path(args.options_root),
        symbol=symbol,
        date=date,
        expiration=expiration,
        right=right,
        strike=strike,
    )
    issues.extend(load_issues)
    if frame.empty:
        return {
            "date": date,
            "cutoff": cutoff,
            "ticker": ticker,
            "symbol": symbol,
            "right": right,
            "strike": strike,
            "passed": False,
            "issues": issues,
        }

    before = frame[frame["dt"] <= entry_dt].copy()
    if before.empty:
        issues.append("no entry quote at or before cutoff")
        entry = frame.iloc[0]
    else:
        entry = before.iloc[-1]
    entry_quote_dt = pd.Timestamp(entry["dt"])
    entry_mid = mid_price(entry)
    entry_bid = float(entry.get("bid", 0.0) or 0.0)
    entry_ask = float(entry.get("ask", 0.0) or 0.0)
    if selected_raw <= 0.0 or selected_entry <= 0.0:
        issues.append("selection has non-positive premium")
    if entry_mid <= 0.0:
        issues.append("entry mid/close unavailable")
    raw_diff = abs(entry_mid - selected_raw)
    raw_tolerance = max(float(args.raw_premium_abs_tolerance), abs(selected_raw) * float(args.raw_premium_rel_tolerance))
    raw_match = bool(selected_raw > 0.0 and entry_mid > 0.0 and raw_diff <= raw_tolerance)
    if not raw_match:
        issues.append(f"raw premium mismatch entry_mid={entry_mid:.6g} selected_raw={selected_raw:.6g}")
    entry_limit_covers_ask = bool(entry_ask > 0.0 and selected_entry >= entry_ask)
    if entry_ask <= 0.0:
        issues.append("entry ask unavailable")

    exit_result = simulate_exit(
        frame,
        entry_dt=entry_quote_dt,
        entry_premium=selected_entry,
        take_profit_pct=float(args.take_profit_pct),
        stop_loss_pct=float(args.stop_loss_pct),
        max_hold_minutes=int(args.max_hold_minutes),
    )
    if not exit_result.get("exit_available"):
        issues.append(str(exit_result.get("exit_reason", "exit unavailable")))
    passed = bool(raw_match and entry_mid > 0.0 and selected_entry > 0.0 and exit_result.get("exit_available"))
    return {
        "date": date,
        "cutoff": cutoff,
        "ticker": ticker,
        "symbol": symbol,
        "right": right,
        "strike": strike,
        "expiration": expiration,
        "source_stream": str(selection.get("source_stream", "")),
        "monthly_backfill_role": str(selection.get("monthly_backfill_role", "")),
        "entry_quote_time": entry_quote_dt.strftime("%H:%M"),
        "entry_bid": float(entry_bid),
        "entry_ask": float(entry_ask),
        "entry_mid": float(entry_mid),
        "selected_raw_entry_premium": float(selected_raw),
        "selected_entry_premium": float(selected_entry),
        "raw_premium_abs_diff": float(raw_diff),
        "raw_premium_match": raw_match,
        "entry_limit_covers_ask": entry_limit_covers_ask,
        "entry_model_under_ask_pct": (
            float(selected_entry / entry_ask - 1.0) if entry_ask > 0.0 and selected_entry > 0.0 else math.nan
        ),
        **exit_result,
        "passed": passed,
        "issues": issues,
    }


def write_markdown(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Offline Fill Simulation",
        "",
        f"- Passed: {payload['passed']}",
        f"- Market-data path passed: {payload['market_data_path_passed']}",
        f"- Strict execution-cost passed: {payload['strict_execution_cost_passed']}",
        f"- Orders: {payload['passed_orders']}/{payload['total_orders']}",
        f"- Entry limit covers ask: {payload['entry_limit_covers_ask_orders']}/{payload['total_orders']}",
        f"- Batch smoke: `{payload['batch_smoke']}`",
        "",
        "This is an offline ThetaData market-data validation of selected contracts. It is not proof of broker API acceptance or real exchange fills.",
        "",
        "## Orders",
        "",
        "| Date | Cutoff | Ticker | Right | Strike | Source | Entry Mid | Entry Ask | Model Entry | Ask Covered | Exit | PnL | Passed | Issues |",
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["orders"]:
        issues = "; ".join(str(item) for item in row.get("issues", [])[:3])
        lines.append(
            f"| {row.get('date', '')} | {row.get('cutoff', '')} | {row.get('ticker', '')} | "
            f"{row.get('right', '')} | {float(row.get('strike', 0.0)):.2f} | {row.get('source_stream', '')} | "
            f"{float(row.get('entry_mid', 0.0)):.3f} | {float(row.get('entry_ask', 0.0)):.3f} | "
            f"{float(row.get('selected_entry_premium', 0.0)):.3f} | {row.get('entry_limit_covers_ask', False)} | "
            f"{row.get('exit_reason', '')}@{row.get('exit_time', '')} | "
            f"{float(row.get('pnl_pct_on_model_entry', 0.0)):.1%} | {row.get('passed', False)} | {issues} |"
        )
    lines += [
        "",
        "## Not Covered",
        "",
    ]
    for item in payload["not_covered"]:
        lines.append(f"- {item}")
    (output_dir / "OFFLINE_FILL_SIMULATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate selected dense candidate orders against ThetaData 1m option market data.")
    parser.add_argument("--batch-smoke", default=str(DEFAULT_BATCH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--options-root", default=str(OPTIONS_ROOT))
    parser.add_argument("--take-profit-pct", type=float, default=0.50)
    parser.add_argument("--stop-loss-pct", type=float, default=-0.30)
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--raw-premium-abs-tolerance", type=float, default=0.025)
    parser.add_argument("--raw-premium-rel-tolerance", type=float, default=0.015)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_path = Path(args.batch_smoke)
    batch = read_json(batch_path)
    orders: list[dict[str, Any]] = []
    for case in batch.get("cases", []):
        if not bool(case.get("passed")):
            continue
        for selection in case.get("selections", []):
            if bool(selection.get("selected")):
                orders.append(validate_selection(case, selection, args))

    passed_orders = sum(1 for row in orders if bool(row.get("passed")))
    ask_covered = sum(1 for row in orders if bool(row.get("entry_limit_covers_ask")))
    payload = {
        "schema_version": 1,
        "validation": "dense_candidate_offline_fill_simulation",
        "passed": bool(orders and passed_orders == len(orders)),
        "market_data_path_passed": bool(orders and passed_orders == len(orders)),
        "strict_execution_cost_passed": bool(orders and ask_covered == len(orders)),
        "total_orders": int(len(orders)),
        "passed_orders": int(passed_orders),
        "entry_limit_covers_ask_orders": int(ask_covered),
        "batch_smoke": str(batch_path),
        "options_root": str(args.options_root),
        "exit_contract": {
            "take_profit_pct": float(args.take_profit_pct),
            "stop_loss_pct": float(args.stop_loss_pct),
            "max_hold_minutes": int(args.max_hold_minutes),
        },
        "orders": orders,
        "not_covered": [
            "broker API order acceptance",
            "real exchange queue position and partial fills",
            "latency between signal, order submission, and fill",
            "future 202607+ performance evidence",
        ],
    }
    (output_dir / "offline_fill_simulation.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    pd.DataFrame(orders).to_csv(output_dir / "offline_fill_simulation_orders.csv", index=False)
    write_markdown(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
