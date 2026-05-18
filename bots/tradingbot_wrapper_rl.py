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
from typing import Optional
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
from neural.signal_policy import entry_cadence_minutes, is_actionable_signal
from modules.utils import get_market_trading_days
from services.compute_features import (
    get_net_exposures_from_parquet, calculate_exact_t, extract_feature_vector,
    compute_wonham_filter,
    safe_log, dist_bps, is_near_level, classify_gamma_regime, sign_divergence,
    inverse_safe_log, invert_delta_filtered_pcr,
    simple_rsi, calculate_fibonacci_levels, rbf_confluence
)

load_dotenv()

ET = ZoneInfo("America/New_York")

# ── Configuration ──
# Must match the promoted model configured in neural/run_pipeline.ps1.
MODEL_PATH = os.path.join(
    PROJECT_ROOT, "neural", "models", "codex_exp",
    "gbt_18m_econ_pf150_minsel10_avail.joblib",
)
NORMALIZER_PATH = os.path.join(
    PROJECT_ROOT, "neural", "models", "codex_exp",
    "gbt_18m_econ_pf150_minsel10_avail_norm.npz",
)
RL_MODEL_PATH = os.path.join(PROJECT_ROOT, "rl_models", "best_rl_agent.pt")
TRADES_DIR = os.path.join(PROJECT_ROOT, "trades_rl")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
POSITIONS_FILE = os.path.join(TRADES_DIR, "open_positions_rl.json")
GBM_TRACKERS_FILE = os.path.join(TRADES_DIR, "open_gbm_trackers.json")
GBM_SIGNALS_FILE = os.path.join(TRADES_DIR, "gbm_signals_rl.json")
COOLDOWNS_FILE = os.path.join(TRADES_DIR, "cooldowns_rl.json")
RT_DATA_DIR = os.path.join(PROJECT_ROOT, "rt_data")
BOT_STATE_FILENAME = "bot_intraday_state.json"

# GBM signal confidence threshold. Must match the RL training/backtest run.
EXPECTED_LIVE_MIN_CONFIDENCE = 0.475
GBM_MIN_CONFIDENCE = float(RL_CONFIG["min_confidence"])
if not math.isclose(GBM_MIN_CONFIDENCE, EXPECTED_LIVE_MIN_CONFIDENCE, rel_tol=0.0, abs_tol=1e-9):
    raise RuntimeError(
        f"Live confidence threshold mismatch: wrapper={GBM_MIN_CONFIDENCE}, "
        f"expected={EXPECTED_LIVE_MIN_CONFIDENCE}"
    )

os.makedirs(TRADES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Discord
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_WEBHOOK_URL_2 = os.getenv("DISCORD_WEBHOOK_URL_2")
DISCORD_WEBHOOKS = [url for url in [DISCORD_WEBHOOK_URL, DISCORD_WEBHOOK_URL_2] if url]
DISCORD_ROLE_PING = os.getenv("DISCORD_ROLE_PING", "<@&1464601287411634226>")
DISCORD_ENABLED = len(DISCORD_WEBHOOKS) > 0

# Process SPX, QQQ, and SPY
TICKERS = ["SPX", "QQQ", "SPY"]
POINT_VALUES = {"SPX": 50.0, "SPY": 100.0, "QQQ": 100.0}
OPTION_CONTRACT_MULTIPLIER = 100.0
RISK_CAPITAL = 1000.0
MODEL_SIZE = "small"

# Map trading ticker → options symbol (matches training data)
OPTIONS_SYMBOLS = {
    "SPX": "SPXW",   # SPX uses SPXW options
    "QQQ": "QQQ",   # QQQ uses QQQ options directly
    "SPY": "SPY",   # SPY uses SPY options (American-style)
}

# Spot source symbol (for underlying derived data)
SPOT_SOURCES = {
    "SPX": "SPX",   # SPX uses SPX underlying derived
    "QQQ": "QQQ",   # QQQ uses QQQ underlying derived
    "SPY": "SPY",   # SPY uses SPY underlying derived
}

# Timing
LOOP_INTERVAL = 65  # seconds — aligned with realtime_feed's 60s poll interval
MAX_FEED_SNAPSHOT_AGE_SECONDS = 150
ENTRY_EVAL_CADENCE_MINUTES = entry_cadence_minutes()
COOLDOWN_MINUTES = 15
EOD_CLEANUP_MINUTE = 55  # minute of 15:XX EST at which EOD cleanup triggers
MIN_ENTRY_MINUTE = 580
MIN_SHORT_ENTRY_MINUTE = 615
MIN_SHORT_PRICE_VS_IB_HIGH = -40.0

# GBM Spot-Based TP/SL Configuration (mirrors backtest_rl.py simulate_mlp_only)
GBM_TARGET_LONG = 0.010       # +1.0% spot move target for LONG
GBM_TARGET_SHORT = 0.010      # +1.0% spot move target for SHORT
GBM_STOP_PCT = 0.0025         # 0.25% adverse spot move stop loss
GBM_MAX_HOLD_MINUTES = 180    # 3 hours max hold
GBM_TRAILING_STOP_PCT = 0.0030 # 0.30% spot retrace from peak (user requested)
GBM_TRAILING_ACTIVATION_PCT = 0.0050 # Activate trailing at +0.50% spot profit
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

def format_expiration_for_tracker(exp_str: str) -> str:
    """Convert YYYYMMDD to M/D/YY for trade_tracker.py."""
    if not exp_str or len(exp_str) != 8:
        return ""
    try:
        dt = datetime.strptime(exp_str, "%Y%m%d")
        # Use str(int(x)) to remove leading zeros if desired, 
        # or just %m/%d/%y which works fine with the tracker's parser.
        return dt.strftime("%m/%d/%y")
    except:
        return ""


def discord_open(ticker: str, direction: str, strike: float, delta: float,
                 confidence: float, sigma_min: float, entry_premium: float,
                 bucket: str, expiration: Optional[str] = None):
    """Send trade OPEN alert — compatible with trade_tracker.py."""
    if not DISCORD_ENABLED:
        return
    right = "C" if direction == "LONG" else "P"
    cmd = "BTO"  # For options, we always BTO (buy call or buy put)
    
    # First line: [BTO|STO] TICKER [DATE] [STRIKE][C|P] @ M
    if expiration:
        exp_fmt = format_expiration_for_tracker(expiration)
        tracker_line = f"{cmd} {ticker} {exp_fmt} {strike:.0f}{right} @ M"
    else:
        tracker_line = f"{cmd} {ticker} @ M"

    # Send tracker command separately for maximum reliability
    _send(tracker_line)

    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[OPTIONS] OPEN {direction} {ticker} {strike:.0f}{right} ({delta:.2f}D)**\n"
        f"Confidence: {confidence:.0%} | Sigma: {sigma_min:.0f}min | Bucket: {bucket}\n"
        f"Entry premium: ${entry_premium:.2f} | Hard stop: {HARD_EXITS['max_loss_pct']:.0%} | Max hold: {HARD_EXITS['max_hold_minutes']}min"
    )
    _send(msg)


def discord_close(ticker: str, direction: str, strike: float,
                  pnl_pct: float, pnl_dollars: float, hold_min: float,
                  reason: str, expiration: Optional[str] = None):
    """Send trade CLOSE alert — compatible with trade_tracker.py."""
    if not DISCORD_ENABLED:
        return
    right = "C" if direction == "LONG" else "P"
    cmd = "STC"  # For options, we always STC (sell back the bought option)
    
    # First line: [STC|BTC] TICKER [DATE] [STRIKE][C|P] @ M
    if expiration:
        exp_fmt = format_expiration_for_tracker(expiration)
        tracker_line = f"{cmd} {ticker} {exp_fmt} {strike:.0f}{right} @ M"
    else:
        tracker_line = f"{cmd} {ticker} @ M"

    result = "WIN" if pnl_pct >= 0 else "LOSS"
    _send(tracker_line)
    
    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[OPTIONS] CLOSED {ticker} {strike:.0f}{right} — {result}**\n"
        f"P&L: {pnl_pct:+.1%} (${pnl_dollars:+.1f}) | {hold_min:.0f}min | {reason}"
    )
    _send(msg)


def discord_status(message: str):
    """Send status update."""
    if not DISCORD_ENABLED:
        return
    _send(f"[Options Bot] {message}")


def discord_gbm_signal(ticker: str, direction: str, confidence: float,
                       probs: list, rl_direction: str = None):
    """Send GBM signal alert — info only, tracker line removed to avoid duplicate."""
    if not DISCORD_ENABLED:
        return
    prob_str = f"SHORT={probs[0]:.0%} | HOLD={probs[1]:.0%} | LONG={probs[2]:.0%}"
    if rl_direction and rl_direction != "HOLD":
        agree = "AGREE" if direction == rl_direction else "DISAGREE"
        agree_str = f" | RL: {rl_direction} ({agree})"
    else:
        agree_str = ""

    msg = (
        f"**[DIRECTION] Signal: {direction} {ticker}**\n"
        f"Confidence: {confidence:.0%} | {prob_str}{agree_str}"
    )
    _send(msg)


