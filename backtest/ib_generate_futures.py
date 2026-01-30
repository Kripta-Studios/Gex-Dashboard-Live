"""
IB Backtest Data Generator for Futures - Historical Initial Balance JSON Creator

Genera archivos JSON con datos de Initial Balance para los últimos 10 días
hábiles de /ES y /NQ usando datos históricos de velas de Tastytrade.

Este script:
- Soporta contratos de futuros /ES (E-mini S&P 500) y /NQ (E-mini NASDAQ 100)
- Resuelve automáticamente el contrato activo (ej: /ES → /ESH6)
- NO incluye funcionalidad de Discord
- NO genera gráficos PNG
- Guarda JSON en /home/Option-Greeks-Plotting-Discord-Bot/ib_backtest/

Uso:
    python ib_generate_futures.py
"""

import pandas as pd
import numpy as np
import json
import os
import asyncio
from datetime import datetime, timedelta, time as dt_time, date
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# --- IMPORTS TASTYTRADE ---
from tastytrade import Session, DXLinkStreamer
from tastytrade.dxfeed import Candle
from tastytrade.instruments import Future, FutureProduct

# --- CONFIGURACIÓN ---
load_dotenv()
TT_USERNAME = os.getenv("TASTYTRADE_USERNAME")
TT_PASSWORD = os.getenv("TASTYTRADE_PASSWORD")

# Directorio de salida para backtest
OUTPUT_DIR = "/home/Option-Greeks-Plotting-Discord-Bot/ib_backtest"

# Futuros a procesar (símbolos raíz)
FUTURES_TO_TRACK = ["/ES", "/NQ"]

# Número de días hábiles hacia atrás
# NOTA: La API DXLink tiene historial limitado para futuros (~5 días)
DAYS_BACK = 15

# Zonas Horarias
try:
    NY_TZ = ZoneInfo("America/New_York")
except:
    NY_TZ = None

# Crear directorio si no existe
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[SETUP] Creado directorio: {OUTPUT_DIR}")

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


def get_active_future_symbol(session, root_symbol: str) -> tuple:
    """
    Obtiene el símbolo del contrato de futuros activo y su streamer symbol.
    
    Args:
        session: Sesión de Tastytrade
        root_symbol: Símbolo raíz (ej: "/ES", "/NQ")
    
    Returns:
        tuple: (full_symbol, streamer_symbol, future_object)
        El streamer_symbol es el formato correcto para DXLink: /ESH26:XCME
    """
    # Códigos de meses de futuros
    month_codes = {
        1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M',
        7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'
    }
    
    # ES y NQ son contratos trimestrales (H, M, U, Z = Mar, Jun, Sep, Dec)
    quarterly_months = [3, 6, 9, 12]
    
    current_date = datetime.now(NY_TZ) if NY_TZ else datetime.now()
    year = current_date.year
    
    # Encontrar el próximo mes de vencimiento trimestral
    for m in quarterly_months:
        # Tercer viernes del mes (aproximación)
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
        # Si pasamos todos los meses de este año, ir a marzo del próximo
        year += 1
        month_code = 'H'  # Marzo
    
    # Usar año de 2 dígitos para el símbolo CLI y el streamer
    year_2digit = str(year)[-2:]  # e.g., "26" para 2026
    year_1digit = str(year)[-1]   # e.g., "6" para 2026 (CLI format)
    
    # full_symbol es el formato CLI: /ESH6
    full_symbol = f"{root_symbol}{month_code}{year_1digit}"
    
    # streamer_symbol es el formato correcto para DXLink: /ESH26:XCME
    base_symbol = root_symbol.lstrip('/')
    streamer_symbol = f"/{base_symbol}{month_code}{year_2digit}:XCME"
    
    print(f"  [FUTURE] Resolviendo {root_symbol} → {full_symbol} (streamer: {streamer_symbol})")
    
    try:
        future = Future.get(session, full_symbol)
        print(f"  [FUTURE] Contrato obtenido: {future.symbol}")
        return full_symbol, streamer_symbol, future
    except Exception as e:
        print(f"  [ERROR] No se pudo resolver {full_symbol}: {e}")
        return None, None, None


