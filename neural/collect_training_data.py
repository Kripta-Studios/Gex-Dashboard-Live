"""
Training Data Collector for Hybrid Model Trading Bot

Collects and preprocesses features from Greek exposure JSONs and IB data
to create training datasets for the neural network.

Usage:
    python collect_training_data.py --output training_data.csv
"""

import sys
import os
import json
import glob
import re
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass  # dotenv not installed, use environment variables directly


def get_env_path(key: str, default: str) -> str:
    """Get environment variable and clean up quotes/spaces."""
    value = os.getenv(key, default)
    # Remove surrounding quotes if present
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    return value.strip()


# --- CONFIGURATION ---
# Paths (Linux server paths - adjust for local testing)
GREEK_DATA_DIR = get_env_path("GREEK_DATA_DIR", os.path.join(PROJECT_ROOT, "trading_data", "json_data"))
IB_CHARTS_DIR = get_env_path("IB_CHARTS_DIR", os.path.join(PROJECT_ROOT, "trading_data", "ib_backtest"))
IB_BACKTEST_DIR = get_env_path("IB_BACKTEST_DIR", os.path.join(PROJECT_ROOT, "trading_data", "ib_backtest"))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "training_data")

# For local Windows testing
if sys.platform == "win32":
    # Adjust paths for local testing if needed
    pass

# Tickers to process - only those used by the hybrid model
# SPX/SPY for /ES trading, QQQ for /NQ trading
TICKERS = [
    "SPX",   # S&P 500 Index -> used for /ES
    "SPY",   # S&P 500 ETF -> also used for /ES
    "QQQ",   # Nasdaq 100 ETF -> used for /NQ
]
FUTURES = ["/ES", "/NQ"]

# Precision threshold for "at level" detection (±0.04%)
LEVEL_PROXIMITY_THRESHOLD = 0.0004

# Minimum price move for a valid signal (±0.4%) - Stricter to avoid chop
TARGET_MOVE_THRESHOLD = 0.004

# Lookahead window for target calculation (minutes)
# Lookahead window for target calculation (minutes)
LOOKAHEAD_MINUTES = 120

# Timezone Offset (Madrid to EST)
# Madrid is UTC+1 (Winter) / UTC+2 (Summer)
# EST is UTC-5 (Winter) / EDT is UTC-4 (Summer)
# Difference is roughly 6 hours (Madrid is ahead)
# We need to SUBTRACT 6 hours from filename time to get EST
TIMEZONE_OFFSET_HOURS = 0


def get_net_greek_exposure(data: dict, greek_name: str) -> float:
    """Calculate net Greek exposure from the 'all' array."""
    greek_data = data.get(greek_name, {})
    if isinstance(greek_data, dict):
        all_data = greek_data.get("all", [])
        if isinstance(all_data, list) and len(all_data) > 0:
            return float(np.sum(all_data))
    return 0.0


def find_max_min_greek_level(data: dict, greek_name: str):
    """Find strikes with max/min Greek exposure."""
    levels = data.get("levels", [])
    greek_data = data.get(greek_name, {})
    
    if isinstance(greek_data, dict):
        all_data = greek_data.get("all", [])
    else:
        all_data = []
    
    if not levels or not all_data or len(levels) != len(all_data):
        return None, None
    
    levels = np.array(levels)
    values = np.array(all_data)
    
    max_idx = np.argmax(values)
    min_idx = np.argmin(values)
    
    return float(levels[max_idx]), float(levels[min_idx])


def classify_gamma_regime(net_gamma: float, threshold: float = 0.1) -> int:
    """Classify gamma regime: 0=short, 1=neutral, 2=long"""
    if net_gamma > threshold:
        return 2  # Long gamma
    elif net_gamma < -threshold:
        return 0  # Short gamma
    return 1  # Neutral


def is_near_level(price: float, level: float, threshold: float = LEVEL_PROXIMITY_THRESHOLD) -> bool:
    """Check if price is within threshold of a level."""
    if level is None or level == 0:
        return False
    return abs(price - level) / price <= threshold


def calculate_fibonacci_levels(ib_high: float, ib_low: float):
    """Calculate Fibonacci extension levels from IB range."""
    ib_range = ib_high - ib_low
    
    # Extensions above IB high
    fib_127_up = ib_low + (ib_range * 1.272)
    fib_161_up = ib_low + (ib_range * 1.618)
    fib_200_up = ib_low + (ib_range * 2.0)
    
    # Extensions below IB low
    fib_127_dn = ib_low + (ib_range * -0.272)
    fib_161_dn = ib_low + (ib_range * -0.618)
    fib_200_dn = ib_low + (ib_range * -1.0)
    
    return {
        "fib_127_up": fib_127_up,
        "fib_161_up": fib_161_up,
        "fib_200_up": fib_200_up,
        "fib_127_dn": fib_127_dn,
        "fib_161_dn": fib_161_dn,
        "fib_200_dn": fib_200_dn,
    }


def simple_rsi(prices: list, period: int = 14) -> float:
    """Calculate simple RSI from price list."""
    if len(prices) < period + 1:
        return 50.0  # Default neutral
    
    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)

