# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 91,
  "win_rate": 0.4065934065934066,
  "profit_factor": 1.141975308641975,
  "pnl_return": 2.3000000000000007,
  "avg_return": 0.025274725274725282,
  "max_drawdown": -3.9999999999999956,
  "call_rate": 0.26373626373626374,
  "days_with_trades": 77,
  "daily_win_rate": 0.45454545454545453,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -3.6999999999999984,
  "top5_day_return": 3.5,
  "top5_share_of_pnl": 1.521739130434782,
  "min_month_trades": 0,
  "positive_month_rate": 0.5
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 91,
    "win_rate": 0.4065934065934066,
    "profit_factor": 1.141975308641975,
    "pnl_return": 2.3000000000000007,
    "avg_return": 0.025274725274725282,
    "max_drawdown": -3.9999999999999956,
    "call_rate": 0.26373626373626374,
    "days_with_trades": 77,
    "daily_win_rate": 0.45454545454545453,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.6999999999999984,
    "top5_day_return": 3.5,
    "top5_share_of_pnl": 1.521739130434782,
    "min_month_trades": 0,
    "positive_month_rate": 0.5
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,ABSTAIN_INVALID_VAL,12667,4797,779,-9.999999999999996e+17,True,381,0.34120734908136485,0.8570628911438272,-10.738608434131029,-0.02818532397409719,-14.138608434131017,0.6272965879265092,128,0.2734375,-0.09999999999999998,-14.138608434131019,7.5,-0.6984145148790781,55,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,15197,4713,616,-9.999999999999996e+17,True,375,0.35733333333333334,0.9182516831388532,-5.910403309060921,-0.015761075490829123,-9.31040330906089,0.042666666666666665,126,0.30952380952380953,-0.09999999999999998,-9.110403309060915,7.5,-1.2689489376303904,55,0.5,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.620_maxday1,17516,4551,793,6.053018983663051,False,98,0.45918367346938777,1.4150943396226412,6.600000000000001,0.06734693877551022,-1.6,0.8367346938775511,98,0.45918367346938777,-0.3,-1.6,2.5,0.37878787878787873,14,1.0,20,0.5,1.666666666666667,2.0,0.1,-1.3000000000000003,0.8,20,0.5,0.1,-1.3000000000000003,2.5,1.25,20,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.429_maxday1,19947,4530,793,6.693128679676231,False,123,0.4878048780487805,1.5996278311130316,11.245637631144621,0.09142794822068798,-1.5000000000000018,0.3170731707317073,123,0.4878048780487805,-0.3,-1.5000000000000018,2.5,0.2223084258980823,18,0.8333333333333334,21,0.47619047619047616,1.5151515151515154,1.7,0.08095238095238096,-1.8000000000000003,0.23809523809523808,21,0.47619047619047616,-0.3,-1.8000000000000003,2.5,1.4705882352941178,21,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.500_maxday2,22454,4471,783,7.380690307474455,False,197,0.48223350253807107,1.5522875816993464,16.900000000000002,0.08578680203045687,-2.500000000000007,0.29441624365482233,107,0.6635514018691588,0.2,-2.2000000000000064,5.0,0.29585798816568043,24,1.0,31,0.3870967741935484,1.0526315789473686,0.3000000000000001,0.009677419354838714,-2.5000000000000004,0.0967741935483871,17,0.5882352941176471,0.2,-2.2,3.2,10.666666666666664,31,1.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.500_maxday1,24374,4606,736,7.213786067451277,False,102,0.5294117647058824,1.875,12.599999999999998,0.12352941176470586,-1.5000000000000036,0.17647058823529413,102,0.5294117647058824,0.5,-1.5000000000000036,2.5,0.19841269841269846,15,1.0,19,0.2631578947368421,0.5952380952380953,-1.7,-0.08947368421052632,-2.1,0.0,19,0.2631578947368421,-0.3,-2.1,2.5,-1.4705882352941178,19,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spxw_d25_wf2026_v1",
    "tickers": [
      "SPXW"
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
    "min_val_pf": 1.2,
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
    "lgb_jobs": 8,
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
      "phys_",
      "ctx_",
      "ret_",
      "dist_",
      "nearest",
      "ib_range",
      "minute",
      "dte_days",
      "underlying_volume",
      "spot"
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
  "feature_count": 125,
  "features": [
    "dte_days",
    "minute",
    "spot",
    "underlying_volume",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
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
  "data_rows": 39663
}
```