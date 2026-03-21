import sys
import os

# Add project root to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import time
import json
import pandas as pd
from pandas.tseries.offsets import BDay
import numpy as np
import matplotlib

matplotlib.use("Agg")  # Backend no interactivo (Vital para Multithreading)
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import math
import orjson
import modules.stats as stats
from modules.tasty_handler import tasty_data, tasty_expirations_strikes
from modules.ticker_dwn import dwn_data
from modules.utils import *
from tastytrade import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from os import getcwd, makedirs, path, getenv
import datetime
from dotenv import load_dotenv
import calendar
import pickle
import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import pandas_market_calendars as mcal
from zoneinfo import ZoneInfo
import datetime

# Inicializar el calendario globalmente para no sobrecargar la memoria
NYSE_CALENDAR = mcal.get_calendar('NYSE')

def is_market_open(check_date) -> bool:
    """Verifica si el NYSE está abierto en una fecha específica."""
    schedule = NYSE_CALENDAR.schedule(start_date=check_date, end_date=check_date)
    return not schedule.empty
# --- CONFIGURACIÓN DE ESTILOS (TAMAÑOS AUMENTADOS Y ALTO CONTRASTE) ---
STYLE_CONFIG = {
    "title_size": 26,
    "label_size": 22,
    "tick_size": 18,
    "legend_size": 16,
    "linewidth": 2.5,
    "grid_width": 0.8,
    "grid_alpha": 0.4,
    "color_text": "#ffffff",
    "color_grid": "#666666",
    "color_bg": "black",
}


def apply_custom_style(ax, fig, title, xlabel, ylabel):
    """Aplica manualmente los estilos configurados sobre objetos privados"""
    c = STYLE_CONFIG

    # Fondos
    fig.patch.set_facecolor(c["color_bg"])
    ax.set_facecolor(c["color_bg"])

    # Títulos y Etiquetas
    ax.set_title(
        title.replace("<br>", " "),
        color=c["color_text"],
        fontsize=c["title_size"],
        pad=25,
    )
    ax.set_xlabel(xlabel, color=c["color_text"], fontsize=c["label_size"], labelpad=20)
    ax.set_ylabel(ylabel, color=c["color_text"], fontsize=c["label_size"], labelpad=20)

    # Ejes (Ticks)
    ax.tick_params(
        axis="x", colors=c["color_text"], labelsize=c["tick_size"], width=2, length=8
    )
    ax.tick_params(
        axis="y", colors=c["color_text"], labelsize=c["tick_size"], width=2, length=8
    )

    # Bordes (Spines)
    for spine in ax.spines.values():
        spine.set_edgecolor(c["color_text"])
        spine.set_linewidth(2)

    # Grid (Cuadrícula)
    ax.grid(
        True,
        color=c["color_grid"],
        linestyle="-",
        linewidth=c["grid_width"],
        alpha=c["grid_alpha"],
    )


# ==============================================================================
# FUNCIONES WORKER PARA PROCESSPOOL - DEBEN ESTAR EN NIVEL DE MÓDULO
# ==============================================================================

def _merge_alert_states(states_list):
    """
    Merge inteligente de múltiples alert_states.
    Estrategia: El último estado válido gana (asumiendo que es el más reciente).
    """
    if not states_list:
        return {}
    
    # Filtrar estados vacíos
    valid_states = [s for s in states_list if s]
    if not valid_states:
        return {}
    
    # Tomar el último estado no vacío (es el más reciente)
    # Si hay conflictos, el último worker en terminar tiene prioridad
    merged = {}
    for state in valid_states:
        merged.update(state)
    
    return merged


def _plot_single_table_worker(args):
    """
    Worker function para plotear una sola tabla en un proceso separado.
    Recibe todos los datos serializados necesarios.
    """
    try:
        (
            pivot_table_dict,
            ticker,
            value,
            today_ddt_string,
            greek,
            exp,
            timestamp,
            spot_price,
            strikes,
            expirations,
            agg_by_strike_dict,
            alert_state,
            rising_strike,
            falling_strike,
            flip_val,
            metric_name,  # NUEVO: para identificar qué pickle actualizar
        ) = args

        # Reconstruir objetos pandas desde diccionarios
        pivot_table = pd.DataFrame(
            pivot_table_dict["data"],
            index=pivot_table_dict["index"],
            columns=pivot_table_dict["columns"],
        )
        agg_by_strike = pd.Series(
            agg_by_strike_dict["data"], index=agg_by_strike_dict["index"]
        )

        name = greek.capitalize()
        PLOT_DIR = "plots"

        # Colores (Originales)
        colors_list = [
            (0.00, (0.7, 0.0, 0.8)),
            (0.15, (0.25, 0.0, 0.35)),
            (0.49, (0.25, 0.0, 0.35)),
            (0.50, (0.1, 0.1, 0.15)),
            (0.51, (0.0, 0.4, 0.5)),
            (0.85, (0.0, 0.4, 0.5)),
            (1.00, (1.0, 0.9, 0.0)),
        ]
        custom_cmap = mcolors.LinearSegmentedColormap.from_list(
            "custom_cmap", colors_list
        )

        alerts = []

        # --- VISUALIZACIÓN TABLA (ALTA RESOLUCIÓN) ---
        fig = Figure(figsize=(16, 32))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        # Estilo Heatmap
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")
        ax.set_title(
            f"{ticker} {value} Heatmap, {today_ddt_string}",
            color="white",
            fontsize=STYLE_CONFIG["title_size"],
            pad=30,
        )
        ax.set_xlabel(
            "Expiration Date",
            color="white",
            fontsize=STYLE_CONFIG["label_size"],
            labelpad=20,
        )
        ax.set_ylabel(
            "Strike Price",
            color="white",
            fontsize=STYLE_CONFIG["label_size"],
            labelpad=20,
        )
        ax.tick_params(colors="white", labelsize=STYLE_CONFIG["tick_size"])
        for spine in ax.spines.values():
            spine.set_edgecolor("white")

        # Normalización y Plot
        V_min = pivot_table.min().min()
        V_max = pivot_table.max().max()
        if V_max <= 0:
            V_max = 1
        if V_min >= 0:
            V_min = -1

        im = ax.imshow(
            pivot_table.values,
            cmap=custom_cmap,
            aspect="auto",
            norm=mcolors.TwoSlopeNorm(vmin=V_min * 0.85, vcenter=0, vmax=V_max * 0.85),
        )

        # Textos en celdas (Grandes)
        for i in range(len(strikes)):
            for j in range(len(expirations)):
                value2text = pivot_table.values[i, j]
                if not np.isnan(value2text):
                    text_color = "white" if value2text <= 0 else "black"
                    text_str = (
                        f"$ {value2text*100000:,.2f}k"
                        if value2text % 1 != 0
                        else f"$ {int(value2text)*100000:,d}k"
                    )
                    ax.text(
                        j,
                        i,
                        text_str,
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=11,
                    )

        # Ejes
        expiration_labels = [
            d.strftime("%b %d") if hasattr(d, "strftime") else str(d)
            for d in expirations
        ]
        ax.set_xticks(np.arange(len(expirations)))
        ax.set_xticklabels(expiration_labels, rotation=0, ha="center")
        ax.set_yticks(np.arange(len(strikes)))
        ax.set_yticklabels([f"{int(s)}" for s in strikes])

        # Helper índice Y
        def get_y(val):
            return np.abs(np.array(strikes) - val).argmin()

        # 1. Spot
        spot_idx = get_y(spot_price)
        ax.axhline(
            y=spot_idx,
            color="white",
            linestyle="--",
            linewidth=2,
            label=f"Spot: {spot_price:.2f}",
        )

        # 2. Max Pos/Neg con lógica de PINNED ALERT
        max_pos = agg_by_strike.idxmax()
        max_neg = agg_by_strike.idxmin()

        # --- PINNED POSITIVE ---
        if not pd.isna(max_pos):
            max_pos_idx = get_y(max_pos)
            ax.axhline(
                y=max_pos_idx,
                color="lime",
                linestyle="--",
                linewidth=2.5,
                label=f"Max Pos: {max_pos:.0f}",
            )

            if spot_idx == max_pos_idx and exp == "0dte":
                current_pinned = float(max_pos)
                if current_pinned != alert_state.get("pos_pinned"):
                    msg = f"**{ticker} {name} ALERT**: Price is pinned at Max Positive {name} Strike: {max_pos:.2f}"
                    alerts.append(msg)
                    alert_state["pos_pinned"] = current_pinned
            else:
                if "pos_pinned" in alert_state:
                    del alert_state["pos_pinned"]

        # --- PINNED NEGATIVE ---
        if not pd.isna(max_neg):
            max_neg_idx = get_y(max_neg)
            ax.axhline(
                y=max_neg_idx,
                color="red",
                linestyle="--",
                linewidth=2.5,
                label=f"Max Neg: {max_neg:.0f}",
            )

            if spot_idx == max_neg_idx and exp == "0dte":
                current_pinned = float(max_neg)
                if current_pinned != alert_state.get("neg_pinned"):
                    msg = f"**{ticker} {name} ALERT**: Price is pinned at Max Negative {name} Strike: {max_neg:.2f}"
                    alerts.append(msg)
                    alert_state["neg_pinned"] = current_pinned
            else:
                if "neg_pinned" in alert_state:
                    del alert_state["neg_pinned"]

        # 3. Rising/Falling (Lineas)
        if rising_strike:
            ax.axhline(
                y=get_y(rising_strike),
                color="cyan",
                linestyle=":",
                linewidth=3,
                label=f"Rising: {rising_strike:.0f}",
            )
        if falling_strike:
            ax.axhline(
                y=get_y(falling_strike),
                color="orange",
                linestyle=":",
                linewidth=3,
                label=f"Falling: {falling_strike:.0f}",
            )

        # 4. Flip
        if flip_val:
            ax.axhline(
                y=get_y(flip_val),
                color="cyan",
                linestyle="--",
                linewidth=2,
                label=f"Flip: {flip_val:.2f}",
            )

        net_val = agg_by_strike.sum() * 100
        ax.plot([], [], " ", label=f"Net {name}: {net_val:,.2f}")

        # Leyenda: Fondo NEGRO, Texto BLANCO
        legend = ax.legend(
            loc="upper right",
            facecolor="black",
            edgecolor="white",
            fontsize=STYLE_CONFIG["legend_size"],
        )
        for text in legend.get_texts():
            text.set_color("white")

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(
            f"{name} Exposure",
            color="white",
            fontsize=STYLE_CONFIG["label_size"],
        )
        tick_vals = [V_min * 0.8, 0, V_max * 0.8]
        cbar.set_ticks(tick_vals)
        cbar.ax.set_yticklabels(
            [f"{x:.2f}" if abs(x) < 1 else f"{int(x)}" for x in tick_vals]
        )
        cbar.ax.yaxis.set_tick_params(
            color="white",
            labelcolor="white",
            labelsize=STYLE_CONFIG["tick_size"],
        )

        filename = f"{PLOT_DIR}/{ticker}/{exp}/{greek}/{value.replace(' ', '_')}_Heatmap/{timestamp}.png"
        makedirs(path.dirname(filename), exist_ok=True)
        fig.savefig(filename, bbox_inches="tight", facecolor="black", dpi=80)
        plt.close(fig)

        # NUEVO: Retornar información completa para sincronización
        return {
            "filename": filename,
            "alerts": alerts,
            "alert_state": alert_state,
            "ticker": ticker,
            "exp": exp,
            "greek": greek,
        }

    except Exception as e:
        print(f"[ERROR TABLE WORKER]: {e}")
        import traceback

        traceback.print_exc()
        return {
            "filename": None,
            "alerts": [],
            "alert_state": {},
            "ticker": None,
            "exp": None,
            "greek": None,
        }


