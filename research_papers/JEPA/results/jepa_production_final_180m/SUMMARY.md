# Production Base+JEPA 180m Artifacts

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_production_20261230_jepa_xinput_v3_production.parquet`
Rows after exact 180m label construction: 56,160 from 221,832
Production cutoff: `20261230`
Label: `spot_price(t+180m) > spot_price(t)`
Backtest diagnostic: fixed 180m hold, cooldown `36` samples, base cost `1.0` bps, notional `$100,000`.

## Important

- These are final production artifacts trained on all eligible rows up to the cutoff.
- The metrics below are model-history diagnostics only. They are not OOS validation and must not be used as a promotion claim.
- The OOS evidence remains the locked research pipeline that trained through March 2026 and tested April/May 2026.
- `future_return_180m` and derived columns are labels/outcomes only and are excluded from model features.

## Prediction Diagnostics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 56160 | 55.4% | 54.9% | 0.976 | 91.9% | 91.8% | 0.844 | 46.50 | -51.94 |
| jepa_only | 56160 | 55.4% | 54.0% | 0.937 | 86.2% | 86.2% | 0.721 | 32.88 | -42.59 |
| base_jepa | 56160 | 55.4% | 54.9% | 0.977 | 92.1% | 92.0% | 0.839 | 44.61 | -51.79 |

## Fixed-Hold 180m Diagnostic

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 2803 | 87.5% | 20.904 | 30.89 | +865,707 | -3,111 | 54.9% |
| jepa_only | 2634 | 86.3% | 11.100 | 28.29 | +745,029 | -2,028 | 54.6% |
| base_jepa | 2808 | 88.1% | 24.990 | 31.23 | +876,958 | -2,674 | 55.5% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 2803 | 87.5% | 20.904 | 30.89 | +865,707 | -3,111 |
| 1 bps | jepa_only | 2634 | 86.3% | 11.100 | 28.29 | +745,029 | -2,028 |
| 1 bps | base_jepa | 2808 | 88.1% | 24.990 | 31.23 | +876,958 | -2,674 |
| 3 bps | base | 2803 | 84.3% | 16.763 | 28.89 | +809,647 | -3,151 |
| 3 bps | jepa_only | 2634 | 83.3% | 9.469 | 26.29 | +692,349 | -2,128 |
| 3 bps | base_jepa | 2808 | 85.2% | 19.617 | 29.23 | +820,798 | -2,714 |
| 5 bps | base | 2803 | 81.5% | 13.350 | 26.89 | +753,587 | -3,191 |
| 5 bps | jepa_only | 2634 | 80.2% | 8.003 | 24.29 | +639,669 | -2,228 |
| 5 bps | base_jepa | 2808 | 82.3% | 15.341 | 27.23 | +764,638 | -2,754 |
| 10 bps | base | 2803 | 72.4% | 7.597 | 21.89 | +613,437 | -3,323 |
| 10 bps | jepa_only | 2634 | 70.1% | 5.102 | 19.29 | +507,969 | -2,485 |
| 10 bps | base_jepa | 2808 | 72.8% | 8.377 | 22.23 | +624,238 | -2,886 |

## Artifacts

- Model directory: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_production_final_180m`
- Modes: `base, jepa_only, base_jepa`
- Live bot uses the `base_jepa` mode.
