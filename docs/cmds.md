# Pipeline Commands — SPX, SPY, QQQ (0DTE)

> All commands run from the project root unless noted otherwise.

---

## 1. Data Collection (Historical Training Data)

Generates the parquet file with all features from D:/ThetaData historical data.

```bash
# Full dataset (training)
python neural/collect_training_data_parquet.py \
  --start 20240101 \
  --end 20260220 \
  --workers 26

# Separate backtest period (out-of-sample)
python neural/collect_training_data_parquet.py \
  --start 20260201 \
  --end 20260220 \
  --workers 26 \
  --output training_data_backtest.parquet
```

| Argument | Default | Description |
|---|---|---|
| `--start` | — | Start date YYYYMMDD |
| `--end` | — | End date YYYYMMDD |
| `--workers` | `1` | Parallel workers (set to CPU cores) |
| `--output` | `training_data_derived.parquet` | Output filename in `training_data/` |

---

## 2. Download Options Data (Bulk Historical)

Downloads raw options OHLC + Greeks from ThetaData API to D:/ThetaData.

```bash
# Options chains (all strikes, OHLC + IV + Greeks)
python services/options_downloader.py \
  --symbols SPXW SPX SPY QQQ VIX TLT \
  --start 2024-01-01 \
  --end 2026-02-28

# Derive underlying OHLC from options (spot price proxy)
python services/underlying_downloader.py \
  --symbols SPXW SPX SPY QQQ VIX TLT \
  --start 2024-01-01 \
  --end 2026-02-28

# Fix zero-gaps in 9:30 AM data (corrector)
python services/data_corrector.py \
  --data-dir D:/ThetaData/data_underlying_derived \
  --symbols SPXW SPY QQQ VIX TLT
```

| Argument | Default | Description |
|---|---|---|
| `--symbols` | `SPXW SPX SPY QQQ VIX TLT` | Ticker symbols |
| `--start` | — | Start date YYYY-MM-DD |
| `--end` | — | End date YYYY-MM-DD |
| `--output` | `D:/ThetaData/data_options` | Output directory |
| `--data-dir` | `D:/ThetaData/data_underlying_derived` | Corrector: directory to scan |

---

## 3. Train MLP (Walk-Forward)

Trains the Hybrid Attention-MLP model with temporal cross-validation.

```bash
# --- Option A: Single model ---
python neural/train_walkforward.py \
  --data training_data/training_data_derived.parquet \
  --model-size medium \
  --train-months 6 --test-months 1 \
  --epochs 35 --batch-size 4096 --lr 0.0005

# --- Option B: Ensemble (3 models, consensus voting — RECOMMENDED) ---
python neural/train_walkforward.py \
  --data training_data/training_data_derived.parquet \
  --model-size small \
  --train-months 6 --test-months 1 \
  --epochs 35 --batch-size 4096 --lr 0.0005 \
  --ensemble 3
```

| Argument | Default | Description |
|---|---|---|
| `--data` | `training_data/training_data_derived.parquet` | Training data path |
| `--model-size` | `small` | `micro` / `small` / `medium` / `medium_optimized` / `medium_v2` / `large` |
| `--train-months` | `3` | Training window size (months) |
| `--test-months` | `1` | Test window size (months) |
| `--epochs` | `60` | Training epochs per window |
| `--batch-size` | `1024` | Batch size |
| `--lr` | `0.001` | Learning rate |
| `--ensemble` | `1` | Number of models (1 = single, 3 = ensemble recommended) |

Output: `models/trading_hybrid_wf.pt` + `models/hybrid_normalizer_wf.npz`

---

## 4. Backtest MLP

Simulates trades on historical data and calculates metrics.

```bash
# --- Single model ---
python -X utf8 neural/backtest_hybrid_parquet.py --data training_data/training_data_backtest.parquet --model models/trading_hybrid_wf.pt --model-size medium --threshold 0.70

# --- Ensemble model ---
python -X utf8 neural/backtest_hybrid_parquet.py --data training_data/training_data_backtest.parquet --model models/trading_hybrid_wf.pt --model-size small --threshold 0.70 --ensemble
```

| Argument | Default | Description |
|---|---|---|
| `--data` | `training_data/training_data_derived.parquet` | Backtest data |
| `--model` | `models/trading_hybrid_wf.pt` | Model checkpoint |
| `--normalizer` | `models/hybrid_normalizer_wf.npz` | Normalizer |
| `--model-size` | `small` | Must match training size |
| `--threshold` | `0.7` | Min confidence to trade (0.5-0.9) |
| `--target_long` | `0.010` | LONG profit target (1%) |
| `--target_short` | `0.005` | SHORT profit target (0.5%) |
| `--stop` | `0.003` | Stop loss (0.3%) |
| `--cooldown` | `30` | Minutes between trades per ticker |
| `--max-time` | `120` | Max predicted time to enter |
| `--uncertainty` | `45.0` | Max Bayesian sigma (minutes) |
| `--ensemble` | off | Add flag to load as ensemble |
| `--discord` | off | Send Discord alerts (first 3) |
| `--limit` | `0` | Max trades to simulate (0 = all) |

