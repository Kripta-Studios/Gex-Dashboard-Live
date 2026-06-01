# alpha_v2_topk8 JEPA Result Summary

Gate A failed.

This run tested whether AlphaJEPA v2 was failing because too many latent columns diluted the GBT. It selected the union of the top 8 AlphaJEPA features per ticker, producing 13 AlphaJEPA columns, then trained GBT on base features plus those Top-K features.

## Selected AlphaJEPA Features

`ajepa_z_03`, `ajepa_z_15`, `ajepa_z_06`, `ajepa_pred_dispersion_short`, `ajepa_z_14`, `ajepa_z_07`, `ajepa_direction_score`, `ajepa_prob_hold`, `ajepa_z_08`, `ajepa_z_05`, `ajepa_z_00`, `ajepa_entropy`, `ajepa_z_02`

## Full Strict-WF Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 3,545 | 49.6% | 1.305 | +367,372 | -17,217 |
| GBT + AlphaJEPA Top-K | 3,858 | 48.8% | 1.213 | +290,583 | -31,268 |
| AlphaJEPA-only | 4,139 | 46.9% | 1.073 | +111,098 | -40,426 |
| GBT + AlphaJEPA Top-K permuted | 4,201 | 47.8% | 1.123 | +187,880 | -33,418 |

## Apr/May 2026 OOS Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 213 | 49.8% | 1.300 | +23,980 | -8,074 |
| GBT + AlphaJEPA Top-K | 226 | 48.7% | 1.195 | +16,948 | -11,273 |
| AlphaJEPA-only | 256 | 52.0% | 1.423 | +38,487 | -9,307 |
| GBT + AlphaJEPA Top-K permuted | 242 | 49.2% | 1.270 | +24,157 | -10,449 |

## Decision

Do not promote Top-K AlphaJEPA.

Top-K did not solve feature dilution. It worsened both full-history and OOS performance versus the baseline.

