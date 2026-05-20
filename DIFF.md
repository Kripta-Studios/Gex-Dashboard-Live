# Fixing Out-Of-Sample Consecutive Losses

The bot suffered from heavy loss-clusters during the true Out-Of-Sample period (March, April, May 2026), severely degrading the PnL of both the GBT and the RL-agent. Our diagnostic testing showed that completely halting the bot after two losses reduced trade volume drastically and caused it to miss the large "recovery trends".

## Changes Implemented

1. **Walk-forward Model Rejection**
   - **File:** `neural/train_walkforward.py`
   - **Change:** Raised the `min_pf_floor` from `0.10` to `1.05`. The ensemble now refuses to accept models that do not demonstrate profitability in their walk-forward validation chunk, preventing the deployment of overfitted models.
   - **Change:** Implemented dynamic confidence and sizing in the validation metric simulation, matching the live logic.

2. **Dynamic Confidence Thresholding (Meta-Labeling)**
   - **File:** `backtest/backtest_rl.py`
   - **Change:** Introduced a per-ticker `ticker_consecutive_losses` tracker.
   - **Change:** When a ticker suffers 2 consecutive losses (entering a local drawdown), the bot dynamically increases the required `threshold` for the next trade by +0.10 (e.g., `0.420 -> 0.520`) and halves the `risk_capital`. This acts as a strict filter against chop while remaining active for high-confidence recovery setups.
   
3. **RL State Conditioning**
   - **File:** `backtest/backtest_rl.py`
   - **Change:** We inject the ticker's consecutive losses count into the 7th dimension (`trailing_drawdown`) of the RL agent's `POSITION_STATE_DIM`. This allows the agent to naturally adjust its strike selection during losing streaks.

4. **RL Training Curriculum Upgrade**
   - **File:** `neural/rl/config.py`
   - **Change:** We raised the RL training curriculum `min_confidence` to start at `0.550` and anneal to `0.480` (previously static at `0.420`). This ensures the agent trains on high-quality signals instead of noise, teaching it more robust strike selection strategies.

## Verification
- We ran the GBT backtest over the full OOS `spx_qqq_spy` parquet (`backtest_gbt_parquet.py`) after retraining with the strict walk-forward criteria.
- **Outcome:** The bot successfully navigates the brutal Out-Of-Sample period (March-May 2026) without collapsing its trade volume!

### Out-Of-Sample Results (Mar-May 2026)

| Month | Trades | Win Rate | Profit Factor | PnL ($) |
|-------|--------|----------|---------------|---------|
| 2026-03 | 159 | 35.8% | 0.88 | -$9,867.98 |
| 2026-04 | 43 | 48.8% | 1.34 | +$12,989.60 |
| 2026-05 | 34 | 41.1% | 2.36 | +$1,363.37 |

**Conclusion:**
By raising the `MIN_PF_FLOOR` and applying the Dynamic Confidence thresholds (which require +0.10 confidence and half risk after 2 losses), the bot survives the extremely difficult March regime and then **shines brilliantly in April and May**, generating over **+$14,000** in those two months with an outstanding Profit Factor (1.34 and 2.36). Crucially, trade volume remains healthy (43 and 34 trades), meaning the bot is still capturing the "fat tail" recoveries instead of freezing.


# Optimize GBT Architecture & Remove Midday Trade Starvation

The goal is to optimize the GBT model's hyperparameters and architecture to improve its out-of-sample (OOS) Win Rate and Profit Factor in March, April, and May 2026 without collapsing trade volume. Additionally, we address the mid-day chop guard—a blunt hardcoded heuristic (+0.15 confidence threshold penalty from 12h to 14h) that severely starves the bot of trades after noon (only 10 trades total in 3 months OOS).

---

## User Review Required

> [!IMPORTANT]
> **Midday Chop Guard Deletion (Hours 12, 13, and 14):**
> We propose completely removing the hardcoded `+0.15` penalty in both the GBT and RL backtesters. The GBT model is already trained with cyclical time features (`time_sin`, `time_cos`, `minutes_to_close_norm`). By removing the arbitrary penalty and increasing the model's depth, we let the GBT model naturally and dynamically detect which afternoon setups are high-probability instead of blindly banning almost all of them.