def _plot_single_histogram_worker(args):
    """
    Worker function para plotear un solo histograma en un proceso separado.
    """
    try:
        (
            df_agg_dict,
            ticker,
            value,
            today_ddt_string,
            greek,
            exp,
            timestamp,
            spot_price,
            lower_bound,
            upper_bound,
            step,
            colors,
            call_ivs_data,
            put_ivs_data,
            rising_strike,
            falling_strike,
            zero_strike,
            prev_close_price,
            date_condition,
        ) = args

        # Reconstruir DataFrame
        df_agg = pd.DataFrame(
            df_agg_dict["data"],
            index=df_agg_dict["index"],
            columns=df_agg_dict["columns"],
        )

        name = value.split()[1] if "Absolute" in value else value.split()[0]
        PLOT_DIR = "plots"
        alerts = []

        # --- ETIQUETA EJE Y DINÁMICA ---
        ylabel_text = f"{name} Exposure"
        if name == "Gamma":
            ylabel_text += " (gamma / 1% move)"
        elif name == "Delta":
            ylabel_text += " (delta / 1% move)"
        elif name == "Vanna":
            ylabel_text += " (vanna / 1% IV move)"
        elif name == "Charm":
            ylabel_text += " (charm / day)"
        elif name == "Zomma":
            ylabel_text += " (zomma / 1% IV move)"
        elif name == "Dgex":
            ylabel_text += " (dgex / 1% move)"
        elif name == "Speed":
            ylabel_text += " (speed / 1% move)"

        # --- FIGURE PRIVADO ---
        fig = Figure(figsize=(20, 12))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        title = f"{ticker} {value}, {today_ddt_string} for {exp}"
        apply_custom_style(
            ax, fig, title, "Strike" if date_condition else "Date", ylabel_text
        )

        # ==========================================================
        # BLOQUE: ABSOLUTE EXPOSURE
        # ==========================================================
        if "Absolute" in value:
            agg_by_strike = df_agg[f"total_{name.lower()}"]

            # --- LÓGICA REGIME ANALYSIS ---
            if greek == "gamma" and ticker == "SPX" and exp == "0dte":
                net_gamma_val = agg_by_strike.sum()  # Ya está en la escala correcta
                current_spot = spot_price
                flip_status = "ABOVE" if current_spot > zero_strike else "BELOW"

                msg = f"__** {ticker} {exp.upper()} REGIME ANALYSIS**__\n"
                msg += f"• **Spot:** {current_spot:.2f} | **Gamma Flip:** {zero_strike:.2f} (Spot is {flip_status})\n"

                if net_gamma_val > 0:
                    regime_name = "POSITIVE GAMMA (Mean Reversion)"
                    behavior = "Dealers buy dips & sell rips. Market is sticky."
                    if current_spot > zero_strike:
                        trade_idea = "**Bullish Bias:** Look to **Buy Dips**"
                    else:
                        trade_idea = "**Cautious:** Spot below Flip but Gamma is positive. Upside capped"
                else:
                    regime_name = "NEGATIVE GAMMA (Directional/Volatile)"
                    behavior = "Dealers sell dips & buy rips. Volatility accelerates."
                    if current_spot < zero_strike:
                        trade_idea = "**Bearish Bias:** **SELL THE RIP**. Volatility expansion likely down"
                    else:
                        trade_idea = "**Breakout Watch:** Spot above Flip in Neg Gamma. Squeeze risk up"

                msg += f"• **Regime:** {regime_name}\n"
                msg += f"• **Behavior:** *{behavior}*\n"
                msg += f"• **Trade Bias:** {trade_idea}\n"

                alerts.append(msg)

            max_pos = agg_by_strike.idxmax()
            max_neg = agg_by_strike.idxmin()

            ax.bar(
                df_agg.index,
                agg_by_strike,
                align="edge",
                width=step * 0.9,
                label=f"{name} Exposure",
                alpha=0.9,
                color=colors["total"],
            )

            if not pd.isna(max_pos):
                ax.axvline(
                    x=max_pos,
                    color="lime",
                    linestyle="--",
                    linewidth=2,
                    label=f"Max Pos: {max_pos:.2f}",
                )
            if not pd.isna(max_neg):
                ax.axvline(
                    x=max_neg,
                    color="red",
                    linestyle="--",
                    linewidth=2,
                    label=f"Max Neg: {max_neg:.2f}",
                )

            if rising_strike:
                ax.axvline(
                    x=rising_strike,
                    dashes=(5, 12),
                    color="cyan",
                    linestyle="--",
                    linewidth=3,
                    label=f"Rising: {rising_strike:.0f}",
                )
            if falling_strike:
                ax.axvline(
                    x=falling_strike,
                    dashes=(5, 12),
                    color="orange",
                    linestyle="--",
                    linewidth=3,
                    label=f"Falling: {falling_strike:.0f}",
                )

            if zero_strike:
                ax.axvline(
                    x=zero_strike,
                    color="yellow",
                    linestyle="--",
                    linewidth=2,
                    label=f"Flip: {zero_strike:.2f}",
                )

            net_val = agg_by_strike.sum() * 100
            ax.plot([], [], " ", label=f"Net {name}: {net_val:,.2f}")

        # ==========================================================
        # BLOQUE: CALLS / PUTS
        # ==========================================================
        elif "Calls/Puts" in value:
            scale = 10**9

            ax.bar(
                df_agg.index,
                df_agg[f"call_{name[:1].lower()}ex"] / scale,
                align="edge",
                width=step * 0.9,
                label=f"Call {name}",
                alpha=0.9,
                color=colors["call"],
            )
            ax.bar(
                df_agg.index,
                df_agg[f"put_{name[:1].lower()}ex"] / scale,
                align="edge",
                width=step * 0.9,
                label=f"Put {name}",
                alpha=0.9,
                color=colors["put"],
            )

            # Líneas de referencia usando datos del histogram absolute
            agg_by_strike_ref = df_agg[f"total_{name.lower()}"]
            max_pos = agg_by_strike_ref.idxmax()
            max_neg = agg_by_strike_ref.idxmin()

            if not pd.isna(max_pos):
                ax.axvline(
                    x=max_pos,
                    color="lime",
                    linestyle="--",
                    linewidth=2,
                    label=f"Max Pos: {max_pos:.2f}",
                )
            if not pd.isna(max_neg):
                ax.axvline(
                    x=max_neg,
                    color="red",
                    linestyle="--",
                    linewidth=2,
                    label=f"Max Neg: {max_neg:.2f}",
                )
            if rising_strike:
                ax.axvline(
                    x=rising_strike,
                    dashes=(5, 12),
                    color="cyan",
                    linestyle="--",
                    linewidth=3,
                    label=f"Rising: {rising_strike:.0f}",
                )
            if falling_strike:
                ax.axvline(
                    x=falling_strike,
                    dashes=(5, 12),
                    color="orange",
                    linestyle="--",
                    linewidth=3,
                    label=f"Falling: {falling_strike:.0f}",
                )

        # ==========================================================
        # BLOQUE: IV AVERAGE
        # ==========================================================
        elif value == "Implied Volatility Average":
            try:
                min_len = min(len(df_agg.index), len(put_ivs_data), len(call_ivs_data))
                if min_len > 0:
                    x_ax = df_agg.index[:min_len]
                    y_p = np.array(put_ivs_data[:min_len]) * 100
                    y_c = np.array(call_ivs_data[:min_len]) * 100
                    ax.plot(
                        x_ax,
                        y_p,
                        label="Put IV",
                        color=colors["put"],
                        linewidth=3,
                    )
                    ax.fill_between(x_ax, y_p, alpha=0.3, color=colors["put"])
                    ax.plot(
                        x_ax,
                        y_c,
                        label="Call IV",
                        color=colors["call"],
                        linewidth=3,
                    )
                    ax.fill_between(x_ax, y_c, alpha=0.3, color=colors["call"])
            except:
                pass

        if date_condition:
            step_plot = math.log10(spot_price)
            if step_plot < 1:
                step_plot = 0.5
            elif 1 <= step_plot < 2:
                step_plot = 2
            elif 2 <= step_plot < 2.5:
                step_plot = 5
            elif 2.5 <= step_plot < 3:
                step_plot = 10
            else:
                step_plot = math.floor(step_plot)
                step_plot = (10 ** (step_plot - 1)) * 0.4

            lb_plot = step_plot * np.floor(float(lower_bound) / step_plot)
            ub_plot = step_plot * np.ceil(float(upper_bound) / step_plot)

            ax.axvline(
                x=spot_price,
                color=colors["spot_line"],
                linestyle="--",
                linewidth=1.5,
                label=f"{ticker} Spot: {spot_price:,.2f}",
            )
            ax.set_xlim(lb_plot, ub_plot)
            x_ticks = np.arange(lb_plot, ub_plot + step_plot, step_plot)
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(
                [f"{x:.2f}" if step_plot < 1 else f"{int(x)}" for x in x_ticks]
            )

        # --- LEYENDA HISTOGRAMA (Fondo NEGRO, Texto BLANCO) ---
        legend = ax.legend(
            loc="best",
            facecolor="black",
            edgecolor="white",
            framealpha=0.9,
            fontsize=STYLE_CONFIG["legend_size"],
        )
        if legend:
            for text in legend.get_texts():
                text.set_color("white")

        value_cl = value.replace("Calls/Puts", "Calls Puts")
        filename = f"{PLOT_DIR}/{ticker}/{exp}/{greek}/{value_cl.replace(' ', '_')}/{timestamp}.png"
        makedirs(path.dirname(filename), exist_ok=True)
        fig.savefig(
            filename,
            bbox_inches="tight",
            facecolor=STYLE_CONFIG["color_bg"],
            dpi=80,
        )
        plt.close(fig)

        return {
            "filename": filename,
            "alerts": alerts,
        }

    except Exception as e:
        print(f"[ERROR HISTOGRAM WORKER]: {e}")
        import traceback

        traceback.print_exc()
        return {
            "filename": None,
            "alerts": [],
        }


