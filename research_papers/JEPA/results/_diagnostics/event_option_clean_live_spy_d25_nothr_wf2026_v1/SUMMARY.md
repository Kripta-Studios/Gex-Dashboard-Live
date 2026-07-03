# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 120,
  "win_rate": 0.325,
  "profit_factor": 0.8024691358024693,
  "pnl_return": -4.799999999999999,
  "avg_return": -0.039999999999999994,
  "max_drawdown": -7.299999999999997,
  "call_rate": 0.38333333333333336,
  "days_with_trades": 120,
  "daily_win_rate": 0.325,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -7.299999999999997,
  "top5_day_return": 2.5,
  "top5_share_of_pnl": -0.5208333333333335,
  "min_month_trades": 18,
  "positive_month_rate": 0.5
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 120,
    "win_rate": 0.325,
    "profit_factor": 0.8024691358024693,
    "pnl_return": -4.799999999999999,
    "avg_return": -0.039999999999999994,
    "max_drawdown": -7.299999999999997,
    "call_rate": 0.38333333333333336,
    "days_with_trades": 120,
    "daily_win_rate": 0.325,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.299999999999997,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.5208333333333335,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,12667,4822,779,5.551047837737513,False,128,0.4296875,1.2656534295306903,5.772093008749546,0.04509447663085583,-2.4999999999999982,0.6484375,128,0.4296875,-0.3,-2.4999999999999982,2.5,0.43311845394909787,19,0.8333333333333334,20,0.3,0.7142857142857144,-1.2,-0.06,-2.6,0.85,20,0.3,-0.3,-2.6,2.5,-2.0833333333333335,20,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday1,15197,4731,615,3.139438079970995,False,126,0.35714285714285715,0.925925925925926,-1.8000000000000005,-0.014285714285714289,-5.799999999999999,0.047619047619047616,126,0.35714285714285715,-0.3,-5.799999999999999,2.5,-1.3888888888888886,19,0.3333333333333333,19,0.05263157894736842,0.0925925925925926,-4.8999999999999995,-0.25789473684210523,-4.899999999999999,0.0,19,0.05263157894736842,-0.3,-4.899999999999999,-0.7,0.14285714285714288,19,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr-999.000_maxday1,17516,4560,799,4.5585769425267575,False,124,0.4032258064516129,1.1349239857390931,2.972093008749547,0.023968492006044735,-2.599999999999998,0.7096774193548387,124,0.4032258064516129,-0.3,-2.599999999999998,2.5,0.8411580635734642,19,0.3333333333333333,22,0.4090909090909091,1.1538461538461542,0.6,0.02727272727272727,-3.0999999999999996,0.8181818181818182,22,0.4090909090909091,-0.3,-3.0999999999999996,2.5,4.166666666666667,22,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday1,19947,4539,689,5.154760112059621,False,125,0.424,1.226851851851852,4.9,0.039200000000000006,-2.9000000000000004,0.52,125,0.424,-0.3,-2.9000000000000004,2.5,0.5102040816326531,19,0.6666666666666666,18,0.4444444444444444,1.3333333333333335,1.0,0.05555555555555555,-1.9999999999999991,0.3333333333333333,18,0.4444444444444444,-0.3,-1.9999999999999991,2.5,2.5,18,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-999.000_maxday1,22454,4376,775,5.703971820606272,False,120,0.4583333333333333,1.4102564102564104,7.999999999999998,0.06666666666666665,-2.8000000000000043,0.35,120,0.4583333333333333,-0.3,-2.8000000000000043,2.5,0.31250000000000006,18,0.6666666666666666,20,0.35,0.8974358974358977,-0.3999999999999999,-0.019999999999999997,-1.0,0.1,20,0.35,-0.3,-1.0,2.5,-6.250000000000002,20,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-999.000_maxday1,24374,4504,724,3.484782293049079,False,121,0.371900826446281,0.9868421052631579,-0.30000000000000027,-0.002479338842975209,-5.199999999999996,0.256198347107438,121,0.371900826446281,-0.3,-5.199999999999996,2.5,-8.333333333333327,18,0.3333333333333333,21,0.38095238095238093,1.025641025641026,0.09999999999999998,0.004761904761904761,-1.7000000000000002,0.14285714285714285,21,0.38095238095238093,-0.3,-1.7000000000000002,2.5,25.000000000000007,21,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spy_d25_nothr_wf2026_v1",
    "tickers": [
      "SPY"
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
    "min_val_trades": 1,
    "min_month_trades": 1,
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
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 100,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 8.0,
    "lgb_jobs": 8,
    "threshold_grid": [
      -999.0
    ],
    "threshold_quantiles": [],
    "max_day_grid": [
      1
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
    }
  ],
  "data_rows": 39663
}
```