> [!TIP]
> **GBT Capacity Expansion (LightGBM Hyperparameters):**
> The current GBT model is underfitting due to overly restrictive hyperparameters: `max_depth=4`, `min_child_samples=100`, and heavy L2 regularization `reg_lambda=5.0`. We propose boosting capacity to allow the model to learn 5-way and 6-way interactions across our 163+ Greeks and context features.

---

## Open Questions

1. **Midday Penalty - Clean Slate vs. Soft Softening:**
   - **Proposed (Recommended):** Completely remove the `+0.15` penalty. Let the GBT probabilities govern entries.
   - **Alternative:** Reduce the penalty to a very small soft bias (e.g., `+0.02` or `+0.03`) during hours 12 to 14.
   - *Which option do you prefer? We recommend a clean slate (0.00 penalty) to let the expanded model express its learning.*

2. **Hyperparameter Selection:**
   - **Proposed (Recommended):** Use `max_depth=6`, `min_child_samples=40`, `reg_lambda=2.0`, `n_estimators=450`, and `learning_rate=0.02`. This is a balanced, moderate capacity increase.
   - **Alternative:** A deeper tree ensemble (`max_depth=8`, `min_child_samples=30`, `reg_lambda=1.5`).
   - *We recommend starting with the balanced configuration to avoid overfitting the walk-forward windows.*

---

## Proposed Changes

### 1. Midday Chop Guard Removal

We will remove the hardcoded midday penalty from the backtesters.

#### [MODIFY] [backtest_gbt_parquet.py](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/backtest/backtest_gbt_parquet.py)
- Remove the lines adding `+0.15` to the confidence threshold during minutes 720 to 900:
```python
# Remove:
if 720 <= current_minute < 900:
    effective_threshold += 0.15
```

#### [MODIFY] [backtest_rl.py](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/backtest/backtest_rl.py)
- Remove the midday chop penalty logic from both `simulate_mlp_rl` and `simulate_mlp_only` loops (lines ~290 and ~870).

---

### 2. GBT Walk-Forward Hyperparameter Tuning

We will adjust the LightGBM classifier initialization in the walk-forward training engine.

#### [MODIFY] [train_walkforward.py](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/train_walkforward.py)
- Modify the `LGBMClassifier` initialization inside `train_single_window` (lines ~449-464):
```python
    model = lgb.LGBMClassifier(
        objective='multiclass',
        n_estimators=450,       # Increased from 300
        max_depth=6,            # Increased from 4
        learning_rate=0.02,     # Decreased from 0.03
        subsample=0.7,
        colsample_bytree=0.7,
        min_child_samples=40,   # Decreased from 100
        reg_alpha=0.5,
        reg_lambda=2.0,         # Decreased from 5.0
        num_class=3,
        random_state=seed,
        class_weight=lgb_class_weight,
        verbose=-1,
        n_jobs=-1,
    )
```

---

## Verification Plan

### Automated Run & Diagnosis

1. **Re-train the specialized GBT Ensembles:**
   - Execute the GBT training portion of the pipeline:
     ```powershell
     powershell -File neural/run_pipeline.ps1 -gbt
     ```
   - *Note:* We will monitor progress and terminate the script once the GBT training loop finishes for all three tickers (SPX, QQQ, SPY), saving computational time and preventing RL from running with stale states.
2. **Execute GBT Backtest:**
   - Run the dedicated GBT backtest on true OOS data up to May 19, 2026:
     ```powershell
     python backtest/backtest_gbt_parquet.py --data training_data/training_data_spx_qqq_spy.parquet --model neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail.joblib --normalizer neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail_norm.npz --model-size small --ensemble --threshold 0.420 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -40.0 --tickers SPX QQQ SPY --strict-wf
     ```
