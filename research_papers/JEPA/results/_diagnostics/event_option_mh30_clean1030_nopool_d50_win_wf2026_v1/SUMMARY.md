# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 277,
  "win_rate": 0.4620938628158845,
  "profit_factor": 0.72163716057251,
  "pnl_return": -24.290255270464996,
  "avg_return": -0.08769045223994583,
  "max_drawdown": -26.590255270465022,
  "call_rate": 0.2815884476534296,
  "days_with_trades": 119,
  "daily_win_rate": 0.4369747899159664,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -31.490255270465003,
  "top5_day_return": 7.5,
  "top5_share_of_pnl": -0.3087657958506265,
  "min_month_trades": 32,
  "positive_month_rate": 0.16666666666666666
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 65,
    "win_rate": 0.4307692307692308,
    "profit_factor": 0.6455693517864369,
    "pnl_return": -7.686283528266664,
    "avg_return": -0.11825051581948713,
    "max_drawdown": -11.086283528266657,
    "call_rate": 0.46153846153846156,
    "days_with_trades": 65,
    "daily_win_rate": 0.4307692307692308,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -11.086283528266657,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.3252547204128151,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  },
  "SPXW": {
    "trades": 112,
    "win_rate": 0.5089285714285714,
    "profit_factor": 0.8609971074681276,
    "pnl_return": -4.435009933352003,
    "avg_return": -0.03959830297635717,
    "max_drawdown": -8.57772837545929,
    "call_rate": 0.24107142857142858,
    "days_with_trades": 112,
    "daily_win_rate": 0.5089285714285714,
    "median_daily_return": 0.11407697978993125,
    "daily_max_drawdown": -8.57772837545929,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.5636965954009685,
    "min_month_trades": 12,
    "positive_month_rate": 0.3333333333333333
  },
  "SPY": {
    "trades": 100,
    "win_rate": 0.43,
    "profit_factor": 0.6385703284248876,
    "pnl_return": -12.168961808846332,
    "avg_return": -0.12168961808846332,
    "max_drawdown": -14.468961808846318,
    "call_rate": 0.21,
    "days_with_trades": 100,
    "daily_win_rate": 0.43,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -14.468961808846318,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.2054406973471314,
    "min_month_trades": 7,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.450_maxday1,3906,4133,674,3.269294190310439,False,128,0.53125,0.9367458916915427,-2.226001864755172,-0.01739063956839978,-5.890243865222466,0.1796875,128,0.53125,0.5,-5.890243865222466,2.5,-1.123089804902281,19,0.5,20,0.45,0.6414938367131418,-2.262173886921094,-0.11310869434605471,-4.2621738869210954,0.15,20,0.45,-0.45499999523162843,-4.2621738869210954,2.5,-1.1051316675760043,20,0.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.700_maxday1,4640,4073,551,2.9034091215394766,False,123,0.5284552845528455,0.9344990875734814,-2.2054741376620246,-0.01793068404603272,-6.790243865222467,0.10569105691056911,123,0.5284552845528455,0.5,-6.790243865222467,2.5,-1.1335431040919826,19,0.3333333333333333,19,0.3684210526315789,0.4861111111111112,-3.6999999999999997,-0.19473684210526315,-4.1000000000000005,0.0,19,0.3684210526315789,-0.6,-4.1000000000000005,2.5,-0.6756756756756758,19,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.783_maxday1,5309,3955,723,2.1886272195163374,False,51,0.45098039215686275,0.6712956632329905,-5.434099898112784,-0.1065509783943683,-5.434099898112785,0.7058823529411765,51,0.45098039215686275,-0.6,-5.434099898112785,2.5,-0.46005779188347795,5,0.5,12,0.75,2.3224043644653896,2.3803278560377,0.19836065466980835,-0.6000000000000001,0.6666666666666666,12,0.75,0.5,-0.6000000000000001,2.5,1.0502754877479383,12,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.600_maxday1,6010,3977,677,0.7919665819183872,False,125,0.488,0.7885624832271997,-8.003155871179628,-0.06402524696943702,-11.641406673662907,0.064,125,0.488,-0.6,-11.641406673662907,2.5,-0.3123767723933523,19,0.0,21,0.38095238095238093,0.571764904408564,-2.995882344575901,-0.14266106402742387,-4.495882344575902,0.14285714285714285,21,0.38095238095238093,-0.6,-4.495882344575902,2.5,-0.834478698579834,21,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.521_maxday1,6740,3924,676,2.447213219258031,False,123,0.5040650406504065,0.8765684641883118,-4.296145949583979,-0.03492801585027625,-8.403166811125763,0.2764227642276423,123,0.5040650406504065,0.009756134777534342,-8.403166811125763,2.5,-0.5819169156117915,19,0.5,20,0.55,0.970873785575425,-0.15728155789270537,-0.00786407789463527,-2.6000000000000005,0.3,20,0.55,0.37135922105364716,-2.6000000000000005,2.5,-15.895061274160666,20,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-999.000_maxday1,7311,4029,656,5.02414105062952,False,124,0.5725806451612904,1.181128245644368,5.3293575656363945,0.04297869004545479,-3.438647073857922,0.46774193548387094,124,0.5725806451612904,0.5,-3.438647073857922,2.5,0.46909969338892865,19,0.6666666666666666,20,0.65,1.5476190476190474,2.3,0.11499999999999999,-2.7000000000000006,0.35,20,0.65,0.5,-2.7000000000000006,2.5,1.0869565217391306,20,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.400_maxday1,3662,3990,617,1.5653639322755082,False,127,0.47244094488188976,0.7813172026490642,-8.153100988869312,-0.06419764558164813,-9.34066098656558,0.2125984251968504,127,0.47244094488188976,-0.10326089879008404,-9.34066098656558,2.5,-0.3066317960997935,19,0.3333333333333333,20,0.2,0.21357380108199375,-7.364444467756482,-0.3682222233878241,-8.864444467756481,0.15,20,0.2,-0.6,-8.864444467756481,1.6355555322435167,-0.2220881071755539,20,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,4348,3921,509,-9.999999999999996e+17,True,368,0.44565217391304346,0.6812959795296655,-37.48881060948854,-0.10187176796056668,-42.44941665504301,0.04891304347826087,126,0.4444444444444444,-0.6330419264376831,-41.84941665504295,7.5,-0.20005969456128134,56,0.3333333333333333,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.773_maxday1,5031,3747,712,1.1776151975304558,False,42,0.42857142857142855,0.5860498615258172,-6.1139181066066115,-0.14556947872872886,-7.2696969715784245,0.21428571428571427,42,0.42857142857142855,-0.6,-7.2696969715784245,2.5,-0.4089030890516077,5,0.16666666666666666,13,0.5384615384615384,0.9722222222222222,-0.09999999999999976,-0.007692307692307674,-2.6,0.46153846153846156,13,0.5384615384615384,0.5,-2.6,2.5,-25.00000000000006,13,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.788_maxday1,5723,3767,567,2.1719345769659135,False,38,0.4473684210526316,0.642436171098692,-4.328477755073998,-0.11390730934405259,-4.328477755073999,0.23684210526315788,38,0.4473684210526316,-0.6,-4.328477755073999,2.5,-0.5775702548244379,3,0.3333333333333333,8,0.625,1.388888888888889,0.7000000000000001,0.08750000000000001,-1.2,0.25,8,0.625,0.5,-1.2,2.5,3.571428571428571,8,1.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.755_maxday1,6420,3637,653,3.7555000329608688,False,44,0.5227272727272727,0.9545898472363967,-0.5470587795305952,-0.0124331540802408,-2.8999999999999995,0.7045454545454546,44,0.5227272727272727,0.5,-2.8999999999999995,2.5,-4.569892840665366,3,0.6666666666666666,8,0.25,0.3010380640916469,-2.3218390605101806,-0.2902298825637726,-2.821839060510181,0.75,8,0.25,-0.6,-2.821839060510181,-0.521839060510181,0.2247524685864819,8,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.700_maxday1,6995,3715,581,3.2061332076663023,False,91,0.5384615384615384,0.9388730577200101,-1.41890245427969,-0.015592334662414175,-6.69884395931394,0.8461538461538461,91,0.5384615384615384,0.06048390895717448,-6.69884395931394,2.5,-1.7619252066690747,13,0.6666666666666666,16,0.625,1.3888888888888888,1.4000000000000001,0.08750000000000001,-1.6000000000000003,0.8125,16,0.625,0.5,-1.6000000000000003,2.5,1.7857142857142856,16,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.724_maxday1,3892,4165,674,3.433042024617427,False,94,0.5106382978723404,0.9040281903900431,-2.547844696795558,-0.027104730816974024,-4.799999999999999,0.20212765957446807,94,0.5106382978723404,0.5,-4.799999999999999,2.5,-0.9812215019009075,13,0.6666666666666666,18,0.3888888888888889,0.5388978926197968,-2.9947368470585576,-0.16637426928103097,-4.494736847058558,0.05555555555555555,18,0.3888888888888889,-0.6,-4.494736847058558,2.5,-0.8347978896561512,18,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr-999.000_maxday1,4630,4101,550,1.1491412863564692,False,126,0.47619047619047616,0.7830169742418693,-8.159619000798529,-0.06475888095871848,-10.581841228907622,0.05555555555555555,126,0.47619047619047616,-0.21586625420458833,-10.581841228907622,2.5,-0.30638685455231934,19,0.16666666666666666,19,0.3684210526315789,0.49181090746771206,-3.6165562757059835,-0.1903450671424202,-4.016556275705984,0.0,19,0.3684210526315789,-0.6,-4.016556275705984,2.5,-0.6912653390170123,19,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.789_maxday1,5308,3973,727,3.028530454773635,False,48,0.5208333333333334,0.8507122835502102,-2.0950042875120536,-0.043645922656501114,-4.3,0.7916666666666666,48,0.5208333333333334,0.2191645229106397,-4.3,2.5,-1.1933149802614025,4,0.5,7,0.14285714285714285,0.1388888888888889,-3.1,-0.4428571428571429,-3.1,1.0,7,0.14285714285714285,-0.6,-3.1,-1.9,0.6129032258064515,7,0.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday1,6015,3993,589,1.3978897261072112,False,125,0.48,0.8040380628430092,-7.272843423395344,-0.058182747387162746,-10.772843423395333,0.12,125,0.48,-0.16455695151977123,-10.772843423395333,2.5,-0.34374451015375623,19,0.3333333333333333,18,0.4444444444444444,0.7070049912679132,-1.6576686860817884,-0.09209270478232158,-2.6,0.16666666666666666,18,0.4444444444444444,-0.4288343430408944,-2.6,2.5,-1.5081421402181518,18,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.643_maxday1,6746,3851,667,1.3970495659154927,False,110,0.4818181818181818,0.8039416753095873,-6.363022625217457,-0.05784566022924961,-11.7792951661385,0.23636363636363636,110,0.4818181818181818,-0.08961537897704352,-11.7792951661385,2.5,-0.3928950354650927,15,0.5,18,0.4444444444444444,0.6666666666666667,-1.9999999999999996,-0.11111111111111109,-3.1,0.2222222222222222,18,0.4444444444444444,-0.6,-3.1,2.5,-1.2500000000000002,18,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.582_maxday1,7319,3945,644,4.345933842792491,False,121,0.5454545454545454,1.069789626614523,2.0919086609779622,0.01728850133039638,-3.537037054043575,0.4297520661157025,121,0.5454545454545454,0.5,-3.537037054043575,2.5,1.195080859233718,18,0.5,20,0.6,1.25,1.2000000000000002,0.06000000000000001,-3.0,0.3,20,0.6,0.5,-3.0,2.5,2.083333333333333,20,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_tp50_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30_clean1030_nopool_d50_win_wf2026_v1",
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
    "entry_time_min_et": "10:30",
    "allow_invalid_val_deploy": false,
    "deploy_month": "",
    "deploy_select_end_month": "",
    "export_deploy_model": false,
    "exclude_months": [],
    "skip_walkforward": false,
    "resume": false,
    "seed": 20260617
  },
  "feature_count": 273,
  "features": [
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "dist_fib_127_up_bps",
    "dist_fib_161_up_bps",
    "dist_fib_200_up_bps",
    "dist_fib_127_dn_bps",
    "dist_fib_161_dn_bps",
    "dist_fib_200_dn_bps",
    "nearest_level_abs_bps",
    "ib_range_bps",
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
    "phys_fib_up_min_abs_bps",
    "phys_fib_up_mean_signed_bps",
    "phys_fib_dn_min_abs_bps",
    "phys_fib_dn_mean_signed_bps",
    "phys_fib_any_min_abs_bps",
    "phys_ib_edge_min_abs_bps",
    "phys_ib_balance",
    "phys_nearest_level_vs_ib_range",
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
    "ctx_spx_ib_range_bps",
    "ctx_spx_nearest_level_abs_bps",
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
    "ctx_spy_ib_range_bps",
    "ctx_spy_nearest_level_abs_bps",
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
    "ctx_qqq_ib_range_bps",
    "ctx_qqq_nearest_level_abs_bps",
    "ctx_qqq_phys_d35_iv_skew_put_minus_call",
    "ctx_qqq_phys_total_volume_skew_call_minus_put",
    "ctx_qqq_phys_total_oi_skew_call_minus_put",
    "ctx_spy_qqq_ret_5m_spread",
    "ctx_spx_spy_ret_5m_spread",
    "ticker_QQQ",
    "ticker_SPXW",
    "ticker_SPY",
    "expiry_mode_zero_dte",
    "nearest_level_name_fib_127_dn",
    "nearest_level_name_fib_127_up",
    "nearest_level_name_fib_161_dn",
    "nearest_level_name_fib_161_up",
    "nearest_level_name_fib_200_dn",
    "nearest_level_name_fib_200_up",
    "nearest_level_name_ib_high",
    "nearest_level_name_ib_low"
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
  "data_rows": 35195
}
```