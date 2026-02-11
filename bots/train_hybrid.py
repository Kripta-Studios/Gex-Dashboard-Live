"""
Training Script for Hybrid Attention-MLP Model

Optimized for small trading datasets with anti-overfitting techniques:
- Label smoothing
- Data augmentation (feature noise, dropout)
- Early stopping with patience
- Learning rate warmup + cosine decay
- Heavy weight decay

Model Sizes:
- micro:  ~50K params  - Best for <10K samples
- small:  ~150K params - Best for 10K-50K samples
- medium: ~500K params - Best for 50K-100K samples
- large:  ~1M params   - Best for 100K+ samples

Usage:
    python train_hybrid.py --model-size small --epochs 200 --batch-size 128
"""

import os
import sys
import argparse
import time
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from hybrid_model import (
    get_hybrid_model, get_device, save_hybrid_model,
    FeatureNormalizer, FEATURE_COLUMNS
)


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


# --- LABEL SMOOTHING LOSS ---
class LabelSmoothingCrossEntropy(nn.Module):
    """
    Cross entropy with label smoothing to prevent overconfident predictions.
    Smoothing 0.1 means: 90% on true label, 10% distributed to other labels.
    """
    
    def __init__(self, smoothing: float = 0.1, num_classes: int = 3):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes
    
    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        confidence = 1.0 - self.smoothing
        smooth_value = self.smoothing / (self.num_classes - 1)
        
        # Create smoothed labels
        one_hot = torch.zeros_like(logits).scatter_(1, targets.unsqueeze(1), 1)
        smooth_labels = one_hot * confidence + (1 - one_hot) * smooth_value
        
        # Compute cross entropy with soft labels
        log_probs = torch.log_softmax(logits, dim=-1)
        loss = (-smooth_labels * log_probs).sum(dim=-1).mean()
        
        return loss


# --- TRAINING UTILITIES ---
def prepare_data(df, feature_columns: list = FEATURE_COLUMNS):
    """Prepare DataFrame for training."""
    available_cols = [c for c in feature_columns if c in df.columns]
    features = df[available_cols].values.astype(np.float32)
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)
    targets = (df['target'].values + 1).astype(np.int64)  # -1,0,1 -> 0,1,2
    
    # Time targets (normalize 0-30 min to 0-1)
    if 'time_to_target' in df.columns:
        time_targets = df['time_to_target'].values.astype(np.float32) / 30.0
        time_targets = np.clip(time_targets, 0.0, 1.0)
    else:
        print("⚠ 'time_to_target' column missing, using zeros")
        time_targets = np.zeros(len(targets), dtype=np.float32)
    
    normalizer = FeatureNormalizer()
    features_norm = normalizer.fit_transform(features, available_cols)
    
    return features_norm, targets, time_targets, normalizer


def split_data(features: np.ndarray, targets: np.ndarray, time_targets: np.ndarray,
               val_split: float = 0.2, shuffle: bool = True):
    """Split data into train/val sets."""
    n_samples = len(features)
    indices = np.arange(n_samples)
    
    if shuffle:
        np.random.shuffle(indices)
    
    val_size = int(n_samples * val_split)
    val_indices = indices[:val_size]
    train_indices = indices[val_size:]
    
    return (
        features[train_indices], targets[train_indices], time_targets[train_indices],
        features[val_indices], targets[val_indices], time_targets[val_indices]
    )


def get_class_weights(targets: np.ndarray) -> torch.Tensor:
    """Compute class weights for imbalanced data."""
    class_counts = np.bincount(targets, minlength=3)
    total = len(targets)
    weights = total / (3 * class_counts + 1e-6)
    return torch.FloatTensor(weights)


