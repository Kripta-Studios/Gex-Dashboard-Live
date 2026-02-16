import os
import sys
import argparse
import time
import json
import numpy as np
import pandas as pd
from pathlib import Path
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from hybrid_model import (
    get_hybrid_model, get_device, save_hybrid_model,
    FeatureNormalizer, FEATURE_COLUMNS
)

from data_utils import walk_forward_splits, add_sample_weights

# --- DATA AUGMENTATION ---
class FeatureAugmentation:
    """
    Data augmentation for tabular features.
    Helps prevent overfitting on small datasets.
    """
    
    def __init__(self, noise_std: float = 0.1, dropout_prob: float = 0.1):
        self.noise_std = noise_std
        self.dropout_prob = dropout_prob
    
    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        # Add Gaussian noise
        if self.noise_std > 0:
            noise = torch.randn_like(x) * self.noise_std
            x = x + noise
        
        # Random feature dropout (set some features to 0)
        if self.dropout_prob > 0:
            mask = torch.rand_like(x) > self.dropout_prob
            x = x * mask.float()
        
        return x

def get_class_weights(targets: np.ndarray, smoothing: float = 0.3) -> torch.Tensor:
    """
    Compute class weights for imbalanced data with optional smoothing.
    """
    class_counts = np.bincount(targets, minlength=3)
    total = len(targets)
    
    # Raw inverse frequency weights
    raw_weights = total / (3 * class_counts + 1e-6)
    
    # Smooth towards uniform weights (all 1.0)
    smooth_weights = (1 - smoothing) * raw_weights + smoothing * np.ones(3)
    
    # Debug output
    print(f"    Class distribution (smoothing={smoothing}):")
    for i, name in enumerate(["SHORT", "HOLD", "LONG"]):
        print(f"      {name} ({i}): {class_counts[i]:,} samples → "
              f"weight {smooth_weights[i]:.3f}")
    
    return torch.FloatTensor(smooth_weights)

# --- METRICAS DE TRADING ---
def calculate_trading_metrics(predictions, targets):
    metrics = {}
    metrics["accuracy"] = (predictions == targets).mean()
    class_names = ["SHORT", "HOLD", "LONG"]
    for cls_idx, cls_name in enumerate(class_names):
        pred_mask = (predictions == cls_idx)
        if pred_mask.sum() > 0:
            precision = (targets[pred_mask] == cls_idx).sum() / pred_mask.sum()
            metrics[f"precision_{cls_name}"] = float(precision)
            metrics[f"count_{cls_name}"] = int(pred_mask.sum())
    
    trade_mask = (predictions != 1)
    if trade_mask.sum() > 0:
        wins = (predictions[trade_mask] == targets[trade_mask]).sum()
        metrics["win_rate"] = float(wins / trade_mask.sum())
        losses = trade_mask.sum() - wins
        metrics["profit_factor"] = float(wins / losses) if losses > 0 else float('inf')
    else:
        metrics["win_rate"], metrics["profit_factor"] = 0, 0
    return metrics

# --- LOSS FUNCTIONS ---
class LabelSmoothingCrossEntropy(nn.Module):
    def __init__(self, smoothing=0.1, num_classes=3, weights=None):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes
        self.weights = weights
    def forward(self, logits, targets):
        confidence = 1.0 - self.smoothing
        smooth_val = self.smoothing / (self.num_classes - 1)
        one_hot = torch.zeros_like(logits).scatter_(1, targets.unsqueeze(1), 1)
        labels = one_hot * confidence + (1 - one_hot) * smooth_val
        log_probs = torch.log_softmax(logits, dim=-1)
        loss = (-labels * log_probs).sum(dim=-1)
        if self.weights is not None:
            loss = loss * self.weights[targets]
        return loss.mean()

def gaussian_nll_loss_clamped(mu, log_sigma, target, mask):
    log_sigma = torch.clamp(log_sigma, min=-3.0, max=3.0)
    variance = torch.exp(2 * log_sigma) + 1e-6
    loss = 0.5 * torch.log(variance) + 0.5 * (((target - mu) ** 2) / variance)
    return (loss.squeeze() * mask).sum() / (mask.sum() + 1e-8)