---

## 5. RL Preprocessing

Builds episode index and options cache for RL training. Run once.

```bash
cd neural
python run_preprocess.py --training-data ../training_data/training_data_derived.parquet --options-dir D:/ThetaData/data_options --output ../rl_data/rl_options_cache_chunks --num-workers 24
```

| Argument | Default | Description |
|---|---|---|
| `--training-data` | — | Path to training parquet |
| `--options-dir` | `D:/ThetaData/data_options` | Path to options data directory |
| `--output` | `../rl_data/rl_options_cache_chunks` | Output directory for per-day cache shards |
| `--num-workers` | `24` | Parallel workers (set to CPU cores) |

Output: `rl_data/episode_index.parquet` + `rl_data/rl_options_cache_chunks/{date}.pkl`

---

## 6. RL Training (PPO)

Trains the RL agent for strike selection + exit timing.

```bash
cd neural
python -m rl.training --episode-index ../rl_data/episode_index.parquet --options-cache ../rl_data/rl_options_cache_chunks --save-dir ../rl_models --total-updates 200
```

| Argument | Default | Description |
|---|---|---|
| `--episode-index` | — | Episode index parquet |
| `--options-cache` | — | Directory of chunked per-day .pkl shards |
| `--save-dir` | `../rl_models` | Directory to save RL checkpoints |
| `--total-updates` | `200` | Number of PPO updates |
| `--max-days-in-ram` | `40` | Max day shards to keep in RAM (LRU) |

Output: `rl_models/best_rl_agent.pt`

---

## 7. RL Backtest (MLP+RL vs MLP-only)

Side-by-side comparison of MLP-only spot trading vs MLP+RL options execution.

```bash
# --- Single MLP + RL ---
python neural/backtest_rl.py \
  --data training_data/training_data_backtest.parquet \
  --model models/trading_hybrid_wf.pt \
  --model-size medium \
  --rl-model rl_models/best_rl_agent.pt \
  --tickers SPX SPY QQQ

# --- Ensemble MLP + RL ---
python neural/backtest_rl.py --data training_data/training_data_backtest.parquet --model models/trading_hybrid_wf.pt --model-size small --rl-model rl_models/best_rl_agent.pt --tickers SPX SPY QQQ --ensemble
```

| Argument | Default | Description |
|---|---|---|
| `--data` | `../training_data/training_data_derived.parquet` | Backtest data |
| `--model` | `../models/trading_hybrid_wf.pt` | MLP checkpoint |
| `--model-size` | `small` | Must match training size |
| `--rl-model` | `../rl_models/best_rl_agent.pt` | RL agent checkpoint |
| `--threshold` | `0.70` | Min confidence |
| `--cooldown` | `30` | Minutes between trades |
| `--tickers` | all | Filter: `SPX SPY QQQ` |
| `--ensemble` | off | Load MLP as ensemble |

---

## 8. Visualization

```bash
# Trade chart (reads backtest CSV results — works regardless of model type)
python neural/visualize_backtest_trades.py --save

# Feature importance (single model)
python neural/visualize_hybrid.py \
  --data training_data/training_data_backtest.parquet \
  --model-size medium \
  --model models/trading_hybrid_wf.pt \
  --save

# Feature importance (ensemble)
python neural/visualize_hybrid.py --data training_data/training_data_backtest.parquet --model-size small --model models/trading_hybrid_wf.pt --save --ensemble
```

| Argument | Default | Description |
|---|---|---|
| `--model` | `models/trading_hybrid_wf.pt` | Model checkpoint |
| `--normalizer` | `models/hybrid_normalizer_wf.npz` | Normalizer |
| `--data` | `training_data/training_data.csv` | Data for feature sampling |
| `--model-size` | `micro` | Must match training size |
| `--feature` | — | Specific feature to inspect in detail |
| `--ensemble` | off | Load as ensemble model |
| `--save` | off | Save chart as PNG |
| `--no-plot` | off | Skip showing chart |

---

## 9. Live Trading

```bash
# Real-time data feed (run first, keep running alongside bot)
python services/realtime_feed.py \
  --symbols SPX SPY QQQ VIX TLT \
  --interval 60

# MLP-only bot
python bots/tradingbot_wrapper.py

# MLP+RL bot (RECOMMENDED — uses ensemble by default)
python bots/tradingbot_wrapper_rl.py
```

| Argument (realtime_feed) | Default | Description |
|---|---|---|
| `--symbols` | `SPX SPY QQQ VIX TLT` | All symbols needed for MLP features |
| `--interval` | `60` | Poll interval in seconds |
| `--dry-run` | off | Single poll then exit |

> `tradingbot_wrapper_rl.py` uses `ENSEMBLE_MODE = True` by default.
> Set to `False` in the file if using a single-model .pt checkpoint.

