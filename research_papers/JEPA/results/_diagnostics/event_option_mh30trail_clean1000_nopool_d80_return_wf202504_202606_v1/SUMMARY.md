# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 424,
  "win_rate": 0.5141509433962265,
  "profit_factor": 1.0677127905382466,
  "pnl_return": 6.975549348538978,
  "avg_return": 0.016451767331459855,
  "max_drawdown": -13.117315687458659,
  "call_rate": 0.33726415094339623,
  "days_with_trades": 203,
  "daily_win_rate": 0.5024630541871922,
  "median_daily_return": 0.005535041196266466,
  "daily_max_drawdown": -12.772756177289526,
  "top5_day_return": 17.73095435871786,
  "top5_share_of_pnl": 2.5418721125428765,
  "min_month_trades": 0,
  "positive_month_rate": 0.4666666666666667
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 424,
    "win_rate": 0.5141509433962265,
    "profit_factor": 1.0677127905382466,
    "pnl_return": 6.975549348538978,
    "avg_return": 0.016451767331459855,
    "max_drawdown": -13.117315687458659,
    "call_rate": 0.33726415094339623,
    "days_with_trades": 203,
    "daily_win_rate": 0.5024630541871922,
    "median_daily_return": 0.005535041196266466,
    "daily_max_drawdown": -12.772756177289526,
    "top5_day_return": 17.73095435871786,
    "top5_share_of_pnl": 2.5418721125428765,
    "min_month_trades": 0,
    "positive_month_rate": 0.4666666666666667
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202508,202508,202501,202501,202502,"202502,202503,202504,202505,202506,202507",202507,thr0.289_maxday1,765,4460,778,5.661041749824169,False,111,0.5405405405405406,1.307055923200852,6.592037894253952,0.05938772877706263,-2.313682618442515,0.5405405405405406,111,0.5405405405405406,0.04411512922944172,-2.313682618442515,7.078454193595947,1.073788456186817,16,0.8333333333333334,14,0.35714285714285715,0.5120468693608494,-1.8296971519726872,-0.1306926537123348,-2.1893568949251514,0.0,14,0.35714285714285715,-0.17579436080562116,-2.1893568949251514,1.920042396938576,-1.0493771577818127,14,0.0
SPXW,202509,202509,"202501,202502",202502,202503,"202503,202504,202505,202506,202507,202508",202508,thr0.100_maxday1,1392,4611,814,7.644418285039527,False,124,0.5806451612903226,1.82740049595337,17.368790216554746,0.14007088884318344,-1.9163756449170322,0.5241935483870968,124,0.5806451612903226,0.25062752092553575,-1.9163756449170322,7.8660645311686235,0.45288499849985103,20,1.0,21,0.5238095238095238,1.2975631348202663,1.1182391270745264,0.053249482241644115,-1.2000000000000002,0.3333333333333333,21,0.5238095238095238,0.2542857215518044,-1.2000000000000002,3.1017176346189785,2.7737516596593395,21,1.0
SPXW,202510,202510,"202501,202502,202503",202503,202504,"202504,202505,202506,202507,202508,202509",202509,thr0.238_maxday2,2116,4701,852,7.540638218228376,False,225,0.5688888888888889,1.5059772747372693,21.946995621886877,0.09754220276394168,-4.246692289539478,0.4088888888888889,121,0.5785123966942148,0.21528425402501927,-4.085323985262028,11.746131202607689,0.5352045175100747,34,1.0,36,0.6388888888888888,2.028331949183896,7.0757998842290535,0.19654999678414037,-1.8000000000000003,0.16666666666666666,20,0.6,0.2886442314665152,-1.4964146330697363,8.898251424160824,1.2575612043514337,36,1.0
SPXW,202511,202511,"202501,202502,202503,202504",202504,202505,"202505,202506,202507,202508,202509,202510",202510,thr0.066_maxday3,2765,4904,648,8.347682164245981,False,382,0.5759162303664922,1.4451688910170957,32.17605631135716,0.08423051390407633,-6.144409009432185,0.3717277486910995,128,0.6015625,0.22241199287447833,-5.687307713498299,17.974897034081618,0.5586420181561229,60,1.0,55,0.5272727272727272,1.2680378532823884,3.912007190680895,0.07112740346692537,-3.2403983950589916,0.4909090909090909,19,0.5263157894736842,0.1737644960124699,-3.2403983950589916,9.42435749285144,2.409084910503732,55,1.0
SPXW,202512,202512,"202501,202502,202503,202504,202505",202505,202506,"202506,202507,202508,202509,202510,202511",202511,thr0.224_maxday3,3585,4732,842,9.975384764403806,False,333,0.5825825825825826,1.6314627905808818,39.8091520267226,0.11954700308325106,-2.6158177111637606,0.38738738738738737,118,0.6271186440677966,0.3218040271062475,-2.2780200844079097,16.757304943316385,0.4209410170823972,48,1.0,64,0.53125,1.0989693801298037,1.238872938329231,0.019357389661394234,-3.674719501849358,0.421875,22,0.5909090909090909,0.1018195205436393,-2.9590347014157836,6.12935666754747,4.947526479845176,64,1.0
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.000_maxday3,4362,4797,779,6.953578644806121,False,381,0.5511811023622047,1.2683795640999076,21.86771147060201,0.05739556816430974,-5.995811469822989,0.4199475065616798,128,0.5390625,0.11183026889601672,-5.988830905945846,16.329347514950577,0.7467332618185964,55,0.8333333333333334,60,0.55,1.1232976899233515,1.577062399272986,0.02628437332121643,-3.0175837822776286,0.5333333333333333,20,0.5,0.04181023816803192,-2.7908488342490996,7.805333802882919,4.9492866017737285,60,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.000_maxday2,5225,4713,616,5.487480059837902,False,251,0.5537848605577689,1.2646105860910237,14.817722937248728,0.05903475273804274,-8.007052211918138,0.027888446215139442,126,0.49206349206349204,-0.06110291763700232,-7.562224638865366,13.48122492031692,0.9098040891578473,37,0.6666666666666666,38,0.39473684210526316,0.9742756127769171,-0.30707676369042314,-0.00808096746553745,-4.261363607628614,0.0,19,0.3684210526315789,-0.5305913408140622,-4.261363607628614,10.066938751976032,-32.78313419417476,38,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.448_maxday3,6003,4551,793,5.84325948458942,False,32,0.6875,2.1397140427039374,5.8670713412056195,0.1833459794126756,-2.079689492846767,0.75,19,0.631578947368421,0.46415442378489,-2.0714334157234737,6.4937051449086,1.106805212901027,3,0.6666666666666666,15,0.6,1.807052929452984,2.3214085877730506,0.15476057251820338,-2.2734694033252953,0.9333333333333333,8,0.625,0.10273496069367066,-2.273469403325295,4.5978104978020315,1.9806123411530734,15,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-0.200_maxday2,6817,4530,793,7.249140748250486,False,249,0.5622489959839357,1.4114437963241298,22.047494716962703,0.08854415548981005,-5.4047154884303215,0.18875502008032127,125,0.552,0.1650305157850337,-4.359887915377558,15.728663464619382,0.7133991261382729,37,1.0,42,0.5,0.7010429138684969,-3.758945714713345,-0.08949870749317489,-5.417343465285607,0.09523809523809523,21,0.47619047619047616,-0.2541129348002442,-5.417343465285607,5.671674146530858,-1.5088470483440797,42,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-999.000_maxday3,7669,4471,783,7.938625526723398,False,366,0.5655737704918032,1.4400035792928843,33.31162284756975,0.09101536297150205,-7.796407208367552,0.34972677595628415,123,0.5691056910569106,0.22353088937988375,-7.796407208367561,19.995530520993093,0.6002568716778044,55,0.8333333333333334,60,0.45,0.624509745697576,-6.276707863647599,-0.10461179772745997,-7.084900569420029,0.38333333333333336,20,0.4,-0.23505218406988815,-6.740341059250893,4.862369487073781,-0.7746687583207194,60,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.200_maxday1,8317,4606,736,6.395672608938283,False,119,0.5966386554621849,1.5533487038321687,12.544970395352419,0.10541991928867579,-3.293730963569308,0.44537815126050423,119,0.5966386554621849,0.17880786671397564,-3.293730963569308,7.327316191063476,0.5840839762984258,19,0.8333333333333334,19,0.5789473684210527,1.4121075806860925,1.904586715203289,0.100241406063331,-2.3396313191908273,0.15789473684210525,19,0.5789473684210527,0.3313149261648174,-2.3396313191908273,4.132761787632401,2.1698995139695096,19,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_v1",
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
    "delta_bucket": 80,
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
  "data_rows": 39638
}
```