# --- ENTRENAMIENTO DE UNA VENTANA ---
def train_single_window(train_df, val_df, model_size="small", epochs=50, batch_size=1024, 
                        learning_rate=0.001, weight_decay=0.1, label_smoothing=0.1, 
                        augment_noise=0.05, augment_dropout=0.1, warmup_epochs=5,
                        device=None, verbose=True):
    if device is None: device = get_device()
    
    cols = [c for c in FEATURE_COLUMNS if c in train_df.columns]
    
    # Preparar datos
    def prep(df):
        x = np.nan_to_num(df[cols].values.astype(np.float32), nan=0.0, posinf=5.0, neginf=-5.0)
        y = (df['target'].values + 1).astype(np.int64)
        t = df['time_to_target'].values.astype(np.float32) / 120.0
        return x, y, t

    X_train_raw, y_train, t_train = prep(train_df)
    X_val_raw, y_val, t_val = prep(val_df)

    norm = FeatureNormalizer()
    X_train = norm.fit_transform(X_train_raw, cols)
    X_val = norm.transform(X_val_raw)

    # Pesos robustos
    cw_tensor = get_class_weights(y_train, smoothing=0.3).to(device)
    
    # Sampler basado en pesos de clase + sample weights (freshness)
    # Reconstruimos los pesos por muestra para el sampler
    class_weights_np = cw_tensor.cpu().numpy()
    sample_weights = np.array([class_weights_np[y] for y in y_train])
    
    if 'sample_weight' in train_df.columns:
        sample_weights *= train_df['sample_weight'].values
    
    sampler = WeightedRandomSampler(torch.FloatTensor(sample_weights), len(sample_weights))

    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train), torch.FloatTensor(t_train)), 
                              batch_size=batch_size, sampler=sampler)
    val_loader = DataLoader(TensorDataset(torch.FloatTensor(X_val), torch.LongTensor(y_val), torch.FloatTensor(t_val)), 
                            batch_size=batch_size * 2)

    model = get_hybrid_model(model_size, X_train.shape[1]).to(device)
    
    # Loss con pesos de clase
    criterion_cls = LabelSmoothingCrossEntropy(smoothing=label_smoothing, weights=cw_tensor)
    
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    
    # Scheduler con Warmup
    def lr_lambda(epoch):
        if epoch < warmup_epochs:
            return (epoch + 1) / (warmup_epochs + 1e-6)
        progress = (epoch - warmup_epochs) / (epochs - warmup_epochs)
        return 0.5 * (1 + np.cos(np.pi * progress))
    
    scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    
    # Augmentation
    augment = FeatureAugmentation(noise_std=augment_noise, dropout_prob=augment_dropout)

    best_val_loss = float('inf')
    best_state = None

    for epoch in range(epochs):
        # --- PHASE: TRAINING ---
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for bx, by, bt in train_loader:
            bx, by, bt = bx.to(device), by.to(device), bt.to(device)
            
            # Apply Augmentation
            bx = augment(bx)
            
            optimizer.zero_grad()
            logits, t_pred = model(bx)
            
            l_cls = criterion_cls(logits, by)
            mask = (by != 1).float()
            l_reg = gaussian_nll_loss_clamped(t_pred[:,0:1], t_pred[:,1:2], bt.unsqueeze(1), mask)
            
            loss = l_cls + 0.5 * l_reg
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            train_loss += loss.item()
            # Stats de entrenamiento rápido
            preds = logits.argmax(1)
            train_correct += (preds == by).sum().item()
            train_total += by.size(0)

        scheduler.step()

        # --- PHASE: VALIDATION ---
        model.eval()
        v_loss = 0
        v_correct = 0
        v_total = 0
        v_signal_correct = 0
        v_signal_total = 0
        
        with torch.no_grad():
            for bx, by, bt in val_loader:
                bx, by, bt = bx.to(device), by.to(device), bt.to(device)
                logits, t_pred = model(bx)
                
                # Losses
                l_cls = criterion_cls(logits, by)
                mask = (by != 1).float()
                l_reg = gaussian_nll_loss_clamped(t_pred[:,0:1], t_pred[:,1:2], bt.unsqueeze(1), mask)
                v_loss += (l_cls + 0.5 * l_reg).item()
                
                # Accuracy Stats
                preds = logits.argmax(1)
                v_correct += (preds == by).sum().item()
                v_total += by.size(0)
                
                # Stats específicas para LONG (2) y SHORT (0)
                sig_mask = (by != 1)
                if sig_mask.sum() > 0:
                    v_signal_correct += ((preds == by) & sig_mask).sum().item()
                    v_signal_total += sig_mask.sum().item()
        
        # --- LOGGING ---
        avg_train_loss = train_loss / len(train_loader)
        avg_v_loss = v_loss / len(val_loader)
        val_acc = (v_correct / v_total) * 100
        # Evitar división por cero si una ventana no tiene señales
        sig_acc = (v_signal_correct / v_signal_total * 100) if v_signal_total > 0 else 0.0
        
        if avg_v_loss < best_val_loss:
            best_val_loss = avg_v_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        
        # Print profesional cada época o cada N épocas
        if verbose:
            if epoch % 20 == 0:
                print(f"      Epoch {epoch:2d}/{epochs} | "
                      f"Loss T/V: {avg_train_loss:.3f}/{avg_v_loss:.3f} | "
                      f"Acc: {val_acc:4.1f}% | "
                      f"SigAcc: {sig_acc:4.1f}% | "
                      f"LR: {scheduler.get_last_lr()[0]:.1e} | "
                      f"Signals: {v_signal_total} predicted")

    if best_state: model.load_state_dict(best_state)
    
    # Final Metrics
    model.eval()
    all_p, all_t = [], []
    with torch.no_grad():
        for bx, by, _ in val_loader:
            logits, _ = model(bx.to(device))
            all_p.extend(logits.argmax(1).cpu().numpy())
            all_t.extend(by.numpy())
    
    return model, norm, calculate_trading_metrics(np.array(all_p), np.array(all_t))

