# OptionValueJEPA Diagnostics

Source: `research_papers\JEPA\results\jepa_full_pipeline_option_policy`

## Overall Metrics

| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.60_hard | 105 | 38.1% | 1.632 | +18,581 | -4,906 | 0.603 | 108.6 |
| fixed_delta_0.70_hard | 105 | 42.9% | 1.725 | +20,719 | -5,095 | 0.702 | 120.3 |
| validation_best_delta_0.70_hard | 105 | 42.9% | 1.725 | +20,719 | -5,095 | 0.702 | 120.3 |
| learned_delta_regression_all_hard | 105 | 37.1% | 1.376 | +11,658 | -5,521 | 0.637 | 108.9 |
| learned_delta_ranker_all_hard | 105 | 37.1% | 1.505 | +13,391 | -4,402 | 0.636 | 108.4 |
| supervised_entry_strike_skip_hard | 32 | 28.1% | 1.353 | +4,808 | -3,546 | 0.669 | 88.4 |
| supervised_entry_strike_learned_exit | 32 | 28.1% | 1.613 | +8,348 | -3,546 | 0.669 | 81.6 |
| oracle_best_delta_hard | 105 | 42.9% | 4.092 | +54,238 | -1,965 | 0.513 | 103.0 |
| oracle_best_delta_oracle_exit | 105 | 87.6% | 140.828 | +167,995 | -342 | 0.464 | 89.2 |

## Per Ticker

| Policy | Ticker | Trades | WR | PF | PnL | Avg Delta | Avg Hold |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.60_hard | QQQ | 35 | 40.0% | 1.328 | +2,593 | 0.603 | 98.9 |
| fixed_delta_0.60_hard | SPX | 36 | 41.7% | 2.190 | +15,379 | 0.600 | 119.6 |
| fixed_delta_0.60_hard | SPY | 34 | 32.4% | 1.071 | +609 | 0.607 | 106.9 |
| fixed_delta_0.70_hard | QQQ | 35 | 42.9% | 1.372 | +2,384 | 0.702 | 111.9 |
| fixed_delta_0.70_hard | SPX | 36 | 52.8% | 2.222 | +17,888 | 0.703 | 134.6 |
| fixed_delta_0.70_hard | SPY | 34 | 32.4% | 1.060 | +448 | 0.701 | 113.8 |
| validation_best_delta_0.70_hard | QQQ | 35 | 42.9% | 1.372 | +2,384 | 0.702 | 111.9 |
| validation_best_delta_0.70_hard | SPX | 36 | 52.8% | 2.222 | +17,888 | 0.703 | 134.6 |
| validation_best_delta_0.70_hard | SPY | 34 | 32.4% | 1.060 | +448 | 0.701 | 113.8 |
| learned_delta_regression_all_hard | QQQ | 35 | 42.9% | 1.291 | +2,012 | 0.679 | 108.0 |
| learned_delta_regression_all_hard | SPX | 36 | 36.1% | 1.592 | +9,540 | 0.605 | 110.4 |
| learned_delta_regression_all_hard | SPY | 34 | 32.4% | 1.013 | +105 | 0.626 | 108.1 |
| learned_delta_ranker_all_hard | QQQ | 35 | 42.9% | 1.365 | +2,350 | 0.699 | 111.9 |
| learned_delta_ranker_all_hard | SPX | 36 | 36.1% | 1.820 | +10,307 | 0.524 | 100.0 |
| learned_delta_ranker_all_hard | SPY | 34 | 32.4% | 1.098 | +734 | 0.690 | 113.7 |
| supervised_entry_strike_skip_hard | QQQ | 9 | 11.1% | 0.264 | -2,147 | 0.621 | 58.3 |
| supervised_entry_strike_skip_hard | SPX | 17 | 41.2% | 1.950 | +8,465 | 0.697 | 107.9 |
| supervised_entry_strike_skip_hard | SPY | 6 | 16.7% | 0.154 | -1,509 | 0.659 | 78.3 |
| supervised_entry_strike_learned_exit | QQQ | 9 | 11.1% | 0.264 | -2,147 | 0.621 | 58.3 |
| supervised_entry_strike_learned_exit | SPX | 17 | 41.2% | 2.347 | +12,005 | 0.697 | 95.0 |
| supervised_entry_strike_learned_exit | SPY | 6 | 16.7% | 0.154 | -1,509 | 0.659 | 78.3 |
| oracle_best_delta_hard | QQQ | 35 | 42.9% | 2.837 | +11,092 | 0.528 | 104.1 |
| oracle_best_delta_hard | SPX | 36 | 52.8% | 7.906 | +29,952 | 0.502 | 111.0 |
| oracle_best_delta_hard | SPY | 34 | 32.4% | 2.841 | +13,195 | 0.510 | 93.5 |
| oracle_best_delta_oracle_exit | QQQ | 35 | 85.7% | 75.537 | +50,516 | 0.432 | 82.7 |
| oracle_best_delta_oracle_exit | SPX | 36 | 91.7% | 246.060 | +81,364 | 0.543 | 101.1 |
| oracle_best_delta_oracle_exit | SPY | 34 | 85.3% | 189.403 | +36,115 | 0.415 | 83.2 |