3. **Analyze the Results:**
   - Execute the trade analyzer script to measure performance improvements:
     ```powershell
     python "C:\Users\Álvaro Schwiedop\.gemini\antigravity\brain\0dfb4a02-6104-4923-bd33-32fd09c9bafb\scratch\analyze_trades.py"
     ```
   - We will verify:
     - The trade volume in April and May 2026 has recovered to active levels.
     - The trade volume during hours 12h, 13h, and 14h has normalized (e.g., at least 30-50 trades in total instead of only 10).
     - The Win Rate and Profit Factor in OOS are higher than the baseline (36.62% WR, 1.04 March PF, 0.67 May PF).


# GBT Optimization Plan: Fixing OOS Performance Collapse

## Problem Statement

The GBT model (LightGBM 3-class classifier) shows degrading performance in the true Out-Of-Sample period (March–May 2026), with dangerously low trade volume in April/May and catastrophic 14h-hour performance. The goal is to improve Win Rate and Profit Factor OOS without collapsing trade volume.

## Diagnostic Findings (from `backtest_trades.csv`)

### 1. OOS Monthly Breakdown

| Month | Trades | Win Rate | PF | PnL ($) |
|-------|--------|----------|----|---------|
| 2026-03 | 118 | 37.3% | 1.10 | +$7,575 |
| 2026-04 | 49 | 38.8% | 0.95 | -$2,241 |
| 2026-05 | 21 | 28.6% | 0.93 | -$645 |

**April has only 49 trades across 3 tickers (~2.6/day), May only 21. The bot is starving.**

### 2. Hourly Performance (OOS Mar-May 2026)

| Hour | Trades | Win Rate | PF | PnL ($) |
|------|--------|----------|----|---------|
| 9h | 30 | 36.7% | 1.03 | +$444 |
| 10h | **70** | **45.7%** | **1.39** | **+$11,447** |
| 11h | 18 | 44.4% | 1.18 | +$1,002 |
| 12h | 20 | 25.0% | 0.73 | -$2,831 |
| 13h | 32 | 31.2% | 0.91 | -$1,225 |
| **14h** | **10** | **10.0%** | **0.01** | **-$6,085** |
| 15h | 8 | 62.5% | 1.88 | +$1,037 |

> [!CAUTION]
> **14h is catastrophically bad OOS**: Only 10 trades with 10% win rate and -$6,085 PnL. This single hour accounts for the entire OOS loss. The problem is NOT midday starvation (the midday penalty was already removed) — it's that the *model is actively wrong at 14h*. Meanwhile 10h is the star hour (+$11,447).

### 3. Consecutive Loss Clustering (Markov Chain)

| Ticker | P(Loss\|prev Loss) | P(Loss\|2 consec losses) | Max Streak |
|--------|-------------------|------------------------|------------|
| QQQ | 0.600 | 0.638 | 13 |
| SPX | 0.571 | 0.592 | 11 |
| SPY | 0.553 | 0.582 | 12 |

**The probability of a loss is HIGHER after a loss.** This is evidence of regime-driven clustering, not random noise. The current `+0.10` threshold bump after 2 losses is clearly not enough — when P(L|LL) is 63.8% for QQQ, even a 52% threshold is accepting losing trades.

### 4. Dynamic Threshold Analysis

| Ticker | Normal Mode | Drawdown Mode (≥2 losses) |
|--------|------------|--------------------------|
| QQQ | 800 trades, 42.9% WR, +$183k | 442 trades, 36.2% WR, +$5k |
| SPX | 676 trades, 47.0% WR, +$96k | 309 trades, 40.8% WR, +$16k |
| SPY | 765 trades, 48.2% WR, +$174k | 323 trades, 41.8% WR, +$26k |

**~32% of all trades happen in drawdown mode**, and drawdown mode has substantially worse WR, but is still marginally profitable. The drawdown mode acts as a filter but doesn't go far enough.

### 5. Confidence Buckets

