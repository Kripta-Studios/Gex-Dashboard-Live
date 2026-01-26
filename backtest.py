"""
Algorithmic Backtester using Greek Exposure Data

Este script ejecuta una estrategia de trading algorítmico basada en:
- Exposición de Griegas (Gamma, Vanna, Charm, DGEX, Zomma)
- Niveles de Initial Balance (IB) como soporte/resistencia
- Extensiones de Fibonacci del IB
- Confluencia entre SPX, QQQ, SPY

Uso: python backtest.py

Output: Genera JSONs individuales para cada trade en ./trades/
"""

import os
import json
import glob
import re
import requests
import asyncio
from datetime import datetime, timedelta, time as dt_time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Directorios (ajustar según ambiente - servidor Linux)
GREEK_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"
IB_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"
TRADES_OUTPUT_DIR = "./trades"

# Tickers a procesar
TICKERS = ["SPX", "SPY", "QQQ"]

# Días a analizar (formato YYYYMMDD)
BACKTEST_DAYS = ["20260120", "20260121", "20260122", "20260123"]

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = 1464600897404276841  # Channel for trade alerts
DISCORD_ROLE_PING = "<@&1464601287411634226>"  # Role to ping
DISCORD_ENABLED = True  # Set to False to disable notifications

# Horario de trading (NYC)
MARKET_OPEN = dt_time(9, 30)
MARKET_CLOSE = dt_time(16, 0)
IB_FORMATION_END = dt_time(10, 30)

# Fibonacci extensions
FIB_EXTENSIONS = [0.272, 0.5, 0.618, 1.0, 1.272, 1.618, 2.0, 2.272]
FIB_EXTENSIONS_NEG = [-0.272, -0.5, -0.618, -1.0, -1.272]

# Parámetros de estrategia
MIN_GAMMA_THRESHOLD = 0.1  # Billion $ threshold para señal
MIN_DGEX_THRESHOLD = 0.05
PRICE_PROXIMITY_PCT = 0.002  # 0.2% proximity to level
MIN_VANNA_TOUCH_THRESHOLD = 0.001  # 0.1% - considered "touched" if price within this range

# ============================================================================
# TRADE MANAGEMENT - ANTI-OVERTRADING
# ============================================================================
# These parameters prevent excessive trading and allow trades to develop

MIN_HOLDING_TIME_MINUTES = 25      # Increased from 15 - allow trades to develop
COOLDOWN_AFTER_EXIT_MINUTES = 10   # Wait time after closing before opening new trade
MIN_CONFIDENCE_THRESHOLD = 0.55    # Minimum confidence to enter

# Emergency stop loss - the ONLY exit allowed before MIN_HOLDING_TIME
EMERGENCY_STOP_LOSS_PCT = 0.005    # 0.5% - catastrophic move triggers immediate exit

# Normal profit/loss thresholds (only checked after MIN_HOLDING_TIME)
PROFIT_TARGET_PCT = 0.012          # 1.2% profit target (increased from 0.8%)
STOP_LOSS_PCT = 0.003              # 0.3% stop loss (tightened from 0.4%)

# Resistance/Support exit proximity (let price test the level before exiting)
RESISTANCE_EXIT_PROXIMITY = 0.995  # Exit when within 0.5% of resistance
SUPPORT_EXIT_PROXIMITY = 1.005     # Exit when within 0.5% of support

# ============================================================================
# DOLLAR VALUE PER POINT
# ============================================================================
# For P&L calculation in dollars

POINT_VALUES = {
    "SPX": 10.0,    # $10 per point
    "SPY": 100.0,    # $10 per point  
    "QQQ": 40.0,    # $40 per point
}

def get_dollar_value(ticker: str, points: float) -> float:
    """Calculate dollar value of trade based on ticker."""
    return points * POINT_VALUES.get(ticker, 100.0)


# ============================================================================
# DISCORD NOTIFICATIONS
# ============================================================================

discord_bot = None  # Will be initialized if Discord is enabled

def init_discord_bot():
    """Initialize Discord bot for notifications."""
    global discord_bot
    if not DISCORD_ENABLED or not DISCORD_BOT_TOKEN:
        print("[DISCORD] Disabled or no token found")
        return None
    
    try:
        import discord
        from discord.ext import commands
        
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix="!", intents=intents)
        discord_bot = bot
        return bot
    except Exception as e:
        print(f"[DISCORD] Failed to initialize: {e}")
        return None


