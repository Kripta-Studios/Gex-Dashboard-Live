"""
Trading Bot - GBT+JEPA 180m + fixed 0.70 delta 0DTE options.

Data source:
    rt_data/{YYYYMMDD}/ produced by services/realtime_feed.py.

Live contract:
    - Direction model: neural/models/jepa/jepa_production_final_180m/base_jepa
    - Entry cadence: 5-minute feature rows, matching the training/backtest sample cadence.
    - Strike selection: buy the 0DTE option whose absolute delta is closest to 0.70.
    - Exit: hard stop -60%, take profit +250%, max hold 180m, EOD cleanup.
    - Cooldown: 180m per ticker after entry/exit, matching the promoted backtest.

This script is an alert/tracker bot. It does not submit broker orders.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

from neural.jepa.jepa_180m_signal import Jepa180mSignalModel

load_dotenv()

ET = ZoneInfo("America/New_York")

TICKERS = ["SPX", "QQQ", "SPY"]
OPTIONS_SYMBOLS = {"SPX": "SPXW", "QQQ": "QQQ", "SPY": "SPY"}
RIGHT_FOR_DIRECTION = {"LONG": "CALL", "SHORT": "PUT"}

DEFAULT_SIGNAL_MODEL_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_final_180m"
DEFAULT_RT_DATA_DIR = PROJECT_ROOT / "rt_data"
DEFAULT_TRADES_DIR = PROJECT_ROOT / "trades_jepa"

MODEL_MODE = "base_jepa"
DELTA_TARGET = 0.70
RISK_CAPITAL = 1000.0
CONTRACT_MULTIPLIER = 100.0
HARD_STOP_PCT = -0.60
TAKE_PROFIT_PCT = 2.50
MAX_HOLD_MINUTES = 180
COOLDOWN_MINUTES = 180
MAX_FEED_SNAPSHOT_AGE_SECONDS = 150
MAX_MODEL_FEATURE_AGE_SECONDS = 390
LOOP_INTERVAL_SECONDS = 65
EOD_CLEANUP_TIME = dt_time(15, 55)

DISCORD_WEBHOOKS = [
    url
    for url in [os.getenv("DISCORD_WEBHOOK_URL"), os.getenv("DISCORD_WEBHOOK_URL_2")]
    if url
]
DISCORD_ROLE_ID = os.getenv("DISCORD_ROLE_ID", "1464601287411634226")
DISCORD_ROLE_PING = os.getenv("DISCORD_ROLE_PING", f"<@&{DISCORD_ROLE_ID}>").strip()


def _now_et() -> datetime:
    return datetime.now(ET)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _normalize_right(value: Any) -> str:
    text = str(value).upper()
    if text in {"C", "CALL"}:
        return "CALL"
    if text in {"P", "PUT"}:
        return "PUT"
    return text


def _format_expiration(value: Any) -> str:
    text = "".join(ch for ch in str(value) if ch.isdigit())
    return text[:8] if len(text) >= 8 else text


def _format_expiration_for_tracker(value: Any) -> str:
    exp = _format_expiration(value)
    try:
        return datetime.strptime(exp, "%Y%m%d").strftime("%m/%d/%y")
    except Exception:
        return ""


def _post_discord(payload: dict[str, Any]) -> None:
    for webhook in DISCORD_WEBHOOKS:
        try:
            requests.post(webhook, json=payload, timeout=10)
        except Exception as exc:
            logging.getLogger(__name__).warning("Discord send failed: %s", exc)


def _send_discord(message: str, ping: bool = True) -> None:
    if not DISCORD_WEBHOOKS:
        return
    content = str(message).lstrip()
    if DISCORD_ROLE_PING and content.startswith(DISCORD_ROLE_PING):
        content = content[len(DISCORD_ROLE_PING) :].lstrip()

    if ping and DISCORD_ROLE_PING:
        ping_payload: dict[str, Any] = {"content": DISCORD_ROLE_PING}
        if DISCORD_ROLE_ID:
            ping_payload["allowed_mentions"] = {"roles": [DISCORD_ROLE_ID]}
        _post_discord(ping_payload)

    if content:
        _post_discord({"content": content})


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


@dataclass
class JepaOptionPosition:
    ticker: str
    direction: str
    right: str
    strike: float
    delta: float
    expiration: str
    entry_time: str
    entry_spot: float
    entry_premium: float
    contracts: int
    confidence: float
    jepa_prob_up: float
    long_threshold: float
    short_threshold: float
    peak_pnl_pct: float = 0.0
    trough_pnl_pct: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict) -> "JepaOptionPosition":
        return cls(
            ticker=str(payload["ticker"]),
            direction=str(payload["direction"]),
            right=str(payload["right"]),
            strike=float(payload["strike"]),
            delta=float(payload["delta"]),
            expiration=str(payload.get("expiration", "")),
            entry_time=str(payload["entry_time"]),
            entry_spot=float(payload["entry_spot"]),
            entry_premium=float(payload["entry_premium"]),
            contracts=int(payload["contracts"]),
            confidence=float(payload.get("confidence", 0.0)),
            jepa_prob_up=float(payload.get("jepa_prob_up", 0.5)),
            long_threshold=float(payload.get("long_threshold", 0.0)),
            short_threshold=float(payload.get("short_threshold", 0.0)),
            peak_pnl_pct=float(payload.get("peak_pnl_pct", 0.0)),
            trough_pnl_pct=float(payload.get("trough_pnl_pct", 0.0)),
        )

    @property
    def entry_dt(self) -> datetime:
        return datetime.fromisoformat(self.entry_time)


class JepaFixedDeltaBot:
    def __init__(
        self,
        model_dir: Path,
        rt_data_dir: Path,
        trades_dir: Path,
        tickers: list[str],
        dry_run: bool = False,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.rt_data_dir = Path(rt_data_dir)
        self.trades_dir = Path(trades_dir)
        self.tickers = [str(t).upper() for t in tickers]
        self.dry_run = bool(dry_run)
        self.positions_path = self.trades_dir / "open_positions_jepa.json"
        self.cooldowns_path = self.trades_dir / "cooldowns_jepa.json"
        self.evaluated_features_path = self.trades_dir / "evaluated_features_jepa.json"
        self.trade_log_path = self.trades_dir / "trades_jepa.csv"
        self.positions: dict[str, JepaOptionPosition] = self._load_positions()
        self.cooldowns: dict[str, str] = _read_json(self.cooldowns_path, {})
        self.evaluated_feature_timestamps: dict[str, str] = _read_json(self.evaluated_features_path, {})
        self.signal_model = Jepa180mSignalModel(self.model_dir, mode=MODEL_MODE, tickers=self.tickers)

    def _load_positions(self) -> dict[str, JepaOptionPosition]:
        payload = _read_json(self.positions_path, {})
        out = {}
        for ticker, item in payload.items():
            try:
                out[str(ticker)] = JepaOptionPosition.from_dict(item)
            except Exception:
                logging.exception("Failed to load JEPA position for %s", ticker)
        return out

    def _save_positions(self) -> None:
        _write_json(self.positions_path, {k: asdict(v) for k, v in self.positions.items()})

    def _save_cooldowns(self) -> None:
        _write_json(self.cooldowns_path, self.cooldowns)

    def _save_evaluated_features(self) -> None:
        _write_json(self.evaluated_features_path, self.evaluated_feature_timestamps)

    def _current_day_dir(self) -> Path:
        return self.rt_data_dir / _now_et().strftime("%Y%m%d")

    @staticmethod
    def _feature_row_id(row: pd.DataFrame) -> str:
        if row.empty:
            return ""
        latest = row.iloc[-1]
        timestamp = latest.get("timestamp")
        if pd.notna(timestamp):
            return str(timestamp)
        date_value = latest.get("date", "")
        minute = latest.get("minutes_since_open", "")
        return f"{date_value}:{minute}"

    def _mark_feature_evaluated(self, ticker: str, feature_id: str) -> None:
        if not feature_id:
            return
        self.evaluated_feature_timestamps[ticker] = feature_id
        self._save_evaluated_features()

    def _read_parquet(self, filename: str, max_age: int = MAX_FEED_SNAPSHOT_AGE_SECONDS) -> pd.DataFrame:
        path = self._current_day_dir() / filename
        if not path.exists():
            return pd.DataFrame()
        age = time.time() - path.stat().st_mtime
        if age > max_age:
            logging.warning("[Feed] stale %s age=%.0fs", filename, age)
            return pd.DataFrame()
        try:
            return pd.read_parquet(path)
        except Exception:
            logging.exception("[Feed] could not read %s", path)
            return pd.DataFrame()

    def _latest_feature_row(self, ticker: str) -> pd.DataFrame:
        df = self._read_parquet(
            f"ml_features_{ticker}_latest.parquet",
            max_age=MAX_MODEL_FEATURE_AGE_SECONDS,
        )
        if df.empty:
            return pd.DataFrame()
        if "xjepa_context_valid" not in df.columns:
            logging.info("[%s] no xjepa_context_valid column yet", ticker)
            return pd.DataFrame()
        row = df.tail(1).copy()
        if float(row["xjepa_context_valid"].iloc[0]) <= 0.0:
            logging.info("[%s] JEPA context not valid yet; needs 24 five-minute rows", ticker)
            return pd.DataFrame()
        return row

    def _latest_spot(self, ticker: str) -> float:
        df = self._read_parquet(f"spot_{ticker}_latest.parquet")
        if df.empty or "close" not in df.columns:
            return 0.0
        return _safe_float(df["close"].iloc[-1])

    def _latest_option_snapshot(self, ticker: str) -> pd.DataFrame:
        symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        df = self._read_parquet(f"{symbol}_greeks_0dte_latest.parquet")
        if df.empty:
            return df
        if "underlying_timestamp" in df.columns:
            dt = pd.to_datetime(df["underlying_timestamp"], format="mixed", errors="coerce")
            latest = dt.max()
            if pd.notna(latest):
                df = df[dt == latest].copy()
        if "right" in df.columns:
            df["right_norm"] = df["right"].map(_normalize_right)
        return df

    def _latest_ohlc_snapshot(self, ticker: str) -> pd.DataFrame:
        symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        df = self._read_parquet(f"{symbol}_ohlc_0dte_latest.parquet")
        if df.empty:
            return df
        time_col = "timestamp" if "timestamp" in df.columns else "underlying_timestamp" if "underlying_timestamp" in df.columns else ""
        if time_col:
            dt = pd.to_datetime(df[time_col], format="mixed", errors="coerce")
            latest = dt.max()
            if pd.notna(latest):
                df = df[dt == latest].copy()
        if "right" in df.columns:
            df["right_norm"] = df["right"].map(_normalize_right)
        return df

    @staticmethod
    def _row_price(row: pd.Series) -> float:
        bid = _safe_float(row.get("bid", 0.0))
        ask = _safe_float(row.get("ask", 0.0))
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        for col in ["mid_price", "mark", "close", "last", "price"]:
            value = _safe_float(row.get(col, 0.0))
            if value > 0:
                return value
        return 0.0

    def _option_price_from_ohlc(self, ticker: str, strike: float, right: str) -> float:
        df = self._latest_ohlc_snapshot(ticker)
        if df.empty or "strike" not in df.columns or "right_norm" not in df.columns:
            return 0.0
        work = df[(df["right_norm"] == right) & (np.isclose(pd.to_numeric(df["strike"], errors="coerce"), strike))]
        if work.empty:
            return 0.0
        return self._row_price(work.iloc[-1])

    def _select_fixed_delta_option(self, ticker: str, direction: str) -> dict | None:
        right = RIGHT_FOR_DIRECTION[direction]
        df = self._latest_option_snapshot(ticker)
        if df.empty or "delta" not in df.columns or "strike" not in df.columns or "right_norm" not in df.columns:
            return None
        work = df[df["right_norm"] == right].copy()
        if work.empty:
            return None
        work["delta_abs"] = pd.to_numeric(work["delta"], errors="coerce").abs()
        work["delta_dist"] = (work["delta_abs"] - DELTA_TARGET).abs()
        work = work.dropna(subset=["delta_dist", "strike"]).sort_values(["delta_dist", "strike"])
        if work.empty:
            return None

        for _, row in work.head(8).iterrows():
            strike = _safe_float(row.get("strike", 0.0))
            if strike <= 0:
                continue
            premium = self._row_price(row)
            if premium <= 0:
                premium = self._option_price_from_ohlc(ticker, strike, right)
            if premium <= 0:
                continue
            return {
                "ticker": ticker,
                "right": right,
                "strike": strike,
                "delta": _safe_float(row.get("delta", 0.0)),
                "premium": premium,
                "expiration": _format_expiration(row.get("expiration", "")),
            }
        return None

    def _current_option_premium(self, pos: JepaOptionPosition) -> float:
        df = self._latest_option_snapshot(pos.ticker)
        if not df.empty and "strike" in df.columns and "right_norm" in df.columns:
            work = df[(df["right_norm"] == pos.right) & (np.isclose(pd.to_numeric(df["strike"], errors="coerce"), pos.strike))]
            if not work.empty:
                price = self._row_price(work.iloc[-1])
                if price > 0:
                    return price
        return self._option_price_from_ohlc(pos.ticker, pos.strike, pos.right)

    def _contracts(self, premium: float) -> int:
        cost = premium * CONTRACT_MULTIPLIER
        if cost <= 0:
            return 0
        return max(1, int(RISK_CAPITAL // cost))

    def _cooldown_active(self, ticker: str, now: datetime) -> bool:
        value = self.cooldowns.get(ticker)
        if not value:
            return False
        try:
            last = datetime.fromisoformat(value)
        except Exception:
            return False
        elapsed = (now - last).total_seconds() / 60.0
        return elapsed < COOLDOWN_MINUTES

    def _record_cooldown(self, ticker: str, now: datetime) -> None:
        self.cooldowns[ticker] = now.isoformat()
        self._save_cooldowns()

    def _append_trade_log(self, row: dict) -> None:
        self.trades_dir.mkdir(parents=True, exist_ok=True)
        exists = self.trade_log_path.exists()
        with self.trade_log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    def _discord_open(self, pos: JepaOptionPosition) -> None:
        right_short = "C" if pos.right == "CALL" else "P"
        exp_fmt = _format_expiration_for_tracker(pos.expiration)
        tracker = f"BTO {pos.ticker} {exp_fmt} {pos.strike:.0f}{right_short} @ M"
        _send_discord(tracker)
        _send_discord(
            f"**[BOT] OPEN {pos.direction} {pos.ticker} {pos.strike:.0f}{right_short}**\n"
            f"prob_up={pos.jepa_prob_up:.3f} conf={pos.confidence:.0%} "
            f"delta={pos.delta:.2f} premium=${pos.entry_premium:.2f} contracts={pos.contracts}\n"
            f"stop={HARD_STOP_PCT:.0%} tp={TAKE_PROFIT_PCT:.0%} max_hold={MAX_HOLD_MINUTES}m",
            ping=False,
        )

    def _discord_close(self, pos: JepaOptionPosition, pnl_pct: float, pnl_dollars: float, hold_min: float, reason: str) -> None:
        right_short = "C" if pos.right == "CALL" else "P"
        exp_fmt = _format_expiration_for_tracker(pos.expiration)
        tracker = f"STC {pos.ticker} {exp_fmt} {pos.strike:.0f}{right_short} @ M"
        _send_discord(tracker)
        _send_discord(
            f"**[BOT] CLOSE {pos.ticker} {pos.strike:.0f}{right_short} {reason}**\n"
            f"pnl={pnl_pct:+.1%} (${pnl_dollars:+.2f}) hold={hold_min:.0f}m",
            ping=False,
        )

    def _close_position(self, ticker: str, premium: float, reason: str, now: datetime) -> None:
        pos = self.positions.pop(ticker)
        pnl_pct = premium / max(pos.entry_premium, 1e-9) - 1.0
        pnl_dollars = pnl_pct * pos.entry_premium * CONTRACT_MULTIPLIER * pos.contracts
        hold_min = (now - pos.entry_dt).total_seconds() / 60.0
        self._record_cooldown(ticker, now)
        self._save_positions()
        self._append_trade_log(
            {
                "date": now.strftime("%Y%m%d"),
                "entry_time": pos.entry_dt.strftime("%H:%M"),
                "exit_time": now.strftime("%H:%M"),
                "ticker": ticker,
                "direction": pos.direction,
                "right": pos.right,
                "strike": pos.strike,
                "delta": pos.delta,
                "entry_premium": pos.entry_premium,
                "exit_premium": premium,
                "contracts": pos.contracts,
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars,
                "hold_minutes": hold_min,
                "exit_reason": reason,
                "source_model": "base_jepa_180m_fixed_delta_0.70",
            }
        )
        logging.info("[%s] CLOSE %s pnl=%+.1f%% $%+.2f hold=%.0fm", ticker, reason, pnl_pct * 100.0, pnl_dollars, hold_min)
        self._discord_close(pos, pnl_pct, pnl_dollars, hold_min, reason)

    def _check_exit(self, ticker: str, now: datetime) -> None:
        pos = self.positions.get(ticker)
        if pos is None:
            return
        premium = self._current_option_premium(pos)
        if premium <= 0:
            logging.warning("[%s] open position but current premium unavailable", ticker)
            return
        pnl_pct = premium / max(pos.entry_premium, 1e-9) - 1.0
        pos.peak_pnl_pct = max(pos.peak_pnl_pct, pnl_pct)
        pos.trough_pnl_pct = min(pos.trough_pnl_pct, pnl_pct)
        hold_min = (now - pos.entry_dt).total_seconds() / 60.0
        self._save_positions()

        if pnl_pct <= HARD_STOP_PCT:
            self._close_position(ticker, premium, "hard_stop_-60pct", now)
        elif pnl_pct >= TAKE_PROFIT_PCT:
            self._close_position(ticker, premium, "take_profit_250pct", now)
        elif hold_min >= MAX_HOLD_MINUTES:
            self._close_position(ticker, premium, "max_hold_180m", now)
        elif now.time() >= EOD_CLEANUP_TIME:
            self._close_position(ticker, premium, "eod_cleanup", now)
        else:
            logging.info("[%s] HOLD option pnl=%+.1f%% hold=%.0fm", ticker, pnl_pct * 100.0, hold_min)

    def _check_entry(self, ticker: str, now: datetime) -> None:
        if ticker in self.positions:
            return
        if now.time() >= EOD_CLEANUP_TIME:
            return
        if self._cooldown_active(ticker, now):
            logging.info("[%s] cooldown active", ticker)
            return

        features = self._latest_feature_row(ticker)
        if features.empty:
            return
        feature_id = self._feature_row_id(features)
        if self.evaluated_feature_timestamps.get(ticker) == feature_id:
            return
        pred = self.signal_model.predict_frame(features).iloc[-1]
        direction_int = int(pred.get("jepa180_direction", 0))
        if direction_int == 0:
            logging.info("[%s] no JEPA signal prob_up=%.3f", ticker, _safe_float(pred.get("jepa180_prob_up", 0.5)))
            self._mark_feature_evaluated(ticker, feature_id)
            return
        direction = "LONG" if direction_int > 0 else "SHORT"
        option = self._select_fixed_delta_option(ticker, direction)
        if option is None:
            logging.warning("[%s] JEPA signal but no fixed 0.70 delta option available", ticker)
            return
        contracts = self._contracts(option["premium"])
        if contracts <= 0:
            logging.warning("[%s] JEPA signal but premium too high/invalid", ticker)
            return
        spot = self._latest_spot(ticker)
        pos = JepaOptionPosition(
            ticker=ticker,
            direction=direction,
            right=option["right"],
            strike=float(option["strike"]),
            delta=float(option["delta"]),
            expiration=str(option["expiration"]),
            entry_time=now.isoformat(),
            entry_spot=float(spot),
            entry_premium=float(option["premium"]),
            contracts=int(contracts),
            confidence=_safe_float(pred.get("jepa180_confidence", 0.0)),
            jepa_prob_up=_safe_float(pred.get("jepa180_prob_up", 0.5)),
            long_threshold=_safe_float(pred.get("jepa180_long_threshold", 0.0)),
            short_threshold=_safe_float(pred.get("jepa180_short_threshold", 0.0)),
        )
        self.positions[ticker] = pos
        self._record_cooldown(ticker, now)
        self._save_positions()
        self._mark_feature_evaluated(ticker, feature_id)
        logging.info(
            "[%s] OPEN %s strike=%.0f delta=%.2f premium=%.2f contracts=%d prob_up=%.3f conf=%.0f%%",
            ticker,
            direction,
            pos.strike,
            pos.delta,
            pos.entry_premium,
            pos.contracts,
            pos.jepa_prob_up,
            pos.confidence * 100.0,
        )
        self._discord_open(pos)

    def run_once(self) -> None:
        now = _now_et()
        for ticker in self.tickers:
            self._check_exit(ticker, now)
        for ticker in self.tickers:
            self._check_entry(ticker, now)

    def is_market_hours(self) -> bool:
        now = _now_et()
        return now.replace(hour=9, minute=30, second=0, microsecond=0) <= now <= now.replace(
            hour=16, minute=0, second=0, microsecond=0
        )

    def run(self, force: bool = False) -> None:
        logging.info("Starting JEPA live bot model_dir=%s rt_data=%s", self.model_dir, self.rt_data_dir)
        while True:
            if force or self.is_market_hours():
                self.run_once()
            else:
                logging.info("Outside market hours; sleeping")
            if self.dry_run:
                break
            time.sleep(LOOP_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live GBT+JEPA 180m + fixed 0.70 delta option bot")
    parser.add_argument("--model-dir", default=str(DEFAULT_SIGNAL_MODEL_DIR))
    parser.add_argument("--rt-data-dir", default=str(DEFAULT_RT_DATA_DIR))
    parser.add_argument("--trades-dir", default=str(DEFAULT_TRADES_DIR))
    parser.add_argument("--tickers", nargs="+", default=TICKERS)
    parser.add_argument("--dry-run", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--force", action="store_true", help="Run outside market hours for diagnostics")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    trades_dir = Path(args.trades_dir)
    trades_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(trades_dir / "tradingbot_jepa.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    bot = JepaFixedDeltaBot(
        model_dir=Path(args.model_dir),
        rt_data_dir=Path(args.rt_data_dir),
        trades_dir=trades_dir,
        tickers=args.tickers,
        dry_run=args.dry_run,
    )
    bot.run(force=args.force)


if __name__ == "__main__":
    main()
