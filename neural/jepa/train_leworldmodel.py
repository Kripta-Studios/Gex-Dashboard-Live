import os
import gc
import sys
import time
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# Import the model
from le_jepa_model import LeWorldModel, SIGReg

# We import the same data building functions used by the GBT
sys.path.append(str(Path(__file__).parent))
from walkforward_gbt_oof import build_terminal_180m_frame, select_features, normalize_ticker, choose_thresholds

class JEPADataset(Dataset):
    def __init__(self, df: pd.DataFrame, feature_cols: list[str]):
        """
        Creates a dataset where each item has:
        - x_t: current features
        - x_future: features at t+180 (shifted by 180 within the same day)
        - label: future_up_180m (only used for goal-matching / probing, NEVER for training JEPA)
        """
        self.features = df[feature_cols].values.astype(np.float32)
        self.labels = df["future_up_180m"].values.astype(np.float32)
        
        # We need to shift features by 180 steps to get the future state.
        # Since the dataframe is grouped by day in build_terminal_180m_frame, we must be careful at day boundaries.
        # For simplicity in this unsupervised setting, we will shift by 180, and mask out invalid cross-day shifts.
        dates = df["date"].values
        self.future_indices = np.arange(len(df)) + 180
        # Valid if the future index is within bounds and on the same day
        valid_mask = (self.future_indices < len(df)) & (dates == np.roll(dates, -180))
        
        # For invalid future states (end of day), we just map to the last valid state of that day,
        # or we just skip them by mapping to itself (they won't have a good future transition).
        # We'll map invalid indices to the current index (x_future = x_t) to avoid out of bounds, 
        # but in training we should ideally ignore them. 
        self.future_indices = np.where(valid_mask, self.future_indices, np.arange(len(df)))
        self.valid_mask = valid_mask

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        x_t = self.features[idx]
        fut_idx = self.future_indices[idx]
        x_fut = self.features[fut_idx]
        is_valid = self.valid_mask[idx]
        label = self.labels[idx]
        
        return x_t, x_fut, is_valid, label

def train_leworldmodel(train_df: pd.DataFrame, feature_cols: list[str], epochs: int = 10, batch_size: int = 256, device="cuda"):
    """
    Trains the LeWorldModel (Encoder + Predictor) using self-supervised learning.
    """
    dataset = JEPADataset(train_df, feature_cols)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)
    
    model = LeWorldModel(input_dim=len(feature_cols), latent_dim=128, hidden_dim=256, num_blocks=2).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    model.train()
    lam = 0.1 # Trade-off parameter from LeWorldModel paper
    
    for epoch in range(epochs):
        total_loss = 0
        total_pred = 0
        total_sigreg = 0
        
        for x_t, x_fut, is_valid, _ in dataloader:
            # Only train on valid transitions (not crossing days)
            valid = is_valid.bool()
            if not valid.any():
                continue
                
            x_t = x_t[valid].to(device)
            x_fut = x_fut[valid].to(device)
            
            optimizer.zero_grad()
            
            # Forward pass
            z_t, z_fut, z_pred = model(x_t, x_fut)
            
            # 1. Prediction Loss (MSE between predicted future and actual encoded future)
            # Stop-gradient is NOT used in LeJEPA/LeWorldModel
            loss_pred = F.mse_loss(z_pred, z_fut)
            
            # 2. SIGReg Loss to prevent collapse
            # We apply SIGReg to the joint embeddings (both z_t and z_fut) to ensure the whole space is Gaussian
            z_all = torch.cat([z_t, z_fut], dim=0)
            loss_sigreg = SIGReg(z_all)
            
            # Total loss
            loss = loss_pred + lam * loss_sigreg
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            total_loss += loss.item()
            total_pred += loss_pred.item()
            total_sigreg += loss_sigreg.item()
            
        scheduler.step()
        #print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss/len(dataloader):.4f} | Pred: {total_pred/len(dataloader):.4f} | SIGReg: {total_sigreg/len(dataloader):.4f}")
        
    return model

