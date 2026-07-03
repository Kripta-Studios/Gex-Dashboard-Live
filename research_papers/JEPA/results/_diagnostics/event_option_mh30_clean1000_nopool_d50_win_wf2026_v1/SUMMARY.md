# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 357,
  "win_rate": 0.4565826330532213,
  "profit_factor": 0.7115215148624646,
  "pnl_return": -32.46845946797026,
  "avg_return": -0.09094806573661138,
  "max_drawdown": -36.20417372643681,
  "call_rate": 0.29411764705882354,
  "days_with_trades": 123,
  "daily_win_rate": 0.43902439024390244,
  "median_daily_return": -0.6774283810189629,
  "daily_max_drawdown": -34.468459467970256,
  "top5_day_return": 9.5,
  "top5_share_of_pnl": -0.2925916460364137,
  "min_month_trades": 49,
  "positive_month_rate": 0.0
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 96,
    "win_rate": 0.46875,
    "profit_factor": 0.749831072224707,
    "pnl_return": -7.384685658046807,
    "avg_return": -0.07692380893798757,
    "max_drawdown": -8.484685658046802,
    "call_rate": 0.3125,
    "days_with_trades": 94,
    "daily_win_rate": 0.46808510638297873,
    "median_daily_return": -0.4560846660963543,
    "daily_max_drawdown": -8.484685658046802,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.3385384450692016,
    "min_month_trades": 9,
    "positive_month_rate": 0.16666666666666666
  },
  "SPXW": {
    "trades": 104,
    "win_rate": 0.4519230769230769,
    "profit_factor": 0.7089939166945908,
    "pnl_return": -9.478516055072067,
    "avg_return": -0.09113957745261603,
    "max_drawdown": -12.714230313538508,
    "call_rate": 0.2980769230769231,
    "days_with_trades": 104,
    "daily_win_rate": 0.4519230769230769,
    "median_daily_return": -0.589883271009296,
    "daily_max_drawdown": -12.714230313538508,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.26375436676738234,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  },
  "SPY": {
    "trades": 157,
    "win_rate": 0.45222929936305734,
    "profit_factor": 0.69074235508477,
    "pnl_return": -15.605257754851385,
    "avg_return": -0.09939654620924449,
    "max_drawdown": -18.50525775485137,
    "call_rate": 0.2802547770700637,
    "days_with_trades": 120,
    "daily_win_rate": 0.4583333333333333,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -18.505257754851378,
    "top5_day_return": 7.5,
    "top5_share_of_pnl": -0.4806072490323583,
    "min_month_trades": 18,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.550_maxday1,4362,4797,779,2.118606289788486,False,127,0.4881889763779528,0.8418974007615548,-5.592026262478141,-0.04403170285415859,-9.189967059180493,0.4566929133858268,127,0.4881889763779528,-0.06396396520240144,-9.189967059180493,2.5,-0.447065139299276,19,0.5,20,0.55,1.0185185185185186,0.10000000000000031,0.005000000000000016,-1.8,0.55,20,0.55,0.5,-1.8,2.5,24.999999999999922,20,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,5225,4713,616,-9.999999999999996e+17,True,375,0.49066666666666664,0.8084148346221791,-21.376142778040247,-0.05700304740810733,-27.22833910331772,0.042666666666666665,126,0.48412698412698413,-0.7,-26.728339103317698,7.5,-0.35085843493264673,55,0.16666666666666666,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.450_maxday1,6003,4551,793,5.06181276560084,False,124,0.5806451612903226,1.1684517798229,5.079836225812272,0.04096642117590542,-3.0380952380952393,0.5725806451612904,124,0.5806451612903226,0.5,-3.0380952380952393,2.5,0.49214185041964553,19,0.6666666666666666,22,0.5454545454545454,1.0445587372490936,0.2559477164478561,0.011633987111266186,-3.8797665420185927,0.6818181818181818,22,0.5454545454545454,0.5,-3.8797665420185927,2.5,9.76761986665086,22,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday1,6817,4530,793,2.445324527265884,False,125,0.528,0.9423762138081272,-2.0178617801138303,-0.016142894240910644,-10.938095238095233,0.072,125,0.528,0.5,-10.938095238095233,2.5,-1.2389352058885676,19,0.6666666666666666,21,0.3333333333333333,0.4117386885555615,-4.419079170242916,-0.21043234144013884,-4.9121023332167555,0.047619047619047616,21,0.3333333333333333,-0.6,-4.9121023332167555,2.5,-0.5657287194206515,21,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.450_maxday1,7669,4471,783,3.1994866852500268,False,123,0.5365853658536586,0.9897679527011588,-0.3369409503567463,-0.002739357319973547,-7.500000000000001,0.1951219512195122,123,0.5365853658536586,0.5,-7.500000000000001,2.5,-7.419697716626756,19,0.5,20,0.35,0.4784437443506422,-3.815384601277006,-0.1907692300638503,-4.715384601277006,0.15,20,0.35,-0.6,-4.715384601277006,2.5,-0.6552419379066666,20,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.500_maxday1,8317,4606,736,3.6263475481624234,False,124,0.532258064516129,0.9863119752331799,-0.4523255516337542,-0.003647786706723824,-5.300000000000001,0.27419354838709675,124,0.532258064516129,0.5,-5.300000000000001,2.5,-5.526992651576398,19,0.5,21,0.47619047619047616,0.7575757575757577,-1.5999999999999996,-0.07619047619047617,-3.0,0.047619047619047616,21,0.47619047619047616,-0.6,-3.0,2.5,-1.5625000000000004,21,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,3974,4524,692,4.159908224439171,False,128,0.5546875,1.095064248773888,3.0502429607695865,0.023830023131012394,-5.253921576648068,0.4296875,128,0.5546875,0.5,-5.253921576648068,2.5,0.8196068418658826,19,0.5,20,0.5,0.8333333333333335,-1.0,-0.05,-2.7,0.45,20,0.5,-0.04999999999999999,-2.7,2.5,-2.5,20,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.700_maxday1,4771,4419,550,0.48358828721684494,False,126,0.4603174603174603,0.7369157899788779,-10.35320750941057,-0.08216831356675056,-13.253207509410556,0.06349206349206349,126,0.4603174603174603,-0.6,-13.253207509410556,2.5,-0.24147106080194178,19,0.3333333333333333,19,0.3684210526315789,0.5063533359489785,-3.4121693321927085,-0.17958785958908993,-3.4121693321927093,0.0,19,0.3684210526315789,-0.6,-3.4121693321927093,2.5,-0.7326717277519942,19,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.806_maxday1,5526,4214,765,2.0715091108884294,False,44,0.4318181818181818,0.6854838700823802,-4.358823547311634,-0.09906417152980987,-5.525490228069235,0.11363636363636363,44,0.4318181818181818,-0.4666666596212002,-5.525490228069235,2.5,-0.5735492554044566,3,0.3333333333333333,13,0.5384615384615384,0.9722222222222222,-0.09999999999999987,-0.007692307692307682,-1.5,0.5384615384615384,13,0.5384615384615384,0.5,-1.5,2.5,-25.000000000000032,13,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.700_maxday1,6323,4182,637,2.24553291238998,False,115,0.5043478260869565,0.8703635918213902,-4.253145452283643,-0.03698387349811864,-8.399999999999995,0.26956521739130435,115,0.5043478260869565,0.05511815236486828,-8.399999999999995,2.5,-0.5878002593721957,17,0.3333333333333333,17,0.5882352941176471,1.1033597132579556,0.4341107956834147,0.025535929157847925,-2.7,0.29411764705882354,17,0.5882352941176471,0.5,-2.7,2.5,5.758898476745514,17,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.745_maxday3,7126,4016,712,2.777598990251389,False,98,0.5306122448979592,0.9361844606156174,-1.7236273298680689,-0.017588033978245602,-8.0,0.6938775510204082,59,0.4745762711864407,-0.09999999999999998,-8.0,7.5,-4.351288628368448,11,0.5,9,0.2222222222222222,0.26844901127357035,-2.7251021907505653,-0.3027891323056184,-3.2251021907505653,0.5555555555555556,7,0.14285714285714285,-0.6,-2.7251021907505653,-1.525102190750565,0.559649541190421,9,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.711_maxday1,7752,4102,619,3.0276879217072814,False,84,0.5357142857142857,0.9729496656779804,-0.6153813687028022,-0.00732596867503336,-7.242780761433699,0.6666666666666666,84,0.5357142857142857,0.5,-7.242780761433699,2.5,-4.062521433285986,12,0.5,18,0.5,0.8855609411136176,-0.5815249307869482,-0.0323069405992749,-1.8815249307869482,0.2222222222222222,18,0.5,0.1092375346065258,-1.8815249307869482,2.5,-4.299041825458587,18,0.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.450_maxday1,4331,4827,779,4.511903027130436,False,128,0.546875,1.07752294689005,2.392476541481805,0.0186912229803266,-3.8722787750494128,0.6796875,128,0.546875,0.5,-3.8722787750494128,2.5,1.044942325098661,19,0.6666666666666666,20,0.55,1.0185185185185186,0.10000000000000031,0.005000000000000016,-1.9,0.75,20,0.55,0.5,-1.9,2.5,24.999999999999922,20,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.500_maxday3,5201,4736,615,-3.3472221033058362,False,375,0.48,0.800982858892814,-22.130358520167267,-0.059014289387112714,-28.670828391387076,0.050666666666666665,126,0.4603174603174603,-0.7,-28.17082839138706,7.5,-0.338900971403843,55,0.16666666666666666,56,0.4107142857142857,0.5871941956282394,-8.084662255893289,-0.14436896885523728,-10.88466225589329,0.0,19,0.3684210526315789,-0.7,-10.38466225589329,7.5,-0.9276825379480632,56,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.504_maxday1,5987,4565,799,3.6385704074625793,False,124,0.532258064516129,1.007574203671308,0.2402358344498221,0.0019373857616921137,-4.9115453961971935,0.7661290322580645,124,0.532258064516129,0.5,-4.9115453961971935,2.5,10.406440844786514,19,0.3333333333333333,22,0.45454545454545453,0.710785027814312,-1.941871961315866,-0.08826690733253936,-4.241871961315866,0.7727272727272727,22,0.45454545454545453,-0.35714286615338553,-4.241871961315866,2.5,-1.2874175279331657,22,0.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.600_maxday1,6807,4544,689,5.3364587158509655,False,125,0.584,1.194206383873985,5.935768814436731,0.04748615051549385,-3.1211981576946575,0.168,125,0.584,0.5,-3.1211981576946575,2.5,0.4211754328975218,19,0.8333333333333334,18,0.4444444444444444,0.6398391598705798,-2.016679757900275,-0.11203776432779305,-3.0,0.16666666666666666,18,0.4444444444444444,-0.3996932664522898,-3.0,2.5,-1.2396613742000109,18,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.400_maxday1,7659,4381,775,4.968444669240254,False,120,0.5666666666666667,1.1317888468205568,3.9104698826321176,0.032587249021934314,-3.424628911063876,0.25833333333333336,120,0.5666666666666667,0.5,-3.424628911063876,2.5,0.6393093605204453,18,0.8333333333333334,20,0.4,0.5584997974061697,-3.1620437797419565,-0.15810218898709782,-4.062043779741956,0.25,20,0.4,-0.6,-4.062043779741956,2.5,-0.7906278894734393,20,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.500_maxday1,8308,4507,724,5.180663786143415,False,121,0.5619834710743802,1.1371321977151634,4.0498988547977195,0.03347023846940264,-3.3226503840084325,0.4049586776859504,121,0.5619834710743802,0.5,-3.3226503840084325,2.5,0.617299367128236,18,1.0,21,0.5238095238095238,0.9166666666666669,-0.49999999999999956,-0.023809523809523787,-3.1,0.19047619047619047,21,0.5238095238095238,0.5,-3.1,2.5,-5.000000000000004,21,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_tp50_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30_clean1000_nopool_d50_win_wf2026_v1",
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