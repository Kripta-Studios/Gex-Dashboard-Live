import time
import functools
import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from os import environ, makedirs
import shutil

# Add root directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tools.data_plotting import get_options_data
from cachetools import TTLCache
import discord
import asyncio
from tools.watchdog_notify import send_watchdog

# Load environment variables
load_dotenv()

# Configuration
TICKERS = ["SPX", "Ticker"]  # Yahoo Finance format
# EXPIRATIONS = ["0dte", "1dte", "weekly", "opex", "monthly", "all"]
EXPIRATIONS = ["0dte", "1dte", "weekly"]
GREEKS = ["delta", "gamma", "vanna", "charm", "dgex", "zomma"]
VISUALIZATIONS = {
    "delta": ["Absolute Delta Exposure", "Delta Exposure By Calls/Puts"],
    "gamma": ["Absolute Gamma Exposure", "Gamma Exposure By Calls/Puts"],
    "vanna": ["Absolute Vanna Exposure", "Implied Volatility Average"],
    "charm": ["Absolute Charm Exposure"],
    "dgex": ["Absolute Dgex Exposure", "Dgex Exposure By Calls/Puts"],
    "zomma": ["Absolute Zomma Exposure"],
}
PLOT_DIR = "plots"
TZ = "America/New_York"  # EST timezone
DISCORD_CHANNEL_IDS = {
    "SPX/0dte/delta": 1387377585427841094,  # Replace with actual channel IDs
    "SPX/0dte/gamma": 1387376148950028288,
    "SPX/0dte/vanna": 1387376757413515344,
    "SPX/0dte/charm": 1387377438589194270,
    "SPX/0dte/dgex": 1456248917258932421,
    "SPX/0dte/zomma": 1456249198726086696,
    "SPX/1dte/delta": 1387377603031207976,
    "SPX/1dte/gamma": 1387376325399941231,
    "SPX/1dte/vanna": 1387376810559275158,
    "SPX/1dte/charm": 1387377460810744019,
    "SPX/1dte/dgex": 1456248945771675678,
    "SPX/1dte/zomma": 1456249231982596137,
    "SPX/opex/delta": 1387377627505102909,
    "SPX/opex/gamma": 1387376441389486131,
    "SPX/opex/vanna": 1387376838757711913,
    "SPX/opex/charm": 1387377489562828952,
    "SPX/opex/dgex": 1456248999639126133,
    "SPX/opex/zomma": 1456249282951905310,
    "SPX/monthly/delta": 1387377650565382234,
    "SPX/monthly/gamma": 1387376549967167569,
    "SPX/monthly/vanna": 1387376930101395528,
    "SPX/monthly/charm": 1387377520105619627,
    "SPX/monthly/dgex": 1456249040927854602,
    "SPX/monthly/zomma": 1456249572384051333,
    "SPX/all/delta": 1387377665589116938,
    "SPX/all/gamma": 1387376590912229396,
    "SPX/all/vanna": 1387376953237180537,
    "SPX/all/charm": 1387377535570018404,
    "SPX/all/dgex": 1456249060263465000,
    "SPX/all/zomma": 1456249589496549522,
    "SPX/weekly/delta": 1393732731413987434,
    "SPX/weekly/gamma": 1393732774296420352,
    "SPX/weekly/vanna": 1393732835923198033,
    "SPX/weekly/charm": 1393732884933906512,
    "SPX/weekly/dgex": 1456248980068368529,
    "SPX/weekly/zomma": 1456249264144388208,
    "Ticker/0dte/delta": 1387378772805947492,
    "Ticker/0dte/gamma": 1387377700465016862,
    "Ticker/0dte/vanna": 1387378541284425828,
    "Ticker/0dte/charm": 1387378654039904417,
    "Ticker/1dte/delta": 1387378789184442378,
    "Ticker/1dte/gamma": 1387378422325448795,
    "Ticker/1dte/vanna": 1387378559214948393,
    "Ticker/1dte/charm": 1387378677075021856,
    "Ticker/opex/delta": 1387378811393282208,
    "Ticker/opex/gamma": 1387378439182352476,
    "Ticker/opex/vanna": 1387378578173198366,
    "Ticker/opex/charm": 1387378698826682409,
    "Ticker/monthly/delta": 1387378837318275132,
    "Ticker/monthly/gamma": 1387378471835144292,
    "Ticker/monthly/vanna": 1387378607344848977,
    "Ticker/monthly/charm": 1387378733371097128,
    "Ticker/all/delta": 1387378868247203901,
    "Ticker/all/gamma": 1387378499417014392,
    "Ticker/all/vanna": 1387378622293344356,
    "Ticker/all/charm": 1387378750827794644,
    "SPY/weekly/gamma": 1405682462197153962,  # Replace with actual channel IDs
    "SPY/0dte/delta": 1462069774136905963,
    "SPY/0dte/gamma": 1435228025217355799,
    "SPY/0dte/vanna": 1448657151198367874,
    "SPY/0dte/zomma": 1457671485190705162,
    "SPY/0dte/dgex": 1457671508959821845,
    "QQQ/weekly/gamma": 1405682477313429624,
    "QQQ/0dte/delta": 1462069803228332179,
    "QQQ/0dte/gamma": 1436339202663911499,
    "QQQ/0dte/vanna": 1448659272161562727,
    "QQQ/0dte/zomma": 1457671530074079304,
    "QQQ/0dte/dgex": 1457671555965386928,
}

