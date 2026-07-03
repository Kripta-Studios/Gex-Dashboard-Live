# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 650,
  "win_rate": 0.5046153846153846,
  "profit_factor": 1.2549710107937033,
  "pnl_return": 48.93307414219575,
  "avg_return": 0.075281652526455,
  "max_drawdown": -10.058456277891324,
  "call_rate": 0.30615384615384617,
  "days_with_trades": 282,
  "daily_win_rate": 0.5177304964539007,
  "median_daily_return": 0.07168361418397706,
  "daily_max_drawdown": -9.458456277891273,
  "top5_day_return": 22.76114309468673,
  "top5_share_of_pnl": 0.4651484398577657,
  "min_month_trades": 9,
  "positive_month_rate": 0.7333333333333333
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 650,
    "win_rate": 0.5046153846153846,
    "profit_factor": 1.2549710107937033,
    "pnl_return": 48.93307414219575,
    "avg_return": 0.075281652526455,
    "max_drawdown": -10.058456277891324,
    "call_rate": 0.30615384615384617,
    "days_with_trades": 282,
    "daily_win_rate": 0.5177304964539007,
    "median_daily_return": 0.07168361418397706,
    "daily_max_drawdown": -9.458456277891273,
    "top5_day_return": 22.76114309468673,
    "top5_share_of_pnl": 0.4651484398577657,
    "min_month_trades": 9,
    "positive_month_rate": 0.7333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.383_maxday3,740,1354,646,4.76237597337656,False,81,0.5308641975308642,1.202146486210416,4.5250051519213095,0.05586426113483098,-5.207229419209016,0.2839506172839506,32,0.5625,0.2202192044214083,-4.60722941920902,9.318837860437775,2.0594093371321383,33,1.0,54,0.5,1.2889063921631312,4.680283553042722,0.08667191764893929,-2.9999999999999982,0.05555555555555555,20,0.55,0.05355397526925715,-2.6699999570846558,12.529821161890414,2.677150010226323,54,1.0
