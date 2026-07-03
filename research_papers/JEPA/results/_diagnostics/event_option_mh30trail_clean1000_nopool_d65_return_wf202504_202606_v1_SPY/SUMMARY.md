# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 310,
  "win_rate": 0.5387096774193548,
  "profit_factor": 1.1064400935784715,
  "pnl_return": 8.301152875932797,
  "avg_return": 0.02677791250300902,
  "max_drawdown": -11.034181159991972,
  "call_rate": 0.38387096774193546,
  "days_with_trades": 214,
  "daily_win_rate": 0.5233644859813084,
  "median_daily_return": 0.17845295334071948,
  "daily_max_drawdown": -10.761338542514233,
  "top5_day_return": 11.216511585980214,
  "top5_share_of_pnl": 1.3511992555274823,
  "min_month_trades": 0,
  "positive_month_rate": 0.4666666666666667
}
```

## Per Ticker

```json
{
  "SPY": {
    "trades": 310,
    "win_rate": 0.5387096774193548,
    "profit_factor": 1.1064400935784715,
    "pnl_return": 8.301152875932797,
    "avg_return": 0.02677791250300902,
    "max_drawdown": -11.034181159991972,
    "call_rate": 0.38387096774193546,
    "days_with_trades": 214,
    "daily_win_rate": 0.5233644859813084,
    "median_daily_return": 0.17845295334071948,
    "daily_max_drawdown": -10.761338542514233,
    "top5_day_return": 11.216511585980214,
    "top5_share_of_pnl": 1.3511992555274823,
    "min_month_trades": 0,
    "positive_month_rate": 0.4666666666666667
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202508,202508,202501,202501,202502,"202502,202503,202504,202505,202506,202507",202507,thr0.241_maxday1,740,4461,786,5.363304188090615,False,110,0.5636363636363636,1.2791138210544752,6.400609900245507,0.05818736272950461,-2.6703606825039476,0.35454545454545455,110,0.5636363636363636,0.26087471213330526,-2.6703606825039476,4.942699809457837,0.7722232547351856,14,0.6666666666666666,13,0.38461538461538464,0.9903544261786627,-0.04352012135308769,-0.003347701642545207,-2.423465008758324,0.0,13,0.38461538461538464,-0.6,-2.423465008758324,4.468406505222074,-102.67449552745897,13,0.0
SPY,202509,202509,"202501,202502",202502,202503,"202503,202504,202505,202506,202507,202508",202508,thr0.200_maxday1,1373,4614,820,5.637097848851637,False,123,0.5447154471544715,1.3515410305299318,9.620440171425347,0.07821496074329551,-4.463094094431487,0.5121951219512195,123,0.5447154471544715,0.20168057040941068,-4.463094094431487,7.877592467190364,0.8188390891498298,20,0.8333333333333334,19,0.3684210526315789,0.6352713297655062,-2.022383266001497,-0.10644122452639457,-2.2222884522832937,0.5263157894736842,19,0.3684210526315789,-0.35204083866896263,-2.2222884522832937,2.830992726175109,-1.3998299796914033,19,0.0
SPY,202510,202510,"202501,202502,202503",202503,202504,"202504,202505,202506,202507,202508,202509",202509,thr0.000_maxday1,2094,4713,852,6.313488861262446,False,125,0.568,1.474371132754856,12.0548586599384,0.0964388692795072,-3.931413453683847,0.464,125,0.568,0.2599009807501782,-3.931413453683847,6.496976357957952,0.5389508530323284,20,1.0,23,0.6521739130434783,1.285543298516765,1.3706078328804723,0.05959164490784662,-1.5418452278522465,0.391304347826087,23,0.6521739130434783,0.3263547255091559,-1.5418452278522465,2.7812646561622643,2.0292198756205506,23,1.0
SPY,202511,202511,"202501,202502,202503,202504",202504,202505,"202505,202506,202507,202508,202509,202510",202510,thr0.000_maxday1,2740,4919,648,6.567064932942777,False,128,0.6171875,1.5202135518164674,12.712496973084415,0.09931638260222199,-3.3206563423997464,0.4296875,128,0.6171875,0.27585918605061277,-3.3206563423997464,6.38666884656373,0.5023929492440337,20,1.0,19,0.631578947368421,1.5451114167010014,2.2894679501442057,0.12049831316548451,-1.8000000000000003,0.5263157894736842,19,0.631578947368421,0.33802829759978814,-1.8000000000000003,3.865842251472859,1.6885330284834794,19,1.0
SPY,202512,202512,"202501,202502,202503,202504,202505",202505,202506,"202506,202507,202508,202509,202510,202511",202511,thr0.050_maxday3,3554,4753,850,6.069438562359734,False,371,0.5444743935309974,1.2057600233987524,18.20025890660445,0.049057301635052425,-6.436529783465726,0.4797843665768194,126,0.5476190476190477,0.1183070215124491,-5.836529783465732,16.34232988349605,0.8979174399308022,55,0.5,65,0.5846153846153846,1.2701736184559498,3.772356578080043,0.05803625504738528,-3.2854049455411483,0.5538461538461539,22,0.5909090909090909,0.27429765505481385,-2.6854049455411477,8.271080944151032,2.192550140199269,65,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,4331,4826,779,5.081227152273567,False,128,0.5546875,1.1768502879533622,5.115303128931415,0.03996330569477668,-3.920945529569913,0.5703125,128,0.5546875,0.22801512993445738,-3.920945529569913,6.279156563612098,1.2275238446961425,19,0.8333333333333334,20,0.7,3.0358354800812175,6.0670986804250475,0.30335493402125235,-1.2000000000000002,0.75,20,0.7,0.32884093292499117,-1.2000000000000002,5.922603160359866,0.976183753112277,20,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.617_maxday2,5201,4735,615,5.329587141593629,False,185,0.5621621621621622,1.1999075660887955,8.914791275011412,0.04818806094600763,-5.560286773070145,0.0,100,0.54,0.13405929758921598,-5.331031292876596,10.705641195956819,1.200885232833801,18,0.8333333333333334,34,0.5588235294117647,1.0523941049062588,0.45540262252422714,0.013394194780124328,-3.0246262311816974,0.0,18,0.4444444444444444,-0.09979021748897376,-3.0,5.319118444750317,11.68003472458559,34,1.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.050_maxday1,5987,4564,799,5.56308246970139,False,123,0.5528455284552846,1.275550477401925,7.641631119696453,0.0621270822739549,-3.351033268951003,0.6260162601626016,123,0.5528455284552846,0.2583932486263203,-3.351033268951003,8.303584597386902,1.0866246312235945,18,0.8333333333333334,22,0.5,1.2892751800291418,1.6567555294922234,0.07530706952237379,-2.990106071932248,0.5909090909090909,22,0.5,0.09195840027731983,-2.990106071932248,4.439101724658929,2.6793945429109045,22,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday2,6807,4543,689,7.203719707630472,False,249,0.5662650602409639,1.374503198535027,21.72835735381296,0.08726247933258217,-4.4073574112304765,0.3172690763052209,125,0.488,-0.01814164426745213,-4.407357411230475,13.58028148695358,0.625002675803768,37,0.8333333333333334,36,0.5277777777777778,0.976124077300672,-0.2209570036979468,-0.006137694547165189,-4.595151306286485,0.2777777777777778,18,0.3888888888888889,-0.16208528836714908,-4.322308688808756,6.45721360726635,-29.223846717678644,36,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.100_maxday2,7659,4380,775,7.363226346911644,False,234,0.5769230769230769,1.4325483831248507,23.15654976719587,0.09895961438972593,-4.546968600049574,0.24358974358974358,119,0.5294117647058824,0.05148917506772854,-4.294158923628196,12.765790764912092,0.5512820732472167,33,0.8333333333333334,38,0.3684210526315789,0.5235909594670722,-6.439029853705488,-0.16944815404488126,-6.439029853705488,0.2894736842105263,19,0.3684210526315789,-0.8981366551606256,-6.439029853705488,5.24600769507467,-0.8147202007544249,38,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.100_maxday1,8307,4507,724,6.59220754662684,False,121,0.6033057851239669,1.5849399913330064,15.043995075836465,0.12433053781683029,-4.615541558030098,0.39669421487603307,121,0.6033057851239669,0.29320987200086535,-4.615541558030098,7.279378283735889,0.48387268455225463,18,1.0,21,0.6190476190476191,1.2948654014884582,1.4153539271445987,0.0673978060545047,-2.4000000000000004,0.23809523809523808,21,0.6190476190476191,0.26709405236303896,-2.4000000000000004,3.9885112672691347,2.818031017383577,21,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_v1_SPY",
    "tickers": [
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
    "lgb_jobs": 4,
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