# Initialize cache
cache = TTLCache(maxsize=150, ttl=60 * 15)  # 15-minute cache

makedirs(PLOT_DIR, exist_ok=True)

# Discord client (passed from bot.py)
discord_client = None

upload_lock_fast = asyncio.Semaphore(3)
upload_lock_slow = asyncio.Semaphore(1)


def log(message):
    """Imprime el mensaje con la hora actual en NY"""
    now = datetime.now(ZoneInfo(TZ)).strftime("%H:%M:%S")
    print(f"[{now}] {message}")
    full_msg = f"[{now}] {message}"
    with open("bot_logging.txt", "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")


async def process_single_request(sem, ticker, exp, greek, channel_id):
    """
    Procesa un solo ticker/exp/greek respetando el semáforo para no saturar.
    """
    async with sem:  # Limita la concurrencia
        try:
            now = time.time()
            log(f"[*] Procesando: {ticker} {exp} {greek}...")  # LOG CHIVATO
            # print(f"Processing {ticker} {exp} {greek}...") # Debug opcional
            raw_data = await get_options_data(ticker, exp, greek)
            end = time.time()
            print("get_options_data Tardo", now-end)
            if not raw_data:
                log(
                    f"[VACÍO] get_options_data devolvió None para {ticker} {exp} {greek}"
                )
                return False

            if isinstance(raw_data, list) and len(raw_data) >= 3:
                hist_files = raw_data[0] or []
                alerts = raw_data[1] or []
                table_files = raw_data[2] or []

                filenames = [f for f in [hist_files, table_files] if f]
                if not filenames:
                    log(
                        f"[VACÍO] No se generaron nombres de archivo para {ticker} {exp} {greek}"
                    )
                # Si el griego es None, enviamos para todos los GREEKS definidos
                if greek is None:
                    # Nota: Esto podría optimizarse más, pero mantenemos lógica original
                    for loop_greek in GREEKS:
                        current_loop_alerts = [
                            a for a in alerts if loop_greek.lower() in a.lower()
                        ]
                        now = time.time()
                        await send_plot_to_discord(
                            filenames,
                            ticker,
                            exp,
                            loop_greek,
                            channel_id,
                            alerts=current_loop_alerts,
                        )
                        end = time.time()
                        print("send_plot_to_discord tardo", now-end)
                else:
                    await send_plot_to_discord(
                        filenames, ticker, exp, greek, channel_id, alerts=alerts
                    )
            else:
                log(f"[ERROR FORMATO] Datos recibidos incorrectos: {type(raw_data)}")

            return True
        except Exception as e:
            log(f"Error processing {ticker}/{exp}/{greek}: {e}")
            import traceback

            traceback.print_exc()
            return False