SPY,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr0.500_maxday1,1373,1367,814,6.477414434708193,False,36,0.6111111111111112,2.1668985727822365,9.317431447320036,0.25881754020333436,-2.687499965075402,0.19444444444444445,36,0.6111111111111112,0.3256425241672639,-2.687499965075402,8.667222160831775,0.9302158228730215,17,1.0,9,0.3333333333333333,0.4003684865107443,-2.1586734485613204,-0.23985260539570227,-2.158673448561321,0.3333333333333333,9,0.3333333333333333,-0.6,-2.158673448561321,0.24132655143867954,-0.11179391287714924,9,0.0
SPY,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr-999.000_maxday2,2094,1460,777,6.545666569637068,False,81,0.5802469135802469,1.6571023621607952,12.465169714569068,0.15389098413048233,-3.0779131879542465,0.3950617283950617,41,0.5609756097560976,0.15000000000000002,-2.4779131879542495,11.677386472116519,0.9368012421417895,39,1.0,40,0.575,1.2403913711464578,2.323921659013,0.058098041475325005,-3.6,0.65,20,0.65,0.3120397983555899,-2.7100000381469727,5.263060411414606,2.264732286048703,40,1.0
SPY,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr0.200_maxday1,2740,1591,870,6.911428315808026,False,36,0.6111111111111112,2.3159020479034984,9.916426648368256,0.2754562957880071,-1.5065825126504233,0.4444444444444444,36,0.6111111111111112,0.2886905128573434,-1.5065825126504233,9.102786928220546,0.9179503112361956,16,1.0,20,0.65,2.341287028270551,5.633405518736314,0.2816702759368157,-1.425000023283065,0.45,20,0.65,0.4119046969839074,-1.425000023283065,6.1207500601644345,1.086509756808248,20,1.0
SPY,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr0.000_maxday3,3554,1647,786,7.258226980433515,False,123,0.5853658536585366,1.6756938069422012,20.135675415413154,0.16370467817409068,-4.385467035140435,0.5691056910569106,42,0.6190476190476191,0.2778574334239494,-4.31767690897108,16.091399166731367,0.7991487166312765,58,1.0,63,0.5238095238095238,1.3461317718357741,6.2183325275545425,0.09870369091356417,-4.512011625090954,0.7301587301587301,21,0.5238095238095238,0.06313009197829456,-4.172649881140211,13.023440106913316,2.09436212187176,63,1.0
SPY,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr0.100_maxday3,4331,1656,820,5.909313408000045,False,111,0.5135135135135135,1.3361083606642776,10.889910885522607,0.09810730527497843,-4.242307630586904,0.5045045045045045,40,0.5,0.02323167126370118,-3.6004157952954774,17.82934036532795,1.6372347352291783,54,1.0,59,0.4745762711864407,1.1173267833347835,2.182278170026981,0.03698776559367765,-7.393031722823316,0.288135593220339,20,0.5,0.194458537587326,-7.393031722823315,11.64276324558946,5.335141690688091,59,1.0
SPY,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr-0.200_maxday3,5201,1606,852,6.508469561804172,False,126,0.5555555555555556,1.560773879881363,18.074634648383498,0.14344948133637697,-6.499033104267445,0.18253968253968253,42,0.6190476190476191,0.25361938980961524,-6.499033104267452,13.724105084373662,0.7593019361860835,63,1.0,68,0.5147058823529411,1.4538506044658508,8.66117884253335,0.12737027709607868,-4.1999999999999975,0.0,23,0.4782608695652174,-0.1514926515036603,-3.2525061495874334,17.137489061176733,1.9786554893680164,68,1.0
SPY,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr0.115_maxday3,5987,1672,647,6.5964110775507105,False,127,0.5590551181102362,1.4809600684830164,15.570838835639888,0.12260503020188888,-4.350116268663892,0.41732283464566927,44,0.5,0.09683957656734826,-3.7501162686638914,16.268183670286977,1.044785309385577,60,1.0,50,0.56,2.048545547912676,13.840801232447319,0.2768160246489464,-4.084870018305679,0.44,18,0.6111111111111112,0.4031353358361598,-3.1983203859608036,15.922486808488994,1.1504021003611793,50,1.0
SPY,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr0.168_maxday3,6807,1499,847,9.707795023831087,False,111,0.6486486486486487,2.4447014400325306,33.53958823784397,0.30215845259318896,-2.4000000000000057,0.3783783783783784,40,0.675,0.6552185694597079,-1.8000000000000007,17.655246906742217,0.5264002283373634,52,1.0,64,0.546875,1.4555122669681018,7.9259134452449755,0.12384239758195274,-5.26066398506582,0.25,22,0.6363636363636364,0.32672465788847616,-4.163605220664111,10.743966037183885,1.3555492513773986,64,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.136_maxday3,7659,1494,779,8.475923089436435,False,117,0.5982905982905983,2.03794517744723,28.82919482773343,0.24640337459601222,-4.436742747795048,0.23076923076923078,39,0.6923076923076923,0.6519481020223908,-4.43674274779503,18.435486367158965,0.6394728148780691,54,1.0,54,0.5185185185185185,1.3957207403960763,6.173243550178789,0.1143193250033109,-2.4000000000000004,0.3333333333333333,19,0.5263157894736842,0.07886174721100059,-1.922489586724823,9.218826589817972,1.4933521599922908,54,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday2,8306,1626,615,8.262325556250119,False,84,0.6190476190476191,2.243143884609501,23.868362584502414,0.2841471736250287,-3.266666749450902,0.13095238095238096,42,0.6428571428571429,0.5152837792600684,-2.8409910824829794,16.419310775912322,0.6879110671200078,40,1.0,38,0.34210526315789475,0.5806775018014232,-6.289837472978651,-0.16552203876259608,-6.888844655549017,0.15789473684210525,19,0.2631578947368421,-1.2,-6.888844655549018,7.67065414326926,-1.219531375210034,38,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.330_maxday3,9153,1394,799,8.881193842636026,False,66,0.6060606060606061,2.7317048432558004,27.014595554790482,0.4093120538604618,-3.314864834387702,0.3787878787878788,31,0.7096774193548387,0.37894752940312837,-2.400000000000002,19.38418920001326,0.7175450456290794,31,1.0,40,0.5,1.0550641699504528,0.6607700394054332,0.01651925098513583,-4.762372885960572,0.45,18,0.6111111111111112,0.36151787553159764,-4.762372885960571,6.294864462742052,9.526558541313749,40,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.071_maxday2,9932,1414,689,8.223217403158298,False,81,0.6419753086419753,2.3212544978596976,22.422289364328943,0.2768183872139376,-3.015314558089006,0.5925925925925926,41,0.6097560975609756,0.6917561806295351,-2.95979507251252,14.673420008816322,0.6544122132399155,37,1.0,36,0.3611111111111111,0.8267903468669672,-2.3902932132358528,-0.06639703370099591,-8.199060956243397,0.3055555555555556,18,0.3333333333333333,-0.2519608311770456,-7.599060956243397,7.952751695131436,-3.3271029893296733,36,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.211_maxday2,10547,1488,775,7.541940427785928,False,76,0.5394736842105263,1.9714605609698619,20.400671780367105,0.2684298918469356,-3.6000000000000085,0.47368421052631576,38,0.5,0.17857142188111136,-3.599999999999998,18.524643821161433,0.9080408733887334,34,1.0,40,0.575,1.225149578089176,2.2965256965095944,0.057413142412739857,-2.0360648656120213,0.1,20,0.55,0.12097463140650422,-1.4360648693373108,5.1842841422839525,2.2574466073527315,40,1.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr0.400_maxday1,11346,1464,724,6.96535699619734,False,31,0.6129032258064516,2.3790972847493705,9.929500450195464,0.32030646613533753,-1.1999999999999993,0.06451612903225806,31,0.6129032258064516,0.321428556223305,-1.1999999999999993,9.202777202565379,0.9268117010241155,12,1.0,15,0.4,0.8472637115330685,-0.8247759577214302,-0.054985063848095345,-2.3300000429153442,0.0,15,0.4,-0.6,-2.3300000429153442,4.2979513957923015,-5.211053202455186,15,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_v1_SPY",
    "tickers": [
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": false,
    "delta_bucket": 25,
    "label_mode": "return",
    "clip_return": 5.0,
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
    "min_call_rate": 0.0,
    "max_call_rate": 1.0,
    "cooldown_minutes": 30,
    "objective": "regression_l1",
    "n_estimators": 160,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 60,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 5.0,
    "lgb_jobs": 2,
    "lgb_device_type": "gpu",
    "threshold_grid": [
      -999.0,
      -0.2,
      -0.1,
      0.0,
      0.05,
      0.1,
      0.2,
      0.3,
      0.4,
      0.5,
      0.75,
      1.0
    ],
    "threshold_quantiles": [
      0.3,
      0.5,
      0.7,
      0.85,
      0.95,
      0.98
    ],
    "max_day_grid": [
      1,
      2,
      3
    ],
    "feature_include_prefixes": [],
    "feature_exclude_prefixes": [],
    "live_observable_features_only": true,
    "entry_time_min_et": "10:00",
    "allow_invalid_val_deploy": false,
    "deploy_month": "",
    "deploy_select_end_month": "",
    "export_deploy_model": false,
    "exclude_months": [],
    "skip_walkforward": false,
    "resume": true,
    "seed": 20260617
  },
  "feature_count": 243,
  "features": [
    "dte_days",
    "minute",
    "spot",
    "underlying_volume",
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
      "threshold": -0.2,
      "max_trades_per_day": 1
    },
    {
      "threshold": -0.2,
      "max_trades_per_day": 2
    },
    {
      "threshold": -0.2,
      "max_trades_per_day": 3
    },
    {
      "threshold": -0.1,
      "max_trades_per_day": 1
    },
    {
      "threshold": -0.1,
      "max_trades_per_day": 2
    },
    {
      "threshold": -0.1,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.0,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.05,
      "max_trades_per_day": 3
    },
    {
      "threshold": 0.1,
      "max_trades_per_day": 1
    },
    {
      "threshold": 0.1,
      "max_trades_per_day": 2
    },
    {
      "threshold": 0.1,
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
    },
    {
      "threshold": 1.0,
      "max_trades_per_day": 1
    },
    {
      "threshold": 1.0,
      "max_trades_per_day": 2
    },
    {
      "threshold": 1.0,
      "max_trades_per_day": 3
    }
  ],
  "data_rows": 13534
}
```