# alpha_v2 JEPA Result Summary

Gate A failed, but alpha_v2 was materially better than tabular_v1.

## What Changed vs tabular_v1

- Latent dimension reduced to 16.
- Stop-gradient target enabled.
- SIGReg weight increased.
- VICReg-style variance/covariance latent-health regularizer added.
- Auxiliary HOLD/SHORT/LONG trading head added.
- Apr/May 2026 OOS backtests added.

## Full Strict-WF Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 3,545 | 49.6% | 1.305 | +367,372 | -17,217 |
| GBT + AlphaJEPA | 3,787 | 50.5% | 1.301 | +390,076 | -22,373 |
| AlphaJEPA-only | 4,139 | 46.9% | 1.073 | +111,098 | -40,426 |
| GBT + AlphaJEPA permuted | 4,152 | 48.1% | 1.143 | +212,521 | -32,445 |

## Apr/May 2026 OOS Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 213 | 49.8% | 1.300 | +23,980 | -8,074 |
| GBT + AlphaJEPA | 234 | 51.7% | 1.292 | +25,430 | -7,913 |
| AlphaJEPA-only | 256 | 52.0% | 1.423 | +38,487 | -9,307 |
| GBT + AlphaJEPA permuted | 235 | 51.9% | 1.352 | +30,283 | -7,556 |

## Interpretation

- GBT + AlphaJEPA increased full-history PnL by about +22.7k but reduced PF and worsened drawdown by about 30%.
- OOS GBT + AlphaJEPA improved PnL by only about +1.45k and reduced PF.
- AlphaJEPA-only OOS was strong, but full-history AlphaJEPA-only remained much weaker than baseline.
- Feature permutation suggests some full-history signal, but OOS permutation beat the unpermuted candidate.

## Decision

Do not promote alpha_v2.

The result is interesting enough to preserve, especially the AlphaJEPA-only OOS behavior, but it is not robust enough for production or for replacing RL.

