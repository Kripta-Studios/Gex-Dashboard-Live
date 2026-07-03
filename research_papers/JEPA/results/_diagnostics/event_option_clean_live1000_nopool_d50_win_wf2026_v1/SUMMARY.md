# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 480,
  "win_rate": 0.38125,
  "profit_factor": 1.019517719681984,
  "pnl_return": 1.7390288236647633,
  "avg_return": 0.003622976715968257,
  "max_drawdown": -7.699999999999992,
  "call_rate": 0.2375,
  "days_with_trades": 121,
  "daily_win_rate": 0.4380165289256198,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -12.0,
  "top5_day_return": 11.6,
  "top5_share_of_pnl": 6.670389726810048,
  "min_month_trades": 57,
  "positive_month_rate": 0.5
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 181,
    "win_rate": 0.3867403314917127,
    "profit_factor": 1.03120206677672,
    "pnl_return": 1.0390288236647642,
    "avg_return": 0.00574049073847936,
    "max_drawdown": -6.4999999999999964,
    "call_rate": 0.2983425414364641,
    "days_with_trades": 112,
    "daily_win_rate": 0.4375,
    "median_daily_return": -0.19999999999999998,
    "daily_max_drawdown": -6.499999999999999,
    "top5_day_return": 5.204918027981351,
    "top5_share_of_pnl": 5.00940677432129,
    "min_month_trades": 13,
    "positive_month_rate": 0.3333333333333333
  },
  "SPXW": {
    "trades": 152,
    "win_rate": 0.3815789473684211,
    "profit_factor": 1.0283687943262412,
    "pnl_return": 0.7999999999999996,
    "avg_return": 0.005263157894736839,
    "max_drawdown": -5.199999999999999,
    "call_rate": 0.21710526315789475,
    "days_with_trades": 118,
    "daily_win_rate": 0.4067796610169492,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.199999999999999,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 6.2500000000000036,
    "min_month_trades": 19,
    "positive_month_rate": 0.6666666666666666
  },
  "SPY": {
    "trades": 147,
    "win_rate": 0.3741496598639456,
    "profit_factor": 0.996376811594203,
    "pnl_return": -0.10000000000000053,
    "avg_return": -0.000680272108843541,
    "max_drawdown": -5.999999999999999,
    "call_rate": 0.1836734693877551,
    "days_with_trades": 110,
    "daily_win_rate": 0.4636363636363636,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.7,
    "top5_day_return": 4.5,
    "top5_share_of_pnl": -44.99999999999976,
    "min_month_trades": 13,
    "positive_month_rate": 0.6666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.395_maxday1,4362,4797,779,5.937057236573397,False,127,0.44881889763779526,1.3611553331817146,7.561904761904762,0.05954255718035245,-2.9,0.6141732283464567,127,0.44881889763779526,-0.3,-2.9,2.5,0.3306045340050378,19,1.0,20,0.5,1.666666666666667,2.0,0.1,-1.8,0.65,20,0.5,0.1,-1.8,2.5,1.25,20,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday1,5225,4713,616,3.5424545745970573,False,126,0.373015873015873,0.9941579371474615,-0.13809523809523777,-0.0010959939531368077,-5.138095238095237,0.05555555555555555,126,0.373015873015873,-0.3,-5.138095238095237,2.5,-18.10344827586211,19,0.3333333333333333,19,0.05263157894736842,0.0925925925925926,-4.8999999999999995,-0.25789473684210523,-4.899999999999999,0.0,19,0.05263157894736842,-0.3,-4.899999999999999,-0.7,0.14285714285714288,19,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.300_maxday1,6003,4551,793,5.4797372971497715,False,124,0.4435483870967742,1.3324873096446697,6.861904761904763,0.05533794162826422,-2.099999999999998,0.532258064516129,124,0.4435483870967742,-0.3,-2.099999999999998,2.5,0.36433032616238714,19,0.5,22,0.45454545454545453,1.3888888888888893,1.4,0.06363636363636363,-1.9,0.6818181818181818,22,0.45454545454545453,-0.3,-1.9,2.5,1.7857142857142858,22,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.550_maxday2,6817,4530,793,5.2095336436293165,False,229,0.4148471615720524,1.15300608995059,6.141373010445357,0.026818222753036493,-4.928339103317698,0.11353711790393013,120,0.5916666666666667,0.2,-4.9283391033177,5.0,0.814150189460225,33,0.8333333333333334,33,0.48484848484848486,1.5686274509803924,2.9000000000000004,0.08787878787878789,-1.9000000000000001,0.030303030303030304,17,0.5882352941176471,0.2,-1.9,5.0,1.7241379310344827,33,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.450_maxday1,7669,4471,783,5.896415914275666,False,117,0.46153846153846156,1.4332659251769457,8.161904761904763,0.06975986975986977,-2.8380952380952382,0.1623931623931624,117,0.46153846153846156,-0.3,-2.8380952380952382,2.5,0.3063010501750291,17,0.8333333333333334,20,0.4,1.1111111111111114,0.40000000000000013,0.020000000000000007,-2.2,0.1,20,0.4,-0.3,-2.2,2.5,6.249999999999998,20,1.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.408_maxday2,8317,4606,736,5.93470447199806,False,245,0.4326530612244898,1.2709832134292565,11.299999999999999,0.046122448979591835,-4.000000000000001,0.24081632653061225,124,0.6370967741935484,0.2,-3.5999999999999996,5.0,0.4424778761061947,37,0.6666666666666666,38,0.34210526315789475,0.8666666666666668,-0.9999999999999996,-0.0263157894736842,-2.8,0.05263157894736842,20,0.45,-0.6,-2.8000000000000003,4.5,-4.500000000000002,38,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.300_maxday1,3974,4524,692,5.69334087042284,False,128,0.453125,1.3623063679459244,7.608433726864421,0.05944088849112829,-2.4999999999999982,0.40625,128,0.453125,-0.3,-2.4999999999999982,2.5,0.3285827398578521,19,0.6666666666666666,20,0.4,1.1111111111111114,0.4000000000000002,0.02000000000000001,-1.6999999999999997,0.35,20,0.4,-0.3,-1.6999999999999997,2.5,6.249999999999997,20,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.700_maxday1,4771,4419,550,6.745260734543036,False,106,0.5,1.6666666666666663,10.600000000000001,0.10000000000000002,-1.799999999999999,0.0660377358490566,106,0.5,0.1,-1.799999999999999,2.5,0.23584905660377356,15,1.0,13,0.23076923076923078,0.5000000000000001,-1.5,-0.11538461538461539,-1.6,0.0,13,0.23076923076923078,-0.3,-1.6,0.8999999999999999,-0.6,13,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.496_maxday1,5526,4214,765,6.22166741222032,False,123,0.4796747967479675,1.5290178580479328,10.157142874520304,0.08257839735382361,-2.90000000000001,0.25203252032520324,123,0.4796747967479675,-0.3,-2.90000000000001,2.5,0.24613220773642694,19,0.8333333333333334,22,0.3181818181818182,0.7777777777777779,-0.9999999999999998,-0.04545454545454544,-2.7,0.4090909090909091,22,0.3181818181818182,-0.3,-2.7,2.5,-2.5000000000000004,22,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday2,6323,4182,637,6.954709785042801,False,249,0.4538152610441767,1.3856605764582497,15.616242002482931,0.06271583133527281,-3.5000000000000107,0.3373493975903614,125,0.68,0.2,-3.4000000000000004,5.0,0.3201794643810602,37,1.0,36,0.5555555555555556,2.007106415767378,4.834110795683414,0.13428085543565038,-1.299999999999999,0.4166666666666667,18,0.7777777777777778,0.2,-1.0000000000000004,5.0,1.0343163844040801,36,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.450_maxday3,7126,4016,712,5.908130193009652,False,325,0.4246153846153846,1.2243054547317165,12.523589029286676,0.038534120090112846,-5.900000000000014,0.4676923076923077,118,0.4491525423728814,-0.09999999999999998,-5.1,7.5,0.5988698593079901,48,0.8333333333333334,54,0.37037037037037035,0.9514625517628773,-0.49508197201864945,-0.009168184667012027,-4.2,0.42592592592592593,20,0.35,-0.09999999999999998,-3.8999999999999995,4.004918027981351,-8.089403885283241,54,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.550_maxday2,7752,4102,619,4.349081178889925,False,161,0.38509316770186336,1.0314515419422026,0.9341107956834154,0.005801930407971524,-3.299999999999999,0.4658385093167702,92,0.5217391304347826,0.2,-3.2,5.0,5.352684096046544,20,0.5,36,0.3333333333333333,0.8333333333333334,-1.1999999999999997,-0.033333333333333326,-3.299999999999999,0.0,19,0.5263157894736842,0.2,-3.3,2.9000000000000004,-2.4166666666666674,36,0.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.400_maxday1,4331,4827,779,5.113318142764605,False,126,0.42857142857142855,1.254576989727055,5.478801842305342,0.04348255430401065,-3.599999999999997,0.6111111111111112,126,0.42857142857142855,-0.3,-3.599999999999997,2.5,0.45630414677455516,18,0.6666666666666666,20,0.5,1.666666666666667,2.0,0.1,-1.5,0.55,20,0.5,0.1,-1.5,2.5,1.25,20,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.500_maxday2,5201,4736,615,3.9147008379162247,False,251,0.3705179282868526,0.977507455170993,-1.0572049008219973,-0.0042119717164223,-5.899999999999999,0.05179282868525897,126,0.5396825396825397,0.2,-5.6,5.0,-4.729452158339791,37,0.6666666666666666,38,0.21052631578947367,0.44444444444444436,-4.999999999999999,-0.13157894736842102,-5.699999999999997,0.0,19,0.3684210526315789,-0.6,-5.3999999999999995,1.7999999999999998,-0.36000000000000004,38,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.600_maxday1,5987,4565,799,3.7760987389667333,False,70,0.37142857142857144,0.9710617971864607,-0.3782434838363931,-0.005403478340519902,-3.2,0.42857142857142855,70,0.37142857142857144,-0.3,-3.2,2.5,-6.609499189895786,7,0.5,13,0.46153846153846156,1.4285714285714286,0.8999999999999999,0.06923076923076922,-1.2000000000000002,0.3076923076923077,13,0.46153846153846156,-0.3,-1.2000000000000002,2.5,2.777777777777778,13,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.400_maxday2,6807,4544,689,5.216381793679134,False,249,0.41767068273092367,1.2018168106849634,8.705425195118151,0.03496154696834599,-6.700000000000034,0.19678714859437751,125,0.616,0.2,-6.400000000000003,5.0,0.5743544844660674,37,0.8333333333333334,36,0.4444444444444444,1.3333333333333335,2.000000000000001,0.05555555555555558,-2.099999999999998,0.2777777777777778,18,0.7222222222222222,0.2,-1.7999999999999998,3.4000000000000004,1.6999999999999995,36,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.500_maxday1,7659,4381,775,5.564060492501617,False,106,0.44339622641509435,1.327683615819209,5.8,0.05471698113207547,-1.5999999999999988,0.10377358490566038,106,0.44339622641509435,-0.3,-1.5999999999999988,2.5,0.4310344827586207,16,0.6666666666666666,19,0.3684210526315789,0.9722222222222224,-0.09999999999999987,-0.005263157894736835,-1.7000000000000002,0.05263157894736842,19,0.3684210526315789,-0.3,-1.7000000000000002,2.5,-25.000000000000032,19,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.383_maxday1,8308,4507,724,5.988229754499353,False,121,0.45454545454545453,1.3944386025688946,7.778801842305342,0.06428761853144911,-2.0211981576946574,0.256198347107438,121,0.45454545454545453,-0.3,-2.0211981576946574,2.5,0.32138625596600806,18,0.8333333333333334,21,0.38095238095238093,1.025641025641026,0.09999999999999998,0.004761904761904761,-1.2,0.047619047619047616,21,0.38095238095238093,-0.3,-1.2,2.5,25.000000000000007,21,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d50_win_wf2026_v1",
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
  "data_rows": 39671
}
```