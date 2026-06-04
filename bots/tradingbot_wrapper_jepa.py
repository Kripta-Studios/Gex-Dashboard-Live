"""
Trading Bot - GBT+JEPA 180m + OptionValue blended 0DTE options.

Data source:
    rt_data/{YYYYMMDD}/ produced by services/realtime_feed.py.

Live contract:
    - Direction model: neural/models/jepa/jepa_production_final_180m/base_jepa
    - Entry cadence: 5-minute feature rows, matching the training/backtest sample cadence.
    - Entry window: feature rows through 14:30 ET, with EOD cleanup at the close.
    - Strike selection: OptionValue blended score over 0.10..0.70 delta candidates,
      falling back to the 0.70 delta rule if the OptionValue model is unavailable.
    - Exit: hard stop -60%, trail from +50% with 25% giveback, emergency TP +1000%,
      max hold 180m, EOD cleanup.
    - Cooldown: 180m per ticker after entry, matching the promoted backtest.

This script is an alert/tracker bot. It does not submit broker orders.
"""

from __future__ import annotations

import argparse
import csv
import __main__ as main_module
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

import joblib
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

from neural.jepa.jepa_180m_signal import Jepa180mSignalModel

try:
    import torch
    from neural.jepa.train_option_value_jepa import (
        FeatureScaler,
        OptionValueConfig,
        OptionValueJEPA,
        add_selector_score_bases,
    )

    OPTION_VALUE_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - live dependency guard
    torch = None
    FeatureScaler = None
    OptionValueConfig = None
    OptionValueJEPA = None
    add_selector_score_bases = None
    OPTION_VALUE_IMPORT_ERROR = exc

load_dotenv()

ET = ZoneInfo("America/New_York")

TICKERS = ["SPX", "QQQ", "SPY"]
OPTIONS_SYMBOLS = {"SPX": "SPXW", "QQQ": "QQQ", "SPY": "SPY"}
RIGHT_FOR_DIRECTION = {"LONG": "CALL", "SHORT": "PUT"}

DEFAULT_SIGNAL_MODEL_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_final_180m"
DEFAULT_OPTION_VALUE_MODEL_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_final_option_value"
DEFAULT_RT_DATA_DIR = PROJECT_ROOT / "rt_data"
DEFAULT_TRADES_DIR = PROJECT_ROOT / "trades_jepa"

MODEL_MODE = "base_jepa"
DELTA_TARGET = 0.70
RISK_CAPITAL = 1000.0
CONTRACT_MULTIPLIER = 100.0
HARD_STOP_PCT = -0.60
TAKE_PROFIT_PCT = 10.00
TRAIL_ACTIVATION_PCT = 0.50
TRAIL_DRAWDOWN_PCT = 0.25
MAX_HOLD_MINUTES = 180
COOLDOWN_MINUTES = 180
LATEST_ENTRY_TIME = dt_time(14, 30)
MAX_FEED_SNAPSHOT_AGE_SECONDS = 150
MAX_MODEL_FEATURE_AGE_SECONDS = 390
LOOP_INTERVAL_SECONDS = 65
CRITICAL_LIVE_CONTEXT_FEATURES = [
    "vix_5d_mean",
    "vix_5d_std",
    "atr_5d_norm",
]
EOD_CLEANUP_TIME = dt_time(16, 0)
FIXED_POLICY_NAME = "base_jepa_180m_fixed_delta_0.70_trail050_025_cutoff1430"
OPTION_VALUE_POLICY_NAME = "base_jepa_180m_option_value_blended_trail050_025_cutoff1430"
OPTION_VALUE_SCORE_BASE = "ovjepa_pred_rule_best_mean"
OPTION_VALUE_DELTA_BONUS = 2.0
OPTION_VALUE_MIN_DELTA_ABS = 0.0
OPTION_VALUE_DELTA_TARGETS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]

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
    raw_entry_premium: float
    entry_spread_pct: float
    contracts: int
    confidence: float
    jepa_prob_up: float
    long_threshold: float
    short_threshold: float
    selector_policy: str = FIXED_POLICY_NAME
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
            raw_entry_premium=float(payload.get("raw_entry_premium", payload.get("entry_premium", 0.0))),
            entry_spread_pct=float(payload.get("entry_spread_pct", 0.0)),
            contracts=int(payload["contracts"]),
            confidence=float(payload.get("confidence", 0.0)),
            jepa_prob_up=float(payload.get("jepa_prob_up", 0.5)),
            long_threshold=float(payload.get("long_threshold", 0.0)),
            short_threshold=float(payload.get("short_threshold", 0.0)),
            selector_policy=str(payload.get("selector_policy", FIXED_POLICY_NAME)),
            peak_pnl_pct=float(payload.get("peak_pnl_pct", 0.0)),
            trough_pnl_pct=float(payload.get("trough_pnl_pct", 0.0)),
        )

    @property
    def entry_dt(self) -> datetime:
        return datetime.fromisoformat(self.entry_time)