def send_discord_trade_open(trade_data: dict, analysis: dict):
    """
    Sends trade OPEN notification to Discord with clear explanation.
    """
    if not DISCORD_ENABLED or not DISCORD_BOT_TOKEN:
        return
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    
    ticker = trade_data.get("ticker", "???")
    direction = trade_data.get("direction", "???")
    entry_price = trade_data.get("entry", {}).get("price", 0)
    entry_time = trade_data.get("entry", {}).get("time", "")
    signals = trade_data.get("signals", {})
    levels = trade_data.get("levels", {})
    
    # Calculate stop loss and target
    stop_loss_price = entry_price * (1 - STOP_LOSS_PCT) if direction == "LONG" else entry_price * (1 + STOP_LOSS_PCT)
    emergency_stop = entry_price * (1 - EMERGENCY_STOP_LOSS_PCT) if direction == "LONG" else entry_price * (1 + EMERGENCY_STOP_LOSS_PCT)
    target_price = entry_price * (1 + PROFIT_TARGET_PCT) if direction == "LONG" else entry_price * (1 - PROFIT_TARGET_PCT)
    
    # Calculate $ risk/reward
    point_value = POINT_VALUES.get(ticker, 10.0)
    stop_distance = abs(entry_price - stop_loss_price)
    target_distance = abs(target_price - entry_price)
    risk_dollars = stop_distance * point_value
    reward_dollars = target_distance * point_value
    
    # Build entry reasoning
    gamma_regime = signals.get("gamma_regime", "neutral")
    vanna_signal = signals.get("vanna_signal", "neutral")
    min_vanna = signals.get("min_vanna_magnet")
    
    reason_parts = []
    if gamma_regime == "long":
        reason_parts.append("Positive Gamma (mean-reverting environment)")
    elif gamma_regime == "short":
        reason_parts.append("Negative Gamma (momentum/trending environment)")
    
    if vanna_signal == "bullish":
        reason_parts.append("Vanna signals dealer buying pressure")
    elif vanna_signal == "bearish":
        reason_parts.append("Vanna signals dealer selling pressure")
    
    if min_vanna:
        reason_parts.append(f"Min Vanna magnet at {min_vanna:.2f}")
    
    reason_text = " • ".join(reason_parts) if reason_parts else "Multiple Greek signals aligned"
    
    color = 0x2ECC71 if direction == "LONG" else 0xE74C3C
    emoji = "📈" if direction == "LONG" else "📉"
    
    embed = {
        "title": f"{emoji} {direction} OPENED - {ticker}",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**Entry Reason:** {reason_text}",
        "color": color,
        "fields": [
            {"name": "💵 Entry Price", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "⏰ Time (NYC)", "value": entry_time, "inline": True},
            {"name": "📊 Point Value", "value": f"${point_value:.0f}/pt", "inline": True},
            {"name": "🎯 Target", "value": f"${target_price:.2f} ({PROFIT_TARGET_PCT*100:.1f}%)", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"${stop_loss_price:.2f} ({STOP_LOSS_PCT*100:.1f}%)", "inline": True},
            {"name": "⚠️ Emergency Stop", "value": f"${emergency_stop:.2f}", "inline": True},
            {"name": "💰 Risk/Reward", "value": f"Risk: ${risk_dollars:.2f} | Reward: ${reward_dollars:.2f}", "inline": False},
        ],
        "footer": {"text": f"Hold time: min {MIN_HOLDING_TIME_MINUTES} min | Greek Exposure Strategy"}
    }
    
    # Add key levels if available
    level_info = []
    if levels.get("ib_high_today"):
        level_info.append(f"Level: {levels['ib_high_today']:.2f}")
    if levels.get("ib_low_today"):
        level_info.append(f"Level: {levels['ib_low_today']:.2f}")
    if levels.get("vp_vpoc"):
        level_info.append(f"VPOC: {levels['vp_vpoc']:.2f}")
    
    if level_info:
        embed["fields"].append({
            "name": "📍 Key Levels",
            "value": " | ".join(level_info),
            "inline": False
        })
    
    payload = {"content": "<@&1464601287411634226> New Trade","embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        if response.status_code >= 400:
            print(f"[DISCORD] Webhook error: {response.status_code}")
    except Exception as e:
        print(f"[DISCORD] Send failed: {e}")


def send_discord_trade_close(trade: dict):
    """
    Sends trade CLOSE notification to Discord with P&L in dollars.
    """
    if not DISCORD_ENABLED or not DISCORD_BOT_TOKEN:
        return
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    
    ticker = trade.get("ticker", "???")
    direction = trade.get("direction", "???")
    entry_price = trade.get("entry", {}).get("price", 0)
    exit_price = trade.get("exit", {}).get("price", 0)
    exit_time = trade.get("exit", {}).get("time", "")
    exit_reason = trade.get("exit", {}).get("reason", "Unknown")
    pnl_points = trade.get("pnl", {}).get("points", 0)
    pnl_pct = trade.get("pnl", {}).get("percent", 0)
    
    # Calculate dollar P&L
    point_value = POINT_VALUES.get(ticker, 10.0)
    pnl_dollars = pnl_points * point_value
    
    # Color and emoji based on P&L
    color = 0x2ECC71 if pnl_points >= 0 else 0xE74C3C
    emoji = "✅" if pnl_points >= 0 else "❌"
    result_text = "PROFIT" if pnl_points >= 0 else "LOSS"
    
    embed = {
        "title": f"{emoji} {direction} CLOSED - {ticker} ({result_text})",
        "description": f"**{DISCORD_ROLE_PING}**\n\n**Exit Reason:** {exit_reason}",
        "color": color,
        "fields": [
            {"name": "� Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "� Exit", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "⏰ Time (NYC)", "value": exit_time, "inline": True},
            {"name": "� P&L Points", "value": f"{pnl_points:+.2f} pts", "inline": True},
            {"name": "📊 P&L %", "value": f"{pnl_pct:+.2f}%", "inline": True},
            {"name": f"� P&L (${point_value:.0f}/pt)", "value": f"**${pnl_dollars:+.2f}**", "inline": True},
        ],
        "footer": {"text": "Greek Exposure Strategy"}
    }
    
    payload = {"content": "<@&1464601287411634226> New Trade","embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        if response.status_code >= 400:
            print(f"[DISCORD] Webhook error: {response.status_code}")
    except Exception as e:
        print(f"[DISCORD] Send failed: {e}")
# ============================================================================

@dataclass
class MinVannaState:
    """Tracks Min Vanna state for a ticker during a session."""
    level: Optional[float] = None
    touched: bool = False
    touch_time: Optional[str] = None
    previous_level: Optional[float] = None
    shift_direction: Optional[str] = None  # "up", "down", or None


# ============================================================================
# VOLUME PROFILE CONFIGURATION
# ============================================================================

# Volume profile zone proximity - zones are ranges, not exact prices
VP_ZONE_WIDTH_PCT = 0.003  # 0.3% zone width around key VP levels
VP_NUM_BUCKETS = 50  # Number of price buckets for volume profile


@dataclass
class VolumeProfileLevels:
    """Volume Profile key levels for a ticker."""
    vpoc: Optional[float] = None  # Point of Control (most volume)
    vah: Optional[float] = None   # Value Area High
    val: Optional[float] = None   # Value Area Low
    lvn_zones: List[dict] = None  # List of {low, high, mid} for Low Volume Nodes
    
    def to_dict(self):
        return {
            "vpoc": self.vpoc,
            "vah": self.vah,
            "val": self.val,
            "lvn_zones": self.lvn_zones or []
        }


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TradeEntry:
    time: str
    price: float
    spot_at_entry: float


@dataclass
class TradeExit:
    time: str
    price: float
    reason: str


@dataclass
class TradePnL:
    points: float
    percent: float


@dataclass
class TradeSignals:
    gamma_exposure: float
    gamma_regime: str
    vanna_signal: str
    charm_signal: str
    dgex_magnet: Optional[float]
    dgex_accelerator: Optional[float]
    zomma_signal: str
    nearest_resistance: Optional[float]
    nearest_support: Optional[float]
    zero_gamma: float
    min_vanna_magnet: Optional[float]  # Min Vanna level acting as price magnet
    min_vanna_touched: bool  # Whether Min Vanna has been touched this session
    min_vanna_direction: str  # "above", "below", or "at" relative to spot


@dataclass
class TradeLevels:
    ib_high_today: Optional[float]
    ib_low_today: Optional[float]
    ib_high_prev_days: List[float]
    ib_low_prev_days: List[float]
    fib_targets_up: List[float]
    fib_targets_down: List[float]
    max_gamma_strike: Optional[float]
    min_gamma_strike: Optional[float]
    max_dgex_strike: Optional[float]
    min_dgex_strike: Optional[float]
    min_vanna_strike: Optional[float]  # Min Vanna price magnet
    # Volume Profile levels
    vp_vpoc: Optional[float]  # Point of Control (most volume)
    vp_vah: Optional[float]   # Value Area High
    vp_val: Optional[float]   # Value Area Low
    vp_lvn_zones: List[dict]  # Low Volume Node zones


@dataclass
class Confluence:
    spx_signal: str
    spy_signal: str
    qqq_signal: str
    aligned: bool


@dataclass
class Trade:
    trade_id: int
    ticker: str
    direction: str  # LONG or SHORT
    entry: TradeEntry
    exit: Optional[TradeExit]
    pnl: Optional[TradePnL]
    signals: TradeSignals
    levels: TradeLevels
    confluence: Confluence


# ============================================================================
# DATA LOADING
# ============================================================================

def parse_greek_filename(filename: str) -> Tuple[str, str, datetime]:
    """
    Parse filename like SPX_0dte_ExposureData_20260120_153045.json
    Returns: (ticker, expiry_type, datetime in NYC)
    """
    pattern = r"(\w+)_(0dte|weekly|all)_ExposureData_(\d{8})_(\d{6})\.json"
    match = re.match(pattern, os.path.basename(filename))
    if not match:
        return None, None, None
    
    ticker = match.group(1)
    expiry = match.group(2)
    date_str = match.group(3)
    time_str = match.group(4)
    
    # El timestamp está en hora de Europa Central, convertir a NYC
    dt_cet = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
    # CET es UTC+1, NYC es UTC-5, diferencia de 6 horas
    dt_nyc = dt_cet - timedelta(hours=6)
    
    return ticker, expiry, dt_nyc


def load_greek_files_for_day(day: str, tickers: List[str]) -> Dict[str, List[dict]]:
    """
    Carga todos los archivos de Greeks para un día específico.
    Retorna dict: {ticker: [list of (datetime, data) sorted by time]}
    """
    result = {t: [] for t in tickers}
    
    pattern = os.path.join(GREEK_DATA_DIR, f"*_0dte_ExposureData_{day}_*.json")
    files = glob.glob(pattern)
    
    for filepath in files:
        ticker, expiry, dt_nyc = parse_greek_filename(filepath)
        
        if ticker not in tickers or expiry != "0dte":
            continue
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Extraer la fecha del día del archivo para verificar que el timestamp NYC
            # corresponde al día que estamos procesando
            file_day = day
            dt_nyc_datestr = dt_nyc.strftime("%Y%m%d")
            
            result[ticker].append({
                "datetime": dt_nyc,
                "filepath": filepath,
                "data": data
            })
        except Exception as e:
            print(f"[WARN] Error loading {filepath}: {e}")
            continue
    
    # Ordenar por datetime
    for ticker in result:
        result[ticker].sort(key=lambda x: x["datetime"])
    
    return result


def load_ib_data(ticker: str, date_str: str) -> Optional[dict]:
    """Carga datos de IB para un ticker y fecha."""
    filepath = os.path.join(IB_DATA_DIR, f"ib_data_{ticker}_{date_str}.json")
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return None


def get_previous_ib_levels(ticker: str, current_day: str, num_days: int = 5) -> Tuple[List[float], List[float]]:
    """
    Obtiene IB high y IB low de los N días anteriores.
    Retorna: (list of ib_highs, list of ib_lows)
    """
    ib_highs = []
    ib_lows = []
    
    current_date = datetime.strptime(current_day, "%Y%m%d")
    
    days_found = 0
    days_back = 1
    
    while days_found < num_days and days_back < 30:
        prev_date = current_date - timedelta(days=days_back)
        # Skip weekends
        if prev_date.weekday() >= 5:
            days_back += 1
            continue
        
        date_str = prev_date.strftime("%Y%m%d")
        ib_data = load_ib_data(ticker, date_str)
        
        if ib_data and "analysis" in ib_data:
            ib_highs.append(ib_data["analysis"].get("ib_high", 0))
            ib_lows.append(ib_data["analysis"].get("ib_low", 0))
            days_found += 1
        
        days_back += 1
    
    return ib_highs, ib_lows


# ============================================================================
# VOLUME PROFILE FUNCTIONS
# ============================================================================

def load_all_ib_volume_data(ticker: str, up_to_day: str) -> List[dict]:
    """
    Carga todos los datos de volumen de IB desde el primer día disponible
    hasta (pero no incluyendo) el día especificado.
    
    Retorna lista de diccionarios con datos de series (OHLCV).
    """
    all_candles = []
    
    # Buscar todos los archivos IB para este ticker
    pattern = os.path.join(IB_DATA_DIR, f"ib_data_{ticker}_*.json")
    files = glob.glob(pattern)
    
    for filepath in sorted(files):
        # Extraer fecha del nombre del archivo
        basename = os.path.basename(filepath)
        # ib_data_SPX_20260120.json
        match = re.search(r"ib_data_\w+_(\d{8})\.json", basename)
        if not match:
            continue
        
        file_date = match.group(1)
        
        # Solo incluir días anteriores al día actual del backtest
        if file_date >= up_to_day:
            continue
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            series = data.get("series", [])
            for candle in series:
                if "volume" in candle:
                    all_candles.append({
                        "date": file_date,
                        "high": candle.get("high", candle.get("price", 0)),
                        "low": candle.get("low", candle.get("price", 0)),
                        "close": candle.get("close", candle.get("price", 0)),
                        "volume": candle.get("volume", 0)
                    })
        except Exception as e:
            continue
    
    return all_candles


def calculate_cumulative_volume_profile(candles: List[dict], num_buckets: int = VP_NUM_BUCKETS) -> VolumeProfileLevels:
    """
    Calcula el perfil de volumen acumulado a partir de una lista de velas OHLCV.
    
    Retorna VolumeProfileLevels con VPOC, VAH, VAL, y LVN zones.
    """
    if not candles:
        return VolumeProfileLevels()
    
    # Obtener rango de precios
    all_highs = [c["high"] for c in candles if c["high"] > 0]
    all_lows = [c["low"] for c in candles if c["low"] > 0]
    
    if not all_highs or not all_lows:
        return VolumeProfileLevels()
    
    price_min = min(all_lows)
    price_max = max(all_highs)
    
    if price_min >= price_max:
        return VolumeProfileLevels()
    
    # Crear buckets de precio
    bucket_size = (price_max - price_min) / num_buckets
    if bucket_size == 0:
        return VolumeProfileLevels()
    
    # Distribuir volumen en buckets
    volume_by_bucket = np.zeros(num_buckets)
    
    for candle in candles:
        candle_low = candle["low"]
        candle_high = candle["high"]
        candle_volume = candle["volume"]
        
        if candle_volume <= 0:
            continue
        
        # Determinar qué buckets cubre esta vela
        start_bucket = max(0, int((candle_low - price_min) / bucket_size))
        end_bucket = min(num_buckets - 1, int((candle_high - price_min) / bucket_size))
        
        # Distribuir volumen proporcionalmente
        num_covered_buckets = max(1, end_bucket - start_bucket + 1)
        vol_per_bucket = candle_volume / num_covered_buckets
        
        for b in range(start_bucket, end_bucket + 1):
            volume_by_bucket[b] += vol_per_bucket
    
    # Calcular precios de cada bucket (punto medio)
    bucket_prices = [price_min + (i + 0.5) * bucket_size for i in range(num_buckets)]
    
    # VPOC: bucket con máximo volumen
    vpoc_idx = np.argmax(volume_by_bucket)
    vpoc = bucket_prices[vpoc_idx]
    
    # Value Area (70% del volumen total)
    total_volume = volume_by_bucket.sum()
    if total_volume == 0:
        return VolumeProfileLevels()
    
    value_area_volume = total_volume * 0.70
    
    # Expandir desde VPOC hasta cubrir 70% del volumen
    va_low_idx = vpoc_idx
    va_high_idx = vpoc_idx
    current_va_volume = volume_by_bucket[vpoc_idx]
    
    while current_va_volume < value_area_volume:
        vol_below = volume_by_bucket[va_low_idx - 1] if va_low_idx > 0 else 0
        vol_above = volume_by_bucket[va_high_idx + 1] if va_high_idx < num_buckets - 1 else 0
        
        if vol_below >= vol_above and va_low_idx > 0:
            va_low_idx -= 1
            current_va_volume += volume_by_bucket[va_low_idx]
        elif va_high_idx < num_buckets - 1:
            va_high_idx += 1
            current_va_volume += volume_by_bucket[va_high_idx]
        else:
            break
    
    val = bucket_prices[va_low_idx] - bucket_size / 2
    vah = bucket_prices[va_high_idx] + bucket_size / 2
    
    # LVN: Low Volume Nodes - valles entre picos HVN
    # Usar detección de mínimos locales en lugar de threshold simple
    
    # Suavizar el perfil para evitar ruido (media móvil de 3)
    smoothed_volume = np.convolve(volume_by_bucket, np.ones(3)/3, mode='same')
    
    # Encontrar HVN (picos locales) y LVN (valles locales)
    hvn_indices = []
    lvn_indices = []
    
    avg_volume = total_volume / num_buckets
    
    for i in range(1, num_buckets - 1):
        prev_vol = smoothed_volume[i - 1]
        curr_vol = smoothed_volume[i]
        next_vol = smoothed_volume[i + 1]
        
        # HVN: máximo local y por encima del promedio
        if curr_vol > prev_vol and curr_vol > next_vol and curr_vol > avg_volume:
            hvn_indices.append(i)
        
        # LVN: mínimo local y por debajo del promedio
        if curr_vol < prev_vol and curr_vol < next_vol and curr_vol < avg_volume:
            lvn_indices.append(i)
    
    # Construir zonas LVN expandiendo desde cada mínimo local
    lvn_zones = []
    lvn_threshold = avg_volume * 0.6  # Umbral más alto para expandir zona
    
    for lvn_idx in lvn_indices:
        # Expandir hacia abajo mientras esté por debajo del umbral
        zone_start_idx = lvn_idx
        while zone_start_idx > 0 and smoothed_volume[zone_start_idx - 1] < lvn_threshold:
            zone_start_idx -= 1
        
        # Expandir hacia arriba mientras esté por debajo del umbral
        zone_end_idx = lvn_idx
        while zone_end_idx < num_buckets - 1 and smoothed_volume[zone_end_idx + 1] < lvn_threshold:
            zone_end_idx += 1
        
        zone_low = bucket_prices[zone_start_idx] - bucket_size / 2
        zone_high = bucket_prices[zone_end_idx] + bucket_size / 2
        
        # Evitar duplicados (zonas que se solapan)
        if lvn_zones and zone_low <= lvn_zones[-1]["high"]:
            # Extender la zona anterior
            lvn_zones[-1]["high"] = max(lvn_zones[-1]["high"], zone_high)
            lvn_zones[-1]["mid"] = (lvn_zones[-1]["low"] + lvn_zones[-1]["high"]) / 2
        else:
            lvn_zones.append({
                "low": zone_low,
                "high": zone_high,
                "mid": (zone_low + zone_high) / 2
            })
    
    return VolumeProfileLevels(
        vpoc=vpoc,
        vah=vah,
        val=val,
        lvn_zones=lvn_zones
    )


def is_price_in_vp_zone(price: float, zone_level: float, zone_width_pct: float = VP_ZONE_WIDTH_PCT) -> bool:
    """
    Verifica si el precio está dentro de una zona de Volume Profile.
    Las zonas son rangos, no precios exactos.
    """
    if zone_level is None or zone_level == 0:
        return False
    zone_half_width = zone_level * zone_width_pct
    return zone_level - zone_half_width <= price <= zone_level + zone_half_width


def is_price_in_lvn_zone(price: float, lvn_zones: List[dict]) -> Optional[dict]:
    """
    Verifica si el precio está en alguna zona LVN.
    Retorna la zona si está, None si no.
    """
    if not lvn_zones:
        return None
    
    for zone in lvn_zones:
        if zone["low"] <= price <= zone["high"]:
            return zone
    return None


# ============================================================================
# GREEK ANALYSIS
# ============================================================================

def get_net_greek_exposure(data: dict, greek_name: str) -> float:
    """
    Calcula la exposición neta de una griega sumando todos los niveles.
    """
    greek_data = data.get(greek_name, {})
    if isinstance(greek_data, dict):
        all_data = greek_data.get("all", [])
        if isinstance(all_data, list) and len(all_data) > 0:
            return sum(all_data)
    return 0.0


def find_max_min_greek_level(data: dict, greek_name: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Encuentra los strikes con máxima y mínima exposición de una griega.
    Retorna: (max_level, max_value, min_level, min_value)
    """
    levels = data.get("levels", [])
    greek_data = data.get(greek_name, {})
    
    if isinstance(greek_data, dict):
        all_data = greek_data.get("all", [])
    else:
        all_data = []
    
    if not levels or not all_data or len(levels) != len(all_data):
        return None, None, None, None
    
    levels = np.array(levels)
    values = np.array(all_data)
    
    max_idx = np.argmax(values)
    min_idx = np.argmin(values)
    
    return levels[max_idx], values[max_idx], levels[min_idx], values[min_idx]


def analyze_gamma(data: dict) -> Tuple[str, float]:
    """
    Analiza el régimen de gamma.
    Retorna: (regime: "long"/"short"/"neutral", net_exposure)
    """
    net_gamma = get_net_greek_exposure(data, "totalgamma")
    
    if net_gamma > MIN_GAMMA_THRESHOLD:
        return "long", net_gamma
    elif net_gamma < -MIN_GAMMA_THRESHOLD:
        return "short", net_gamma
    else:
        return "neutral", net_gamma


def analyze_vanna(data: dict, spot_price: float) -> str:
    """
    Analiza la señal de vanna.
    Vanna positivo + IV bajando = dealers compran = bullish
    Vanna negativo + IV subiendo = dealers compran = bullish
    
    Sin datos de IV, usamos la posición relativa al spot.
    """
    net_vanna = get_net_greek_exposure(data, "totalvanna")
    
    # Simplificación: asumimos que IV tiende a revertir
    # Vanna > 0: si IV baja, dealers compran → bullish
    # Vanna < 0: si IV sube, dealers compran → bullish
    
    if net_vanna > MIN_GAMMA_THRESHOLD:
        return "bullish"  # Expecting IV mean reversion down
    elif net_vanna < -MIN_GAMMA_THRESHOLD:
        return "bearish"  # Expecting IV mean reversion up
    else:
        return "neutral"


def analyze_charm(data: dict) -> str:
    """
    Analiza la señal de charm (time decay effect on delta).
    Charm positivo = delta sube con tiempo = buying pressure
    Charm negativo = delta baja con tiempo = selling pressure
    """
    net_charm = get_net_greek_exposure(data, "totalcharm")
    
    if net_charm > MIN_GAMMA_THRESHOLD:
        return "bullish"
    elif net_charm < -MIN_GAMMA_THRESHOLD:
        return "bearish"
    else:
        return "neutral"


def analyze_dgex(data: dict) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Analiza DGEX para identificar magnets y accelerators.
    Retorna: (signal, magnet_level, accelerator_level)
    """
    max_level, max_val, min_level, min_val = find_max_min_greek_level(data, "totaldgex")
    
    net_dgex = get_net_greek_exposure(data, "totaldgex")
    
    if net_dgex > MIN_DGEX_THRESHOLD:
        signal = "sticky"  # Market gravitates to magnet
    elif net_dgex < -MIN_DGEX_THRESHOLD:
        signal = "volatile"  # Expect breakouts
    else:
        signal = "neutral"
    
    return signal, max_level, min_level


def analyze_zomma(data: dict) -> str:
    """
    Analiza Zomma (gamma sensitivity to IV).
    Zomma > 0: IV sube → gamma más positiva → más estabilidad
    Zomma < 0: IV sube → gamma más negativa → más volatilidad
    """
    net_zomma = get_net_greek_exposure(data, "totalzomma")
    
    if net_zomma > 0:
        return "stabilizing"
    elif net_zomma < 0:
        return "destabilizing"
    else:
        return "neutral"


def analyze_min_vanna(
    data: dict,
    spot_price: float,
    min_vanna_state: MinVannaState,
    current_time: datetime
) -> Tuple[Optional[float], bool, str, MinVannaState]:
    """
    Analiza el Min Vanna como imán de precio.
    
    Reglas:
    - Min Vanna actúa como imán: si no ha sido tocado, alta probabilidad de serlo
    - Una vez tocado, deja de ser útil hasta que cambie
    - Si Min Vanna baja: probable continuación bajista
    - Si Min Vanna sube: probable rebote alcista
    
    Retorna: (min_vanna_level, touched, direction, updated_state)
    """
    # Encontrar Min Vanna actual
    _, _, min_vanna_level, _ = find_max_min_greek_level(data, "totalvanna")
    
    if min_vanna_level is None:
        return None, min_vanna_state.touched, "neutral", min_vanna_state
    
    # Actualizar estado
    new_state = MinVannaState(
        level=min_vanna_level,
        touched=min_vanna_state.touched,
        touch_time=min_vanna_state.touch_time,
        previous_level=min_vanna_state.level,
        shift_direction=None
    )
    
    # Verificar si el precio tocó el Min Vanna
    if not new_state.touched:
        if is_price_near_level(spot_price, min_vanna_level, MIN_VANNA_TOUCH_THRESHOLD):
            new_state.touched = True
            new_state.touch_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Detectar cambio de nivel (shift)
    if min_vanna_state.level is not None and min_vanna_state.level != min_vanna_level:
        if min_vanna_level < min_vanna_state.level:
            new_state.shift_direction = "down"  # Probable continuación bajista
            new_state.touched = False  # Nuevo nivel, reiniciar
        else:
            new_state.shift_direction = "up"  # Probable rebote alcista
            new_state.touched = False
    
    # Determinar dirección relativa al spot
    if spot_price > min_vanna_level * 1.001:
        direction = "below"  # Min Vanna está debajo del precio
    elif spot_price < min_vanna_level * 0.999:
        direction = "above"  # Min Vanna está arriba del precio
    else:
        direction = "at"
    
    return min_vanna_level, new_state.touched, direction, new_state


# ============================================================================
# LEVEL CALCULATIONS
# ============================================================================

def calculate_fib_extensions(ib_high: float, ib_low: float) -> Tuple[List[float], List[float]]:
    """
    Calcula extensiones de Fibonacci del IB.
    Retorna: (extensions_up, extensions_down)
    """
    ib_range = ib_high - ib_low
    
    # Extensions above IB high
    extensions_up = [ib_high + (ib_range * ext) for ext in FIB_EXTENSIONS]
    
    # Extensions below IB low
    extensions_down = [ib_low + (ib_range * ext) for ext in FIB_EXTENSIONS_NEG]
    
    return extensions_up, extensions_down


def find_nearest_levels(price: float, levels: List[float], direction: str = "both") -> Tuple[Optional[float], Optional[float]]:
    """
    Encuentra los niveles más cercanos arriba y abajo del precio.
    Retorna: (nearest_above, nearest_below)
    """
    if not levels:
        return None, None
    
    levels = sorted(levels)
    
    above = [l for l in levels if l > price]
    below = [l for l in levels if l < price]
    
    nearest_above = min(above) if above else None
    nearest_below = max(below) if below else None
    
    return nearest_above, nearest_below


def is_price_near_level(price: float, level: float, threshold_pct: float = PRICE_PROXIMITY_PCT) -> bool:
    """Verifica si el precio está cerca de un nivel."""
    if level == 0:
        return False
    return abs(price - level) / level < threshold_pct


# ============================================================================
# SIGNAL GENERATION
# ============================================================================

def generate_composite_signal(
    gamma_regime: str,
    vanna_signal: str,
    charm_signal: str,
    dgex_signal: str,
    zomma_signal: str,
    spot_price: float,
    resistance: Optional[float],
    support: Optional[float],
    dgex_magnet: Optional[float],
    min_vanna_level: Optional[float] = None,
    min_vanna_touched: bool = False,
    min_vanna_direction: str = "neutral",
    vp_levels: VolumeProfileLevels = None
) -> Tuple[str, float]:
    """
    Genera una señal compuesta basada en todos los inputs.
    
    Min Vanna Logic:
    - Min Vanna actúa como imán si no ha sido tocado
    - Da dirección pero RESPETANDO la tendencia actual
    - Si precio en resistencia + Min Vanna abajo → SHORT hacia Min Vanna
    - Si precio en soporte + Min Vanna arriba → LONG hacia Min Vanna
    
    Volume Profile Logic:
    - VPOC: Point of Control = price magnet (highest volume)
    - VAH: Value Area High = resistance zone
    - VAL: Value Area Low = support zone
    - LVN: Low Volume Nodes = weak S/R, price moves fast through
    
    Retorna: (direction: "LONG"/"SHORT"/"HOLD", confidence: 0-1)
    """
    bullish_score = 0
    bearish_score = 0
    
    # Gamma regime
    if gamma_regime == "long":
        # Long gamma = fade moves, but overall supportive
        bullish_score += 0.5
    elif gamma_regime == "short":
        # Short gamma = momentum, more volatile
        # Neutral on direction, depends on momentum
        pass
    
    # Vanna signal
    if vanna_signal == "bullish":
        bullish_score += 1
    elif vanna_signal == "bearish":
        bearish_score += 1
    
    # Charm signal
    if charm_signal == "bullish":
        bullish_score += 0.5
    elif charm_signal == "bearish":
        bearish_score += 0.5
    
    # DGEX magnet proximity
    if dgex_magnet:
        if dgex_magnet > spot_price:
            bullish_score += 0.5  # Magnet above = pull up
        elif dgex_magnet < spot_price:
            bearish_score += 0.5  # Magnet below = pull down
    
    # ==========================================
    # VOLUME PROFILE S/R LOGIC
    # ==========================================
    if vp_levels:
        # VPOC as price magnet
        if vp_levels.vpoc:
            if is_price_in_vp_zone(spot_price, vp_levels.vpoc):
                # Price at VPOC = consolidation area, less directional bias
                pass  # Neutral, price tends to stick here
            elif vp_levels.vpoc > spot_price * 1.003:
                bullish_score += 0.3  # VPOC above = pull towards it
            elif vp_levels.vpoc < spot_price * 0.997:
                bearish_score += 0.3  # VPOC below = pull towards it
        
        # VAH as resistance
        if vp_levels.vah and is_price_in_vp_zone(spot_price, vp_levels.vah, 0.004):
            bearish_score += 0.5  # At VAH = resistance, expect rejection
        
        # VAL as support
        if vp_levels.val and is_price_in_vp_zone(spot_price, vp_levels.val, 0.004):
            bullish_score += 0.5  # At VAL = support, expect bounce
        
        # LVN zones: if price is in LVN, expect fast movement through
        if vp_levels.lvn_zones:
            lvn_zone = is_price_in_lvn_zone(spot_price, vp_levels.lvn_zones)
            if lvn_zone:
                # In LVN = price will move fast, momentum play
                # Increase confidence in existing direction
                pass  # Will be handled in momentum section
    
    # ==========================================
    # MIN VANNA MAGNET LOGIC
    # ==========================================
    # Min Vanna as untouched magnet gives directional bias
    # BUT only when confirmed by price action (at resistance/support)
    
    min_vanna_score = 0
    if min_vanna_level and not min_vanna_touched:
        # Min Vanna is an active magnet
        
        if min_vanna_direction == "below":
            # Min Vanna below current price = potential downside target
            # Only go short if we're hitting resistance (trend reversal)
            if resistance and is_price_near_level(spot_price, resistance, 0.004):
                bearish_score += 1.5  # Strong short signal: resistance + magnet below
                min_vanna_score = -1.5
            else:
                # Don't fight uptrend just because min vanna is below
                pass
                
        elif min_vanna_direction == "above":
            # Min Vanna above current price = potential upside target
            # Only go long if we're hitting support (trend reversal)
            if support and is_price_near_level(spot_price, support, 0.004):
                bullish_score += 1.5  # Strong long signal: support + magnet above
                min_vanna_score = 1.5
            else:
                # Don't fight downtrend just because min vanna is above
                pass
    
    # Zomma (adjustment to confidence)
    confidence_adj = 0
    if zomma_signal == "stabilizing":
        confidence_adj = 0.1  # More confidence in signals
    elif zomma_signal == "destabilizing":
        confidence_adj = -0.1  # Less confidence
    
    # Level proximity (only if not already scored by min vanna logic)
    if min_vanna_score == 0:
        if support and is_price_near_level(spot_price, support, 0.003):
            bullish_score += 0.5  # Near support = potential bounce
        if resistance and is_price_near_level(spot_price, resistance, 0.003):
            bearish_score += 0.5  # Near resistance = potential rejection
    
    # Calculate final signal
    total_score = bullish_score - bearish_score
    max_possible = 5.0  # Increased for VP impact
    confidence = min(abs(total_score) / max_possible + confidence_adj, 1.0)
    
    if total_score > 0.5:
        return "LONG", confidence
    elif total_score < -0.5:
        return "SHORT", confidence
    else:
        return "HOLD", 0.0


def check_multi_ticker_confluence(signals: Dict[str, str]) -> Confluence:
    """
    Verifica si hay confluencia entre múltiples tickers.
    """
    spx_sig = signals.get("SPX", "neutral")
    spy_sig = signals.get("SPY", "neutral")
    qqq_sig = signals.get("QQQ", "neutral")
    
    # Count bullish/bearish signals
    bullish = sum(1 for s in [spx_sig, spy_sig, qqq_sig] if s == "bullish" or s == "LONG")
    bearish = sum(1 for s in [spx_sig, spy_sig, qqq_sig] if s == "bearish" or s == "SHORT")
    
    aligned = (bullish >= 2) or (bearish >= 2)
    
    return Confluence(
        spx_signal=spx_sig,
        spy_signal=spy_sig,
        qqq_signal=qqq_sig,
        aligned=aligned
    )


# ============================================================================
# TRADE MANAGEMENT
# ============================================================================

def should_exit_trade(
    trade: Trade,
    current_price: float,
    current_time: datetime,
    gamma_regime: str,
    resistance: Optional[float],
    support: Optional[float],
    min_vanna_target: Optional[float] = None
) -> Tuple[bool, str]:
    """
    Determina si se debe cerrar un trade.
    
    ANTI-OVERTRADING LOGIC:
    - Before MIN_HOLDING_TIME: Only exit on EMERGENCY_STOP_LOSS or market close
    - After MIN_HOLDING_TIME: Check all normal exit conditions
    
    Retorna: (should_exit, reason)
    """
    entry_price = trade.entry.price
    direction = trade.direction
    
    # Parse entry time
    entry_time = datetime.strptime(trade.entry.time, "%Y-%m-%d %H:%M:%S")
    time_in_trade = (current_time - entry_time).total_seconds() / 60  # minutes
    
    # Forced exit before market close - ALWAYS applies
    if current_time.time() >= dt_time(15, 55):
        return True, "Market close approaching"
    
    # Calculate P&L
    if direction == "LONG":
        pnl_pct = (current_price - entry_price) / entry_price
    else:  # SHORT
        pnl_pct = (entry_price - current_price) / entry_price
    
    # ========================================
    # PHASE 1: Before minimum holding time
    # Only EMERGENCY stop loss allowed
    # ========================================
    if time_in_trade < MIN_HOLDING_TIME_MINUTES:
        # Emergency stop loss - catastrophic move
        if pnl_pct <= -EMERGENCY_STOP_LOSS_PCT:
            return True, f"EMERGENCY STOP LOSS ({pnl_pct*100:.2f}% in {time_in_trade:.0f}min)"
        
        # Otherwise, let the trade develop
        return False, ""
    
    # ========================================
    # PHASE 2: After minimum holding time
    # Normal exit conditions apply
    # ========================================
    
    if direction == "LONG":
        # Hit resistance (use wider proximity to let price test level)
        if resistance and current_price >= resistance * RESISTANCE_EXIT_PROXIMITY:
            return True, f"Resistance hit at {resistance:.2f}"
        
        # Approaching Min Vanna target above
        if min_vanna_target and min_vanna_target > entry_price:
            if current_price >= min_vanna_target * RESISTANCE_EXIT_PROXIMITY:
                return True, f"Min Vanna target at {min_vanna_target:.2f}"
        
        # Profit target
        if pnl_pct >= PROFIT_TARGET_PCT:
            return True, f"Profit target hit ({pnl_pct*100:.2f}%)"
        
        # Normal stop loss
        if pnl_pct <= -STOP_LOSS_PCT:
            return True, f"Stop loss hit ({pnl_pct*100:.2f}%)"
        
        # Gamma flip with profit
        if gamma_regime == "short" and pnl_pct > 0.002:
            return True, "Gamma flipped to short, taking profit"
    
    elif direction == "SHORT":
        # Approaching Min Vanna target below
        if min_vanna_target and min_vanna_target < entry_price:
            if current_price <= min_vanna_target * SUPPORT_EXIT_PROXIMITY:
                return True, f"Min Vanna target at {min_vanna_target:.2f}"
        
        # Hit support (use wider proximity)
        if support and current_price <= support * SUPPORT_EXIT_PROXIMITY:
            return True, f"Support hit at {support:.2f}"
        
        # Profit target
        if pnl_pct >= PROFIT_TARGET_PCT:
            return True, f"Profit target hit ({pnl_pct*100:.2f}%)"
        
        # Normal stop loss
        if pnl_pct <= -STOP_LOSS_PCT:
            return True, f"Stop loss hit ({pnl_pct*100:.2f}%)"
    
    return False, ""


# ============================================================================
# MAIN BACKTEST LOOP
# ============================================================================

def run_backtest():
    """Ejecuta el backtest completo."""
    
    # Crear directorio de output
    if not os.path.exists(TRADES_OUTPUT_DIR):
        os.makedirs(TRADES_OUTPUT_DIR, exist_ok=True)
    
    all_trades: List[Trade] = []
    trade_counter = 0
    current_trade: Optional[Trade] = None
    last_trade_exit_time: Optional[datetime] = None  # Cooldown tracking
    
    print("=" * 70)
    print("GREEK EXPOSURE ALGORITHMIC BACKTESTER")
    print("=" * 70)
    print(f"Días: {BACKTEST_DAYS}")
    print(f"Tickers: {TICKERS}")
    print(f"Output: {TRADES_OUTPUT_DIR}")
    print("=" * 70)
    
    for day in BACKTEST_DAYS:
        print(f"\n[{day}] Procesando día...")
        
        # Cargar datos de Greeks para este día
        greek_data = load_greek_files_for_day(day, TICKERS)
        
        # Verificar que hay datos
        total_files = sum(len(v) for v in greek_data.values())
        if total_files == 0:
            print(f"  [SKIP] Sin datos de Greeks para {day}")
            continue
        
        print(f"  Archivos cargados: {total_files}")
        
        # Cargar IB de días anteriores
        prev_ib_data = {}
        for ticker in TICKERS:
            highs, lows = get_previous_ib_levels(ticker, day, 5)
            prev_ib_data[ticker] = {"highs": highs, "lows": lows}
        
        # Cargar IB del día actual (solo usar después de 10:30)
        current_ib_data = {}
        for ticker in TICKERS:
            ib = load_ib_data(ticker, day)
            if ib:
                current_ib_data[ticker] = ib.get("analysis", {})
        
        # Initialize Min Vanna state tracking for each ticker (reset each day)
        min_vanna_states = {ticker: MinVannaState() for ticker in TICKERS}
        
        # Reset cooldown for new day
        last_trade_exit_time = None
        
        # Load cumulative volume profile from all previous days
        # This gives us VPOC, VAH, VAL, LVN as historical S/R levels
        cumulative_vp = {}
        for ticker in TICKERS:
            historical_candles = load_all_ib_volume_data(ticker, day)
            if historical_candles:
                cumulative_vp[ticker] = calculate_cumulative_volume_profile(historical_candles)
                if cumulative_vp[ticker].vpoc:
                    print(f"  [{ticker}] VP loaded: VPOC={cumulative_vp[ticker].vpoc:.2f}, VAH={cumulative_vp[ticker].vah:.2f}, VAL={cumulative_vp[ticker].val:.2f}")
            else:
                cumulative_vp[ticker] = VolumeProfileLevels()
        
        # Crear timeline unificado de todos los tickers
        # Agrupar por minuto aproximado
        timeline = defaultdict(dict)
        
        for ticker in TICKERS:
            for entry in greek_data[ticker]:
                # Redondear al minuto
                dt = entry["datetime"]
                minute_key = dt.replace(second=0, microsecond=0)
                timeline[minute_key][ticker] = entry["data"]
        
        # Ordenar timeline
        sorted_times = sorted(timeline.keys())
        
        print(f"  Timeline: {len(sorted_times)} puntos de tiempo")
        
        for current_time in sorted_times:
            # Verificar horario de trading
            if current_time.time() < MARKET_OPEN:
                continue
            if current_time.time() >= MARKET_CLOSE:
                # Cerrar cualquier trade abierto
                if current_trade:
                    spot = timeline[current_time].get(current_trade.ticker, {}).get("spot_price", current_trade.entry.price)
                    current_trade.exit = TradeExit(
                        time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        price=spot,
                        reason="Market close"
                    )
                    pnl_points = spot - current_trade.entry.price if current_trade.direction == "LONG" else current_trade.entry.price - spot
                    pnl_pct = pnl_points / current_trade.entry.price * 100
                    current_trade.pnl = TradePnL(points=pnl_points, percent=pnl_pct)
                    all_trades.append(current_trade)
                    save_trade(current_trade)
                    current_trade = None
                continue
            
            # Determinar si podemos usar IB del día
            can_use_current_ib = current_time.time() >= IB_FORMATION_END
            
            # Procesar cada ticker
            ticker_signals = {}
            ticker_analysis = {}
            
            for ticker in TICKERS:
                if ticker not in timeline[current_time]:
                    continue
                
                data = timeline[current_time][ticker]
                spot_price = data.get("spot_price", 0)
                
                if spot_price == 0:
                    continue
                
                # Analizar Greeks
                gamma_regime, gamma_exp = analyze_gamma(data)
                vanna_signal = analyze_vanna(data, spot_price)
                charm_signal = analyze_charm(data)
                dgex_signal, dgex_magnet, dgex_accel = analyze_dgex(data)
                zomma_signal = analyze_zomma(data)
                
                # Encontrar niveles de Greek walls
                max_gamma_strike, _, min_gamma_strike, _ = find_max_min_greek_level(data, "totalgamma")
                max_dgex_strike, _, min_dgex_strike, _ = find_max_min_greek_level(data, "totaldgex")
                
                # Zero gamma
                zero_gamma = data.get("zerogamma", 0)
                
                # Compilar todos los niveles de S/R
                all_levels = []
                
                # IB de días anteriores
                if ticker in prev_ib_data:
                    all_levels.extend(prev_ib_data[ticker]["highs"])
                    all_levels.extend(prev_ib_data[ticker]["lows"])
                
                # IB del día actual (si después de 10:30)
                ib_high_today = None
                ib_low_today = None
                fib_up = []
                fib_down = []
                
                if can_use_current_ib and ticker in current_ib_data:
                    ib_high_today = current_ib_data[ticker].get("ib_high")
                    ib_low_today = current_ib_data[ticker].get("ib_low")
                    
                    if ib_high_today and ib_low_today:
                        all_levels.extend([ib_high_today, ib_low_today])
                        fib_up, fib_down = calculate_fib_extensions(ib_high_today, ib_low_today)
                        all_levels.extend(fib_up)
                        all_levels.extend(fib_down)
                
                # Greek levels
                if max_gamma_strike:
                    all_levels.append(max_gamma_strike)
                if min_gamma_strike:
                    all_levels.append(min_gamma_strike)
                if dgex_magnet:
                    all_levels.append(dgex_magnet)
                
                # Volume Profile levels as S/R zones
                vp = cumulative_vp.get(ticker, VolumeProfileLevels())
                if vp.vah:
                    all_levels.append(vp.vah)
                if vp.val:
                    all_levels.append(vp.val)
                if vp.vpoc:
                    all_levels.append(vp.vpoc)
                
                # Encontrar S/R más cercanos
                resistance, support = find_nearest_levels(spot_price, all_levels)
                
                # Analyze Min Vanna as price magnet
                min_vanna_level, min_vanna_touched, min_vanna_dir, updated_vanna_state = analyze_min_vanna(
                    data, spot_price, min_vanna_states[ticker], current_time
                )
                min_vanna_states[ticker] = updated_vanna_state
                
                # Add Min Vanna to levels if active
                if min_vanna_level and not min_vanna_touched:
                    all_levels.append(min_vanna_level)
                
                # Generar señal (now with Min Vanna and Volume Profile)
                vp = cumulative_vp.get(ticker, VolumeProfileLevels())
                signal, confidence = generate_composite_signal(
                    gamma_regime, vanna_signal, charm_signal, dgex_signal, zomma_signal,
                    spot_price, resistance, support, dgex_magnet,
                    min_vanna_level, min_vanna_touched, min_vanna_dir,
                    vp
                )
                
                ticker_signals[ticker] = signal
                ticker_analysis[ticker] = {
                    "spot_price": spot_price,
                    "gamma_regime": gamma_regime,
                    "gamma_exp": gamma_exp,
                    "vanna_signal": vanna_signal,
                    "charm_signal": charm_signal,
                    "dgex_signal": dgex_signal,
                    "dgex_magnet": dgex_magnet,
                    "dgex_accel": dgex_accel,
                    "zomma_signal": zomma_signal,
                    "zero_gamma": zero_gamma,
                    "resistance": resistance,
                    "support": support,
                    "signal": signal,
                    "confidence": confidence,
                    "ib_high_today": ib_high_today,
                    "ib_low_today": ib_low_today,
                    "fib_up": fib_up,
                    "fib_down": fib_down,
                    "max_gamma_strike": max_gamma_strike,
                    "min_gamma_strike": min_gamma_strike,
                    "max_dgex_strike": max_dgex_strike,
                    "min_dgex_strike": min_dgex_strike,
                    "min_vanna_level": min_vanna_level,
                    "min_vanna_touched": min_vanna_touched,
                    "min_vanna_direction": min_vanna_dir,
                    "vp_vpoc": vp.vpoc,
                    "vp_vah": vp.vah,
                    "vp_val": vp.val,
                    "vp_lvn_zones": vp.lvn_zones or [],
                    "prev_ib_highs": prev_ib_data.get(ticker, {}).get("highs", []),
                    "prev_ib_lows": prev_ib_data.get(ticker, {}).get("lows", []),
                }
            
            # Verificar confluencia
            confluence = check_multi_ticker_confluence(ticker_signals)
            
            # Si hay trade abierto, verificar exit
            if current_trade:
                ticker = current_trade.ticker
                if ticker in ticker_analysis:
                    analysis = ticker_analysis[ticker]
                    should_exit, exit_reason = should_exit_trade(
                        current_trade,
                        analysis["spot_price"],
                        current_time,
                        analysis["gamma_regime"],
                        analysis["resistance"],
                        analysis["support"],
                        analysis.get("min_vanna_level")  # Min Vanna as profit target
                    )
                    
                    if should_exit:
                        current_trade.exit = TradeExit(
                            time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            price=analysis["spot_price"],
                            reason=exit_reason
                        )
                        
                        if current_trade.direction == "LONG":
                            pnl_points = analysis["spot_price"] - current_trade.entry.price
                        else:
                            pnl_points = current_trade.entry.price - analysis["spot_price"]
                        
                        pnl_pct = pnl_points / current_trade.entry.price * 100
                        current_trade.pnl = TradePnL(points=pnl_points, percent=pnl_pct)
                        
                        all_trades.append(current_trade)
                        save_trade(current_trade)
                        
                        dollar_pnl = get_dollar_value(ticker, pnl_points)
                        print(f"    [{current_time.strftime('%H:%M')}] CLOSED {current_trade.direction} {ticker} @ {analysis['spot_price']:.2f} | P&L: {pnl_points:.2f} pts (${dollar_pnl:+.2f})")
                        
                        # Send Discord notification
                        send_discord_trade_close(asdict(current_trade))
                        
                        last_trade_exit_time = current_time  # Track for cooldown
                        current_trade = None
            
            # Si no hay trade abierto, buscar entrada
            if current_trade is None:
                # Check cooldown after last exit
                if last_trade_exit_time:
                    minutes_since_exit = (current_time - last_trade_exit_time).total_seconds() / 60
                    if minutes_since_exit < COOLDOWN_AFTER_EXIT_MINUTES:
                        continue  # Still in cooldown, skip entry
                
                # Buscar el mejor ticker para entrar
                best_ticker = None
                best_signal = "HOLD"
                best_confidence = 0
                
                for ticker in TICKERS:
                    if ticker not in ticker_analysis:
                        continue
                    
                    analysis = ticker_analysis[ticker]
                    signal = analysis["signal"]
                    confidence = analysis["confidence"]
                    
                    # Solo entrar si hay confluencia y confianza suficiente
                    if signal in ["LONG", "SHORT"] and confidence > MIN_CONFIDENCE_THRESHOLD:
                        if confluence.aligned and confidence > best_confidence:
                            best_ticker = ticker
                            best_signal = signal
                            best_confidence = confidence
                
                # Abrir trade
                if best_ticker and best_signal != "HOLD":
                    analysis = ticker_analysis[best_ticker]
                    trade_counter += 1
                    
                    current_trade = Trade(
                        trade_id=trade_counter,
                        ticker=best_ticker,
                        direction=best_signal,
                        entry=TradeEntry(
                            time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            price=analysis["spot_price"],
                            spot_at_entry=analysis["spot_price"]
                        ),
                        exit=None,
                        pnl=None,
                        signals=TradeSignals(
                            gamma_exposure=analysis["gamma_exp"],
                            gamma_regime=analysis["gamma_regime"],
                            vanna_signal=analysis["vanna_signal"],
                            charm_signal=analysis["charm_signal"],
                            dgex_magnet=analysis["dgex_magnet"],
                            dgex_accelerator=analysis["dgex_accel"],
                            zomma_signal=analysis["zomma_signal"],
                            nearest_resistance=analysis["resistance"],
                            nearest_support=analysis["support"],
                            zero_gamma=analysis["zero_gamma"],
                            min_vanna_magnet=analysis["min_vanna_level"],
                            min_vanna_touched=analysis["min_vanna_touched"],
                            min_vanna_direction=analysis["min_vanna_direction"]
                        ),
                        levels=TradeLevels(
                            ib_high_today=analysis["ib_high_today"],
                            ib_low_today=analysis["ib_low_today"],
                            ib_high_prev_days=analysis["prev_ib_highs"],
                            ib_low_prev_days=analysis["prev_ib_lows"],
                            fib_targets_up=analysis["fib_up"],
                            fib_targets_down=analysis["fib_down"],
                            max_gamma_strike=analysis["max_gamma_strike"],
                            min_gamma_strike=analysis["min_gamma_strike"],
                            max_dgex_strike=analysis["max_dgex_strike"],
                            min_dgex_strike=analysis["min_dgex_strike"],
                            min_vanna_strike=analysis["min_vanna_level"],
                            vp_vpoc=analysis.get("vp_vpoc"),
                            vp_vah=analysis.get("vp_vah"),
                            vp_val=analysis.get("vp_val"),
                            vp_lvn_zones=analysis.get("vp_lvn_zones", [])
                        ),
                        confluence=confluence
                    )
                    
                    print(f"    [{current_time.strftime('%H:%M')}] OPENED {best_signal} {best_ticker} @ {analysis['spot_price']:.2f} (conf: {best_confidence:.2f})")
                    
                    # Send Discord notification
                    send_discord_trade_open(asdict(current_trade), analysis)
    
    # Resumen final
    print("\n" + "=" * 70)
    print("BACKTEST SUMMARY")
    print("=" * 70)
    
    if not all_trades:
        print("No trades executed.")
        return
    
    total_pnl = sum(t.pnl.points for t in all_trades if t.pnl)
    total_pnl_pct = sum(t.pnl.percent for t in all_trades if t.pnl)
    winners = sum(1 for t in all_trades if t.pnl and t.pnl.points > 0)
    losers = sum(1 for t in all_trades if t.pnl and t.pnl.points <= 0)
    
    # Calculate dollar P&L per ticker
    total_dollars = 0.0
    dollars_by_ticker = {}
    for t in all_trades:
        if t.pnl:
            dollars = get_dollar_value(t.ticker, t.pnl.points)
            total_dollars += dollars
            dollars_by_ticker[t.ticker] = dollars_by_ticker.get(t.ticker, 0) + dollars
    
    print(f"Total Trades: {len(all_trades)}")
    print(f"Winners: {winners} | Losers: {losers}")
    print(f"Win Rate: {winners/len(all_trades)*100:.1f}%")
    print("-" * 40)
    print(f"Total P&L: {total_pnl:.2f} points ({total_pnl_pct:.2f}%)")
    print(f"Total P&L: ${total_dollars:,.2f}")
    print("-" * 40)
    print("P&L by Ticker:")
    for ticker, dollars in sorted(dollars_by_ticker.items()):
        count = sum(1 for t in all_trades if t.ticker == ticker)
        print(f"  {ticker}: ${dollars:+,.2f} ({count} trades)")
    print("-" * 40)
    print(f"Trades saved to: {TRADES_OUTPUT_DIR}/")
    print("=" * 70)


def save_trade(trade: Trade):
    """Guarda un trade como JSON."""
    filename = f"trade_{trade.trade_id:03d}_{trade.ticker}_{trade.entry.time.replace(' ', '_').replace(':', '')}.json"
    filepath = os.path.join(TRADES_OUTPUT_DIR, filename)
    
    # Convertir dataclass a dict
    trade_dict = {
        "trade_id": trade.trade_id,
        "ticker": trade.ticker,
        "direction": trade.direction,
        "entry": asdict(trade.entry),
        "exit": asdict(trade.exit) if trade.exit else None,
        "pnl": asdict(trade.pnl) if trade.pnl else None,
        "signals": asdict(trade.signals),
        "levels": asdict(trade.levels),
        "confluence": asdict(trade.confluence)
    }
    
    with open(filepath, 'w') as f:
        json.dump(trade_dict, f, indent=4, default=str)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        run_backtest()
    except KeyboardInterrupt:
        print("\n[STOP] Backtest interrupted by user.")
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
