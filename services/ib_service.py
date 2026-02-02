"""
IB Charts Generator usando DXLinkStreamer para velas minuto a minuto.
Obtiene datos de candles en tiempo real via tastytrade API y
combina con datos de griegas de json_data/.
"""

import sys
import os

# Add project root to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import matplotlib.patheffects as pe
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
import re
import glob
import asyncio
import discord
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# --- IMPORTS TASTYTRADE (DIRECTOS, SIN TTCLI) ---
from tastytrade import Session, DXLinkStreamer
from tastytrade.dxfeed import Candle

# --- CONFIGURACIÓN ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TT_USERNAME = os.getenv("TASTYTRADE_USERNAME")
TT_PASSWORD = os.getenv("TASTYTRADE_PASSWORD")

# Mapeo de Canales
CHANNEL_MAPPING = {
    "SPX": 1462142087305892064,
    "SPY": 1462142165915406495,
    "QQQ": 1462142196332495092,
    "IWM": 1462142236505538631,
    "VIX": 1462142259796512902,
    "AAPL": 1462142296198742157,
    "AMZN": 1462142319393243167,
    "MSFT": 1462142359742714038,
    "GOOGL": 1462142389081870404,
    "META": 1462142431276306656,
    "NVDA": 1462142452558336052,
    "AMD": 1462142477514445101,
    "TSLA": 1462142516714410076,
    "NFLX": 1462142543004176485,
    "PLTR": 1462142565775052811,
    "HOOD": 1462142586457297009,
    "MSTR": 1462142605419872459,
    "HIMS": 1462142622792417321,
    "UNH": 1462142640236662957,
    "GLD": 1462142666761568310,
    "SLV": 1462142697254027388,
    # Futures
    "/ES": 1466750485724921990,
    "/NQ": 1466750528037064880,
}

DATA_FOLDER_PATH = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"
OUTPUT_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_charts"
IB_BACKTEST_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"  # EOD backup with volume_profile

# Zonas Horarias
try:
    NY_TZ = ZoneInfo("America/New_York")
    SERVER_TZ = ZoneInfo("Europe/Madrid")
except:
    NY_TZ = None
    SERVER_TZ = None

# Tickers a seguir
TICKERS_TO_TRACK = [
    "SPX",
    "SPY",
    "QQQ",
    "IWM",
    "VIX",
    "AAPL",
    "NVDA",
    "TSLA",
    "AMD",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
]

# Futuros a seguir (procesados con candlestick aesthetic)
FUTURES_TO_TRACK = ["/ES", "/NQ"]

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

if not os.path.exists(IB_BACKTEST_DIR):
    os.makedirs(IB_BACKTEST_DIR)

# Track which dates have been saved to ib_backtest today (to avoid duplicates)
EOD_SAVED_DATES = set()

SENT_CACHE = {}

# --- SESIÓN TASTYTRADE ---
# --- SESIÓN TASTYTRADE ---
_session = None

def get_tastytrade_session(force_refresh=False):
    """
    Crea o reutiliza una sesión de tastytrade.
    Si force_refresh=True, destruye la sesión anterior y crea una nueva.
    """
    global _session
    
    if force_refresh and _session is not None:
        try:
            print("[TT] Destruyendo sesión caducada...")
            _session.destroy()
        except Exception:
            pass # Ignorar errores al cerrar sesión vieja
        _session = None

    if _session is None:
        if not TT_USERNAME or not TT_PASSWORD:
            raise ValueError("Falta TT_USERNAME o TT_PASSWORD en .env")
        print("[TT] Creando nueva sesión...")
        _session = Session(TT_USERNAME, TT_PASSWORD)
        print("[TT] Sesión creada exitosamente")
        
    return _session

