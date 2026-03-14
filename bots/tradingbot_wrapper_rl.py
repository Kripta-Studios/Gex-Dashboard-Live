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
from services.compute_features import get_net_exposures_from_parquet, calculate_exact_t

load_dotenv()

# ── Feature transforms (must match training pipeline exactly) ──
def safe_log(x: float) -> float:
    """Sign-preserving log-transform: sign(x) * log1p(|x|).
    Compresses extreme greek values (10^8-10^11) to manageable range (~20-26)
    while preserving sign and monotonicity."""
    return math.copysign(math.log1p(abs(x)), x)

BPS_CLIP = 500  # clamp distances at ±500 bps (±5%)

def dist_bps(spot: float, level: float) -> float:
    """Percentage distance from spot to level in basis points, clamped."""
    if spot <= 0 or level <= 0:
        return 0.0
    return float(np.clip((spot - level) / spot * 10000.0, -BPS_CLIP, BPS_CLIP))

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
COOLDOWN_MINUTES = 30

# GBM Spot-Based TP/SL Configuration (mirrors backtest_rl.py simulate_mlp_only)
GBM_TARGET_LONG = 0.010       # +1.0% spot move target for LONG
GBM_TARGET_SHORT = 0.010      # +1.0% spot move target for SHORT
GBM_STOP_PCT = 0.003          # 0.3% adverse spot move stop loss
GBM_MAX_HOLD_MINUTES = 180    # 3 hours max hold
# IB constants
LEVEL_PROXIMITY_THRESHOLD = 0.0004

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

def classify_gamma_regime(net_gamma: float, threshold: float = 1e8) -> int:
    if net_gamma > threshold:
        return 2  # positive gamma
    elif net_gamma < -threshold:
        return 0  # negative gamma
    return 1  # neutral

