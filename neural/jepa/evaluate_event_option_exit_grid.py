from __future__ import annotations

import argparse
import json
import math
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_event_option_dataset import load_chain, select_contract


DELTA_RE = re.compile(r"d(\d{2})", re.IGNORECASE)


def parse_time_to_ts(date_value: object, time_value: object) -> pd.Timestamp:
    date_text = str(date_value).replace("-", "")[:8]
    time_text = str(time_value)[:5]
    return pd.to_datetime(f"{date_text} {time_text}", format="%Y%m%d %H:%M", errors="coerce")


def parse_delta_target(row: pd.Series) -> float:
    for col in ["event_delta_bucket", "source_stream", "deploy_config", "event_candidate_id"]:
        if col not in row.index:
            continue
        match = DELTA_RE.search(str(row.get(col, "")))
        if match:
            return float(int(match.group(1))) / 100.0
    return 0.25


def normalize_action(value: object) -> str:
    text = str(value).upper()
    if text.startswith("C"):
        return "CALL"
    if text.startswith("P"):
        return "PUT"
    return text


def normalize_ticker(value: object) -> str:
    ticker = str(value).upper()
    return "SPXW" if ticker == "SPX" else ticker


def profit_factor(returns: pd.Series) -> float:
    vals = pd.to_numeric(returns, errors="coerce").dropna().astype(float)
    gains = float(vals[vals > 0.0].sum())
    losses = float(vals[vals < 0.0].sum())
    if losses == 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / abs(losses)


def metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_return": 0.0,
            "avg_hold_minutes": 0.0,
            "median_hold_minutes": 0.0,
            "min_month_trades": 0,
            "avg_month_trades": 0.0,
        }
    returns = pd.to_numeric(frame["exit_ret"], errors="coerce").astype(float)
    month_counts = frame.groupby("month", sort=True).size()
    return {
        "trades": int(len(frame)),
        "win_rate": float((returns > 0.0).mean()),
        "profit_factor": float(profit_factor(returns)),
        "avg_return": float(returns.mean()),
        "avg_hold_minutes": float(pd.to_numeric(frame["hold_minutes"], errors="coerce").mean()),
        "median_hold_minutes": float(pd.to_numeric(frame["hold_minutes"], errors="coerce").median()),
        "min_month_trades": int(month_counts.min()) if not month_counts.empty else 0,
        "avg_month_trades": float(month_counts.mean()) if not month_counts.empty else 0.0,
    }


def passes_objective(per_ticker: dict[str, dict], min_month_trades: int) -> bool:
    required = {"QQQ", "SPXW", "SPY"}
    if not required.issubset(set(per_ticker)):
        return False
    for ticker in sorted(required):
        item = per_ticker[ticker]
        if float(item.get("avg_hold_minutes", 0.0)) <= 30.0:
            return False
        if float(item.get("profit_factor", 0.0)) <= 1.3:
            return False
        if float(item.get("win_rate", 0.0)) <= 0.48:
            return False
        if int(item.get("min_month_trades", 0)) < int(min_month_trades):
            return False
    return True


def find_snapshot(greeks: pd.DataFrame, ts: pd.Timestamp) -> pd.DataFrame:
    exact = greeks[greeks["dt"].eq(ts)]
    if not exact.empty:
        return exact
    prior_times = greeks.loc[greeks["dt"].le(ts), "dt"]
    if prior_times.empty:
        return greeks.iloc[0:0]
    nearest = prior_times.max()
    if abs((ts - nearest).total_seconds()) > 180:
        return greeks.iloc[0:0]
    return greeks[greeks["dt"].eq(nearest)]


