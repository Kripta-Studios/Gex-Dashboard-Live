# XInputJEPA Predictive Capacity

Data: `training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Model: `neural\models\jepa\xinput_v3`
OOS split: dates >= `20260401`

## Verdict

- XInputJEPA does not show strong short/medium-horizon latent prediction capacity versus a persistence baseline.
- OOS 60m latent MSE improvement versus persistence: -8.7%; the predictor beats persistence on 28.3% of samples.
- OOS auxiliary direction head: balanced accuracy 41.5%, long AUC 0.722, short AUC 0.424, trade-vs-hold AUC 0.606.
- The clearest direct latent signal is long horizon: OOS 180m latent MSE improvement versus persistence is 19.1%.
- OOS XInputJEPA-only trades: win rate 54.6%, PnL +34,800, alignment AUC for trade win 0.519.
- Exact OOS 180m terminal-up test: direction-score AUC 0.545, sign accuracy 49.0%, Spearman to 180m return 0.119.
- This supports the interpretation that the JEPA learned some slower future-state structure, but not enough short-horizon tradable signal for clean GBT integration.

## Direction Head

| Segment | Ticker | Rows | Target S/H/L | Pred S/H/L | Acc | Bal Acc | Macro F1 | Long AUC | Short AUC | Trade AUC | Dir Spearman |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | ALL | 157192 | 15.5%/67.4%/17.1% | 35.8%/31.6%/32.7% | 45.9% | 51.6% | 43.2% | 0.793 | 0.554 | 0.661 | 0.222 |
| pre_oos | ALL | 151032 | 15.8%/67.3%/17.0% | 35.5%/31.7%/32.9% | 46.2% | 52.0% | 43.5% | 0.797 | 0.559 | 0.663 | 0.228 |
| oos | ALL | 6160 | 9.5%/71.6%/18.9% | 43.6%/29.1%/27.3% | 38.7% | 41.5% | 35.6% | 0.722 | 0.424 | 0.606 | 0.128 |

## Direct Latent Prediction

MSE is measured between the predicted future latent state and the observed future latent state. Persistence uses current `z_t` as the future prediction.

| Segment | Ticker | Horizon | Rows | Model MSE | Persistence MSE | Improvement | Beat Persistence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| oos | ALL | 5m | 6050 | 0.02583 | 0.00452 | -471.6% | 0.6% |
| oos | ALL | 15m | 5830 | 0.04196 | 0.01984 | -111.4% | 5.4% |
| oos | ALL | 30m | 5500 | 0.06555 | 0.04630 | -41.6% | 12.5% |
| oos | ALL | 60m | 4840 | 0.10274 | 0.09452 | -8.7% | 28.3% |
| oos | ALL | 120m | 3520 | 0.16923 | 0.17983 | 5.9% | 51.0% |
| oos | ALL | 180m | 2200 | 0.21221 | 0.26241 | 19.1% | 65.5% |
| overall | ALL | 5m | 154385 | 0.03246 | 0.00491 | -560.6% | 0.6% |
| overall | ALL | 15m | 148771 | 0.04855 | 0.02082 | -133.2% | 4.5% |
| overall | ALL | 30m | 140350 | 0.07096 | 0.04769 | -48.8% | 12.2% |
| overall | ALL | 60m | 123508 | 0.10605 | 0.09471 | -12.0% | 29.0% |
| overall | ALL | 120m | 89824 | 0.16631 | 0.17784 | 6.5% | 51.4% |
| overall | ALL | 180m | 56140 | 0.20762 | 0.26562 | 21.8% | 66.0% |
| pre_oos | ALL | 5m | 148335 | 0.03273 | 0.00493 | -563.9% | 0.6% |
| pre_oos | ALL | 15m | 142941 | 0.04882 | 0.02086 | -134.1% | 4.5% |
| pre_oos | ALL | 30m | 134850 | 0.07118 | 0.04775 | -49.1% | 12.2% |
| pre_oos | ALL | 60m | 118668 | 0.10618 | 0.09472 | -12.1% | 29.0% |
| pre_oos | ALL | 120m | 86304 | 0.16619 | 0.17776 | 6.5% | 51.4% |
| pre_oos | ALL | 180m | 53940 | 0.20744 | 0.26575 | 21.9% | 66.0% |

## Exact 180m Spot Direction

This measures whether the current JEPA direction score predicts `spot_price(t+180m) > spot_price(t)` exactly, not whether a target/stop path wins inside the 180m window.

| Segment | Ticker | Rows | Future Up | Pred Up | Sign Acc | AUC Up | Spearman Ret | Mean Ret bps | Top Q Ret bps | Bottom Q Ret bps |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | ALL | 56140 | 55.4% | 40.8% | 60.6% | 0.641 | 0.255 | 1.98 | 25.60 | -4.55 |
| oos | ALL | 2200 | 63.1% | 37.7% | 49.0% | 0.545 | 0.119 | 7.67 | 11.93 | 1.27 |
| pre_oos | ALL | 53940 | 55.1% | 40.9% | 61.0% | 0.646 | 0.261 | 1.75 | 26.08 | -5.04 |

## Lagged Surprise Features

| Segment | Feature | Rows | Mean | Median | Short Mean | Hold Mean | Long Mean | Trade AUC From Error |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | xjepa_lagged_pred_30m_err | 140350 | 0.9605 | 0.8559 | 0.8707 | 1.0004 | 0.8685 | 0.423 |
| overall | xjepa_lagged_pred_60m_err | 123508 | 1.1568 | 1.0086 | 1.0504 | 1.1980 | 1.0537 | 0.435 |
| overall | xjepa_lagged_pred_180m_err | 56140 | 1.6769 | 1.5252 | 1.5927 | 1.6847 | 1.6817 | 0.485 |
| oos | xjepa_lagged_pred_30m_err | 5500 | 0.9406 | 0.8527 | 0.8414 | 0.9652 | 0.8829 | 0.440 |
| oos | xjepa_lagged_pred_60m_err | 4840 | 1.1404 | 0.9928 | 1.0306 | 1.1718 | 1.0364 | 0.449 |
| oos | xjepa_lagged_pred_180m_err | 2200 | 1.7078 | 1.5386 | 1.7901 | 1.7053 | 1.7152 | 0.498 |
| pre_oos | xjepa_lagged_pred_30m_err | 134850 | 0.9614 | 0.8561 | 0.8713 | 1.0019 | 0.8679 | 0.422 |
| pre_oos | xjepa_lagged_pred_60m_err | 118668 | 1.1574 | 1.0092 | 1.0507 | 1.1991 | 1.0545 | 0.434 |
| pre_oos | xjepa_lagged_pred_180m_err | 53940 | 1.6757 | 1.5248 | 1.5910 | 1.6838 | 1.6803 | 0.485 |

## Trade-Level Capacity

| Trade File | Segment | Trades | Merge | WR | PnL | Align AUC Win | Align Spearman PnL | Conf AUC Win | Low-Err AUC Win |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gbt_xjepa_trades.csv | overall | 3843 | 100.0% | 51.1% | +439,787 | 0.568 | 0.129 | 0.566 | 0.460 |
| gbt_xjepa_trades.csv | pre_oos | 3616 | 100.0% | 51.3% | +431,025 | 0.569 | 0.134 | 0.566 | 0.460 |
| gbt_xjepa_trades.csv | oos | 227 | 100.0% | 48.0% | +8,763 | 0.546 | 0.064 | 0.559 | 0.449 |
| xjepa_only_trades.csv | overall | 3967 | 100.0% | 49.6% | +279,232 | 0.584 | 0.146 | 0.582 | 0.449 |
| xjepa_only_trades.csv | pre_oos | 3718 | 100.0% | 49.3% | +244,431 | 0.588 | 0.156 | 0.588 | 0.446 |
| xjepa_only_trades.csv | oos | 249 | 100.0% | 54.6% | +34,800 | 0.519 | 0.012 | 0.498 | 0.498 |
| gbt_xjepa_oos_trades.csv | overall | 227 | 100.0% | 48.0% | +8,763 | 0.546 | 0.064 | 0.559 | 0.449 |
| gbt_xjepa_oos_trades.csv | oos | 227 | 100.0% | 48.0% | +8,763 | 0.546 | 0.064 | 0.559 | 0.449 |
| xjepa_only_oos_trades.csv | overall | 249 | 100.0% | 54.6% | +34,800 | 0.519 | 0.012 | 0.498 | 0.498 |
| xjepa_only_oos_trades.csv | oos | 249 | 100.0% | 54.6% | +34,800 | 0.519 | 0.012 | 0.498 | 0.498 |

## Interpretation

- Beating persistence in latent space means the predictor is not only copying the current state.
- The auxiliary direction head has useful but weak row-level discrimination; the majority HOLD class is large, so balanced accuracy and AUC matter more than raw accuracy.
- Trade-level alignment is the strictest test. If alignment AUC is near 0.50, the JEPA signal may predict state transitions but not the option payoff distribution reliably.
- The current result is consistent with the backtests: XInputJEPA captures some market-state dynamics, but GBT integration needs stronger calibration/gating before promotion.
