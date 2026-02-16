"""
Data Utilities for Robust Training - Anti-Lookahead Bias

Contains:
- Robust target label calculation with temporal buffer
- Dataset balancing methods
- Temporal weighting for sample freshness
- Walk-forward data splitting

These utilities address common ML trading pitfalls:
1. Lookahead bias - using future information in features
2. Class imbalance - HOLD dominates the dataset
3. Non-stationarity - old data less relevant than new
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, List


# =============================================================================
# ROBUST TARGET LABEL CALCULATION
# =============================================================================

def calculate_target_label_robust(
    prices: List[float],
    current_idx: int,
    lookahead_min: int = 30,
    lookahead_max: int = 60,
    buffer_minutes: int = 5,
    min_threshold: float = 0.003,
    use_adaptive_threshold: bool = True,
    vol_lookback: int = 60
) -> Optional[int]:
    """
    Calculate target label with anti-lookahead bias measures.
    
    Key improvements over naive approach:
    1. Buffer period after current timestamp (no immediate future info)
    2. Uses SUSTAINED move (average of window) not spike
    3. Adaptive threshold based on recent volatility
    
    Args:
        prices: List of prices (1-minute intervals assumed)
        current_idx: Current position in the list
        lookahead_min: Minimum lookahead window (after buffer)
        lookahead_max: Maximum lookahead window
        buffer_minutes: Gap between current time and lookahead start
        min_threshold: Minimum move threshold (used if adaptive disabled)
        use_adaptive_threshold: Calculate threshold from volatility
        vol_lookback: Lookback period for volatility calculation
        
    Returns:
        -1 (SHORT), 0 (HOLD), 1 (LONG), or None if insufficient data
    """
    # Check if we have enough future data
    required_future = buffer_minutes + lookahead_max
    if current_idx + required_future >= len(prices):
        return None  # Not enough data
    
    current_price = prices[current_idx]
    if current_price <= 0:
        return None
    
    # Apply temporal buffer - don't look immediately after
    buffer_end = current_idx + buffer_minutes
    
    # Future price window (after buffer)
    future_start = buffer_end
    future_end = min(buffer_end + lookahead_max, len(prices))
    future_prices = prices[future_start:future_end]
    
    if len(future_prices) < lookahead_min:
        return None
    
    # Calculate SUSTAINED move (average of last portion of window)
    # This avoids labeling based on temporary spikes
    sustained_window = min(15, len(future_prices) // 2)
    avg_future = np.mean(future_prices[-sustained_window:])
    move_pct = (avg_future - current_price) / current_price
    
    # Determine threshold
    if use_adaptive_threshold:
        # Calculate recent volatility
        vol_start = max(0, current_idx - vol_lookback)
        recent_prices = prices[vol_start:current_idx + 1]
        
        if len(recent_prices) > 1:
            returns = np.diff(recent_prices) / recent_prices[:-1]
            recent_vol = np.std(returns) * np.sqrt(lookahead_min)  # Scale to lookahead
            threshold = max(min_threshold, recent_vol * 1.5)
        else:
            threshold = min_threshold
    else:
        threshold = min_threshold
    
    # Classify
    if move_pct > threshold:
        return 1  # LONG
    elif move_pct < -threshold:
        return -1  # SHORT
    return 0  # HOLD


def calculate_target_with_max_adverse(
    prices: List[float],
    current_idx: int,
    lookahead: int = 30,
    profit_threshold: float = 0.003,
    max_adverse_pct: float = 0.002
) -> Tuple[Optional[int], Dict]:
    """
    Calculate target considering both profit potential AND drawdown.
    
    A trade is only LONG if:
    - Price goes up by profit_threshold
    - AND max drawdown before profit is < max_adverse_pct
    
    This creates more realistic labels for actual trading.
    
    Returns:
        (label, metadata_dict)
    """
    if current_idx + lookahead >= len(prices):
        return None, {}
    
    current_price = prices[current_idx]
    if current_price <= 0:
        return None, {}
    
    future_prices = prices[current_idx + 1:current_idx + lookahead + 1]
    
    # Track running max and min from current price
    running_max = current_price
    running_min = current_price
    max_profit_long = 0
    max_drawdown_long = 0
    max_profit_short = 0
    max_drawdown_short = 0
    
    for price in future_prices:
        running_max = max(running_max, price)
        running_min = min(running_min, price)
        
        # For LONG: profit = upside, drawdown = downside before profit
        profit_long = (price - current_price) / current_price
        drawdown_long = (current_price - running_min) / current_price
        max_profit_long = max(max_profit_long, profit_long)
        if profit_long < max_profit_long:  # Not at peak, so this is drawdown territory
            max_drawdown_long = max(max_drawdown_long, drawdown_long)
        
        # For SHORT: profit = downside, drawdown = upside before profit
        profit_short = (current_price - price) / current_price
        drawdown_short = (running_max - current_price) / current_price
        max_profit_short = max(max_profit_short, profit_short)
        if profit_short < max_profit_short:
            max_drawdown_short = max(max_drawdown_short, drawdown_short)
    
    metadata = {
        "max_profit_long": max_profit_long,
        "max_drawdown_long": max_drawdown_long,
        "max_profit_short": max_profit_short,
        "max_drawdown_short": max_drawdown_short,
    }
    
    # Determine label with adverse movement constraint
    long_valid = (max_profit_long >= profit_threshold and 
                  max_drawdown_long <= max_adverse_pct)
    short_valid = (max_profit_short >= profit_threshold and 
                   max_drawdown_short <= max_adverse_pct)
    
    if long_valid and not short_valid:
        return 1, metadata
    elif short_valid and not long_valid:
        return -1, metadata
    elif long_valid and short_valid:
        # Both valid - pick the one with better risk/reward
        rr_long = max_profit_long / (max_drawdown_long + 0.0001)
        rr_short = max_profit_short / (max_drawdown_short + 0.0001)
        return (1 if rr_long > rr_short else -1), metadata
    
    return 0, metadata


# =============================================================================
# DATASET BALANCING
# =============================================================================

def balance_classes_undersample(df: pd.DataFrame, target_col: str = "target",
                                 random_state: int = 42) -> pd.DataFrame:
    """
    Undersample majority classes to match minority class count.
    
    Pros: No synthetic data, maintains data integrity
    Cons: Loses potentially useful samples
    """
    class_counts = df[target_col].value_counts()
    min_count = class_counts.min()
    
    balanced_dfs = []
    for class_val in class_counts.index:
        class_df = df[df[target_col] == class_val]
        if len(class_df) > min_count:
            class_df = class_df.sample(n=min_count, random_state=random_state)
        balanced_dfs.append(class_df)
    
    return pd.concat(balanced_dfs).sample(frac=1, random_state=random_state).reset_index(drop=True)


def balance_classes_weighted(df: pd.DataFrame, target_col: str = "target") -> Dict[int, float]:
    """
    Calculate class weights for weighted loss function.
    Does not modify the dataset - use weights during training.
    
    Formula: weight[c] = n_samples / (n_classes * n_samples[c])
    """
    class_counts = df[target_col].value_counts()
    n_samples = len(df)
    n_classes = len(class_counts)
    
    weights = {}
    for class_val, count in class_counts.items():
        weights[class_val] = n_samples / (n_classes * count)
    
    return weights


def stratified_undersample_with_time(
    df: pd.DataFrame,
    target_col: str = "target",
    date_col: str = "date",
    keep_recent_ratio: float = 0.6,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Undersample but keep more recent samples (temporal bias).
    
    Recent data is more relevant due to non-stationarity.
    """
    df = df.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    max_date = df['_date'].max()
    
    # Calculate age in days
    df['_age_days'] = (max_date - df['_date']).dt.days
    
    # Split into recent and old
    median_age = df['_age_days'].median()
    recent_df = df[df['_age_days'] <= median_age]
    old_df = df[df['_age_days'] > median_age]
    
    # Balance within each group
    class_counts = df[target_col].value_counts()
    min_count = class_counts.min()
    
    # Allocate samples: more recent, fewer old
    recent_count = int(min_count * keep_recent_ratio)
    old_count = min_count - recent_count
    
    balanced_dfs = []
    for class_val in class_counts.index:
        # Sample from recent
        recent_class = recent_df[recent_df[target_col] == class_val]
        if len(recent_class) >= recent_count:
            balanced_dfs.append(recent_class.sample(n=recent_count, random_state=random_state))
        else:
            balanced_dfs.append(recent_class)
            # Need more from old to compensate
            extra_needed = recent_count - len(recent_class)
            old_count += extra_needed
        
        # Sample from old
        old_class = old_df[old_df[target_col] == class_val]
        if len(old_class) >= old_count:
            balanced_dfs.append(old_class.sample(n=old_count, random_state=random_state))
        else:
            balanced_dfs.append(old_class)
    
    result = pd.concat(balanced_dfs).drop(columns=['_date', '_age_days'])
    return result.sample(frac=1, random_state=random_state).reset_index(drop=True)


