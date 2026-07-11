# Nested Event Option Profile Selector

For each ticker-month, every candidate profile is trained only on months before the validation window. Profile and threshold are selected only from validation months, then applied to the test month.

## Overall

```json
{
  "trades": 39,
  "win_rate": 0.4358974358974359,
  "profit_factor": 1.1088030396301882,
  "pnl_return": 1.3939921063526362,
  "avg_return": 0.03574338734237529,
  "max_drawdown": -4.766921782788755,
  "call_rate": 0.5128205128205128,
  "days_with_trades": 39,
  "daily_win_rate": 0.4358974358974359,
  "median_daily_return": -0.3908045624218768,
  "daily_max_drawdown": -4.766921782788755,
  "top5_day_return": 9.613067794184113,
  "top5_share_of_pnl": 6.896070465805284,
  "min_month_trades": 0,
  "positive_month_rate": 0.2
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 39,
    "win_rate": 0.4358974358974359,
    "profit_factor": 1.1088030396301882,
    "pnl_return": 1.3939921063526362,
    "avg_return": 0.03574338734237529,
    "max_drawdown": -4.766921782788755,
    "call_rate": 0.5128205128205128,
    "days_with_trades": 39,
    "daily_win_rate": 0.4358974358974359,
    "median_daily_return": -0.3908045624218768,
    "daily_max_drawdown": -4.766921782788755,
    "top5_day_return": 9.613067794184113,
    "top5_share_of_pnl": 6.896070465805284,
    "min_month_trades": 0,
    "positive_month_rate": 0.2
  }
}
```

## Selected Folds

```csv
ticker,month,profile,delta_bucket,label_mode,expiry_modes,train_scope,train_tickers,training_months,val_months,selection_months,cooldown_minutes,train_rows,val_rows,test_rows,feature_count,status,val_score,deploy_config,policy_artifact_path,policy_artifact_sha256,model_artifact_path,model_artifact_sha256,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate,selected
SPXW,202601,target_zero_dte_d25_win,25.0,win,zero_dte,target,SPXW,"202201,202202,202203,202204,202205,202206,202207,202208,202209,202210,202211,202212,202301,202302,202303,202304,202305,202306,202307,202308,202309,202310,202311,202312,202401,202402,202403,202404,202405,202406,202407,202408,202409,202410,202411,202412,202501,202502,202503,202504,202505,202506,202507,202508,202509","202510,202511,202512","202510,202511,202512",0.0,5442.0,384.0,120.0,257.0,ok,6.724662546474579,thr0.350_maxday4,research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_model_artifacts/202601/SPXW/fold_policy.json,a680d10fed84e93f58d8eb3221f3bb088f7ff5afb883a8902e998edf6b184da1,research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_model_artifacts/202601/SPXW/event_option_gate_direction_model.pkl,01c079121cca6b48839c32ed1fdb38e9c136854843d421d323a02f4ae6d76a8f,64.0,0.515625,1.829040321064559,13.841187728526084,0.21626855825822006,-3.775575118423925,0.265625,64.0,0.515625,0.03781890652887154,-3.775575118423925,18.20591756871429,1.3153435908677613,19.0,1.0,20,0.4,1.3487201159476905,2.31766195778906,0.11588309788945299,-4.766921782788755,0.25,20.0,0.4,-0.3958766620738881,-4.766921782788755,8.195652125939041,3.5361723474795723,20.0,1.0,True
SPXW,202602,target_zero_dte_d25_win,25.0,win,zero_dte,target,SPXW,"202201,202202,202203,202204,202205,202206,202207,202208,202209,202210,202211,202212,202301,202302,202303,202304,202305,202306,202307,202308,202309,202310,202311,202312,202401,202402,202403,202404,202405,202406,202407,202408,202409,202410,202411,202412,202501,202502,202503,202504,202505,202506,202507,202508,202509,202510","202511,202512,202601","202511,202512,202601",0.0,5580.0,366.0,114.0,257.0,ok,6.382013308411772,thr0.450_maxday4,research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_model_artifacts/202602/SPXW/fold_policy.json,96f79a09c8b9c75fa72358e00c8f8ba21afc6358fb40386afded690f56ae8a86,research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_model_artifacts/202602/SPXW/event_option_gate_direction_model.pkl,a8b2f4c1c8121179424a5997ede734c08667019c3e07ee109cc9ff7d0e3ede8e,57.0,0.5087719298245614,1.7509358257023897,11.179961992938537,0.196139684086641,-3.5495530337815353,0.49122807017543857,57.0,0.5087719298245614,0.04651158148692014,-3.5495530337815353,13.000963533422947,1.162880834624893,18.0,1.0,19,0.47368421052631576,0.8501964516108168,-0.9236698514364251,-0.04861420270718027,-2.8388337325056923,0.7894736842105263,19.0,0.47368421052631576,-0.3908045624218768,-2.8388337325056923,4.032347565486939,-4.365572351653701,19.0,0.0,True
SPXW,202603,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPXW,202604,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPXW,202605,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
QQQ,202601,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
QQQ,202602,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
QQQ,202603,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
QQQ,202604,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
QQQ,202605,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPY,202601,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPY,202602,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPY,202603,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPY,202604,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False
SPY,202605,ABSTAIN_NO_VALID_PROFILE,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,0,,,0.0,,,,,,,,,,,,False

```

