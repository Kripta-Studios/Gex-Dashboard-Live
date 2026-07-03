# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 316,
  "win_rate": 0.3860759493670886,
  "profit_factor": 1.048109965635739,
  "pnl_return": 2.799999999999999,
  "avg_return": 0.008860759493670883,
  "max_drawdown": -8.599999999999998,
  "call_rate": 0.40822784810126583,
  "days_with_trades": 120,
  "daily_win_rate": 0.44166666666666665,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -6.699999999999999,
  "top5_day_return": 6.7,
  "top5_share_of_pnl": 2.3928571428571437,
  "min_month_trades": 18,
  "positive_month_rate": 0.8333333333333334
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 98,
    "win_rate": 0.30612244897959184,
    "profit_factor": 0.7352941176470588,
    "pnl_return": -5.4,
    "avg_return": -0.05510204081632653,
    "max_drawdown": -8.599999999999996,
    "call_rate": 0.35714285714285715,
    "days_with_trades": 90,
    "daily_win_rate": 0.3333333333333333,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -8.599999999999998,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.4629629629629629,
    "min_month_trades": 9,
    "positive_month_rate": 0.5
  },
  "SPXW": {
    "trades": 88,
    "win_rate": 0.375,
    "profit_factor": 0.9999999999999998,
    "pnl_return": -4.440892098500626e-16,
    "avg_return": -5.046468293750712e-18,
    "max_drawdown": -1.9000000000000001,
    "call_rate": 0.4090909090909091,
    "days_with_trades": 71,
    "daily_win_rate": 0.4507042253521127,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -1.8999999999999995,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": -6755399441055744.0,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  },
  "SPY": {
    "trades": 130,
    "win_rate": 0.45384615384615384,
    "profit_factor": 1.384976525821596,
    "pnl_return": 8.2,
    "avg_return": 0.06307692307692307,
    "max_drawdown": -2.1999999999999975,
    "call_rate": 0.4461538461538462,
    "days_with_trades": 92,
    "daily_win_rate": 0.5543478260869565,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -2.1999999999999975,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 0.6097560975609757,
    "min_month_trades": 0,
    "positive_month_rate": 0.8333333333333334
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.200_maxday1,4362,4797,779,4.603011087763099,False,41,0.43902439024390244,1.3043478260869568,2.1,0.051219512195121955,-2.3000000000000003,0.36585365853658536,41,0.43902439024390244,-0.3,-2.3000000000000003,2.5,1.1904761904761905,4,0.6666666666666666,9,0.3333333333333333,0.8333333333333333,-0.29999999999999993,-0.033333333333333326,-1.2999999999999998,0.6666666666666666,9,0.3333333333333333,-0.3,-1.2999999999999998,0.8999999999999999,-3.0000000000000004,9,0.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,5225,4713,616,-9.999999999999996e+17,True,375,0.33066666666666666,0.8222553593392101,-13.347006654778408,-0.03559201774607575,-15.447006654778528,0.034666666666666665,126,0.30952380952380953,-0.09999999999999998,-15.447006654778422,7.5,-0.5619237476977581,55,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.200_maxday1,6003,4551,793,5.89551615016066,False,56,0.5357142857142857,1.8790849724910628,6.8568627854302875,0.12244397831125513,-2.243137214569713,0.8928571428571429,56,0.5357142857142857,0.5,-2.243137214569713,2.5,0.36459822490718224,9,0.6666666666666666,6,0.3333333333333333,0.8333333333333334,-0.19999999999999996,-0.033333333333333326,-0.6,1.0,6,0.3333333333333333,-0.3,-0.6,0.09999999999999998,-0.5,6,0.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-0.016_maxday2,6817,4530,793,5.619684795582919,False,239,0.41841004184100417,1.1928993392013822,8.043902444697647,0.033656495584508984,-4.199999999999997,0.24686192468619247,123,0.5934959349593496,0.2,-4.199999999999997,5.0,0.6215888412838576,37,0.8333333333333334,35,0.4,1.1111111111111114,0.7000000000000002,0.020000000000000004,-1.9,0.22857142857142856,18,0.7222222222222222,0.2,-1.5999999999999999,2.1,2.9999999999999996,35,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.023_maxday1,7669,4471,783,6.251883098743185,False,109,0.47706422018348627,1.5204678362573099,8.899999999999997,0.08165137614678897,-1.799999999999999,0.3761467889908257,109,0.47706422018348627,-0.3,-1.799999999999999,2.5,0.28089887640449446,15,0.8333333333333334,17,0.35294117647058826,0.9090909090909093,-0.29999999999999993,-0.017647058823529408,-1.7,0.17647058823529413,17,0.35294117647058826,-0.3,-1.7,2.5,-8.333333333333336,17,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.207_maxday1,8317,4606,736,5.089826188094468,False,124,0.41935483870967744,1.2037037037037037,4.3999999999999995,0.03548387096774193,-2.7999999999999994,0.33064516129032256,124,0.41935483870967744,-0.3,-2.7999999999999994,2.5,0.5681818181818182,19,0.6666666666666666,21,0.38095238095238093,1.025641025641026,0.10000000000000014,0.004761904761904768,-0.8999999999999999,0.6190476190476191,21,0.38095238095238093,-0.3,-0.8999999999999999,2.5,24.999999999999964,21,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-0.174_maxday1,3973,4517,692,4.267206956039544,False,128,0.390625,1.0683760683760684,1.5999999999999996,0.012499999999999997,-3.8000000000000007,0.375,128,0.390625,-0.3,-3.8000000000000007,2.5,1.5625000000000004,19,0.5,20,0.4,1.1111111111111114,0.39999999999999997,0.019999999999999997,-1.5,0.45,20,0.4,-0.3,-1.5,2.5,6.250000000000001,20,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.300_maxday1,4769,4413,550,3.3602228897744832,False,116,0.3620689655172414,0.9459459459459459,-1.2,-0.010344827586206896,-5.799999999999998,0.2413793103448276,116,0.3620689655172414,-0.3,-5.799999999999998,2.5,-2.0833333333333335,16,0.5,18,0.3888888888888889,1.0606060606060608,0.20000000000000012,0.011111111111111118,-1.3,0.4444444444444444,18,0.3888888888888889,-0.3,-1.3,2.5,12.499999999999993,18,1.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.159_maxday1,5523,4209,765,4.58076038930585,False,41,0.4146341463414634,1.200564970538544,1.419999992847442,0.034634146167010785,-1.3800000071525573,0.1951219512195122,41,0.4146341463414634,-0.3,-1.3800000071525573,2.5,1.7605633891496701,4,0.6666666666666666,9,0.3333333333333333,0.8333333333333333,-0.29999999999999993,-0.033333333333333326,-1.3,0.8888888888888888,9,0.3333333333333333,-0.3,-1.3,0.8999999999999999,-3.0000000000000004,9,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.045_maxday1,6319,4178,637,5.508522559039793,False,104,0.4326923076923077,1.2711864406779658,4.799999999999999,0.04615384615384614,-1.799999999999998,0.4326923076923077,104,0.4326923076923077,-0.3,-1.799999999999998,2.5,0.5208333333333335,15,0.8333333333333334,12,0.25,0.5555555555555556,-1.2,-0.09999999999999999,-2.2,0.5833333333333334,12,0.25,-0.3,-2.2,0.8999999999999999,-0.75,12,0.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.087_maxday2,7122,4012,711,5.628753433333368,False,113,0.45132743362831856,1.3489006580717073,6.489552240133763,0.057429665841891714,-1.8999999999999986,0.10619469026548672,67,0.6268656716417911,0.2,-1.5999999999999988,5.0,0.7704691810751091,15,0.6666666666666666,19,0.05263157894736842,0.0925925925925926,-4.8999999999999995,-0.25789473684210523,-5.099999999999999,0.05263157894736842,11,0.09090909090909091,-0.6,-4.8999999999999995,-1.2999999999999998,0.2653061224489796,19,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.205_maxday1,7746,4099,619,4.71126633737336,False,121,0.4132231404958678,1.1544390723067492,3.289552240133763,0.02718638214986581,-2.910447759866231,0.30578512396694213,121,0.4132231404958678,-0.3,-2.910447759866231,2.5,0.7599818508729147,18,0.5,20,0.4,1.1111111111111114,0.39999999999999997,0.019999999999999997,-1.3,0.1,20,0.4,-0.3,-1.3,2.5,6.250000000000001,20,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.014_maxday1,4331,4822,779,4.537915272279219,False,87,0.41379310344827586,1.176470588235294,2.700000000000001,0.031034482758620703,-2.9000000000000004,0.6436781609195402,87,0.41379310344827586,-0.3,-2.9000000000000004,2.5,0.9259259259259256,13,0.5,15,0.4,1.1111111111111112,0.3000000000000001,0.020000000000000007,-0.8999999999999999,0.6666666666666666,15,0.4,-0.3,-0.8999999999999999,2.5,8.33333333333333,15,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,5201,4731,615,-9.999999999999996e+17,True,375,0.33866666666666667,0.8569163914189246,-10.58076232181914,-0.028215366191517707,-12.48076232181912,0.048,126,0.30158730158730157,-0.09999999999999998,-12.080762321819122,7.5,-0.708833614430017,55,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr-0.089_maxday2,5987,4560,799,3.9129960812288718,False,239,0.37656903765690375,1.0090751776938038,0.4035171562906825,0.001688356302471475,-5.099999999999998,0.6485355648535565,122,0.5983606557377049,0.2,-4.8,5.0,12.39104687880517,36,0.3333333333333333,40,0.4,1.1111111111111112,0.8000000000000002,0.020000000000000004,-1.8000000000000005,0.325,21,0.6190476190476191,0.2,-1.7999999999999998,3.7,4.624999999999999,40,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-0.075_maxday1,6807,4539,689,5.003870517824916,False,118,0.423728813559322,1.2254901960784312,4.6000000000000005,0.03898305084745763,-4.199999999999998,0.788135593220339,118,0.423728813559322,-0.3,-4.199999999999998,2.5,0.5434782608695652,18,0.8333333333333334,16,0.5,1.6666666666666667,1.6,0.1,-1.3000000000000003,0.625,16,0.5,0.1,-1.3000000000000003,2.5,1.5625,16,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.111_maxday2,7659,4376,775,4.769606009157108,False,231,0.3939393939393939,1.0833333333333333,3.4999999999999987,0.015151515151515145,-4.4999999999999964,0.5800865800865801,117,0.5897435897435898,0.2,-4.1999999999999975,5.0,1.428571428571429,32,0.6666666666666666,39,0.4358974358974359,1.287878787878788,1.900000000000001,0.048717948717948746,-1.9999999999999984,0.358974358974359,20,0.6,0.2,-2.0,5.0,2.6315789473684195,39,1.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.150_maxday1,8306,4504,724,4.044453472731723,False,120,0.38333333333333336,1.0360360360360361,0.8000000000000005,0.0066666666666666706,-3.2999999999999954,0.5166666666666667,120,0.38333333333333336,-0.3,-3.2999999999999954,2.5,3.1249999999999982,18,0.3333333333333333,20,0.6,2.5,3.6,0.18,-0.8999999999999999,0.55,20,0.6,0.5,-0.8999999999999999,2.5,0.6944444444444444,20,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d15_return_wf2026_v1",
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
  "data_rows": 39657
}
```