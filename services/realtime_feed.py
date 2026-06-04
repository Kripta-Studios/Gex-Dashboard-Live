"""
Real-Time Options + Spot Feed — Parquet-based for MLP+RL Bot

60-second polling daemon that fetches from ThetaData:
  - SPXW 0DTE:    Greeks, OI, IV, OHLC (all strikes, calls+puts)
  - SPXW Weekly:  Greeks, OI           (all strikes, calls+puts)
  - QQQ/SPY 0DTE+Weekly: same schema
  - Spot prices:  SPX, QQQ, SPY, VIX, TLT (1-min OHLC candles)

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
import json
import signal
import time as time_module
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
    extract_feature_vector, compute_wonham_filter,
    inverse_safe_log, invert_delta_filtered_pcr
)
from neural.hybrid_model import FEATURE_COLUMNS
from modules.utils import get_market_trading_days

try:
    import torch
    from neural.jepa.features import load_feature_names
    from neural.jepa.xinput_dataset import XInputNormalizers
    from neural.jepa.xinput_model import load_xinput_model
    JEPA_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - live dependency guard
    torch = None
    load_feature_names = None
    XInputNormalizers = None
    load_xinput_model = None
    JEPA_IMPORT_ERROR = exc

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
# OI is removed from regular polling because it's static intraday.
# IV is removed because 'greeks' already contains implied_volatility.
ENDPOINTS_0DTE  = ["greeks", "ohlc"]
ENDPOINTS_WEEKLY = ["greeks"]
FEED_STATE_FILENAME = "feed_intraday_state.json"
DEFAULT_POLL_INTERVAL_SECONDS = 60
MODEL_SAMPLE_MINUTES = 5
MARKET_DATA_START_TIME = dt_time(9, 30)
MARKET_DATA_STOP_TIME = dt_time(16, 1)
JEPA_LIVE_EXECUTION_CONFIG = {
    "policy": "base_jepa_180m_option_value_blended_trail050_025_cutoff1430",
    "entry_cutoff_et": "14:30",
    "model_sample_minutes": MODEL_SAMPLE_MINUTES,
    "selector": "OptionValue rule/best mean + 2.0*abs_delta over 0.10..0.70 candidates",
    "fallback_delta_target": 0.70,
    "cooldown_minutes": 180,
    "risk_capital_dollars": 1000.0,
    "hard_stop_pct": -0.60,
    "trail_activation_pct": 0.50,
    "trail_drawdown_pct": 0.25,
    "take_profit_pct": 10.00,
    "max_hold_minutes": 180,
    "eod_cleanup_et": "16:00",
    "data_poll_stop_et": "16:01",
}
DEFAULT_JEPA_FEATURE_MODEL_DIR = os.path.join(
    PROJECT_ROOT,
    "neural",
    "models",
    "jepa",
    os.environ.get("JEPA_FEATURE_EXPERIMENT", "xinput_v3_production"),
)

# Spot indices/stocks to fetch
SPOT_SYMBOLS = ["SPX", "QQQ", "SPY", "VIX", "TLT"]

# Map trading ticker → options symbol
OPTIONS_TICKERS = {
    "SPX": "SPXW",    # SPX uses SPXW options
    "QQQ": "QQQ",    # QQQ uses QQQ options directly
    "SPY": "SPY",    # SPY uses SPY options (American-style)
}


class OnlineXInputJEPAFeatureEngine:
    """Append live-safe XInputJEPA features to the 5-minute feature diary.

    The training pipeline builds JEPA features from same-day 5-minute rows only.
    This engine mirrors that contract: each feature at row t is computed from
    rows <= t, and lagged prediction errors compare an old prediction with the
    state that is now observable.
    """

    def __init__(
        self,
        model_dir: str | Path = DEFAULT_JEPA_FEATURE_MODEL_DIR,
        device: str = "auto",
        enabled: bool = True,
        batch_size: int = 1024,
    ):
        self.model_dir = Path(model_dir)
        self.device_name = device
        self.enabled = bool(enabled)
        self.batch_size = int(batch_size)
        self.ready = False
        self.normalizers = None
        self.model = None
        self.device = None
        self.feature_names = self._default_feature_names()

        if not self.enabled:
            logger.info("[JEPA] Live XInputJEPA feature generation disabled")
            return
        if JEPA_IMPORT_ERROR is not None:
            logger.warning(f"[JEPA] Live XInputJEPA imports unavailable: {JEPA_IMPORT_ERROR}")
            return
        try:
            self._load()
        except Exception as exc:
            logger.warning(f"[JEPA] Could not load live XInputJEPA feature engine: {exc}")

    @staticmethod
    def _default_feature_names() -> list[str]:
        names = [f"xjepa_z_{i:02d}" for i in range(16)]
        names += [f"xjepa_u_{i:02d}" for i in range(12)]
        names += [
            "xjepa_latent_velocity",
            "xjepa_input_velocity",
            "xjepa_pred_dispersion_short",
            "xjepa_pred_dispersion_long",
            "xjepa_lagged_pred_30m_err",
            "xjepa_lagged_pred_60m_err",
            "xjepa_lagged_pred_180m_err",
            "xjepa_prob_short",
            "xjepa_prob_hold",
            "xjepa_prob_long",
            "xjepa_trade_confidence",
            "xjepa_direction_score",
            "xjepa_entropy",
            "xjepa_context_valid",
        ]
        return names

    def _load(self) -> None:
        normalizer_path = self.model_dir / "normalizers.json"
        model_path = self.model_dir / "model.pt"
        feature_names_path = self.model_dir / "jepa_feature_names.json"
        if not normalizer_path.exists():
            raise FileNotFoundError(normalizer_path)
        if not model_path.exists():
            raise FileNotFoundError(model_path)

        self.normalizers = XInputNormalizers.load(normalizer_path)
        self.model = load_xinput_model(self.model_dir, map_location="cpu")
        if feature_names_path.exists():
            self.feature_names = load_feature_names(feature_names_path)
        if not self.feature_names:
            self.feature_names = self._default_feature_names()

        if self.device_name == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(self.device_name)
        self.model.to(self.device)
        self.model.eval()
        self.ready = True
        logger.info(
            f"[JEPA] Live XInputJEPA feature engine loaded from {self.model_dir} "
            f"on {self.device}"
        )

    @staticmethod
    def _pairwise_dispersion(preds: np.ndarray, indices: list[int]) -> float:
        valid = [i for i in indices if i >= 0]
        if len(valid) < 2:
            return 0.0
        vals = preds[valid]
        dists = []
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                dists.append(float(np.linalg.norm(vals[i] - vals[j])))
        return float(np.mean(dists)) if dists else 0.0

    def _zero_features(self, n_rows: int) -> dict[str, np.ndarray]:
        return {name: np.zeros(n_rows, dtype=np.float32) for name in self.feature_names}

    def append_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        n_rows = len(out)
        if n_rows == 0:
            for name in self.feature_names:
                out[name] = np.asarray([], dtype=np.float32)
            return out

        feature_data = self._zero_features(n_rows)
        if not self.ready:
            for name, values in feature_data.items():
                out[name] = values
            return out

        context_len = int(self.model.config.context_len)
        if n_rows < context_len:
            for name, values in feature_data.items():
                out[name] = values
            return out

        work = out.copy()
        for col in self.normalizers.state.feature_names + self.normalizers.input.feature_names:
            if col not in work.columns:
                work[col] = 0.0
        sort_cols = [c for c in ["timestamp", "time", "minutes_since_open"] if c in work.columns]
        if sort_cols:
            work = work.sort_values(sort_cols).reset_index(drop=False).rename(columns={"index": "_orig_index"})
        else:
            work = work.reset_index(drop=False).rename(columns={"index": "_orig_index"})

        try:
            s_arr = self.normalizers.state.transform_frame(work)
            u_arr = self.normalizers.input.transform_frame(work)
        except Exception as exc:
            logger.warning(f"[JEPA] Normalization failed; writing invalid xjepa context: {exc}")
            for name, values in feature_data.items():
                out[name] = values
            return out

        contexts_s = []
        contexts_u = []
        positions = []
        for pos in range(context_len - 1, len(work)):
            contexts_s.append(s_arr[pos - context_len + 1 : pos + 1])
            contexts_u.append(u_arr[pos - context_len + 1 : pos + 1])
            positions.append(pos)
        if not contexts_s:
            for name, values in feature_data.items():
                out[name] = values
            return out

        state_ctx = np.stack(contexts_s, axis=0).astype(np.float32)
        input_ctx = np.stack(contexts_u, axis=0).astype(np.float32)
        z_parts, u_parts, pred_parts, prob_parts = [], [], [], []
        with torch.no_grad():
            for start in range(0, len(state_ctx), self.batch_size):
                s = torch.from_numpy(state_ctx[start : start + self.batch_size]).to(self.device).float()
                uin = torch.from_numpy(input_ctx[start : start + self.batch_size]).to(self.device).float()
                z, u_lat, pred, logits = self.model(s, uin)
                z_parts.append(z.cpu().numpy())
                u_parts.append(u_lat.cpu().numpy())
                pred_parts.append(pred.cpu().numpy())
                prob_parts.append(torch.softmax(logits, dim=-1).cpu().numpy())

        z = np.concatenate(z_parts)
        u_lat = np.concatenate(u_parts)
        pred = np.concatenate(pred_parts)
        probs = np.concatenate(prob_parts)

        z_dim = int(self.model.config.z_dim)
        u_dim = int(self.model.config.u_dim)
        horizons = [int(h) for h in self.model.config.horizons]
        h_to_idx = {h: i for i, h in enumerate(horizons)}
        z_by_pos = np.zeros((len(work), z_dim), dtype=np.float32)
        u_by_pos = np.zeros((len(work), u_dim), dtype=np.float32)
        pred_by_pos = np.zeros((len(work), len(horizons), z_dim), dtype=np.float32)
        prob_by_pos = np.zeros((len(work), 3), dtype=np.float32)
        valid = np.zeros(len(work), dtype=bool)

        for row_i, pos in enumerate(positions):
            z_by_pos[pos] = z[row_i]
            u_by_pos[pos] = u_lat[row_i]
            pred_by_pos[pos] = pred[row_i]
            prob_by_pos[pos] = probs[row_i]
            valid[pos] = True

        for pos in range(len(work)):
            orig_i = int(work.loc[pos, "_orig_index"])
            if not valid[pos]:
                continue
            feature_data["xjepa_context_valid"][orig_i] = 1.0
            for zi in range(z_dim):
                col = f"xjepa_z_{zi:02d}"
                if col in feature_data:
                    feature_data[col][orig_i] = z_by_pos[pos, zi]
            for ui in range(u_dim):
                col = f"xjepa_u_{ui:02d}"
                if col in feature_data:
                    feature_data[col][orig_i] = u_by_pos[pos, ui]
            if pos >= 1 and valid[pos - 1]:
                feature_data["xjepa_latent_velocity"][orig_i] = float(np.linalg.norm(z_by_pos[pos] - z_by_pos[pos - 1]))
                feature_data["xjepa_input_velocity"][orig_i] = float(np.linalg.norm(u_by_pos[pos] - u_by_pos[pos - 1]))
            short_idx = [h_to_idx.get(h, -1) for h in (1, 3, 6)]
            long_idx = [h_to_idx.get(h, -1) for h in (12, 24, 36)]
            feature_data["xjepa_pred_dispersion_short"][orig_i] = self._pairwise_dispersion(pred_by_pos[pos], short_idx)
            feature_data["xjepa_pred_dispersion_long"][orig_i] = self._pairwise_dispersion(pred_by_pos[pos], long_idx)
            for h, col in [
                (6, "xjepa_lagged_pred_30m_err"),
                (12, "xjepa_lagged_pred_60m_err"),
                (36, "xjepa_lagged_pred_180m_err"),
            ]:
                hi = h_to_idx.get(h)
                src = pos - h
                if col in feature_data and hi is not None and src >= 0 and valid[src]:
                    feature_data[col][orig_i] = float(np.linalg.norm(pred_by_pos[src, hi] - z_by_pos[pos]))
            p = prob_by_pos[pos]
            entropy = -float(np.sum(p * np.log(np.clip(p, 1e-8, 1.0))))
            feature_data["xjepa_prob_short"][orig_i] = float(p[0])
            feature_data["xjepa_prob_hold"][orig_i] = float(p[1])
            feature_data["xjepa_prob_long"][orig_i] = float(p[2])
            feature_data["xjepa_trade_confidence"][orig_i] = float(max(p[0], p[2]))
            feature_data["xjepa_direction_score"][orig_i] = float(p[2] - p[0])
            feature_data["xjepa_entropy"][orig_i] = entropy

        for name, values in feature_data.items():
            out[name] = values
        return out


class RealtimeOptionsFeed:
    """
    Real-time options + spot feed for GBM+RL bot.

    Polls every 60 seconds during market hours.
    Fetches SPXW + QQQ options (0DTE + weekly) + spot prices.
    Saves all data as Parquet files in rt_data/{YYYYMMDD}/.
    """

    def __init__(
        self,
        poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
        output_dir: str = None,
        enable_jepa_features: bool = True,
        jepa_model_dir: str = DEFAULT_JEPA_FEATURE_MODEL_DIR,
        jepa_device: str = "auto",
    ):
        thetadata_url = os.environ.get("THETADATA_URL", "http://91.99.90.39:25503/v3")
        self.client = ThetaClient(base_url=thetadata_url)
        self.poll_interval = poll_interval
        self.running = False

        today_str = datetime.now(ET).strftime("%Y%m%d")
        self.output_dir = Path(output_dir or os.path.join(PROJECT_ROOT, "rt_data", today_str))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_trading_day = datetime.now(ET).date()
        self._write_live_execution_config()

        # Expiration cache — per ticker: {"SPX": (0dte, weekly), "QQQ": (0dte, weekly)}
        self._expirations = {}  # ticker -> (exp_0dte, exp_weekly)
        self._expirations_resolved = False
        self._historical_backfilled = False
        self._restored_state_day: str | None = None

        # Base rt_data directory (parent of per-day dirs)
        self._rt_data_base = Path(output_dir or os.path.join(PROJECT_ROOT, "rt_data"))
        self._rt_data_base.mkdir(parents=True, exist_ok=True)

        # ── ML feature computation state (per-ticker) ──
        self.price_history = {}    # ticker -> deque(maxlen=35)
        self.iv_history = {}       # ticker -> deque(maxlen=32)
        self.tlt_price_history = deque(maxlen=35)  # shared (TLT is global)
        self.ib_high: dict[str, float | None] = {}  # ticker -> float
        self.ib_low: dict[str, float | None] = {}   # ticker -> float
        self.historical_ibs = {}   # ticker -> list[dict|None]
        self.prev_features = {}    # ticker -> dict
        self._ml_features_rows = {}  # ticker -> list of rows
        self._ml_features_1m_rows = {}  # ticker -> list of diagnostic 1m rows
        self._last_model_sample_bucket = {}  # ticker -> last emitted 5m bucket
        self._historical_ib_loaded = {}  # ticker -> bool
        self.day_atr = {}             # ticker -> float
        self.net_gamma_window = {}    # ticker -> deque(maxlen=60)
        self.net_charm_history = {}   # ticker -> deque(maxlen=32)
        self.pcr_history = {}         # ticker -> deque(maxlen=32)
        self.wonham_probs = {}        # ticker -> float
        self._gamma_regime_state = {}        # ticker -> latest raw gamma regime
        self._gamma_regime_persistence = {}  # ticker -> consecutive 5m/1m observations in same regime
        self._prev_call_vol = {tk: 0.0 for tk in OPTIONS_TICKERS}
        self._prev_put_vol = {tk: 0.0 for tk in OPTIONS_TICKERS}

        # Initialize per-ticker structures
        for tk in OPTIONS_TICKERS:
            self.price_history[tk] = deque(maxlen=35)
            self.iv_history[tk] = deque(maxlen=32)
            self.ib_high[tk] = None
            self.ib_low[tk] = None
            self.historical_ibs[tk] = []
            self._ml_features_rows[tk] = []
            self._ml_features_1m_rows[tk] = []
            self._last_model_sample_bucket[tk] = None
            self._historical_ib_loaded[tk] = False
            self.day_atr[tk] = 1.0
            self.net_gamma_window[tk] = deque(maxlen=60)
            self.net_charm_history[tk] = deque(maxlen=32)
            self.pcr_history[tk] = deque(maxlen=32)
            self.wonham_probs[tk] = 0.5
            self._gamma_regime_state[tk] = None
            self._gamma_regime_persistence[tk] = 0

        self.jepa_feature_engine = OnlineXInputJEPAFeatureEngine(
            model_dir=jepa_model_dir,
            device=jepa_device,
            enabled=enable_jepa_features,
        )

    def _write_live_execution_config(self) -> None:
        payload = dict(JEPA_LIVE_EXECUTION_CONFIG)
        payload["written_at_et"] = datetime.now(ET).isoformat()
        path = self.output_dir / "jepa_live_execution_config.json"
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[JEPA] Could not write live execution config {path}: {exc}")

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

        # Optimized Filter: ±15 ATR (balance between model needs and RAM usage)
        atr = self.day_atr.get(ticker, 1.0)
        min_strike = spot_price - (15.0 * atr) if spot_price > 0 else 0.0
        max_strike = spot_price + (15.0 * atr) if spot_price > 0 else float('inf')

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
                        
                        # --- FILTRO ±15 ATR ---
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
                        # --- FILTRO ±15 ATR (caso diccionario plano) ---
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
                # VIX/TLT might have fewer bars if derived — be more lenient
                min_rows = 380 if "VIX" not in filepath.name and "TLT" not in filepath.name else 50
                if row_count < min_rows:
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
            norm = RealtimeOptionsFeed._float_or_none(value)
            if norm is not None:
                normalized[key] = norm
        return normalized or None

    def _get_state_path(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir / FEED_STATE_FILENAME

    def _reset_intraday_runtime_state(self):
        self.tlt_price_history.clear()
        self._prev_call_vol = {tk: 0.0 for tk in OPTIONS_TICKERS}
        self._prev_put_vol = {tk: 0.0 for tk in OPTIONS_TICKERS}
        self.prev_features = {}
        for tk in OPTIONS_TICKERS:
            self.price_history[tk].clear()
            self.iv_history[tk].clear()
            self.ib_high[tk] = None
            self.ib_low[tk] = None
            self.historical_ibs[tk] = []
            self._ml_features_rows[tk] = []
            self._ml_features_1m_rows[tk] = []
            self._last_model_sample_bucket[tk] = None
            self._historical_ib_loaded[tk] = False
            self.day_atr[tk] = 1.0
            self.net_gamma_window[tk].clear()
            self.net_charm_history[tk].clear()
            self.pcr_history[tk].clear()
            self.wonham_probs[tk] = 0.5
            self._gamma_regime_state[tk] = None
            self._gamma_regime_persistence[tk] = 0

    @staticmethod
    def _model_sample_bucket(minutes_since_open) -> int | None:
        minute = RealtimeOptionsFeed._float_or_none(minutes_since_open)
        if minute is None:
            return None
        return int(max(0, minute)) // MODEL_SAMPLE_MINUTES

    def _load_existing_ml_feature_rows(self, ticker: str) -> list[dict]:
        path = self.output_dir / f"ml_features_{ticker}_latest.parquet"
        if not path.exists():
            return []
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return []
            if "minutes_since_open" in df.columns:
                df = (
                    df.sort_values("timestamp" if "timestamp" in df.columns else "minutes_since_open")
                    .drop_duplicates(subset=["minutes_since_open"], keep="last")
                    .reset_index(drop=True)
                )
            return df.to_dict("records")
        except Exception as e:
            logger.warning(f"[ML][{ticker}] Failed to reload feature diary: {e}")
            return []

    def _latest_model_sample_bucket_from_rows(self, ticker: str) -> int | None:
        rows = self._ml_features_rows.get(ticker) or []
        if not rows:
            return None
        return self._model_sample_bucket(rows[-1].get("minutes_since_open"))

    def _restore_tlt_price_history_from_spot(self) -> bool:
        path = self.output_dir / "spot_TLT_latest.parquet"
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
            self.tlt_price_history.clear()
            for _, row in df.tail(self.tlt_price_history.maxlen).iterrows():
                close = self._float_or_none(row.get("close", 0.0))
                if close is None or close <= 0:
                    continue
                mins = max(0, (row["dt"].hour * 60 + row["dt"].minute) - (9 * 60 + 30))
                self.tlt_price_history.append((float(mins), close))
            return len(self.tlt_price_history) > 0
        except Exception as e:
            logger.warning(f"[TLT] Failed to restore intraday history: {e}")
            return False

    def _restore_price_history_from_spot(self, ticker: str) -> bool:
        path = self.output_dir / f"spot_{ticker}_latest.parquet"
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
            self.price_history[ticker].clear()
            for _, row in df.tail(self.price_history[ticker].maxlen).iterrows():
                close = self._float_or_none(row.get("close", 0.0))
                if close is None or close <= 0:
                    continue
                mins = max(0, (row["dt"].hour * 60 + row["dt"].minute) - (9 * 60 + 30))
                self.price_history[ticker].append((float(mins), close))
            if len(self.price_history[ticker]) > 0:
                self._compute_ib_from_spot(ticker)
                return True
        except Exception as e:
            logger.warning(f"[{ticker}] Failed to restore spot history: {e}")
        return False

    def _restore_prev_features_from_df(self, ticker: str, df_features: pd.DataFrame, latest_spot: float):
        """Restore prev_features in the same representation used by training.

        collect_training_data_spx_qqq.py sets prev_features = features_dict and
        then adds prev_features["spot"] = spot.  That means temporal deltas in
        extract_feature_vector compare the current raw Greek exposures against
        the previous *feature-space* values, not against inverse-transformed raw
        exposures.  Keep live aligned with that training contract.
        """
        if df_features.empty:
            return
        last = df_features.iloc[-1]
        prev: dict[str, float] = {}
        for key, value in last.items():
            if key in {"timestamp", "date", "time", "ticker"}:
                continue
            norm = self._float_or_none(value)
            if norm is not None:
                prev[str(key)] = float(norm)

        spot = latest_spot
        if spot <= 0 and pd.notna(last.get("spot_price")):
            spot = self._float_or_none(last.get("spot_price")) or 0.0
        if spot > 0:
            prev["spot"] = float(spot)
        if prev:
            self.prev_features[ticker] = prev

    def _restore_feature_diary_state(self, ticker: str) -> bool:
        path = self.output_dir / f"ml_features_{ticker}_latest.parquet"
        if not path.exists():
            return False
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return False

            if "minutes_since_open" in df.columns:
                df = (
                    df.sort_values("timestamp" if "timestamp" in df.columns else "minutes_since_open")
                    .drop_duplicates(subset=["minutes_since_open"], keep="last")
                    .reset_index(drop=True)
                )

            self._ml_features_rows[ticker] = df.to_dict("records")
            self._last_model_sample_bucket[ticker] = self._latest_model_sample_bucket_from_rows(ticker)

            iv_col = "atm_iv_raw" if "atm_iv_raw" in df.columns else "atm_iv"
            if iv_col in df.columns:
                vals = [self._float_or_none(v) for v in df[iv_col].tail(self.iv_history[ticker].maxlen)]
                self.iv_history[ticker] = deque([v for v in vals if v is not None and v > 0], maxlen=32)

            if "pcr_raw" in df.columns:
                pcr_vals = [self._float_or_none(v) for v in df["pcr_raw"].tail(self.pcr_history[ticker].maxlen)]
                self.pcr_history[ticker] = deque([v for v in pcr_vals if v is not None and v >= 0], maxlen=32)
            elif "delta_filtered_pcr" in df.columns:
                pcr_vals = []
                for val in df["delta_filtered_pcr"].tail(self.pcr_history[ticker].maxlen):
                    pcr_norm = self._float_or_none(val)
                    if pcr_norm is not None:
                        pcr_vals.append(float(invert_delta_filtered_pcr(pcr_norm)))
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
                last_prob = self._float_or_none(df["wonham_trend_prob"].iloc[-1])
                if last_prob is not None:
                    self.wonham_probs[ticker] = float(np.clip(last_prob, 0.0, 1.0))

            latest_spot = self.price_history[ticker][-1][1] if self.price_history[ticker] else 0.0
            self._restore_prev_features_from_df(ticker, df, latest_spot)
            return True
        except Exception as e:
            logger.warning(f"[ML][{ticker}] Failed to restore feature diary state: {e}")
            return False

    def _seed_pcr_volume_baseline(self, ticker: str, spot: float):
        options_symbol = OPTIONS_TICKERS.get(ticker, "SPXW")
        path = self.output_dir / f"{options_symbol}_ohlc_0dte_latest.parquet"
        if not path.exists() or spot <= 0:
            return
        try:
            df_opt = pd.read_parquet(path)
            if df_opt.empty or "volume" not in df_opt.columns or "strike" not in df_opt.columns or "right" not in df_opt.columns:
                return
            day_atr = max(self.day_atr.get(ticker, 1.0), 1e-6)
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
        state = {
            "session_date": self.current_trading_day.strftime("%Y%m%d"),
            "tlt_price_history": self._serialize_price_history(self.tlt_price_history),
            "prev_call_vol": {tk: float(v) for tk, v in self._prev_call_vol.items()},
            "prev_put_vol": {tk: float(v) for tk, v in self._prev_put_vol.items()},
            "tickers": {},
        }

        for tk in OPTIONS_TICKERS:
            state["tickers"][tk] = {
                "price_history": self._serialize_price_history(self.price_history[tk]),
                "iv_history": [float(v) for v in self.iv_history[tk]],
                "ib_high": self._float_or_none(self.ib_high.get(tk)),
                "ib_low": self._float_or_none(self.ib_low.get(tk)),
                "prev_features": self._normalize_prev_features(self.prev_features.get(tk)),
                "last_model_sample_bucket": self._last_model_sample_bucket.get(tk),
                "day_atr": float(self.day_atr.get(tk, 1.0)),
                "net_gamma_window": [float(v) for v in self.net_gamma_window[tk]],
                "net_charm_history": [float(v) for v in self.net_charm_history[tk]],
                "pcr_history": [float(v) for v in self.pcr_history[tk]],
                "wonham_prob": float(self.wonham_probs.get(tk, 0.5)),
                "gamma_regime_state": self._float_or_none(self._gamma_regime_state.get(tk)),
                "gamma_regime_persistence": int(self._gamma_regime_persistence.get(tk, 0)),
            }

        path = self._get_state_path()
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            logger.warning(f"Failed to save feed intraday state: {e}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def _restore_intraday_state_from_disk(self):
        day_str = self.current_trading_day.strftime("%Y%m%d")
        if self._restored_state_day == day_str:
            return

        self._reset_intraday_runtime_state()
        restored = False
        path = self._get_state_path()

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("session_date") == day_str:
                    self.tlt_price_history = self._deserialize_price_history(
                        state.get("tlt_price_history"), self.tlt_price_history.maxlen
                    )
                    for tk in OPTIONS_TICKERS:
                        tk_state = (state.get("tickers") or {}).get(tk, {})
                        self.price_history[tk] = self._deserialize_price_history(
                            tk_state.get("price_history"), self.price_history[tk].maxlen
                        )
                        self.iv_history[tk] = deque(
                            [float(v) for v in tk_state.get("iv_history", []) if self._float_or_none(v) is not None],
                            maxlen=32,
                        )
                        self.ib_high[tk] = self._float_or_none(tk_state.get("ib_high"))
                        self.ib_low[tk] = self._float_or_none(tk_state.get("ib_low"))
                        prev = self._normalize_prev_features(tk_state.get("prev_features"))
                        if prev:
                            self.prev_features[tk] = prev
                        sample_bucket = tk_state.get("last_model_sample_bucket")
                        if sample_bucket is not None:
                            try:
                                self._last_model_sample_bucket[tk] = int(sample_bucket)
                            except Exception:
                                self._last_model_sample_bucket[tk] = None
                        self.day_atr[tk] = float(tk_state.get("day_atr", 1.0))
                        self.net_gamma_window[tk] = deque(
                            [float(v) for v in tk_state.get("net_gamma_window", []) if self._float_or_none(v) is not None],
                            maxlen=60,
                        )
                        self.net_charm_history[tk] = deque(
                            [float(v) for v in tk_state.get("net_charm_history", []) if self._float_or_none(v) is not None],
                            maxlen=32,
                        )
                        self.pcr_history[tk] = deque(
                            [float(v) for v in tk_state.get("pcr_history", []) if self._float_or_none(v) is not None],
                            maxlen=32,
                        )
                        wonham = self._float_or_none(tk_state.get("wonham_prob"))
                        if wonham is not None:
                            self.wonham_probs[tk] = float(np.clip(wonham, 0.0, 1.0))
                        gamma_state = self._float_or_none(tk_state.get("gamma_regime_state"))
                        self._gamma_regime_state[tk] = gamma_state
                        try:
                            self._gamma_regime_persistence[tk] = int(tk_state.get("gamma_regime_persistence", 0) or 0)
                        except Exception:
                            self._gamma_regime_persistence[tk] = 0
                        self._ml_features_rows[tk] = self._load_existing_ml_feature_rows(tk)
                        if self._last_model_sample_bucket.get(tk) is None:
                            self._last_model_sample_bucket[tk] = self._latest_model_sample_bucket_from_rows(tk)
                        if self._ml_features_rows[tk]:
                            latest_spot = self.price_history[tk][-1][1] if self.price_history[tk] else 0.0
                            self._restore_prev_features_from_df(tk, pd.DataFrame(self._ml_features_rows[tk]), latest_spot)
                    self._prev_call_vol = {
                        tk: float((state.get("prev_call_vol") or {}).get(tk, 0.0))
                        for tk in OPTIONS_TICKERS
                    }
                    self._prev_put_vol = {
                        tk: float((state.get("prev_put_vol") or {}).get(tk, 0.0))
                        for tk in OPTIONS_TICKERS
                    }
                    restored = True
                    logger.info(f"[State] Feed intraday state restored from {path.name}")
            except Exception as e:
                logger.warning(f"[State] Failed to restore feed intraday state: {e}")

        if not restored:
            any_restored = self._restore_tlt_price_history_from_spot()
            for tk in OPTIONS_TICKERS:
                self._load_historical_ib_levels(tk)
                self.day_atr[tk] = self._calculate_current_atr(tk)
                any_restored = self._restore_price_history_from_spot(tk) or any_restored
                any_restored = self._restore_feature_diary_state(tk) or any_restored
                if self.price_history[tk]:
                    self._seed_pcr_volume_baseline(tk, self.price_history[tk][-1][1])
            if any_restored:
                logger.info("[State] Feed intraday histories rebuilt from rt_data")

        self._restored_state_day = day_str

    # ─────────────────────────────────────────
    # MAIN POLL CYCLE
    # ─────────────────────────────────────────

    async def poll_once(self):
        """Single poll cycle — fetch all data and save as Parquet."""
        now = datetime.now(ET)
        now_date = now.date()

        # ── NUEVO: Detección de cambio de día ──
        if now_date > self.current_trading_day:
            logger.info("Cambio de día detectado. Reseteando expiraciones y directorios.")
            self.current_trading_day = now_date
            self._expirations_resolved = False
            self._expirations.clear()
            self._restored_state_day = None
             
            # Actualizar la carpeta de salida al nuevo día
            today_str = now_date.strftime("%Y%m%d")
            self.output_dir = Path(os.path.join(self._rt_data_base, today_str))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self._write_live_execution_config()

        # Restore exact intraday state on reboot, or rebuild best-effort from rt_data.
        self._restore_intraday_state_from_disk()
        # ───────────────────────────────────────

        now_str = now.strftime("%H:%M:%S EST")
        logger.info(f"{'='*50}")
        logger.info(f"--- Poll at {now_str} ---")
        self._write_live_execution_config()

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
            logger.debug(f"  [ATR][{ticker}] Current 15-day ATR: {self.day_atr[ticker]:.4f} (Filter range: ±{15*self.day_atr[ticker]:.2f})")

        # ── 2. Options data per ticker (CONCURRENT WITH SEMAPHORE MAX 4) ──
        # El semáforo limita a 4 peticiones en vuelo exactamente
        semaphore = asyncio.Semaphore(4)

        async def fetch_and_save(options_symbol, exp, ep_key, current_spot, fname, ticker_sym):
            async with semaphore:  # Espera su turno en la fila de 4
                try:
                    result_df = await self._fetch_options_data(options_symbol, exp, ep_key, current_spot, ticker_sym)
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
                    tasks.append(fetch_and_save(options_symbol, exp_0dte, ep_key, current_spot, fname, ticker))

            # Preparar tareas Weekly
            if exp_weekly:
                logger.info(f"[{options_symbol} Weekly] Queueing exp={exp_weekly} | Full chain")
                for ep_key in ENDPOINTS_WEEKLY:
                    fname = f"{options_symbol}_{ep_key}_weekly_latest.parquet"
                    tasks.append(fetch_and_save(options_symbol, exp_weekly, ep_key, current_spot, fname, ticker))
            
            # --- NUEVO: Descargar OI una sola vez si no existe para hoy y es hora adecuada ---
            # El OI definitivo suele publicarse entre las 01:00 y 07:00 AM ET.
            # Bajándolo a partir de las 08:00 AM aseguramos datos frescos para la sesión.
            is_after_eight = now.hour >= 8
            for suffix, exp_target in [("0dte", exp_0dte), ("weekly", exp_weekly)]:
                if not exp_target: continue
                oi_fname = f"{options_symbol}_oi_{suffix}_latest.parquet"
                if not (self.output_dir / oi_fname).exists() and is_after_eight:
                    logger.info(f"[{options_symbol}] Downloading static OI for {suffix} (Time: {now.strftime('%H:%M')})...")
                    tasks.append(fetch_and_save(options_symbol, exp_target, "oi", current_spot, oi_fname, ticker))

        # Lanzar todas las tareas (el semáforo gestionará el tráfico internamente)
        if tasks:
            logger.info("Downloading options endpoints (Max 4 concurrently)...")
            await asyncio.gather(*tasks)

        # Force garbage collection after large Pandas processing
        import gc
        gc.collect()

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
        # Training load_historical_ib_levels returns D-1 first, then D-2...
        # get_previous_trading_days returns ascending dates, so reverse it here
        # to preserve offline/OOS feature parity for D1-D5 features.
        prev_days = list(reversed(self._get_previous_trading_days(15)))
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

    def _load_vix_history_from_rt(self, n_days: int = 5) -> list[float]:
        """Load previous trading-day VIX closes from rt_data, mirroring offline collector.

        The production/OOS collector computes vix_5d_mean/std outside
        extract_feature_vector.  Live must do the same instead of letting the
        FEATURE_COLUMNS vectorization silently fill those columns with 0.0.
        """
        vals: list[float] = []
        for day in reversed(self._get_previous_trading_days(int(n_days))):
            day_str = day.strftime("%Y%m%d")
            path = self._rt_data_base / day_str / "spot_VIX_latest.parquet"
            if not path.exists():
                continue
            try:
                df = pd.read_parquet(path)
                if df.empty or "close" not in df.columns:
                    continue
                close = self._float_or_none(df["close"].iloc[-1])
                if close is not None and close > 0:
                    vals.append(float(close))
            except Exception as exc:
                logger.warning(f"[VIX] Failed to load historical VIX {day_str}: {exc}")
        return vals

    def _compute_live_extra_context_features(self, ticker: str, spot: float) -> dict[str, float]:
        """Compute live-only context features that the offline collector adds manually.

        These columns are part of FEATURE_COLUMNS/model artifacts, but they are
        not produced inside services.compute_features.extract_feature_vector().
        If live calls extract_feature_vector(... FEATURE_COLUMNS=FEATURE_COLUMNS),
        they become silent zeros.  This method restores training/OOS parity.
        """
        vix_history = self._load_vix_history_from_rt(n_days=5)
        vix_5d_mean = float(np.mean(vix_history)) if len(vix_history) > 0 else 20.0
        vix_5d_std = float(np.std(vix_history)) if len(vix_history) > 1 else 0.0

        historical_ibs = self.historical_ibs.get(ticker, [])
        recent_5d_ibs = [h for h in historical_ibs if h is not None][:5]
        if recent_5d_ibs and spot > 0:
            ranges = []
            for h in recent_5d_ibs:
                high = self._float_or_none(h.get("daily_high", h.get("ib_high", 0.0))) or 0.0
                low = self._float_or_none(h.get("daily_low", h.get("ib_low", 0.0))) or 0.0
                if high > 0 and low > 0 and high >= low:
                    ranges.append(high - low)
            if ranges:
                atr_5d = float(np.mean(ranges))
                atr_5d_norm = float(np.clip(atr_5d / max(float(spot), 1e-9), 0.0, 0.05))
            else:
                atr_5d_norm = 0.005
        else:
            atr_5d_norm = 0.005

        live_feature_context_valid = (
            len(vix_history) >= 5
            and len(recent_5d_ibs) >= 5
            and vix_5d_mean > 0.0
            and vix_5d_std > 0.0
            and atr_5d_norm > 0.0
        )
        return {
            "vix_5d_mean": float(vix_5d_mean),
            "vix_5d_std": float(vix_5d_std),
            "atr_5d_norm": float(atr_5d_norm),
            "live_feature_context_valid": float(live_feature_context_valid),
        }

    def _update_signal_persistence(self, ticker: str, raw_net_gamma: float) -> float:
        """Mirror collect_training_data_spx_qqq.py regime persistence."""
        try:
            raw_net_gamma = float(raw_net_gamma)
        except Exception:
            raw_net_gamma = 0.0
        regime = 2.0 if raw_net_gamma > 1.0 else (0.0 if raw_net_gamma < -1.0 else 1.0)
        if regime == self._gamma_regime_state.get(ticker):
            self._gamma_regime_persistence[ticker] = int(self._gamma_regime_persistence.get(ticker, 0)) + 1
        else:
            self._gamma_regime_state[ticker] = regime
            self._gamma_regime_persistence[ticker] = 1
        return float(np.clip(self._gamma_regime_persistence[ticker] / 12.0, 0.0, 1.0))

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
        snapshot_ts = pd.Timestamp.now(tz="America/New_York")
        if "underlying_timestamp" in df_greeks.columns:
            df_greeks["dt"] = pd.to_datetime(df_greeks["underlying_timestamp"], format="mixed", errors="coerce")
            latest_ts = df_greeks["dt"].max()
            if pd.notna(latest_ts):
                snapshot_ts = latest_ts
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

        df_pq["T"] = calculate_exact_t(snapshot_ts)

        required = ["strike", "right", "implied_vol", "open_interest", "underlying_price", "T"]
        for col in required:
            if col not in df_pq.columns:
                return None
        df_pq = df_pq.dropna(subset=required)

        if df_pq.empty:
            return None
        return get_net_exposures_from_parquet(df_pq)

    def _load_atm_iv_local(self, spot: float, ticker: str = "SPX") -> float:
        """Load ATM IV from either IV or Greeks parquet."""
        options_symbol = OPTIONS_TICKERS.get(ticker, "SPXW")
        iv_path = self.output_dir / f"{options_symbol}_iv_0dte_latest.parquet"
        g_path = self.output_dir / f"{options_symbol}_greeks_0dte_latest.parquet"
        
        # Use greeks as primary source if IV is not being polled
        path = g_path if g_path.exists() else iv_path
        
        if not path.exists():
            return 0.0
            
        try:
            df = pd.read_parquet(path)
            if df.empty:
                return 0.0
                
            iv_col = "implied_vol" if "implied_vol" in df.columns else "implied_volatility"
            if iv_col not in df.columns or "strike" not in df.columns:
                return 0.0
                
            if "underlying_timestamp" in df.columns:
                df["dt"] = pd.to_datetime(df["underlying_timestamp"], format="mixed", errors="coerce")
                df = df[df["dt"] == df["dt"].max()]
            
            if df.empty:
                return 0.0
                
            closest_idx = (df["strike"] - spot).abs().idxmin()
            atm_iv = float(df.loc[closest_idx, iv_col])
            if atm_iv > 1.0:
                atm_iv = atm_iv / 100.0
            return max(atm_iv, 0.01)
        except Exception:
            return 0.0

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
        Loops over SPX, QQQ, and SPY.
        """
        now_et = datetime.now(ET)
        minutes_since_open = max(0, (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30))

        # Shared data (VIX, TLT are the same for all tickers)
        vix_spot = self._load_spot_local("VIX")
        tlt_spot = self._load_spot_local("TLT")
        if tlt_spot > 0:
            last_tlt_minute = self.tlt_price_history[-1][0] if self.tlt_price_history else None
            if last_tlt_minute is None or int(last_tlt_minute) != int(minutes_since_open):
                self.tlt_price_history.append((float(minutes_since_open), float(tlt_spot)))

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
        last_rows_1m = self._ml_features_1m_rows.get(ticker, [])
        if last_rows_1m:
            last_minute = self._float_or_none(last_rows_1m[-1].get("minutes_since_open"))
            if last_minute is not None and int(last_minute) == int(minutes_since_open):
                logger.info(
                    f"  [ML][{ticker}] Duplicate poll inside minute {minutes_since_open} "
                    f"— keeping single 1m snapshot"
                )
                return

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
        if atm_iv > 0:
            atm_iv = atm_iv / 100.0 if atm_iv > 1.0 else atm_iv
            self.iv_history[ticker].append(atm_iv)
        elif len(self.iv_history[ticker]) > 0:
            atm_iv = float(self.iv_history[ticker][-1])

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
        # Match offline/OOS collection: extract a dict first, then add the
        # extra context features that collect_training_data_spx_qqq.py adds
        # outside extract_feature_vector.  Passing FEATURE_COLUMNS here would
        # silently fill those external features with 0.0.
        exp_0dte["signal_persistence_5m"] = self._update_signal_persistence(
            ticker, exp_0dte.get("net_gamma", 0.0)
        )
        features_dict = extract_feature_vector(
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
            day_atr=self.day_atr.get(ticker, 1.0),
            now_et=now_et,
            FEATURE_COLUMNS=None,
            wonham_prob=self.wonham_probs[ticker]
        )
        features_dict.update(self._compute_live_extra_context_features(ticker, spot))

        # ── Build Final Dataframe Row ──
        row = {col: float(features_dict.get(col, 0.0)) for col in FEATURE_COLUMNS}
        row.update({
            "timestamp": pd.Timestamp(now_et).isoformat(),
            "date": now_et.strftime("%Y%m%d"),
            "time": now_et.strftime("%H:%M"),
            "minutes_since_open": float(minutes_since_open),
            "ticker": ticker,
            "spot_price": float(spot),
            "atm_iv_raw": float(atm_iv),
            "pcr_raw": float(self.pcr_history[ticker][-1]) if self.pcr_history[ticker] else 0.5,
            "net_gamma_raw": float(exp_0dte["net_gamma"]),
            "net_vanna_raw": float(exp_0dte["net_vanna"]),
            "net_charm_raw": float(exp_0dte["net_charm"]),
            "net_dgex_raw": float(exp_0dte["net_dgex"]),
            "net_delta_raw": float(exp_0dte.get("net_delta", 0.0)),
            "net_vega_raw": float(exp_0dte.get("net_vega", 0.0)),
            "net_vomma_raw": float(exp_0dte.get("net_vomma", 0.0)),
            "live_feature_context_valid": float(features_dict.get("live_feature_context_valid", 0.0)),
        })
        
        # Update prev_features for the next poll's temporal deltas.
        # Keep the same representation as training: prev_features = features_dict
        # plus raw spot.
        self.prev_features[ticker] = {
            k: float(v) for k, v in features_dict.items()
            if self._float_or_none(v) is not None
        }
        self.prev_features[ticker]["spot"] = float(spot)

        self._ml_features_1m_rows[ticker].append(dict(row))
        self._ml_features_1m_rows[ticker] = self._ml_features_1m_rows[ticker][-500:]
        self._save_parquet(
            pd.DataFrame(self._ml_features_1m_rows[ticker]),
            f"ml_features_1m_{ticker}_latest.parquet",
        )

        sample_bucket = self._model_sample_bucket(minutes_since_open)
        last_sample_bucket = self._last_model_sample_bucket.get(ticker)
        if sample_bucket is None or sample_bucket == last_sample_bucket:
            self._save_intraday_state()
            logger.info(
                f"  [ML][{ticker}] 1m feature snapshot saved; waiting for next "
                f"{MODEL_SAMPLE_MINUTES}m model bucket "
                f"(m={minutes_since_open}, bucket={sample_bucket}, last={last_sample_bucket})"
            )
            return

        self._ml_features_rows[ticker].append(row)
        df_features = pd.DataFrame(self._ml_features_rows[ticker])
        df_features = self.jepa_feature_engine.append_features(df_features)
        self._ml_features_rows[ticker] = df_features.to_dict("records")
        self._last_model_sample_bucket[ticker] = sample_bucket
        self._save_parquet(df_features, f"ml_features_{ticker}_latest.parquet")
        self._save_intraday_state()
        context_valid = float(df_features["xjepa_context_valid"].iloc[-1]) if "xjepa_context_valid" in df_features.columns else 0.0
        logger.info(
            f"  [ML][{ticker}] 5m Base+JEPA feature vector saved "
            f"({len(self._ml_features_rows[ticker])} rows, spot=${spot:.2f}, "
            f"vix5_mean={row.get('vix_5d_mean', 0.0):.3f}, "
            f"vix5_std={row.get('vix_5d_std', 0.0):.3f}, "
            f"atr5_norm={row.get('atr_5d_norm', 0.0):.5f}, "
            f"persist={row.get('signal_persistence_5m', 0.0):.3f}, "
            f"live_ctx={row.get('live_feature_context_valid', 0.0):.0f}, "
            f"xjepa_valid={context_valid:.0f})"
        )

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
        logger.info(f"JEPA live execution config: {JEPA_LIVE_EXECUTION_CONFIG}")

        # Backfill historical spot data on first startup
        if not self._historical_backfilled:
            await self._backfill_historical_spot()

        try:
            while self.running:
                now = datetime.now(ET)

                # Dry run bypasses market hours (for testing)
                if not dry_run:
                    # Poll one minute after the cash close so the bot can see the final
                    # same-day option snapshot for EOD exits. Entry cutoff lives in the bot.
                    market_open = now.replace(
                        hour=MARKET_DATA_START_TIME.hour,
                        minute=MARKET_DATA_START_TIME.minute,
                        second=0,
                    )
                    market_close = now.replace(
                        hour=MARKET_DATA_STOP_TIME.hour,
                        minute=MARKET_DATA_STOP_TIME.minute,
                        second=0,
                    )

                    if now.weekday() >= 5:
                        logger.info("Weekend — sleeping 60s")
                        await asyncio.sleep(60)
                        continue

                    if now < market_open or now > market_close:
                        logger.info(f"Outside market hours ({now.strftime('%H:%M EST')}) — sleeping 60s")
                        await asyncio.sleep(60)
                        continue

                poll_started = time_module.monotonic()
                await self.poll_once()

                if dry_run:
                    logger.info("Dry run — exiting after one poll")
                    break

                elapsed = time_module.monotonic() - poll_started
                await asyncio.sleep(max(0.0, self.poll_interval - elapsed))

        except asyncio.CancelledError:
            logger.info("Feed stopped.")
        except KeyboardInterrupt:
            logger.info("Feed interrupted.")
        finally:
            self.running = False
            await self.client.close()


