# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 331,
  "win_rate": 0.4259818731117825,
  "profit_factor": 0.6119579881562532,
  "pnl_return": -43.865182840639235,
  "avg_return": -0.13252321099891007,
  "max_drawdown": -45.7651828406394,
  "call_rate": 0.2084592145015106,
  "days_with_trades": 122,
  "daily_win_rate": 0.3524590163934426,
  "median_daily_return": -0.39999999999999997,
  "daily_max_drawdown": -44.96518284063927,
  "top5_day_return": 10.0,
  "top5_share_of_pnl": -0.2279712371501943,
  "min_month_trades": 41,
  "positive_month_rate": 0.0
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 82,
    "win_rate": 0.43902439024390244,
    "profit_factor": 0.647208349433316,
    "pnl_return": -9.600420310806005,
    "avg_return": -0.11707829647324396,
    "max_drawdown": -10.807055398497146,
    "call_rate": 0.3170731707317073,
    "days_with_trades": 81,
    "daily_win_rate": 0.43209876543209874,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -10.807055398497146,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.26040526550551746,
    "min_month_trades": 5,
    "positive_month_rate": 0.16666666666666666
  },
  "SPXW": {
    "trades": 107,
    "win_rate": 0.40186915887850466,
    "profit_factor": 0.5505123773096051,
    "pnl_return": -17.15357140628051,
    "avg_return": -0.1603137514605655,
    "max_drawdown": -19.053571406280494,
    "call_rate": 0.14018691588785046,
    "days_with_trades": 103,
    "daily_win_rate": 0.3786407766990291,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -19.053571406280494,
    "top5_day_return": 3.5,
    "top5_share_of_pnl": -0.20403914246793706,
    "min_month_trades": 14,
    "positive_month_rate": 0.16666666666666666
  },
  "SPY": {
    "trades": 142,
    "win_rate": 0.43661971830985913,
    "profit_factor": 0.6410274910038402,
    "pnl_return": -17.11119112355272,
    "avg_return": -0.12050134594051212,
    "max_drawdown": -17.911191123552708,
    "call_rate": 0.19718309859154928,
    "days_with_trades": 105,
    "daily_win_rate": 0.44761904761904764,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -17.911191123552715,
    "top5_day_return": 6.5,
    "top5_share_of_pnl": -0.379868353586038,
    "min_month_trades": 9,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.779_maxday2,4362,4797,779,1.2915578427822194,False,75,0.4533333333333333,0.6910569105691057,-7.6,-0.10133333333333333,-8.199999999999992,0.12,50,0.36,-0.09999999999999998,-7.6999999999999975,5.0,-0.6578947368421053,9,0.16666666666666666,14,0.5714285714285714,1.1111111111111112,0.40000000000000013,0.02857142857142858,-2.0,0.07142857142857142,10,0.4,-0.09999999999999998,-1.5000000000000002,2.9,7.249999999999997,14,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.400_maxday1,5225,4713,616,-0.24619133177218386,False,126,0.4444444444444444,0.681195706191513,-13.104193325798803,-0.10400153433173653,-14.204193325798785,0.07142857142857142,126,0.4444444444444444,-0.6,-14.204193325798785,2.5,-0.19077862618816374,19,0.16666666666666666,19,0.2631578947368421,0.29761904761904767,-5.899999999999999,-0.3105263157894736,-5.899999999999999,0.0,19,0.2631578947368421,-0.6,-5.899999999999999,2.5,-0.4237288135593221,19,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.700_maxday1,6003,4551,793,5.510314989500877,False,75,0.6133333333333333,1.3613303222982205,6.104761847094525,0.081396824627927,-2.3,0.64,75,0.6133333333333333,0.5,-2.3,2.5,0.40951638452363864,10,0.8333333333333334,18,0.5,0.8333333333333334,-0.8999999999999999,-0.049999999999999996,-1.7999999999999998,0.6666666666666666,18,0.5,-0.04999999999999999,-1.7999999999999998,2.5,-2.777777777777778,18,0.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday1,6817,4530,793,0.7042552949779748,False,125,0.488,0.8140072181946808,-6.968955211040303,-0.055751641688322424,-15.308955172893327,0.08,125,0.488,-0.20895517289332977,-15.308955172893327,2.5,-0.35873383086742616,19,0.5,21,0.38095238095238093,0.46399055869212874,-4.053571406280507,-0.19302720982288127,-4.86250001192093,0.047619047619047616,21,0.38095238095238093,-0.6,-4.86250001192093,2.5,-0.6167400914972312,21,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.700_maxday1,7669,4471,783,3.5712837131107857,False,76,0.5526315789473685,1.0294117647058822,0.6000000000000006,0.007894736842105272,-4.5,0.18421052631578946,76,0.5526315789473685,0.5,-4.5,2.5,4.1666666666666625,10,0.3333333333333333,15,0.4,0.5555555555555556,-2.4,-0.16,-2.5,0.0,15,0.4,-0.6,-2.5,2.5,-1.0416666666666667,15,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.550_maxday1,8317,4606,736,3.0625691248093783,False,121,0.5206611570247934,0.8910611668287476,-3.7910713943595784,-0.03133116854842627,-6.4910713943595795,0.256198347107438,121,0.5206611570247934,0.5,-6.4910713943595795,2.5,-0.6594441887112817,18,0.6666666666666666,20,0.35,0.44871794871794884,-4.3,-0.215,-4.300000000000001,0.05,20,0.35,-0.6,-4.300000000000001,2.5,-0.5813953488372093,20,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-999.000_maxday1,3974,4522,692,2.8952623610153405,False,128,0.53125,0.9736617558846109,-0.9176108860374566,-0.007168835047167629,-7.864485979286128,0.546875,128,0.53125,0.5,-7.864485979286128,2.5,-2.724466370267049,19,0.3333333333333333,20,0.4,0.5555555555555557,-3.1999999999999997,-0.15999999999999998,-3.2,0.6,20,0.4,-0.6,-3.2,2.5,-0.7812500000000001,20,0.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.700_maxday1,4771,4417,550,-0.7485417524918294,False,125,0.432,0.6481473872414325,-14.657191761451317,-0.11725753409161054,-16.4571917614513,0.056,125,0.432,-0.6,-16.4571917614513,2.5,-0.17056473304627465,19,0.3333333333333333,19,0.3157894736842105,0.3937341245855775,-4.619354820102608,-0.24312393790013723,-4.6193548201026084,0.0,19,0.3157894736842105,-0.6,-4.6193548201026084,2.5,-0.54120111949843,19,0.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.793_maxday1,5526,4212,765,1.1278772009934077,False,53,0.41509433962264153,0.5992389976655288,-7.356615712350145,-0.13880407004434236,-8.367105254902398,0.09433962264150944,53,0.41509433962264153,-0.6,-8.367105254902398,2.5,-0.3398301743290802,6,0.3333333333333333,14,0.5,0.8333333333333333,-0.6999999999999998,-0.04999999999999999,-2.7,0.5714285714285714,14,0.5,-0.04999999999999999,-2.7,2.5,-3.571428571428572,14,0.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.760_maxday1,6323,4180,637,3.56547483235893,False,58,0.5344827586206896,0.9567901234567902,-0.6999999999999997,-0.012068965517241374,-4.4,0.27586206896551724,58,0.5344827586206896,0.5,-4.4,2.5,-3.571428571428573,8,0.6666666666666666,5,0.4,0.34016634533636303,-1.1877005783945465,-0.23754011567890929,-1.7999999999999998,0.2,5,0.4,-0.6,-1.7999999999999998,-1.1877005783945465,1.0,5,0.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.727_maxday2,7126,4014,712,2.725655962124519,False,81,0.5061728395061729,0.862736949555672,-3.1507697804349717,-0.038898392351049034,-5.7088235384349595,0.7160493827160493,57,0.45614035087719296,-0.09999999999999998,-5.7088235384349595,5.0,-1.5869137856558144,8,0.3333333333333333,6,0.6666666666666666,1.6666666666666667,0.7999999999999999,0.13333333333333333,-0.7000000000000001,0.3333333333333333,5,0.6,0.5,-0.7000000000000001,0.7999999999999999,1.0,6,1.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.650_maxday1,7752,4100,619,2.75240479849243,False,107,0.5233644859813084,0.9198165522316594,-2.407055366708011,-0.022495844548672997,-7.019354788313461,0.6261682242990654,107,0.5233644859813084,0.5,-7.019354788313461,2.5,-1.0386134172805108,14,0.3333333333333333,18,0.5,0.8664902382142453,-0.6933649123088514,-0.0385202729060473,-2.4,0.16666666666666666,18,0.5,0.053317543845574356,-2.4,2.5,-3.605605007722692,18,0.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.650_maxday1,4331,4822,779,1.2751130397574102,False,110,0.4727272727272727,0.7663029025852306,-7.929142004141367,-0.07208310912855788,-10.4563025161379,0.43636363636363634,110,0.4727272727272727,-0.5352941021787251,-10.4563025161379,2.5,-0.31529262544349157,17,0.3333333333333333,19,0.47368421052631576,0.7500000000000001,-1.4999999999999996,-0.07894736842105261,-2.0,0.5263157894736842,19,0.47368421052631576,-0.6,-2.0,2.5,-1.6666666666666672,19,0.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.450_maxday3,5201,4731,615,-6.347290797545299,False,375,0.4533333333333333,0.7048887970573079,-35.209852426020745,-0.093892939802722,-36.30893498479452,0.05333333333333334,126,0.4603174603174603,-0.7,-35.80893498479446,7.5,-0.21300856104859328,55,0.16666666666666666,56,0.39285714285714285,0.540863013454134,-9.337866939264863,-0.16674762391544398,-12.13786693926486,0.0,19,0.3684210526315789,-0.7,-11.637866939264864,6.4,-0.6853813661756728,56,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.730_maxday1,5987,4560,799,2.2003526977061854,False,56,0.4642857142857143,0.7316892904511475,-4.653601912162352,-0.08310003414575629,-5.67142858283252,0.8035714285714286,56,0.4642857142857143,-0.5720390699034865,-5.67142858283252,2.5,-0.5372182767645342,6,0.3333333333333333,9,0.4444444444444444,0.6666666666666666,-0.9999999999999998,-0.11111111111111109,-2.0,0.8888888888888888,9,0.4444444444444444,-0.6,-2.0,1.4,-1.4000000000000001,9,0.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-999.000_maxday1,6807,4539,689,2.3224981518702523,False,125,0.512,0.8930773404704391,-3.8311632709700305,-0.030649306167760244,-9.426617807188322,0.208,125,0.512,0.5,-9.426617807188322,2.5,-0.6525433199214746,19,0.5,18,0.6111111111111112,1.286739346268706,1.1266758157121401,0.06259310087289667,-1.9000000000000001,0.2222222222222222,18,0.6111111111111112,0.5,-1.9000000000000001,2.5,2.2189168926287994,18,1.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-999.000_maxday1,7659,4376,775,2.181788963944872,False,120,0.5166666666666667,0.9053524384413988,-3.1943864911101088,-0.026619887425917574,-9.621062306822248,0.21666666666666667,120,0.5166666666666667,0.5,-9.621062306822248,2.5,-0.7826228939289069,18,0.3333333333333333,20,0.35,0.44871794871794884,-4.299999999999999,-0.21499999999999994,-5.199999999999999,0.25,20,0.35,-0.6,-5.199999999999999,2.5,-0.5813953488372094,20,0.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.550_maxday1,8306,4504,724,3.0110739749432076,False,118,0.5338983050847458,0.951859131447101,-1.5706737191815163,-0.013310794230351834,-7.444055911993194,0.2966101694915254,118,0.5338983050847458,0.5,-7.444055911993194,2.5,-1.5916736681013284,18,0.5,20,0.45,0.681818181818182,-2.0999999999999996,-0.10499999999999998,-3.1,0.05,20,0.45,-0.6,-3.1,2.5,-1.1904761904761907,20,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_tp50_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30_clean1000_nopool_d35_win_wf2026_v1",
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
    "delta_bucket": 35,
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
  "data_rows": 39664
}
```