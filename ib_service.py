"""
IB Charts Generator usando DXLinkStreamer para velas minuto a minuto.
Obtiene datos de candles en tiempo real via tastytrade API y
combina con datos de griegas de json_data/.
"""

import matplotlib.patheffects as pe
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
import re
import os
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

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

if not os.path.exists(IB_BACKTEST_DIR):
    os.makedirs(IB_BACKTEST_DIR)

# Track which dates have been saved to ib_backtest today (to avoid duplicates)
EOD_SAVED_DATES = set()

SENT_CACHE = {}

# --- SESIÓN TASTYTRADE ---
_session = None

def get_tastytrade_session():
    """Crea o reutiliza una sesión de tastytrade."""
    global _session
    if _session is None:
        if not TT_USERNAME or not TT_PASSWORD:
            raise ValueError("Falta TT_USERNAME o TT_PASSWORD en .env")
        _session = Session(TT_USERNAME, TT_PASSWORD)
        print("[TT] Sesión creada exitosamente")
    return _session


# --- 1. OBTENER CANDLES VÍA DXLINKSTREAMER ---
async def get_candle_data_for_today(ticker: str) -> pd.DataFrame:
    """
    Descarga datos de velas de 1 minuto para el día de hoy usando DXLinkStreamer.
    Retorna un DataFrame con columnas: datetime, open, high, low, close, volume
    """
    candles_list = []
    
    # Calcular el inicio del día de trading (9:30 AM NY)
    now = datetime.now(NY_TZ) if NY_TZ else datetime.now()
    today = now.date()
    
    # Si estamos antes de las 9:30, podría ser día anterior
    if now.time() < dt_time(9, 30):
        today = today - timedelta(days=1)
    
    start_time = datetime.combine(today, dt_time(9, 0))
    if NY_TZ:
        start_time = start_time.replace(tzinfo=NY_TZ)
    
    ts = round(start_time.timestamp() * 1000)
    
    print(f"[CANDLE] Descargando velas 1m para {ticker} desde {start_time.strftime('%H:%M')}")
    
    try:
        session = get_tastytrade_session()
        
        async with DXLinkStreamer(session) as streamer:
            await streamer.subscribe_candle([ticker], "1m", start_time)
            
            # Timeout: esperar máximo 60 segundos para descargar todas las velas
            last_count = 0
            stall_checks = 0
            try:
                async with asyncio.timeout(60):
                    async for candle in streamer.listen(Candle):
                        if candle.close:
                            # Convertir timestamp a datetime EN ZONA NY (no local del servidor)
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
                        
                        # Romper cuando llegamos al inicio del día (vela más antigua)
                        if candle.time == ts:
                            print(f"[CANDLE] {ticker}: Llegamos al inicio del día")
                            break
            except asyncio.TimeoutError:
                print(f"[CANDLE] {ticker}: Timeout 60s, {len(candles_list)} velas")
                        
    except Exception as e:
        print(f"[ERROR CANDLE] {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    
    if not candles_list:
        return pd.DataFrame()
    
    df = pd.DataFrame(candles_list)
    df = df.sort_values("datetime").reset_index(drop=True)
    
    # Filtrar solo horas de trading (9:00 - 16:20)
    df = df[df["datetime"].apply(lambda x: dt_time(9, 0) <= x.time() <= dt_time(16, 20))]
    
    print(f"[CANDLE] {ticker}: {len(df)} velas descargadas")
    return df


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

    # Plot precio
    ax.plot(df["datetime"], df["close"], color="#00F0FF", linewidth=1.5, label="Price")

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