def prepare_trades(runtime_trades: pd.DataFrame, manifest: pd.DataFrame, horizon_minutes: int) -> tuple[pd.DataFrame, dict]:
    manifest_keyed = manifest.copy()
    manifest_keyed["ticker"] = manifest_keyed["ticker"].astype(str).str.upper()
    manifest_keyed["trade_date"] = manifest_keyed["trade_date"].astype(str).str.replace("-", "", regex=False)
    manifest_lookup = {
        (str(row["ticker"]).upper(), str(row["trade_date"]), str(row.get("expiry_mode", "zero_dte"))): row
        for _, row in manifest_keyed.iterrows()
    }

    chain_cache: dict[tuple[str, str, str], tuple[pd.DataFrame, pd.DataFrame]] = {}
    prepared: list[dict] = []
    issues: list[dict] = []

    for idx, raw in runtime_trades.iterrows():
        ticker = normalize_ticker(raw.get("ticker", ""))
        date_value = str(raw.get("date", raw.get("trade_date", ""))).replace("-", "")[:8]
        expiry_mode = str(raw.get("expiry_mode", "zero_dte"))
        ts = parse_time_to_ts(date_value, raw.get("time", ""))
        action = normalize_action(raw.get("action", ""))
        delta_target = parse_delta_target(raw)
        manifest_key = (ticker, date_value, expiry_mode)
        manifest_row = manifest_lookup.get(manifest_key)
        if manifest_row is None:
            issues.append({"row": int(idx), "reason": "missing_manifest", "ticker": ticker, "date": date_value})
            continue
        if pd.isna(ts):
            issues.append({"row": int(idx), "reason": "bad_timestamp", "ticker": ticker, "date": date_value})
            continue

        if manifest_key not in chain_cache:
            chain_cache[manifest_key] = load_chain(pd.Series(manifest_row))
        greeks, ohlc = chain_cache[manifest_key]
        if greeks.empty or ohlc.empty:
            issues.append({"row": int(idx), "reason": "empty_chain", "ticker": ticker, "date": date_value})
            continue
        snapshot = find_snapshot(greeks, ts)
        if snapshot.empty:
            issues.append({"row": int(idx), "reason": "missing_snapshot", "ticker": ticker, "date": date_value, "time": str(raw.get("time", ""))})
            continue
        contract = select_contract(snapshot, action, delta_target)
        if contract is None:
            issues.append({"row": int(idx), "reason": "missing_contract", "ticker": ticker, "date": date_value, "time": str(raw.get("time", "")), "action": action, "delta": delta_target})
            continue

        strike = float(contract["strike"])
        bid = float(contract.get("bid", 0.0) or 0.0)
        ask = float(contract.get("ask", 0.0) or 0.0)
        entry = float(contract.get("opt_close", 0.0) or 0.0)
        if entry <= 0.0 and bid > 0.0 and ask > 0.0:
            entry = (bid + ask) / 2.0
        if entry <= 0.0:
            issues.append({"row": int(idx), "reason": "bad_entry", "ticker": ticker, "date": date_value, "time": str(raw.get("time", "")), "strike": strike})
            continue

        end_ts = ts + pd.Timedelta(minutes=int(horizon_minutes))
        path = ohlc[
            (ohlc["right"].astype(str).eq(action))
            & (np.isclose(ohlc["strike"].astype(float), strike))
            & (ohlc["dt"] > ts)
            & (ohlc["dt"] <= end_ts)
        ].copy()
        path = path[(path["high"].astype(float) > 0.0) | (path["low"].astype(float) > 0.0)].sort_values("dt")
        if path.empty:
            issues.append({"row": int(idx), "reason": "empty_path", "ticker": ticker, "date": date_value, "time": str(raw.get("time", "")), "strike": strike})
            continue

        prepared.append(
            {
                "source_index": int(idx),
                "ticker": ticker,
                "date": date_value,
                "month": date_value[:6],
                "time": str(raw.get("time", ""))[:5],
                "ts": ts,
                "action": action,
                "delta_target": float(delta_target),
                "strike": strike,
                "entry": float(entry),
                "actual_delta_abs": float(abs(float(contract.get("delta", np.nan)))),
                "expected_realized_return": float(raw.get("realized_return", np.nan)),
                "source_stream": str(raw.get("source_stream", "")),
                "monthly_backfill_role": str(raw.get("monthly_backfill_role", "")),
                "path": path[["dt", "open", "high", "low", "close"]].copy(),
            }
        )
    return pd.DataFrame(prepared), {"issues": issues, "chain_cache_days": len(chain_cache)}


