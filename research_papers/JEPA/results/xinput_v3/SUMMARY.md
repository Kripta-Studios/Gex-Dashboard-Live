# xinput_v3 JEPA Result Summary

Gate A failed, but this is the strongest JEPA variant so far.

## Architecture

This run implements an explicit exogenous-input Market JEPA:

```text
state_encoder(current market state) -> z_t
input_encoder(dynamic Greek/IV/price changes) -> u_t
predictor(z_t, u_t, horizon) -> z_hat_{t+h}
```

State features: 155 current-state features.

Input/delta features: 25 dynamic features:

`gamma_change`, `vanna_change`, `dgex_change`, `delta_change`, `vega_change`, `vomma_change`, `spot_change`, `gamma_momentum`, `signal_persistence_5m`, `momentum_5m_bps`, `ret_1m_vol_adj`, `ret_5m_vol_adj`, `ret_15m_vol_adj`, `tlt_ret_1m`, `tlt_ret_5m`, `tlt_ret_15m`, `gamma_speed`, `charm_accel_weighted`, `gamma_phase_delta`, `pcr_derivative_5m`, `rvol_trend`, `rvol_regime`, `iv_zscore`, `iv_percentile`, `vix_5d_std`.

## Full Strict-WF Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 3,545 | 49.6% | 1.305 | +367,372 | -17,217 |
| GBT + XInputJEPA | 3,843 | 51.1% | 1.335 | +439,787 | -18,997 |
| XInputJEPA-only | 3,967 | 49.6% | 1.197 | +279,232 | -27,146 |
| GBT + XInputJEPA permuted | 4,233 | 47.2% | 1.109 | +168,118 | -33,559 |

## Apr/May 2026 OOS Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 213 | 49.8% | 1.300 | +23,980 | -8,074 |
| GBT + XInputJEPA | 227 | 48.0% | 1.094 | +8,763 | -6,154 |
| XInputJEPA-only | 249 | 54.6% | 1.406 | +34,800 | -6,479 |
| GBT + XInputJEPA permuted | 230 | 50.4% | 1.355 | +28,544 | -5,872 |

## Feature Usage

LightGBM used XInputJEPA features meaningfully:

| Ticker | XInputJEPA feature-importance share |
| --- | ---: |
| SPX | 14.28% |
| QQQ | 16.12% |
| SPY | 15.53% |

Top features included `xjepa_direction_score`, several `xjepa_z_*` latents, and `xjepa_u_06`.

## Direct Predictive Capacity

Diagnostic report: `research_papers/JEPA/results/xinput_v3/predictive_diagnostics/SUMMARY.md`

The direct diagnostic compared predicted future latent states against the observed future latent states, with a persistence baseline that assumes `z_{t+h} = z_t`.

OOS latent prediction versus persistence:

| Horizon | Model MSE | Persistence MSE | Improvement | Beat persistence |
| --- | ---: | ---: | ---: | ---: |
| 5m | 0.02583 | 0.00452 | -471.6% | 0.6% |
| 15m | 0.04196 | 0.01984 | -111.4% | 5.4% |
| 30m | 0.06555 | 0.04630 | -41.6% | 12.5% |
| 60m | 0.10274 | 0.09452 | -8.7% | 28.3% |
| 120m | 0.16923 | 0.17983 | +5.9% | 51.0% |
| 180m | 0.21221 | 0.26241 | +19.1% | 65.5% |

OOS direction-head metrics:

- Balanced accuracy: 41.5%
- Long AUC: 0.722
- Short AUC: 0.424
- Trade-vs-hold AUC: 0.606
- Direction Spearman: 0.128

Trade-level JEPA alignment was weak OOS:

- `GBT+XInputJEPA`: alignment AUC for winner/loss separation 0.546.
- `XInputJEPA-only`: alignment AUC for winner/loss separation 0.519.

Exact 180m terminal spot direction:

| Segment | Rows | Future up rate | Sign accuracy | AUC up | Spearman to return | Top-quintile return | Bottom-quintile return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full history | 56,140 | 55.4% | 60.6% | 0.641 | 0.255 | +25.60 bps | -4.55 bps |
| Apr/May OOS | 2,200 | 63.1% | 49.0% | 0.545 | 0.119 | +11.93 bps | +1.27 bps |

Conclusion: XInputJEPA learned some slower future-state structure, especially at 120-180 minutes, but the exact 180m up/down signal degraded sharply OOS. It is not enough evidence to say the model can reliably operate futures or options on a 180m forecast yet. It should be treated as a candidate medium-horizon regime/side signal that needs a dedicated 180m trading backtest.

Follow-up dedicated 180m experiment: `research_papers/JEPA/results/jepa_180m_direction/SUMMARY.md`

- Reframing the task as `spot_price(t+180m) > spot_price(t)` and training a dedicated walk-forward classifier improved the result.
- Apr/May 2026 OOS `base_jepa` beat `base` on AUC (0.623 vs 0.617), fixed-hold PF (1.886 vs 1.591), and fixed-hold PnL (+8,707 vs +5,596 at $100k notional, 1 bps cost).
- This supports continuing a separate JEPA-180m module, but not promoting the earlier GBT target/stop augmentation.

## Decision

Do not promote `xinput_v3`.

Reasons:

- Full strict-WF improved PF and PnL, but max drawdown worsened by 10.3%, just over the 10% gate.
- Apr/May OOS GBT + XInputJEPA was materially worse than baseline: PF 1.094 vs 1.300.
- OOS permutation beat the unpermuted GBT + XInputJEPA candidate, so the live value is not stable.
- XInputJEPA-only OOS was strong, but full-history XInputJEPA-only did not beat baseline.

This architecture is directionally more promising than previous tabular JEPA variants, but it needs a stronger input encoder, better OOS calibration, or raw option-surface inputs before it can be considered again.
