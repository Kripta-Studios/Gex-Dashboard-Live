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
from dotenv import load_dotenv
from datetime import date, datetime, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import deque

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THETADATA_API = os.path.join(PROJECT_ROOT, "thetadata-api")
sys.path.insert(0, THETADATA_API)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural"))

from thetadata_api.client import ThetaClient
from thetadata_api.corrector import fix_dataframe
from thetadata_api.utils import fetch_with_interval_fallback, parse_response, get_logger
from services.compute_features import (
    get_net_exposures_from_parquet, calculate_exact_t,
    extract_feature_vector, compute_wonham_filter
)
from neural.hybrid_model import FEATURE_COLUMNS
from modules.utils import get_market_trading_days

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
LEVEL_PROXIMITY_THRESHOLD = 0.0015

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
SPOT_SYMBOLS = ["QQQ", "SPY", "VIX", "TLT"]

# Map trading ticker → options symbol
OPTIONS_TICKERS = {
    "QQQ": "QQQ",    # QQQ uses QQQ options directly
    "SPY": "SPY",    # SPY uses SPY options (American-style)
}


class RealtimeOptionsFeed:
    """
    Real-time options + spot feed for GBM+RL bot.

    Polls every 60 seconds during market hours.
    Fetches SPXW + QQQ options (0DTE + weekly) + spot prices.
    Saves all data as Parquet files in rt_data/{YYYYMMDD}/.
    """

    def __init__(self, poll_interval: int = 60, output_dir: str = None):
        thetadata_url = os.environ.get("THETADATA_URL", "http://91.99.90.39:25503/v3")
        self.client = ThetaClient(base_url=thetadata_url)
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
        self.ib_high: dict[str, float | None] = {}  # ticker -> float
        self.ib_low: dict[str, float | None] = {}   # ticker -> float
        self.historical_ibs = {}   # ticker -> list[dict|None]
        self.prev_features = {}    # ticker -> dict
        self._ml_features_rows = {}  # ticker -> list of rows
        self._historical_ib_loaded = {}  # ticker -> bool
        self.day_atr = {}             # ticker -> float
        self.net_gamma_window = {}    # ticker -> deque(maxlen=100)
        self.net_charm_history = {}   # ticker -> deque(maxlen=60)
        self.pcr_history = {}         # ticker -> deque(maxlen=60)
        self.wonham_probs = {}        # ticker -> float

        # Initialize per-ticker structures
        for tk in OPTIONS_TICKERS:
            self.price_history[tk] = deque(maxlen=35)
            self.iv_history[tk] = deque(maxlen=60)
            self.ib_high[tk] = None
            self.ib_low[tk] = None
            self.historical_ibs[tk] = []
            self._ml_features_rows[tk] = []
            self._historical_ib_loaded[tk] = False
            self.day_atr[tk] = 1.0
            self.net_gamma_window[tk] = deque(maxlen=100)
            self.net_charm_history[tk] = deque(maxlen=60)
            self.pcr_history[tk] = deque(maxlen=60)
            self.wonham_probs[tk] = 0.5

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

        semaphore = asyncio.Semaphore(4)
        
        async def fetch_and_compute(ticker, options_symbol):
            async with semaphore:
                try:
                    exps = await self.client.get_expirations(options_symbol, today_str)
                    available = []
                    for exp_str in exps:
                        try:
                            exp_date = date(int(exp_str[:4]), int(exp_str[4:6]), int(exp_str[6:8]))
                            available.append(exp_date)
                        except (ValueError, IndexError):
                            continue
                    exp_0dte, exp_weekly = self._compute_target_expirations(today, available)
                    return ticker, options_symbol, exp_0dte, exp_weekly, True
                except Exception as e:
                    logger.warning(f"Cannot get expirations for {options_symbol}: {e}")
                    return ticker, options_symbol, None, None, False

        tasks = [fetch_and_compute(t, s) for t, s in OPTIONS_TICKERS.items()]
        results = await asyncio.gather(*tasks)

        all_resolved = True
        for ticker, options_symbol, exp_0dte, exp_weekly, success in results:
            if not success:
                all_resolved = False
            else:
                self._expirations[ticker] = (exp_0dte, exp_weekly)
                logger.info(f"Expirations [{options_symbol}]: 0DTE={exp_0dte} | Weekly={exp_weekly}")

        self._expirations_resolved = all_resolved or len(self._expirations) > 0

    # ─────────────────────────────────────────
    # OPTIONS CHAIN DOWNLOAD
    # ─────────────────────────────────────────

    async def _fetch_options_data(self, options_symbol: str, expiration: date, endpoint_key: str, spot_price: float = 0.0, ticker: str = "SPX") -> pd.DataFrame:
        """
        Fetch options data para el simbolo, endpoint y expiracion dados.
        Filtra strikes que estén fuera de ±50 ATR del spot_price actual.
        """
        now_et = datetime.now(ET)
        today_str = now_et.strftime("%Y%m%d")
        exp_str = expiration.strftime("%Y%m%d")
        endpoint = OPTIONS_ENDPOINTS[endpoint_key]

        window_start = (now_et - timedelta(seconds=60)).strftime("%H:%M:%S")
        window_end   = now_et.strftime("%H:%M:%S")

        base_url = getattr(self.client, "base_url", "http://91.99.90.39:25503/v3")
        all_rows = []

        # Expanded Filter: ±50 ATR (to match training/backtest availability)
        atr = self.day_atr.get(ticker, 1.0)
        min_strike = spot_price - (50.0 * atr) if spot_price > 0 else 0.0
        max_strike = spot_price + (50.0 * atr) if spot_price > 0 else float('inf')

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
                # Reuse self.client.session for connection pooling
                response = await self.client.session.get(f"{base_url}{endpoint}", params=params, timeout=180.0)

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
                        
                        # --- FILTRO ±50 ATR ---
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
                        # --- FILTRO ±50 ATR (caso diccionario plano) ---
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

            except httpx.TimeoutException:
                logger.warning(f"[{options_symbol}] {endpoint_key} {right} exp={exp_str}: Request timed out after 180s")
            except Exception as e:
                logger.warning(f"[{options_symbol}] {endpoint_key} {right} exp={exp_str}: {type(e).__name__} - {e}")

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
            # Map SPX to SPXW just for the underlying proxy request to ensure 0DTE derivation
            api_symbol = "SPXW" if symbol == "SPX" else symbol
            res = await self.client.fetch_underlying_ohlc(api_symbol, today_str, interval="1m")
            if res and not res.data.empty:
                df = res.data.copy()
                df = self._fix_ohlc_zeros(df)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(str), format="mixed", errors="coerce")
                elif "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"].astype(str), format="mixed", errors="coerce")
                return df
        except Exception as e:
            logger.warning(f"Error deriving spot {symbol}: {e}")

        return pd.DataFrame()

    async def _fetch_spot_vix(self) -> pd.DataFrame:
        """
        Derive VIX spot from greeks of the nearest future VIX expiration.

        VIX options never have a 0DTE expiration — they settle on Wednesdays
        using a special SOQ (Settlement Opening Quotation) process. ThetaData
        cannot derive VIX spot from today's date directly. The correct approach,
        mirroring script4_underlying_from_options.py, is:
          1. Fetch available VIX expirations
          2. Find the nearest expiration AFTER today
          3. Pick the central strike of that expiration
          4. Request 1-minute greeks and extract underlying_price
        """
        today_str = datetime.now(ET).strftime("%Y%m%d")
        today = datetime.now(ET).date()
        base_url = getattr(self.client, "base_url", "http://91.99.90.39:25503/v3")

        try:
            # 1. Get available VIX expirations
            resp = await self.client.session.get(
                f"{base_url}/option/list/expirations",
                params={"symbol": "VIX", "date": today_str, "format": "json"},
                timeout=30.0
            )
            if resp.status_code != 200:
                logger.warning(f"VIX expirations HTTP {resp.status_code}")
                return pd.DataFrame()

            raw_exps = parse_response(resp.json())
            available = set()
            for item in raw_exps:
                try:
                    exp_str = item.get("expiration", item) if isinstance(item, dict) else str(item)
                    exp_str = str(exp_str).replace("-", "")
                    available.add(date(int(exp_str[:4]), int(exp_str[4:6]), int(exp_str[6:8])))
                except Exception:
                    continue

            # 2. Find nearest expiration strictly after today
            future_exps = sorted(e for e in available if e > today)
            if not future_exps:
                logger.warning("VIX: no future expirations found")
                return pd.DataFrame()
            target_exp = future_exps[0]
            exp_str = target_exp.strftime("%Y%m%d")

            # 3. Get strikes for that expiration, pick the central one
            resp_s = await self.client.session.get(
                f"{base_url}/option/list/strikes",
                params={"symbol": "VIX", "expiration": exp_str, "date": today_str, "format": "json"},
                timeout=30.0
            )
            if resp_s.status_code != 200:
                logger.warning(f"VIX strikes HTTP {resp_s.status_code}")
                return pd.DataFrame()

            strikes_raw = parse_response(resp_s.json())
            strikes = sorted([
                float(s.get("strike", s.get("value", 0))) if isinstance(s, dict) else float(s)
                for s in strikes_raw
            ])
            if not strikes:
                logger.warning("VIX: no strikes available")
                return pd.DataFrame()
            central_strike = strikes[len(strikes) // 2]

            # 4. Fetch 1-minute greeks from the central strike, extract underlying_price
            now_et = datetime.now(ET)
            window_start = (now_et - timedelta(seconds=60)).strftime("%H:%M:%S")
            window_end = now_et.strftime("%H:%M:%S")

            for right in ["C", "P"]:
                resp_g = await self.client.session.get(
                    f"{base_url}/option/history/greeks/first_order",
                    params={
                        "symbol": "VIX", "expiration": exp_str,
                        "strike": str(central_strike), "right": right,
                        "date": today_str,
                        "start_time": window_start, "end_time": window_end,
                        "format": "json",
                    },
                    timeout=60.0
                )
                if resp_g.status_code != 200:
                    continue

                items = parse_response(resp_g.json())
                rows = []
                for it in items:
                    if isinstance(it, dict) and "data" in it:
                        rows.extend(it["data"])
                    elif isinstance(it, dict) and "underlying_price" in it:
                        rows.append(it)

                if not rows:
                    continue

                df_raw = pd.DataFrame(rows)
                if "underlying_price" not in df_raw.columns:
                    continue

                # Build OHLC from underlying_price ticks
                ts_col = next((c for c in ["timestamp", "underlying_timestamp"] if c in df_raw.columns), None)
                if ts_col is None:
                    continue

                df_raw["_ts"] = pd.to_datetime(df_raw[ts_col], utc=False, errors="coerce")
                df_raw = df_raw.dropna(subset=["_ts", "underlying_price"])
                df_raw = df_raw.sort_values("_ts")
                if df_raw.empty:
                    continue

                df_raw["_minute"] = df_raw["_ts"].dt.floor("min")
                ohlc = (
                    df_raw.groupby("_minute")["underlying_price"]
                    .agg(open="first", high="max", low="min", close="last")
                    .reset_index()
                    .rename(columns={"_minute": "timestamp"})
                )
                ohlc["timestamp"] = ohlc["timestamp"].astype(str)
                logger.debug(f"VIX spot derived from exp={exp_str} strike={central_strike} {right} ({len(ohlc)} bars)")
                return ohlc

        except Exception as e:
            logger.warning(f"Error deriving VIX spot: {e}")

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

    def _verify_parquet_file(self, filepath: Path) -> bool:
        """
        Verify if a Parquet file is complete and contains valid data.
        A full RTH day should have ~391 minutes.
        Also checks for NaN/Inf in OHLC columns.
        """
        try:
            df = pd.read_parquet(filepath)
            if df.empty:
                return False
            
            # 1. Check for NaN or Inf
            ohlc_cols = [c for c in ["open", "high", "low", "close", "underlying_price"] if c in df.columns]
            if ohlc_cols:
                if df[ohlc_cols].isna().any().any():
                    logger.warning(f"  [verify] {filepath.name}: Found NaN values")
                    return False
                # Convert to numpy for fast Inf check
                if np.isinf(df[ohlc_cols].to_numpy()).any():
                    logger.warning(f"  [verify] {filepath.name}: Found Inf values")
                    return False

            # 2. Check row count (only for spot files)
            # Full RTH: 9:30 - 16:00 inclusive = 391 bars.
            if "spot_" in filepath.name:
                row_count = len(df)
                if row_count < 380:
                    logger.warning(f"  [verify] {filepath.name}: Incomplete data ({row_count} rows)")
                    return False
            
            return True
        except Exception as e:
            logger.warning(f"  [verify] {filepath.name}: Corruption or error: {e}")
            return False

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
            df = df[df['underlying_price'] > 0].copy()
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

        # ── 1. Spot prices (CONCURRENT WITH SEMAPHORE MAX 4) ──
        spot_prices = {}
        spot_semaphore = asyncio.Semaphore(4)

        async def fetch_and_process_spot(symbol):
            async with spot_semaphore:
                if symbol == "VIX":
                    df_spot = await self._fetch_spot_vix()
                else:
                    df_spot = await self._fetch_spot(symbol)
                
                self._save_parquet(df_spot, f"spot_{symbol}_latest.parquet")
                
                if not df_spot.empty and 'close' in df_spot.columns:
                    last_price = float(df_spot['close'].iloc[-1])
                    logger.info(f"  [Spot {symbol}] ${last_price:.2f}")
                    return symbol, last_price
                else:
                    fallback_price = self._load_spot_local(symbol)
                    if fallback_price > 0:
                        logger.info(f"  [Spot {symbol}] ${fallback_price:.2f} (fallback)")
                    return symbol, fallback_price

        spot_tasks = [fetch_and_process_spot(sym) for sym in SPOT_SYMBOLS]
        logger.info("Downloading spot prices (Max 4 concurrently)...")
        results = await asyncio.gather(*spot_tasks)
        for sym, price in results:
            spot_prices[sym] = price

        # ── 1.1 Update ATR (needed for options filtering) ──
        for ticker in OPTIONS_TICKERS:
            self.day_atr[ticker] = self._calculate_current_atr(ticker)
            logger.debug(f"  [ATR][{ticker}] Current 1m ATR: {self.day_atr[ticker]:.4f} (Filter range: ±{50*self.day_atr[ticker]:.2f})")

        # ── 2. Options data per ticker (CONCURRENT WITH SEMAPHORE MAX 4) ──
        # El semáforo limita a 4 peticiones en vuelo exactamente
        semaphore = asyncio.Semaphore(4)

        async def fetch_and_save(options_symbol, exp, ep_key, current_spot, fname):
            async with semaphore:  # Espera su turno en la fila de 4
                try:
                    result_df = await self._fetch_options_data(options_symbol, exp, ep_key, current_spot, ticker)
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
            
            # Use ticker context in fetch_and_save (already updated in semaphore def)

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

    def _get_previous_trading_days(self, n: int = 15) -> list[date]:
        """Return the last N trading days BEFORE today using the market calendar."""
        # Get today's date in ET
        today = datetime.now(ET).date()
        
        # We want the N trading days PRIOR to today.
        # get_market_trading_days(n+1) will include today if it's a trading day,
        # so we fetch n+1 and exclude today to be safe and accurate.
        all_recent = get_market_trading_days(n + 1, end_date=today)
        
        # Filter out today if it's in the list, then take last N
        result = [d for d in all_recent if d < today]
        return result[-n:]

    async def _backfill_historical_spot(self):
        """
        On startup, ensure spot_SPX/VIX/TLT data exists for the last 15 trading days.
        If missing or incomplete/corrupt, download full-day OHLC from ThetaData.
        This provides the bot with Historical IB (D-1 to D-15) and accurate ATR.
        """
        prev_days = self._get_previous_trading_days(15)
        logger.info(f"Backfilling historical spot for {len(prev_days)} previous trading days...")

        semaphore = asyncio.Semaphore(4)
        tasks = []

        async def fetch_and_save_spot(day, symbol, day_str, filepath):
            async with semaphore:
                logger.info(f"  Downloading spot {symbol} for {day_str}...")
                try:
                    # Map SPX to SPXW just for the underlying proxy request
                    api_symbol = "SPXW" if symbol == "SPX" else symbol
                    res = await self.client.fetch_underlying_ohlc(api_symbol, day_str, interval="1m")
                    if res and not res.data.empty:
                        df = self._fix_ohlc_zeros(res.data.copy())
                        if "timestamp" in df.columns:
                            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(str), format="mixed", errors="coerce")
                        elif "time" in df.columns:
                            df["time"] = pd.to_datetime(df["time"].astype(str), format="mixed", errors="coerce")
                        df.to_parquet(filepath, engine='pyarrow', index=False)
                        logger.info(f"  ✓ spot_{symbol} {day_str} ({len(df)} rows)")
                    else:
                        logger.warning(f"  ✗ spot_{symbol} {day_str}: empty data")
                except Exception as e:
                    logger.warning(f"  ✗ spot_{symbol} {day_str}: {e}")

        for day in prev_days:
            day_str = day.strftime("%Y%m%d")
            day_dir = self._rt_data_base / day_str
            day_dir.mkdir(parents=True, exist_ok=True)

            for symbol in SPOT_SYMBOLS:
                filepath = day_dir / f"spot_{symbol}_latest.parquet"
                if filepath.exists():
                    if self._verify_parquet_file(filepath):
                        continue  # File exists and is valid
                    else:
                        logger.info(f"  [verify] {symbol} {day_str} failed verification, re-downloading...")
                
                tasks.append(fetch_and_save_spot(day, symbol, day_str, filepath))

        if tasks:
            logger.info(f"Queueing {len(tasks)} backfill tasks (Max 4 concurrently)...")
            await asyncio.gather(*tasks)

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

    def _calculate_current_atr(self, ticker: str) -> float:
        """Calculate 15-day ATR from historical daily ranges (high-low)."""
        hist = self.historical_ibs.get(ticker, [])
        # Each entry in hist is {ib_high, ib_low, close_price, daily_high, daily_low}
        # Using daily_high - daily_low for true ATR-like range
        ranges = []
        for h in hist:
            if h is not None:
                h_daily = h.get('daily_high', h['ib_high'])
                l_daily = h.get('daily_low', h['ib_low'])
                ranges.append(h_daily - l_daily)
        
        if len(ranges) >= 1:
            return float(np.mean(ranges))
        
        # Fallbacks (consistent with original logic)
        return 70.0 if ticker == "SPX" else 4.0

    @staticmethod
    def _is_near_level(price: float, level: float, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
        if price <= 0 or level <= 0:
            return False
        return abs(price - level) / price < threshold

    @staticmethod
    def _calculate_fibonacci_levels(ib_high: float, ib_low: float) -> dict:
        ib_range = ib_high - ib_low
        return {
            "fib_127_up": ib_low + (ib_range * 1.272),
            "fib_161_up": ib_low + (ib_range * 1.618),
            "fib_200_up": ib_low + (ib_range * 2.0),
            "fib_127_dn": ib_low + (ib_range * -0.272),
            "fib_161_dn": ib_low + (ib_range * -0.618),
            "fib_200_dn": ib_low + (ib_range * -1.0),
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
        if level_a is None or level_b is None or spot_price is None:
            return 0.0
        if spot_price <= 0:
            return 0.0
        dist_a = abs(spot_price - level_a) / spot_price
        dist_b = abs(spot_price - level_b) / spot_price
        overlap_dist = abs(level_a - level_b) / spot_price
        return float(np.exp(-0.5 * (dist_a/sigma)**2) * np.exp(-0.5 * (dist_b/sigma)**2) * np.exp(-0.5 * (overlap_dist/(2*sigma))**2))

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
        """Load Historical IB (D-1 to D-15) from previous days' spot Parquet."""
        prev_days = self._get_previous_trading_days(15)
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
                    df["dt"] = pd.to_datetime(df["timestamp"].astype(str), format="mixed", errors="coerce")
                elif "time" in df.columns:
                    df["dt"] = pd.to_datetime(df["time"].astype(str), format="mixed", errors="coerce")
                else:
                    self.historical_ibs[ticker].append(None)
                    continue

                df = df.sort_values("dt")
                df = df[(df["dt"].dt.time >= dt_time(9, 0)) & (df["dt"].dt.time <= dt_time(17, 0))]

                if df.empty:
                    self.historical_ibs[ticker].append(None)
                    continue

                rth_df = df[df["dt"].dt.time >= dt_time(9, 30)]
                if rth_df.empty:
                    self.historical_ibs[ticker].append(None)
                    continue

                rth_open = rth_df["dt"].dt.normalize().iloc[0] + pd.Timedelta(hours=9, minutes=30)
                ib_end = rth_open + pd.Timedelta(minutes=60)
                df_ib = rth_df[(rth_df["dt"] >= rth_open) & (rth_df["dt"] < ib_end)]

                ib_h = float(df_ib["high"].max()) if not df_ib.empty and "high" in df_ib.columns else 0
                ib_l = float(df_ib["low"].min()) if not df_ib.empty and "low" in df_ib.columns else 0

                close_df = df[df["dt"].dt.time <= dt_time(16, 0)]
                close_price = float(close_df["close"].iloc[-1]) if not close_df.empty and "close" in close_df.columns else 0

                if ib_h > 0 and ib_l > 0:
                    self.historical_ibs[ticker].append({
                        "ib_high": ib_h, "ib_low": ib_l,
                        "daily_high": float(df["high"].max()),
                        "daily_low": float(df["low"].min()),
                        "close_price": close_price, "date_str": day_str,
                    })
                else:
                    self.historical_ibs[ticker].append(None)
            except Exception as e:
                logger.warning(f"Failed to load historical IB for {ticker} {day_str}: {e}")
                self.historical_ibs[ticker].append(None)

        while len(self.historical_ibs[ticker]) < 15:
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
            df["dt"] = pd.to_datetime(df["timestamp"].astype(str), format="mixed", errors="coerce")
        elif "time" in df.columns:
            df["dt"] = pd.to_datetime(df["time"].astype(str), format="mixed", errors="coerce")
        else:
            return
        df = df.sort_values("dt")
        df_rth = df[df["dt"].dt.time >= dt_time(9, 30)]
        if df_rth.empty:
            return
        rth_start = df_rth["dt"].dt.normalize().iloc[0] + pd.Timedelta(hours=9, minutes=30)
        ib_end = rth_start + pd.Timedelta(minutes=60)
        df_ib = df_rth[(df_rth["dt"] >= rth_start) & (df_rth["dt"] < ib_end)]
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

        # 2. Update IB: re-compute during the first hour (9:30-10:30)
        # to ensure it expands dynamically. Locks after 60 minutes.
        if self.ib_high.get(ticker) is None or minutes_since_open <= 60:
            self._compute_ib_from_spot(ticker)

        atm_iv = self._load_atm_iv_local(spot, ticker)

        self.price_history[ticker].append((minutes_since_open, spot))
        
        # ── State Updates (for advanced features & Wonham) ──
        self.net_gamma_window[ticker].append(exp_0dte["net_gamma"])
        self.net_charm_history[ticker].append(exp_0dte["net_charm"])
        # Delta-filtered PCR proxy (dynamic live tracking using volume changes if available)
        try:
            day_atr = self.day_atr.get(ticker, 1.0)
            otm_range = 1.5 * day_atr
            df_opt = exp_0dte.get('_df')
            
            pcr_val = 0.5
            if df_opt is not None and not df_opt.empty and 'volume' in df_opt.columns:
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
                
                if not hasattr(self, '_prev_call_vol'):
                    self._prev_call_vol = {}
                    self._prev_put_vol = {}
                    
                prev_vol_c = self._prev_call_vol.get(ticker, 0)
                prev_vol_p = self._prev_put_vol.get(ticker, 0)
                
                min_call_vol = max(0, call_vol - prev_vol_c)
                min_put_vol = max(0, put_vol - prev_vol_p)
                
                self._prev_call_vol[ticker] = call_vol
                self._prev_put_vol[ticker] = put_vol
                
                if min_call_vol + min_put_vol > 0:
                    pcr_val = min_put_vol / (min_call_vol + 1e-6)
            
            self.pcr_history[ticker].append(pcr_val)
        except Exception as e:
            logger.error(f"[{ticker}] Error calculating dynamic PCR: {e}")
            self.pcr_history[ticker].append(0.5) 

        # Update Wonham Filter State
        prices = [p for _, p in self.price_history[ticker]]
        if len(prices) >= 2:
            # Recursive update using the last known probability
            self.wonham_probs[ticker] = compute_wonham_filter(
                [prices[-2], prices[-1]], 
                p_start=self.wonham_probs[ticker]
            )[-1]

        # ── Unified Feature Extraction (Single Source of Truth) ──
        features_vec = extract_feature_vector(
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
            day_atr=self.day_atr.get(ticker, 1.0),
            now_et=now_et,
            FEATURE_COLUMNS=FEATURE_COLUMNS,
            wonham_prob=self.wonham_probs[ticker]
        )

        # ── Build Final Dataframe Row ──
        row = {col: float(features_vec[i]) for i, col in enumerate(FEATURE_COLUMNS)}
        
        # Update prev_features for the next poll's temporal deltas
        self.prev_features[ticker] = {
            "spot": spot,
            "net_gamma": exp_0dte["net_gamma"],
            "net_vanna": exp_0dte["net_vanna"],
            "net_dgex": exp_0dte["net_dgex"],
            "net_delta": exp_0dte.get("net_delta", 0.0),
            "net_vega": exp_0dte.get("net_vega", 0.0),
            "net_vomma": exp_0dte.get("net_vomma", 0.0),
        }

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