# --- 1. OBTENER CANDLES VÍA DXLINKSTREAMER ---
async def get_candle_data_for_today(ticker: str) -> pd.DataFrame:
    """
    Descarga datos de velas de 1 minuto para el día de hoy usando DXLinkStreamer.
    Incluye lógica de reintento automático si el token ha caducado.
    """
    # Calcular el inicio del día de trading (9:30 AM NY)
    now = datetime.now(NY_TZ) if NY_TZ else datetime.now()
    today = now.date()

    # Si estamos antes de las 9:30, podría ser día anterior
    if now.time() < dt_time(3, 0):
        today = today - timedelta(days=1)

    start_time = datetime.combine(today, dt_time(3, 0))
    if NY_TZ:
        start_time = start_time.replace(tzinfo=NY_TZ)

    ts = round(start_time.timestamp() * 1000)

    # --- LÓGICA DE REINTENTO (MAX 3 INTENTOS) ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # En el primer intento usamos la sesión actual. 
            # En reintentos (attempt > 0), forzamos refresh.
            force_refresh = (attempt > 0)
            session = get_tastytrade_session(force_refresh=force_refresh)

            print(f"[CANDLE] Descargando velas 1m para {ticker} (Intento {attempt+1})")
            
            candles_list = []
            
            # Usamos el streamer dentro del bloque try para capturar AuthException
            async with DXLinkStreamer(session) as streamer:
                await streamer.subscribe_candle([ticker], "1m", start_time)

                # Timeout: esperar máximo 60 segundos
                try:
                    async with asyncio.timeout(60):
                        async for candle in streamer.listen(Candle):
                            if candle.close:
                                # Convertir timestamp
                                if NY_TZ:
                                    dt_candle = datetime.fromtimestamp(candle.time / 1000, tz=NY_TZ)
                                else:
                                    dt_candle = datetime.fromtimestamp(candle.time / 1000)

                                candles_list.append({
                                    "datetime": dt_candle,
                                    "open": float(candle.open) if candle.open else 0,
                                    "high": float(candle.high) if candle.high else 0,
                                    "low": float(candle.low) if candle.low else 0,
                                    "close": float(candle.close) if candle.close else 0,
                                    "volume": float(candle.volume) if candle.volume else 0
                                })

                            # Condición de parada: llegamos al inicio del día
                            if candle.time == ts:
                                break
                except asyncio.TimeoutError:
                    print(f"[CANDLE] {ticker}: Timeout 60s, obtenidas {len(candles_list)} velas")

            # --- PROCESAMIENTO DE DATOS (Si llegamos aquí, la descarga fue exitosa) ---
            if not candles_list:
                return pd.DataFrame()

            df = pd.DataFrame(candles_list)
            df = df.sort_values("datetime").reset_index(drop=True)
            # Filtrar solo horas de trading
            df = df[df["datetime"].apply(lambda x: dt_time(3, 0) <= x.time() <= dt_time(17, 0))]
            
            print(f"[CANDLE] {ticker}: {len(df)} velas descargadas correctamente.")
            return df

        except Exception as e:
            error_msg = str(e).lower()
            # Detectar errores de autenticación o token expirado
            if "expired" in error_msg or "auth" in error_msg or "token" in error_msg or "unauthorized" in error_msg:
                print(f"[AUTH ERROR] Token expirado en intento {attempt+1}. Refrescando sesión...")
                # El loop continuará y 'force_refresh' será True en la siguiente vuelta
                continue
            else:
                # Si es otro error (ej. error de red grave), imprimimos y salimos para no buclear infinito
                print(f"[ERROR CANDLE FATAL] {ticker}: {e}")
                import traceback
                traceback.print_exc()
                return pd.DataFrame()

    print(f"[ERROR CANDLE] {ticker}: Fallaron todos los intentos de descarga.")
    return pd.DataFrame()


# --- 1b. FUNCIONES PARA FUTUROS ---
def get_active_future_symbol(root_symbol: str) -> tuple:
    """
    Obtiene el símbolo del contrato de futuros activo.
    Returns: (full_symbol, streamer_symbol)
    """
    month_codes = {
        1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M',
        7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'
    }
    quarterly_months = [3, 6, 9, 12]
    
    current_date = datetime.now(NY_TZ) if NY_TZ else datetime.now()
    year = current_date.year
    
    for m in quarterly_months:
        first_day = datetime(year, m, 1)
        weekday = first_day.weekday()
        delta = (4 - weekday + 7) % 7
        third_friday = 1 + delta + 14
        expiry = datetime(year, m, third_friday)
        if NY_TZ:
            expiry = expiry.replace(tzinfo=NY_TZ)
        
        if current_date < expiry:
            month_code = month_codes[m]
            break
    else:
        year += 1
        month_code = 'H'
    
    year_2digit = str(year)[-2:]
    year_1digit = str(year)[-1]
    
    full_symbol = f"{root_symbol}{month_code}{year_1digit}"
    base_symbol = root_symbol.lstrip('/')
    streamer_symbol = f"/{base_symbol}{month_code}{year_2digit}:XCME"
    
    return full_symbol, streamer_symbol


async def get_futures_candle_data_for_today(ticker: str) -> pd.DataFrame:
    """
    Descarga datos de velas de 1 minuto para futuros.
    """
    full_symbol, streamer_symbol = get_active_future_symbol(ticker)
    
    now = datetime.now(NY_TZ) if NY_TZ else datetime.now()
    today = now.date()

    if now.time() < dt_time(3, 0):
        today = today - timedelta(days=1)

    start_time = datetime.combine(today, dt_time(3, 0))
    if NY_TZ:
        start_time = start_time.replace(tzinfo=NY_TZ)

    ts = round(start_time.timestamp() * 1000)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            force_refresh = (attempt > 0)
            session = get_tastytrade_session(force_refresh=force_refresh)

            print(f"[CANDLE FUTURES] Descargando {streamer_symbol} (Intento {attempt+1})")
            
            candles_list = []
            
            async with DXLinkStreamer(session) as streamer:
                await streamer.subscribe_candle([streamer_symbol], "1m", start_time)

                try:
                    async with asyncio.timeout(60):
                        async for candle in streamer.listen(Candle):
                            if candle.close:
                                if NY_TZ:
                                    dt_candle = datetime.fromtimestamp(candle.time / 1000, tz=NY_TZ)
                                else:
                                    dt_candle = datetime.fromtimestamp(candle.time / 1000)

                                candles_list.append({
                                    "datetime": dt_candle,
                                    "open": float(candle.open) if candle.open else 0,
                                    "high": float(candle.high) if candle.high else 0,
                                    "low": float(candle.low) if candle.low else 0,
                                    "close": float(candle.close) if candle.close else 0,
                                    "volume": float(candle.volume) if candle.volume else 0
                                })

                            if candle.time <= ts:
                                break
                except asyncio.TimeoutError:
                    print(f"[CANDLE FUTURES] {streamer_symbol}: Timeout, obtenidas {len(candles_list)} velas")

            if not candles_list:
                return pd.DataFrame()

            df = pd.DataFrame(candles_list)
            df = df.sort_values("datetime").reset_index(drop=True)
            df = df[df["datetime"].apply(lambda x: dt_time(3, 0) <= x.time() <= dt_time(17, 0))]
            
            print(f"[CANDLE FUTURES] {streamer_symbol}: {len(df)} velas RTH")
            return df

        except Exception as e:
            error_msg = str(e).lower()
            if "expired" in error_msg or "auth" in error_msg:
                continue
            else:
                print(f"[ERROR CANDLE FUTURES] {streamer_symbol}: {e}")
                return pd.DataFrame()

    return pd.DataFrame()


