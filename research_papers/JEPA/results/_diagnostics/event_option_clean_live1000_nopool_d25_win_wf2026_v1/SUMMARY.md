# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 482,
  "win_rate": 0.38589211618257263,
  "profit_factor": 1.0397277118095227,
  "pnl_return": 3.527820808685603,
  "avg_return": 0.007319130308476355,
  "max_drawdown": -7.572179191314377,
  "call_rate": 0.29045643153526973,
  "days_with_trades": 122,
  "daily_win_rate": 0.4918032786885246,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -12.100000000000001,
  "top5_day_return": 10.0,
  "top5_share_of_pnl": 2.8346110934488773,
  "min_month_trades": 58,
  "positive_month_rate": 0.6666666666666666
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 166,
    "win_rate": 0.42771084337349397,
    "profit_factor": 1.222028800304758,
    "pnl_return": 6.327820808685605,
    "avg_return": 0.03811940246196147,
    "max_drawdown": -4.999999999999997,
    "call_rate": 0.37349397590361444,
    "days_with_trades": 108,
    "daily_win_rate": 0.5462962962962963,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -4.9999999999999964,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 0.7901614396439561,
    "min_month_trades": 8,
    "positive_month_rate": 0.5
  },
  "SPXW": {
    "trades": 138,
    "win_rate": 0.3695652173913043,
    "profit_factor": 0.9770114942528735,
    "pnl_return": -0.6000000000000008,
    "avg_return": -0.004347826086956527,
    "max_drawdown": -5.4,
    "call_rate": 0.3188405797101449,
    "days_with_trades": 119,
    "daily_win_rate": 0.4117647058823529,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.4,
    "top5_day_return": 3.5,
    "top5_share_of_pnl": -5.833333333333326,
    "min_month_trades": 18,
    "positive_month_rate": 0.6666666666666666
  },
  "SPY": {
    "trades": 178,
    "win_rate": 0.3595505617977528,
    "profit_factor": 0.9356725146198833,
    "pnl_return": -2.2,
    "avg_return": -0.012359550561797755,
    "max_drawdown": -5.999999999999995,
    "call_rate": 0.19101123595505617,
    "days_with_trades": 113,
    "daily_win_rate": 0.40707964601769914,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.799999999999999,
    "top5_day_return": 4.4,
    "top5_share_of_pnl": -2.0,
    "min_month_trades": 19,
    "positive_month_rate": 0.6666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.500_maxday1,4362,4797,779,6.095828912559802,False,105,0.47619047619047616,1.5348535689999245,8.711801239587032,0.0829695356151146,-2.488198760412965,0.5428571428571428,105,0.47619047619047616,-0.3,-2.488198760412965,2.5,0.28696706125936683,16,0.8333333333333334,18,0.5,1.6666666666666667,1.8,0.1,-1.2000000000000002,0.6666666666666666,18,0.5,0.1,-1.2000000000000002,2.5,1.3888888888888888,18,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday1,5225,4713,616,2.2631063552138446,False,126,0.3253968253968254,0.803921568627451,-4.999999999999998,-0.039682539682539666,-7.599999999999992,0.06349206349206349,126,0.3253968253968254,-0.3,-7.599999999999992,2.5,-0.5000000000000002,19,0.3333333333333333,19,0.05263157894736842,0.0925925925925926,-4.8999999999999995,-0.25789473684210523,-4.899999999999999,0.0,19,0.05263157894736842,-0.3,-4.899999999999999,-0.7,0.14285714285714288,19,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.500_maxday1,6003,4551,793,5.766867525325784,False,121,0.45454545454545453,1.3629555001312468,7.186518902598687,0.059392718203294934,-1.8000000000000016,0.5867768595041323,121,0.45454545454545453,-0.3,-1.8000000000000016,2.5,0.34787357187580564,18,0.6666666666666666,21,0.42857142857142855,1.2500000000000002,0.8999999999999999,0.04285714285714285,-1.7000000000000004,0.6190476190476191,21,0.42857142857142855,-0.3,-1.7000000000000004,2.5,2.777777777777778,21,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday1,6817,4530,793,6.245571806909817,False,125,0.504,1.6935483870967738,12.899999999999997,0.10319999999999997,-4.300000000000018,0.296,125,0.504,0.5,-4.300000000000018,2.5,0.19379844961240314,19,0.6666666666666666,21,0.47619047619047616,1.5151515151515154,1.7000000000000004,0.08095238095238097,-1.3,0.2857142857142857,21,0.47619047619047616,-0.3,-1.3,2.5,1.4705882352941173,21,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.400_maxday1,7669,4471,783,6.519829968221888,False,122,0.48360655737704916,1.5608465608465605,10.6,0.08688524590163935,-1.8000000000000034,0.4098360655737705,122,0.48360655737704916,-0.3,-1.8000000000000034,2.5,0.2358490566037736,18,0.8333333333333334,20,0.35,0.8974358974358977,-0.3999999999999999,-0.019999999999999997,-2.2,0.25,20,0.35,-0.3,-2.2,2.5,-6.250000000000002,20,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.340_maxday2,8317,4606,736,5.686231908153304,False,247,0.42105263157894735,1.212121212121212,9.099999999999998,0.036842105263157884,-4.600000000000016,0.27530364372469635,124,0.6048387096774194,0.2,-4.600000000000001,5.0,0.5494505494505496,37,0.8333333333333334,39,0.38461538461538464,1.0416666666666667,0.30000000000000043,0.007692307692307703,-1.9,0.20512820512820512,20,0.65,0.2,-1.5999999999999999,2.9000000000000004,9.666666666666654,39,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.398_maxday1,3974,4521,692,5.648078276803502,False,122,0.4426229508196721,1.3235294117647058,6.6,0.054098360655737705,-2.6999999999999966,0.7131147540983607,122,0.4426229508196721,-0.3,-2.6999999999999966,2.5,0.3787878787878788,19,0.8333333333333334,20,0.6,2.5,3.6000000000000005,0.18000000000000002,-0.8999999999999995,0.75,20,0.6,0.5,-0.8999999999999995,2.5,0.6944444444444443,20,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.737_maxday1,4771,4416,550,3.512893446164689,False,72,0.3333333333333333,0.8323948920729343,-2.4135135541497448,-0.03352102158541312,-3.299999999999999,0.05555555555555555,72,0.3333333333333333,-0.3,-3.299999999999999,2.5,-1.0358342490770571,10,0.6666666666666666,8,0.125,0.23809523809523808,-1.5999999999999999,-0.19999999999999998,-1.8,0.0,8,0.125,-0.3,-1.8,-0.7,0.4375,8,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.450_maxday2,5526,4211,765,7.153239063437759,False,239,0.4602510460251046,1.4028057742966527,15.58858346528046,0.06522419859949984,-2.5090909001345345,0.2803347280334728,122,0.6885245901639344,0.2,-1.9999999999999987,5.0,0.32074755292141893,36,1.0,43,0.4883720930232558,1.5909090909090913,3.8999999999999995,0.09069767441860464,-1.1999999999999993,0.46511627906976744,22,0.6818181818181818,0.2,-1.2000000000000002,5.0,1.2820512820512822,43,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.400_maxday2,6323,4179,637,6.150117839791428,False,244,0.4262295081967213,1.2460968684367353,10.26969690949026,0.04208892176020598,-3.900000000000013,0.32786885245901637,124,0.6612903225806451,0.2,-3.299999999999999,5.0,0.4868692858286289,37,1.0,36,0.3611111111111111,0.844611711403711,-1.0721791913143948,-0.029782755314288742,-5.0,0.4444444444444444,18,0.5,-0.19999999999999998,-5.0,3.527820808685605,-3.2903276217856976,36,0.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.387_maxday1,7126,4013,712,6.314096432201893,False,120,0.475,1.487752301148175,9.218518491700518,0.07682098743083765,-2.499999999999999,0.48333333333333334,120,0.475,-0.3,-2.499999999999999,2.5,0.27119325109026615,18,1.0,20,0.5,1.666666666666667,2.000000000000001,0.10000000000000005,-1.5999999999999988,0.55,20,0.5,0.1,-1.5999999999999988,2.5,1.2499999999999996,20,1.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.450_maxday2,7751,4100,619,6.13024624678876,False,215,0.4325581395348837,1.2600688112486484,9.518518491700515,0.04427217903116519,-2.600000000000012,0.4325581395348837,115,0.6260869565217392,0.2,-2.6000000000000014,5.0,0.5252918302737607,32,0.8333333333333334,39,0.358974358974359,0.9333333333333335,-0.4999999999999998,-0.012820512820512815,-2.5999999999999996,0.0,20,0.6,0.2,-2.6,2.9000000000000004,-5.800000000000003,39,0.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.304_maxday1,4331,4822,779,4.564954988765521,False,128,0.3984375,1.103896103896104,2.4000000000000017,0.018750000000000013,-3.7999999999999954,0.7890625,128,0.3984375,-0.3,-3.7999999999999954,2.5,1.0416666666666659,19,0.6666666666666666,20,0.4,1.1111111111111114,0.40000000000000013,0.020000000000000007,-1.6,0.8,20,0.4,-0.3,-1.6,2.5,6.249999999999998,20,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.400_maxday3,5201,4731,615,3.826213442972539,False,374,0.37433155080213903,0.9921160950246276,-0.5516224967784171,-0.0014749264619743773,-7.5999999999999925,0.05080213903743316,126,0.3333333333333333,-0.09999999999999998,-7.6,7.5,-13.596254764447536,55,0.6666666666666666,56,0.25,0.5555555555555555,-5.6,-0.09999999999999999,-5.799999999999995,0.0,19,0.15789473684210525,-0.09999999999999998,-5.600000000000001,1.8999999999999995,-0.3392857142857142,56,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.394_maxday1,5987,4560,799,4.382638059285089,False,124,0.3951612903225806,1.0888888888888888,1.9999999999999991,0.01612903225806451,-3.499999999999996,0.5161290322580645,124,0.3951612903225806,-0.3,-3.499999999999996,2.5,1.2500000000000007,19,0.5,22,0.5909090909090909,2.4074074074074074,3.8000000000000007,0.17272727272727276,-1.2,0.4090909090909091,22,0.5909090909090909,0.5,-1.2,2.5,0.6578947368421051,22,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.450_maxday2,6807,4539,689,4.915646220607759,False,230,0.40869565217391307,1.1496629915751817,6.106250056267407,0.02654891328811916,-4.699999999999993,0.2826086956521739,123,0.6016260162601627,0.2,-4.699999999999997,5.0,0.8188331551977698,32,0.5,32,0.375,1.0000000000000002,1.1102230246251565e-16,3.469446951953614e-18,-3.4,0.21875,17,0.5294117647058824,0.2,-3.1,3.7,3.332663724254167e+16,32,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.379_maxday1,7659,4376,775,5.125286364658371,False,118,0.4491525423728814,1.358974358974359,7.0,0.059322033898305086,-3.9999999999999964,0.23728813559322035,118,0.4491525423728814,-0.3,-3.9999999999999964,2.5,0.35714285714285715,16,0.5,19,0.2631578947368421,0.5952380952380953,-1.6999999999999997,-0.0894736842105263,-2.3,0.10526315789473684,19,0.2631578947368421,-0.3,-2.3,2.5,-1.470588235294118,19,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.550_maxday3,8306,4504,724,5.505968279710019,False,131,0.42748091603053434,1.2444444444444445,5.5,0.04198473282442748,-2.4999999999999996,0.15267175572519084,70,0.5285714285714286,0.2,-2.1999999999999997,5.5,1.0,14,0.8333333333333334,29,0.41379310344827586,1.1764705882352942,0.8999999999999999,0.031034482758620686,-1.0,0.0,16,0.5,0.05000000000000002,-0.6000000000000001,3.0999999999999996,3.444444444444444,29,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d25_win_wf2026_v1",
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
  "data_rows": 39663
}
```