from __future__ import annotations

import argparse
import json
import sys
from datetime import time as dt_time
from pathlib import Path
from types import MethodType
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bots.tradingbot_wrapper_jepa import JepaFixedDeltaBot
from neural.jepa.event_option_component_live import EventOptionComponentRegistry
from neural.jepa.event_option_live_scorer import score_event_option_live_candidates
from neural.jepa.event_option_live_snapshot import build_live_event_option_snapshots


OPTIONS_ROOT = Path(r"D:\ThetaData\data_options")
SPOT_ROOT = Path(r"D:\ThetaData\data_underlying_derived")
OPTIONS_TO_UNDERLYING = {"SPXW": "SPX", "SPY": "SPY", "QQQ": "QQQ"}
BOT_TICKERS = {"SPXW": "SPX", "SPY": "SPY", "QQQ": "QQQ"}


def _parse_cutoff(date: str, cutoff: str) -> pd.Timestamp:
    return pd.Timestamp(f"{date} {cutoff}")


def _month_parts(date: str) -> tuple[str, str]:
    return date[:4], date[4:6]


def _option_file(symbol: str, kind: str, date: str, expiration: str) -> Path:
    year, month = _month_parts(date)
    return OPTIONS_ROOT / symbol / kind / year / month / f"{symbol}_{expiration}_{date}_{kind}.parquet"


def _spot_file(symbol: str, date: str) -> Path:
    year, month = _month_parts(date)
    return SPOT_ROOT / symbol / year / month / f"{symbol}_{date}.parquet"


def _read_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def _filter_time(frame: pd.DataFrame, cutoff: pd.Timestamp, columns: tuple[str, ...]) -> pd.DataFrame:
    out = frame.copy()
    time_col = next((col for col in columns if col in out.columns), "")
    if not time_col:
        return out
    parsed = pd.to_datetime(out[time_col], format="mixed", errors="coerce")
    out = out[parsed <= cutoff].copy()
    return out


def prepare_live_day_dir(
    *,
    output_root: Path,
    date: str,
    cutoff: str,
    tickers: list[str],
) -> Path:
    cutoff_ts = _parse_cutoff(date, cutoff)
    day_dir = output_root / date
    day_dir.mkdir(parents=True, exist_ok=True)
    for symbol in tickers:
        expiration = date
        greeks = _filter_time(
            _read_required(_option_file(symbol, "greeks", date, expiration)),
            cutoff_ts,
            ("underlying_timestamp", "timestamp"),
        )
        ohlc = _filter_time(
            _read_required(_option_file(symbol, "ohlc", date, expiration)),
            cutoff_ts,
            ("timestamp", "underlying_timestamp"),
        )
        oi = _read_required(_option_file(symbol, "oi", date, expiration))
        if greeks.empty:
            raise RuntimeError(f"{symbol}: greeks empty through {cutoff}")
        if ohlc.empty:
            raise RuntimeError(f"{symbol}: ohlc empty through {cutoff}")
        greeks.to_parquet(day_dir / f"{symbol}_greeks_0dte_latest.parquet", index=False)
        ohlc.to_parquet(day_dir / f"{symbol}_ohlc_0dte_latest.parquet", index=False)
        oi.to_parquet(day_dir / f"{symbol}_oi_0dte_latest.parquet", index=False)

        underlying = OPTIONS_TO_UNDERLYING[symbol]
        spot_source = "SPXW" if underlying == "SPX" and not _spot_file("SPX", date).exists() else underlying
        spot = _filter_time(_read_required(_spot_file(spot_source, date)), cutoff_ts, ("timestamp", "time"))
        if spot.empty:
            raise RuntimeError(f"{symbol}: spot empty through {cutoff}")
        spot.to_parquet(day_dir / f"spot_{underlying}_latest.parquet", index=False)
    return day_dir


def _load_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _bot_for_day(day_dir: Path, registry: EventOptionComponentRegistry, policy: dict[str, Any]) -> JepaFixedDeltaBot:
    bot = object.__new__(JepaFixedDeltaBot)
    bot._current_day_dir = MethodType(lambda self: day_dir, bot)
    bot.trades_dir = day_dir
    bot.event_option_state = {"entries": [], "candidate_ids": []}
    bot.event_option_state_path = day_dir / "__smoke_event_option_runtime_state.json"
    bot.event_option_policy = policy
    bot.event_option_components = registry
    bot.trade_log_path = day_dir / "__smoke_trades_jepa.csv"
    bot.latest_entry_time = dt_time(14, 30)
    return bot


