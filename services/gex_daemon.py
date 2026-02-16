import sys
import os

# Add project root to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import asyncio
import json
import pandas as pd
import numpy as np
import math
import modules.stats as stats
from modules.tasty_handler import tasty_data, tasty_expirations_strikes
from modules.utils import *
from tastytrade import Session
from datetime import datetime, timedelta, time, date, timezone
from os import getcwd, makedirs, path, getenv
from dotenv import load_dotenv
import calendar
import pickle
import traceback
import pandas_market_calendars as mcal

# Inicializar el calendario del NYSE de forma global por rendimiento
NYSE_CALENDAR = mcal.get_calendar('NYSE')

# --- CONFIGURACIÓN ---
TICKERS_TO_TRACK = ["SPX", "SPY", "QQQ"]
EXPIRATION_MODE = "0dte"  # O "weekly", "all"
UPDATE_INTERVAL = 30  # Segundos entre vueltas completas

def is_market_open(check_date) -> bool:
    """
    Verifica si el NYSE está abierto en una fecha específica.
    """
    schedule = NYSE_CALENDAR.schedule(start_date=check_date, end_date=check_date)
    return not schedule.empty

# --- FUNCIONES DE CÁLCULO (Tu código original de calc_exposures y spx_media) ---
# [PEGAR AQUÍ LA FUNCIÓN calc_exposures QUE ME PASASTE]
# [PEGAR AQUÍ LA FUNCIÓN calcular_spx_media QUE ME PASASTE]
# Para que el script funcione, asegúrate de importar o copiar esas funciones aquí.
# Por brevedad, asumo que las tienes en el mismo archivo o importadas.
async def calc_exposures(
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

    # ==============================================================================
    # NUEVO: CÁLCULO DE DELTA-ADJUSTED GEX Y ZOMMA
    # ==============================================================================

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

    # ==============================================================================
    # NUEVO: CÁLCULO DE VEGA Y VOMMA EXPOSURES
    # ==============================================================================

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

    # ==============================================================================

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

    option_data["total_vega"] = (
        option_data["call_vegex"].to_numpy() + option_data["put_vegex"].to_numpy()
    ) / 10**9

    option_data["total_vomma"] = (
        option_data["call_vommex"].to_numpy() + option_data["put_vommex"].to_numpy()
    ) / 10**9

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
    totalvega = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }
    totalvomma = {
        "all": np.array([]),
        "ex_next": np.array([]),
        "ex_fri": np.array([]),
    }

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

    call_vega_ex = np.where(
        nonzero_call_cond,
        stats.calc_vega_ex(
            levels,
            opt_call_ivs,
            time_till_exp,
            dividend_yield,
            call_open_interest,
            call_pdf_dp,
        ),
        0,
    )
    put_vega_ex = np.where(
        nonzero_put_cond,
        stats.calc_vega_ex(
            levels,
            opt_put_ivs,
            time_till_exp,
            dividend_yield,
            put_open_interest,
            put_pdf_dp,
        ),
        0,
    )

    call_vomma_ex = np.where(
        nonzero_call_cond,
        stats.calc_vomma_ex(call_vega_ex, call_dp, opt_call_ivs, time_till_exp),
        0,
    )
    put_vomma_ex = np.where(
        nonzero_put_cond,
        stats.calc_vomma_ex(put_vega_ex, put_dp, opt_put_ivs, time_till_exp),
        0,
    )

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
        totalvega["ex_next"] = (
            np.where(expirs_next_expiry, call_vega_ex, 0).sum(axis=1)
            + np.where(expirs_next_expiry, put_vega_ex, 0).sum(axis=1)
        ) / 10**9
        totalvomma["ex_next"] = (
            np.where(expirs_next_expiry, call_vomma_ex, 0).sum(axis=1)
            + np.where(expirs_next_expiry, put_vomma_ex, 0).sum(axis=1)
        ) / 10**9
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
            totalvega["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_vega_ex, 0).sum(axis=1)
                + np.where(expirs_up_to_monthly_opex, put_vega_ex, 0).sum(axis=1)
            ) / 10**9
            totalvomma["ex_fri"] = (
                np.where(expirs_up_to_monthly_opex, call_vomma_ex, 0).sum(axis=1)
                + np.where(expirs_up_to_monthly_opex, put_vomma_ex, 0).sum(axis=1)
            ) / 10**9

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
        zerodelta,
        zerogamma,
        call_ivs,
        put_ivs,
    )