# ==============================================================================
# FUNCIONES PRINCIPALES MODIFICADAS PARA USAR PROCESSPOOL
# ==============================================================================


async def plot_greeks_table(
    df,
    today_ddt,
    today_ddt_string,
    monthly_options_dates,
    spot_price,
    from_strike,
    to_strike,
    levels,
    totaldelta,
    totalgamma,
    totalvanna,
    totalcharm,
    totaldgex,
    totalzomma,
    totalvega, 
    totalvomma,
    totalspeed,
    zerodelta,
    zerogamma,
    zerospeed,
    call_ivs,
    put_ivs,
    exp,
    ticker,
    lower_bound,
    upper_bound,
    prev_close_price,
    greek_filter=None,
):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], []

    filenames = []
    all_alerts = []
    GREEKS = (
        [greek_filter]
        if greek_filter
        else ["delta", "gamma", "speed", "vanna", "charm", "dgex", "zomma", "vega", "vomma"]
    )

    VISUALIZATIONS = {
        "delta": ["Absolute Delta Exposure", "Delta Exposure By Calls/Puts"],
        "gamma": ["Absolute Gamma Exposure", "Gamma Exposure By Calls/Puts"],
        "speed": ["Absolute Speed Exposure"],
        "vanna": ["Absolute Vanna Exposure", "Implied Volatility Average"],
        "charm": ["Absolute Charm Exposure"],
        "dgex": ["Absolute Dgex Exposure"],
        "zomma": ["Absolute Zomma Exposure"],
        "vega": ["Absolute Vega Exposure"],
        "vomma": ["Absolute Vomma Exposure"],
    }
    timestamp = datetime.datetime.now(ZoneInfo("America/New_York")).strftime(
        "%Y%m%d_%H%M%S"
    )

    # Preparar trabajos para ProcessPool
    worker_args = []

    for greek in GREEKS:
        for value in VISUALIZATIONS[greek]:
            if "Absolute" not in value:
                continue
            try:
                name = greek.capitalize()
                metric = f"total_{greek.lower()}"

                # --- LÓGICA DE ALERTA DE PINNED ---
                alert_state_path = Path(
                    f"pickles/{ticker}/{exp}/{greek}/pinned_alert_state.pkl"
                )
                alert_state = {}
                if alert_state_path.exists():
                    try:
                        with open(alert_state_path, "rb") as f:
                            alert_state = pickle.load(f)
                    except:
                        alert_state = {}

                available_strikes = sorted(df["strike_price"].unique())
                if len(available_strikes) > 50:
                    spot_idx = np.searchsorted(
                        available_strikes, spot_price, side="left"
                    )
                    lower_idx = max(0, spot_idx - 50)
                    upper_idx = min(len(available_strikes), spot_idx + 51)
                    lower_limit = spot_price * 0.75
                    upper_limit = spot_price * 1.25
                    lower_strike = max(available_strikes[lower_idx], lower_limit)
                    upper_strike = min(available_strikes[upper_idx - 1], upper_limit)
                else:
                    lower_limit = spot_price * 0.75
                    upper_limit = spot_price * 1.25
                    lower_strike = max(min(available_strikes), lower_limit)
                    upper_strike = min(max(available_strikes), upper_limit)

                df_filtered = df[
                    (df["strike_price"] >= lower_strike)
                    & (df["strike_price"] <= upper_strike)
                ]
                if df_filtered.empty:
                    continue

                pivot_table = df_filtered.pivot_table(
                    index="strike_price",
                    columns="expiration_date",
                    values=metric,
                    aggfunc="sum",
                )
                pivot_table = pivot_table.fillna(0)
                if pivot_table.empty:
                    continue

                # --- CALCULOS PREVIOS PARA TABLA (RISING/FALLING) ---
                agg_by_strike = df_filtered.groupby("strike_price")[metric].sum()
                pickle_path = Path(f"pickles/{ticker}/{exp}/{greek}/agg_by_strike.pkl")
                pickle_path.parent.mkdir(parents=True, exist_ok=True)

                rising_strike = None
                falling_strike = None

                if pickle_path.exists():
                    try:
                        previous = pd.read_pickle(pickle_path)
                        common = agg_by_strike.index.intersection(previous.index)
                        if not common.empty:
                            diff = agg_by_strike.loc[common] - previous.loc[common]
                            if not diff.empty and diff.abs().max() > 0:
                                rising_strike = diff.idxmax()
                                falling_strike = diff.idxmin()
                    except:
                        pass

                pd.to_pickle(agg_by_strike, pickle_path)

                # Flip Calc
                zero_strikes = []
                signs = np.sign(agg_by_strike.values)
                if len(signs) > 0:
                    runs = []
                    current_sign = signs[0]
                    start = 0
                    for j in range(1, len(signs)):
                        if signs[j] != current_sign:
                            runs.append((current_sign, start, j - 1))
                            current_sign = signs[j]
                            start = j
                    runs.append((current_sign, start, len(signs) - 1))
                    for r in range(1, len(runs)):
                        prev_run = runs[r - 1]
                        curr_run = runs[r]
                        if (prev_run[2] - prev_run[1] + 1) >= 2 and (
                            curr_run[2] - curr_run[1] + 1
                        ) >= 2:
                            idx1 = prev_run[2]
                            idx2 = curr_run[1]
                            s1, v1 = agg_by_strike.index[idx1], agg_by_strike.iloc[idx1]
                            s2, v2 = agg_by_strike.index[idx2], agg_by_strike.iloc[idx2]
                            z_val = s2 - ((s2 - s1) * v2 / (v2 - v1))
                            zero_strikes.append(z_val)

                flip_val = None
                if zero_strikes:
                    zs = np.array(zero_strikes)
                    flip_val = zs[np.argmin(np.abs(zs - spot_price))]

                # Guardar tabla historia
                table_pickle_path = Path(
                    f"pickles/{ticker}/{exp}/{greek}/table_history.pkl"
                )
                table_pickle_path.parent.mkdir(parents=True, exist_ok=True)
                pd.to_pickle(pivot_table, table_pickle_path)

                strikes = sorted(pivot_table.index, reverse=True)
                expirations = sorted(pivot_table.columns)
                pivot_table = pivot_table.reindex(
                    index=strikes, columns=expirations, fill_value=0
                )

                # Serializar para enviar al worker
                pivot_table_dict = {
                    "data": pivot_table.values.tolist(),
                    "index": pivot_table.index.tolist(),
                    "columns": [
                        col.isoformat() if hasattr(col, "isoformat") else str(col)
                        for col in pivot_table.columns
                    ],
                }

                agg_by_strike_dict = {
                    "data": agg_by_strike.values.tolist(),
                    "index": agg_by_strike.index.tolist(),
                }

                # Convertir expirations a formato serializable
                expirations_serializable = [
                    exp_date.to_pydatetime() if hasattr(exp_date, "to_pydatetime") else exp_date
                    for exp_date in expirations
                ]

                worker_args.append(
                    (
                        pivot_table_dict,
                        ticker,
                        value,
                        today_ddt_string,
                        greek,
                        exp,
                        timestamp,
                        spot_price,
                        strikes,
                        expirations_serializable,
                        agg_by_strike_dict,
                        alert_state,
                        rising_strike,
                        falling_strike,
                        flip_val,
                        metric,  # NUEVO: para identificar
                    )
                )

            except Exception as e:
                print(f"[ERROR TABLE PREP] {ticker}/{exp}/{greek}: {e}")
                import traceback

                traceback.print_exc()

    # Ejecutar en ProcessPool
    if worker_args:
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor() as executor:
            results = await loop.run_in_executor(
                None, lambda: list(executor.map(_plot_single_table_worker, worker_args))
            )

        # NUEVO: Agrupar resultados por (ticker, exp, greek) para sincronización
        alert_states_by_key = {}
        
        # Procesar resultados
        for result in results:
            if result["filename"]:
                filenames.append(result["filename"])
            if result["alerts"]:
                all_alerts.extend(result["alerts"])
            
            # Agrupar alert_states por clave única
            if result["ticker"] and result["exp"] and result["greek"]:
                key = (result["ticker"], result["exp"], result["greek"])
                if key not in alert_states_by_key:
                    alert_states_by_key[key] = []
                alert_states_by_key[key].append(result["alert_state"])

        # NUEVO: Sincronizar alert_states consolidados de vuelta a disco
        for (ticker_key, exp_key, greek_key), states_list in alert_states_by_key.items():
            alert_state_path = Path(
                f"pickles/{ticker_key}/{exp_key}/{greek_key}/pinned_alert_state.pkl"
            )
            alert_state_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Merge inteligente de todos los estados
            final_state = _merge_alert_states(states_list)
            
            # Guardar estado consolidado
            if final_state:
                with open(alert_state_path, "wb") as f:
                    pickle.dump(final_state, f)

    return filenames, all_alerts


