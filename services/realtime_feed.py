"""
Real-Time Options + Spot Feed — Parquet-based for MLP+RL Bot

60-second polling daemon that fetches from ThetaData:
  - SPXW 0DTE:   Greeks, OI, IV, OHLC (all strikes, calls+puts)
  - SPXW Weekly:  Greeks, OI            (all strikes, calls+puts)
  - Spot prices:  SPX, VIX, TLT         (1-min OHLC candles)

Friday logic: 0DTE = today, weekly = NEXT Friday (never same as 0DTE).

All output saved as Parquet in rt_data/{YYYYMMDD}/ — overwritten each poll.

Usage:
    python services/realtime_feed.py --dry-run
    python services/realtime_feed.py
"""

import sys
import httpx
import os
import asyncio
import argparse
import signal
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import deque

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THETADATA_API = os.path.join(PROJECT_ROOT, "thetadata-api")
sys.path.insert(0, THETADATA_API)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural"))

from thetadata_api.client import ThetaClient
from thetadata_api.corrector import fix_dataframe
from thetadata_api.utils import fetch_with_interval_fallback, parse_response, get_logger
from services.compute_features import get_net_exposures_from_parquet, calculate_exact_t
from neural.hybrid_model import FEATURE_COLUMNS

logger = get_logger("RealtimeFeed")

ET = ZoneInfo("America/New_York")

# ── Feature transforms (must match training pipeline exactly) ──
import math as _math

def safe_log(x: float) -> float:
    """Sign-preserving log-transform: sign(x) * log1p(|x|)."""
    return _math.copysign(_math.log1p(abs(x)), x)

BPS_CLIP = 500

def dist_bps(spot: float, level: float) -> float:
    """Percentage distance from spot to level in basis points, clamped."""
    if spot <= 0 or level <= 0:
        return 0.0
    return float(np.clip((spot - level) / spot * 10000.0, -BPS_CLIP, BPS_CLIP))

# ─────────────────────────────────────────────
# LEVEL PROXIMITY THRESHOLD (mirrors bot)
# ─────────────────────────────────────────────
LEVEL_PROXIMITY_THRESHOLD = 0.0004

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Options endpoints
OPTIONS_ENDPOINTS = {
    "greeks": "/option/history/greeks/first_order",
    "oi":     "/option/history/open_interest",
    "iv":     "/option/history/greeks/implied_volatility",
    "ohlc":   "/option/history/ohlc",
}

# Which endpoints to fetch for 0DTE vs weekly
ENDPOINTS_0DTE  = ["greeks", "oi", "iv", "ohlc"]
ENDPOINTS_WEEKLY = ["greeks", "oi"]

# Spot indices/stocks to fetch
SPOT_SYMBOLS = ["SPX", "QQQ", "VIX", "TLT"]

# Map trading ticker → options symbol
OPTIONS_TICKERS = {
    "SPX": "SPXW",   # SPX uses SPXW options
    "QQQ": "QQQ",    # QQQ uses QQQ options directly
}


