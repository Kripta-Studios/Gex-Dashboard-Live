# JEPA Supervised 0DTE Option Policy

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Signal model: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_180m_frozen_march` / mode `base_jepa`
Train cutoff: `20260331`
Test start: `20260401`
Signals after `180`m cooldown: 2,793 total, 2,689 train, 104 test.
Option candidates with valid real premium paths: 19,551.
Candidate deltas: `0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7`.
Execution: buy 0DTE option, risk capital `$1,000`, max hold `180`m, hard stop `-35%`, take profit `250%`.

## Policies Tested

- `fixed_delta_0.60_hard` / `fixed_delta_0.70_hard`: use every JEPA signal, buy the closest fixed-delta contract, exit with hard stop/take-profit/max-time.
- `validation_best_delta_hard`: choose the fixed delta from the pre-OOS validation months, then use every OOS JEPA signal.
- `learned_delta_regression_all_hard`: LightGBM predicts candidate option utility, chooses the best delta per signal, never skips a JEPA entry.
- `learned_delta_ranker_all_hard`: LightGBM ranker chooses the best delta per signal, never skips a JEPA entry.
- `supervised_entry_strike_skip_hard`: older LightGBM entry/strike policy with a validation threshold that can skip weak entries.
- `supervised_entry_strike_learned_exit`: same skip-gated entry/strike model plus a supervised continuation-value exit model, only available when option paths are rebuilt in the same run.
- `oracle_best_delta_hard`: non-deployable upper bound that chooses the best delta after seeing the future under hard exits.
- `oracle_best_delta_oracle_exit`: non-deployable upper bound that chooses best delta and best future exit.

## Apr/May OOS Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.60_hard | 104 | 38.5% | 1.672 | +19,286 | -4,201 | +185 | 108.9 | 0.603 |
| fixed_delta_0.70_hard | 104 | 43.3% | 1.773 | +21,487 | -4,327 | +207 | 120.7 | 0.702 |
| validation_best_delta_0.70_hard | 104 | 43.3% | 1.773 | +21,487 | -4,327 | +207 | 120.7 | 0.702 |
| learned_delta_regression_all_hard | 104 | 40.4% | 1.614 | +17,412 | -4,753 | +167 | 112.1 | 0.646 |
| learned_delta_ranker_all_hard | 104 | 37.5% | 1.531 | +13,844 | -3,706 | +133 | 108.8 | 0.642 |
| supervised_entry_strike_skip_hard | 3 | 0.0% | 0.000 | -1,279 | -1,279 | -426 | 48.3 | 0.539 |
| supervised_entry_strike_learned_exit | 3 | 0.0% | 0.000 | -1,279 | -1,279 | -426 | 48.3 | 0.539 |
| oracle_best_delta_hard | 104 | 43.3% | 4.152 | +54,490 | -1,762 | +524 | 103.6 | 0.515 |
| oracle_best_delta_oracle_exit | 104 | 87.5% | 139.894 | +166,873 | -342 | +1,605 | 88.6 | 0.462 |

## Per-Ticker OOS Results

### fixed_delta_0.60_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 40.0% | 1.328 | +2,593 | -2,454 | +74 | 98.9 | 0.603 |
| SPX | 35 | 42.9% | 2.317 | +16,084 | -1,772 | +460 | 120.9 | 0.599 |
| SPY | 34 | 32.4% | 1.071 | +609 | -2,430 | +18 | 106.9 | 0.607 |

### fixed_delta_0.70_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 1.372 | +2,384 | -2,112 | +68 | 111.9 | 0.702 |
| SPX | 35 | 54.3% | 2.345 | +18,656 | -2,669 | +533 | 136.3 | 0.703 |
| SPY | 34 | 32.4% | 1.060 | +448 | -2,387 | +13 | 113.8 | 0.701 |

### validation_best_delta_0.70_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 1.372 | +2,384 | -2,112 | +68 | 111.9 | 0.702 |
| SPX | 35 | 54.3% | 2.345 | +18,656 | -2,669 | +533 | 136.3 | 0.703 |
| SPY | 34 | 32.4% | 1.060 | +448 | -2,387 | +13 | 113.8 | 0.701 |

### learned_delta_regression_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 1.291 | +2,012 | -2,095 | +57 | 108.0 | 0.679 |
| SPX | 35 | 45.7% | 2.137 | +15,294 | -3,401 | +437 | 120.1 | 0.632 |
| SPY | 34 | 32.4% | 1.013 | +105 | -2,813 | +3 | 108.1 | 0.626 |

### learned_delta_ranker_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 1.372 | +2,384 | -2,112 | +68 | 111.9 | 0.702 |
| SPX | 35 | 37.1% | 1.893 | +10,797 | -3,331 | +308 | 101.0 | 0.529 |
| SPY | 34 | 32.4% | 1.087 | +663 | -2,166 | +19 | 113.8 | 0.695 |

### supervised_entry_strike_skip_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 3 | 0.0% | 0.000 | -1,279 | -1,279 | -426 | 48.3 | 0.539 |

### supervised_entry_strike_learned_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 3 | 0.0% | 0.000 | -1,279 | -1,279 | -426 | 48.3 | 0.539 |

### oracle_best_delta_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 2.837 | +11,092 | -1,762 | +317 | 104.1 | 0.528 |
| SPX | 35 | 54.3% | 8.394 | +30,204 | -891 | +863 | 112.9 | 0.508 |
| SPY | 34 | 32.4% | 2.841 | +13,195 | -1,442 | +388 | 93.5 | 0.510 |

### oracle_best_delta_oracle_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 85.7% | 75.537 | +50,516 | -342 | +1,443 | 82.7 | 0.432 |
| SPX | 35 | 91.4% | 242.680 | +80,242 | -157 | +2,293 | 99.6 | 0.539 |
| SPY | 34 | 85.3% | 189.403 | +36,115 | -85 | +1,062 | 83.2 | 0.415 |

## Validation Choices

- Fixed delta selected on pre-April validation: `0.70`.
- Entry utility threshold selected on pre-April validation: `0.5321`.
- Learned-exit margin selected on pre-April validation: `-0.2000`.

## Interpretation

- This is a frozen OOS test: option-policy models are trained through the March 2026 cutoff and scored from April 1, 2026 onward.
- Future option paths are used only to create supervised labels and to score the backtest, not as model inputs.
- The test is stricter than the previous spot proxy because it uses real 0DTE option premium paths and spread-adjusted entries.
- The current deployable validated policy is `validation_best_delta_0.70_hard` unless a learned selector beats it on rolling walk-forward validation.
- The oracle rows are ceilings, not deployable strategies. They diagnose the remaining strike/delta and exit-selection gap.

## Config

```json
{
  "config": {
    "data": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\training_data\\training_data_spx_qqq_spy_jepa_xinput_v3.parquet",
    "signal_model_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\neural\\models\\jepa\\jepa_180m_frozen_march",
    "signal_mode": "base_jepa",
    "output_dir": "research_papers\\JEPA\\results\\jepa_option_policy_2022",
    "model_dir": "neural\\models\\jepa\\jepa_option_policy_2022_frozen_march",
    "tickers": [
      "SPX",
      "QQQ",
      "SPY"
    ],
    "train_start_date": "20220801",
    "train_end_date": "20260331",
    "test_start_date": "20260401",
    "horizon_steps": 36,
    "cooldown_minutes": 180,
    "max_hold_minutes": 180,
    "risk_capital": 1000.0,
    "hard_stop_pct": -0.35,
    "take_profit_pct": 2.5,
    "min_exit_hold_minutes": 15,
    "delta_targets": [
      0.1,
      0.2,
      0.3,
      0.4,
      0.5,
      0.6,
      0.7
    ],
    "val_months": 3,
    "min_val_trades": 12,
    "n_estimators": 120,
    "exit_n_estimators": 80,
    "seed": 991,
    "n_jobs": 1,
    "greeks_cache_size": 50,
    "progress_every": 100,
    "max_signals": 0,
    "reuse_candidates": false
  },
  "base_feature_count": 222,
  "entry_features": [
    "net_gamma",
    "net_vanna",
    "net_charm",
    "net_dgex",
    "net_zomma",
    "net_delta",
    "signal_persistence_5m",
    "gamma_regime",
    "vanna_bullish",
    "charm_bullish",
    "dgex_sticky",
    "zomma_stabilizing",
    "dist_to_max_gamma",
    "dist_to_min_gamma",
    "dist_to_min_vanna",
    "dist_to_zero_gamma",
    "dist_to_max_dgex",
    "dist_to_min_dgex",
    "near_min_vanna",
    "wk_net_gamma",
    "wk_net_vanna",
    "wk_net_charm",
    "wk_net_dgex",
    "wk_net_zomma",
    "wk_net_delta",
    "wk_net_vega",
    "wk_net_vomma",
    "wk_gamma_regime",
    "wk_vanna_bullish",
    "wk_dgex_sticky",
    "wk_zomma_stabilizing",
    "gamma_0dte_vs_wk",
    "vanna_0dte_vs_wk",
    "dgex_0dte_vs_wk",
    "delta_0dte_vs_wk",
    "vega_0dte_vs_wk",
    "vomma_0dte_vs_wk",
    "vix_5d_mean",
    "vix_5d_std",
    "atr_5d_norm",
    "price_vs_ib_high",
    "price_vs_ib_low",
    "ib_range_pct",
    "near_ib_high",
    "near_ib_low",
    "above_ib",
    "below_ib",
    "in_ib_range",
    "dist_fib_127_up",
    "dist_fib_161_up",
    "dist_fib_200_up",
    "dist_fib_127_dn",
    "dist_fib_161_dn",
    "dist_fib_200_dn",
    "atm_iv",
    "iv_zscore",
    "iv_percentile",
    "vix_spot",
    "vix_gamma",
    "vix_regime",
    "rsi",
    "gamma_vanna_ratio",
    "dgex_gamma_ratio",
    "charm_vanna_ratio",
    "delta_gamma_ratio",
    "vega_gamma_ratio",
    "vomma_vega_ratio",
    "gamma_change",
    "vanna_change",
    "dgex_change",
    "delta_change",
    "vega_change",
    "vomma_change",
    "spot_change",
    "gamma_momentum",
    "price_vs_dgex_magnet",
    "net_vega",
    "net_vomma",
    "vega_elevated",
    "dist_to_max_vega",
    "dist_to_min_vega",
    "dist_to_max_vomma",
    "dist_to_min_vomma",
    "confluence_ib_high_max_gamma",
    "confluence_ib_low_min_gamma",
    "confluence_ib_high_max_vega",
    "confluence_ib_low_max_dgex",
    "confluence_fib127_bull_max_gamma",
    "confluence_fib161_bull_max_vega",
    "confluence_fib127_bear_min_gamma",
    "confluence_fib161_bear_max_vomma",
    "confluence_fib161_bull_max_vomma",
    "confluence_fib127_bear_min_vomma",
    "confluence_fib127_bull_max_dgex",
    "confluence_fib127_bear_min_dgex",
    "confluence_fib161_bull_max_dgex",
    "confluence_fib161_bear_min_dgex",
    "rvol_iv_log",
    "rvol_trend",
    "rvol_regime",
    "dist_ib_high_D1",
    "dist_ib_low_D1",
    "prev_close_vs_ib_D1",
    "dist_ib_high_D2",
    "dist_ib_low_D2",
    "prev_close_vs_ib_D2",
    "dist_ib_high_D3",
    "dist_ib_low_D3",
    "prev_close_vs_ib_D3",
    "dist_ib_high_D4",
    "dist_ib_low_D4",
    "prev_close_vs_ib_D4",
    "dist_ib_high_D5",
    "dist_ib_low_D5",
    "prev_close_vs_ib_D5",
    "ret_1m_vol_adj",
    "ret_5m_vol_adj",
    "ret_15m_vol_adj",
    "time_sin",
    "time_cos",
    "minutes_to_close_norm",
    "dow_sin",
    "dow_cos",
    "ib_range_percentile",
    "gap_pct",
    "gap_direction",
    "overnight_vs_ib_ratio",
    "days_to_opex_norm",
    "is_opex_week",
    "is_quarterly_opex_week",
    "charm_accel_weighted",
    "gamma_speed",
    "gamma_phase_sin",
    "gamma_phase_cos",
    "gamma_amplitude_ratio",
    "gamma_phase_delta",
    "delta_filtered_pcr",
    "pcr_derivative_5m",
    "tlt_ret_1m",
    "tlt_ret_5m",
    "tlt_ret_15m",
    "confluence_d1ibh_max_gamma",
    "confluence_d1ibl_min_gamma",
    "confluence_d1ibh_max_dgex",
    "confluence_d1ibl_min_dgex",
    "confluence_d1ibh_max_vomma",
    "confluence_d1ibh_ibh_today",
    "confluence_d1ibl_ibl_today",
    "speed_x_near_ib_high",
    "speed_x_near_ib_low",
    "charm_accel_x_near_ib_high",
    "charm_accel_x_near_ib_low",
    "wonham_trend_prob",
    "nearest_level_dist",
    "level_cluster_density",
    "momentum_5m_bps",
    "rejection_bullish",
    "rejection_bearish",
    "trend_grind_up",
    "trend_flush_down",
    "bouncing_from_support",
    "rejecting_resistance",
    "wall_at_fib",
    "wall_at_ib",
    "is_touching_fib",
    "is_touching_max_gamma",
    "is_touching_min_gamma",
    "is_touching_max_dgex",
    "nearest_level_id",
    "nearest_level_dist_bps",
    "gamma_x_near_fib_up",
    "gamma_x_near_fib_dn",
    "gamma_x_near_ib",
    "delta_x_near_fib_up",
    "delta_x_near_fib_dn",
    "delta_x_near_ib_high",
    "delta_x_near_ib_low",
    "vanna_x_near_fib_up",
    "vanna_x_near_fib_dn",
    "vanna_x_near_ib",
    "xjepa_z_00",
    "xjepa_z_01",
    "xjepa_z_02",
    "xjepa_z_03",
    "xjepa_z_04",
    "xjepa_z_05",
    "xjepa_z_06",
    "xjepa_z_07",
    "xjepa_z_08",
    "xjepa_z_09",
    "xjepa_z_10",
    "xjepa_z_11",
    "xjepa_z_12",
    "xjepa_z_13",
    "xjepa_z_14",
    "xjepa_z_15",
    "xjepa_u_00",
    "xjepa_u_01",
    "xjepa_u_02",
    "xjepa_u_03",
    "xjepa_u_04",
    "xjepa_u_05",
    "xjepa_u_06",
    "xjepa_u_07",
    "xjepa_u_08",
    "xjepa_u_09",
    "xjepa_u_10",
    "xjepa_u_11",
    "xjepa_latent_velocity",
    "xjepa_input_velocity",
    "xjepa_pred_dispersion_short",
    "xjepa_pred_dispersion_long",
    "xjepa_lagged_pred_30m_err",
    "xjepa_lagged_pred_60m_err",
    "xjepa_lagged_pred_180m_err",
    "xjepa_prob_short",
    "xjepa_prob_hold",
    "xjepa_prob_long",
    "xjepa_trade_confidence",
    "xjepa_direction_score",
    "xjepa_entropy",
    "xjepa_context_valid",
    "ticker_SPX",
    "ticker_QQQ",
    "ticker_SPY",
    "side_LONG",
    "side_SHORT",
    "jepa180_prob_up",
    "jepa180_confidence",
    "jepa180_direction",
    "jepa180_edge",
    "entry_minute",
    "pos_in_day",
    "minutes_to_close",
    "delta_target",
    "actual_delta",
    "actual_delta_abs",
    "entry_premium",
    "raw_entry_premium",
    "entry_spread_pct",
    "premium_to_spot_bps",
    "strike_distance_pts",
    "strike_distance_bps",
    "actual_iv",
    "actual_theta",
    "actual_gamma",
    "theta_over_premium",
    "gamma_notional"
  ],
  "exit_features": [
    "net_gamma",
    "net_vanna",
    "net_charm",
    "net_dgex",
    "net_zomma",
    "net_delta",
    "signal_persistence_5m",
    "gamma_regime",
    "vanna_bullish",
    "charm_bullish",
    "dgex_sticky",
    "zomma_stabilizing",
    "dist_to_max_gamma",
    "dist_to_min_gamma",
    "dist_to_min_vanna",
    "dist_to_zero_gamma",
    "dist_to_max_dgex",
    "dist_to_min_dgex",
    "near_min_vanna",
    "wk_net_gamma",
    "wk_net_vanna",
    "wk_net_charm",
    "wk_net_dgex",
    "wk_net_zomma",
    "wk_net_delta",
    "wk_net_vega",
    "wk_net_vomma",
    "wk_gamma_regime",
    "wk_vanna_bullish",
    "wk_dgex_sticky",
    "wk_zomma_stabilizing",
    "gamma_0dte_vs_wk",
    "vanna_0dte_vs_wk",
    "dgex_0dte_vs_wk",
    "delta_0dte_vs_wk",
    "vega_0dte_vs_wk",
    "vomma_0dte_vs_wk",
    "vix_5d_mean",
    "vix_5d_std",
    "atr_5d_norm",
    "price_vs_ib_high",
    "price_vs_ib_low",
    "ib_range_pct",
    "near_ib_high",
    "near_ib_low",
    "above_ib",
    "below_ib",
    "in_ib_range",
    "dist_fib_127_up",
    "dist_fib_161_up",
    "dist_fib_200_up",
    "dist_fib_127_dn",
    "dist_fib_161_dn",
    "dist_fib_200_dn",
    "atm_iv",
    "iv_zscore",
    "iv_percentile",
    "vix_spot",
    "vix_gamma",
    "vix_regime",
    "rsi",
    "gamma_vanna_ratio",
    "dgex_gamma_ratio",
    "charm_vanna_ratio",
    "delta_gamma_ratio",
    "vega_gamma_ratio",
    "vomma_vega_ratio",
    "gamma_change",
    "vanna_change",
    "dgex_change",
    "delta_change",
    "vega_change",
    "vomma_change",
    "spot_change",
    "gamma_momentum",
    "price_vs_dgex_magnet",
    "net_vega",
    "net_vomma",
    "vega_elevated",
    "dist_to_max_vega",
    "dist_to_min_vega",
    "dist_to_max_vomma",
    "dist_to_min_vomma",
    "confluence_ib_high_max_gamma",
    "confluence_ib_low_min_gamma",
    "confluence_ib_high_max_vega",
    "confluence_ib_low_max_dgex",
    "confluence_fib127_bull_max_gamma",
    "confluence_fib161_bull_max_vega",
    "confluence_fib127_bear_min_gamma",
    "confluence_fib161_bear_max_vomma",
    "confluence_fib161_bull_max_vomma",
    "confluence_fib127_bear_min_vomma",
    "confluence_fib127_bull_max_dgex",
    "confluence_fib127_bear_min_dgex",
    "confluence_fib161_bull_max_dgex",
    "confluence_fib161_bear_min_dgex",
    "rvol_iv_log",
    "rvol_trend",
    "rvol_regime",
    "dist_ib_high_D1",
    "dist_ib_low_D1",
    "prev_close_vs_ib_D1",
    "dist_ib_high_D2",
    "dist_ib_low_D2",
    "prev_close_vs_ib_D2",
    "dist_ib_high_D3",
    "dist_ib_low_D3",
    "prev_close_vs_ib_D3",
    "dist_ib_high_D4",
    "dist_ib_low_D4",
    "prev_close_vs_ib_D4",
    "dist_ib_high_D5",
    "dist_ib_low_D5",
    "prev_close_vs_ib_D5",
    "ret_1m_vol_adj",
    "ret_5m_vol_adj",
    "ret_15m_vol_adj",
    "time_sin",
    "time_cos",
    "minutes_to_close_norm",
    "dow_sin",
    "dow_cos",
    "ib_range_percentile",
    "gap_pct",
    "gap_direction",
    "overnight_vs_ib_ratio",
    "days_to_opex_norm",
    "is_opex_week",
    "is_quarterly_opex_week",
    "charm_accel_weighted",
    "gamma_speed",
    "gamma_phase_sin",
    "gamma_phase_cos",
    "gamma_amplitude_ratio",
    "gamma_phase_delta",
    "delta_filtered_pcr",
    "pcr_derivative_5m",
    "tlt_ret_1m",
    "tlt_ret_5m",
    "tlt_ret_15m",
    "confluence_d1ibh_max_gamma",
    "confluence_d1ibl_min_gamma",
    "confluence_d1ibh_max_dgex",
    "confluence_d1ibl_min_dgex",
    "confluence_d1ibh_max_vomma",
    "confluence_d1ibh_ibh_today",
    "confluence_d1ibl_ibl_today",
    "speed_x_near_ib_high",
    "speed_x_near_ib_low",
    "charm_accel_x_near_ib_high",
    "charm_accel_x_near_ib_low",
    "wonham_trend_prob",
    "nearest_level_dist",
    "level_cluster_density",
    "momentum_5m_bps",
    "rejection_bullish",
    "rejection_bearish",
    "trend_grind_up",
    "trend_flush_down",
    "bouncing_from_support",
    "rejecting_resistance",
    "wall_at_fib",
    "wall_at_ib",
    "is_touching_fib",
    "is_touching_max_gamma",
    "is_touching_min_gamma",
    "is_touching_max_dgex",
    "nearest_level_id",
    "nearest_level_dist_bps",
    "gamma_x_near_fib_up",
    "gamma_x_near_fib_dn",
    "gamma_x_near_ib",
    "delta_x_near_fib_up",
    "delta_x_near_fib_dn",
    "delta_x_near_ib_high",
    "delta_x_near_ib_low",
    "vanna_x_near_fib_up",
    "vanna_x_near_fib_dn",
    "vanna_x_near_ib",
    "xjepa_z_00",
    "xjepa_z_01",
    "xjepa_z_02",
    "xjepa_z_03",
    "xjepa_z_04",
    "xjepa_z_05",
    "xjepa_z_06",
    "xjepa_z_07",
    "xjepa_z_08",
    "xjepa_z_09",
    "xjepa_z_10",
    "xjepa_z_11",
    "xjepa_z_12",
    "xjepa_z_13",
    "xjepa_z_14",
    "xjepa_z_15",
    "xjepa_u_00",
    "xjepa_u_01",
    "xjepa_u_02",
    "xjepa_u_03",
    "xjepa_u_04",
    "xjepa_u_05",
    "xjepa_u_06",
    "xjepa_u_07",
    "xjepa_u_08",
    "xjepa_u_09",
    "xjepa_u_10",
    "xjepa_u_11",
    "xjepa_latent_velocity",
    "xjepa_input_velocity",
    "xjepa_pred_dispersion_short",
    "xjepa_pred_dispersion_long",
    "xjepa_lagged_pred_30m_err",
    "xjepa_lagged_pred_60m_err",
    "xjepa_lagged_pred_180m_err",
    "xjepa_prob_short",
    "xjepa_prob_hold",
    "xjepa_prob_long",
    "xjepa_trade_confidence",
    "xjepa_direction_score",
    "xjepa_entropy",
    "xjepa_context_valid",
    "ticker_SPX",
    "ticker_QQQ",
    "ticker_SPY",
    "side_LONG",
    "side_SHORT",
    "jepa180_prob_up",
    "jepa180_confidence",
    "jepa180_direction",
    "jepa180_edge",
    "entry_minute",
    "pos_in_day",
    "minutes_to_close",
    "delta_target",
    "actual_delta",
    "actual_delta_abs",
    "entry_premium",
    "raw_entry_premium",
    "entry_spread_pct",
    "premium_to_spot_bps",
    "strike_distance_pts",
    "strike_distance_bps",
    "actual_iv",
    "actual_theta",
    "actual_gamma",
    "theta_over_premium",
    "gamma_notional",
    "hold_minutes",
    "hold_norm",
    "current_pnl_pct",
    "current_return_on_risk",
    "current_premium",
    "premium_ratio",
    "peak_pnl_pct",
    "drawdown_from_peak",
    "mae_pnl_pct",
    "current_delta",
    "current_delta_abs",
    "current_iv",
    "current_gamma",
    "spot_return_bps",
    "signed_spot_return_bps",
    "minutes_remaining"
  ],
  "train_candidates": 18823,
  "test_candidates": 728,
  "train_signals": 2689,
  "test_signals": 104,
  "validation": {
    "val_months": [
      "202601",
      "202602",
      "202603"
    ],
    "best_fixed_delta": 0.7,
    "fixed_delta_grid": [
      {
        "delta_target": 0.1,
        "score": -1000029669.1321275,
        "trades": 182,
        "win_rate": 0.08241758241758242,
        "profit_factor": 0.5687644824205662,
        "pnl_dollars": -29669.132127553625,
        "max_drawdown": -33871.08528770248,
        "avg_pnl": -163.01720949205287,
        "avg_hold_minutes": 47.08791208791209,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.09894505494505494
      },
      {
        "delta_target": 0.2,
        "score": -1000014320.1697992,
        "trades": 182,
        "win_rate": 0.13736263736263737,
        "profit_factor": 0.7653475362561475,
        "pnl_dollars": -14320.169799214145,
        "max_drawdown": -19640.193108960237,
        "avg_pnl": -78.68225164403377,
        "avg_hold_minutes": 55.714285714285715,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.2001483516483516
      },
      {
        "delta_target": 0.3,
        "score": -1000011611.5267034,
        "trades": 182,
        "win_rate": 0.16483516483516483,
        "profit_factor": 0.8000442298593099,
        "pnl_dollars": -11611.526703414786,
        "max_drawdown": -17782.718371918265,
        "avg_pnl": -63.79959727150981,
        "avg_hold_minutes": 64.86263736263736,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.2975840659340659
      },
      {
        "delta_target": 0.4,
        "score": -1000008653.6803168,
        "trades": 182,
        "win_rate": 0.2032967032967033,
        "profit_factor": 0.8493937962942052,
        "pnl_dollars": -8653.680316751877,
        "max_drawdown": -13822.006732356462,
        "avg_pnl": -47.54769404808724,
        "avg_hold_minutes": 72.99450549450549,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.39689615384615384
      },
      {
        "delta_target": 0.5,
        "score": 4.874091620899942,
        "trades": 182,
        "win_rate": 0.27472527472527475,
        "profit_factor": 1.0091436303578527,
        "pnl_dollars": 515.5411241989905,
        "max_drawdown": -8691.645201946256,
        "avg_pnl": 2.832643539554893,
        "avg_hold_minutes": 84.6978021978022,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.5024884615384615
      },
      {
        "delta_target": 0.6,
        "score": 7.984454945794817,
        "trades": 182,
        "win_rate": 0.3791208791208791,
        "profit_factor": 1.300587235563318,
        "pnl_dollars": 16234.698324533292,
        "max_drawdown": -8288.121617758414,
        "avg_pnl": 89.20163914578733,
        "avg_hold_minutes": 101.45604395604396,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.6030247252747252
      },
      {
        "delta_target": 0.7,
        "score": 12.288779757705854,
        "trades": 182,
        "win_rate": 0.4725274725274725,
        "profit_factor": 1.7212179364400833,
        "pnl_dollars": 36074.10353458478,
        "max_drawdown": -5705.832033190491,
        "avg_pnl": 198.20936008013615,
        "avg_hold_minutes": 118.13186813186813,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.7043021978021977
      }
    ],
    "entry_threshold": 0.532074180196185,
    "exit_margin": -0.2,
    "entry_threshold_grid": {
      "grid": [
        {
          "threshold": -1000000000.0,
          "score": 11.538767301075696,
          "trades": 182,
          "win_rate": 0.44505494505494503,
          "profit_factor": 1.6553198676212049,
          "pnl_dollars": 32427.92041340084,
          "max_drawdown": -6547.813383207005,
          "avg_pnl": 178.1753868868178,
          "avg_hold_minutes": 112.39010989010988,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6571862637362638
        },
        {
          "threshold": -0.5,
          "score": 11.538767301075696,
          "trades": 182,
          "win_rate": 0.44505494505494503,
          "profit_factor": 1.6553198676212049,
          "pnl_dollars": 32427.92041340084,
          "max_drawdown": -6547.813383207005,
          "avg_pnl": 178.1753868868178,
          "avg_hold_minutes": 112.39010989010988,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6571862637362638
        },
        {
          "threshold": -0.391481504093696,
          "score": 11.538767301075696,
          "trades": 182,
          "win_rate": 0.44505494505494503,
          "profit_factor": 1.6553198676212049,
          "pnl_dollars": 32427.92041340084,
          "max_drawdown": -6547.813383207005,
          "avg_pnl": 178.1753868868178,
          "avg_hold_minutes": 112.39010989010988,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6571862637362638
        },
        {
          "threshold": -0.25,
          "score": 11.946367198614919,
          "trades": 179,
          "win_rate": 0.45251396648044695,
          "profit_factor": 1.7072773115802833,
          "pnl_dollars": 33933.866667509195,
          "max_drawdown": -6256.737593525053,
          "avg_pnl": 189.5746741201631,
          "avg_hold_minutes": 113.57541899441341,
          "long_rate": 0.40782122905027934,
          "avg_delta_abs": 0.6621206703910615
        },
        {
          "threshold": -0.2391910109647856,
          "score": 11.946367198614919,
          "trades": 179,
          "win_rate": 0.45251396648044695,
          "profit_factor": 1.7072773115802833,
          "pnl_dollars": 33933.866667509195,
          "max_drawdown": -6256.737593525053,
          "avg_pnl": 189.5746741201631,
          "avg_hold_minutes": 113.57541899441341,
          "long_rate": 0.40782122905027934,
          "avg_delta_abs": 0.6621206703910615
        },
        {
          "threshold": -0.19888879713603913,
          "score": 12.157592232509202,
          "trades": 177,
          "win_rate": 0.4576271186440678,
          "profit_factor": 1.7362639148613872,
          "pnl_dollars": 34734.85319190981,
          "max_drawdown": -6256.737593525053,
          "avg_pnl": 196.242108428869,
          "avg_hold_minutes": 113.954802259887,
          "long_rate": 0.4067796610169492,
          "avg_delta_abs": 0.6654282485875707
        },
        {
          "threshold": -0.13216974693918856,
          "score": 12.728161715326754,
          "trades": 172,
          "win_rate": 0.46511627906976744,
          "profit_factor": 1.8150655586003728,
          "pnl_dollars": 36635.140093435664,
          "max_drawdown": -5778.287612290589,
          "avg_pnl": 212.99500054323062,
          "avg_hold_minutes": 114.59302325581395,
          "long_rate": 0.4011627906976744,
          "avg_delta_abs": 0.6659843023255815
        },
        {
          "threshold": -0.1,
          "score": 13.801392615686018,
          "trades": 167,
          "win_rate": 0.47904191616766467,
          "profit_factor": 1.9671069972492519,
          "pnl_dollars": 40109.21598763276,
          "max_drawdown": -5778.287612290591,
          "avg_pnl": 240.17494603372907,
          "avg_hold_minutes": 115.7185628742515,
          "long_rate": 0.39520958083832336,
          "avg_delta_abs": 0.6670730538922157
        },
        {
          "threshold": -0.06893888509846369,
          "score": 13.970254557321315,
          "trades": 164,
          "win_rate": 0.4878048780487805,
          "profit_factor": 1.9928727680354688,
          "pnl_dollars": 40645.42389439256,
          "max_drawdown": -5395.750442567274,
          "avg_pnl": 247.83795057556438,
          "avg_hold_minutes": 115.39634146341463,
          "long_rate": 0.3902439024390244,
          "avg_delta_abs": 0.6677384146341464
        },
        {
          "threshold": -0.005358169628944671,
          "score": 13.324582652089113,
          "trades": 155,
          "win_rate": 0.49032258064516127,
          "profit_factor": 1.9530927455625784,
          "pnl_dollars": 37315.330403227985,
          "max_drawdown": -5395.7504425672705,
          "avg_pnl": 240.7440671175999,
          "avg_hold_minutes": 114.25806451612904,
          "long_rate": 0.4,
          "avg_delta_abs": 0.670965806451613
        },
        {
          "threshold": 0.0,
          "score": 13.43603985933699,
          "trades": 154,
          "win_rate": 0.4935064935064935,
          "profit_factor": 1.9707336814453593,
          "pnl_dollars": 37665.79633705094,
          "max_drawdown": -5395.7504425672705,
          "avg_pnl": 244.58309309773338,
          "avg_hold_minutes": 114.90259740259741,
          "long_rate": 0.3961038961038961,
          "avg_delta_abs": 0.6707350649350651
        },
        {
          "threshold": 0.04864754962413943,
          "score": 13.725664692044278,
          "trades": 143,
          "win_rate": 0.48951048951048953,
          "profit_factor": 2.053074448455457,
          "pnl_dollars": 37920.555152190514,
          "max_drawdown": -5395.750442567274,
          "avg_pnl": 265.1787073579756,
          "avg_hold_minutes": 114.96503496503496,
          "long_rate": 0.40559440559440557,
          "avg_delta_abs": 0.6700573426573427
        },
        {
          "threshold": 0.05,
          "score": 13.62578326735207,
          "trades": 142,
          "win_rate": 0.4859154929577465,
          "profit_factor": 2.0430818745940997,
          "pnl_dollars": 37560.728789697634,
          "max_drawdown": -5395.750442567274,
          "avg_pnl": 264.51217457533545,
          "avg_hold_minutes": 114.50704225352112,
          "long_rate": 0.4084507042253521,
          "avg_delta_abs": 0.6698936619718311
        },
        {
          "threshold": 0.1,
          "score": 12.97135930268469,
          "trades": 124,
          "win_rate": 0.5,
          "profit_factor": 2.0478793208002024,
          "pnl_dollars": 33381.37097273677,
          "max_drawdown": -5091.633030918232,
          "avg_pnl": 269.2046046188449,
          "avg_hold_minutes": 113.4274193548387,
          "long_rate": 0.4274193548387097,
          "avg_delta_abs": 0.6704427419354839
        },
        {
          "threshold": 0.11357530891413539,
          "score": 12.492349322368124,
          "trades": 117,
          "win_rate": 0.48717948717948717,
          "profit_factor": 2.015139700552014,
          "pnl_dollars": 31333.34988340198,
          "max_drawdown": -5091.633030918232,
          "avg_pnl": 267.80640925984596,
          "avg_hold_minutes": 111.28205128205128,
          "long_rate": 0.4188034188034188,
          "avg_delta_abs": 0.66761452991453
        },
        {
          "threshold": 0.19252662207299015,
          "score": 14.660994485080673,
          "trades": 89,
          "win_rate": 0.550561797752809,
          "profit_factor": 2.543154354619864,
          "pnl_dollars": 34027.52066656966,
          "max_drawdown": -3709.3627927456164,
          "avg_pnl": 382.33169288280516,
          "avg_hold_minutes": 118.48314606741573,
          "long_rate": 0.34831460674157305,
          "avg_delta_abs": 0.6604202247191012
        },
        {
          "threshold": 0.2,
          "score": 14.459603535163998,
          "trades": 88,
          "win_rate": 0.5454545454545454,
          "profit_factor": 2.517312810097076,
          "pnl_dollars": 33457.698414069295,
          "max_drawdown": -3709.3627927456164,
          "avg_pnl": 380.20111834169654,
          "avg_hold_minutes": 117.7840909090909,
          "long_rate": 0.3409090909090909,
          "avg_delta_abs": 0.6628829545454545
        },
        {
          "threshold": 0.3,
          "score": 14.733762074731294,
          "trades": 68,
          "win_rate": 0.5735294117647058,
          "profit_factor": 2.7991225356034235,
          "pnl_dollars": 30674.472792053442,
          "max_drawdown": -3709.3627927456164,
          "avg_pnl": 451.095188118433,
          "avg_hold_minutes": 118.52941176470588,
          "long_rate": 0.27941176470588236,
          "avg_delta_abs": 0.6659176470588236
        },
        {
          "threshold": 0.320570908783404,
          "score": 14.684865161753779,
          "trades": 65,
          "win_rate": 0.5692307692307692,
          "profit_factor": 2.8227951571575773,
          "pnl_dollars": 30437.96185436587,
          "max_drawdown": -3709.3627927456164,
          "avg_pnl": 468.27633622101337,
          "avg_hold_minutes": 117.61538461538461,
          "long_rate": 0.24615384615384617,
          "avg_delta_abs": 0.6653015384615385
        },
        {
          "threshold": 0.532074180196185,
          "score": 19.04996999515226,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.684027013241054,
          "pnl_dollars": 24860.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 731.199098785568,
          "avg_hold_minutes": 111.02941176470588,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        }
      ]
    },
    "exit_margin_grid": {
      "grid": [
        {
          "exit_margin": -0.2,
          "score": 18.316550696542226,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.510648967561948,
          "pnl_dollars": 23690.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 696.7873340796857,
          "avg_hold_minutes": 105.73529411764706,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        },
        {
          "exit_margin": -0.1,
          "score": 18.147300089170677,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.470638649328308,
          "pnl_dollars": 23420.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 688.8461576090974,
          "avg_hold_minutes": 105.44117647058823,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        },
        {
          "exit_margin": -0.05,
          "score": 18.10342030207435,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.460265603860327,
          "pnl_dollars": 23350.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 686.7873340796857,
          "avg_hold_minutes": 105.29411764705883,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        },
        {
          "exit_margin": 0.0,
          "score": 17.971780940785372,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.429146467456385,
          "pnl_dollars": 23140.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 680.6108634914503,
          "avg_hold_minutes": 104.55882352941177,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        },
        {
          "exit_margin": 0.05,
          "score": 17.89342417811336,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.410623171977848,
          "pnl_dollars": 23015.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 676.9343929032151,
          "avg_hold_minutes": 104.41176470588235,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        },
        {
          "exit_margin": 0.1,
          "score": 17.663368722908334,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.356238776452863,
          "pnl_dollars": 22648.769358709313,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 666.1402752561562,
          "avg_hold_minutes": 103.38235294117646,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        },
        {
          "exit_margin": 0.2,
          "score": 17.610086124291364,
          "trades": 34,
          "win_rate": 0.5588235294117647,
          "profit_factor": 4.343642935527458,
          "pnl_dollars": 22563.76935870932,
          "max_drawdown": -1789.066044186009,
          "avg_pnl": 663.6402752561564,
          "avg_hold_minutes": 102.3529411764706,
          "long_rate": 0.058823529411764705,
          "avg_delta_abs": 0.6571441176470588
        }
      ]
    },
    "entry_validation_metrics": {
      "trades": 34,
      "win_rate": 0.5588235294117647,
      "profit_factor": 4.684027013241054,
      "pnl_dollars": 24860.769358709313,
      "max_drawdown": -1789.066044186009,
      "avg_pnl": 731.199098785568,
      "avg_hold_minutes": 111.02941176470588,
      "long_rate": 0.058823529411764705,
      "avg_delta_abs": 0.6571441176470588
    }
  },
  "policy_metrics": {
    "fixed_delta_0.60_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.38461538461538464,
        "profit_factor": 1.6723069478233359,
        "pnl_dollars": 19285.713332255153,
        "max_drawdown": -4201.199459318421,
        "avg_pnl": 185.43955127168417,
        "avg_hold_minutes": 108.89423076923077,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.6028653846153846
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.4,
          "profit_factor": 1.3282274721612175,
          "pnl_dollars": 2593.170355607453,
          "max_drawdown": -2453.986249960487,
          "avg_pnl": 74.09058158878437,
          "avg_hold_minutes": 98.85714285714286,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6025828571428571
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 2.316633958610674,
          "pnl_dollars": 16083.512195689156,
          "max_drawdown": -1771.6954782217836,
          "avg_pnl": 459.528919876833,
          "avg_hold_minutes": 120.85714285714286,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.5993685714285714
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.0710677725779407,
          "pnl_dollars": 609.0307809585381,
          "max_drawdown": -2429.503981096632,
          "avg_pnl": 17.9126700281923,
          "avg_hold_minutes": 106.91176470588235,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6067558823529412
        }
      }
    },
    "fixed_delta_0.70_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.4326923076923077,
        "profit_factor": 1.7730937596517395,
        "pnl_dollars": 21487.335047192435,
        "max_drawdown": -4327.491368523391,
        "avg_pnl": 206.6089908383888,
        "avg_hold_minutes": 120.72115384615384,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.7021144230769232
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.3721669742786247,
          "pnl_dollars": 2383.6570487517897,
          "max_drawdown": -2112.0218844432366,
          "avg_pnl": 68.10448710719399,
          "avg_hold_minutes": 111.85714285714286,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.7020771428571428
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.5428571428571428,
          "profit_factor": 2.345146716659212,
          "pnl_dollars": 18655.900483443565,
          "max_drawdown": -2669.0211155970046,
          "avg_pnl": 533.0257280983876,
          "avg_hold_minutes": 136.28571428571428,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.7032371428571428
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.0595440356812984,
          "pnl_dollars": 447.7775149970818,
          "max_drawdown": -2387.3277811256717,
          "avg_pnl": 13.169926911678877,
          "avg_hold_minutes": 113.82352941176471,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.7009970588235294
        }
      }
    },
    "validation_best_delta_0.70_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.4326923076923077,
        "profit_factor": 1.7730937596517395,
        "pnl_dollars": 21487.335047192435,
        "max_drawdown": -4327.491368523391,
        "avg_pnl": 206.6089908383888,
        "avg_hold_minutes": 120.72115384615384,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.7021144230769232
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.3721669742786247,
          "pnl_dollars": 2383.6570487517897,
          "max_drawdown": -2112.0218844432366,
          "avg_pnl": 68.10448710719399,
          "avg_hold_minutes": 111.85714285714286,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.7020771428571428
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.5428571428571428,
          "profit_factor": 2.345146716659212,
          "pnl_dollars": 18655.900483443565,
          "max_drawdown": -2669.0211155970046,
          "avg_pnl": 533.0257280983876,
          "avg_hold_minutes": 136.28571428571428,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.7032371428571428
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.0595440356812984,
          "pnl_dollars": 447.7775149970818,
          "max_drawdown": -2387.3277811256717,
          "avg_pnl": 13.169926911678877,
          "avg_hold_minutes": 113.82352941176471,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.7009970588235294
        }
      }
    },
    "learned_delta_regression_all_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.40384615384615385,
        "profit_factor": 1.6143167989062197,
        "pnl_dollars": 17411.76836696509,
        "max_drawdown": -4752.74045156978,
        "avg_pnl": 167.42084968235665,
        "avg_hold_minutes": 112.11538461538461,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.645751923076923
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.2908679609459024,
          "pnl_dollars": 2012.4874400069198,
          "max_drawdown": -2094.8171624599645,
          "avg_pnl": 57.49964114305485,
          "avg_hold_minutes": 108.0,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6791742857142857
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.45714285714285713,
          "profit_factor": 2.137477426198236,
          "pnl_dollars": 15294.242885709835,
          "max_drawdown": -3400.7979813663687,
          "avg_pnl": 436.97836816313816,
          "avg_hold_minutes": 120.14285714285714,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.6318314285714286
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.0131648954431571,
          "pnl_dollars": 105.03804124833181,
          "max_drawdown": -2812.576864172061,
          "avg_pnl": 3.0893541543627,
          "avg_hold_minutes": 108.08823529411765,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6256764705882354
        }
      }
    },
    "learned_delta_ranker_all_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.375,
        "profit_factor": 1.5307694722818705,
        "pnl_dollars": 13844.067193403083,
        "max_drawdown": -3705.6656702254822,
        "avg_pnl": 133.1160307057989,
        "avg_hold_minutes": 108.84615384615384,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.6415067307692308
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.3721669742786247,
          "pnl_dollars": 2383.6570487517897,
          "max_drawdown": -2112.0218844432366,
          "avg_pnl": 68.10448710719399,
          "avg_hold_minutes": 111.85714285714286,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.7020771428571428
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.37142857142857144,
          "profit_factor": 1.8933610642852066,
          "pnl_dollars": 10797.499868688954,
          "max_drawdown": -3330.8535836446126,
          "avg_pnl": 308.49999624825585,
          "avg_hold_minutes": 101.0,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.529
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.087318910170571,
          "pnl_dollars": 662.9102759623372,
          "max_drawdown": -2166.35458442004,
          "avg_pnl": 19.4973610577158,
          "avg_hold_minutes": 113.82352941176471,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6949705882352941
        }
      }
    },
    "supervised_entry_strike_skip_hard": {
      "overall": {
        "trades": 3,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "pnl_dollars": -1279.3410912065794,
        "max_drawdown": -1279.3410912065794,
        "avg_pnl": -426.44703040219315,
        "avg_hold_minutes": 48.333333333333336,
        "long_rate": 1.0,
        "avg_delta_abs": 0.5385666666666666
      },
      "per_ticker": {
        "QQQ": {
          "trades": 3,
          "win_rate": 0.0,
          "profit_factor": 0.0,
          "pnl_dollars": -1279.3410912065794,
          "max_drawdown": -1279.3410912065794,
          "avg_pnl": -426.44703040219315,
          "avg_hold_minutes": 48.333333333333336,
          "long_rate": 1.0,
          "avg_delta_abs": 0.5385666666666666
        }
      }
    },
    "supervised_entry_strike_learned_exit": {
      "overall": {
        "trades": 3,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "pnl_dollars": -1279.3410912065794,
        "max_drawdown": -1279.3410912065794,
        "avg_pnl": -426.44703040219315,
        "avg_hold_minutes": 48.333333333333336,
        "long_rate": 1.0,
        "avg_delta_abs": 0.5385666666666666
      },
      "per_ticker": {
        "QQQ": {
          "trades": 3,
          "win_rate": 0.0,
          "profit_factor": 0.0,
          "pnl_dollars": -1279.3410912065794,
          "max_drawdown": -1279.3410912065794,
          "avg_pnl": -426.44703040219315,
          "avg_hold_minutes": 48.333333333333336,
          "long_rate": 1.0,
          "avg_delta_abs": 0.5385666666666666
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.4326923076923077,
        "profit_factor": 4.151548154964666,
        "pnl_dollars": 54490.33466571002,
        "max_drawdown": -1762.49950754418,
        "avg_pnl": 523.9455256318271,
        "avg_hold_minutes": 103.60576923076923,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.5153865384615385
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 2.8369844017491443,
          "pnl_dollars": 11092.03477498964,
          "max_drawdown": -1762.49950754418,
          "avg_pnl": 316.91527928541825,
          "avg_hold_minutes": 104.14285714285714,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.5283514285714286
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.5428571428571428,
          "profit_factor": 8.393806126098559,
          "pnl_dollars": 30203.653420330193,
          "max_drawdown": -890.972140915509,
          "avg_pnl": 862.9615262951484,
          "avg_hold_minutes": 112.85714285714286,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.5077799999999999
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 2.841065977373498,
          "pnl_dollars": 13194.646470390184,
          "max_drawdown": -1441.5848443971167,
          "avg_pnl": 388.0778373644172,
          "avg_hold_minutes": 93.52941176470588,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.509870588235294
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 104,
        "win_rate": 0.875,
        "profit_factor": 139.89437446863488,
        "pnl_dollars": 166873.07809124154,
        "max_drawdown": -342.42661216767584,
        "avg_pnl": 1604.5488278003993,
        "avg_hold_minutes": 88.5576923076923,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.4623865384615385
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.8571428571428571,
          "profit_factor": 75.5366985203139,
          "pnl_dollars": 50515.71667452988,
          "max_drawdown": -342.42661216767584,
          "avg_pnl": 1443.3061907008537,
          "avg_hold_minutes": 82.71428571428571,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.43162
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.9142857142857143,
          "profit_factor": 242.68035802538822,
          "pnl_dollars": 80242.23202329787,
          "max_drawdown": -157.42959075512044,
          "avg_pnl": 2292.6352006656534,
          "avg_hold_minutes": 99.57142857142857,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.5387914285714285
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.8529411764705882,
          "profit_factor": 189.40261230585097,
          "pnl_dollars": 36115.12939341375,
          "max_drawdown": -84.68778027878943,
          "avg_pnl": 1062.2096880415809,
          "avg_hold_minutes": 83.23529411764706,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.4154058823529412
        }
      }
    }
  }
}
```