def get_spx_greeks(date_str: str) -> dict:
    """Obtiene los niveles de griegas de SPX para /ES."""
    pattern = os.path.join(DATA_FOLDER_PATH, f"*SPX*0dte*ExposureData*{date_str}*.json")
    files = sorted(glob.glob(pattern))
    
    if not files:
        return {}
    
    try:
        with open(files[-1], "r") as f:
            content = json.load(f)

        raw_df = content.get("option_data", {})
        if not raw_df or "data" not in raw_df:
            return {}

        df = pd.DataFrame(data=raw_df["data"], columns=raw_df["columns"])
        for col in ["strike_price", "total_gamma", "total_vanna", "total_dgex"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        greeks = df.groupby("strike_price")[["total_gamma", "total_vanna", "total_dgex"]].sum()

        if greeks.empty:
            return {}

        return {
            "max_gamma": float(greeks["total_gamma"].idxmax()),
            "min_gamma": float(greeks["total_gamma"].idxmin()),
            "min_vanna": float(greeks["total_vanna"].idxmin()),
            "max_dgex": float(greeks["total_dgex"].idxmax()),
            "min_dgex": float(greeks["total_dgex"].idxmin()),
        }
    except Exception as e:
        print(f"[ERROR SPX GREEKS] {e}")
        return {}


async def get_qqq_greeks_converted_to_ndx(date_str: str) -> dict:
    """
    Obtiene niveles de griegas de QQQ y los convierte a NDX para /NQ.
    Obtiene el precio NDX real de Tastytrade en vez de estimarlo.
    """
    from modules.tasty_handler import tasty_data
    
    pattern = os.path.join(DATA_FOLDER_PATH, f"*QQQ*0dte*ExposureData*{date_str}*.json")
    files = sorted(glob.glob(pattern))
    
    if not files:
        return {}
    
    try:
        with open(files[-1], "r") as f:
            qqq_content = json.load(f)
        
        qqq_spot = float(qqq_content.get("spot_price", 0))
        if qqq_spot == 0:
            return {}
        
        raw_df = qqq_content.get("option_data", {})
        if not raw_df or "data" not in raw_df:
            return {}

        df = pd.DataFrame(data=raw_df["data"], columns=raw_df["columns"])
        for col in ["strike_price", "total_gamma", "total_vanna", "total_dgex"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        greeks = df.groupby("strike_price")[["total_gamma", "total_vanna", "total_dgex"]].sum()

        if greeks.empty:
            return {}

        qqq_greeks = {
            "max_gamma": float(greeks["total_gamma"].idxmax()),
            "min_gamma": float(greeks["total_gamma"].idxmin()),
            "min_vanna": float(greeks["total_vanna"].idxmin()),
            "max_dgex": float(greeks["total_dgex"].idxmax()),
            "min_dgex": float(greeks["total_dgex"].idxmin()),
        }
        
        # Obtener NDX spot real de Tastytrade
        session = get_tastytrade_session()
        _, quotes = await tasty_data(session, equities_ticker=["NDX"])
        
        ndx_spot = 0
        for q in quotes:
            if "NDX" in q.get("symbol", ""):
                ndx_spot = float(q.get("last", 0))
                break
        
        # Fallback si no se obtiene NDX
        if ndx_spot == 0:
            print("[WARN] No se pudo obtener NDX spot, usando ratio ~40.8")
            ndx_spot = qqq_spot * 40.8
        
        # Convertir cada nivel de QQQ a NDX por porcentaje
        ndx_greeks = {}
        for key, qqq_level in qqq_greeks.items():
            pct_from_spot = (qqq_level - qqq_spot) / qqq_spot
            ndx_level = ndx_spot * (1 + pct_from_spot)
            ndx_greeks[key] = ndx_level
        
        # Guardar precio spot de NDX para uso en JSON
        ndx_greeks["_underlying_spot"] = ndx_spot
        
        return ndx_greeks
    except Exception as e:
        print(f"[ERROR QQQ->NDX GREEKS] {e}")
        return {}


async def get_greeks_for_future(future_ticker: str, date_str: str) -> dict:
    """Obtiene griegas para futuros: /ES usa SPX, /NQ usa QQQ→NDX."""
    if future_ticker == "/ES":
        return get_spx_greeks(date_str)
    elif future_ticker == "/NQ":
        return await get_qqq_greeks_converted_to_ndx(date_str)
    return {}


def generate_futures_ib_chart(ticker: str, df_candles: pd.DataFrame, greeks: dict, date_str: str):
    """
    Genera gráfico IB de futuros con estilo candlestick (estética plot_futures.py).
    """
    from matplotlib.patches import Rectangle
    
    if df_candles.empty:
        return None

    df = df_candles.copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    
    current_price = df.iloc[-1]["close"]
    day_high = df["high"].max()
    day_low = df["low"].min()

    # Cálculo IB
    ib_start = dt_time(9, 30)
    ib_end = dt_time(10, 30)
    ib_data = df[df["datetime"].apply(lambda x: ib_start <= x.time() <= ib_end)]
    if ib_data.empty:
        ib_data = df

    ib_high = float(ib_data["high"].max())
    ib_low = float(ib_data["low"].min())
    ib_range = ib_high - ib_low

    # === JSON GENERATION (WEB DASHBOARD) ===
    ticker_clean = ticker.replace("/", "")
    try:
        series_data = []
        for index, row in df.iterrows():
            candle_time = row["datetime"]
            series_data.append({
                "time": candle_time.strftime("%H:%M"),
                "full_date": candle_time.strftime("%Y-%m-%d %H:%M:%S"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "price": float(row["close"]),
                "volume": float(row.get("volume", 0)),
            })

        # Extract underlying spot if available (for NQ/NDX ratio)
        underlying_spot = greeks.pop("_underlying_spot", None)
        
        json_data = {
            "meta": {
                "ticker": ticker,
                "date": date_str,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "analysis": {
                "ib_high": float(ib_high),
                "ib_low": float(ib_low),
                "ib_range": float(ib_range),
                "current_price": float(current_price),
                "underlying_spot": float(underlying_spot) if underlying_spot else None
            },
            "levels": {k: float(v) for k, v in greeks.items() if not pd.isna(v)},
            "series": series_data,
        }

        json_filename = os.path.join(OUTPUT_DIR, f"ib_data_{ticker_clean}_{date_str}.json")
        with open(json_filename, "w") as f:
            json.dump(json_data, f, indent=4)
            
        print(f"[FUTURES JSON] Saved: {json_filename}")

    except Exception as e:
        print(f"[ERROR FUTURES JSON] {ticker}: {e}")

    # === GRÁFICO CON CANDLESTICKS ===
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

    plt.rcParams["font.family"] = "monospace"
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#0a0a0a")
    ax.set_facecolor("#0a0a0a")

    ax.grid(True, which="major", color="#222222", linestyle="-", linewidth=0.3)
    ax.set_axisbelow(True)

    plt.title(
        f"{ticker} Futures | IB & LEVELS | {formatted_date}",
        color="#ffffff",
        fontsize=16,
        fontweight="bold",
        pad=20,
        loc="left",
    )

    txt_outline = [pe.withStroke(linewidth=2, foreground="black")]
    trans = ax.get_yaxis_transform()

    # CANDLESTICKS
    candle_width = 0.0004
    times = df["datetime"].tolist()
    opens = df["open"].tolist()
    highs = df["high"].tolist()
    lows = df["low"].tolist()
    closes = df["close"].tolist()

    for i in range(len(times)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        t = mdates.date2num(times[i])
        
        if c >= o:
            body_color, wick_color = "#00d26a", "#00d26a"
        else:
            body_color, wick_color = "#ff4757", "#ff4757"
        
        ax.plot([t, t], [l, h], color=wick_color, linewidth=0.8)
        body_bottom = min(o, c)
        body_height = abs(c - o) if abs(c - o) > 0 else 0.01
        
        rect = Rectangle(
            (t - candle_width / 2, body_bottom),
            candle_width, body_height,
            facecolor=body_color, edgecolor=wick_color,
            linewidth=0.5, alpha=0.9
        )
        ax.add_patch(rect)

    # IB ZONES
    ax.axhspan(ib_low, ib_high, color="#ffffff", alpha=0.05, lw=0)
    ax.axhline(ib_high, color="#ffffff", linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(ib_low, color="#ffffff", linestyle="--", linewidth=1, alpha=0.6)
    
    ax.text(0.01, ib_high, f"IB HIGH: {ib_high:.2f}", color="#ffffff", fontsize=9,
            transform=trans, va="bottom", ha="left", path_effects=txt_outline, alpha=0.9)
    ax.text(0.01, ib_low, f"IB LOW: {ib_low:.2f}", color="#ffffff", fontsize=9,
            transform=trans, va="top", ha="left", path_effects=txt_outline, alpha=0.9)

    # FIBONACCI
    colors_fib = ["#ffc107", "#ff9800", "#ff5722"]
    
    if current_price > ib_high:
        for i, ext in enumerate([1.272, 1.618, 2.0]):
            fib_level = ib_low + (ib_range * ext)
            if fib_level <= day_high * 1.02:
                ax.axhline(fib_level, color=colors_fib[i], linestyle=":", linewidth=1, alpha=0.7)
                ax.text(0.01, fib_level, f"FIB {ext}: {fib_level:.2f}", color=colors_fib[i],
                        fontsize=8, transform=trans, va="bottom", ha="left", path_effects=txt_outline)
    elif current_price < ib_low:
        for i, ext in enumerate([-0.272, -0.618, -1.0]):
            fib_level = ib_low + (ib_range * ext)
            if fib_level >= day_low * 0.98:
                ax.axhline(fib_level, color=colors_fib[i], linestyle=":", linewidth=1, alpha=0.7)
                ax.text(0.01, fib_level, f"FIB {ext}: {fib_level:.2f}", color=colors_fib[i],
                        fontsize=8, transform=trans, va="top", ha="left", path_effects=txt_outline)

    # GREEK LEVELS
    greek_colors = {
        "max_gamma": "#00FF00", "min_gamma": "#FF0000",
        "min_vanna": "#FF00FF", "max_dgex": "#00FFFF", "min_dgex": "#FFA500",
    }

    for key, val in greeks.items():
        if pd.isna(val):
            continue
        c = greek_colors.get(key, "#888888")
        label_txt = key.replace("_", " ").upper()
        ax.axhline(val, color=c, linestyle="-.", linewidth=1, alpha=0.6)
        ax.text(0.99, val, f"{label_txt}: {val:.0f}", color=c, fontsize=8, fontweight="bold",
                transform=trans, va="bottom", ha="right", path_effects=txt_outline)

    # CURRENT PRICE
    #ax.axhline(current_price, color="#00bfff", linestyle="-", linewidth=1.5, alpha=0.8)
    #ax.text(0.99, current_price, f"LAST: {current_price:.2f}", color="#00bfff", fontsize=10, fontweight="bold",
    #transform=trans, va="center", ha="right", path_effects=txt_outline,
    #bbox=dict(boxstyle="round,pad=0.3", facecolor="#0a0a0a", edgecolor="#00bfff", alpha=0.8))

    # AXIS CONFIG
    if times:
        base_date = times[0].date()
        start_plot = datetime.combine(base_date, dt_time(9, 25))
        end_plot = datetime.combine(base_date, dt_time(16, 5))
        if NY_TZ:
            start_plot = start_plot.replace(tzinfo=NY_TZ)
            end_plot = end_plot.replace(tzinfo=NY_TZ)
        ax.set_xlim(start_plot, end_plot)

    if NY_TZ:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=NY_TZ))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))

    # Extend Y axis to include greek levels if they are outside candle price range
    y_min = day_low
    y_max = day_high
    for key, val in greeks.items():
        if not pd.isna(val):
            y_min = min(y_min, val)
            y_max = max(y_max, val)
    
    price_range = y_max - y_min
    y_padding = price_range * 0.05
    ax.set_ylim(y_min - y_padding, y_max + y_padding)

    ax.tick_params(axis="x", colors="#888888", rotation=0, labelsize=9)
    ax.tick_params(axis="y", colors="#888888", labelsize=9)
    ax.spines["bottom"].set_color("#333333")
    ax.spines["left"].set_color("#333333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    output_filename = os.path.join(OUTPUT_DIR, f"futures_ib_{ticker_clean}_{date_str}.png")
    plt.savefig(output_filename, dpi=150, facecolor="#0a0a0a", bbox_inches="tight")
    plt.close()

    return output_filename


# --- 2. OBTENER ARCHIVOS DE GRIEGAS ---
def get_all_greeks_files(ticker: str, expiry: str, date_str: str) -> list:
    """
    Obtiene todos los archivos de griegas para un ticker y fecha,
    ordenados por timestamp.
    Retorna lista de tuplas: (datetime, filepath)
    """
    pattern = os.path.join(
        DATA_FOLDER_PATH, f"*{ticker}*{expiry}*ExposureData*{date_str}*.json"
    )
    files = glob.glob(pattern)
    
    file_times = []
    for filepath in files:
        try:
            if os.path.getsize(filepath) == 0:
                continue
                
            filename = os.path.basename(filepath)
            match = re.search(r"_(\d{8})_(\d{6})\.json", filename)
            if not match:
                continue
            
            dt_str = f"{match.group(1)} {match.group(2)}"
            dt_file = datetime.strptime(dt_str, "%Y%m%d %H%M%S")
            
            if SERVER_TZ and NY_TZ:
                dt_file = dt_file.replace(tzinfo=SERVER_TZ).astimezone(NY_TZ)
            
            file_times.append((dt_file, filepath))
        except:
            continue
    
    file_times.sort(key=lambda x: x[0])
    return file_times


def get_closest_greeks_file(target_time: datetime, greeks_files: list) -> str:
    """Encuentra el archivo de griegas más cercano en tiempo."""
    if not greeks_files:
        return None
    closest = min(greeks_files, key=lambda x: abs((x[0] - target_time).total_seconds()))
    return closest[1]


def extract_greeks_from_file(filepath: str) -> dict:
    """Extrae niveles de griegas de un archivo JSON."""
    try:
        with open(filepath, "r") as f:
            content = json.load(f)

        raw_df = content.get("option_data", {})
        if not raw_df or "data" not in raw_df:
            return {}

        df = pd.DataFrame(data=raw_df["data"], columns=raw_df["columns"])
        for col in ["strike_price", "total_gamma", "total_vanna", "total_dgex"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        greeks = df.groupby("strike_price")[
            ["total_gamma", "total_vanna", "total_dgex"]
        ].sum()

        if greeks.empty:
            return {}

        return {
            "max_gamma": float(greeks["total_gamma"].idxmax()),
            "min_gamma": float(greeks["total_gamma"].idxmin()),
            "min_vanna": float(greeks["total_vanna"].idxmin()),
            "max_dgex": float(greeks["total_dgex"].idxmax()),
            "min_dgex": float(greeks["total_dgex"].idxmin()),
        }
    except Exception as e:
        print(f"[ERROR GREEKS] {filepath}: {e}")
        return {}


# --- 2.5 VOLUME PROFILE CALCULATION (for ib_backtest) ---
def calculate_volume_profile(df: pd.DataFrame, num_buckets: int = 50) -> dict:
    """
    Calculates volume profile for the given candlestick data.
    Returns: vpoc, vah, val, lvn_zones, total_volume, profile
    """
    if df.empty or "volume" not in df.columns:
        return {}
    
    price_min = df["low"].min()
    price_max = df["high"].max()
    
    if price_min == price_max:
        return {}
    
    bucket_size = (price_max - price_min) / num_buckets
    if bucket_size == 0:
        return {}
    
    volume_by_bucket = np.zeros(num_buckets)
    
    for _, row in df.iterrows():
        candle_low = row["low"]
        candle_high = row["high"]
        candle_volume = row["volume"]
        
        if candle_volume <= 0:
            continue
        
        start_bucket = max(0, int((candle_low - price_min) / bucket_size))
        end_bucket = min(num_buckets - 1, int((candle_high - price_min) / bucket_size))
        
        num_covered_buckets = end_bucket - start_bucket + 1
        vol_per_bucket = candle_volume / num_covered_buckets
        
        for b in range(start_bucket, end_bucket + 1):
            volume_by_bucket[b] += vol_per_bucket
    
    bucket_prices = [price_min + (i + 0.5) * bucket_size for i in range(num_buckets)]
    
    vpoc_idx = np.argmax(volume_by_bucket)
    vpoc = bucket_prices[vpoc_idx]
    
    total_volume = volume_by_bucket.sum()
    if total_volume == 0:
        return {}
    
    value_area_volume = total_volume * 0.70
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
    
    # LVN detection
    smoothed_volume = np.convolve(volume_by_bucket, np.ones(3)/3, mode='same')
    lvn_zones = []
    avg_volume = total_volume / num_buckets
    lvn_threshold = avg_volume * 0.6
    
    for i in range(1, num_buckets - 1):
        if smoothed_volume[i] < smoothed_volume[i-1] and smoothed_volume[i] < smoothed_volume[i+1] and smoothed_volume[i] < avg_volume:
            zone_low = bucket_prices[i] - bucket_size / 2
            zone_high = bucket_prices[i] + bucket_size / 2
            lvn_zones.append({"low": zone_low, "high": zone_high, "mid": bucket_prices[i]})
    
    profile = [{"price": bucket_prices[i], "volume": float(volume_by_bucket[i])} for i in range(num_buckets)]
    
    return {
        "vpoc": float(vpoc),
        "vah": float(vah),
        "val": float(val),
        "lvn_zones": lvn_zones,
        "total_volume": float(total_volume),
        "bucket_size": float(bucket_size),
        "profile": profile
    }


def save_to_ib_backtest(ticker: str, df_candles: pd.DataFrame, ib_high: float, ib_low: float, 
                        current_price: float, levels: dict, date_str: str):
    """
    Saves IB data to ib_backtest directory with volume_profile for historical use.
    Called once per day after market close.
    """
    global EOD_SAVED_DATES
    
    key = f"{ticker}_{date_str}"
    if key in EOD_SAVED_DATES:
        return  # Already saved today
    
    # Calculate volume profile
    volume_profile = calculate_volume_profile(df_candles)
    
    # Build series data
    series_data = []
    for _, row in df_candles.iterrows():
        candle_time = row["datetime"]
        series_data.append({
            "time": candle_time.strftime("%H:%M"),
            "full_date": candle_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "price": float(row["close"]),
            "volume": float(row["volume"]),
        })
    
    ib_range = ib_high - ib_low
    
    json_data = {
        "meta": {
            "ticker": ticker,
            "date": date_str,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "EOD backup from ib_service.py with volume profile"
        },
        "analysis": {
            "ib_high": float(ib_high),
            "ib_low": float(ib_low),
            "ib_range": float(ib_range),
            "current_price": float(current_price),
            "day_high": float(df_candles["high"].max()) if not df_candles.empty else 0,
            "day_low": float(df_candles["low"].min()) if not df_candles.empty else 0,
            "total_volume": float(df_candles["volume"].sum()) if not df_candles.empty else 0,
        },
        "volume_profile": volume_profile,
        "levels": levels,  # Include Greek levels from ib_service
        "series": series_data,
    }
    
    filepath = os.path.join(IB_BACKTEST_DIR, f"ib_data_{ticker}_{date_str}.json")
    try:
        with open(filepath, "w") as f:
            json.dump(json_data, f, indent=4)
        EOD_SAVED_DATES.add(key)
        print(f"[EOD BACKUP] Saved {ticker} to ib_backtest/")
    except Exception as e:
        print(f"[EOD BACKUP ERROR] {ticker}: {e}")


# --- 3. GENERACIÓN DEL GRÁFICO IB ---
def generate_ib_chart(ticker: str, df_candles: pd.DataFrame, greeks_files: list, date_str: str):
    """
    Genera el gráfico IB usando datos de candles minuto a minuto.
    Para cada minuto, busca los niveles de griegas más cercanos en tiempo.
    """
    if df_candles.empty:
        return None

    df = df_candles.copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    
    current_price = df.iloc[-1]["close"]

    # --- 1. CÁLCULO IB (09:29 - 10:30) ---
    ib_start = dt_time(9, 29)
    ib_end = dt_time(10, 30)

    ib_data = df[df["datetime"].apply(lambda x: ib_start <= x.time() <= ib_end)]
    if ib_data.empty:
        if df.iloc[-1]["datetime"].time() < ib_start:
            return None
        ib_data = df

    ib_high = ib_data["high"].max()
    ib_low = ib_data["low"].min()
    ib_range = ib_high - ib_low

    # --- 2. CONSTRUIR SERIES CON VOLUMEN ---
    series_data = []
    for idx, row in df.iterrows():
        candle_time = row["datetime"]
        
        series_data.append({
            "time": candle_time.strftime("%H:%M"),
            "full_date": candle_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "price": float(row["close"]),
            "volume": float(row["volume"]),
        })

    # --- 3. OBTENER NIVELES FINALES ---
    final_levels = {}
    if greeks_files:
        final_file = greeks_files[-1][1]
        final_levels = extract_greeks_from_file(final_file)

    # --- 4. GUARDAR JSON ---
    try:
        json_data = {
            "meta": {
                "ticker": ticker,
                "date": date_str,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "analysis": {
                "ib_high": float(ib_high),
                "ib_low": float(ib_low),
                "ib_range": float(ib_range),
                "current_price": float(current_price),
            },
            "levels": {k: float(v) for k, v in final_levels.items() if not pd.isna(v)},
            "series": series_data,
        }

        json_filename = os.path.join(OUTPUT_DIR, f"ib_data_{ticker}_{date_str}.json")
        with open(json_filename, "w") as f:
            json.dump(json_data, f, indent=4)

        print(f"[JSON] Guardado: {json_filename}")
        
        # --- EOD BACKUP: Save to ib_backtest after market close (16:00+ NY) ---
        now_ny = datetime.now(NY_TZ) if NY_TZ else datetime.now()
        if now_ny.time() >= dt_time(16, 0):
            levels_for_backup = {k: float(v) for k, v in final_levels.items() if not pd.isna(v)}
            save_to_ib_backtest(ticker, df, ib_high, ib_low, current_price, levels_for_backup, date_str)

    except Exception as e:
        print(f"[ERROR JSON] {ticker}: {e}")

    # --- 5. GENERAR GRÁFICO PNG ---
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

    plt.rcParams["font.family"] = "monospace"
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#080808")
    ax.set_facecolor("#080808")

    ax.grid(True, which="major", color="#333333", linestyle=":", linewidth=0.5)
    ax.set_axisbelow(True)

    plt.title(
        f"{ticker} | INITIAL BALANCE & LEVELS | {formatted_date} (NY Time)",
        color="#e0e0e0",
        fontsize=14,
        fontweight="bold",
        pad=20,
        loc="left",
    )

    # === CANDLESTICKS ===
    from matplotlib.patches import Rectangle
    
    day_high = df["high"].max()
    day_low = df["low"].min()
    
    candle_width = 0.0004
    times = df["datetime"].tolist()
    opens = df["open"].tolist()
    highs = df["high"].tolist()
    lows = df["low"].tolist()
    closes = df["close"].tolist()

    for i in range(len(times)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        t = mdates.date2num(times[i])
        
        if c >= o:
            body_color, wick_color = "#00d26a", "#00d26a"  # Green (bullish)
        else:
            body_color, wick_color = "#ff4757", "#ff4757"  # Red (bearish)
        
        # Wick
        ax.plot([t, t], [l, h], color=wick_color, linewidth=0.8)
        # Body
        body_bottom = min(o, c)
        body_height = abs(c - o) if abs(c - o) > 0 else 0.01
        
        rect = Rectangle(
            (t - candle_width / 2, body_bottom),
            candle_width, body_height,
            facecolor=body_color, edgecolor=wick_color,
            linewidth=0.5, alpha=0.9
        )
        ax.add_patch(rect)

    txt_outline = [pe.withStroke(linewidth=2, foreground="black")]
    trans = ax.get_yaxis_transform()

    # Plot IB
    ax.axhspan(ib_low, ib_high, color="#FFFFFF", alpha=0.07, lw=0)
    ax.axhline(ib_high, color="#FFFFFF", linestyle="--", linewidth=1, alpha=0.5)
    ax.axhline(ib_low, color="#FFFFFF", linestyle="--", linewidth=1, alpha=0.5)

    ax.text(
        0.01, ib_high, f"IB HIGH: {ib_high:.2f}",
        color="#FFFFFF", fontsize=8, transform=trans,
        va="bottom", ha="left", path_effects=txt_outline, alpha=0.8,
    )
    ax.text(
        0.01, ib_low, f"IB LOW: {ib_low:.2f}",
        color="#FFFFFF", fontsize=8, transform=trans,
        va="top", ha="left", path_effects=txt_outline, alpha=0.8,
    )

    # Fibonacci
    colors_fib = ["#FFD700", "#FF8C00", "#FF4500"]

    if current_price > ib_high:
        exts = [1.272, 1.618, 2.0]
        for i, ext in enumerate(exts):
            fib_level = ib_low + (ib_range * ext)
            ax.axhline(fib_level, color=colors_fib[i], linestyle=":", linewidth=1, alpha=0.8)
            ax.text(
                0.01, fib_level, f"FIB {ext} ({fib_level:.2f})",
                color=colors_fib[i], fontsize=8, transform=trans,
                va="bottom", ha="left", path_effects=txt_outline,
            )
    elif current_price < ib_low:
        exts = [-0.272, -0.618, -1.0]
        for i, ext in enumerate(exts):
            fib_level = ib_low + (ib_range * ext)
            ax.axhline(fib_level, color=colors_fib[i], linestyle=":", linewidth=1, alpha=0.8)
            ax.text(
                0.01, fib_level, f"FIB {ext} ({fib_level:.2f})",
                color=colors_fib[i], fontsize=8, transform=trans,
                va="bottom", ha="left", path_effects=txt_outline,
            )

    # Griegos
    greek_colors = {
        "max_gamma": "#00FF00",
        "min_gamma": "#FF0000",
        "min_vanna": "#FF00FF",
        "max_dgex": "#00FFFF",
        "min_dgex": "#FFA500",
    }

    sorted_greeks = sorted(
        [(k, v) for k, v in final_levels.items() if not pd.isna(v)],
        key=lambda x: x[1]
    )

    for key, val in sorted_greeks:
        c = greek_colors.get(key, "#888888")
        label_txt = key.replace("_", " ").upper()

        ax.axhline(val, color=c, linestyle="-.", linewidth=1, alpha=0.6)
        ax.text(
            0.99, val, f"{label_txt}: {val:.0f}",
            color=c, fontsize=8, fontweight="bold", transform=trans,
            va="bottom", ha="right", path_effects=txt_outline,
        )

    # Ejes
    base_date = df["datetime"].iloc[0].date()
    start_plot = datetime.combine(base_date, dt_time(8, 0))
    end_plot = datetime.combine(base_date, dt_time(16, 15))
    if NY_TZ:
        start_plot = start_plot.replace(tzinfo=NY_TZ)
        end_plot = end_plot.replace(tzinfo=NY_TZ)

    ax.set_xlim(start_plot, end_plot)

    if NY_TZ:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=NY_TZ))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))

    ax.tick_params(axis="x", colors="#888888", rotation=0, labelsize=9)
    ax.tick_params(axis="y", colors="#888888", labelsize=9)
    ax.spines["bottom"].set_color("#333333")
    ax.spines["left"].set_color("#333333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ymin, ymax = ax.get_ylim()
    margin = (ymax - ymin) * 0.05
    ax.set_ylim(ymin - margin, ymax + margin)

    output_filename = os.path.join(OUTPUT_DIR, f"ib_chart_{ticker}_{date_str}.png")
    plt.savefig(output_filename, dpi=120, bbox_inches="tight", facecolor="#080808")
    plt.close()

    return output_filename


# --- BOT DE DISCORD ---
class IBBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.bg_task = None

    async def on_ready(self):
        print(f"[IB BOT] Conectado como {self.user}")
        if not self.bg_task:
            self.bg_task = self.loop.create_task(self.ib_loop())

    async def ib_loop(self):
        await self.wait_until_ready()
        print(f"[IB BOT] Iniciando monitoreo IB con DXLinkStreamer...")
        while not self.is_closed():
            try:
                await self.process_tickers_async()
            except Exception as e:
                print(f"[ERROR LOOP] {e}")
                import traceback
                traceback.print_exc()
            await asyncio.sleep(20)

    async def process_tickers_async(self):
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        print(f"--- Ciclo IB {now.strftime('%H:%M:%S')} ---", flush=True)

        # Procesar tickers normales (equities)
        for ticker in TICKERS_TO_TRACK:
            try:
                # 1. Descargar velas de 1 minuto vía DXLinkStreamer
                df_candles = await get_candle_data_for_today(ticker)
                
                if df_candles.empty:
                    print(f"[SKIP] {ticker}: No hay velas")
                    continue

                # 2. Obtener archivos de griegas de json_data/
                target_exp = "0dte" if ticker in ["SPX", "SPY", "QQQ"] else "weekly"
                greeks_files = get_all_greeks_files(ticker, target_exp, today_str)
                
                if not greeks_files:
                    print(f"[WARN] {ticker}: Sin archivos de griegas, usando solo velas")
                
                # 3. Generar gráfico y JSON
                png_path = generate_ib_chart(ticker, df_candles, greeks_files, today_str)
                
                if png_path and os.path.exists(png_path):
                    await self.send_plot(ticker, png_path)
                    SENT_CACHE[ticker] = datetime.now().timestamp()
                    print(f"[IB OK] {ticker}")
                    
            except Exception as e:
                print(f"[ERROR] {ticker}: {e}")
                import traceback
                traceback.print_exc()

        # Procesar futuros (/ES, /NQ) con candlestick aesthetic
        for ticker in FUTURES_TO_TRACK:
            try:
                # 1. Descargar velas de futuros
                df_candles = await get_futures_candle_data_for_today(ticker)
                
                if df_candles.empty:
                    print(f"[SKIP FUTURES] {ticker}: No hay velas")
                    continue

                # 2. Obtener griegas mapeadas (SPX para /ES, QQQ→NDX para /NQ)
                greeks = await get_greeks_for_future(ticker, today_str)
                if not greeks:
                    print(f"[WARN FUTURES] {ticker}: Sin griegas, generando sin niveles")
                
                # 3. Generar gráfico con candlesticks
                png_path = generate_futures_ib_chart(ticker, df_candles, greeks, today_str)
                
                if png_path and os.path.exists(png_path):
                    await self.send_plot(ticker, png_path)
                    SENT_CACHE[ticker] = datetime.now().timestamp()
                    print(f"[IB FUTURES OK] {ticker}")
                    
            except Exception as e:
                print(f"[ERROR FUTURES] {ticker}: {e}")
                import traceback
                traceback.print_exc()

    async def send_plot(self, ticker, png_path):
        channel_id = CHANNEL_MAPPING.get(ticker, CHANNEL_MAPPING.get("DEFAULT"))
        if not channel_id:
            return
        channel = self.get_channel(channel_id)
        if channel:
            try:
                now_ny = datetime.now(NY_TZ) if NY_TZ else datetime.now()
                date_str = now_ny.strftime("%a %b %d %H:%M:%S %Y EST")
                msg_content = f"**IB Analysis** | {ticker} | {date_str}"
                file = discord.File(png_path, filename=os.path.basename(png_path))
                await channel.send(content=msg_content, file=file)
            except Exception as e:
                print(f"[DISCORD ERROR] {ticker}: {e}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: Falta DISCORD_BOT_TOKEN")
    elif not TT_USERNAME or not TT_PASSWORD:
        print("ERROR: Falta TT_USERNAME o TT_PASSWORD en .env")
    else:
        client = IBBot()
        client.run(DISCORD_TOKEN)