def set_discord_client(client):
    global discord_client
    discord_client = client
    log(f"Discord client set: {client}")


async def send_plot_to_discord(filenames, ticker, exp, greek, channel_id, alerts=None):
    if discord_client is None:
        log("Discord client not initialized")
        return
    if channel_id == None:
        if (ticker == "SPX") and (exp in EXPIRATIONS):
            channel_key = f"{ticker}/{exp}/{greek}"
            channel_id = DISCORD_CHANNEL_IDS.get(channel_key)
        elif ticker == "SPX":
            channel_key = f"SPX/0dte/{greek}"
            channel_id = DISCORD_CHANNEL_IDS.get(channel_key)
        elif (ticker in ["QQQ", "SPY"]) and (exp in EXPIRATIONS) and exp != "1dte":
            channel_key = f"{ticker}/{exp}/{greek}"
            channel_id = DISCORD_CHANNEL_IDS.get(channel_key)
        else:
            channel_key = f"Ticker/0dte/{greek}"
            channel_id = DISCORD_CHANNEL_IDS.get(channel_key)

    if not channel_id:
        log(f"[ERROR] No hay ID de canal configurado para: {ticker}/{exp}/{greek}")
        return
    channel = discord_client.get_channel(channel_id)
    channel_key = channel
    # print("Channel:", channel)
    if not channel:
        log(f"Channel ID {channel_id} on {channel_key} not found")
        return

    if alerts:
        unique_alerts = list(set(alerts))
        filtered_alerts = [a for a in unique_alerts if greek.lower() in a.lower()]

        if filtered_alerts:
            alert_msg = "\n".join(filtered_alerts)
            if len(alert_msg) > 1950:
                alert_msg = alert_msg[:1950] + "... (truncated)"
            try:
                await channel.send(alert_msg)
            except Exception as e:
                log(f"Failed to send alerts to {channel_key}: {e}")

    valid_files = []
    for file_group in filenames:
        for file_path in file_group:
            if greek in file_path:
                if os.path.exists(file_path):
                    valid_files.append(file_path)
                else:
                    log(f"File not found {file_path}")
    if not valid_files:
        log(
            f"[WARN] Se procesaron datos para {ticker}/{exp}/{greek} pero no salieron archivos válidos."
        )
        return

    if exp == "0dte":
        lock_to_use = upload_lock_fast
    else:
        lock_to_use = upload_lock_slow

    async with lock_to_use:
        try:
            log(f"[SUBIENDO] Enviando {len(valid_files)} imágenes a #{channel.name}...")
            timeInfo = "America/New_York"
            header_msg = f"{ticker}/{exp}/{greek} at {datetime.now(ZoneInfo(timeInfo)).ctime()} EST"
            await channel.send(header_msg)

            BATCH_SIZE = 4
            for i in range(0, len(valid_files), BATCH_SIZE):
                batch_paths = valid_files[i : i + BATCH_SIZE]

                # Bucle de Reintentos
                MAX_RETRIES = 3
                for attempt in range(MAX_RETRIES):
                    try:
                        # Creamos los objetos File justo antes de enviar
                        # (Si reusamos un objeto File fallido, el puntero de lectura estaría al final y enviaría 0 bytes)
                        discord_files_batch = [
                            discord.File(path) for path in batch_paths
                        ]

                        await channel.send(files=discord_files_batch)
                        break  # ¡Éxito! Salimos del bucle de reintentos
                    except Exception as e:
                        wait_time = attempt + 1
                        log(
                            f"[RETRY {attempt+1}/{MAX_RETRIES}] Error enviando a {channel.name}: {e}. Esperando {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)

                        if attempt == MAX_RETRIES - 1:
                            log(
                                f"[ERROR] Se perdió el lote {i} de {greek} tras {MAX_RETRIES} intentos."
                            )

            log(f"[OK] Enviado correctamente: {ticker}/{exp}/{greek}")
            # print(f"Sent {i} to Discord channel {channel_key}")
        except Exception as e:
            mensaje = f"Failed to send {filenames} to {channel_key}"
            await channel.send(mensaje)
            log(
                f"Failed to send {filenames} to {channel_key}: {type(e).__name__} - {e}"
            )


async def process_ticker_batch(
    ticker, expirations_list, specific_greek=None, channel_id=None
):
    # Obtenemos el bucle de eventos actual
    loop = asyncio.get_running_loop()

    for exp in expirations_list:
        try:
            # print(f"[*] Procesando: {ticker} {exp} (En hilo secundario)...")

            # --- LA MAGIA: EJECUTAR EN UN HILO APARTE ---
            # Esto evita que Matplotlib congele el bot.
            # Nota: get_options_data NO debe tener 'async' en su definición en data_plotting.py
            now = time.time()
            print("Inicia descarga", now)
            raw_data = await loop.run_in_executor(
                None,  # Usa el ThreadPool por defecto
                functools.partial(get_options_data, ticker, exp, specific_greek),
            )
            end = time.time()
            print("Tardo la descarga", end-now)

            if isinstance(raw_data, list) and len(raw_data) >= 3:
                hist_files = raw_data[0] or []
                alerts = raw_data[1] or []
                table_files = raw_data[2] or []
                filenames = [f for f in [hist_files, table_files] if f]

                greeks_to_send = [specific_greek] if specific_greek else GREEKS

                for greek in greeks_to_send:
                    relevant_alerts = [a for a in alerts if greek.lower() in a.lower()]
                    # La subida a Discord SÍ debe ser en el hilo principal (es async)
                    now = time.time()
                    print("Inicia el envío", now)
                    await send_plot_to_discord(
                        filenames,
                        ticker,
                        exp,
                        greek,
                        channel_id,
                        alerts=relevant_alerts,
                    )
                    end = time.time()
                    print("Tardo el send_plot_to_discord", end-now)

            # Pausa obligatoria entre expiraciones para dejar respirar a la CPU
            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"[ERROR LOTE] Fallo en {ticker} {exp}: {e}")
            import traceback

            traceback.print_exc()