# --- MAIN TRAINING FUNCTION ---
def train(
    data_path: str,
    model_path: str = "models/trading_hybrid.pt",
    normalizer_path: str = "models/hybrid_normalizer.npz",
    model_size: str = "small",
    epochs: int = 200,
    batch_size: int = 128,
    learning_rate: float = 0.001,
    val_split: float = 0.2,
    early_stopping_patience: int = 25,
    weight_decay: float = 0.05,
    label_smoothing: float = 0.1,
    augment_noise: float = 0.05,
    augment_dropout: float = 0.1,
    warmup_epochs: int = 10,
):
    """Main training function with anti-overfitting techniques."""
    
    print("=" * 70)
    print("HYBRID MULTI-TASK TRAINING (Class + Time)")
    print("=" * 70)
    
    device = get_device()
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    # Load data
    print(f"\n[1/6] Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"    Loaded {len(df):,} samples")
    
    # Prepare features
    print("\n[2/6] Preparing features...")
    features, targets, time_targets, normalizer = prepare_data(df, FEATURE_COLUMNS)
    print(f"    Features shape: {features.shape}")
    
    # Class distribution
    class_counts = np.bincount(targets, minlength=3)
    print(f"    Classes: SHORT={class_counts[0]}, HOLD={class_counts[1]}, LONG={class_counts[2]}")
    
    # Recommend model size based on data
    recommended = "micro" if len(df) < 10000 else "small" if len(df) < 50000 else "medium"
    if model_size != recommended:
        print(f"    ⚠ Recommendation: '{recommended}' model for {len(df):,} samples")
    
    # Split data
    print("\n[3/6] Splitting data...")
    X_train, y_train, t_train, X_val, y_val, t_val = split_data(features, targets, time_targets, val_split)
    print(f"    Training: {len(X_train):,} | Validation: {len(X_val):,}")
    
    # DataLoaders
    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train), torch.FloatTensor(t_train))
    val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.LongTensor(y_val), torch.FloatTensor(t_val))
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size * 2)
    
    # Initialize model
    print(f"\n[4/6] Initializing {model_size.upper()} Hybrid model...")
    input_size = features.shape[1]
    model = get_hybrid_model(model_size, input_size)
    model.to(device)
    
    total_params = sum(p.numel() for p in model.parameters())
    params_per_sample = total_params / len(X_train)
    
    print(f"    Parameters: {total_params:,} ({total_params/1e3:.0f}K)")
    print(f"    Params/sample ratio: {params_per_sample:.2f}")
    
    if params_per_sample > 10:
        print(f"    ⚠ HIGH OVERFITTING RISK! Ratio should be < 10")
    
    # Loss function with label smoothing
    cls_criterion = LabelSmoothingCrossEntropy(smoothing=label_smoothing, num_classes=3)
    reg_criterion = nn.MSELoss(reduction='none') # We'll apply mask efficiently
    
    # Class weights for imbalanced data
    class_weights = get_class_weights(y_train).to(device)
    
    # Optimizer with weight decay
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    
    # LR scheduler: warmup + cosine decay
    def lr_lambda(epoch):
        if epoch < warmup_epochs:
            return (epoch + 1) / warmup_epochs
        progress = (epoch - warmup_epochs) / (epochs - warmup_epochs)
        return 0.5 * (1 + np.cos(np.pi * progress))
    
    scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    
    # Data augmentation
    augment = FeatureAugmentation(noise_std=augment_noise, dropout_prob=augment_dropout)
    
    print(f"\n[5/6] Training configuration:")
    print(f"    Epochs: {epochs}")
    print(f"    Batch size: {batch_size}")
    print(f"    Learning rate: {learning_rate}")
    print(f"    Weight decay: {weight_decay}")
    print(f"    Label smoothing: {label_smoothing}")
    print(f"    Augmentation: noise={augment_noise}, dropout={augment_dropout}")
    print(f"    Early stopping: {early_stopping_patience} epochs")
    
    # Training loop
    print("\n[6/6] Training...")
    print("-" * 70)
    
    best_val_loss = float('inf')
    best_val_acc = 0.0
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "val_acc": [], "val_mae": []}
    
    start_time = time.time()
    
    for epoch in range(epochs):
        epoch_start = time.time()
        
        # Training phase
        model.train()
        train_loss = 0.0
        train_cls_loss = 0.0
        train_reg_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for batch_x, batch_y, batch_t in train_loader:
            batch_x, batch_y, batch_t = batch_x.to(device), batch_y.to(device), batch_t.to(device)
            
            # Apply augmentation during training
            batch_x = augment(batch_x)
            
            optimizer.zero_grad()
            logits, time_pred = model(batch_x)
            
            # Classification Loss
            loss_cls = cls_criterion(logits, batch_y)
            
            # Regression Loss (only for signals, not HOLD)
            # HOLD is class 1 (derived from -1, 0, 1 -> 0, 1, 2)
            # wait, original targets are -1 (SHORT), 0 (HOLD), 1 (LONG)
            # mapped to 0, 1, 2. So HOLD is 1.
            loss_reg = reg_criterion(time_pred.squeeze(), batch_t)
            
            # Mask: 1 for SHORT/LONG, 0 for HOLD
            mask = (batch_y != 1).float()
            
            # Weighted sum of losses
            # If no signals in batch, reg_loss is 0
            if mask.sum() > 0:
                masked_reg_loss = (loss_reg * mask).sum() / mask.sum()
            else:
                masked_reg_loss = torch.tensor(0.0, device=device)
            
            # Combined loss (alpha=0.5 for regression)
            loss = loss_cls + 0.5 * masked_reg_loss
            
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            train_loss += loss.item()
            train_cls_loss += loss_cls.item()
            train_reg_loss += masked_reg_loss.item()
            
            _, predicted = logits.max(1)
            train_total += batch_y.size(0)
            train_correct += predicted.eq(batch_y).sum().item()
        
        scheduler.step()
        avg_train_loss = train_loss / len(train_loader)
        avg_train_cls = train_cls_loss / len(train_loader)
        avg_train_reg = train_reg_loss / len(train_loader)
        train_acc = train_correct / train_total
        
        # Validation phase (no augmentation)
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        val_mae_sum = 0.0
        val_signal_count = 0
        
        with torch.no_grad():
            for batch_x, batch_y, batch_t in val_loader:
                batch_x, batch_y, batch_t = batch_x.to(device), batch_y.to(device), batch_t.to(device)
                
                logits, time_pred = model(batch_x)
                
                # Losses
                loss_cls = cls_criterion(logits, batch_y)
                loss_reg = reg_criterion(time_pred.squeeze(), batch_t)
                mask = (batch_y != 1).float()
                
                if mask.sum() > 0:
                    masked_reg_loss = (loss_reg * mask).sum() / mask.sum()
                    # MAE for signals (in minutes: pred * 30 - target * 30)
                    abs_err = torch.abs(time_pred.squeeze() - batch_t) * 30.0
                    val_mae_sum += (abs_err * mask).sum().item()
                    val_signal_count += mask.sum().item()
                else:
                    masked_reg_loss = torch.tensor(0.0, device=device)
                
                loss = loss_cls + 0.5 * masked_reg_loss
                val_loss += loss.item()
                
                _, predicted = logits.max(1)
                val_total += batch_y.size(0)
                val_correct += predicted.eq(batch_y).sum().item()
        
        avg_val_loss = val_loss / len(val_loader)
        val_acc = val_correct / val_total
        val_mae = val_mae_sum / val_signal_count if val_signal_count > 0 else 0.0
        
        # Record history
        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        history["val_acc"].append(val_acc)
        history["val_mae"].append(val_mae)
        
        epoch_time = time.time() - epoch_start
        
        # Print progress
        if (epoch + 1) % 10 == 0 or epoch == 0:
            current_lr = optimizer.param_groups[0]['lr']
            gap = avg_val_loss - avg_train_loss
            print(f"Epoch {epoch+1:3d}/{epochs} | "
                  f"Loss: {avg_train_loss:.4f}/{avg_val_loss:.4f} | "
                  f"Acc: {val_acc:.1%} | "
                  f"Time MAE: {val_mae:.1f}m | "
                  f"LR: {current_lr:.2e}")
        
        # Early stopping
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_val_acc = val_acc
            patience_counter = 0
            save_hybrid_model(model, normalizer, model_path, normalizer_path)
        else:
            patience_counter += 1
            if patience_counter >= early_stopping_patience:
                print(f"\n⚠ Early stopping at epoch {epoch+1}")
                break
    
    total_time = time.time() - start_time
    
    print("-" * 70)
    print(f"\n✓ Training complete in {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"Best validation loss: {best_val_loss:.4f}")
    print(f"Best validation accuracy: {best_val_acc:.1%}")
    print(f"Final Time MAE: {history['val_mae'][-1]:.1f} min")
    
    # Overfitting analysis
    final_gap = history["val_loss"][-1] - history["train_loss"][-1]
    if final_gap > 0.1:
        print(f"\n⚠ OVERFITTING DETECTED! Train-Val gap: {final_gap:.3f}")
        print("  Suggestions:")
        print("  - Use smaller model size (--model-size micro)")
        print("  - Increase weight decay (--weight-decay 0.1)")
        print("  - Increase augmentation (--augment-noise 0.1)")
    else:
        print(f"\n✓ Good generalization (gap: {final_gap:.3f})")
    
    # Final evaluation
    print("\n" + "=" * 70)
    print("FINAL EVALUATION")
    print("=" * 70)
    
    model.eval()
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for batch_x, batch_y, batch_t in val_loader:
            batch_x = batch_x.to(device)
            logits, _ = model(batch_x)
            _, predicted = logits.max(1)
            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(batch_y.numpy())
    
    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)
    
    print(f"\nAccuracy: {(all_preds == all_targets).mean():.1%}")
    
    print(f"\nPer-class accuracy:")
    for cls, name in enumerate(["SHORT", "HOLD", "LONG"]):
        mask = all_targets == cls
        if mask.sum() > 0:
            acc = (all_preds[mask] == cls).mean()
            print(f"  {name}: {acc:.1%} ({mask.sum()} samples)")
    
    return {"best_val_loss": best_val_loss, "best_val_acc": best_val_acc, "history": history}


