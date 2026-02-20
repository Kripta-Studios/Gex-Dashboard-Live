#!/usr/bin/env python3
"""
Script de Diagnóstico Completo del Trading Bot
Verifica TODOS los componentes y simula una predicción real.
"""

import sys
import os
import json
import numpy as np
from datetime import datetime
import pytz

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

print("=" * 80)
print("DIAGNÓSTICO COMPLETO DEL TRADING BOT")
print("=" * 80)

# =============================================================================
# TEST 1: Cargar el Modelo
# =============================================================================
print("\n[TEST 1] Cargando modelo...")

try:
    import torch
    from neural.hybrid_model import load_hybrid_model, FEATURE_COLUMNS, get_device
    
    MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "trading_hybrid_wf.pt")
    NORMALIZER_PATH = os.path.join(PROJECT_ROOT, "models", "hybrid_normalizer_wf.npz")
    
    # Intentar cargar con MICRO
    device = get_device()
    print(f"  Device: {device}")
    
    model, normalizer = load_hybrid_model(
        MODEL_PATH, 
        NORMALIZER_PATH,
        model_size='micro'  # FORZAR MICRO
    )
    
    print(f"  ✅ Modelo cargado exitosamente")
    print(f"  Features esperadas: {len(FEATURE_COLUMNS)}")
    print(f"  Normalizer features: {len(normalizer.feature_names) if hasattr(normalizer, 'feature_names') else 'N/A'}")
    
    # Ver arquitectura
    print(f"\n  Arquitectura del modelo:")
    for name, param in model.named_parameters():
        if 'mlp' in name and 'weight' in name and 'fc' in name:
            print(f"    {name}: {param.shape}")
    
