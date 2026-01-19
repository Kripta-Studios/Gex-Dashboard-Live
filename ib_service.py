import matplotlib.patheffects as pe
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
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

# --- CONFIGURACIÓN ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Mapeo de Canales (Asegúrate de que sean correctos
CHANNEL_MAPPING = {
    "SPX": 1462142087305892064,  # ID del canal para Índices
    "SPY": 1462142165915406495,
    "QQQ": 1462142196332495092,
    "IWM": 1462142236505538631,
    "VIX": 1462142259796512902,
    "AAPL":1462142296198742157, # ID del canal para Tech
    "AMZN":1462142319393243167,
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
    "SLV": 1462142697254027388
}


DATA_FOLDER_PATH = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"
OUTPUT_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_charts"

# Zonas Horarias
try:
    SERVER_TZ = ZoneInfo("Europe/Madrid")
    NY_TZ = ZoneInfo("America/New_York")
except:
    SERVER_TZ = None
    NY_TZ = None

# Tickers a seguir
TICKERS_TO_TRACK = ["SPX", "SPY", "QQQ", "IWM", "VIX", "AAPL", "NVDA", "TSLA", "AMD", "MSFT", "AMZN", "META", "GOOGL"]

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

SENT_CACHE = {}

# --- 1. EXTRACCIÓN ---
def get_spot_history(ticker, expiry, date_str):
    pattern = os.path.join(DATA_FOLDER_PATH, f"*{ticker}*{expiry}*ExposureData*{date_str}*.json")
    files = glob.glob(pattern)
    files.sort()
    data = []
    for filepath in files:
        try:
            if os.path.getsize(filepath) == 0: continue
                        
            filename = os.path.basename(filepath)
            match = re.search(r'_(\d{8})_(\d{6})\.json', filename)
            if not match: continue
            
            dt_str = f"{match.group(1)} {match.group(2)}"
            dt_server = datetime.strptime(dt_str, "%Y%m%d %H%M%S")
            
            if SERVER_TZ and NY_TZ:
                dt_server = dt_server.replace(tzinfo=SERVER_TZ)
                dt_ny = dt_server.astimezone(NY_TZ)
            else:
                dt_ny = dt_server

            with open(filepath, 'r') as f:
                content = json.load(f)
                spot = content.get('spot_price', 0)

            if spot > 0:
                data.append({'datetime': dt_ny, 'spot': spot})
            else:
                print("Spot is zero:", spot, "in", ticker, "exp", exp)
        except: continue
            
    return pd.DataFrame(data), files[-1] if files else None

def get_latest_greeks_levels(filepath, ticker):
    try:
        with open(filepath, 'r') as f:
            content = json.load(f)
        
        raw_df = content.get('option_data', {})
        if not raw_df or 'data' not in raw_df: return {}
        
        df = pd.DataFrame(data=raw_df['data'], columns=raw_df['columns'])
        for col in ['strike_price', 'total_gamma', 'total_vanna', 'total_dgex']:
            if col in df.columns: 
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        greeks = df.groupby('strike_price')[['total_gamma', 'total_vanna', 'total_dgex']].sum()
        
        return {
            'max_gamma': greeks['total_gamma'].idxmax(),
            'min_gamma': greeks['total_gamma'].idxmin(),
            'min_vanna': greeks['total_vanna'].idxmin(),
            'max_dgex': greeks['total_dgex'].idxmax(),
            'min_dgex': greeks['total_dgex'].idxmin()
        }
    except: return {}