async def plot_greeks_histogram(
    df,
    today_ddt,
    today_ddt_string,
    monthly_options_dates,
    spot_price,
    from_strike,
    to_strike,
    levels,
    totaldelta,
    totalgamma,
    totalvanna,
    totalcharm,
    totaldgex,
    totalzomma,
    totalvega, 
    totalvomma,
    totalspeed,
    zerodelta,
    zerogamma,
    zerospeed,
    call_ivs,
    put_ivs,
    exp,
    ticker,
    lower_bound,
    upper_bound,
    prev_close_price,
    greek_filter=None,
):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None, []

    filenames = []
    all_alerts = []
    GREEKS = (
        [greek_filter]
        if greek_filter
        else ["delta", "gamma", "speed", "vanna", "charm", "dgex", "zomma", "vega", "vomma"]
    )
    VISUALIZATIONS = {
        "delta": ["Absolute Delta Exposure", "Delta Exposure By Calls/Puts"],
        "gamma": ["Absolute Gamma Exposure", "Gamma Exposure By Calls/Puts"],
        "speed": ["Absolute Speed Exposure"],
        "vanna": ["Absolute Vanna Exposure", "Implied Volatility Average"],
        "charm": ["Absolute Charm Exposure"],
        "dgex": ["Absolute Dgex Exposure"],
        "zomma": ["Absolute Zomma Exposure"],
        "vega": ["Absolute Vega Exposure"],
        "vomma": ["Absolute Vomma Exposure"],
    }
    timestamp = datetime.datetime.now(ZoneInfo("America/New_York")).strftime(
        "%Y%m%d_%H%M%S"
    )
    colors = {
        "total": "#89CFF0",
        "call": "#90EE90",
        "put": "#FF7F7F",
        "spot_line": "#C0C0C0",
    }

    # Preparar trabajos para ProcessPool
    worker_args = []

    for greek in GREEKS:
        for value in VISUALIZATIONS[greek]:
            try:
                date_condition = not "Profile" in value
                # Validaciones
                if date_condition:
                    if not isinstance(from_strike, (int, float)) or not isinstance(
                        to_strike, (int, float)
                    ):
                        continue
                    df_agg = df.groupby(["strike_price"]).sum(numeric_only=True)
                    strikes_sorted = np.sort(df_agg.index.values)
                    strike_steps = np.diff(strikes_sorted)
                    step = (
                        np.min(strike_steps[strike_steps > 0])
                        if len(strike_steps) > 0
                        else 1
                    )
                    lower_strike_calc = max(
                        np.floor(lower_bound / step) * step, df_agg.index.min()
                    )
                    upper_strike_calc = min(
                        np.ceil(upper_bound / step) * step, df_agg.index.max()
                    )
                    strikes = np.arange(
                        lower_strike_calc, upper_strike_calc + step, step
                    )
                    df_agg = df_agg.reindex(strikes, method="ffill").fillna(0)
                    if df_agg.empty:
                        continue
                else:
                    df_agg = df.groupby(["expiration_date"]).sum(numeric_only=True)
                    if df_agg.empty:
                        continue
                    step = 1  # No usado para profiles

                if "Calls/Puts" in value or value == "Implied Volatility Average":
                    key = "strike" if date_condition else "exp"
                    call_ivs_data = call_ivs.get(key)
                    put_ivs_data = put_ivs.get(key)
                else:
                    call_ivs_data = put_ivs_data = None

                name = value.split()[1] if "Absolute" in value else value.split()[0]

                # Cálculos específicos para cada tipo
                rising_strike = None
                falling_strike = None
                zero_strike = 0

                if "Absolute" in value or "Calls/Puts" in value:
                    agg_by_strike = df_agg[f"total_{name.lower()}"]
                    pickle_path = Path(
                        f"pickles/{ticker}/{exp}/{greek}/agg_by_strike.pkl"
                    )
                    pickle_path.parent.mkdir(parents=True, exist_ok=True)

                    # Zero Strike Calc
                    signs = np.sign(agg_by_strike.values)
                    runs = []
                    if len(signs) > 0:
                        current_sign = signs[0]
                        start = 0
                        for j in range(1, len(signs)):
                            if signs[j] != current_sign:
                                runs.append((current_sign, start, j - 1))
                                current_sign = signs[j]
                                start = j
                        runs.append((current_sign, start, len(signs) - 1))

                    zero_strikes = []
                    for r in range(1, len(runs)):
                        prev_run = runs[r - 1]
                        curr_run = runs[r]
                        if (
                            (prev_run[2] - prev_run[1] + 1) >= 2
                            and (curr_run[2] - curr_run[1] + 1) >= 2
                            and prev_run[0] != 0
                            and curr_run[0] != 0
                        ):
                            idx1 = prev_run[2]
                            idx2 = curr_run[1]
                            s1, v1 = agg_by_strike.index[idx1], agg_by_strike.iloc[idx1]
                            s2, v2 = agg_by_strike.index[idx2], agg_by_strike.iloc[idx2]
                            zero_strikes.append(s2 - ((s2 - s1) * v2 / (v2 - v1)))

                    if zero_strikes:
                        zs = np.array(zero_strikes)
                        zero_strike = zs[np.argmin(np.abs(zs - spot_price))]

                    # --- LÓGICA SHIFTED ALERTS (Solo añadir a alertas, no plotear) ---
                    if pickle_path.exists():
                        try:
                            previous = pd.read_pickle(pickle_path)

                            if ticker == "SPX" and exp == "0dte":
                                try:
                                    if greek == "vanna":
                                        prev_min = previous.idxmin()
                                        curr_min = agg_by_strike.idxmin()
                                        if (
                                            prev_min != curr_min
                                            and spot_price * 0.98
                                            < float(curr_min)
                                            < spot_price * 1.02
                                        ):
                                            msg = f"**SPX 0DTE Vanna Alert**: Max Negative Vanna shifted from {prev_min} to {curr_min}"
                                            all_alerts.append(msg)

                                    if greek == "gamma":
                                        prev_max = previous.idxmax()
                                        curr_max = agg_by_strike.idxmax()
                                        prev_min = previous.idxmin()
                                        curr_min = agg_by_strike.idxmin()
                                        if prev_max != curr_max:
                                            msg = f"**SPX 0DTE Gamma Alert**: Max Positive Gamma shifted from {prev_max} to {curr_max}"
                                            all_alerts.append(msg)
                                        if prev_min != curr_min:
                                            msg = f"**SPX 0DTE Gamma Alert**: Max Negative Gamma shifted from {prev_min} to {curr_min}"
                                            all_alerts.append(msg)
                                except Exception as e:
                                    print(f"Error checking shifts: {e}")

                            common = agg_by_strike.index.intersection(previous.index)
                            if not common.empty:
                                diff = agg_by_strike.loc[common] - previous.loc[common]
                                if not diff.empty and diff.abs().max() > 0:
                                    rising_strike = diff.idxmax()
                                    falling_strike = diff.idxmin()
                        except:
                            pass

                    pd.to_pickle(agg_by_strike, pickle_path)

                # Serializar df_agg
                df_agg_dict = {
                    "data": df_agg.values.tolist(),
                    "index": df_agg.index.tolist(),
                    "columns": df_agg.columns.tolist(),
                }

                # Convertir call_ivs_data y put_ivs_data a listas si son arrays
                if call_ivs_data is not None:
                    call_ivs_data = (
                        call_ivs_data.tolist()
                        if hasattr(call_ivs_data, "tolist")
                        else list(call_ivs_data)
                    )
                if put_ivs_data is not None:
                    put_ivs_data = (
                        put_ivs_data.tolist()
                        if hasattr(put_ivs_data, "tolist")
                        else list(put_ivs_data)
                    )

                worker_args.append(
                    (
                        df_agg_dict,
                        ticker,
                        value,
                        today_ddt_string,
                        greek,
                        exp,
                        timestamp,
                        spot_price,
                        lower_bound,
                        upper_bound,
                        step,
                        colors,
                        call_ivs_data,
                        put_ivs_data,
                        rising_strike,
                        falling_strike,
                        zero_strike,
                        prev_close_price,
                        date_condition,
                    )
                )

            except Exception as e:
                print(f"[ERROR HISTOGRAM PREP] {ticker}/{exp}/{greek}/{value}: {e}")
                import traceback

                traceback.print_exc()

    # Ejecutar en ProcessPool
    if worker_args:
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor() as executor:
            results = await loop.run_in_executor(
                None,
                lambda: list(executor.map(_plot_single_histogram_worker, worker_args)),
            )

        # Procesar resultados
        for result in results:
            if result["filename"]:
                filenames.append(result["filename"])
            if result["alerts"]:
                all_alerts.extend(result["alerts"])

    return filenames, all_alerts


