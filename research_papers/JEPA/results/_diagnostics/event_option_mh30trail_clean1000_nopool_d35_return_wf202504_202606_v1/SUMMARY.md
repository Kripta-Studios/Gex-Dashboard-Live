# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 607,
  "win_rate": 0.48105436573311366,
  "profit_factor": 1.1542452968122736,
  "pnl_return": 28.553227169839825,
  "avg_return": 0.04703991296513974,
  "max_drawdown": -10.354106978321548,
  "call_rate": 0.342668863261944,
  "days_with_trades": 224,
  "daily_win_rate": 0.45535714285714285,
  "median_daily_return": -0.13078533306657686,
  "daily_max_drawdown": -9.754106978321552,
  "top5_day_return": 28.86199547291723,
  "top5_share_of_pnl": 1.0108137795157373,
  "min_month_trades": 0,
  "positive_month_rate": 0.3333333333333333
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 607,
    "win_rate": 0.48105436573311366,
    "profit_factor": 1.1542452968122736,
    "pnl_return": 28.553227169839825,
    "avg_return": 0.04703991296513974,
    "max_drawdown": -10.354106978321548,
    "call_rate": 0.342668863261944,
    "days_with_trades": 224,
    "daily_win_rate": 0.45535714285714285,
    "median_daily_return": -0.13078533306657686,
    "daily_max_drawdown": -9.754106978321552,
    "top5_day_return": 28.86199547291723,
    "top5_share_of_pnl": 1.0108137795157373,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202508,202508,202501,202501,202502,"202502,202503,202504,202505,202506,202507",202507,thr0.168_maxday1,765,4460,778,4.093958492547149,False,120,0.5166666666666667,1.1126405018239338,3.708401838531964,0.030903348654433036,-5.894016000772767,0.3333333333333333,120,0.5166666666666667,0.25,-5.894016000772767,8.279956313480241,2.232755961732024,18,0.5,21,0.23809523809523808,0.2627354440298823,-6.741765332939201,-0.32103644442567625,-6.741765332939201,0.23809523809523808,21,0.23809523809523808,-0.6,-6.741765332939201,2.402530670912711,-0.3563652177530306,21,0.0
