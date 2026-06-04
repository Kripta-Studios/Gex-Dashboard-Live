# GBT+JEPA 180m Continuation-Exit Walk-Forward

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Model dir: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_full_pipeline_180m_frozen_march`
Signal mode: `base_jepa`
Test months: `202604` to `latest`
State rows use every 5m point until `180`m.
Model features: `689` numeric entry/current/delta features.

## OOS Aggregate

| Policy | Trades | WR | PF | Avg bps | PnL | Max DD | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_180m | 174 | 53.4% | 1.381 | 3.64 | +6,336 | -2,979 | 133.8 |
| fixed_trailing_exit | 174 | 55.2% | 1.494 | 4.32 | +7,522 | -1,819 | 117.6 |
| oracle_exit | 174 | 84.5% | 33.894 | 19.48 | +33,902 | -215 | 77.6 |

## Promotion Gate

An exit policy is promotable only if it beats fixed 180m on PF, PnL, and max drawdown without changing entries.

| Policy | Passed | PF | PnL | DD | Same Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| fixed_trailing_exit | True | True | True | True | True |

## Monthly Folds

| Policy | Month | Trades | Margin $ | Fixed PF | Learned PF | Fixed PnL | Learned PnL | Fixed DD | Learned DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

## Interpretation

- `oracle_exit` is not deployable. It chooses the best point after seeing the future path.
- `fixed_trailing_exit`, when present, is a fixed mechanical trail/limit config. It is not a learned JEPA exit.
- The learned policies only see information available at each 5m state: entry features, current features, JEPA probability changes, PnL path statistics, and time remaining.
- Future best/terminal values are labels only and are not included as model features.
- If every non-oracle policy fails the promotion gate, fixed 180m remains the correct GBT+JEPA exit contract.