def discord_gbm_track_open(ticker: str, direction: str, entry_price: float,
                           confidence: float, target_price: float, stop_price: float):
    """Send GBM TP/SL tracking OPEN alert — compatible with trade_tracker.py."""
    if not DISCORD_ENABLED:
        return
    cmd = "BTO" if direction == "LONG" else "STO"
    tracker_line = f"{cmd} {ticker} @ M"

    _send(tracker_line)

    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[DIRECTION] TRACKING {direction} {ticker} @ {entry_price:.2f}**\n"
        f"Confidence: {confidence:.0%} | "
        f"TP: {target_price:.2f} | SL: {stop_price:.2f} | Max: {GBM_MAX_HOLD_MINUTES}min"
    )
    _send(msg)


def discord_gbm_track_close(ticker: str, direction: str, entry_price: float,
                            exit_price: float, pnl_pct: float, hold_min: float,
                            reason: str):
    """Send GBM TP/SL tracking result alert — compatible with trade_tracker.py."""
    if not DISCORD_ENABLED:
        return
    cmd = "STC" if direction == "LONG" else "BTC"
    tracker_line = f"{cmd} {ticker} @ M"

    result = "WIN" if pnl_pct >= 0 else "LOSS"
    _send(tracker_line)

    msg = (
        f"{DISCORD_ROLE_PING}\n"
        f"**[DIRECTION] {result} {ticker} @ {exit_price:.2f}**\n"
        f"Entry: {entry_price:.2f} | P&L: {pnl_pct:+.2%} | {hold_min:.0f}min | {reason}"
    )
    _send(msg)


def _send(content: str):
    """Send raw message to all configured Discord webhooks."""
    for url in DISCORD_WEBHOOKS:
        try:
            resp = requests.post(url, json={"content": content}, timeout=5)
            if resp.status_code >= 400:
                logger.error(f"Discord webhook error ({url}): {resp.status_code}")
        except Exception as e:
            logger.error(f"Discord send failed for {url}: {e}")


# ═════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════

def calc_contracts_options(entry_premium: float) -> int:
    cost_per_contract = float(entry_premium or 0.0) * OPTION_CONTRACT_MULTIPLIER
    if cost_per_contract <= 0:
        return 1
    return max(1, int(RISK_CAPITAL / cost_per_contract))


# ═════════════════════════════════════════════════════════════════════════
# POSITION TRACKING
# ═════════════════════════════════════════════════════════════════════════

