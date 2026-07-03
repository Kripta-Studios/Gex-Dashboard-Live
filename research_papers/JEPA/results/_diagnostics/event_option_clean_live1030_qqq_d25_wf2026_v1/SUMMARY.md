# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 18,
  "win_rate": 0.16666666666666666,
  "profit_factor": 0.3333333333333334,
  "pnl_return": -2.9999999999999996,
  "avg_return": -0.16666666666666663,
  "max_drawdown": -2.999999999999999,
  "call_rate": 0.1111111111111111,
  "days_with_trades": 18,
  "daily_win_rate": 0.16666666666666666,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -2.999999999999999,
  "top5_day_return": 0.8999999999999999,
  "top5_share_of_pnl": -0.3,
  "min_month_trades": 0,
  "positive_month_rate": 0.0
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 18,
    "win_rate": 0.16666666666666666,
    "profit_factor": 0.3333333333333334,
    "pnl_return": -2.9999999999999996,
    "avg_return": -0.16666666666666663,
    "max_drawdown": -2.999999999999999,
    "call_rate": 0.1111111111111111,
    "days_with_trades": 18,
    "daily_win_rate": 0.16666666666666666,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -2.999999999999999,
    "top5_day_return": 0.8999999999999999,
    "top5_share_of_pnl": -0.3,
    "min_month_trades": 0,
    "positive_month_rate": 0.0
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,ABSTAIN_INVALID_VAL,11460,3987,617,-9.999999999999996e+17,True,370,0.33513513513513515,0.8345651639548168,-12.20909090013454,-0.03299754297333659,-13.109090900134571,0.2972972972972973,127,0.29133858267716534,-0.09999999999999998,-12.809090900134535,6.590909099865461,-0.539836188769209,56,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,13618,3918,509,-9.999999999999996e+17,True,368,0.3342391304347826,0.8311688312906867,-12.40909090013454,-0.03372035570688734,-16.809090900134557,0.02717391304347826,126,0.2698412698412698,-0.09999999999999998,-16.009090900134538,7.5,-0.6043956048318322,56,0.5,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,ABSTAIN_INVALID_VAL,15648,3744,712,-9.999999999999996e+17,True,362,0.32044198895027626,0.7779255977314518,-16.38909088741888,-0.04527373173320133,-16.48909088741893,0.32044198895027626,124,0.22580645161290322,-0.09999999999999998,-16.389090887418874,6.590909099865461,-0.40215220875521446,54,0.16666666666666666,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,ABSTAIN_INVALID_VAL,17748,3764,567,-9.999999999999996e+17,True,365,0.3041095890410959,0.725830529545828,-20.834387310187907,-0.057080513178597005,-22.73438731018798,0.08493150684931507,125,0.232,-0.09999999999999998,-22.43438731018792,6.5,-0.31198421644113017,54,0.16666666666666666,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.428_maxday1,19906,3634,653,6.066550011395878,False,116,0.46551724137931033,1.451612903225806,8.399999999999997,0.07241379310344825,-2.1999999999999984,0.1724137931034483,116,0.46551724137931033,-0.3,-2.1999999999999984,2.5,0.2976190476190477,18,0.8333333333333334,18,0.16666666666666666,0.3333333333333334,-2.9999999999999996,-0.16666666666666663,-2.999999999999999,0.1111111111111111,18,0.16666666666666666,-0.3,-2.999999999999999,0.8999999999999999,-0.3,18,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,ABSTAIN_INVALID_VAL,21622,3713,581,-9.999999999999996e+17,True,356,0.3202247191011236,0.7851239669421489,-15.600000000000001,-0.04382022471910113,-16.000000000000103,0.2696629213483146,121,0.2644628099173554,-0.09999999999999998,-16.00000000000001,7.5,-0.4807692307692307,53,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_qqq_d25_wf2026_v1",
    "tickers": [
      "QQQ"
    ],
    "train_tickers": [
      "SPXW",
      "SPY",
      "QQQ"
    ],
    "expiry_modes": [
      "zero_dte"
    ],
    "start_month": "202601",
    "end_month": "202606",
    "val_months": 6,
    "pooled_train": true,
    "delta_bucket": 25,
    "label_mode": "win",
    "clip_return": 2.0,
    "min_train_rows": 500,
    "min_val_rows": 30,
    "min_val_trades": 72,
    "min_month_trades": 12,
    "min_val_pf": 1.15,
    "min_val_win_rate": 0.45,
    "min_val_positive_month_rate": 0.0,
    "min_val_daily_win_rate": 0.0,
    "min_val_median_daily_return": -Infinity,
    "max_val_top5_share": Infinity,
    "max_val_daily_drawdown": Infinity,
    "min_call_rate": 0.05,
    "max_call_rate": 0.85,
    "cooldown_minutes": 30,
    "objective": "regression_l1",
    "n_estimators": 180,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 100,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 8.0,
    "lgb_jobs": 4,
    "threshold_grid": [
      -999.0,
      0.48,
      0.5,
      0.52,
      0.55,
      0.58,
      0.6,
      0.62,
      0.65,
      0.68,
      0.7,
      0.72,
      0.75
    ],
    "threshold_quantiles": [
      0.3,
      0.4,
      0.5,
      0.6,
      0.7,
      0.8,
      0.85,
      0.9,
      0.93,
      0.95
    ],
    "max_day_grid": [
      1,
      2,
      3
    ],
    "feature_include_prefixes": [
      "ret_",
      "dist_",
      "nearest_",
      "ib_",
      "call_",
      "put_",
      "phys_",
      "ctx_"
    ],
    "feature_exclude_prefixes": [],
    "live_observable_features_only": true,
    "entry_time_min_et": "10:30",
    "allow_invalid_val_deploy": false,
    "deploy_month": "",
    "deploy_select_end_month": "",
    "export_deploy_model": false,
    "exclude_months": [],
    "skip_walkforward": false,
    "resume": false,
    "seed": 20260617
  },
  "feature_count": 273,
  "features": [
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "dist_fib_127_up_bps",
    "dist_fib_161_up_bps",
    "dist_fib_200_up_bps",
    "dist_fib_127_dn_bps",
    "dist_fib_161_dn_bps",
    "dist_fib_200_dn_bps",
    "nearest_level_abs_bps",
    "ib_range_bps",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
    "call_d15_available",
    "call_d15_strike_bps",
    "call_d15_abs_delta",
    "call_d15_iv",
    "call_d15_mid_bps",
    "call_d15_spread_pct",
    "call_d15_theta_over_mid",
    "call_d15_vega",
    "call_d15_oi",
    "call_d15_volume",
    "put_d15_available",
    "put_d15_strike_bps",
    "put_d15_abs_delta",
    "put_d15_iv",
    "put_d15_mid_bps",
    "put_d15_spread_pct",
    "put_d15_theta_over_mid",
    "put_d15_vega",
    "put_d15_oi",
    "put_d15_volume",
    "call_d25_available",
    "call_d25_strike_bps",
    "call_d25_abs_delta",
    "call_d25_iv",
    "call_d25_mid_bps",
    "call_d25_spread_pct",
    "call_d25_theta_over_mid",
    "call_d25_vega",
    "call_d25_oi",
    "call_d25_volume",
    "put_d25_available",
    "put_d25_strike_bps",
    "put_d25_abs_delta",
    "put_d25_iv",
    "put_d25_mid_bps",
    "put_d25_spread_pct",
    "put_d25_theta_over_mid",
    "put_d25_vega",
    "put_d25_oi",
    "put_d25_volume",
    "call_d35_available",
    "call_d35_strike_bps",
    "call_d35_abs_delta",
    "call_d35_iv",
    "call_d35_mid_bps",
    "call_d35_spread_pct",
    "call_d35_theta_over_mid",
    "call_d35_vega",
    "call_d35_oi",
    "call_d35_volume",
    "put_d35_available",
    "put_d35_strike_bps",
    "put_d35_abs_delta",
    "put_d35_iv",
    "put_d35_mid_bps",
    "put_d35_spread_pct",
    "put_d35_theta_over_mid",
    "put_d35_vega",
    "put_d35_oi",
    "put_d35_volume",
    "call_d50_available",
    "call_d50_strike_bps",
    "call_d50_abs_delta",
    "call_d50_iv",
    "call_d50_mid_bps",
    "call_d50_spread_pct",
    "call_d50_theta_over_mid",
    "call_d50_vega",
    "call_d50_oi",
    "call_d50_volume",
    "put_d50_available",
    "put_d50_strike_bps",
    "put_d50_abs_delta",
    "put_d50_iv",
    "put_d50_mid_bps",
    "put_d50_spread_pct",
    "put_d50_theta_over_mid",
    "put_d50_vega",
    "put_d50_oi",
    "put_d50_volume",
    "call_d65_available",
    "call_d65_strike_bps",
    "call_d65_abs_delta",
    "call_d65_iv",
    "call_d65_mid_bps",
    "call_d65_spread_pct",
    "call_d65_theta_over_mid",
    "call_d65_vega",
    "call_d65_oi",
    "call_d65_volume",
    "put_d65_available",
    "put_d65_strike_bps",
    "put_d65_abs_delta",
    "put_d65_iv",
    "put_d65_mid_bps",
    "put_d65_spread_pct",
    "put_d65_theta_over_mid",
    "put_d65_vega",
    "put_d65_oi",
    "put_d65_volume",
    "call_d80_available",
    "call_d80_strike_bps",
    "call_d80_abs_delta",
    "call_d80_iv",
    "call_d80_mid_bps",
    "call_d80_spread_pct",
    "call_d80_theta_over_mid",
    "call_d80_vega",
    "call_d80_oi",
    "call_d80_volume",
    "put_d80_available",
    "put_d80_strike_bps",
    "put_d80_abs_delta",
    "put_d80_iv",
    "put_d80_mid_bps",
    "put_d80_spread_pct",
    "put_d80_theta_over_mid",
    "put_d80_vega",
    "put_d80_oi",
    "put_d80_volume",
    "phys_d15_iv_skew_put_minus_call",
    "phys_d15_iv_mean",
    "phys_d15_volume_skew_call_minus_put",
    "phys_d15_oi_skew_call_minus_put",
    "phys_d15_mid_skew_call_minus_put",
    "phys_d15_spread_mean",
    "phys_d15_theta_skew_call_minus_put",
    "phys_d15_vega_skew_call_minus_put",
    "phys_d15_abs_delta_gap",
    "phys_d15_liquidity_score",
    "phys_d25_iv_skew_put_minus_call",
    "phys_d25_iv_mean",
    "phys_d25_volume_skew_call_minus_put",
    "phys_d25_oi_skew_call_minus_put",
    "phys_d25_mid_skew_call_minus_put",
    "phys_d25_spread_mean",
    "phys_d25_theta_skew_call_minus_put",
    "phys_d25_vega_skew_call_minus_put",
    "phys_d25_abs_delta_gap",
    "phys_d25_liquidity_score",
    "phys_d35_iv_skew_put_minus_call",
    "phys_d35_iv_mean",
    "phys_d35_volume_skew_call_minus_put",
    "phys_d35_oi_skew_call_minus_put",
    "phys_d35_mid_skew_call_minus_put",
    "phys_d35_spread_mean",
    "phys_d35_theta_skew_call_minus_put",
    "phys_d35_vega_skew_call_minus_put",
    "phys_d35_abs_delta_gap",
    "phys_d35_liquidity_score",
    "phys_d50_iv_skew_put_minus_call",
    "phys_d50_iv_mean",
    "phys_d50_volume_skew_call_minus_put",
    "phys_d50_oi_skew_call_minus_put",
    "phys_d50_mid_skew_call_minus_put",
    "phys_d50_spread_mean",
    "phys_d50_theta_skew_call_minus_put",
    "phys_d50_vega_skew_call_minus_put",
    "phys_d50_abs_delta_gap",
    "phys_d50_liquidity_score",
    "phys_d65_iv_skew_put_minus_call",
    "phys_d65_iv_mean",
    "phys_d65_volume_skew_call_minus_put",
    "phys_d65_oi_skew_call_minus_put",
    "phys_d65_mid_skew_call_minus_put",
    "phys_d65_spread_mean",
    "phys_d65_theta_skew_call_minus_put",
    "phys_d65_vega_skew_call_minus_put",
    "phys_d65_abs_delta_gap",
    "phys_d65_liquidity_score",
    "phys_d80_iv_skew_put_minus_call",
    "phys_d80_iv_mean",
    "phys_d80_volume_skew_call_minus_put",
    "phys_d80_oi_skew_call_minus_put",
    "phys_d80_mid_skew_call_minus_put",
    "phys_d80_spread_mean",
    "phys_d80_theta_skew_call_minus_put",
    "phys_d80_vega_skew_call_minus_put",
    "phys_d80_abs_delta_gap",
    "phys_d80_liquidity_score",
    "phys_total_volume_skew_call_minus_put",
    "phys_total_oi_skew_call_minus_put",
    "phys_total_option_volume_log",
    "phys_total_option_oi_log",
    "phys_call_iv_slope_low_to_high",
    "phys_put_iv_slope_low_to_high",
    "phys_call_mid_slope_low_to_high",
    "phys_put_mid_slope_low_to_high",
    "phys_fib_up_min_abs_bps",
    "phys_fib_up_mean_signed_bps",
    "phys_fib_dn_min_abs_bps",
    "phys_fib_dn_mean_signed_bps",
    "phys_fib_any_min_abs_bps",
    "phys_ib_edge_min_abs_bps",
    "phys_ib_balance",
    "phys_nearest_level_vs_ib_range",
    "phys_momentum_accel_ret_1m_bps_minus_ret_5m_bps",
    "phys_abs_ret_1m_bps",
    "phys_momentum_accel_ret_5m_bps_minus_ret_15m_bps",
    "phys_abs_ret_5m_bps",
    "phys_momentum_accel_ret_15m_bps_minus_ret_30m_bps",
    "phys_abs_ret_15m_bps",
    "phys_abs_ret_30m_bps",
    "ctx_spx_spot",
    "ctx_spx_ret_1m_bps",
    "ctx_spx_ret_1m_bps_minus_self",
    "ctx_spx_ret_5m_bps",
    "ctx_spx_ret_5m_bps_minus_self",
    "ctx_spx_ret_15m_bps",
    "ctx_spx_ret_15m_bps_minus_self",
    "ctx_spx_ret_30m_bps",
    "ctx_spx_ret_30m_bps_minus_self",
    "ctx_spx_ib_range_bps",
    "ctx_spx_nearest_level_abs_bps",
    "ctx_spx_phys_d35_iv_skew_put_minus_call",
    "ctx_spx_phys_total_volume_skew_call_minus_put",
    "ctx_spx_phys_total_oi_skew_call_minus_put",
    "ctx_spy_spot",
    "ctx_spy_ret_1m_bps",
    "ctx_spy_ret_1m_bps_minus_self",
    "ctx_spy_ret_5m_bps",
    "ctx_spy_ret_5m_bps_minus_self",
    "ctx_spy_ret_15m_bps",
    "ctx_spy_ret_15m_bps_minus_self",
    "ctx_spy_ret_30m_bps",
    "ctx_spy_ret_30m_bps_minus_self",
    "ctx_spy_ib_range_bps",
    "ctx_spy_nearest_level_abs_bps",
    "ctx_spy_phys_d35_iv_skew_put_minus_call",
    "ctx_spy_phys_total_volume_skew_call_minus_put",
    "ctx_spy_phys_total_oi_skew_call_minus_put",
    "ctx_qqq_spot",
    "ctx_qqq_ret_1m_bps",
    "ctx_qqq_ret_1m_bps_minus_self",
    "ctx_qqq_ret_5m_bps",
    "ctx_qqq_ret_5m_bps_minus_self",
    "ctx_qqq_ret_15m_bps",
    "ctx_qqq_ret_15m_bps_minus_self",
    "ctx_qqq_ret_30m_bps",
    "ctx_qqq_ret_30m_bps_minus_self",
    "ctx_qqq_ib_range_bps",
    "ctx_qqq_nearest_level_abs_bps",
    "ctx_qqq_phys_d35_iv_skew_put_minus_call",
    "ctx_qqq_phys_total_volume_skew_call_minus_put",
    "ctx_qqq_phys_total_oi_skew_call_minus_put",
    "ctx_spy_qqq_ret_5m_spread",
    "ctx_spx_spy_ret_5m_spread",
    "ticker_QQQ",
    "ticker_SPXW",
    "ticker_SPY",
    "expiry_mode_zero_dte",
    "nearest_level_name_fib_127_dn",
    "nearest_level_name_fib_127_up",
    "nearest_level_name_fib_161_dn",
    "nearest_level_name_fib_161_up",
    "nearest_level_name_fib_200_dn",
    "nearest_level_name_fib_200_up",
    "nearest_level_name_ib_high",
    "nearest_level_name_ib_low"
  ],
  "grid": [
    {
      "threshold": -999.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": -999.0,
      "max_trades_per_day": 2
    },
    {
      "threshold": -999.0,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.48,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.48,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.48,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.5,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.5,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.5,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.52,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.52,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.52,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.55,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.55,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.55,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.58,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.58,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.58,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.6,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.6,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.6,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.62,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.62,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.62,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.65,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.65,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.65,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.68,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.68,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.68,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.7,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.7,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.7,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.72,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.72,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.72,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.75,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.75,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.75,
      "max_trades_per_day": 3
    }
  ],
  "data_rows": 35187
}
```