async def request_plots(
    specific_ticker=None, specific_exp=None, specific_greek=None, channel_id=None
):
    try:
        # 1. Configuración de concurrencia
        tasks = []

        # 2. Definir listas a procesar
        tickers_to_process = (
            [specific_ticker] if specific_ticker else ["SPX", "SPY", "QQQ"]
        )  # O tu lista TICKERS global si prefieres
        expirations_to_process = [specific_exp] if specific_exp else EXPIRATIONS
        # 3. Crear las tareas (Tasks)
        for ticker in tickers_to_process:
            task = asyncio.create_task(
                process_ticker_batch(
                    ticker, expirations_to_process, specific_greek, channel_id
                )
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks)

        return True

    except Exception as e:
        log(f"ERROR en request_plots: {e}")
        import traceback

        traceback.print_exc()
        return False


def cleanup_plots_daily():
    """
    Borra la carpeta PLOT_DIR completa y la recrea vacía.
    Es más rápido que borrar archivo por archivo.
    """
    log("[MANTENIMIENTO] Iniciando limpieza diaria de plots (00:00 Hora Servidor)...")
    try:
        if os.path.exists(PLOT_DIR):
            shutil.rmtree(PLOT_DIR)  # Borra carpeta y subcarpetas

        os.makedirs(PLOT_DIR, exist_ok=True)  # La recrea vacía inmediatamente
        log("[MANTENIMIENTO] Carpeta plots reiniciada correctamente.")
    except Exception as e:
        log(f"[ERROR MANTENIMIENTO] Fallo al limpiar plots: {e}")