def calcular_spx_media(es_price, sofr_rate):
    dividend_yield = 0.01234
    denominador = 252

    hoy = datetime.now(timezone.utc) - timedelta(hours=4)  # Hora NY aprox (UTC-4)
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
        fecha += timedelta(days=1)

    T1 = dias_laborables / denominador
    T2 = (dias_laborables + domingos) / denominador

    def spx_from_t(T):
        return es_price * math.exp(-(sofr_rate - dividend_yield) * T)

    spx_T1 = spx_from_t(T1)
    spx_T2 = spx_from_t(T2)
    spx_media = (spx_T1 + spx_T2) / 2

    return spx_media


# Si están en otro archivo, descomenta:
# from modules.calculos import calc_exposures, calcular_spx_media


# --- NUEVA FUNCIÓN: Lógica de Alertas SIN Matplotlib ---
def calculate_alerts_headless(df, ticker, exp, greek, spot_price):
    """
    Calcula alertas matemáticas (Pinnings, Shifts) sin generar gráficos.
    """
    alerts = []
    try:
        if df.empty:
            return []

        metric = f"total_{greek.lower()}"

        # Filtrar rango cercano al spot para eficiencia
        lower_limit = spot_price * 0.85
        upper_limit = spot_price * 1.15
        df_filtered = df[
            (df["strike_price"] >= lower_limit) & (df["strike_price"] <= upper_limit)
        ]

        agg_by_strike = df_filtered.groupby("strike_price")[metric].sum()

        # 1. Detectar Max Pos/Neg
        max_pos = agg_by_strike.idxmax()
        max_neg = agg_by_strike.idxmin()
        max_pos_val = agg_by_strike.max()
        max_neg_val = agg_by_strike.min()

        # 2. Cargar estado previo (Pickles)
        pickle_path = Path(f"pickles/{ticker}/{exp}/{greek}/agg_by_strike.pkl")
        pickle_path.parent.mkdir(parents=True, exist_ok=True)

        alert_state_path = Path(
            f"pickles/{ticker}/{exp}/{greek}/pinned_alert_state.pkl"
        )
        alert_state = {}
        if alert_state_path.exists():
            try:
                with open(alert_state_path, "rb") as f:
                    alert_state = pickle.load(f)
            except:
                pass

        # 3. Lógica de Pinned (Precio pegado a un strike con mucha gamma/vanna)
        # Usamos un umbral de cercanía (ej: 0.2% del spot)
        threshold = spot_price * 0.002

        # Check Positive Pinned
        if (
            not pd.isna(max_pos)
            and abs(spot_price - max_pos) < threshold
            and max_pos_val > 0
        ):
            current_pinned = float(max_pos)
            if current_pinned != alert_state.get("pos_pinned"):
                msg = f"**{ticker} {greek.upper()} ALERT**: Price is pinned at Max Positive Strike: {max_pos:.2f}"
                alerts.append(msg)
                alert_state["pos_pinned"] = current_pinned
        else:
            if "pos_pinned" in alert_state:
                del alert_state["pos_pinned"]

        # Check Negative Pinned
        if (
            not pd.isna(max_neg)
            and abs(spot_price - max_neg) < threshold
            and max_neg_val < 0
        ):
            current_pinned = float(max_neg)
            if current_pinned != alert_state.get("neg_pinned"):
                msg = f"**{ticker} {greek.upper()} ALERT**: Price is pinned at Max Negative Strike: {max_neg:.2f}"
                alerts.append(msg)
                alert_state["neg_pinned"] = current_pinned
        else:
            if "neg_pinned" in alert_state:
                del alert_state["neg_pinned"]

        # Guardar estado alertas
        with open(alert_state_path, "wb") as f:
            pickle.dump(alert_state, f)

        # 4. Lógica de Shift (Cambio de muro)
        if pickle_path.exists():
            try:
                previous = pd.read_pickle(pickle_path)
                prev_max = previous.idxmax()
                prev_min = previous.idxmin()

                # Solo alertar si el cambio es significativo y está cerca del dinero
                if (
                    prev_max != max_pos
                    and spot_price * 0.95 < max_pos < spot_price * 1.05
                ):
                    msg = f"**{ticker} {greek.upper()} Alert**: Max Positive shifted from {prev_max} to {max_pos}"
                    if msg not in alerts:
                        alerts.append(msg)

                if (
                    prev_min != max_neg
                    and spot_price * 0.95 < max_neg < spot_price * 1.05
                ):
                    msg = f"**{ticker} {greek.upper()} Alert**: Max Negative shifted from {prev_min} to {max_neg}"
                    if msg not in alerts:
                        alerts.append(msg)
            except:
                pass

        # Guardar datos actuales para la próxima comparación
        pd.to_pickle(agg_by_strike, pickle_path)

    except Exception as e:
        print(f"[ALERTS ERROR] {ticker}: {e}")

    return alerts