## Candidate Validation Rows

15 validation-only candidate rows written to `candidate_validation.csv`.

## Config

```json
{
  "args": {
    "data": "tmp\\event_option_dataset_execquote_causal1000_noib_early_202201_202605_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1",
    "tickers": [
      "SPXW",
      "QQQ",
      "SPY"
    ],
    "train_universe": [
      "SPXW",
      "QQQ",
      "SPY"
    ],
    "profile_kind": "production_zero_dte",
    "profile_allowlist": [
      "target_zero_dte_d25_win"
    ],
    "start_month": "202601",
    "end_month": "202605",
    "val_months": 3,
    "clip_return": 2.0,
    "min_train_rows": 2500,
    "min_val_rows": 250,
    "min_val_trades": 54,
    "min_month_trades": 18,
    "min_val_pf": 1.3,
    "min_val_win_rate": 0.5,
    "min_val_positive_month_rate": 1.0,
    "min_call_rate": 0.0,
    "max_call_rate": 1.0,
    "daily_win_weight": 0.25,
    "top5_share_penalty": 0.1,
    "cooldown_minutes": 30,
    "ticker_cooldown_minutes": [
      "SPXW=0",
      "QQQ=30",
      "SPY=0"
    ],
    "objective": "regression_l1",
    "n_estimators": 240,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 80,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "lgb_jobs": 28,
    "lgb_device_type": "cpu",
    "lgb_gpu_use_dp": true,
    "profile_workers": 1,
    "live_observable_features_only": true,
    "entry_time_min_et": "10:00",
    "feature_exclude_prefixes": [],
    "return_threshold_grid": [
      -0.1,
      -0.05,
      0.0,
      0.05,
      0.1,
      0.15,
      0.2
    ],
    "return_threshold_quantiles": [
      0.4,
      0.5,
      0.6,
      0.7,
      0.8,
      0.9
    ],
    "win_threshold_grid": [
      0.35,
      0.4,
      0.45,
      0.5,
      0.55,
      0.6,
      0.65,
      0.7,
      0.75
    ],
    "win_threshold_quantiles": [
      0.4,
      0.5,
      0.6,
      0.7,
      0.8,
      0.9
    ],
    "max_day_grid": [
      999,
      12,
      8,
      6,
      4,
      2
    ],
    "ticker_max_day_grids": [
      "SPXW=4",
      "QQQ=2",
      "SPY=1"
    ],
    "allow_invalid_val_deploy": false,
    "risk_capital": 5000.0,
    "seed": 20260618,
    "no_resume": true,
    "ticker_cooldown_map": {
      "SPXW": 0,
      "QQQ": 30,
      "SPY": 0
    },
    "ticker_max_day_grid_map": {
      "SPXW": [
        4
      ],
      "QQQ": [
        2
      ],
      "SPY": [
        1
      ]
    }
  },
  "all_tickers": [
    "QQQ",
    "SPXW",
    "SPY"
  ],
  "profile_count": 1,
  "profiles": [
    {
      "name": "target_zero_dte_d25_win",
      "delta_bucket": 25,
      "label_mode": "win",
      "expiry_modes": [
        "zero_dte"
      ],
      "train_scope": "target"
    }
  ],
  "data_rows": 18684,
  "entry_start_minute_et": 600,
  "features_by_profile": {
    "target_zero_dte_d25_win": [
      "dte_days",
      "minute",
      "spot",
      "underlying_volume",
      "ret_1m_bps",
      "ret_5m_bps",
      "ret_15m_bps",
      "ret_30m_bps",
      "call_d15_available",
      "call_d15_strike",
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
      "put_d15_strike",
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
      "call_d25_strike",
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
      "put_d25_strike",
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
      "call_d35_strike",
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
      "put_d35_strike",
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
      "call_d50_strike",
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
      "put_d50_strike",
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
      "call_d65_strike",
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
      "put_d65_strike",
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
      "call_d80_strike",
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
      "put_d80_strike",
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
    ]
  },
  "policy_selection_provenance": {
    "schema_version": 1,
    "passed": false,
    "mode": "nested_walk_forward",
    "evaluation_months": [
      "202601",
      "202602",
      "202603",
      "202604",
      "202605"
    ],
    "selection_protocol_frozen_before_evaluation": true,
    "trade_artifact_kind": "nested_walk_forward_fold_outputs",
    "folds": [
      {
        "evaluation_month": "202601",
        "training_months": [
          "202201",
          "202202",
          "202203",
          "202204",
          "202205",
          "202206",
          "202207",
          "202208",
          "202209",
          "202210",
          "202211",
          "202212",
          "202301",
          "202302",
          "202303",
          "202304",
          "202305",
          "202306",
          "202307",
          "202308",
          "202309",
          "202310",
          "202311",
          "202312",
          "202401",
          "202402",
          "202403",
          "202404",
          "202405",
          "202406",
          "202407",
          "202408",
          "202409",
          "202410",
          "202411",
          "202412",
          "202501",
          "202502",
          "202503",
          "202504",
          "202505",
          "202506",
          "202507",
          "202508",
          "202509"
        ],
        "selection_months": [
          "202510",
          "202511",
          "202512"
        ],
        "policy_frozen_before_evaluation": true,
        "policy_artifact_path": "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_policy_artifacts/fold_policy_202601.json",
        "policy_artifact_sha256": "5fe4d8c46f918868f9bf08df43684ac5ce7dff4f875dfc499b31b6752ad426e0"
      },
      {
        "evaluation_month": "202602",
        "training_months": [
          "202201",
          "202202",
          "202203",
          "202204",
          "202205",
          "202206",
          "202207",
          "202208",
          "202209",
          "202210",
          "202211",
          "202212",
          "202301",
          "202302",
          "202303",
          "202304",
          "202305",
          "202306",
          "202307",
          "202308",
          "202309",
          "202310",
          "202311",
          "202312",
          "202401",
          "202402",
          "202403",
          "202404",
          "202405",
          "202406",
          "202407",
          "202408",
          "202409",
          "202410",
          "202411",
          "202412",
          "202501",
          "202502",
          "202503",
          "202504",
          "202505",
          "202506",
          "202507",
          "202508",
          "202509",
          "202510"
        ],
        "selection_months": [
          "202511",
          "202512",
          "202601"
        ],
        "policy_frozen_before_evaluation": true,
        "policy_artifact_path": "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_policy_artifacts/fold_policy_202602.json",
        "policy_artifact_sha256": "6ff6547f82dd7105a25a1a43b3284132515a8855c6ac5882e4ca9d9286b66e9e"
      },
      {
        "evaluation_month": "202603",
        "training_months": [],
        "selection_months": [],
        "policy_frozen_before_evaluation": false,
        "policy_artifact_path": "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_policy_artifacts/fold_policy_202603.json",
        "policy_artifact_sha256": "d5720f81b4dbc09e2a57df93e321e2a4d1c0044688ee03e32f616bc387685b41"
      },
      {
        "evaluation_month": "202604",
        "training_months": [],
        "selection_months": [],
        "policy_frozen_before_evaluation": false,
        "policy_artifact_path": "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_policy_artifacts/fold_policy_202604.json",
        "policy_artifact_sha256": "ccce8b13cda38d0f3abe229c4a4c655bee3c6cb4bc3d09df40fdad7e10dd4e4e"
      },
      {
        "evaluation_month": "202605",
        "training_months": [],
        "selection_months": [],
        "policy_frozen_before_evaluation": false,
        "policy_artifact_path": "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/fold_policy_artifacts/fold_policy_202605.json",
        "policy_artifact_sha256": "58011783cacd5f2b099eafaa8a160808ff7377870c3e2e2e59f19615022470db"
      }
    ]
  }
}
```