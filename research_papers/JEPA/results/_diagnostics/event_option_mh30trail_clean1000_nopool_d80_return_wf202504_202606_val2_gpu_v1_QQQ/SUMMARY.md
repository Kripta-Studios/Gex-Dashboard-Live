# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 448,
  "win_rate": 0.4799107142857143,
  "profit_factor": 0.9368732123125867,
  "pnl_return": -6.6342227605979875,
  "avg_return": -0.014808532947763365,
  "max_drawdown": -14.139623404405667,
  "call_rate": 0.5066964285714286,
  "days_with_trades": 281,
  "daily_win_rate": 0.47330960854092524,
  "median_daily_return": -0.06796636492241592,
  "daily_max_drawdown": -13.852357604835108,
  "top5_day_return": 14.244366272754386,
  "top5_share_of_pnl": -2.147104007021682,
  "min_month_trades": 13,
  "positive_month_rate": 0.5333333333333333
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 448,
    "win_rate": 0.4799107142857143,
    "profit_factor": 0.9368732123125867,
    "pnl_return": -6.6342227605979875,
    "avg_return": -0.014808532947763365,
    "max_drawdown": -14.139623404405667,
    "call_rate": 0.5066964285714286,
    "days_with_trades": 281,
    "daily_win_rate": 0.47330960854092524,
    "median_daily_return": -0.06796636492241592,
    "daily_max_drawdown": -13.852357604835108,
    "top5_day_return": 14.244366272754386,
    "top5_share_of_pnl": -2.147104007021682,
    "min_month_trades": 13,
    "positive_month_rate": 0.5333333333333333
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
QQQ,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.400_maxday2,631,1222,589,5.626928926044405,False,44,0.5227272727272727,1.919856666253896,7.431600108742487,0.16890000247142017,-2.7191639487730104,0.8181818181818182,24,0.5833333333333334,0.1875948521124869,-2.6669446763841993,10.56484191813032,1.4216106576700631,8,0.5,30,0.6,1.3693038609961328,2.343511020393053,0.07811703401310176,-3.5641266874845954,1.0,16,0.5625,0.13685659115957288,-3.5641266874845954,5.996421061114108,2.5587338864352303,30,1.0
QQQ,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr0.386_maxday1,1195,1247,761,4.389905891111221,False,34,0.5,1.136456822987863,1.104710212075751,0.032491476825757384,-2.989590288903419,0.5294117647058824,34,0.5,0.026129041859440427,-2.989590288903419,5.891972714709399,5.3335007229075755,16,1.0,13,0.3076923076923077,0.22696877752752442,-3.7731422836415085,-0.29024171412626987,-3.7731422836415085,0.5384615384615384,13,0.3076923076923077,-0.6,-3.7731422836415085,0.8053887831078815,-0.2134530644655654,13,0.0
QQQ,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr0.000_maxday2,1853,1350,763,5.292398198910405,False,81,0.5308641975308642,1.265553998002794,4.5408132565932995,0.05605942292090493,-2.990823736448271,0.6172839506172839,41,0.5121951219512195,0.011421308738863711,-2.7714689063391944,9.169396769333126,2.0193291930733075,39,1.0,40,0.6,1.4804168240334077,2.9520082605693077,0.07380020651423269,-2.0156410043291304,0.475,20,0.6,0.04038322204174383,-1.8001810812616692,6.0260998902338,2.0413560391161103,40,1.0
QQQ,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr0.143_maxday1,2442,1524,797,6.16437897163025,False,39,0.5641025641025641,1.9690947384230542,5.712228779503638,0.1464674046026574,-1.6580548704866498,0.41025641025641024,39,0.5641025641025641,0.17352410799892182,-1.6580548704866498,5.643771977914387,0.988015745826763,18,1.0,20,0.5,1.0118169959862686,0.04302036036496748,0.002151018018248374,-1.543606422120467,1.0,20,0.5,0.0392086551948449,-1.543606422120467,2.5621191921856354,59.55596769644987,20,1.0
QQQ,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr-0.100_maxday3,3203,1560,755,6.480370780865938,False,120,0.575,1.6428258857125575,10.54611767338374,0.0878843139448645,-3.239464998925021,0.7833333333333333,41,0.5853658536585366,0.36735687265816497,-3.0018912479512627,11.353505475191582,1.0765578222065098,57,1.0,61,0.4426229508196721,0.9190446533230906,-0.8782283075284599,-0.014397185369319014,-4.896388895675014,1.0,21,0.42857142857142855,-0.06796636492241592,-4.896388895675015,7.085228393348684,-8.06763837217702,61,0.0
QQQ,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr-0.006_maxday1,3966,1552,795,6.490765414575298,False,40,0.625,2.175959420186648,6.090731115680589,0.15226827789201472,-1.2812221293076753,0.575,40,0.625,0.28141935604683066,-1.2812221293076753,4.259342133051213,0.699315410934089,19,1.0,19,0.5263157894736842,1.3216878492019104,1.1557689790588044,0.06082994626625286,-1.9160364177313092,0.3684210526315789,19,0.5263157894736842,0.023411348835963075,-1.9160364177313092,3.329948498388255,2.8811540703402376,19,1.0
QQQ,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr0.050_maxday3,4763,1550,802,6.6497485439425175,False,123,0.5528455284552846,1.6912909009712744,12.63957946289856,0.1027608086414517,-3.766995044460476,0.10569105691056911,42,0.6190476190476191,0.3017712844217052,-3.7669950444604776,10.657075294179231,0.8431510973495084,60,1.0,68,0.4264705882352941,0.8598813042008316,-2.7373335145132023,-0.040254904625194154,-7.961530092745459,0.0,23,0.391304347826087,-0.4689656218507168,-7.230495714596174,11.123467691861379,-4.063614328646956,68,0.0
QQQ,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr0.000_maxday2,5518,1597,624,6.229245659950131,False,88,0.5681818181818182,1.5765245649944768,8.994934114812724,0.10221516039559914,-2.64729193440962,0.3522727272727273,44,0.5681818181818182,0.16731420923368856,-2.612116088727542,9.529678080869097,1.059449458909962,42,1.0,38,0.39473684210526316,0.554628754936792,-5.87026320376966,-0.15448061062551738,-5.889253136399833,0.5263157894736842,19,0.3684210526315789,-0.2135181929904607,-5.870263203769661,4.72399233891057,-0.8047326286625447,38,0.0
QQQ,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr-0.100_maxday1,6313,1426,742,5.350921395500258,False,42,0.5952380952380952,1.7481655111981946,5.903521024486628,0.14056002439253876,-2.323857828653049,0.19047619047619047,42,0.5952380952380952,0.28824525863471506,-2.323857828653049,5.132532886630141,0.8694019832133092,19,0.5,22,0.5,1.1925057227285707,0.7936214379672168,0.036073701725782586,-2.0814283497611337,0.22727272727272727,22,0.5,0.03000001112620032,-2.0814283497611337,3.519934993749593,4.4352821450559095,22,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr0.199_maxday1,7115,1366,692,6.193731679848071,False,31,0.5806451612903226,2.272052342103489,7.141004544112256,0.23035498529394374,-3.1810108879343195,0.2903225806451613,31,0.5806451612903226,0.12380947767562023,-3.1810108879343195,8.50247341836373,1.1906550914288385,14,1.0,13,0.6923076923076923,3.9049246740865864,4.623552577509515,0.355657890577655,-1.2000000000000002,0.3076923076923077,13,0.6923076923076923,0.38092783565969235,-1.2000000000000002,4.764001243954613,1.030376785835266,13,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr-999.000_maxday2,7739,1434,550,6.119826230894179,False,84,0.6428571428571429,1.606776873683747,7.941284813261638,0.0945391049197814,-2.7391947377959927,0.7142857142857143,42,0.5714285714285714,0.1443426614386793,-2.7391947377959918,6.580698369677185,0.828669229781014,40,1.0,37,0.6216216216216216,1.4673159061466952,3.210165009888513,0.08676121648347332,-2.5054319596498598,0.40540540540540543,19,0.5789473684210527,0.1436488620645987,-2.470285414980876,5.808903345354198,1.8095341913766412,37,1.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.139_maxday1,8481,1242,764,5.661765464751213,False,34,0.5882352941176471,1.7357326139075473,4.091887384737116,0.12034962896285635,-1.8326384992072198,0.5882352941176471,34,0.5882352941176471,0.26096263341492365,-1.8326384992072198,3.8874339537312954,0.9500344433308603,17,1.0,22,0.5,1.6781300333290394,2.9038096514202154,0.13199134779182797,-1.2000000000000002,0.5454545454545454,22,0.5,-0.023395595857969853,-1.2000000000000002,4.682250260295379,1.6124508223207232,22,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.224_maxday2,9173,1314,636,6.144017880335068,False,61,0.5409836065573771,1.6902824989608547,7.549500386855249,0.12376230142385655,-2.1854062526154956,0.5245901639344263,35,0.5714285714285714,0.21007619250145493,-2.1696333221639232,7.902531339344449,1.0467621609906632,25,1.0,26,0.34615384615384615,0.4275337633545894,-4.936087071919556,-0.18984950276613677,-5.929562855154579,0.38461538461538464,15,0.4,-0.3263157803926441,-5.929562855154579,3.2715566450532396,-0.6627834147546732,26,0.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr-999.000_maxday1,9723,1400,706,5.362180139578924,False,40,0.525,1.5099595442805829,4.102728039700908,0.1025682009925227,-2.4000000000000004,0.5,40,0.525,0.084165401466606,-2.4000000000000004,5.059620351473443,1.2332331810719515,18,1.0,20,0.35,0.3871706863322581,-3.9901999850901118,-0.19950999925450558,-5.2924393578841435,0.4,20,0.35,-0.5080867911315063,-5.2924393578841435,2.402239338114965,-0.6020348220869223,20,0.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr0.139_maxday1,10487,1342,617,4.732705983887077,False,35,0.45714285714285713,1.1421642171535524,1.1414908765717504,0.03261402504490715,-1.3973826467474337,0.2,35,0.45714285714285713,-0.04273500354724069,-1.3973826467474337,4.728385012053867,4.142288921532748,17,1.0,19,0.42105263157894735,0.4975621590241364,-2.4744256913070783,-0.13023293112142517,-3.4609056566986034,0.47368421052631576,19,0.42105263157894735,-0.2027027000903735,-3.4609056566986034,1.9031466380363329,-0.7691266077305494,19,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_v1_QQQ",
    "tickers": [
      "QQQ"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 2,
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
    "ticker_QQQ",
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
  "data_rows": 12446
}
```