# --- MISMAS FUNCIONES DE CÁLCULO DE SIEMPRE (SIN CAMBIOS) ---
def calc_exposures(
    option_data,
    ticker,
    expir,
    first_expiry,
    this_monthly_opex,
    spot_price,
    today_ddt,
    today_ddt_string,
    SOFR_yield,
):
    dividend_yield = 0.0  # assume 0
    risk_free_yield = SOFR_yield

    monthly_options_dates = [first_expiry, this_monthly_opex]

    strike_prices = option_data["strike_price"].to_numpy(dtype=np.float64).copy()
    expirations = option_data["expiration_date"].to_numpy()
    time_till_exp = option_data["time_till_exp"].to_numpy(dtype=np.float64).copy()
    opt_call_ivs = option_data["call_iv"].to_numpy(dtype=np.float64).copy()
    opt_put_ivs = option_data["put_iv"].to_numpy(dtype=np.float64).copy()
    call_open_interest = option_data["call_open_int"].to_numpy(dtype=np.float64).copy()
    put_open_interest = option_data["put_open_int"].to_numpy(dtype=np.float64).copy()

    nonzero_call_cond = (time_till_exp > 0) & (opt_call_ivs > 0)
    nonzero_put_cond = (time_till_exp > 0) & (opt_put_ivs > 0)
    np_spot_price = np.array([[spot_price]], dtype=np.float64)

    call_dp, call_cdf_dp, call_pdf_dp = stats.calc_dp_cdf_pdf(
        np_spot_price,
        strike_prices,
        opt_call_ivs,
        time_till_exp,
        risk_free_yield,
        dividend_yield,
    )
    put_dp, put_cdf_dp, put_pdf_dp = stats.calc_dp_cdf_pdf(
        np_spot_price,
        strike_prices,
        opt_put_ivs,
        time_till_exp,
        risk_free_yield,
        dividend_yield,
    )

    from_strike = 0.5 * spot_price
    to_strike = 1.5 * spot_price

    # ---=== CALCULATE EXPOSURES ===---
    option_data["call_dex"] = (
        option_data["call_delta"].to_numpy() * call_open_interest * spot_price
    )
    option_data["put_dex"] = (
        option_data["put_delta"].to_numpy() * put_open_interest * spot_price
    )
    option_data["call_gex"] = (
        option_data["call_gamma"].to_numpy()
        * call_open_interest
        * spot_price
        * spot_price
    )
    option_data["put_gex"] = (
        option_data["put_gamma"].to_numpy()
        * put_open_interest
        * spot_price
        * spot_price
        * -1
    )
    option_data["call_vex"] = np.where(
        nonzero_call_cond,
        stats.calc_vanna_ex(
            np_spot_price,
            opt_call_ivs,
            time_till_exp,
            dividend_yield,
            call_open_interest,
            call_dp,
            call_pdf_dp,
        )[0],
        0,
    )
    option_data["put_vex"] = np.where(
        nonzero_put_cond,
        stats.calc_vanna_ex(
            np_spot_price,
            opt_put_ivs,
            time_till_exp,
            dividend_yield,
            put_open_interest,
            put_dp,
            put_pdf_dp,
        )[0],
        0,
    )
    option_data["call_cex"] = np.where(
        nonzero_call_cond,
        stats.calc_charm_ex(
            np_spot_price,
            opt_call_ivs,
            time_till_exp,
            risk_free_yield,
            dividend_yield,
            "call",
            call_open_interest,
            call_dp,
            call_cdf_dp,
            call_pdf_dp,
        )[0],
        0,
    )
    option_data["put_cex"] = np.where(
        nonzero_put_cond,
        stats.calc_charm_ex(
            np_spot_price,
            opt_put_ivs,
            time_till_exp,
            risk_free_yield,
            dividend_yield,
            "put",
            put_open_interest,
            put_dp,
            put_cdf_dp,
            put_pdf_dp,
        )[0],
        0,
    )

    call_gex_2d = option_data["call_gex"].to_numpy().reshape(1, -1)
    put_gex_2d = option_data["put_gex"].to_numpy().reshape(1, -1)

    option_data["call_dgex"] = np.where(
        nonzero_call_cond,
        stats.calc_delta_adjusted_gex(
            call_gex_2d, call_cdf_dp, time_till_exp, dividend_yield, "call"
        )[0],
        0,
    )

    option_data["put_dgex"] = np.where(
        nonzero_put_cond,
        stats.calc_delta_adjusted_gex(
            put_gex_2d, put_cdf_dp, time_till_exp, dividend_yield, "put"
        )[0],
        0,
    )

    option_data["call_zomma"] = np.where(
        nonzero_call_cond,
        stats.calc_zomma_ex(call_gex_2d, call_dp, opt_call_ivs, time_till_exp)[0],
        0,
    )

    option_data["put_zomma"] = np.where(
        nonzero_put_cond,
        stats.calc_zomma_ex(put_gex_2d, put_dp, opt_put_ivs, time_till_exp)[0],
        0,
    )

    option_data["call_vegex"] = option_data["call_vega"].to_numpy() * call_open_interest * 100
    option_data["put_vegex"] = option_data["put_vega"].to_numpy() * put_open_interest * 100

    call_vegex_2d = option_data["call_vegex"].to_numpy().reshape(1, -1)
    put_vegex_2d = option_data["put_vegex"].to_numpy().reshape(1, -1)

    option_data["call_vommex"] = np.where(
        nonzero_call_cond,
        stats.calc_vomma_ex(call_vegex_2d, call_dp, opt_call_ivs, time_till_exp)[0],
        0,
    )
    option_data["put_vommex"] = np.where(
        nonzero_put_cond,
        stats.calc_vomma_ex(put_vegex_2d, put_dp, opt_put_ivs, time_till_exp)[0],
        0,
    )

    option_data["call_speed"] = np.where(
        nonzero_call_cond,
        stats.calc_speed_ex(call_gex_2d, call_dp, opt_call_ivs, time_till_exp, np_spot_price)[0],
        0,
    )
    option_data["put_speed"] = np.where(
        nonzero_put_cond,
        stats.calc_speed_ex(put_gex_2d, put_dp, opt_put_ivs, time_till_exp, np_spot_price)[0],
        0,
    )

    # Calculate total and scale down
    option_data["total_delta"] = (
        option_data["call_dex"].to_numpy() + option_data["put_dex"].to_numpy()
    ) / 10**9
    option_data["total_gamma"] = (
        option_data["call_gex"].to_numpy() + option_data["put_gex"].to_numpy()
    ) / 10**9
    option_data["total_vanna"] = (
        option_data["call_vex"].to_numpy() - option_data["put_vex"].to_numpy()
    ) / 10**9
    option_data["total_charm"] = (
        option_data["call_cex"].to_numpy() - option_data["put_cex"].to_numpy()
    ) / 10**9

    option_data["total_dgex"] = (
        option_data["call_dgex"].to_numpy() + option_data["put_dgex"].to_numpy()
    ) / 10**9

    option_data["total_zomma"] = (
        option_data["call_zomma"].to_numpy() + option_data["put_zomma"].to_numpy()
    ) / 10**9

    option_data["total_vega"] = (option_data["call_vegex"].to_numpy() + option_data["put_vegex"].to_numpy()) / 10**9
    option_data["total_vomma"] = (option_data["call_vommex"].to_numpy() + option_data["put_vommex"].to_numpy()) / 10**9
    option_data["total_speed"] = (option_data["call_speed"].to_numpy() + option_data["put_speed"].to_numpy()) / 10**9


    df_agg_strike_mean = (
        option_data[["strike_price", "call_iv", "put_iv"]]
        .groupby(["strike_price"])
        .mean(numeric_only=True)
    )
    df_agg_exp_mean = (
        option_data[["expiration_date", "call_iv", "put_iv"]]
        .groupby(["expiration_date"])
        .mean(numeric_only=True)
    )
    df_agg_strike_mean = df_agg_strike_mean[from_strike:to_strike]

    call_ivs = {
        "strike": df_agg_strike_mean["call_iv"].to_numpy(),
        "exp": df_agg_exp_mean["call_iv"].to_numpy(),
    }
    put_ivs = {
        "strike": df_agg_strike_mean["put_iv"].to_numpy(),
        "exp": df_agg_exp_mean["put_iv"].to_numpy(),
    }

    # ---=== CALCULATE EXPOSURE PROFILES ===---
    levels = np.linspace(from_strike, to_strike, 300).reshape(-1, 1)

    totaldelta = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }
    totalgamma = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }
    totalvanna = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }
    totalcharm = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }

    totaldgex = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }
    totalzomma = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }

    totalvega = {"all": np.array([]), "ex_next": np.array([]), "ex_fri": np.array([])}
    totalvomma = {"all": np.array([]), "ex_next": np.array([]), "ex_fri": np.array([])}
    totalspeed = {"all": np.array([]), "ex_next": np.array([]), "ex_fri": np.array([])}

    call_dp, call_cdf_dp, call_pdf_dp = stats.calc_dp_cdf_pdf(
        levels,
        strike_prices,
        opt_call_ivs,
        time_till_exp,
        risk_free_yield,
        dividend_yield,
    )
    put_dp, put_cdf_dp, put_pdf_dp = stats.calc_dp_cdf_pdf(
        levels,
        strike_prices,
        opt_put_ivs,
        time_till_exp,
        risk_free_yield,
        dividend_yield,
    )
    call_delta_ex = np.where(
        nonzero_call_cond,
        stats.calc_delta_ex(
            levels,
            time_till_exp,
            dividend_yield,
            "call",
            call_open_interest,
            call_cdf_dp,
        ),
        0,
    )
    put_delta_ex = np.where(
        nonzero_put_cond,
        stats.calc_delta_ex(
            levels,
            time_till_exp,
            dividend_yield,
            "put",
            put_open_interest,
            put_cdf_dp,
        ),
        0,
    )
    call_gamma_ex = np.where(
        nonzero_call_cond,
        stats.calc_gamma_ex(
            levels,
            opt_call_ivs,
            time_till_exp,
            dividend_yield,
            call_open_interest,
            call_pdf_dp,
        ),
        0,
    )
    put_gamma_ex = np.where(
        nonzero_put_cond,
        stats.calc_gamma_ex(
            levels,
            opt_put_ivs,
            time_till_exp,
            dividend_yield,
            put_open_interest,
            put_pdf_dp,
        ),
        0,
    )
    call_speed_ex = np.where(
        nonzero_call_cond,
        stats.calc_speed_ex(call_gamma_ex, call_dp, opt_call_ivs, time_till_exp, levels),
        0,
    )
    put_speed_ex = np.where(
        nonzero_put_cond,
        stats.calc_speed_ex(put_gamma_ex, put_dp, opt_put_ivs, time_till_exp, levels),
        0,
    )
    call_vanna_ex = np.where(
        nonzero_call_cond,
        stats.calc_vanna_ex(
            levels,
            opt_call_ivs,
            time_till_exp,
            dividend_yield,
            call_open_interest,
            call_dp,
            call_pdf_dp,
        ),
        0,
    )
    put_vanna_ex = np.where(
        nonzero_put_cond,
        stats.calc_vanna_ex(
            levels,
            opt_put_ivs,
            time_till_exp,
            dividend_yield,
            put_open_interest,
            put_dp,
            put_pdf_dp,
        ),
        0,
    )
    call_charm_ex = np.where(
        nonzero_call_cond,
        stats.calc_charm_ex(
            levels,
            opt_call_ivs,
            time_till_exp,
            risk_free_yield,
            dividend_yield,
            "call",
            call_open_interest,
            call_dp,
            call_cdf_dp,
            call_pdf_dp,
        ),
        0,
    )
    put_charm_ex = np.where(
        nonzero_put_cond,
        stats.calc_charm_ex(
            levels,
            opt_put_ivs,
            time_till_exp,
            risk_free_yield,
            dividend_yield,
            "put",
            put_open_interest,
            put_dp,
            put_cdf_dp,
            put_pdf_dp,
        ),
        0,
    )

    call_dgex_ex = np.where(
        nonzero_call_cond,
        stats.calc_delta_adjusted_gex(
            call_gamma_ex, call_cdf_dp, time_till_exp, dividend_yield, "call"
        ),
        0,
    )
    put_dgex_ex = np.where(
        nonzero_put_cond,
        stats.calc_delta_adjusted_gex(
            put_gamma_ex, put_cdf_dp, time_till_exp, dividend_yield, "put"
        ),
        0,
    )

    call_zomma_ex = np.where(
        nonzero_call_cond,
        stats.calc_zomma_ex(call_gamma_ex, call_dp, opt_call_ivs, time_till_exp),
        0,
    )
    put_zomma_ex = np.where(
        nonzero_put_cond,
        stats.calc_zomma_ex(put_gamma_ex, put_dp, opt_put_ivs, time_till_exp),
        0,
    )

    # --- VEGA & VOMMA 2D ---
    call_vega_ex = np.where(nonzero_call_cond, stats.calc_vega_ex(levels, opt_call_ivs, time_till_exp, dividend_yield, call_open_interest, call_pdf_dp), 0)
    put_vega_ex = np.where(nonzero_put_cond, stats.calc_vega_ex(levels, opt_put_ivs, time_till_exp, dividend_yield, put_open_interest, put_pdf_dp), 0)
    call_vomma_ex = np.where(nonzero_call_cond, stats.calc_vomma_ex(call_vega_ex, call_dp, opt_call_ivs, time_till_exp), 0)
    put_vomma_ex = np.where(nonzero_put_cond, stats.calc_vomma_ex(put_vega_ex, put_dp, opt_put_ivs, time_till_exp), 0)


    totaldelta["all"] = (call_delta_ex.sum(axis=1) + put_delta_ex.sum(axis=1)) / 10**9
    totalgamma["all"] = (call_gamma_ex.sum(axis=1) - put_gamma_ex.sum(axis=1)) / 10**9
    totalvanna["all"] = (call_vanna_ex.sum(axis=1) - put_vanna_ex.sum(axis=1)) / 10**9
    totalcharm["all"] = (call_charm_ex.sum(axis=1) - put_charm_ex.sum(axis=1)) / 10**9
    totaldgex["all"] = (call_dgex_ex.sum(axis=1) + put_dgex_ex.sum(axis=1)) / 10**9
    totalzomma["all"] = (call_zomma_ex.sum(axis=1) + put_zomma_ex.sum(axis=1)) / 10**9
    totalvega["all"] = (call_vega_ex.sum(axis=1) + put_vega_ex.sum(axis=1)) / 10**9
    totalvomma["all"] = (call_vomma_ex.sum(axis=1) + put_vomma_ex.sum(axis=1)) / 10**9

    expirs_next_expiry = expirations == first_expiry
    expirs_up_to_monthly_opex = expirations <= this_monthly_opex
    if expir != "0dte":
        totaldelta["ex_next"] = (
            np.where(expirs_next_expiry, call_delta_ex, 0).sum(axis=1)
            + np.where(expirs_next_expiry, put_delta_ex, 0).sum(axis=1)
        ) / 10**9
        totalgamma["ex_next"] = (
            np.where(expirs_next_expiry, call_gamma_ex, 0).sum(axis=1)
            - np.where(expirs_next_expiry, put_gamma_ex, 0).sum(axis=1)
        ) / 10**9
        totalvanna["ex_next"] = (
            np.where(expirs_next_expiry, call_vanna_ex, 0).sum(axis=1)
            - np.where(expirs_next_expiry, put_vanna_ex, 0).sum(axis=1)
        ) / 10**9
        totalcharm["ex_next"] = (
            np.where(expirs_next_expiry, call_charm_ex, 0).sum(axis=1)
            - np.where(expirs_next_expiry, put_charm_ex, 0).sum(axis=1)
        ) / 10**9
        totaldgex["ex_next"] = (
            np.where(expirs_next_expiry, call_dgex_ex, 0).sum(axis=1)
            + np.where(expirs_next_expiry, put_dgex_ex, 0).sum(axis=1)
        ) / 10**9
        totalzomma["ex_next"] = (
            np.where(expirs_next_expiry, call_zomma_ex, 0).sum(axis=1)
            + np.where(expirs_next_expiry, put_zomma_ex, 0).sum(axis=1)
        ) / 10**9
        totalvega["ex_next"] = (np.where(expirs_next_expiry, call_vega_ex, 0).sum(axis=1) + np.where(expirs_next_expiry, put_vega_ex, 0).sum(axis=1)) / 10**9
        totalvomma["ex_next"] = (np.where(expirs_next_expiry, call_vomma_ex, 0).sum(axis=1) + np.where(expirs_next_expiry, put_vomma_ex, 0).sum(axis=1)) / 10**9
        totalspeed["ex_next"] = (np.where(expirs_next_expiry, call_speed_ex, 0).sum(axis=1) + np.where(expirs_next_expiry, put_speed_ex, 0).sum(axis=1)) / 10**9

        if expir == "all":
            totaldelta["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_delta_ex, 0).sum(axis=1)
                + np.where(expirs_up_to_monthly_opex, put_delta_ex, 0).sum(axis=1)
            ) / 10**9
            totalgamma["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_gamma_ex, 0).sum(axis=1)
                - np.where(expirs_up_to_monthly_opex, put_gamma_ex, 0).sum(axis=1)
            ) / 10**9
            totalvanna["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_vanna_ex, 0).sum(axis=1)
                - np.where(expirs_up_to_monthly_opex, put_vanna_ex, 0).sum(axis=1)
            ) / 10**9
            totalcharm["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_charm_ex, 0).sum(axis=1)
                - np.where(expirs_up_to_monthly_opex, put_charm_ex, 0).sum(axis=1)
            ) / 10**9
            totaldgex["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_dgex_ex, 0).sum(axis=1)
                + np.where(expirs_up_to_monthly_opex, put_dgex_ex, 0).sum(axis=1)
            ) / 10**9
            totalzomma["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_zomma_ex, 0).sum(axis=1)
                + np.where(expirs_up_to_monthly_opex, put_zomma_ex, 0).sum(axis=1)
            ) / 10**9
            totalvega["ex_fri"] = (np.where(expirs_up_to_monthly_opex, call_vega_ex, 0).sum(axis=1) + np.where(expirs_up_to_monthly_opex, put_vega_ex, 0).sum(axis=1)) / 10**9
            totalvomma["ex_fri"] = (np.where(expirs_up_to_monthly_opex, call_vomma_ex, 0).sum(axis=1) + np.where(expirs_up_to_monthly_opex, put_vomma_ex, 0).sum(axis=1)) / 10**9
            totalspeed["ex_fri"] = (np.where(expirs_up_to_monthly_opex, call_speed_ex, 0).sum(axis=1) + np.where(expirs_up_to_monthly_opex, put_speed_ex, 0).sum(axis=1)) / 10**9


    zero_cross_idx = np.where(np.diff(np.sign(totaldelta["all"])))[0]
    neg_delta = totaldelta["all"][zero_cross_idx]
    pos_delta = totaldelta["all"][zero_cross_idx + 1]
    neg_strike = levels[zero_cross_idx]
    pos_strike = levels[zero_cross_idx + 1]
    zerodelta = pos_strike - (
        (pos_strike - neg_strike) * pos_delta / (pos_delta - neg_delta)
    )

    zero_cross_idx = np.where(np.diff(np.sign(totalgamma["all"])))[0]
    negGamma = totalgamma["all"][zero_cross_idx]
    posGamma = totalgamma["all"][zero_cross_idx + 1]
    neg_strike = levels[zero_cross_idx]
    pos_strike = levels[zero_cross_idx + 1]
    zerogamma = pos_strike - (
        (pos_strike - neg_strike) * posGamma / (posGamma - negGamma)
    )

    if zerodelta.size > 0:
        zerodelta = zerodelta[0][0]
    else:
        zerodelta = 0
    if zerogamma.size > 0:
        zerogamma = zerogamma[0][0]
    else:
        zerogamma = 0

    zero_cross_idx = np.where(np.diff(np.sign(totalspeed["all"])))[0]
    negSpeed = totalspeed["all"][zero_cross_idx]
    posSpeed = totalspeed["all"][zero_cross_idx + 1]
    neg_strike = levels[zero_cross_idx]
    pos_strike = levels[zero_cross_idx + 1]
    zerospeed = pos_strike - (
        (pos_strike - neg_strike) * posSpeed / (posSpeed - negSpeed)
    )
    if zerospeed.size > 0:
        zerospeed = zerospeed[0][0]
    else:
        zerospeed = 0


    return (
        option_data,
        today_ddt,
        today_ddt_string,
        monthly_options_dates,
        spot_price,
        from_strike,
        to_strike,
        levels.ravel(),
        totaldelta,
        totalgamma,
        totalvanna,
        totalcharm,
        totaldgex,
        totalzomma,
        totalvega,
        totalvomma,
        totalspeed,
        zerodelta,
        zerogamma,
        zerospeed,
        call_ivs,
        put_ivs,
    )