class LinearProbe(nn.Module):
    def __init__(self, latent_dim):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 1)
        )
        
    def forward(self, z):
        return self.fc(z)

def train_linear_probe(
    model,
    train_df: pd.DataFrame,
    feature_cols: list[str],
    epochs: int = 50,
    batch_size: int = 1024,
    device="cuda",
    fine_tune_encoder: bool = False,
):
    """
    Train a supervised probe on top of the JEPA encoder.

    By default this freezes the encoder so the downstream label cannot reshape
    the self-supervised representation. Use fine_tune_encoder=True only for an
    explicit end-to-end supervised ablation.

    Uses PnL-Weighted Loss to prioritize high-magnitude trades and heavily penalize drawdowns.
    """
    if fine_tune_encoder:
        model.train()
    else:
        model.eval()
    probe = LinearProbe(latent_dim=128).to(device)
    probe.train()
    
    params = list(probe.parameters())
    if fine_tune_encoder:
        params += list(model.parameters())
    optimizer = torch.optim.AdamW(params, lr=1e-4, weight_decay=1e-4)
    
    features = train_df[feature_cols].values.astype(np.float32)
    
    # Extract continuous returns for PnL weighting
    returns_bps = train_df["future_return_bps_180m"].values.astype(np.float32)
    labels = (returns_bps >= 0).astype(np.float32)
    
    # PnL Weighting: Mean normalized absolute returns
    abs_returns = np.abs(returns_bps)
    weights = abs_returns / (np.mean(abs_returns) + 1e-8)
    
    x_t = torch.tensor(features, device=device)
    y_t = torch.tensor(labels, device=device).unsqueeze(1)
    w_t = torch.tensor(weights, device=device).unsqueeze(1)
    
    dataset = torch.utils.data.TensorDataset(x_t, y_t, w_t)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    for epoch in range(epochs):
        for batch_x, batch_y, batch_w in dataloader:
            optimizer.zero_grad()
            if fine_tune_encoder:
                batch_z = model.encode(batch_x)
            else:
                with torch.no_grad():
                    batch_z = model.encode(batch_x)
            logits = probe(batch_z)
            
            # PnL-Weighted BCE Loss
            loss = F.binary_cross_entropy_with_logits(logits, batch_y, weight=batch_w)
            
            loss.backward()
            optimizer.step()
            
    return probe

