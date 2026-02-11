"""
Walk-Forward Training for Hybrid Model

Implements temporal validation that prevents lookahead bias:
- Train on older data, validate on newer data
- Multiple walk-forward windows for robust evaluation
- Trading-specific metrics (not just accuracy)
- Sample weighting by freshness

Usage:
    python train_walkforward.py --data training_data.csv --windows 5
"""

import os
import sys
import argparse
import time
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

from hybrid_model import (
    get_hybrid_model, get_device, save_hybrid_model,
    FeatureNormalizer, FEATURE_COLUMNS
)
from data_utils import (
    temporal_train_val_test_split,
    walk_forward_splits,
    balance_classes_weighted,
    add_sample_weights,
)


# =============================================================================
# TRADING METRICS
# =============================================================================

def calculate_trading_metrics(
    predictions: np.ndarray, 
    targets: np.ndarray,
    prices: np.ndarray = None
) -> dict:
    """
    Calculate metrics that matter for trading, not just accuracy.
    
    Metrics:
    - Per-class precision (especially LONG/SHORT)
    - Win rate on actual trades (excluding HOLD)
    - Simulated profit factor
    - Edge per trade
    """
    metrics = {}
    
    # Overall accuracy
    metrics["accuracy"] = (predictions == targets).mean()
    
    # Per-class precision
    class_names = ["SHORT", "HOLD", "LONG"]
    for cls_idx, cls_name in enumerate(class_names):
        pred_mask = predictions == cls_idx
        if pred_mask.sum() > 0:
            correct = (targets[pred_mask] == cls_idx).sum()
            precision = correct / pred_mask.sum()
            recall_mask = targets == cls_idx
            recall = (predictions[recall_mask] == cls_idx).sum() / recall_mask.sum() if recall_mask.sum() > 0 else 0
            
            metrics[f"precision_{cls_name}"] = float(precision)
            metrics[f"recall_{cls_name}"] = float(recall)
            metrics[f"count_{cls_name}"] = int(pred_mask.sum())
    
    # Trading-specific: only count actual trades (not HOLD predictions)
    trade_mask = predictions != 1  # Not HOLD
    if trade_mask.sum() > 0:
        trade_preds = predictions[trade_mask]
        trade_targets = targets[trade_mask]
        
        # Win = predicted correctly
        wins = (trade_preds == trade_targets).sum()
        losses = trade_mask.sum() - wins
        
        metrics["trade_count"] = int(trade_mask.sum())
        metrics["win_rate"] = float(wins / trade_mask.sum()) if trade_mask.sum() > 0 else 0
        
        # Profit factor (wins / losses)
        if losses > 0:
            metrics["profit_factor"] = float(wins / losses)
        else:
            metrics["profit_factor"] = float('inf') if wins > 0 else 0
    else:
        metrics["trade_count"] = 0
        metrics["win_rate"] = 0
        metrics["profit_factor"] = 0
    
    # Edge per trade (expected value)
    # Assuming equal position sizing and symmetric payoffs
    if metrics.get("win_rate", 0) > 0:
        # E[V] = win_rate * avg_win - (1-win_rate) * avg_loss
        # With symmetric payoffs: E[V] = 2*win_rate - 1
        metrics["edge_per_trade"] = 2 * metrics["win_rate"] - 1
    else:
        metrics["edge_per_trade"] = 0
    
    return metrics


