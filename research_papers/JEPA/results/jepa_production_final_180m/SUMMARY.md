# Production Base+JEPA 180m Artifacts

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_production_20261230_jepa_xinput_v3_production.parquet`
Rows after exact 180m label construction: 56,220 from 222,069
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
| base | 56220 | 55.4% | 54.9% | 0.976 | 91.8% | 91.7% | 0.846 | 46.58 | -52.72 |
| jepa_only | 56220 | 55.4% | 54.3% | 0.942 | 87.0% | 86.9% | 0.758 | 35.07 | -47.95 |
| base_jepa | 56220 | 55.4% | 55.1% | 0.975 | 91.9% | 91.8% | 0.832 | 43.36 | -52.18 |

## Fixed-Hold 180m Diagnostic

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 2811 | 85.7% | 17.340 | 30.41 | +854,830 | -2,674 | 54.5% |
| jepa_only | 2790 | 86.9% | 13.937 | 29.86 | +833,167 | -7,906 | 55.7% |
| base_jepa | 2796 | 90.4% | 29.367 | 32.12 | +898,155 | -1,799 | 56.2% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 2811 | 85.7% | 17.340 | 30.41 | +854,830 | -2,674 |
| 1 bps | jepa_only | 2790 | 86.9% | 13.937 | 29.86 | +833,167 | -7,906 |
| 1 bps | base_jepa | 2796 | 90.4% | 29.367 | 32.12 | +898,155 | -1,799 |
| 3 bps | base | 2811 | 82.8% | 14.063 | 28.41 | +798,610 | -2,714 |
| 3 bps | jepa_only | 2790 | 83.5% | 11.701 | 27.86 | +777,367 | -7,946 |
| 3 bps | base_jepa | 2796 | 87.2% | 23.224 | 30.12 | +842,235 | -1,819 |
| 5 bps | base | 2811 | 80.1% | 11.368 | 26.41 | +742,390 | -2,754 |
| 5 bps | jepa_only | 2790 | 81.0% | 9.748 | 25.86 | +721,567 | -7,986 |
| 5 bps | base_jepa | 2796 | 84.2% | 18.151 | 28.12 | +786,315 | -1,839 |
| 10 bps | base | 2811 | 71.6% | 6.736 | 21.41 | +601,840 | -2,886 |
| 10 bps | jepa_only | 2790 | 71.4% | 6.039 | 20.86 | +582,067 | -8,086 |
| 10 bps | base_jepa | 2796 | 73.7% | 9.647 | 23.12 | +646,515 | -1,921 |

## Artifacts

- Model directory: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_production_final_180m`
- Modes: `base, jepa_only, base_jepa`
- Live bot uses the `base_jepa` mode.