def rescue_corrupted_data(raw_text: str) -> dict:
    """
    Lee el texto bruto y extrae los datos usando Regex, ignorando 
    la corrupción, llaves faltantes o nombres truncados.
    """
    data = {}
    
    # 1. Rescatar el Precio (spot_price)
    # Buscamos cosas como "spot_price": 631.13, "price": 631.13 o el truncado e": 631.13
    # Patrón: busca cualquier letra(s) seguidas de ": y un número decimal
    price_matches = re.findall(r'[a-zA-Z_]"\s*:\s*([0-9]{3,5}\.[0-9]{1,4})', raw_text)
    if price_matches:
        # Cogemos el último encontrado, ya que la corrupción suele estar por añadir datos nuevos al final
        data["spot_price"] = float(price_matches[-1])
    else:
        # Fallback basado en tu ejemplo: el número justo antes de "greek_filter"
        fallback = re.search(r'([0-9]{3,5}\.[0-9]{1,4})\s*,\s*"greek_filter"', raw_text)
        if fallback:
            data["spot_price"] = float(fallback.group(1))

    # 2. Rescatar Zero Gamma y Zero Delta
    for key in ["zerogamma", "zerodelta"]:
        matches = re.findall(fr'"{key}"\s*:\s*([0-9.-]+)', raw_text)
        if matches:
            data[key] = float(matches[-1])

    # 3. Rescatar el array de "levels" (Strikes)
    # Busca "levels": [ ... ] y extrae los números de dentro
    levels_matches = re.findall(r'"levels"\s*:\s*\[([\s0-9.,-]+)\]', raw_text)
    if levels_matches:
        try:
            levels_str = levels_matches[-1] # Cogemos la última versión válida
            data["levels"] = [float(x.strip()) for x in levels_str.split(',') if x.strip()]
        except:
            pass

    # 4. Rescatar las Griegas (totalgamma, totalvanna, etc.)
    greeks = ["totalgamma", "totalvanna", "totalcharm", "totaldgex", 
              "totalzomma", "totaldelta", "totalvega", "totalvomma"]
    
    for greek in greeks:
        # Buscamos el bloque de la griega, por ejemplo "totalgamma": {... "all": [1.2, 3.4...]}
        # re.DOTALL permite que la búsqueda funcione aunque haya saltos de línea por el medio
        pattern = fr'"{greek}"\s*:\s*\{{.*?"all"\s*:\s*\[([\s0-9.,-]+)\]'
        matches = re.findall(pattern, raw_text, re.DOTALL)
        if matches:
            try:
                vals_str = matches[-1]
                vals = [float(x.strip()) for x in vals_str.split(',') if x.strip()]
                data[greek] = {"all": vals}
            except:
                pass

    return data

