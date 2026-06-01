# OptionValueJEPA Diagnostics

Source: `research_papers\JEPA\results\option_value_jepa_2022_walkforward`

## Overall Metrics

| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 2099 | 58.1% | 3.005 | +794,618 | -6,442 | 0.703 | 135.5 |
| option_value_hold180_select_hard | 2099 | 47.3% | 2.458 | +707,925 | -8,021 | 0.576 | 119.3 |
| option_value_rule_select_hard | 2099 | 50.1% | 2.625 | +716,498 | -6,963 | 0.613 | 123.3 |
| option_value_best_select_hard | 2099 | 35.1% | 2.004 | +633,844 | -17,985 | 0.396 | 96.2 |
| option_value_best_select_learned_exit_5m | 2099 | 35.9% | 1.872 | +543,044 | -20,182 | 0.396 | 87.6 |
| oracle_best_delta_hard | 2099 | 58.2% | 7.311 | +1,542,132 | -2,334 | 0.523 | 120.2 |
| oracle_best_delta_oracle_exit | 2099 | 95.9% | 643.263 | +4,255,387 | -342 | 0.387 | 114.5 |

## Per Ticker

| Policy | Ticker | Trades | WR | PF | PnL | Avg Delta | Avg Hold |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | QQQ | 702 | 57.5% | 2.907 | +173,864 | 0.704 | 136.0 |
| fixed_delta_0.70_hard | SPX | 695 | 58.0% | 3.101 | +449,861 | 0.701 | 132.9 |
| fixed_delta_0.70_hard | SPY | 702 | 58.8% | 2.878 | +170,893 | 0.704 | 137.5 |
| option_value_hold180_select_hard | QQQ | 702 | 44.4% | 2.112 | +149,967 | 0.534 | 115.1 |
| option_value_hold180_select_hard | SPX | 695 | 52.7% | 2.855 | +402,694 | 0.655 | 125.6 |
| option_value_hold180_select_hard | SPY | 702 | 44.9% | 2.161 | +155,264 | 0.541 | 117.3 |
| option_value_rule_select_hard | QQQ | 702 | 49.9% | 2.452 | +170,361 | 0.610 | 124.1 |
| option_value_rule_select_hard | SPX | 695 | 50.5% | 2.868 | +384,746 | 0.625 | 120.6 |
| option_value_rule_select_hard | SPY | 702 | 50.0% | 2.372 | +161,391 | 0.604 | 125.2 |
| option_value_best_select_hard | QQQ | 702 | 26.1% | 1.596 | +121,116 | 0.275 | 80.3 |
| option_value_best_select_hard | SPX | 695 | 51.7% | 2.761 | +405,117 | 0.628 | 123.3 |
| option_value_best_select_hard | SPY | 702 | 27.6% | 1.544 | +107,611 | 0.288 | 85.2 |
| option_value_best_select_learned_exit_5m | QQQ | 702 | 26.9% | 1.637 | +128,605 | 0.275 | 78.0 |
| option_value_best_select_learned_exit_5m | SPX | 695 | 53.4% | 2.427 | +317,832 | 0.628 | 101.2 |
| option_value_best_select_learned_exit_5m | SPY | 702 | 27.5% | 1.488 | +96,607 | 0.288 | 83.7 |
| oracle_best_delta_hard | QQQ | 702 | 57.5% | 6.231 | +444,992 | 0.525 | 121.2 |
| oracle_best_delta_hard | SPX | 695 | 58.3% | 10.281 | +683,140 | 0.518 | 115.6 |
| oracle_best_delta_hard | SPY | 702 | 58.8% | 5.832 | +414,001 | 0.525 | 123.8 |
| oracle_best_delta_oracle_exit | QQQ | 702 | 96.3% | 627.705 | +1,384,019 | 0.326 | 110.2 |
| oracle_best_delta_oracle_exit | SPX | 695 | 96.4% | 866.392 | +1,625,221 | 0.507 | 120.6 |
| oracle_best_delta_oracle_exit | SPY | 702 | 95.0% | 491.765 | +1,246,147 | 0.330 | 112.8 |

## Distance To Oracle Hard-Exit Delta

| Policy | Matched | Same Candidate | Avg Delta Gap | Selected Avg Delta | Oracle Avg Delta | PnL Capture | PnL Gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 2099 | 47.7% | 0.180 | 0.703 | 0.523 | 51.5% | -747,514 |
| option_value_hold180_select_hard | 2099 | 29.8% | 0.195 | 0.576 | 0.523 | 45.9% | -834,207 |
| option_value_rule_select_hard | 2099 | 32.0% | 0.187 | 0.613 | 0.523 | 46.5% | -825,635 |
| option_value_best_select_hard | 2099 | 21.1% | 0.272 | 0.396 | 0.523 | 41.1% | -908,288 |
| option_value_best_select_learned_exit_5m | 2099 | 21.1% | 0.272 | 0.396 | 0.523 | 35.2% | -999,088 |

