# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 467,
  "win_rate": 0.5053533190578159,
  "profit_factor": 1.1529901624051035,
  "pnl_return": 20.718245891516723,
  "avg_return": 0.04436455223022853,
  "max_drawdown": -13.03260858878992,
  "call_rate": 0.2569593147751606,
  "days_with_trades": 280,
  "daily_win_rate": 0.5035714285714286,
  "median_daily_return": 0.05476807051763677,
  "daily_max_drawdown": -13.032608588789921,
  "top5_day_return": 21.12642698720415,
  "top5_share_of_pnl": 1.0197015277173904,
  "min_month_trades": 13,
  "positive_month_rate": 0.7333333333333333
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 467,
    "win_rate": 0.5053533190578159,
    "profit_factor": 1.1529901624051035,
    "pnl_return": 20.718245891516723,
    "avg_return": 0.04436455223022853,
    "max_drawdown": -13.03260858878992,
    "call_rate": 0.2569593147751606,
    "days_with_trades": 280,
    "daily_win_rate": 0.5035714285714286,
    "median_daily_return": 0.05476807051763677,
    "daily_max_drawdown": -13.032608588789921,
    "top5_day_return": 21.12642698720415,
    "top5_share_of_pnl": 1.0197015277173904,
    "min_month_trades": 13,
    "positive_month_rate": 0.7333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.200_maxday1,740,1354,646,4.571526491128104,False,36,0.5277777777777778,1.1954122742380375,1.8750387100440626,0.05208440861233507,-3.0000000000000004,0.25,36,0.5277777777777778,0.2768813871897253,-3.0000000000000004,4.974295613371574,2.652902890338024,16,1.0,18,0.5,1.2810795152695538,1.5178293824555902,0.08432385458086612,-1.7999999999999998,0.1111111111111111,18,0.5,-0.04103370051808258,-1.7999999999999998,4.56644790769319,3.008538351198244,18,1.0