def _record_entry(bot: JepaFixedDeltaBot, row: pd.Series, option: dict[str, Any]) -> None:
    entries = bot.event_option_state.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    entries.append(
        {
            "entry_time": str(row.get("timestamp", "")),
            "date": str(row.get("date", row.get("trade_date", ""))),
            "time": str(row.get("time", "")),
            "policy_ticker": str(row.get("policy_ticker", "")),
            "bot_ticker": str(row.get("bot_ticker", option.get("ticker", ""))),
            "event_candidate_id": str(row.get("event_candidate_id", "")),
            "monthly_backfill_role": str(row.get("monthly_backfill_role", "")),
            "source_stream": str(row.get("source_stream", "")),
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


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    tickers = [str(t).upper() for t in args.tickers]
    day_dir = prepare_live_day_dir(
        output_root=Path(args.output_dir) / "rt_day",
        date=str(args.date),
        cutoff=str(args.cutoff),
        tickers=tickers,
    )
    snapshot = build_live_event_option_snapshots(day_dir, tickers=tuple(tickers), suffixes=("0dte",))
    snapshot_path = Path(args.output_dir) / "event_option_snapshots_latest.parquet"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.rows.to_parquet(snapshot_path, index=False)
    (Path(args.output_dir) / "event_option_snapshots_latest.summary.json").write_text(
        json.dumps(snapshot.summary, indent=2, allow_nan=True), encoding="utf-8"
    )

    registry = EventOptionComponentRegistry.from_path(Path(args.registry), project_root=PROJECT_ROOT)
    policy = _load_policy(Path(args.policy))
    candidates, issues, enriched = score_event_option_live_candidates(
        registry,
        snapshot.rows,
        strict_features=bool(args.strict_features),
    )
    enriched.to_parquet(Path(args.output_dir) / "event_option_snapshots_enriched.parquet", index=False)
    if not candidates.empty:
        candidates.to_parquet(Path(args.output_dir) / "event_option_live_candidates.parquet", index=False)
        candidates.to_csv(Path(args.output_dir) / "event_option_live_candidates.csv", index=False)

    bot = _bot_for_day(day_dir, registry, policy)
    selections: list[dict[str, Any]] = []
    for symbol in tickers:
        bot_ticker = BOT_TICKERS[symbol]
        row = bot._select_event_option_candidate(bot_ticker, candidates, pd.Timestamp(f"{args.date} {args.cutoff}").to_pydatetime())
        if row is None:
            selections.append({"ticker": bot_ticker, "selected": False, "reason": "no_candidate"})
            continue
        option = bot._select_event_option_option(bot_ticker, row)
        if option is None:
            selections.append(
                {
                    "ticker": bot_ticker,
                    "policy_ticker": str(row.get("policy_ticker", "")),
                    "selected": False,
                    "reason": "candidate_but_no_contract",
                    "action": str(row.get("action", "")),
                    "source_stream": str(row.get("source_stream", "")),
                }
            )
            continue
        _record_entry(bot, row, option)
        selections.append(
            {
                "ticker": bot_ticker,
                "policy_ticker": str(row.get("policy_ticker", "")),
                "selected": True,
                "action": str(row.get("action", "")),
                "source_stream": str(row.get("source_stream", "")),
                "monthly_backfill_role": str(row.get("monthly_backfill_role", "")),
                "event_delta_bucket": str(row.get("event_delta_bucket", "")),
                "score": float(row.get("score", 0.0)),
                "strike": float(option["strike"]),
                "delta": float(option["delta"]),
                "raw_entry_premium": float(option["raw_entry_premium"]),
                "entry_premium": float(option["entry_premium"]),
                "expiration": str(option["expiration"]),
                "selector_policy": str(option["selector_policy"]),
            }
        )

    payload = {
        "schema_version": 1,
        "smoke": "dense_live_snapshot_to_order",
        "date": str(args.date),
        "cutoff": str(args.cutoff),
        "day_dir": str(day_dir),
        "snapshot_summary": snapshot.summary,
        "candidate_rows": int(len(candidates)),
        "candidate_issues": issues,
        "selections": selections,
        "passed": bool(
            snapshot.summary.get("rows", 0) >= len(tickers)
            and not issues
            and all(row.get("selected") for row in selections)
        ),
        "scope": "ThetaData historical files -> live day_dir schema -> event snapshot builder -> candidate registry scorer -> bot delta contract selection",
        "not_covered": [
            "historical OOS fold model equivalence",
            "future deploy-month trading quality",
            "broker/order execution fills",
        ],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test dense event-option live snapshot to bot order selection.")
    parser.add_argument("--date", default="20260515")
    parser.add_argument("--cutoff", default="14:30")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--registry", default="neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/component_registry.json")
    parser.add_argument("--policy", default="neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/event_option_policy.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--strict-features", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = run_smoke(args)
    (output_dir / "snapshot_to_order_smoke.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Dense Live Snapshot-To-Order Smoke",
        "",
        f"- Passed: {payload['passed']}",
        f"- Date/cutoff: {payload['date']} {payload['cutoff']}",
        f"- Snapshot rows: {payload['snapshot_summary'].get('rows', 0)}",
        f"- Candidate rows: {payload['candidate_rows']}",
        "",
        "## Selections",
        "",
        "| Ticker | Selected | Action | Source | Delta Bucket | Strike | Delta | Premium |",
        "| --- | ---: | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in payload["selections"]:
        lines.append(
            f"| {row.get('ticker', '')} | {row.get('selected', False)} | {row.get('action', '')} | "
            f"{row.get('source_stream', '')} | {row.get('event_delta_bucket', '')} | "
            f"{float(row.get('strike', 0.0)):.2f} | {float(row.get('delta', 0.0)):.4f} | "
            f"{float(row.get('entry_premium', 0.0)):.2f} |"
        )
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
