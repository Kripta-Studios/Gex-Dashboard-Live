"""
Generate Episode Index — creates episode_index.parquet for RL training.

Runs the ensemble model (GBT or MLP) over the full training dataset,
extracts directional signals with confidence >= min_confidence,
and saves a balanced LONG/SHORT episode index.
"""
import pandas as pd
import sys
import os
import argparse

sys.path.insert(0, '.')
from hybrid_model import load_ensemble_model
from rl.preprocess import generate_episode_index

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

ep, _ = generate_episode_index(
    df,
    mlp_model=ensemble,
    mlp_normalizer=normalizer,
    strict_wf=args.strict_wf,
)

out = os.path.abspath(args.output)
os.makedirs(os.path.dirname(out), exist_ok=True)
ep.to_parquet(out, index=False)
print(f'Saved: {len(ep):,} episodes')
print(f'Directions: {ep.mlp_direction.value_counts().to_dict()}')
print(f'Confidence mean: {ep.mlp_confidence.mean():.4f} +/- {ep.mlp_confidence.std():.4f}')
print(f'Path: {out}')