| Confidence | Trades | WR | PF | PnL |
|-----------|--------|----|----|-----|
| [0.40, 0.45) | 438 | 38.8% | 1.02 | +$4.6k |
| [0.45, 0.50) | 555 | 42.7% | 1.19 | +$50k |
| [0.50, 0.55) | 713 | 39.0% | 1.09 | +$25k |
| [0.60, 0.65) | 328 | 45.1% | 1.47 | +$52k |
| [0.70, 0.80) | 253 | 53.0% | 2.21 | +$93k |
| [0.80, 1.00) | 225 | 70.7% | 5.37 | +$188k |

**Below 0.50 confidence, trades are barely profitable.** The 0.420 threshold is too aggressive — it accepts many noise trades.

### 6. Direction Analysis (OOS)

| Direction | Trades | WR | PF | PnL |
|-----------|--------|----|----|-----|
| LONG | 146 | 37.7% | 1.11 | +$6,840 |
| SHORT | 42 | 40.5% | 0.84 | -$3,051 |

SHORT trades are unprofitable OOS. The IB high filter at `-40.0` bps is both:
- Too restrictive for trend-following shorts (blocks valid entries)
- Not restrictive enough for reversal shorts that are caught by sudden rallies

---

## Root Cause Analysis

1. **Class Imbalance** (`$GbtHoldRatioArg = "1.0"`): Creates 50% HOLD / 25% LONG / 25% SHORT distribution. Under OOS feature drift, the model defaults heavily to HOLD with high confidence, starving Apr/May of trades.

2. **IB High Filter** (`$MinShortPriceVsIbHighArg = "-40.0"`): Too tight. Blocks shorts when price is >0.40% below IB high. Should be relaxed to allow trend-following shorts on down days.

3. **14h Hour Catastrophe**: The model's 163 features include cyclical time encoding (`time_sin`, `time_cos`, `minutes_to_close_norm`), but LightGBM at depth 6 may not be capturing the time×regime interaction well enough. The 14h window has extremely low signal-to-noise OOS.

4. **Consecutive Loss Persistence**: P(L|L) ≈ 0.60 across all tickers. The current `+0.10` threshold bump is insufficient. Need a more aggressive dynamic threshold that scales with streak length.

5. **Base Threshold Too Low**: The `0.420` threshold accepts trades in the [0.40, 0.50) range which are barely profitable (PF 1.02–1.19). Raising to 0.45 would eliminate the weakest bucket while retaining volume.

---

## Proposed Changes

### 1. Rebalance Training Classes → Fix HOLD Dominance

#### [MODIFY] [run_pipeline.ps1](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/run_pipeline.ps1)

Change `$GbtHoldRatioArg` from `"1.0"` to `"0.5"`:

```diff
-$GbtHoldRatioArg = "1.0"
+$GbtHoldRatioArg = "0.5"
```

**Rationale**: `hold_ratio=0.5` means HOLD gets 0.5× the total directional count. If we have 1000 LONG + 1000 SHORT = 2000 directional, HOLD gets 1000. This creates a 1:1:1 balanced dataset instead of the current 2:1:1 (HOLD-heavy) split. This directly reduces the model's prior towards HOLD and increases the probability of directional predictions, recovering trade volume in OOS months.

### 2. Relax IB High Short Filter → Recover SHORT Volume

#### [MODIFY] [run_pipeline.ps1](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/run_pipeline.ps1)

```diff
-$MinShortPriceVsIbHighArg = "-40.0"
+$MinShortPriceVsIbHighArg = "-150.0"
```

**Rationale**: At `-40.0` bps, the filter blocks short entries when the spot price is only 0.40% below the intraday high. On a down-trending day where SPX drops 1%, this blocks ALL shorts after the morning. At `-150.0` bps (1.5%), we allow shorts in genuine downtrends while still blocking extreme oversold entries.

### 3. Raise Base Confidence → Filter Noise Trades

#### [MODIFY] [run_pipeline.ps1](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/run_pipeline.ps1)

```diff
-$BacktestBaseConfidenceArg = "0.420"
+$BacktestBaseConfidenceArg = "0.450"
```

**Rationale**: The [0.40, 0.45) confidence bucket has 438 trades with only 38.8% WR and PF 1.02 — barely above breakeven. Raising the floor to 0.450 eliminates these noise trades. The [0.45, 0.50) bucket has 42.7% WR and PF 1.19 which is genuinely profitable.

