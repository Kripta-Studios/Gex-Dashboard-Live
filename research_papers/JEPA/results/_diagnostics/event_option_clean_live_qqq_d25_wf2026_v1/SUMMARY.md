# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 61,
  "win_rate": 0.4426229508196721,
  "profit_factor": 1.3235294117647058,
  "pnl_return": 3.3,
  "avg_return": 0.054098360655737705,
  "max_drawdown": -3.6999999999999966,
  "call_rate": 0.4426229508196721,
  "days_with_trades": 61,
  "daily_win_rate": 0.4426229508196721,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -3.6999999999999966,
  "top5_day_return": 2.5,
  "top5_share_of_pnl": 0.7575757575757576,
  "min_month_trades": 0,
  "positive_month_rate": 0.3333333333333333
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 61,
    "win_rate": 0.4426229508196721,
    "profit_factor": 1.3235294117647058,
    "pnl_return": 3.3,
    "avg_return": 0.054098360655737705,
    "max_drawdown": -3.6999999999999966,
    "call_rate": 0.4426229508196721,
    "days_with_trades": 61,
    "daily_win_rate": 0.4426229508196721,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.6999999999999966,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": 0.7575757575757576,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.321_maxday1,12667,4521,692,6.263716370312772,False,127,0.48031496062992124,1.5404040404040404,10.699999999999996,0.08425196850393697,-3.0999999999999996,0.6850393700787402,127,0.48031496062992124,-0.3,-3.0999999999999996,2.5,0.2336448598130842,19,0.8333333333333334,20,0.6,2.5,3.6000000000000005,0.18000000000000002,-0.6000000000000001,0.7,20,0.6,0.5,-0.6000000000000001,2.5,0.6944444444444443,20,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,15197,4416,550,-9.999999999999996e+17,True,374,0.34759358288770054,0.887978142076503,-8.2,-0.02192513368983957,-12.799999999999981,0.045454545454545456,126,0.3333333333333333,-0.09999999999999998,-12.500000000000002,7.5,-0.9146341463414634,57,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.501_maxday1,17516,4211,765,6.866868810479464,False,122,0.4918032786885246,1.6129032258064513,11.399999999999999,0.09344262295081966,-1.6,0.6065573770491803,122,0.4918032786885246,-0.3,-1.6,2.5,0.2192982456140351,19,1.0,22,0.5,1.666666666666667,2.2,0.1,-1.5999999999999999,0.5,22,0.5,0.1,-1.5999999999999999,2.5,1.1363636363636362,22,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,ABSTAIN_INVALID_VAL,19947,4179,637,-9.999999999999996e+17,True,370,0.3945945945945946,1.0745093274148565,5.007026802278357,0.013532504871022586,-6.70000000000002,0.34324324324324323,125,0.4,-0.09999999999999998,-6.400000000000004,7.5,1.497894917715891,54,0.6666666666666666,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.413_maxday1,22454,4013,712,7.161966183220485,False,116,0.5344827586206896,1.8900320056605253,14.418518491700517,0.12429757320431481,-2.2000000000000055,0.31896551724137934,116,0.5344827586206896,0.5,-2.2000000000000055,2.5,0.17338813286809127,16,0.8333333333333334,19,0.21052631578947367,0.44444444444444453,-2.4999999999999996,-0.13157894736842102,-3.099999999999999,0.10526315789473684,19,0.21052631578947367,-0.3,-3.099999999999999,1.7,-0.68,19,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,ABSTAIN_INVALID_VAL,24374,4100,619,-9.999999999999996e+17,True,359,0.33147632311977715,0.8210905346069517,-12.881481508299482,-0.0358815640899707,-18.58148150829951,0.20334261838440112,121,0.2809917355371901,-0.09999999999999998,-18.081481508299483,7.5,-0.5822311661254013,54,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_qqq_d25_wf2026_v1",
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