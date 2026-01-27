#! /usr/bin/python3

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from threading import Thread
from discord_app.bot import bot, DISCORD_TOKEN
from discord_app.discord_send_plots import start_scheduler
import asyncio
from tools.data_plotting import get_options_data
import re
from sdnotify import SystemdNotifier

notifier = SystemdNotifier()
notifier.notify("READY=1")
# Crear un event loop global para manejar las tareas asíncronas
# loop = asyncio.get_event_loop()


async def run_bot_async():
    print("[SYSTEM] Iniciando Bot de Discord...")
    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        print(f"[Error] running Discord bot: {e}")
    finally:
        await bot.close()


async def run_scheduler_async():
    print("[SYSTEM] Iniciando Scheduler...")
    try:
        # Asumiendo que start_scheduler es async; si no, ajustar en consecuencia
        await asyncio.sleep(5)
        await start_scheduler()
    except Exception as e:
        print(f"[Error] running scheduler: {e}")


async def main():
    # Ejecutar ambas tareas en paralelo
    await asyncio.gather(run_bot_async(), run_scheduler_async())


"""
async def keep_alive():
    
    # Ejecutar el bot y el scheduler como tareas asíncronas
    tasks = [
        run_bot_async(),
        run_scheduler_async()
    ]
    await asyncio.gather(*tasks)
"""


if __name__ == "__main__":
    # Crear y configurar el event loop en el hilo principal
    # loop = asyncio.get_event_loop()
    try:
        # loop.run_until_complete(keep_alive())
        asyncio.run(main())
    except Exception as e:
        print("Shutting down...", e)