class RLPosition:
    """Tracks an open RL-managed position."""
    def __init__(self, ticker, direction, strike, delta, entry_premium,
                 confidence, bucket, entry_time, signal_spot, position_entry_spot,
                 entry_atm_iv, bucket_index,
                 expiration=None, mae=0.0, prev_pnl_pct=0.0, time_to_target=0.5,
                 log_sigma=0.0, max_unrealized_pnl=0.0, right=None,
                 entry_market_features=None, trailing_drawdown=0.0,
                 contracts=1):
        self.ticker = ticker
        self.direction = direction
        self.strike = strike
        self.delta = delta
        self.entry_premium = entry_premium
        self.confidence = confidence
        self.bucket = bucket
        self.entry_time = entry_time
        self.signal_spot = signal_spot
        self.position_entry_spot = position_entry_spot
        self.entry_atm_iv = entry_atm_iv
        self.expiration = expiration
        self.mae = mae
        self.prev_pnl_pct = prev_pnl_pct
        self.bucket_index = bucket_index
        self.time_to_target = time_to_target
        self.log_sigma = log_sigma
        self.max_unrealized_pnl = max_unrealized_pnl
        self.right = right or ("CALL" if direction == "LONG" else "PUT")
        self.entry_market_features = entry_market_features
        self.trailing_drawdown = trailing_drawdown
        self.contracts = max(1, int(contracts or 1))

    def to_dict(self):
        return {
            "ticker": self.ticker, "direction": self.direction,
            "strike": self.strike, "delta": self.delta,
            "entry_premium": self.entry_premium,
            "confidence": self.confidence, "bucket": self.bucket,
            "entry_time": self.entry_time.isoformat(),
            "signal_spot": self.signal_spot,
            "position_entry_spot": self.position_entry_spot,
            "entry_atm_iv": self.entry_atm_iv,
            "expiration": self.expiration,
            "mae": self.mae,
            "prev_pnl_pct": self.prev_pnl_pct,
            "bucket_index": self.bucket_index,
            "time_to_target": self.time_to_target,
            "log_sigma": self.log_sigma,
            "max_unrealized_pnl": self.max_unrealized_pnl,
            "right": self.right,
            "entry_market_features": self.entry_market_features,
            "trailing_drawdown": self.trailing_drawdown,
            "contracts": self.contracts,
        }

    @classmethod
    def from_dict(cls, d):
        pos = cls(d["ticker"], d["direction"], d["strike"], d["delta"],
                  d["entry_premium"], d["confidence"], d["bucket"],
                  entry_time=datetime.fromisoformat(d["entry_time"]),
                  signal_spot=d.get("signal_spot", d.get("entry_spot", 0.0)),
                  position_entry_spot=d.get("position_entry_spot", d.get("entry_spot", 0.0)),
                  entry_atm_iv=d.get("entry_atm_iv", 0.15),
                  bucket_index=d.get("bucket_index", 4),
                  expiration=d.get("expiration"),
                  mae=d.get("mae", 0.0),
                  prev_pnl_pct=d.get("prev_pnl_pct", 0.0),
                  time_to_target=d.get("time_to_target", 0.5),
                  log_sigma=d.get("log_sigma", 0.0),
                  max_unrealized_pnl=d.get("max_unrealized_pnl", 0.0),
                  right=d.get("right"),
                  entry_market_features=d.get("entry_market_features"),
                  trailing_drawdown=d.get("trailing_drawdown", 0.0),
                  contracts=d.get("contracts", 1))
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
        self.peak_price = entry_price  # Track peak favorable price

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
            self.peak_price = max(self.peak_price, current_price)
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            peak_pnl = (self.peak_price - self.entry_price) / self.entry_price
            
            if current_price >= self.target_price:
                return {"reason": "target", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
            if current_price <= self.stop_price:
                return {"reason": "stop", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
            
            # Trailing Stop check
            if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                if (self.peak_price - current_price) / self.entry_price >= GBM_TRAILING_STOP_PCT:
                    return {"reason": "trailing_stop", "exit_price": current_price,
                            "pnl_pct": pnl_pct, "hold_min": hold_minutes}
        else:  # SHORT
            self.peak_price = min(self.peak_price, current_price)
            pnl_pct = (self.entry_price - current_price) / self.entry_price
            peak_pnl = (self.entry_price - self.peak_price) / self.entry_price
            
            if current_price <= self.target_price:
                return {"reason": "target", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
            if current_price >= self.stop_price:
                return {"reason": "stop", "exit_price": current_price,
                        "pnl_pct": pnl_pct, "hold_min": hold_minutes}
            
            # Trailing Stop check
            if peak_pnl >= GBM_TRAILING_ACTIVATION_PCT:
                if (current_price - self.peak_price) / self.entry_price >= GBM_TRAILING_STOP_PCT:
                    return {"reason": "trailing_stop", "exit_price": current_price,
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
            "peak_price": self.peak_price,
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
        tracker.peak_price = d.get("peak_price", d["entry_price"])
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
        self.current_session_date = datetime.now(ET).date()
        self._intraday_state_ready_date = None

        # Rolling state for feature computation — per ticker
        self.price_history = {t: deque(maxlen=35) for t in TICKERS}
        self.iv_history = {t: deque(maxlen=32) for t in TICKERS}
        self.spot_candles = {t: deque(maxlen=400) for t in TICKERS}
        self.tlt_price_history = deque(maxlen=35)  # TLT is cross-ticker
        self.ib_high = {t: None for t in TICKERS}
        self.ib_low = {t: None for t in TICKERS}
        self.historical_ibs = {t: [] for t in TICKERS}
        self.pcr_history = {t: deque(maxlen=32) for t in TICKERS}
        self.net_charm_history = {t: deque(maxlen=32) for t in TICKERS}
        self.net_gamma_window = {t: deque(maxlen=60) for t in TICKERS}
        self.wonham_probs = {t: 0.5 for t in TICKERS}

        # Track volume for PCR calculation
        self._prev_call_vol = {t: 0 for t in TICKERS}
        self._prev_put_vol = {t: 0 for t in TICKERS}

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
        self._last_gbm_direction = self._load_gbm_signals()
        self.last_trade_time = self._load_cooldowns()
        self._restore_rl_system_state()
        for ticker in TICKERS:
            self._load_historical_ib_levels(ticker)
        self._restore_intraday_state_from_rt_data()

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
                min_confidence=GBM_MIN_CONFIDENCE,
            )

        logger.info(f"IntegratedTradingSystem isolated per ticker ready: {TICKERS}")
        logger.info(
            "Live policy: min_conf=%.3f cooldown=%s target_L=%.3f target_S=%.3f "
            "stop=%.4f min_entry=%s min_short_entry=%s short_price_vs_ib_high>=%.1f",
            GBM_MIN_CONFIDENCE,
            COOLDOWN_MINUTES,
            GBM_TARGET_LONG,
            GBM_TARGET_SHORT,
            GBM_STOP_PCT,
            MIN_ENTRY_MINUTE,
            MIN_SHORT_ENTRY_MINUTE,
            MIN_SHORT_PRICE_VS_IB_HIGH,
        )
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

    def _is_past_eod(self, now: datetime = None) -> bool:
        """Check if current time is past EOD cleanup cutoff (15:55 EST)."""
        if now is None:
            now = datetime.now(ET)
        return (now.hour > 15) or (now.hour == 15 and now.minute >= EOD_CLEANUP_MINUTE)

    def _load_positions(self):
        """Restore positions from disk (passive load — no cleanup, no Discord)."""
        if not os.path.exists(POSITIONS_FILE):
            return
        try:
            with open(POSITIONS_FILE) as f:
                data = json.load(f)
            
            for ticker, d in data.items():
                pos = RLPosition.from_dict(d)
                self.positions[ticker] = pos
                logger.info(f"Loaded position: {ticker} {d['direction']} {d['strike']:.0f}")
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")

    def _close_stale_position(self, ticker: str, pos: RLPosition, reason: str = "STALE_RECOVERY"):
        """Close a position found stale (previous day) or past EOD during startup."""
        # EOD_CLOSE uses last known PnL; STALE_RECOVERY assumes -100% (0DTE expired)
        if reason == "EOD_CLOSE":
            pnl_pct = pos.prev_pnl_pct
        else:
            pnl_pct = -1.0
        pnl_dollars = pnl_pct * pos.entry_premium * POINT_VALUES.get(ticker, 100)
        
        now = datetime.now(ET)
        trade = {
            "ticker": ticker, "direction": pos.direction,
            "strike": pos.strike, "delta": pos.delta,
            "entry_premium": pos.entry_premium,
            "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars,
            "hold_minutes": (now - pos.entry_time).total_seconds() / 60,
            "exit_reason": reason,
            "confidence": pos.confidence, "bucket": pos.bucket,
            "entry_time": pos.entry_time.isoformat(),
            "exit_time": now.isoformat(),
        }
        self._log_trade_history(trade, now, "trades_rl")

        discord_close(ticker, pos.direction, pos.strike, pnl_pct, pnl_dollars, 
                      (now - pos.entry_time).total_seconds() / 60, reason,
                      expiration=pos.expiration)

    def _save_gbm_signals(self):
        """Persist last seen GBM directions to disk."""
        try:
            with open(GBM_SIGNALS_FILE, "w") as f:
                json.dump(self._last_gbm_direction, f)
        except Exception as e:
            logger.error(f"Failed to save GBM signals: {e}")

    def _load_gbm_signals(self) -> dict:
        """Load last seen GBM directions from disk."""
        if not os.path.exists(GBM_SIGNALS_FILE):
            return {}
        try:
            with open(GBM_SIGNALS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load GBM signals: {e}")
            return {}

    def _save_cooldowns(self):
        """Persist last trade times for cooldown enforcement."""
        try:
            # Convert datetime to ISO strings for JSON
            data = {t: dt.isoformat() for t, dt in self.last_trade_time.items()}
            with open(COOLDOWNS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save cooldowns: {e}")

    def _load_cooldowns(self) -> dict:
        """Load last trade times from disk."""
        if not os.path.exists(COOLDOWNS_FILE):
            return {}
        try:
            with open(COOLDOWNS_FILE, "r") as f:
                data = json.load(f)
                # Convert ISO strings back to datetime objects
                return {t: datetime.fromisoformat(dt) for t, dt in data.items()}
        except Exception as e:
            logger.error(f"Failed to load cooldowns: {e}")
            return {}

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
        """Restore GBM trackers from disk (passive load — no cleanup, no Discord)."""
        if not os.path.exists(GBM_TRACKERS_FILE):
            return
        try:
            with open(GBM_TRACKERS_FILE) as f:
                data = json.load(f)
            
            for ticker, d in data.items():
                tracker = GBMSignalTracker.from_dict(d)
                self.gbm_trackers[ticker] = tracker
                logger.info(
                    f"Loaded GBM tracker: {ticker} {d['direction']} @ {d['entry_price']:.2f} "
                    f"(TP:{d['target_price']:.2f} SL:{d['stop_price']:.2f})")
        except Exception as e:
            logger.error(f"Failed to load GBM trackers: {e}")

    def _close_stale_tracker(self, ticker: str, tracker: GBMSignalTracker, reason: str = "STALE_RECOVERY"):
        """Close a GBM tracker found stale or past EOD."""
        now = datetime.now(ET)

        # EOD_CLOSE: estimate real PnL from last known price direction
        if reason == "EOD_CLOSE":
            # Use peak_price as best exit proxy (market was still open recently)
            exit_price = tracker.peak_price
            if tracker.direction == "LONG":
                pnl_pct = (exit_price - tracker.entry_price) / tracker.entry_price
            else:
                pnl_pct = (tracker.entry_price - exit_price) / tracker.entry_price
        else:
            exit_price = tracker.entry_price * 0.5
            pnl_pct = -0.5

        hold_min = (now - tracker.entry_time).total_seconds() / 60
        discord_gbm_track_close(
            ticker, tracker.direction, tracker.entry_price,
            exit_price, pnl_pct, hold_min, reason)

        trade = {
            "model": "GBM", "ticker": ticker, "direction": tracker.direction,
            "entry_price": tracker.entry_price, "exit_price": exit_price,
            "pnl_pct": pnl_pct, "pnl_dollars": 0.0,
            "hold_minutes": hold_min,
            "exit_reason": reason, "confidence": tracker.confidence,
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

    @staticmethod
    def _serialize_price_history(history: deque) -> list[list[float]]:
        rows = []
        for item in history:
            try:
                minute, price = item
                rows.append([float(minute), float(price)])
            except Exception:
                continue
        return rows

    @staticmethod
    def _deserialize_price_history(rows, maxlen: int) -> deque:
        history = deque(maxlen=maxlen)
        for item in rows or []:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                history.append((float(item[0]), float(item[1])))
            except Exception:
                continue
        return history

    @staticmethod
    def _float_or_none(value):
        try:
            value = float(value)
        except Exception:
            return None
        return value if np.isfinite(value) else None

    @staticmethod
    def _normalize_prev_features(prev: dict | None) -> dict | None:
        if not isinstance(prev, dict):
            return None
        normalized = {}
        for key, value in prev.items():
            norm = RLTradingBot._float_or_none(value)
            if norm is not None:
                normalized[key] = norm
        return normalized or None

    def _get_day_rt_data_dir(self, day=None, create: bool = False) -> Path:
        day = day or datetime.now(ET).date()
        day_dir = Path(RT_DATA_DIR) / day.strftime("%Y%m%d")
        if create:
            day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def _get_intraday_state_path(self, day=None, create: bool = False) -> Path:
        return self._get_day_rt_data_dir(day=day, create=create) / BOT_STATE_FILENAME

    def _reset_feature_runtime_state(self):
        self.prev_features = {}
        self.tlt_price_history.clear()
        for ticker in TICKERS:
            self.price_history[ticker].clear()
            self.iv_history[ticker].clear()
            self.spot_candles[ticker].clear()
            self.ib_high[ticker] = None
            self.ib_low[ticker] = None
            self.pcr_history[ticker].clear()
            self.net_charm_history[ticker].clear()
            self.net_gamma_window[ticker].clear()
            self.wonham_probs[ticker] = 0.5
            self._prev_call_vol[ticker] = 0.0
            self._prev_put_vol[ticker] = 0.0
            self._frozen_spot_count[ticker] = 0
            self._frozen_spot_prev[ticker] = 0.0

            system = self.systems.get(ticker)
            if system is None:
                continue

            system._spot_history.clear()
            system._option_price_history.clear()
            system._dynamic_market_state = np.zeros(8, dtype=np.float32)
            if system.open_position is None:
                system._signal_spot = 0.0
                system._position_entry_spot = 0.0
                system._signal_direction = "HOLD"
                system._signal_confidence = 0.0
                system._entry_atm_iv = 0.15

    def _has_runtime_feature_state(self) -> bool:
        if len(self.tlt_price_history) > 0:
            return True
        if self.prev_features:
            return True
        for ticker in TICKERS:
            if (
                len(self.price_history[ticker]) > 0 or
                len(self.iv_history[ticker]) > 0 or
                len(self.pcr_history[ticker]) > 0 or
                len(self.net_gamma_window[ticker]) > 0 or
                len(self.net_charm_history[ticker]) > 0
            ):
                return True
        return False

    def _load_day_spot_history(self, day_dir: Path, symbol: str, target_history: deque) -> bool:
        path = day_dir / f"spot_{symbol}_latest.parquet"
        if not path.exists():
            return False
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return False
            if "timestamp" in df.columns:
                df["dt"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")
            elif "time" in df.columns:
                df["dt"] = pd.to_datetime(df["time"], format="mixed", errors="coerce")
            else:
                return False
            df = df.dropna(subset=["dt"]).sort_values("dt")
            df = df[(df["dt"].dt.time >= dt_time(9, 30)) & (df["dt"].dt.time <= dt_time(16, 0))]
            target_history.clear()
            for _, row in df.tail(target_history.maxlen).iterrows():
                close = self._float_or_none(row.get("close", 0.0))
                if close is None or close <= 0:
                    continue
                mins = max(0, (row["dt"].hour * 60 + row["dt"].minute) - (9 * 60 + 30))
                target_history.append((float(mins), close))
            return len(target_history) > 0
        except Exception as e:
            logger.warning(f"[{symbol}] Failed to restore spot history: {e}")
            return False

    def _restore_prev_features_from_df(self, ticker: str, df_features: pd.DataFrame, latest_spot: float):
        if df_features.empty:
            return
        last = df_features.iloc[-1]

        def _raw_value(raw_col: str, feat_col: str) -> float:
            raw_val = last.get(raw_col)
            if pd.notna(raw_val):
                raw_val = self._float_or_none(raw_val)
                if raw_val is not None:
                    return raw_val
            feat_val = last.get(feat_col)
            if pd.notna(feat_val):
                feat_val = self._float_or_none(feat_val)
                if feat_val is not None:
                    return float(inverse_safe_log(feat_val))
            return 0.0

        spot = latest_spot
        if spot <= 0 and pd.notna(last.get("spot_price")):
            spot = self._float_or_none(last.get("spot_price")) or 0.0
        if spot <= 0:
            return

        self.prev_features[ticker] = {
            "spot": float(spot),
            "net_gamma": _raw_value("net_gamma_raw", "net_gamma"),
            "net_vanna": _raw_value("net_vanna_raw", "net_vanna"),
            "net_dgex": _raw_value("net_dgex_raw", "net_dgex"),
            "net_delta": _raw_value("net_delta_raw", "net_delta"),
            "net_vega": _raw_value("net_vega_raw", "net_vega"),
            "net_vomma": _raw_value("net_vomma_raw", "net_vomma"),
        }

    def _restore_feature_diary_state(self, ticker: str, day_dir: Path) -> bool:
        path = day_dir / f"ml_features_{ticker}_latest.parquet"
        if not path.exists():
            return False
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return False

            iv_col = "atm_iv_raw" if "atm_iv_raw" in df.columns else "atm_iv"
            if iv_col in df.columns:
                iv_vals = [self._float_or_none(v) for v in df[iv_col].tail(self.iv_history[ticker].maxlen)]
                self.iv_history[ticker] = deque([v for v in iv_vals if v is not None and v > 0], maxlen=32)

            if "pcr_raw" in df.columns:
                pcr_vals = [self._float_or_none(v) for v in df["pcr_raw"].tail(self.pcr_history[ticker].maxlen)]
                self.pcr_history[ticker] = deque([v for v in pcr_vals if v is not None and v >= 0], maxlen=32)
            elif "delta_filtered_pcr" in df.columns:
                pcr_vals = []
                for val in df["delta_filtered_pcr"].tail(self.pcr_history[ticker].maxlen):
                    parsed = self._float_or_none(val)
                    if parsed is not None:
                        pcr_vals.append(float(invert_delta_filtered_pcr(parsed)))
                self.pcr_history[ticker] = deque(pcr_vals, maxlen=32)

            gamma_col = "net_gamma_raw" if "net_gamma_raw" in df.columns else "net_gamma"
            gamma_vals = []
            if gamma_col in df.columns:
                for val in df[gamma_col].tail(self.net_gamma_window[ticker].maxlen):
                    parsed = self._float_or_none(val)
                    if parsed is None:
                        continue
                    gamma_vals.append(parsed if gamma_col.endswith("_raw") else float(inverse_safe_log(parsed)))
            self.net_gamma_window[ticker] = deque(gamma_vals, maxlen=60)

            charm_col = "net_charm_raw" if "net_charm_raw" in df.columns else "net_charm"
            charm_vals = []
            if charm_col in df.columns:
                for val in df[charm_col].tail(self.net_charm_history[ticker].maxlen):
                    parsed = self._float_or_none(val)
                    if parsed is None:
                        continue
                    charm_vals.append(parsed if charm_col.endswith("_raw") else float(inverse_safe_log(parsed)))
            self.net_charm_history[ticker] = deque(charm_vals, maxlen=32)

            if "wonham_trend_prob" in df.columns:
                wonham = self._float_or_none(df["wonham_trend_prob"].iloc[-1])
                if wonham is not None:
                    self.wonham_probs[ticker] = float(np.clip(wonham, 0.0, 1.0))

            latest_spot = self.price_history[ticker][-1][1] if self.price_history[ticker] else 0.0
            self._restore_prev_features_from_df(ticker, df, latest_spot)
            return True
        except Exception as e:
            logger.warning(f"[{ticker}] Failed to restore feature diary: {e}")
            return False

    def _seed_pcr_volume_baseline(self, ticker: str, spot: float):
        if spot <= 0:
            return
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        day_dir = self._get_day_rt_data_dir(day=datetime.now(ET).date(), create=False)
        path = day_dir / f"{options_symbol}_ohlc_0dte_latest.parquet"
        if not path.exists():
            return
        df_opt = pd.read_parquet(path)
        if df_opt.empty or "volume" not in df_opt.columns or "strike" not in df_opt.columns or "right" not in df_opt.columns:
            return
        try:
            day_atr = max(self._calculate_current_atr(ticker), 1e-6)
            otm_range = 1.5 * day_atr
            df_calls_otm = df_opt[
                (df_opt["right"].astype(str).str.upper().isin(["CALL", "C"])) &
                (df_opt["strike"].between(spot, spot + otm_range))
            ]
            df_puts_otm = df_opt[
                (df_opt["right"].astype(str).str.upper().isin(["PUT", "P"])) &
                (df_opt["strike"].between(spot - otm_range, spot))
            ]
            self._prev_call_vol[ticker] = float(df_calls_otm["volume"].sum())
            self._prev_put_vol[ticker] = float(df_puts_otm["volume"].sum())
        except Exception as e:
            logger.warning(f"[{ticker}] Failed to seed PCR baseline: {e}")

    def _save_intraday_state(self):
        day = datetime.now(ET).date()
        state = {
            "session_date": day.strftime("%Y%m%d"),
            "tlt_price_history": self._serialize_price_history(self.tlt_price_history),
            "tickers": {},
        }

        for ticker in TICKERS:
            system = self.systems.get(ticker)
            state["tickers"][ticker] = {
                "price_history": self._serialize_price_history(self.price_history[ticker]),
                "iv_history": [float(v) for v in self.iv_history[ticker]],
                "ib_high": self._float_or_none(self.ib_high.get(ticker)),
                "ib_low": self._float_or_none(self.ib_low.get(ticker)),
                "prev_features": self._normalize_prev_features(self.prev_features.get(ticker)),
                "pcr_history": [float(v) for v in self.pcr_history[ticker]],
                "net_charm_history": [float(v) for v in self.net_charm_history[ticker]],
                "net_gamma_window": [float(v) for v in self.net_gamma_window[ticker]],
                "wonham_prob": float(self.wonham_probs.get(ticker, 0.5)),
                "prev_call_vol": float(self._prev_call_vol.get(ticker, 0.0)),
                "prev_put_vol": float(self._prev_put_vol.get(ticker, 0.0)),
                "frozen_spot_count": int(self._frozen_spot_count.get(ticker, 0)),
                "frozen_spot_prev": float(self._frozen_spot_prev.get(ticker, 0.0)),
                "its": {
                    "spot_history": [float(v) for v in getattr(system, "_spot_history", [])] if system else [],
                    "option_price_history": [float(v) for v in getattr(system, "_option_price_history", [])] if system else [],
                    "signal_spot": self._float_or_none(getattr(system, "_signal_spot", 0.0)) if system else 0.0,
                    "position_entry_spot": self._float_or_none(getattr(system, "_position_entry_spot", 0.0)) if system else 0.0,
                    "entry_market_features": getattr(system, "_entry_market_features", None).tolist() if system and getattr(system, "_entry_market_features", None) is not None else None,
                    "signal_direction": getattr(system, "_signal_direction", "HOLD") if system else "HOLD",
                    "signal_confidence": float(getattr(system, "_signal_confidence", 0.0)) if system else 0.0,
                    "entry_atm_iv": float(getattr(system, "_entry_atm_iv", 0.15)) if system else 0.15,
                    "dynamic_market_state": getattr(system, "_dynamic_market_state", np.zeros(8, dtype=np.float32)).tolist() if system else [0.0] * 8,
                },
            }

        path = self._get_intraday_state_path(day=day, create=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            logger.warning(f"Failed to save bot intraday state: {e}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def _restore_intraday_state_from_rt_data(self, now: datetime = None) -> bool:
        now = now or datetime.now(ET)
        day = now.date()
        if self._intraday_state_ready_date == day:
            return True

        day_dir = self._get_day_rt_data_dir(day=day, create=False)
        if not day_dir.exists():
            return False

        self._reset_feature_runtime_state()
        restored = False
        state_path = self._get_intraday_state_path(day=day, create=False)

        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("session_date") == day.strftime("%Y%m%d"):
                    self.tlt_price_history = self._deserialize_price_history(
                        state.get("tlt_price_history"), self.tlt_price_history.maxlen
                    )
                    for ticker in TICKERS:
                        tk_state = (state.get("tickers") or {}).get(ticker, {})
                        self.price_history[ticker] = self._deserialize_price_history(
                            tk_state.get("price_history"), self.price_history[ticker].maxlen
                        )
                        self.iv_history[ticker] = deque(
                            [float(v) for v in tk_state.get("iv_history", []) if self._float_or_none(v) is not None],
                            maxlen=32,
                        )
                        self.ib_high[ticker] = self._float_or_none(tk_state.get("ib_high"))
                        self.ib_low[ticker] = self._float_or_none(tk_state.get("ib_low"))
                        prev = self._normalize_prev_features(tk_state.get("prev_features"))
                        if prev:
                            self.prev_features[ticker] = prev
                        self.pcr_history[ticker] = deque(
                            [float(v) for v in tk_state.get("pcr_history", []) if self._float_or_none(v) is not None],
                            maxlen=32,
                        )
                        self.net_charm_history[ticker] = deque(
                            [float(v) for v in tk_state.get("net_charm_history", []) if self._float_or_none(v) is not None],
                            maxlen=32,
                        )
                        self.net_gamma_window[ticker] = deque(
                            [float(v) for v in tk_state.get("net_gamma_window", []) if self._float_or_none(v) is not None],
                            maxlen=60,
                        )
                        wonham = self._float_or_none(tk_state.get("wonham_prob"))
                        if wonham is not None:
                            self.wonham_probs[ticker] = float(np.clip(wonham, 0.0, 1.0))
                        self._prev_call_vol[ticker] = float(tk_state.get("prev_call_vol", 0.0))
                        self._prev_put_vol[ticker] = float(tk_state.get("prev_put_vol", 0.0))
                        self._frozen_spot_count[ticker] = int(tk_state.get("frozen_spot_count", 0))
                        self._frozen_spot_prev[ticker] = float(tk_state.get("frozen_spot_prev", 0.0))

                        system = self.systems.get(ticker)
                        if system is not None:
                            sys_state = tk_state.get("its") or {}
                            system._spot_history = deque(
                                [float(v) for v in sys_state.get("spot_history", []) if self._float_or_none(v) is not None],
                                maxlen=25,
                            )
                            system._option_price_history = deque(
                                [float(v) for v in sys_state.get("option_price_history", []) if self._float_or_none(v) is not None],
                                maxlen=10,
                            )
                            system._signal_spot = float(sys_state.get("signal_spot", 0.0) or 0.0)
                            system._position_entry_spot = float(sys_state.get("position_entry_spot", 0.0) or 0.0)
                            entry_market_features = sys_state.get("entry_market_features")
                            if entry_market_features:
                                system._entry_market_features = np.array(entry_market_features, dtype=np.float32)
                            system._signal_direction = str(sys_state.get("signal_direction", "HOLD"))
                            system._signal_confidence = float(sys_state.get("signal_confidence", 0.0) or 0.0)
                            system._entry_atm_iv = float(sys_state.get("entry_atm_iv", 0.15) or 0.15)
                            dynamic_state = sys_state.get("dynamic_market_state") or []
                            if len(dynamic_state) == 8:
                                system._dynamic_market_state = np.array(dynamic_state, dtype=np.float32)
                    restored = True
                    logger.info(f"[State] Bot intraday state restored from {state_path.name}")
            except Exception as e:
                logger.warning(f"[State] Failed to restore bot intraday state: {e}")

        if not restored:
            any_restored = self._load_day_spot_history(day_dir, "TLT", self.tlt_price_history)
            for ticker in TICKERS:
                any_restored = self._load_day_spot_history(day_dir, ticker, self.price_history[ticker]) or any_restored
                if self.price_history[ticker]:
                    df_spot = pd.read_parquet(day_dir / f"spot_{ticker}_latest.parquet")
                    if "timestamp" in df_spot.columns:
                        df_spot["dt"] = pd.to_datetime(df_spot["timestamp"], format="mixed", errors="coerce")
                    elif "time" in df_spot.columns:
                        df_spot["dt"] = pd.to_datetime(df_spot["time"], format="mixed", errors="coerce")
                    self._compute_ib_levels(df_spot, ticker)
                any_restored = self._restore_feature_diary_state(ticker, day_dir) or any_restored

                latest_spot = self.price_history[ticker][-1][1] if self.price_history[ticker] else 0.0
                if latest_spot > 0:
                    self._seed_pcr_volume_baseline(ticker, latest_spot)
                    system = self.systems.get(ticker)
                    if system is not None:
                        system._spot_history = deque(
                            [price for _, price in list(self.price_history[ticker])[-25:]],
                            maxlen=25,
                        )
                        if ticker in self.positions:
                            pos = self.positions[ticker]
                            system._signal_spot = pos.signal_spot or latest_spot
                            system._position_entry_spot = pos.position_entry_spot or system._signal_spot
                            system._entry_atm_iv = pos.entry_atm_iv or system._entry_atm_iv
                            if not system._option_price_history:
                                system._option_price_history.append(float(pos.entry_premium))

            if any_restored:
                logger.info("[State] Bot intraday histories rebuilt from rt_data")
                restored = True

        if restored:
            self._intraday_state_ready_date = day
            self._save_intraday_state()
        return restored

    def _handle_session_rollover(self, now: datetime):
        if now.date() <= self.current_session_date:
            return

        logger.info(f"Session rollover detected: {self.current_session_date} -> {now.date()}")
        self.current_session_date = now.date()
        self._intraday_state_ready_date = None
        self._reset_feature_runtime_state()
        for ticker in TICKERS:
            self._load_historical_ib_levels(ticker)
        self._last_gbm_direction = {}
        self._save_gbm_signals()
        self.last_trade_time = {}
        self._save_cooldowns()

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
            
            # Use the new restore_state method to populate all internal references
            self.systems[ticker].restore_state(
                pos_data=pos.to_dict(),
                confidence=pos.confidence,
                time_to_target=pos.time_to_target,
                log_sigma=pos.log_sigma
            )
            logger.info(f"Restored RL system state for {ticker} (conf={pos.confidence:.0%})")

    # ─────────────────────────────────────────
    # PARQUET DATA LOADING
    # ─────────────────────────────────────────

    def _get_rt_data_dir(self) -> Path:
        """Get the current session rt_data directory. Never fall back to a prior day."""
        today_str = datetime.now(ET).strftime("%Y%m%d")
        return Path(RT_DATA_DIR) / today_str

    def _get_previous_trading_days(self, n: int = 10) -> list:
        """Return the last N actual market trading days before today."""
        today = datetime.now(ET).date()
        all_recent = get_market_trading_days(n + 1, end_date=today)
        result = [d for d in all_recent if d < today]
        return result[-n:]

    def _load_historical_ib_levels(self, ticker: str):
        """
        Load Historical IB (D-1 to D-15) from previous days' spot data.
        """
        prev_days = self._get_previous_trading_days(15)
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
                        "daily_high": float(df['high'].max()) if 'high' in df.columns else ib_h,
                        "daily_low": float(df['low'].min()) if 'low' in df.columns else ib_l,
                        "close_price": close_price,
                        "date_str": day_str,
                    })
                    logger.info(f"  Hist IB: {day_str} h={ib_h:.2f} l={ib_l:.2f} c={close_price:.2f}")
                else:
                    self.historical_ibs[ticker].append(None)

            except Exception as e:
                logger.warning(f"Failed to load historical IB for {ticker} {day_str}: {e}")
                self.historical_ibs[ticker].append(None)

        while len(self.historical_ibs[ticker]) < 15:
            self.historical_ibs[ticker].append(None)

        loaded = sum(1 for h in self.historical_ibs[ticker] if h is not None)
        logger.info(f"[{ticker}] Historical IB: {loaded}/15 days loaded")

    _stale_last_warned: dict = {}

    def _read_parquet(self, filename: str, max_age: int = MAX_FEED_SNAPSHOT_AGE_SECONDS) -> pd.DataFrame:
        """
        Read a Parquet from rt_data, rejecting stale snapshots.

        For 0DTE intraday trading we prefer to skip a cycle rather than act on
        delayed Greeks/spot/IV data under the current minute's decision logic.
        Warning throttled to max 1x/minute per file.
        """
        rt_dir = self._get_rt_data_dir()
        path = rt_dir / filename
        if not path.exists():
            logger.debug(f"[Feed] {filename} not found yet")
            return pd.DataFrame()

        age = time.time() - path.stat().st_mtime

        # Relax staleness check for OI files (static intraday)
        effective_max_age = max_age
        if "_oi_" in filename:
            effective_max_age = 86400  # 24 hours

        if age > effective_max_age:
            now_ts = time.time()
            last_warned = self._stale_last_warned.get(filename, 0)
            if now_ts - last_warned > 60:
                logger.warning(
                    f"[Feed] STALE {filename} ({age:.0f}s) -- "
                    f"blocking live decision until fresh snapshot arrives"
                )
                self._stale_last_warned[filename] = now_ts
            return pd.DataFrame()

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

        snapshot_ts = pd.Timestamp.now(tz='America/New_York')
        if 'underlying_timestamp' in df_greeks.columns:
            df_greeks['dt'] = pd.to_datetime(df_greeks['underlying_timestamp'], format='mixed', errors='coerce')
            latest_ts = df_greeks['dt'].max()
            if pd.notna(latest_ts):
                snapshot_ts = latest_ts
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

        df_pq['T'] = calculate_exact_t(snapshot_ts)

        required = ['strike', 'right', 'implied_vol', 'open_interest', 'underlying_price', 'T']
        for col in required:
            if col not in df_pq.columns:
                logger.warning(f"Missing column: {col}")
                return None
        df_pq = df_pq.dropna(subset=required)

        if df_pq.empty:
            return None

        return get_net_exposures_from_parquet(df_pq)

    def _load_options_chain(self, ticker: str) -> tuple:
        """
        Load real options chain for RL strike resolution.
        Returns (calls, puts, expiration)
        """
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        df_greeks = self._read_parquet(f"{options_symbol}_greeks_0dte_latest.parquet")
        if df_greeks.empty:
            return {}, {}, None

        expiration = None
        if 'expiration' in df_greeks.columns:
            # All rows in 0dte file should have same expiration
            expiration = str(df_greeks['expiration'].iloc[0])

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

        return calls, puts, expiration

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
        """Load ATM IV from either IV or Greeks parquet."""
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        iv_path = f"{options_symbol}_iv_0dte_latest.parquet"
        g_path = f"{options_symbol}_greeks_0dte_latest.parquet"
        
        # Prefer greeks as primary source if IV is not being polled
        df = self._read_parquet(g_path)
        if df.empty:
            df = self._read_parquet(iv_path)
            
        if df.empty:
            return 0.0
            
        iv_col = "implied_vol" if "implied_vol" in df.columns else "implied_volatility"
        if iv_col not in df.columns or "strike" not in df.columns:
            return 0.0
            
        if "underlying_timestamp" in df.columns:
            df["dt"] = pd.to_datetime(df["underlying_timestamp"], format="mixed", errors="coerce")
            latest_ts = df["dt"].max()
            if pd.notna(latest_ts):
                df = df[df["dt"] == latest_ts]

        if df.empty:
            return 0.0
            
        closest_idx = (df["strike"] - spot).abs().idxmin()
        atm_iv = float(df.loc[closest_idx, iv_col])
        if atm_iv > 1.0:
            atm_iv = atm_iv / 100.0
        return max(atm_iv, 0.01)

    def _compute_pcr_val(self, ticker: str, spot: float, day_atr: float) -> float:
        """Compute delta-filtered PCR proxy using recent option volume."""
        options_symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        df_opt = self._read_parquet(f"{options_symbol}_ohlc_0dte_latest.parquet")
        
        pcr_val = 0.5
        if df_opt is not None and not df_opt.empty and 'volume' in df_opt.columns and 'strike' in df_opt.columns and 'right' in df_opt.columns:
            try:
                otm_range = 1.5 * day_atr
                df_calls_otm = df_opt[
                    (df_opt['right'].str.upper().isin(['CALL', 'C'])) &
                    (df_opt['strike'].between(spot, spot + otm_range))
                ]
                df_puts_otm = df_opt[
                    (df_opt['right'].str.upper().isin(['PUT', 'P'])) &
                    (df_opt['strike'].between(spot - otm_range, spot))
                ]
                call_vol = float(df_calls_otm['volume'].sum())
                put_vol = float(df_puts_otm['volume'].sum())
                
                prev_vol_c = self._prev_call_vol.get(ticker, 0)
                prev_vol_p = self._prev_put_vol.get(ticker, 0)
                
                min_call_vol = max(0, call_vol - prev_vol_c)
                min_put_vol = max(0, put_vol - prev_vol_p)
                
                self._prev_call_vol[ticker] = call_vol
                self._prev_put_vol[ticker] = put_vol
                
                if min_call_vol + min_put_vol > 0:
                    pcr_val = min_put_vol / (min_call_vol + 1e-6)
            except Exception as e:
                logger.error(f"[{ticker}] Error calculating PCR: {e}")
        return pcr_val

    def _calculate_current_atr(self, ticker: str) -> float:
        """Calculate 15-day ATR from historical daily ranges (high-low)."""
        hist = self.historical_ibs.get(ticker, [])
        # CRITICAL PARITY FIX: Use daily_high - daily_low to match collect_training_data_spx_qqq.py
        ranges = [h.get('daily_high', h['ib_high']) - h.get('daily_low', h['ib_low']) 
                  for h in hist if h is not None]
        
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
            historical_ibs=self.historical_ibs[ticker][:10],
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
            is_gbt = hasattr(self.gbm_model, "predict_proba") and not isinstance(self.gbm_model, torch.nn.Module)
            if is_gbt:
                probs = self.gbm_model.predict_proba(features.reshape(1, -1))[0]
            else:
                features_norm = self.gbm_normalizer.transform(features.reshape(1, -1))
                probs = self.gbm_model.predict_proba(features_norm)[0]
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

    @staticmethod
    def _feature_value(features: np.ndarray, name: str, default: float = 0.0) -> float:
        try:
            return float(features[FEATURE_COLUMNS.index(name)])
        except (ValueError, IndexError, TypeError):
            return float(default)

    def _check_gbm_trackers(self, ticker: str, spot: float, now: datetime):
        """Check GBM spot-based TP/SL trackers for this ticker."""
        if ticker not in self.gbm_trackers:
            return

        tracker = self.gbm_trackers[ticker]
        result = tracker.check(spot, now)
        
        # Debug log to see SL/TP levels
        if now.second < 10: # Log only every minute-ish
            logger.info(f"[{ticker}][GBM] Monitoring: Spot={spot:.2f} SL={tracker.stop_price:.2f} TP={tracker.target_price:.2f}")

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
            
            # Set cooldown so we don't instantly re-enter a new trade
            self.last_trade_time[ticker] = now
            self._save_cooldowns()

            # Reset last known direction so the next signal (even same direction)
            # triggers a fresh Discord alert and creates a new tracker, BUT only after cooldown
            self._last_gbm_direction[ticker] = None
            self._save_gbm_signals()

    def _execute_eod_cleanup(self, ticker: str, spot: float, now: datetime):
        """Forcefully close open positions and trackers at End of Day (15:55 EST)."""
        closed_something = False

        # Close RL Position
        if ticker in self.positions:
            pos = self.positions.pop(ticker)
            pnl_pct = pos.prev_pnl_pct
            pnl_dollars = pnl_pct * pos.entry_premium * POINT_VALUES.get(ticker, 100)
            hold_min = (now - pos.entry_time).total_seconds() / 60
            
            self.daily_pnl += pnl_dollars
            self.last_trade_time[ticker] = now
            self._save_cooldowns()
            self._save_positions()
            
            logger.info(f"[{ticker}] EOD_CLOSE RL | {pnl_pct:+.1%} | ${pnl_dollars:+.1f} | {hold_min:.0f}min")
            discord_close(ticker, pos.direction, pos.strike, pnl_pct, pnl_dollars, hold_min, "EOD_CLOSE", expiration=pos.expiration)
            
            trade = {
                "ticker": ticker, "direction": pos.direction,
                "strike": pos.strike, "delta": pos.delta,
                "entry_premium": pos.entry_premium,
                "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars,
                "hold_minutes": hold_min, "exit_reason": "EOD_CLOSE",
                "confidence": pos.confidence, "bucket": pos.bucket,
                "entry_time": pos.entry_time.isoformat(),
                "exit_time": now.isoformat(),
            }
            self._log_trade_history(trade, now, "trades_rl")
            closed_something = True

        # Close GBM Tracker
        if ticker in self.gbm_trackers:
            tracker = self.gbm_trackers.pop(ticker)
            
            if tracker.direction == "LONG":
                pnl_pct = (spot - tracker.entry_price) / tracker.entry_price
            else:
                pnl_pct = (tracker.entry_price - spot) / tracker.entry_price
                
            hold_min = (now - tracker.entry_time).total_seconds() / 60
            
            logger.info(f"[{ticker}][GBM] EOD_CLOSE | {tracker.direction} entry={tracker.entry_price:.2f} exit={spot:.2f} pnl={pnl_pct:+.2%} hold={hold_min:.0f}min")
            discord_gbm_track_close(ticker, tracker.direction, tracker.entry_price, spot, pnl_pct, hold_min, "EOD_CLOSE")
            
            trade = {
                "model": "GBM", "ticker": ticker, "direction": tracker.direction,
                "entry_price": tracker.entry_price, "exit_price": spot,
                "pnl_pct": pnl_pct, "pnl_dollars": 0.0,
                "hold_minutes": hold_min, "exit_reason": "EOD_CLOSE",
                "confidence": tracker.confidence,
                "entry_time": tracker.entry_time.isoformat(), "exit_time": now.isoformat()
            }
            self._log_trade_history(trade, now, "trades_gbm")
            self._save_gbm_trackers()
            closed_something = True

        if closed_something:
            self._last_gbm_direction[ticker] = None
            self._save_gbm_signals()

    def process_ticker(self, ticker: str):
        """Process a single ticker through GBM+RL pipeline."""
        now = datetime.now(ET)
        if self._intraday_state_ready_date != now.date() and not self._has_runtime_feature_state():
            self._restore_intraday_state_from_rt_data(now)
        minutes_since_open = max(0, (now.hour * 60 + now.minute) - (9 * 60 + 30))
        entry_eval_due = (minutes_since_open % ENTRY_EVAL_CADENCE_MINUTES) == 0
        
        # 0. Skip the unstable opening window configured by the promoted backtest.
        current_minute = now.hour * 60 + now.minute
        if 570 <= current_minute < MIN_ENTRY_MINUTE:
            logger.info(f"[{ticker}] NO-TRADE: Skipping market open volatility ({now.strftime('%H:%M:%S')})")
            return

        logger.info(f"[{ticker}] --- process_ticker {now.strftime('%H:%M:%S')} ---")

        # 1. Load data from Parquet
        exp_0dte = self._load_greek_exposures(ticker, is_weekly=False)
        if not exp_0dte:
            options_symbol = OPTIONS_SYMBOLS.get(ticker, "SPXW")
            logger.info(f"[{ticker}] NO-TRADE: 0DTE data missing/stale ({options_symbol}_greeks_0dte_latest.parquet empty)")
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

        # --- EOD CLEANUP (15:55 EST) ---
        if self._is_past_eod(now):
            self._execute_eod_cleanup(ticker, spot, now)
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

            else:
                logger.info(
                    f"[{ticker}] spot repeated ({count}/{FROZEN_CYCLES_THRESHOLD}) "
                    f"@ {spot:.2f} — processing normally"
                )
        else:
            # Spot cambió: limpiar contador
            if self._frozen_spot_count.get(ticker, 0) > 0:
                logger.info(
                    f"[{ticker}] spot recovered: {prev_spot:.2f} → {spot:.2f} "
                    f"(frozen {self._frozen_spot_count[ticker]} cycles)"
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
        
        day_atr = self._calculate_current_atr(ticker)
        pcr_val = self._compute_pcr_val(ticker, spot, day_atr)
        self.pcr_history[ticker].append(pcr_val) 
        
        if tlt_spot > 0:
             self.tlt_price_history.append((minutes_since_open, tlt_spot))

        # 4. Extract features (safe_log applied internally to match training)
        features = self.extract_features(
            exp_0dte, exp_weekly, spot, atm_iv, vix_spot, tlt_spot, ticker)
        if features is None:
            logger.info(f"[{ticker}] NO-TRADE: extract_features() returned None")
            self._save_intraday_state()
            return

        if np.isnan(features).any() or np.isinf(features).any():
            n_bad = int(np.sum(np.isnan(features) | np.isinf(features)))
            logger.info(f"[{ticker}] NO-TRADE: {n_bad} features with NaN/Inf")
            self._save_intraday_state()
            return

        # Keep temporal-delta features aligned with training/realtime_feed.
        # The current row must become the previous raw exposure snapshot for
        # the next poll.
        self.prev_features[ticker] = {
            "spot": spot,
            "net_gamma": exp_0dte.get("net_gamma", 0.0),
            "net_vanna": exp_0dte.get("net_vanna", 0.0),
            "net_dgex": exp_0dte.get("net_dgex", 0.0),
            "net_delta": exp_0dte.get("net_delta", 0.0),
            "net_vega": exp_0dte.get("net_vega", 0.0),
            "net_vomma": exp_0dte.get("net_vomma", 0.0),
        }

        if ticker not in self.positions and not entry_eval_due:
            logger.info(
                f"[{ticker}] ENTRY-GATED: waiting for {ENTRY_EVAL_CADENCE_MINUTES}m bar "
                f"(m={minutes_since_open})"
            )
            self._check_gbm_trackers(ticker, spot, now)
            self._save_intraday_state()
            return

        # 5. Run GBM prediction (independent, no RL)
        gbm_result = self._run_gbm_prediction(features, ticker)

        if gbm_result and gbm_result["direction"] == "HOLD":
            logger.info(f"[{ticker}] NO-TRADE: GBM says HOLD conf={gbm_result['confidence']:.0%}")
        elif (
            ticker not in self.positions
            and gbm_result
            and gbm_result["direction"] == "SHORT"
            and current_minute < MIN_SHORT_ENTRY_MINUTE
        ):
            logger.info(
                f"[{ticker}] NO-TRADE: SHORT entry before "
                f"{MIN_SHORT_ENTRY_MINUTE // 60:02d}:{MIN_SHORT_ENTRY_MINUTE % 60:02d}"
            )
            self._check_gbm_trackers(ticker, spot, now)
            self._save_intraday_state()
            return
        elif (
            ticker not in self.positions
            and gbm_result
            and gbm_result["direction"] == "SHORT"
            and self._feature_value(features, "price_vs_ib_high") < MIN_SHORT_PRICE_VS_IB_HIGH
        ):
            price_vs_ib_high = self._feature_value(features, "price_vs_ib_high")
            logger.info(
                f"[{ticker}] NO-TRADE: SHORT price_vs_ib_high={price_vs_ib_high:.1f} "
                f"below {MIN_SHORT_PRICE_VS_IB_HIGH:.1f}"
            )
            self._check_gbm_trackers(ticker, spot, now)
            self._save_intraday_state()
            return
        elif gbm_result and not is_actionable_signal(
            gbm_result["direction"],
            gbm_result["confidence"],
            base_confidence=GBM_MIN_CONFIDENCE,
        ):
            if ticker not in self.positions:
                logger.info(
                    f"[{ticker}] NO-TRADE: GBM confidence insufficient "
                    f"{gbm_result['confidence']:.0%} below directional threshold"
                )
                self._save_intraday_state()
                return
            # If position is open, fall through to ITS for exit evaluation
            logger.info(
                f"[{ticker}] GBM conf low ({gbm_result['confidence']:.0%}) "
                f"but position open — evaluating exit"
            )

        # 6. Load real options chain for RL
        calls, puts, expiration = self._load_options_chain(ticker)
        options_data = {"calls": calls, "puts": puts}

        # 7. Call IntegratedTradingSystem (GBM + RL)
        result = self.systems[ticker].on_new_minute(
            market_features=features,
            options_data=options_data,
            spot=spot,
            timestamp=now,
            has_real_position=(ticker in self.positions),
        )

        action = result.get("action", "NO_SIGNAL")
        rl_conf = result.get("confidence", 0)
        
        # Enhanced logging for RL state
        if action == "HOLD" and ticker in self.positions:
            pos = self.positions[ticker]
            # Use gbm_result for live confidence if available, else rl_conf
            live_conf = gbm_result["confidence"] if gbm_result else rl_conf
            details = result.get("details", {})
            pnl_pct = details.get("pnl_pct", 0.0)
            logger.info(f"[{ticker}] RL: action={action} | PnL={pnl_pct:+.1%} | LiveConf={live_conf:.0%} | EntryConf={pos.confidence:.0%}")
        else:
            logger.info(f"[{ticker}] RL: action={action} conf={rl_conf:.0%}")

        # Update P&L and MAE for open position (if HOLD)
        if action == "HOLD" and ticker in self.positions:
            pos = self.positions[ticker]
            details = result.get("details", {})
            pos.mae = details.get("mae", pos.mae)
            pos.prev_pnl_pct = details.get("pnl_pct", pos.prev_pnl_pct)
            pos.max_unrealized_pnl = details.get("max_unrealized_pnl", getattr(pos, 'max_unrealized_pnl', 0.0))
            pos.trailing_drawdown = details.get("trailing_drawdown", getattr(pos, 'trailing_drawdown', 0.0))
            self._save_positions()

        # Update: include reason in NO-TRADE logs for better debugging
        if action == "NO_SIGNAL" or (action == "HOLD" and ticker not in self.positions):
            details = result.get("details", {})
            reason = details.get("reason", "unknown")
            gbm_dir = gbm_result["direction"] if gbm_result else "unknown"
            logger.info(f"[{ticker}] NO-TRADE: RL action={action} | GBM={gbm_dir} | Reason={reason} | conf={rl_conf:.0%}")

        # 8. Check existing GBM spot trackers for TP/SL
        self._check_gbm_trackers(ticker, spot, now)

        # 9. GBM Discord alert + create TP/SL tracker (only when direction changes or is actionable)
        if gbm_result and is_actionable_signal(
            gbm_result["direction"],
            gbm_result["confidence"],
            base_confidence=GBM_MIN_CONFIDENCE,
        ):
            last_gbm = self._last_gbm_direction.get(ticker)
            if gbm_result["direction"] != last_gbm:
                # Check cooldown before tracking again
                last = self.last_trade_time.get(ticker)
                if last and (now - last).total_seconds() / 60 < COOLDOWN_MINUTES:
                    elapsed = (now - last).total_seconds() / 60
                    logger.info(f"[{ticker}][GBM] NO-TRADE: cooldown active ({elapsed:.1f} min elapsed) - suppressing GBM tracker")
                else:
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
                    self._save_gbm_signals()

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
            if self._last_gbm_direction.get(ticker) is not None:
                self._last_gbm_direction[ticker] = None
                self._save_gbm_signals()

        if action.startswith("BUY_"):
            last = self.last_trade_time.get(ticker)
            if last and (now - last).total_seconds() / 60 < COOLDOWN_MINUTES:
                elapsed = (now - last).total_seconds() / 60
                logger.info(
                    f"[{ticker}] NO-TRADE: cooldown active "
                    f"({elapsed:.1f} min elapsed, requires {COOLDOWN_MINUTES} min)"
                )
                # Rollback ITS state: it already set open_position internally
                self.systems[ticker]._reset_position_state()
                self._save_intraday_state()
                return

            if ticker in self.positions:
                pos = self.positions[ticker]
                logger.info(
                    f"[{ticker}] NO-TRADE: already in position "
                    f"{pos.direction} strike={pos.strike:.0f} since {pos.entry_time.strftime('%H:%M')}"
                )
                # Rollback ITS state: wrapper rejected the entry
                self.systems[ticker]._reset_position_state()
                self._save_intraday_state()
                return

            details = result.get("details", {})
            entry_premium = details.get("entry_price", 0)
            contracts = calc_contracts_options(entry_premium)
            pos = RLPosition(
                ticker=ticker,
                direction="LONG" if "CALL" in action else "SHORT",
                strike=result.get("strike", 0),
                delta=result.get("delta", 0),
                entry_premium=entry_premium,
                confidence=result.get("confidence", 0),
                bucket=details.get("bucket", "unknown"),
                entry_time=now,
                signal_spot=self.systems[ticker]._signal_spot,
                position_entry_spot=spot,
                entry_atm_iv=self.systems[ticker]._entry_atm_iv,
                bucket_index=details.get("bucket_index", 4),
                expiration=expiration,
                time_to_target=details.get("time_to_target", 0.5),
                log_sigma=details.get("log_sigma", 0.5),
                right="CALL" if "CALL" in action else "PUT",
                entry_market_features=(
                    getattr(self.systems[ticker], "_entry_market_features", None).tolist()
                    if getattr(self.systems[ticker], "_entry_market_features", None) is not None
                    else None
                ),
                contracts=contracts,
            )
            self.positions[ticker] = pos
            self.last_trade_time[ticker] = now
            self._save_cooldowns()
            self.trade_count += 1
            self._save_positions()

            logger.info(
                f"OPEN {pos.direction} {ticker} {pos.strike:.0f} {pos.bucket} | "
                f"conf={pos.confidence:.0%} | contracts={pos.contracts}"
            )

            discord_open(
                ticker, pos.direction, pos.strike, pos.delta,
                pos.confidence, 0, pos.entry_premium, pos.bucket,
                expiration=pos.expiration)

        elif action == "EXIT":
            if ticker not in self.positions:
                self._save_intraday_state()
                return

            pos = self.positions.pop(ticker)
            details = result.get("details", {})
            pnl_pct = details.get("final_pnl_pct", 0)
            hold_min = (now - pos.entry_time).total_seconds() / 60
            pnl_dollars = pnl_pct * pos.entry_premium * OPTION_CONTRACT_MULTIPLIER * pos.contracts
            reason = details.get("exit_reason", "unknown")
            self.daily_pnl += pnl_dollars
            self.last_trade_time[ticker] = now
            self._save_cooldowns()
            self._save_positions()

            logger.info(f"CLOSE {ticker} | {pnl_pct:+.1%} | ${pnl_dollars:+.1f} | {hold_min:.0f}min | {reason}")

            discord_close(ticker, pos.direction, pos.strike,
                          pnl_pct, pnl_dollars, hold_min, reason,
                          expiration=pos.expiration)

            trade = {
                "ticker": ticker, "direction": pos.direction,
                "strike": pos.strike, "delta": pos.delta,
                "entry_premium": pos.entry_premium,
                "contracts": pos.contracts,
                "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars,
                "hold_minutes": hold_min, "exit_reason": reason,
                "confidence": pos.confidence, "bucket": pos.bucket,
                "entry_time": pos.entry_time.isoformat(),
                "exit_time": now.isoformat(),
            }
            self._log_trade_history(trade, now, "trades_rl")

        self._save_intraday_state()

    def is_market_hours(self) -> bool:
        """Check if within trading window (9:30-16:00 EST)."""
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)
        return market_open <= now <= market_close

    def _startup_cleanup(self):
        """
        Run once when market opens. Closes any stale (previous day) or
        post-EOD (same day, past 15:55) positions/trackers WITH Discord
        notifications so the trade tracker picks them up.
        """
        now = datetime.now(ET)
        cleaned = False

        # --- RL Positions ---
        stale_tickers = []
        for ticker, pos in list(self.positions.items()):
            if pos.entry_time.date() != now.date():
                reason = "STALE_RECOVERY"
                dur_days = (now.date() - pos.entry_time.date()).days
                logger.warning(f"[{ticker}] Startup cleanup: stale position from {dur_days} days ago")
            elif self._is_past_eod(now):
                reason = "EOD_CLOSE"
                logger.warning(f"[{ticker}] Startup cleanup: same-day post-EOD position")
            else:
                continue  # valid position, keep it

            self._close_stale_position(ticker, pos, reason=reason)
            stale_tickers.append(ticker)
            cleaned = True

        for t in stale_tickers:
            self.positions.pop(t, None)
        if stale_tickers:
            self._save_positions()

        # --- GBM Trackers ---
        stale_tracker_tickers = []
        for ticker, tracker in list(self.gbm_trackers.items()):
            if tracker.entry_time.date() != now.date():
                reason = "STALE_RECOVERY"
                logger.warning(f"[{ticker}][GBM] Startup cleanup: stale tracker from previous day")
            elif self._is_past_eod(now):
                reason = "EOD_CLOSE"
                logger.warning(f"[{ticker}][GBM] Startup cleanup: same-day post-EOD tracker")
            else:
                continue  # valid tracker, keep it

            self._close_stale_tracker(ticker, tracker, reason=reason)
            stale_tracker_tickers.append(ticker)
            cleaned = True

        for t in stale_tracker_tickers:
            self.gbm_trackers.pop(t, None)
        if stale_tracker_tickers:
            self._save_gbm_trackers()

        # --- Wipe auxiliary JSON if anything was cleaned ---
        if cleaned:
            self._last_gbm_direction = {}
            self._save_gbm_signals()
            self.last_trade_time = {}
            self._save_cooldowns()
            logger.info("Startup cleanup complete — stale JSON state cleared.")

    def run(self):
        """Main loop."""
        logger.info("Starting GBM+RL Trading Bot (Parquet pipeline)")
        discord_status("Bot started")
        startup_cleanup_done = False

        while True:
            try:
                now = datetime.now(ET)
                self._handle_session_rollover(now)

                if not self.is_market_hours():
                    # Outside market hours: just sleep. No cleanup here
                    # because the Discord trade tracker ignores messages
                    # sent outside market hours.
                    startup_cleanup_done = False  # reset so cleanup runs on next open
                    time.sleep(60)
                    continue

                # First market-hours loop: clean up stale/EOD positions
                if not startup_cleanup_done:
                    self._startup_cleanup()
                    startup_cleanup_done = True

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