# --- 2. GENERACIÓN ---
def generate_ib_chart(ticker, df, levels, date_str):
    if df.empty: return None
    
    df = df.sort_values('datetime').reset_index(drop=True)
    current_price = df.iloc[-1]['spot']
    
    # --- 1. CÁLCULO IB (09:29 - 10:30) ---
    ib_start = dt_time(9, 29) 
    ib_end = dt_time(10, 30)
    
    # Filtramos por hora (la columna datetime ya tiene zona horaria)
    ib_data = df[df['datetime'].apply(lambda x: ib_start <= x.time() <= ib_end)]
    if ib_data.empty:
        if df.iloc[-1]['datetime'].time() < ib_start: return None
        ib_data = df 
    
    ib_high = ib_data['spot'].max()
    ib_low = ib_data['spot'].min()
    ib_range = ib_high - ib_low
    
    # ==========================================
    # NUEVO BLOQUE: GUARDAR DATOS EN JSON
    # ==========================================
    try:
        # Preparamos el diccionario de datos
        json_data = {
            "meta": {
                "ticker": ticker,
                "date": date_str,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "analysis": {
                "ib_high": float(ib_high),
                "ib_low": float(ib_low),
                "ib_range": float(ib_range),
                "current_price": float(current_price)
            },
            # Convertimos valores de numpy a float nativo para evitar errores de JSON
            "levels": {k: float(v) for k, v in levels.items() if not pd.isna(v)},
            # Serie temporal completa para que el frontend pueda pintar la línea
            "series": df.apply(lambda row: {
                "time": row['datetime'].strftime('%H:%M'), # Hora NY formateada
                "full_date": row['datetime'].strftime('%Y-%m-%d %H:%M:%S'),
                "price": float(row['spot'])
            }, axis=1).tolist()
        }

        # Guardamos el archivo .json
        json_filename = os.path.join(OUTPUT_DIR, f"ib_data_{ticker}_{date_str}.json")
        with open(json_filename, 'w') as f:
            json.dump(json_data, f, indent=4)
            
        #print(f"[JSON] Guardado datos para {ticker}") # Opcional: Debug
        
    except Exception as e:
        print(f"[ERROR JSON] No se pudo guardar JSON para {ticker}: {e}")

    # ==========================================
    # FIN BLOQUE JSON - CONTINÚA EL GRÁFICO PNG
    # ==========================================
    
    # --- 2. ESTILO PREMIUM ---
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    
    plt.rcParams['font.family'] = 'monospace'
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#080808')
    ax.set_facecolor('#080808')
    
    # Grid Sutil
    ax.grid(True, which='major', color='#333333', linestyle=':', linewidth=0.5)
    ax.set_axisbelow(True)
    
    plt.title(f'{ticker} | INITIAL BALANCE & LEVELS | {formatted_date} (NY Time)', 
              color='#e0e0e0', fontsize=14, fontweight='bold', pad=20, loc='left')
    
    # --- 3. PLOT PRECIO ---
    ax.plot(df['datetime'], df['spot'], color='#00F0FF', linewidth=1.5, label='Price')
    
    # Efecto borde negro para el texto
    txt_outline = [pe.withStroke(linewidth=2, foreground='black')]
    
    # Transformación para pegar texto a los ejes (0=izq, 1=der)
    trans = ax.get_yaxis_transform()

    # --- 4. PLOT IB ---
    ax.axhspan(ib_low, ib_high, color='#FFFFFF', alpha=0.07, lw=0)
    ax.axhline(ib_high, color='#FFFFFF', linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(ib_low, color='#FFFFFF', linestyle='--', linewidth=1, alpha=0.5)
    
    # Textos IB (Alineados a la IZQUIERDA: x=0.01)
    ax.text(0.01, ib_high, f'IB HIGH: {ib_high:.2f}', color='#FFFFFF', fontsize=8, 
            transform=trans, va='bottom', ha='left', path_effects=txt_outline, alpha=0.8)
    ax.text(0.01, ib_low, f'IB LOW: {ib_low:.2f}', color='#FFFFFF', fontsize=8, 
            transform=trans, va='top', ha='left', path_effects=txt_outline, alpha=0.8)

    # --- 5. FIBONACCI ---
    colors_fib = ['#FFD700', '#FF8C00', '#FF4500'] # Oro, Naranja, Rojo
    
    if current_price > ib_high:
        exts = [1.272, 1.618, 2.0]
        for i, ext in enumerate(exts):
            fib_level = ib_low + (ib_range * ext)
            ax.axhline(fib_level, color=colors_fib[i], linestyle=':', linewidth=1, alpha=0.8)
            ax.text(0.01, fib_level, f'FIB {ext} ({fib_level:.2f})', color=colors_fib[i], 
                    fontsize=8, transform=trans, va='bottom', ha='left', path_effects=txt_outline)
            
    elif current_price < ib_low:
        exts = [-0.272, -0.618, -1.0]
        for i, ext in enumerate(exts):
            fib_level = ib_low + (ib_range * ext)
            ax.axhline(fib_level, color=colors_fib[i], linestyle=':', linewidth=1, alpha=0.8)
            ax.text(0.01, fib_level, f'FIB {ext} ({fib_level:.2f})', color=colors_fib[i], 
                    fontsize=8, transform=trans, va='bottom', ha='left', path_effects=txt_outline)

    # --- 6. GRIEGOS ---
    greek_colors = {
        'max_gamma': '#00FF00', # Lime
        'min_gamma': '#FF0000', # Red
        'min_vanna': '#FF00FF', # Magenta
        'max_dgex': '#00FFFF',  # Cyan
        'min_dgex': '#FFA500'   # Orange
    }
    
    # Ordenar para evitar solapamiento (simple)
    sorted_greeks = sorted([(k, v) for k, v in levels.items() if not pd.isna(v)], key=lambda x: x[1])

    for key, val in sorted_greeks:
        c = greek_colors.get(key, '#888888')
        label_txt = key.replace('_', ' ').upper()
        
        ax.axhline(val, color=c, linestyle='-.', linewidth=1, alpha=0.6)
        
        # Textos Griegos (Alineados a la DERECHA: x=0.99)
        ax.text(0.99, val, f'{label_txt}: {val:.0f}', color=c, fontsize=8, fontweight='bold',
                transform=trans, va='bottom', ha='right', path_effects=txt_outline)

    # --- 7. EJES ---
    # Definir límites de tiempo (08:00 - 16:15)
    base_date = df['datetime'].iloc[0].date()
    start_plot = datetime.combine(base_date, dt_time(8, 0)).replace(tzinfo=NY_TZ)
    end_plot = datetime.combine(base_date, dt_time(16, 15)).replace(tzinfo=NY_TZ)
    
    ax.set_xlim(start_plot, end_plot)
    
    # Formato Ejes
    if NY_TZ:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=NY_TZ))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    
    # Estilo Ejes
    ax.tick_params(axis='x', colors='#888888', rotation=0, labelsize=9)
    ax.tick_params(axis='y', colors='#888888', labelsize=9)
    ax.spines['bottom'].set_color('#333333')
    ax.spines['left'].set_color('#333333')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Margen vertical
    ymin, ymax = ax.get_ylim()
    margin = (ymax - ymin) * 0.05
    ax.set_ylim(ymin - margin, ymax + margin)
    
    output_filename = os.path.join(OUTPUT_DIR, f"ib_chart_{ticker}_{date_str}.png")
    plt.savefig(output_filename, dpi=120, bbox_inches='tight', facecolor='#080808')
    plt.close()
    
    return output_filename
