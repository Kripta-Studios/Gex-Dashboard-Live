import json
import os
import glob
import re
import pandas as pd
import numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# --- CONFIGURACIÓN DE RUTAS ---
IB_DATA_DIR = "ib_backtest"      # Donde están tus JSON de IB
GREEK_DATA_DIR = "json_data"   # Donde están tus JSON de Griegas
MAX_WORKERS = 10

def extract_muros_from_greeks(ticker, date_str):
    """Busca el archivo de griegas más reciente para ese ticker/fecha y saca los muros."""
    # Mapeo para futuros (si el IB es _ES, busca griegas de SPX)
    greek_ticker = "SPX" if ticker == "ES" else "QQQ" if ticker == "NQ" else ticker
    
    pattern = os.path.join(GREEK_DATA_DIR, f"*{greek_ticker}*0dte*ExposureData*{date_str}*.json")
    greek_files = sorted(glob.glob(pattern))
    
    if not greek_files:
        pattern = os.path.join(GREEK_DATA_DIR, f"*{greek_ticker}*weekly*ExposureData*{date_str}*.json")
        greek_files = sorted(glob.glob(pattern))

    if not greek_files:
        return None

    try:
        with open(greek_files[-1], "r") as f:
            data = json.load(f)
        
        raw_df = data.get("option_data", {})
        if not raw_df or "data" not in raw_df:
            return None

        df = pd.DataFrame(data=raw_df["data"], columns=raw_df["columns"])
        
        # Columnas objetivo
        target_cols = ["total_gamma", "total_vega", "total_vomma", "total_vanna", "total_dgex"]
        for col in ["strike_price"] + target_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        greeks = df.groupby("strike_price")[target_cols].sum()
        
        # Encontrar los niveles de mayor exposición
        levels = {
            "max_gamma": float(greeks["total_gamma"].idxmax()),
            "min_gamma": float(greeks["total_gamma"].idxmin()),
            "max_vega": float(greeks["total_vega"].idxmax()),
            "max_vomma": float(greeks["total_vomma"].idxmax()),
            "min_vanna": float(greeks["total_vanna"].idxmin()),
            "max_dgex": float(greeks["total_dgex"].idxmax())
        }

        extract_muros_from_greeks.latest_file_used = greek_files[-1]
        return levels
    except Exception as e:
        print(f"  [ERROR] Procesando griegas para {ticker} {date_str}: {e}")
        return None

def process_ib_file(filepath):
    """Actualiza un solo archivo de IB inyectando los muros de Vega/Vomma."""
    filename = os.path.basename(filepath)
    
    # Extraer Ticker y Fecha del nombre: ib_data_TICKER_YYYYMMDD.json
    match = re.search(r"ib_data_([^_]+)_(\d{8})\.json", filename)
    if not match:
        return

    ticker = match.group(1)
    date_str = match.group(2)

    try:
        with open(filepath, "r") as f:
            ib_json = json.load(f)

        # Si ya tiene max_vega, podemos saltarlo (opcional)
        # if "max_vega" in ib_json.get("levels", {}): return

        print(f"[PROCESSING] {filename}...")
        
        muros = extract_muros_from_greeks(ticker, date_str)
        
        if muros:
            # Caso especial: Conversión de escala QQQ -> NDX para el futuro /NQ
            if ticker == "NQ" and "underlying_spot" in ib_json["analysis"]:
                ndx_spot = ib_json["analysis"]["underlying_spot"]
                
                # Necesitamos el spot del QQQ de ese día para calcular la distancia %
                # Lo abrimos del mismo archivo de griegas de donde sacamos los muros
                with open(extract_muros_from_greeks.latest_file_used, "r") as f_g:
                    greek_data = json.load(f_g)
                    qqq_spot_historico = float(greek_data.get("spot_price", 0))

                if qqq_spot_historico > 0:
                    muros_convertidos = {}
                    for k, val in muros.items():
                        # 1. Calculamos a qué % de distancia estaba el muro del spot del QQQ
                        pct_dist = (val - qqq_spot_historico) / qqq_spot_historico
                        # 2. Proyectamos ese mismo % sobre el spot del NDX (escala 24k)
                        muros_convertidos[k] = ndx_spot * (1 + pct_dist)
                    
                    ib_json["levels"].update(muros_convertidos)
                    print(f"  [CONVERSION] QQQ({qqq_spot_historico}) -> NDX({ndx_spot}) aplicada a {filename}")
                else:
                    # Fallback si no hay spot: inyectamos original (aunque la escala será errónea)
                    ib_json["levels"].update(muros)
            
            else:
                # Caso normal (SPX, SPY, AAPL, etc.): Inyección directa
                ib_json["levels"].update(muros)

            # Guardar el archivo de IB actualizado
            with open(filepath, "w") as f:
                json.dump(ib_json, f, indent=4)
            print(f"  [OK] Niveles inyectados en {filename}")
        else:
            print(f"  [SKIP] No se encontraron griegas para {ticker} en {date_str}")

    except Exception as e:
        print(f"  [CRITICAL ERROR] en {filename}: {e}")

def main():
    ib_files = glob.glob(os.path.join(IB_DATA_DIR, "*.json"))
    print(f"Iniciando backfill de {len(ib_files)} archivos de IB...")
    
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(process_ib_file, ib_files)
    
    print("Backfill de IB completado.")

if __name__ == "__main__":
    main()
