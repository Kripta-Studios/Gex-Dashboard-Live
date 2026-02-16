import matplotlib.patheffects as pe
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")  # Backend sin pantalla
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
import re
import os
import glob
import asyncio
import discord
import time
from datetime import datetime, timedelta
from datetime import time as dt_time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import pandas_market_calendars as mcal

# --- CONFIGURACIÓN DE DISCORD ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NYSE_CALENDAR = mcal.get_calendar('NYSE')
# ¡¡IMPORTANTE!!: RELLENA ESTOS IDs CON LOS DE TU SERVIDOR
# Si no pones IDs, el script generará las imágenes pero no las enviará.
CHANNEL_MAPPING = {
    "SPX": 1462142087305892064,  # ID del canal para Índices
    "SPY": 1462142165915406495,
    "QQQ": 1462142196332495092,
    "IWM": 1462142236505538631,
    "VIX": 1462142259796512902,
    "AAPL": 1462142296198742157,  # ID del canal para Tech
    "AMZN": 1462142319393243167,
    # Añade el resto o usa un canal "default" para los demás
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

# --- RUTAS Y ZONAS ---
DATA_FOLDER_PATH = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"
OUTPUT_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/fourier"

try:
    SERVER_TZ = ZoneInfo("Europe/Madrid")
    NY_TZ = ZoneInfo("America/New_York")
except Exception as e:
    print(f"[CRITICAL ERROR] No encuentro las zonas horarias. Instala tzdata: {e}")
    SERVER_TZ = None
    NY_TZ = None

TICKERS_TO_TRACK = [
    "SPX",
    "SPY",
    "QQQ",
    "IWM",
    "VIX",
    "AAPL",
    "MSFT",
    "AMZN",
    "META",
    "MSTR",
    "TSLA",
    "SLV",
    "GLD",
    "GOOGL",
    "NVDA",
    "AMD",
    "NFLX",
    "PLTR",
    "HOOD",
    "HIMS",
    "UNH",
]

FOURIER_THRESHOLD_PRICE = 0.05
FOURIER_THRESHOLD_IV = 0.08

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

SENT_CACHE = {}

# --- 1. PROCESAMIENTO ---
def is_market_open(check_date) -> bool:
    """
    Verifica si el NYSE está abierto en una fecha específica.
    """
    schedule = NYSE_CALENDAR.schedule(start_date=check_date, end_date=check_date)
    return not schedule.empty

def process_single_file(filepath, spot_price_key="spot_price"):
    try:
        filename = os.path.basename(filepath)

        with open(filepath, "r") as f:
            content = json.load(f)

        spot = content.get(spot_price_key, 0)
        if spot == 0:
            return None

        # Regex fecha
        match = re.search(r"_(\d{8})_(\d{6})\.json", filename)
        if match:
            dt_str = f"{match.group(1)} {match.group(2)}"
            dt_server = datetime.strptime(dt_str, "%Y%m%d %H%M%S")

            # Conversión TZ
            if SERVER_TZ and NY_TZ:
                dt_server = dt_server.replace(tzinfo=SERVER_TZ)
                dt_ny = dt_server.astimezone(NY_TZ)
                ny_time = dt_ny.time()
            else:
                dt_ny = dt_server  # Fallback si fallan las TZ
        else:
            print(f"[DEBUG ERROR] Regex falló en archivo: {filename}")
            return None

        raw_df = content.get("option_data", {})
        if not raw_df or "data" not in raw_df:
            return None

        df_opt = pd.DataFrame(data=raw_df["data"], columns=raw_df["columns"])

        # Limpieza de columnas
        cols = ["strike_price", "put_iv"]
        for col in cols:
            if col in df_opt.columns:
                df_opt[col] = pd.to_numeric(df_opt[col], errors="coerce")

        # Calcular IV ATM
        df_opt["dist"] = (df_opt["strike_price"] - spot).abs()
        if df_opt.empty:
            return None

        atm_iv = df_opt.loc[df_opt["dist"].idxmin()]["put_iv"]

        return {"datetime": dt_ny, "spot": spot, "atm_put_iv": atm_iv}

    except Exception as e:
        print(f"[DEBUG ERROR] Fallo procesando {os.path.basename(filepath)}: {e}")
        return None


def get_data_for_ticker(ticker, expiry, target_date):
    pattern = os.path.join(
        DATA_FOLDER_PATH, f"*{ticker}*{expiry}*ExposureData*{target_date}*.json"
    )
    files = glob.glob(pattern)
    files.sort()
    if not files:
        return pd.DataFrame(), None

    last_file_mtime = os.path.getmtime(files[-1])

    data_records = []
    for f in files:
        res = process_single_file(f)
        if res:
            data_records.append(res)

    return pd.DataFrame(data_records), last_file_mtime


# --- 2. MATEMÁTICAS ---


def apply_fourier_filter(series, threshold=0.08):
    y = np.array(series)
    n = len(y)
    if n == 0:
        return np.array([])
    x = np.arange(n)
    try:
        coeffs = np.polyfit(x, y, 1)
        trend = np.polyval(coeffs, x)
        detrended = y - trend
        fft_coeffs = np.fft.rfft(detrended)
        frequencies = np.fft.rfftfreq(n)
        fft_coeffs[frequencies > threshold] = 0
        return np.fft.irfft(fft_coeffs, n) + trend
    except Exception as e:
        print(f"[MATH ERROR] Fourier falló: {e}")
        return y


def detect_turns(y_data):
    if len(y_data) < 2:
        return []
    dy = np.diff(y_data, prepend=y_data[0])
    turns_indices = np.where(np.diff(np.sign(dy)))[0]
    events = []
    for i in turns_indices:
        if i + 1 >= len(y_data):
            continue
        current_sign = np.sign(dy[i + 1])
        prev_sign = np.sign(dy[i])
        if prev_sign > 0 and current_sign < 0:
            events.append((i, "PEAK"))
        elif prev_sign < 0 and current_sign > 0:
            events.append((i, "VALLEY"))
    return events


# --- 3. GENERACIÓN ---
def analyze_save_and_plot(ticker, df, date_str):
    if df.empty or len(df) < 5:
        return None

    df = df.sort_values("datetime").reset_index(drop=True)
    start_time = dt_time(3, 0)  # 03:00 AM
    end_time = dt_time(17, 0)
    # df['datetime'] ya viene en hora NY desde process_single_file
    df = df[df["datetime"].apply(lambda x: start_time <= x.time() <= end_time)]

    # Importante: Si después de filtrar no quedan datos (ej. son las 2 AM), salimos
    if df.empty or len(df) < 5:
        return None

    df = df.reset_index(drop=True)

    # Fourier calculations
    df["spot_fft"] = apply_fourier_filter(df["spot"], threshold=FOURIER_THRESHOLD_PRICE)
    df["iv_fft"] = apply_fourier_filter(
        df["atm_put_iv"], threshold=FOURIER_THRESHOLD_IV
    )

    # 1. JSON
    json_df = df.copy()
    json_df["datetime"] = json_df["datetime"].apply(
        lambda x: x.strftime("%Y-%m-%d %H:%M:%S")
    )
    json_filename = os.path.join(OUTPUT_DIR, f"fourier_data_{ticker}_{date_str}.json")
    json_df.to_json(json_filename, orient="records", indent=4)

    # 2. PNG - ESTILO PREMIUM
    spot_turns = detect_turns(df["spot_fft"])
    iv_turns = detect_turns(df["iv_fft"])

    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")

    plt.rcParams["font.family"] = "monospace"
    fig, ax1 = plt.subplots(figsize=(16, 8))
    fig.patch.set_facecolor("#080808")  # Negro puro
    ax1.set_facecolor("#080808")

    # Grid sutil
    ax1.grid(True, which="major", color="#333333", linestyle=":", linewidth=0.5)
    ax1.set_axisbelow(True)

    plt.title(
        f"{ticker} | FOURIER PRICE vs IV | {formatted_date} (NY Time)",
        color="#e0e0e0",
        fontsize=14,
        fontweight="bold",
        pad=20,
        loc="left",
    )

    # --- EJE PRECIO (NEON CYAN) ---
    ax1.plot(
        df["datetime"], df["spot_fft"], color="#00F0FF", linewidth=2, label="Spot Price"
    )
    ax1.set_ylabel(f"{ticker} Spot", color="#00F0FF", fontsize=10, fontweight="bold")
    ax1.tick_params(axis="y", colors="#00F0FF", labelsize=9)
    ax1.spines["left"].set_color("#00F0FF")
    ax1.spines["left"].set_alpha(0.5)

    for idx, tipo in spot_turns:
        x_val = df["datetime"].iloc[idx]
        y_val = df["spot_fft"][idx]
        ax1.axvline(x=x_val, color="#00F0FF", linestyle=":", alpha=0.2)
        c = "#FF0000" if tipo == "PEAK" else "#00FF00"
        ax1.scatter(
            x_val, y_val, color=c, s=50, zorder=10, edgecolors="white", linewidth=1
        )

    # --- EJE IV (NEON MAGENTA) ---
    ax2 = ax1.twinx()
    ax2.plot(
        df["datetime"],
        df["iv_fft"],
        color="#FF00FF",
        linewidth=2,
        alpha=0.9,
        label="Put IV",
    )
    ax2.set_ylabel("ATM IV", color="#FF00FF", fontsize=10, fontweight="bold")
    ax2.tick_params(axis="y", colors="#FF00FF", labelsize=9)
    ax2.spines["right"].set_color("#FF00FF")
    ax2.spines["right"].set_alpha(0.5)
    ax2.spines["left"].set_visible(False)

    for idx, tipo in iv_turns:
        x_val = df["datetime"].iloc[idx]
        y_val = df["iv_fft"][idx]
        ax1.axvline(x=x_val, color="#FF00FF", linestyle=":", alpha=0.2)
        c = "#FF0000" if tipo == "PEAK" else "#00FF00"
        ax2.scatter(
            x_val,
            y_val,
            color=c,
            s=40,
            zorder=10,
            marker="D",
            edgecolors="white",
            linewidth=1,
        )

    # Limpieza de bordes
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax1.spines["bottom"].set_color("#333333")

    # Eje X - Hora
    if NY_TZ:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=NY_TZ))
    else:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    ax1.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
    ax1.tick_params(axis="x", colors="#888888", rotation=0, labelsize=9)

    png_filename = os.path.join(OUTPUT_DIR, f"fourier_plot_{ticker}_{date_str}.png")
    plt.savefig(png_filename, dpi=120, bbox_inches="tight", facecolor="#080808")
    plt.close()

    return png_filename


