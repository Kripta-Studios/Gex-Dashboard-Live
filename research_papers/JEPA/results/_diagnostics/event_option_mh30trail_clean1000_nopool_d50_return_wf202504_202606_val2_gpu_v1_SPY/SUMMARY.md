# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 479,
  "win_rate": 0.511482254697286,
  "profit_factor": 1.0090693553773078,
  "pnl_return": 1.2146344468217616,
  "avg_return": 0.0025357712877281035,
  "max_drawdown": -12.058441316964528,
  "call_rate": 0.25052192066805845,
  "days_with_trades": 274,
  "daily_win_rate": 0.5036496350364964,
  "median_daily_return": 0.056649058003378494,
  "daily_max_drawdown": -12.058441316964528,
  "top5_day_return": 14.701941151677655,
  "top5_share_of_pnl": 12.104004781147998,
  "min_month_trades": 7,
  "positive_month_rate": 0.4666666666666667
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 479,
    "win_rate": 0.511482254697286,
    "profit_factor": 1.0090693553773078,
    "pnl_return": 1.2146344468217616,
    "avg_return": 0.0025357712877281035,
    "max_drawdown": -12.058441316964528,
    "call_rate": 0.25052192066805845,
    "days_with_trades": 274,
    "daily_win_rate": 0.5036496350364964,
    "median_daily_return": 0.056649058003378494,
    "daily_max_drawdown": -12.058441316964528,
    "top5_day_return": 14.701941151677655,
    "top5_share_of_pnl": 12.104004781147998,
    "min_month_trades": 7,
    "positive_month_rate": 0.4666666666666667
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.400_maxday2,740,1354,646,5.214912858220442,False,51,0.5882352941176471,1.369148454767021,4.459712385443674,0.08744534089105244,-2.9835491003771435,0.4117647058823529,28,0.6071428571428571,0.11297679990328235,-2.3999999999999995,7.618502800367802,1.7082946481558532,20,1.0,34,0.4411764705882353,0.8981440401371894,-1.1100132489276753,-0.0326474484978728,-3.148342529792444,0.14705882352941177,18,0.4444444444444444,-0.20835497808548886,-3.148342529792444,6.675488909246029,-6.013882190771024,34,0.0
SPY,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr0.300_maxday1,1373,1367,814,3.947116856070131,False,36,0.5277777777777778,1.1633599146249285,1.5203130216840948,0.04223091726900263,-3.2240754714039372,0.4166666666666667,36,0.5277777777777778,0.26357573165185366,-3.2240754714039372,4.987697621851865,3.28070440147046,17,0.5,20,0.6,1.216875813276599,0.9275611553311515,0.046378057766557575,-2.4212549409927147,0.45,20,0.6,0.276666674349044,-2.4212549409927147,2.922418053038828,3.150647303676151,20,1.0
SPY,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr-0.100_maxday1,2094,1460,777,7.239655970673686,False,41,0.7317073170731707,2.574923750521005,9.63904978534835,0.23509877525239878,-1.1401593913371464,0.3902439024390244,41,0.7317073170731707,0.34782607287224865,-1.1401593913371464,4.714010631017079,0.4890534581720409,20,1.0,20,0.7,2.4573569722833364,4.253323365321516,0.21266616826607582,-1.8,0.5,20,0.7,0.2927031058896207,-1.8,4.397588853400554,1.0339182976905241,20,1.0
SPY,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr-0.100_maxday1,2740,1591,870,5.844358784729252,False,41,0.6829268292682927,1.75809417789312,5.682527473230721,0.13859823105440783,-2.247325343468851,0.36585365853658536,41,0.6829268292682927,0.27985067257612606,-2.247325343468851,5.309515386333672,0.9343580671357532,20,1.0,22,0.5909090909090909,1.535848490361009,2.358286234660831,0.10719482884821958,-1.3728394880034616,0.4090909090909091,22,0.5909090909090909,0.28976610401236846,-1.3728394880034616,3.5380068081473626,1.500244862624235,22,1.0
SPY,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr0.300_maxday1,3554,1647,786,6.237533158994333,False,33,0.6060606060606061,2.0648454766525726,7.825481381594858,0.23713579944226842,-2.459343366254616,0.30303030303030304,33,0.6060606060606061,0.2862318064379754,-2.459343366254616,9.317237119742337,1.1906279838140073,16,1.0,15,0.4666666666666667,0.6634013866632242,-1.569284976442023,-0.10461899842946819,-1.7472048345450917,0.2,15,0.4666666666666667,-0.4621849118312109,-1.7472048345450917,2.4469829492558417,-1.559298015331663,15,0.0
SPY,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr0.200_maxday3,4331,1656,820,5.0899422853317375,False,102,0.5294117647058824,1.18451789380671,5.160000127200206,0.05058823654117849,-4.279356269989955,0.5098039215686274,39,0.5897435897435898,0.19512195594722548,-3.0793562699899546,11.272586202058083,2.184609675227768,50,1.0,56,0.44642857142857145,0.632510269922566,-6.835308979440269,-0.12205908891857623,-8.211456779016023,0.30357142857142855,20,0.45,-0.2976604926446241,-7.659815960056353,5.654102155152917,-0.8271904272593572,56,0.0
SPY,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr0.000_maxday3,5201,1606,852,6.29893766059107,False,126,0.5873015873015873,1.5336088220081958,15.221600518317196,0.12080635331997774,-5.96020337435548,0.1349206349206349,42,0.5952380952380952,0.461957226249053,-5.960203374355483,11.446964704466573,0.752021095987354,63,1.0,68,0.5147058823529411,1.208501551968465,3.91343686056328,0.05755054206710706,-4.361482542612522,0.0,23,0.5217391304347826,0.15669333994870993,-3.4759275029791707,12.596660709321998,3.218823034111479,68,1.0
SPY,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr-0.100_maxday1,5987,1672,649,4.844244862625243,False,44,0.5454545454545454,1.2911841296690492,3.1649658635889937,0.07193104235429532,-3.3622807873668834,0.4772727272727273,44,0.5454545454545454,0.18632084512243208,-3.3622807873668834,6.135310735792245,1.938507712318563,21,1.0,19,0.5789473684210527,1.1022427975354843,0.4907654281703252,0.025829759377385537,-2.7281021672335783,0.5789473684210527,19,0.5789473684210527,0.26470582434669154,-2.7281021672335783,3.3871269820652268,6.901722875413484,19,1.0
SPY,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr0.266_maxday3,6807,1501,850,8.093286083077764,False,69,0.6811594202898551,2.5874171276853946,20.21732157518424,0.2930046605099165,-3.362831874646904,0.21739130434782608,32,0.71875,0.5485833494609467,-3.362831874646897,12.269852719109313,0.6068980341179293,32,1.0,44,0.4772727272727273,0.9613676712518061,-0.5161457220455719,-0.011730584591944815,-4.399507558187417,0.09090909090909091,19,0.3684210526315789,-0.5340337296157134,-3.799507558187416,7.841296410179488,-15.192020538508231,44,0.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.000_maxday3,7659,1499,779,7.853297461591606,False,120,0.6416666666666667,1.866341961371261,21.360817994126513,0.17800681661772094,-3.0,0.19166666666666668,41,0.6585365853658537,0.30857505186328027,-2.838827621237968,14.412791554675962,0.6747303197208544,54,1.0,60,0.5166666666666667,0.8938741124244074,-1.785197186228016,-0.0297532864371336,-5.557435540791122,0.23333333333333334,20,0.45,-0.33317803194761697,-5.26390383389645,5.207523108451423,-2.917057649779584,60,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday2,8308,1629,615,6.708644587217314,False,84,0.6428571428571429,1.8231265086195116,13.723529640493666,0.16337535286301982,-3.8821816383515397,0.36904761904761907,42,0.5714285714285714,0.06378253310911519,-2.7742254216285556,9.20203812727233,0.670529985239374,40,1.0,38,0.47368421052631576,0.748631524194769,-2.912898294102483,-0.07665521826585482,-6.434706525121926,0.34210526315789475,19,0.3684210526315789,-0.13735632026411293,-6.434706525121926,5.712915013794487,-1.9612476773943597,38,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.100_maxday2,9158,1394,799,6.890062659143989,False,77,0.5974025974025974,1.8431363891701298,14.441672733931712,0.1875541913497625,-3.2467350092588028,0.4025974025974026,39,0.5897435897435898,0.19807710823928792,-3.2467350092587974,13.262945692827415,0.9183801583915694,38,1.0,44,0.5909090909090909,1.581564255903057,5.718078420136912,0.12995632773038437,-2.6810345149557886,0.5,22,0.5454545454545454,0.528526552864772,-2.6810345149557886,7.68230276291723,1.3435112634802386,44,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.400_maxday3,9937,1414,689,4.569055064668758,False,30,0.5666666666666667,1.181648704392942,1.2064093840493002,0.040213646134976674,-2.1856137394621444,0.43333333333333335,18,0.5555555555555556,0.3349232806508466,-2.1856137394621444,4.424502641411382,3.667496871220105,11,1.0,7,0.0,0.0,-4.037037054043575,-0.5767195791490821,-4.037037054043575,0.14285714285714285,5,0.0,-0.6,-4.037037054043575,-4.037037054043575,1.0,7,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.312_maxday1,10552,1488,775,6.912269584997201,False,32,0.71875,2.7140823152432447,8.824463037791354,0.2757644699309798,-2.4,0.46875,32,0.71875,0.3787311525826961,-2.4,6.3609268320209775,0.7208287693857273,14,1.0,13,0.46153846153846156,0.6390918185656203,-1.502115651596942,-0.11554735781514938,-1.8,0.07692307692307693,13,0.46153846153846156,-0.5620437797419562,-1.8,2.386118512428097,-1.5885051925870997,13,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr0.030_maxday1,11351,1464,724,5.437822605820235,False,37,0.5405405405405406,1.4725783572138182,4.5156743355897335,0.12204525231323604,-1.8322151306456251,0.1891891891891892,37,0.5405405405405406,0.3037189553404578,-1.8322151306456251,7.230703512724408,1.6012455671872758,17,1.0,19,0.5789473684210527,1.7960800198883964,3.821184095464304,0.20111495239285812,-1.1999999999999997,0.05263157894736842,19,0.5789473684210527,0.4137168169600429,-1.1999999999999997,5.797995764035302,1.5173296075730682,19,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_v1_SPY",
    "tickers": [
      "SPY"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 2,
    "pooled_train": false,
    "delta_bucket": 50,
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
  "data_rows": 13539
}
```