def main():
    parser = argparse.ArgumentParser(description="Real-time options + spot feed (Parquet)")
    parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS, help="Poll interval in seconds")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Single poll then exit")
    parser.add_argument("--disable-jepa", action="store_true", help="Do not append live xjepa_* features")
    parser.add_argument("--jepa-model-dir", type=str, default=DEFAULT_JEPA_FEATURE_MODEL_DIR, help="XInputJEPA feature model directory")
    parser.add_argument("--jepa-device", type=str, default="auto", help="JEPA device: auto, cpu, cuda")
    args = parser.parse_args()

    print("="*60)
    print("REAL-TIME OPTIONS FEED — SPXW+QQQ+SPY 0DTE+Weekly + Spot (Parquet)")
    print("="*60)
    print(f"  Options:  {', '.join(f'{t}->{s}' for t,s in OPTIONS_TICKERS.items())} (0DTE + Weekly)")
    print(f"  Spot:     {', '.join(SPOT_SYMBOLS)}")
    print(f"  Interval: {args.interval}s")
    print(f"  JEPA:     {'disabled' if args.disable_jepa else args.jepa_model_dir}")
    print(
        "  JEPA live policy: "
        f"{JEPA_LIVE_EXECUTION_CONFIG['policy']} "
        f"(entry <= {JEPA_LIVE_EXECUTION_CONFIG['entry_cutoff_et']} ET, "
        f"trail {JEPA_LIVE_EXECUTION_CONFIG['trail_activation_pct']:.0%}/"
        f"{JEPA_LIVE_EXECUTION_CONFIG['trail_drawdown_pct']:.0%})"
    )
    print(f"  Timezone: EST (America/New_York)")
    print("=" * 60)

    feed = RealtimeOptionsFeed(
        poll_interval=args.interval,
        output_dir=args.output,
        enable_jepa_features=not args.disable_jepa,
        jepa_model_dir=args.jepa_model_dir,
        jepa_device=args.jepa_device,
    )
    asyncio.run(feed.run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