class RealtimeOptionsFeed:
    """
    Real-time options + spot feed for GBM+RL bot.

    Polls every 60 seconds during market hours.
    Fetches SPXW + QQQ options (0DTE + weekly) + spot prices.
    Saves all data as Parquet files in rt_data/{YYYYMMDD}/.
    """

    def __init__(self, poll_interval: int = 60, output_dir: str = None):
        self.client = ThetaClient()
        self.poll_interval = poll_interval
        self.running = False

        today_str = datetime.now(ET).strftime("%Y%m%d")
        self.output_dir = Path(output_dir or os.path.join(PROJECT_ROOT, "rt_data", today_str))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Expiration cache — per ticker: {"SPX": (0dte, weekly), "QQQ": (0dte, weekly)}
        self._expirations = {}  # ticker -> (exp_0dte, exp_weekly)
        self._expirations_resolved = False
        self._historical_backfilled = False

        # Base rt_data directory (parent of per-day dirs)
        self._rt_data_base = Path(output_dir or os.path.join(PROJECT_ROOT, "rt_data"))
        self._rt_data_base.mkdir(parents=True, exist_ok=True)

        # ── ML feature computation state (per-ticker) ──
        self.price_history = {}    # ticker -> deque(maxlen=35)
        self.iv_history = {}       # ticker -> deque(maxlen=60)
        self.tlt_price_history = deque(maxlen=35)  # shared (TLT is global)
        self.ib_high = {}          # ticker -> float
        self.ib_low = {}           # ticker -> float
        self.historical_ibs = {}   # ticker -> list[dict|None]
        self.prev_features = {}    # ticker -> dict
        self._ml_features_rows = {}  # ticker -> list of rows
        self._historical_ib_loaded = {}  # ticker -> bool

        # Initialize per-ticker structures
        for tk in OPTIONS_TICKERS:
            self.price_history[tk] = deque(maxlen=35)
            self.iv_history[tk] = deque(maxlen=60)
            self.ib_high[tk] = None
            self.ib_low[tk] = None
            self.historical_ibs[tk] = []
            self._ml_features_rows[tk] = []
            self._historical_ib_loaded[tk] = False

    # ─────────────────────────────────────────
    # EXPIRATION RESOLUTION
    # ─────────────────────────────────────────

    def _compute_target_expirations(self, today: date, available_exps: list[date]):
        """
        Compute 0DTE and weekly target expirations.

        Rules:
          - 0DTE: today's date (must be in available_exps)
          - Weekly: this week's Friday. If Friday is not available (holiday),
            walk backward to Thursday, Wednesday, etc.
            If the weekly == 0DTE (today IS the weekly exp), jump to next week's
            Friday and repeat the walk-backward.
        """
        avail_set = set(available_exps)

        # 0DTE = today
        exp_0dte = today if today in avail_set else None

        def _find_weekly_for_week(target_friday: date) -> date:
            """Walk backward from target Friday through available exps."""
            # Try Friday, Thursday, Wednesday, Tuesday, Monday
            for offset in range(5):
                candidate = target_friday - timedelta(days=offset)
                if candidate in avail_set and candidate > today:
                    return candidate
                # Also allow candidate == today only if it differs from 0DTE
                if candidate in avail_set and candidate == today and candidate != exp_0dte:
                    return candidate
            return None

        # This week's Friday
        days_to_friday = (4 - today.weekday()) % 7
        if days_to_friday == 0:
            this_friday = today  # today is Friday
        else:
            this_friday = today + timedelta(days=days_to_friday)

        exp_weekly = _find_weekly_for_week(this_friday)

        # If weekly matches 0DTE (e.g., today is Friday and is also the weekly exp),
        # or if no weekly found this week, try next week
        if exp_weekly is None or (exp_0dte and exp_weekly == exp_0dte):
            next_friday = this_friday + timedelta(days=7)
            exp_weekly = _find_weekly_for_week(next_friday)

        return exp_0dte, exp_weekly

    async def _resolve_expirations(self):
        """Fetch available expirations from ThetaData for each ticker and compute targets."""
        today = datetime.now(ET).date()
        today_str = today.strftime("%Y%m%d")

        all_resolved = True
        for ticker, options_symbol in OPTIONS_TICKERS.items():
            try:
                exps = await self.client.get_expirations(options_symbol, today_str)
            except Exception as e:
                logger.warning(f"Cannot get expirations for {options_symbol}: {e}")
                all_resolved = False
                continue

            available = []
            for exp_str in exps:
                try:
                    exp_date = date(int(exp_str[:4]), int(exp_str[4:6]), int(exp_str[6:8]))
                    available.append(exp_date)
                except (ValueError, IndexError):
                    continue

            exp_0dte, exp_weekly = self._compute_target_expirations(today, available)
            self._expirations[ticker] = (exp_0dte, exp_weekly)
            logger.info(f"Expirations [{options_symbol}]: 0DTE={exp_0dte} | Weekly={exp_weekly}")

        self._expirations_resolved = all_resolved or len(self._expirations) > 0

    # ─────────────────────────────────────────
    # OPTIONS CHAIN DOWNLOAD
    # ─────────────────────────────────────────

    async def _fetch_options_data(self, options_symbol: str, expiration: date, endpoint_key: str, spot_price: float = 0.0) -> pd.DataFrame:
        """
        Fetch options data para el simbolo, endpoint y expiracion dados.
        Filtra strikes que estén fuera de ±2% del spot_price actual.
        """
        now_et = datetime.now(ET)
        today_str = now_et.strftime("%Y%m%d")
        exp_str = expiration.strftime("%Y%m%d")
        endpoint = OPTIONS_ENDPOINTS[endpoint_key]

        window_start = (now_et - timedelta(seconds=60)).strftime("%H:%M:%S")
        window_end   = now_et.strftime("%H:%M:%S")

        base_url = getattr(self.client, "base_url", "http://127.0.0.1:25503/v3")
        all_rows = []

        # No client-side strike filter — API fetches all strikes with strike="*"
        # and features like net_gamma/net_delta need the full chain for accuracy.
        min_strike = 0.0
        max_strike = float('inf')

        for right in ["C", "P"]:
            params = {
                "symbol":     options_symbol,
                "expiration": exp_str,
                "strike":     "*",
                "right":      right,
                "date":       today_str,
                "start_time": window_start,
                "end_time":   window_end,
                "format":     "json",
            }

            try:
                async with httpx.AsyncClient(timeout=30.0) as hx:
                    response = await hx.get(f"{base_url}{endpoint}", params=params)

                if response.status_code != 200:
                    logger.warning(
                        f"[{options_symbol}] {endpoint_key} {right} exp={exp_str}: "
                        f"HTTP {response.status_code}"
                    )
                    continue

                raw = response.json()

                if isinstance(raw, dict) and ("error_code" in raw or "code" in raw):
                    err_code = raw.get("error_code") or raw.get("code")
                    err_msg  = raw.get("error") or raw.get("message") or str(raw)
                    logger.warning(
                        f"[{options_symbol}] {endpoint_key} {right} exp={exp_str}: "
                        f"ThetaData error {err_code} -- {err_msg}"
                    )
                    continue

                items = parse_response(raw) if not isinstance(raw, list) else raw
                if not isinstance(items, list) or not items:
                    continue

                # Define si el endpoint debería tener datos de precio para aplicar el filtro
                needs_price_filter = endpoint_key in ["greeks", "ohlc"]

                rows = []
                for item in items:
                    if isinstance(item, dict) and "contract" in item and "data" in item:
                        contract = item["contract"]
                        
                        # --- FILTRO ±2% ---
                        strike = float(contract.get("strike", 0))
                        if spot_price > 0 and (strike < min_strike or strike > max_strike):
                            continue
                        # ------------------

                        for datarow in item.get("data", []):
                            # ZERO-PRICE FILTER (Solo para Griegas y OHLC)
                            if needs_price_filter:
                                price_val = datarow.get("close") or datarow.get("underlying_price") or 0
                                if price_val == 0:
                                    continue
                                    
                            rows.append({**contract, **datarow})
                            
                    elif isinstance(item, dict):
                        # --- FILTRO ±2% (caso diccionario plano) ---
                        strike = float(item.get("strike", 0))
                        if spot_price > 0 and (strike < min_strike or strike > max_strike):
                            continue
                        # -------------------------------------------

                        # ZERO-PRICE FILTER (Solo para Griegas y OHLC)
                        if needs_price_filter:
                            price_val = item.get("close") or item.get("underlying_price") or 0
                            if price_val == 0:
                                continue
                                
                        rows.append(item)

                if rows:
                    df_part = pd.DataFrame(rows)
                    if 'right' not in df_part.columns:
                        df_part['right'] = "CALL" if right == "C" else "PUT"
                    else:
                        df_part['right'] = df_part['right'].replace({"C": "CALL", "P": "PUT"})
                    all_rows.append(df_part)

            except Exception as e:
                logger.warning(f"[{options_symbol}] {endpoint_key} {right} exp={exp_str}: {e}")

        if not all_rows:
            return pd.DataFrame()

        df = pd.concat(all_rows, ignore_index=True)
        df['expiration'] = exp_str
        df['trade_date'] = today_str

        return df
    # ─────────────────────────────────────────
    # SPOT PRICE DOWNLOAD
    # ─────────────────────────────────────────

    async def _fetch_spot(self, symbol: str) -> pd.DataFrame:
        """Fetch intraday 1-min OHLC candles derived from options Greeks."""
        today_str = datetime.now(ET).strftime("%Y%m%d")

        try:
            res = await self.client.fetch_underlying_ohlc(symbol, today_str, interval="1m")
            if res and not res.data.empty:
                df = res.data.copy()
                df = self._fix_ohlc_zeros(df)
                return df
        except Exception as e:
            logger.warning(f"Error deriving spot {symbol}: {e}")

        return pd.DataFrame()

    @staticmethod
    def _fix_ohlc_zeros(df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix zero values in OHLC columns.

        For each row, if any of open/high/low/close is 0, replace it with the
        first non-zero value from the same row. Drop rows where ALL OHLC are zero.
        This handles the known issue with underlying_derived having zeros at 9:30.
        """
        ohlc_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
        if not ohlc_cols:
            return df

        # Drop rows where ALL OHLC are zero (no salvageable data)
        all_zero_mask = (df[ohlc_cols] == 0).all(axis=1)
        if all_zero_mask.any():
            n_dropped = all_zero_mask.sum()
            df = df[~all_zero_mask].copy()
            if n_dropped > 0:
                logger.debug(f"  Dropped {n_dropped} all-zero OHLC rows")

        # For rows with SOME zeros, fill with the first non-zero col in that row
        for col in ohlc_cols:
            zero_mask = df[col] == 0
            if not zero_mask.any():
                continue
            # Find a non-zero value from the other OHLC columns in the same row
            other_cols = [c for c in ohlc_cols if c != col]
            for other in other_cols:
                fill_mask = zero_mask & (df[other] != 0)
                if fill_mask.any():
                    df.loc[fill_mask, col] = df.loc[fill_mask, other]
                    zero_mask = df[col] == 0

        return df

    # ─────────────────────────────────────────
    # SAVE TO PARQUET
    # ─────────────────────────────────────────

    def _save_parquet(self, df: pd.DataFrame, filename: str):
        """Guarda DataFrame como Parquet, sobreescribiendo el anterior.
        Filtro de seguridad: elimina filas donde underlying_price=0 antes de guardar.
        """
        if df.empty:
            return
        # Filtro de seguridad: underlying_price=0 corrompe net_gamma/delta/vanna
        if 'underlying_price' in df.columns:
            before = len(df)
            df = df[df['underlying_price'] > 0]
            removed = before - len(df)
            if removed > 0:
                logger.debug(f"  [filter] {filename}: eliminadas {removed} filas con underlying_price=0")
        if df.empty:
            logger.debug(f"  [filter] {filename}: DataFrame vacio tras filtro, no se guarda")
            return
        filepath = self.output_dir / filename
        try:
            df.to_parquet(filepath, engine='pyarrow', index=False)
            logger.info(f"  OK {filename} ({len(df)} rows)")
        except Exception as e:
            logger.warning(f"  FAIL {filename}: {e}")

    # ─────────────────────────────────────────
    # MAIN POLL CYCLE
    # ─────────────────────────────────────────

    async def poll_once(self):
        """Single poll cycle — fetch all data and save as Parquet."""
        now = datetime.now(ET)
        now_str = now.strftime("%H:%M:%S EST")
        logger.info(f"{'='*50}")
        logger.info(f"--- Poll at {now_str} ---")

        if not self._expirations_resolved:
            await self._resolve_expirations()
            if not self._expirations_resolved:
                logger.error("Cannot resolve expirations — skipping poll")
                return

        # ── 1. Spot prices (SEQUENTIAL) ──
        spot_prices = {}
        for symbol in SPOT_SYMBOLS:
            df_spot = await self._fetch_spot(symbol)
            self._save_parquet(df_spot, f"spot_{symbol}_latest.parquet")
            if not df_spot.empty and 'close' in df_spot.columns:
                last_price = float(df_spot['close'].iloc[-1])
                spot_prices[symbol] = last_price
                logger.info(f"  [Spot {symbol}] ${last_price:.2f}")
            else:
                fallback_price = self._load_spot_local(symbol)
                spot_prices[symbol] = fallback_price
                if fallback_price > 0:
                    logger.info(f"  [Spot {symbol}] ${fallback_price:.2f} (fallback)")

        # ── 2. Options data per ticker (CONCURRENT WITH SEMAPHORE MAX 4) ──
        # El semáforo limita a 4 peticiones en vuelo exactamente
        semaphore = asyncio.Semaphore(4)

        async def fetch_and_save(options_symbol, exp, ep_key, current_spot, fname):
            async with semaphore:  # Espera su turno en la fila de 4
                try:
                    result_df = await self._fetch_options_data(options_symbol, exp, ep_key, current_spot)
                    self._save_parquet(result_df, fname)
                except Exception as e:
                    logger.error(f"  FAIL {fname}: {e}")

        tasks = []

        for ticker, options_symbol in OPTIONS_TICKERS.items():
            exps = self._expirations.get(ticker)
            if not exps:
                continue
            
            exp_0dte, exp_weekly = exps
            current_spot = spot_prices.get(ticker, 0.0)

            # Preparar tareas 0DTE
            if exp_0dte:
                logger.info(f"[{options_symbol} 0DTE] Queueing exp={exp_0dte} | Full chain")
                for ep_key in ENDPOINTS_0DTE:
                    fname = f"{options_symbol}_{ep_key}_0dte_latest.parquet"
                    tasks.append(fetch_and_save(options_symbol, exp_0dte, ep_key, current_spot, fname))

            # Preparar tareas Weekly
            if exp_weekly:
                logger.info(f"[{options_symbol} Weekly] Queueing exp={exp_weekly} | Full chain")
                for ep_key in ENDPOINTS_WEEKLY:
                    fname = f"{options_symbol}_{ep_key}_weekly_latest.parquet"
                    tasks.append(fetch_and_save(options_symbol, exp_weekly, ep_key, current_spot, fname))

        # Lanzar todas las tareas (el semáforo gestionará el tráfico internamente)
        if tasks:
            logger.info("Downloading options endpoints (Max 4 concurrently)...")
            await asyncio.gather(*tasks)

        # ── 3. Compute ML features ──
        try:
            self.compute_and_save_ml_features()
        except Exception as e:
            logger.warning(f"[ML] Feature computation failed: {e}")

        logger.info(f"--- Poll complete ---\n")

    # ─────────────────────────────────────────
    # HISTORICAL SPOT BACKFILL
    # ─────────────────────────────────────────

    def _get_previous_trading_days(self, n: int = 5) -> list[date]:
        """Return the last N trading days before today (Mon-Fri, no weekends)."""
        today = datetime.now(ET).date()
        result = []
        candidate = today - timedelta(days=1)
        while len(result) < n and candidate > today - timedelta(days=30):
            if candidate.weekday() < 5:  # Mon-Fri
                result.append(candidate)
            candidate -= timedelta(days=1)
        return result

    async def _backfill_historical_spot(self):
        """
        On startup, ensure spot_SPX/VIX/TLT data exists for the last 5 trading days.
        If missing, download full-day OHLC from ThetaData and save as Parquet.
        This provides the bot with Historical IB (D-1 to D-5) from the first minute.
        """
        prev_days = self._get_previous_trading_days(5)
        logger.info(f"Backfilling historical spot for {len(prev_days)} previous trading days...")

        for day in prev_days:
            day_str = day.strftime("%Y%m%d")
            day_dir = self._rt_data_base / day_str
            day_dir.mkdir(parents=True, exist_ok=True)

            for symbol in SPOT_SYMBOLS:
                filepath = day_dir / f"spot_{symbol}_latest.parquet"
                if filepath.exists():
                    continue  # Already have this day

                logger.info(f"  Downloading spot {symbol} for {day_str}...")
                try:
                    res = await self.client.fetch_underlying_ohlc(symbol, day_str, interval="1m")
                    if res and not res.data.empty:
                        df = self._fix_ohlc_zeros(res.data.copy())
                        df.to_parquet(filepath, engine='pyarrow', index=False)
                        logger.info(f"  ✓ spot_{symbol} {day_str} ({len(df)} rows)")
                    else:
                        logger.warning(f"  ✗ spot_{symbol} {day_str}: empty data")
                except Exception as e:
                    logger.warning(f"  ✗ spot_{symbol} {day_str}: {e}")

        self._historical_backfilled = True
        logger.info("Historical spot backfill complete.")

    # ─────────────────────────────────────────
    # ML FEATURE COMPUTATION HELPERS
    # ─────────────────────────────────────────

    @staticmethod
    def _classify_gamma_regime(net_gamma: float, threshold: float = 1e8) -> int:
        if net_gamma > threshold:
            return 2
        elif net_gamma < -threshold:
            return 0
        return 1

    @staticmethod
    def _is_near_level(price: float, level: float, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
        if price <= 0 or level <= 0:
            return False
        return abs(price - level) / price < threshold

    @staticmethod
    def _calculate_fibonacci_levels(ib_high: float, ib_low: float) -> dict:
        ib_range = ib_high - ib_low
        return {
            "fib_127_up": ib_high + ib_range * 0.272,
            "fib_161_up": ib_high + ib_range * 0.618,
            "fib_200_up": ib_high + ib_range * 1.0,
            "fib_127_dn": ib_low - ib_range * 0.272,
            "fib_161_dn": ib_low - ib_range * 0.618,
            "fib_200_dn": ib_low - ib_range * 1.0,
        }

    @staticmethod
    def _simple_rsi(prices: list, period: int = 14) -> float:
        if len(prices) < 2:
            return 50.0
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _sign_divergence(a: float, b: float) -> float:
        if abs(a) < 0.01 or abs(b) < 0.01:
            return 0.5
        return 1.0 if (a > 0) != (b > 0) else 0.0

    @staticmethod
    def _rbf_confluence(level_a, level_b, spot_price: float, sigma: float = 0.05) -> float:
        if spot_price <= 0 or level_a is None or level_b is None or level_a == 0 or level_b == 0:
            return 0.0
        d = abs(level_a - level_b) / spot_price
        v = np.exp(-d ** 2 / (2 * sigma ** 2))
        return float(np.clip(v, 0.0, 1.0)) if np.isfinite(v) else 0.0

    @staticmethod
    def _get_price_n_minutes_ago(history: deque, current_min: float, n_min: int):
        target_min = current_min - n_min
        best_price = None
        best_diff = float("inf")
        for (t, p) in history:
            if t > current_min:
                continue
            diff = abs(t - target_min)
            if diff < best_diff:
                best_diff = diff
                best_price = p
        return best_price if best_diff <= 2.0 else None

    def _load_historical_ib_levels(self, ticker: str = "SPX"):
        """Load Historical IB (D-1 to D-5) from previous days' spot Parquet."""
        prev_days = self._get_previous_trading_days(5)
        self.historical_ibs[ticker] = []
        spot_symbol = ticker  # SPX -> spot_SPX, QQQ -> spot_QQQ

        for day in prev_days:
            day_str = day.strftime("%Y%m%d")
            path = self._rt_data_base / day_str / f"spot_{spot_symbol}_latest.parquet"

            if not path.exists():
                self.historical_ibs[ticker].append(None)
                continue

            try:
                df = pd.read_parquet(path)
                if "timestamp" in df.columns:
                    df["dt"] = pd.to_datetime(df["timestamp"])
                elif "time" in df.columns:
                    df["dt"] = pd.to_datetime(df["time"])
                else:
                    self.historical_ibs[ticker].append(None)
                    continue

                df = df.sort_values("dt")
                df = df[(df["dt"].dt.time >= dt_time(9, 0)) & (df["dt"].dt.time <= dt_time(17, 0))]

                if df.empty:
                    self.historical_ibs[ticker].append(None)
                    continue

                rth_start = df[df["dt"].dt.time >= dt_time(9, 30)]
                if rth_start.empty:
                    self.historical_ibs[ticker].append(None)
                    continue

                rth_open = rth_start["dt"].iloc[0]
                ib_end = rth_open + pd.Timedelta(minutes=60)
                df_ib = rth_start[rth_start["dt"] < ib_end]

                ib_h = float(df_ib["high"].max()) if not df_ib.empty and "high" in df_ib.columns else 0
                ib_l = float(df_ib["low"].min()) if not df_ib.empty and "low" in df_ib.columns else 0

                close_df = df[df["dt"].dt.time <= dt_time(16, 0)]
                close_price = float(close_df["close"].iloc[-1]) if not close_df.empty and "close" in close_df.columns else 0

                if ib_h > 0 and ib_l > 0:
                    self.historical_ibs[ticker].append({
                        "ib_high": ib_h, "ib_low": ib_l,
                        "close_price": close_price, "date_str": day_str,
                    })
                else:
                    self.historical_ibs[ticker].append(None)
            except Exception as e:
                logger.warning(f"Failed to load historical IB for {ticker} {day_str}: {e}")
                self.historical_ibs[ticker].append(None)

        while len(self.historical_ibs[ticker]) < 5:
            self.historical_ibs[ticker].append(None)
        self._historical_ib_loaded[ticker] = True

    def _load_greek_exposures_local(self, is_weekly: bool = False, ticker: str = "SPX"):
        """Load Greeks+OI from Parquet and compute net exposures (mirrors bot)."""
        options_symbol = OPTIONS_TICKERS.get(ticker, "SPXW")
        suffix = "weekly" if is_weekly else "0dte"
        g_path = self.output_dir / f"{options_symbol}_greeks_{suffix}_latest.parquet"
        oi_path = self.output_dir / f"{options_symbol}_oi_{suffix}_latest.parquet"

        if not g_path.exists():
            return None
        df_greeks = pd.read_parquet(g_path)
        if df_greeks.empty:
            return None

        df_oi = pd.read_parquet(oi_path) if oi_path.exists() else pd.DataFrame()

        # Get latest timestamp snapshot
        if "underlying_timestamp" in df_greeks.columns:
            df_greeks["dt"] = pd.to_datetime(df_greeks["underlying_timestamp"], format="mixed", errors="coerce")
            latest_ts = df_greeks["dt"].max()
            df_greeks = df_greeks[df_greeks["dt"] == latest_ts].copy()

        # Merge with OI
        if not df_oi.empty and "open_interest" in df_oi.columns:
            oi_cols = ["strike", "right"]
            df_oi_agg = df_oi.groupby([c for c in oi_cols if c in df_oi.columns]).agg(
                {"open_interest": "max"}).reset_index()
            merge_cols = [c for c in oi_cols if c in df_greeks.columns and c in df_oi_agg.columns]
            if merge_cols:
                df_pq = pd.merge(df_greeks, df_oi_agg, on=merge_cols, how="inner")
            else:
                df_pq = df_greeks.copy()
                df_pq["open_interest"] = 1000
        else:
            df_pq = df_greeks.copy()
            df_pq["open_interest"] = 1000

        if "implied_vol" not in df_pq.columns:
            if "implied_volatility" in df_pq.columns:
                df_pq["implied_vol"] = df_pq["implied_volatility"]
            else:
                df_pq["implied_vol"] = 0.15

        if "underlying_price" not in df_pq.columns:
            return None

        now_et = pd.Timestamp.now(tz="America/New_York")
        df_pq["T"] = calculate_exact_t(now_et)

        required = ["strike", "right", "implied_vol", "open_interest", "underlying_price", "T"]
        for col in required:
            if col not in df_pq.columns:
                return None
        df_pq = df_pq.dropna(subset=required)

        if df_pq.empty:
            return None
        return get_net_exposures_from_parquet(df_pq)

    def _load_atm_iv_local(self, spot: float, ticker: str = "SPX") -> float:
        """Load ATM IV from the IV parquet."""
        options_symbol = OPTIONS_TICKERS.get(ticker, "SPXW")
        iv_path = self.output_dir / f"{options_symbol}_iv_0dte_latest.parquet"
        if not iv_path.exists():
            return 0.0
        df_iv = pd.read_parquet(iv_path)
        if df_iv.empty or "implied_vol" not in df_iv.columns or "strike" not in df_iv.columns:
            return 0.0
        if "underlying_timestamp" in df_iv.columns:
            df_iv["dt"] = pd.to_datetime(df_iv["underlying_timestamp"], format="mixed", errors="coerce")
            df_iv = df_iv[df_iv["dt"] == df_iv["dt"].max()]
        if df_iv.empty:
            return 0.0
        closest_idx = (df_iv["strike"] - spot).abs().idxmin()
        atm_iv = float(df_iv.loc[closest_idx, "implied_vol"])
        if atm_iv > 1.0:
            atm_iv = atm_iv / 100.0
        return max(atm_iv, 0.01)

    def _load_spot_local(self, symbol: str) -> float:
        """Load latest spot price from Parquet."""
        path = self.output_dir / f"spot_{symbol}_latest.parquet"
        if not path.exists():
            return 0.0
        df = pd.read_parquet(path)
        if df.empty or "close" not in df.columns:
            return 0.0
        return float(df["close"].iloc[-1])

    def _compute_ib_from_spot(self, ticker: str = "SPX"):
        """Compute IB from today's spot candles."""
        spot_symbol = ticker  # SPX -> spot_SPX, QQQ -> spot_QQQ
        path = self.output_dir / f"spot_{spot_symbol}_latest.parquet"
        if not path.exists():
            return
        df = pd.read_parquet(path)
        if df.empty:
            return
        if "timestamp" in df.columns:
            df["dt"] = pd.to_datetime(df["timestamp"])
        elif "time" in df.columns:
            df["dt"] = pd.to_datetime(df["time"])
        else:
            return
        df = df.sort_values("dt")
        df_rth = df[df["dt"].dt.time >= dt_time(9, 30)]
        if df_rth.empty:
            return
        rth_start = df_rth["dt"].min()
        ib_end = rth_start + pd.Timedelta(minutes=60)
        df_ib = df_rth[df_rth["dt"] < ib_end]
        if not df_ib.empty and "high" in df_ib.columns and "low" in df_ib.columns:
            self.ib_high[ticker] = float(df_ib["high"].max())
            self.ib_low[ticker] = float(df_ib["low"].min())

    # ─────────────────────────────────────────
    # ML FEATURE VECTOR COMPUTATION
    # ─────────────────────────────────────────

    def compute_and_save_ml_features(self):
        """
        Build the 163-feature vector (identical to tradingbot_wrapper_rl.py)
        from the freshly-polled Parquet data and save per-ticker parquet files.
        Loops over both SPX and QQQ.
        """
        now_et = datetime.now(ET)
        minutes_since_open = max(0, (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30))

        # Shared data (VIX, TLT are the same for all tickers)
        vix_spot = self._load_spot_local("VIX")
        tlt_spot = self._load_spot_local("TLT")

        for ticker in OPTIONS_TICKERS:
            try:
                self._compute_ml_features_for_ticker(
                    ticker, now_et, minutes_since_open, vix_spot, tlt_spot)
            except Exception as e:
                logger.warning(f"[ML][{ticker}] Feature computation failed: {e}")

    def _compute_ml_features_for_ticker(
        self, ticker: str, now_et, minutes_since_open: int,
        vix_spot: float, tlt_spot: float
    ):
        """Compute and save ML features for a single ticker."""
        # Lazy load historical IB on first call
        if not self._historical_ib_loaded.get(ticker, False):
            self._load_historical_ib_levels(ticker)

        # Load exposures
        exp_0dte = self._load_greek_exposures_local(is_weekly=False, ticker=ticker)
        if exp_0dte is None:
            logger.debug(f"[ML][{ticker}] No 0DTE data — skipping feature computation")
            return

        exp_weekly = self._load_greek_exposures_local(is_weekly=True, ticker=ticker)
        spot = exp_0dte["spot_price"]
        if spot <= 0:
            spot = self._load_spot_local(ticker)
        if spot <= 0:
            return

        # Compute IB once per session per ticker
        if self.ib_high.get(ticker) is None:
            self._compute_ib_from_spot(ticker)

        atm_iv = self._load_atm_iv_local(spot, ticker)

        self.price_history[ticker].append((minutes_since_open, spot))

        features = {}

        # ── 0DTE Greek exposures (safe_log to match training) ──
        features["net_gamma"] = safe_log(exp_0dte["net_gamma"])
        features["net_vanna"] = safe_log(exp_0dte["net_vanna"])
        features["net_charm"] = safe_log(exp_0dte["net_charm"])
        features["net_dgex"] = safe_log(exp_0dte["net_dgex"])
        features["net_zomma"] = safe_log(exp_0dte["net_zomma"])
        features["net_delta"] = safe_log(exp_0dte["net_delta"])
        features["net_vega"] = safe_log(exp_0dte["net_vega"])
        features["net_vomma"] = safe_log(exp_0dte["net_vomma"])

        # ── Signals ──
        features["gamma_regime"] = self._classify_gamma_regime(exp_0dte["net_gamma"]) / 2.0
        features["vanna_bullish"] = 1 if exp_0dte["net_vanna"] > 0.1 else 0
        features["charm_bullish"] = 1 if exp_0dte["net_charm"] > 0.1 else 0
        features["dgex_sticky"] = 1 if exp_0dte["net_dgex"] > 0.1 else 0
        features["zomma_stabilizing"] = 1 if exp_0dte["net_zomma"] > 0.1 else 0
        features["vega_elevated"] = 1 if abs(exp_0dte["net_vega"]) > 0.1 else 0

        # ── ATR ──
        day_atr = 1.0
        if len(self.price_history[ticker]) >= 3:
            prices = [p for _, p in self.price_history[ticker]]
            abs_returns = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
            if abs_returns:
                day_atr = max(np.mean(abs_returns), 0.5)
        atr_denom = day_atr + 1e-6

        # ── Greek strike distances (basis points, matching training) ──
        features["dist_to_max_gamma"] = dist_bps(spot, exp_0dte["max_gamma_strike"])
        features["dist_to_min_gamma"] = dist_bps(spot, exp_0dte["min_gamma_strike"])
        features["dist_to_min_vanna"] = dist_bps(spot, exp_0dte["min_vanna_strike"])
        features["dist_to_zero_gamma"] = dist_bps(spot, exp_0dte["zero_gamma"])
        features["dist_to_max_dgex"] = dist_bps(spot, exp_0dte["max_dgex_strike"])
        features["dist_to_min_dgex"] = dist_bps(spot, exp_0dte["min_dgex_strike"])
        features["dist_to_max_vega"] = dist_bps(spot, exp_0dte["max_vega_strike"])
        features["dist_to_min_vega"] = dist_bps(spot, exp_0dte["min_vega_strike"])
        features["dist_to_max_vomma"] = dist_bps(spot, exp_0dte["max_vomma_strike"])
        features["dist_to_min_vomma"] = dist_bps(spot, exp_0dte["min_vomma_strike"])

        features["near_max_gamma"] = 1 if self._is_near_level(spot, exp_0dte["max_gamma_strike"]) else 0
        features["near_min_gamma"] = 1 if self._is_near_level(spot, exp_0dte["min_gamma_strike"]) else 0
        features["near_min_vanna"] = 1 if self._is_near_level(spot, exp_0dte["min_vanna_strike"]) else 0
        features["near_zero_gamma"] = 1 if self._is_near_level(spot, exp_0dte["zero_gamma"]) else 0

        # ── Weekly features ──
        wk_defaults = {
            "wk_net_gamma": 0.0, "wk_net_vanna": 0.0, "wk_net_charm": 0.0,
            "wk_net_dgex": 0.0, "wk_net_zomma": 0.0, "wk_net_delta": 0.0,
            "wk_net_vega": 0.0, "wk_net_vomma": 0.0,
            "wk_gamma_regime": 0.5, "wk_vanna_bullish": 0,
            "wk_dgex_sticky": 0, "wk_zomma_stabilizing": 0,
        }
        if exp_weekly:
            wk_defaults.update({
                "wk_net_gamma": safe_log(exp_weekly["net_gamma"]), "wk_net_vanna": safe_log(exp_weekly["net_vanna"]),
                "wk_net_charm": safe_log(exp_weekly["net_charm"]), "wk_net_dgex": safe_log(exp_weekly["net_dgex"]),
                "wk_net_zomma": safe_log(exp_weekly["net_zomma"]), "wk_net_delta": safe_log(exp_weekly["net_delta"]),
                "wk_net_vega": safe_log(exp_weekly["net_vega"]), "wk_net_vomma": safe_log(exp_weekly["net_vomma"]),
                "wk_gamma_regime": self._classify_gamma_regime(exp_weekly["net_gamma"]) / 2.0,
                "wk_vanna_bullish": 1 if exp_weekly["net_vanna"] > 0.1 else 0,
                "wk_dgex_sticky": 1 if exp_weekly["net_dgex"] > 0.1 else 0,
                "wk_zomma_stabilizing": 1 if exp_weekly["net_zomma"] > 0.1 else 0,
            })
        features.update(wk_defaults)

        # ── Cross-expiry divergence ──
        features["gamma_0dte_vs_wk"] = self._sign_divergence(exp_0dte["net_gamma"], wk_defaults["wk_net_gamma"])
        features["vanna_0dte_vs_wk"] = self._sign_divergence(exp_0dte["net_vanna"], wk_defaults["wk_net_vanna"])
        features["dgex_0dte_vs_wk"] = self._sign_divergence(exp_0dte["net_dgex"], wk_defaults["wk_net_dgex"])
        features["delta_0dte_vs_wk"] = self._sign_divergence(exp_0dte["net_delta"], wk_defaults["wk_net_delta"])
        features["vega_0dte_vs_wk"] = self._sign_divergence(exp_0dte["net_vega"], wk_defaults.get("wk_net_vega", 0))
        features["vomma_0dte_vs_wk"] = self._sign_divergence(exp_0dte["net_vomma"], wk_defaults.get("wk_net_vomma", 0))

        # ── IB levels ──
        ib_high = self.ib_high.get(ticker) or spot
        ib_low = self.ib_low.get(ticker) or spot
        ib_range = max(ib_high - ib_low, 0.01)

        features["price_vs_ib_high"] = dist_bps(spot, ib_high)
        features["price_vs_ib_low"] = dist_bps(spot, ib_low)
        features["ib_range_pct"] = ib_range / spot if spot > 0 else 0
        features["near_ib_high"] = 1 if self._is_near_level(spot, ib_high) else 0
        features["near_ib_low"] = 1 if self._is_near_level(spot, ib_low) else 0
        features["above_ib"] = 1 if spot > ib_high else 0
        features["below_ib"] = 1 if spot < ib_low else 0
        features["in_ib_range"] = 1 if ib_low <= spot <= ib_high else 0

        # ── Fibonacci (basis points, matching training) ──
        fib = self._calculate_fibonacci_levels(ib_high, ib_low)
        for key in fib:
            features[f"dist_{key}"] = dist_bps(spot, fib[key])

        # ── Confluences ──
        features["confluence_ib_high_max_gamma"] = self._rbf_confluence(ib_high, exp_0dte["max_gamma_strike"], spot)
        features["confluence_ib_low_min_gamma"] = self._rbf_confluence(ib_low, exp_0dte["min_gamma_strike"], spot)
        features["confluence_ib_high_max_vega"] = self._rbf_confluence(ib_high, exp_0dte.get("max_vega_strike", 0), spot)
        features["confluence_ib_low_max_dgex"] = self._rbf_confluence(ib_low, exp_0dte["max_dgex_strike"], spot)
        features["confluence_fib127_bull_max_gamma"] = self._rbf_confluence(fib["fib_127_up"], exp_0dte["max_gamma_strike"], spot)
        features["confluence_fib161_bull_max_vega"] = self._rbf_confluence(fib["fib_161_up"], exp_0dte.get("max_vega_strike", 0), spot)
        features["confluence_fib127_bear_min_gamma"] = self._rbf_confluence(fib["fib_127_dn"], exp_0dte["min_gamma_strike"], spot)
        features["confluence_fib161_bear_max_vomma"] = self._rbf_confluence(fib["fib_161_dn"], exp_0dte.get("max_vomma_strike", 0), spot)
        features["confluence_fib161_bull_max_vomma"] = self._rbf_confluence(fib["fib_161_up"], exp_0dte.get("max_vomma_strike", 0), spot)
        features["confluence_fib127_bear_min_vomma"] = self._rbf_confluence(fib["fib_127_dn"], exp_0dte.get("min_vomma_strike", 0), spot)
        features["confluence_fib127_bull_max_dgex"] = self._rbf_confluence(fib["fib_127_up"], exp_0dte["max_dgex_strike"], spot)
        features["confluence_fib127_bear_min_dgex"] = self._rbf_confluence(fib["fib_127_dn"], exp_0dte["min_dgex_strike"], spot)
        features["confluence_fib161_bull_max_dgex"] = self._rbf_confluence(fib["fib_161_up"], exp_0dte["max_dgex_strike"], spot)
        features["confluence_fib161_bear_min_dgex"] = self._rbf_confluence(fib["fib_161_dn"], exp_0dte["min_dgex_strike"], spot)

        # ── IV / VIX ──
        atm_iv_norm = atm_iv / 100.0 if atm_iv > 1 else atm_iv
        if atm_iv_norm > 0:
            self.iv_history[ticker].append(atm_iv_norm)
        iv_hist = self.iv_history[ticker]
        iv_mean = np.mean(iv_hist) if iv_hist else 0.15
        iv_std = np.std(iv_hist) if len(iv_hist) > 1 else 0
        iv_zscore = float((atm_iv_norm - iv_mean) / iv_std) if iv_std > 0 else 0
        iv_min, iv_max = (min(iv_hist), max(iv_hist)) if iv_hist else (0, 1)
        iv_pct = float((atm_iv_norm - iv_min) / (iv_max - iv_min)) if iv_max > iv_min else 0.5

        features["atm_iv"] = atm_iv_norm
        features["iv_zscore"] = np.clip(iv_zscore, -3, 3) / 3.0
        features["iv_percentile"] = iv_pct
        features["vix_spot"] = vix_spot / 50.0 if vix_spot > 0 else 0
        features["vix_gamma"] = 0
        features["vix_regime"] = (2 if vix_spot > 25 else (1 if vix_spot > 18 else 0)) / 2.0

        # ── RSI ──
        prices_list = [p for _, p in self.price_history[ticker]]
        features["rsi"] = self._simple_rsi(prices_list) / 100.0
        features["vol_relative"] = 0.2

        # ── Greek ratios (safe_log to match training) ──
        eps = 1e-6
        features["gamma_vanna_ratio"] = safe_log(exp_0dte["net_gamma"] / (abs(exp_0dte["net_vanna"]) + eps))
        features["dgex_gamma_ratio"] = safe_log(exp_0dte["net_dgex"] / (abs(exp_0dte["net_gamma"]) + eps))
        features["charm_vanna_ratio"] = safe_log(exp_0dte["net_charm"] / (abs(exp_0dte["net_vanna"]) + eps))
        features["delta_gamma_ratio"] = safe_log(exp_0dte["net_delta"] / (abs(exp_0dte["net_gamma"]) + eps))
        features["vega_gamma_ratio"] = safe_log(exp_0dte["net_vega"] / (abs(exp_0dte["net_gamma"]) + eps))
        features["vomma_vega_ratio"] = safe_log(exp_0dte["net_vomma"] / (abs(exp_0dte["net_vega"]) + eps))

        # ── Temporal deltas (safe_log to match training) ──
        prev = self.prev_features.get(ticker)
        if prev:
            features["gamma_change"] = safe_log(exp_0dte["net_gamma"] - prev["net_gamma"])
            features["vanna_change"] = safe_log(exp_0dte["net_vanna"] - prev["net_vanna"])
            features["dgex_change"] = safe_log(exp_0dte["net_dgex"] - prev["net_dgex"])
            features["delta_change"] = safe_log(exp_0dte["net_delta"] - prev.get("net_delta", 0))
            features["vega_change"] = safe_log(exp_0dte["net_vega"] - prev.get("net_vega", 0))
            features["vomma_change"] = safe_log(exp_0dte["net_vomma"] - prev.get("net_vomma", 0))
            features["spot_change"] = ((spot - prev["spot"]) / prev["spot"] * 10000.0) if prev["spot"] > 0 else 0
            features["gamma_momentum"] = safe_log((exp_0dte["net_gamma"] - prev["net_gamma"]) * np.sign(exp_0dte["net_gamma"]))
            features["price_vs_dgex_magnet"] = features["spot_change"] * np.sign(
                (spot - exp_0dte["max_dgex_strike"]) / spot) if spot > 0 and exp_0dte["max_dgex_strike"] else 0
        else:
            for f in ["gamma_change", "vanna_change", "dgex_change", "delta_change",
                       "spot_change", "gamma_momentum", "price_vs_dgex_magnet",
                       "vega_change", "vomma_change"]:
                features[f] = 0.0

        self.prev_features[ticker] = {
            "spot": spot, "net_gamma": exp_0dte["net_gamma"], "net_vanna": exp_0dte["net_vanna"],
            "net_dgex": exp_0dte["net_dgex"], "net_delta": exp_0dte["net_delta"],
            "net_vega": exp_0dte["net_vega"], "net_vomma": exp_0dte["net_vomma"],
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

        # ── Defaults for features needing extra context ──
        defaults = {
            "signal_persistence_5m": 0.0,
            "ret_1m_vol_adj": 0.0, "ret_5m_vol_adj": 0.0,
            "ret_15m_vol_adj": 0.0, "ret_30m_vol_adj": 0.0,
            "time_sin": float(np.sin(2 * np.pi * minutes_since_open / 390)),
            "time_cos": float(np.cos(2 * np.pi * minutes_since_open / 390)),
            "minutes_to_close_norm": max(0, 390 - minutes_since_open) / 390.0,
            "dow_sin": float(np.sin(2 * np.pi * now_et.weekday() / 5)),
            "dow_cos": float(np.cos(2 * np.pi * now_et.weekday() / 5)),
            "ib_range_percentile": 0.5,
            "gap_pct": 0.0, "gap_direction": 0.0, "overnight_vs_ib_ratio": 0.0,
            "days_to_opex_norm": 0.5, "is_opex_week": 0.0, "is_quarterly_opex_week": 0.0,
            "rvol_iv_log": 0.0, "rvol_trend": 0.0, "rvol_regime": 1.0,
            "charm_accel_weighted": 0.0, "gamma_speed": 0.0,
            "gamma_phase_sin": 0.0, "gamma_phase_cos": 0.0,
            "gamma_amplitude_ratio": 0.0, "gamma_phase_delta": 0.0,
            "delta_filtered_pcr": 0.0, "pcr_derivative_5m": 0.0,
            "wonham_trend_prob": 0.5,
            "speed_x_near_ib_high": 0.0, "speed_x_near_ib_low": 0.0,
            "charm_accel_x_near_ib_high": 0.0, "charm_accel_x_near_ib_low": 0.0,
            # Level identity (defaults)
            "nearest_level_id": 8,  # "none"
            "nearest_level_dist_bps": 0.0,
            # Greek × Level interactions (defaults)
            "gamma_x_near_fib_up": 0.0, "gamma_x_near_fib_dn": 0.0, "gamma_x_near_ib": 0.0,
            "delta_x_near_fib_up": 0.0, "delta_x_near_fib_dn": 0.0,
            "delta_x_near_ib_high": 0.0, "delta_x_near_ib_low": 0.0,
            "vanna_x_near_fib_up": 0.0, "vanna_x_near_fib_dn": 0.0, "vanna_x_near_ib": 0.0,
        }
        for k, v in defaults.items():
            features.setdefault(k, v)

        # ── Historical IB D-1 to D-5 ──
        hist_ibs = self.historical_ibs.get(ticker, [])
        for i in range(5):
            d = i + 1
            hist = hist_ibs[i] if i < len(hist_ibs) else None
            if hist is not None:
                h_ib_h = hist["ib_high"]
                h_ib_l = hist["ib_low"]
                prev_close = hist["close_price"]
                ib_mid = (h_ib_h + h_ib_l) / 2.0
                ib_width = h_ib_h - h_ib_l + 1e-6
                features[f"dist_ib_high_D{d}"] = dist_bps(spot, h_ib_h)
                features[f"dist_ib_low_D{d}"] = dist_bps(spot, h_ib_l)
                features[f"prev_close_vs_ib_D{d}"] = float(np.clip((prev_close - ib_mid) / ib_width, -2, 2))
            else:
                features[f"dist_ib_high_D{d}"] = 0.0
                features[f"dist_ib_low_D{d}"] = 0.0
                features[f"prev_close_vs_ib_D{d}"] = 0.0

        # ── D-1 IB confluences ──
        if hist_ibs and hist_ibs[0] is not None:
            d1_ib_high = hist_ibs[0]["ib_high"]
            d1_ib_low = hist_ibs[0]["ib_low"]
            features["confluence_d1ibh_max_gamma"] = self._rbf_confluence(d1_ib_high, exp_0dte["max_gamma_strike"], spot)
            features["confluence_d1ibl_min_gamma"] = self._rbf_confluence(d1_ib_low, exp_0dte["min_gamma_strike"], spot)
            features["confluence_d1ibh_max_dgex"] = self._rbf_confluence(d1_ib_high, exp_0dte["max_dgex_strike"], spot)
            features["confluence_d1ibl_min_dgex"] = self._rbf_confluence(d1_ib_low, exp_0dte["min_dgex_strike"], spot)
            features["confluence_d1ibh_max_vomma"] = self._rbf_confluence(d1_ib_high, exp_0dte.get("max_vomma_strike", 0), spot)
            features["confluence_d1ibh_ibh_today"] = self._rbf_confluence(d1_ib_high, ib_high, spot)
            features["confluence_d1ibl_ibl_today"] = self._rbf_confluence(d1_ib_low, ib_low, spot)
        else:
            for key in ["confluence_d1ibh_max_gamma", "confluence_d1ibl_min_gamma",
                        "confluence_d1ibh_max_dgex", "confluence_d1ibl_min_dgex",
                        "confluence_d1ibh_max_vomma",
                        "confluence_d1ibh_ibh_today", "confluence_d1ibl_ibl_today"]:
                features[key] = 0.0

        # ── IB Range Percentile ──
        past_ranges = [h["ib_high"] - h["ib_low"] for h in hist_ibs if h is not None]
        if past_ranges:
            current_ib_range = ib_high - ib_low
            features["ib_range_percentile"] = sum(r < current_ib_range for r in past_ranges) / len(past_ranges)

        # ── Vol-adjusted returns ──
        atm_iv_for_norm = atm_iv_norm if atm_iv_norm > 0.001 else 0.15
        for label, lb in [("1m", 1), ("5m", 5), ("15m", 15), ("30m", 30)]:
            past_price = self._get_price_n_minutes_ago(self.price_history[ticker], minutes_since_open, lb)
            if past_price and past_price > 0:
                raw_return = (spot - past_price) / past_price
                vol_norm = atm_iv_for_norm * np.sqrt(lb / (252.0 * 390.0)) + 1e-8
                features[f"ret_{label}_vol_adj"] = float(np.clip(raw_return / vol_norm, -5, 5))

        # ── Build final row and save (per-ticker) ──
        row = {col: features.get(col, 0.0) for col in FEATURE_COLUMNS}
        row["timestamp"] = now_et.isoformat()
        row["spot_price"] = spot
        row["ticker"] = ticker

        self._ml_features_rows[ticker].append(row)
        df_features = pd.DataFrame(self._ml_features_rows[ticker])
        self._save_parquet(df_features, f"ml_features_{ticker}_latest.parquet")
        logger.info(f"  [ML][{ticker}] Feature vector saved ({len(self._ml_features_rows[ticker])} rows, spot=${spot:.2f})")

    # ─────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────

    def get_output_dir(self) -> Path:
        """Return the current day's output directory."""
        return self.output_dir

    @staticmethod
    def get_latest_dir(base_dir: str = None) -> Path:
        """Get the most recent rt_data/{date}/ directory."""
        base = Path(base_dir or os.path.join(PROJECT_ROOT, "rt_data"))
        if not base.exists():
            return base
        subdirs = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
        return subdirs[0] if subdirs else base

    # ─────────────────────────────────────────
    # RUN LOOP
    # ─────────────────────────────────────────

    async def run(self, dry_run: bool = False):
        """Start the polling loop."""
        self.running = True
        logger.info(f"Starting RealtimeOptionsFeed")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(f"Output: {self.output_dir}")

        # Backfill historical spot data on first startup
        if not self._historical_backfilled:
            await self._backfill_historical_spot()

        try:
            while self.running:
                now = datetime.now(ET)

                # Dry run bypasses market hours (for testing)
                if not dry_run:
                    # Market hours check (9:30-16:00 EST)
                    market_open = now.replace(hour=9, minute=30, second=0)
                    market_close = now.replace(hour=16, minute=0, second=0)

                    if now.weekday() >= 5:
                        logger.info("Weekend — sleeping 60s")
                        await asyncio.sleep(60)
                        continue

                    if now < market_open or now > market_close:
                        logger.info(f"Outside market hours ({now.strftime('%H:%M EST')}) — sleeping 60s")
                        await asyncio.sleep(60)
                        continue

                await self.poll_once()

                if dry_run:
                    logger.info("Dry run — exiting after one poll")
                    break

                await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            logger.info("Feed stopped.")
        except KeyboardInterrupt:
            logger.info("Feed interrupted.")
        finally:
            self.running = False
            await self.client.close()


def main():
    parser = argparse.ArgumentParser(description="Real-time options + spot feed (Parquet)")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Single poll then exit")
    args = parser.parse_args()

    print("="*60)
    print("REAL-TIME OPTIONS FEED — SPXW+QQQ 0DTE+Weekly + Spot (Parquet)")
    print("="*60)
    print(f"  Options:  {', '.join(f'{t}->{s}' for t,s in OPTIONS_TICKERS.items())} (0DTE + Weekly)")
    print(f"  Spot:     {', '.join(SPOT_SYMBOLS)}")
    print(f"  Interval: {args.interval}s")
    print(f"  Timezone: EST (America/New_York)")
    print("=" * 60)

    feed = RealtimeOptionsFeed(
        poll_interval=args.interval,
        output_dir=args.output,
    )
    asyncio.run(feed.run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()