# --- BOT ---
class IBBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.bg_task = None

    async def on_ready(self):
        print(f'[IB BOT] Conectado como {self.user}')
        if not self.bg_task:
            self.bg_task = self.loop.create_task(self.ib_loop())

    async def ib_loop(self):
        await self.wait_until_ready()
        print(f"[IB BOT] Iniciando monitoreo IB...")
        while not self.is_closed():
            try:
                await self.loop.run_in_executor(None, self.process_tickers)
            except Exception as e:
                print(f"[ERROR LOOP] {e}")
            await asyncio.sleep(20)

    def process_tickers(self):
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        print(f"--- Iniciando ciclo de procesamiento IB {datetime.now().strftime('%H:%M:%S')} ---", flush=True)
        if SERVER_TZ:
            now_server = datetime.now(SERVER_TZ)
            
        for ticker in TICKERS_TO_TRACK:
            try:
                target_exp = "0dte" if ticker in ["SPX", "SPY", "QQQ"] else "weekly"
                df_spot, latest_file = get_spot_history(ticker, target_exp, today_str)
                
                if df_spot.empty or not latest_file: continue
                
                last_mtime = os.path.getmtime(latest_file)
                last_processed = SENT_CACHE.get(ticker)
                
                if last_processed != last_mtime:
                    levels = get_latest_greeks_levels(latest_file, ticker)
                    png_path = generate_ib_chart(ticker, df_spot, levels, today_str)
                    
                    if png_path and os.path.exists(png_path):
                        future = asyncio.run_coroutine_threadsafe(
                            self.send_plot(ticker, png_path), 
                            self.loop
                        )
                        SENT_CACHE[ticker] = last_mtime
                        print(f"[IB UPDATE] {ticker}: Enviado.")
            except Exception as e:
                print(f"[ERROR IB] {ticker}: {e}")

    async def send_plot(self, ticker, png_path):
        channel_id = CHANNEL_MAPPING.get(ticker, CHANNEL_MAPPING.get("DEFAULT"))
        if not channel_id: return
        channel = self.get_channel(channel_id)
        if channel:
            try:
                now_ny = datetime.now(NY_TZ) if NY_TZ else datetime.now()
                date_str = now_ny.strftime("%a %b %d %H:%M:%S %Y EST")
                msg_content = f"**IB Analysis** | {ticker} | {date_str}"
                file = discord.File(png_path, filename=os.path.basename(png_path))
                await channel.send(content=msg_content, file=file)
            except Exception as e:
                print(f"[DISCORD IB ERROR] {ticker}: {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: Falta DISCORD_TOKEN")
    else:
        client = IBBot()
        client.run(DISCORD_TOKEN)
