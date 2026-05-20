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
parser.add_argument("--min-confidence", type=float, default=None, help="Base confidence threshold for episode extraction")
parser.add_argument("--min-entry-minute", type=int, default=580, help="Earliest absolute minute of day for episodes (10:30 = 630)")
parser.add_argument("--min-short-entry-minute", type=int, default=None, help="Earliest absolute minute of day for SHORT episodes (10:15 = 615)")
parser.add_argument("--min-short-price-vs-ib-high", type=float, default=None, help="For SHORT episodes, require price_vs_ib_high >= this value")
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

if args.strict_wf and MODEL_PATH.endswith('.joblib') and not MODEL_PATH.endswith('_history.joblib'):
    MODEL_PATH = MODEL_PATH.replace('.joblib', '_history.joblib')

from pathlib import Path
model_path = str(Path(MODEL_PATH).resolve())
normalizer_path = str(Path(NORM_PATH).resolve())

ticker_models = {}
ticker_normalizers = {}
is_ticker_specific = False
ensemble = None
normalizer = None

for ticker in ["SPX", "QQQ", "SPY"]:
    if "_history.joblib" in model_path:
        t_model_path = model_path.replace("_history.joblib", f"_{ticker}_history.joblib")
    else:
        t_model_path = model_path.replace(".joblib", f"_{ticker}.joblib")
    t_norm_path = normalizer_path.replace(".npz", f"_{ticker}.npz")

    if os.path.exists(t_model_path) and os.path.exists(t_norm_path):
        print(f"  [i] Ticker-specific model found for {ticker} in Episode Index Gen")
        try:
            t_model, t_normalizer = load_ensemble_model(t_model_path, t_norm_path, 'small')
            ticker_models[ticker] = t_model
            ticker_normalizers[ticker] = t_normalizer
            is_ticker_specific = True
        except Exception as e:
            print(f"  [WARNING] Failed to load ticker-specific model for {ticker}: {e}")

if is_ticker_specific:
    print(f"  [OK] Loaded ticker-specific models for: {list(ticker_models.keys())}")
    any_model = next(iter(ticker_models.values()))
    ensemble = any_model
    normalizer = next(iter(ticker_normalizers.values()))
else:
    try:
        ensemble, normalizer = load_ensemble_model(model_path, normalizer_path, 'small')
        print(f"  [OK] Ensemble model loaded")
    except Exception as e:
        print(f"  [ERROR] Error loading model: {e}")

df = pd.read_parquet(DATA_PATH)
print(f'Data loaded: {len(df):,} rows')

ep, _ = generate_episode_index(
    df,
    mlp_model=ensemble,
    mlp_normalizer=normalizer,
    min_confidence=args.min_confidence,
    strict_wf=args.strict_wf,
    min_entry_minute=args.min_entry_minute,
    min_short_entry_minute=args.min_short_entry_minute,
    min_short_price_vs_ib_high=args.min_short_price_vs_ib_high,
    ticker_models=ticker_models,
    ticker_normalizers=ticker_normalizers,
    is_ticker_specific=is_ticker_specific,
)

out = os.path.abspath(args.output)
os.makedirs(os.path.dirname(out), exist_ok=True)
ep.to_parquet(out, index=False)
print(f'Saved: {len(ep):,} episodes')
print(f'Directions: {ep.mlp_direction.value_counts().to_dict()}')
print(f'Confidence mean: {ep.mlp_confidence.mean():.4f} +/- {ep.mlp_confidence.std():.4f}')
print(f'Path: {out}')
