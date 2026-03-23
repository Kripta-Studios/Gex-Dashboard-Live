"""
Trading Bot — GBM + RL Agent — Parquet-based Data Pipeline

Uses IntegratedTradingSystem: GBM signals + RL execution (strike selection + exit).
Data source: rt_data/ Parquet files produced by services/realtime_feed.py.
Discord messages: no emoji, essential info only.

Usage:
    python bots/tradingbot_wrapper_rl.py
"""

import os
import sys
import json
import time
import math
import asyncio
import requests
import logging
import numpy as np
import pandas as pd
import torch
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import deque
import calendar
from scipy.signal import hilbert as scipy_hilbert

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "thetadata-api"))

from dotenv import load_dotenv
from neural.hybrid_model import get_hybrid_model, FEATURE_COLUMNS, get_device, load_ensemble_model
from neural.gbt_model import load_gbt_ensemble
from neural.rl.agent import PPOAgent
from neural.rl.integration import IntegratedTradingSystem
from neural.rl.config import STRIKE_BUCKETS, HARD_EXITS, RL_CONFIG
from services.compute_features import (
    get_net_exposures_from_parquet, calculate_exact_t, extract_feature_vector,
    compute_wonham_filter,
    safe_log, dist_bps, is_near_level, classify_gamma_regime, sign_divergence,
    simple_rsi, calculate_fibonacci_levels, rbf_confluence
)

load_dotenv()

ET = ZoneInfo("America/New_York")

# ── Configuration ──
MODEL_PATH = os.path.join(PROJECT_ROOT, "neural/models", "trading_hybrid_wf.joblib")
NORMALIZER_PATH = os.path.join(PROJECT_ROOT, "neural/models", "hybrid_normalizer_wf.npz")
RL_MODEL_PATH = os.path.join(PROJECT_ROOT, "rl_models", "best_rl_agent.pt")
TRADES_DIR = os.path.join(PROJECT_ROOT, "trades_rl")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
POSITIONS_FILE = os.path.join(TRADES_DIR, "open_positions_rl.json")
GBM_TRACKERS_FILE = os.path.join(TRADES_DIR, "open_gbm_trackers.json")
RT_DATA_DIR = os.path.join(PROJECT_ROOT, "rt_data")

# GBM signal confidence threshold
GBM_MIN_CONFIDENCE = 0.50

os.makedirs(TRADES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Discord
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_ROLE_PING = os.getenv("DISCORD_ROLE_PING", "<@&1464601287411634226>")
DISCORD_ENABLED = bool(DISCORD_WEBHOOK_URL)

# Process both SPX and QQQ
TICKERS = ["SPX", "QQQ"]
POINT_VALUES = {"SPX": 50.0, "SPY": 100.0, "QQQ": 100.0}
MODEL_SIZE = "small"

# Map trading ticker → options symbol (matches training data)
OPTIONS_SYMBOLS = {
    "SPX": "SPXW",  # SPX uses SPXW options
    "QQQ": "QQQ",   # QQQ uses QQQ options directly
}

# Spot source symbol (for underlying derived data)
SPOT_SOURCES = {
    "SPX": "SPX",   # SPX uses SPXW underlying derived
    "QQQ": "QQQ",   # QQQ uses QQQ underlying derived
}

# Timing
LOOP_INTERVAL = 65  # seconds — aligned with realtime_feed's 60s poll interval
COOLDOWN_MINUTES = 5

# GBM Spot-Based TP/SL Configuration (mirrors backtest_rl.py simulate_mlp_only)
GBM_TARGET_LONG = 0.010       # +1.0% spot move target for LONG
GBM_TARGET_SHORT = 0.010      # +1.0% spot move target for SHORT
GBM_STOP_PCT = 0.003          # 0.3% adverse spot move stop loss
GBM_MAX_HOLD_MINUTES = 180    # 3 hours max hold
# IB constants
LEVEL_PROXIMITY_THRESHOLD = 0.0015

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "tradingbot_rl.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════
# DISCORD — MINIMAL, NO EMOJI
# ═════════════════════════════════════════════════════════════════════════

def discord_open(ticker: str, direction: str, strike: float, delta: float,
                 confidence: float, sigma_min: float, entry_premium: float,
                 bucket: str):
    """Send trade OPEN alert — clean, no emoji. Tagged [RL]."""
    if not DISCORD_ENABLED:
        return
    right = "C" if direction == "LONG" else "P"
    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[RL] OPEN {direction} {ticker} {strike:.0f}{right} ({delta:.2f}D)**\n"
        f"Confidence: {confidence:.0%} | Sigma: {sigma_min:.0f}min | Bucket: {bucket}\n"
        f"Entry premium: ${entry_premium:.2f} | Hard stop: {HARD_EXITS['max_loss_pct']:.0%} | Max hold: {HARD_EXITS['max_hold_minutes']}min"
    )
    _send(msg)


def discord_close(ticker: str, direction: str, strike: float,
                  pnl_pct: float, pnl_dollars: float, hold_min: float,
                  reason: str):
    """Send trade CLOSE alert — clean, no emoji. Tagged [RL]."""
    if not DISCORD_ENABLED:
        return
    right = "C" if direction == "LONG" else "P"
    result = "WIN" if pnl_pct >= 0 else "LOSS"
    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[RL] CLOSED {ticker} {strike:.0f}{right} — {result}**\n"
        f"P&L: {pnl_pct:+.1%} (${pnl_dollars:+.1f}) | {hold_min:.0f}min | {reason}"
    )
    _send(msg)


def discord_status(message: str):
    """Send status update."""
    if not DISCORD_ENABLED:
        return
    _send(f"[RL Bot] {message}")


def discord_gbm_signal(ticker: str, direction: str, confidence: float,
                       probs: list, rl_direction: str = None):
    """Send GBM signal alert — tagged [GBM]."""
    if not DISCORD_ENABLED:
        return
    prob_str = f"SHORT={probs[0]:.0%} | HOLD={probs[1]:.0%} | LONG={probs[2]:.0%}"
    if rl_direction and rl_direction != "HOLD":
        agree = "AGREE" if direction == rl_direction else "DISAGREE"
        agree_str = f" | RL: {rl_direction} ({agree})"
    else:
        agree_str = ""
    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[GBM] Signal: {direction} {ticker}**\n"
        f"Confidence: {confidence:.0%} | {prob_str}{agree_str}"
    )
    _send(msg)


def discord_gbm_track_open(ticker: str, direction: str, entry_price: float,
                           confidence: float, target_price: float, stop_price: float):
    """Send GBM TP/SL tracking OPEN alert."""
    if not DISCORD_ENABLED:
        return
    msg = (
        f"**[GBM] TRACKING {direction} {ticker} @ {entry_price:.2f}**\n"
        f"Confidence: {confidence:.0%} | "
        f"TP: {target_price:.2f} | SL: {stop_price:.2f} | Max: {GBM_MAX_HOLD_MINUTES}min"
    )
    _send(msg)


