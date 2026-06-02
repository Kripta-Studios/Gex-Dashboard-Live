# Frozen Base+JEPA 180m Candidate

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Rows after exact 180m label construction: 56,220 from 222,069
Train cutoff: `20260331`
Test start: `20260401`
Label: `spot_price(t+180m) > spot_price(t)`
Backtest: fixed 180m hold, cooldown `36` samples, base cost `1.0` bps, notional `$100,000`.

## Prediction Metrics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 2280 | 63.5% | 60.7% | 0.629 | 62.9% | 60.7% | 0.186 | 11.42 | -0.81 |
| jepa_only | 2280 | 63.5% | 51.2% | 0.579 | 56.1% | 56.2% | 0.125 | 12.19 | 3.22 |
| base_jepa | 2280 | 63.5% | 56.1% | 0.639 | 62.3% | 61.5% | 0.224 | 14.11 | -0.47 |

## Fixed-Hold 180m Backtest

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 82 | 59.8% | 1.479 | 5.28 | +4,333 | -1,640 | 65.9% |
| jepa_only | 113 | 59.3% | 1.346 | 4.08 | +4,614 | -3,514 | 53.1% |
| base_jepa | 107 | 69.2% | 2.031 | 9.31 | +9,963 | -1,522 | 64.5% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 82 | 59.8% | 1.479 | 5.28 | +4,333 | -1,640 |
| 1 bps | jepa_only | 113 | 59.3% | 1.346 | 4.08 | +4,614 | -3,514 |
| 1 bps | base_jepa | 107 | 69.2% | 2.031 | 9.31 | +9,963 | -1,522 |
| 3 bps | base | 82 | 57.3% | 1.277 | 3.28 | +2,693 | -1,920 |
| 3 bps | jepa_only | 113 | 59.3% | 1.165 | 2.08 | +2,354 | -3,934 |
| 3 bps | base_jepa | 107 | 66.4% | 1.755 | 7.31 | +7,823 | -1,562 |
| 5 bps | base | 82 | 56.1% | 1.101 | 1.28 | +1,053 | -2,441 |
| 5 bps | jepa_only | 113 | 58.4% | 1.006 | 0.08 | +94 | -4,354 |
| 5 bps | base_jepa | 107 | 65.4% | 1.513 | 5.31 | +5,683 | -1,625 |
| 10 bps | base | 82 | 50.0% | 0.754 | -3.72 | -3,047 | -4,648 |
| 10 bps | jepa_only | 113 | 49.6% | 0.687 | -4.92 | -5,556 | -6,134 |
| 10 bps | base_jepa | 107 | 56.1% | 1.025 | 0.31 | +333 | -2,086 |

## Decision

- This is the strict frozen-candidate test: all Apr/May predictions use models trained only through the cutoff.
- `future_return_180m` is used only for labels/backtest outcome and is excluded from features.
- If `base_jepa` beats `base` here, it is a credible replacement candidate for the current 180m entry model; if it fails, the monthly-retrained result was too optimistic.