def calculate_pnl_metrics(
    predictions: np.ndarray,
    targets: np.ndarray,
    price_changes: np.ndarray
) -> dict:
    """
    Calculate actual P&L if we followed the model's predictions.
    
    Args:
        predictions: Model predictions (0=SHORT, 1=HOLD, 2=LONG)
        targets: Actual labels
        price_changes: Actual price change percentages
    """
    metrics = {}
    
    # Convert to positions: LONG=+1, SHORT=-1, HOLD=0
    positions = np.zeros_like(predictions, dtype=float)
    positions[predictions == 2] = 1.0   # LONG
    positions[predictions == 0] = -1.0  # SHORT
    
    # P&L = position * price_change
    pnl_per_trade = positions * price_changes
    
    # Total P&L
    metrics["total_pnl_pct"] = float(pnl_per_trade.sum())
    metrics["avg_pnl_per_trade"] = float(pnl_per_trade[positions != 0].mean()) if (positions != 0).sum() > 0 else 0
    
    # Separate wins and losses
    wins = pnl_per_trade[pnl_per_trade > 0]
    losses = pnl_per_trade[pnl_per_trade < 0]
    
    metrics["gross_profit"] = float(wins.sum()) if len(wins) > 0 else 0
    metrics["gross_loss"] = float(losses.sum()) if len(losses) > 0 else 0
    
    if metrics["gross_loss"] != 0:
        metrics["pnl_profit_factor"] = abs(metrics["gross_profit"] / metrics["gross_loss"])
    else:
        metrics["pnl_profit_factor"] = float('inf') if metrics["gross_profit"] > 0 else 0
    
    # Max drawdown (cumulative P&L)
    cumulative_pnl = np.cumsum(pnl_per_trade)
    running_max = np.maximum.accumulate(cumulative_pnl)
    drawdown = running_max - cumulative_pnl
    metrics["max_drawdown_pct"] = float(drawdown.max())
    
    return metrics


# =============================================================================
# LABEL SMOOTHING LOSS
# =============================================================================

class LabelSmoothingCrossEntropy(nn.Module):
    """Cross entropy with label smoothing."""
    
    def __init__(self, smoothing: float = 0.1, num_classes: int = 3):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes
    
    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        confidence = 1.0 - self.smoothing
        smooth_value = self.smoothing / (self.num_classes - 1)
        
        one_hot = torch.zeros_like(logits).scatter_(1, targets.unsqueeze(1), 1)
        smooth_labels = one_hot * confidence + (1 - one_hot) * smooth_value
        
        log_probs = torch.log_softmax(logits, dim=-1)
        loss = (-smooth_labels * log_probs).sum(dim=-1).mean()
        
        return loss


# =============================================================================
# WALK-FORWARD TRAINING
# =============================================================================

def train_single_window(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    model_size: str = "small",
    epochs: int = 100,
    batch_size: int = 128,
    learning_rate: float = 0.001,
    weight_decay: float = 0.05,
    label_smoothing: float = 0.1,
    device: torch.device = None,
    verbose: bool = True
) -> tuple:
    """
    Train model on a single walk-forward window.
    
    Returns:
        (trained_model, normalizer, val_metrics, history)
    """
    if device is None:
        device = get_device()
    
    # Prepare features
    available_cols = [c for c in FEATURE_COLUMNS if c in train_df.columns]
    
    X_train = train_df[available_cols].values.astype(np.float32)
    y_train = (train_df['target'].values + 1).astype(np.int64)  # -1,0,1 -> 0,1,2
    
    X_val = val_df[available_cols].values.astype(np.float32)
    y_val = (val_df['target'].values + 1).astype(np.int64)
    
    # Handle NaN/Inf
    X_train = np.nan_to_num(X_train, nan=0.0, posinf=5.0, neginf=-5.0)
    X_val = np.nan_to_num(X_val, nan=0.0, posinf=5.0, neginf=-5.0)
    
    # Normalize
    normalizer = FeatureNormalizer()
    X_train_norm = normalizer.fit_transform(X_train, available_cols)
    X_val_norm = normalizer.transform(X_val)
    
    # Get sample weights if available
    if 'sample_weight' in train_df.columns:
        sample_weights = train_df['sample_weight'].values
    else:
        sample_weights = np.ones(len(train_df))
    
    # Class weights for imbalanced data
    class_weights = balance_classes_weighted(train_df)
    class_weight_tensor = torch.FloatTensor([
        class_weights.get(0, 1.0),  # SHORT
        class_weights.get(1, 1.0),  # HOLD
        class_weights.get(2, 1.0),  # LONG
    ]).to(device)
    
    # Create weighted sampler
    sample_class_weights = np.array([class_weights[y] for y in (train_df['target'].values + 1)])
    combined_weights = sample_weights * sample_class_weights
    sampler = WeightedRandomSampler(
        weights=torch.FloatTensor(combined_weights),
        num_samples=len(combined_weights),
        replacement=True
    )
    
    # DataLoaders
    train_dataset = TensorDataset(
        torch.FloatTensor(X_train_norm),
        torch.LongTensor(y_train)
    )
    val_dataset = TensorDataset(
        torch.FloatTensor(X_val_norm),
        torch.LongTensor(y_val)
    )
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler)
    val_loader = DataLoader(val_dataset, batch_size=batch_size * 2)
    
    # Initialize model
    input_size = X_train_norm.shape[1]
    model = get_hybrid_model(model_size, input_size)
    model.to(device)
    
    # Loss and optimizer
    criterion = LabelSmoothingCrossEntropy(smoothing=label_smoothing)
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    
    # LR scheduler
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    # Training loop
    best_val_loss = float('inf')
    best_model_state = None
    history = {"train_loss": [], "val_loss": [], "val_acc": []}
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0.0
        
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            train_loss += loss.item()
        
        scheduler.step()
        avg_train_loss = train_loss / len(train_loader)
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_preds = []
        val_targets = []
        
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                
                val_loss += loss.item()
                val_preds.extend(outputs.argmax(dim=1).cpu().numpy())
                val_targets.extend(batch_y.cpu().numpy())
        
        avg_val_loss = val_loss / len(val_loader)
        val_acc = (np.array(val_preds) == np.array(val_targets)).mean()
        
        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        history["val_acc"].append(val_acc)
        
        # Save best
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        
        if verbose and (epoch + 1) % 20 == 0:
            print(f"    Epoch {epoch+1}/{epochs} | "
                  f"Train: {avg_train_loss:.4f} | Val: {avg_val_loss:.4f} | Acc: {val_acc:.1%}")
    
    # Load best model
    if best_model_state:
        model.load_state_dict(best_model_state)
        model.to(device)
    
    # Calculate final validation metrics
    model.eval()
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for batch_x, batch_y in val_loader:
            batch_x = batch_x.to(device)
            outputs = model(batch_x)
            all_preds.extend(outputs.argmax(dim=1).cpu().numpy())
            all_targets.extend(batch_y.numpy())
    
    val_metrics = calculate_trading_metrics(np.array(all_preds), np.array(all_targets))
    
    return model, normalizer, val_metrics, history


