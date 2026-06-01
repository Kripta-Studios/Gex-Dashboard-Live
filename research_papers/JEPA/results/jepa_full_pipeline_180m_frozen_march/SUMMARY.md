# Frozen Base+JEPA 180m Candidate

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Rows after exact 180m label construction: 56,160 from 221,832
Train cutoff: `20260331`
Test start: `20260401`
Label: `spot_price(t+180m) > spot_price(t)`
Backtest: fixed 180m hold, cooldown `36` samples, base cost `1.0` bps, notional `$100,000`.

## Prediction Metrics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 2220 | 62.6% | 60.1% | 0.626 | 62.3% | 60.4% | 0.183 | 10.82 | -0.67 |
| jepa_only | 2220 | 62.6% | 51.0% | 0.579 | 55.9% | 56.0% | 0.129 | 12.29 | 2.47 |
| base_jepa | 2220 | 62.6% | 55.4% | 0.636 | 61.8% | 61.1% | 0.222 | 13.89 | -0.66 |

## Fixed-Hold 180m Backtest

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 80 | 58.8% | 1.389 | 4.40 | +3,522 | -1,640 | 65.0% |
| jepa_only | 110 | 59.1% | 1.333 | 3.86 | +4,245 | -3,270 | 52.7% |
| base_jepa | 105 | 68.6% | 1.945 | 8.70 | +9,132 | -1,522 | 63.8% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 80 | 58.8% | 1.389 | 4.40 | +3,522 | -1,640 |
| 1 bps | jepa_only | 110 | 59.1% | 1.333 | 3.86 | +4,245 | -3,270 |
| 1 bps | base_jepa | 105 | 68.6% | 1.945 | 8.70 | +9,132 | -1,522 |
| 3 bps | base | 80 | 56.2% | 1.198 | 2.40 | +1,922 | -1,920 |
| 3 bps | jepa_only | 110 | 59.1% | 1.150 | 1.86 | +2,045 | -3,490 |
| 3 bps | base_jepa | 105 | 65.7% | 1.679 | 6.70 | +7,032 | -1,562 |
| 5 bps | base | 80 | 55.0% | 1.031 | 0.40 | +322 | -2,441 |
| 5 bps | jepa_only | 110 | 58.2% | 0.989 | -0.14 | -155 | -3,753 |
| 5 bps | base_jepa | 105 | 64.8% | 1.445 | 4.70 | +4,932 | -1,625 |
| 10 bps | base | 80 | 48.8% | 0.704 | -4.60 | -3,678 | -5,099 |
| 10 bps | jepa_only | 110 | 49.1% | 0.670 | -5.14 | -5,655 | -5,638 |
| 10 bps | base_jepa | 105 | 55.2% | 0.976 | -0.30 | -318 | -2,086 |

## Decision

- This is the strict frozen-candidate test: all Apr/May predictions use models trained only through the cutoff.
- `future_return_180m` is used only for labels/backtest outcome and is excluded from features.
- If `base_jepa` beats `base` here, it is a credible replacement candidate for the current 180m entry model; if it fails, the monthly-retrained result was too optimistic.
