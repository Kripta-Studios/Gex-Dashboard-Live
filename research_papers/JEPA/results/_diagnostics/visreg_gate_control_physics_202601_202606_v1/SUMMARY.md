# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 362,
  "win_rate": 0.3259668508287293,
  "profit_factor": 0.8007994329467286,
  "pnl_return": -14.581481508299483,
  "avg_return": -0.040280335658285864,
  "max_drawdown": -17.58148150829957,
  "call_rate": 0.2569060773480663,
  "days_with_trades": 123,
  "daily_win_rate": 0.2926829268292683,
  "median_daily_return": -0.8999999999999999,
  "daily_max_drawdown": -18.08148150829949,
  "top5_day_return": 7.5,
  "top5_share_of_pnl": -0.5143510277560721,
  "min_month_trades": 57,
  "positive_month_rate": 0.16666666666666666
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 119,
    "win_rate": 0.3697478991596639,
    "profit_factor": 0.9608230440755785,
    "pnl_return": -0.8814815082994834,
    "avg_return": -0.0074074076327687675,
    "max_drawdown": -4.581481508299484,
    "call_rate": 0.19327731092436976,
    "days_with_trades": 119,
    "daily_win_rate": 0.3697478991596639,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -4.581481508299484,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -2.8361343674955743,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  },
  "SPXW": {
    "trades": 123,
    "win_rate": 0.2926829268292683,
    "profit_factor": 0.689655172413793,
    "pnl_return": -8.1,
    "avg_return": -0.06585365853658537,
    "max_drawdown": -9.399999999999995,
    "call_rate": 0.2926829268292683,
    "days_with_trades": 123,
    "daily_win_rate": 0.2926829268292683,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -9.399999999999995,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.308641975308642,
    "min_month_trades": 19,
    "positive_month_rate": 0.16666666666666666
  },
  "SPY": {
    "trades": 120,
    "win_rate": 0.31666666666666665,
    "profit_factor": 0.7723577235772359,
    "pnl_return": -5.6,
    "avg_return": -0.04666666666666666,
    "max_drawdown": -7.299999999999995,
    "call_rate": 0.2833333333333333,
    "days_with_trades": 120,
    "daily_win_rate": 0.31666666666666665,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.299999999999995,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.44642857142857145,
    "min_month_trades": 18,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.350_maxday1,22454,1490,779,7.366321780687098,False,41.0,0.6341463414634146,2.8888888888888893,8.5,0.2073170731707317,-1.200000000000001,0.3170731707317073,41.0,0.6341463414634146,0.5,-1.200000000000001,2.5,0.29411764705882354,19.0,1.0,20,0.35,0.8974358974358977,-0.3999999999999999,-0.019999999999999997,-2.7,0.45,20,0.35,-0.3,-2.7,2.5,-6.250000000000002,20,0.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr0.300_maxday1,24374,1621,616,6.828515139003582,False,42.0,0.5952380952380952,2.450980392156863,7.3999999999999995,0.17619047619047618,-1.5999999999999988,0.23809523809523808,42.0,0.5952380952380952,0.5,-1.5999999999999988,2.5,0.3378378378378379,20.0,1.0,19,0.21052631578947367,0.44444444444444453,-2.4999999999999996,-0.13157894736842102,-2.5,0.3684210526315789,19,0.21052631578947367,-0.3,-2.5,1.7,-0.68,19,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr-999.000_maxday1,26807,1395,793,3.2284031650622182,False,39.0,0.3333333333333333,0.8333333333333335,-1.3,-0.03333333333333333,-3.1,0.3076923076923077,39.0,0.3333333333333333,-0.3,-3.1,2.5,-1.923076923076923,19.0,0.5,22,0.45454545454545453,1.3888888888888893,1.4,0.06363636363636363,-2.2999999999999994,0.6818181818181818,22,0.45454545454545453,-0.3,-2.2999999999999994,2.5,1.7857142857142858,22,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.350_maxday1,29057,1409,793,5.3467540632629555,False,41.0,0.5121951219512195,1.7500000000000002,4.5,0.10975609756097561,-1.6,0.5365853658536586,41.0,0.5121951219512195,0.5,-1.6,2.5,0.5555555555555556,19.0,0.5,21,0.2857142857142857,0.6666666666666669,-1.5,-0.07142857142857142,-2.8,0.23809523809523808,21,0.2857142857142857,-0.3,-2.8,2.5,-1.6666666666666667,21,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr-999.000_maxday1,30838,1586,783,5.20026196624066,False,43.0,0.46511627906976744,1.4492753623188408,3.1000000000000005,0.07209302325581396,-2.4999999999999982,0.4883720930232558,43.0,0.46511627906976744,-0.3,-2.4999999999999982,2.5,0.8064516129032256,21.0,1.0,20,0.25,0.5555555555555557,-1.9999999999999996,-0.09999999999999998,-2.5999999999999996,0.0,20,0.25,-0.3,-2.5999999999999996,2.5,-1.2500000000000002,20,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr-999.000_maxday1,33195,1576,736,-1e+18,False,,,,,,,,,,,,,,,,21,0.19047619047619047,0.3921568627450981,-3.099999999999999,-0.1476190476190476,-3.3,0.0,21,0.19047619047619047,-0.3,-3.3,1.7,-0.5483870967741937,21,0.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.400_maxday1,22454,1494,779,8.143423807360843,False,41.0,0.6829268292682927,3.5897435897435908,10.100000000000001,0.24634146341463417,-0.6000000000000014,0.3170731707317073,41.0,0.6829268292682927,0.5,-0.6000000000000014,2.5,0.2475247524752475,19.0,1.0,20,0.35,0.8974358974358977,-0.3999999999999999,-0.019999999999999997,-3.1000000000000005,0.45,20,0.35,-0.3,-3.1000000000000005,2.5,-6.250000000000002,20,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr0.350_maxday1,24374,1626,615,6.542753810012868,False,42.0,0.5714285714285714,2.2222222222222223,6.6,0.15714285714285714,-1.5999999999999988,0.21428571428571427,42.0,0.5714285714285714,0.5,-1.5999999999999988,2.5,0.3787878787878788,20.0,1.0,19,0.21052631578947367,0.44444444444444453,-2.4999999999999996,-0.13157894736842102,-2.5,0.42105263157894735,19,0.21052631578947367,-0.3,-2.5,1.7,-0.68,19,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.350_maxday1,26807,1394,799,3.587732641004063,False,39.0,0.358974358974359,0.9333333333333335,-0.4999999999999998,-0.012820512820512815,-2.5000000000000004,0.3076923076923077,39.0,0.358974358974359,-0.3,-2.5000000000000004,2.5,-5.000000000000003,19.0,0.5,22,0.5454545454545454,2.0000000000000004,3.000000000000001,0.1363636363636364,-1.0999999999999988,0.5909090909090909,22,0.5454545454545454,0.5,-1.0999999999999988,2.5,0.833333333333333,22,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.350_maxday1,29057,1414,689,4.827200197101629,False,41.0,0.4634146341463415,1.4393939393939397,2.9,0.07073170731707316,-1.5999999999999999,0.6097560975609756,41.0,0.4634146341463415,-0.3,-1.5999999999999999,2.5,0.8620689655172414,19.0,0.5,18,0.2777777777777778,0.6410256410256412,-1.4,-0.07777777777777778,-2.8000000000000003,0.16666666666666666,18,0.2777777777777778,-0.3,-2.8000000000000003,2.5,-1.7857142857142858,18,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.350_maxday1,30838,1488,775,5.513595189052118,False,40.0,0.5,1.666666666666667,3.9999999999999996,0.09999999999999999,-2.4999999999999982,0.45,40.0,0.5,0.1,-2.4999999999999982,2.5,0.6250000000000001,18.0,1.0,20,0.25,0.5555555555555557,-1.9999999999999996,-0.09999999999999998,-2.5999999999999996,0.05,20,0.25,-0.3,-2.5999999999999996,2.5,-1.2500000000000002,20,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr-999.000_maxday1,33195,1464,724,-1e+18,False,,,,,,,,,,,,,,,,21,0.23809523809523808,0.5208333333333334,-2.3,-0.10952380952380951,-2.5,0.0,21,0.23809523809523808,-0.3,-2.5,2.5,-1.0869565217391306,21,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.400_maxday1,22454,1369,692,7.058223078997179,False,41.0,0.6097560975609756,2.604166666666667,7.699999999999999,0.18780487804878046,-1.2,0.2926829268292683,41.0,0.6097560975609756,0.5,-1.2,2.5,0.32467532467532473,19.0,1.0,20,0.35,0.8974358974358977,-0.3999999999999999,-0.019999999999999997,-2.0,0.2,20,0.35,-0.3,-2.0,2.5,-6.250000000000002,20,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday1,24374,1436,550,-1e+18,False,,,,,,,,,,,,,,,,19,0.3157894736842105,0.7692307692307694,-0.8999999999999999,-0.047368421052631574,-1.5999999999999999,0.3157894736842105,19,0.3157894736842105,-0.3,-1.5999999999999999,2.5,-2.777777777777778,19,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.400_maxday1,26807,1242,765,3.2677326410040632,False,39.0,0.358974358974359,0.9333333333333335,-0.4999999999999998,-0.012820512820512815,-1.6,0.358974358974359,39.0,0.358974358974359,-0.3,-1.6,2.5,-5.000000000000003,19.0,0.0,22,0.5,1.666666666666667,2.200000000000001,0.10000000000000005,-0.8999999999999999,0.4090909090909091,22,0.5,0.1,-0.8999999999999999,2.5,1.1363636363636358,22,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.350_maxday1,29057,1315,637,6.196778961974131,False,41.0,0.5365853658536586,1.929824561403509,5.3,0.12926829268292683,-1.2,0.4878048780487805,41.0,0.5365853658536586,0.5,-1.2,2.5,0.4716981132075472,19.0,1.0,18,0.4444444444444444,1.206172830566839,0.6185184917005169,0.03436213842780649,-1.3,0.2222222222222222,18,0.4444444444444444,-0.3,-1.3,2.5,4.041916342915881,18,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.300_maxday1,30838,1402,712,6.194998794556557,False,40.0,0.55,1.9663923132778736,5.218518491700516,0.13046296229251292,-1.299999999999999,0.45,40.0,0.55,0.5,-1.299999999999999,2.5,0.4790631678274163,18.0,1.0,20,0.2,0.4166666666666667,-2.7999999999999994,-0.13999999999999996,-3.699999999999999,0.0,20,0.2,-0.3,-3.699999999999999,1.7,-0.6071428571428573,20,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr-999.000_maxday1,33195,1349,619,-1e+18,False,,,,,,,,,,,,,,,,20,0.4,1.1111111111111114,0.39999999999999997,0.019999999999999997,-1.3,0.0,20,0.4,-0.3,-1.3,2.5,6.250000000000001,20,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers/JEPA/results/_diagnostics/visreg_gate_control_physics_202601_202606_v1",
    "tickers": [
      "SPXW",
      "SPY",
      "QQQ"
    ],
    "train_tickers": [],
    "expiry_modes": [
      "zero_dte"
    ],
    "start_month": "202601",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": true,
    "delta_bucket": 25,
    "label_mode": "win",
    "clip_return": 2.0,
    "min_train_rows": 500,
    "min_val_rows": 30,
    "min_val_trades": 5,
    "min_month_trades": 1,
    "min_val_pf": 0.0,
    "min_val_win_rate": 0.0,
    "min_val_positive_month_rate": 0.0,
    "min_val_daily_win_rate": 0.0,
    "min_val_median_daily_return": -Infinity,
    "max_val_top5_share": Infinity,
    "max_val_daily_drawdown": Infinity,
    "min_call_rate": 0.2,
    "max_call_rate": 0.8,
    "cooldown_minutes": 30,
    "objective": "regression_l1",
    "n_estimators": 240,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 80,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "lgb_jobs": 16,
    "threshold_grid": [
      -999.0,
      -0.05,
      0.0,
      0.05,
      0.1,
      0.15,
      0.2,
      0.25,
      0.3,
      0.35,
      0.4
    ],
    "threshold_quantiles": [],
    "max_day_grid": [
      1
    ],
    "feature_include_prefixes": [],
    "feature_exclude_prefixes": [
      "xjepa_"
    ],
    "allow_invalid_val_deploy": true,
    "deploy_month": "",
    "deploy_select_end_month": "",
    "export_deploy_model": false,
    "exclude_months": [],
    "skip_walkforward": false,
    "resume": false,
    "seed": 20260617
  },
  "feature_count": 282,
  "features": [
    "dte_days",
    "minute",
    "spot",
    "underlying_volume",
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "dist_fib_127_up_bps",
    "dist_fib_161_up_bps",
    "dist_fib_200_up_bps",
    "dist_fib_127_dn_bps",
    "dist_fib_161_dn_bps",
    "dist_fib_200_dn_bps",
    "nearest_level_abs_bps",
    "ib_range_bps",
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
    "phys_fib_up_min_abs_bps",
    "phys_fib_up_mean_signed_bps",
    "phys_fib_dn_min_abs_bps",
    "phys_fib_dn_mean_signed_bps",
    "phys_fib_any_min_abs_bps",
    "phys_ib_edge_min_abs_bps",
    "phys_ib_balance",
    "phys_nearest_level_vs_ib_range",
    "phys_momentum_accel_ret_1m_bps_minus_ret_5m_bps",
    "phys_abs_ret_1m_bps",
    "phys_momentum_accel_ret_5m_bps_minus_ret_15m_bps",
    "phys_abs_ret_5m_bps",
    "phys_momentum_accel_ret_15m_bps_minus_ret_30m_bps",
    "phys_abs_ret_15m_bps",
    "phys_abs_ret_30m_bps",
    "phys_event_seq_in_day",
    "phys_event_frac_in_day",
    "phys_minutes_since_first_event",
    "phys_spot_ret_from_first_event_bps",
    "phys_same_day_event_count",
    "ctx_spx_spot",
    "ctx_spx_ret_1m_bps",
    "ctx_spx_ret_1m_bps_minus_self",
    "ctx_spx_ret_5m_bps",
    "ctx_spx_ret_5m_bps_minus_self",
    "ctx_spx_ret_15m_bps",
    "ctx_spx_ret_15m_bps_minus_self",
    "ctx_spx_ret_30m_bps",
    "ctx_spx_ret_30m_bps_minus_self",
    "ctx_spx_ib_range_bps",
    "ctx_spx_nearest_level_abs_bps",
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
    "ctx_spy_ib_range_bps",
    "ctx_spy_nearest_level_abs_bps",
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
    "ctx_qqq_ib_range_bps",
    "ctx_qqq_nearest_level_abs_bps",
    "ctx_qqq_phys_d35_iv_skew_put_minus_call",
    "ctx_qqq_phys_total_volume_skew_call_minus_put",
    "ctx_qqq_phys_total_oi_skew_call_minus_put",
    "ctx_spy_qqq_ret_5m_spread",
    "ctx_spx_spy_ret_5m_spread",
    "ticker_QQQ",
    "ticker_SPXW",
    "ticker_SPY",
    "expiry_mode_zero_dte",
    "nearest_level_name_fib_127_dn",
    "nearest_level_name_fib_127_up",
    "nearest_level_name_fib_161_dn",
    "nearest_level_name_fib_161_up",
    "nearest_level_name_fib_200_dn",
    "nearest_level_name_fib_200_up",
    "nearest_level_name_ib_high",
    "nearest_level_name_ib_low"
  ],
  "grid": [
    {
      "threshold": -999.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": -0.05,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.1,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.15,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.2,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.25,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.3,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.35,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.4,
      "max_trades_per_day": 1
    }
  ],
  "data_rows": 39663
}
```