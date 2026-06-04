# JEPA Supervised 0DTE Option Policy

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Signal model: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_full_pipeline_180m_frozen_march` / mode `base_jepa`
Train cutoff: `20260331`
Test start: `20260401`
Signals after `180`m cooldown: 5,135 total, 4,956 train, 179 test.
Option candidates with valid real premium paths: 35,945.
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

## OOS Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.60_hard | 179 | 39.7% | 1.270 | +16,112 | -10,154 | +90 | 111.1 | 0.599 |
| fixed_delta_0.70_hard | 179 | 44.7% | 1.398 | +21,651 | -9,585 | +121 | 119.1 | 0.705 |
| validation_best_delta_0.70_hard | 179 | 44.7% | 1.398 | +21,651 | -9,585 | +121 | 119.1 | 0.705 |
| learned_delta_regression_all_hard | 179 | 44.1% | 1.402 | +21,684 | -9,585 | +121 | 119.1 | 0.703 |
| learned_delta_ranker_all_hard | 179 | 44.7% | 1.394 | +21,529 | -9,327 | +120 | 118.1 | 0.692 |
| supervised_entry_strike_skip_hard | 51 | 45.1% | 2.100 | +17,898 | -3,388 | +351 | 109.6 | 0.702 |
| supervised_entry_strike_learned_exit | 51 | 45.1% | 2.202 | +19,558 | -3,388 | +383 | 107.6 | 0.702 |
| oracle_best_delta_hard | 179 | 45.8% | 3.173 | +92,567 | -5,502 | +517 | 106.5 | 0.534 |
| oracle_best_delta_oracle_exit | 179 | 83.8% | 84.497 | +251,309 | -335 | +1,404 | 59.8 | 0.438 |

## Per-Ticker OOS Results

### fixed_delta_0.60_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 33.3% | 0.582 | -7,687 | -10,154 | -151 | 106.1 | 0.588 |
| SPX | 52 | 42.3% | 2.002 | +18,300 | -4,302 | +352 | 115.6 | 0.602 |
| SPY | 76 | 42.1% | 1.240 | +5,499 | -5,783 | +72 | 111.3 | 0.605 |

### fixed_delta_0.70_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 37.3% | 0.695 | -4,587 | -7,893 | -90 | 115.8 | 0.710 |
| SPX | 52 | 51.9% | 2.161 | +21,529 | -5,669 | +414 | 124.1 | 0.699 |
| SPY | 76 | 44.7% | 1.227 | +4,709 | -4,968 | +62 | 117.9 | 0.704 |

### validation_best_delta_0.70_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 37.3% | 0.695 | -4,587 | -7,893 | -90 | 115.8 | 0.710 |
| SPX | 52 | 51.9% | 2.161 | +21,529 | -5,669 | +414 | 124.1 | 0.699 |
| SPY | 76 | 44.7% | 1.227 | +4,709 | -4,968 | +62 | 117.9 | 0.704 |

### learned_delta_regression_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 37.3% | 0.695 | -4,587 | -7,893 | -90 | 115.8 | 0.710 |
| SPX | 52 | 50.0% | 2.189 | +21,562 | -5,669 | +415 | 124.0 | 0.695 |
| SPY | 76 | 44.7% | 1.227 | +4,709 | -4,968 | +62 | 117.9 | 0.704 |

### learned_delta_ranker_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 37.3% | 0.711 | -4,329 | -7,635 | -85 | 115.1 | 0.702 |
| SPX | 52 | 51.9% | 2.119 | +21,161 | -5,669 | +407 | 124.1 | 0.693 |
| SPY | 76 | 44.7% | 1.226 | +4,697 | -5,103 | +62 | 116.1 | 0.684 |

### supervised_entry_strike_skip_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 5 | 20.0% | 0.417 | -1,087 | -1,397 | -217 | 62.0 | 0.722 |
| SPX | 34 | 50.0% | 2.483 | +16,590 | -3,329 | +488 | 111.5 | 0.699 |
| SPY | 12 | 41.7% | 1.744 | +2,394 | -1,121 | +200 | 124.2 | 0.703 |

### supervised_entry_strike_learned_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 5 | 20.0% | 0.417 | -1,087 | -1,397 | -217 | 62.0 | 0.722 |
| SPX | 34 | 50.0% | 2.631 | +18,250 | -3,329 | +537 | 108.5 | 0.699 |
| SPY | 12 | 41.7% | 1.744 | +2,394 | -1,121 | +200 | 124.2 | 0.703 |

### oracle_best_delta_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 37.3% | 1.509 | +7,314 | -5,502 | +143 | 108.5 | 0.574 |
| SPX | 52 | 55.8% | 6.397 | +46,118 | -1,862 | +887 | 105.1 | 0.535 |
| SPY | 76 | 44.7% | 2.990 | +39,134 | -3,448 | +515 | 106.2 | 0.508 |

### oracle_best_delta_oracle_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 84.3% | 68.780 | +67,706 | -335 | +1,328 | 54.6 | 0.415 |
| SPX | 52 | 86.5% | 151.740 | +90,807 | -158 | +1,746 | 73.5 | 0.466 |
| SPY | 76 | 81.6% | 66.884 | +92,796 | -283 | +1,221 | 53.9 | 0.434 |

## Validation Choices

- Fixed delta selected on pre-OOS validation: `0.70`.
- Entry utility threshold selected on pre-OOS validation: `0.3545`.
- Learned-exit margin selected on pre-OOS validation: `-0.2000`.

## Interpretation

- This is a frozen OOS test: option-policy models are trained through the configured cutoff and scored from the configured test start onward.
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
    "truncate_eod_horizon": true,
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
    "n_jobs": 20,
    "greeks_cache_size": 50,
    "progress_every": 100,
    "max_signals": 0,
    "reuse_candidates": false,
    "labels_only": false
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
  "train_candidates": 34692,
  "test_candidates": 1253,
  "train_signals": 4956,
  "test_signals": 179,
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
        "score": 9.811479204286842,
        "trades": 326,
        "win_rate": 0.18404907975460122,
        "profit_factor": 1.2366780386996872,
        "pnl_dollars": 38301.254033296704,
        "max_drawdown": -23579.255746746996,
        "avg_pnl": 117.48850930459112,
        "avg_hold_minutes": 72.45398773006134,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.09792331288343557
      },
      {
        "delta_target": 0.2,
        "score": 16.535597431122344,
        "trades": 326,
        "win_rate": 0.26993865030674846,
        "profit_factor": 1.5802090230420018,
        "pnl_dollars": 81220.94429419156,
        "max_drawdown": -14716.886068049265,
        "avg_pnl": 249.1440009024281,
        "avg_hold_minutes": 77.16257668711657,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.1981131901840491
      },
      {
        "delta_target": 0.3,
        "score": 21.17158998014805,
        "trades": 326,
        "win_rate": 0.3374233128834356,
        "profit_factor": 1.900440246261623,
        "pnl_dollars": 106966.23923412929,
        "max_drawdown": -10570.145525796854,
        "avg_pnl": 328.11729826420026,
        "avg_hold_minutes": 84.75460122699387,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.2955733128834356
      },
      {
        "delta_target": 0.4,
        "score": 24.700443663466228,
        "trades": 326,
        "win_rate": 0.40797546012269936,
        "profit_factor": 2.171402873294936,
        "pnl_dollars": 125350.91957049817,
        "max_drawdown": -8139.688898662502,
        "avg_pnl": 384.51202322238703,
        "avg_hold_minutes": 94.079754601227,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.39554999999999996
      },
      {
        "delta_target": 0.5,
        "score": 27.25648916602927,
        "trades": 326,
        "win_rate": 0.5122699386503068,
        "profit_factor": 2.442215429134048,
        "pnl_dollars": 133665.28845489363,
        "max_drawdown": -5007.394857939478,
        "avg_pnl": 410.0162222542749,
        "avg_hold_minutes": 104.86196319018404,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.501476380368098
      },
      {
        "delta_target": 0.6,
        "score": 33.31845704122702,
        "trades": 326,
        "win_rate": 0.6012269938650306,
        "profit_factor": 3.097496799517628,
        "pnl_dollars": 155377.20664995746,
        "max_drawdown": -3072.934449150169,
        "avg_pnl": 476.6171983127529,
        "avg_hold_minutes": 115.15337423312883,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.6012923312883436
      },
      {
        "delta_target": 0.7,
        "score": 40.18597563814039,
        "trades": 326,
        "win_rate": 0.6871165644171779,
        "profit_factor": 4.032015092755324,
        "pnl_dollars": 169913.07432127756,
        "max_drawdown": -3010.7717899457493,
        "avg_pnl": 521.2057494517717,
        "avg_hold_minutes": 122.36196319018404,
        "long_rate": 0.36809815950920244,
        "avg_delta_abs": 0.7059423312883436
      }
    ],
    "entry_threshold": 0.35447509119268517,
    "exit_margin": -0.2,
    "entry_threshold_grid": {
      "grid": [
        {
          "threshold": -1000000000.0,
          "score": 36.85416685756728,
          "trades": 326,
          "win_rate": 0.6533742331288344,
          "profit_factor": 3.5782479768202666,
          "pnl_dollars": 162867.92179681544,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 499.5948521374707,
          "avg_hold_minutes": 118.65030674846626,
          "long_rate": 0.36809815950920244,
          "avg_delta_abs": 0.6632914110429448
        },
        {
          "threshold": -0.5766777166440532,
          "score": 36.85416685756728,
          "trades": 326,
          "win_rate": 0.6533742331288344,
          "profit_factor": 3.5782479768202666,
          "pnl_dollars": 162867.92179681544,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 499.5948521374707,
          "avg_hold_minutes": 118.65030674846626,
          "long_rate": 0.36809815950920244,
          "avg_delta_abs": 0.6632914110429448
        },
        {
          "threshold": -0.5,
          "score": 36.85416685756728,
          "trades": 326,
          "win_rate": 0.6533742331288344,
          "profit_factor": 3.5782479768202666,
          "pnl_dollars": 162867.92179681544,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 499.5948521374707,
          "avg_hold_minutes": 118.65030674846626,
          "long_rate": 0.36809815950920244,
          "avg_delta_abs": 0.6632914110429448
        },
        {
          "threshold": -0.40030244789848696,
          "score": 36.85416685756728,
          "trades": 326,
          "win_rate": 0.6533742331288344,
          "profit_factor": 3.5782479768202666,
          "pnl_dollars": 162867.92179681544,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 499.5948521374707,
          "avg_hold_minutes": 118.65030674846626,
          "long_rate": 0.36809815950920244,
          "avg_delta_abs": 0.6632914110429448
        },
        {
          "threshold": -0.3044018282114051,
          "score": 36.85416685756728,
          "trades": 326,
          "win_rate": 0.6533742331288344,
          "profit_factor": 3.5782479768202666,
          "pnl_dollars": 162867.92179681544,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 499.5948521374707,
          "avg_hold_minutes": 118.65030674846626,
          "long_rate": 0.36809815950920244,
          "avg_delta_abs": 0.6632914110429448
        },
        {
          "threshold": -0.25,
          "score": 36.85416685756728,
          "trades": 326,
          "win_rate": 0.6533742331288344,
          "profit_factor": 3.5782479768202666,
          "pnl_dollars": 162867.92179681544,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 499.5948521374707,
          "avg_hold_minutes": 118.65030674846626,
          "long_rate": 0.36809815950920244,
          "avg_delta_abs": 0.6632914110429448
        },
        {
          "threshold": -0.16793434797493156,
          "score": 36.61308382560766,
          "trades": 323,
          "win_rate": 0.6501547987616099,
          "profit_factor": 3.5610461278853927,
          "pnl_dollars": 161781.2810189408,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 500.87083906792816,
          "avg_hold_minutes": 118.12693498452012,
          "long_rate": 0.3653250773993808,
          "avg_delta_abs": 0.6629928792569659
        },
        {
          "threshold": -0.1,
          "score": 36.47576735960478,
          "trades": 319,
          "win_rate": 0.6520376175548589,
          "profit_factor": 3.561545719525363,
          "pnl_dollars": 160821.6699768448,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 504.1431660716138,
          "avg_hold_minutes": 117.46081504702194,
          "long_rate": 0.36363636363636365,
          "avg_delta_abs": 0.6624987460815047
        },
        {
          "threshold": -0.04223167576018518,
          "score": 36.78483447445792,
          "trades": 307,
          "win_rate": 0.6579804560260586,
          "profit_factor": 3.659261765018704,
          "pnl_dollars": 159996.85802409926,
          "max_drawdown": -3655.727470583668,
          "avg_pnl": 521.162403987294,
          "avg_hold_minutes": 116.40065146579805,
          "long_rate": 0.3550488599348534,
          "avg_delta_abs": 0.6616882736156352
        },
        {
          "threshold": 0.0,
          "score": 37.29795502756701,
          "trades": 299,
          "win_rate": 0.6688963210702341,
          "profit_factor": 3.7591370803029376,
          "pnl_dollars": 160394.41202634017,
          "max_drawdown": -3655.727470583668,
          "avg_pnl": 536.4361606232113,
          "avg_hold_minutes": 116.10367892976589,
          "long_rate": 0.35785953177257523,
          "avg_delta_abs": 0.6610732441471573
        },
        {
          "threshold": 0.05,
          "score": 38.48109318773541,
          "trades": 289,
          "win_rate": 0.6782006920415224,
          "profit_factor": 3.9548697505931347,
          "pnl_dollars": 162079.9122547196,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 560.8301462101024,
          "avg_hold_minutes": 115.48442906574394,
          "long_rate": 0.35294117647058826,
          "avg_delta_abs": 0.6593965397923877
        },
        {
          "threshold": 0.08673097891933544,
          "score": 38.33279545510747,
          "trades": 284,
          "win_rate": 0.676056338028169,
          "profit_factor": 3.963183516030817,
          "pnl_dollars": 160814.82100821493,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 566.2493697472356,
          "avg_hold_minutes": 115.49295774647888,
          "long_rate": 0.3485915492957746,
          "avg_delta_abs": 0.6584080985915494
        },
        {
          "threshold": 0.1,
          "score": 38.32614896080017,
          "trades": 280,
          "win_rate": 0.6785714285714286,
          "profit_factor": 3.988465989835006,
          "pnl_dollars": 159883.01713032412,
          "max_drawdown": -3010.7717899457493,
          "avg_pnl": 571.0107754654433,
          "avg_hold_minutes": 114.73214285714286,
          "long_rate": 0.35,
          "avg_delta_abs": 0.6578250000000001
        },
        {
          "threshold": 0.2,
          "score": 38.78805878347886,
          "trades": 254,
          "win_rate": 0.6929133858267716,
          "profit_factor": 4.27688604963703,
          "pnl_dollars": 152422.17553458162,
          "max_drawdown": -3070.2304725921276,
          "avg_pnl": 600.0873052542584,
          "avg_hold_minutes": 115.43307086614173,
          "long_rate": 0.3228346456692913,
          "avg_delta_abs": 0.6547649606299213
        },
        {
          "threshold": 0.22448100332454582,
          "score": 38.68932091684307,
          "trades": 248,
          "win_rate": 0.6935483870967742,
          "profit_factor": 4.313458896528038,
          "pnl_dollars": 150435.26158042595,
          "max_drawdown": -3070.2304725921276,
          "avg_pnl": 606.593796695266,
          "avg_hold_minutes": 115.88709677419355,
          "long_rate": 0.3185483870967742,
          "avg_delta_abs": 0.655025
        },
        {
          "threshold": 0.3,
          "score": 39.87540354231597,
          "trades": 231,
          "win_rate": 0.7056277056277056,
          "profit_factor": 4.616246340792433,
          "pnl_dollars": 149078.3133898746,
          "max_drawdown": -3518.18515766965,
          "avg_pnl": 645.3606640254311,
          "avg_hold_minutes": 114.87012987012987,
          "long_rate": 0.30303030303030304,
          "avg_delta_abs": 0.652660606060606
        },
        {
          "threshold": 0.35447509119268517,
          "score": 40.93545777417946,
          "trades": 216,
          "win_rate": 0.7129629629629629,
          "profit_factor": 4.897885439037796,
          "pnl_dollars": 147713.40479776537,
          "max_drawdown": -3720.072340417333,
          "avg_pnl": 683.8583555452101,
          "avg_hold_minutes": 114.23611111111111,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "threshold": 0.4864097399125772,
          "score": 36.63723721538374,
          "trades": 174,
          "win_rate": 0.7068965517241379,
          "profit_factor": 4.68496550783168,
          "pnl_dollars": 126211.80848534199,
          "max_drawdown": -3615.7555262994283,
          "avg_pnl": 725.3552211801264,
          "avg_hold_minutes": 112.90229885057471,
          "long_rate": 0.27011494252873564,
          "avg_delta_abs": 0.6453413793103449
        },
        {
          "threshold": 0.6318378793950774,
          "score": 26.826393137122203,
          "trades": 116,
          "win_rate": 0.6637931034482759,
          "profit_factor": 3.96614344836683,
          "pnl_dollars": 81442.98537877829,
          "max_drawdown": -4107.407044740627,
          "avg_pnl": 702.0947015411922,
          "avg_hold_minutes": 107.71551724137932,
          "long_rate": 0.23275862068965517,
          "avg_delta_abs": 0.6383077586206897
        },
        {
          "threshold": 0.9895105337364475,
          "score": 21.2058020756928,
          "trades": 58,
          "win_rate": 0.6551724137931034,
          "profit_factor": 4.106333645358244,
          "pnl_dollars": 46504.80168495821,
          "max_drawdown": -3768.145778422637,
          "avg_pnl": 801.8069256027278,
          "avg_hold_minutes": 112.67241379310344,
          "long_rate": 0.15517241379310345,
          "avg_delta_abs": 0.6152931034482758
        }
      ]
    },
    "exit_margin_grid": {
      "grid": [
        {
          "exit_margin": -0.2,
          "score": 40.9983688326749,
          "trades": 216,
          "win_rate": 0.7129629629629629,
          "profit_factor": 4.904746361481074,
          "pnl_dollars": 147973.40479776537,
          "max_drawdown": -3720.072340417333,
          "avg_pnl": 685.0620592489138,
          "avg_hold_minutes": 113.51851851851852,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "exit_margin": -0.1,
          "score": 40.92529521857636,
          "trades": 216,
          "win_rate": 0.7129629629629629,
          "profit_factor": 4.8967771361815755,
          "pnl_dollars": 147671.40479776537,
          "max_drawdown": -3720.072340417333,
          "avg_pnl": 683.6639111007656,
          "avg_hold_minutes": 113.37962962962963,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "exit_margin": -0.05,
          "score": 40.92529521857636,
          "trades": 216,
          "win_rate": 0.7129629629629629,
          "profit_factor": 4.8967771361815755,
          "pnl_dollars": 147671.40479776537,
          "max_drawdown": -3720.072340417333,
          "avg_pnl": 683.6639111007656,
          "avg_hold_minutes": 113.37962962962963,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "exit_margin": 0.0,
          "score": 40.87372900446053,
          "trades": 216,
          "win_rate": 0.7129629629629629,
          "profit_factor": 4.8919599041020865,
          "pnl_dollars": 147414.90479776537,
          "max_drawdown": -3720.072340417333,
          "avg_pnl": 682.4764111007656,
          "avg_hold_minutes": 113.26388888888889,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "exit_margin": 0.05,
          "score": 40.60409324362424,
          "trades": 216,
          "win_rate": 0.7129629629629629,
          "profit_factor": 4.866804078267003,
          "pnl_dollars": 146133.40479776537,
          "max_drawdown": -3843.072340417333,
          "avg_pnl": 676.5435407303952,
          "avg_hold_minutes": 112.87037037037037,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "exit_margin": 0.1,
          "score": 40.80881540702034,
          "trades": 216,
          "win_rate": 0.7268518518518519,
          "profit_factor": 4.904197387130733,
          "pnl_dollars": 146168.90479776537,
          "max_drawdown": -3843.072340417333,
          "avg_pnl": 676.707892582247,
          "avg_hold_minutes": 111.9675925925926,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        },
        {
          "exit_margin": 0.2,
          "score": 40.70588716151738,
          "trades": 216,
          "win_rate": 0.7175925925925926,
          "profit_factor": 4.891148207771065,
          "pnl_dollars": 145885.90479776537,
          "max_drawdown": -3931.572340417333,
          "avg_pnl": 675.3977073970619,
          "avg_hold_minutes": 109.44444444444444,
          "long_rate": 0.2916666666666667,
          "avg_delta_abs": 0.6496523148148149
        }
      ]
    },
    "entry_validation_metrics": {
      "trades": 216,
      "win_rate": 0.7129629629629629,
      "profit_factor": 4.897885439037796,
      "pnl_dollars": 147713.40479776537,
      "max_drawdown": -3720.072340417333,
      "avg_pnl": 683.8583555452101,
      "avg_hold_minutes": 114.23611111111111,
      "long_rate": 0.2916666666666667,
      "avg_delta_abs": 0.6496523148148149
    }
  },
  "policy_metrics": {
    "fixed_delta_0.60_hard": {
      "overall": {
        "trades": 179,
        "win_rate": 0.39664804469273746,
        "profit_factor": 1.2703624500251955,
        "pnl_dollars": 16111.922298342328,
        "max_drawdown": -10153.916639621706,
        "avg_pnl": 90.0107390968845,
        "avg_hold_minutes": 111.06145251396649,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.5993346368715083
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.3333333333333333,
          "profit_factor": 0.5820915709609747,
          "pnl_dollars": -7686.518443287995,
          "max_drawdown": -10153.916639621706,
          "avg_pnl": -150.71604790760776,
          "avg_hold_minutes": 106.07843137254902,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.5879313725490195
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.4230769230769231,
          "profit_factor": 2.002280624377215,
          "pnl_dollars": 18299.627968380155,
          "max_drawdown": -4301.6550890614535,
          "avg_pnl": 351.91592246884915,
          "avg_hold_minutes": 115.57692307692308,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.6017846153846154
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.42105263157894735,
          "profit_factor": 1.2396731077833307,
          "pnl_dollars": 5498.812773250172,
          "max_drawdown": -5782.709057705979,
          "avg_pnl": 72.35279964802858,
          "avg_hold_minutes": 111.3157894736842,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.6053105263157894
        }
      }
    },
    "fixed_delta_0.70_hard": {
      "overall": {
        "trades": 179,
        "win_rate": 0.44692737430167595,
        "profit_factor": 1.398214933689381,
        "pnl_dollars": 21650.83735409942,
        "max_drawdown": -9585.101170852997,
        "avg_pnl": 120.95439862625375,
        "avg_hold_minutes": 119.10614525139665,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.7045145251396648
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.37254901960784315,
          "profit_factor": 0.6950922640072876,
          "pnl_dollars": -4587.154139102566,
          "max_drawdown": -7892.555203009154,
          "avg_pnl": -89.94419880593266,
          "avg_hold_minutes": 115.7843137254902,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.7101960784313723
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.5192307692307693,
          "profit_factor": 2.160713765962015,
          "pnl_dollars": 21528.711328205067,
          "max_drawdown": -5668.925225696251,
          "avg_pnl": 414.01367938855896,
          "avg_hold_minutes": 124.13461538461539,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.6990076923076922
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.4473684210526316,
          "profit_factor": 1.2266528173886415,
          "pnl_dollars": 4709.280164996918,
          "max_drawdown": -4968.499041965574,
          "avg_pnl": 61.964212697327866,
          "avg_hold_minutes": 117.89473684210526,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.7044697368421053
        }
      }
    },
    "validation_best_delta_0.70_hard": {
      "overall": {
        "trades": 179,
        "win_rate": 0.44692737430167595,
        "profit_factor": 1.398214933689381,
        "pnl_dollars": 21650.83735409942,
        "max_drawdown": -9585.101170852997,
        "avg_pnl": 120.95439862625375,
        "avg_hold_minutes": 119.10614525139665,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.7045145251396648
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.37254901960784315,
          "profit_factor": 0.6950922640072876,
          "pnl_dollars": -4587.154139102566,
          "max_drawdown": -7892.555203009154,
          "avg_pnl": -89.94419880593266,
          "avg_hold_minutes": 115.7843137254902,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.7101960784313723
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.5192307692307693,
          "profit_factor": 2.160713765962015,
          "pnl_dollars": 21528.711328205067,
          "max_drawdown": -5668.925225696251,
          "avg_pnl": 414.01367938855896,
          "avg_hold_minutes": 124.13461538461539,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.6990076923076922
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.4473684210526316,
          "profit_factor": 1.2266528173886415,
          "pnl_dollars": 4709.280164996918,
          "max_drawdown": -4968.499041965574,
          "avg_pnl": 61.964212697327866,
          "avg_hold_minutes": 117.89473684210526,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.7044697368421053
        }
      }
    },
    "learned_delta_regression_all_hard": {
      "overall": {
        "trades": 179,
        "win_rate": 0.441340782122905,
        "profit_factor": 1.4019424790387065,
        "pnl_dollars": 21684.472473185728,
        "max_drawdown": -9585.101170852997,
        "avg_pnl": 121.14230431947334,
        "avg_hold_minutes": 119.07821229050279,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.7032223463687151
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.37254901960784315,
          "profit_factor": 0.6950922640072876,
          "pnl_dollars": -4587.154139102566,
          "max_drawdown": -7892.555203009154,
          "avg_pnl": -89.94419880593266,
          "avg_hold_minutes": 115.7843137254902,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.7101960784313723
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.5,
          "profit_factor": 2.189496605698016,
          "pnl_dollars": 21562.346447291373,
          "max_drawdown": -5668.925225696251,
          "avg_pnl": 414.66050860175716,
          "avg_hold_minutes": 124.03846153846153,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.6945596153846154
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.4473684210526316,
          "profit_factor": 1.2266528173886415,
          "pnl_dollars": 4709.280164996918,
          "max_drawdown": -4968.499041965574,
          "avg_pnl": 61.964212697327866,
          "avg_hold_minutes": 117.89473684210526,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.7044697368421053
        }
      }
    },
    "learned_delta_ranker_all_hard": {
      "overall": {
        "trades": 179,
        "win_rate": 0.44692737430167595,
        "profit_factor": 1.393710437435875,
        "pnl_dollars": 21529.081777119292,
        "max_drawdown": -9327.340040243567,
        "avg_pnl": 120.27419987217482,
        "avg_hold_minutes": 118.12849162011173,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.691663687150838
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.37254901960784315,
          "profit_factor": 0.7113237745756559,
          "pnl_dollars": -4329.393008493134,
          "max_drawdown": -7634.7940723997235,
          "avg_pnl": -84.89005899006146,
          "avg_hold_minutes": 115.09803921568627,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.7017549019607843
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.5192307692307693,
          "profit_factor": 2.118713969909538,
          "pnl_dollars": 21161.033238454173,
          "max_drawdown": -5668.925225696251,
          "avg_pnl": 406.9429468933495,
          "avg_hold_minutes": 124.13461538461539,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.6934961538461538
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.4473684210526316,
          "profit_factor": 1.2261687911572714,
          "pnl_dollars": 4697.4415471582515,
          "max_drawdown": -5103.005069911249,
          "avg_pnl": 61.80844140997699,
          "avg_hold_minutes": 116.05263157894737,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.6836381578947368
        }
      }
    },
    "supervised_entry_strike_skip_hard": {
      "overall": {
        "trades": 51,
        "win_rate": 0.45098039215686275,
        "profit_factor": 2.0998692401101158,
        "pnl_dollars": 17897.667835701668,
        "max_drawdown": -3388.4914407410442,
        "avg_pnl": 350.93466344513075,
        "avg_hold_minutes": 109.6078431372549,
        "long_rate": 0.2549019607843137,
        "avg_delta_abs": 0.7019823529411766
      },
      "per_ticker": {
        "QQQ": {
          "trades": 5,
          "win_rate": 0.2,
          "profit_factor": 0.41739481217908964,
          "pnl_dollars": -1086.7005540453956,
          "max_drawdown": -1396.9408127485901,
          "avg_pnl": -217.34011080907914,
          "avg_hold_minutes": 62.0,
          "long_rate": 0.2,
          "avg_delta_abs": 0.7222000000000001
        },
        "SPX": {
          "trades": 34,
          "win_rate": 0.5,
          "profit_factor": 2.4826652730346463,
          "pnl_dollars": 16589.915363242184,
          "max_drawdown": -3329.466543049878,
          "avg_pnl": 487.9386871541819,
          "avg_hold_minutes": 111.47058823529412,
          "long_rate": 0.29411764705882354,
          "avg_delta_abs": 0.6986529411764706
        },
        "SPY": {
          "trades": 12,
          "win_rate": 0.4166666666666667,
          "profit_factor": 1.7440704866363537,
          "pnl_dollars": 2394.453026504883,
          "max_drawdown": -1120.9548539824377,
          "avg_pnl": 199.53775220874024,
          "avg_hold_minutes": 124.16666666666667,
          "long_rate": 0.16666666666666666,
          "avg_delta_abs": 0.7029916666666667
        }
      }
    },
    "supervised_entry_strike_learned_exit": {
      "overall": {
        "trades": 51,
        "win_rate": 0.45098039215686275,
        "profit_factor": 2.201881577993646,
        "pnl_dollars": 19557.667835701668,
        "max_drawdown": -3388.4914407410442,
        "avg_pnl": 383.4836830529739,
        "avg_hold_minutes": 107.6470588235294,
        "long_rate": 0.2549019607843137,
        "avg_delta_abs": 0.7019823529411766
      },
      "per_ticker": {
        "QQQ": {
          "trades": 5,
          "win_rate": 0.2,
          "profit_factor": 0.41739481217908964,
          "pnl_dollars": -1086.7005540453956,
          "max_drawdown": -1396.9408127485901,
          "avg_pnl": -217.34011080907914,
          "avg_hold_minutes": 62.0,
          "long_rate": 0.2,
          "avg_delta_abs": 0.7222000000000001
        },
        "SPX": {
          "trades": 34,
          "win_rate": 0.5,
          "profit_factor": 2.631021928228366,
          "pnl_dollars": 18249.915363242184,
          "max_drawdown": -3329.466543049878,
          "avg_pnl": 536.7622165659466,
          "avg_hold_minutes": 108.52941176470588,
          "long_rate": 0.29411764705882354,
          "avg_delta_abs": 0.6986529411764706
        },
        "SPY": {
          "trades": 12,
          "win_rate": 0.4166666666666667,
          "profit_factor": 1.7440704866363537,
          "pnl_dollars": 2394.453026504883,
          "max_drawdown": -1120.9548539824377,
          "avg_pnl": 199.53775220874024,
          "avg_hold_minutes": 124.16666666666667,
          "long_rate": 0.16666666666666666,
          "avg_delta_abs": 0.7029916666666667
        }
      }
    },
    "oracle_best_delta_hard": {
      "overall": {
        "trades": 179,
        "win_rate": 0.4581005586592179,
        "profit_factor": 3.1732134049894785,
        "pnl_dollars": 92566.53832374749,
        "max_drawdown": -5502.185210109927,
        "avg_pnl": 517.131499015349,
        "avg_hold_minutes": 106.53631284916202,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.5344972067039107
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.37254901960784315,
          "profit_factor": 1.5085896132612917,
          "pnl_dollars": 7313.8027845478955,
          "max_drawdown": -5502.185210109927,
          "avg_pnl": 143.40789773623325,
          "avg_hold_minutes": 108.52941176470588,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.5736529411764706
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.5576923076923077,
          "profit_factor": 6.39720540358934,
          "pnl_dollars": 46118.24767127291,
          "max_drawdown": -1861.9406562427212,
          "avg_pnl": 886.8893782937098,
          "avg_hold_minutes": 105.09615384615384,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.5353788461538461
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.4473684210526316,
          "profit_factor": 2.9896613589711873,
          "pnl_dollars": 39134.487867926684,
          "max_drawdown": -3447.943480726617,
          "avg_pnl": 514.9274719464038,
          "avg_hold_minutes": 106.1842105263158,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.5076184210526316
        }
      }
    },
    "oracle_best_delta_oracle_exit": {
      "overall": {
        "trades": 179,
        "win_rate": 0.8379888268156425,
        "profit_factor": 84.49731783801025,
        "pnl_dollars": 251309.24132714665,
        "max_drawdown": -335.1588102329224,
        "avg_pnl": 1403.9622420510987,
        "avg_hold_minutes": 59.77653631284916,
        "long_rate": 0.4972067039106145,
        "avg_delta_abs": 0.438091061452514
      },
      "per_ticker": {
        "QQQ": {
          "trades": 51,
          "win_rate": 0.8431372549019608,
          "profit_factor": 68.78015922998901,
          "pnl_dollars": 67706.08614148624,
          "max_drawdown": -335.1588102329224,
          "avg_pnl": 1327.5703164997303,
          "avg_hold_minutes": 54.6078431372549,
          "long_rate": 0.5490196078431373,
          "avg_delta_abs": 0.4152411764705882
        },
        "SPX": {
          "trades": 52,
          "win_rate": 0.8653846153846154,
          "profit_factor": 151.7398964501104,
          "pnl_dollars": 90807.44152488957,
          "max_drawdown": -158.49409752091015,
          "avg_pnl": 1746.2969524017224,
          "avg_hold_minutes": 73.46153846153847,
          "long_rate": 0.46153846153846156,
          "avg_delta_abs": 0.4663596153846153
        },
        "SPY": {
          "trades": 76,
          "win_rate": 0.8157894736842105,
          "profit_factor": 66.88407406905868,
          "pnl_dollars": 92795.7136607708,
          "max_drawdown": -283.08610378968297,
          "avg_pnl": 1220.996232378563,
          "avg_hold_minutes": 53.88157894736842,
          "long_rate": 0.4868421052631579,
          "avg_delta_abs": 0.4340828947368421
        }
      }
    }
  }
}
```