def get_trading_days(num_days: int) -> list:
    """
    Obtiene los últimos N días hábiles (excluyendo fines de semana).
    Retorna lista de dates ordenados del más antiguo al más reciente.
    """
    trading_days = []
    current = datetime.now(NY_TZ).date() if NY_TZ else datetime.now().date()
    
    # No incluir hoy si el mercado aún no ha cerrado
    now = datetime.now(NY_TZ) if NY_TZ else datetime.now()
    if now.time() < dt_time(16, 15):
        current = current - timedelta(days=1)
    
    while len(trading_days) < num_days:
        # Retroceder hasta encontrar un día hábil (lunes=0 a viernes=4)
        if current.weekday() < 5:  # No es sábado ni domingo
            trading_days.append(current)
        current = current - timedelta(days=1)
    
    # Ordenar del más antiguo al más reciente
    trading_days.reverse()
    return trading_days


async def get_candle_data_for_date(session, streamer_symbol: str, target_date: date) -> pd.DataFrame:
    """
    Descarga datos de velas de 1 minuto para una fecha específica usando DXLinkStreamer.
    Filtra a horas RTH (Regular Trading Hours): 9:30 AM - 4:00 PM ET
    
    Args:
        session: Sesión de Tastytrade
        streamer_symbol: Símbolo completo con exchange (ej: "/ESH26:XCME")
        target_date: Fecha objetivo
    
    Retorna un DataFrame con columnas: datetime, open, high, low, close, volume
    """
    candles_list = []
    
    # Futuros: comenzar desde las 6:00 AM (pre-market de futuros)
    # Los futuros CME abren a 6PM del día anterior y cierran a 5PM
    start_time = datetime.combine(target_date, dt_time(6, 0))
    end_time = datetime.combine(target_date, dt_time(17, 0))
    
    if NY_TZ:
        start_time = start_time.replace(tzinfo=NY_TZ)
        end_time = end_time.replace(tzinfo=NY_TZ)
    
    ts_start = round(start_time.timestamp() * 1000)
    
    print(f"  [CANDLE] Descargando {streamer_symbol} para {target_date.strftime('%Y-%m-%d')}...")
    
    try:
        async with DXLinkStreamer(session) as streamer:
            await streamer.subscribe_candle([streamer_symbol], "1m", start_time)
            
            try:
                async with asyncio.timeout(60):
                    async for candle in streamer.listen(Candle):
                        if candle.close:
                            # Convertir timestamp a datetime en zona NY
                            if NY_TZ:
                                dt_candle = datetime.fromtimestamp(candle.time / 1000, tz=NY_TZ)
                            else:
                                dt_candle = datetime.fromtimestamp(candle.time / 1000)
                            
                            # Solo incluir velas del día objetivo
                            if dt_candle.date() != target_date:
                                continue
                            
                            candles_list.append({
                                "datetime": dt_candle,
                                "open": float(candle.open) if candle.open else 0,
                                "high": float(candle.high) if candle.high else 0,
                                "low": float(candle.low) if candle.low else 0,
                                "close": float(candle.close) if candle.close else 0,
                                "volume": float(candle.volume) if candle.volume else 0
                            })
                        
                        # Condición de salida: llegamos al inicio del período solicitado
                        if candle.time <= ts_start:
                            break
                            
            except asyncio.TimeoutError:
                print(f"    [TIMEOUT] {streamer_symbol}: {len(candles_list)} velas obtenidas")
                
    except Exception as e:
        print(f"    [ERROR] {streamer_symbol}: {e}")
        return pd.DataFrame()
    
    # Procesar y retornar
    if candles_list:
        print(f"    [OK] {streamer_symbol}: {len(candles_list)} velas recibidas")
        df = pd.DataFrame(candles_list)
        df = df.sort_values("datetime").reset_index(drop=True)
        
        # Filtrar solo horas RTH (9:30 - 16:00)
        df = df[df["datetime"].apply(lambda x: dt_time(9, 30) <= x.time() <= dt_time(16, 0))]
        
        # Eliminar duplicados por datetime
        df = df.drop_duplicates(subset=["datetime"], keep="last")
        
        print(f"    [OK] {len(df)} velas RTH procesadas")
        return df
    
    print(f"    [WARN] Sin datos para {streamer_symbol}")
    return pd.DataFrame()


