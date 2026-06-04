# Production Base+JEPA 180m Artifacts

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_production_20261230_jepa_xinput_v3_production.parquet`
Rows after max/EOD-truncated 180m label construction: 154,935 from 222,543
Production cutoff: `20261230`
Label: `spot_price(min(t+180m, same-day last row)) > spot_price(t)`
Backtest diagnostic: max 180m hold truncated to same-day last row, cooldown `36` samples, base cost `1.0` bps, notional `$100,000`.

## Important

- These are final production artifacts trained on all eligible rows up to the cutoff.
- The metrics below are model-history diagnostics only. They are not OOS validation and must not be used as a promotion claim.
- The OOS evidence remains the locked research pipeline that trained through March 2026 and tested April/May 2026.
- `future_return_180m` and derived columns are labels/outcomes only and are excluded from model features.

## Prediction Diagnostics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 154935 | 53.6% | 53.0% | 0.951 | 88.5% | 88.5% | 0.814 | 37.93 | -41.82 |
| jepa_only | 154935 | 53.6% | 51.7% | 0.881 | 80.4% | 80.4% | 0.682 | 31.00 | -34.88 |
| base_jepa | 154935 | 53.6% | 53.2% | 0.953 | 89.1% | 89.0% | 0.819 | 37.84 | -41.46 |

## Fixed-Hold 180m Diagnostic

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 5241 | 86.9% | 15.326 | 25.68 | +1,345,889 | -1,362 | 53.7% |
| jepa_only | 5455 | 79.7% | 6.803 | 21.83 | +1,190,797 | -2,375 | 52.7% |
| base_jepa | 5500 | 87.7% | 17.117 | 26.09 | +1,434,780 | -1,362 | 54.6% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 5241 | 86.9% | 15.326 | 25.68 | +1,345,889 | -1,362 |
| 1 bps | jepa_only | 5455 | 79.7% | 6.803 | 21.83 | +1,190,797 | -2,375 |
| 1 bps | base_jepa | 5500 | 87.7% | 17.117 | 26.09 | +1,434,780 | -1,362 |
| 3 bps | base | 5241 | 82.9% | 12.312 | 23.68 | +1,241,069 | -1,394 |
| 3 bps | jepa_only | 5455 | 75.9% | 5.715 | 19.83 | +1,081,697 | -2,471 |
| 3 bps | base_jepa | 5500 | 83.7% | 13.639 | 24.09 | +1,324,780 | -1,382 |
| 5 bps | base | 5241 | 78.8% | 9.750 | 21.68 | +1,136,249 | -1,454 |
| 5 bps | jepa_only | 5455 | 72.5% | 4.775 | 17.83 | +972,597 | -2,632 |
| 5 bps | base_jepa | 5500 | 80.0% | 10.731 | 22.09 | +1,214,780 | -1,402 |
| 10 bps | base | 5241 | 67.6% | 5.379 | 16.68 | +874,199 | -1,604 |
| 10 bps | jepa_only | 5455 | 62.2% | 3.017 | 12.83 | +699,847 | -4,005 |
| 10 bps | base_jepa | 5500 | 68.4% | 5.802 | 17.09 | +939,780 | -1,452 |

## Artifacts

- Model directory: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_production_final_180m`
- Modes: `base, jepa_only, base_jepa`
- Live bot uses the `base_jepa` mode.
