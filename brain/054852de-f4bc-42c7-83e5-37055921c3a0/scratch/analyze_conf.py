import pandas as pd
import numpy as np
import torch
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

from neural.gbt_model import load_gbt_ensemble
from neural.hybrid_model import FEATURE_COLUMNS

def analyze_confidence():
    model_path = PROJECT_ROOT / "neural" / "models" / "trading_hybrid_wf.joblib"
    norm_path = PROJECT_ROOT / "neural" / "models" / "hybrid_normalizer_wf.npz"
    data_path = PROJECT_ROOT / "training_data" / "training_data_spx_qqq_spy.parquet"

    print(f"Loading model from {model_path}...")
    ensemble, normalizer = load_gbt_ensemble(str(model_path), str(norm_path))

    print(f"Loading data from {data_path}...")
    df = pd.read_parquet(data_path)
    df = df[df['date'] >= '20260201']
    print(f"Analyzing {len(df)} rows from {df['date'].min()} to {df['date'].max()}...")

    features = np.zeros((len(df), len(FEATURE_COLUMNS)), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in df.columns:
            features[:, i] = df[col].values.astype(np.float32)
    
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)
    
    # Simple predict_proba (not strict-wf for speed, just to see current model capability)
    probs = ensemble.predict_proba(features)
    
    df['prob_short'] = probs[:, 0]
    df['prob_hold'] = probs[:, 1]
    df['prob_long'] = probs[:, 2]
    df['pred'] = np.argmax(probs, axis=1)
    df['max_conf'] = np.max(probs, axis=1)

    print("\nConfidence Distribution (Overall since Feb):")
    print(df['max_conf'].describe())

    print("\nPrediction Distribution (Overall since Feb):")
    print(df['pred'].value_counts().sort_index())

    print("\nMean Confidence per Class:")
    for cls in [0, 1, 2]:
        cls_df = df[df['pred'] == cls]
        if not cls_df.empty:
            print(f"  Class {cls}: count={len(cls_df):5d}, mean_conf={cls_df['max_conf'].mean():.4f}")

    print("\nActionable Signals (Conf >= 0.60):")
    longs = df[(df['pred'] == 2) & (df['max_conf'] >= 0.60)]
    shorts = df[(df['pred'] == 0) & (df['max_conf'] >= 0.65)]
    
    print(f"Total Long signals: {len(longs)} ({len(longs)/len(df):.2%})")
    print(f"Total Short signals: {len(shorts)} ({len(shorts)/len(df):.2%})")

    print("\nSignals by Month:")
    df['month'] = df['date'].str[:6]
    for month in sorted(df['month'].unique()):
        m_df = df[df['month'] == month]
        m_longs = m_df[(m_df['pred'] == 2) & (m_df['max_conf'] >= 0.60)]
        m_shorts = m_df[(m_df['pred'] == 0) & (m_df['max_conf'] >= 0.65)]
        print(f"  {month}: Longs={len(m_longs):3d}, Shorts={len(m_shorts):3d} | Total Rows={len(m_df)}")

if __name__ == "__main__":
    analyze_confidence()
