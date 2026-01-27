"""
Backtest Plot Generator

Genera gráficos visuales de los trades ejecutados en el backtest:
- Velas de 1 minuto por día y ticker
- Marcas de entrada/salida de trades
- Niveles de S/R durante cada trade
- Perfil de volumen usado en la sesión

Uso: 
    python plot_backtest.py                    # Default: backtest trades
    python plot_backtest.py --source backtest  # Backtest trades
    python plot_backtest.py --source bot1      # TradingBot1 live trades
    python plot_backtest.py --source bot2      # TradingBot2 live trades
    python plot_backtest.py --source all       # All sources combined
"""

import os
import sys
import json
import glob
import re
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

# Script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Directorios
IB_DATA_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"
PLOTS_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "plots")

# Trade directories by source
TRADES_DIRS = {
    "backtest": os.path.join(SCRIPT_DIR, "trades"),
    "bot1": os.path.join(PROJECT_ROOT, "bots", "trades_live"),
    "bot2": os.path.join(PROJECT_ROOT, "bots", "trades_live2"),
}

# Tickers a procesar
TICKERS = ["SPX", "SPY", "QQQ"]

# Colores para niveles
LEVEL_COLORS = {
    "ib_high": "#FF6B6B",      # Rojo claro
    "ib_low": "#4ECDC4",       # Cyan
    "resistance": "#FF4757",    # Rojo
    "support": "#2ED573",       # Verde
    "min_vanna": "#9B59B6",     # Púrpura
    "vp_vpoc": "#F39C12",       # Naranja
    "vp_vah": "#E74C3C",        # Rojo oscuro
    "vp_val": "#27AE60",        # Verde oscuro
    "fib": "#95A5A6",           # Gris
    "gamma": "#3498DB",         # Azul
    "dgex": "#E91E63",          # Rosa
}


def load_candle_data(ticker: str, date_str: str) -> list:
    """Carga datos de velas de ib_backtest para un ticker y fecha."""
    filepath = os.path.join(IB_DATA_DIR, f"ib_data_{ticker}_{date_str}.json")
    
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data.get("series", [])
    except Exception as e:
        print(f"[ERROR] Loading {filepath}: {e}")
        return []


def load_volume_profile(ticker: str, date_str: str) -> dict:
    """Carga perfil de volumen de ib_backtest."""
    filepath = os.path.join(IB_DATA_DIR, f"ib_data_{ticker}_{date_str}.json")
    
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data.get("volume_profile", {})
    except:
        return {}


def load_trades_for_day(date_str: str, trade_dirs: list) -> list:
    """Carga todos los trades para un día específico desde múltiples directorios."""
    trades = []
    
    for trades_dir in trade_dirs:
        if not os.path.exists(trades_dir):
            continue
            
        # Buscar trades con diferentes patrones de nombre
        patterns = [
            os.path.join(trades_dir, f"trade_*_{date_str[:8]}*.json"),
            os.path.join(trades_dir, f"live_trade_*_{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}*.json"),
            os.path.join(trades_dir, "*.json"),  # Fallback
        ]
        
        files_found = set()
        for pattern in patterns:
            files_found.update(glob.glob(pattern))
        
        for filepath in files_found:
            try:
                with open(filepath, 'r') as f:
                    trade = json.load(f)
                
                # Verificar que el trade es del día correcto
                entry_time = trade.get("entry", {}).get("time", "")
                if date_str in entry_time.replace("-", ""):
                    # Añadir source info para identificar origen
                    if "trades_live2" in trades_dir:
                        trade["_source"] = "bot2"
                    elif "trades_live" in trades_dir:
                        trade["_source"] = "bot1"
                    else:
                        trade["_source"] = "backtest"
                    trades.append(trade)
            except Exception as e:
                continue
    
    return trades


def parse_time_to_minutes(time_str: str) -> int:
    """Convierte HH:MM a minutos desde medianoche."""
    try:
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except:
        return 0