## Delta Target Distribution

| Policy | Delta | Count | Share |
| --- | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 0.70 | 2099 | 100.0% |
| option_value_hold180_select_hard | 0.10 | 30 | 1.4% |
| option_value_hold180_select_hard | 0.20 | 50 | 2.4% |
| option_value_hold180_select_hard | 0.30 | 175 | 8.3% |
| option_value_hold180_select_hard | 0.40 | 254 | 12.1% |
| option_value_hold180_select_hard | 0.50 | 244 | 11.6% |
| option_value_hold180_select_hard | 0.60 | 280 | 13.3% |
| option_value_hold180_select_hard | 0.70 | 1066 | 50.8% |
| option_value_rule_select_hard | 0.10 | 14 | 0.7% |
| option_value_rule_select_hard | 0.20 | 11 | 0.5% |
| option_value_rule_select_hard | 0.30 | 78 | 3.7% |
| option_value_rule_select_hard | 0.40 | 201 | 9.6% |
| option_value_rule_select_hard | 0.50 | 255 | 12.1% |
| option_value_rule_select_hard | 0.60 | 346 | 16.5% |
| option_value_rule_select_hard | 0.70 | 1194 | 56.9% |
| option_value_best_select_hard | 0.10 | 287 | 13.7% |
| option_value_best_select_hard | 0.20 | 397 | 18.9% |
| option_value_best_select_hard | 0.30 | 438 | 20.9% |
| option_value_best_select_hard | 0.40 | 233 | 11.1% |
| option_value_best_select_hard | 0.50 | 79 | 3.8% |
| option_value_best_select_hard | 0.60 | 55 | 2.6% |
| option_value_best_select_hard | 0.70 | 610 | 29.1% |
| option_value_best_select_learned_exit_5m | 0.10 | 287 | 13.7% |
| option_value_best_select_learned_exit_5m | 0.20 | 397 | 18.9% |
| option_value_best_select_learned_exit_5m | 0.30 | 438 | 20.9% |
| option_value_best_select_learned_exit_5m | 0.40 | 233 | 11.1% |
| option_value_best_select_learned_exit_5m | 0.50 | 79 | 3.8% |
| option_value_best_select_learned_exit_5m | 0.60 | 55 | 2.6% |
| option_value_best_select_learned_exit_5m | 0.70 | 610 | 29.1% |
| oracle_best_delta_hard | 0.10 | 185 | 8.8% |
| oracle_best_delta_hard | 0.20 | 128 | 6.1% |
| oracle_best_delta_hard | 0.30 | 183 | 8.7% |
| oracle_best_delta_hard | 0.40 | 191 | 9.1% |
| oracle_best_delta_hard | 0.50 | 176 | 8.4% |
| oracle_best_delta_hard | 0.60 | 234 | 11.1% |
| oracle_best_delta_hard | 0.70 | 1002 | 47.7% |
| oracle_best_delta_oracle_exit | 0.10 | 579 | 27.6% |
| oracle_best_delta_oracle_exit | 0.20 | 243 | 11.6% |
| oracle_best_delta_oracle_exit | 0.30 | 182 | 8.7% |
| oracle_best_delta_oracle_exit | 0.40 | 214 | 10.2% |
| oracle_best_delta_oracle_exit | 0.50 | 121 | 5.8% |
| oracle_best_delta_oracle_exit | 0.60 | 107 | 5.1% |
| oracle_best_delta_oracle_exit | 0.70 | 653 | 31.1% |

## Learned Exit Versus Hard Exit

| Ticker | Matched | Learned Exit Rate | Avg Hold Delta | PnL Delta Vs Hard | Avg PnL Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL | 2099 | 19.9% | -8.6 | -90,800 | -43 |
| QQQ | 702 | 14.7% | -2.4 | +7,489 | +11 |
| SPX | 695 | 31.7% | -22.1 | -87,285 | -126 |
| SPY | 702 | 13.5% | -1.5 | -11,004 | -16 |

## Initial Interpretation

- The learned `best` target over-selects low delta contracts, especially in QQQ/SPY.
- The hard-exit oracle uses lower average delta than fixed 0.70, but it still keeps a large 0.70 allocation; the learned model moves too far toward cheap convexity.
- The learned 5m exit reduces average hold time, but currently destroys more PnL than it saves. It should not be attached to the promoted GBT+JEPA 180m model until a separate OOS exit gate passes.