## Distance To Oracle Hard-Exit Delta

| Policy | Matched | Same Candidate | Avg Delta Gap | Selected Avg Delta | Oracle Avg Delta | PnL Capture | PnL Gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.60_hard | 105 | 15.2% | 0.171 | 0.603 | 0.513 | 34.3% | -35,657 |
| fixed_delta_0.70_hard | 105 | 41.0% | 0.189 | 0.702 | 0.513 | 38.2% | -33,519 |
| validation_best_delta_0.70_hard | 105 | 41.0% | 0.189 | 0.702 | 0.513 | 38.2% | -33,519 |
| learned_delta_regression_all_hard | 105 | 25.7% | 0.221 | 0.637 | 0.513 | 21.5% | -42,580 |
| learned_delta_ranker_all_hard | 105 | 37.1% | 0.185 | 0.636 | 0.513 | 24.7% | -40,847 |
| supervised_entry_strike_skip_hard | 32 | 31.2% | 0.197 | 0.669 | 0.513 | 33.9% | -9,392 |
| supervised_entry_strike_learned_exit | 32 | 31.2% | 0.197 | 0.669 | 0.513 | 58.8% | -5,852 |

## Delta Target Distribution

| Policy | Delta | Count | Share |
| --- | ---: | ---: | ---: |
| fixed_delta_0.60_hard | 0.60 | 105 | 100.0% |
| fixed_delta_0.70_hard | 0.70 | 105 | 100.0% |
| validation_best_delta_0.70_hard | 0.70 | 105 | 100.0% |
| learned_delta_regression_all_hard | 0.30 | 6 | 5.7% |
| learned_delta_regression_all_hard | 0.40 | 7 | 6.7% |
| learned_delta_regression_all_hard | 0.50 | 6 | 5.7% |
| learned_delta_regression_all_hard | 0.60 | 8 | 7.6% |
| learned_delta_regression_all_hard | 0.70 | 78 | 74.3% |
| learned_delta_ranker_all_hard | 0.20 | 1 | 1.0% |
| learned_delta_ranker_all_hard | 0.30 | 10 | 9.5% |
| learned_delta_ranker_all_hard | 0.40 | 6 | 5.7% |
| learned_delta_ranker_all_hard | 0.50 | 1 | 1.0% |
| learned_delta_ranker_all_hard | 0.60 | 10 | 9.5% |
| learned_delta_ranker_all_hard | 0.70 | 77 | 73.3% |
| supervised_entry_strike_skip_hard | 0.30 | 1 | 3.1% |
| supervised_entry_strike_skip_hard | 0.40 | 1 | 3.1% |
| supervised_entry_strike_skip_hard | 0.50 | 1 | 3.1% |
| supervised_entry_strike_skip_hard | 0.60 | 3 | 9.4% |
| supervised_entry_strike_skip_hard | 0.70 | 26 | 81.2% |
| supervised_entry_strike_learned_exit | 0.30 | 1 | 3.1% |
| supervised_entry_strike_learned_exit | 0.40 | 1 | 3.1% |
| supervised_entry_strike_learned_exit | 0.50 | 1 | 3.1% |
| supervised_entry_strike_learned_exit | 0.60 | 3 | 9.4% |
| supervised_entry_strike_learned_exit | 0.70 | 26 | 81.2% |
| oracle_best_delta_hard | 0.10 | 8 | 7.6% |
| oracle_best_delta_hard | 0.20 | 6 | 5.7% |
| oracle_best_delta_hard | 0.30 | 13 | 12.4% |
| oracle_best_delta_hard | 0.40 | 10 | 9.5% |
| oracle_best_delta_hard | 0.50 | 9 | 8.6% |
| oracle_best_delta_hard | 0.60 | 16 | 15.2% |
| oracle_best_delta_hard | 0.70 | 43 | 41.0% |
| oracle_best_delta_oracle_exit | 0.10 | 18 | 17.1% |
| oracle_best_delta_oracle_exit | 0.20 | 12 | 11.4% |
| oracle_best_delta_oracle_exit | 0.30 | 4 | 3.8% |
| oracle_best_delta_oracle_exit | 0.40 | 12 | 11.4% |
| oracle_best_delta_oracle_exit | 0.50 | 9 | 8.6% |
| oracle_best_delta_oracle_exit | 0.60 | 7 | 6.7% |
| oracle_best_delta_oracle_exit | 0.70 | 43 | 41.0% |

## Initial Interpretation

- The learned `best` target over-selects low delta contracts, especially in QQQ/SPY.
- The hard-exit oracle uses lower average delta than fixed 0.70, but it still keeps a large 0.70 allocation; the learned model moves too far toward cheap convexity.
- The learned 5m exit reduces average hold time, but currently destroys more PnL than it saves. It should not be attached to the promoted GBT+JEPA 180m model until a separate OOS exit gate passes.
