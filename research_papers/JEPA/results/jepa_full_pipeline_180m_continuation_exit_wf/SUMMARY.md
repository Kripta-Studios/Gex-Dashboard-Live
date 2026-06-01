# GBT+JEPA 180m Continuation-Exit Walk-Forward

Data: `.\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Model dir: `.\neural\models\jepa\jepa_full_pipeline_180m_frozen_march`
Signal mode: `base_jepa`
Test months: `202604` to `202605`
State rows use every 5m point until `180`m.
Model features: `689` numeric entry/current/delta features.

## OOS Aggregate

| Policy | Trades | WR | PF | Avg bps | PnL | Max DD | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_180m | 105 | 68.6% | 1.945 | 8.70 | +9,132 | -2,093 | 180.0 |
| pooled_continue_edge_l1 | 105 | 68.6% | 1.945 | 8.70 | +9,132 | -2,093 | 180.0 |
| pooled_continue_edge_q75 | 105 | 70.5% | 1.901 | 8.27 | +8,679 | -2,093 | 175.9 |
| per_ticker_continue_edge_l1 | 105 | 68.6% | 1.799 | 7.01 | +7,357 | -2,033 | 149.7 |
| oracle_exit | 105 | 90.5% | 44.155 | 26.12 | +27,428 | -215 | 110.0 |

Metrics in this table are recomputed in chronological `date,time,ticker,trade_id` order so drawdown is comparable across policies.

## Promotion Gate

A learned exit is promotable only if it beats fixed 180m on PF, PnL, and max drawdown without changing entries.

| Policy | Passed | PF | PnL | DD | Same Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| pooled_continue_edge_l1 | False | False | False | False | True |
| pooled_continue_edge_q75 | False | False | False | False | True |
| per_ticker_continue_edge_l1 | False | False | False | True | True |

## Monthly Folds

| Policy | Month | Trades | Margin $ | Fixed PF | Learned PF | Fixed PnL | Learned PnL | Fixed DD | Learned DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pooled_continue_edge_l1 | 202604 | 52 | -250 | 1.867 | 1.867 | +4,299 | +4,299 | -2,033 | -2,033 |
| pooled_continue_edge_l1 | 202605 | 53 | -250 | 2.027 | 2.027 | +4,832 | +4,832 | -2,093 | -2,093 |
| pooled_continue_edge_q75 | 202604 | 52 | -250 | 1.867 | 1.867 | +4,299 | +4,299 | -2,033 | -2,033 |
| pooled_continue_edge_q75 | 202605 | 53 | 50 | 2.027 | 1.936 | +4,832 | +4,380 | -2,093 | -2,093 |
| per_ticker_continue_edge_l1 | 202604 | 52 | -250 | 1.867 | 1.867 | +4,299 | +4,299 | -2,033 | -2,033 |
| per_ticker_continue_edge_l1 | 202605 | 53 | 100 | 2.027 | 1.720 | +4,832 | +3,057 | -2,093 | -1,739 |

## Interpretation

- `oracle_exit` is not deployable. It chooses the best point after seeing the future path.
- The learned policies only see information available at each 5m state: entry features, current features, JEPA probability changes, PnL path statistics, and time remaining.
- Future best/terminal values are labels only and are not included as model features.
- Every learned policy failed the promotion gate. Fixed 180m remains the correct GBT+JEPA exit contract.