SPY,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr0.300_maxday1,1373,1367,814,4.7111585539299865,False,39,0.5641025641025641,1.296876972647638,2.898531586582631,0.07432132273288798,-3.6667072292749934,0.28205128205128205,39,0.5641025641025641,0.28179194575191846,-3.6667072292749934,5.312616435682554,1.832864772036564,19,1.0,21,0.5238095238095238,0.9540932665881228,-0.25803854541683635,-0.012287549781754111,-2.102702748418463,0.2857142857142857,21,0.5238095238095238,0.25,-2.102702748418463,3.5700189781017695,-13.835215867981075,21,0.0
SPY,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr-999.000_maxday1,2094,1460,777,6.714863507579662,False,41,0.6585365853658537,2.0534316789821845,8.684958973785871,0.21182826765331395,-0.9219100717251489,0.3902439024390244,41,0.6585365853658537,0.34259255579960346,-0.9219100717251489,6.735794452371607,0.7755700945395944,20,1.0,20,0.5,1.0288901727059043,0.15338388856522644,0.007669194428261322,-2.4,0.55,20,0.5,-0.04499997695287067,-2.4,4.134595459264359,26.95586542980441,20,1.0
SPY,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr0.244_maxday3,2740,1591,870,7.519523463831795,False,92,0.6195652173913043,2.0549988626093163,21.334421468564628,0.23189588552787638,-5.019630579500864,0.358695652173913,34,0.6764705882352942,0.711575208437627,-4.419630579500864,16.045199591738417,0.7520803699964559,41,1.0,41,0.34146341463414637,0.5167791607747974,-7.828177595448283,-0.19093116086459228,-7.8281775954482775,0.14634146341463414,16,0.3125,-0.9149122614389419,-7.828177595448283,5.9379672521478195,-0.7585376263819651,41,0.0
SPY,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr0.400_maxday3,3554,1647,786,6.792218921234003,False,40,0.6,2.3320355450178694,12.303613151565667,0.30759032878914166,-3.6,0.225,23,0.5217391304347826,0.26923086622057935,-3.5999999999999996,12.550583363759038,1.0200729825581312,18,1.0,13,0.46153846153846156,0.7575931089225785,-1.0181089425251706,-0.0783160725019362,-3.0285714703859115,0.15384615384615385,7,0.42857142857142855,-0.028571470385911346,-2.4285714703859114,0.7818910574748293,-0.7679836850617769,13,0.0
SPY,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr0.000_maxday1,4331,1656,820,5.124857228711991,False,43,0.4883720930232558,1.3480060411942307,4.080466654787376,0.09489457336714828,-2.733870983247826,0.4418604651162791,43,0.4883720930232558,0.0,-2.733870983247826,8.546137822998045,2.0944020735891455,21,1.0,21,0.42857142857142855,0.759298999611652,-1.5923875521915054,-0.07582797867578597,-3.3601505163797194,0.47619047619047616,21,0.42857142857142855,-0.6,-3.3601505163797194,3.665579152996493,-2.3019390901114374,21,0.0
SPY,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr0.400_maxday2,5201,1606,852,5.372020938833285,False,70,0.6,1.5328843669440446,8.723556437153738,0.12462223481648196,-6.0330840379059545,0.1,36,0.5555555555555556,0.33124105189179837,-6.033084037905957,9.388882819191135,1.076267791333792,32,1.0,37,0.5675675675675675,1.4818990895096211,4.507460180528993,0.1218232481224052,-2.4000000000000004,0.0,19,0.5263157894736842,0.05647490837393809,-1.3312499243300389,8.211487278715884,1.8217548130956953,37,1.0
SPY,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr0.000_maxday1,5987,1672,647,5.760839897826934,False,44,0.5909090909090909,1.6589785919941835,7.093005948306394,0.16120468064332713,-2.976425003190298,0.4090909090909091,44,0.5909090909090909,0.28173080396524475,-2.976425003190298,8.643960310024479,1.2186596730668762,21,1.0,19,0.631578947368421,1.6701012860532778,2.814425401423766,0.148127652706514,-1.7058881477048926,0.5789473684210527,19,0.631578947368421,0.3500001059638158,-1.7058881477048926,4.326383915486435,1.5372174772505238,19,1.0
SPY,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr0.352_maxday3,6807,1499,847,8.0727623661064,False,68,0.6323529411764706,2.348135632654192,20.222034489812874,0.297382860144307,-2.4000000000000057,0.1323529411764706,31,0.6129032258064516,0.3653846624099779,-2.099350733014802,17.341152238590112,0.8575374672279367,32,1.0,50,0.52,1.263789378962058,3.7985670570536354,0.0759713411410727,-4.080458592133521,0.14,22,0.5454545454545454,0.08004925131861096,-4.042704382881314,9.343537499346946,2.4597532066721697,50,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.086_maxday3,7659,1494,779,9.105642007206198,False,115,0.6608695652173913,2.2897610890310824,30.18040948332736,0.26243834333328137,-3.1197968079930334,0.14782608695652175,40,0.65,0.5523872558824049,-3.1197968079930263,16.431127873671493,0.5444302497866566,52,1.0,59,0.5084745762711864,1.3701710866034364,6.057756264548545,0.10267383499234822,-2.446092818594316,0.1694915254237288,20,0.55,0.22831061212583537,-1.915478152308422,9.539175930211739,1.5747044802771786,59,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday2,8306,1626,615,7.572203745104968,False,84,0.6071428571428571,1.9797050247289059,19.39815948963233,0.2309304701146706,-3.2113910058096735,0.19047619047619047,42,0.5952380952380952,0.23132093588209968,-2.7420927051590187,14.883627129041919,0.7672700668842691,40,1.0,38,0.5,1.2489137362557363,2.822150821022807,0.07426712686902123,-4.737866939264863,0.18421052631578946,19,0.47368421052631576,-0.31470598712511666,-4.737866939264865,10.550925665154928,3.7386115534856676,38,1.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.284_maxday3,9153,1394,799,6.791634990520595,False,70,0.6142857142857143,2.0120143189649284,16.33175242008677,0.2333107488583824,-5.337866939264874,0.2714285714285714,33,0.6363636363636364,0.6718281557682462,-5.337866939264867,11.637639329095999,0.7125775011616401,35,1.0,53,0.5094339622641509,1.034711076530088,0.5414927938693747,0.01021684516734669,-3.2063787063689344,0.5094339622641509,21,0.5238095238095238,0.053061232661335445,-3.2063787063689344,6.4966673489065245,11.997698625835689,53,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.247_maxday1,9932,1414,689,6.458024411664083,False,40,0.675,2.0794353134247947,7.9469358190139925,0.19867339547534982,-1.9100766069644228,0.6,40,0.675,0.3346990638733248,-1.9100766069644228,6.543659971181553,0.8234192549441591,18,1.0,18,0.5,1.0576480270468096,0.31129934605277065,0.017294408114042814,-1.8,0.2222222222222222,18,0.5,-0.1500000055879353,-1.8,4.342052584034828,13.948158385462124,18,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr-0.100_maxday2,10547,1488,775,5.764345692367623,False,80,0.5375,1.585220647102527,12.656006452643144,0.1582000806580393,-6.640948277953822,0.5375,40,0.525,0.03341546417086416,-6.316960567641534,14.399509830585908,1.1377609425585147,36,1.0,40,0.625,1.6335757549116188,5.702181794204568,0.1425545448551142,-3.8742313311581293,0.375,20,0.6,0.3411764615650409,-3.874231331158132,7.268716459070305,1.2747254860337651,40,1.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr0.050_maxday1,11346,1464,724,6.521911397862323,False,38,0.631578947368421,2.069131003608399,8.691252746560307,0.22871717754106072,-1.799999999999999,0.3684210526315789,38,0.631578947368421,0.2908065624613483,-1.799999999999999,9.19572248632028,1.0580433862034013,18,1.0,19,0.42105263157894735,1.4966243171744755,3.188411597373245,0.167811136703855,-2.691860452221819,0.10526315789473684,19,0.42105263157894735,-0.6,-2.691860452221819,8.447119032713662,2.6493188770461047,19,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_v1_SPY",
    "tickers": [
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": false,
    "delta_bucket": 35,
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