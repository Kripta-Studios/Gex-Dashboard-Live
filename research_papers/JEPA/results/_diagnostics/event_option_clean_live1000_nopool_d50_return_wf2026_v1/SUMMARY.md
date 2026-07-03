# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 578,
  "win_rate": 0.3685121107266436,
  "profit_factor": 0.9722617275848688,
  "pnl_return": -3.027967464173805,
  "avg_return": -0.005238698034902777,
  "max_drawdown": -8.299999999999994,
  "call_rate": 0.3494809688581315,
  "days_with_trades": 120,
  "daily_win_rate": 0.475,
  "median_daily_return": -0.14999999999999997,
  "daily_max_drawdown": -11.313402099695866,
  "top5_day_return": 11.600000000000001,
  "top5_share_of_pnl": -3.830952656278001,
  "min_month_trades": 78,
  "positive_month_rate": 0.5
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 162,
    "win_rate": 0.4074074074074074,
    "profit_factor": 1.1331288470723409,
    "pnl_return": 3.834110795683415,
    "avg_return": 0.023667350590638365,
    "max_drawdown": -3.4999999999999996,
    "call_rate": 0.3765432098765432,
    "days_with_trades": 103,
    "daily_win_rate": 0.4854368932038835,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.4999999999999996,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 1.3040833367750317,
    "min_month_trades": 3,
    "positive_month_rate": 0.5
  },
  "SPXW": {
    "trades": 209,
    "win_rate": 0.3588516746411483,
    "profit_factor": 0.9407437252905118,
    "pnl_return": -2.3620782598572188,
    "avg_return": -0.011301809855776166,
    "max_drawdown": -5.099999999999996,
    "call_rate": 0.4258373205741627,
    "days_with_trades": 107,
    "daily_win_rate": 0.42990654205607476,
    "median_daily_return": -0.09999999999999998,
    "daily_max_drawdown": -4.9,
    "top5_day_return": 4.286597900304134,
    "top5_share_of_pnl": -1.814756933821171,
    "min_month_trades": 13,
    "positive_month_rate": 0.3333333333333333
  },
  "SPY": {
    "trades": 207,
    "win_rate": 0.34782608695652173,
    "profit_factor": 0.8888888888888888,
    "pnl_return": -4.5,
    "avg_return": -0.021739130434782608,
    "max_drawdown": -8.299999999999986,
    "call_rate": 0.25120772946859904,
    "days_with_trades": 119,
    "daily_win_rate": 0.35294117647058826,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.899999999999995,
    "top5_day_return": 6.5,
    "top5_share_of_pnl": -1.4444444444444444,
    "min_month_trades": 19,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday3,4362,4797,779,5.270132468223313,False,381,0.4041994750656168,1.1255439665568923,8.491277799163678,0.02228681837050834,-5.082589236031062,0.6456692913385826,128,0.3828125,-0.09999999999999998,-4.682589236031072,7.5,0.8832592899903345,55,0.5,60,0.38333333333333336,1.0537502325072836,0.5865979003041333,0.009776631671735555,-2.2,0.75,20,0.35,-0.09999999999999998,-1.4,3.6865979003041343,6.284710358480221,60,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday3,5225,4713,616,4.8488658690968505,False,375,0.39466666666666667,1.0776613538007145,5.258231724954288,0.014021951266544768,-6.028339103317698,0.05333333333333334,126,0.373015873015873,-0.09999999999999998,-5.728339103317706,7.5,1.4263350100009524,55,0.6666666666666666,56,0.26785714285714285,0.6097560975609756,-4.8,-0.08571428571428572,-4.999999999999996,0.0,19,0.21052631578947367,-0.09999999999999998,-4.800000000000001,2.6999999999999997,-0.5625,56,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr-0.092_maxday1,6003,4551,793,5.427778898506111,False,124,0.4274193548387097,1.247757847533632,5.261904761904763,0.0424347158218126,-1.838095238095237,0.4838709677419355,124,0.4274193548387097,-0.3,-1.838095238095237,2.5,0.4751131221719456,19,0.6666666666666666,22,0.5454545454545454,2.0000000000000004,3.000000000000001,0.1363636363636364,-1.299999999999999,0.4090909090909091,22,0.5454545454545454,0.5,-1.299999999999999,2.5,0.833333333333333,22,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.400_maxday2,6817,4530,793,5.941769837036761,False,88,0.48863636363636365,1.580179965230696,7.716393525919782,0.08768629006727024,-1.799999999999999,0.38636363636363635,58,0.603448275862069,0.2,-1.7999999999999998,5.0,0.6479710998674096,9,0.6666666666666666,13,0.3076923076923077,0.7407407407407408,-0.7,-0.05384615384615384,-1.2,0.0,7,0.5714285714285714,0.2,-0.9,0.5,-0.7142857142857143,13,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.100_maxday1,7669,4471,783,7.070858677833795,False,120,0.525,1.8297434998075128,14.188613846708474,0.11823844872257062,-2.2999999999999963,0.5083333333333333,120,0.525,0.5,-2.2999999999999963,2.5,0.1761976206421291,18,0.8333333333333334,20,0.35,0.8974358974358977,-0.39999999999999986,-0.019999999999999993,-1.5,0.4,20,0.35,-0.3,-1.5,2.5,-6.250000000000003,20,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.101_maxday2,8317,4606,736,6.4734440142302505,False,245,0.4448979591836735,1.3185874995462257,12.99836998148601,0.05305457135300412,-3.3000000000000016,0.5387755102040817,124,0.6935483870967742,0.2,-2.9999999999999982,5.0,0.384663616062757,37,0.8333333333333334,38,0.3684210526315789,0.9930942833724629,-0.04867616016135129,-0.001280951583193455,-2.4486761601613516,0.7105263157894737,19,0.631578947368421,0.2,-2.4486761601613516,2.7513238398386486,-56.523025454731545,38,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,3974,4524,692,6.164559561241833,False,128,0.4609375,1.4251207729468598,8.799999999999999,0.06874999999999999,-2.799999999999997,0.203125,128,0.4609375,-0.3,-2.799999999999997,2.5,0.2840909090909091,19,1.0,20,0.25,0.5555555555555557,-2.0,-0.1,-2.9,0.15,20,0.25,-0.3,-2.9,2.5,-1.25,20,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.500_maxday1,4771,4419,550,4.552710150148664,False,37,0.43243243243243246,1.26984126984127,1.7,0.04594594594594594,-1.9000000000000001,0.05405405405405406,37,0.43243243243243246,-0.3,-1.9000000000000001,2.5,1.4705882352941178,4,0.6666666666666666,3,0.3333333333333333,0.8333333333333334,-0.09999999999999998,-0.033333333333333326,-0.6,0.0,3,0.3333333333333333,-0.3,-0.6,-0.09999999999999998,1.0,3,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.040_maxday2,5526,4214,765,5.431929668820306,False,235,0.4127659574468085,1.1673630058630229,6.860050181290097,0.029191702899106796,-3.499999999999998,0.4297872340425532,121,0.5785123966942148,0.2,-3.1999999999999997,5.0,0.728857642125834,36,0.6666666666666666,43,0.46511627906976744,1.4492753623188408,3.1,0.07209302325581396,-2.1999999999999975,0.6511627906976745,22,0.6363636363636364,0.2,-1.8999999999999986,5.0,1.6129032258064515,43,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-0.084_maxday2,6323,4182,637,6.915524663238631,False,249,0.4578313253012048,1.403630889879888,16.265925221640376,0.065325000890122,-3.300000000000007,0.43373493975903615,125,0.688,0.2,-3.1999999999999993,5.0,0.30739106026062024,37,0.8333333333333334,36,0.5277777777777778,1.7910021168006696,4.034110795683414,0.11205863321342818,-1.5999999999999979,0.4722222222222222,18,0.7222222222222222,0.2,-1.5999999999999996,5.0,1.2394305097792822,36,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.013_maxday2,7126,4016,712,7.099028729242932,False,218,0.46788990825688076,1.4594830486242794,15.940928957489705,0.07312352732793442,-3.1000000000000085,0.5275229357798165,114,0.6491228070175439,0.2,-2.799999999999999,5.0,0.313658006590061,29,1.0,40,0.325,0.8024691358024691,-1.6,-0.04,-2.1,0.275,20,0.45,-0.6,-2.0,4.2,-2.625,40,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.051_maxday1,7752,4102,619,4.540723318513907,False,121,0.4132231404958678,1.1565310232715216,3.334110795683415,0.027554634675069547,-3.799999999999998,0.3305785123966942,121,0.4132231404958678,-0.3,-3.799999999999998,2.5,0.7498251117619378,18,0.5,20,0.4,1.1111111111111114,0.39999999999999997,0.019999999999999997,-1.2,0.1,20,0.4,-0.3,-1.2,2.5,6.250000000000001,20,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,4331,4827,779,4.356197195695961,False,128,0.3828125,1.0372039486074531,0.8788018423053452,0.006865639393010509,-3.6000000000000014,0.65625,128,0.3828125,-0.3,-3.6000000000000014,2.5,2.8447823839806645,19,0.6666666666666666,20,0.4,1.1111111111111114,0.39999999999999997,0.019999999999999997,-1.6,0.7,20,0.4,-0.3,-1.6,2.5,6.250000000000001,20,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday1,5201,4736,615,3.7088779979650943,False,126,0.36507936507936506,0.961490300292574,-0.9211981576946582,-0.007311096489640144,-4.499999999999999,0.05555555555555555,126,0.36507936507936506,-0.3,-4.499999999999999,2.5,-2.7138569254810148,19,0.5,19,0.15789473684210525,0.3125,-3.2999999999999994,-0.17368421052631575,-3.499999999999999,0.0,19,0.15789473684210525,-0.3,-3.499999999999999,0.8999999999999999,-0.27272727272727276,19,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr-999.000_maxday2,5987,4565,799,3.835364898368593,False,247,0.3684210526315789,0.9698012951703092,-1.3995531334530256,-0.005666207018028444,-4.364270370971284,0.4777327935222672,124,0.5967741935483871,0.2,-4.364270370971283,5.0,-3.5725689010918993,37,0.3333333333333333,44,0.36363636363636365,0.9523809523809523,-0.3999999999999997,-0.009090909090909084,-3.6000000000000005,0.3409090909090909,22,0.5454545454545454,0.2,-3.6,4.2,-10.500000000000009,44,0.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.130_maxday3,6807,4544,689,5.497575672304395,False,280,0.425,1.221066244143848,10.596872922275171,0.03784597472241132,-5.800000000000009,0.18214285714285713,112,0.4107142857142857,-0.09999999999999998,-5.000000000000002,7.5,0.7077559630100513,42,0.6666666666666666,45,0.35555555555555557,0.9195402298850573,-0.7,-0.015555555555555555,-3.3000000000000003,0.044444444444444446,17,0.4117647058823529,-0.09999999999999998,-3.0,3.5,-5.0,45,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-999.000_maxday1,7659,4381,775,4.907511868565938,False,120,0.425,1.236591579451209,4.878801842305343,0.040656682019211195,-4.099999999999995,0.23333333333333334,120,0.425,-0.3,-4.099999999999995,2.5,0.5124208936550483,18,0.6666666666666666,20,0.25,0.5555555555555557,-1.9999999999999998,-0.09999999999999999,-2.7,0.1,20,0.25,-0.3,-2.7,2.5,-1.2500000000000002,20,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.072_maxday3,8308,4507,724,6.644264023240671,False,357,0.42016806722689076,1.2103460009933877,12.985769849284026,0.036374705460179346,-3.4000000000000234,0.34173669467787116,121,0.4049586776859504,-0.09999999999999998,-3.100000000000003,7.5,0.5775552845188855,52,1.0,59,0.4067796610169492,1.1428571428571426,1.4999999999999998,0.025423728813559317,-3.4999999999999973,0.3220338983050847,21,0.3333333333333333,-0.09999999999999998,-2.6,5.9,3.933333333333334,59,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d50_return_wf2026_v1",
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
    "delta_bucket": 50,
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
  "data_rows": 39671
}
```