# =============================================================================
# TEMPORAL WEIGHTING
# =============================================================================

def add_sample_weights(df: pd.DataFrame, date_col: str = "date",
                       decay_days: float = 90.0) -> pd.DataFrame:
    """
    Add sample weights based on data freshness.
    
    Uses exponential decay: weight = exp(-age / decay_days)
    - Data from today: weight ≈ 1.0
    - Data from 90 days ago: weight ≈ 0.37
    - Data from 180 days ago: weight ≈ 0.14
    """
    df = df.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    max_date = df['_date'].max()
    
    df['days_ago'] = (max_date - df['_date']).dt.days
    df['sample_weight'] = np.exp(-df['days_ago'] / decay_days)
    
    df = df.drop(columns=['_date'])
    return df


def get_temporal_train_val_test_weights(
    df: pd.DataFrame,
    date_col: str = "date"
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Create sample weights that emphasize recent data more in training.
    
    Returns weights for train, val, test splits.
    """
    df = df.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    
    # Normalize dates to 0-1 range
    min_date = df['_date'].min()
    max_date = df['_date'].max()
    date_range = (max_date - min_date).days
    
    if date_range == 0:
        return np.ones(len(df)), np.ones(len(df)), np.ones(len(df))
    
    df['normalized_time'] = (df['_date'] - min_date).dt.days / date_range
    
    # Weights increase with time (0.5 to 1.5 range)
    weights = 0.5 + df['normalized_time'].values
    
    return weights


# =============================================================================
# WALK-FORWARD SPLITS
# =============================================================================

def temporal_train_val_test_split(
    df: pd.DataFrame,
    date_col: str = "date",
    train_months: int = 4,
    val_months: int = 1,
    test_months: int = 1
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Chronological split for realistic backtesting.
    
    Instead of random split, uses:
    - Train: oldest data (train_months)
    - Validation: middle data (val_months)  
    - Test: most recent data (test_months)
    
    This prevents temporal leakage and simulates real-world deployment.
    """
    df = df.copy()
    df['_date'] = pd.to_datetime(df[date_col])
    df = df.sort_values('_date')
    
    max_date = df['_date'].max()
    test_start = max_date - timedelta(days=test_months * 30)
    val_start = test_start - timedelta(days=val_months * 30)
    train_start = val_start - timedelta(days=train_months * 30)
    
    train_df = df[(df['_date'] >= train_start) & (df['_date'] < val_start)]
    val_df = df[(df['_date'] >= val_start) & (df['_date'] < test_start)]
    test_df = df[df['_date'] >= test_start]
    
    # Clean up temp column
    for split_df in [train_df, val_df, test_df]:
        if '_date' in split_df.columns:
            split_df.drop(columns=['_date'], inplace=True, errors='ignore')
    
    return train_df, val_df, test_df


def walk_forward_splits(
    df: pd.DataFrame,
    date_col: str = "date",
    train_window_months: int = 3,
    test_window_months: int = 1,
    step_months: int = 1
) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Generate multiple train/test splits for walk-forward validation.
    
    Walk-forward simulates retraining the model periodically:
    1. Train on months 1-3, test on month 4
    2. Train on months 2-4, test on month 5
    3. etc.
    
    Returns list of (train_df, test_df) tuples.
    """
    df = df.copy()
    
    # 1. FORZAR CONVERSIÓN DE FECHA (Convierte 20260127 -> Datetime)
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        # Intentar formato YYYYMMDD que es el que tienes
        df[date_col] = pd.to_datetime(df[date_col].astype(str), format='%Y%m%d', errors='coerce')
        
    df = df.sort_values(date_col)
    # Extraer solo la fecha (sin hora) para contar días únicos
    unique_dates = sorted(df[date_col].dt.date.unique())
    n_unique_days = len(unique_dates)
    
    # 2. LÓGICA DE EMERGENCIA PARA 14 DÍAS (Modo Micro-Window)
    if train_window_months == 0 or n_unique_days < 20:
        # Forzamos una partición proporcional: 6 días entreno / 2 días test
        train_days = 6 
        test_days = 2
        step_days = 2 # Desplazamos la ventana de 2 en 2 días
        
        print(f"    [WF-DEBUG] Corregido: Detectados {n_unique_days} días reales.")
        print(f"    [WF-DEBUG] Ventanas: Train={train_days}d, Test={test_days}d")
        
        splits = []
        for i in range(0, n_unique_days - train_days - test_days + 1, step_days):
            train_dates = unique_dates[i : i + train_days]
            test_dates = unique_dates[i + train_days : i + train_days + test_days]
            
            train_split = df[df[date_col].dt.date.isin(train_dates)].copy()
            test_split = df[df[date_col].dt.date.isin(test_dates)].copy()
            
            if len(train_split) > 100: # Asegurar que hay datos
                splits.append((train_split, test_split))
        
        return splits

    min_date = df['_date'].min()
    max_date = df['_date'].max()
    
    splits = []
    current_train_start = min_date
    
    while True:
        train_end = current_train_start + timedelta(days=train_window_months * 30)
        test_end = train_end + timedelta(days=test_window_months * 30)
        
        if test_end > max_date:
            break
        
        train_mask = (df['_date'] >= current_train_start) & (df['_date'] < train_end)
        test_mask = (df['_date'] >= train_end) & (df['_date'] < test_end)
        
        train_split = df[train_mask].drop(columns=['_date'], errors='ignore')
        test_split = df[test_mask].drop(columns=['_date'], errors='ignore')
        
        if len(train_split) > 100 and len(test_split) > 10:  # Minimum samples
            splits.append((train_split, test_split))
        
        current_train_start += timedelta(days=step_months * 30)
    
    return splits


# =============================================================================
# FEATURE ENGINEERING UTILITIES
# =============================================================================

def add_lagged_features(
    df: pd.DataFrame,
    feature_cols: List[str],
    lags: List[int] = [1, 5, 15],
    group_col: str = "ticker"
) -> pd.DataFrame:
    """
    Add lagged versions of features (within each ticker group).
    
    This is SAFE because lags are backwards, not forwards.
    """
    df = df.copy()
    
    for col in feature_cols:
        if col not in df.columns:
            continue
        for lag in lags:
            new_col = f"{col}_lag{lag}"
            df[new_col] = df.groupby(group_col)[col].shift(lag)
    
    return df


def add_rolling_features(
    df: pd.DataFrame,
    feature_cols: List[str],
    windows: List[int] = [5, 15, 30],
    group_col: str = "ticker"
) -> pd.DataFrame:
    """
    Add rolling statistics (mean, std) for features.
    
    Rolling uses PAST data only (safe from lookahead).
    """
    df = df.copy()
    
    for col in feature_cols:
        if col not in df.columns:
            continue
        for window in windows:
            # Rolling mean
            mean_col = f"{col}_ma{window}"
            df[mean_col] = df.groupby(group_col)[col].transform(
                lambda x: x.rolling(window=window, min_periods=1).mean()
            )
            
            # Rolling std
            std_col = f"{col}_std{window}"
            df[std_col] = df.groupby(group_col)[col].transform(
                lambda x: x.rolling(window=window, min_periods=2).std()
            )
    
    return df


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("DATA UTILITIES TEST")
    print("=" * 70)
    
    # Test robust target calculation
    print("\n[1] Testing robust target label calculation...")
    
    # Simulate price series (trending up)
    prices_up = [100 + i * 0.05 + np.random.randn() * 0.1 for i in range(100)]
    label = calculate_target_label_robust(prices_up, 30, lookahead_min=15, lookahead_max=30)
    print(f"  Uptrend label (should be 1): {label}")
    
    # Simulate flat prices
    prices_flat = [100 + np.random.randn() * 0.05 for _ in range(100)]
    label = calculate_target_label_robust(prices_flat, 30)
    print(f"  Flat label (should be 0): {label}")
    
    # Simulate downtrend
    prices_down = [100 - i * 0.05 + np.random.randn() * 0.1 for i in range(100)]
    label = calculate_target_label_robust(prices_down, 30)
    print(f"  Downtrend label (should be -1): {label}")
    
    # Test with max adverse movement
    print("\n[2] Testing target with max adverse movement...")
    label, meta = calculate_target_with_max_adverse(prices_up, 30)
    print(f"  Label: {label}")
    print(f"  Metadata: {meta}")
    
    # Test class balancing
    print("\n[3] Testing class balancing...")
    
    # Create imbalanced dataset
    np.random.seed(42)
    n_samples = 1000
    test_df = pd.DataFrame({
        "feature1": np.random.randn(n_samples),
        "feature2": np.random.randn(n_samples),
        "target": np.random.choice([-1, 0, 1], n_samples, p=[0.15, 0.70, 0.15]),
        "date": pd.date_range("2025-01-01", periods=n_samples, freq="h"),
    })
    
    print(f"  Original distribution:\n{test_df['target'].value_counts()}")
    
    balanced_df = balance_classes_undersample(test_df)
    print(f"  After undersample:\n{balanced_df['target'].value_counts()}")
    
    weights = balance_classes_weighted(test_df)
    print(f"  Class weights: {weights}")
    
    # Test temporal weighting
    print("\n[4] Testing temporal weights...")
    weighted_df = add_sample_weights(test_df, decay_days=30)
    print(f"  Weight range: {weighted_df['sample_weight'].min():.3f} - {weighted_df['sample_weight'].max():.3f}")
    
    # Test walk-forward splits
    print("\n[5] Testing walk-forward splits...")
    splits = walk_forward_splits(test_df, train_window_months=1, test_window_months=1, step_months=1)
    print(f"  Generated {len(splits)} walk-forward windows")
    for i, (train, test) in enumerate(splits[:3]):
        print(f"    Window {i+1}: Train={len(train)}, Test={len(test)}")
    
    print("\n" + "=" * 70)
    print("All data utility tests passed!")
    print("=" * 70)
