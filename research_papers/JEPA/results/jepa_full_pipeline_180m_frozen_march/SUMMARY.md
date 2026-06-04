# Frozen Base+JEPA 180m Candidate

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Rows after max/EOD-truncated 180m label construction: 154,935 from 222,543
Train cutoff: `20260331`
Test start: `20260401`
Label: `spot_price(min(t+180m, same-day last row)) > spot_price(t)`
Backtest: max 180m hold truncated to same-day last row, cooldown `36` samples, base cost `1.0` bps, notional `$100,000`.

## Prediction Metrics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 6600 | 64.3% | 47.8% | 0.587 | 55.2% | 56.3% | 0.162 | 10.94 | 2.31 |
| jepa_only | 6600 | 64.3% | 50.3% | 0.500 | 49.9% | 49.8% | 0.014 | 7.05 | 7.91 |
| base_jepa | 6600 | 64.3% | 42.9% | 0.578 | 52.0% | 54.4% | 0.169 | 11.41 | 1.28 |

## Fixed-Hold 180m Backtest

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 188 | 50.5% | 1.021 | 0.23 | +426 | -2,778 | 44.7% |
| jepa_only | 205 | 50.7% | 1.169 | 1.75 | +3,592 | -4,342 | 54.6% |
| base_jepa | 179 | 54.2% | 1.405 | 3.78 | +6,767 | -2,255 | 49.7% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 188 | 50.5% | 1.021 | 0.23 | +426 | -2,778 |
| 1 bps | jepa_only | 205 | 50.7% | 1.169 | 1.75 | +3,592 | -4,342 |
| 1 bps | base_jepa | 179 | 54.2% | 1.405 | 3.78 | +6,767 | -2,255 |
| 3 bps | base | 188 | 45.2% | 0.850 | -1.77 | -3,334 | -5,009 |
| 3 bps | jepa_only | 205 | 47.3% | 0.978 | -0.25 | -508 | -5,626 |
| 3 bps | base_jepa | 179 | 52.0% | 1.173 | 1.78 | +3,187 | -2,715 |
| 5 bps | base | 188 | 41.5% | 0.709 | -3.77 | -7,094 | -7,927 |
| 5 bps | jepa_only | 205 | 44.9% | 0.820 | -2.25 | -4,608 | -7,890 |
| 5 bps | base_jepa | 179 | 50.3% | 0.980 | -0.22 | -393 | -3,194 |
| 10 bps | base | 188 | 35.1% | 0.451 | -8.77 | -16,494 | -16,655 |
| 10 bps | jepa_only | 205 | 39.5% | 0.528 | -7.25 | -14,858 | -16,476 |
| 10 bps | base_jepa | 179 | 43.6% | 0.624 | -5.22 | -9,343 | -9,583 |

## Decision

- This is the strict frozen-candidate test: all OOS predictions use models trained only through the cutoff.
- `future_return_180m` is used only for labels/backtest outcome and is excluded from features.
- If `base_jepa` beats `base` here, it is a credible replacement candidate for the current 180m entry model; if it fails, the monthly-retrained result was too optimistic.