class OptionValueLiveSelector:
    @staticmethod
    def _coerce_scalers(raw_scalers: dict) -> dict:
        scalers = {}
        for name, scaler in raw_scalers.items():
            if hasattr(scaler, "transform"):
                scalers[name] = scaler
            elif isinstance(scaler, dict) and {"features", "median", "scale"}.issubset(scaler):
                scalers[name] = FeatureScaler(
                    features=list(scaler["features"]),
                    median={str(k): float(v) for k, v in dict(scaler["median"]).items()},
                    scale={str(k): float(v) for k, v in dict(scaler["scale"]).items()},
                )
            else:
                raise TypeError(f"Unsupported OptionValue scaler payload for {name}: {type(scaler).__name__}")
        return scalers

    def __init__(self, model_dir: Path, device: str = "auto") -> None:
        if OPTION_VALUE_IMPORT_ERROR is not None:
            raise RuntimeError(f"OptionValue imports unavailable: {OPTION_VALUE_IMPORT_ERROR}")
        self.model_dir = Path(model_dir)
        model_path = self.model_dir / "option_value_jepa.pt"
        scalers_path = self.model_dir / "option_value_jepa_scalers.joblib"
        if not model_path.exists():
            raise FileNotFoundError(model_path)
        if not scalers_path.exists():
            raise FileNotFoundError(scalers_path)

        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        checkpoint = torch.load(model_path, map_location="cpu")
        config = OptionValueConfig(**checkpoint["config"])
        self.model = OptionValueJEPA(config).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()
        if FeatureScaler is not None and not hasattr(main_module, "FeatureScaler"):
            setattr(main_module, "FeatureScaler", FeatureScaler)
        self.scalers = self._coerce_scalers(joblib.load(scalers_path))

    def predict(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty:
            return candidates.copy()
        out = candidates.copy()
        market = torch.from_numpy(self.scalers["market"].transform(out)).to(self.device)
        option = torch.from_numpy(self.scalers["option"].transform(out)).to(self.device)
        horizon = torch.ones((len(out), 1), dtype=torch.float32, device=self.device)
        with torch.no_grad():
            pred = self.model.forward_entry(market, option, horizon).detach().cpu().numpy()
        out["ovjepa_pred_hold180"] = pred[:, 0]
        out["ovjepa_pred_rule"] = pred[:, 1]
        out["ovjepa_pred_best"] = pred[:, 2]
        return add_selector_score_bases(out)

    def select(self, candidates: pd.DataFrame) -> pd.Series | None:
        pred = self.predict(candidates)
        if pred.empty or OPTION_VALUE_SCORE_BASE not in pred.columns:
            return None
        work = pred.copy()
        if OPTION_VALUE_MIN_DELTA_ABS > 0.0:
            work = work[work["actual_delta_abs"].astype(float) >= OPTION_VALUE_MIN_DELTA_ABS].copy()
        if work.empty:
            return None
        work["_selector_score"] = (
            work[OPTION_VALUE_SCORE_BASE].astype(float)
            + OPTION_VALUE_DELTA_BONUS * work["actual_delta_abs"].astype(float)
        )
        return work.sort_values("_selector_score").iloc[-1]


class JepaFixedDeltaBot:
    def __init__(
        self,
        model_dir: Path,
        option_value_model_dir: Path | None,
        option_value_device: str,
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
        self.option_value_selector = self._load_option_value_selector(option_value_model_dir, option_value_device)

    def _load_option_value_selector(self, model_dir: Path | None, device: str) -> OptionValueLiveSelector | None:
        if model_dir is None:
            logging.info("OptionValue live selector disabled; using fixed delta %.2f", DELTA_TARGET)
            return None
        try:
            selector = OptionValueLiveSelector(Path(model_dir), device=device)
            logging.info(
                "Loaded OptionValue live selector model_dir=%s score=%s + %.2f*abs_delta",
                model_dir,
                OPTION_VALUE_SCORE_BASE,
                OPTION_VALUE_DELTA_BONUS,
            )
            return selector
        except Exception as exc:
            logging.warning("OptionValue selector unavailable (%s); falling back to fixed delta %.2f", exc, DELTA_TARGET)
            return None

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

    @staticmethod
    def _feature_entry_time(row: pd.DataFrame) -> dt_time | None:
        if row.empty:
            return None
        latest = row.iloc[-1]
        value = latest.get("time")
        if pd.notna(value):
            try:
                hour, minute = str(value)[:5].split(":")
                return dt_time(int(hour), int(minute))
            except Exception:
                pass
        minute_value = _safe_float(latest.get("minutes_since_open", float("nan")), float("nan"))
        if math.isfinite(minute_value):
            total_minutes = 9 * 60 + 30 + int(round(minute_value))
            return dt_time(total_minutes // 60, total_minutes % 60)
        return None

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

        # Safety guard: xjepa_context_valid only proves the JEPA sequence has
        # enough same-day 5-minute rows.  It does not prove the base live
        # context features match the OOS/production-training feature contract.
        # Do not open entries if the feed has not populated the historical
        # context features that the model used in training.  This guard only
        # affects entries; exits/position management are handled elsewhere.
        if "live_feature_context_valid" not in row.columns:
            logging.info("[%s] live_feature_context_valid missing; skipping entry", ticker)
            return pd.DataFrame()
        if _safe_float(row["live_feature_context_valid"].iloc[0], 0.0) <= 0.0:
            bad = []
            for col in CRITICAL_LIVE_CONTEXT_FEATURES:
                if col not in row.columns or _safe_float(row[col].iloc[0], 0.0) <= 0.0:
                    bad.append(col)
            logging.info(
                "[%s] live feature context not valid; skipping entry bad=%s",
                ticker,
                bad or ["live_feature_context_valid"],
            )
            return pd.DataFrame()

        bad = [
            col for col in CRITICAL_LIVE_CONTEXT_FEATURES
            if col not in row.columns or _safe_float(row[col].iloc[0], 0.0) <= 0.0
        ]
        if bad:
            logging.info("[%s] zero/invalid critical live features; skipping entry bad=%s", ticker, bad)
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
        if bid > 0 or ask > 0:
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
        work = work[work["delta_abs"] > 0.01].copy()
        if "bid" in work.columns:
            work = work[pd.to_numeric(work["bid"], errors="coerce") > 0].copy()
        if work.empty:
            return None
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
                "selector_policy": FIXED_POLICY_NAME,
            }
        return None

    def _option_value_candidates(self, ticker: str, direction: str, features: pd.DataFrame) -> pd.DataFrame:
        if features.empty:
            return pd.DataFrame()
        right = RIGHT_FOR_DIRECTION[direction]
        df = self._latest_option_snapshot(ticker)
        if df.empty or "delta" not in df.columns or "strike" not in df.columns or "right_norm" not in df.columns:
            return pd.DataFrame()
        work = df[df["right_norm"] == right].copy()
        if work.empty:
            return pd.DataFrame()
        work["delta_abs"] = pd.to_numeric(work["delta"], errors="coerce").abs()
        work = work[work["delta_abs"] > 0.01].copy()
        if "bid" in work.columns:
            work = work[pd.to_numeric(work["bid"], errors="coerce") > 0].copy()
        if work.empty:
            return pd.DataFrame()

        feature_row = features.iloc[-1].to_dict()
        spot = self._latest_spot(ticker)
        if spot <= 0:
            spot = _safe_float(feature_row.get("spot_price", 0.0), 0.0)
        now = _now_et()
        date_value = str(feature_row.get("date", now.strftime("%Y%m%d")))
        time_value = str(feature_row.get("time", now.strftime("%H:%M")))
        rows: list[dict[str, Any]] = []
        for delta_target in OPTION_VALUE_DELTA_TARGETS:
            target_work = work.copy()
            target_work["delta_dist"] = (target_work["delta_abs"] - float(delta_target)).abs()
            target_work = target_work.dropna(subset=["delta_dist", "strike"]).sort_values(["delta_dist", "strike"])
            for _, chain_row in target_work.head(8).iterrows():
                strike = _safe_float(chain_row.get("strike", 0.0))
                if strike <= 0:
                    continue
                raw_premium = self._row_price(chain_row)
                if raw_premium <= 0:
                    raw_premium = self._option_price_from_ohlc(ticker, strike, right)
                if raw_premium <= 0:
                    continue
                actual_delta = _safe_float(chain_row.get("delta", 0.0))
                actual_delta_abs = abs(actual_delta)
                entry_spread_pct = self._entry_spread_pct(actual_delta_abs, features)
                entry_premium = raw_premium * (1.0 + entry_spread_pct)
                contracts = self._contracts(entry_premium)
                if contracts <= 0:
                    continue
                actual_iv = _safe_float(
                    chain_row.get("implied_vol", chain_row.get("implied_volatility", chain_row.get("iv", 0.15))),
                    0.15,
                )
                actual_theta = _safe_float(chain_row.get("theta", 0.0), 0.0)
                actual_gamma = _safe_float(chain_row.get("gamma", 0.0), 0.0)
                candidate = dict(feature_row)
                candidate.update(
                    {
                        "ticker": ticker,
                        "date": date_value,
                        "month": date_value[:6],
                        "time": time_value[:5],
                        "side": direction,
                        "ticker_SPX": 1.0 if ticker == "SPX" else 0.0,
                        "ticker_QQQ": 1.0 if ticker == "QQQ" else 0.0,
                        "ticker_SPY": 1.0 if ticker == "SPY" else 0.0,
                        "side_LONG": 1.0 if direction == "LONG" else 0.0,
                        "side_SHORT": 1.0 if direction == "SHORT" else 0.0,
                        "spot_price": spot,
                        "delta_target": float(delta_target),
                        "actual_strike": strike,
                        "strike": strike,
                        "right": right,
                        "expiration": _format_expiration(chain_row.get("expiration", "")),
                        "contracts": int(contracts),
                        "entry_cost_dollars": entry_premium * CONTRACT_MULTIPLIER * contracts,
                        "actual_delta": actual_delta,
                        "actual_delta_abs": actual_delta_abs,
                        "entry_premium": entry_premium,
                        "raw_entry_premium": raw_premium,
                        "premium": raw_premium,
                        "entry_spread_pct": entry_spread_pct,
                        "premium_to_spot_bps": entry_premium / max(spot, 1e-9) * 10000.0,
                        "strike_distance_pts": strike - spot,
                        "strike_distance_bps": (strike - spot) / max(spot, 1e-9) * 10000.0,
                        "actual_iv": actual_iv,
                        "actual_theta": actual_theta,
                        "actual_gamma": actual_gamma,
                        "theta_over_premium": actual_theta / max(entry_premium, 1e-9),
                        "gamma_notional": actual_gamma * spot * CONTRACT_MULTIPLIER * contracts,
                    }
                )
                rows.append(candidate)
                break
        return pd.DataFrame(rows)

    def _select_option_value_option(self, ticker: str, direction: str, features: pd.DataFrame) -> dict | None:
        if self.option_value_selector is None:
            return None
        candidates = self._option_value_candidates(ticker, direction, features)
        selected = self.option_value_selector.select(candidates)
        if selected is None:
            return None
        return {
            "ticker": ticker,
            "right": str(selected["right"]),
            "strike": float(selected["strike"]),
            "delta": float(selected["actual_delta"]),
            "premium": float(selected["raw_entry_premium"]),
            "entry_premium": float(selected["entry_premium"]),
            "raw_entry_premium": float(selected["raw_entry_premium"]),
            "entry_spread_pct": float(selected["entry_spread_pct"]),
            "expiration": str(selected.get("expiration", "")),
            "selector_policy": OPTION_VALUE_POLICY_NAME,
            "selector_score": _safe_float(selected.get("_selector_score", 0.0), 0.0),
            "ovjepa_pred_hold180": _safe_float(selected.get("ovjepa_pred_hold180", 0.0), 0.0),
            "ovjepa_pred_rule": _safe_float(selected.get("ovjepa_pred_rule", 0.0), 0.0),
            "ovjepa_pred_best": _safe_float(selected.get("ovjepa_pred_best", 0.0), 0.0),
        }

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

    @staticmethod
    def _entry_spread_pct(abs_delta: float, features: pd.DataFrame) -> float:
        abs_delta = abs(float(abs_delta))
        if abs_delta < 0.30:
            spread = 0.03
        elif abs_delta > 0.60:
            spread = 0.01
        else:
            spread = 0.015
        gamma_speed = 0.0
        if not features.empty and "gamma_speed" in features.columns:
            gamma_speed = _safe_float(features.iloc[-1].get("gamma_speed", 0.0), 0.0)
        return float(spread) * (1.0 + 0.5 * abs(gamma_speed))

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
            f"stop={HARD_STOP_PCT:.0%} trail={TRAIL_ACTIVATION_PCT:.0%}/"
            f"{TRAIL_DRAWDOWN_PCT:.0%} tp={TAKE_PROFIT_PCT:.0%} "
            f"cutoff={LATEST_ENTRY_TIME.strftime('%H:%M')} max_hold={MAX_HOLD_MINUTES}m\n"
            f"policy={pos.selector_policy}",
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
                "peak_pnl_pct": pos.peak_pnl_pct,
                "trough_pnl_pct": pos.trough_pnl_pct,
                "source_model": pos.selector_policy,
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
        elif pos.peak_pnl_pct >= TRAIL_ACTIVATION_PCT and pnl_pct <= pos.peak_pnl_pct - TRAIL_DRAWDOWN_PCT:
            self._close_position(ticker, premium, "trail_stop_50pct_25pct_giveback", now)
        elif pnl_pct >= TAKE_PROFIT_PCT:
            self._close_position(ticker, premium, "take_profit_1000pct", now)
        elif hold_min >= MAX_HOLD_MINUTES:
            self._close_position(ticker, premium, "max_hold_180m", now)
        elif now.time() >= EOD_CLEANUP_TIME:
            self._close_position(ticker, premium, "eod_cleanup", now)
        else:
            giveback = pos.peak_pnl_pct - pnl_pct
            logging.info(
                "[%s] HOLD option pnl=%+.1f%% peak=%+.1f%% giveback=%.1f%% hold=%.0fm",
                ticker,
                pnl_pct * 100.0,
                pos.peak_pnl_pct * 100.0,
                giveback * 100.0,
                hold_min,
            )

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
        feature_time = self._feature_entry_time(features)
        if feature_time is not None and feature_time > LATEST_ENTRY_TIME:
            logging.info("[%s] feature row %s past live entry window", ticker, feature_time.strftime("%H:%M"))
            self._mark_feature_evaluated(ticker, feature_id)
            return
        pred = self.signal_model.predict_frame(features).iloc[-1]
        direction_int = int(pred.get("jepa180_direction", 0))
        if direction_int == 0:
            logging.info("[%s] no JEPA signal prob_up=%.3f", ticker, _safe_float(pred.get("jepa180_prob_up", 0.5)))
            self._mark_feature_evaluated(ticker, feature_id)
            return
        direction = "LONG" if direction_int > 0 else "SHORT"
        option = self._select_option_value_option(ticker, direction, features)
        if option is None:
            option = self._select_fixed_delta_option(ticker, direction)
        if option is None:
            logging.warning("[%s] JEPA signal but no valid 0DTE option candidate available", ticker)
            return
        raw_entry_premium = float(option.get("raw_entry_premium", option["premium"]))
        entry_spread_pct = float(
            option.get("entry_spread_pct", self._entry_spread_pct(abs(float(option["delta"])), features))
        )
        entry_premium = float(option.get("entry_premium", raw_entry_premium * (1.0 + entry_spread_pct)))
        contracts = self._contracts(entry_premium)
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
            entry_premium=float(entry_premium),
            raw_entry_premium=float(raw_entry_premium),
            entry_spread_pct=float(entry_spread_pct),
            contracts=int(contracts),
            confidence=_safe_float(pred.get("jepa180_confidence", 0.0)),
            jepa_prob_up=_safe_float(pred.get("jepa180_prob_up", 0.5)),
            long_threshold=_safe_float(pred.get("jepa180_long_threshold", 0.0)),
            short_threshold=_safe_float(pred.get("jepa180_short_threshold", 0.0)),
            selector_policy=str(option.get("selector_policy", FIXED_POLICY_NAME)),
        )
        self.positions[ticker] = pos
        self._record_cooldown(ticker, now)
        self._save_positions()
        self._mark_feature_evaluated(ticker, feature_id)
        logging.info(
            "[%s] OPEN %s strike=%.0f delta=%.2f premium=%.2f contracts=%d prob_up=%.3f conf=%.0f%% policy=%s",
            ticker,
            direction,
            pos.strike,
            pos.delta,
            pos.entry_premium,
            pos.contracts,
            pos.jepa_prob_up,
            pos.confidence * 100.0,
            pos.selector_policy,
        )
        self._discord_open(pos)
        time.sleep(3)

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
        logging.info(
            "Starting JEPA live bot model_dir=%s rt_data=%s policy=%s cutoff=%s stop=%.0f%% trail=%.0f%%/%.0f%% tp=%.0f%%",
            self.model_dir,
            self.rt_data_dir,
            OPTION_VALUE_POLICY_NAME if self.option_value_selector is not None else FIXED_POLICY_NAME,
            LATEST_ENTRY_TIME.strftime("%H:%M"),
            HARD_STOP_PCT * 100.0,
            TRAIL_ACTIVATION_PCT * 100.0,
            TRAIL_DRAWDOWN_PCT * 100.0,
            TAKE_PROFIT_PCT * 100.0,
        )
        while True:
            if force or self.is_market_hours() or self.positions:
                self.run_once()
            else:
                logging.info("Outside market hours; sleeping")
            if self.dry_run:
                break
            time.sleep(LOOP_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live GBT+JEPA 180m + OptionValue/fixed-delta option bot")
    parser.add_argument("--model-dir", default=str(DEFAULT_SIGNAL_MODEL_DIR))
    parser.add_argument("--option-value-model-dir", default=str(DEFAULT_OPTION_VALUE_MODEL_DIR))
    parser.add_argument("--option-value-device", default="auto", help="OptionValue device: auto, cpu, cuda")
    parser.add_argument("--disable-option-value", action="store_true", help="Use fixed 0.70 delta even if OptionValue is available")
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
        option_value_model_dir=None if args.disable_option_value else Path(args.option_value_model_dir),
        option_value_device=args.option_value_device,
        rt_data_dir=Path(args.rt_data_dir),
        trades_dir=trades_dir,
        tickers=args.tickers,
        dry_run=args.dry_run,
    )
    bot.run(force=args.force)


if __name__ == "__main__":
    main()