def discord_gbm_track_close(ticker: str, direction: str, entry_price: float,
                            exit_price: float, pnl_pct: float, hold_min: float,
                            reason: str):
    """Send GBM TP/SL tracking result alert."""
    if not DISCORD_ENABLED:
        return
    result = "WIN" if pnl_pct >= 0 else "LOSS"
    msg = (
        f"**[GBM] {result} {ticker} @ {exit_price:.2f}**\n"
        f"Entry: {entry_price:.2f} | P&L: {pnl_pct:+.2%} | {hold_min:.0f}min | {reason}"
    )
    _send(msg)


def _send(content: str):
    """Send raw message to Discord webhook."""
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=5)
        if resp.status_code >= 400:
            logger.error(f"Discord webhook error: {resp.status_code}")
    except Exception as e:
        logger.error(f"Discord send failed: {e}")


# ═════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════
# POSITION TRACKING
# ═════════════════════════════════════════════════════════════════════════

class RLPosition:
    """Tracks an open RL-managed position."""
    def __init__(self, ticker, direction, strike, delta, entry_premium,
                 confidence, bucket, entry_time=None, entry_spot=0.0, entry_atm_iv=0.15,
                 mae=0.0, prev_pnl_pct=0.0, bucket_index=4, time_to_target=0.5, log_sigma=0.5, max_unrealized_pnl=0.0):
        self.ticker = ticker
        self.direction = direction
        self.strike = strike
        self.delta = delta
        self.entry_premium = entry_premium
        self.confidence = confidence
        self.bucket = bucket
        self.entry_time = entry_time or datetime.now(ET)
        self.entry_spot = entry_spot
        self.entry_atm_iv = entry_atm_iv
        self.mae = mae
        self.prev_pnl_pct = prev_pnl_pct
        self.bucket_index = bucket_index
        self.time_to_target = time_to_target
        self.log_sigma = log_sigma
        self.max_unrealized_pnl = max_unrealized_pnl

    def to_dict(self):
        return {
            "ticker": self.ticker, "direction": self.direction,
            "strike": self.strike, "delta": self.delta,
            "entry_premium": self.entry_premium,
            "confidence": self.confidence, "bucket": self.bucket,
            "entry_time": self.entry_time.isoformat(),
            "entry_spot": self.entry_spot,
            "entry_atm_iv": self.entry_atm_iv,
            "mae": self.mae,
            "prev_pnl_pct": self.prev_pnl_pct,
            "bucket_index": self.bucket_index,
            "time_to_target": self.time_to_target,
            "log_sigma": self.log_sigma,
            "max_unrealized_pnl": self.max_unrealized_pnl,
        }

    @classmethod
    def from_dict(cls, d):
        pos = cls(d["ticker"], d["direction"], d["strike"], d["delta"],
                  d["entry_premium"], d["confidence"], d["bucket"])
        pos.entry_time = datetime.fromisoformat(d["entry_time"])
        pos.entry_spot = d.get("entry_spot", 0.0)
        pos.entry_atm_iv = d.get("entry_atm_iv", 0.15)
        pos.mae = d.get("mae", 0.0)
        pos.prev_pnl_pct = d.get("prev_pnl_pct", 0.0)
        pos.bucket_index = d.get("bucket_index", 4)
        pos.time_to_target = d.get("time_to_target", 0.5)
        pos.log_sigma = d.get("log_sigma", 0.5)
        pos.max_unrealized_pnl = d.get("max_unrealized_pnl", 0.0)
        return pos


