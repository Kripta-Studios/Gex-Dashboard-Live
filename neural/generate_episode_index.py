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
parser.add_argument("--strict-wf", action="store_true", help="Enable strict Walk-Forward date filtering for GBT inference")
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

if args.strict_wf and MODEL_PATH.endswith('.joblib'):
    MODEL_PATH = MODEL_PATH.replace('.joblib', '_history.joblib')

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
    if args.strict_wf:
        print(f"  [i] Using STRICT Walk-Forward inference (date-by-date filtering) for Episode Index...")
        probs = np.zeros((len(df), 3), dtype=np.float32)
        unique_dates = sorted(df['date'].unique()) # Using 'date' column as filter
        for d_str in unique_dates:
            mask = df['date'] == d_str
            idx = np.where(mask)[0]
            if len(idx) == 0: continue
            probs[idx] = ensemble.predict_proba(feats[idx], date=str(d_str))
    else:
        probs = ensemble.predict_proba(feats)
        
    # Dummy time predictions
    tpreds = np.column_stack([
        np.full(len(feats), 60.0),
        np.full(len(feats), 0.0)
    ])
    print(f'  [GBT] Inference complete (strict={args.strict_wf}): {len(feats):,} samples')
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

# Filter valid signals with ASYMMETRIC threshold
# SHORT signals are harder for the model to detect, so we use a lower threshold to capture more of them.
short_thresh = RL_CONFIG['min_confidence'] - 0.05
long_thresh  = RL_CONFIG['min_confidence']

mask_long  = (df['mlp_direction'] == 'LONG')  & (df['mlp_confidence'] >= long_thresh)
mask_short = (df['mlp_direction'] == 'SHORT') & (df['mlp_confidence'] >= short_thresh)

ep_long  = df[mask_long].copy()
ep_short = df[mask_short].copy()

print(f'Detected signals: LONG={len(ep_long):,} SHORT={len(ep_short):,}')

# ── NO OVERSAMPLING here ──
# Previously, SHORT/LONG were oversampled (duplicated) to match counts.
# This caused data leakage: the same episode could appear in both RL train
# and eval splits as duplicates, inflating eval metrics.
# The RL trainer handles class balance during collect_episodes() via
# weighted sampling from the date-restricted pool.
if not ep_short.empty and not ep_long.empty:
    n_long = len(ep_long)
    n_short = len(ep_short)
    ratio = max(n_long, n_short) / max(min(n_long, n_short), 1)
    print(f'  [Balance] No oversampling (anti-leakage). L:S ratio = {ratio:.2f}')
    print(f'  [Balance] RL trainer will handle balance via weighted sampling per split.')

ep = pd.concat([ep_long, ep_short]).sort_values('date').reset_index(drop=True)
ep['episode_id'] = range(len(ep))

out = os.path.abspath(args.output)
os.makedirs(os.path.dirname(out), exist_ok=True)
ep.to_parquet(out, index=False)
print(f'Saved: {len(ep):,} episodes')
print(f'Directions: {ep.mlp_direction.value_counts().to_dict()}')
print(f'Confidence mean: {ep.mlp_confidence.mean():.4f} +/- {ep.mlp_confidence.std():.4f}')
print(f'Path: {out}')