def main():
    parser = argparse.ArgumentParser(description="Train Hybrid Attention-MLP model")
    parser.add_argument("--data", default="training_data/training_data.csv")
    parser.add_argument("--model", default="models/trading_hybrid.pt")
    parser.add_argument("--normalizer", default="models/hybrid_normalizer.npz")
    parser.add_argument("--model-size", choices=["micro", "small", "medium", "large"],
                        default="small", help="Model size")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--weight-decay", type=float, default=0.05)
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--augment-noise", type=float, default=0.05)
    parser.add_argument("--augment-dropout", type=float, default=0.1)
    parser.add_argument("--warmup", type=int, default=10)
    
    args = parser.parse_args()
    
    # Resolve paths
    if not os.path.isabs(args.data):
        args.data = os.path.join(PROJECT_ROOT, args.data)
    if not os.path.isabs(args.model):
        args.model = os.path.join(PROJECT_ROOT, args.model)
    if not os.path.isabs(args.normalizer):
        args.normalizer = os.path.join(PROJECT_ROOT, args.normalizer)
    
    if not os.path.exists(args.data):
        print(f"ERROR: Data file not found: {args.data}")
        print("\nRun collect_training_data.py first")
        sys.exit(1)
    
    train(
        data_path=args.data,
        model_path=args.model,
        normalizer_path=args.normalizer,
        model_size=args.model_size,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        val_split=args.val_split,
        early_stopping_patience=args.patience,
        weight_decay=args.weight_decay,
        label_smoothing=args.label_smoothing,
        augment_noise=args.augment_noise,
        augment_dropout=args.augment_dropout,
        warmup_epochs=args.warmup,
    )


if __name__ == "__main__":
    main()
