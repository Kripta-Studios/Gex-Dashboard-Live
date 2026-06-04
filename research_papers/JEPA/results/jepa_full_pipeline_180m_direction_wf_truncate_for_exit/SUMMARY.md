# JEPA 180m Direction Experiment

Data: `training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Rows after EOD-truncated 180m label construction: 154,605 from 222,069
Label: `spot_price(t+180m) > spot_price(t)`
Test months: `202501 to 202605`
OOS split: dates >= `20260401`
Backtest: max 180m hold truncated to same-day last row, cooldown `36` samples, cost `1.0` bps, notional `$100,000` per trade.

## Prediction Metrics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base_jepa overall | 57255 | 53.1% | 44.5% | 0.607 | 56.4% | 56.7% | 0.220 | 10.91 | -12.75 |
| base_jepa OOS | 6105 | 65.4% | 42.2% | 0.580 | 51.5% | 54.3% | 0.176 | 10.96 | 0.27 |

## Fixed-Hold 180m Backtest

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base_jepa overall | 1649 | 57.6% | 1.558 | 6.61 | +109,017 | -12,725 | 46.8% |
| base_jepa OOS | 185 | 54.1% | 1.267 | 2.75 | +5,090 | -4,555 | 47.6% |

## Interpretation

- This is a terminal 180m direction experiment, not the original target/stop 0DTE label.
- The future return is used only as the label and backtest outcome; feature columns explicitly exclude future/target columns.
- OOS metrics are the important decision point because previous XInputJEPA evidence was unstable in Apr/May 2026.
- A promotable 180m module should beat the base feature model OOS on AUC and fixed-hold PnL, with enough trades after the 180m cooldown.
