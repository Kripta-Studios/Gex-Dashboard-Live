# GBT+JEPA 180m Continuation-Exit Walk-Forward

Data: `training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Model dir: `neural\models\jepa\jepa_full_pipeline_180m_frozen_march`
Signal mode: `base_jepa`
Test months: `202604` to `202605`
State rows use every 5m point until `180`m.
Model features: `689` numeric entry/current/delta features.

## OOS Aggregate

| Policy | Trades | WR | PF | Avg bps | PnL | Max DD | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_180m | 169 | 53.3% | 1.381 | 3.67 | +6,202 | -2,979 | 133.6 |
| trailing_exit | 169 | 53.3% | 1.285 | 3.00 | +5,063 | -3,113 | 131.5 |
| fixed_trailing_exit | 169 | 55.0% | 1.498 | 4.39 | +7,411 | -1,819 | 117.2 |
| oracle_exit | 169 | 84.6% | 34.978 | 19.73 | +33,339 | -215 | 77.9 |

## Promotion Gate

An exit policy is promotable only if it beats fixed 180m on PF, PnL, and max drawdown without changing entries.

| Policy | Passed | PF | PnL | DD | Same Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| trailing_exit | False | False | False | False | True |
| fixed_trailing_exit | True | True | True | True | True |

## Monthly Folds

| Policy | Month | Trades | Margin $ | Fixed PF | Learned PF | Fixed PnL | Learned PnL | Fixed DD | Learned DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| trailing_exit | 202604 | 80 | nan | 1.059 | 0.929 | +505 | -694 | -2,979 | -3,113 |
| trailing_exit | 202605 | 89 | nan | 1.733 | 1.716 | +5,697 | +5,757 | -1,308 | -1,308 |

## Interpretation

- `oracle_exit` is not deployable. It chooses the best point after seeing the future path.
- `fixed_trailing_exit`, when present, is a fixed mechanical trail/limit config. It is not a learned JEPA exit.
- The learned policies only see information available at each 5m state: entry features, current features, JEPA probability changes, PnL path statistics, and time remaining.
- Future best/terminal values are labels only and are not included as model features.
- If every non-oracle policy fails the promotion gate, fixed 180m remains the correct GBT+JEPA exit contract.
