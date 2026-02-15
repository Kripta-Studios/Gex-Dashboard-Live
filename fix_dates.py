import os
import json
import re
import glob
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURACIÓN ---
BASE_DIR = "./trading_data"
DRY_RUN = False  # Cambia a False para aplicar los cambios
MAX_WORKERS = 1  # Número de hilos concurrentes

try:
    MADRID_TZ = ZoneInfo("Europe/Madrid")
    NY_TZ = ZoneInfo("America/New_York")
except Exception as e:
    print(f"Error cargando zonas horarias: {e}")
    exit(1)


def process_greek_file(filepath):
    """Worker para archivos de griegas."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        # 1. Leemos la fecha real INMUTABLE que se guardó dentro del JSON
        if "today_ddt" not in data: 
            return None
        
        # today_ddt viene en formato ISO (ej: "2026-02-12T18:00:00-05:00")
        real_date_str = data["today_ddt"]
        
        # Convertimos el ISO a un objeto datetime de Python
        real_date_obj = datetime.fromisoformat(real_date_str)
        
        # 2. Generamos cómo DEBERÍA llamarse el archivo
        correct_date_str = real_date_obj.strftime("%Y%m%d_%H%M%S")

        # 3. Comparamos con cómo se llama AHORA
        match = re.search(r"_(\d{8}_\d{6})\.json", filename)
        if match:
            current_date_str = match.group(1)
            
            if current_date_str != correct_date_str:
                new_filename = filename.replace(current_date_str, correct_date_str)
                new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
                
                if not DRY_RUN:
                    # Si hay colisión, sobrescribimos
                    if os.path.exists(new_filepath):
                        os.remove(new_filepath)
                    os.rename(filepath, new_filepath)
                return f"[FIX GREEKS] {filename}  -->  {new_filename}"
                
    except Exception as e:
        return f"[ERROR] {filename}: {e}"
    return None

def process_ib_file(filepath):
    """Worker para archivos de Interactive Brokers."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if "series" in data and len(data["series"]) > 0:
            first_candle_time = data["series"][0].get("full_date", "")
            if not first_candle_time: return None

            real_date_obj = datetime.strptime(first_candle_time, "%Y-%m-%d %H:%M:%S")
            real_date_str = real_date_obj.strftime("%Y%m%d")

            match = re.search(r"_(\d{8})\.json", filename)
            if match:
                current_date_str = match.group(1)
                if current_date_str != real_date_str:
                    new_filename = filename.replace(current_date_str, real_date_str)
                    new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
                    
                    if not DRY_RUN:
                        if os.path.exists(new_filepath):
                            os.remove(new_filepath)
                        os.rename(filepath, new_filepath)
                    return f"[FIX IB] {filename}  -->  {new_filename}"
    except Exception as e:
        return f"[ERROR] {filename}: {e}"
    return None


def process_fourier_file(filepath):
    """Worker para archivos de Fourier."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if isinstance(data, list) and len(data) > 0:
            first_record_time = data[0].get("datetime", "")
            if not first_record_time: return None

            real_date_obj = datetime.strptime(first_record_time, "%Y-%m-%d %H:%M:%S")
            real_date_str = real_date_obj.strftime("%Y%m%d")

            match = re.search(r"_(\d{8})\.json", filename)
            if match:
                current_date_str = match.group(1)
                if current_date_str != real_date_str:
                    new_filename = filename.replace(current_date_str, real_date_str)
                    new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
                    
                    if not DRY_RUN:
                        if os.path.exists(new_filepath):
                            os.remove(new_filepath)
                        os.rename(filepath, new_filepath)
                    return f"[FIX FOURIER] {filename}  -->  {new_filename}"
    except Exception as e:
        return f"[ERROR] {filename}: {e}"
    return None


def run_concurrently(folder_name, file_pattern, worker_func):
    """Ejecutor de hilos maestro."""
    folder = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder):
        print(f"⚠️  Carpeta no encontrada: {folder}")
        return

    files = glob.glob(os.path.join(folder, file_pattern))
    if not files:
        print(f"ℹ️  No se encontraron archivos en {folder_name}")
        return

    print(f"\n" + "="*60)
    print(f"🚀 PROCESANDO {len(files)} ARCHIVOS EN '{folder_name}' CON {MAX_WORKERS} WORKERS")
    print("="*60)

    fixed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Enviar todas las tareas al pool de hilos
        futures = {executor.submit(worker_func, filepath): filepath for filepath in files}
        
        # Procesar los resultados a medida que cada hilo termina
        for future in as_completed(futures):
            result = future.result()
            if result:
                print(result)
                if "[FIX" in result:
                    fixed_count += 1

    print(f"✅ Total arreglados en {folder_name}: {fixed_count}")


if __name__ == "__main__":
    if DRY_RUN:
        print("⚠️  MODO DRY RUN ACTIVADO: NO SE MODIFICARÁN ARCHIVOS.")
        print("Revisa la salida y cambia DRY_RUN = False en el script para aplicar los cambios.\n")
    else:
        print("🚨 MODO ESCRITURA ACTIVADO: Renombrando archivos a máxima velocidad...\n")

    # Ejecutar las carpetas
    run_concurrently("json_data", "*.json", process_greek_file)
    run_concurrently("ib_charts", "ib_data_*.json", process_ib_file)
    run_concurrently("ib_backtest", "ib_data_*.json", process_ib_file)
    run_concurrently("fourier", "fourier_data_*.json", process_fourier_file)

    print("\n🎯 ¡Proceso finalizado!")
