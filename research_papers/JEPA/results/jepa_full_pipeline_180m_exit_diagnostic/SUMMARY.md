# GBT+JEPA 180m Learned Exit Diagnostic

Data: `.\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Model dir: `.\neural\models\jepa\jepa_full_pipeline_180m_frozen_march`
Train cutoff: `20260331`
Test start: `20260401`
Selected margin: `$100`

## OOS Results

| Policy | Trades | WR | PF | Avg bps | PnL | Max DD | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_180m | 105 | 68.6% | 1.945 | 8.70 | +9,132 | -1,522 | 180.0 |
| learned_exit | 105 | 70.5% | 1.951 | 8.17 | +8,579 | -1,522 | 145.9 |
| oracle_exit | 105 | 90.5% | 44.155 | 26.12 | +27,428 | -239 | 110.0 |

## Validation Margin Grid

| Margin $ | Trades | WR | PF | PnL | Max DD | Score |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| -750 | 182 | 88.5% | 23.489 | +46,611 | -362 | 126.953 |
| -500 | 182 | 88.5% | 23.489 | +46,611 | -362 | 126.953 |
| -250 | 182 | 88.5% | 23.489 | +46,611 | -362 | 126.953 |
| -100 | 182 | 88.5% | 23.489 | +46,611 | -362 | 126.953 |
| 0 | 182 | 88.5% | 23.261 | +46,140 | -362 | 125.722 |
| 100 | 182 | 85.7% | 36.489 | +45,922 | -194 | 194.645 |
| 250 | 182 | 75.3% | 9.086 | +27,573 | -412 | 50.011 |
| 500 | 182 | 48.4% | 1.790 | +5,646 | -1,026 | 9.686 |
| 750 | 182 | 42.3% | 0.983 | -141 | -1,421 | 4.824 |

## Interpretation

- `fixed_180m` is the promoted GBT+JEPA 180m contract.
- `learned_exit` is diagnostic only; it is not promoted unless it beats fixed hold OOS without increasing drawdown materially.
- `oracle_exit` is the non-deployable ceiling showing the maximum possible benefit of perfect exit timing.
