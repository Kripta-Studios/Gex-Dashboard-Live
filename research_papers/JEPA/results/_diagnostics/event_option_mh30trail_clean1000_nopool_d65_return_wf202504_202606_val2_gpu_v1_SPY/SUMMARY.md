# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 455,
  "win_rate": 0.545054945054945,
  "profit_factor": 1.0545721793400216,
  "pnl_return": 6.198962252352799,
  "avg_return": 0.013624092862313844,
  "max_drawdown": -8.760311724129723,
  "call_rate": 0.34285714285714286,
  "days_with_trades": 296,
  "daily_win_rate": 0.5033783783783784,
  "median_daily_return": 0.009051837840955923,
  "daily_max_drawdown": -8.284423375911771,
  "top5_day_return": 12.423531827003941,
  "top5_share_of_pnl": 2.0041309046991898,
  "min_month_trades": 18,
  "positive_month_rate": 0.6
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 455,
    "win_rate": 0.545054945054945,
    "profit_factor": 1.0545721793400216,
    "pnl_return": 6.198962252352799,
    "avg_return": 0.013624092862313844,
    "max_drawdown": -8.760311724129723,
    "call_rate": 0.34285714285714286,
    "days_with_trades": 296,
    "daily_win_rate": 0.5033783783783784,
    "median_daily_return": 0.009051837840955923,
    "daily_max_drawdown": -8.284423375911771,
    "top5_day_return": 12.423531827003941,
    "top5_share_of_pnl": 2.0041309046991898,
    "min_month_trades": 18,
    "positive_month_rate": 0.6
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.500_maxday2,740,1354,646,5.654802490884361,False,41,0.6097560975609756,1.8080120260622334,6.104208508695226,0.14888313435842015,-3.67499997516473,0.7560975609756098,22,0.5454545454545454,0.21273549310134177,-3.6749999751647326,7.4617455161308275,1.2223936167157197,6,1.0,27,0.4444444444444444,0.6574942591688328,-2.917255416637834,-0.10804649691251236,-5.018799933825594,0.4074074074074074,16,0.4375,-0.22780581944262046,-5.018799933825594,4.183789790710653,-1.4341527200016353,27,0.0
SPY,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr0.100_maxday1,1373,1367,814,3.872839796617625,False,41,0.5121951219512195,1.1465943369174052,1.431500423213214,0.034914644468614975,-3.7195462231248952,0.4146341463414634,41,0.5121951219512195,0.25,-3.7195462231248952,4.056515923082619,2.8337511168716043,20,0.5,21,0.6190476190476191,1.5324602456509393,2.3080949027529307,0.10990928108347289,-1.84390925680307,0.3333333333333333,21,0.6190476190476191,0.18835614313214077,-1.84390925680307,4.119282005278696,1.7847108454533263,21,1.0
SPY,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr0.050_maxday1,2094,1460,777,5.721389178107234,False,41,0.6341463414634146,1.841296519427631,6.584505873643664,0.16059770423521133,-3.758970721288688,0.34146341463414637,41,0.6341463414634146,0.2772727948293512,-3.758970721288688,4.623763951739807,0.7022188210428549,20,1.0,20,0.75,1.9661615187300943,2.8984845561902843,0.14492422780951422,-1.2000000000000002,0.45,20,0.75,0.2799505003091969,-1.2000000000000002,3.510203400389333,1.2110478190724192,20,1.0
SPY,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr0.156_maxday1,2740,1591,870,4.775792167647802,False,40,0.6,1.3260144554602666,2.7444486285540926,0.06861121571385231,-3.511144658219096,0.325,40,0.6,0.2670189029925867,-3.511144658219096,4.332219359372502,1.578539060377648,19,1.0,21,0.42857142857142855,0.7304985632416828,-1.602561845594133,-0.07631246883781587,-2.379577008835009,0.2857142857142857,21,0.42857142857142855,-0.29090913228752113,-2.379577008835009,3.0063777633287816,-1.875982366355539,21,0.0
SPY,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr0.114_maxday3,3554,1647,786,6.532838178514165,False,124,0.5887096774193549,1.5792177369292446,14.597088658416018,0.11771845692270982,-4.710351598832546,0.5161290322580645,42,0.6428571428571429,0.605779702077225,-4.041211809037892,10.666207542482335,0.7307078686771341,58,1.0,59,0.6101694915254238,1.2330991743849202,2.724232144882258,0.04617342618444505,-3.8636148392744927,0.576271186440678,21,0.42857142857142855,-0.07953024009933818,-3.2636148392744926,8.115615756550529,2.9790470580110155,59,1.0
SPY,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr0.200_maxday2,4331,1656,820,5.159114437757834,False,69,0.5797101449275363,1.2353217194662551,3.7944024809337273,0.05499134030338735,-2.7265208029318,0.5652173913043478,38,0.5,0.0360145420914712,-2.5522784614735996,8.25801564721163,2.176367870489979,32,1.0,30,0.43333333333333335,0.6705352148815606,-3.1290655881990803,-0.10430218627330268,-4.76373660633857,0.5,16,0.5,-0.11345707801009497,-4.16373660633857,4.651218246614291,-1.486455977195185,30,0.0
SPY,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr0.569_maxday1,5201,1606,852,5.4278646989561725,False,33,0.6060606060606061,1.550858111797535,3.2989192972801016,0.09996725143273034,-1.49089458913244,0.0,33,0.6060606060606061,0.2746913711974903,-1.49089458913244,4.610816190888991,1.397674745996522,13,1.0,23,0.6521739130434783,1.3325741211191309,1.5963557813718285,0.06940677310312297,-1.5027767171529511,0.0,23,0.6521739130434783,0.3204225961047271,-1.5027767171529511,3.0335814038476103,1.9003166081440201,23,1.0
SPY,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr0.000_maxday1,5987,1672,648,4.87144081903468,False,44,0.5454545454545454,1.2059800850841418,1.9548259397937502,0.044427862268039776,-2.052777874359374,0.5909090909090909,44,0.5454545454545454,0.22712422073526628,-2.052777874359374,4.531254591051028,2.3179836622840764,21,1.0,19,0.42105263157894735,0.66345130705685,-2.2212213734247905,-0.11690638807498897,-2.9922843921921785,0.6842105263157895,19,0.42105263157894735,-0.6,-2.9922843921921785,3.2281095427063695,-1.4533038360463406,19,0.0
SPY,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr0.050_maxday2,6807,1500,850,6.009750833649004,False,80,0.65,1.5671629662961684,9.203920601909337,0.11504900752386671,-3.58273750559111,0.225,42,0.5238095238095238,0.18432564636385246,-3.58273750559111,8.142403502835306,0.884666856116314,35,1.0,44,0.6136363636363636,1.5395302226080634,4.654288970872303,0.10577929479255234,-2.161543546752817,0.18181818181818182,22,0.45454545454545453,-0.03871162010031681,-1.9020015252034161,6.733011482985113,1.4466251505056889,44,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.100_maxday2,7659,1498,779,6.503005205777646,False,80,0.6,1.7820415441183473,13.71345551321135,0.17141819391514188,-4.576987724339192,0.225,41,0.5121951219512195,0.559957443546327,-4.576987724339198,12.03806975704934,0.8778290596015011,36,1.0,40,0.6,1.4716252313604659,4.527602221060471,0.11319005552651178,-3.2671897009591513,0.375,20,0.45,-0.017318594086867423,-2.9229406310962647,8.374120231883195,1.8495706608081348,40,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr0.050_maxday2,8307,1629,615,6.258149527033143,False,84,0.6071428571428571,1.6377815699501381,10.665594380823244,0.1269713616764672,-3.58708862459903,0.40476190476190477,42,0.5,0.08410962315373904,-3.181088678004792,9.144205844709072,0.8573554851429911,40,1.0,38,0.5263157894736842,1.0478036356560547,0.4871519526324415,0.012819788227169513,-2.867614965739836,0.21052631578947367,19,0.5263157894736842,0.09594599819252936,-2.8641244101673315,5.777871495282767,11.860511826054815,38,1.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.300_maxday2,9157,1394,799,6.27345792108099,False,48,0.6458333333333334,1.8265607722781434,8.1360283928329,0.16950059151735208,-2.043230728708073,0.25,27,0.6296296296296297,0.26162782638636584,-1.443230728708075,8.029971771941439,0.9869645709465705,23,1.0,35,0.5714285714285714,1.2417120407126772,1.818376306433359,0.05195360875523883,-2.7299329997338404,0.4857142857142857,19,0.5263157894736842,0.11699673083273943,-2.12993299973384,5.488994182635504,3.018623902662839,35,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.112_maxday1,9936,1414,689,5.925030806864816,False,40,0.575,1.8109395124094796,6.597791404700597,0.16494478511751492,-2.532060420875866,0.55,40,0.575,0.31507835919535765,-2.532060420875866,6.182332480485748,0.9370306063451997,18,1.0,18,0.6666666666666666,2.1272994758979658,3.2515245789848963,0.1806402543880498,-1.1657282861199043,0.4444444444444444,18,0.6666666666666666,0.3114549102390507,-1.1657282861199043,4.018922886147064,1.2360118426051523,18,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.320_maxday1,10551,1488,775,6.3416659941561475,False,31,0.6129032258064516,2.125365798412623,6.034308424064378,0.1946551104536896,-1.1999999999999993,0.3548387096774194,31,0.6129032258064516,0.3309524209591286,-1.1999999999999993,5.365371341574216,0.8891443665984174,15,1.0,20,0.35,0.4997746924035265,-3.593867980121506,-0.1796933990060753,-3.593867980121506,0.05,20,0.35,-0.6,-3.593867980121506,2.9972199087902327,-0.8339816391054239,20,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr-0.100_maxday2,11350,1464,724,4.070479701512012,False,76,0.5657894736842105,1.0937890909647634,1.7875025892246463,0.02351977091085061,-3.899545787150254,0.2236842105263158,38,0.39473684210526316,-0.08710357706322658,-3.355258320357044,8.341057460439304,4.666319092750155,36,0.5,40,0.425,0.6512744728143467,-4.603176958850625,-0.11507942397126562,-5.822434632554848,0.1,21,0.3333333333333333,-0.17786885758491977,-5.076980537306642,5.355644180121667,-1.16346693338049,40,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_v1_SPY",
    "tickers": [
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": false,
    "delta_bucket": 65,
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
  "data_rows": 13538
}
```