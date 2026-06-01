# JEPA Supervised 0DTE Option Policy

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Signal model: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_180m_frozen_march` / mode `base_jepa`
Train cutoff: `20260331`
Test start: `20260401`
Signals after `180`m cooldown: 1,029 total, 925 train, 104 test.
Option candidates with valid real premium paths: 7,203.
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
| learned_delta_regression_all_hard | 104 | 40.4% | 1.657 | +18,867 | -4,815 | +181 | 112.5 | 0.640 |
| learned_delta_ranker_all_hard | 104 | 39.4% | 1.786 | +19,530 | -3,142 | +188 | 108.5 | 0.640 |
| supervised_entry_strike_skip_hard | 103 | 40.8% | 1.692 | +19,461 | -4,815 | +189 | 112.8 | 0.644 |
| supervised_entry_strike_learned_exit | 0 | nan | nan | +0 | +0 | nan | nan | nan |
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
| QQQ | 35 | 42.9% | 1.428 | +3,070 | -2,251 | +88 | 105.7 | 0.664 |
| SPX | 35 | 45.7% | 2.120 | +14,934 | -2,734 | +427 | 121.9 | 0.617 |
| SPY | 34 | 32.4% | 1.105 | +862 | -2,499 | +25 | 110.0 | 0.637 |

### learned_delta_ranker_all_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 1.377 | +2,462 | -2,112 | +70 | 108.7 | 0.695 |
| SPX | 35 | 42.9% | 2.612 | +16,855 | -2,095 | +482 | 106.4 | 0.551 |
| SPY | 34 | 32.4% | 1.027 | +213 | -2,387 | +6 | 110.4 | 0.674 |

### supervised_entry_strike_skip_hard

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 35 | 42.9% | 1.428 | +3,070 | -2,251 | +88 | 105.7 | 0.664 |
| SPX | 34 | 47.1% | 2.219 | +15,528 | -2,316 | +457 | 122.9 | 0.630 |
| SPY | 34 | 32.4% | 1.105 | +862 | -2,499 | +25 | 110.0 | 0.637 |

### supervised_entry_strike_learned_exit

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

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
- Entry utility threshold selected on pre-April validation: `-0.2500`.
- Learned-exit margin selected on pre-April validation: `nan`.

## Interpretation

- This is a frozen OOS test: option-policy models are trained through the March 2026 cutoff and scored from April 1, 2026 onward.
- Future option paths are used only to create supervised labels and to score the backtest, not as model inputs.
- The test is stricter than the previous spot proxy because it uses real 0DTE option premium paths and spread-adjusted entries.
- The current deployable validated policy is `validation_best_delta_0.70_hard` unless a learned selector beats it on rolling walk-forward validation.
- The oracle rows are ceilings, not deployable strategies. They diagnose the remaining strike/delta and exit-selection gap.

## Monthly Walk-Forward Validation

File: `monthly_cv_policy_grid.csv`

This validation uses only months before Apr/May OOS. For each month from 2025-05 through 2026-03, models are trained on prior months and scored on the next month.

| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_070 | 685 | 58.0% | 2.793 | +239,857 | -5,706 | 0.703 |
| jepa_huber_60 | 685 | 53.6% | 2.567 | +224,060 | -6,214 | 0.651 |
| full_huber_100 | 685 | 53.1% | 2.482 | +214,810 | -6,158 | 0.647 |
| option_huber_180 | 685 | 52.7% | 2.520 | +214,519 | -7,910 | 0.634 |
| full_reg_180 | 685 | 50.5% | 2.344 | +210,566 | -7,241 | 0.608 |
| jepa_l1_180 | 685 | 51.8% | 2.393 | +207,129 | -5,375 | 0.629 |
| full_reg_100 | 685 | 50.5% | 2.324 | +206,690 | -6,310 | 0.619 |
| fixed_060 | 685 | 49.2% | 2.294 | +193,999 | -8,971 | 0.602 |

Decision: fixed 0.70 is the current robust deployable delta policy. Learned delta selectors remain research candidates.

## Config

```json
{
  "config": {
    "data": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\training_data\\training_data_spx_qqq_spy_jepa_xinput_v3.parquet",
    "signal_model_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\neural\\models\\jepa\\jepa_180m_frozen_march",
    "signal_mode": "base_jepa",
    "output_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\research_papers\\JEPA\\results\\jepa_option_policy",
    "model_dir": "C:\\Users\\\u00c1lvaro Schwiedop\\Desktop\\KriptaStudios\\Gex-Dashboard-Live\\neural\\models\\jepa\\jepa_option_policy_frozen_march",
    "tickers": [
      "SPX",
      "QQQ",
      "SPY"
    ],
    "train_start_date": "20250101",
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
    "n_estimators": 180,
    "exit_n_estimators": 100,
    "seed": 991,
    "n_jobs": 1,
    "greeks_cache_size": 50,
    "progress_every": 100,
    "max_signals": 0,
    "reuse_candidates": true
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
  "exit_features": [],
  "train_candidates": 6475,
  "test_candidates": 728,
  "train_signals": 925,
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
    "entry_threshold": -0.25,
    "exit_margin": NaN,
    "entry_threshold_grid": {
      "grid": [
        {
          "threshold": -1000000000.0,
          "score": 8.875914836589487,
          "trades": 182,
          "win_rate": 0.4010989010989011,
          "profit_factor": 1.3673079040761302,
          "pnl_dollars": 20422.908507459862,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 112.21378300802122,
          "avg_hold_minutes": 102.3076923076923,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6205857142857143
        },
        {
          "threshold": -0.5,
          "score": 8.875914836589487,
          "trades": 182,
          "win_rate": 0.4010989010989011,
          "profit_factor": 1.3673079040761302,
          "pnl_dollars": 20422.908507459862,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 112.21378300802122,
          "avg_hold_minutes": 102.3076923076923,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6205857142857143
        },
        {
          "threshold": -0.40082637152399386,
          "score": 8.875914836589487,
          "trades": 182,
          "win_rate": 0.4010989010989011,
          "profit_factor": 1.3673079040761302,
          "pnl_dollars": 20422.908507459862,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 112.21378300802122,
          "avg_hold_minutes": 102.3076923076923,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6205857142857143
        },
        {
          "threshold": -0.2898291155455615,
          "score": 8.875914836589487,
          "trades": 182,
          "win_rate": 0.4010989010989011,
          "profit_factor": 1.3673079040761302,
          "pnl_dollars": 20422.908507459862,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 112.21378300802122,
          "avg_hold_minutes": 102.3076923076923,
          "long_rate": 0.41208791208791207,
          "avg_delta_abs": 0.6205857142857143
        },
        {
          "threshold": -0.25,
          "score": 8.948972077832238,
          "trades": 181,
          "win_rate": 0.40331491712707185,
          "profit_factor": 1.3760208789535324,
          "pnl_dollars": 20774.978293124906,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 114.77888559737518,
          "avg_hold_minutes": 102.70718232044199,
          "long_rate": 0.4143646408839779,
          "avg_delta_abs": 0.6200591160220995
        },
        {
          "threshold": -0.24010666181249687,
          "score": 8.948972077832238,
          "trades": 181,
          "win_rate": 0.40331491712707185,
          "profit_factor": 1.3760208789535324,
          "pnl_dollars": 20774.978293124906,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 114.77888559737518,
          "avg_hold_minutes": 102.70718232044199,
          "long_rate": 0.4143646408839779,
          "avg_delta_abs": 0.6200591160220995
        },
        {
          "threshold": -0.11011949778845828,
          "score": 8.224146462851914,
          "trades": 172,
          "win_rate": 0.4011627906976744,
          "profit_factor": 1.321309873658668,
          "pnl_dollars": 17043.99004311504,
          "max_drawdown": -5786.952142234524,
          "avg_pnl": 99.09296536694792,
          "avg_hold_minutes": 101.68604651162791,
          "long_rate": 0.4186046511627907,
          "avg_delta_abs": 0.6156081395348838
        },
        {
          "threshold": -0.1,
          "score": 8.567118114788062,
          "trades": 169,
          "win_rate": 0.40236686390532544,
          "profit_factor": 1.362132057747517,
          "pnl_dollars": 18608.300286640326,
          "max_drawdown": -5786.952142234524,
          "avg_pnl": 110.10828571976523,
          "avg_hold_minutes": 101.80473372781066,
          "long_rate": 0.42011834319526625,
          "avg_delta_abs": 0.6142337278106509
        },
        {
          "threshold": 0.0,
          "score": 8.903742567240009,
          "trades": 159,
          "win_rate": 0.41509433962264153,
          "profit_factor": 1.4142548421373233,
          "pnl_dollars": 20155.01031468742,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 126.7610711615561,
          "avg_hold_minutes": 103.58490566037736,
          "long_rate": 0.4025157232704403,
          "avg_delta_abs": 0.609719496855346
        },
        {
          "threshold": 0.007571562231594652,
          "score": 8.903742567240009,
          "trades": 159,
          "win_rate": 0.41509433962264153,
          "profit_factor": 1.4142548421373233,
          "pnl_dollars": 20155.01031468742,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 126.7610711615561,
          "avg_hold_minutes": 103.58490566037736,
          "long_rate": 0.4025157232704403,
          "avg_delta_abs": 0.609719496855346
        },
        {
          "threshold": 0.05,
          "score": 8.838837925055696,
          "trades": 155,
          "win_rate": 0.4129032258064516,
          "profit_factor": 1.41423471914875,
          "pnl_dollars": 19865.03840013244,
          "max_drawdown": -5786.952142234526,
          "avg_pnl": 128.16153806537056,
          "avg_hold_minutes": 103.25806451612904,
          "long_rate": 0.3935483870967742,
          "avg_delta_abs": 0.611445806451613
        },
        {
          "threshold": 0.1,
          "score": 8.678186111740672,
          "trades": 144,
          "win_rate": 0.4166666666666667,
          "profit_factor": 1.4215924146067833,
          "pnl_dollars": 19229.500470630985,
          "max_drawdown": -6393.017461302874,
          "avg_pnl": 133.53819771271517,
          "avg_hold_minutes": 103.57638888888889,
          "long_rate": 0.3888888888888889,
          "avg_delta_abs": 0.6049270833333333
        },
        {
          "threshold": 0.10463658202429257,
          "score": 8.17369706216079,
          "trades": 143,
          "win_rate": 0.4125874125874126,
          "profit_factor": 1.3696930927282644,
          "pnl_dollars": 16862.28986647619,
          "max_drawdown": -6393.017461302872,
          "avg_pnl": 117.91811095437895,
          "avg_hold_minutes": 103.04195804195804,
          "long_rate": 0.38461538461538464,
          "avg_delta_abs": 0.6042188811188811
        },
        {
          "threshold": 0.2,
          "score": 7.727314333058161,
          "trades": 128,
          "win_rate": 0.4296875,
          "profit_factor": 1.352738901196435,
          "pnl_dollars": 14729.079142262919,
          "max_drawdown": -6393.017461302873,
          "avg_pnl": 115.07093079892906,
          "avg_hold_minutes": 104.3359375,
          "long_rate": 0.390625,
          "avg_delta_abs": 0.6026750000000001
        },
        {
          "threshold": 0.20866137581428906,
          "score": 7.8645329528935335,
          "trades": 127,
          "win_rate": 0.4330708661417323,
          "profit_factor": 1.3684078520858958,
          "pnl_dollars": 15207.209809105454,
          "max_drawdown": -5914.886794460338,
          "avg_pnl": 119.74180952051539,
          "avg_hold_minutes": 104.60629921259843,
          "long_rate": 0.3858267716535433,
          "avg_delta_abs": 0.604240157480315
        },
        {
          "threshold": 0.3,
          "score": 8.199986135505728,
          "trades": 111,
          "win_rate": 0.44144144144144143,
          "profit_factor": 1.449923980895771,
          "pnl_dollars": 16598.499173267493,
          "max_drawdown": -6026.568982828142,
          "avg_pnl": 149.53602858799545,
          "avg_hold_minutes": 106.57657657657657,
          "long_rate": 0.32432432432432434,
          "avg_delta_abs": 0.6031297297297297
        },
        {
          "threshold": 0.3333451196537931,
          "score": 7.75131012428537,
          "trades": 107,
          "win_rate": 0.42990654205607476,
          "profit_factor": 1.4110279589070498,
          "pnl_dollars": 14985.383035040344,
          "max_drawdown": -7076.92495925429,
          "avg_pnl": 140.0503087386948,
          "avg_hold_minutes": 104.20560747663552,
          "long_rate": 0.3177570093457944,
          "avg_delta_abs": 0.6016168224299066
        },
        {
          "threshold": 0.47482859552798884,
          "score": 8.672603785710761,
          "trades": 86,
          "win_rate": 0.43023255813953487,
          "profit_factor": 1.6046048211200092,
          "pnl_dollars": 17500.876193041993,
          "max_drawdown": -4870.030629311468,
          "avg_pnl": 203.4985603842092,
          "avg_hold_minutes": 101.62790697674419,
          "long_rate": 0.29069767441860467,
          "avg_delta_abs": 0.5988418604651163
        },
        {
          "threshold": 0.6933195524928704,
          "score": 7.064236076201121,
          "trades": 62,
          "win_rate": 0.3870967741935484,
          "profit_factor": 1.4851349457319731,
          "pnl_dollars": 11546.234406269516,
          "max_drawdown": -4870.03062931147,
          "avg_pnl": 186.22958719789543,
          "avg_hold_minutes": 99.51612903225806,
          "long_rate": 0.27419354838709675,
          "avg_delta_abs": 0.5938096774193549
        },
        {
          "threshold": 0.9514592373075991,
          "score": 4.68107685005873,
          "trades": 30,
          "win_rate": 0.36666666666666664,
          "profit_factor": 1.3240896745435116,
          "pnl_dollars": 4370.808965940014,
          "max_drawdown": -6058.220930171823,
          "avg_pnl": 145.69363219800047,
          "avg_hold_minutes": 102.83333333333333,
          "long_rate": 0.2,
          "avg_delta_abs": 0.6130200000000001
        }
      ]
    },
    "exit_margin_grid": {
      "grid": []
    },
    "entry_validation_metrics": {
      "trades": 181,
      "win_rate": 0.40331491712707185,
      "profit_factor": 1.3760208789535324,
      "pnl_dollars": 20774.978293124906,
      "max_drawdown": -5786.952142234526,
      "avg_pnl": 114.77888559737518,
      "avg_hold_minutes": 102.70718232044199,
      "long_rate": 0.4143646408839779,
      "avg_delta_abs": 0.6200591160220995
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
        "profit_factor": 1.657083365430647,
        "pnl_dollars": 18866.67144246447,
        "max_drawdown": -4814.514131476706,
        "avg_pnl": 181.41030233138915,
        "avg_hold_minutes": 112.54807692307692,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.6396740384615384
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.4277498360689975,
          "pnl_dollars": 3070.107911609782,
          "max_drawdown": -2250.9525425672814,
          "avg_pnl": 87.71736890313663,
          "avg_hold_minutes": 105.71428571428571,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6644399999999999
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.45714285714285713,
          "profit_factor": 2.1197664370658282,
          "pnl_dollars": 14934.168749338838,
          "max_drawdown": -2733.917365292743,
          "avg_pnl": 426.6905356953954,
          "avg_hold_minutes": 121.85714285714286,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.6172542857142856
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.1051887387426136,
          "pnl_dollars": 862.3947815158497,
          "max_drawdown": -2498.6198540583055,
          "avg_pnl": 25.36455239752499,
          "avg_hold_minutes": 110.0,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6372588235294118
        }
      }
    },
    "learned_delta_ranker_all_hard": {
      "overall": {
        "trades": 104,
        "win_rate": 0.3942307692307692,
        "profit_factor": 1.7858934336036827,
        "pnl_dollars": 19530.385959490788,
        "max_drawdown": -3141.740873965402,
        "avg_pnl": 187.79217268741144,
        "avg_hold_minutes": 108.50961538461539,
        "long_rate": 0.6442307692307693,
        "avg_delta_abs": 0.6395788461538461
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.377211464092639,
          "pnl_dollars": 2461.92929981687,
          "max_drawdown": -2112.0218844432366,
          "avg_pnl": 70.34083713762486,
          "avg_hold_minutes": 108.71428571428571,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6947142857142857
        },
        "SPX": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 2.6123451383511203,
          "pnl_dollars": 16855.30759555126,
          "max_drawdown": -2095.323143055865,
          "avg_pnl": 481.58021701575035,
          "avg_hold_minutes": 106.42857142857143,
          "long_rate": 0.6285714285714286,
          "avg_delta_abs": 0.5506714285714285
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.027081592617023,
          "pnl_dollars": 213.14906412265032,
          "max_drawdown": -2387.2376688813006,
          "avg_pnl": 6.269090121254421,
          "avg_hold_minutes": 110.44117647058823,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6743441176470588
        }
      }
    },
    "supervised_entry_strike_skip_hard": {
      "overall": {
        "trades": 103,
        "win_rate": 0.4077669902912621,
        "profit_factor": 1.6921078590639687,
        "pnl_dollars": 19460.98910354545,
        "max_drawdown": -4814.514131476706,
        "avg_pnl": 188.94164178199466,
        "avg_hold_minutes": 112.81553398058253,
        "long_rate": 0.6407766990291263,
        "avg_delta_abs": 0.6440184466019416
      },
      "per_ticker": {
        "QQQ": {
          "trades": 35,
          "win_rate": 0.42857142857142855,
          "profit_factor": 1.4277498360689975,
          "pnl_dollars": 3070.107911609782,
          "max_drawdown": -2250.9525425672814,
          "avg_pnl": 87.71736890313663,
          "avg_hold_minutes": 105.71428571428571,
          "long_rate": 0.6571428571428571,
          "avg_delta_abs": 0.6644399999999999
        },
        "SPX": {
          "trades": 34,
          "win_rate": 0.47058823529411764,
          "profit_factor": 2.2186332525916628,
          "pnl_dollars": 15528.48641041981,
          "max_drawdown": -2315.8942774184034,
          "avg_pnl": 456.7201885417591,
          "avg_hold_minutes": 122.94117647058823,
          "long_rate": 0.6176470588235294,
          "avg_delta_abs": 0.6297558823529412
        },
        "SPY": {
          "trades": 34,
          "win_rate": 0.3235294117647059,
          "profit_factor": 1.1051887387426136,
          "pnl_dollars": 862.3947815158497,
          "max_drawdown": -2498.6198540583055,
          "avg_pnl": 25.36455239752499,
          "avg_hold_minutes": 110.0,
          "long_rate": 0.6470588235294118,
          "avg_delta_abs": 0.6372588235294118
        }
      }
    },
    "supervised_entry_strike_learned_exit": {
      "overall": {
        "trades": 0,
        "win_rate": NaN,
        "profit_factor": NaN,
        "pnl_dollars": 0.0,
        "max_drawdown": 0.0,
        "avg_pnl": NaN,
        "avg_hold_minutes": NaN,
        "long_rate": NaN,
        "avg_delta_abs": NaN
      },
      "per_ticker": {}
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
