# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 459,
  "win_rate": 0.31808278867102396,
  "profit_factor": 0.7730516745488155,
  "pnl_return": -21.31044775986624,
  "avg_return": -0.04642799076223582,
  "max_drawdown": -24.410447759866372,
  "call_rate": 0.3638344226579521,
  "days_with_trades": 119,
  "daily_win_rate": 0.3445378151260504,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -25.81044775986622,
  "top5_day_return": 10.299999999999999,
  "top5_share_of_pnl": -0.4833309987694341,
  "min_month_trades": 28,
  "positive_month_rate": 0.3333333333333333
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 186,
    "win_rate": 0.3548387096774194,
    "profit_factor": 0.9052653400037158,
    "pnl_return": -3.4104477598662384,
    "avg_return": -0.01833574064444214,
    "max_drawdown": -8.110447759866227,
    "call_rate": 0.3870967741935484,
    "days_with_trades": 106,
    "daily_win_rate": 0.33962264150943394,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.61044775986623,
    "top5_day_return": 6.2,
    "top5_share_of_pnl": -1.8179431079287873,
    "min_month_trades": 9,
    "positive_month_rate": 0.3333333333333333
  },
  "SPXW": {
    "trades": 143,
    "win_rate": 0.3006993006993007,
    "profit_factor": 0.7166666666666668,
    "pnl_return": -8.5,
    "avg_return": -0.05944055944055944,
    "max_drawdown": -9.899999999999988,
    "call_rate": 0.44755244755244755,
    "days_with_trades": 99,
    "daily_win_rate": 0.35353535353535354,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -9.79999999999999,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": -0.5882352941176471,
    "min_month_trades": 7,
    "positive_month_rate": 0.3333333333333333
  },
  "SPY": {
    "trades": 130,
    "win_rate": 0.2846153846153846,
    "profit_factor": 0.6630824372759857,
    "pnl_return": -9.4,
    "avg_return": -0.07230769230769231,
    "max_drawdown": -11.300000000000015,
    "call_rate": 0.23846153846153847,
    "days_with_trades": 109,
    "daily_win_rate": 0.3211009174311927,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -11.299999999999999,
    "top5_day_return": 3.5,
    "top5_share_of_pnl": -0.3723404255319149,
    "min_month_trades": 12,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.550_maxday1,4362,4797,779,4.99011893983759,False,58,0.4482758620689655,1.3541666666666667,3.4000000000000012,0.058620689655172434,-2.099999999999999,0.2413793103448276,58,0.4482758620689655,-0.3,-2.099999999999999,2.5,0.7352941176470585,6,0.6666666666666666,7,0.42857142857142855,1.25,0.2999999999999999,0.04285714285714284,-0.9000000000000001,0.14285714285714285,7,0.42857142857142855,-0.3,-0.9000000000000001,0.8999999999999999,3.000000000000001,7,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.200_maxday1,5225,4713,616,2.6405124895243435,False,126,0.3412698412698413,0.8634538152610443,-3.3999999999999995,-0.02698412698412698,-6.9999999999999964,0.06349206349206349,126,0.3412698412698413,-0.3,-6.9999999999999964,2.5,-0.735294117647059,19,0.3333333333333333,19,0.05263157894736842,0.0925925925925926,-4.8999999999999995,-0.25789473684210523,-4.899999999999999,0.0,19,0.05263157894736842,-0.3,-4.899999999999999,-0.7,0.14285714285714288,19,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.500_maxday2,6003,4551,793,5.9414199459681,False,201,0.43781094527363185,1.297935103244838,10.100000000000001,0.05024875621890548,-3.100000000000019,0.7412935323383084,113,0.6371681415929203,0.2,-3.1000000000000068,5.0,0.495049504950495,29,0.6666666666666666,37,0.2972972972972973,0.7051282051282052,-2.2999999999999994,-0.062162162162162145,-3.299999999999999,0.8648648648648649,20,0.4,-0.3,-3.3,3.4000000000000004,-1.478260869565218,37,0.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.400_maxday1,6817,4530,793,5.839077850667832,False,125,0.464,1.4427860696517412,8.899999999999995,0.07119999999999996,-3.700000000000003,0.376,125,0.464,-0.3,-3.700000000000003,2.5,0.2808988764044945,19,0.8333333333333334,19,0.42105263157894735,1.2121212121212124,0.7000000000000002,0.036842105263157905,-1.8000000000000003,0.42105263157894735,19,0.42105263157894735,-0.3,-1.8000000000000003,2.5,3.5714285714285707,19,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.336_maxday2,7669,4471,783,6.313656686411146,False,244,0.430327868852459,1.2589928057553956,10.799999999999999,0.04426229508196721,-2.5999999999999988,0.4098360655737705,123,0.6666666666666666,0.2,-2.2,5.0,0.462962962962963,37,0.8333333333333334,40,0.325,0.8024691358024691,-1.5999999999999999,-0.039999999999999994,-2.2,0.425,20,0.5,-0.19999999999999998,-2.2,3.4000000000000004,-2.1250000000000004,40,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.502_maxday2,8317,4606,736,4.887962042007025,False,117,0.42735042735042733,1.243781094527363,4.899999999999998,0.04188034188034186,-4.199999999999997,0.41025641025641024,77,0.5584415584415584,0.2,-4.1999999999999975,5.0,1.0204081632653066,11,0.6666666666666666,21,0.3333333333333333,0.8333333333333335,-0.6999999999999997,-0.03333333333333332,-1.1,0.2857142857142857,14,0.35714285714285715,-0.3,-1.1,2.6000000000000005,-3.7142857142857166,21,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.550_maxday3,3973,4517,692,4.381853580690774,False,60,0.43333333333333335,1.2745098039215685,2.800000000000001,0.04666666666666668,-4.399999999999999,0.8333333333333334,41,0.5121951219512195,0.2,-4.3999999999999995,4.2,1.4999999999999996,7,0.6666666666666666,9,0.3333333333333333,0.8333333333333333,-0.29999999999999993,-0.033333333333333326,-0.8999999999999999,1.0,7,0.2857142857142857,-0.3,-0.6,0.2999999999999999,-0.9999999999999998,9,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.500_maxday1,4769,4413,550,3.113845822857676,False,126,0.3412698412698413,0.8634538152610443,-3.3999999999999986,-0.02698412698412697,-6.299999999999998,0.05555555555555555,126,0.3412698412698413,-0.3,-6.299999999999998,2.5,-0.7352941176470591,19,0.6666666666666666,19,0.21052631578947367,0.44444444444444453,-2.4999999999999996,-0.13157894736842102,-2.5,0.15789473684210525,19,0.21052631578947367,-0.3,-2.5,1.7,-0.68,19,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.420_maxday3,5523,4209,765,6.141005765664433,False,329,0.41033434650455924,1.170304541572134,9.822705242753672,0.02985624693846101,-3.877294757246326,0.42249240121580545,119,0.42857142857142855,-0.09999999999999998,-3.6772947572463264,7.5,0.7635371127045515,46,1.0,63,0.3492063492063492,0.8943089430894309,-1.3000000000000005,-0.02063492063492064,-6.199999999999999,0.5873015873015873,22,0.3181818181818182,-0.09999999999999998,-5.199999999999999,5.1000000000000005,-3.923076923076922,63,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.300_maxday1,6319,4178,637,5.906296180913161,False,125,0.448,1.3526570048309177,7.3,0.0584,-1.9999999999999982,0.424,125,0.448,-0.3,-1.9999999999999982,2.5,0.3424657534246575,19,0.8333333333333334,18,0.5,1.5146489778273198,1.3895522401337634,0.07719734667409797,-0.8104477598662367,0.5555555555555556,18,0.5,-0.1052238799331183,-0.8104477598662367,2.5,1.7991407071959675,18,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.328_maxday1,7122,4012,711,5.459829082579361,False,120,0.44166666666666665,1.2979876736384957,5.989552240133763,0.04991293533444803,-2.299999999999997,0.49166666666666664,120,0.44166666666666665,-0.3,-2.299999999999997,2.5,0.41739347112600994,18,0.6666666666666666,20,0.3,0.7142857142857144,-1.2,-0.06,-1.7,0.55,20,0.3,-0.3,-1.7,2.5,-2.0833333333333335,20,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.300_maxday3,7746,4099,619,4.457172523888689,False,359,0.3816155988857939,1.0223656492512583,1.4895522401337626,0.004149170585330815,-5.599999999999994,0.3593314763231198,121,0.3305785123966942,-0.09999999999999998,-5.399999999999999,7.5,5.035070135792281,54,0.6666666666666666,57,0.38596491228070173,1.0476190476190474,0.5000000000000002,0.008771929824561408,-2.8,0.03508771929824561,20,0.4,-0.09999999999999998,-2.8,4.6000000000000005,9.199999999999998,57,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.509_maxday2,4331,4822,779,6.1394357750453965,False,99,0.494949494949495,1.633756388965735,9.352091888670621,0.09446557463303658,-2.2000000000000064,0.42424242424242425,72,0.5972222222222222,0.2,-2.1000000000000014,5.0,0.5346397425860556,11,0.6666666666666666,12,0.08333333333333333,0.15151515151515155,-2.7999999999999994,-0.23333333333333328,-2.8,0.25,10,0.1,-0.3,-2.8000000000000003,-0.7,0.25000000000000006,12,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.450_maxday1,5201,4731,615,2.6231063552138436,False,126,0.3253968253968254,0.803921568627451,-4.999999999999999,-0.03968253968253967,-5.799999999999997,0.05555555555555555,126,0.3253968253968254,-0.3,-5.799999999999997,2.5,-0.5000000000000001,19,0.3333333333333333,19,0.05263157894736842,0.0925925925925926,-4.8999999999999995,-0.25789473684210523,-4.899999999999999,0.0,19,0.05263157894736842,-0.3,-4.899999999999999,-0.7,0.14285714285714288,19,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.372_maxday1,5987,4560,799,4.950386487078269,False,123,0.4065040650406504,1.1415525114155252,3.100000000000001,0.025203252032520333,-2.4000000000000004,0.4878048780487805,123,0.4065040650406504,-0.3,-2.4000000000000004,2.5,0.8064516129032255,19,0.6666666666666666,22,0.4090909090909091,1.1538461538461542,0.6000000000000002,0.027272727272727282,-1.4000000000000004,0.3181818181818182,22,0.4090909090909091,-0.3,-1.4000000000000004,2.5,4.166666666666665,22,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.340_maxday1,6807,4539,689,4.594636730285496,False,125,0.4,1.1111111111111112,2.5,0.02,-3.6999999999999975,0.528,125,0.4,-0.3,-3.6999999999999975,2.5,1.0,19,0.6666666666666666,18,0.2777777777777778,0.6410256410256412,-1.4,-0.07777777777777778,-3.4000000000000004,0.3333333333333333,18,0.2777777777777778,-0.3,-3.4000000000000004,2.5,-1.7857142857142858,18,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.351_maxday2,7659,4376,775,5.2409062595976215,False,237,0.4050632911392405,1.1347517730496455,5.699999999999999,0.0240506329113924,-4.499999999999995,0.2911392405063291,119,0.6470588235294118,0.2,-4.199999999999997,5.0,0.8771929824561404,34,0.8333333333333334,39,0.3076923076923077,0.7407407407407408,-2.1,-0.05384615384615385,-2.8,0.23076923076923078,20,0.5,-0.19999999999999998,-2.8,2.9000000000000004,-1.3809523809523812,39,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.431_maxday1,8306,4504,724,6.239255786470855,False,118,0.4745762711864407,1.505376344086021,9.399999999999999,0.07966101694915254,-2.1999999999999984,0.2796610169491525,118,0.4745762711864407,-0.3,-2.1999999999999984,2.5,0.2659574468085107,18,0.8333333333333334,20,0.45,1.363636363636364,1.2,0.06,-1.3,0.3,20,0.45,-0.3,-1.3,2.5,2.0833333333333335,20,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d15_win_wf2026_v1",
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
    "delta_bucket": 15,
    "label_mode": "win",
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
  "data_rows": 39657
}
```