def plot_candles_with_trades(ticker: str, date_str: str, candles: list, trades: list, output_path: str):
    """
    Genera gráfico de velas con trades marcados.
    """
    if not candles:
        print(f"  [SKIP] No candles for {ticker} {date_str}")
        return
    
    # Filtrar trades para este ticker
    ticker_trades = [t for t in trades if t.get("ticker") == ticker]
    
    # Preparar datos de velas
    times = []
    opens = []
    highs = []
    lows = []
    closes = []
    
    for candle in candles:
        time_str = candle.get("time", "")
        times.append(time_str)
        opens.append(candle.get("open", candle.get("price", 0)))
        highs.append(candle.get("high", candle.get("price", 0)))
        lows.append(candle.get("low", candle.get("price", 0)))
        closes.append(candle.get("close", candle.get("price", 0)))
    
    if not times:
        return
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(20, 10))
    
    # Plotear velas
    x_positions = list(range(len(times)))
    
    for i in range(len(times)):
        color = "green" if closes[i] >= opens[i] else "red"
        
        # Mecha
        ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.5)
        
        # Cuerpo
        body_bottom = min(opens[i], closes[i])
        body_height = abs(closes[i] - opens[i])
        rect = plt.Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                              facecolor=color, edgecolor=color, alpha=0.8)
        ax.add_patch(rect)
    
    # Crear mapeo tiempo -> índice
    time_to_idx = {t: i for i, t in enumerate(times)}
    
    # Plotear trades
    for trade in ticker_trades:
        entry_time = trade.get("entry", {}).get("time", "")
        exit_time = trade.get("exit", {}).get("time", "")
        entry_price = trade.get("entry", {}).get("price", 0)
        exit_price = trade.get("exit", {}).get("price", 0)
        direction = trade.get("direction", "")
        
        # Extraer HH:MM de la entrada
        entry_hhmm = entry_time.split(" ")[-1][:5] if " " in entry_time else entry_time[:5]
        exit_hhmm = exit_time.split(" ")[-1][:5] if exit_time and " " in exit_time else (exit_time[:5] if exit_time else "")
        
        entry_idx = time_to_idx.get(entry_hhmm)
        exit_idx = time_to_idx.get(exit_hhmm)
        
        # Colores según dirección
        # LONG: verde O entrada, rojo C salida
        # SHORT: rojo O entrada, verde C salida
        if direction == "LONG":
            entry_color = "green"
            exit_color = "red"
        else:  # SHORT
            entry_color = "red"
            exit_color = "green"
        
        # Marcar entrada
        if entry_idx is not None:
            ax.scatter(entry_idx, entry_price, color=entry_color, s=150, zorder=10, marker='o')
            ax.annotate('O', (entry_idx, entry_price), fontsize=8, fontweight='bold',
                       ha='center', va='center', color='white', zorder=11)
        
        # Marcar salida
        if exit_idx is not None and exit_price:
            ax.scatter(exit_idx, exit_price, color=exit_color, s=150, zorder=10, marker='o')
            ax.annotate('C', (exit_idx, exit_price), fontsize=8, fontweight='bold',
                       ha='center', va='center', color='white', zorder=11)
        
        # Dibujar niveles durante el trade
        if entry_idx is not None and exit_idx is not None:
            draw_trade_levels(ax, trade, entry_idx, exit_idx)
    
    # Configurar ejes
    ax.set_xlim(-1, len(times))
    
    # Etiquetas del eje X (cada 30 minutos)
    tick_positions = list(range(0, len(times), 30))
    tick_labels = [times[i] if i < len(times) else "" for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45)
    
    # Título y etiquetas
    ax.set_title(f"{ticker} - {date_str} | Trades: {len(ticker_trades)}", fontsize=14, fontweight='bold')
    ax.set_xlabel("Time (NYC)")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)
    
    # Leyenda
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10, label='LONG Entry / SHORT Exit'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='SHORT Entry / LONG Exit'),
        Line2D([0], [0], color=LEVEL_COLORS["resistance"], linewidth=2, label='Resistance'),
        Line2D([0], [0], color=LEVEL_COLORS["support"], linewidth=2, label='Support'),
        Line2D([0], [0], color=LEVEL_COLORS["min_vanna"], linewidth=2, linestyle='--', label='Min Vanna'),
        Line2D([0], [0], color=LEVEL_COLORS["vp_vpoc"], linewidth=2, linestyle=':', label='VP POC'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  [SAVED] {output_path}")


def draw_trade_levels(ax, trade: dict, start_idx: int, end_idx: int):
    """Dibuja líneas horizontales para los niveles que el trade está siguiendo."""
    signals = trade.get("signals", {})
    levels = trade.get("levels", {})
    
    # Resistencia
    resistance = signals.get("nearest_resistance")
    if resistance and resistance > 0:
        ax.hlines(y=resistance, xmin=start_idx, xmax=end_idx, 
                 colors=LEVEL_COLORS["resistance"], linewidth=1.5, linestyles='-', alpha=0.7)
    
    # Soporte
    support = signals.get("nearest_support")
    if support and support > 0:
        ax.hlines(y=support, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["support"], linewidth=1.5, linestyles='-', alpha=0.7)
    
    # Min Vanna
    min_vanna = signals.get("min_vanna_magnet") or levels.get("min_vanna_strike")
    if min_vanna and min_vanna > 0:
        ax.hlines(y=min_vanna, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["min_vanna"], linewidth=1.5, linestyles='--', alpha=0.7)
    
    # IB High Today
    ib_high = levels.get("ib_high_today")
    if ib_high and ib_high > 0:
        ax.hlines(y=ib_high, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["ib_high"], linewidth=1, linestyles='-', alpha=0.5)
    
    # IB Low Today
    ib_low = levels.get("ib_low_today")
    if ib_low and ib_low > 0:
        ax.hlines(y=ib_low, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["ib_low"], linewidth=1, linestyles='-', alpha=0.5)
    
    # VPOC
    vpoc = levels.get("vp_vpoc")
    if vpoc and vpoc > 0:
        ax.hlines(y=vpoc, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["vp_vpoc"], linewidth=1.5, linestyles=':', alpha=0.7)
    
    # VAH
    vah = levels.get("vp_vah")
    if vah and vah > 0:
        ax.hlines(y=vah, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["vp_vah"], linewidth=1, linestyles=':', alpha=0.5)
    
    # VAL
    val = levels.get("vp_val")
    if val and val > 0:
        ax.hlines(y=val, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["vp_val"], linewidth=1, linestyles=':', alpha=0.5)
    
    # Max Gamma
    max_gamma = levels.get("max_gamma_strike")
    if max_gamma and max_gamma > 0:
        ax.hlines(y=max_gamma, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["gamma"], linewidth=1, linestyles='-.', alpha=0.5)
    
    # DGEX Magnet
    dgex = signals.get("dgex_magnet")
    if dgex and dgex > 0:
        ax.hlines(y=dgex, xmin=start_idx, xmax=end_idx,
                 colors=LEVEL_COLORS["dgex"], linewidth=1, linestyles='-.', alpha=0.5)


def plot_volume_profile(ticker: str, date_str: str, vp_data: dict, output_path: str):
    """
    Genera gráfico del perfil de volumen.
    """
    if not vp_data:
        return
    
    profile = vp_data.get("profile", [])
    if not profile:
        return
    
    vpoc = vp_data.get("vpoc", 0)
    vah = vp_data.get("vah", 0)
    val = vp_data.get("val", 0)
    
    # Preparar datos
    prices = [p.get("price", 0) for p in profile]
    volumes = [p.get("volume", 0) for p in profile]
    
    if not prices or not volumes:
        return
    
    # Crear figura horizontal (volume profile típico)
    fig, ax = plt.subplots(figsize=(10, 12))
    
    # Colores: azul normal, destacar área de valor
    colors = []
    for price in prices:
        if val <= price <= vah:
            colors.append("#3498DB")  # Azul para Value Area
        else:
            colors.append("#BDC3C7")  # Gris fuera
    
    # Plot horizontal
    ax.barh(prices, volumes, height=(prices[1] - prices[0]) * 0.9 if len(prices) > 1 else 1,
            color=colors, edgecolor='none', alpha=0.8)
    
    # Marcar niveles clave
    if vpoc:
        ax.axhline(y=vpoc, color=LEVEL_COLORS["vp_vpoc"], linewidth=2, linestyle='-', label=f'VPOC: {vpoc:.2f}')
    if vah:
        ax.axhline(y=vah, color=LEVEL_COLORS["vp_vah"], linewidth=1.5, linestyle='--', label=f'VAH: {vah:.2f}')
    if val:
        ax.axhline(y=val, color=LEVEL_COLORS["vp_val"], linewidth=1.5, linestyle='--', label=f'VAL: {val:.2f}')
    
    # LVN zones
    lvn_zones = vp_data.get("lvn_zones", [])
    for zone in lvn_zones:
        zone_low = zone.get("low", 0)
        zone_high = zone.get("high", 0)
        if zone_low and zone_high:
            ax.axhspan(zone_low, zone_high, alpha=0.2, color='red', label='LVN Zone' if zone == lvn_zones[0] else '')
    
    # Configuración
    ax.set_title(f"Volume Profile - {ticker} {date_str}", fontsize=14, fontweight='bold')
    ax.set_xlabel("Volume")
    ax.set_ylabel("Price")
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  [SAVED] {output_path}")


def get_available_dates() -> list:
    """Obtiene las fechas disponibles en ib_backtest."""
    dates = set()
    
    pattern = os.path.join(IB_DATA_DIR, "ib_data_*.json")
    files = glob.glob(pattern)
    
    for filepath in files:
        basename = os.path.basename(filepath)
        match = re.search(r"ib_data_\w+_(\d{8})\.json", basename)
        if match:
            dates.add(match.group(1))
    
    return sorted(dates)


def main():
    """Punto de entrada principal."""
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Genera gráficos visuales de trades ejecutados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python plot_backtest.py                    # Usa trades del backtest
  python plot_backtest.py --source bot1      # Usa trades de TradingBot1
  python plot_backtest.py --source bot2      # Usa trades de TradingBot2
  python plot_backtest.py --source all       # Combina todas las fuentes
        """
    )
    parser.add_argument(
        "--source", "-s",
        choices=["backtest", "bot1", "bot2", "all"],
        default="backtest",
        help="Fuente de trades a plotear (default: backtest)"
    )
    parser.add_argument(
        "--date", "-d",
        type=str,
        default=None,
        help="Fecha específica a plotear (formato: YYYYMMDD)"
    )
    args = parser.parse_args()
    
    # Determinar directorios de trades según source
    if args.source == "all":
        trade_dirs = list(TRADES_DIRS.values())
        source_name = "ALL SOURCES"
    else:
        trade_dirs = [TRADES_DIRS[args.source]]
        source_name = args.source.upper()
    
    # Crear directorio de output
    if not os.path.exists(PLOTS_OUTPUT_DIR):
        os.makedirs(PLOTS_OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("TRADE PLOT GENERATOR")
    print("=" * 60)
    print(f"Source: {source_name}")
    print(f"Trade Dirs: {trade_dirs}")
    print(f"IB Data: {IB_DATA_DIR}")
    print(f"Output: {PLOTS_OUTPUT_DIR}")
    print("=" * 60)
    
    # Obtener fechas disponibles
    if args.date:
        dates = [args.date]
    else:
        dates = get_available_dates()
    
    if not dates:
        print("[ERROR] No IB data found!")
        return
    
    print(f"\nFechas a procesar: {len(dates)}")
    if len(dates) > 1:
        print(f"Rango: {dates[0]} - {dates[-1]}")
    
    total_trades = 0
    
    for date_str in dates:
        print(f"\n[{date_str}] Procesando...")
        
        # Cargar trades del día desde los directorios seleccionados
        trades = load_trades_for_day(date_str, trade_dirs)
        total_trades += len(trades)
        
        # Mostrar breakdown por source
        sources = {}
        for t in trades:
            src = t.get("_source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        
        source_info = ", ".join([f"{k}:{v}" for k, v in sources.items()]) if sources else "ninguno"
        print(f"  Trades encontrados: {len(trades)} ({source_info})")
        
        for ticker in TICKERS:
            # Cargar datos de velas
            candles = load_candle_data(ticker, date_str)
            
            if not candles:
                print(f"  [{ticker}] Sin datos de velas")
                continue
            
            # Filtrar trades por ticker
            ticker_trades = [t for t in trades if t.get("ticker") == ticker]
            if not ticker_trades:
                continue
                
            print(f"  [{ticker}] {len(candles)} velas, {len(ticker_trades)} trades")
            
            # Generar gráfico de velas con trades
            candles_output = os.path.join(PLOTS_OUTPUT_DIR, f"candles_{ticker}_{date_str}_{args.source}.png")
            plot_candles_with_trades(ticker, date_str, candles, trades, candles_output)
            
            # Generar perfil de volumen
            vp_data = load_volume_profile(ticker, date_str)
            if vp_data:
                vp_output = os.path.join(PLOTS_OUTPUT_DIR, f"volume_profile_{ticker}_{date_str}.png")
                plot_volume_profile(ticker, date_str, vp_data, vp_output)
    
    print("\n" + "=" * 60)
    print(f"COMPLETADO - {total_trades} trades procesados")
    print(f"Gráficos guardados en {PLOTS_OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