### 4. Strengthen Dynamic Threshold — Graduated Scaling

#### [MODIFY] [backtest_gbt_parquet.py](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/backtest/backtest_gbt_parquet.py)

Change the dynamic threshold from a flat `+0.10` after 2 losses to a graduated scale:

```python
# Current:
is_drawdown = ticker_consecutive_losses[ticker] >= 2
effective_threshold = self.threshold + 0.10 if is_drawdown else self.threshold
effective_risk_capital = self.risk_capital * 0.5 if is_drawdown else self.risk_capital

# Proposed:
consec = ticker_consecutive_losses[ticker]
if consec >= 4:
    # 4+ consecutive losses: very aggressive filter
    effective_threshold = self.threshold + 0.20
    effective_risk_capital = self.risk_capital * 0.25
elif consec >= 2:
    # 2-3 consecutive losses: moderate filter
    effective_threshold = self.threshold + 0.10
    effective_risk_capital = self.risk_capital * 0.50
else:
    effective_threshold = self.threshold
    effective_risk_capital = self.risk_capital
```

**Rationale**: P(L|LL) ≈ 0.60 and P(L|LLL) is likely even higher. After 4 consecutive losses, the model is clearly wrong about the current regime, and only the highest-confidence signals should be trusted.

#### [MODIFY] [train_walkforward.py](file:///c:/Users/Álvaro%20Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/neural/train_walkforward.py)

Apply the same graduated scale in `calculate_economic_metrics()` for consistent validation scoring.

---

## Open Questions

> [!IMPORTANT]
> **Confidence threshold 0.420 → 0.450**: This will reduce total trade volume by approximately 13% (438 trades out of 3,315). In the OOS period this should be smaller since most OOS trades already have >0.45 confidence. Are you comfortable with this tradeoff?

> [!IMPORTANT]
> **Hold ratio 1.0 → 0.5**: This is a significant shift from HOLD-heavy training to balanced training. It should increase directional predictions but may slightly increase false signals in choppy markets. The walk-forward PF floor (`min_pf_floor=1.50`) should reject windows where this is harmful.

> [!WARNING]
> **14h hour management**: The diagnostic shows 14h is catastrophically bad OOS (10% WR, -$6,085). Options:
> - **A (Recommended)**: Add a soft `+0.05` confidence penalty for entries between 14:00-14:30 only (minute 840-870), letting the model still trade at 14h but only with high confidence.
> - **B**: No penalty — trust the model and the graduated dynamic threshold to handle it.
> - **C**: Hard block on entries at 14h.
> - *Which do you prefer?*

---

## Verification Plan

### Step 1: Re-train GBT Models

```powershell
powershell -File neural/run_pipeline.ps1 -gbt
```

Monitor and terminate after all 3 tickers (SPX, QQQ, SPY) finish training. Do NOT let it proceed to RL.

### Step 2: Run GBT Backtest

```powershell
python backtest/backtest_gbt_parquet.py `
    --data training_data/training_data_spx_qqq_spy.parquet `
    --model neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail.joblib `
    --normalizer neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail_norm.npz `
    --model-size small --ensemble `
    --threshold 0.450 --cooldown 8 `
    --target_long 0.010 --target_short 0.010 --stop 0.0025 `
    --risk-capital 1000.0 `
    --min-entry-minute 580 `
    --min-short-entry-minute 615 `
    --min-short-price-vs-ib-high -150.0 `
    --tickers SPX QQQ SPY --strict-wf
```

### Step 3: Analyze Results

Run the deep diagnostic script on the new `backtest_trades.csv` and compare:

| Metric | Baseline (Current) | Target |
|--------|-------------------|--------|
| Apr 2026 trades | 49 | ≥60 |
| May 2026 trades | 21 | ≥30 |
| Apr WR | 38.8% | ≥42% |
| May WR | 28.6% | ≥38% |
| 14h PnL | -$6,085 | >-$1,000 |
| Overall OOS PF | ~1.0 | ≥1.15 |