def is_near_level(price: float, level: float, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
    if price <= 0 or level <= 0:
        return False
    return abs(price - level) / price < threshold

def calculate_fibonacci_levels(ib_high: float, ib_low: float) -> dict:
    ib_range = ib_high - ib_low
    return {
        "fib_127_up": ib_high + ib_range * 0.272,
        "fib_161_up": ib_high + ib_range * 0.618,
        "fib_200_up": ib_high + ib_range * 1.0,
        "fib_127_dn": ib_low - ib_range * 0.272,
        "fib_161_dn": ib_low - ib_range * 0.618,
        "fib_200_dn": ib_low - ib_range * 1.0,
    }

def simple_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < 2:
        return 50.0
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def sign_divergence(a: float, b: float) -> float:
    if abs(a) < 0.01 or abs(b) < 0.01:
        return 0.5
    return 1.0 if (a > 0) != (b > 0) else 0.0

def rbf_confluence(level_a, level_b, spot_price: float, sigma: float = 0.05) -> float:
    if spot_price <= 0 or level_a is None or level_b is None or level_a == 0 or level_b == 0:
        return 0.0
    d = abs(level_a - level_b) / spot_price
    v = np.exp(-d**2 / (2 * sigma**2))
    return float(np.clip(v, 0.0, 1.0)) if np.isfinite(v) else 0.0


# ═════════════════════════════════════════════════════════════════════════
# POSITION TRACKING
# ═════════════════════════════════════════════════════════════════════════

class RLPosition:
    """Tracks an open RL-managed position."""
    def __init__(self, ticker, direction, strike, delta, entry_premium,
                 confidence, bucket, entry_time=None):
        self.ticker = ticker
        self.direction = direction
        self.strike = strike
        self.delta = delta
        self.entry_premium = entry_premium
        self.confidence = confidence
        self.bucket = bucket
        self.entry_time = entry_time or datetime.now(ET)

    def to_dict(self):
        return {
            "ticker": self.ticker, "direction": self.direction,
            "strike": self.strike, "delta": self.delta,
            "entry_premium": self.entry_premium,
            "confidence": self.confidence, "bucket": self.bucket,
            "entry_time": self.entry_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, d):
        pos = cls(d["ticker"], d["direction"], d["strike"], d["delta"],
                  d["entry_premium"], d["confidence"], d["bucket"])
        pos.entry_time = datetime.fromisoformat(d["entry_time"])
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
        self.systems = {}  # ticker -> IntegratedTradingSystem
        self.gbm_model = None  # GBT ensemble (independent)
        self.gbm_normalizer = None
        self.positions = {}  # ticker -> RLPosition
        self.last_trade_time = {}
        self.prev_features = {}
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
        self.net_charm_history = {t: deque(maxlen=5) for t in TICKERS}
        self.net_gamma_window = {t: deque(maxlen=60) for t in TICKERS}

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
        """Restore positions from disk."""
        if not os.path.exists(POSITIONS_FILE):
            return
        try:
            with open(POSITIONS_FILE) as f:
                data = json.load(f)
            for ticker, d in data.items():
                self.positions[ticker] = RLPosition.from_dict(d)
                dur = (datetime.now(ET) - self.positions[ticker].entry_time).total_seconds() / 60
                logger.info(f"Restored: {ticker} {d['direction']} {d['strike']:.0f} ({dur:.0f}min)")
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")

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
        """Restore GBM trackers from disk."""
        if not os.path.exists(GBM_TRACKERS_FILE):
            return
        try:
            with open(GBM_TRACKERS_FILE) as f:
                data = json.load(f)
            for ticker, d in data.items():
                self.gbm_trackers[ticker] = GBMSignalTracker.from_dict(d)
                dur = (datetime.now(ET) - self.gbm_trackers[ticker].entry_time).total_seconds() / 60
                logger.info(
                    f"Restored GBM tracker: {ticker} {d['direction']} @ {d['entry_price']:.2f} "
                    f"(TP:{d['target_price']:.2f} SL:{d['stop_price']:.2f}, {dur:.0f}min)")
        except Exception as e:
            logger.error(f"Failed to load GBM trackers: {e}")

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
                "entry_iv": 0.15,
                "entry_delta": pos.delta,
                "entry_theta": -0.05,
                "entry_gamma": 0.0,
                "entry_time": pos.entry_time,
                "strike_action": 4,  # default ATM bucket
            }
            self.systems[ticker]._mae = 0.0
            self.systems[ticker]._prev_pnl_pct = 0.0
            self.systems[ticker]._entry_mlp_context = np.array(
                [pos.confidence, 0.5, 0.0, 0.5], dtype=np.float32)
            logger.info(
                f"Restored RL system state: {ticker} {pos.direction} "
                f"strike={pos.strike:.0f} premium={pos.entry_premium:.2f}")

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
        options_symbol = OPTIONS_SYMBOLS.get(ticker, "SPXW")
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
        options_symbol = OPTIONS_SYMBOLS.get(ticker, "SPXW")
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

    def _load_spot(self, symbol: str = "SPX") -> float:
        """Load latest spot price from Parquet."""
        df = self._read_parquet(f"spot_{symbol}_latest.parquet")
        if df.empty or 'close' not in df.columns:
            return 0.0
        return float(df['close'].iloc[-1])

    def _load_spot_candles(self) -> pd.DataFrame:
        """Load full intraday spot candles for IB computation."""
        df = self._read_parquet("spot_SPX_latest.parquet")
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

        rth_start = df_rth['dt'].min()
        ib_end = rth_start + pd.Timedelta(minutes=60)
        df_ib = df_rth[df_rth['dt'] < ib_end]

        if not df_ib.empty and 'high' in df_ib.columns and 'low' in df_ib.columns:
            self.ib_high[ticker] = float(df_ib['high'].max())
            self.ib_low[ticker] = float(df_ib['low'].min())

    def _load_atm_iv(self, spot: float, ticker: str = "SPX") -> float:
        """Load ATM IV from IV parquet."""
        options_symbol = OPTIONS_SYMBOLS.get(ticker, "SPXW")
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

    # ─────────────────────────────────────────
    # FEATURE EXTRACTION
    # ─────────────────────────────────────────

    def extract_features(self, exp_0dte: dict, exp_weekly: dict,
                         spot: float, atm_iv: float,
                         vix_spot: float, tlt_spot: float,
                         ticker: str) -> np.ndarray:
        """
        Extract features — identical to collect_training_data_spx_qqq.py.

        CRITICAL: All greek values are passed through safe_log() before being
        stored in the feature vector, exactly matching the training pipeline
        (collect_training_data lines 1291-1350). The normalizer was fitted on
        safe_log'd values (~15-26 range), NOT on raw greek magnitudes (~10^8-10^11).
        Signal thresholds (vanna_bullish etc.) use 0.1 to match training.
        """
        features = {}

        if spot <= 0 or exp_0dte is None:
            return None

        # ── 0DTE Greek exposures — safe_log to match training ──
        # Training: "net_gamma": safe_log(exp["net_gamma"]), etc.
        features["net_gamma"] = safe_log(exp_0dte["net_gamma"])
        features["net_vanna"] = safe_log(exp_0dte["net_vanna"])
        features["net_charm"] = safe_log(exp_0dte["net_charm"])
        features["net_dgex"]  = safe_log(exp_0dte["net_dgex"])
        features["net_zomma"] = safe_log(exp_0dte["net_zomma"])
        features["net_delta"] = safe_log(exp_0dte["net_delta"])
        features["net_vega"]  = safe_log(exp_0dte["net_vega"])
        features["net_vomma"] = safe_log(exp_0dte["net_vomma"])

        # ── Signals — threshold 0.1 on safe_log'd values, matching training ──
        # Training: "vanna_bullish": 1 if exp["net_vanna"] > 0.1 else 0
        # (net_vanna is already safe_log'd in training's sample dict)
        features["gamma_regime"] = classify_gamma_regime(exp_0dte["net_gamma"]) / 2.0
        features["vanna_bullish"]      = 1 if exp_0dte["net_vanna"] > 0.1 else 0
        features["charm_bullish"]      = 1 if exp_0dte["net_charm"] > 0.1 else 0
        features["dgex_sticky"]        = 1 if exp_0dte["net_dgex"]  > 0.1 else 0
        features["zomma_stabilizing"]  = 1 if exp_0dte["net_zomma"] > 0.1 else 0
        features["vega_elevated"]      = 1 if abs(exp_0dte["net_vega"]) > 0.1 else 0

        # ── ATR for normalizing distances (rolling 15-bar) ──
        now_et = datetime.now(ET)
        minutes_since_open = max(0, (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30))
        self.price_history[ticker].append((minutes_since_open, spot))

        day_atr = 1.0
        if len(self.price_history[ticker]) >= 3:
            prices = [p for _, p in self.price_history[ticker]]
            abs_returns = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
            if abs_returns:
                day_atr = max(np.mean(abs_returns), 0.5)
        atr_denom = day_atr + 1e-6

        # ── Greek strike distances (basis points) ──
        features["dist_to_max_gamma"]  = dist_bps(spot, exp_0dte["max_gamma_strike"])
        features["dist_to_min_gamma"]  = dist_bps(spot, exp_0dte["min_gamma_strike"])
        features["dist_to_min_vanna"]  = dist_bps(spot, exp_0dte["min_vanna_strike"])
        features["dist_to_zero_gamma"] = dist_bps(spot, exp_0dte["zero_gamma"])
        features["dist_to_max_dgex"]   = dist_bps(spot, exp_0dte["max_dgex_strike"])
        features["dist_to_min_dgex"]   = dist_bps(spot, exp_0dte["min_dgex_strike"])
        features["dist_to_max_vega"]   = dist_bps(spot, exp_0dte["max_vega_strike"])
        features["dist_to_min_vega"]   = dist_bps(spot, exp_0dte["min_vega_strike"])
        features["dist_to_max_vomma"]  = dist_bps(spot, exp_0dte["max_vomma_strike"])
        features["dist_to_min_vomma"]  = dist_bps(spot, exp_0dte["min_vomma_strike"])

        features["near_max_gamma"]  = 1 if is_near_level(spot, exp_0dte["max_gamma_strike"]) else 0
        features["near_min_gamma"]  = 1 if is_near_level(spot, exp_0dte["min_gamma_strike"]) else 0
        features["near_min_vanna"]  = 1 if is_near_level(spot, exp_0dte["min_vanna_strike"]) else 0
        features["near_zero_gamma"] = 1 if is_near_level(spot, exp_0dte["zero_gamma"]) else 0

        # ── Weekly features — safe_log to match training ──
        wk_defaults = {
            "wk_net_gamma": 0.0, "wk_net_vanna": 0.0, "wk_net_charm": 0.0,
            "wk_net_dgex": 0.0, "wk_net_zomma": 0.0, "wk_net_delta": 0.0,
            "wk_net_vega": 0.0, "wk_net_vomma": 0.0,
            "wk_dist_to_max_gamma": 0.0, "wk_dist_to_min_gamma": 0.0,
            "wk_dist_to_max_dgex": 0.0, "wk_dist_to_min_dgex": 0.0,
            "wk_dist_to_max_vega": 0.0, "wk_dist_to_min_vega": 0.0,
            "wk_dist_to_max_vomma": 0.0, "wk_dist_to_min_vomma": 0.0,
            "wk_gamma_regime": 0.5, "wk_vanna_bullish": 0,
            "wk_dgex_sticky": 0, "wk_zomma_stabilizing": 0, "wk_vega_elevated": 0,
        }

        if exp_weekly:
            wk_defaults.update({
                # safe_log to match training pipeline
                "wk_net_gamma": safe_log(exp_weekly["net_gamma"]),
                "wk_net_vanna": safe_log(exp_weekly["net_vanna"]),
                "wk_net_charm": safe_log(exp_weekly["net_charm"]),
                "wk_net_dgex":  safe_log(exp_weekly["net_dgex"]),
                "wk_net_zomma": safe_log(exp_weekly["net_zomma"]),
                "wk_net_delta": safe_log(exp_weekly["net_delta"]),
                "wk_net_vega":  safe_log(exp_weekly["net_vega"]),
                "wk_net_vomma": safe_log(exp_weekly["net_vomma"]),
                "wk_dist_to_max_gamma": dist_bps(spot, exp_weekly["max_gamma_strike"]),
                "wk_dist_to_min_gamma": dist_bps(spot, exp_weekly["min_gamma_strike"]),
                "wk_dist_to_max_dgex":  dist_bps(spot, exp_weekly["max_dgex_strike"]),
                "wk_dist_to_min_dgex":  dist_bps(spot, exp_weekly["min_dgex_strike"]),
                "wk_dist_to_max_vega":  dist_bps(spot, exp_weekly["max_vega_strike"]),
                "wk_dist_to_min_vega":  dist_bps(spot, exp_weekly["min_vega_strike"]),
                "wk_dist_to_max_vomma": dist_bps(spot, exp_weekly["max_vomma_strike"]),
                "wk_dist_to_min_vomma": dist_bps(spot, exp_weekly["min_vomma_strike"]),
                "wk_gamma_regime": classify_gamma_regime(exp_weekly["net_gamma"]) / 2.0,
                # thresholds on raw values (pre-safe_log) — 0.1 matches training intent
                "wk_vanna_bullish":     1 if exp_weekly["net_vanna"] > 0.1 else 0,
                "wk_dgex_sticky":       1 if exp_weekly["net_dgex"]  > 0.1 else 0,
                "wk_zomma_stabilizing": 1 if exp_weekly["net_zomma"] > 0.1 else 0,
                "wk_vega_elevated":     1 if abs(exp_weekly["net_vega"]) > 0.1 else 0,
            })
        features.update(wk_defaults)

        # ── Cross-expiry divergence ──
        # sign_divergence compares raw greek signs — use raw exp values, not safe_log'd
        features["gamma_0dte_vs_wk"] = sign_divergence(exp_0dte["net_gamma"], exp_weekly["net_gamma"] if exp_weekly else 0)
        features["vanna_0dte_vs_wk"] = sign_divergence(exp_0dte["net_vanna"], exp_weekly["net_vanna"] if exp_weekly else 0)
        features["dgex_0dte_vs_wk"]  = sign_divergence(exp_0dte["net_dgex"],  exp_weekly["net_dgex"]  if exp_weekly else 0)
        features["delta_0dte_vs_wk"] = sign_divergence(exp_0dte["net_delta"], exp_weekly["net_delta"] if exp_weekly else 0)
        features["vega_0dte_vs_wk"]  = sign_divergence(exp_0dte["net_vega"],  exp_weekly["net_vega"]  if exp_weekly else 0)
        features["vomma_0dte_vs_wk"] = sign_divergence(exp_0dte["net_vomma"], exp_weekly["net_vomma"] if exp_weekly else 0)

        # ── IB levels ──
        ib_high = self.ib_high.get(ticker) or spot
        ib_low = self.ib_low.get(ticker) or spot
        ib_range = max(ib_high - ib_low, 0.01)

        features["price_vs_ib_high"] = dist_bps(spot, ib_high)
        features["price_vs_ib_low"]  = dist_bps(spot, ib_low)
        features["ib_range_pct"] = ib_range / spot if spot > 0 else 0
        features["near_ib_high"] = 1 if is_near_level(spot, ib_high) else 0
        features["near_ib_low"]  = 1 if is_near_level(spot, ib_low) else 0
        features["above_ib"] = 1 if spot > ib_high else 0
        features["below_ib"] = 1 if spot < ib_low else 0
        features["in_ib_range"] = 1 if ib_low <= spot <= ib_high else 0

        # ── Fibonacci (basis points) ──
        fib = calculate_fibonacci_levels(ib_high, ib_low)
        for key in fib:
            features[f"dist_{key}"] = dist_bps(spot, fib[key])

        # ── Confluences ──
        features["confluence_ib_high_max_gamma"] = rbf_confluence(ib_high, exp_0dte["max_gamma_strike"], spot)
        features["confluence_ib_low_min_gamma"]  = rbf_confluence(ib_low, exp_0dte["min_gamma_strike"], spot)
        features["confluence_ib_high_max_vega"]  = rbf_confluence(ib_high, exp_0dte.get("max_vega_strike", 0), spot)
        features["confluence_ib_low_max_dgex"]   = rbf_confluence(ib_low, exp_0dte["max_dgex_strike"], spot)
        features["confluence_fib127_bull_max_gamma"] = rbf_confluence(fib["fib_127_up"], exp_0dte["max_gamma_strike"], spot)
        features["confluence_fib161_bull_max_vega"]  = rbf_confluence(fib["fib_161_up"], exp_0dte.get("max_vega_strike", 0), spot)
        features["confluence_fib127_bear_min_gamma"] = rbf_confluence(fib["fib_127_dn"], exp_0dte["min_gamma_strike"], spot)
        features["confluence_fib161_bear_max_vomma"] = rbf_confluence(fib["fib_161_dn"], exp_0dte.get("max_vomma_strike", 0), spot)
        features["confluence_fib161_bull_max_vomma"] = rbf_confluence(fib["fib_161_up"], exp_0dte.get("max_vomma_strike", 0), spot)
        features["confluence_fib127_bear_min_vomma"] = rbf_confluence(fib["fib_127_dn"], exp_0dte.get("min_vomma_strike", 0), spot)
        features["confluence_fib127_bull_max_dgex"]  = rbf_confluence(fib["fib_127_up"], exp_0dte["max_dgex_strike"], spot)
        features["confluence_fib127_bear_min_dgex"]  = rbf_confluence(fib["fib_127_dn"], exp_0dte["min_dgex_strike"], spot)
        features["confluence_fib161_bull_max_dgex"]  = rbf_confluence(fib["fib_161_up"], exp_0dte["max_dgex_strike"], spot)
        features["confluence_fib161_bear_min_dgex"]  = rbf_confluence(fib["fib_161_dn"], exp_0dte["min_dgex_strike"], spot)

        # ── IV / VIX ──
        atm_iv_norm = atm_iv / 100.0 if atm_iv > 1 else atm_iv
        if atm_iv_norm > 0:
            self.iv_history[ticker].append(atm_iv_norm)
        iv_mean = np.mean(self.iv_history[ticker]) if self.iv_history[ticker] else 0.15
        iv_std = np.std(self.iv_history[ticker]) if len(self.iv_history[ticker]) > 1 else 0
        iv_zscore = float((atm_iv_norm - iv_mean) / iv_std) if iv_std > 0 else 0
        iv_min, iv_max = (min(self.iv_history[ticker]), max(self.iv_history[ticker])) if self.iv_history[ticker] else (0, 1)
        iv_pct = float((atm_iv_norm - iv_min) / (iv_max - iv_min)) if iv_max > iv_min else 0.5

        features["atm_iv"] = atm_iv_norm
        features["iv_zscore"] = np.clip(iv_zscore, -3, 3) / 3.0
        features["iv_percentile"] = iv_pct
        features["vix_spot"] = vix_spot / 50.0 if vix_spot > 0 else 0
        features["vix_gamma"] = 0
        features["vix_regime"] = (2 if vix_spot > 25 else (1 if vix_spot > 18 else 0)) / 2.0

        # ── RSI ──
        prices_list = [p for _, p in self.price_history[ticker]]
        features["rsi"] = simple_rsi(prices_list) / 100.0
        features["vol_relative"] = 0.2

        # ── Greek ratios — safe_log to match training ──
        # Training: "gamma_vanna_ratio": safe_log(exp["net_gamma"] / (abs(exp["net_vanna"]) + 1e-6))
        eps = 1e-6
        features["gamma_vanna_ratio"] = safe_log(exp_0dte["net_gamma"] / (abs(exp_0dte["net_vanna"]) + eps))
        features["dgex_gamma_ratio"]  = safe_log(exp_0dte["net_dgex"]  / (abs(exp_0dte["net_gamma"]) + eps))
        features["charm_vanna_ratio"] = safe_log(exp_0dte["net_charm"] / (abs(exp_0dte["net_vanna"]) + eps))
        features["delta_gamma_ratio"] = safe_log(exp_0dte["net_delta"] / (abs(exp_0dte["net_gamma"]) + eps))
        features["vega_gamma_ratio"]  = safe_log(exp_0dte["net_vega"]  / (abs(exp_0dte["net_gamma"]) + eps))
        features["vomma_vega_ratio"]  = safe_log(exp_0dte["net_vomma"] / (abs(exp_0dte["net_vega"])  + eps))

        # ── Temporal deltas — safe_log to match training ──
        # Training: "gamma_change": safe_log(exp["net_gamma"] - prev_vals["net_gamma"])
        prev = self.prev_features.get(ticker)
        if prev:
            features["gamma_change"]  = safe_log(exp_0dte["net_gamma"] - prev["net_gamma"])
            features["vanna_change"]  = safe_log(exp_0dte["net_vanna"] - prev["net_vanna"])
            features["dgex_change"]   = safe_log(exp_0dte["net_dgex"]  - prev["net_dgex"])
            features["delta_change"]  = safe_log(exp_0dte["net_delta"] - prev.get("net_delta", 0))
            features["vega_change"]   = safe_log(exp_0dte["net_vega"]  - prev.get("net_vega", 0))
            features["vomma_change"]  = safe_log(exp_0dte["net_vomma"] - prev.get("net_vomma", 0))
            features["spot_change"]   = ((spot - prev["spot"]) / prev["spot"] * 10000.0) if prev["spot"] > 0 else 0
            # Training: "gamma_momentum": safe_log((exp["net_gamma"] - prev_vals["net_gamma"]) * np.sign(exp["net_gamma"]))
            features["gamma_momentum"] = safe_log(
                (exp_0dte["net_gamma"] - prev["net_gamma"]) * np.sign(exp_0dte["net_gamma"]))
            features["price_vs_dgex_magnet"] = features["spot_change"] * np.sign(
                (spot - exp_0dte["max_dgex_strike"]) / spot) if spot > 0 and exp_0dte["max_dgex_strike"] else 0
        else:
            for f in ["gamma_change", "vanna_change", "dgex_change", "delta_change",
                       "spot_change", "gamma_momentum", "price_vs_dgex_magnet",
                       "vega_change", "vomma_change"]:
                features[f] = 0.0

        self.prev_features[ticker] = {
            "spot": spot,
            "net_gamma": exp_0dte["net_gamma"], "net_vanna": exp_0dte["net_vanna"],
            "net_dgex": exp_0dte["net_dgex"],   "net_delta": exp_0dte["net_delta"],
            "net_vega": exp_0dte["net_vega"],    "net_vomma": exp_0dte["net_vomma"],
        }

        # ── TLT features ──
        if tlt_spot > 0:
            self.tlt_price_history.append((minutes_since_open, tlt_spot))
            for label, lb in [("1m", 1), ("5m", 5), ("15m", 15)]:
                past_price = self._get_price_n_minutes_ago(self.tlt_price_history, minutes_since_open, lb)
                if past_price and past_price > 0:
                    tlt_norm = 0.05 * np.sqrt(lb)
                    features[f"tlt_ret_{label}"] = float(np.clip((tlt_spot - past_price) / (tlt_norm + 1e-8), -3, 3))
                else:
                    features[f"tlt_ret_{label}"] = 0.0
        else:
            for label in ["1m", "5m", "15m"]:
                features[f"tlt_ret_{label}"] = 0.0

        # ── Historical IB D-1 to D-5 ──
        for i in range(5):
            d = i + 1
            hist = self.historical_ibs[ticker][i] if i < len(self.historical_ibs[ticker]) else None
            if hist is not None:
                h_ib_h = hist['ib_high']
                h_ib_l = hist['ib_low']
                prev_close = hist['close_price']
                ib_mid = (h_ib_h + h_ib_l) / 2.0
                ib_width = h_ib_h - h_ib_l + 1e-6
                features[f"dist_ib_high_D{d}"] = dist_bps(spot, h_ib_h)
                features[f"dist_ib_low_D{d}"]  = dist_bps(spot, h_ib_l)
                features[f"prev_close_vs_ib_D{d}"] = float(np.clip((prev_close - ib_mid) / ib_width, -2, 2))
            else:
                features[f"dist_ib_high_D{d}"] = 0.0
                features[f"dist_ib_low_D{d}"]  = 0.0
                features[f"prev_close_vs_ib_D{d}"] = 0.0

        # ── Gap Features ──
        if self.historical_ibs[ticker] and self.historical_ibs[ticker][0] is not None and len(self.price_history[ticker]) > 0:
            d1_close = self.historical_ibs[ticker][0]['close_price']
            today_open = self.price_history[ticker][0][1]
            if d1_close > 0 and today_open > 0:
                gap_pct = np.clip((today_open - d1_close) / d1_close, -0.02, 0.02)
                gap_direction = 1.0 if gap_pct > 0.001 else (-1.0 if gap_pct < -0.001 else 0.0)
                overnight_vs_ib_ratio = np.clip(abs(today_open - d1_close) / ib_range, 0.0, 3.0)
                features["gap_pct"] = float(gap_pct)
                features["gap_direction"] = float(gap_direction)
                features["overnight_vs_ib_ratio"] = float(overnight_vs_ib_ratio)
            else:
                features["gap_pct"] = 0.0
                features["gap_direction"] = 0.0
                features["overnight_vs_ib_ratio"] = 0.0
        else:
            features["gap_pct"] = 0.0
            features["gap_direction"] = 0.0
            features["overnight_vs_ib_ratio"] = 0.0

        # ── OpEx Proximity ──
        dt = now_et
        year, month = dt.year, dt.month
        cal = calendar.Calendar(firstweekday=0)
        fridays = [d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] == 4]
        third_friday = fridays[2][0] if len(fridays) >= 3 else fridays[-1][0]
        opex_date = datetime(year, month, third_friday, tzinfo=ET)
        days_to_opex = (opex_date - dt).days
        if days_to_opex < 0:
            nm = month + 1 if month < 12 else 1
            ny = year if month < 12 else year + 1
            fridays_next = [d for d in calendar.Calendar().itermonthdays2(ny, nm) if d[0] != 0 and d[1] == 4]
            third_friday_next = fridays_next[2][0] if len(fridays_next) >= 3 else fridays_next[-1][0]
            opex_date = datetime(ny, nm, third_friday_next, tzinfo=ET)
            days_to_opex = (opex_date - dt).days
        is_quarterly = opex_date.month in (3, 6, 9, 12)
        features["days_to_opex_norm"] = float(np.clip(days_to_opex / 21.0, 0.0, 1.0))
        features["is_opex_week"] = 1.0 if abs(days_to_opex) <= 5 else 0.0
        features["is_quarterly_opex_week"] = 1.0 if abs(days_to_opex) <= 5 and is_quarterly else 0.0

        # ── Volatility Risk Premium (RVOL) ──
        closes = [h['close_price'] for h in self.historical_ibs[ticker] if h is not None and h.get('close_price', 0) > 0]
        if len(closes) >= 5:
            closes_arr = np.array(closes[::-1])
            log_rets = np.diff(np.log(closes_arr))
            if len(log_rets) >= 4:
                rvol_full = float(np.std(log_rets) * np.sqrt(252))
                ratio = rvol_full / (atm_iv_norm + 1e-6)
                features["rvol_iv_log"] = float(np.clip(np.log(max(ratio, 1e-6)), -1.5, 1.5))
                rvol_5d = float(np.std(log_rets[-min(5, len(log_rets)):]) * np.sqrt(252))
                features["rvol_trend"] = float(np.clip((rvol_5d - rvol_full) / (atm_iv_norm + 1e-6), -1.0, 1.0))
                features["rvol_regime"] = 0.0 if ratio < 0.85 else (2.0 if ratio > 1.15 else 1.0)
            else:
                features["rvol_iv_log"] = 0.0
                features["rvol_trend"] = 0.0
                features["rvol_regime"] = 1.0
        else:
            features["rvol_iv_log"] = 0.0
            features["rvol_trend"] = 0.0
            features["rvol_regime"] = 1.0

        # ── Signal Persistence ──
        self.net_charm_history[ticker].append(math.copysign(1.0, exp_0dte["net_charm"]))
        signal_persistence_5m = 0
        if len(self.net_charm_history[ticker]) > 0:
            current_bias = self.net_charm_history[ticker][-1]
            for x in reversed(self.net_charm_history[ticker]):
                if x == current_bias: signal_persistence_5m += current_bias
                else: break
        features["signal_persistence_5m"] = signal_persistence_5m

        # ── Hilbert phase of net gamma ──
        self.net_gamma_window[ticker].append(exp_0dte["net_gamma"])
        if len(self.net_gamma_window[ticker]) >= 30:
            try:
                gamma_arr = np.array(self.net_gamma_window[ticker])
                gamma_detrended = gamma_arr - np.mean(gamma_arr)
                gamma_std = np.std(gamma_detrended) + 1e-8
                gamma_normalized = gamma_detrended / gamma_std
                pad_len = max(1, len(gamma_normalized) // 4)
                left_pad = gamma_normalized[pad_len:0:-1]
                right_pad = gamma_normalized[-2:-(pad_len + 2):-1]
                padded_gamma = np.concatenate([left_pad, gamma_normalized, right_pad])
                analytic_padded = scipy_hilbert(padded_gamma)
                analytic_signal = analytic_padded[len(left_pad):len(left_pad) + len(gamma_normalized)]
                amplitude_envelope = np.abs(analytic_signal)
                instant_phase = np.angle(analytic_signal)
                current_phase = float(instant_phase[-1])
                current_amplitude = float(amplitude_envelope[-1])
                mean_amplitude = float(np.mean(amplitude_envelope))
                amplitude_ratio = float(np.clip(current_amplitude / (mean_amplitude + 1e-8), 0.0, 3.0))
                phase_delta_norm = 0.0
                if len(self.net_gamma_window[ticker]) >= 2:
                    unwrapped = np.unwrap(instant_phase)
                    phase_delta_norm = float(np.clip((unwrapped[-1] - unwrapped[-2]) / np.pi, -1.0, 1.0))
                signal_quality = 1.0 if amplitude_ratio > 0.5 else 0.0
                features["gamma_phase_sin"] = float(np.sin(current_phase)) * signal_quality
                features["gamma_phase_cos"] = float(np.cos(current_phase)) * signal_quality
                features["gamma_amplitude_ratio"] = amplitude_ratio
                features["gamma_phase_delta"] = phase_delta_norm * signal_quality
            except:
                features["gamma_phase_sin"] = 0.0
                features["gamma_phase_cos"] = 0.0
                features["gamma_amplitude_ratio"] = 0.0
                features["gamma_phase_delta"] = 0.0
        else:
            features["gamma_phase_sin"] = 0.0
            features["gamma_phase_cos"] = 0.0
            features["gamma_amplitude_ratio"] = 0.0
            features["gamma_phase_delta"] = 0.0

        # ── Gamma Speed — safe_log to match training ──
        # Training: "gamma_speed": safe_log(gamma_speed_val)
        gamma_speed_val = 0.0
        if exp_0dte.get('_df') is not None and not exp_0dte['_df'].empty:
            df_pq = exp_0dte['_df']
            if 'pq_net_gamma' in df_pq.columns:
                delta_s = 5.0 if spot > 1000 else 1.0
                g_by_strike = df_pq.groupby('strike')['pq_net_gamma'].sum()
                strikes = g_by_strike.index.values
                if len(strikes) >= 2:
                    idx_upper = int(np.argmin(np.abs(strikes - (spot + delta_s))))
                    idx_lower = int(np.argmin(np.abs(strikes - (spot - delta_s))))
                    if idx_upper != idx_lower:
                        gamma_upper = float(g_by_strike.iloc[idx_upper])
                        gamma_lower = float(g_by_strike.iloc[idx_lower])
                        speed_raw = (gamma_upper - gamma_lower) / (2.0 * delta_s)
                        speed_scaled = speed_raw * (day_atr ** 2)
                        speed_norm = float(np.sign(speed_scaled) * np.log1p(np.abs(speed_scaled)))
                        gamma_speed_val = float(np.clip(speed_norm, -20.0, 20.0))
        features["gamma_speed"] = safe_log(gamma_speed_val)

        # ── Charm Acceleration ──
        charm_accel_weighted = 0.0
        if len(self.net_charm_history[ticker]) >= 3:
            charm_arr = np.array(list(self.net_charm_history[ticker])[-3:])
            charm_accel = charm_arr[-1] - 2.0 * charm_arr[-2] + charm_arr[-3]
            charm_accel_norm = float(np.clip(charm_accel / (atm_iv_norm + 1e-6), -5.0, 5.0))
            minutes_to_close = max(0.0, 390.0 - minutes_since_open)
            close_weight = 1.0 + np.exp(-minutes_to_close / 60.0)
            charm_accel_weighted = float(np.clip(charm_accel_norm * close_weight, -10.0, 10.0))
        features["charm_accel_weighted"] = charm_accel_weighted

        # ── Vol-adjusted returns & RSI ──
        prices_before = [p for _, p in self.price_history[ticker]]
        rsi = simple_rsi(prices_before)
        features["rsi"] = rsi / 100.0
        
        atm_iv_for_norm = atm_iv_norm if atm_iv_norm > 0.001 else 0.15
        for label, lb in [("1m", 1), ("5m", 5), ("15m", 15), ("30m", 30)]:
            past_price = self._get_price_n_minutes_ago(self.price_history[ticker], minutes_since_open, lb)
            if past_price and past_price > 0:
                raw_return = (spot - past_price) / past_price
                vol_norm = atm_iv_for_norm * np.sqrt(lb / (252.0 * 390.0)) + 1e-8
                features[f"ret_{label}_vol_adj"] = float(np.clip(raw_return / vol_norm, -5, 5))
            else:
                features[f"ret_{label}_vol_adj"] = 0.0
                
        # ── Gap & IB features ──
        if self.historical_ibs[ticker] and self.historical_ibs[ticker][0] is not None:
            prev_close = self.historical_ibs[ticker][0].get('close', spot)
            if prev_close and prev_close > 0:
                gap_pct = (spot - prev_close) / prev_close
                features["gap_pct"] = float(np.clip(gap_pct * 100.0, -5.0, 5.0))
                features["gap_direction"] = 1.0 if gap_pct > 0.001 else (-1.0 if gap_pct < -0.001 else 0.0)
                if ib_high > ib_low:
                    features["overnight_vs_ib_ratio"] = float(np.clip(abs(spot - prev_close) / (ib_high - ib_low), 0.0, 10.0))
                else:
                    features["overnight_vs_ib_ratio"] = 0.0
        if "gap_pct" not in features:
            features["gap_pct"] = 0.0
            features["gap_direction"] = 0.0
            features["overnight_vs_ib_ratio"] = 0.0
            
        # ── IV and VRP context ──
        if ticker not in getattr(self, 'iv_history', {}):
            self.iv_history = {t: [] for t in self.systems.keys()}
        self.iv_history[ticker].append(atm_iv_norm)
        while len(self.iv_history[ticker]) > 30:
            if hasattr(self.iv_history[ticker], 'popleft'):
                self.iv_history[ticker].popleft()
            else:
                self.iv_history[ticker].pop(0)
            
        iv_hist_arr = self.iv_history[ticker]
        iv_min = min(iv_hist_arr)
        iv_max = max(iv_hist_arr)
        iv_pct = float((atm_iv_norm - iv_min) / (iv_max - iv_min)) if iv_max > iv_min else 0.5
        iv_mean = np.mean(iv_hist_arr)
        iv_std = np.std(iv_hist_arr)
        iv_zscore = float((atm_iv_norm - iv_mean) / iv_std) if iv_std > 1e-6 else 0.0
        
        features["iv_percentile"] = iv_pct
        features["iv_zscore"] = float(np.clip(iv_zscore, -3.0, 3.0) / 3.0)
        
        # We don't have intraday minute-by-minute total volume easily accessible in RT yet, 
        # so vol_relative defaults to 1.0 (neutral) to match training average for now.
        vol_relative = features.get("vol_relative", 1.0)
        
        features["rvol_iv_log"] = safe_log(vol_relative / (atm_iv_norm + 1e-6))
        features["rvol_trend"] = float(np.clip((vol_relative - 1.0)/1.0, -2.0, 2.0))
        features["rvol_regime"] = 1.0 if vol_relative > 1.2 else (0.0 if vol_relative < 0.8 else 0.5)

        # ── Time encoding ──
        features["time_sin"] = float(np.sin(2 * np.pi * minutes_since_open / 390))
        features["time_cos"] = float(np.cos(2 * np.pi * minutes_since_open / 390))
        features["minutes_to_close_norm"] = max(0, 390 - minutes_since_open) / 390.0
        features["dow_sin"] = float(np.sin(2 * np.pi * now_et.weekday() / 5))
        features["dow_cos"] = float(np.cos(2 * np.pi * now_et.weekday() / 5))

        # ── D-1 IB confluences ──
        if self.historical_ibs[ticker] and self.historical_ibs[ticker][0] is not None:
            d1_ib_high = self.historical_ibs[ticker][0]['ib_high']
            d1_ib_low  = self.historical_ibs[ticker][0]['ib_low']
            features["confluence_d1ibh_max_gamma"]  = rbf_confluence(d1_ib_high, exp_0dte["max_gamma_strike"], spot)
            features["confluence_d1ibl_min_gamma"]  = rbf_confluence(d1_ib_low,  exp_0dte["min_gamma_strike"], spot)
            features["confluence_d1ibh_max_dgex"]   = rbf_confluence(d1_ib_high, exp_0dte["max_dgex_strike"], spot)
            features["confluence_d1ibl_min_dgex"]   = rbf_confluence(d1_ib_low,  exp_0dte["min_dgex_strike"], spot)
            features["confluence_d1ibh_max_vomma"]  = rbf_confluence(d1_ib_high, exp_0dte.get("max_vomma_strike", 0), spot)
            features["confluence_d1ibh_ibh_today"]  = rbf_confluence(d1_ib_high, ib_high, spot)
            features["confluence_d1ibl_ibl_today"]  = rbf_confluence(d1_ib_low,  ib_low, spot)
        else:
            for key in ["confluence_d1ibh_max_gamma", "confluence_d1ibl_min_gamma",
                        "confluence_d1ibh_max_dgex", "confluence_d1ibl_min_dgex",
                        "confluence_d1ibh_max_vomma",
                        "confluence_d1ibh_ibh_today", "confluence_d1ibl_ibl_today"]:
                features[key] = 0.0

        # ── IB Range Percentile ──
        past_ranges = [h['ib_high'] - h['ib_low'] for h in self.historical_ibs[ticker] if h is not None]
        if past_ranges:
            current_ib_range = ib_high - ib_low
            features["ib_range_percentile"] = sum(r < current_ib_range for r in past_ranges) / len(past_ranges)
        else:
            features["ib_range_percentile"] = 0.5

        # ── Wonham Trend Probability ──
        prices_so_far = [p for _, p in self.price_history[ticker]]
        if len(prices_so_far) >= 5:
            x = np.arange(len(prices_so_far), dtype=float)
            slope = np.polyfit(x, prices_so_far, 1)[0]
            trend_norm = float(np.clip(slope / (prices_so_far[-1] * 0.0001), -1.0, 1.0))
            features["wonham_trend_prob"] = float(np.clip((trend_norm + 1.0) / 2.0, 0.0, 1.0))
        else:
            features["wonham_trend_prob"] = 0.5

        # ── Delta-filtered PCR proxy ──
        delta_filtered_pcr_norm = 0.0
        pcr_derivative_5m_clipped = 0.0
        if exp_0dte.get('_df') is not None and not exp_0dte['_df'].empty:
            df_pq = exp_0dte['_df']
            if 'volume' in df_pq.columns:
                otm_range = 1.5 * day_atr
                df_calls_otm = df_pq[
                    (df_pq['right'].str.upper() == 'CALL') &
                    (df_pq['strike'].between(spot, spot + otm_range))
                ]
                df_puts_otm = df_pq[
                    (df_pq['right'].str.upper() == 'PUT') &
                    (df_pq['strike'].between(spot - otm_range, spot))
                ]
                call_vol = float(df_calls_otm['volume'].sum())
                put_vol = float(df_puts_otm['volume'].sum())
                delta_filtered_pcr_raw = put_vol / (call_vol + 1e-6)
                delta_filtered_pcr_norm = float(np.clip(np.log1p(delta_filtered_pcr_raw) / np.log1p(5.0), 0.0, 1.0))

                self.pcr_history[ticker].append(delta_filtered_pcr_raw)
                if len(self.pcr_history[ticker]) >= 5:
                    pcr_history_list = list(self.pcr_history[ticker])
                    pcr_derivative_5m_clipped = float(np.clip(
                        (pcr_history_list[-1] - pcr_history_list[-5]) / 5.0, -1.0, 1.0))
        features["delta_filtered_pcr"] = delta_filtered_pcr_norm
        features["pcr_derivative_5m"] = pcr_derivative_5m_clipped

        # ── Interaction features ──
        near_ib_high = 1 if is_near_level(spot, ib_high) else 0
        near_ib_low  = 1 if is_near_level(spot, ib_low) else 0
        speed_norm = features.get("gamma_speed", 0.0)
        charm_accel_norm = features.get("charm_accel_weighted", 0.0)

        features["speed_x_near_ib_high"] = speed_norm * near_ib_high
        features["speed_x_near_ib_low"]  = speed_norm * near_ib_low
        features["charm_accel_x_near_ib_high"] = charm_accel_norm * near_ib_high
        features["charm_accel_x_near_ib_low"]  = charm_accel_norm * near_ib_low

        # ── Level identity — nearest named level ──
        named_levels = {
            "ib_high":    ib_high,    "ib_low":     ib_low,
            "fib_127_up": fib["fib_127_up"], "fib_161_up": fib["fib_161_up"],
            "fib_200_up": fib["fib_200_up"], "fib_127_dn": fib["fib_127_dn"],
            "fib_161_dn": fib["fib_161_dn"], "fib_200_dn": fib["fib_200_dn"],
        }
        LEVEL_IDENTITY_MAP = {
            "ib_high": 0, "ib_low": 1,
            "fib_127_up": 2, "fib_161_up": 3, "fib_200_up": 4,
            "fib_127_dn": 5, "fib_161_dn": 6, "fib_200_dn": 7,
            "none": 8,
        }
        best_name, best_dist = "none", float('inf')
        for name, level in named_levels.items():
            if level is None or level <= 0:
                continue
            d = abs(spot - level) / spot
            if d < LEVEL_PROXIMITY_THRESHOLD and d < best_dist:
                best_dist = d
                best_name = name
        features["nearest_level_id"] = float(LEVEL_IDENTITY_MAP[best_name])
        features["nearest_level_dist_bps"] = float(np.clip(best_dist * 10000.0, 0.0, BPS_CLIP)) if best_name != "none" else float(BPS_CLIP)

        # ── Signal Persistence & TLT ──
        # Net charm history handles persistence
        if ticker not in getattr(self, 'net_charm_history', {}):
            self.net_charm_history = {t: deque(maxlen=5) for t in self.systems.keys()}
            
        current_charm_sign = math.copysign(1.0, features.get("net_charm", 0.0))
        self.net_charm_history[ticker].append(current_charm_sign)
        
        signal_persistence_5m = 0.0
        if len(self.net_charm_history[ticker]) > 0:
            hist_list = list(self.net_charm_history[ticker])
            current_bias = hist_list[-1]
            for x in reversed(hist_list):
                if x == current_bias:
                    signal_persistence_5m += current_bias
                else: break
        features["signal_persistence_5m"] = signal_persistence_5m
        
        # TLT missing values (assume proxy or flat if missing)
        for label in ["tlt_ret_1m", "tlt_ret_5m", "tlt_ret_15m"]:
            if label not in features: features[label] = 0.0

        # ── Greek × Level interaction scalars ──
        # Training uses safe_log on raw net_delta/net_gamma/net_vanna then multiplies by proximity flag
        near_any_fib_up = any(is_near_level(spot, fib[k]) for k in ["fib_127_up", "fib_161_up", "fib_200_up"])
        near_any_fib_dn = any(is_near_level(spot, fib[k]) for k in ["fib_127_dn", "fib_161_dn", "fib_200_dn"])
        near_ib_flag = bool(near_ib_high or near_ib_low)

        net_delta_sl  = safe_log(exp_0dte["net_delta"])
        net_gamma_sl  = safe_log(exp_0dte["net_gamma"])
        net_vanna_sl  = safe_log(exp_0dte["net_vanna"])

        features["gamma_x_near_fib_up"]  = net_gamma_sl * float(near_any_fib_up)
        features["gamma_x_near_fib_dn"]  = net_gamma_sl * float(near_any_fib_dn)
        features["gamma_x_near_ib"]      = net_gamma_sl * float(near_ib_flag)
        features["delta_x_near_fib_up"]  = net_delta_sl * float(near_any_fib_up)
        features["delta_x_near_fib_dn"]  = net_delta_sl * float(near_any_fib_dn)
        features["delta_x_near_ib_high"] = net_delta_sl * float(near_ib_high)
        features["delta_x_near_ib_low"]  = net_delta_sl * float(near_ib_low)
        features["vanna_x_near_fib_up"]  = net_vanna_sl * float(near_any_fib_up)
        features["vanna_x_near_fib_dn"]  = net_vanna_sl * float(near_any_fib_dn)
        features["vanna_x_near_ib"]      = net_vanna_sl * float(near_ib_flag)

        # ── Build final vector ──
        return np.array([features.get(col, 0.0) for col in FEATURE_COLUMNS], dtype=np.float32)

    @staticmethod
    def _get_price_n_minutes_ago(history: deque, current_min: float, n_min: int):
        """Retrieve price from N minutes ago."""
        target_min = current_min - n_min
        best_price = None
        best_diff = float('inf')
        for (t, p) in history:
            if t > current_min:
                continue
            diff = abs(t - target_min)
            if diff < best_diff:
                best_diff = diff
                best_price = p
        return best_price if best_diff <= 2.0 else None

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

            del self.gbm_trackers[ticker]
            self._save_gbm_trackers()

    def process_ticker(self, ticker: str):
        """Process a single ticker through GBM+RL pipeline."""
        now = datetime.now(ET)
        
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

        FROZEN_CYCLES_THRESHOLD = 2  # ciclos de 30s = 60s congelado
        prev_spot = self._frozen_spot_prev.get(ticker, 0.0)

        if prev_spot > 0 and spot == prev_spot:
            self._frozen_spot_count[ticker] += 1
            count = self._frozen_spot_count[ticker]

            if count >= FROZEN_CYCLES_THRESHOLD:
                # Resetear prev_features: en el próximo ciclo los deltas
                # (spot_change, gamma_change, etc.) serán 0 en vez de
                # acumularse sobre una base contaminada. Pero al menos
                # el GBM no verá un vector de "todo igual que siempre".
                self.prev_features.pop(ticker, None)
                logger.warning(
                    f"[{ticker}] SPOT CONGELADO {count} ciclos @ {spot:.2f} "
                    f"— prev_features reseteado, saltando ciclo"
                )
                return  # no procesar hasta que el feed se recupere

            else:
                logger.warning(
                    f"[{ticker}] spot repetido ({count}/{FROZEN_CYCLES_THRESHOLD}) "
                    f"@ {spot:.2f} — vigilando"
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

        # 2. Load spot candles and compute IB (once per session per ticker)
        if self.ib_high[ticker] is None:
            df_spot = self._load_spot_candles()
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
            trades_file = os.path.join(TRADES_DIR, f"trades_{now.strftime('%Y%m%d')}.json")
            try:
                existing = []
                if os.path.exists(trades_file):
                    with open(trades_file) as f:
                        existing = json.load(f)
                existing.append(trade)
                with open(trades_file, "w") as f:
                    json.dump(existing, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save trade: {e}")

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