# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 227,
  "win_rate": 0.5198237885462555,
  "profit_factor": 1.2904317616688983,
  "pnl_return": 18.623292617071307,
  "avg_return": 0.08204093663908064,
  "max_drawdown": -6.574192445814827,
  "call_rate": 0.28634361233480177,
  "days_with_trades": 117,
  "daily_win_rate": 0.5128205128205128,
  "median_daily_return": 0.12247709131092266,
  "daily_max_drawdown": -6.574192445814831,
  "top5_day_return": 17.79736293763356,
  "top5_share_of_pnl": 0.9556507167437919,
  "min_month_trades": 18,
  "positive_month_rate": 1.0
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 227,
    "win_rate": 0.5198237885462555,
    "profit_factor": 1.2904317616688983,
    "pnl_return": 18.623292617071307,
    "avg_return": 0.08204093663908064,
    "max_drawdown": -6.574192445814827,
    "call_rate": 0.28634361233480177,
    "days_with_trades": 117,
    "daily_win_rate": 0.5128205128205128,
    "median_daily_return": 0.12247709131092266,
    "daily_max_drawdown": -6.574192445814831,
    "top5_day_return": 17.79736293763356,
    "top5_share_of_pnl": 0.9556507167437919,
    "min_month_trades": 18,
    "positive_month_rate": 1.0
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.086_maxday3,7659,1494,779,9.105642007206198,False,115,0.6608695652173913,2.2897610890310824,30.18040948332736,0.26243834333328137,-3.1197968079930334,0.14782608695652175,40,0.65,0.5523872558824049,-3.1197968079930263,16.431127873671493,0.5444302497866566,52,1.0,59,0.5084745762711864,1.3701710866034364,6.057756264548545,0.10267383499234822,-2.446092818594316,0.1694915254237288,20,0.55,0.22831061212583537,-1.915478152308422,9.539175930211739,1.5747044802771786,59,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday2,8306,1626,615,7.572203745104968,False,84,0.6071428571428571,1.9797050247289059,19.39815948963233,0.2309304701146706,-3.2113910058096735,0.19047619047619047,42,0.5952380952380952,0.23132093588209968,-2.7420927051590187,14.883627129041919,0.7672700668842691,40,1.0,38,0.5,1.2489137362557363,2.822150821022807,0.07426712686902123,-4.737866939264863,0.18421052631578946,19,0.47368421052631576,-0.31470598712511666,-4.737866939264865,10.550925665154928,3.7386115534856676,38,1.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.284_maxday3,9153,1394,799,6.791634990520595,False,70,0.6142857142857143,2.0120143189649284,16.33175242008677,0.2333107488583824,-5.337866939264874,0.2714285714285714,33,0.6363636363636364,0.6718281557682462,-5.337866939264867,11.637639329095999,0.7125775011616401,35,1.0,53,0.5094339622641509,1.034711076530088,0.5414927938693747,0.01021684516734669,-3.2063787063689344,0.5094339622641509,21,0.5238095238095238,0.053061232661335445,-3.2063787063689344,6.4966673489065245,11.997698625835689,53,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.247_maxday1,9932,1414,689,6.458024411664083,False,40,0.675,2.0794353134247947,7.9469358190139925,0.19867339547534982,-1.9100766069644228,0.6,40,0.675,0.3346990638733248,-1.9100766069644228,6.543659971181553,0.8234192549441591,18,1.0,18,0.5,1.0576480270468096,0.31129934605277065,0.017294408114042814,-1.8,0.2222222222222222,18,0.5,-0.1500000055879353,-1.8,4.342052584034828,13.948158385462124,18,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr-0.100_maxday2,10547,1488,775,5.764345692367623,False,80,0.5375,1.585220647102527,12.656006452643144,0.1582000806580393,-6.640948277953822,0.5375,40,0.525,0.03341546417086416,-6.316960567641534,14.399509830585908,1.1377609425585147,36,1.0,40,0.625,1.6335757549116188,5.702181794204568,0.1425545448551142,-3.8742313311581293,0.375,20,0.6,0.3411764615650409,-3.874231331158132,7.268716459070305,1.2747254860337651,40,1.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr0.050_maxday1,11346,1464,724,6.521911397862323,False,38,0.631578947368421,2.069131003608399,8.691252746560307,0.22871717754106072,-1.799999999999999,0.3684210526315789,38,0.631578947368421,0.2908065624613483,-1.799999999999999,9.19572248632028,1.0580433862034013,18,1.0,19,0.42105263157894735,1.4966243171744755,3.188411597373245,0.167811136703855,-2.691860452221819,0.10526315789473684,19,0.42105263157894735,-0.6,-2.691860452221819,8.447119032713662,2.6493188770461047,19,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\goal_clean_spy_d35_baseline_with_exit_wf202601_202606_v1",
    "tickers": [
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202601",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": false,
    "delta_bucket": 35,
    "label_mode": "return",
    "clip_return": 5.0,
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
    "min_call_rate": 0.0,
    "max_call_rate": 1.0,
    "cooldown_minutes": 30,
    "objective": "regression_l1",
    "n_estimators": 160,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 60,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "lgb_jobs": 4,
    "lgb_device_type": "gpu",
    "threshold_grid": [
      -999.0,
      -0.2,
      -0.1,
      0.0,
      0.05,
      0.1,
      0.2,
      0.3,
      0.4,
      0.5,
      0.75,
      1.0
    ],
    "threshold_quantiles": [
      0.3,
      0.5,
      0.7,
      0.85,
      0.95,
      0.98
    ],
    "max_day_grid": [
      1,
      2,
      3
    ],
    "feature_include_prefixes": [],
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
  "feature_count": 243,
  "features": [
    "dte_days",
    "minute",
    "spot",
    "underlying_volume",
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
      "threshold": -0.2,
      "max_trades_per_day": 1
    },
    {
      "threshold": -0.2,
      "max_trades_per_day": 2
    },
    {
      "threshold": -0.2,
      "max_trades_per_day": 3
    },
    {
      "threshold": -0.1,
      "max_trades_per_day": 1
    },
    {
      "threshold": -0.1,
      "max_trades_per_day": 2
    },
    {
      "threshold": -0.1,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.1,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.1,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.1,
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
    },
    {
      "threshold": 1.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": 1.0,
      "max_trades_per_day": 2
    },
    {
      "threshold": 1.0,
      "max_trades_per_day": 3
    }
  ],
  "data_rows": 13534
}
```