def evaluate_linear_probe(model, probe, test_df: pd.DataFrame, feature_cols: list[str], device="cuda"):
    """
    Evaluates the linear probe on test data and returns probabilities.
    """
    model.eval()
    probe.eval()
    
    features = test_df[feature_cols].values.astype(np.float32)
    x_t = torch.tensor(features, device=device)
    
    batch_size = 1024
    probs = []
    
    with torch.no_grad():
        for i in range(0, len(x_t), batch_size):
            z_t = model.encode(x_t[i:i+batch_size])
            logits = probe(z_t)
            prob = torch.sigmoid(logits)
            probs.append(prob.cpu().numpy())
            
    return np.concatenate(probs).flatten()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Full dataset parquet.")
    parser.add_argument("--jepa-feature-names", required=True, help="Features JSON.")
    parser.add_argument("--output", required=True, help="Output predictions parquet.")
    parser.add_argument("--tickers", nargs="+", default=["QQQ", "SPY", "SPX"])
    parser.add_argument("--min-train-months", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument(
        "--fine-tune-probe-encoder",
        action="store_true",
        help="Allow the supervised probe to update the JEPA encoder. Default keeps the encoder frozen.",
    )
    args = parser.parse_args()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[LeWorldModel] Running on {device}")
    
    df = build_terminal_180m_frame(args.data, 36, 0.0, truncate_to_eod=True)
    features = select_features(df, "base_jepa", args.jepa_feature_names)
    df["ticker"] = df["ticker"].map(normalize_ticker)
    tickers = [normalize_ticker(t) for t in args.tickers]
    
    all_predictions = []
    
    for ticker in tickers:
        ticker_df = df[df["ticker"] == ticker].copy()
        if ticker_df.empty:
            continue
            
        months = sorted(ticker_df["month"].unique().tolist())
        eligible_months = months[args.min_train_months:]
        print(f"--- WalkForward for {ticker} ({len(eligible_months)} months) ---")
        
        for test_month in eligible_months:
            train_months = [m for m in months if m < test_month]
            train_all = ticker_df[ticker_df["month"].isin(train_months)].copy()
            test = ticker_df[ticker_df["month"] == test_month].copy()
            
            if train_all.empty or test.empty:
                continue
                
            # Validation split for threshold selection
            val_keys = train_months[-6:] if len(train_months) > 6 else train_months[-1:]
            fit = train_all[~train_all["month"].isin(val_keys)].copy()
            val = train_all[train_all["month"].isin(val_keys)].copy()
            if fit.empty or val.empty:
                fit = train_all.copy()
                val = train_all.tail(min(len(train_all), max(200, len(train_all) // 5))).copy()
                
            # Normalize features (CRITICAL for Neural Networks)
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            fit[features] = scaler.fit_transform(fit[features].values)
            val[features] = scaler.transform(val[features].values)
            
            # 1. Train LeWorldModel on fit
            model = train_leworldmodel(fit, features, epochs=args.epochs, device=device)
            
            # 2. Train Linear Probe on fit
            probe = train_linear_probe(
                model,
                fit,
                features,
                device=device,
                fine_tune_encoder=bool(args.fine_tune_probe_encoder),
            )
            
            # 3. Evaluate on val to get scores
            val_prob_up = evaluate_linear_probe(model, probe, val, features, device=device)
            
            # 4. Choose thresholds based on strict percentiles
            # We want roughly ~15 longs and ~15 shorts per month (30 trades/month = ~1000 total)
            # 15 / 1100 validation samples = ~1.36%
            long_threshold = float(np.percentile(val_prob_up, 98.5))
            short_threshold = float(np.percentile(val_prob_up, 1.5))
            
            thresholds = {
                "long_threshold": long_threshold,
                "short_threshold": short_threshold
            }
            
            # 5. Retrain on train_all (full data) for the actual test set
            scaler_full = StandardScaler()
            train_all_scaled = train_all.copy()
            train_all_scaled[features] = scaler_full.fit_transform(train_all_scaled[features].values)
            
            test_scaled = test.copy()
            test_scaled[features] = scaler_full.transform(test_scaled[features].values)
            
            model_full = train_leworldmodel(train_all_scaled, features, epochs=args.epochs, device=device)
            probe_full = train_linear_probe(
                model_full,
                train_all_scaled,
                features,
                device=device,
                fine_tune_encoder=bool(args.fine_tune_probe_encoder),
            )
            
            # 6. Evaluate on test set
            test_prob_up = evaluate_linear_probe(model_full, probe_full, test_scaled, features, device=device)
            
            pred = test[["ticker", "date", "time", "month", "pos_in_day", "spot_price", "future_return_180m", "future_return_bps_180m"]].copy()
            for opt_col in ["terminal_exit_time", "terminal_hold_minutes", "terminal_horizon_truncated"]:
                if opt_col in test.columns:
                    pred[opt_col] = test[opt_col]
                    
            pred["jepa180_prob_up"] = test_prob_up
            pred["jepa180_long_threshold"] = float(thresholds["long_threshold"])
            pred["jepa180_short_threshold"] = float(thresholds["short_threshold"])
            
            all_predictions.append(pred)
            
            print(f"[LeWM] {ticker} {test_month}: Train={len(train_all)} Test={len(test)} Done.")
            
    oof_df = pd.concat(all_predictions, ignore_index=True)
    oof_df.to_parquet(args.output)
    print(f"[LeWM] Saved OOF predictions to {args.output}")

if __name__ == "__main__":
    main()
