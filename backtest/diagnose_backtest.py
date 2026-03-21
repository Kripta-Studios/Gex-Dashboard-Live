"""
Diagnóstico de imports para backtest_rl.py
Ejecutar desde el mismo directorio que backtest_rl.py:
    python diagnose_backtest.py
"""
import sys, os, time

def step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

step("Inicio — Python arrancado")

# Reproducir exactamente el sys.path de backtest_rl.py
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural"))
step(f"sys.path configurado | PROJECT_ROOT={PROJECT_ROOT}")

step("Importando numpy...")
import numpy as np
step("OK numpy")

step("Importando pandas...")
import pandas as pd
step("OK pandas")

step("Importando torch...")
import torch
step(f"OK torch {torch.__version__}")

step("Importando pathlib, datetime, time...")
from pathlib import Path
from datetime import datetime
import time as _time
step("OK stdlib")

step("Importando hybrid_model...")
from hybrid_model import (
    get_hybrid_model, get_device, load_hybrid_model, load_ensemble_model,
    FeatureNormalizer, FEATURE_COLUMNS
)
step(f"OK hybrid_model | {len(FEATURE_COLUMNS)} features")

step("Importando neural.rl.config...")
from neural.rl.config import RL_CONFIG, HARD_EXITS, STRIKE_BUCKETS, SNIPER_TOTAL_STATE_DIM, MLP_CONTEXT_DIM, SNIPER_STATE_DIM
step("OK neural.rl.config")

step("Importando neural.rl.agent (PPOAgent)...")
from neural.rl.agent import PPOAgent
step("OK PPOAgent")

step("Importando rl.rewards...")
from rl.rewards import compute_step_reward, compute_terminal_reward
step("OK rl.rewards")

step("=== TODOS LOS IMPORTS OK ===")
step("El deadlock NO está en los imports.")
step("Está en get_device() o load_ensemble_model().")
step("")
step("Probando get_device()...")
device = get_device()
step(f"OK get_device() → {device}")

MODEL_PATH = os.path.join(PROJECT_ROOT, "neural", "models", "trading_hybrid_wf.joblib")
NORM_PATH  = os.path.join(PROJECT_ROOT, "neural", "models", "hybrid_normalizer_wf.npz")
step(f"Probando load_ensemble_model({MODEL_PATH})...")
model, normalizer = load_ensemble_model(MODEL_PATH, NORM_PATH, "small", "cpu")
step(f"OK load_ensemble_model — {len(model.models)} modelos cargados")

step("=== DIAGNÓSTICO COMPLETO — sin deadlock detectado ===")