def calculate_volume_profile(df: pd.DataFrame, num_buckets: int = 50) -> dict:
    """
    Calcula el perfil de volumen para los datos dados.
    
    Retorna:
    - vpoc: Point of Control (precio con más volumen)
    - vah: Value Area High (70% del volumen arriba del VPOC)
    - val: Value Area Low (70% del volumen abajo del VPOC)
    - lvn: Low Volume Nodes (zonas con < 20% del volumen promedio)
    - profile: lista de (precio, volumen) para cada bucket
    """
    if df.empty or "volume" not in df.columns:
        return {}
    
    # Obtener rango de precios
    price_min = df["low"].min()
    price_max = df["high"].max()
    
    if price_min == price_max:
        return {}
    
    # Crear buckets de precio
    bucket_size = (price_max - price_min) / num_buckets
    if bucket_size == 0:
        return {}
    
    # Distribuir volumen en buckets basado en el rango de cada vela
    volume_by_bucket = np.zeros(num_buckets)
    
    for _, row in df.iterrows():
        candle_low = row["low"]
        candle_high = row["high"]
        candle_volume = row["volume"]
        
        if candle_volume <= 0:
            continue
        
        # Determinar qué buckets cubre esta vela
        start_bucket = max(0, int((candle_low - price_min) / bucket_size))
        end_bucket = min(num_buckets - 1, int((candle_high - price_min) / bucket_size))
        
        # Distribuir volumen proporcionalmente
        num_covered_buckets = end_bucket - start_bucket + 1
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
        return {}
    
    value_area_volume = total_volume * 0.70
    
    # Expandir desde VPOC hasta cubrir 70% del volumen
    va_low_idx = vpoc_idx
    va_high_idx = vpoc_idx
    current_va_volume = volume_by_bucket[vpoc_idx]
    
    while current_va_volume < value_area_volume:
        # Expandir hacia el lado con más volumen
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
    
    val = bucket_prices[va_low_idx] - bucket_size / 2  # Lower edge
    vah = bucket_prices[va_high_idx] + bucket_size / 2  # Upper edge
    
    # LVN: Low Volume Nodes
    smoothed_volume = np.convolve(volume_by_bucket, np.ones(3)/3, mode='same')
    avg_volume = total_volume / num_buckets
    
    lvn_indices = []
    for i in range(1, num_buckets - 1):
        prev_vol = smoothed_volume[i - 1]
        curr_vol = smoothed_volume[i]
        next_vol = smoothed_volume[i + 1]
        if curr_vol < prev_vol and curr_vol < next_vol and curr_vol < avg_volume:
            lvn_indices.append(i)
    
    lvn_zones = []
    lvn_threshold = avg_volume * 0.6
    
    for lvn_idx in lvn_indices:
        zone_start_idx = lvn_idx
        while zone_start_idx > 0 and smoothed_volume[zone_start_idx - 1] < lvn_threshold:
            zone_start_idx -= 1
        
        zone_end_idx = lvn_idx
        while zone_end_idx < num_buckets - 1 and smoothed_volume[zone_end_idx + 1] < lvn_threshold:
            zone_end_idx += 1
        
        zone_low = bucket_prices[zone_start_idx] - bucket_size / 2
        zone_high = bucket_prices[zone_end_idx] + bucket_size / 2
        
        if lvn_zones and zone_low <= lvn_zones[-1]["high"]:
            lvn_zones[-1]["high"] = max(lvn_zones[-1]["high"], zone_high)
            lvn_zones[-1]["mid"] = (lvn_zones[-1]["low"] + lvn_zones[-1]["high"]) / 2
        else:
            lvn_zones.append({
                "low": zone_low,
                "high": zone_high,
                "mid": (zone_low + zone_high) / 2
            })
    
    # Build profile data
    profile = [
        {"price": bucket_prices[i], "volume": float(volume_by_bucket[i])}
        for i in range(num_buckets)
    ]
    
    return {
        "vpoc": float(vpoc),
        "vah": float(vah),
        "val": float(val),
        "lvn_zones": lvn_zones,
        "total_volume": float(total_volume),
        "bucket_size": float(bucket_size),
        "profile": profile
    }


