import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, '.')
from hybrid_model import load_ensemble_model, FEATURE_COLUMNS
from signal_policy import is_actionable_prediction

df = pd.read_parquet("C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/training_data/training_data_spx_qqq_spy.parquet")
model_path = "C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail_SPX_history.joblib"
norm_path = "C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail_norm_SPX.npz"

print(f"Loaded {len(df)} rows")
df_spx = df[df['ticker'] == 'SPX'].copy().reset_index(drop=True)

feature_cols = [c for c in FEATURE_COLUMNS if c in df_spx.columns]
raw = np.zeros((len(df_spx), len(feature_cols)), dtype=np.float32)
for j, col in enumerate(feature_cols):
    raw[:, j] = df_spx[col].values.astype(np.float32)
raw = np.nan_to_num(raw, nan=0.0)

is_up_day = (df_spx["gap_direction"] > 0).values

model, _ = load_ensemble_model(model_path, norm_path, 'small')

probs = model.predict_proba(raw, is_up_day=is_up_day)

print("Probs shape:", probs.shape)
print("Mean prob short:", probs[:, 0].mean())
print("Mean prob hold:", probs[:, 1].mean())
print("Mean prob long:", probs[:, 2].mean())

print("Max prob short:", probs[:, 0].max())
print("Max prob long:", probs[:, 2].max())

print("Number of probs short > 0.45:", (probs[:, 0] >= 0.45).sum())
print("Number of probs long > 0.45:", (probs[:, 2] >= 0.45).sum())