def cleanup_old_json_data():
    """
    1. Borra archivos con más de 'days_to_keep' de antigüedad.
    2. Borra CUALQUIER archivo creado en Sábado o Domingo (histórico o reciente).
    """
    days_to_keep = 70  # Días a mantener (solo días de semana)
    folder_path = "/home/Option-Greeks-Plotting-Discord-Bot/json_data"

    log(
        f"[MANTENIMIENTO] Iniciando limpieza de JSONs (Antiguos >{days_to_keep}d O Fines de Semana)..."
    )

    deleted_count = 0
    weekend_deleted = 0
    now = time.time()
    cutoff = now - (days_to_keep * 86400)  # Límite de tiempo para archivos antiguos

    try:
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)

                # Solo procesamos archivos .json
                if filename.endswith(".json") and os.path.isfile(file_path):
                    try:
                        mtime = os.path.getmtime(file_path)

                        # CONDICIÓN 1: ¿Es viejo?
                        is_old = mtime < cutoff

                        # CONDICIÓN 2: ¿Es finde?
                        # tm_wday devuelve: 0=Lunes ... 5=Sábado, 6=Domingo
                        day_of_week = time.localtime(mtime).tm_wday
                        is_weekend = day_of_week == 5 or day_of_week == 6

                        if is_old or is_weekend:
                            os.remove(file_path)
                            deleted_count += 1
                            if is_weekend:
                                weekend_deleted += 1

                    except Exception as e:
                        log(f"[WARN] No se pudo borrar {filename}: {e}")

            log(
                f"[MANTENIMIENTO] Limpieza completada. Total borrados: {deleted_count} (Por ser finde: {weekend_deleted})"
            )
        else:
            log("[WARN] La carpeta json_data no existe.")

    except Exception as e:
        log(f"[ERROR MANTENIMIENTO] Fallo crítico limpiando JSONs: {e}")


async def start_scheduler():
    # cleanup_directory()
    sched = BackgroundScheduler(daemon=True)

    # --- TRABAJO RÁPIDO (0DTE) ---
    # Se ejecuta cada 2 MINUTOS. Solo procesa 0dte.
    log("[SYSTEM] Programando 0DTE cada 2 minutos...")
    sched.add_job(
        lambda: asyncio.run_coroutine_threadsafe(
            request_plots(specific_exp="0dte"), discord_client.loop  # Solo pedimos 0dte
        ).result(),
        CronTrigger.from_crontab(
            "*/2 3-16 * * 0-4",  # <--- CADA 2 MINUTOS
            timezone=ZoneInfo("America/New_York"),
        ),
        id="fast_0dte_job",
        max_instances=1,
        coalesce=True,
    )

    # --- TRABAJO LENTO (1DTE y Weekly) ---
    # Se ejecuta cada 10 MINUTOS. Procesan el resto.
    # Esto libera ancho de banda para que el 0dte fluya rápido.
    log("[SYSTEM] Programando 1DTE/Weekly cada 10 minutos...")
    for slow_exp in ["1dte", "weekly"]:
        sched.add_job(
            lambda e=slow_exp: asyncio.run_coroutine_threadsafe(
                request_plots(specific_exp=e), discord_client.loop
            ).result(),
            CronTrigger.from_crontab(
                "*/9 3-16 * * 0-4",  # <--- CADA 10 MINUTOS
                timezone=ZoneInfo("America/New_York"),
            ),
            id=f"slow_{slow_exp}_job",
            max_instances=1,
            coalesce=True,
        )

    log("[SYSTEM] Programando limpieza de plots a las 00:00 (Hora Servidor)...")

    sched.add_job(
        cleanup_plots_daily,
        CronTrigger(hour=0, minute=0),  # <--- Sin timezone = Hora local del servidor
        id="daily_cleanup_job",
        replace_existing=True,
    )

    log("[SYSTEM] Programando limpieza de JSONs antiguos a las 00:30...")

    sched.add_job(
        cleanup_old_json_data,
        CronTrigger(hour=0, minute=30),
        id="json_cleanup_job",
        replace_existing=True,
    )

    sched.start()
    print("[SYSTEM] Scheduler Híbrido Iniciado (0DTE Rápido / Resto Normal)")
