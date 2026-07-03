# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 631,
  "win_rate": 0.5277337559429477,
  "profit_factor": 1.2920842004597475,
  "pnl_return": 51.853558702051174,
  "avg_return": 0.08217679667519996,
  "max_drawdown": -8.986348202599643,
  "call_rate": 0.3185419968304279,
  "days_with_trades": 286,
  "daily_win_rate": 0.5244755244755245,
  "median_daily_return": 0.1281124706932837,
  "daily_max_drawdown": -8.98634820259959,
  "top5_day_return": 24.003181481650966,
  "top5_share_of_pnl": 0.46290326223456424,
  "min_month_trades": 13,
  "positive_month_rate": 0.8666666666666667
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 631,
    "win_rate": 0.5277337559429477,
    "profit_factor": 1.2920842004597475,
    "pnl_return": 51.853558702051174,
    "avg_return": 0.08217679667519996,
    "max_drawdown": -8.986348202599643,
    "call_rate": 0.3185419968304279,
    "days_with_trades": 286,
    "daily_win_rate": 0.5244755244755245,
    "median_daily_return": 0.1281124706932837,
    "daily_max_drawdown": -8.98634820259959,
    "top5_day_return": 24.003181481650966,
    "top5_share_of_pnl": 0.46290326223456424,
    "min_month_trades": 13,
    "positive_month_rate": 0.8666666666666667
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.400_maxday1,765,1351,649,4.894723953523226,False,32,0.5625,1.4946309968393277,3.7016538604311564,0.11567668313847364,-3.956461494007748,0.3125,32,0.5625,0.33383760983715827,-3.956461494007748,5.60261407073755,1.513543481368346,12,1.0,17,0.5882352941176471,1.6908001727094517,2.9013607253796976,0.1706682779635116,-1.2,0.058823529411764705,17,0.5882352941176471,0.3789062555297278,-1.2,4.737140510682783,1.6327306250631208,17,1.0
SPXW,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr0.300_maxday2,1392,1373,820,5.690772460834701,False,79,0.5822784810126582,1.4715657237509665,8.977449018308741,0.11363859516846508,-4.467199824016667,0.34177215189873417,40,0.6,0.34102279162018584,-4.190533182781319,8.925244556212325,0.9941849336053094,38,1.0,40,0.55,1.3474998831090803,3.7529987375780673,0.09382496843945168,-3.6000000000000005,0.4,20,0.55,0.1380685464228626,-3.6000000000000005,7.426952168767868,1.978938094064141,40,1.0
SPXW,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr0.100_maxday2,2116,1469,777,6.4317911492162825,False,81,0.5802469135802469,1.58693461126256,11.973466069756222,0.1478205687624225,-2.9999999999999982,0.37037037037037035,41,0.6585365853658537,0.17469121557677403,-2.4000000000000004,8.49585828198831,0.7095571351263106,39,1.0,39,0.6153846153846154,1.208816914328183,1.8793522289536466,0.04818851869111914,-1.8147278499305979,0.358974358974359,20,0.45,-0.09366220963033078,-1.6981926460429968,5.58944092958177,2.9741316414612515,39,1.0
SPXW,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr0.420_maxday3,2765,1597,863,8.003324596456038,False,37,0.7837837837837838,3.4831061713418108,11.918909622440689,0.322132692498397,-1.6321429082325527,0.13513513513513514,20,0.75,0.3762462625331394,-1.0705487303727095,9.760818535471797,0.8189355272141942,16,1.0,13,0.6153846153846154,1.8235004895289872,2.470501468586962,0.1900385745066894,-1.5305555370118884,0.46153846153846156,8,0.625,0.36141302220537425,-1.530555537011888,4.276056981756993,1.730845755862976,13,1.0
SPXW,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr-0.200_maxday3,3585,1640,778,6.47528413718063,False,125,0.592,1.4542595362100956,13.254819755326048,0.10603855804260838,-3.6000000000000005,0.56,42,0.6428571428571429,0.3940901825552864,-3.5999999999999996,12.5258637864927,0.9450044600915497,59,1.0,63,0.5555555555555556,1.3562635173561088,5.676833470548676,0.09010846778648691,-3.494350908970925,0.6190476190476191,21,0.5714285714285714,0.12361631207695456,-3.494350908970926,9.376636260983762,1.6517370660297868,63,1.0
SPXW,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr-0.100_maxday3,4362,1641,814,7.615520907155009,False,126,0.5873015873015873,1.7288096702791125,21.16616142183457,0.16798540810979817,-3.4628795581816902,0.5952380952380952,42,0.6904761904761905,0.4033335679320299,-3.1534200273185533,14.072929366735712,0.6648786752716708,63,1.0,63,0.5714285714285714,1.3255770235033761,5.274347780754691,0.08371980604372525,-4.629887569098814,0.47619047619047616,21,0.5238095238095238,0.11228250945494633,-4.6298875690988135,8.295063700751427,1.5727183806534106,63,1.0
SPXW,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr0.456_maxday2,5225,1592,852,7.895770869721597,False,70,0.6714285714285714,2.441754324017663,19.896209671443735,0.2842315667349105,-3.6000000000000014,0.08571428571428572,39,0.6410256410256411,0.5192307974459867,-3.5684210823513443,12.214526023963488,0.6139122086904084,32,1.0,41,0.6097560975609756,1.2252332195669997,2.162238907843196,0.052737534337638926,-2.5089263265013946,0.0,21,0.47619047619047616,-0.054819364322079456,-2.5089263265013946,5.835815073163136,2.6989686717756283,41,1.0
SPXW,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr0.050_maxday2,6003,1666,648,9.331692755754428,False,87,0.7241379310344828,2.8504307277050756,26.323361311355782,0.30256737139489404,-1.8000000000000003,0.40229885057471265,44,0.7045454545454546,0.5809291796627624,-1.8,14.99378048663732,0.5695997676470393,41,1.0,37,0.5405405405405406,1.3341261601305219,3.408086833331319,0.09211045495490051,-4.800000000000001,0.5405405405405406,19,0.5263157894736842,0.1625984133712649,-4.800000000000001,8.764940651771665,2.5718067292329394,37,1.0
SPXW,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr0.400_maxday3,6817,1500,842,8.832092966942794,False,85,0.6235294117647059,2.50925009960877,28.15363298825264,0.33121921162650164,-3.769668593236684,0.09411764705882353,35,0.6285714285714286,0.31038406991508294,-2.901024431264382,21.29465123081132,0.7563731202895451,41,1.0,47,0.425531914893617,0.8301546658375499,-2.751494413431691,-0.05854243432833386,-5.342778492275317,0.02127659574468085,19,0.3684210526315789,-0.6,-5.342778492275318,7.683731907779945,-2.7925667848973452,47,0.0
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr-0.200_maxday2,7669,1490,779,7.712363216214873,False,81,0.654320987654321,2.330158391792318,22.346660982110947,0.2758847034828512,-5.571930735785184,0.1111111111111111,41,0.7073170731707317,0.5961227347771245,-4.971930735785186,12.525820437931554,0.5605231335436995,37,1.0,40,0.45,1.0692744303404667,0.9144224804941568,0.022860562012353917,-6.2007708129419035,0.025,20,0.35,-0.18738242392439763,-5.746225395341478,9.724284371228544,10.634345260161922,40,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday3,8317,1621,616,7.898581802056708,False,126,0.6190476190476191,1.8364050466770263,23.875749992827185,0.18949007930815226,-3.9824482561688974,0.3253968253968254,42,0.6666666666666666,0.3608929462318379,-3.6601838094385712,17.38217454244821,0.7280263257770001,60,1.0,56,0.42857142857142855,0.9794580951511586,-0.39440457309775523,-0.007042938805317057,-5.916450312612257,0.21428571428571427,19,0.47368421052631576,-0.583640530717541,-5.916450312612256,12.31424442886669,-31.22236725641247,56,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.200_maxday3,9159,1395,793,6.581563474620609,False,106,0.5471698113207547,1.616714127683105,17.761366877273428,0.167560064879938,-5.915521657019685,0.1509433962264151,38,0.5789473684210527,0.21707217701286646,-5.9155216570196885,19.52732276299467,1.0994268007593984,49,1.0,64,0.421875,1.0429142211102111,0.9526957086466915,0.014885870447604555,-7.986203348318729,0.625,22,0.45454545454545453,-0.11849207061359368,-7.986203348318733,11.191165846690957,11.74684187733779,64,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.109_maxday2,9938,1409,793,7.1134277324761985,False,82,0.6341463414634146,1.9873577610150557,17.772439698271004,0.2167370694911098,-4.67731212552372,0.6219512195121951,41,0.5609756097560976,0.24230775099534274,-4.6773121255237164,13.53511728883545,0.7615790245248218,38,1.0,40,0.7,3.3611398482677086,17.0002069075275,0.4250051726881875,-2.2968750291038287,0.475,20,0.75,0.8255281521040785,-2.2968750291038287,13.335513363224967,0.7844324151913794,40,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.300_maxday1,10554,1586,783,9.166521294300175,False,42,0.6904761904761905,3.9004916992148235,22.47596705226063,0.5351420726728721,-2.7081105178506872,0.5952380952380952,42,0.6904761904761905,0.4231798633917837,-2.7081105178506872,14.513854629217875,0.6457499512911091,20,1.0,20,0.7,2.609920835276975,5.79571500699711,0.2897857503498555,-1.2213032798149799,0.0,20,0.7,0.33341521795895246,-1.2213032798149799,5.748618350906777,0.9918738833718577,20,1.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr-0.100_maxday3,11347,1576,736,5.979265144102534,False,120,0.5083333333333333,1.4345719322955368,15.217406069466206,0.1268117172455517,-6.849470190639034,0.25833333333333336,41,0.6341463414634146,0.2906789059047711,-6.249470190639041,15.056502124500334,0.9894263224473765,58,1.0,51,0.43137254901960786,1.1653825986762072,2.8106974319389098,0.05511171435174333,-4.022085141000034,0.0392156862745098,19,0.5263157894736842,0.30756305132035233,-3.422085141000033,10.957152169649785,3.8983748464491206,51,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_v1_SPXW",
    "tickers": [
      "SPXW"
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
    "ticker_SPXW",
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
  "data_rows": 13659
}
```