def simulate_prepared(prepared: list[dict] | pd.DataFrame, config: dict) -> pd.DataFrame:
    rows: list[dict] = []
    min_hold = int(config["min_hold_minutes"])
    horizon = int(config["horizon_minutes"])
    tp = float(config["take_profit_pct"])
    sl = abs(float(config["stop_loss_pct"]))
    records = prepared if isinstance(prepared, list) else prepared.to_dict("records")
    for trade in records:
        entry = float(trade["entry"])
        ts = pd.Timestamp(trade["ts"])
        status = 0
        exit_ret = np.nan
        exit_minutes = 0
        exit_reason = "max_hold"
        path = trade["path"]
        last_point = None
        for item in path.itertuples(index=False):
            last_point = item
            elapsed = int((pd.Timestamp(item.dt) - ts).total_seconds() // 60)
            if elapsed < min_hold:
                continue
            high = float(item.high)
            low = float(item.low)
            high_ret = high / entry - 1.0 if high > 0.0 else -float("inf")
            low_ret = low / entry - 1.0 if low > 0.0 else float("inf")
            if low_ret <= -sl:
                status = -1
                exit_ret = -sl
                exit_minutes = elapsed
                exit_reason = "stop_loss"
                break
            if high_ret >= tp:
                status = 1
                exit_ret = tp
                exit_minutes = elapsed
                exit_reason = "take_profit"
                break
            if elapsed >= horizon:
                break
        if status == 0:
            if last_point is None:
                continue
            close = float(last_point.close)
            exit_ret = close / entry - 1.0 if close > 0.0 else np.nan
            exit_minutes = int((pd.Timestamp(last_point.dt) - ts).total_seconds() // 60)
            exit_reason = "max_hold"
            if np.isfinite(exit_ret):
                status = 1 if exit_ret > 0.0 else (-1 if exit_ret < 0.0 else 0)
        row = {key: value for key, value in trade.items() if key != "path"}
        row.update(
            {
                "exit_ret": float(exit_ret) if np.isfinite(exit_ret) else np.nan,
                "hold_minutes": int(exit_minutes),
                "exit_status": int(status),
                "exit_reason": exit_reason,
                **config,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate_grid(prepared: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    prepared_records = prepared.to_dict("records")
    configs: list[dict] = []
    for min_hold in args.min_hold_minutes:
        for stop_loss in args.stop_losses:
            for take_profit in args.take_profits:
                configs.append(
                    {
                        "min_hold_minutes": int(min_hold),
                        "stop_loss_pct": float(stop_loss),
                        "take_profit_pct": float(take_profit),
                        "horizon_minutes": int(args.horizon_minutes),
                    }
                )

    all_rows: list[dict] = []
    best_trades = pd.DataFrame()
    best_score = -float("inf")
    best_summary: dict = {}
    for config in configs:
        trades = simulate_prepared(prepared_records, config)
        overall = metrics(trades)
        per_ticker = {ticker: metrics(part) for ticker, part in trades.groupby("ticker", sort=True)}
        ok = passes_objective(per_ticker, int(args.min_month_trades))
        qqq = per_ticker.get("QQQ", {})
        min_hold_shortfall = sum(max(0.0, 30.0 - float(v.get("avg_hold_minutes", 0.0))) for v in per_ticker.values())
        wr_shortfall = sum(max(0.0, 0.48 - float(v.get("win_rate", 0.0))) for v in per_ticker.values())
        pf_shortfall = sum(max(0.0, 1.3 - float(v.get("profit_factor", 0.0))) for v in per_ticker.values())
        score = (
            (1000000.0 if ok else 0.0)
            + float(overall["avg_return"]) * 100.0
            + float(overall["profit_factor"]) * 10.0
            + float(overall["win_rate"]) * 25.0
            - min_hold_shortfall * 5.0
            - wr_shortfall * 100.0
            - pf_shortfall * 20.0
            + float(qqq.get("win_rate", 0.0)) * 10.0
        )
        row = {
            **config,
            "passes": bool(ok),
            "score": float(score),
            **{f"overall_{k}": v for k, v in overall.items()},
        }
        for ticker, item in per_ticker.items():
            for key, value in item.items():
                row[f"{ticker}_{key}"] = value
        all_rows.append(row)
        if score > best_score:
            best_score = float(score)
            best_trades = trades
            best_summary = {"config": config, "overall": overall, "per_ticker": per_ticker, "passes": bool(ok), "score": float(score)}

    return pd.DataFrame(all_rows).sort_values(["passes", "score"], ascending=[False, False]), best_trades, best_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate event-option exit grids on fixed runtime-replayed entries.")
    parser.add_argument("--runtime-trades", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--horizon-minutes", type=int, default=180)
    parser.add_argument("--min-hold-minutes", nargs="+", type=int, default=[0, 10, 15, 20, 25, 30, 35, 40, 45, 60])
    parser.add_argument("--stop-losses", nargs="+", type=float, default=[0.30, 0.40, 0.50, 0.60, 0.80, 1.00])
    parser.add_argument("--take-profits", nargs="+", type=float, default=[0.50, 0.75, 1.00, 1.50, 2.00])
    parser.add_argument("--min-month-trades", type=int, default=18)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime = pd.read_csv(args.runtime_trades, dtype={"date": str})
    prepared_cache = output_dir / "prepared_trades_with_paths.pkl"
    if prepared_cache.exists():
        with prepared_cache.open("rb") as handle:
            cached = pickle.load(handle)
        prepared = cached["prepared"]
        prep_info = cached["prep_info"]
    else:
        manifest = pd.read_csv(args.manifest, dtype={"trade_date": str, "expiration": str})
        prepared, prep_info = prepare_trades(runtime, manifest, int(args.horizon_minutes))
        with prepared_cache.open("wb") as handle:
            pickle.dump({"prepared": prepared, "prep_info": prep_info}, handle, protocol=pickle.HIGHEST_PROTOCOL)
    if prepared.empty:
        raise SystemExit("No trades could be prepared")

    prepared_out = prepared.drop(columns=["path"]).copy()
    prepared_out.to_csv(output_dir / "prepared_trades.csv", index=False)
    grid, best_trades, best_summary = evaluate_grid(prepared, args)
    grid.to_csv(output_dir / "exit_grid_metrics.csv", index=False)
    best_trades.to_csv(output_dir / "best_exit_grid_trades.csv", index=False)

    baseline = simulate_prepared(
        prepared,
        {
            "min_hold_minutes": 0,
            "stop_loss_pct": 0.30,
            "take_profit_pct": 0.50,
            "horizon_minutes": int(args.horizon_minutes),
        },
    )
    baseline["abs_realized_return_diff"] = (
        pd.to_numeric(baseline["exit_ret"], errors="coerce")
        - pd.to_numeric(baseline["expected_realized_return"], errors="coerce")
    ).abs()
    baseline_summary = {
        "prepared_rows": int(len(prepared)),
        "runtime_rows": int(len(runtime)),
        "missing_rows": int(len(runtime) - len(prepared)),
        "prep_info": prep_info,
        "baseline_metrics": metrics(baseline),
        "baseline_per_ticker": {ticker: metrics(part) for ticker, part in baseline.groupby("ticker", sort=True)},
        "baseline_max_abs_realized_return_diff": float(baseline["abs_realized_return_diff"].max()),
        "baseline_mean_abs_realized_return_diff": float(baseline["abs_realized_return_diff"].mean()),
    }
    summary = {
        "args": vars(args),
        "baseline": baseline_summary,
        "best": best_summary,
        "top10": grid.head(10).replace({np.nan: None}).to_dict("records"),
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
