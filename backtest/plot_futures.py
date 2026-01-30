"""
Plot Futures - Generador de Gráficos de Velas para Futuros

Lee los archivos JSON generados por ib_generate_futures.py y crea
gráficos PNG con velas del movimiento del contrato de futuros.

Uso:
    python plot_futures.py
"""

import json
import os
import glob
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import matplotlib.patheffects as pe

# --- CONFIGURACIÓN ---
# Directorio de entrada (donde están los JSON de ib_generate_futures.py)
INPUT_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"

# Directorio de salida para los gráficos PNG
OUTPUT_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/futures_plots"

# Zona horaria
try:
    NY_TZ = ZoneInfo("America/New_York")
except:
    NY_TZ = None

# Crear directorio de salida si no existe
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[SETUP] Creado directorio: {OUTPUT_DIR}")


def load_json_data(filepath: str) -> dict:
    """Carga datos de un archivo JSON."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] No se pudo cargar {filepath}: {e}")
        return {}


def plot_candlestick_chart(json_data: dict, output_path: str):
    """
    Genera un gráfico de velas a partir de los datos JSON.
    
    Args:
        json_data: Diccionario con datos del JSON
        output_path: Ruta donde guardar el PNG
    """
    if not json_data or "series" not in json_data:
        print(f"  [SKIP] Sin datos de series")
        return False
    
    series = json_data["series"]
    if not series:
        print(f"  [SKIP] Series vacía")
        return False
    
    meta = json_data.get("meta", {})
    analysis = json_data.get("analysis", {})
    volume_profile = json_data.get("volume_profile", {})
    
    ticker = meta.get("ticker", "UNKNOWN")
    date_str = meta.get("date", "")
    
    # Convertir series a listas para plotting
    times = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []
    
    for candle in series:
        try:
            # Parsear tiempo
            if "full_date" in candle:
                dt = datetime.strptime(candle["full_date"], "%Y-%m-%d %H:%M:%S")
                if NY_TZ:
                    dt = dt.replace(tzinfo=NY_TZ)
            else:
                # Fallback: usar solo la hora y asumir la fecha del JSON
                date_part = datetime.strptime(date_str, "%Y%m%d").date()
                time_part = datetime.strptime(candle["time"], "%H:%M").time()
                dt = datetime.combine(date_part, time_part)
                if NY_TZ:
                    dt = dt.replace(tzinfo=NY_TZ)
            
            times.append(dt)
            opens.append(candle.get("open", candle.get("price", 0)))
            highs.append(candle.get("high", candle.get("price", 0)))
            lows.append(candle.get("low", candle.get("price", 0)))
            closes.append(candle.get("price", candle.get("close", 0)))
            volumes.append(candle.get("volume", 0))
        except Exception as e:
            continue
    
    if not times:
        print(f"  [SKIP] No se pudieron parsear las velas")
        return False
    
    # Extraer valores de análisis
    ib_high = analysis.get("ib_high", 0)
    ib_low = analysis.get("ib_low", 0)
    ib_range = analysis.get("ib_range", 0)
    current_price = analysis.get("current_price", closes[-1] if closes else 0)
    day_high = analysis.get("day_high", max(highs) if highs else 0)
    day_low = analysis.get("day_low", min(lows) if lows else 0)
    
    # Volume profile
    vpoc = volume_profile.get("vpoc", 0)
    vah = volume_profile.get("vah", 0)
    val = volume_profile.get("val", 0)
    
    # --- CREAR GRÁFICO ---
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d") if date_str else ""
    
    plt.rcParams["font.family"] = "monospace"
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    
    # Grid
    ax.grid(True, which="major", color="#222222", linestyle="-", linewidth=0.3)
    ax.set_axisbelow(True)
    
    # Título
    ticker_display = ticker.replace("/", "")
    plt.title(
        f"{ticker} Futures | Candlestick Chart | {formatted_date}",
        color="#ffffff",
        fontsize=16,
        fontweight="bold",
        pad=20,
        loc="left",
    )
    
    # Path effects para texto
    txt_outline = [pe.withStroke(linewidth=2, foreground="black")]
    trans = ax.get_yaxis_transform()
    
    # Ancho de vela (en términos de tiempo)
    candle_width = 0.0004  # Ajustar según sea necesario
    
    # Dibujar velas
    for i in range(len(times)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        t = mdates.date2num(times[i])
        
        # Determinar color
        if c >= o:
            body_color = "#00d26a"  # Verde para alcista
            wick_color = "#00d26a"
        else:
            body_color = "#ff4757"  # Rojo para bajista
            wick_color = "#ff4757"
        
        # Dibujar mecha (wick)
        ax.plot([t, t], [l, h], color=wick_color, linewidth=0.8)
        
        # Dibujar cuerpo
        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height == 0:
            body_height = 0.01  # Mínimo visible para doji
        
        rect = Rectangle(
            (t - candle_width / 2, body_bottom),
            candle_width,
            body_height,
            facecolor=body_color,
            edgecolor=wick_color,
            linewidth=0.5,
            alpha=0.9
        )
        ax.add_patch(rect)
    
    # --- IB ZONES ---
    if ib_high > 0 and ib_low > 0:
        ax.axhspan(ib_low, ib_high, color="#ffffff", alpha=0.05, lw=0)
        ax.axhline(ib_high, color="#ffffff", linestyle="--", linewidth=1, alpha=0.6)
        ax.axhline(ib_low, color="#ffffff", linestyle="--", linewidth=1, alpha=0.6)
        
        ax.text(
            0.01, ib_high, f"IB HIGH: {ib_high:.2f}",
            color="#ffffff", fontsize=9, transform=trans,
            va="bottom", ha="left", path_effects=txt_outline, alpha=0.9,
        )
        ax.text(
            0.01, ib_low, f"IB LOW: {ib_low:.2f}",
            color="#ffffff", fontsize=9, transform=trans,
            va="top", ha="left", path_effects=txt_outline, alpha=0.9,
        )
    
    # --- VOLUME PROFILE LEVELS ---
    if vpoc > 0:
        ax.axhline(vpoc, color="#ffd700", linestyle="-", linewidth=1.5, alpha=0.8)
        ax.text(
            0.99, vpoc, f"VPOC: {vpoc:.2f}",
            color="#ffd700", fontsize=9, fontweight="bold", transform=trans,
            va="bottom", ha="right", path_effects=txt_outline,
        )
    
    if vah > 0:
        ax.axhline(vah, color="#4ecdc4", linestyle=":", linewidth=1, alpha=0.7)
        ax.text(
            0.99, vah, f"VAH: {vah:.2f}",
            color="#4ecdc4", fontsize=8, transform=trans,
            va="bottom", ha="right", path_effects=txt_outline,
        )
    
    if val > 0:
        ax.axhline(val, color="#ff6b6b", linestyle=":", linewidth=1, alpha=0.7)
        ax.text(
            0.99, val, f"VAL: {val:.2f}",
            color="#ff6b6b", fontsize=8, transform=trans,
            va="top", ha="right", path_effects=txt_outline,
        )
    
    # --- FIBONACCI EXTENSIONS ---
    if ib_range > 0:
        colors_fib = ["#ffc107", "#ff9800", "#ff5722"]
        
        if current_price > ib_high:
            exts = [1.272, 1.618, 2.0]
            for i, ext in enumerate(exts):
                fib_level = ib_low + (ib_range * ext)
                if fib_level <= day_high * 1.02:  # Solo mostrar si está cerca del rango
                    ax.axhline(fib_level, color=colors_fib[i], linestyle=":", linewidth=1, alpha=0.7)
                    ax.text(
                        0.01, fib_level, f"FIB {ext}: {fib_level:.2f}",
                        color=colors_fib[i], fontsize=8, transform=trans,
                        va="bottom", ha="left", path_effects=txt_outline,
                    )
        elif current_price < ib_low:
            exts = [-0.272, -0.618, -1.0]
            for i, ext in enumerate(exts):
                fib_level = ib_low + (ib_range * ext)
                if fib_level >= day_low * 0.98:
                    ax.axhline(fib_level, color=colors_fib[i], linestyle=":", linewidth=1, alpha=0.7)
                    ax.text(
                        0.01, fib_level, f"FIB {ext}: {fib_level:.2f}",
                        color=colors_fib[i], fontsize=8, transform=trans,
                        va="top", ha="left", path_effects=txt_outline,
                    )
    
    # --- CURRENT PRICE MARKER ---
    ax.axhline(current_price, color="#00bfff", linestyle="-", linewidth=1.5, alpha=0.8)
    ax.text(
        0.99, current_price, f"LAST: {current_price:.2f}",
        color="#00bfff", fontsize=10, fontweight="bold", transform=trans,
        va="center", ha="right", path_effects=txt_outline,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#0a0a0a", edgecolor="#00bfff", alpha=0.8)
    )
    
    # --- EJES ---
    # Límites de tiempo
    if times:
        base_date = times[0].date()
        start_plot = datetime.combine(base_date, dt_time(9, 25))
        end_plot = datetime.combine(base_date, dt_time(16, 5))
        if NY_TZ:
            start_plot = start_plot.replace(tzinfo=NY_TZ)
            end_plot = end_plot.replace(tzinfo=NY_TZ)
        ax.set_xlim(start_plot, end_plot)
    
    # Formatear eje X
    if NY_TZ:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=NY_TZ))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[15, 30, 45]))
    
    # Límites de precio con padding
    price_range = day_high - day_low
    y_padding = price_range * 0.05
    ax.set_ylim(day_low - y_padding, day_high + y_padding)
    
    # Estilo de ejes
    ax.tick_params(axis="x", colors="#888888", rotation=0, labelsize=9)
    ax.tick_params(axis="y", colors="#888888", labelsize=9)
    ax.spines["bottom"].set_color("#333333")
    ax.spines["left"].set_color("#333333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    # Etiquetas
    ax.set_xlabel("Time (ET)", color="#888888", fontsize=10)
    ax.set_ylabel("Price", color="#888888", fontsize=10)
    
    # --- INFO BOX ---
    info_text = (
        f"Open: {opens[0]:.2f}  High: {day_high:.2f}\n"
        f"Low: {day_low:.2f}  Close: {current_price:.2f}\n"
        f"IB Range: {ib_range:.2f}"
    )
    ax.text(
        0.99, 0.02, info_text,
        transform=ax.transAxes, fontsize=9, color="#cccccc",
        verticalalignment="bottom", horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a1a1a", edgecolor="#333333", alpha=0.9),
        family="monospace"
    )
    
    # Ajustar layout y guardar
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor="#0a0a0a", edgecolor="none", bbox_inches="tight")
    plt.close()
    
    return True


def process_all_json_files():
    """Procesa todos los archivos JSON de futuros y genera gráficos PNG."""
    
    # Buscar archivos JSON de ES y NQ
    pattern = os.path.join(INPUT_DIR, "ib_data_*_*.json")
    json_files = glob.glob(pattern)
    
    # Filtrar solo ES y NQ
    futures_files = [f for f in json_files if "_ES_" in f or "_NQ_" in f]
    
    if not futures_files:
        print(f"[ERROR] No se encontraron archivos JSON de futuros en {INPUT_DIR}")
        print(f"        Patrón buscado: ib_data_ES_*.json, ib_data_NQ_*.json")
        return
    
    print(f"\n{'='*60}")
    print(f"FUTURES PLOT GENERATOR")
    print(f"{'='*60}")
    print(f"Archivos encontrados: {len(futures_files)}")
    print(f"Input: {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")
    
    success_count = 0
    
    for filepath in sorted(futures_files):
        filename = os.path.basename(filepath)
        print(f"[PROCESSING] {filename}...")
        
        # Cargar JSON
        json_data = load_json_data(filepath)
        if not json_data:
            print(f"  [SKIP] No se pudo cargar")
            continue
        
        # Generar nombre de salida
        # ib_data_ES_20260129.json -> ES_20260129.png
        parts = filename.replace("ib_data_", "").replace(".json", "")
        output_filename = f"{parts}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # Verificar si ya existe
        if os.path.exists(output_path):
            print(f"  [SKIP] Ya existe: {output_filename}")
            success_count += 1
            continue
        
        # Generar gráfico
        if plot_candlestick_chart(json_data, output_path):
            print(f"  [SAVED] {output_filename}")
            success_count += 1
        else:
            print(f"  [FAILED] No se pudo generar")
    
    print(f"\n{'='*60}")
    print(f"COMPLETADO: {success_count}/{len(futures_files)} gráficos generados")
    print(f"Directorio: {OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        process_all_json_files()
    except KeyboardInterrupt:
        print("\n[STOP] Detenido por usuario.")
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