# --- MAIN ENGINE ---
def walk_forward_train(data_path, model_path, norm_path, model_size, train_m, test_m, step_m, epochs, batch_size, lr):
    print("=" * 70 + "\nWALK-FORWARD MULTI-TASK TRAINING\n" + "=" * 70)
    df = pd.read_csv(data_path)
    if 'date' in df.columns: df = add_sample_weights(df, decay_days=14) # Freshness para 14 días
    
    splits = walk_forward_splits(df, train_window_months=train_m, test_window_months=test_m, step_months=step_m)
    print(f"[OK] Generated {len(splits)} windows")

    results, best_model, best_norm, best_wr = [], None, None, 0
    
    for i, (tr_df, ts_df) in enumerate(splits):
        print(f"\n--- Window {i+1}/{len(splits)} | Train: {len(tr_df):,} | Test: {len(ts_df):,} ---")
        # Usamos parámetros robustos por defecto
        mod, nr, met = train_single_window(
            tr_df, ts_df, 
            model_size=model_size, 
            epochs=epochs, 
            batch_size=batch_size, 
            learning_rate=lr,
            weight_decay=0.05,
            label_smoothing=0.1,
            augment_noise=0.05,
            augment_dropout=0.1,
            warmup_epochs=max(1, int(epochs * 0.1))
        )
        print(f"      Results: Acc={met['accuracy']:.1%} | WinRate={met['win_rate']:.1%} | PF={met['profit_factor']:.2f}")
        results.append(met)
        if met['win_rate'] > best_wr:
            best_wr, best_model, best_norm = met['win_rate'], mod, nr

    if best_model:
        save_hybrid_model(best_model, best_norm, model_path, norm_path)
        print(f"\n✓ Best model saved to {model_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="training_data/training_data.csv")
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--train-months", type=int, default=0)
    parser.add_argument("--test-months", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=0.001)
    args = parser.parse_args()

    walk_forward_train(args.data, "models/trading_hybrid_wf.pt", "models/hybrid_normalizer_wf.npz",
                       args.model_size, args.train_months, args.test_months, 1, args.epochs, args.batch_size, args.lr)

if __name__ == "__main__": main()