class GBMSignalTracker:
    """Tracks a GBM spot-based signal for TP/SL monitoring (like backtest simulate_mlp_only)."""
    def __init__(self, ticker: str, direction: str, entry_price: float,
                 confidence: float, entry_time=None):
        self.ticker = ticker
        self.direction = direction
        self.entry_price = entry_price
        self.confidence = confidence
        self.entry_time = entry_time or datetime.now(ET)
        self.target_pct = GBM_TARGET_LONG if direction == "LONG" else GBM_TARGET_SHORT
        self.stop_pct = GBM_STOP_PCT
        self.max_hold_minutes = GBM_MAX_HOLD_MINUTES

        # Pre-compute target/stop prices
        if direction == "LONG":
            self.target_price = entry_price * (1 + self.target_pct)
            self.stop_price = entry_price * (1 - self.stop_pct)
        else:  # SHORT
            self.target_price = entry_price * (1 - self.target_pct)
            self.stop_price = entry_price * (1 + self.stop_pct)

    def check(self, current_price: float, now: datetime) -> dict | None:
        """
        Check if TP, SL, or max hold has been hit.
        Returns dict with exit info or None if still holding.
        """
        hold_minutes = (now - self.entry_time).total_seconds() / 60.0

        if self.direction == "LONG":
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            if current_price >= self.target_price:
                return {"reason": "target", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
            if current_price <= self.stop_price:
                return {"reason": "stop", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
        else:  # SHORT
            pnl_pct = (self.entry_price - current_price) / self.entry_price
            if current_price <= self.target_price:
                return {"reason": "target", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
            if current_price >= self.stop_price:
                return {"reason": "stop", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}

        if hold_minutes >= self.max_hold_minutes:
            if self.direction == "LONG":
                pnl_pct = (current_price - self.entry_price) / self.entry_price
            else:
                pnl_pct = (self.entry_price - current_price) / self.entry_price
            return {"reason": "max_time", "exit_price": current_price,
                    "pnl_pct": pnl_pct, "hold_min": hold_minutes}

        return None

    def to_dict(self):
        return {
            "ticker": self.ticker, "direction": self.direction,
            "entry_price": self.entry_price, "confidence": self.confidence,
            "entry_time": self.entry_time.isoformat(),
            "target_price": self.target_price, "stop_price": self.stop_price,
        }

    @classmethod
    def from_dict(cls, d):
        tracker = cls(
            d["ticker"], d["direction"], d["entry_price"],
            d["confidence"],
            entry_time=datetime.fromisoformat(d["entry_time"]),
        )
        # Restore pre-computed levels from saved state
        tracker.target_price = d["target_price"]
        tracker.stop_price = d["stop_price"]
        return tracker


# ═════════════════════════════════════════════════════════════════════════
# MAIN BOT
# ═════════════════════════════════════════════════════════════════════════

class RLTradingBot:
    """GBM+RL trading bot — reads Parquet data from realtime_feed."""

    def __init__(self):
        self.device = get_device()
        self.systems: dict[str, IntegratedTradingSystem] = {}
        self.gbm_model = None  # GBT ensemble (independent)
        self.gbm_normalizer = None
        self.positions: dict[str, RLPosition] = {}
        self.last_trade_time: dict[str, datetime] = {}
        self.prev_features: dict[str, np.ndarray] = {}
        self.trade_count = 0
        self.daily_pnl = 0.0

        # Rolling state for feature computation — per ticker
        self.price_history = {t: deque(maxlen=35) for t in TICKERS}
        self.iv_history = {t: deque(maxlen=60) for t in TICKERS}
        self.spot_candles = {t: deque(maxlen=400) for t in TICKERS}
        self.tlt_price_history = deque(maxlen=35)  # TLT is cross-ticker
        self.ib_high = {t: None for t in TICKERS}
        self.ib_low = {t: None for t in TICKERS}
        self.historical_ibs = {t: [] for t in TICKERS}
        self.pcr_history = {t: deque(maxlen=32) for t in TICKERS}
        self.net_charm_history = {t: deque(maxlen=60) for t in TICKERS}
        self.net_gamma_window = {t: deque(maxlen=100) for t in TICKERS}
        self.wonham_probs = {t: 0.5 for t in TICKERS}

        # GBM signal tracking (avoid spamming repeated signals)
        self._last_gbm_direction = {}

        # ── PATCH: detección de spot congelado ──────────────────────────
        # Cuenta ciclos consecutivos con el mismo underlying_price.
        # Si >= FROZEN_CYCLES_THRESHOLD: resetea prev_features para evitar
        # que el vector de deltas=0 contamine el GBM y produzca HOLD 100%.
        self._frozen_spot_count = {t: 0 for t in TICKERS}
        self._frozen_spot_prev  = {t: 0.0 for t in TICKERS}

        # GBM spot-based TP/SL trackers (mirrors backtest simulate_mlp_only)
        self.gbm_trackers = {}  # ticker -> GBMSignalTracker

        self._load_models()
        self._load_positions()
        self._load_gbm_trackers()
        self._restore_rl_system_state()
        for ticker in TICKERS:
            self._load_historical_ib_levels(ticker)

    def _load_models(self):
        """Load GBM + RL agent."""
        logger.info("=" * 60)
        logger.info("Loading GBM + RL Agent...")

        # GBM (primary model — replaces legacy MLP)
        model, normalizer = load_ensemble_model(
            MODEL_PATH, NORMALIZER_PATH, MODEL_SIZE, self.device)
        logger.info(f"GBM ensemble loaded from {MODEL_PATH}")

        # Store reference for raw GBM prediction alerts
        self.gbm_model = model
        self.gbm_normalizer = normalizer

        # RL
        if os.path.exists(RL_MODEL_PATH):
            rl_agent = PPOAgent.load(RL_MODEL_PATH, self.device)
            logger.info(f"RL agent loaded from {RL_MODEL_PATH}")
        else:
            rl_agent = PPOAgent()
            rl_agent.to(self.device)
            logger.warning(f"RL model not found at {RL_MODEL_PATH} — using untrained agent")

        # IntegratedTradingSystem: GBM signals → RL execution
        for ticker in TICKERS:
            self.systems[ticker] = IntegratedTradingSystem(
                mlp_model=model,
                mlp_normalizer=normalizer,
                rl_agent=rl_agent,
                feature_columns=FEATURE_COLUMNS,
                device=self.device,
            )

        logger.info(f"IntegratedTradingSystem isolated per ticker ready: {TICKERS}")
        logger.info(f"Discord: {'enabled' if DISCORD_ENABLED else 'disabled'}")
        logger.info(f"Data source: {RT_DATA_DIR}")
        logger.info("=" * 60)

    def _save_positions(self):
        """Persist open positions to disk."""
        try:
            data = {t: p.to_dict() for t, p in self.positions.items()}
            tmp = POSITIONS_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, POSITIONS_FILE)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def _load_positions(self):
        """Restore positions from disk. Cleans up stale positions from previous days."""
        if not os.path.exists(POSITIONS_FILE):
            return
        try:
            with open(POSITIONS_FILE) as f:
                data = json.load(f)
            
            now = datetime.now(ET)
            for ticker, d in data.items():
                pos = RLPosition.from_dict(d)
                
                # Check for stale position (different day)
                if pos.entry_time.date() != now.date():
                    dur_days = (now.date() - pos.entry_time.date()).days
                    logger.warning(f"[{ticker}] Clearing stale position from {dur_days} days ago: {pos.strike:.0f}")
                    self._close_stale_position(ticker, pos)
                    continue

                self.positions[ticker] = pos
                dur = (now - pos.entry_time).total_seconds() / 60
                logger.info(f"Restored: {ticker} {d['direction']} {d['strike']:.0f} ({dur:.0f}min)")
            
            # Save any changes (in case we cleared stale positions)
            self._save_positions()
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")

    def _close_stale_position(self, ticker: str, pos: RLPosition):
        """Close a position that was found to be from a previous day during startup."""
        pnl_pct = -1.0  # 100% loss since 0DTE expired
        pnl_dollars = pnl_pct * pos.entry_premium * POINT_VALUES.get(ticker, 100)
        
        # Log to trade history
        now = datetime.now(ET)
        trade = {
            "ticker": ticker, "direction": pos.direction,
            "strike": pos.strike, "delta": pos.delta,
            "entry_premium": pos.entry_premium,
            "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars,
            "hold_minutes": (now - pos.entry_time).total_seconds() / 60,
            "exit_reason": "STALE_RECOVERY",
            "confidence": pos.confidence, "bucket": pos.bucket,
            "entry_time": pos.entry_time.isoformat(),
            "exit_time": now.isoformat(),
        }
        
        # Append to daily trades file (of the trade's OWN date if possible, or today)
        self._log_trade_history(trade, now, "trades_rl")

        discord_close(ticker, pos.direction, pos.strike, pnl_pct, pnl_dollars, 
                      (now - pos.entry_time).total_seconds() / 60, "STALE_RECOVERY")

    def _save_gbm_trackers(self):
        """Persist open GBM trackers to disk."""
        try:
            data = {t: tr.to_dict() for t, tr in self.gbm_trackers.items()}
            tmp = GBM_TRACKERS_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, GBM_TRACKERS_FILE)
        except Exception as e:
            logger.error(f"Failed to save GBM trackers: {e}")

    def _load_gbm_trackers(self):
        """Restore GBM trackers from disk. Cleans up stale trackers from previous days."""
        if not os.path.exists(GBM_TRACKERS_FILE):
            return
        try:
            with open(GBM_TRACKERS_FILE) as f:
                data = json.load(f)
            
            now = datetime.now(ET)
            for ticker, d in data.items():
                tracker = GBMSignalTracker.from_dict(d)
                
                # Check for stale tracker (different day)
                if tracker.entry_time.date() != now.date():
                    logger.warning(f"[{ticker}][GBM] Clearing stale tracker from a previous day: {tracker.direction}")
                    self._close_stale_tracker(ticker, tracker)
                    continue

                self.gbm_trackers[ticker] = tracker
                dur = (now - tracker.entry_time).total_seconds() / 60
                logger.info(
                    f"Restored GBM tracker: {ticker} {d['direction']} @ {d['entry_price']:.2f} "
                    f"(TP:{d['target_price']:.2f} SL:{d['stop_price']:.2f}, {dur:.0f}min)")
            
            # Save any changes
            self._save_gbm_trackers()
        except Exception as e:
            logger.error(f"Failed to load GBM trackers: {e}")

    def _close_stale_tracker(self, ticker: str, tracker: GBMSignalTracker):
        """Close a GBM tracker that was found to be from a previous day during startup."""
        now = datetime.now(ET)
        discord_gbm_track_close(
            ticker, tracker.direction, tracker.entry_price,
            tracker.entry_price * 0.5, -0.5, (now - tracker.entry_time).total_seconds() / 60, 
            "STALE_RECOVERY")

        trade = {
            "model": "GBM", "ticker": ticker, "direction": tracker.direction,
            "entry_price": tracker.entry_price, "exit_price": tracker.entry_price * 0.5,
            "pnl_pct": -0.5, "pnl_dollars": 0.0,
            "hold_minutes": (now - tracker.entry_time).total_seconds() / 60,
            "exit_reason": "STALE_RECOVERY", "confidence": tracker.confidence,
            "entry_time": tracker.entry_time.isoformat(), "exit_time": now.isoformat()
        }
        self._log_trade_history(trade, now, "trades_gbm")

    def _log_trade_history(self, trade: dict, now: datetime, prefix: str = "trades"):
        """Append trade to daily json file."""
        trades_file = os.path.join(TRADES_DIR, f"{prefix}_{now.strftime('%Y%m%d')}.json")
        try:
            existing = []
            if os.path.exists(trades_file):
                with open(trades_file, "r") as f:
                    existing = json.load(f)
            existing.append(trade)
            with open(trades_file, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to log trade history: {e}")

    def _restore_rl_system_state(self):
        """
        After loading persisted RL positions, restore IntegratedTradingSystem.open_position
        so the RL exit head continues monitoring after a reboot.
        """
        if not hasattr(self, 'systems') or not self.positions:
            return
            
        for ticker, pos in self.positions.items():
            if ticker not in self.systems:
                continue
            right = "CALL" if pos.direction == "LONG" else "PUT"
            self.systems[ticker].open_position = {
                "strike": pos.strike,
                "right": right,
                "direction": pos.direction,
                "entry_price": pos.entry_premium,
                "raw_entry_price": pos.entry_premium,
                "entry_iv": pos.entry_atm_iv,
                "entry_delta": pos.delta,
                "entry_theta": -0.05,
                "entry_gamma": 0.0,
                "entry_time": pos.entry_time,
                
            }
            # will populate it correctly on the first on_new_minute() call.
            self.systems[ticker]._dynamic_market_state = np.zeros(8, dtype=np.float32)
            logger.info(
                f"Restored RL system state: {ticker} {pos.direction} "
                f"strike={pos.strike:.0f} premium={pos.entry_premium:.2f} "
                f"mae={pos.mae:+.2%}")

    # ─────────────────────────────────────────
    # PARQUET DATA LOADING
    # ─────────────────────────────────────────

    def _get_rt_data_dir(self) -> Path:
        """Get today's rt_data directory."""
        today_str = datetime.now(ET).strftime("%Y%m%d")
        d = Path(RT_DATA_DIR) / today_str
        if d.exists():
            return d
        # Fallback: most recent directory
        base = Path(RT_DATA_DIR)
        if base.exists():
            subdirs = sorted([x for x in base.iterdir() if x.is_dir()], reverse=True)
            if subdirs:
                return subdirs[0]
        return d

    def _get_previous_trading_days(self, n: int = 5) -> list:
        """Return the last N trading days before today (Mon-Fri)."""
        today = datetime.now(ET).date()
        result = []
        candidate = today - timedelta(days=1)
        while len(result) < n and candidate > today - timedelta(days=30):
            if candidate.weekday() < 5:  # Mon-Fri
                result.append(candidate)
            candidate -= timedelta(days=1)
        return result

    def _load_historical_ib_levels(self, ticker: str):
        """
        Load Historical IB (D-1 to D-5) from previous days' spot data.
        """
        prev_days = self._get_previous_trading_days(5)
        self.historical_ibs[ticker] = []

        spot_source = SPOT_SOURCES.get(ticker, ticker)
        missing_days = []
        for day in prev_days:
            day_str = day.strftime("%Y%m%d")
            path = Path(RT_DATA_DIR) / day_str / f"spot_{spot_source}_latest.parquet"
            if not path.exists():
                missing_days.append(day)
        if missing_days:
            logger.warning(f"[{ticker}] Missing historical data for {len(missing_days)} days: "
                           f"{[d.strftime('%Y%m%d') for d in missing_days]}")
            logger.info("Run 'python services/realtime_feed.py --dry-run' to download missing data.")

        for day in prev_days:
            day_str = day.strftime("%Y%m%d")
            path = Path(RT_DATA_DIR) / day_str / f"spot_{spot_source}_latest.parquet"

            if not path.exists():
                self.historical_ibs[ticker].append(None)
                continue

            try:
                df = pd.read_parquet(path)
                if 'timestamp' in df.columns:
                    df['dt'] = pd.to_datetime(df['timestamp'])
                elif 'time' in df.columns:
                    df['dt'] = pd.to_datetime(df['time'])
                else:
                    self.historical_ibs[ticker].append(None)
                    continue

                df = df.sort_values('dt')
                df = df[(df['dt'].dt.time >= dt_time(9, 0)) & (df['dt'].dt.time <= dt_time(17, 0))]

                if df.empty:
                    self.historical_ibs[ticker].append(None)
                    continue

                rth_start = df[df['dt'].dt.time >= dt_time(9, 30)]
                if rth_start.empty:
                    self.historical_ibs[ticker].append(None)
                    continue

                rth_open = rth_start['dt'].iloc[0]
                ib_end = rth_open + pd.Timedelta(minutes=60)
                df_ib = rth_start[rth_start['dt'] < ib_end]

                ib_h = float(df_ib['high'].max()) if not df_ib.empty and 'high' in df_ib.columns else 0
                ib_l = float(df_ib['low'].min())  if not df_ib.empty and 'low' in df_ib.columns  else 0

                close_df = df[df['dt'].dt.time <= dt_time(16, 0)]
                close_price = float(close_df['close'].iloc[-1]) if not close_df.empty and 'close' in close_df.columns else 0

                if ib_h > 0 and ib_l > 0:
                    self.historical_ibs[ticker].append({
                        "ib_high": ib_h,
                        "ib_low": ib_l,
                        "close_price": close_price,
                        "date_str": day_str,
                    })
                    logger.info(f"  Hist IB: {day_str} h={ib_h:.2f} l={ib_l:.2f} c={close_price:.2f}")
                else:
                    self.historical_ibs[ticker].append(None)

            except Exception as e:
                logger.warning(f"Failed to load historical IB for {ticker} {day_str}: {e}")
                self.historical_ibs[ticker].append(None)

        while len(self.historical_ibs[ticker]) < 5:
            self.historical_ibs[ticker].append(None)

        loaded = sum(1 for h in self.historical_ibs[ticker] if h is not None)
        logger.info(f"[{ticker}] Historical IB: {loaded}/5 days loaded")

    _stale_last_warned: dict = {}

    def _read_parquet(self, filename: str, max_age: int = 300) -> pd.DataFrame:
        """
        Read a Parquet from rt_data, checking freshness.
        Returns data even if stale (better old snapshot than empty).
        Warning throttled to max 1x/minute per file.
        """
        rt_dir = self._get_rt_data_dir()
        path = rt_dir / filename
        if not path.exists():
            logger.debug(f"[Feed] {filename} not found yet")
            return pd.DataFrame()

        age = time.time() - path.stat().st_mtime

        if age > max_age:
            now_ts = time.time()
            last_warned = self._stale_last_warned.get(filename, 0)
            if now_ts - last_warned > 60:
                logger.warning(
                    f"[Feed] STALE {filename} ({age:.0f}s) -- "
                    f"using prior snapshot (delayed feed poll)"
                )
                self._stale_last_warned[filename] = now_ts

        try:
            return pd.read_parquet(path)
        except Exception as e:
            logger.error(f"[Feed] Error reading {filename}: {e}")
            return pd.DataFrame()

    def _load_greek_exposures(self, ticker: str, is_weekly: bool = False) -> dict:
        """
        Load Greeks + OI from Parquet, merge, and compute net exposures.
        """
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker) # Default to ticker if not in map
        suffix = "weekly" if is_weekly else "0dte"
        df_greeks = self._read_parquet(f"{options_symbol}_greeks_{suffix}_latest.parquet")
        df_oi = self._read_parquet(f"{options_symbol}_oi_{suffix}_latest.parquet")

        if df_greeks.empty:
            return None

        if 'underlying_timestamp' in df_greeks.columns:
            df_greeks['dt'] = pd.to_datetime(df_greeks['underlying_timestamp'], format='mixed', errors='coerce')
            latest_ts = df_greeks['dt'].max()
            df_greeks = df_greeks[df_greeks['dt'] == latest_ts].copy()

        if not df_oi.empty:
            oi_cols = ['strike', 'right']
            if 'open_interest' in df_oi.columns:
                df_oi_agg = df_oi.groupby([c for c in oi_cols if c in df_oi.columns]).agg(
                    {'open_interest': 'max'}).reset_index()
                merge_cols = [c for c in oi_cols if c in df_greeks.columns and c in df_oi_agg.columns]
                if merge_cols:
                    df_pq = pd.merge(df_greeks, df_oi_agg, on=merge_cols, how='inner')
                else:
                    df_pq = df_greeks.copy()
                    df_pq['open_interest'] = 1000
            else:
                df_pq = df_greeks.copy()
                df_pq['open_interest'] = 1000
        else:
            df_pq = df_greeks.copy()
            df_pq['open_interest'] = 1000

        if 'implied_vol' not in df_pq.columns:
            if 'implied_volatility' in df_pq.columns:
                df_pq['implied_vol'] = df_pq['implied_volatility']
            else:
                df_pq['implied_vol'] = 0.15

        if 'underlying_price' not in df_pq.columns:
            logger.warning("No underlying_price column — cannot compute exposures")
            return None

        now_et = pd.Timestamp.now(tz='America/New_York')
        df_pq['T'] = calculate_exact_t(now_et)

        required = ['strike', 'right', 'implied_vol', 'open_interest', 'underlying_price', 'T']
        for col in required:
            if col not in df_pq.columns:
                logger.warning(f"Missing column: {col}")
                return None
        df_pq = df_pq.dropna(subset=required)

        if df_pq.empty:
            return None

        return get_net_exposures_from_parquet(df_pq)

    def _load_options_chain(self, ticker: str) -> dict:
        """
        Load real options chain for RL strike resolution.
        Returns {calls: {strike: {price, delta, iv, theta, gamma}}, puts: {...}}
        """
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        df_greeks = self._read_parquet(f"{options_symbol}_greeks_0dte_latest.parquet")
        if df_greeks.empty:
            return {"calls": {}, "puts": {}}

        if 'underlying_timestamp' in df_greeks.columns:
            df_greeks['dt'] = pd.to_datetime(df_greeks['underlying_timestamp'], format='mixed', errors='coerce')
            latest_ts = df_greeks['dt'].max()
            df_greeks = df_greeks[df_greeks['dt'] == latest_ts]

        calls, puts = {}, {}
        for _, row in df_greeks.iterrows():
            strike = float(row.get('strike', 0))
            if strike <= 0:
                continue
            right = str(row.get('right', '')).upper()

            bid = float(row.get('bid', 0))
            ask = float(row.get('ask', 0))
            if bid > 0 and ask > 0:
                price = (bid + ask) / 2
            else:
                price = float(row.get('mid_price', row.get('close', row.get('last', 0.01))))
            price = max(price, 0.01)

            data = {
                "price": price,
                "delta": float(row.get('delta', 0)),
                "iv": float(row.get('implied_vol', row.get('implied_volatility', 0.15))),
                "theta": float(row.get('theta', -0.05)),
                "gamma": float(row.get('gamma', 0)),
            }

            if right in ("C", "CALL"):
                calls[strike] = data
            elif right in ("P", "PUT"):
                puts[strike] = data

        return {"calls": calls, "puts": puts}

    def _load_spot(self, symbol: str) -> float:
        """Load latest spot price from Parquet."""
        df = self._read_parquet(f"spot_{symbol}_latest.parquet")
        if df.empty or 'close' not in df.columns:
            return 0.0
        return float(df['close'].iloc[-1])

    def _load_spot_candles(self, ticker: str = "SPX") -> pd.DataFrame:
        """Load full intraday spot candles for IB computation."""
        df = self._read_parquet(f"spot_{ticker}_latest.parquet")
        if df.empty:
            return df
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'])
        elif 'time' in df.columns:
            df['dt'] = pd.to_datetime(df['time'])
        return df

    def _compute_ib_levels(self, df_spot: pd.DataFrame, ticker: str = "SPX"):
        """Compute Initial Balance (high/low of first 60 minutes) from spot candles."""
        if df_spot.empty or 'dt' not in df_spot.columns:
            return

        df_sorted = df_spot.sort_values('dt')
        df_rth = df_sorted[df_sorted['dt'].dt.time >= dt_time(9, 30)]
        if df_rth.empty:
            return

        # Always use 9:30 - 10:30 RTH window for IB
        rth_start = df_rth['dt'].dt.normalize().iloc[0] + pd.Timedelta(hours=9, minutes=30)
        ib_end = rth_start + pd.Timedelta(minutes=60)
        df_ib = df_rth[(df_rth['dt'] >= rth_start) & (df_rth['dt'] < ib_end)]

        if not df_ib.empty and 'high' in df_ib.columns and 'low' in df_ib.columns:
            self.ib_high[ticker] = float(df_ib['high'].max())
            self.ib_low[ticker] = float(df_ib['low'].min())

    def _load_atm_iv(self, spot: float, ticker: str) -> float:
        """Load ATM IV from IV parquet."""
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        df_iv = self._read_parquet(f"{options_symbol}_iv_0dte_latest.parquet")
        if df_iv.empty or 'implied_vol' not in df_iv.columns or 'strike' not in df_iv.columns:
            return 0.0

        if 'underlying_timestamp' in df_iv.columns:
            df_iv['dt'] = pd.to_datetime(df_iv['underlying_timestamp'], format='mixed', errors='coerce')
            latest_ts = df_iv['dt'].max()
            df_iv = df_iv[df_iv['dt'] == latest_ts]

        if df_iv.empty:
            return 0.0
        closest_idx = (df_iv['strike'] - spot).abs().idxmin()
        atm_iv = float(df_iv.loc[closest_idx, 'implied_vol'])
        if atm_iv > 1.0:
            atm_iv = atm_iv / 100.0
        return max(atm_iv, 0.01)

    def _calculate_current_atr(self, ticker: str) -> float:
        """Calculate 15-day ATR from historical daily ranges (high-low)."""
        hist = self.historical_ibs.get(ticker, [])
        ranges = [h['ib_high'] - h['ib_low'] for h in hist if h is not None]
        
        if len(ranges) >= 1:
            return float(np.mean(ranges))
        
        # Fallbacks
        return 70.0 if ticker == "SPX" else 4.0

    def extract_features(self, exp_0dte: dict, exp_weekly: dict,
                         spot: float, atm_iv: float,
                         vix_spot: float, tlt_spot: float,
                         ticker: str) -> np.ndarray:
        """
        Extract features using the unified logic in services.compute_features.
        """
        if spot <= 0 or exp_0dte is None:
            return None

        now_et = datetime.now(ET)
        minutes_since_open = max(0, (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30))
        
        # Update Wonham Filter State (recursive update)
        prices_list = [p for _, p in self.price_history[ticker]]
        if len(prices_list) >= 2:
            self.wonham_probs[ticker] = compute_wonham_filter(
                [prices_list[-2], prices_list[-1]], 
                p_start=self.wonham_probs[ticker]
            )[-1]

        # ATR logic (15-day range)
        day_atr = self._calculate_current_atr(ticker)
        
        return extract_feature_vector(
            exp_0dte=exp_0dte,
            exp_weekly=exp_weekly,
            spot=spot,
            atm_iv=atm_iv,
            vix_spot=vix_spot,
            tlt_spot=tlt_spot,
            ib_high=self.ib_high.get(ticker) or spot,
            ib_low=self.ib_low.get(ticker) or spot,
            historical_ibs=self.historical_ibs[ticker],
            price_history=self.price_history[ticker],
            tlt_price_history=self.tlt_price_history,
            iv_history=self.iv_history[ticker],
            pcr_history=self.pcr_history[ticker],
            net_gamma_window=self.net_gamma_window[ticker],
            net_charm_history=self.net_charm_history[ticker],
            prev_features=self.prev_features.get(ticker),
            minutes_since_open=minutes_since_open,
            day_atr=day_atr,
            now_et=now_et,
            FEATURE_COLUMNS=FEATURE_COLUMNS,
            wonham_prob=self.wonham_probs[ticker]
        )

    # ─────────────────────────────────────────
    # MAIN PROCESSING
    # ─────────────────────────────────────────

    def _run_gbm_prediction(self, features: np.ndarray, ticker: str):
        """Run GBM model independently and send Discord alert if signal changes."""
        if self.gbm_model is None or self.gbm_normalizer is None:
            return None

        try:
            features_norm = self.gbm_normalizer.transform(features.reshape(1, -1))
            probs = self.gbm_model.predict_proba(features_norm)[0]  # [SHORT, HOLD, LONG]
            prediction = int(np.argmax(probs))
            confidence = float(np.max(probs))
            direction_map = {0: "SHORT", 1: "HOLD", 2: "LONG"}
            direction = direction_map.get(prediction, "HOLD")

            logger.info(f"[{ticker}][GBM] {direction} conf={confidence:.0%} | "
                        f"S={probs[0]:.0%} H={probs[1]:.0%} L={probs[2]:.0%}")

            return {
                "direction": direction,
                "confidence": confidence,
                "probs": probs.tolist(),
            }

        except Exception as e:
            logger.warning(f"[{ticker}][GBM] Prediction failed: {e}")
            return None

    def _check_gbm_trackers(self, ticker: str, spot: float, now: datetime):
        """Check GBM spot-based TP/SL trackers for this ticker."""
        if ticker not in self.gbm_trackers:
            return

        tracker = self.gbm_trackers[ticker]
        result = tracker.check(spot, now)

        if result is not None:
            # Tracker has triggered — log and alert
            reason = result["reason"]
            pnl_pct = result["pnl_pct"]
            hold_min = result["hold_min"]
            exit_price = result["exit_price"]

            logger.info(
                f"[{ticker}][GBM] {reason.upper()} | {tracker.direction} "
                f"entry={tracker.entry_price:.2f} exit={exit_price:.2f} "
                f"pnl={pnl_pct:+.2%} hold={hold_min:.0f}min"
            )

            discord_gbm_track_close(
                ticker, tracker.direction, tracker.entry_price,
                exit_price, pnl_pct, hold_min, reason)

            trade = {
                "model": "GBM", "ticker": ticker, "direction": tracker.direction,
                "entry_price": tracker.entry_price, "exit_price": exit_price,
                "pnl_pct": pnl_pct, "pnl_dollars": 0.0,
                "hold_minutes": hold_min, "exit_reason": reason,
                "confidence": tracker.confidence,
                "entry_time": tracker.entry_time.isoformat(), "exit_time": now.isoformat()
            }
            self._log_trade_history(trade, now, "trades_gbm")

            del self.gbm_trackers[ticker]
            self._save_gbm_trackers()

    def process_ticker(self, ticker: str):
        """Process a single ticker through GBM+RL pipeline."""
        now = datetime.now(ET)
        minutes_since_open = max(0, (now.hour * 60 + now.minute) - (9 * 60 + 30))
        
        # 0. Skip the first 10 minutes of the market (09:30 - 09:39) due to toxic options pricing
        current_minute = now.hour * 60 + now.minute
        if 570 <= current_minute < 580:
            logger.info(f"[{ticker}] NO-TRADE: Skipping market open volatility ({now.strftime('%H:%M:%S')})")
            return

        logger.info(f"[{ticker}] --- process_ticker {now.strftime('%H:%M:%S')} ---")

        # 1. Load data from Parquet
        exp_0dte = self._load_greek_exposures(ticker, is_weekly=False)
        if not exp_0dte:
            options_symbol = OPTIONS_SYMBOLS.get(ticker, "SPXW")
            logger.info(f"[{ticker}] NO-TRADE: 0DTE data missing ({options_symbol}_greeks_0dte_latest.parquet empty)")
            return

        exp_weekly = self._load_greek_exposures(ticker, is_weekly=True)

        # Read spot from spot parquet FIRST (refreshed in ~2s of each feed poll)
        # instead of exp_0dte["spot_price"] which sits inside greeks parquet
        # (takes ~60-90s to refresh, causing "SPOT CONGELADO" false positives).
        spot_source = SPOT_SOURCES.get(ticker, ticker)
        spot = self._load_spot(spot_source)
        if spot <= 0:
            spot = exp_0dte["spot_price"]
        if spot <= 0:
            logger.info(f"[{ticker}] NO-TRADE: spot=0")
            return

        FROZEN_CYCLES_THRESHOLD = 5  # ciclos de 65s = ~5.4 mins congelado
        prev_spot = self._frozen_spot_prev.get(ticker, 0.0)

        if prev_spot > 0 and spot == prev_spot:
            self._frozen_spot_count[ticker] += 1
            count = self._frozen_spot_count[ticker]

            if count >= FROZEN_CYCLES_THRESHOLD:
                # Si el mercado está muerto de verdad por >5 min, reseteamos prev_features
                # para que el próximo cambio real no tenga un momentum contaminado.
                self.prev_features.pop(ticker, None)
                logger.warning(
                    f"[{ticker}] SPOT CONGELADO {count} ciclos @ {spot:.2f} "
                    f"— prev_features reseteado para evitar momentum rancio"
                )
                # NOTA: No hacemos 'return' prematuro. Dejamos que el bot procese
                # aunque el spot sea igual. Si no hay señal, el modelo dirá HOLD.
                # Pero no bloqueamos el ciclo por "prev_spot == spot" para permitirlo
                # en mercados laterales o feeds lentos.

            else:
                logger.info(
                    f"[{ticker}] spot lateral/repetido ({count}/{FROZEN_CYCLES_THRESHOLD}) "
                    f"@ {spot:.2f} — procesando normalmente"
                )
        else:
            # Spot cambió: limpiar contador
            if self._frozen_spot_count.get(ticker, 0) > 0:
                logger.info(
                    f"[{ticker}] spot recuperado: {prev_spot:.2f} → {spot:.2f} "
                    f"(congelado {self._frozen_spot_count[ticker]} ciclos)"
                )
            self._frozen_spot_count[ticker] = 0

        self._frozen_spot_prev[ticker] = spot

        # 2. Update IB: re-compute during the first hour (9:30-10:30)
        # to ensure it expands dynamically. Locks after 60 minutes.
        # This matches the dynamic IB logic in collect_training_data_spx_qqq.py
        now_et = datetime.now(ET)
        minutes_since_open = max(0, (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30))
        
        if self.ib_high[ticker] is None or minutes_since_open <= 60:
            df_spot = self._load_spot_candles(ticker)
            self._compute_ib_levels(df_spot, ticker)

        # 3. Load additional data
        atm_iv = self._load_atm_iv(spot, ticker)
        vix_spot = self._load_spot("VIX")
        tlt_spot = self._load_spot("TLT")

        logger.info(
            f"[{ticker}] Data: spot={spot:.2f} atm_iv={atm_iv:.3f} "
            f"vix={vix_spot:.2f} tlt={tlt_spot:.2f} "
            f"net_gamma={exp_0dte.get('net_gamma', 0):.2e} "
            f"net_delta={exp_0dte.get('net_delta', 0):.2e} "
            f"net_vanna={exp_0dte.get('net_vanna', 0):.2e}"
        )
        # Update rolling histories (essential for multi-step features)
        self.price_history[ticker].append((minutes_since_open, spot))
        if atm_iv > 0:
            # Normalize IV to 0-1 if it's in percentage (e.g. 15.0 -> 0.15)
            self.iv_history[ticker].append(atm_iv / 100.0 if atm_iv > 1.0 else atm_iv)
        self.net_gamma_window[ticker].append(exp_0dte.get("net_gamma", 0.0))
        self.net_charm_history[ticker].append(exp_0dte.get("net_charm", 0.0))
        self.pcr_history[ticker].append(0.5) 
        
        if tlt_spot > 0:
             self.tlt_price_history.append((minutes_since_open, tlt_spot))

        # 4. Extract features (safe_log applied internally to match training)
        features = self.extract_features(
            exp_0dte, exp_weekly, spot, atm_iv, vix_spot, tlt_spot, ticker)
        if features is None:
            logger.info(f"[{ticker}] NO-TRADE: extract_features() returned None")
            return

        if np.isnan(features).any() or np.isinf(features).any():
            n_bad = int(np.sum(np.isnan(features) | np.isinf(features)))
            logger.info(f"[{ticker}] NO-TRADE: {n_bad} features with NaN/Inf")
            return

        # 5. Run GBM prediction (independent, no RL)
        gbm_result = self._run_gbm_prediction(features, ticker)

        if gbm_result and gbm_result["direction"] == "HOLD":
            logger.info(f"[{ticker}] NO-TRADE: GBM says HOLD conf={gbm_result['confidence']:.0%}")
        elif gbm_result and gbm_result["confidence"] < GBM_MIN_CONFIDENCE:
            logger.info(
                f"[{ticker}] NO-TRADE: GBM confidence insufficient "
                f"{gbm_result['confidence']:.0%} < {GBM_MIN_CONFIDENCE:.0%} required"
            )

        # 6. Load real options chain for RL
        options_data = self._load_options_chain(ticker)

        # 7. Call IntegratedTradingSystem (GBM + RL)
        result = self.systems[ticker].on_new_minute(
            market_features=features,
            options_data=options_data,
            spot=spot,
            timestamp=now
        )

        action = result.get("action", "")
        rl_conf = result.get("confidence", 0)
        logger.info(f"[{ticker}] RL: action={action} conf={rl_conf:.0%}")

        if not action.startswith("BUY_"):
            logger.info(f"[{ticker}] NO-TRADE: RL action={action} (not BUY)")
        
        # Update P&L and MAE for open position (if HOLD)
        if action == "HOLD" and ticker in self.positions:
            pos = self.positions[ticker]
            details = result.get("details", {})
            pos.mae = details.get("mae", pos.mae)
            pos.prev_pnl_pct = details.get("pnl_pct", pos.prev_pnl_pct)
            pos.max_unrealized_pnl = details.get("max_unrealized_pnl", getattr(pos, 'max_unrealized_pnl', 0.0))
            self._save_positions()

        # 8. Check existing GBM spot trackers for TP/SL
        self._check_gbm_trackers(ticker, spot, now)

        # 9. GBM Discord alert + create TP/SL tracker (only when direction changes or is actionable)
        if gbm_result and gbm_result["direction"] != "HOLD" and gbm_result["confidence"] >= GBM_MIN_CONFIDENCE:
            last_gbm = self._last_gbm_direction.get(ticker)
            if gbm_result["direction"] != last_gbm:
                rl_action = result.get("action", "")
                if rl_action.startswith("BUY_CALL"):
                    rl_dir = "LONG"
                elif rl_action.startswith("BUY_PUT"):
                    rl_dir = "SHORT"
                else:
                    rl_dir = None
                discord_gbm_signal(
                    ticker, gbm_result["direction"], gbm_result["confidence"],
                    gbm_result["probs"], rl_direction=rl_dir)
                self._last_gbm_direction[ticker] = gbm_result["direction"]

                # Create spot-based tracker if not already tracking this ticker
                if ticker not in self.gbm_trackers:
                    tracker = GBMSignalTracker(
                        ticker=ticker,
                        direction=gbm_result["direction"],
                        entry_price=spot,
                        confidence=gbm_result["confidence"],
                        entry_time=now,
                    )
                    self.gbm_trackers[ticker] = tracker
                    logger.info(
                        f"[{ticker}][GBM] Tracking {gbm_result['direction']} @ {spot:.2f} | "
                        f"TP: {tracker.target_price:.2f} | SL: {tracker.stop_price:.2f}")
                    discord_gbm_track_open(
                        ticker, gbm_result["direction"], spot,
                        gbm_result["confidence"], tracker.target_price, tracker.stop_price)
                    self._save_gbm_trackers()
        elif gbm_result and gbm_result["direction"] == "HOLD":
            self._last_gbm_direction[ticker] = None

        if action.startswith("BUY_"):
            last = self.last_trade_time.get(ticker)
            if last and (now - last).total_seconds() / 60 < COOLDOWN_MINUTES:
                elapsed = (now - last).total_seconds() / 60
                logger.info(
                    f"[{ticker}] NO-TRADE: cooldown active "
                    f"({elapsed:.1f} min elapsed, requires {COOLDOWN_MINUTES} min)"
                )
                return

            if ticker in self.positions:
                pos = self.positions[ticker]
                logger.info(
                    f"[{ticker}] NO-TRADE: already in position "
                    f"{pos.direction} strike={pos.strike:.0f} since {pos.entry_time.strftime('%H:%M')}"
                )
                return

            details = result.get("details", {})
            pos = RLPosition(
                ticker=ticker,
                direction="LONG" if "CALL" in action else "SHORT",
                strike=result.get("strike", 0),
                delta=result.get("delta", 0),
                entry_premium=details.get("entry_price", 0),
                confidence=result.get("confidence", 0),
                bucket=details.get("bucket", "unknown"),
                entry_time=now,
                entry_spot=spot,
                entry_atm_iv=atm_iv,
                bucket_index=details.get("bucket_index", 4),
                time_to_target=details.get("time_to_target", 0.5),
                log_sigma=details.get("log_sigma", 0.5),
            )
            self.positions[ticker] = pos
            self.last_trade_time[ticker] = now
            self.trade_count += 1
            self._save_positions()

            logger.info(f"OPEN {pos.direction} {ticker} {pos.strike:.0f} {pos.bucket} | conf={pos.confidence:.0%}")

            discord_open(
                ticker, pos.direction, pos.strike, pos.delta,
                pos.confidence, 0, pos.entry_premium, pos.bucket)

        elif action == "EXIT":
            if ticker not in self.positions:
                return

            pos = self.positions.pop(ticker)
            details = result.get("details", {})
            pnl_pct = details.get("final_pnl_pct", 0)
            hold_min = (now - pos.entry_time).total_seconds() / 60
            pnl_dollars = pnl_pct * pos.entry_premium * POINT_VALUES.get(ticker, 100)
            reason = details.get("exit_reason", "unknown")
            self.daily_pnl += pnl_dollars
            self._save_positions()

            logger.info(f"CLOSE {ticker} | {pnl_pct:+.1%} | ${pnl_dollars:+.1f} | {hold_min:.0f}min | {reason}")

            discord_close(ticker, pos.direction, pos.strike,
                          pnl_pct, pnl_dollars, hold_min, reason)

            trade = {
                "ticker": ticker, "direction": pos.direction,
                "strike": pos.strike, "delta": pos.delta,
                "entry_premium": pos.entry_premium,
                "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars,
                "hold_minutes": hold_min, "exit_reason": reason,
                "confidence": pos.confidence, "bucket": pos.bucket,
                "entry_time": pos.entry_time.isoformat(),
                "exit_time": now.isoformat(),
            }
            self._log_trade_history(trade, now, "trades_rl")

    def is_market_hours(self) -> bool:
        """Check if within trading window (9:30-16:00 EST)."""
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)
        return market_open <= now <= market_close

    def run(self):
        """Main loop."""
        logger.info("Starting GBM+RL Trading Bot (Parquet pipeline)")
        discord_status("Bot started")

        while True:
            try:
                if not self.is_market_hours():
                    time.sleep(60)
                    continue

                for ticker in TICKERS:
                    try:
                        self.process_ticker(ticker)
                    except Exception as e:
                        logger.error(f"[{ticker}] Error: {e}")

                time.sleep(LOOP_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Bot stopped")
                discord_status(f"Bot stopped | Daily P&L: ${self.daily_pnl:+.1f}")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(10)


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    bot = RLTradingBot()
    bot.run()