except Exception as e:
    print(f"  ❌ ERROR cargando modelo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 2: Verificar TradingWrapper
# =============================================================================
print("\n[TEST 2] Verificando TradingWrapper...")

try:
    from trading_wrapper import TradingWrapper, MarketRegime
    
    GREEK_DATA_DIR = os.getenv("GREEK_DATA_DIR", "/home/Option-Greeks-Plotting-Discord-Bot/json_data")
    FOURIER_DIR = os.getenv("FOURIER_DIR", "/home/Option-Greeks-Plotting-Discord-Bot/fourier")
    IB_CHARTS_DIR = os.getenv("IB_CHARTS_DIR", "/home/Option-Greeks-Plotting-Discord-Bot/ib_charts")
    
    print(f"  Greek data dir: {GREEK_DATA_DIR}")
    print(f"  Fourier dir: {FOURIER_DIR}")
    print(f"  IB charts dir: {IB_CHARTS_DIR}")
    
    wrapper = TradingWrapper(
        model=model,
        normalizer=normalizer,
        greek_dir=GREEK_DATA_DIR,
        fourier_dir=FOURIER_DIR,
        ib_dir=IB_CHARTS_DIR,
        min_confidence=0.50,  # Bajo para testing
        min_iv_pct=0.0  # Desactivado
    )
    
    print(f"  ✅ TradingWrapper creado exitosamente")
    
except Exception as e:
    print(f"  ❌ ERROR creando wrapper: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 3: Verificar Timezone
# =============================================================================
print("\n[TEST 3] Verificando timezone...")

try:
    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    
    print(f"  Hora del servidor: {datetime.now()}")
    print(f"  Hora en NY: {now_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Check trading hours
    hour = now_ny.hour
    minute = now_ny.minute
    current_mins = hour * 60 + minute
    open_mins = 9 * 60 + 30  # 9:30 AM
    close_mins = 16 * 60 + 0  # 4:00 PM
    
    in_trading_hours = (open_mins + 15) <= current_mins <= (close_mins - 15)
    
    print(f"  Current time (mins): {current_mins}")
    print(f"  Trading window: {open_mins + 15} - {close_mins - 15}")
    print(f"  ✅ En horario de trading: {in_trading_hours}")
    
    if not in_trading_hours:
        print(f"  ⚠️  FUERA de horario de trading!")
        print(f"  Esto explicaría por qué no hay señales")
    
except Exception as e:
    print(f"  ❌ ERROR verificando timezone: {e}")

# =============================================================================
# TEST 4: Verificar Datos de Griegas
# =============================================================================
print("\n[TEST 4] Verificando datos de griegas...")

try:
    from pathlib import Path
    import glob
    
    tickers_to_check = ["SPX", "SPY", "QQQ"]
    
    for ticker in tickers_to_check:
        pattern = f"{ticker}_0dte_ExposureData_*.json"
        files = sorted(
            glob.glob(os.path.join(GREEK_DATA_DIR, pattern)),
            key=lambda p: os.path.getmtime(p),
            reverse=True
        )
        
        if files:
            latest = files[0]
            age_seconds = datetime.now().timestamp() - os.path.getmtime(latest)
            age_minutes = age_seconds / 60
            
            status = "✅" if age_minutes < 5 else "⚠️"
            print(f"  {status} {ticker}: {os.path.basename(latest)} ({age_minutes:.1f} min old)")
            
            if age_minutes < 5:
                # Intentar cargar
                try:
                    with open(latest, 'r') as f:
                        data = json.load(f)
                    
                    spot = data.get("spot_price", 0)
                    gamma_data = data.get("totalgamma", {}).get("all", [])
                    net_gamma = sum(gamma_data) if gamma_data else 0
                    
                    print(f"      Spot: {spot}, Net Gamma: {net_gamma:.2e}")
                except Exception as e:
                    print(f"      ❌ Error leyendo JSON: {e}")
        else:
            print(f"  ❌ {ticker}: No hay archivos")
    
except Exception as e:
    print(f"  ❌ ERROR verificando griegas: {e}")

# =============================================================================
# TEST 5: Verificar Datos de IB
# =============================================================================
print("\n[TEST 5] Verificando datos de IB...")

try:
    for ticker in ["SPX", "SPY", "QQQ", "ES", "NQ"]:
        pattern = f"ib_data_{ticker}_*.json"
        files = sorted(
            glob.glob(os.path.join(IB_CHARTS_DIR, pattern)),
            key=lambda p: os.path.getmtime(p),
            reverse=True
        )
        
        if files:
            latest = files[0]
            age_seconds = datetime.now().timestamp() - os.path.getmtime(latest)
            age_minutes = age_seconds / 60
            
            status = "✅" if age_minutes < 5 else "⚠️"
            print(f"  {status} {ticker}: {os.path.basename(latest)} ({age_minutes:.1f} min old)")
        else:
            print(f"  ❌ {ticker}: No hay archivos")
    
except Exception as e:
    print(f"  ❌ ERROR verificando IB: {e}")

# =============================================================================
# TEST 6: Simular Predicción Real
# =============================================================================
print("\n[TEST 6] Simulando predicción con datos reales...")

try:
    # Cargar datos reales de SPX
    pattern = "SPX_0dte_ExposureData_*.json"
    files = sorted(
        glob.glob(os.path.join(GREEK_DATA_DIR, pattern)),
        key=lambda p: os.path.getmtime(p),
        reverse=True
    )
    
    if not files:
        print("  ⚠️  No hay datos de SPX para simular")
    else:
        with open(files[0], 'r') as f:
            greek_data = json.load(f)
        
        spot = greek_data.get("spot_price", 0)
        print(f"  Usando datos de: {os.path.basename(files[0])}")
        print(f"  Spot price: {spot}")
        
        # Crear features dummy basadas en los datos reales
        features = np.zeros(101, dtype=np.float32)
        
        # Intentar extraer algunas features reales
        gamma_data = greek_data.get("totalgamma", {}).get("all", [])
        if gamma_data:
            features[0] = float(sum(gamma_data))  # net_gamma
        
        vanna_data = greek_data.get("totalvanna", {}).get("all", [])
        if vanna_data:
            features[1] = float(sum(vanna_data))  # net_vanna
        
        print(f"  Features creadas: {len(features)}")
        print(f"  net_gamma: {features[0]:.2e}")
        print(f"  net_vanna: {features[1]:.2e}")
        
        # Intentar predecir con el wrapper
        signal = wrapper.get_signal("SPX", features, spot)
        
        print(f"\n  📊 RESULTADO DE LA PREDICCIÓN:")
        print(f"    Direction: {signal.direction}")
        print(f"    Raw Confidence: {signal.raw_confidence:.4f}")
        print(f"    Calibrated Confidence: {signal.calibrated_confidence:.4f}")
        print(f"    Position Size: {signal.position_size:.4f}")
        print(f"    Regime: {signal.regime}")
        print(f"    Entry Price: {signal.entry_price}")
        print(f"    Stop Loss: {signal.stop_loss}")
        print(f"    Take Profit 1: {signal.take_profit_1}")
        
        if hasattr(signal, 'reasoning'):
            print(f"\n  📝 REASONING:")
            for key, value in signal.reasoning.items():
                if key == 'raw_probs':
                    print(f"    {key}:")
                    for cls, prob in value.items():
                        print(f"      {cls}: {prob:.4f}")
                elif key != 'regime_data':
                    print(f"    {key}: {value}")
        
        # Diagnóstico de por qué se bloqueó
        if signal.raw_confidence == 0.0:
            print(f"\n  🔴 SEÑAL BLOQUEADA - Analizando razón...")
            
            # Verificar régimen
            regime, meta = wrapper.regime_filter.classify_regime("SPX")
            print(f"    Régimen detectado: {regime}")
            print(f"    Metadata:")
            for key, value in meta.items():
                if key != 'regime_data':
                    print(f"      {key}: {value}")
            
            # Verificar tradeable
            tradeable, reason = wrapper.regime_filter.is_tradeable("SPX")
            print(f"\n    is_tradeable: {tradeable}")
            print(f"    Razón: {reason}")
            
            if not tradeable:
                print(f"\n  🎯 PROBLEMA ENCONTRADO:")
                print(f"    El wrapper está bloqueando la señal con: {reason}")
        
        elif signal.direction == "HOLD":
            print(f"\n  ℹ️  Modelo predice HOLD (confianza: {signal.raw_confidence:.4f})")
        
        else:
            print(f"\n  ✅ SEÑAL VÁLIDA GENERADA!")
            print(f"    El modelo está funcionando correctamente")
    
except Exception as e:
    print(f"  ❌ ERROR simulando predicción: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# TEST 7: Verificar Calibration
# =============================================================================
print("\n[TEST 7] Verificando calibration.json...")

CALIBRATION_PATH = os.path.join(PROJECT_ROOT, "models", "calibration.json")

if os.path.exists(CALIBRATION_PATH):
    print(f"  ✅ Archivo existe: {CALIBRATION_PATH}")
    try:
        with open(CALIBRATION_PATH, 'r') as f:
            cal = json.load(f)
        
        print(f"  Contenido:")
        print(f"    min_confidence: {cal.get('min_confidence', 'N/A')}")
        print(f"    regime_adjustments: {cal.get('regime_adjustments', {})}")
        
        if cal.get('min_confidence', 0) > 0.70:
            print(f"  ⚠️  min_confidence muy alto: {cal['min_confidence']}")
        
    except Exception as e:
        print(f"  ⚠️  Error leyendo calibration: {e}")
else:
    print(f"  ⚠️  Archivo NO existe: {CALIBRATION_PATH}")
    print(f"  El wrapper usará defaults")

# =============================================================================
# RESUMEN FINAL
# =============================================================================
print("\n" + "=" * 80)
print("RESUMEN DEL DIAGNÓSTICO")
print("=" * 80)

issues = []

if 'model' not in dir() or model is None:
    issues.append("❌ Modelo no se cargó correctamente")

if not in_trading_hours:
    issues.append("⚠️  Fuera de horario de trading (8:00 AM - 4:30 PM EST)")

if issues:
    print("\n🔴 PROBLEMAS DETECTADOS:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("\n✅ Todos los componentes básicos funcionan")

print("\n📋 RECOMENDACIONES:")
print("  1. Si el modelo carga pero no hay señales:")
print("     → Verifica que estés en horario de trading (TEST 3)")
print("     → Verifica que los datos sean recientes (<5 min, TEST 4)")
print("  2. Si la señal se bloquea con confidence=0.0:")
print("     → Mira el TEST 6 para ver la razón exacta del bloqueo")
print("  3. Si todo está OK pero sigue sin funcionar:")
print("     → Ejecuta el bot con este comando para ver logs en vivo:")
print("     → python tradingbot_wrapper.py 2>&1 | tee bot_output.log")

print("\n" + "=" * 80)
