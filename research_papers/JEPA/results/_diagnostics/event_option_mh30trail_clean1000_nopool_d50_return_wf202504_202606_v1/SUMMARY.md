# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 484,
  "win_rate": 0.5413223140495868,
  "profit_factor": 1.2677843918852327,
  "pnl_return": 34.50609422399511,
  "avg_return": 0.07129358310742792,
  "max_drawdown": -9.648990197036305,
  "call_rate": 0.29338842975206614,
  "days_with_trades": 203,
  "daily_win_rate": 0.49261083743842365,
  "median_daily_return": -0.061618348883500595,
  "daily_max_drawdown": -9.276305340249046,
  "top5_day_return": 20.822317014177557,
  "top5_share_of_pnl": 0.6034388267478263,
  "min_month_trades": 0,
  "positive_month_rate": 0.4666666666666667
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 484,
    "win_rate": 0.5413223140495868,
    "profit_factor": 1.2677843918852327,
    "pnl_return": 34.50609422399511,
    "avg_return": 0.07129358310742792,
    "max_drawdown": -9.648990197036305,
    "call_rate": 0.29338842975206614,
    "days_with_trades": 203,
    "daily_win_rate": 0.49261083743842365,
    "median_daily_return": -0.061618348883500595,
    "daily_max_drawdown": -9.276305340249046,
    "top5_day_return": 20.822317014177557,
    "top5_share_of_pnl": 0.6034388267478263,
    "min_month_trades": 0,
    "positive_month_rate": 0.4666666666666667
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202508,202508,202501,202501,202502,"202502,202503,202504,202505,202506,202507",202507,thr0.300_maxday3,765,4460,778,6.855308236497606,False,315,0.5523809523809524,1.2669051734848042,21.487612233386354,0.06821464201075034,-6.693918038394305,0.39365079365079364,114,0.5526315789473685,0.2158075728978004,-6.084819753440517,16.128602584292963,0.7506000391813272,46,1.0,58,0.5862068965517241,1.428231166235961,5.582743167744895,0.09625419254732578,-3.693495835107192,0.5689655172413793,20,0.6,0.24467226999968972,-2.7434958752618996,8.926714573801164,1.5989835651721445,58,1.0
SPXW,202509,202509,"202501,202502",202502,202503,"202503,202504,202505,202506,202507,202508",202508,thr0.000_maxday3,1392,4611,814,6.593969668882256,False,373,0.5522788203753352,1.26257417405423,24.502879355029933,0.06569136556308293,-9.025381246456904,0.5093833780160858,125,0.608,0.31354664449947334,-8.033961513045695,14.446860943400356,0.5895985012240904,58,0.8333333333333334,63,0.5555555555555556,1.426617176138972,6.888472249040483,0.10934082934984893,-4.547990153550378,0.3492063492063492,21,0.5714285714285714,0.3921569019830454,-4.547990153550377,9.564419649907403,1.3884674720493593,63,1.0
SPXW,202510,202510,"202501,202502,202503",202503,202504,"202504,202505,202506,202507,202508,202509",202509,thr-999.000_maxday3,2116,4701,852,5.666027594479007,False,373,0.5361930294906166,1.1739111456886178,16.743431692266935,0.04488855681572905,-8.352405498985156,0.42091152815013405,125,0.56,0.18729223187088617,-7.7524054989851665,13.830974224116606,0.8260537312971828,58,0.6666666666666666,68,0.6764705882352942,2.1356095186870583,14.485481435271199,0.21302178581281175,-3.348349757855635,0.36764705882352944,23,0.6521739130434783,0.6357076608427393,-2.748349757855636,12.439417933682076,0.858750742201285,68,1.0
SPXW,202511,202511,"202501,202502,202503,202504",202504,202505,"202505,202506,202507,202508,202509,202510",202510,thr-0.100_maxday3,2765,4904,648,9.638294512961643,False,381,0.5853018372703412,1.5110379350813652,45.11279755720274,0.11840629280105706,-6.552565397467184,0.45931758530183725,128,0.640625,0.4463868223765476,-6.233177612575242,19.76989568856341,0.4382325361998512,58,1.0,55,0.6363636363636364,1.8491704083807734,10.19004490056928,0.18527354364671417,-4.902813167901094,0.32727272727272727,19,0.631578947368421,0.36309533405736905,-3.966326560666955,11.907404125235681,1.1685330380213004,55,1.0
SPXW,202512,202512,"202501,202502,202503,202504,202505",202505,202506,"202506,202507,202508,202509,202510,202511",202511,thr0.330_maxday3,3585,4732,842,7.196208017029072,False,221,0.5656108597285068,1.402627821757557,22.28038650128324,0.10081622851259384,-4.630289902759031,0.3031674208144796,94,0.5319148936170213,0.180435056415572,-4.544105539570946,15.30735610682178,0.6870327902947354,28,0.8333333333333334,36,0.3611111111111111,0.9037132226357192,-1.209120805271613,-0.03358668903532258,-4.163103066605041,0.19444444444444445,15,0.3333333333333333,-0.3430554626532517,-3.6956170114958384,6.206154748894949,-5.132783028657603,36,0.0
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.299_maxday3,4362,4797,779,7.514861226854443,False,257,0.5525291828793775,1.4285830569191202,28.310375908199802,0.11015710470116655,-7.38466063289043,0.2607003891050584,111,0.5765765765765766,0.282619131179083,-7.384660632890387,21.55459649540909,0.7613673716415058,30,1.0,40,0.525,1.116497271885172,1.3280688994909604,0.03320172248727401,-8.723626346256893,0.325,19,0.42105263157894735,-0.24285711548766253,-8.443226413395566,8.956794936413125,6.7442245954605236,40,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.050_maxday3,5225,4713,616,7.464700658632971,False,374,0.5508021390374331,1.3134453918244213,30.813701721042886,0.08238957679423231,-9.000000000000021,0.0481283422459893,126,0.5873015873015873,0.25526522913709443,-9.000000000000004,18.979006063294367,0.6159274933960134,55,1.0,56,0.44642857142857145,0.9242545652837364,-1.4088650857224971,-0.02515830510218745,-5.649048854381215,0.0,19,0.3684210526315789,-0.8084906610996081,-5.3999999999999995,12.209047155572701,-8.665873886222137,56,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.100_maxday1,6003,4551,793,8.183232558270497,False,124,0.6290322580645161,1.8722504602875458,23.25203811470585,0.18751643640891816,-2.4000000000000057,0.49193548387096775,124,0.6290322580645161,0.3259339576346798,-2.4000000000000057,12.068259573871728,0.5190194302253059,19,1.0,22,0.5,1.3054271365015158,1.900627035957327,0.08639213799806032,-1.8745641650641756,0.5454545454545454,22,0.5,-0.047402656600427195,-1.8745641650641756,5.890823046505622,3.0994103183102792,22,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.477_maxday3,6817,4530,793,8.701068684452139,False,53,0.7358490566037735,3.3616362154375627,18.47484066303532,0.3485818993025532,-1.8000000000000007,0.09433962264150944,37,0.6756756756756757,0.6166665818956163,-0.9897662508755118,10.157185211763704,0.5497847259969241,4,1.0,8,0.5,0.6512496145884592,-0.7457103893975933,-0.09321379867469916,-1.2225210487636313,0.0,5,0.4,-0.022521048763631146,-1.2225210487636313,-0.7457103893975933,1.0,8,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.200_maxday2,7669,4471,783,7.36094060158371,False,234,0.5427350427350427,1.431150784926288,26.899071312383754,0.11495329620676818,-6.421037511195351,0.21367521367521367,121,0.5041322314049587,0.15000000000000002,-6.185514899727532,17.625833654254002,0.655258073766266,34,0.8333333333333334,39,0.48717948717948717,0.7814317434662768,-2.62281907840468,-0.06725177124114563,-4.331106628033695,0.15384615384615385,20,0.35,-0.3223592867770749,-4.331106628033695,6.075473640198621,-2.3163906691932428,39,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.100_maxday2,8317,4606,736,8.248407201205788,False,248,0.5887096774193549,1.5060957482009552,29.999130641601475,0.12096423645807046,-4.119355948376612,0.375,124,0.5,0.0197452408433072,-4.119355948376597,15.180700241220732,0.5060380056536974,38,0.8333333333333334,39,0.48717948717948717,1.0097643245597798,0.11717189471735856,0.0030044075568553476,-3.9035354869062573,0.15384615384615385,20,0.45,-0.09630510083385857,-2.7651538357897563,6.685468981312257,57.056933298201855,39,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_v1",
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
  "data_rows": 39671
}
```