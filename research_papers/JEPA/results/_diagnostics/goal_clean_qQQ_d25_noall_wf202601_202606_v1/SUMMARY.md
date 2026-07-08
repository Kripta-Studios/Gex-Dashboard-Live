# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 234,
  "win_rate": 0.5042735042735043,
  "profit_factor": 1.3788704720457974,
  "pnl_return": 26.02014096220116,
  "avg_return": 0.11119718359915026,
  "max_drawdown": -9.103813749560558,
  "call_rate": 0.36752136752136755,
  "days_with_trades": 119,
  "daily_win_rate": 0.5126050420168067,
  "median_daily_return": 0.01842101960961473,
  "daily_max_drawdown": -7.903813749560564,
  "top5_day_return": 18.57167261615931,
  "top5_share_of_pnl": 0.7137421985199057,
  "min_month_trades": 20,
  "positive_month_rate": 0.8333333333333334
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 234,
    "win_rate": 0.5042735042735043,
    "profit_factor": 1.3788704720457974,
    "pnl_return": 26.02014096220116,
    "avg_return": 0.11119718359915026,
    "max_drawdown": -9.103813749560558,
    "call_rate": 0.36752136752136755,
    "days_with_trades": 119,
    "daily_win_rate": 0.5126050420168067,
    "median_daily_return": 0.01842101960961473,
    "daily_max_drawdown": -7.903813749560564,
    "top5_day_return": 18.57167261615931,
    "top5_share_of_pnl": 0.7137421985199057,
    "min_month_trades": 20,
    "positive_month_rate": 0.8333333333333334
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr-0.200_maxday1,7126,1369,692,7.674235915875795,False,41,0.6585365853658537,2.6995675756376305,14.276367635356094,0.3482040886672218,-1.799999999999999,0.43902439024390244,41,0.6585365853658537,0.3611111005988279,-1.799999999999999,10.936828218018697,0.766079194467725,19,1.0,20,0.65,2.138722729248673,4.782635462844427,0.23913177314222134,-1.2000000000000002,0.4,20,0.65,0.33160945612887993,-1.2000000000000002,5.703981131573839,1.1926439252765986,20,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr0.000_maxday3,7751,1436,550,6.462867420988947,False,117,0.5470085470085471,1.5331409379133196,16.953881825643577,0.14490497286874854,-5.838544365619306,0.4700854700854701,41,0.5853658536585366,0.39848486271552674,-5.838544365619313,16.38079291504419,0.9661971861964637,57,1.0,54,0.42592592592592593,0.7680425120590275,-4.264042257619341,-0.07896374551146927,-9.103813749560565,0.3888888888888889,19,0.3684210526315789,-0.5316326952635959,-7.9038137495605625,6.324696541919638,-1.4832631010206692,54,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr-0.063_maxday2,8495,1242,765,5.936268000236667,False,77,0.5714285714285714,1.8041347709974782,15.855987531185578,0.20592191598942308,-6.015674102267893,0.4935064935064935,39,0.5384615384615384,0.19761923143383353,-5.415674102267875,14.237412012599037,0.8979202326311669,37,0.5,44,0.6136363636363636,2.4233271744506086,14.4684301205127,0.3288279572843795,-2.052439080236356,0.5909090909090909,22,0.5909090909090909,0.36705418964660763,-1.4524390802363563,12.854386783310542,0.8884437825141901,44,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.050_maxday2,9187,1315,637,6.516225200498117,False,81,0.5555555555555556,1.8579376666113714,18.431323389004763,0.22754720233339215,-7.30115803525918,0.691358024691358,41,0.5121951219512195,0.02179498935827795,-7.0083008048197035,15.37852449841274,0.8343689801236315,37,1.0,36,0.5,1.4596902570444845,4.858200175058677,0.13495000486274103,-5.6711611238805,0.5833333333333334,18,0.5,-0.06856728177034133,-5.671161123880502,10.581294521055362,2.1780276933375973,36,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.000_maxday3,9737,1402,712,7.3593585873054455,False,120,0.5583333333333333,1.7321846869642838,22.86450073722135,0.19053750614351123,-5.502509271698955,0.5666666666666667,40,0.625,0.5517253658208495,-5.400000000000002,16.05586789149495,0.7022181711301242,54,1.0,60,0.45,1.060633663114397,1.2005465296650675,0.020009108827751126,-5.794658704603771,0.11666666666666667,20,0.45,-0.09223146036747792,-5.522926422382539,12.617133402694735,10.509491378243128,60,1.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr-0.200_maxday1,10502,1349,619,5.319821544305341,False,38,0.5263157894736842,1.5677677089893551,6.131891257085037,0.16136555939697467,-3.8554054968369242,0.23684210526315788,38,0.5263157894736842,0.21776436754819195,-3.8554054968369242,9.788615602711651,1.596345269724326,18,1.0,20,0.5,1.8943979285899837,4.974370931739632,0.2487185465869816,-1.8688405790841771,0.15,20,0.5,-0.03442028954208859,-1.8688405790841771,8.336571001258735,1.6759045748008337,20,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\goal_clean_qQQ_d25_noall_wf202601_202606_v1",
    "tickers": [
      "QQQ"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202601",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": false,
    "delta_bucket": 25,
    "label_mode": "return",
    "clip_return": 5.0,
    "min_train_rows": 500,
    "min_val_rows": 30,
    "min_val_trades": 18,
    "min_month_trades": 18,
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
    "n_estimators": 180,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 60,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "lgb_jobs": 4,
    "lgb_device_type": "gpu",
    "threshold_grid": [
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
    "seed": 20260704
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
    "ticker_QQQ",
    "expiry_mode_zero_dte"
  ],
  "grid": [
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
  "data_rows": 12470
}
```