def extract_features_from_greek_file(filepath: str) -> dict:
    """Extract features from a single Greek exposure JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            raw_content = f.read().strip()
            
        if not raw_content:
            return None

        data = None
        # INTENTO 1: Parseo normal
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            # INTENTO 2: ¡Tu idea! Rescate por Fuerza Bruta / Regex
            data = rescue_corrupted_data(raw_content)

        if not data or "spot_price" not in data:
            return None

        # --- VALIDACIÓN DE SEGURIDAD ---
        # Si rescatamos los arrays pero uno se cortó por la mitad, tendrán longitudes distintas.
        # En ese caso, recortamos ambos al tamaño del más pequeño para que no salte error en find_max_min_greek_level
        levels = data.get("levels", [])
        gamma_all = data.get("totalgamma", {}).get("all", [])
        
        if levels and gamma_all and len(levels) != len(gamma_all):
            min_len = min(len(levels), len(gamma_all))
            data["levels"] = levels[:min_len]
            data["totalgamma"]["all"] = gamma_all[:min_len]
            # Hacemos lo mismo para las demás griegas si existen
            for greek in ["totalvanna", "totalcharm", "totaldgex", "totalzomma", "totaldelta", "totalvega", "totalvomma"]:
                if greek in data and "all" in data[greek]:
                    data[greek]["all"] = data[greek]["all"][:min_len]
        
        spot_price = float(data.get("spot_price", 0))
        if spot_price == 0:
            return None
        
        # Net Greek exposures
        net_gamma = get_net_greek_exposure(data, "totalgamma")
        net_vanna = get_net_greek_exposure(data, "totalvanna")
        net_charm = get_net_greek_exposure(data, "totalcharm")
        net_dgex = get_net_greek_exposure(data, "totaldgex")
        net_zomma = get_net_greek_exposure(data, "totalzomma")
        net_delta = get_net_greek_exposure(data, "totaldelta")
        net_vega = get_net_greek_exposure(data, "totalvega")
        net_vomma = get_net_greek_exposure(data, "totalvomma")
        
        # Zero crossing levels
        zero_gamma = float(data.get("zerogamma", 0))
        zero_delta = float(data.get("zerodelta", 0))
        
        # Max/min Greek strikes
        max_gamma, min_gamma = find_max_min_greek_level(data, "totalgamma")
        max_vanna, min_vanna = find_max_min_greek_level(data, "totalvanna")
        max_dgex, min_dgex = find_max_min_greek_level(data, "totaldgex")
        max_zomma, min_zomma = find_max_min_greek_level(data, "totalzomma")
        max_vega, min_vega = find_max_min_greek_level(data, "totalvega")
        max_vomma, min_vomma = find_max_min_greek_level(data, "totalvomma")
        
        # Gamma regime classification
        gamma_regime = classify_gamma_regime(net_gamma)
        
        # Greek signals (binary)
        vanna_bullish = 1 if net_vanna > 0.1 else 0
        charm_bullish = 1 if net_charm > 0.1 else 0
        dgex_sticky = 1 if net_dgex > 0.1 else 0
        zomma_stabilizing = 1 if net_zomma > 0.1 else 0
        vega_elevated = 1 if abs(net_vega) > 0.1 else 0
        
        # Price relative to key levels
        dist_to_max_gamma = (spot_price - max_gamma) / spot_price if max_gamma else 0
        dist_to_min_gamma = (spot_price - min_gamma) / spot_price if min_gamma else 0
        dist_to_min_vanna = (spot_price - min_vanna) / spot_price if min_vanna else 0
        dist_to_zero_gamma = (spot_price - zero_gamma) / spot_price if zero_gamma else 0
        dist_to_max_vega = (spot_price - max_vega) / spot_price if max_vega else 0
        dist_to_min_vega = (spot_price - min_vega) / spot_price if min_vega else 0
        dist_to_max_vomma = (spot_price - max_vomma) / spot_price if max_vomma else 0
        dist_to_min_vomma = (spot_price - min_vomma) / spot_price if min_vomma else 0
        
        # Check if near key levels
        near_max_gamma = 1 if is_near_level(spot_price, max_gamma) else 0
        near_min_gamma = 1 if is_near_level(spot_price, min_gamma) else 0
        near_min_vanna = 1 if is_near_level(spot_price, min_vanna) else 0
        near_zero_gamma = 1 if is_near_level(spot_price, zero_gamma) else 0
        
        # Extract timestamp from filename
        filename = os.path.basename(filepath)
        match = re.search(r"_(\d{8})_(\d{6})\.json", filename)
        if match:
            timestamp_str = f"{match.group(1)} {match.group(2)}"
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d %H%M%S")
            
        else:
            timestamp = None
        
        return {
            "timestamp": timestamp,
            "spot_price": spot_price,
            # Net exposures (normalized by dividing by typical values)
            "net_gamma": net_gamma,
            "net_vanna": net_vanna,
            "net_charm": net_charm,
            "net_dgex": net_dgex,
            "net_zomma": net_zomma,
            "net_delta": net_delta,
            # Key levels
            "max_gamma_strike": max_gamma,
            "min_gamma_strike": min_gamma,
            "min_vanna_strike": min_vanna,
            "max_dgex_strike": max_dgex,
            "min_dgex_strike": min_dgex,
            "zero_gamma": zero_gamma,
            # Regime & signals
            "gamma_regime": gamma_regime,
            "vanna_bullish": vanna_bullish,
            "charm_bullish": charm_bullish,
            "dgex_sticky": dgex_sticky,
            "zomma_stabilizing": zomma_stabilizing,
            # Distances
            "dist_to_max_gamma": dist_to_max_gamma,
            "dist_to_min_gamma": dist_to_min_gamma,
            "dist_to_min_vanna": dist_to_min_vanna,
            "dist_to_zero_gamma": dist_to_zero_gamma,
            # Near level flags
            "near_max_gamma": near_max_gamma,
            "near_min_gamma": near_min_gamma,
            "near_min_vanna": near_min_vanna,
            "near_zero_gamma": near_zero_gamma,
            # Vega/Vomma features
            "net_vega": net_vega,
            "net_vomma": net_vomma,
            "vega_elevated": vega_elevated,
            "max_vega_strike": max_vega,
            "min_vega_strike": min_vega,
            "max_vomma_strike": max_vomma,
            "min_vomma_strike": min_vomma,
            "dist_to_max_vega": dist_to_max_vega,
            "dist_to_min_vega": dist_to_min_vega,
            "dist_to_max_vomma": dist_to_max_vomma,
            "dist_to_min_vomma": dist_to_min_vomma,
        }

    except json.JSONDecodeError as e:
        print(f"Skipping corrupted JSON: {filepath} ({e})")
        return None
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return None


def load_ib_data(ticker: str, date_str: str) -> dict:
    """Load IB data for a ticker and date."""
    # For futures like /ES, the files are saved as ES (without slash)
    file_ticker = ticker.lstrip("/")
    
    # Try different date formats: YYYYMMDD and YYYY-MM-DD
    date_formats = [date_str]
    if len(date_str) == 8:  # YYYYMMDD
        date_formats.append(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}")
    
    # Try ib_backtest first (historical with volume profile)
    filepath = None
    for fmt in date_formats:
        test_path = os.path.join(IB_BACKTEST_DIR, f"ib_data_{file_ticker}_{fmt}.json")
        if os.path.exists(test_path):
            filepath = test_path
            break
        test_path = os.path.join(IB_CHARTS_DIR, f"ib_data_{file_ticker}_{fmt}.json")
        if os.path.exists(test_path):
            filepath = test_path
            break
    
    if filepath is None:
        return None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        analysis = data.get("analysis", {})
        volume_profile = data.get("volume_profile", {})
        
        return {
            "ib_high": analysis.get("ib_high", 0),
            "ib_low": analysis.get("ib_low", 0),
            "ib_range": analysis.get("ib_range", 0),
            "vpoc": volume_profile.get("vpoc", 0),
            "vah": volume_profile.get("vah", 0),
            "val": volume_profile.get("val", 0),
            "total_volume": volume_profile.get("total_volume", 0),
            "series": data.get("series", []),
        }
    except Exception as e:
        print(f"Error loading IB data {filepath}: {e}")
        return None


# Fourier output directory (same as in fourier_service_fast.py)
FOURIER_DIR = get_env_path("FOURIER_DIR", os.path.join(PROJECT_ROOT, "trading_data", "fourier"))


def load_fourier_data(ticker: str, date_str: str) -> dict:
    """Load IV data from Fourier JSON files.
    
    The fourier JSONs contain:
    - atm_put_iv: ATM put implied volatility
    - iv_fft: Fourier-filtered IV
    - spot: Spot price
    - spot_fft: Fourier-filtered spot price
    """
    # Convert date format: YYYYMMDD -> YYYYMMDD (already correct)
    filepath = os.path.join(FOURIER_DIR, f"fourier_data_{ticker}_{date_str}.json")
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if not data or len(data) == 0:
            return None
        
        # Get latest values from the time series
        latest = data[-1] if isinstance(data, list) else data
        
        # Calculate IV statistics across the day
        if isinstance(data, list):
            iv_values = [d.get("atm_put_iv", 0) for d in data if d.get("atm_put_iv")]
            if iv_values:
                current_iv = float(latest.get("atm_put_iv", 0))
                iv_mean = np.mean(iv_values)
                iv_std = np.std(iv_values) if len(iv_values) > 1 else 0
                iv_min = np.min(iv_values)
                iv_max = np.max(iv_values)
                
                # IV zscore (how far from mean in std units)
                iv_zscore = (current_iv - iv_mean) / iv_std if iv_std > 0 else 0
                
                # IV percentile (0-1)
                iv_pct = (current_iv - iv_min) / (iv_max - iv_min) if iv_max > iv_min else 0.5
            else:
                current_iv = 0
                iv_zscore = 0
                iv_pct = 0.5
        else:
            current_iv = float(latest.get("atm_put_iv", 0))
            iv_zscore = 0
            iv_pct = 0.5
        
        return {
            "atm_iv": current_iv,
            "iv_zscore": float(iv_zscore),
            "iv_percentile": float(iv_pct),
            "iv_fft": float(latest.get("iv_fft", current_iv)),
        }
    except Exception as e:
        print(f"Error loading Fourier data {filepath}: {e}")
        return None


def load_vix_data(date_str: str) -> dict:
    """Load VIX data for correlation with IV.
    
    VIX spot comes from IB minute bars (ib_backtest/ib_data_VIX_{date}.json).
    VIX gamma comes from weekly options exposure (VIX_weekly_ExposureData_*.json).
    """
    defaults = {"vix_spot": 0, "vix_gamma": 0, "vix_regime": 1}
    
    vix_spot = 0
    vix_gamma = 0
    
    # --- VIX Spot from IB minute bars ---
    # Try both date formats: YYYYMMDD and YYYY-MM-DD
    for fmt in [date_str, f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str]:
        ib_path = os.path.join(IB_BACKTEST_DIR, f"ib_data_VIX_{fmt}.json")
        if os.path.exists(ib_path):
            try:
                with open(ib_path, 'r') as f:
                    ib_data = json.load(f)
                series = ib_data.get("series", [])
                if series:
                    # Use last available price as VIX spot
                    vix_spot = float(series[-1].get("price", series[-1].get("close", 0)))
                break
            except Exception as e:
                print(f"Error loading VIX IB data: {e}")
    
    # --- VIX Gamma from weekly exposure data ---
    pattern = os.path.join(GREEK_DATA_DIR, f"*VIX*weekly*ExposureData*{date_str}*.json")
    vix_files = sorted(glob.glob(pattern))
    if vix_files:
        try:
            with open(vix_files[-1], 'r') as f:
                data = json.load(f)
            vix_gamma = get_net_greek_exposure(data, "totalgamma")
            # If we didn't get spot from IB, try from exposure data
            if vix_spot == 0:
                vix_spot = float(data.get("spot_price", 0))
        except Exception as e:
            print(f"Error loading VIX weekly data: {e}")
    
    # VIX regime classification
    if vix_spot > 25:
        vix_regime = 2  # High fear
    elif vix_spot > 18:
        vix_regime = 1  # Elevated
    else:
        vix_regime = 0  # Low/Complacent
    
    return {
        "vix_spot": vix_spot,
        "vix_gamma": vix_gamma,
        "vix_regime": vix_regime,
    }


def calculate_target_label(series: list, current_idx: int, lookahead: int = LOOKAHEAD_MINUTES) -> tuple:
    """
    Calculate target label based on future price movement.
    Returns: (label, time_to_target, time_to_stop, max_favorable_move)
        label: -1 (SHORT), 0 (HOLD), 1 (LONG)
        time_to_target: Minutes until target (0.3%) is hit (0 if not hit)
        time_to_stop: Minutes until stop (opposite 0.3%) is hit (0 if not hit)
        max_favorable_move: Maximum favorable move percentage
    """
    if current_idx + lookahead >= len(series):
        return (0, 0, 0, 0.0)  # Not enough future data
    
    current_price = series[current_idx].get("price", 0)
    if current_price == 0:
        return (0, 0, 0, 0.0)
    
    # Track timing and max moves
    max_price = current_price
    min_price = current_price
    max_price_time = 0
    min_price_time = 0
    
    # For LONG direction
    time_to_target_long = 0
    time_to_stop_long = 0
    
    # For SHORT direction  
    time_to_target_short = 0
    time_to_stop_short = 0
    
    target_threshold = TARGET_MOVE_THRESHOLD  # 0.3%
    
    for i in range(current_idx + 1, min(current_idx + lookahead + 1, len(series))):
        price = series[i].get("price", current_price)
        minutes_elapsed = i - current_idx
        
        # Track max/min prices and when they occurred
        if price > max_price:
            max_price = price
            max_price_time = minutes_elapsed
        if price < min_price:
            min_price = price
            min_price_time = minutes_elapsed
        
        up_pct = (price - current_price) / current_price
        down_pct = (current_price - price) / current_price
        
        # Track first time target/stop is hit
        if time_to_target_long == 0 and up_pct >= target_threshold:
            time_to_target_long = minutes_elapsed
        if time_to_stop_long == 0 and down_pct >= target_threshold:
            time_to_stop_long = minutes_elapsed
            
        if time_to_target_short == 0 and down_pct >= target_threshold:
            time_to_target_short = minutes_elapsed
        if time_to_stop_short == 0 and up_pct >= target_threshold:
            time_to_stop_short = minutes_elapsed
    
    up_move = (max_price - current_price) / current_price
    down_move = (current_price - min_price) / current_price
    
    # Determine direction based on which move is larger and significant
    if up_move >= TARGET_MOVE_THRESHOLD and up_move > down_move:
        # LONG is better - return LONG metrics
        return (1, time_to_target_long, time_to_stop_long, up_move)
    elif down_move >= TARGET_MOVE_THRESHOLD and down_move > up_move:
        # SHORT is better - return SHORT metrics
        return (-1, time_to_target_short, time_to_stop_short, down_move)
    
    # HOLD - no clear direction
    return (0, 0, 0, 0.0)


def sign_divergence(a: float, b: float) -> float:
    """Compute sign divergence between two values.
    Returns: 1.0 if signs differ, 0.0 if same, 0.5 if either is ~zero."""
    if abs(a) < 0.01 or abs(b) < 0.01:
        return 0.5  # One side is neutral
    if (a > 0) != (b > 0):
        return 1.0  # Divergence
    return 0.0  # Agreement


def rbf_confluence(level_a: float, level_b: float, spot_price: float, sigma: float = 0.05) -> float:
    """Calculate RBF (Gaussian kernel) confluence between two price levels.
    
    Returns value in [0, 1] where 1.0 = levels are identical,
    0.0 = levels are far apart relative to sigma.
    
    Args:
        level_a: First price level
        level_b: Second price level  
        spot_price: Current spot price for normalization
        sigma: Width parameter (0.05 = ~5% price distance = 50% confluence)
    """
    if spot_price == 0 or level_a is None or level_b is None:
        return 0.0
    d = abs(level_a - level_b) / spot_price
    confluence = np.exp(-d**2 / (2 * sigma**2))
    # Clip to [0, 1] and handle NaN/inf
    if not np.isfinite(confluence):
        return 0.0
    return float(np.clip(confluence, 0.0, 1.0))


def load_weekly_greeks(ticker: str, date_str: str) -> dict:
    """Load weekly options Greek data for a ticker and date.
    
    Returns extracted features with 'wk_' prefix, or defaults (zeros) if unavailable.
    Uses the same JSON structure as 0DTE files.
    """
    defaults = {
        "wk_net_gamma": 0.0, "wk_net_vanna": 0.0, "wk_net_charm": 0.0,
        "wk_net_dgex": 0.0, "wk_net_zomma": 0.0, "wk_net_delta": 0.0,
        "wk_net_vega": 0.0, "wk_net_vomma": 0.0,
        "wk_dist_to_max_gamma": 0.0, "wk_dist_to_min_gamma": 0.0,
        "wk_dist_to_max_dgex": 0.0, "wk_dist_to_min_dgex": 0.0,
        "wk_dist_to_max_vega": 0.0, "wk_dist_to_min_vega": 0.0,
        "wk_dist_to_max_vomma": 0.0, "wk_dist_to_min_vomma": 0.0,
        "wk_gamma_regime": 0.5, "wk_vanna_bullish": 0,
        "wk_dgex_sticky": 0, "wk_zomma_stabilizing": 0,
        "wk_vega_elevated": 0,
    }
    
    pattern = os.path.join(GREEK_DATA_DIR, f"*{ticker}*weekly*ExposureData*{date_str}*.json")
    weekly_files = sorted(glob.glob(pattern))
    
    if not weekly_files:
        return defaults
    
    try:
        # Use the latest weekly file for this date
        features = extract_features_from_greek_file(weekly_files[-1])
        if features is None:
            return defaults
        
        spot = features["spot_price"]
        
        # DGEX key levels from weekly
        max_dgex = features.get("max_dgex_strike")
        min_dgex = features.get("min_dgex_strike")
        max_gamma = features.get("max_gamma_strike")
        min_gamma = features.get("min_gamma_strike")
        
        return {
            "wk_net_gamma": features["net_gamma"],
            "wk_net_vanna": features["net_vanna"],
            "wk_net_charm": features["net_charm"],
            "wk_net_dgex": features["net_dgex"],
            "wk_net_zomma": features["net_zomma"],
            "wk_net_delta": features.get("net_delta", 0.0),
            "wk_net_vega": features.get("net_vega", 0.0),
            "wk_net_vomma": features.get("net_vomma", 0.0),
            "wk_dist_to_max_gamma": (spot - max_gamma) / spot if max_gamma and spot else 0.0,
            "wk_dist_to_min_gamma": (spot - min_gamma) / spot if min_gamma and spot else 0.0,
            "wk_dist_to_max_dgex": (spot - max_dgex) / spot if max_dgex and spot else 0.0,
            "wk_dist_to_min_dgex": (spot - min_dgex) / spot if min_dgex and spot else 0.0,
            "wk_dist_to_max_vega": (spot - features.get("max_vega_strike", spot)) / spot if spot else 0.0,
            "wk_dist_to_min_vega": (spot - features.get("min_vega_strike", spot)) / spot if spot else 0.0,
            "wk_dist_to_max_vomma": (spot - features.get("max_vomma_strike", spot)) / spot if spot else 0.0,  # <-- NUEVO
            "wk_dist_to_min_vomma": (spot - features.get("min_vomma_strike", spot)) / spot if spot else 0.0,  # <-- NUEVO
            "wk_gamma_regime": features["gamma_regime"] / 2.0,  # normalize 0-1
            "wk_vanna_bullish": features["vanna_bullish"],
            "wk_dgex_sticky": features["dgex_sticky"],
            "wk_zomma_stabilizing": features["zomma_stabilizing"],
            "wk_vega_elevated": features.get("vega_elevated", 0),
        }
    except Exception as e:
        print(f"Error loading weekly Greeks for {ticker}/{date_str}: {e}")
        return defaults


def process_ticker_date(args: tuple) -> list:
    """Process a single (ticker, date) pair. Designed to run in parallel.
    
    Args:
        args: Tuple of (ticker, target_date, futures_greek_map)
    Returns:
        List of sample dictionaries for this ticker/date
    """
    ticker, target_date, futures_greek_map = args
    samples = []
    
    # Determine Greek source ticker (for futures, use underlying)
    greek_ticker = futures_greek_map.get(ticker, ticker)
    date_str = target_date.strftime("%Y%m%d")
    
    # Load Greek files for this date (from underlying for futures)
    pattern = os.path.join(GREEK_DATA_DIR, f"*{greek_ticker}*0dte*ExposureData*{date_str}*.json")
    greek_files = sorted(glob.glob(pattern))
    
    if not greek_files:
        return []
    
    # Load IB data for context
    ib_data = load_ib_data(ticker, date_str)
    if not ib_data:
        return []
    
    ib_high = ib_data["ib_high"]
    ib_low = ib_data["ib_low"]
    series = ib_data["series"]
    
    if not series:
        return []
    
    # Load weekly Greek data (once per day, same for all 0DTE snapshots)
    weekly_data = load_weekly_greeks(greek_ticker, date_str)
    
    # Calculate Fibonacci levels
    fib_levels = calculate_fibonacci_levels(ib_high, ib_low)
    
    # Build price lookup by time
    price_by_time = {}
    for i, candle in enumerate(series):
        time_str = candle.get("time", "")
        price_by_time[time_str] = (i, candle.get("price", 0))
    
    # Load IV data from Fourier (once per day)
    fourier_data = load_fourier_data(greek_ticker, date_str)
    if fourier_data:
        atm_iv = fourier_data["atm_iv"]
        iv_zscore = fourier_data["iv_zscore"]
        iv_percentile = fourier_data["iv_percentile"]
    else:
        atm_iv = 0.0
        iv_zscore = 0.0
        iv_percentile = 0.5
    
    # Load VIX data (once per day)
    vix_data = load_vix_data(date_str)
    vix_spot = vix_data["vix_spot"]
    vix_gamma = vix_data["vix_gamma"]
    vix_regime = vix_data["vix_regime"]
    
    # Process each Greek file
    prev_vals = None  # Cache for temporal deltas
    for greek_file in greek_files:
        features = extract_features_from_greek_file(greek_file)
        if features is None or features["timestamp"] is None:
            continue
        
        timestamp = features["timestamp"]
        time_key = timestamp.strftime("%H:%M")
        spot = features["spot_price"]
        
        # Skip data outside 08:00 - 17:00 EST (keep 1.5h pre-market + RTH + 1h post)
        if timestamp.time() < dt_time(8, 0) or timestamp.time() > dt_time(17, 0):
            continue
        
        # Find corresponding price series index
        if time_key not in price_by_time:
            continue
        
        series_idx, series_price = price_by_time[time_key]
        
        # Calculate target label and timing
        target_label, time_to_target, time_to_stop, max_move = calculate_target_label(series, series_idx, LOOKAHEAD_MINUTES)
        
        # IB context features
        price_vs_ib_high = (spot - ib_high) / spot if spot > 0 else 0
        price_vs_ib_low = (spot - ib_low) / spot if spot > 0 else 0
        ib_range_pct = (ib_high - ib_low) / spot if spot > 0 else 0
        
        # Near IB levels
        near_ib_high = 1 if is_near_level(spot, ib_high) else 0
        near_ib_low = 1 if is_near_level(spot, ib_low) else 0
        
        # Fibonacci distances (bullish + bearish extensions)
        ib_range = ib_high - ib_low if ib_high > ib_low else 1e-6
        dist_fib_127_up = (spot - fib_levels["fib_127_up"]) / spot
        dist_fib_161_up = (spot - fib_levels["fib_161_up"]) / spot
        dist_fib_200_up = (spot - fib_levels["fib_200_up"]) / spot
        dist_fib_127_dn = (spot - fib_levels["fib_127_dn"]) / spot
        dist_fib_161_dn = (spot - fib_levels["fib_161_dn"]) / spot
        dist_fib_200_dn = (spot - fib_levels["fib_200_dn"]) / spot
        
        # Position in range
        above_ib = 1 if spot > ib_high else 0
        below_ib = 1 if spot < ib_low else 0
        in_ib_range = 1 if ib_low <= spot <= ib_high else 0
        
        # Time features
        hour_normalized = timestamp.hour / 24.0
        minute_normalized = timestamp.minute / 60.0
        
        # Calculate RSI from recent prices
        prices_before = [series[i].get("price", 0) for i in range(max(0, series_idx - 15), series_idx + 1)]
        rsi = simple_rsi(prices_before)
        
        # Volume context
        total_vol = ib_data.get("total_volume", 1)
        current_vol = series[series_idx].get("volume", 0) if series_idx < len(series) else 0
        vol_relative = current_vol / (total_vol / len(series)) if total_vol > 0 and len(series) > 0 else 1.0
        
        # Combine all features
        sample = {
            "ticker": ticker,
            "date": date_str,
            "time": time_key,
            "timestamp": timestamp,
            "spot_price": spot,
            "target": target_label,
            "time_to_target": time_to_target,
            "time_to_stop": time_to_stop,
            "max_move": max_move,
            # ===== 0DTE Greek features =====
            "net_gamma": features["net_gamma"],
            "net_vanna": features["net_vanna"],
            "net_charm": features["net_charm"],
            "net_dgex": features["net_dgex"],
            "net_zomma": features["net_zomma"],
            "net_delta": features.get("net_delta", 0.0),
            "gamma_regime": features["gamma_regime"],
            "vanna_bullish": features["vanna_bullish"],
            "charm_bullish": features["charm_bullish"],
            "dgex_sticky": features["dgex_sticky"],
            "zomma_stabilizing": features["zomma_stabilizing"],
            # 0DTE Key level distances (now includes DGEX levels)
            "dist_to_max_gamma": features["dist_to_max_gamma"],
            "dist_to_min_gamma": features["dist_to_min_gamma"],
            "dist_to_min_vanna": features["dist_to_min_vanna"],
            "dist_to_zero_gamma": features["dist_to_zero_gamma"],
            "dist_to_max_dgex": (spot - (features.get("max_dgex_strike") or spot)) / spot if spot > 0 else 0,
            "dist_to_min_dgex": (spot - (features.get("min_dgex_strike") or spot)) / spot if spot > 0 else 0,
            # Near level flags
            "near_max_gamma": features["near_max_gamma"],
            "near_min_gamma": features["near_min_gamma"],
            # ===== Weekly Greek features =====
            **weekly_data,
            # ===== Cross-expiry divergence =====
            "gamma_0dte_vs_wk": sign_divergence(features["net_gamma"], weekly_data["wk_net_gamma"]),
            "vanna_0dte_vs_wk": sign_divergence(features["net_vanna"], weekly_data["wk_net_vanna"]),
            "dgex_0dte_vs_wk": sign_divergence(features["net_dgex"], weekly_data["wk_net_dgex"]),
            "delta_0dte_vs_wk": sign_divergence(features.get("net_delta", 0), weekly_data["wk_net_delta"]),
            "vega_0dte_vs_wk": sign_divergence(features.get("net_vega", 0), weekly_data.get("wk_net_vega", 0)),
            "vomma_0dte_vs_wk": sign_divergence(features.get("net_vomma", 0), weekly_data.get("wk_net_vomma", 0)),
            # ===== IB features =====
            "price_vs_ib_high": price_vs_ib_high,
            "price_vs_ib_low": price_vs_ib_low,
            "ib_range_pct": ib_range_pct,
            "near_ib_high": near_ib_high,
            "near_ib_low": near_ib_low,
            "above_ib": above_ib,
            "below_ib": below_ib,
            "in_ib_range": in_ib_range,
            # Fibonacci
            "dist_fib_127_up": dist_fib_127_up,
            "dist_fib_161_up": dist_fib_161_up,
            # IV features
            "atm_iv": atm_iv / 100.0 if atm_iv > 1 else atm_iv,
            "iv_zscore": np.clip(iv_zscore, -3, 3) / 3.0,
            "iv_percentile": iv_percentile,
            # VIX features
            "vix_spot": vix_spot / 50.0 if vix_spot > 0 else 0,
            "vix_gamma": vix_gamma,
            "vix_regime": vix_regime / 2.0,
            # Market context
            "rsi": rsi / 100.0,
            "vol_relative": min(vol_relative, 5.0) / 5.0,
            
            # ===== ENGINEERED FEATURES =====
            # Ratios
            "gamma_vanna_ratio": features["net_gamma"] / (abs(features["net_vanna"]) + 1e-6),
            "dgex_gamma_ratio": features["net_dgex"] / (abs(features["net_gamma"]) + 1e-6),
            "charm_vanna_ratio": features["net_charm"] / (abs(features["net_vanna"]) + 1e-6),
            "delta_gamma_ratio": features.get("net_delta", 0) / (abs(features["net_gamma"]) + 1e-6),
            
            # Temporal Deltas (using prev_vals)
            "gamma_change": features["net_gamma"] - prev_vals["net_gamma"] if prev_vals else 0.0,
            "vanna_change": features["net_vanna"] - prev_vals["net_vanna"] if prev_vals else 0.0,
            "dgex_change": features["net_dgex"] - prev_vals["net_dgex"] if prev_vals else 0.0,
            "delta_change": features.get("net_delta", 0) - prev_vals.get("net_delta", 0) if prev_vals else 0.0,
            "spot_change": (spot - prev_vals["spot"]) / prev_vals["spot"] if prev_vals and prev_vals["spot"] > 0 else 0.0,
            
            # Cross-Features
            "gamma_momentum": (features["net_gamma"] - prev_vals["net_gamma"]) * np.sign(features["net_gamma"]) if prev_vals else 0.0,
            "price_vs_dgex_magnet": ((spot - prev_vals["spot"]) / prev_vals["spot"]) * np.sign((spot - (features.get("max_dgex_strike") or spot))/spot) if prev_vals and prev_vals["spot"] > 0 else 0.0,
            
            # ===== VEGA/VOMMA FEATURES =====
            # 0DTE Vega/Vomma
            "net_vega": features.get("net_vega", 0.0),
            "net_vomma": features.get("net_vomma", 0.0),
            "vega_elevated": features.get("vega_elevated", 0),
            "dist_to_max_vega": features.get("dist_to_max_vega", 0.0),
            "dist_to_min_vega": features.get("dist_to_min_vega", 0.0),
            "dist_to_max_vomma": features.get("dist_to_max_vomma", 0.0),
            "dist_to_min_vomma": features.get("dist_to_min_vomma", 0.0),
            # Cross-expiry divergence (Vega/Vomma)
            "vega_0dte_vs_wk": sign_divergence(features.get("net_vega", 0), weekly_data.get("wk_net_vega", 0)),
            "vomma_0dte_vs_wk": sign_divergence(features.get("net_vomma", 0), weekly_data.get("wk_net_vomma", 0)),
            # Vega/Vomma ratios
            "vega_gamma_ratio": features.get("net_vega", 0) / (abs(features["net_gamma"]) + 1e-6),
            "vomma_vega_ratio": features.get("net_vomma", 0) / (abs(features.get("net_vega", 0)) + 1e-6),
            # Vega/Vomma temporal deltas
            "vega_change": features.get("net_vega", 0) - prev_vals.get("net_vega", 0) if prev_vals else 0.0,
            "vomma_change": features.get("net_vomma", 0) - prev_vals.get("net_vomma", 0) if prev_vals else 0.0,
            
            # ===== IB FIBONACCI EXTENSIONS (bearish side) =====
            "dist_fib_200_up": dist_fib_200_up,
            "dist_fib_127_dn": dist_fib_127_dn,
            "dist_fib_161_dn": dist_fib_161_dn,
            "dist_fib_200_dn": dist_fib_200_dn,
            
            # ===== RBF CONFLUENCES =====
            # IB × Greek confluences
            "confluence_ib_high_max_gamma": rbf_confluence(ib_high, features.get("max_gamma_strike", 0), spot),
            "confluence_ib_low_min_gamma": rbf_confluence(ib_low, features.get("min_gamma_strike", 0), spot),
            "confluence_ib_high_max_vega": rbf_confluence(ib_high, features.get("max_vega_strike", 0), spot),
            "confluence_ib_low_max_dgex": rbf_confluence(ib_low, features.get("max_dgex_strike", 0), spot),
            # Fib × Greek confluences
            "confluence_fib127_bull_max_gamma": rbf_confluence(fib_levels["fib_127_up"], features.get("max_gamma_strike", 0), spot),
            "confluence_fib161_bull_max_vega": rbf_confluence(fib_levels["fib_161_up"], features.get("max_vega_strike", 0), spot),
            "confluence_fib127_bear_min_gamma": rbf_confluence(fib_levels["fib_127_dn"], features.get("min_gamma_strike", 0), spot),
            "confluence_fib161_bear_max_vomma": rbf_confluence(fib_levels["fib_161_dn"], features.get("max_vomma_strike", 0), spot),
            "confluence_fib161_bull_max_vomma": rbf_confluence(fib_levels["fib_161_up"], features.get("max_vomma_strike", 0), spot),
            "confluence_fib127_bear_min_vomma": rbf_confluence(fib_levels["fib_127_dn"], features.get("min_vomma_strike", 0), spot),
            "confluence_fib127_bull_max_dgex": rbf_confluence(fib_levels["fib_127_up"], features.get("max_dgex_strike", 0), spot),
            "confluence_fib127_bear_min_dgex": rbf_confluence(fib_levels["fib_127_dn"], features.get("min_dgex_strike", 0), spot),
            "confluence_fib161_bull_max_dgex": rbf_confluence(fib_levels["fib_161_up"], features.get("max_dgex_strike", 0), spot),
            "confluence_fib161_bear_min_dgex": rbf_confluence(fib_levels["fib_161_dn"], features.get("min_dgex_strike", 0), spot),
        }
        
        # Update previous values for next iteration
        prev_vals = {
            "spot": spot,
            "net_gamma": features["net_gamma"],
            "net_vanna": features["net_vanna"],
            "net_dgex": features["net_dgex"],
            "net_delta": features.get("net_delta", 0),
            "net_vega": features.get("net_vega", 0),
            "net_vomma": features.get("net_vomma", 0),
        }
        
        samples.append(sample)
    
    return samples


def collect_training_data(tickers: list, num_days: int = 365, num_workers: int = None) -> pd.DataFrame:
    """Collect and merge training data from all sources using parallel processing.
    
    Parallelizes by (ticker, date) pairs for maximum CPU utilization.
    
    Args:
        tickers: List of tickers to process
        num_days: Maximum number of trading days to process
        num_workers: Number of parallel workers (default: CPU count)
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import multiprocessing
    
    if num_workers is None:
        num_workers = min(multiprocessing.cpu_count(), 20)  # Use up to 20 workers for Ryzen 9
    
    # Mapping for futures to their underlying Greek source
    FUTURES_GREEK_MAP = {
        "/ES": "SPX",
        "/NQ": "QQQ",
    }
    
    # Combine tickers and futures for processing
    all_symbols = list(tickers) + FUTURES
    
    # Auto-detect available days by scanning the data directories
    available_dates = set()
    
    # Scan Greek data directory for available dates
    for pattern in ["*ExposureData*.json"]:
        for filepath in glob.glob(os.path.join(GREEK_DATA_DIR, pattern)):
            filename = os.path.basename(filepath)
            match = re.search(r"_(\d{8})_\d{6}\.json", filename)
            if match:
                date_str = match.group(1)
                try:
                    available_dates.add(datetime.strptime(date_str, "%Y%m%d").date())
                except:
                    pass
    
    # Scan IB data directories
    for ib_dir in [IB_BACKTEST_DIR, IB_CHARTS_DIR]:
        if os.path.exists(ib_dir):
            for filepath in glob.glob(os.path.join(ib_dir, "ib_data_*.json")):
                filename = os.path.basename(filepath)
                match = re.search(r"ib_data_[\w/]+_([\d-]+)\.json", filename)
                if match:
                    date_part = match.group(1)
                    try:
                        if "-" in date_part:
                            available_dates.add(datetime.strptime(date_part, "%Y-%m-%d").date())
                        else:
                            available_dates.add(datetime.strptime(date_part, "%Y%m%d").date())
                    except:
                        pass
    
    if not available_dates:
        print("No data files found! Check GREEK_DATA_DIR and IB_BACKTEST_DIR paths.")
        return pd.DataFrame()
    
    # Sort dates and limit to num_days
    sorted_dates = sorted(available_dates)
    trading_days = sorted_dates[-num_days:] if len(sorted_dates) > num_days else sorted_dates
    
    # Create (ticker, date) task pairs for fine-grained parallelism
    task_args = []
    for ticker in all_symbols:
        for target_date in trading_days:
            task_args.append((ticker, target_date, FUTURES_GREEK_MAP))
    
    total_tasks = len(task_args)
    print(f"Found {len(available_dates)} unique dates with data")
    print(f"Processing {len(trading_days)} trading days (from {trading_days[0]} to {trading_days[-1]})")
    print(f"Processing {len(all_symbols)} symbols × {len(trading_days)} days = {total_tasks} tasks")
    print(f"Using {num_workers} parallel workers...\n")
    
    # Process in parallel with progress tracking
    all_samples = []
    completed = 0
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_ticker_date, args): args for args in task_args}
        
        for future in as_completed(futures):
            ticker, target_date, _ = futures[future]
            completed += 1
            try:
                samples = future.result()
                if samples:
                    all_samples.extend(samples)
                    # Progress update every 50 tasks
                    if completed % 50 == 0 or completed == total_tasks:
                        print(f"Progress: {completed}/{total_tasks} tasks ({100*completed/total_tasks:.1f}%) - {len(all_samples)} samples")
            except Exception as e:
                print(f"[{ticker} {target_date}] ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    df = pd.DataFrame(all_samples)
    print(f"\nTotal samples collected: {len(df)}")
    
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect training data for PyTorch trading bot")
    parser.add_argument("--output", default="training_data.csv", help="Output CSV filename")
    parser.add_argument("--days", type=int, default=365, help="Max trading days to process (auto-detects available)")
    parser.add_argument("--tickers", nargs="+", default=TICKERS, help="Tickers to process (default: all)")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: CPU count, max 16)")
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Collect data
    df = collect_training_data(args.tickers, args.days, args.workers)
    
    if df.empty:
        print("No data collected!")
        return
    
    # Save to CSV
    output_path = os.path.join(OUTPUT_DIR, args.output)
    df.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")
    
    # Print summary statistics
    print("\n=== Dataset Summary ===")
    print(f"Total samples: {len(df)}")
    print(f"Tickers: {df['ticker'].unique().tolist()}")
    print(f"Dates: {df['date'].nunique()} unique days")
    print(f"\nTarget distribution:")
    print(df['target'].value_counts().sort_index())
    print(f"\nFeature statistics:")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    print(df[numeric_cols].describe().T[['mean', 'std', 'min', 'max']])


if __name__ == "__main__":
    main()