# --- PROCESAMIENTO PRINCIPAL ---
async def process_ticker(session, ticker, expir, greek_filter="gamma"):
    try:
        print(f"[PROCESSING] {ticker} {expir}...")
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
                print("PREVE CLOSE PRICE ", prev_close_price)
            if q.get("symbol") == get_SOFR_ticker():
                sofr = float(q.get("last"))

        yield_val = (100 - sofr) / 100

        if "SPX" in ticker:
            now_ny = pd.Timestamp.now(tz="America/New_York")
            hora_ny = now_ny.time()
            rth_start = time(9, 30)
            rth_end = time(
                16, 15
            )  # SPX cierra a las 16:00, pero precios se asientan hasta 16:15
            # Si estamos en horario regular (RTH), usamos el spot directo
            if rth_start <= hora_ny <= rth_end:
                precio_spot_final = spot
            else:
                # Estamos en ETH (Overnight). Necesitamos el futuro /ES obligatoriamente
                print("Calculando SPX nocturno basado en futuro /ES...")

                # Forzamos la búsqueda del futuro actual (ej: /ESH6)
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
                        # Fallback si no encontramos precio del futuro
                        print(
                            "No se pudo obtener precio del futuro, usando último spot conocido."
                        )
                        precio_spot_final = spot
                except Exception as e:
                    print(f"Error obteniendo datos del futuro: {e}")
                    precio_spot_final = spot

            spot = precio_spot_final

        # --- FILTRADO CORRECTO PARA EVITAR ERROR 'record_not_found' ---
        t_list_clean = [t for t in t_list if "SR3" not in t]
        exp_dates, exp_strikes = await tasty_expirations_strikes(session, t_list_clean)

        today = pd.Timestamp.now(tz="America/New_York")
        exp_clean = expir.replace(" ", "").lower()
        all_dates = get_all_unique_expirations_timestamps(exp_dates)

        # Seleccionar expiración (0dte logic)
        first = all_dates[0] if today <= all_dates[0] else all_dates[1]
        sel_date = 0
        if exp_clean != "all":
            sel_date = pd.Timestamp(expir_to_datetime(exp_clean)).tz_localize(
                "America/New_York"
            ) + timedelta(hours=16)
        if sel_date == 0:
            sel_date = all_dates[-1]

        low, high = get_strike_bounds(exp_strikes, spot)
        req = {
            "tickers": t_list_clean,
            "start_date": first.date(),
            "end_date": sel_date.date(),
            "lower_strike": low,
            "upper_strike": high,
        }

        gr_list, _ = await tasty_data(session, options_requested=req)
        opt_data = format_data(gr_list, today)

        # 3. Calcular Griegas (Tu función pesada)
        this_opex, _ = is_third_friday(first, "America/New_York")
        today_str = today.strftime("%Y %b %d, %I:%M %p %Z")

        exp_data = await calc_exposures(
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

        # Desempaquetar lo necesario para guardar
        # (Tu función devuelve una tupla gigante, la mantenemos)
        full_data = exp_data + (exp_clean, t_san, low, high, prev_close_price, greek_filter)

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
            "zerodelta",
            "zerogamma",
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

        # 4. Calcular Alertas (HEADLESS)
        # Usamos el dataframe 'option_data' que está en la posición 0 de la tupla
        df_options = exp_data[0]
        alerts = calculate_alerts_headless(
            df_options, t_san, exp_clean, greek_filter, spot
        )
        exp_dict["alerts"] = alerts

        # 5. Guardar JSON
        def serialize(obj):
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict(orient="split")
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (pd.Timestamp, date, datetime)):
                return obj.isoformat()
            if isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, (np.int64, np.int32)):
                return int(obj)
            return str(obj)

        json_dir = "json_data"
        if not path.exists(json_dir):
            makedirs(json_dir, exist_ok=True)

        # Usamos timestamp en el nombre para historial, o fijo para sobrescribir (según prefieras)
        # Para tu dashboard web, probablemente prefieras sobrescribir o tener un "latest".
        # Aquí guardo con timestamp como tenías.
        ny_time = pd.Timestamp.now(tz="America/New_York")
        fname = f"{t_san}_{exp_clean}_ExposureData_{ny_time.strftime('%Y%m%d_%H%M%S')}.json"

        # OP
        with open(path.join(json_dir, fname), "w") as f:
            json.dump(exp_dict, f, default=serialize)

        print(f"[SUCCESS] {ticker} JSON saved.", {fname})

    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        traceback.print_exc()