def calculate_ib_and_save(ticker: str, df_candles: pd.DataFrame, date_str: str):
    """
    Calcula Initial Balance, Volume Profile, y guarda JSON.
    Incluye volumen en los datos minuto a minuto.
    """
    if df_candles.empty:
        return None

    df = df_candles.copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    
    # Precio actual (último del día)
    current_price = df.iloc[-1]["close"]

    # --- CÁLCULO IB (09:30 - 10:30) ---
    ib_start = dt_time(9, 30)
    ib_end = dt_time(10, 30)

    ib_data = df[df["datetime"].apply(lambda x: ib_start <= x.time() <= ib_end)]
    
    if ib_data.empty:
        # Si no hay datos en el rango IB, usar todo el día
        ib_data = df

    ib_high = float(ib_data["high"].max())
    ib_low = float(ib_data["low"].min())
    ib_range = ib_high - ib_low

    # --- CÁLCULO VOLUME PROFILE ---
    volume_profile = calculate_volume_profile(df)

    # Construir series de precio CON VOLUMEN
    series_data = []
    for idx, row in df.iterrows():
        candle_time = row["datetime"]
        series_data.append({
            "time": candle_time.strftime("%H:%M"),
            "full_date": candle_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "price": float(row["close"]),  # "price" for backward compatibility
            "volume": float(row["volume"]),
        })

    # Ticker limpio para el nombre del archivo (sin /)
    ticker_clean = ticker.replace("/", "")

    # Construir y guardar JSON
    json_data = {
        "meta": {
            "ticker": ticker,
            "ticker_clean": ticker_clean,
            "date": date_str,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Historical backtest data for futures with volume profile"
        },
        "analysis": {
            "ib_high": ib_high,
            "ib_low": ib_low,
            "ib_range": ib_range,
            "current_price": float(current_price),
            "day_high": float(df["high"].max()),
            "day_low": float(df["low"].min()),
            "total_volume": float(df["volume"].sum()),
        },
        "volume_profile": volume_profile,
        "levels": {},  # Greeks no disponibles para futuros en este script
        "series": series_data,
    }

    json_filename = os.path.join(OUTPUT_DIR, f"ib_data_{ticker_clean}_{date_str}.json")
    with open(json_filename, "w") as f:
        json.dump(json_data, f, indent=4)

    return json_filename


async def process_all_futures():
    """Procesa todos los futuros para todos los días."""
    
    # Obtener días hábiles a procesar
    trading_days = get_trading_days(DAYS_BACK)
    
    print(f"\n{'='*60}")
    print(f"IB BACKTEST DATA GENERATOR - FUTURES")
    print(f"{'='*60}")
    print(f"Futuros: {', '.join(FUTURES_TO_TRACK)}")
    print(f"Días a procesar: {len(trading_days)}")
    print(f"Rango: {trading_days[0]} a {trading_days[-1]}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")
    
    session = get_tastytrade_session()
    total_files = 0
    
    # Resolver símbolos de futuros activos
    futures_resolved = {}
    for root_symbol in FUTURES_TO_TRACK:
        full_symbol, streamer_symbol, future_obj = get_active_future_symbol(session, root_symbol)
        if streamer_symbol:
            futures_resolved[root_symbol] = {
                "full_symbol": full_symbol,
                "streamer_symbol": streamer_symbol,
                "future": future_obj
            }
    
    if not futures_resolved:
        print("[ERROR] No se pudo resolver ningún símbolo de futuros")
        return
    
    print(f"\nFuturos resueltos: {list(futures_resolved.keys())}\n")
    
    for target_date in trading_days:
        date_str = target_date.strftime("%Y%m%d")
        print(f"\n[{date_str}] Procesando fecha...")
        
        for root_symbol, info in futures_resolved.items():
            ticker_clean = root_symbol.replace("/", "")
            try:
                # Verificar si ya existe el archivo
                json_path = os.path.join(OUTPUT_DIR, f"ib_data_{ticker_clean}_{date_str}.json")
                if os.path.exists(json_path):
                    print(f"  [SKIP] {root_symbol}: Already exists")
                    total_files += 1
                    continue
                
                # Descargar velas para esta fecha
                df_candles = await get_candle_data_for_date(
                    session,
                    info["streamer_symbol"],
                    target_date
                )
                
                if df_candles.empty:
                    print(f"  [SKIP] {root_symbol}: Sin datos")
                    continue
                
                # Calcular IB y guardar JSON
                json_file = calculate_ib_and_save(root_symbol, df_candles, date_str)
                
                if json_file:
                    print(f"  [SAVED] {os.path.basename(json_file)}")
                    total_files += 1
                
                # Pequeña pausa para no saturar la API
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"  [ERROR] {root_symbol}: {e}")
                import traceback
                traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"COMPLETADO: {total_files} archivos JSON generados")
    print(f"Directorio: {OUTPUT_DIR}")
    print(f"{'='*60}\n")


async def main():
    """Punto de entrada principal."""
    if not TT_USERNAME or not TT_PASSWORD:
        print("ERROR: Faltan credenciales TASTYTRADE_USERNAME o TASTYTRADE_PASSWORD en .env")
        return
    
    await process_all_futures()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Detenido por usuario.")
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
