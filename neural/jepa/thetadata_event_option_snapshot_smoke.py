from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.event_option_component_live import EventOptionComponentRegistry
from neural.jepa.event_option_live_snapshot import build_live_event_option_snapshots


THETADATA_URL = os.environ.get("THETADATA_URL", "http://91.99.90.39:25503/v3").rstrip("/")
ET = ZoneInfo("America/New_York")
OPTIONS_ENDPOINTS = {
    "greeks": "/option/history/greeks/first_order",
    "oi": "/option/history/open_interest",
    "iv": "/option/history/greeks/implied_volatility",
    "ohlc": "/option/history/ohlc",
}
OPTIONS_TO_UNDERLYING = {"SPXW": "SPX", "SPX": "SPX", "SPY": "SPY", "QQQ": "QQQ"}


def parse_response(raw: Any) -> Any:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("response", [])
    return []


def request_json(path: str, params: dict[str, Any], timeout: float) -> Any:
    response = requests.get(f"{THETADATA_URL}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def default_et_time_window(date_yyyymmdd: str, window_minutes: int) -> tuple[str, str]:
    now_et = datetime.now(ET)
    today_et = now_et.strftime("%Y%m%d")
    market_time = dt_time(9, 35) <= now_et.time().replace(tzinfo=None) <= dt_time(16, 0)
    if date_yyyymmdd == today_et and market_time:
        end_dt = now_et
    else:
        end_dt = datetime.combine(
            datetime.strptime(date_yyyymmdd, "%Y%m%d").date(),
            dt_time(15, 55),
            tzinfo=ET,
        )
    start_dt = end_dt - timedelta(minutes=int(window_minutes))
    return start_dt.strftime("%H:%M:%S"), end_dt.strftime("%H:%M:%S")


def normalize_expiration(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("expiration", "")
    text = "".join(ch for ch in str(value) if ch.isdigit())
    return text[:8] if len(text) >= 8 else ""


def get_expirations(symbol: str, date_yyyymmdd: str, timeout: float) -> list[str]:
    raw = request_json(
        "/option/list/expirations",
        {"symbol": symbol, "date": date_yyyymmdd, "format": "json"},
        timeout,
    )
    out = [normalize_expiration(item) for item in parse_response(raw)]
    return sorted(exp for exp in out if exp)


def choose_expirations(symbol: str, date_yyyymmdd: str, timeout: float) -> dict[str, str]:
    exps = get_expirations(symbol, date_yyyymmdd, timeout)
    if not exps:
        return {}
    today = datetime.strptime(date_yyyymmdd, "%Y%m%d").date()
    today_exp = date_yyyymmdd if date_yyyymmdd in exps else ""
    future = [exp for exp in exps if exp >= date_yyyymmdd]
    weekly = ""
    if future:
        target_friday = today + timedelta(days=(4 - today.weekday()) % 7)
        candidates = []
        for offset in range(5):
            day = target_friday - timedelta(days=offset)
            candidates.append(day.strftime("%Y%m%d"))
        next_friday = target_friday + timedelta(days=7)
        for offset in range(5):
            day = next_friday - timedelta(days=offset)
            candidates.append(day.strftime("%Y%m%d"))
        for exp in candidates:
            if exp in future and exp != today_exp:
                weekly = exp
                break
        if not weekly:
            weekly = next((exp for exp in future if exp != today_exp), "")
    out = {}
    if today_exp:
        out["0dte"] = today_exp
    if weekly:
        out["weekly"] = weekly
    return out


def flatten_option_response(raw: Any, default_right: str, expiration: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in parse_response(raw):
        if isinstance(item, dict) and "contract" in item and "data" in item:
            contract = dict(item.get("contract") or {})
            data_rows = item.get("data") or []
            for data in data_rows:
                if isinstance(data, dict):
                    rows.append({**contract, **data})
        elif isinstance(item, dict):
            rows.append(dict(item))
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if "right" not in frame.columns:
        frame["right"] = default_right
    frame["right"] = frame["right"].replace({"C": "CALL", "P": "PUT", "Call": "CALL", "Put": "PUT"})
    frame["expiration"] = expiration
    return frame


def fetch_option_endpoint(
    symbol: str,
    expiration: str,
    endpoint_key: str,
    date_yyyymmdd: str,
    start_time: str,
    end_time: str,
    timeout: float,
) -> pd.DataFrame:
    endpoint = OPTIONS_ENDPOINTS[endpoint_key]
    parts: list[pd.DataFrame] = []
    errors: list[str] = []
    for api_right, right_name in (("C", "CALL"), ("P", "PUT")):
        base_params: dict[str, Any] = {
            "symbol": symbol,
            "expiration": expiration,
            "strike": "*",
            "right": api_right,
            "date": date_yyyymmdd,
            "format": "json",
        }
        request_variants = [base_params]
        if endpoint_key != "oi":
            live_params = {**base_params, "start_time": start_time, "end_time": end_time}
            interval_params = {**live_params, "interval": "1m"}
            request_variants = [live_params, interval_params]
        raw = None
        for params in request_variants:
            try:
                raw = request_json(endpoint, params, timeout)
                break
            except Exception as exc:
                interval_label = "interval" if "interval" in params else "no_interval"
                errors.append(f"{endpoint_key}:{api_right}:{interval_label}:{exc}")
        if raw is None:
            continue
        part = flatten_option_response(raw, right_name, expiration)
        if not part.empty:
            parts.append(part)
    if not parts:
        if errors:
            frame = pd.DataFrame()
            frame.attrs["errors"] = errors
            return frame
        return pd.DataFrame()
    frame = pd.concat(parts, ignore_index=True, sort=False)
    for col in ("strike", "underlying_price", "delta", "implied_vol", "implied_volatility", "theta", "vega", "bid", "ask", "close", "volume", "count", "open_interest"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def write_spot_from_greeks(output_dir: Path, symbol: str, greeks_frames: list[pd.DataFrame]) -> None:
    frames = [frame for frame in greeks_frames if not frame.empty and "underlying_price" in frame.columns]
    if not frames:
        return
    raw = pd.concat(frames, ignore_index=True, sort=False)
    time_col = "underlying_timestamp" if "underlying_timestamp" in raw.columns else "timestamp" if "timestamp" in raw.columns else ""
    if not time_col:
        return
    raw["dt"] = pd.to_datetime(raw[time_col], format="mixed", errors="coerce")
    raw = raw.dropna(subset=["dt", "underlying_price"]).copy()
    raw = raw[pd.to_numeric(raw["underlying_price"], errors="coerce") > 0].copy()
    if raw.empty:
        return
    raw["_minute"] = raw["dt"].dt.floor("min")
    spot = (
        raw.groupby("_minute", as_index=False)["underlying_price"]
        .agg(open="first", high="max", low="min", close="last", tick_count="count")
        .rename(columns={"_minute": "timestamp"})
    )
    spot.insert(0, "symbol", OPTIONS_TO_UNDERLYING.get(symbol, symbol))
    spot["timestamp"] = pd.to_datetime(spot["timestamp"], format="mixed", errors="coerce").astype(str)
    out_symbol = OPTIONS_TO_UNDERLYING.get(symbol, symbol)
    spot.to_parquet(output_dir / f"spot_{out_symbol}_latest.parquet", index=False)


def write_rt_data_from_thetadata(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    default_start_time, default_end_time = default_et_time_window(args.date, int(args.window_minutes))
    end_time = str(args.end_time) if args.end_time else default_end_time
    start_time = str(args.start_time) if args.start_time else default_start_time
    summary: dict[str, Any] = {
        "base_url": THETADATA_URL,
        "timezone": "America/New_York",
        "generated_at_et": datetime.now(ET).isoformat(),
        "date": args.date,
        "start_time": start_time,
        "end_time": end_time,
        "symbols": {},
    }

    for symbol in args.tickers:
        expirations = choose_expirations(symbol, args.date, float(args.timeout))
        wanted_suffixes = {str(s).lower() for s in args.suffixes}
        expirations = {suffix: exp for suffix, exp in expirations.items() if suffix in wanted_suffixes}
        symbol_summary: dict[str, Any] = {"expirations": expirations, "files": {}}
        greeks_for_spot: list[pd.DataFrame] = []
        for suffix, expiration in expirations.items():
            for endpoint_key in args.endpoints:
                try:
                    frame = fetch_option_endpoint(
                        symbol,
                        expiration,
                        endpoint_key,
                        args.date,
                        start_time,
                        end_time,
                        float(args.timeout),
                    )
                except Exception as exc:
                    symbol_summary["files"][f"{suffix}:{endpoint_key}"] = {"error": str(exc)}
                    continue
                if endpoint_key == "greeks" and not frame.empty:
                    greeks_for_spot.append(frame)
                out_path = output_dir / f"{symbol}_{endpoint_key}_{suffix}_latest.parquet"
                frame.to_parquet(out_path, index=False)
                symbol_summary["files"][f"{suffix}:{endpoint_key}"] = {
                    "path": str(out_path),
                    "rows": int(len(frame)),
                    "columns": int(len(frame.columns)),
                    "errors": list(frame.attrs.get("errors", [])),
                }
        write_spot_from_greeks(output_dir, symbol, greeks_for_spot)
        summary["symbols"][symbol] = symbol_summary
    return summary


def score_registry_coverage(registry_path: Path, snapshots: pd.DataFrame, device: str) -> dict[str, Any]:
    registry = EventOptionComponentRegistry.from_path(registry_path)
    out: dict[str, Any] = {
        "registry": registry.summary(),
        "snapshot_rows": int(len(snapshots)),
        "snapshot_columns": int(len(snapshots.columns)) if not snapshots.empty else 0,
        "components": {},
    }
    if snapshots.empty:
        return out
    ptdj_snapshots_by_ticker: dict[str, pd.DataFrame] = {}
    for name, component in registry.components.items():
        if component.kind == "event_phys_td_jepa_encoder":
            continue
        component_ticker = str(name).split(".", 1)[0].upper()
        if component_ticker in {"SPX", "SPXW", "SPY", "QQQ"} and "ticker" in snapshots.columns:
            frame = snapshots[snapshots["ticker"].astype(str).str.upper().isin({component_ticker, "SPXW" if component_ticker == "SPX" else component_ticker})].copy()
        else:
            frame = snapshots.copy()
        raw_expiry_modes = (component.metadata.get("args") or {}).get("expiry_modes", [])
        if isinstance(raw_expiry_modes, list) and raw_expiry_modes and "expiry_mode" in frame.columns:
            wanted_expiry_modes = {str(item) for item in raw_expiry_modes}
            frame = frame[frame["expiry_mode"].astype(str).isin(wanted_expiry_modes)].copy()
        if frame.empty:
            out["components"][name] = {
                "kind": component.kind,
                "coverage": registry.feature_coverage(name, frame),
                "skipped": "no snapshot rows for component ticker",
            }
            continue
        if "PTDJ.core_encoder" in component.registry_entry.get("requires_components", []):
            cache_key = component_ticker if component_ticker in {"SPX", "SPXW", "SPY", "QQQ"} else "__all__"
            if cache_key not in ptdj_snapshots_by_ticker:
                ptdj_snapshots_by_ticker[cache_key] = registry.append_phys_td_jepa_features(
                    "PTDJ.core_encoder",
                    frame,
                    strict=False,
                    device=device,
                )
            frame = ptdj_snapshots_by_ticker[cache_key]
        coverage = registry.feature_coverage(name, frame)
        record: dict[str, Any] = {"kind": component.kind, "coverage": coverage}
        try:
            if component.kind == "event_option_gate_direction_model":
                scored = registry.score_event_option_gate_component(name, frame, strict=False)
                record["score_rows"] = int(len(scored))
                record["passes"] = int(scored.get("event_gate_pass", pd.Series(dtype=bool)).astype(bool).sum())
                keep_cols = [c for c in ("ticker", "expiry_mode", "time", "action", "score", "event_gate_pass", "deploy_config") if c in scored.columns]
                record["preview"] = scored[keep_cols].head(8).to_dict("records")
            elif component.kind == "event_trade_union_topk_regressor":
                scored = registry.score_topk_component(name, frame, strict=False)
                record["score_rows"] = int(len(scored))
                record["selected_topk"] = component.selected_topk
            elif component.kind == "event_daily_source_router":
                scored = registry.score_daily_router_sources(name, frame, strict=False)
                record["score_rows"] = int(len(scored))
                keep_cols = [c for c in ("ticker", "expiry_mode", "time", "daily_source", "daily_router_pred_return") if c in scored.columns]
                record["preview"] = scored[keep_cols].head(8).to_dict("records")
        except Exception as exc:
            record["score_error"] = str(exc)
        out["components"][name] = record
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a tiny ThetaData live window and smoke-test event-option snapshots/components.")
    parser.add_argument("--date", default=datetime.now(ET).strftime("%Y%m%d"))
    parser.add_argument("--tickers", nargs="+", default=["SPY", "QQQ", "SPXW"])
    parser.add_argument("--suffixes", nargs="+", default=["0dte", "weekly"], choices=["0dte", "weekly"])
    parser.add_argument("--endpoints", nargs="+", default=["greeks", "oi", "ohlc"], choices=list(OPTIONS_ENDPOINTS))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--window-minutes", type=int, default=20)
    parser.add_argument("--start-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--registry", default="neural/models/jepa/jepa_production_event_options/component_registry.json")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path(tempfile.mkdtemp(prefix="event_option_smoke_"))
    download_summary = write_rt_data_from_thetadata(args, output_dir)
    snapshot_result = build_live_event_option_snapshots(
        output_dir,
        tickers=tuple(str(t).upper() for t in args.tickers),
        suffixes=tuple(str(s).lower() for s in args.suffixes),
    )
    snapshots_path = output_dir / "event_option_snapshots_latest.parquet"
    snapshot_result.rows.to_parquet(snapshots_path, index=False)
    coverage = score_registry_coverage(Path(args.registry), snapshot_result.rows, str(args.device))
    summary = {
        "output_dir": str(output_dir),
        "download": download_summary,
        "snapshots": snapshot_result.summary,
        "snapshots_path": str(snapshots_path),
        "coverage": coverage,
    }
    summary_path = output_dir / "event_option_snapshot_smoke_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=True, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, allow_nan=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
