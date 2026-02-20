#!/usr/bin/env python3
"""
Script para inspeccionar el modelo guardado y detectar el mismatch exacto.
"""

import sys
import os
import torch
import numpy as np

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

print("=" * 80)
print("INSPECCIÓN DEL MODELO Y NORMALIZER")
print("=" * 80)

MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "trading_hybrid_wf.pt")
NORMALIZER_PATH = os.path.join(PROJECT_ROOT, "models", "hybrid_normalizer_wf.npz")

# =============================================================================
# 1. INSPECCIONAR CHECKPOINT
# =============================================================================
print("\n[1] Inspeccionando checkpoint del modelo...")

if not os.path.exists(MODEL_PATH):
    print(f"❌ Modelo no encontrado: {MODEL_PATH}")
    sys.exit(1)

checkpoint = torch.load(MODEL_PATH, map_location='cpu')

print(f"✅ Checkpoint cargado")
print(f"\nClaves en el checkpoint:")
for key in checkpoint.keys():
    if key != 'model_state_dict':
        print(f"  - {key}: {checkpoint[key]}")

print(f"\nArquitectura del modelo (capas relevantes):")
for key, value in checkpoint['model_state_dict'].items():
    if 'weight' in key and ('fc' in key or 'output' in key):
        print(f"  {key}: {value.shape}")

# Extraer dimensiones clave
mlp_input_shape = checkpoint['model_state_dict']['mlp.0.fc.weight'].shape
n_features_in_model = mlp_input_shape[1]

print(f"\n🎯 DIMENSIÓN CRÍTICA:")
print(f"   El modelo espera: {n_features_in_model} features de entrada")

# =============================================================================
# 2. INSPECCIONAR NORMALIZER
# =============================================================================
print("\n[2] Inspeccionando normalizer...")

if not os.path.exists(NORMALIZER_PATH):
    print(f"❌ Normalizer no encontrado: {NORMALIZER_PATH}")
    sys.exit(1)

norm_data = np.load(NORMALIZER_PATH)

print(f"✅ Normalizer cargado")
print(f"\nContenido del normalizer:")
print(f"  Mean shape: {norm_data['mean'].shape}")
print(f"  Std shape: {norm_data['std'].shape}")
print(f"  Feature names: {len(norm_data['feature_names'])} features")

n_features_in_normalizer = len(norm_data['feature_names'])

print(f"\n🎯 DIMENSIÓN CRÍTICA:")
print(f"   El normalizer tiene: {n_features_in_normalizer} features")

print(f"\nPrimeras 20 features en el normalizer:")
for i, feat in enumerate(norm_data['feature_names'][:20]):
    print(f"  {i:3d}. {feat}")

if len(norm_data['feature_names']) > 20:
    print(f"  ... ({len(norm_data['feature_names']) - 20} más)")

# =============================================================================
# 3. COMPARAR CON CÓDIGO ACTUAL
# =============================================================================
print("\n[3] Comparando con código actual...")

try:
    from neural.hybrid_model import FEATURE_COLUMNS
    
    print(f"✅ FEATURE_COLUMNS cargado")
    print(f"   Código actual define: {len(FEATURE_COLUMNS)} features")
    
    print(f"\nPrimeras 20 features en FEATURE_COLUMNS:")
    for i, feat in enumerate(FEATURE_COLUMNS[:20]):
        print(f"  {i:3d}. {feat}")
    
    if len(FEATURE_COLUMNS) > 20:
        print(f"  ... ({len(FEATURE_COLUMNS) - 20} más)")
    
except Exception as e:
    print(f"❌ Error cargando FEATURE_COLUMNS: {e}")
    FEATURE_COLUMNS = []

# =============================================================================
# 4. ANÁLISIS DE DISCREPANCIAS
# =============================================================================
print("\n" + "=" * 80)
print("ANÁLISIS DE DISCREPANCIAS")
print("=" * 80)

print(f"\nResumen:")
print(f"  Modelo espera:      {n_features_in_model} features")
print(f"  Normalizer tiene:   {n_features_in_normalizer} features")
print(f"  Código actual usa:  {len(FEATURE_COLUMNS)} features")

if n_features_in_model == n_features_in_normalizer:
    print(f"\n✅ Modelo y normalizer son consistentes")
else:
    print(f"\n❌ INCONSISTENCIA: Modelo ({n_features_in_model}) ≠ Normalizer ({n_features_in_normalizer})")

if len(FEATURE_COLUMNS) == n_features_in_normalizer:
    print(f"✅ Código y normalizer son consistentes")
else:
    diff = len(FEATURE_COLUMNS) - n_features_in_normalizer
    if diff > 0:
        print(f"⚠️  Código tiene {diff} features EXTRA vs normalizer")
    else:
        print(f"⚠️  Código tiene {abs(diff)} features MENOS vs normalizer")

# =============================================================================
# 5. IDENTIFICAR FEATURES FALTANTES/EXTRA
# =============================================================================
if FEATURE_COLUMNS and norm_data['feature_names']:
    print("\n[5] Identificando diferencias en features...")
    
    trained_features = set(norm_data['feature_names'])
    current_features = set(FEATURE_COLUMNS)
    
    missing = current_features - trained_features
    extra = trained_features - current_features
    
    if missing:
        print(f"\n⚠️  Features en código ACTUAL pero NO en modelo entrenado ({len(missing)}):")
        for feat in sorted(list(missing))[:20]:
            print(f"  - {feat}")
        if len(missing) > 20:
            print(f"  ... y {len(missing) - 20} más")
    
    if extra:
        print(f"\n⚠️  Features en modelo ENTRENADO pero NO en código actual ({len(extra)}):")
        for feat in sorted(list(extra))[:20]:
            print(f"  - {feat}")
        if len(extra) > 20:
            print(f"  ... y {len(extra) - 20} más")
    
    if not missing and not extra:
        print("\n✅ Las features son idénticas entre código y modelo")

# =============================================================================
# 6. RECOMENDACIÓN
# =============================================================================
print("\n" + "=" * 80)
print("RECOMENDACIÓN")
print("=" * 80)

if n_features_in_model != len(FEATURE_COLUMNS):
    print("\n🔴 ACCIÓN REQUERIDA:")
    print("\nTienes 2 opciones:")
    print("\nOPCIÓN 1 (Rápida - Para testing):")
    print("  Modificar el código para que use solo las features del modelo entrenado:")
    print(f"  FEATURE_COLUMNS = FEATURE_COLUMNS[:{n_features_in_model}]")
    print("  ⚠️  Esto descartará las features nuevas")
    
    print("\nOPCIÓN 2 (Correcta - Para producción):")
    print("  Re-entrenar el modelo con todas las features actuales:")
    print("  1. Generar nuevo training data")
    print("  2. Ejecutar: python train_walkforward.py")
    print(f"  3. El modelo se entrenará con {len(FEATURE_COLUMNS)} features")
    
else:
    print("\n✅ El número de features coincide")
    print("El problema puede estar en otro lado (ver errores de carga del modelo)")

print("\n" + "=" * 80)
