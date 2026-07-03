# Proposition: Should We Use JEPA / LeWorldModel in This Trading Pipeline?

## Current Production Note - 2026-07

The conclusion still holds: do not replace the live stack with a literal LeWorldModel-style controller. The current production system is the event-option static-union package:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
policy: event_option_frozen2025_static_union_balanced_202607
```

New JEPA, SIGReg, VISReg, XInputJEPA, or RL work must be evaluated as an auxiliary or replacement candidate against this package, using the same walk-forward, leakage, live-equivalence, and systemd smoke checks.

## Executive Conclusion

Do not replace the current GBT + RL pipeline with a literal LeWorldModel architecture.

LeWorldModel is designed for action-conditioned physical control from pixels: the agent chooses actions, those actions causally change the future observation, and the model plans action sequences in latent space. Our trading action does not causally change SPX, QQQ, SPY, VIX, or the option chain. It changes only our portfolio payoff. That breaks the core control assumption behind LeWorldModel-style MPC.

However, JEPA is still relevant. The right adaptation is a small tabular/time-series LeJEPA used as an auxiliary representation learner. It should learn compact latent states from market/options trajectories, export latent features and prediction-surprise features, and feed those into the existing walk-forward LightGBM and, later, the RL state. This is a research add-on, not a production replacement.

Recommended path:

1. Keep the current GBT as the judge and baseline.
2. Pretrain a small Temporal Tabular LeJEPA on existing market/options feature sequences.
3. Add its latent features to the GBT training data.
4. Run the exact same strict walk-forward and true OOS backtests.
5. Promote only if it improves PF/PnL without collapsing trade volume or increasing drawdown.

## Current Pipeline Readout

The orchestrator is `neural/run_pipeline.ps1`.

The important flow is:

1. Step 0 collects SPX, QQQ, and SPY data into `training_data/training_data_spx_qqq_spy.parquet`.
2. It creates a March-2026 true OOS cutoff file: `training_data/training_data_spx_qqq_spy_march_2026.parquet`.
3. Step 1 trains ticker-specific LightGBM walk-forward models.
4. Step 2 generates the RL episode index from GBT signals.
5. Step 3 builds an RL options cache.
6. Step 4 trains PPO.
7. Steps 6 and 7 backtest GBT-only and GBT+RL.

The currently promoted GBT configuration is strong enough that the RL layer is the weak link, not the entry model. The backtest logs show:

- GBT-only full backtest: 3,545 trades, 49.6% WR, PF 1.305, PnL about +367k, max drawdown about -17k.
- Recent GBT+RL v7 variants: 4,122 to 5,820 trades, PF about 1.08 to 1.15, PnL materially below GBT-only, max drawdown much worse.

That means the next model research should not disrupt GBT selection until it proves incremental value.

## Data We Actually Have

The collector is `neural/collect_training_data_spx_qqq.py`.

Data sources:

- Underlying minute OHLC from `D:\ThetaData\data_underlying_derived`.
- SPX uses `SPXW`; ETFs use `QQQ` and `SPY`.
- 0DTE and weekly option chain Greeks from `D:\ThetaData\data_options`.
- Open interest files for daily and weekly option chains.
- 0DTE option OHLC/volume when available.
- VIX underlying data and VIX weekly option gamma.
- TLT intraday proxy data.
- Historical IB levels from recent days.
- Calendar/opex context, gap features, realized-vs-implied vol, Wonham trend probability, Hilbert phase, support/resistance proximity, Greek wall confluences, PCR proxy, and Greek dynamics.

Output data observed locally:

- Full parquet: 221,753 rows, 190 columns, 959 trading dates, 3 tickers.
- March cutoff parquet: 213,063 rows, 190 columns, through 2026-03-31.
- Per ticker-day: 79 samples, meaning a 5-minute grid across the session.
- Target distribution full data:
  - SHORT: 43,869
  - HOLD: 130,001
  - LONG: 47,883
- RL episode index: 39,219 rows through 2026-03-31.

The model feature surface is tabular and engineered, not pixels. The stable production feature list is `FEATURE_COLUMNS` in `neural/hybrid_model.py`, around 163 features.

Important label detail: labels are not generic next-bar direction. A row becomes LONG/SHORT only when price is near a support/resistance or vanna-magnet context, and the future path hits a ticker-specific target before the stop within a 180-minute lookahead. Otherwise the target is HOLD. This makes the learning problem event-driven and asymmetric, which is good for trading but important for JEPA design.

## Current Model Architecture

The current entry model is LightGBM, not the legacy PyTorch hybrid model.

From `neural/train_walkforward.py` and `neural/run_pipeline.ps1`:

- Ticker-specific models for SPX, QQQ, and SPY.
- Walk-forward split: 12 train months, 1 test month.
- Ensemble per window, top windows selected by economic PF/recency.
- SPX uses multiclass; QQQ and SPY use binary one-vs-rest.
- Small LightGBM config: 500 trees, max depth 6, learning rate 0.02, subsample 0.5, colsample 0.5, alpha 2.0, lambda 5.0.
- Class balancing keeps directional examples and undersamples HOLD.
- Selection and ranking are based on deployed economic simulation, not just label accuracy.

The RL policy in `neural/rl/agent.py` is a compact PPO MLP:

- State dimension about 185: 163 market features, 8 dynamic option-cache features, 7 position features, 4 GBT context features, 3 ticker one-hot features.
- Backbone: 256 -> 256 -> 128 with LayerNorm/GELU/dropout.
- Heads: strike bucket, exit HOLD/EXIT, sniper/entry-skip, and critic value.
- Current PPO model has about 181k parameters.

The RL environment does not simulate market impact. It replays historical option paths from the cache and lets the agent choose strike/entry skip/exit. This is correct for trading, but it is not the same control setting as LeWorldModel.

## Does LeWorldModel Make Sense Here?

Literal LeWorldModel: no.

Reasons:

1. LeWorldModel assumes action-conditioned dynamics: `z_{t+1} = pred(z_t, action_t)`. In trading, our trade action does not affect the future market state.

2. LeWorldModel learns from raw pixels. Our data is already structured tabular market state and option-chain aggregates. We do not need a ViT pixel encoder as the first implementation.

3. LeWorldModel plans by optimizing actions to reach a goal observation. For this system, there is no controllable market goal observation. We can choose payoff exposure, not the future state of SPX.

4. Our data size is moderate. 221k rows is useful for small sequence models, but not enough to justify a large end-to-end foundation-style world model. The current LightGBM is data-efficient and already strong.

5. The theory paper `When Does LeJEPA Learn a World Model?` warns that the clean guarantee needs stationary additive-noise Gaussian latents. Markets are nonstationary, heavy-tailed, path-dependent, and regime-shifting.

But LeJEPA-style predictive representation learning does make sense.

The correct analogy is:

- Observation: market/options feature vector at time `t`.
- Latent state: learned compact representation of current market microstructure/regime.
- Prediction: future latent state at multiple horizons.
- Regularization: SIGReg to prevent collapse and keep latent dimensions usable.
- Downstream use: GBT/RL receives latent features, latent velocity, and prediction error/surprise.

## Why It Could Improve Results

The existing GBT sees a strong engineered snapshot, plus some handcrafted short-history features. It does not learn a reusable latent sequence state from the full intraday trajectory.

A small temporal JEPA could add:

- A learned state representation of option-surface evolution.
- Multi-horizon context aligned with the 180-minute label/backtest horizon.
- Prediction-surprise features that identify regime shifts where GBT confidence is less reliable.
- Latent velocity and curvature features that capture transitions, not only current levels.
- Representation pretraining from all rows, including HOLD rows, without needing more labels.

This is especially attractive because individual Spearman correlations between numeric features and target are small. The edge is likely nonlinear, conditional, and sequence-dependent. LightGBM handles nonlinear tabular interactions well, but it can only use the features we give it.

## Why It Might Fail

The risk is real.

- The current engineered features already encode a lot of domain structure.
- A self-supervised objective may learn time of day, VIX level, or ticker identity without learning tradable alpha.
- Positive-pair design can easily encode the wrong invariance.
- SIGReg's Gaussian assumption is only approximate for market states.
- Deep sequence models can overfit walk-forward windows.
- If JEPA features are trained with future leakage, they will look great and fail in true OOS.

Therefore the first JEPA experiment must be small, additive, and judged only by strict walk-forward backtest.

## Proposed Architecture: Temporal Tabular LeJEPA

Input:

- Per ticker-day sequence of 5-minute samples.
- Use the 163 `FEATURE_COLUMNS` only.
- Add ticker one-hot only inside the JEPA model or as a conditioning vector, not as a leakage-prone ID shortcut.
- Sequence length: start with 24 steps, equal to 120 minutes.
- Predict horizons: 1, 3, 6, 12, 24, and 36 steps, equal to 5, 15, 30, 60, 120, and 180 minutes.

Encoder:

- Start simple: 2-layer GRU, TCN, or a small Transformer encoder.
- Embedding dimension: 32 or 64.
- Parameter budget: keep below 1M for the first experiment.

Predictor:

- MLP or small temporal predictor from `z_t` to `z_{t+h}` for each horizon.
- No trade action conditioning.
- Optional conditioning on ticker, time-of-day embedding, and VIX regime.

Loss:

```text
L = (1 - lambda) * sum_h MSE(pred_h(z_t), z_{t+h})
    + lambda * SIGReg(z_t)