def calcular_spx_media(es_price, sofr_rate):
    dividend_yield = 0.01234
    denominador = 252

    hoy = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
    hoy = hoy.date()
    year = hoy.year
    current_month = hoy.month

    def tercer_viernes(year, month):
        c = calendar.Calendar()
        viernes_count = 0
        for day in c.itermonthdates(year, month):
            if day.month == month and day.weekday() == 4:
                viernes_count += 1
                if viernes_count == 3:
                    return day
        return None

    def siguiente_opex_month(current_month):
        meses_opex = [3, 6, 9, 12]
        for m in meses_opex:
            if m >= current_month:
                return m
        return 3

    opex_month = siguiente_opex_month(current_month)
    fecha_opex = tercer_viernes(year, opex_month)
    if fecha_opex <= hoy:
        if opex_month == 12:
            year += 1
            opex_month = 3
        else:
            meses_opex = [3, 6, 9, 12]
            idx = meses_opex.index(opex_month)
            opex_month = meses_opex[(idx + 1) % 4]
            if opex_month == 3:
                year += 1
        fecha_opex = tercer_viernes(year, opex_month)

    dias_laborables = 0
    domingos = 0
    fecha = hoy
    while fecha <= fecha_opex:
        if fecha.weekday() == 6:
            domingos += 1
        elif fecha.weekday() < 5:
            dias_laborables += 1
        fecha += datetime.timedelta(days=1)

    T1 = dias_laborables / denominador
    T2 = (dias_laborables + domingos) / denominador

    def spx_from_t(T):
        return es_price * math.exp(-(sofr_rate - dividend_yield) * T)

    spx_T1 = spx_from_t(T1)
    spx_T2 = spx_from_t(T2)
    spx_media = (spx_T1 + spx_T2) / 2

    return spx_media