def walk_forward_train(
    data_path: str,
    model_path: str = "models/trading_hybrid_wf.pt",
    normalizer_path: str = "models/hybrid_normalizer_wf.npz",
    model_size: str = "small",
    train_months: int = 3,
    test_months: int = 1,
    step_months: int = 1,
    epochs_per_window: int = 100,
    batch_size: int = 128,
    learning_rate: float = 0.001,
):
    """
    Full walk-forward training with multiple windows.
    """
    print("=" * 70)
    print("WALK-FORWARD TRAINING")
    print("=" * 70)
    
    device = get_device()
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    # Load data
    print(f"\n[1/4] Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    
    # Add sample weights
    if 'date' in df.columns:
        df = add_sample_weights(df, decay_days=90)
    
    print(f"    Loaded {len(df):,} samples")
    print(f"    Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Generate walk-forward windows
    print(f"\n[2/4] Generating walk-forward windows...")
    print(f"    Train: {train_months} months | Test: {test_months} month | Step: {step_months} month")
    
    splits = walk_forward_splits(
        df, 
        date_col='date',
        train_window_months=train_months,
        test_window_months=test_months,
        step_months=step_months
    )
    
    print(f"    Generated {len(splits)} windows")
    
    if len(splits) == 0:
        print("ERROR: No walk-forward windows could be generated. Need more data.")
        return None
    
    # Train each window
    print(f"\n[3/4] Training {len(splits)} windows...")
    
    all_window_metrics = []
    all_predictions = []
    all_targets = []
    best_model = None
    best_normalizer = None
    best_win_rate = 0
    
    for i, (train_df, test_df) in enumerate(splits):
        print(f"\n  --- Window {i+1}/{len(splits)} ---")
        print(f"      Train: {len(train_df):,} samples | Test: {len(test_df):,} samples")
        
        model, normalizer, metrics, history = train_single_window(
            train_df=train_df,
            val_df=test_df,
            model_size=model_size,
            epochs=epochs_per_window,
            batch_size=batch_size,
            learning_rate=learning_rate,
            device=device,
            verbose=True
        )
        
        print(f"      Results: Acc={metrics['accuracy']:.1%} | "
              f"Win Rate={metrics['win_rate']:.1%} | "
              f"PF={metrics['profit_factor']:.2f}")
        
        all_window_metrics.append(metrics)
        
        # Collect predictions for aggregate metrics
        available_cols = [c for c in FEATURE_COLUMNS if c in test_df.columns]
        X_test = test_df[available_cols].values.astype(np.float32)
        X_test = np.nan_to_num(X_test, nan=0.0, posinf=5.0, neginf=-5.0)
        X_test_norm = normalizer.transform(X_test)
        
        model.eval()
        with torch.no_grad():
            x = torch.FloatTensor(X_test_norm).to(device)
            preds = model(x).argmax(dim=1).cpu().numpy()
        
        all_predictions.extend(preds)
        all_targets.extend((test_df['target'].values + 1).astype(np.int64))
        
        # Keep best model
        if metrics['win_rate'] > best_win_rate:
            best_win_rate = metrics['win_rate']
            best_model = model
            best_normalizer = normalizer
    
    # Aggregate results
    print(f"\n[4/4] Aggregate Results Across All Windows...")
    print("-" * 50)
    
    all_predictions = np.array(all_predictions)
    all_targets = np.array(all_targets)
    aggregate_metrics = calculate_trading_metrics(all_predictions, all_targets)
    
    print(f"  Overall Accuracy:     {aggregate_metrics['accuracy']:.1%}")
    print(f"  Trade Win Rate:       {aggregate_metrics['win_rate']:.1%}")
    print(f"  Profit Factor:        {aggregate_metrics['profit_factor']:.2f}")
    print(f"  Edge per Trade:       {aggregate_metrics['edge_per_trade']:.2%}")
    print(f"  Total Trades:         {aggregate_metrics['trade_count']}")
    
    print(f"\n  Per-Class Precision:")
    for cls in ["SHORT", "HOLD", "LONG"]:
        prec = aggregate_metrics.get(f"precision_{cls}", 0)
        recall = aggregate_metrics.get(f"recall_{cls}", 0)
        count = aggregate_metrics.get(f"count_{cls}", 0)
        print(f"    {cls}: P={prec:.1%} R={recall:.1%} (n={count})")
    
    # Profitability assessment
    print("\n" + "=" * 50)
    if aggregate_metrics['win_rate'] > 0.52 and aggregate_metrics['profit_factor'] > 1.0:
        print("✓ MODEL SHOWS POTENTIAL EDGE")
        print(f"  Expected edge: {aggregate_metrics['edge_per_trade']:.2%} per trade")
    elif aggregate_metrics['win_rate'] > 0.50:
        print("⚠ MARGINAL EDGE - May not cover transaction costs")
    else:
        print("✗ NO EDGE DETECTED - Model is not profitable")
    print("=" * 50)
    
    # Save best model
    if best_model is not None:
        save_hybrid_model(best_model, best_normalizer, model_path, normalizer_path)
        print(f"\n✓ Best model saved to {model_path}")
    
    # Save metrics
    metrics_path = model_path.replace('.pt', '_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump({
            "aggregate": aggregate_metrics,
            "per_window": all_window_metrics,
        }, f, indent=2, default=float)
    print(f"✓ Metrics saved to {metrics_path}")
    
    return aggregate_metrics


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Training for Hybrid Model")
    parser.add_argument("--data", default="training_data/training_data.csv")
    parser.add_argument("--model", default="models/trading_hybrid_wf.pt")
    parser.add_argument("--normalizer", default="models/hybrid_normalizer_wf.npz")
    parser.add_argument("--model-size", choices=["micro", "small", "medium", "large"],
                        default="small")
    parser.add_argument("--train-months", type=int, default=3)
    parser.add_argument("--test-months", type=int, default=1)
    parser.add_argument("--step-months", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.001)
    
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
    
    walk_forward_train(
        data_path=args.data,
        model_path=args.model,
        normalizer_path=args.normalizer,
        model_size=args.model_size,
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
        epochs_per_window=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )


if __name__ == "__main__":
    main()
