# JEPA Supervised 0DTE Option Policy

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Signal model: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_full_pipeline_180m_frozen_march` / mode `base_jepa`
Train cutoff: `20260331`
Test start: `20260401`
Signals after `180`m cooldown: 2,794 total, 2,689 train, 105 test.
Option candidates with valid real premium paths: 19,558.
Candidate deltas: `0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7`.
Execution: buy 0DTE option, risk capital `$1,000`, max hold `180`m, hard stop `-60%`, take profit `250%`.

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
| fixed_delta_0.60_hard | 105 | 51.4% | 1.885 | +25,226 | -3,354 | +240 | 152.6 | 0.603 |
| fixed_delta_0.70_hard | 105 | 56.2% | 2.033 | +28,115 | -3,548 | +268 | 161.0 | 0.702 |
| validation_best_delta_0.70_hard | 105 | 56.2% | 2.033 | +28,115 | -3,548 | +268 | 161.0 | 0.702 |
| learned_delta_regression_all_hard | 105 | 53.3% | 1.889 | +26,223 | -3,548 | +250 | 156.5 | 0.635 |
| learned_delta_ranker_all_hard | 105 | 55.2% | 1.965 | +27,145 | -3,548 | +259 | 159.7 | 0.686 |
| supervised_entry_strike_skip_hard | 46 | 58.7% | 2.235 | +19,472 | -2,389 | +423 | 156.1 | 0.642 |
| supervised_entry_strike_learned_exit | 46 | 58.7% | 2.489 | +23,381 | -2,389 | +508 | 149.9 | 0.642 |
| oracle_best_delta_hard | 105 | 56.2% | 5.053 | +69,480 | -1,703 | +662 | 144.6 | 0.548 |
| oracle_best_delta_oracle_exit | 105 | 87.6% | 140.828 | +167,995 | -342 | +1,600 | 89.2 | 0.464 |

## Per-Ticker OOS Results

### fixed_delta_0.60_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 45.7% | 1.236 | +2,092 | -3,354 | +60 | 139.0 | 0.603 |
| SPX | 36 | 58.3% | 2.553 | +18,849 | -2,795 | +524 | 156.5 | 0.600 |
| SPY | 34 | 50.0% | 1.571 | +4,286 | -2,364 | +126 | 162.4 | 0.607 |

### fixed_delta_0.70_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 51.4% | 1.474 | +3,229 | -2,144 | +92 | 151.4 | 0.702 |
| SPX | 36 | 63.9% | 2.406 | +20,298 | -3,548 | +564 | 166.1 | 0.703 |
| SPY | 34 | 52.9% | 1.770 | +4,589 | -2,261 | +135 | 165.6 | 0.701 |

### validation_best_delta_0.70_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 51.4% | 1.474 | +3,229 | -2,144 | +92 | 151.4 | 0.702 |
| SPX | 36 | 63.9% | 2.406 | +20,298 | -3,548 | +564 | 166.1 | 0.703 |
| SPY | 34 | 52.9% | 1.770 | +4,589 | -2,261 | +135 | 165.6 | 0.701 |

### learned_delta_regression_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 48.6% | 1.388 | +3,294 | -2,917 | +94 | 143.7 | 0.605 |
| SPX | 36 | 58.3% | 2.254 | +18,088 | -3,548 | +502 | 163.6 | 0.662 |
| SPY | 34 | 52.9% | 1.735 | +4,841 | -2,261 | +142 | 162.2 | 0.637 |

### learned_delta_ranker_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 48.6% | 1.290 | +2,209 | -2,332 | +63 | 147.6 | 0.669 |
| SPX | 36 | 63.9% | 2.406 | +20,298 | -3,548 | +564 | 166.1 | 0.703 |
| SPY | 34 | 52.9% | 1.765 | +4,638 | -2,261 | +136 | 165.3 | 0.686 |

### supervised_entry_strike_skip_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 11 | 54.5% | 1.669 | +1,447 | -1,115 | +132 | 151.8 | 0.570 |
| SPX | 23 | 60.9% | 2.246 | +13,864 | -2,389 | +603 | 163.3 | 0.700 |
| SPY | 12 | 58.3% | 2.678 | +4,162 | -687 | +347 | 146.2 | 0.597 |

### supervised_entry_strike_learned_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 11 | 54.5% | 1.895 | +1,874 | -1,115 | +170 | 148.2 | 0.570 |
| SPX | 23 | 60.9% | 2.564 | +17,404 | -2,389 | +757 | 153.7 | 0.700 |
| SPY | 12 | 58.3% | 2.654 | +4,103 | -687 | +342 | 144.2 | 0.597 |

### oracle_best_delta_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 51.4% | 3.341 | +15,364 | -1,703 | +439 | 144.6 | 0.558 |
| SPX | 36 | 63.9% | 7.884 | +33,903 | -1,353 | +942 | 143.2 | 0.571 |
| SPY | 34 | 52.9% | 4.575 | +20,212 | -1,153 | +594 | 146.2 | 0.514 |

### oracle_best_delta_oracle_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 85.7% | 75.537 | +50,516 | -342 | +1,443 | 82.7 | 0.432 |
| SPX | 36 | 91.7% | 246.060 | +81,364 | -157 | +2,260 | 101.1 | 0.543 |
| SPY | 34 | 85.3% | 189.403 | +36,115 | -85 | +1,062 | 83.2 | 0.415 |

## Validation Choices

- Fixed delta selected on pre-April validation: `0.70`.
- Entry utility threshold selected on pre-April validation: `0.3000`.
- Learned-exit margin selected on pre-April validation: `0.0000`.

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
    "data": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\training_data\\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet",
    "signal_model_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\neural\\models\\jepa\\jepa_full_pipeline_180m_frozen_march",
    "signal_mode": "base_jepa",
    "output_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\research_papers\\JEPA\\results\\jepa_full_pipeline_option_policy",
    "model_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\neural\\models\\jepa\\jepa_full_pipeline_option_policy",
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
    "hard_stop_pct": -0.6,
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
    "n_estimators": 260,
    "exit_n_estimators": 220,
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
  "test_candidates": 735,
  "train_signals": 2689,
  "test_signals": 105,
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
        "score": -1000013582.1321275,
        "trades": 182,
        "win_rate": 0.1813186813186813,
        "profit_factor": 0.8414268016031035,
        "pnl_dollars": -13582.132127553627,
        "max_drawdown": -23865.218124454543,
        "avg_pnl": -74.627099601943,
        "avg_hold_minutes": 103.4065934065934,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.09894505494505494
      },
      {
        "delta_target": 0.2,
        "score": 5.284248002501385,
        "trades": 182,
        "win_rate": 0.24725274725274726,
        "profit_factor": 1.051236048469734,
        "pnl_dollars": 3679.330200785852,
        "max_drawdown": -11201.693108960255,
        "avg_pnl": 20.21610000431787,
        "avg_hold_minutes": 106.97802197802197,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.2001483516483516
      },
      {
        "delta_target": 0.3,
        "score": 8.305205065088487,
        "trades": 182,
        "win_rate": 0.3516483516483517,
        "profit_factor": 1.3052608174353357,
        "pnl_dollars": 18434.473296585213,
        "max_drawdown": -6759.608376917833,
        "avg_pnl": 101.28831481640226,
        "avg_hold_minutes": 121.4010989010989,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.2975840659340659
      },
      {
        "delta_target": 0.4,
        "score": 11.7832923983655,
        "trades": 182,
        "win_rate": 0.4230769230769231,
        "profit_factor": 1.6448731331411888,
        "pnl_dollars": 36303.31968324812,
        "max_drawdown": -8319.667604784376,
        "avg_pnl": 199.46878946839627,
        "avg_hold_minutes": 130.6868131868132,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.39689615384615384
      },
      {
        "delta_target": 0.5,
        "score": 15.775490134202439,
        "trades": 182,
        "win_rate": 0.5274725274725275,
        "profit_factor": 2.0456807560249497,
        "pnl_dollars": 54993.04112419899,
        "max_drawdown": -7615.1909972721805,
        "avg_pnl": 302.159566616478,
        "avg_hold_minutes": 140.3021978021978,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.5024884615384615
      },
      {
        "delta_target": 0.6,
        "score": 17.88207326543078,
        "trades": 182,
        "win_rate": 0.5659340659340659,
        "profit_factor": 2.2948675064409474,
        "pnl_dollars": 62452.198324533296,
        "max_drawdown": -6364.541288647786,
        "avg_pnl": 343.143946838095,
        "avg_hold_minutes": 150.82417582417582,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.6030247252747252
      },
      {
        "delta_target": 0.7,
        "score": 19.901033891206982,
        "trades": 182,
        "win_rate": 0.6153846153846154,
        "profit_factor": 2.588070059856908,
        "pnl_dollars": 66958.10353458476,
        "max_drawdown": -5545.832033190494,
        "avg_pnl": 367.9016677724438,
        "avg_hold_minutes": 159.25824175824175,
        "long_rate": 0.41208791208791207,
        "avg_delta_abs": 0.7043021978021977
      }
    ],
    "entry_threshold": 0.3,
    "exit_margin": 0.0,
    "entry_threshold_grid": {
      "grid": [
        {
          "threshold": -1000000000.0,
          "score": 18.52060678544826,
          "trades": 182,
          "win_rate": 0.554945054945055,
          "profit_factor": 2.329720914198531,
          "pnl_dollars": 66612.49544605476,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 366.0027222310701,
          "avg_hold_minutes": 153.04945054945054,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.626812087912088
        },
        {
          "threshold": -0.5172904073966719,
          "score": 18.52060678544826,
          "trades": 182,
          "win_rate": 0.554945054945055,
          "profit_factor": 2.329720914198531,
          "pnl_dollars": 66612.49544605476,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 366.0027222310701,
          "avg_hold_minutes": 153.04945054945054,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.626812087912088
        },
        {
          "threshold": -0.5,
          "score": 18.52060678544826,
          "trades": 182,
          "win_rate": 0.554945054945055,
          "profit_factor": 2.329720914198531,
          "pnl_dollars": 66612.49544605476,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 366.0027222310701,
          "avg_hold_minutes": 153.04945054945054,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.626812087912088
        },
        {
          "threshold": -0.2540725880836995,
          "score": 18.720663185669945,
          "trades": 181,
          "win_rate": 0.5580110497237569,
          "profit_factor": 2.3587640438538107,
          "pnl_dollars": 67229.30929877936,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 371.4326480595545,
          "avg_hold_minutes": 153.67403314917127,
          "long_rate": 0.4143646408839779,
          "avg_delta_abs": 0.62673591160221
        },
        {
          "threshold": -0.25,
          "score": 18.720663185669945,
          "trades": 181,
          "win_rate": 0.5580110497237569,
          "profit_factor": 2.3587640438538107,
          "pnl_dollars": 67229.30929877936,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 371.4326480595545,
          "avg_hold_minutes": 153.67403314917127,
          "long_rate": 0.4143646408839779,
          "avg_delta_abs": 0.62673591160221
        },
        {
          "threshold": -0.1494020104832998,
          "score": 18.720663185669945,
          "trades": 181,
          "win_rate": 0.5580110497237569,
          "profit_factor": 2.3587640438538107,
          "pnl_dollars": 67229.30929877936,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 371.4326480595545,
          "avg_hold_minutes": 153.67403314917127,
          "long_rate": 0.4143646408839779,
          "avg_delta_abs": 0.62673591160221
        },
        {
          "threshold": -0.1,
          "score": 18.88786946705607,
          "trades": 180,
          "win_rate": 0.5611111111111111,
          "profit_factor": 2.383536388612424,
          "pnl_dollars": 67743.54228599841,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 376.35301269999115,
          "avg_hold_minutes": 153.61111111111111,
          "long_rate": 0.4111111111111111,
          "avg_delta_abs": 0.6264116666666667
        },
        {
          "threshold": -0.02465773173258236,
          "score": 18.986755547801714,
          "trades": 176,
          "win_rate": 0.5681818181818182,
          "profit_factor": 2.408296242208273,
          "pnl_dollars": 67983.45199396327,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 386.26961360206406,
          "avg_hold_minutes": 153.01136363636363,
          "long_rate": 0.4090909090909091,
          "avg_delta_abs": 0.6255897727272728
        },
        {
          "threshold": 0.0,
          "score": 19.515794505525204,
          "trades": 170,
          "win_rate": 0.5764705882352941,
          "profit_factor": 2.4994665113778165,
          "pnl_dollars": 69416.70234934565,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 408.333543231445,
          "avg_hold_minutes": 153.76470588235293,
          "long_rate": 0.4,
          "avg_delta_abs": 0.6248776470588235
        },
        {
          "threshold": 0.05,
          "score": 19.619939497648854,
          "trades": 163,
          "win_rate": 0.5828220858895705,
          "profit_factor": 2.5480847246101295,
          "pnl_dollars": 69023.39357017512,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 423.456402271013,
          "avg_hold_minutes": 153.55828220858896,
          "long_rate": 0.4110429447852761,
          "avg_delta_abs": 0.6222398773006135
        },
        {
          "threshold": 0.08683147699724106,
          "score": 19.621252614597967,
          "trades": 160,
          "win_rate": 0.58125,
          "profit_factor": 2.562021731802893,
          "pnl_dollars": 68798.75805089217,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 429.99223781807603,
          "avg_hold_minutes": 153.0625,
          "long_rate": 0.4125,
          "avg_delta_abs": 0.621516875
        },
        {
          "threshold": 0.1,
          "score": 19.71305213748594,
          "trades": 157,
          "win_rate": 0.5796178343949044,
          "profit_factor": 2.586880756889516,
          "pnl_dollars": 68940.14068283558,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 439.1091763237935,
          "avg_hold_minutes": 153.5031847133758,
          "long_rate": 0.4140127388535032,
          "avg_delta_abs": 0.6223713375796178
        },
        {
          "threshold": 0.2,
          "score": 20.216282069106047,
          "trades": 147,
          "win_rate": 0.6054421768707483,
          "profit_factor": 2.6996927383107225,
          "pnl_dollars": 70026.35983487376,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 476.3697947950596,
          "avg_hold_minutes": 152.27891156462584,
          "long_rate": 0.41496598639455784,
          "avg_delta_abs": 0.6200904761904762
        },
        {
          "threshold": 0.20155261861014356,
          "score": 20.66121146299201,
          "trades": 146,
          "win_rate": 0.6095890410958904,
          "profit_factor": 2.771210944680973,
          "pnl_dollars": 71089.61661477723,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 486.91518229299476,
          "avg_hold_minutes": 152.87671232876713,
          "long_rate": 0.4178082191780822,
          "avg_delta_abs": 0.619267808219178
        },
        {
          "threshold": 0.3,
          "score": 20.913315002480967,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.887041071002776,
          "pnl_dollars": 70288.76854234704,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 524.5430488234854,
          "avg_hold_minutes": 152.57462686567163,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "threshold": 0.3179925979296413,
          "score": 20.325700756251653,
          "trades": 132,
          "win_rate": 0.6212121212121212,
          "profit_factor": 2.8238358504149326,
          "pnl_dollars": 67934.49168593177,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 514.6552400449377,
          "avg_hold_minutes": 152.1590909090909,
          "long_rate": 0.4166666666666667,
          "avg_delta_abs": 0.6184848484848485
        },
        {
          "threshold": 0.4242392495905458,
          "score": 17.39004313158929,
          "trades": 113,
          "win_rate": 0.5929203539823009,
          "profit_factor": 2.5432750979924794,
          "pnl_dollars": 56218.79160296476,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 497.5114301147324,
          "avg_hold_minutes": 149.69026548672565,
          "long_rate": 0.37168141592920356,
          "avg_delta_abs": 0.6208469026548672
        },
        {
          "threshold": 0.5175511263346324,
          "score": 18.59704639546295,
          "trades": 91,
          "win_rate": 0.6373626373626373,
          "profit_factor": 2.914157413012611,
          "pnl_dollars": 56971.342952392646,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 626.0587137625565,
          "avg_hold_minutes": 150.4945054945055,
          "long_rate": 0.34065934065934067,
          "avg_delta_abs": 0.6182263736263737
        },
        {
          "threshold": 0.6943002574490443,
          "score": 15.25156361857736,
          "trades": 61,
          "win_rate": 0.6065573770491803,
          "profit_factor": 2.7389975192737985,
          "pnl_dollars": 42246.443778887835,
          "max_drawdown": -5545.832033190491,
          "avg_pnl": 692.5646521129154,
          "avg_hold_minutes": 150.1639344262295,
          "long_rate": 0.3114754098360656,
          "avg_delta_abs": 0.6392393442622951
        },
        {
          "threshold": 1.0770458467867867,
          "score": 16.613803400259957,
          "trades": 37,
          "win_rate": 0.5945945945945946,
          "profit_factor": 3.617277727296254,
          "pnl_dollars": 37329.35605220113,
          "max_drawdown": -5545.832033190491,
          "avg_pnl": 1008.901514924355,
          "avg_hold_minutes": 153.1081081081081,
          "long_rate": 0.24324324324324326,
          "avg_delta_abs": 0.6459594594594595
        }
      ]
    },
    "exit_margin_grid": {
      "grid": [
        {
          "exit_margin": -0.2,
          "score": 20.79051834454233,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.8728121722985827,
          "pnl_dollars": 69758.76854234701,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 520.5878249428881,
          "avg_hold_minutes": 150.8955223880597,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "exit_margin": -0.1,
          "score": 20.610377964264437,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.8519386463693195,
          "pnl_dollars": 68981.26854234702,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 514.7855861369181,
          "avg_hold_minutes": 150.63432835820896,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "exit_margin": -0.05,
          "score": 20.53890104167186,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.843656353444332,
          "pnl_dollars": 68672.76854234702,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 512.4833473309479,
          "avg_hold_minutes": 150.33582089552237,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "exit_margin": 0.0,
          "score": 21.049539104499285,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.905210104552144,
          "pnl_dollars": 70759.76854234701,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 528.0579741966195,
          "avg_hold_minutes": 149.36567164179104,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "exit_margin": 0.05,
          "score": 20.651852100539653,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.859027777528306,
          "pnl_dollars": 69048.26854234702,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 515.2855861369181,
          "avg_hold_minutes": 148.02238805970148,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "exit_margin": 0.1,
          "score": 20.604216457040533,
          "trades": 134,
          "win_rate": 0.6417910447761194,
          "profit_factor": 2.850886410264913,
          "pnl_dollars": 68971.26854234702,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 514.7109592712465,
          "avg_hold_minutes": 146.044776119403,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        },
        {
          "exit_margin": 0.2,
          "score": 19.831260248587284,
          "trades": 134,
          "win_rate": 0.6268656716417911,
          "profit_factor": 2.7576895499253626,
          "pnl_dollars": 65813.26854234702,
          "max_drawdown": -5545.832033190494,
          "avg_pnl": 491.143795092142,
          "avg_hold_minutes": 141.11940298507463,
          "long_rate": 0.417910447761194,
          "avg_delta_abs": 0.6170783582089553
        }
      ]
    },
    "entry_validation_metrics": {
      "trades": 134,
      "win_rate": 0.6268656716417911,
      "profit_factor": 2.887041071002776,
      "pnl_dollars": 70288.76854234704,
      "max_drawdown": -5545.832033190494,
      "avg_pnl": 524.5430488234854,
      "avg_hold_minutes": 152.57462686567163,
      "long_rate": 0.417910447761194,
      "avg_delta_abs": 0.6170783582089553
    }
  },
  "policy_metrics": {
    "fixed_delta_0.60_hard": {
      "overall": {
        "trades": 105,
        "win_rate": 0.5142857142857142,
        "profit_factor": 1.885043609247198,
        "pnl_dollars": 25225.861604997135,
        "max_drawdown": -3353.560386331479,
        "avg_pnl": 240.2463009999727,
        "avg_hold_minutes": 152.57142857142858,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.6029561904761905
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.45714285714285713,
          "profit_factor": 1.2362267449178503,
          "pnl_dollars": 2091.670355607453,
          "max_drawdown": -3353.560386331479,
          "avg_pnl": 59.762010160212945,
          "avg_hold_minutes": 139.0,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6025828571428571
        },
        "SPX": {
          "trades": 36,
          "win_rate": 0.5833333333333334,
          "profit_factor": 2.552866306693678,
          "pnl_dollars": 18848.660468431142,
          "max_drawdown": -2794.851930333655,
          "avg_pnl": 523.573901900865,
          "avg_hold_minutes": 156.52777777777777,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.5997305555555555
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.5,
          "profit_factor": 1.5706500069356384,
          "pnl_dollars": 4285.530780958537,
          "max_drawdown": -2364.3862343654914,
          "avg_pnl": 126.04502296936874,
          "avg_hold_minutes": 162.35294117647058,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6067558823529412
        }
      }
    },
    "fixed_delta_0.70_hard": {
      "overall": {
        "trades": 105,
        "win_rate": 0.5619047619047619,
        "profit_factor": 2.033279021214499,
        "pnl_dollars": 28115.412084034062,
        "max_drawdown": -3547.9676886717352,
        "avg_pnl": 267.76582937175294,
        "avg_hold_minutes": 161.04761904761904,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.7018904761904762
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.5142857142857142,
          "profit_factor": 1.4738695695010169,
          "pnl_dollars": 3228.65704875179,
          "max_drawdown": -2144.4928378222658,
          "avg_pnl": 92.24734425005114,
          "avg_hold_minutes": 151.42857142857142,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.7020771428571428
        },
        "SPX": {
          "trades": 36,
          "win_rate": 0.6388888888888888,
          "profit_factor": 2.4058885724136005,
          "pnl_dollars": 20297.977520285192,
          "max_drawdown": -3547.9676886717352,
          "avg_pnl": 563.8327088968109,
          "avg_hold_minutes": 166.11111111111111,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.7025527777777777
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.5294117647058824,
          "profit_factor": 1.7700999599510128,
          "pnl_dollars": 4588.777514997081,
          "max_drawdown": -2260.68503362054,
          "avg_pnl": 134.96404455873767,
          "avg_hold_minutes": 165.58823529411765,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.7009970588235294
        }
      }
    },
    "validation_best_delta_0.70_hard": {
      "overall": {
        "trades": 105,
        "win_rate": 0.5619047619047619,
        "profit_factor": 2.033279021214499,
        "pnl_dollars": 28115.412084034062,
        "max_drawdown": -3547.9676886717352,
        "avg_pnl": 267.76582937175294,
        "avg_hold_minutes": 161.04761904761904,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.7018904761904762
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.5142857142857142,
          "profit_factor": 1.4738695695010169,
          "pnl_dollars": 3228.65704875179,
          "max_drawdown": -2144.4928378222658,
          "avg_pnl": 92.24734425005114,
          "avg_hold_minutes": 151.42857142857142,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.7020771428571428
        },
        "SPX": {
          "trades": 36,
          "win_rate": 0.6388888888888888,
          "profit_factor": 2.4058885724136005,
          "pnl_dollars": 20297.977520285192,
          "max_drawdown": -3547.9676886717352,
          "avg_pnl": 563.8327088968109,
          "avg_hold_minutes": 166.11111111111111,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.7025527777777777
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.5294117647058824,
          "profit_factor": 1.7700999599510128,
          "pnl_dollars": 4588.777514997081,
          "max_drawdown": -2260.68503362054,
          "avg_pnl": 134.96404455873767,
          "avg_hold_minutes": 165.58823529411765,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.7009970588235294
        }
      }
    },
    "learned_delta_regression_all_hard": {
      "overall": {
        "trades": 105,
        "win_rate": 0.5333333333333333,
        "profit_factor": 1.8887382423110703,
        "pnl_dollars": 26223.067519804536,
        "max_drawdown": -3547.9676886717352,
        "avg_pnl": 249.74350018861463,
        "avg_hold_minutes": 156.52380952380952,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.6345161904761905
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.4857142857142857,
          "profit_factor": 1.387766551662588,
          "pnl_dollars": 3293.520734965642,
          "max_drawdown": -2916.8551964765647,
          "avg_pnl": 94.10059242758977,
          "avg_hold_minutes": 143.71428571428572,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6045028571428571
        },
        "SPX": {
          "trades": 36,
          "win_rate": 0.5833333333333334,
          "profit_factor": 2.2538466373467485,
          "pnl_dollars": 18088.45618725963,
          "max_drawdown": -3547.9676886717352,
          "avg_pnl": 502.45711631276754,
          "avg_hold_minutes": 163.61111111111111,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.6617055555555554
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.5294117647058824,
          "profit_factor": 1.7350560946628475,
          "pnl_dollars": 4841.090597579261,
          "max_drawdown": -2260.6850336205393,
          "avg_pnl": 142.38501757586062,
          "avg_hold_minutes": 162.2058823529412,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6366235294117648
        }
      }
    },
    "learned_delta_ranker_all_hard": {
      "overall": {
        "trades": 105,
        "win_rate": 0.5523809523809524,
        "profit_factor": 1.9652047696173305,
        "pnl_dollars": 27144.57535961654,
        "max_drawdown": -3547.9676886717352,
        "avg_pnl": 258.5197653296813,
        "avg_hold_minutes": 159.66666666666666,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.6861180952380952
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.4857142857142857,
          "profit_factor": 1.2898622566002553,
          "pnl_dollars": 2208.997668659936,
          "max_drawdown": -2331.9655611868966,
          "avg_pnl": 63.11421910456961,
          "avg_hold_minutes": 147.57142857142858,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.66914
        },
        "SPX": {
          "trades": 36,
          "win_rate": 0.6388888888888888,
          "profit_factor": 2.4058885724136005,
          "pnl_dollars": 20297.977520285192,
          "max_drawdown": -3547.9676886717352,
          "avg_pnl": 563.8327088968109,
          "avg_hold_minutes": 166.11111111111111,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.7025527777777777
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.5294117647058824,
          "profit_factor": 1.764719654849848,
          "pnl_dollars": 4637.6001706714105,
          "max_drawdown": -2260.68503362054,
          "avg_pnl": 136.40000501974737,
          "avg_hold_minutes": 165.2941176470588,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6861941176470588
        }
      }
    },
    "supervised_entry_strike_skip_hard": {
      "overall": {
        "trades": 46,
        "win_rate": 0.5869565217391305,
        "profit_factor": 2.234846954436589,
        "pnl_dollars": 19472.302626080156,
        "max_drawdown": -2389.2064565244855,
        "avg_pnl": 423.31092665391645,
        "avg_hold_minutes": 156.08695652173913,
        "long_rate": 0.6304347826086957,
        "avg_delta_abs": 0.6418608695652175
      },
      "per_ticker": {
        "QQQ": {
          "trades": 11,
          "win_rate": 0.5454545454545454,
          "profit_factor": 1.6687610205581525,
          "pnl_dollars": 1446.61736570211,
          "max_drawdown": -1114.5999043100862,
          "avg_pnl": 131.51066960928273,
          "avg_hold_minutes": 151.8181818181818,
          "long_rate": 0.8181818181818182,
          "avg_delta_abs": 0.5699545454545454
        },
        "SPX": {
          "trades": 23,
          "win_rate": 0.6086956521739131,
          "profit_factor": 2.24612625396947,
          "pnl_dollars": 13863.988049377855,
          "max_drawdown": -2389.2064565244855,
          "avg_pnl": 602.782089103385,
          "avg_hold_minutes": 163.2608695652174,
          "long_rate": 0.5652173913043478,
          "avg_delta_abs": 0.6996565217391304
        },
        "SPY": {
          "trades": 12,
          "win_rate": 0.5833333333333334,
          "profit_factor": 2.677967411883264,
          "pnl_dollars": 4161.697211000193,
          "max_drawdown": -686.9110363548091,
          "avg_pnl": 346.8081009166828,
          "avg_hold_minutes": 146.25,
          "long_rate": 0.5833333333333334,
          "avg_delta_abs": 0.597
        }
      }
    },
    "supervised_entry_strike_learned_exit": {
      "overall": {
        "trades": 46,
        "win_rate": 0.5869565217391305,
        "profit_factor": 2.489317881273472,
        "pnl_dollars": 23380.802626080156,
        "max_drawdown": -2389.2064565244846,
        "avg_pnl": 508.27831795826427,
        "avg_hold_minutes": 149.8913043478261,
        "long_rate": 0.6304347826086957,
        "avg_delta_abs": 0.6418608695652175
      },
      "per_ticker": {
        "QQQ": {
          "trades": 11,
          "win_rate": 0.5454545454545454,
          "profit_factor": 1.8953657495855147,
          "pnl_dollars": 1874.11736570211,
          "max_drawdown": -1114.5999043100862,
          "avg_pnl": 170.37430597291907,
          "avg_hold_minutes": 148.1818181818182,
          "long_rate": 0.8181818181818182,
          "avg_delta_abs": 0.5699545454545454
        },
        "SPX": {
          "trades": 23,
          "win_rate": 0.6086956521739131,
          "profit_factor": 2.564309371506843,
          "pnl_dollars": 17403.988049377855,
          "max_drawdown": -2389.2064565244855,
          "avg_pnl": 756.6951325816459,
          "avg_hold_minutes": 153.69565217391303,
          "long_rate": 0.5652173913043478,
          "avg_delta_abs": 0.6996565217391304
        },
        "SPY": {
          "trades": 12,
          "win_rate": 0.5833333333333334,
          "profit_factor": 2.6541790216468395,
          "pnl_dollars": 4102.697211000193,
          "max_drawdown": -686.9110363548091,
          "avg_pnl": 341.8914342500161,
          "avg_hold_minutes": 144.16666666666666,
          "long_rate": 0.5833333333333334,
          "avg_delta_abs": 0.597
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 105,
        "win_rate": 0.5619047619047619,
        "profit_factor": 5.053111536830328,
        "pnl_dollars": 69480.14171453597,
        "max_drawdown": -1703.3687367736284,
        "avg_pnl": 661.7156353765331,
        "avg_hold_minutes": 144.61904761904762,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.5483990476190477
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.5142857142857142,
          "profit_factor": 3.3411036616532463,
          "pnl_dollars": 15364.438313645878,
          "max_drawdown": -1703.3687367736284,
          "avg_pnl": 438.98395181845365,
          "avg_hold_minutes": 144.57142857142858,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.5584485714285713
        },
        "SPX": {
          "trades": 36,
          "win_rate": 0.6388888888888888,
          "profit_factor": 7.883513518424748,
          "pnl_dollars": 33903.252515315035,
          "max_drawdown": -1352.9490530411658,
          "avg_pnl": 941.7570143143065,
          "avg_hold_minutes": 143.19444444444446,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.5712194444444444
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.5294117647058824,
          "profit_factor": 4.5747464610424515,
          "pnl_dollars": 20212.45088557505,
          "max_drawdown": -1153.3183861986322,
          "avg_pnl": 594.4838495757367,
          "avg_hold_minutes": 146.1764705882353,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.5138911764705882
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 105,
        "win_rate": 0.8761904761904762,
        "profit_factor": 140.8283189366126,
        "pnl_dollars": 167995.15512808313,
        "max_drawdown": -342.42661216767584,
        "avg_pnl": 1599.9538583626966,
        "avg_hold_minutes": 89.19047619047619,
        "long_rate": 0.638095238095238,
        "avg_delta_abs": 0.46444571428571424
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
          "trades": 36,
          "win_rate": 0.9166666666666666,
          "profit_factor": 246.05992478416448,
          "pnl_dollars": 81364.3090601395,
          "max_drawdown": -157.42959075512044,
          "avg_pnl": 2260.119696114986,
          "avg_hold_minutes": 101.11111111111111,
          "long_rate": 0.6111111111111112,
          "avg_delta_abs": 0.5426749999999999
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