# --- BOT ---


class FourierBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.bg_task = None

    async def on_ready(self):
        print(f"[DISCORD] Conectado como {self.user}")
        if not self.bg_task:
            self.bg_task = self.loop.create_task(self.fourier_loop())

    async def fourier_loop(self):
        await self.wait_until_ready()
        print(f"[SYSTEM] Iniciando Bucle Fourier. Tickers: {len(TICKERS_TO_TRACK)}")

        while not self.is_closed():
            try:
                # --- VALIDACIÓN DE DÍA HÁBIL ---
                now_ny = datetime.now(NY_TZ) if NY_TZ else datetime.now()
                trading_date = now_ny.date()
                
                # Si son antes de las 3:00 AM en NY, cuenta como el día de trading anterior
                if now_ny.time() < dt_time(3, 0):
                    trading_date = trading_date - timedelta(days=1)
                
                if not is_market_open(trading_date):
                    # El mercado está cerrado hoy. Dormimos 5 minutos y volvemos a comprobar.
                    print(f"[{now_ny.strftime('%H:%M:%S')}] NYSE CERRADO. FourierBot en reposo (esperando 5 min)...")
                    await asyncio.sleep(300) 
                    continue
                await self.loop.run_in_executor(None, self.process_tickers_sync)
            except Exception as e:
                print(f"[ERROR LOOP] {e}")

            print("[SYSTEM] Esperando 60 segundos...")
            await asyncio.sleep(60)

    def process_tickers_sync(self):
        now_ny = datetime.now(NY_TZ) if NY_TZ else datetime.now()
        trading_date = now_ny.date()
        if now_ny.time() < dt_time(3, 0):
            trading_date = trading_date - timedelta(days=1)
        today_str = trading_date.strftime("%Y%m%d")

        for ticker in TICKERS_TO_TRACK:
            try:
                target_exp = "0dte" if ticker in ["SPX", "SPY", "QQQ"] else "weekly"

                df, last_mtime = get_data_for_ticker(ticker, target_exp, today_str)

                # Debug si no encuentra nada
                if df.empty:
                    # Solo imprimimos una vez para no floodear, o si es SPX
                    if ticker == "SPX":
                        print(
                            f"[DEBUG SPX] No se encontraron registros válidos para hoy ({today_str})."
                        )
                    else:
                        print(f"EMPTY {ticker} {target_exp}")
                if not df.empty and last_mtime:
                    last_processed = SENT_CACHE.get(ticker)

                    if last_processed != last_mtime:
                        png_path = analyze_save_and_plot(ticker, df, today_str)

                        if png_path and os.path.exists(png_path):
                            future = asyncio.run_coroutine_threadsafe(
                                self.send_plot(ticker, png_path), self.loop
                            )
                            SENT_CACHE[ticker] = last_mtime
                            print(f"[UPDATE] {ticker}: Procesado y enviado.")
                    else:
                        print("JSON data file has not changed for", ticker)
            except Exception as e:
                print(f"[ERROR TICKER] {ticker}: {e}")

    async def send_plot(self, ticker, png_path):
        channel_id = CHANNEL_MAPPING.get(ticker, CHANNEL_MAPPING.get("DEFAULT"))
        if not channel_id:
            return

        channel = self.get_channel(channel_id)
        if channel:
            try:
                now_ny = datetime.now(NY_TZ) if NY_TZ else datetime.now()
                date_str = now_ny.strftime("%a %b %d %H:%M:%S %Y EST")
                msg_content = f"Fourier {ticker} at {date_str}"

                file = discord.File(png_path, filename=os.path.basename(png_path))
                await channel.send(content=msg_content, file=file)
            except Exception as e:
                print(f"[DISCORD ERROR] {ticker}: {e}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: Falta DISCORD_TOKEN")
    else:
        client = FourierBot()
        client.run(DISCORD_TOKEN)
