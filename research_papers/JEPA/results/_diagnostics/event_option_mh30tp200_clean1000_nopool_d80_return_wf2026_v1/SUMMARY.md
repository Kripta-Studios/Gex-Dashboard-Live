# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 410,
  "win_rate": 0.44878048780487806,
  "profit_factor": 1.0301390166755713,
  "pnl_return": 3.0442731034872352,
  "avg_return": 0.007425056349968867,
  "max_drawdown": -17.55141564802129,
  "call_rate": 0.47560975609756095,
  "days_with_trades": 104,
  "daily_win_rate": 0.4519230769230769,
  "median_daily_return": -0.21587283367614324,
  "daily_max_drawdown": -20.867221056241902,
  "top5_day_return": 26.682322035172206,
  "top5_share_of_pnl": 8.764759641507665,
  "min_month_trades": 0,
  "positive_month_rate": 0.3333333333333333
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 87,
    "win_rate": 0.42528735632183906,
    "profit_factor": 0.923361904287839,
    "pnl_return": -1.690894239328923,
    "avg_return": -0.019435565969297967,
    "max_drawdown": -5.655388247080388,
    "call_rate": 0.4942528735632184,
    "days_with_trades": 87,
    "daily_win_rate": 0.42528735632183906,
    "median_daily_return": -0.1428571664007805,
    "daily_max_drawdown": -5.655388247080388,
    "top5_day_return": 8.287439719215634,
    "top5_share_of_pnl": -4.9012170758265325,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  },
  "SPXW": {
    "trades": 177,
    "win_rate": 0.423728813559322,
    "profit_factor": 0.8524352612708019,
    "pnl_return": -6.846162981690727,
    "avg_return": -0.03867888690220749,
    "max_drawdown": -17.55141564802129,
    "call_rate": 0.5310734463276836,
    "days_with_trades": 95,
    "daily_win_rate": 0.49473684210526314,
    "median_daily_return": -0.0538505989294884,
    "daily_max_drawdown": -16.683609433781363,
    "top5_day_return": 12.051482601739762,
    "top5_share_of_pnl": -1.7603265703679656,
    "min_month_trades": 0,
    "positive_month_rate": 0.16666666666666666
  },
  "SPY": {
    "trades": 146,
    "win_rate": 0.4931506849315068,
    "profit_factor": 1.3558007407201007,
    "pnl_return": 11.581330324506887,
    "avg_return": 0.07932418030484169,
    "max_drawdown": -3.3516667388338828,
    "call_rate": 0.3972602739726027,
    "days_with_trades": 84,
    "daily_win_rate": 0.5238095238095238,
    "median_daily_return": 0.0588269577574847,
    "daily_max_drawdown": -3.3113283746703317,
    "top5_day_return": 13.647804298933954,
    "top5_share_of_pnl": 1.1784314855482765,
    "min_month_trades": 0,
    "positive_month_rate": 0.6666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.100_maxday2,4362,4797,779,5.748376517104867,False,253,0.47035573122529645,1.2054800074671943,12.308234181784425,0.0486491469635748,-5.068747574527793,0.47035573122529645,128,0.4453125,-0.15406488596287748,-5.068747574527797,12.01428491558887,0.9761176735952437,37,0.6666666666666666,40,0.425,0.6673357200596413,-3.2528328768695425,-0.08132082192173856,-4.376394310328422,0.675,20,0.5,-0.07751214984900517,-4.233537111863448,3.6243899178731747,-1.1142256780684074,40,0.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,5225,4713,616,-9.999999999999996e+17,True,375,0.408,1.0804646438957548,8.27203401062391,0.02205875736166376,-21.72077336069011,0.037333333333333336,126,0.40476190476190477,-0.622443076346222,-21.720773360690075,26.27079057066243,3.175856208632897,55,0.5,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.000_maxday3,6003,4551,793,5.386001397381124,False,368,0.5108695652173914,1.1791068127312163,14.399063943275465,0.03912789115020507,-9.419210209179392,0.9103260869565217,124,0.5241935483870968,0.04117197422064567,-8.588108192387953,16.804298320780966,1.1670410234290802,55,0.8333333333333334,66,0.3181818181818182,0.6924820340671549,-5.650701813438259,-0.08561669414300392,-13.970790553532632,0.8181818181818182,22,0.3181818181818182,-0.5278650276908718,-13.102984339292705,8.644153713942655,-1.5297486930535773,66,0.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.100_maxday2,6817,4530,793,6.233963266463534,False,247,0.41295546558704455,1.3202603165930336,20.98771625882179,0.08497051116931899,-8.521113914806486,0.15789473684210525,124,0.46774193548387094,-0.15793545012031046,-8.49056735744438,19.377140883793736,0.9232610468349037,37,0.8333333333333334,37,0.43243243243243246,0.812877920705357,-2.0915366668016464,-0.05652801802166612,-4.222337983530425,0.1891891891891892,19,0.47368421052631576,-0.37473180950957186,-4.222337983530425,6.347436009470276,-3.0348193795601497,37,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.300_maxday1,7669,4471,783,7.355103661427261,False,78,0.5512820512820513,2.0278003138314844,15.94020212611296,0.20436156571939693,-2.643386226655588,0.3076923076923077,78,0.5512820512820513,0.13754306815283235,-2.643386226655588,9.314080629229677,0.584313834638992,10,1.0,13,0.6153846153846154,0.8638459743799783,-0.3324903797376151,-0.025576183056739622,-1.424885209650687,0.15384615384615385,13,0.6153846153846154,0.019027516710269587,-1.424885209650687,2.0389846576782458,-6.1324621160086235,13,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.097_maxday1,8317,4606,736,6.4288034954226925,False,124,0.5806451612903226,1.6766163379428056,15.468154257898366,0.12474317949918037,-5.388733772722958,0.6370967741935484,124,0.5806451612903226,0.06388585530026503,-5.388733772722958,7.9122527205424555,0.5115188657045033,19,0.8333333333333334,21,0.6190476190476191,1.9696688443403427,4.481398755156334,0.2133999407217302,-3.4940092554748357,0.19047619047619047,21,0.6190476190476191,0.13429600039331313,-3.4940092554748357,6.225625396085769,1.3892147823093208,21,1.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.100_maxday1,3966,4515,692,5.62243572541758,False,128,0.5078125,1.3889112595650153,9.88560479067657,0.0772312874271607,-4.161100844736902,0.390625,128,0.5078125,0.02982951032650294,-4.161100844736902,8.76935452400414,0.8870832599210114,19,0.6666666666666666,20,0.4,0.707338160563627,-1.340244234842805,-0.06701221174214025,-3.536530398969221,0.4,20,0.4,-0.06415926005856815,-3.536530398969221,2.849265240526484,-2.125929861478322,20,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,4763,4410,550,-9.999999999999996e+17,True,374,0.39572192513368987,1.047422218729352,4.587911239994458,0.012267142352926358,-25.51907049859532,0.034759358288770054,126,0.40476190476190477,-0.43545015451247,-24.319070498595316,25.755223066636688,5.613714328672976,57,0.6666666666666666,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.100_maxday1,5518,4205,764,4.567197298122774,False,98,0.47959183673469385,1.1371553531371512,3.067291481279738,0.03129889266611977,-2.92881397077999,0.6224489795918368,98,0.47959183673469385,-0.03467293483959716,-2.92881397077999,8.54517657839368,2.7859030126567736,14,0.5,20,0.4,0.8329324165130211,-0.7477707656572693,-0.03738853828286347,-2.1027527520745655,0.65,20,0.4,-0.1679633710831141,-2.1027527520745655,3.5523691190754407,-4.750612463370388,20,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.282_maxday1,6313,4174,636,6.168289173873456,False,86,0.4418604651162791,1.4791637376546896,10.463768787694251,0.12167173008946804,-3.0575513027436307,0.1511627906976744,86,0.4418604651162791,-0.10462322235107424,-3.0575513027436307,10.0,0.9556786090075252,12,1.0,11,0.36363636363636365,0.38776131615152204,-2.1915098518348217,-0.19922816834862014,-2.4400551561792545,0.0,11,0.36363636363636365,-0.29551448465225993,-2.4400551561792545,1.1040046328174378,-0.5037643941655657,11,0.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.053_maxday1,7115,4008,706,5.201030956473487,False,120,0.475,1.3288999983109915,8.46514912575579,0.07054290938129824,-5.032222627021986,0.5666666666666667,120,0.475,-0.04376845934043622,-5.032222627021986,8.518793726576941,1.006337112320672,18,0.6666666666666666,20,0.5,1.2195117081648046,1.0953960515919325,0.05476980257959663,-1.9901486383110518,0.7,20,0.5,0.003263196984707728,-1.9901486383110518,5.357010238381763,4.890477951418989,20,1.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.128_maxday1,7739,4090,617,5.415387790439404,False,109,0.47706422018348627,1.3169055124143587,7.02253976990737,0.06442697036612266,-2.9472320562953764,0.8532110091743119,109,0.47706422018348627,-0.06521733046028577,-2.9472320562953764,6.412701647892065,0.9131598905813887,17,0.6666666666666666,16,0.4375,1.336438529880333,1.4932345614140412,0.09332716008837758,-1.7999999999999998,0.5,16,0.4375,-0.1739968775552998,-1.7999999999999998,5.68962730626852,3.810270304004108,16,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday2,4331,4822,778,6.752609800283823,False,255,0.5294117647058824,1.3637205174579936,18.347700623141257,0.07195176714957356,-4.124336915502479,0.6745098039215687,128,0.5390625,0.09038638171220825,-4.124336915502475,11.205221945290024,0.6107153247942853,37,0.6666666666666666,40,0.525,1.4640456567763596,3.524643874707574,0.08811609686768936,-3.3516667388338828,0.625,20,0.55,0.09744043947306796,-2.4974294548077722,6.612286847743518,1.876015587047674,40,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,ABSTAIN_INVALID_VAL,5201,4730,615,-9.999999999999996e+17,True,375,0.416,1.0903010113969078,8.927974622971794,0.023807932327924785,-21.493726571831967,0.037333333333333336,126,0.4126984126984127,-0.5738547601397044,-21.493726571831942,25.73091241860827,2.882054833848015,55,0.5,0,,,0.0,,0.0,,0,,,0.0,0.0,,0,
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.356_maxday2,5987,4559,799,5.565024038977519,False,47,0.574468085106383,1.6594520025910469,5.8862844002728885,0.12524009362282743,-2.6666922590524633,0.6595744680851063,30,0.6,0.1538299505099593,-2.57335896931567,8.241772467137361,1.4001655215224178,4,0.8333333333333334,11,0.7272727272727273,3.964332011160626,3.8530399179571355,0.3502763561779214,-0.699800394642216,0.7272727272727273,6,0.6666666666666666,0.7744166851769853,-0.699800394642216,4.552840312599352,1.1816229287894966,11,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday2,6807,4538,689,7.227432194104992,False,249,0.46184738955823296,1.4101408530745072,24.197948060488784,0.09718051429915174,-5.747044657383714,0.2570281124497992,125,0.48,-0.09186019068476337,-5.61636282765657,18.434261515326934,0.7618109382351725,37,0.8333333333333334,36,0.4444444444444444,0.9406148484155867,-0.5752549338712064,-0.015979303718644623,-3.311328374670333,0.25,18,0.3888888888888889,-0.17868228702627914,-3.311328374670332,6.977516257371491,-12.129433137436912,36,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.074_maxday2,7659,4375,775,6.985811847565673,False,228,0.5087719298245614,1.487914104620543,24.097273999588968,0.10568979824381126,-7.183788692849266,0.3684210526315789,116,0.5,0.03007960663158432,-7.183788692849234,16.478692204451505,0.6838405126128617,34,0.8333333333333334,38,0.42105263157894735,1.4401906617067184,3.591132579754712,0.09450348894091347,-3.171465654572189,0.3157894736842105,19,0.5789473684210527,0.27790707960398564,-2.6973368899945203,7.741946109535567,2.1558508179790934,38,1.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-999.000_maxday1,8306,4503,724,5.797405217727276,False,121,0.512396694214876,1.3828245043325276,9.253795069008794,0.07647764519841978,-3.6398837215682973,0.512396694214876,121,0.512396694214876,0.005797095840604838,-3.6398837215682973,8.61649837479788,0.9311313153729504,18,0.8333333333333334,21,0.5238095238095238,1.2044423194460212,1.187768885958671,0.0565604231408891,-3.246043591094226,0.19047619047619047,21,0.5238095238095238,0.0328466838890733,-3.246043591094226,5.345238933970614,4.500234849691629,21,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_tp200_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30tp200_clean1000_nopool_d80_return_wf2026_v1",
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
    "delta_bucket": 80,
    "label_mode": "return",
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
      0.0,
      0.1,
      0.2,
      0.3,
      0.4,
      0.5,
      0.75,
      1.0,
      1.25,
      1.5
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
    "entry_time_min_et": "10:00",
    "allow_invalid_val_deploy": false,
    "deploy_month": "",
    "deploy_select_end_month": "",
    "export_deploy_model": false,
    "exclude_months": [],
    "skip_walkforward": false,
    "resume": false,
    "seed": 20260617
  },
  "feature_count": 241,
  "features": [
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
    },
    {
      "threshold": 1.25,
      "max_trades_per_day": 1
    },
    {
      "threshold": 1.25,
      "max_trades_per_day": 2
    },
    {
      "threshold": 1.25,
      "max_trades_per_day": 3
    },
    {
      "threshold": 1.5,
      "max_trades_per_day": 1
    },
    {
      "threshold": 1.5,
      "max_trades_per_day": 2
    },
    {
      "threshold": 1.5,
      "max_trades_per_day": 3
    }
  ],
  "data_rows": 39638
}
```