```

Recommended first grid:

- `lambda`: 0.03, 0.05, 0.10
- `z_dim`: 32, 64
- context length: 12 and 24 steps
- horizons: at minimum 5, 30, 60, 180 minutes

Exported features:

- `jepa_z_00 ... jepa_z_31` or `jepa_z_63`
- `jepa_surprise_5m`, `jepa_surprise_30m`, `jepa_surprise_60m`, `jepa_surprise_180m`
- `jepa_latent_velocity`
- `jepa_latent_accel`
- `jepa_pred_consistency`, for agreement between short-horizon and long-horizon predicted latents

These features should be appended to the parquet and then passed into the existing LightGBM training path.

## Better Phase-2 Architecture: Option Surface LeJEPA

The tabular feature vector is already compressed. A bigger opportunity is the raw option chain.

Instead of only net gamma/vanna/charm and max/min strike levels, build a per-minute option-surface tensor:

- Buckets by moneyness or delta.
- Separate channels for calls/puts.
- Separate daily 0DTE and weekly expiry views.
- Features per bucket: IV, OI, volume, gamma, delta, vanna, charm, dgex, vega, vomma.

Then train a set/curve encoder with SIGReg to predict future option-surface embeddings. This could recover information lost by the handcrafted aggregate features.

This is more expensive and should be phase 2 only if the small tabular JEPA shows signal.

## Pipeline Integration Plan

Add a new optional step between collection and GBT training:

```text
Step 0: collect_training_data_spx_qqq.py
Step 0.5: train_temporal_jepa.py
Step 0.6: append_jepa_features.py
Step 1: train_walkforward.py using augmented parquet
```

Suggested files:

- `neural/jepa/sigreg.py`
- `neural/jepa/model.py`
- `neural/jepa/train_temporal_jepa.py`
- `neural/jepa/append_jepa_features.py`
- `neural/jepa/diagnose_jepa_features.py`

Initial proof-of-concept should train only on the March cutoff:

- Train JEPA on `training_data_spx_qqq_spy_march_2026.parquet`.
- Generate latents for the March cutoff and full parquet.
- Train GBT on March cutoff with JEPA features.
- Backtest full data through May 2026 with the existing true OOS policy.

If this works, the stricter version is per-window JEPA training inside each walk-forward window. That is cleaner but more engineering work.

## Validation Criteria

The only acceptable judge is the same backtest discipline already used by the project.

Primary comparison:

- Baseline: current GBT-only strict-WF.
- Candidate: GBT-only strict-WF with JEPA features.

Promotion criteria:

- Profit Factor improves by at least +0.05 absolute, or PnL improves by at least +10%.
- Trade count remains at least 90% of baseline unless PF improves materially.
- Max drawdown does not worsen by more than 10%.
- Improvement appears in at least two of SPX, QQQ, SPY, or the losing ticker is explicitly contained by a predeclared rule.
- April/May 2026 true OOS remains positive.

Diagnostics before backtesting:

- Check embedding collapse: covariance spectrum should not be rank-deficient.
- Check SIGReg loss and prediction loss separately.
- Check whether training loss correlates with downstream validation PF.
- Check feature importances: GBT should use JEPA features, but not only ticker/time shortcuts.
- Check surprise by regime: high surprise should correspond to lower GBT reliability or larger realized moves.

## How It Could Help RL

Do not start by replacing PPO.

If the GBT experiment works, then try these RL uses:

1. Add `jepa_z` and `jepa_surprise` to the RL state.
2. Penalize entries in high-surprise states unless GBT confidence is very high.
3. Use prediction error as a volatility/regime shock feature for exit decisions.
4. Pretrain the RL critic on JEPA latent state plus realized option payoff.

Avoid using JEPA as a model-predictive planner for trade actions. The market will not move differently because the agent bought an option.

## Recommendation

Build a Temporal Tabular LeJEPA prototype, not LeWorldModel-from-pixels.

The expected value is positive because:

- The data is sequential and mostly unlabeled.
- The current labels are noisy and event-driven.
- The current GBT can absorb additive latent features with low implementation risk.
- SIGReg gives a principled anti-collapse method.
- Prediction surprise is directly useful as a confidence/risk filter.

The expected value of a full LeWorldModel port is low because:

- It solves the wrong causal problem.
- It requires a heavier architecture than the data supports.
- It would complicate a pipeline whose current GBT baseline is already profitable.

Best first experiment:

Train a sub-1M parameter, actionless Temporal LeJEPA on the March-2026 cutoff, append 32 latent and 4 surprise features, rerun the exact current GBT-only backtest, and accept or reject based on strict true OOS PF/PnL/drawdown.
