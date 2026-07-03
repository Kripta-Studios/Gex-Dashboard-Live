# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 64,
  "win_rate": 0.515625,
  "profit_factor": 0.8870967741935482,
  "pnl_return": -2.0999999999999996,
  "avg_return": -0.032812499999999994,
  "max_drawdown": -5.4,
  "call_rate": 0.359375,
  "days_with_trades": 53,
  "daily_win_rate": 0.4528301886792453,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -4.800000000000001,
  "top5_day_return": 3.5,
  "top5_share_of_pnl": -1.666666666666667,
  "min_month_trades": 0,
  "positive_month_rate": 0.3333333333333333
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 20,
    "win_rate": 0.55,
    "profit_factor": 1.0185185185185186,
    "pnl_return": 0.10000000000000031,
    "avg_return": 0.005000000000000016,
    "max_drawdown": -1.4,
    "call_rate": 0.4,
    "days_with_trades": 20,
    "daily_win_rate": 0.55,
    "median_daily_return": 0.5,
    "daily_max_drawdown": -1.4,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": 24.999999999999922,
    "min_month_trades": 0,
    "positive_month_rate": 0.16666666666666666
  },
  "SPXW": {
    "trades": 44,
    "win_rate": 0.5,
    "profit_factor": 0.8333333333333335,
    "pnl_return": -2.1999999999999993,
    "avg_return": -0.04999999999999998,
    "max_drawdown": -5.4,
    "call_rate": 0.3409090909090909,
    "days_with_trades": 40,
    "daily_win_rate": 0.475,
    "median_daily_return": -0.09999999999999998,
    "daily_max_drawdown": -4.9,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": -1.363636363636364,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.450_maxday1,4362,4797,779,1.9909772657760405,False,40,0.425,0.649034681970795,-4.596372560846419,-0.11490931402116047,-5.271982339637004,0.325,40,0.425,-0.6,-5.271982339637004,2.5,-0.5439071717762641,6,0.3333333333333333,7,0.5714285714285714,1.1111111111111112,0.20000000000000007,0.02857142857142858,-1.7999999999999998,0.14285714285714285,7,0.5714285714285714,0.5,-1.7999999999999998,1.4,6.999999999999997,7,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,5225,4713,616,-9.999999999999996e+17,True,375,0.4666666666666667,0.7331940835160596,-31.638374927003742,-0.0843689998053433,-33.33837492700376,0.042666666666666665,126,0.4603174603174603,-0.7,-32.838374927003734,7.5,-0.23705389474977925,55,0.16666666666666666,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.300_maxday1,6003,4551,793,3.69817219925164,False,66,0.5303030303030303,0.9408602150537632,-1.1000000000000003,-0.01666666666666667,-3.7,0.803030303030303,66,0.5303030303030303,0.5,-3.7,2.5,-2.272727272727272,7,0.6666666666666666,16,0.4375,0.6481481481481483,-1.8999999999999997,-0.11874999999999998,-2.2,0.875,16,0.4375,-0.6,-2.2,2.5,-1.3157894736842108,16,0.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.502_maxday1,6817,4530,793,1.5931046756918148,False,58,0.4482758620689655,0.7018301695991577,-5.522999670169214,-0.0952241322442968,-8.922999670169213,0.06896551724137931,58,0.4482758620689655,-0.6,-8.922999670169213,2.5,-0.45265257093948097,5,0.5,7,0.42857142857142855,0.625,-0.8999999999999999,-0.12857142857142856,-1.4,0.0,7,0.42857142857142855,-0.6,-1.4,0.30000000000000004,-0.3333333333333334,7,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.500_maxday3,7669,4471,783,3.289318055165963,False,69,0.5072463768115942,0.875197411817597,-2.495488747682948,-0.03616650358960794,-3.795488747682949,0.057971014492753624,40,0.45,-0.19774437384147392,-3.6954887476829477,6.0,-2.4043386312885513,3,0.5,7,0.42857142857142855,0.625,-0.8999999999999999,-0.12857142857142856,-1.7999999999999998,0.0,4,0.25,-0.09999999999999998,-1.2999999999999998,-0.8999999999999999,1.0,7,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.500_maxday2,8317,4606,736,3.1008807897532007,False,31,0.5161290322580645,0.8888888888888891,-0.9999999999999998,-0.032258064516129024,-3.0,0.22580645161290322,25,0.44,-0.09999999999999998,-2.8,3.5,-3.500000000000001,3,0.3333333333333333,7,0.7142857142857143,2.0833333333333335,1.3,0.18571428571428572,-0.7,0.0,6,0.6666666666666666,0.5,-0.7,1.9,1.4615384615384615,7,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-0.070_maxday1,3974,4522,692,1.966791983246904,False,128,0.484375,0.809470726355509,-7.296628884372037,-0.05700491315915654,-8.014486010123246,0.46875,128,0.484375,-0.26974299264399304,-8.014486010123246,2.5,-0.3426239760328931,19,0.3333333333333333,20,0.55,1.0185185185185186,0.10000000000000031,0.005000000000000016,-1.4,0.4,20,0.55,0.5,-1.4,2.5,24.999999999999922,20,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_tp50_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30_clean1000_nopool_d35_return_wf2026_v1",
    "tickers": [
      "SPXW",
      "QQQ",
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [
      "zero_dte"
    ],
    "start_month": "202601",
    "end_month": "202606",
    "val_months": 6,
    "pooled_train": false,
    "delta_bucket": 35,
    "label_mode": "return",
    "clip_return": 2.0,
    "min_train_rows": 500,
    "min_val_rows": 30,
    "min_val_trades": 30,
    "min_month_trades": 3,
    "min_val_pf": 0.0,
    "min_val_win_rate": 0.0,
    "min_val_positive_month_rate": 0.0,
    "min_val_daily_win_rate": 0.0,
    "min_val_median_daily_return": -Infinity,
    "max_val_top5_share": Infinity,
    "max_val_daily_drawdown": Infinity,
    "min_call_rate": 0.05,
    "max_call_rate": 0.95,
    "cooldown_minutes": 30,
    "objective": "regression_l1",
    "n_estimators": 120,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 60,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "lgb_jobs": 8,
    "threshold_grid": [
      -999.0,
      0.2,
      0.3,
      0.4,
      0.45,
      0.5,
      0.55,
      0.6,
      0.65,
      0.7
    ],
    "threshold_quantiles": [
      0.3,
      0.5,
      0.7,
      0.85,
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
    "entry_time_min_et": "10:00",
    "allow_invalid_val_deploy": false,
    "deploy_month": "",
    "deploy_select_end_month": "",
    "export_deploy_model": false,
    "exclude_months": [],
    "skip_walkforward": false,
    "resume": false,
    "seed": 20260617
  },
  "feature_count": 241,
  "features": [
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
    "ctx_qqq_phys_d35_iv_skew_put_minus_call",
    "ctx_qqq_phys_total_volume_skew_call_minus_put",
    "ctx_qqq_phys_total_oi_skew_call_minus_put",
    "ctx_spy_qqq_ret_5m_spread",
    "ctx_spx_spy_ret_5m_spread",
    "ticker_QQQ",
    "ticker_SPXW",
    "ticker_SPY",
    "expiry_mode_zero_dte"
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
      "threshold": 0.2,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.2,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.2,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.3,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.3,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.3,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.4,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.4,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.4,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.45,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.45,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.45,
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
    }
  ],
  "data_rows": 39664
}
```