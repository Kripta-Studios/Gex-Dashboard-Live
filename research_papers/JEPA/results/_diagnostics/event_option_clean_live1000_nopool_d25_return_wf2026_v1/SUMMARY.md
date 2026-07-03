# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 397,
  "win_rate": 0.3677581863979849,
  "profit_factor": 0.9694555112881809,
  "pnl_return": -2.299999999999999,
  "avg_return": -0.005793450881612088,
  "max_drawdown": -7.799999999999979,
  "call_rate": 0.3778337531486146,
  "days_with_trades": 121,
  "daily_win_rate": 0.4380165289256198,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -11.099999999999994,
  "top5_day_return": 8.5,
  "top5_share_of_pnl": -3.6956521739130452,
  "min_month_trades": 43,
  "positive_month_rate": 0.5
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 122,
    "win_rate": 0.36885245901639346,
    "profit_factor": 0.974025974025974,
    "pnl_return": -0.6000000000000003,
    "avg_return": -0.004918032786885248,
    "max_drawdown": -4.6,
    "call_rate": 0.319672131147541,
    "days_with_trades": 78,
    "daily_win_rate": 0.47435897435897434,
    "median_daily_return": -0.09999999999999998,
    "daily_max_drawdown": -4.5,
    "top5_day_return": 4.5,
    "top5_share_of_pnl": -7.4999999999999964,
    "min_month_trades": 10,
    "positive_month_rate": 0.5
  },
  "SPXW": {
    "trades": 139,
    "win_rate": 0.3597122302158273,
    "profit_factor": 0.9363295880149815,
    "pnl_return": -1.7000000000000002,
    "avg_return": -0.012230215827338131,
    "max_drawdown": -7.299999999999996,
    "call_rate": 0.49640287769784175,
    "days_with_trades": 99,
    "daily_win_rate": 0.46464646464646464,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.099999999999998,
    "top5_day_return": 4.5,
    "top5_share_of_pnl": -2.6470588235294117,
    "min_month_trades": 9,
    "positive_month_rate": 0.5
  },
  "SPY": {
    "trades": 136,
    "win_rate": 0.375,
    "profit_factor": 1.0,
    "pnl_return": 2.220446049250313e-16,
    "avg_return": 1.6326809185664067e-18,
    "max_drawdown": -5.399999999999999,
    "call_rate": 0.3088235294117647,
    "days_with_trades": 117,
    "daily_win_rate": 0.4017094017094017,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.399999999999999,
    "top5_day_return": 4.5,
    "top5_share_of_pnl": 2.026619832316723e+16,
    "min_month_trades": 17,
    "positive_month_rate": 0.5
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.244_maxday1,4362,4797,779,5.184980753996555,False,60,0.45,1.387479978185145,3.7701298669128884,0.06283549778188148,-2.429870133087112,0.6333333333333333,60,0.45,-0.3,-2.429870133087112,2.5,0.6631071311204156,4,0.8333333333333334,9,0.3333333333333333,0.8333333333333333,-0.29999999999999993,-0.033333333333333326,-1.8,0.7777777777777778,9,0.3333333333333333,-0.3,-1.8,0.8999999999999999,-3.0000000000000004,9,0.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.500_maxday1,5225,4713,616,4.195996987149387,False,60,0.38333333333333336,1.056189389360837,0.6118012395870321,0.010196687326450536,-1.8881987604129682,0.05,60,0.38333333333333336,-0.3,-1.8881987604129682,2.5,4.086294433936597,6,0.5,10,0.3,0.7142857142857143,-0.5999999999999999,-0.059999999999999984,-0.9999999999999999,0.1,10,0.3,-0.3,-0.9999999999999999,0.8999999999999999,-1.5000000000000002,10,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.009_maxday2,6003,4551,793,6.459929583160653,False,240,0.43333333333333335,1.268302777626907,10.946753327177799,0.04561147219657416,-2.799999999999998,0.6958333333333333,122,0.6885245901639344,0.2,-2.799999999999998,5.0,0.45675643275768035,37,1.0,43,0.23255813953488372,0.5050505050505051,-4.8999999999999995,-0.11395348837209301,-5.399999999999998,0.7906976744186046,22,0.4090909090909091,-0.6,-5.1,1.7999999999999998,-0.3673469387755102,43,0.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.051_maxday1,6817,4530,793,6.061369832482417,False,119,0.46218487394957986,1.443239058209008,8.44563763114462,0.07097174479953462,-2.254362368855376,0.5042016806722689,119,0.46218487394957986,-0.3,-2.254362368855376,2.5,0.29601080571831023,18,0.8333333333333334,18,0.3888888888888889,1.0606060606060608,0.20000000000000012,0.011111111111111118,-1.2000000000000002,0.3888888888888889,18,0.3888888888888889,-0.3,-1.2000000000000002,2.5,12.499999999999993,18,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.029_maxday1,7669,4471,783,6.500679989628086,False,117,0.49572649572649574,1.638418079096045,11.299999999999997,0.09658119658119656,-2.6000000000000005,0.42735042735042733,117,0.49572649572649574,-0.3,-2.6000000000000005,2.5,0.2212389380530974,18,0.8333333333333334,20,0.45,1.363636363636364,1.2,0.06,-1.5999999999999994,0.35,20,0.45,-0.3,-1.5999999999999994,2.5,2.0833333333333335,20,1.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.229_maxday2,8317,4606,736,6.385052180481424,False,246,0.44308943089430897,1.326034063260341,13.399999999999999,0.05447154471544715,-3.9999999999999964,0.35772357723577236,124,0.6774193548387096,0.2,-3.3999999999999977,5.0,0.373134328358209,36,0.8333333333333334,39,0.46153846153846156,1.4285714285714288,2.700000000000001,0.06923076923076926,-1.9999999999999982,0.3333333333333333,20,0.75,0.2,-1.6999999999999997,3.4000000000000004,1.2592592592592589,39,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.089_maxday3,3974,4521,692,5.9787016621711615,False,117,0.4444444444444444,1.3333333333333333,6.500000000000001,0.055555555555555566,-1.7999999999999994,0.29914529914529914,61,0.4918032786885246,-0.09999999999999998,-1.7999999999999994,6.0,0.9230769230769229,16,1.0,14,0.2857142857142857,0.6666666666666667,-1.0,-0.07142857142857142,-1.9,0.5714285714285714,8,0.125,-0.19999999999999998,-1.4,-0.09999999999999992,0.09999999999999992,14,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.383_maxday1,4771,4416,550,3.791531656473033,False,118,0.3728813559322034,0.9903822723355971,-0.2135135541497437,-0.0018094368995740992,-4.5135135541497435,0.1694915254237288,118,0.3728813559322034,-0.3,-4.5135135541497435,2.5,-11.708858531045163,16,0.5,15,0.4,1.1111111111111112,0.2999999999999999,0.019999999999999993,-0.9000000000000001,0.26666666666666666,15,0.4,-0.3,-0.9000000000000001,2.5,8.333333333333337,15,1.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.300_maxday1,5526,4211,765,5.625615126547652,False,60,0.48333333333333334,1.6070529005639722,5.477272748823994,0.09128787914706657,-2.4000000000000004,0.31666666666666665,60,0.48333333333333334,-0.16136362558800318,-2.4000000000000004,2.5,0.45643153347380155,6,0.8333333333333334,11,0.2727272727272727,0.625,-0.8999999999999999,-0.0818181818181818,-1.0999999999999999,0.8181818181818182,11,0.2727272727272727,-0.3,-1.0999999999999999,0.8999999999999999,-1.0,11,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.065_maxday2,6323,4179,637,5.667459809806898,False,241,0.4149377593360996,1.182033096926714,7.699999999999999,0.031950207468879666,-2.9000000000000004,0.44398340248962653,123,0.6422764227642277,0.2,-2.6,5.0,0.6493506493506495,37,0.6666666666666666,36,0.3888888888888889,1.0606060606060608,0.4000000000000002,0.011111111111111117,-2.6,0.3333333333333333,18,0.6111111111111112,0.2,-2.6,3.4000000000000004,8.499999999999996,36,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.242_maxday3,7126,4013,712,4.960089069742586,False,71,0.4647887323943662,1.413905130850922,4.718518491700517,0.0664580069253594,-2.9,0.5352112676056338,36,0.4722222222222222,-0.09999999999999998,-2.5000000000000004,5.318518491700517,1.127158556452698,7,0.5,10,0.3,0.7142857142857143,-0.5999999999999999,-0.059999999999999984,-0.9999999999999999,0.2,6,0.3333333333333333,-0.19999999999999998,-0.7999999999999998,-0.29999999999999993,0.5,10,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.008_maxday2,7751,4100,619,4.843273789868138,False,178,0.39325842696629215,1.0684727929537199,2.218518491700517,0.012463587032025377,-2.8000000000000003,0.25842696629213485,106,0.5660377358490566,0.2,-2.2,5.0,2.253756287678021,25,0.6666666666666666,36,0.4166666666666667,1.1904761904761907,1.2000000000000002,0.03333333333333334,-1.6,0.1111111111111111,20,0.7,0.2,-1.5,2.7,2.25,36,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,4331,4822,779,4.661830548663509,False,128,0.4140625,1.1777777777777778,4.0,0.03125,-3.8000000000000007,0.7421875,128,0.4140625,-0.3,-3.8000000000000007,2.5,0.625,19,0.5,20,0.3,0.7142857142857144,-1.2,-0.06,-2.8,0.5,20,0.3,-0.3,-2.8,2.5,-2.0833333333333335,20,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday1,5201,4731,615,3.960679499517411,False,126,0.3968253968253968,1.0964912280701753,2.1999999999999997,0.017460317460317457,-5.799999999999999,0.1111111111111111,126,0.3968253968253968,-0.3,-5.799999999999999,2.5,1.1363636363636365,19,0.5,19,0.15789473684210525,0.3125,-3.2999999999999994,-0.17368421052631575,-3.299999999999999,0.3157894736842105,19,0.15789473684210525,-0.3,-3.299999999999999,0.8999999999999999,-0.27272727272727276,19,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr-0.123_maxday1,5987,4560,799,4.1634425160089865,False,124,0.3870967741935484,1.0526315789473684,1.2000000000000013,0.00967741935483872,-3.099999999999999,0.6451612903225806,124,0.3870967741935484,-0.3,-3.099999999999999,2.5,2.0833333333333313,19,0.3333333333333333,22,0.5909090909090909,2.4074074074074074,3.8000000000000003,0.17272727272727273,-1.299999999999999,0.6363636363636364,22,0.5909090909090909,0.5,-1.299999999999999,2.5,0.6578947368421052,22,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-0.114_maxday1,6807,4539,689,5.459629514246495,False,125,0.448,1.3526570048309177,7.300000000000003,0.05840000000000003,-3.399999999999997,0.536,125,0.448,-0.3,-3.399999999999997,2.5,0.34246575342465735,19,0.6666666666666666,18,0.3888888888888889,1.0606060606060608,0.20000000000000012,0.011111111111111118,-1.5000000000000002,0.3888888888888889,18,0.3888888888888889,-0.3,-1.5000000000000002,2.5,12.499999999999993,18,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.115_maxday1,7659,4376,775,5.075708848925813,False,78,0.4230769230769231,1.2499999999999998,3.3000000000000016,0.04230769230769233,-1.5999999999999996,0.2692307692307692,78,0.4230769230769231,-0.3,-1.5999999999999996,2.5,0.7575757575757572,8,0.6666666666666666,17,0.35294117647058826,0.9090909090909093,-0.29999999999999993,-0.017647058823529408,-1.6,0.0,17,0.35294117647058826,-0.3,-1.6,2.5,-8.333333333333336,17,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.014_maxday2,8306,4504,724,5.227633170058157,False,200,0.41,1.158192090395481,5.6,0.027999999999999997,-4.299999999999996,0.285,109,0.6238532110091743,0.2,-3.999999999999998,5.0,0.8928571428571429,30,0.8333333333333334,40,0.4,1.1111111111111112,0.8000000000000003,0.020000000000000007,-2.3000000000000003,0.125,21,0.5714285714285714,0.2,-2.0000000000000004,4.5,5.624999999999998,40,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d25_return_wf2026_v1",
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
    "delta_bucket": 25,
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
  "data_rows": 39663
}
```