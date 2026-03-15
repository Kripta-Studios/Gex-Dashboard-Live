"""
Generate Episode Index — creates episode_index.parquet for RL training.

Runs the ensemble model (GBT or MLP) over the full training dataset,
extracts directional signals with confidence >= min_confidence,
and saves a balanced LONG/SHORT episode index.
"""
import numpy as np
import pandas as pd
import torch
import sys
import os
import argparse

sys.path.insert(0, '.')
from hybrid_model import load_ensemble_model, FEATURE_COLUMNS
from rl.config import RL_CONFIG

parser = argparse.ArgumentParser(description="Generate Episode Index for RL")
parser.add_argument("--data", default=os.environ.get('TRAINING_DATA', '../training_data/training_data_spx_qqq.parquet'), help="Path to the training data parquet file")
parser.add_argument("--output", default='../rl_data/episode_index.parquet', help="Path to save the generated episode index parquet file")
args = parser.parse_args()

# Paths relative to neural/ (CWD)
MODEL_PATH = os.environ.get('MODEL_PATH', 'models/trading_hybrid_wf.joblib')
NORM_PATH  = os.environ.get('NORM_PATH', 'models/hybrid_normalizer_wf.npz')
DATA_PATH  = args.data

# Auto-detect model format
if not os.path.exists(MODEL_PATH):
    # Fallback to legacy .pt path
    alt_path = MODEL_PATH.replace('.joblib', '.pt')
    if os.path.exists(alt_path):
        MODEL_PATH = alt_path
        print(f"  [!] Using legacy .pt model: {MODEL_PATH}")

ensemble, normalizer = load_ensemble_model(MODEL_PATH, NORM_PATH, 'small')

df = pd.read_parquet(DATA_PATH)
print(f'Data loaded: {len(df):,} rows')

# Filter to only features that exist in the parquet
cols = [c for c in FEATURE_COLUMNS if c in df.columns]
missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
if missing:
    print(f'  [!] {len(missing)} features missing from parquet (using {len(cols)}/{len(FEATURE_COLUMNS)}): {missing}')

# Normalize features
feats = normalizer.transform(df[cols].values.astype('float32'))

# Inference
all_probs, all_tpreds = [], []

# Check if this is a GBT or PyTorch model
is_gbt = hasattr(ensemble, 'predict_proba') and not isinstance(ensemble, torch.nn.Module)

if is_gbt:
    # GBT: direct numpy inference
    probs = ensemble.predict_proba(feats)
    # Dummy time predictions
    tpreds = np.column_stack([
        np.full(len(feats), 60.0),
        np.full(len(feats), 0.0)
    ])
    print(f'  [GBT] Inference complete: {len(feats):,} samples')
else:
    # PyTorch: batch inference with GPU
    device = next(ensemble.parameters()).device
    ensemble.eval()
    with torch.no_grad():
        for i in range(0, len(feats), 4096):
            batch = torch.FloatTensor(feats[i:i+4096]).to(device)
            logits, time_pred = ensemble(batch)
            all_probs.append(torch.softmax(logits, -1).cpu().numpy())
            all_tpreds.append(time_pred.cpu().numpy())
    probs  = np.concatenate(all_probs)
    tpreds = np.concatenate(all_tpreds)

# Add columns to df
dm = {0: 'SHORT', 1: 'HOLD', 2: 'LONG'}
df['mlp_direction']      = [dm[p] for p in np.argmax(probs, 1)]
df['mlp_confidence']     = probs.max(1)
df['mlp_time_to_target'] = tpreds[:, 0] / 180.0  # normalized 0-1
df['mlp_log_sigma']      = tpreds[:, 1]

# Filter valid signals
mask = df['mlp_direction'].isin(['LONG', 'SHORT']) & (df['mlp_confidence'] >= RL_CONFIG['min_confidence'])
ep = df[mask].copy().reset_index(drop=True)

# ── Balance LONG/SHORT episodes ──
ep_long = ep[ep.mlp_direction == 'LONG']
ep_short = ep[ep.mlp_direction == 'SHORT']
n_min = min(len(ep_long), len(ep_short))
print(f'Pre-balance: LONG={len(ep_long):,} SHORT={len(ep_short):,} → downsample to {n_min:,} each')
if len(ep_short) > n_min:
    ep_short = ep_short.sample(n_min, random_state=42)
if len(ep_long) > n_min:
    ep_long = ep_long.sample(n_min, random_state=42)
ep = pd.concat([ep_long, ep_short]).sort_values('date').reset_index(drop=True)
ep['episode_id'] = range(len(ep))

out = os.path.abspath(args.output)
os.makedirs(os.path.dirname(out), exist_ok=True)
ep.to_parquet(out, index=False)
print(f'Saved: {len(ep):,} episodes')
print(f'Directions: {ep.mlp_direction.value_counts().to_dict()}')
print(f'Confidence mean: {ep.mlp_confidence.mean():.4f} +/- {ep.mlp_confidence.std():.4f}')
print(f'Path: {out}')