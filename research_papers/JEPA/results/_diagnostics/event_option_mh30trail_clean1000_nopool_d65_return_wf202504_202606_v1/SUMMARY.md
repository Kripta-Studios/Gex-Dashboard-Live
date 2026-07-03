# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 447,
  "win_rate": 0.5324384787472036,
  "profit_factor": 1.0813932213938147,
  "pnl_return": 9.483670773724473,
  "avg_return": 0.02121626571303014,
  "max_drawdown": -9.674550165503563,
  "call_rate": 0.3243847874720358,
  "days_with_trades": 225,
  "daily_win_rate": 0.48444444444444446,
  "median_daily_return": -0.053326384398093896,
  "daily_max_drawdown": -9.27992214970568,
  "top5_day_return": 12.682068565730852,
  "top5_share_of_pnl": 1.3372531447282927,
  "min_month_trades": 0,
  "positive_month_rate": 0.4
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 447,
    "win_rate": 0.5324384787472036,
    "profit_factor": 1.0813932213938147,
    "pnl_return": 9.483670773724473,
    "avg_return": 0.02121626571303014,
    "max_drawdown": -9.674550165503563,
    "call_rate": 0.3243847874720358,
    "days_with_trades": 225,
    "daily_win_rate": 0.48444444444444446,
    "median_daily_return": -0.053326384398093896,
    "daily_max_drawdown": -9.27992214970568,
    "top5_day_return": 12.682068565730852,
    "top5_share_of_pnl": 1.3372531447282927,
    "min_month_trades": 0,
    "positive_month_rate": 0.4
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202508,202508,202501,202501,202502,"202502,202503,202504,202505,202506,202507",202507,thr0.200_maxday1,765,4460,778,6.44176698983458,False,121,0.5206611570247934,1.399833165325986,11.66510994092128,0.09640586728034116,-2.5637556792898604,0.3305785123966942,121,0.5206611570247934,0.18117650349934888,-2.5637556792898604,9.467167975087099,0.8115798327691892,18,1.0,18,0.5,1.0648705937792087,0.35030120640772755,0.019461178133762642,-1.7999999999999998,0.05555555555555555,18,0.5,-0.16844661409976897,-1.7999999999999998,4.584417015883576,13.087071731484752,18,1.0
SPXW,202509,202509,"202501,202502",202502,202503,"202503,202504,202505,202506,202507,202508",202508,thr0.000_maxday2,1392,4611,814,6.681824036094498,False,249,0.5461847389558233,1.3335650858776726,19.330020766297366,0.07763060548713802,-5.556801604143683,0.4497991967871486,125,0.56,0.07617459716219799,-5.556801604143681,11.104579364399395,0.5744732247655241,39,0.8333333333333334,42,0.5476190476190477,1.4071022647393816,3.748044110670887,0.08923914549216397,-4.033998762001892,0.30952380952380953,21,0.5238095238095238,0.18571842261609273,-4.033998762001892,6.987584004307665,1.8643281130052956,42,1.0
SPXW,202510,202510,"202501,202502,202503",202503,202504,"202504,202505,202506,202507,202508,202509",202509,thr0.200_maxday1,2116,4701,852,7.345178376423176,False,121,0.6033057851239669,1.6770774631232048,17.13049683022929,0.1415743539688371,-2.4192893935735325,0.38016528925619836,121,0.6033057851239669,0.2996599307632437,-2.4192893935735325,7.225615799009052,0.42179837926582414,19,1.0,23,0.6956521739130435,1.5895369126825867,2.4760550332668636,0.10765456666377668,-1.8000000000000003,0.21739130434782608,23,0.6956521739130435,0.3375705745903672,-1.8000000000000003,2.827965741391063,1.1421255599718616,23,1.0
SPXW,202511,202511,"202501,202502,202503,202504",202504,202505,"202505,202506,202507,202508,202509,202510",202510,thr0.000_maxday2,2765,4904,648,6.727293617655585,False,256,0.5625,1.320367740907999,18.422892082255398,0.07196442219631015,-4.852951042466598,0.4453125,128,0.5546875,0.11305481531036654,-4.527219970592109,12.942302969028212,0.7025120112109873,40,0.8333333333333334,37,0.5945945945945946,1.5060953673805637,4.290908997283216,0.11597051344008692,-2.3999999999999995,0.4864864864864865,19,0.5263157894736842,0.03681810552423659,-2.4000000000000004,7.235530124254691,1.6862464640559514,37,1.0
SPXW,202512,202512,"202501,202502,202503,202504,202505",202505,202506,"202506,202507,202508,202509,202510,202511",202511,thr0.000_maxday3,3585,4732,842,9.553371516601644,False,374,0.5909090909090909,1.527274373320928,41.181109185157766,0.11010991760737371,-4.2330682228514345,0.4572192513368984,126,0.5952380952380952,0.2928712536746376,-4.2330682228514345,14.982815267827352,0.3638273850386566,55,0.8333333333333334,66,0.5303030303030303,0.9761008717902322,-0.400739111312425,-0.0060718047168549245,-6.835245813858247,0.4696969696969697,22,0.5454545454545454,0.14243579662926376,-6.132723041140897,7.402195129092794,-18.471356850721467,66,0.0
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday3,4362,4797,779,7.943714218983317,False,381,0.5669291338582677,1.3333509974693263,29.146004669173216,0.07649869991908981,-5.941209069573006,0.4146981627296588,128,0.59375,0.19630991883878002,-5.3273510569387845,17.954057081122116,0.6160040556128621,55,1.0,60,0.5833333333333334,1.0817185558288152,1.1125829629789488,0.018543049382982478,-3.385657503525998,0.4166666666666667,20,0.45,-0.07853089352770892,-3.385657503525998,5.969217931068207,5.365189050788252,60,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.460_maxday2,5225,4713,616,6.324630083304032,False,230,0.5652173913043478,1.2901166477850294,16.024874439863925,0.06967336712984315,-6.063767964579597,0.008695652173913044,120,0.5,-0.003909491610527338,-6.063767964579574,11.965981025369064,0.7467129349607979,32,1.0,37,0.43243243243243246,0.8763690203028441,-1.5577503441841676,-0.04210136065362615,-4.2,0.0,19,0.3684210526315789,-0.6,-4.152076663904385,9.05353339780654,-5.811928356560948,37,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.000_maxday2,6003,4551,793,6.611655009707486,False,247,0.5708502024291497,1.3505163015921668,20.305977960815753,0.08221043708832289,-5.652787046526761,0.6194331983805668,124,0.5,-0.0094633062124031,-5.6527870465267664,15.865443765386292,0.7813188705317067,37,0.6666666666666666,44,0.5227272727272727,1.3249061896434968,3.571334048940447,0.08116668293046471,-5.221198740610854,0.6363636363636364,22,0.36363636363636365,-0.1524572904257131,-4.621198740610854,8.674452072233263,2.42891086450085,44,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.104_maxday2,6817,4530,793,8.617165008170067,False,244,0.6065573770491803,1.6012620405586704,33.536086310037405,0.13744297668048117,-5.4,0.1598360655737705,123,0.5528455284552846,0.28903734588470675,-4.799999999999997,17.254940534515995,0.5145186106391778,37,1.0,40,0.525,0.9757773000728278,-0.25814057638629784,-0.006453514409657446,-2.9146771643624048,0.125,20,0.5,0.07174566389210046,-2.9146771643624048,6.2631886303706885,-24.262704910823697,40,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.200_maxday2,7669,4471,783,9.171628646779661,False,245,0.6163265306122448,1.6916754503514244,36.54966129677007,0.14918229100722477,-4.656141026190659,0.2816326530612245,123,0.5691056910569106,0.32404756091889875,-4.098246369657972,15.500383705206927,0.4240910354640335,37,1.0,40,0.425,0.7529589259148052,-3.260942177924573,-0.08152355444811432,-4.868833926144195,0.325,20,0.4,-0.19525990268173288,-4.268833926144195,4.795357690816782,-1.4705436126036395,40,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.000_maxday2,8317,4606,736,7.979484987482902,False,247,0.6032388663967612,1.4835707201871675,25.91910383684431,0.104935643064147,-4.1128016275250125,0.43724696356275305,124,0.5403225806451613,0.1993556057854221,-4.112801627524995,12.79902014738282,0.49380643049814327,38,1.0,40,0.525,0.9484225108757761,-0.5879833760161558,-0.014699584400403896,-6.4228709794621395,0.15,21,0.42857142857142855,-0.13961745672246606,-5.962488436184606,6.608179308639584,-11.23871792670889,40,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_v1",
    "tickers": [
      "SPXW",
      "QQQ",
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 6,
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
    "lgb_jobs": 6,
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
  "feature_count": 245,
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
  "data_rows": 39667
}
```