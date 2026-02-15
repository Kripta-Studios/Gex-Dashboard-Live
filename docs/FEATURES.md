# Trading Model Features Documentation

This document provides a complete reference for all features used in the hybrid trading model, including their mathematical formulas, data sources, and trading rationale.

---

## Table of Contents

1. [Meta Features](#meta-features)
2. [Target Labels](#target-labels)
3. [0DTE Greek Exposures](#0dte-greek-exposures)
4. [0DTE Key Levels](#0dte-key-levels)
5. [Weekly Greek Exposures](#weekly-greek-exposures)
6. [Cross-Expiry Divergence](#cross-expiry-divergence)
7. [Initial Balance (IB) Features](#initial-balance-ib-features)
8. [Fibonacci Extensions](#fibonacci-extensions)
9. [Implied Volatility (IV) Features](#implied-volatility-iv-features)
10. [VIX Features](#vix-features)
11. [Market Context](#market-context)
12. [Engineered Features](#engineered-features)

---

## Meta Features

### Basic Identifiers

| Feature | Type | Description |
|---------|------|-------------|
| `ticker` | string | Symbol being traded (SPX, SPY, QQQ, /ES, /NQ) |
| `date` | string | Trading date in YYYYMMDD format |
| `time` | string | Time of day in HH:MM format |
| `timestamp` | datetime | Full timestamp of the observation |
| `spot_price` | float | Current market price of the underlying |

---

## Target Labels

### Target Classification

**Formula:**
```
target = {
    1   if max_up_move ≥ 0.4% AND max_up_move > max_down_move  (LONG)
    -1  if max_down_move ≥ 0.4% AND max_down_move > max_up_move  (SHORT)
    0   otherwise  (HOLD)
}

where:
    max_up_move = (max_price_next_120min - current_price) / current_price
    max_down_move = (current_price - min_price_next_120min) / current_price
```

**Threshold:** 0.4% (TARGET_MOVE_THRESHOLD)
**Lookahead Window:** 120 minutes

### Timing Features

| Feature | Formula | Description |
|---------|---------|-------------|
| `time_to_target` | Minutes until 0.4% target hit | Time to reach profit target (0 if not hit) |
| `time_to_stop` | Minutes until 0.4% stop hit | Time to hit opposite-direction stop (0 if not hit) |
| `max_move` | max(max_up_move, max_down_move) | Maximum favorable price movement percentage |

**Purpose:** These provide the model with information about how long profitable moves typically take to develop, helping optimize entry timing.

---

## 0DTE Greek Exposures

0DTE (zero days to expiration) options dominate intraday flow and create immediate hedging pressure on market makers.

### Net Greek Values

All net Greeks are calculated by summing the exposure across all strikes:

```
net_greek = Σ(greek_exposure[strike]) for all strikes
```

| Feature | Source Greek | Formula | Trading Significance |
|---------|--------------|---------|---------------------|
| `net_gamma` | totalgamma | Σ(all[i]) | **Volatility dampening/amplification**. Positive = dealers long gamma (stabilizing), negative = dealers short gamma (destabilizing) |
| `net_vanna` | totalvanna | Σ(all[i]) | **Vol-spot correlation**. Positive vanna means rising IV → rising spot (bullish feedback loop) |
| `net_charm` | totalcharm | Σ(all[i]) | **Time decay directional pressure**. Positive charm = theta decay pushes price up |
| `net_dgex` | totaldgex | Σ(all[i]) | **Dealer gamma exposure**. Shows where dealers need to hedge most aggressively |
| `net_zomma` | totalzomma | Σ(all[i]) | **Gamma stability**. Positive = gamma increases with vol (stabilizing effect) |
| `net_delta` | totaldelta | Σ(all[i]) | **Directional exposure**. Net directional pressure from all options |

### Greek Regime Classification

**Formula:**
```python
gamma_regime = {
    2  if net_gamma > 0.1   # Long gamma (dealers stabilize)
    0  if net_gamma < -0.1  # Short gamma (dealers amplify)
    1  otherwise            # Neutral
}
```

**Binary Greek Signals:**

| Feature | Formula | Interpretation |
|---------|---------|----------------|
| `vanna_bullish` | 1 if net_vanna > 0.1 else 0 | Vol-spot feedback is bullish |
| `charm_bullish` | 1 if net_charm > 0.1 else 0 | Time decay favors upside |
| `dgex_sticky` | 1 if net_dgex > 0.1 else 0 | Dealers pin price (high hedging) |
| `zomma_stabilizing` | 1 if net_zomma > 0.1 else 0 | Gamma becomes more stabilizing with vol |

---

## 0DTE Key Levels

Key levels are strikes where Greek exposure is concentrated, creating natural support/resistance.

### Strike Identification

**Max/Min Greek Strikes:**
```python
max_gamma_strike = levels[argmax(totalgamma.all)]
min_gamma_strike = levels[argmin(totalgamma.all)]
max_dgex_strike = levels[argmax(totaldgex.all)]
min_dgex_strike = levels[argmin(totaldgex.all)]
min_vanna_strike = levels[argmin(totalvanna.all)]
```

**Zero Crossings:**
- `zero_gamma`: Strike where net gamma changes sign
- `zero_delta`: Strike where net delta changes sign

### Distance Features

All distances are normalized by current price:

```python
dist_to_level = (spot_price - level) / spot_price
```

| Feature | Formula | Trading Use |
|---------|---------|-------------|
| `dist_to_max_gamma` | (spot - max_gamma) / spot | Distance to strongest gamma wall (resistance/support) |
| `dist_to_min_gamma` | (spot - min_gamma) / spot | Distance to gamma hole (volatility zone) |
| `dist_to_min_vanna` | (spot - min_vanna) / spot | Distance to vanna flip point |
| `dist_to_zero_gamma` | (spot - zero_gamma) / spot | Distance to gamma transition level |
| `dist_to_max_dgex` | (spot - max_dgex) / spot | Distance to peak dealer hedging |
| `dist_to_min_dgex` | (spot - min_dgex) / spot | Distance to dealer hedging hole |

### Proximity Flags

**Formula:**
```python
near_level = 1 if |spot - level| / spot ≤ 0.04% else 0
```

| Feature | Condition | Significance |
|---------|-----------|-------------|
| `near_max_gamma` | Within 0.04% of max gamma | At gamma wall - expect rejection or breakout |
| `near_min_gamma` | Within 0.04% of min gamma | In gamma hole - expect acceleration |
| `near_min_vanna` | Within 0.04% of min vanna | At vanna inflection - vol/spot relationship changes |
| `near_zero_gamma` | Within 0.04% of zero gamma | At regime transition point |

**Trading Logic:** When price is "near" a key level, the market often shows distinct behavior (consolidation, reversal, or breakout).

---

## Weekly Greek Exposures

Weekly options provide intermediate-term context (1-4 weeks to expiration) and show institutional positioning.

All weekly features use the same formulas as 0DTE Greeks but with `wk_` prefix and are normalized to [0, 1] range where applicable.

### Net Weekly Greeks

| Feature | Source | Normalized Formula |
|---------|--------|-------------------|
| `wk_net_gamma` | weekly totalgamma | Σ(all[i]) |
| `wk_net_vanna` | weekly totalvanna | Σ(all[i]) |
| `wk_net_charm` | weekly totalcharm | Σ(all[i]) |
| `wk_net_dgex` | weekly totaldgex | Σ(all[i]) |
| `wk_net_zomma` | weekly totalzomma | Σ(all[i]) |
| `wk_net_delta` | weekly totaldelta | Σ(all[i]) |

### Weekly Key Levels

| Feature | Formula | Purpose |
|---------|---------|---------|
| `wk_dist_to_max_gamma` | (spot - wk_max_gamma) / spot | Weekly gamma wall location |
| `wk_dist_to_min_gamma` | (spot - wk_min_gamma) / spot | Weekly gamma hole location |
| `wk_dist_to_max_dgex` | (spot - wk_max_dgex) / spot | Weekly dealer pin level |
| `wk_dist_to_min_dgex` | (spot - wk_min_dgex) / spot | Weekly dealer hedging hole |

### Weekly Regime

| Feature | Formula | Range |
|---------|---------|-------|
| `wk_gamma_regime` | wk_gamma_regime / 2.0 | [0, 1] where 0=short, 0.5=neutral, 1=long |
| `wk_vanna_bullish` | 1 if wk_net_vanna > 0.1 else 0 | Binary |
| `wk_dgex_sticky` | 1 if wk_net_dgex > 0.1 else 0 | Binary |
| `wk_zomma_stabilizing` | 1 if wk_net_zomma > 0.1 else 0 | Binary |

**Purpose:** Weekly Greeks show where institutions are positioned for multi-day moves, while 0DTE shows intraday hedging flow.

---

## Cross-Expiry Divergence

Divergence between 0DTE and weekly Greeks indicates flow disagreement and potential regime changes.

### Sign Divergence Formula

```python
def sign_divergence(a: float, b: float) -> float:
    if |a| < 0.01 or |b| < 0.01:
        return 0.5  # One side is neutral
    if sign(a) ≠ sign(b):
        return 1.0  # Divergence (conflicting signals)
    return 0.0  # Agreement
```

| Feature | Comparison | Trading Interpretation |
|---------|------------|----------------------|
| `gamma_0dte_vs_wk` | sign_div(net_gamma, wk_net_gamma) | 1.0 = intraday vs multi-day regime conflict |
| `vanna_0dte_vs_wk` | sign_div(net_vanna, wk_net_vanna) | 1.0 = vol-spot feedback disagreement |
| `dgex_0dte_vs_wk` | sign_div(net_dgex, wk_net_dgex) | 1.0 = intraday vs multi-day dealer hedging conflict |
| `delta_0dte_vs_wk` | sign_div(net_delta, wk_net_delta) | 1.0 = directional flow disagreement |

**Trading Edge:** High divergence (1.0) often precedes reversals or regime changes as one timeframe "wins" the tug-of-war.

---

## Initial Balance (IB) Features

Initial Balance is the price range established in the first hour of trading (9:30-10:30 AM ET). It's a critical framework for intraday trading.

### IB Range Definition

```
ib_high = max(price) for t ∈ [9:30, 10:30]
ib_low = min(price) for t ∈ [9:30, 10:30]
ib_range = ib_high - ib_low
```

### Price Relative to IB

| Feature | Formula | Interpretation |
|---------|---------|----------------|
| `price_vs_ib_high` | (spot - ib_high) / spot | Positive = above IB (bullish breakout) |
| `price_vs_ib_low` | (spot - ib_low) / spot | Negative = below IB (bearish breakdown) |
| `ib_range_pct` | (ib_high - ib_low) / spot | IB volatility (wider = more volatile day) |

### IB Proximity Flags

| Feature | Condition | Trading Signal |
|---------|-----------|---------------|
| `near_ib_high` | \|spot - ib_high\| / spot ≤ 0.04% | Testing IB high - breakout or rejection |
| `near_ib_low` | \|spot - ib_low\| / spot ≤ 0.04% | Testing IB low - breakdown or bounce |

### IB Position Flags

| Feature | Condition | Trading Context |
|---------|-----------|----------------|
| `above_ib` | spot > ib_high | Bullish - IB high is now support |
| `below_ib` | spot < ib_low | Bearish - IB low is now resistance |
| `in_ib_range` | ib_low ≤ spot ≤ ib_high | Consolidation - expect breakout |

**Trading Framework:** 
- 68% of days stay within IB ± 1 extension
- Breakouts above/below IB tend to continue
- Returns to IB after breakout often fail (trap)

---

## Fibonacci Extensions

Fibonacci levels project probable price targets based on IB range using classical ratios.

### Calculation

```python
ib_range = ib_high - ib_low

# Upside extensions (from IB low)
fib_127_up = ib_low + (ib_range × 1.272)
fib_161_up = ib_low + (ib_range × 1.618)
fib_200_up = ib_low + (ib_range × 2.000)

# Downside extensions (from IB low)
fib_127_dn = ib_low + (ib_range × -0.272)
fib_161_dn = ib_low + (ib_range × -0.618)
fib_200_dn = ib_low + (ib_range × -1.000)
```

### Distance Features

| Feature | Formula | Usage |
|---------|---------|-------|
| `dist_fib_127_up` | (spot - fib_127_up) / spot | Distance to 1.272 extension (first target) |
| `dist_fib_161_up` | (spot - fib_161_up) / spot | Distance to 1.618 extension (golden ratio target) |

**Trading Application:**
- 1.272 extension: ~50% of breakouts reach this level
- 1.618 extension: ~30% of breakouts reach this level (strong move)
- 2.0 extension: ~10% of breakouts (rare, momentum day)

---

## Implied Volatility (IV) Features

IV features are derived from ATM put options using Fourier filtering to remove noise.

### Raw IV

**Source:** ATM put implied volatility from options chain
**Formula:**
```python
atm_iv = IV(ATM_put) / 100  # Normalized to decimal (e.g., 0.15 = 15%)
```

### IV Statistical Context

**Daily Statistics:**
```python
iv_mean = mean(atm_iv[t]) for all t in trading_day
iv_std = std(atm_iv[t]) for all t in trading_day
iv_min = min(atm_iv[t]) for all t in trading_day
iv_max = max(atm_iv[t]) for all t in trading_day
```

| Feature | Formula | Interpretation |
|---------|---------|----------------|
| `iv_zscore` | clip((atm_iv - iv_mean) / iv_std, -3, 3) / 3 | Normalized to [-1, 1]; 1.0 = IV is 3σ above mean (extreme fear) |
| `iv_percentile` | (atm_iv - iv_min) / (iv_max - iv_min) | Where current IV ranks in today's range [0, 1] |

**Trading Logic:**
- High IV Z-score (>0.5): Options expensive, consider selling premium or fading moves
- Low IV Z-score (<-0.5): Options cheap, consider buying options or expecting expansion
- IV percentile > 0.8: IV near daily highs, likely to contract (mean reversion)

---

## VIX Features

VIX (CBOE Volatility Index) provides market-wide fear/greed context independent of underlying-specific Greeks.

### VIX Data Sources

1. **VIX Spot:** From IB minute bars (VIX index itself)
2. **VIX Gamma:** From VIX weekly options exposure (dealers' VIX hedging needs)

### VIX Metrics

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `vix_spot` | VIX_index_price / 50 | [0, 1+] | Normalized VIX level (0.3 = 15 VIX, 0.5 = 25 VIX) |
| `vix_gamma` | Σ(VIX_weekly_totalgamma[i]) | Raw | Net gamma in VIX options (hedging demand) |

### VIX Regime Classification

**Formula:**
```python
vix_regime = {
    2  if vix_spot > 25   # High fear
    1  if vix_spot > 18   # Elevated anxiety
    0  otherwise          # Low/complacent
}

vix_regime_normalized = vix_regime / 2.0  # Scale to [0, 1]
```

| VIX Level | Regime | Typical Market Behavior |
|-----------|--------|------------------------|
| < 18 | Low (0) | Complacent, low hedging, trending markets |
| 18-25 | Elevated (1) | Moderate uncertainty, choppy |
| > 25 | High (2) | Fear, aggressive hedging, volatile |

**Trading Application:**
- VIX > 25 + positive gamma = expect mean reversion (dealers stabilize)
- VIX > 25 + negative gamma = expect continued volatility (dealers amplify)
- VIX < 18 = "vol crush" regime, fade extended moves

---

## Market Context

### Technical Indicators

#### RSI (Relative Strength Index)

**Formula:**
```python
def rsi(prices, period=14):
    deltas = diff(prices)
    gains = where(deltas > 0, deltas, 0)
    losses = where(deltas < 0, -deltas, 0)
    
    avg_gain = mean(gains[-period:])
    avg_loss = mean(losses[-period:])
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi / 100  # Normalized to [0, 1]
```

**Interpretation:**
- RSI > 0.7 (70): Overbought, potential reversal
- RSI < 0.3 (30): Oversold, potential bounce
- RSI ~ 0.5 (50): Neutral, no momentum bias

#### Volume Relative

**Formula:**
```python
avg_volume_per_bar = total_daily_volume / num_bars
vol_relative = current_bar_volume / avg_volume_per_bar
vol_relative_normalized = min(vol_relative, 5.0) / 5.0  # Capped at 5x average
```

**Interpretation:**
- vol_relative > 2.0: High volume bar, significant price action
- vol_relative < 0.5: Low volume bar, lack of conviction
- Volume spikes confirm breakouts, lack of volume suggests false moves

### Time Features

| Feature | Formula | Purpose |
|---------|---------|---------|
| `hour_normalized` | hour / 24.0 | Time of day effect [0, 1] |
| `minute_normalized` | minute / 60.0 | Intra-hour positioning [0, 1] |

**Intraday Patterns:**
- 9:30-10:30: Initial balance formation, high volatility
- 10:30-11:30: Trend development or IB test
- 11:30-14:00: Lunch lull, low volume/volatility
- 14:00-15:00: Afternoon continuation or reversal
- 15:00-16:00: Closing drive, profit-taking, stops triggered

---

## Engineered Features

These features combine multiple inputs to capture complex market dynamics.

### Greek Ratios

Ratios reveal the relative strength of different Greek forces:

| Feature | Formula | Interpretation |
|---------|---------|----------------|
| `gamma_vanna_ratio` | net_gamma / (\|net_vanna\| + ε) | Gamma vs vanna dominance; high = gamma effects override vol-spot feedback |
| `dgex_gamma_ratio` | net_dgex / (\|net_gamma\| + ε) | Dealer hedging intensity vs gamma regime |
| `charm_vanna_ratio` | net_charm / (\|net_vanna\| + ε) | Time decay pressure vs vol-spot feedback |
| `delta_gamma_ratio` | net_delta / (\|net_gamma\| + ε) | Directional flow vs gamma regime |

**Note:** ε = 1e-6 prevents division by zero

**Trading Use:**
- High gamma_vanna_ratio: Price stability dominates (gamma pinning)
- High dgex_gamma_ratio: Aggressive dealer hedging, expect sharp moves
- Negative charm_vanna_ratio with high magnitude: Complex feedback loops

### Temporal Deltas

Changes between consecutive observations reveal flow acceleration/deceleration:

| Feature | Formula | Interpretation |
|---------|---------|----------------|
| `gamma_change` | net_gamma(t) - net_gamma(t-1) | Gamma accumulation/decay rate |
| `vanna_change` | net_vanna(t) - net_vanna(t-1) | Vol-spot feedback strengthening/weakening |
| `dgex_change` | net_dgex(t) - net_dgex(t-1) | Dealer hedging pressure change |
| `delta_change` | net_delta(t) - net_delta(t-1) | Directional flow acceleration |
| `spot_change` | (spot(t) - spot(t-1)) / spot(t-1) | Price momentum |

**Trading Logic:**
- Positive gamma_change + rising price = gamma wall building above (resistance)
- Negative dgex_change = dealers reducing hedging (expect mean reversion)
- Large spot_change with small delta_change = move driven by technical factors, not flow

### Cross-Features

Complex interactions between price action and Greek dynamics:

#### Gamma Momentum

**Formula:**
```python
gamma_momentum = (net_gamma(t) - net_gamma(t-1)) × sign(net_gamma(t))
```

**Interpretation:**
- Positive gamma_momentum (>0): Long gamma regime strengthening → expect stabilization
- Negative gamma_momentum (<0): Short gamma regime deepening → expect volatility expansion

#### Price vs DGEX Magnet

**Formula:**
```python
price_vs_dgex_magnet = (
    (spot(t) - spot(t-1)) / spot(t-1)  # Price change direction
    × 
    sign((spot(t) - max_dgex_strike(t)) / spot(t))  # Position relative to DGEX max
)
```

**Interpretation:**
- Positive: Price moving toward max DGEX (magnetic pull)
- Negative: Price moving away from max DGEX (breaking free or reversal)
- Magnitude: Speed of attraction/repulsion

**Trading Edge:** Max DGEX strikes act as "magnets" due to dealer hedging. When price approaches max DGEX with positive price_vs_dgex_magnet, expect consolidation. When negative, expect breakout continuation.

---

## Feature Summary Table

| Category | Count | Key Features | Primary Use |
|----------|-------|--------------|-------------|
| Meta | 5 | ticker, date, time, timestamp, spot_price | Identification |
| Target | 4 | target, time_to_target, time_to_stop, max_move | Model output |
| 0DTE Greeks | 17 | net_gamma, net_vanna, net_dgex, distances, flags | Intraday flow |
| Weekly Greeks | 14 | wk_net_gamma, wk_net_vanna, wk_dgex, distances | Multi-day context |
| Cross-Expiry | 4 | gamma_0dte_vs_wk, vanna_0dte_vs_wk, etc. | Regime detection |
| IB Features | 8 | price_vs_ib_high, near_ib_high, in_ib_range | Intraday framework |
| Fibonacci | 2 | dist_fib_127_up, dist_fib_161_up | Target projection |
| IV Features | 4 | atm_iv, iv_zscore, iv_percentile | Vol environment |
| VIX Features | 3 | vix_spot, vix_gamma, vix_regime | Market-wide sentiment |
| Market Context | 3 | rsi, vol_relative, time features | Technical confirmation |
| Engineered | 10 | ratios, deltas, gamma_momentum, dgex_magnet | Complex dynamics |

**Total Features:** ~74 numerical features (excluding meta fields)

---

## Data Flow Pipeline

```
1. Raw Data Collection
   ├─ Greek JSONs (0DTE & Weekly) → Net exposures, key strikes
   ├─ IB Minute Bars → Price series, volume, IB range
   ├─ Fourier IV Data → ATM IV time series
   └─ VIX Data → VIX spot, VIX gamma

2. Feature Engineering
   ├─ Greek Processing → Net values, distances, flags
   ├─ Level Detection → Max/min strikes, zero crossings
   ├─ Temporal Joins → Match Greek snapshots to price bars
   └─ Statistical Context → RSI, IV percentiles, volume

3. Cross-Feature Generation
   ├─ Greek Ratios → Relative strength of forces
   ├─ Temporal Deltas → Rate of change
   └─ Complex Interactions → Gamma momentum, DGEX magnet

4. Target Calculation
   └─ Lookahead Analysis → Price moves over next 120 minutes

5. Dataset Output
   └─ CSV with 79,576 samples × 74+ features
```

---

## Feature Importance Insights

From model training, the top 5 most important features are:

1. **price_vs_dgex_magnet** (0.0213): Price movement relative to dealer hedging concentration
2. **dgex_sticky** (0.0195): Binary flag for high dealer gamma exposure (pinning)
3. **zomma_stabilizing** (0.0187): Indicates gamma will strengthen with volatility
4. **wk_net_charm** (0.0182): Multi-day time decay pressure
5. **gamma_regime** (0.0180): Overall market maker hedging stance

**Insight:** The model prioritizes dealer hedging dynamics (DGEX) and cross-expiry information over pure gamma/vanna, suggesting that understanding where dealers MUST hedge (not just aggregate exposure) is key to profitability.

---

## Usage Notes

### Feature Scaling

- **Distance features:** Already normalized by dividing by spot_price (scale ~0.001 to 0.05)
- **Greek exposures:** Raw values (scale varies by ticker, model learns appropriate weighting)
- **Binary flags:** {0, 1}
- **Normalized features:** [0, 1] range (IV percentile, RSI, time features)
- **Ratios:** Can be unbounded; model handles naturally

### Missing Data Handling

- **Missing Greek data:** Use zeros (indicates no options flow that period)
- **Missing IB data:** Skip that day entirely (IB is critical framework)
- **Missing IV data:** Use 0.5 for percentile, 0 for zscore (neutral assumption)
- **Missing VIX data:** Use regime=1 (elevated/neutral assumption)

### Computational Notes

- **Greek files:** ~1-2 per minute during market hours (9:30-16:00 ET)
- **Processing time:** ~12 minutes for 14 days × 5 tickers (parallelized)
- **Dataset size:** 79,576 samples = ~14 days × 5 tickers × ~1140 snapshots/day
- **Feature count:** 74 numerical features + 5 meta features

---

## References

### Data Sources

- **Greek Exposures:** SpotGamma-style calculations from options chains
- **IB Methodology:** Dalton's Market Profile framework
- **Fibonacci Ratios:** Classical technical analysis (1.272, 1.618, 2.0)
- **VIX:** CBOE Volatility Index (ticker: VIX)

### Key Concepts

- **Gamma Pinning:** Price gravitates toward strikes with high positive gamma
- **Charm:** dGamma/dTime - how gamma changes with time decay
- **Vanna:** dDelta/dVol - how directional exposure changes with volatility
- **Zomma:** dGamma/dVol - how gamma changes with volatility

### Model Architecture

- **Type:** Hybrid LSTM + Dense Neural Network
- **Framework:** PyTorch with CUDA acceleration
- **Training:** 200 epochs, best validation: 88.7% accuracy
- **Generalization:** -0.148 train-val gap (excellent)

---

## Changelog

**v1.0** - Initial feature set with 0DTE Greeks, IB features, basic IV
**v2.0** - Added weekly Greeks, cross-expiry divergence, VIX features
**v3.0** - Added Fourier IV processing, engineered features (ratios, deltas, cross-features)
**v3.1** - Added DGEX key levels and price_vs_dgex_magnet feature (breakthrough improvement)

---

*Last Updated: 2025-02-14*
*Model Version: trading_hybrid.pt*
*Training Dataset: 79,576 samples, 14 days, 88.2% final accuracy*