```bash
# 1. Recolectar datos (si no tienes training_data_spx.parquet)
python collect_training_data_parquet.py `
  --start 20220801 `
  --end 20260220 `
  --workers 26 `
  --tickers SPX `
  --output training_data_spx.parquet
```

```bash
# 2. Entrenar MLP walk-forward
python train_walkforward.py `
  --data ../training_data/training_data_spx.parquet `
  --model-size small `
  --train-months 3 `
  --test-months 1 `
  --epochs 120 `
  --batch-size 1024 `
  --ensemble 5
```

```bash
# 3. Generar episode_index con el nuevo MLP

python generate_episode_index.py

# Ó:

```python
import torch, numpy as np, pandas as pd, sys, os
sys.path.insert(0, '.')
from hybrid_model import load_ensemble_model, FEATURE_COLUMNS

ensemble, normalizer = load_ensemble_model(
    '../models/trading_hybrid_wf.pt',
    '../models/hybrid_normalizer_wf.npz',
    'small'
)
device = next(ensemble.parameters()).device

df = pd.read_parquet('../training_data/training_data_spx.parquet')
print(f'Datos cargados: {len(df):,} filas')

# Normalizar features
feats = normalizer.transform(df[FEATURE_COLUMNS].values.astype('float32'))

# Inferencia en batches
ensemble.eval()
all_probs, all_tpreds = [], []
with torch.no_grad():
    for i in range(0, len(feats), 4096):
        batch = torch.FloatTensor(feats[i:i+4096]).to(device)
        logits, time_pred = ensemble(batch)           # devuelve (logits, time_pred) directamente
        all_probs.append(torch.softmax(logits, -1).cpu().numpy())
        all_tpreds.append(time_pred[:, 0].cpu().numpy())  # solo mu, ignorar log_sigma

probs  = np.concatenate(all_probs)
tpreds = np.concatenate(all_tpreds)

# Añadir columnas al df
dm = {0: 'SHORT', 1: 'HOLD', 2: 'LONG'}
df['mlp_direction']    = [dm[p] for p in np.argmax(probs, 1)]
df['mlp_confidence']   = probs.max(1)
df['mlp_time_to_target'] = tpreds  # ya normalizado 0-1 por sigmoid en forward()

# Filtrar señales válidas
mask = df['mlp_direction'].isin(['LONG', 'SHORT']) & (df['mlp_confidence'] >= 0.55)
ep = df[mask].copy().reset_index(drop=True)
ep['episode_id'] = range(len(ep))

out = os.path.abspath('../rl_data/episode_index.parquet')
os.makedirs(os.path.dirname(out), exist_ok=True)
ep.to_parquet(out, index=False)
print(f'Guardado: {len(ep):,} episodios')
print(f'Direcciones: {ep.mlp_direction.value_counts().to_dict()}')
print(f'Confianza media: {ep.mlp_confidence.mean():.4f} +/- {ep.mlp_confidence.std():.4f}')
print(f'Path: {out}')
"

```bash
python run_preprocess.py `
  --training-data ../training_data/training_data_spx.parquet `
  --options-dir D:/ThetaData/data_options `
  --output ../rl_data/rl_options_cache_chunks `
  --num-workers 26

python -m rl.training `
  --episode-index ../rl_data/episode_index.parquet `
  --options-cache ../rl_data/rl_options_cache_chunks `
  --save-dir ../rl_models `
  --total-updates 200

# DESDE neural/

python ..\backtest\backtest_hybrid_parquet.py `
  --data training_data/training_data_spx.parquet `
  --model models/trading_hybrid_wf.pt `
  --normalizer models/hybrid_normalizer_wf.npz `
  --model-size small --ensemble `
  --threshold 0.55 --cooldown 30 `
  --target_long 0.010 --target_short 0.005 --stop 0.003 `
  --uncertainty 150


  # Ver todos los trades de un día específico con gráfico
python backtest_hybrid_parquet.py/../visualize_backtest_trades.py `
  --trades training_data/backtest_trades.csv `
  --date 20241030


python ..\backtest\backtest_rl.py `
  --data ..\training_data\training_data_spx.parquet `
  --model models\trading_hybrid_wf.pt `
  --normalizer models\hybrid_normalizer_wf.npz `
  --rl-model ..\rl_models\best_rl_agent.pt `
  --model-size small --ensemble `
  --threshold 0.55 --cooldown 30 `
  --target-long 0.010 --target-short 0.005 --stop 0.003



python visualize_backtest_trades.py --trades training_data/backtest_trades.csv --ticker SPX --save

python visualize_hybrid.py `
  --model models/trading_hybrid_wf.pt `
  --normalizer models/hybrid_normalizer_wf.npz `
  --data training_data/training_data_spx.parquet `
  --model-size small `
  --ensemble `
  --save

mv .\training_data\charts\feature_importance_small.png ..\training_data\charts\

  