SPXW,202509,202509,"202501,202502",202502,202503,"202503,202504,202505,202506,202507,202508",202508,thr-0.100_maxday3,1392,4611,814,8.350263299080408,False,373,0.5871313672922251,1.4275830654641644,37.91496194074682,0.10164869153015234,-8.005848772631696,0.5093833780160858,125,0.64,0.4206653171402618,-7.4058487726317015,17.263426751071254,0.4553196381431265,58,0.8333333333333334,63,0.49206349206349204,0.9674012896699938,-0.6138978077300522,-0.009744409646508766,-7.155515176183837,0.5714285714285714,21,0.47619047619047616,-0.046808407024968246,-6.555515176183835,7.8194404158645385,-12.737364944790555,63,0.0
SPXW,202510,202510,"202501,202502,202503",202503,202504,"202504,202505,202506,202507,202508,202509",202509,thr0.051_maxday3,2116,4701,852,6.359489106374856,False,366,0.5191256830601093,1.1957895472922186,20.306082082825263,0.05548109858695427,-7.607451601654908,0.5163934426229508,124,0.5564516129032258,0.2824349248866819,-6.940113678233352,15.174076440417,0.7472675614391968,58,0.8333333333333334,64,0.5625,1.8276924470477305,12.75924261175964,0.19936316580874439,-3.761365475127798,0.375,22,0.5454545454545454,0.4709287749703782,-2.8785103231637716,13.484523185676384,1.0568435444003772,64,1.0
SPXW,202511,202511,"202501,202502,202503,202504",202504,202505,"202505,202506,202507,202508,202509,202510",202510,thr0.100_maxday3,2765,4904,648,8.00760804130483,False,356,0.550561797752809,1.3263467326790657,30.774514463885094,0.08644526534799184,-5.405275869188678,0.5140449438202247,124,0.5725806451612904,0.24768270737913767,-5.2461849527087345,17.207814055709115,0.5591579381667597,56,0.8333333333333334,51,0.45098039215686275,1.0692979001872018,1.1642047231449917,0.02282754359107827,-6.953507113000104,0.4117647058823529,18,0.4444444444444444,-0.3456238226242649,-6.953507113000104,11.028857164939504,9.473297046198253,51,1.0
SPXW,202512,202512,"202501,202502,202503,202504,202505",202505,202506,"202506,202507,202508,202509,202510,202511",202511,thr0.084_maxday3,3585,4732,842,9.787517110956806,False,352,0.5823863636363636,1.5405126587064488,45.90967500797239,0.13042521309083066,-6.202293499318184,0.5056818181818182,124,0.5887096774193549,0.3137951396154106,-5.4772934754763085,17.99023443960409,0.3918615071110832,54,1.0,63,0.42857142857142855,0.9307639694101889,-1.432578136293465,-0.022739335496721667,-7.54567901961343,0.4126984126984127,22,0.45454545454545453,-0.04272809143576434,-6.087986682577297,7.229246189933133,-5.046318945392738,63,0.0
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-0.200_maxday3,4362,4797,779,8.41221934352689,False,377,0.5358090185676393,1.3586829065273078,36.178461254965285,0.09596408820945698,-6.419863108547094,0.4509283819628647,127,0.6062992125984252,0.28851538708602276,-6.090915711306856,19.557878600623095,0.5405945394634187,54,0.8333333333333334,60,0.6,1.569894738565865,8.206484235348459,0.13677473725580763,-2.6579159537253974,0.5166666666666667,20,0.55,0.23480521570951607,-2.514672736170059,8.95593259888912,1.091323926549752,60,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.000_maxday3,5225,4713,616,8.847131030294037,False,371,0.5363881401617251,1.4083601891823025,41.77968137594554,0.11261369643112007,-8.155888155903824,0.05121293800539083,125,0.568,0.22506531332919488,-7.471052602759766,22.25322113669131,0.5326326195848755,54,1.0,56,0.42857142857142855,0.9950430569921173,-0.09517330575134864,-0.0016995233169883686,-6.0,0.0,19,0.3684210526315789,-0.8021126807859269,-5.953968458206889,12.31424442886669,-129.38758753467164,56,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.125_maxday3,6003,4551,793,9.076187796664966,False,355,0.5746478873239437,1.5126360737873814,45.63124933473305,0.1285387305203748,-8.63993295472557,0.5352112676056338,122,0.6639344262295082,0.38046338227571413,-8.639932954725555,17.430097058570464,0.38197720449663936,55,0.8333333333333334,64,0.546875,1.2892868117998206,4.939226878262118,0.07717541997284559,-5.580529084887577,0.671875,22,0.5,0.003922102302107711,-4.6429784612081395,10.611272434868372,2.1483670818138205,64,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.200_maxday3,6817,4530,793,10.553508037651524,False,352,0.5681818181818182,1.6064977207553457,54.79575059693949,0.15566974601403263,-7.200000000000017,0.07954545454545454,123,0.6585365853658537,0.36296241425553244,-7.199999999999996,21.97143019111939,0.40096959986431063,54,1.0,61,0.4098360655737705,0.9135345382700818,-1.8458530771761588,-0.03025988651108457,-5.71251166490133,0.16393442622950818,21,0.3333333333333333,-0.46739137069038716,-5.375011688743187,10.472282480485644,-5.6734106359680885,61,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.200_maxday3,7669,4471,783,9.642316765201961,False,343,0.5335276967930029,1.487686761684126,46.28423806176192,0.134939469567819,-6.7422779435552505,0.16034985422740525,121,0.6198347107438017,0.4090591305961654,-6.742277943555258,22.87526380222884,0.49423442537185064,49,1.0,59,0.4576271186440678,0.9924931046107831,-0.14413239147296508,-0.0024429218893722896,-6.086176165033979,0.11864406779661017,20,0.5,0.15398704248198525,-6.086176165033979,10.033446908182944,-69.612713739402,59,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.300_maxday3,8317,4606,736,10.945898238656321,False,285,0.543859649122807,1.713909605305825,55.68494921385433,0.19538578671527834,-5.814818798644708,0.2771929824561403,112,0.5446428571428571,0.14088631173080984,-5.067408563417917,22.910346770481173,0.41142799075735015,40,1.0,45,0.5111111111111111,1.9497627594820084,12.357468772687808,0.27461041717084017,-2.4,0.1111111111111111,18,0.6111111111111112,0.42170215019774315,-1.7999999999999998,15.721862896655846,1.2722559276381862,45,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_v1",
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
  "data_rows": 39664
}
```