def get_options_data(ticker, expir, greek_filter):
    async def _fetch_internal():
        ny_tz = ZoneInfo("America/New_York")
        now_ny = datetime.datetime.now(ny_tz)
        trading_date = now_ny.date()
        
        # Ajuste de madrugada: Si son antes de las 3 AM, cuenta como el día de ayer
        if now_ny.time() < datetime.time(3, 0):
            trading_date -= datetime.timedelta(days=1)
            
        if not is_market_open(trading_date):
            print(f"[{now_ny.strftime('%H:%M:%S')}] NYSE CERRADO. Omitiendo descarga y guardado de JSON para {ticker}.")
            # Retornamos vacío para abortar el proceso sin causar errores
            return [], [], []
        load_dotenv()
        t0 = time.time()
        username = getenv("TASTYTRADE_USERNAME")
        password = getenv("TASTYTRADE_PASSWORD")
        session = Session(provider_secret=os.getenv('TASTYTRADE_CLIENT_SECRET'),
            refresh_token=os.getenv('TASTYTRADE_REFRESH_TOKEN'))
        t1 = time.time()
        print(f"📡 [RED] API Tastytrade Session: {t1 - t0:.4f}s")
        t_san = ticker.replace("^", "").replace(" ", "").upper()
        t_list = [get_future_ticker(t_san)] if "/" in t_san else [t_san]
        if t_san == "SPX":
            t_list.append("SPXW")
        t_list.append(get_SOFR_ticker())

        _, quotes = await tasty_data(session, equities_ticker=t_list)

        spot = 0
        sofr = 4.5
        prev_close_price = 0
        for q in quotes:
            if t_san in q.get("symbol"):
                spot = float(q.get("last"))
                prev_close_price = float(q.get("prev_close"))
                print("PREV CLOSE PRICE ", prev_close_price)
            if q.get("symbol") == get_SOFR_ticker():
                sofr = float(q.get("last"))

        yield_val = (100 - sofr) / 100

        if "SPX" in ticker:
            ny_tz = ZoneInfo("America/New_York")
            now_ny = datetime.datetime.now(ny_tz)
            hora_ny = now_ny.time()

            rth_start = datetime.time(9, 30)
            rth_end = datetime.time(16, 00)
            es_weekend = now_ny.weekday() >= 5

            if rth_start <= hora_ny <= rth_end and not es_weekend:
                precio_spot_final = spot
            else:
                print("Calculando SPX nocturno basado en futuro /ES...")

                ticker_future = get_future_ticker("/ES")
                tickerList2 = [ticker_future]
                try:
                    _, tickers_quotes2 = await tasty_data(
                        session, equities_ticker=tickerList2
                    )
                    es_price = 0
                    for quote2 in tickers_quotes2:
                        if quote2.get("symbol") == ticker_future:
                            es_price = float(quote2.get("last"))

                    if es_price > 0:
                        precio_spot_final = calcular_spx_media(es_price, yield_val)
                        print(
                            f"Precio Futuro (/ES): {es_price} -> SPX Calculado: {precio_spot_final:.2f}"
                        )
                    else:
                        print(
                            "No se pudo obtener precio del futuro, usando último spot conocido."
                        )
                        precio_spot_final = spot
                except Exception as e:
                    print(f"Error obteniendo datos del futuro: {e}")
                    precio_spot_final = spot

            spot = precio_spot_final

        t_list_clean = [t for t in t_list if "SR3" not in t]
        t0 = time.time()
        exp_dates, exp_strikes = await tasty_expirations_strikes(session, t_list_clean)
        t1 = time.time()
        print(f"📡 [RED] API Tastytrade exp dates strikes: {t1 - t0:.4f}s")
        today = pd.Timestamp.now(tz="America/New_York")
        exp_clean = expir.replace(" ", "").lower()

        all_dates = get_all_unique_expirations_timestamps(exp_dates)
        first = all_dates[0] if today <= all_dates[0] else all_dates[1]

        sel_date = 0
        if exp_clean != "all":
            sel_date = pd.Timestamp(expir_to_datetime(exp_clean)).tz_localize(
                "America/New_York"
            ) + timedelta(hours=16)
        if sel_date == 0:
            sel_date = all_dates[-1]

        low, high = get_strike_bounds(exp_strikes, spot)
        start = first.date()
        end = sel_date.date()
        if start > end:
            start, end = end, start

        req = {
            "tickers": t_list_clean,
            "start_date": start,
            "end_date": end,
            "lower_strike": low,
            "upper_strike": high,
        }

        t0 = time.time()
        gr_list, _ = await tasty_data(session, options_requested=req)
        opt_data = format_data(gr_list, today)
        t1 = time.time()
        print(f"📡 [RED] API Tastytrade options y dataframe: {t1 - t0:.4f}s")
        this_opex, _ = is_third_friday(first, "America/New_York")
        today_str = today.strftime("%Y %b %d, %I:%M %p %Z")

        exp_data = calc_exposures(
            opt_data,
            t_san,
            exp_clean,
            first,
            this_opex,
            spot,
            today,
            today_str,
            yield_val,
        )

        full_data = exp_data + (exp_clean, t_san, low, high, prev_close_price, greek_filter)

        try:
            keys_map = [
                "option_data",
                "today_ddt",
                "today_ddt_string",
                "monthly_options_dates",
                "spot_price",
                "from_strike",
                "to_strike",
                "levels",
                "totaldelta",
                "totalgamma",
                "totalvanna",
                "totalcharm",
                "totaldgex",
                "totalzomma",
                "totalvega",
                "totalvomma",
                "totalspeed",
                "zerodelta",
                "zerogamma",
                "zerospeed",
                "call_ivs",
                "put_ivs",
                "expir",
                "ticker",
                "lower_strike",
                "upper_strike",
                "prev_close_price",
                "greek_filter",
            ]
            exp_dict = dict(zip(keys_map, full_data))
            t0 = time.time()
            h_file, h_alert = await plot_greeks_histogram(*full_data)
            t_file, t_alert = await plot_greeks_table(*full_data)
            all_alerts = h_alert + t_alert
            exp_dict["alerts"] = all_alerts
            t1 = time.time()
            print(f"\t[MatPlot] Crear los pngs: {t1 - t0:.4f}s")
            def serialize(obj):
                if isinstance(obj, pd.DataFrame):
                    return obj.to_dict(orient="split")
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, (pd.Timestamp, datetime.date, datetime.datetime)):
                    return obj.isoformat()
                if isinstance(obj, (np.float64, np.float32)):
                    return float(obj)
                if isinstance(obj, (np.int64, np.int32)):
                    return int(obj)
                return str(obj)

            json_dir = "json_data"
            if not path.exists(json_dir):
                makedirs(json_dir, exist_ok=True)
            fname = f"{t_san}_{exp_clean}_ExposureData_{today.strftime('%Y%m%d_%H%M%S')}.json"
            t0 = time.time()
            with open(path.join(json_dir, fname), "w") as f:
                json.dump(exp_dict, f, default=serialize)
            t1 = time.time()
            print(f"\t[DISK] Cargan en el json serialize: {t1 - t0:.4f}s")
            return [h_file, all_alerts, t_file]

        except Exception as e:
            print(f"Post-process error: {e}")
            import traceback

            traceback.print_exc()
            return [], [], []

    return asyncio.run(_fetch_internal())