# --- BUCLE PRINCIPAL ---
async def main_loop():
    load_dotenv()
    username = getenv("TASTYTRADE_USERNAME")
    password = getenv("TASTYTRADE_PASSWORD")

    print("[SYSTEM] Iniciando GEX JSON Daemon...")

    session = Session(provider_secret=os.getenv('TASTYTRADE_CLIENT_SECRET'),
        refresh_token=os.getenv('TASTYTRADE_REFRESH_TOKEN'))

    while True:
        # 1. Obtener la hora actual en NY
        now_ny = pd.Timestamp.now(tz="America/New_York")
        trading_date = now_ny.date()
        
        # Ajuste para la madrugada (antes de las 3:00 AM cuenta como el día anterior)
        if now_ny.time() < time(3, 0):
            trading_date = trading_date - timedelta(days=1)

        # 2. Validar si el mercado está abierto hoy
        if not is_market_open(trading_date):
            print(f"[{now_ny.strftime('%H:%M:%S')}] NYSE CERRADO. Esperando 50 minutos...")
            await asyncio.sleep(3000)  # Duerme 5 minutos para no consumir CPU ni log spam
            continue
            
        if not (time(3, 0) <= current_time <= time(17, 0)):
            print(f"[{now_ny.strftime('%H:%M:%S')}] FUERA DE HORARIO. En reposo (50 min)...")
            await asyncio.sleep(3000)
            continue
        
        start_time = datetime.now()

        # Validar sesión
        if not await session.validate():
            print("[AUTH] Re-conectando sesión...")
            session = Session(provider_secret=os.getenv('TASTYTRADE_CLIENT_SECRET'),
                refresh_token=os.getenv('TASTYTRADE_REFRESH_TOKEN'))

        tasks = []
        for ticker in TICKERS_TO_TRACK:
            # Procesamos secuencialmente o en paralelo
            # Para evitar rate limits de Tastytrade, mejor secuencial o con pequeños delays
            await process_ticker(session, ticker, EXPIRATION_MODE)
        await asyncio.sleep(20)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("[STOP] Detenido por usuario.")
