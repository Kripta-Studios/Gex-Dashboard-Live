# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 487,
  "win_rate": 0.5420944558521561,
  "profit_factor": 1.1434326172111966,
  "pnl_return": 17.907947036986442,
  "avg_return": 0.03677196516834998,
  "max_drawdown": -10.809235119953435,
  "call_rate": 0.25667351129363447,
  "days_with_trades": 279,
  "daily_win_rate": 0.5017921146953405,
  "median_daily_return": 0.004761979909714387,
  "daily_max_drawdown": -10.440453973741246,
  "top5_day_return": 19.156523732019725,
  "top5_share_of_pnl": 1.0697219336451307,
  "min_month_trades": 14,
  "positive_month_rate": 0.6666666666666666
}
```

## Per Ticker

```json
{
  "SPXW": {
    "trades": 487,
    "win_rate": 0.5420944558521561,
    "profit_factor": 1.1434326172111966,
    "pnl_return": 17.907947036986442,
    "avg_return": 0.03677196516834998,
    "max_drawdown": -10.809235119953435,
    "call_rate": 0.25667351129363447,
    "days_with_trades": 279,
    "daily_win_rate": 0.5017921146953405,
    "median_daily_return": 0.004761979909714387,
    "daily_max_drawdown": -10.440453973741246,
    "top5_day_return": 19.156523732019725,
    "top5_share_of_pnl": 1.0697219336451307,
    "min_month_trades": 14,
    "positive_month_rate": 0.6666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202504,202504,202501,202501,202502,"202502,202503",202503,thr0.346_maxday1,765,1351,649,6.697908999580666,False,37,0.6486486486486487,2.3283674441948348,8.135494473681437,0.21987822901841722,-1.799999999999999,0.5675675675675675,37,0.6486486486486487,0.3279411386591058,-1.799999999999999,5.440548362016653,0.668742186429723,16,1.0,19,0.42105263157894735,1.0046948466353534,0.028713623260214094,0.0015112433294849523,-2.101648439864575,0.15789473684210525,19,0.42105263157894735,-0.6,-2.101648439864575,5.254696016777656,183.00358575988628,19,1.0
SPXW,202505,202505,"202501,202502",202502,202503,"202503,202504",202504,thr-0.200_maxday1,1392,1373,820,5.152078422971149,False,41,0.5365853658536586,1.6734048155361605,6.400773229554458,0.15611642023303557,-3.1000442185307673,0.43902439024390244,41,0.5365853658536586,0.2581857747409486,-3.1000442185307673,7.514112082846923,1.1739381811172152,20,0.5,21,0.6666666666666666,1.7484897941018231,2.8988599853696218,0.1380409516842677,-1.3454916925721316,0.38095238095238093,21,0.6666666666666666,0.30763238024331474,-1.3454916925721316,4.148017178099598,1.4309132552225357,21,1.0
SPXW,202506,202506,"202501,202502,202503",202503,202504,"202504,202505",202505,thr-0.100_maxday1,2116,1469,777,6.436985898250575,False,41,0.6097560975609756,1.9600814774240605,8.29429848214902,0.2022999629792444,-1.6502283026678404,0.3170731707317073,41,0.6097560975609756,0.27694603802590567,-1.6502283026678404,7.514112082846923,0.9059370239711998,20,1.0,20,0.4,0.6170859481625314,-2.1576829401932063,-0.10788414700966031,-3.310857494991283,0.2,20,0.4,-0.16542358945297242,-3.310857494991283,2.767233479450648,-1.2825023676568814,20,0.0
SPXW,202507,202507,"202501,202502,202503,202504",202504,202505,"202505,202506",202506,thr0.300_maxday3,2765,1597,863,5.702740345670173,False,86,0.5813953488372093,1.46244341812954,8.854838191805399,0.10296323478843487,-4.479322380386625,0.23255813953488372,37,0.5945945945945946,0.19399827146416027,-4.190860879545374,9.650075373503638,1.0898082115644057,39,1.0,33,0.48484848484848486,0.7464589235552667,-2.3977944354463196,-0.07266043743776726,-2.6636363289572973,0.15151515151515152,15,0.5333333333333333,0.16582434311554828,-2.3997362832972517,3.2414870504491864,-1.3518619455157022,33,0.0
SPXW,202508,202508,"202501,202502,202503,202504,202505",202505,202506,"202506,202507",202507,thr0.200_maxday3,3585,1640,778,5.969756877735737,False,110,0.5636363636363636,1.359218927091755,9.068546722800743,0.08244133384364312,-3.1568909430809198,0.3090909090909091,42,0.5952380952380952,0.2544772028244237,-2.5568909430809197,9.209507055973475,1.015543872406625,51,1.0,60,0.6333333333333333,1.142279956439785,1.8377062725786721,0.030628437876311202,-3.9305061673253516,0.45,21,0.6190476190476191,0.2641050431919424,-3.163114907205899,6.88622520764074,3.7471849067468104,60,1.0
SPXW,202509,202509,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508",202508,thr0.287_maxday3,4362,1641,814,6.599683365725543,False,76,0.6447368421052632,1.741698611295354,11.36920931128181,0.14959485935897118,-2.5884149179601863,0.5263157894736842,33,0.6363636363636364,0.5281385427883062,-2.588414917960189,9.221710410637474,0.8111127307232047,35,1.0,33,0.6363636363636364,1.6807865207729904,3.921051659890629,0.11881974726941301,-2.4620253380398167,0.5454545454545454,16,0.625,0.36384796737960245,-2.4620253380398163,6.253334406630131,1.5948105123421294,33,1.0
SPXW,202510,202510,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509",202509,thr0.400_maxday3,5225,1592,852,7.070770930850388,False,109,0.6330275229357798,1.7119161917215224,14.425883657145054,0.1323475564875693,-2.3999999999999986,0.027522935779816515,40,0.675,0.4695954592529573,-2.3033425793978317,10.20362746280841,0.7073138606489879,47,1.0,68,0.5294117647058824,1.2459489582867704,4.531402803120223,0.06663827651647386,-4.487423173276314,0.0,23,0.5217391304347826,0.09789111772656212,-4.487423173276312,13.65666844598896,3.0137838191266693,68,1.0
SPXW,202511,202511,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510",202510,thr-999.000_maxday1,6003,1666,648,5.584919604755138,False,44,0.5681818181818182,1.4889356217948277,4.787095046166195,0.10879761468559535,-1.7117674707279722,0.5,44,0.5681818181818182,0.29039633584971725,-1.7117674707279722,5.810632589994025,1.2138118282501082,21,1.0,19,0.5263157894736842,1.0043854110792554,0.023681219827978994,0.001246379990946263,-2.4000000000000004,0.5263157894736842,19,0.5263157894736842,0.3152173913043479,-2.4000000000000004,3.4458075858712265,145.50802749611987,19,1.0
SPXW,202512,202512,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511",202511,thr-0.100_maxday2,6817,1500,842,6.330947937693925,False,83,0.5903614457831325,1.6143661128562619,12.115751986379719,0.14597291549855082,-3.7877990601790383,0.08433734939759036,42,0.5714285714285714,0.45224425545884933,-3.1877990601790387,13.616679330226605,1.1238823100319484,37,1.0,44,0.5227272727272727,1.071284441188926,0.8090382504983095,0.018387232965870668,-3.1799741839780933,0.13636363636363635,22,0.36363636363636365,-0.16621984990819544,-3.179974183978093,6.924217405004887,8.558578535365994,44,1.0
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512",202512,thr-999.000_maxday2,7669,1490,779,6.284123621404474,False,81,0.6296296296296297,1.86277752356507,14.407281555408364,0.17786767352356006,-6.475025711696109,0.24691358024691357,41,0.5853658536585366,0.6286872812584112,-5.917131055163423,11.379263803924779,0.7898272661752144,37,1.0,40,0.65,1.9313852231767712,7.069126224360101,0.1767281556090025,-2.9595927557820887,0.25,20,0.6,0.17806240434503773,-2.715317895495371,8.055729402505683,1.139565081572,40,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601",202601,thr0.100_maxday2,8317,1621,616,6.77733112881727,False,84,0.6309523809523809,1.7500460076726145,12.20353212217992,0.14528014431166572,-2.3853403681263665,0.4523809523809524,42,0.5476190476190477,0.36533105589200576,-1.8685536815593966,8.925867906408255,0.7314167584469655,40,1.0,38,0.5526315789473685,1.1841101852929559,1.8779238899881496,0.04941904973653025,-3.3469696507309425,0.21052631578947367,19,0.47368421052631576,-0.30185188010886865,-3.346969650730942,8.588507361371606,4.5734054543743,38,1.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512",202512,202601,"202601,202602",202602,thr0.374_maxday3,9159,1395,793,6.535022355277039,False,66,0.6515151515151515,1.8632202973302427,11.792266288354526,0.17867070133870494,-3.460784303642429,0.16666666666666666,31,0.5806451612903226,0.5828911382073032,-2.8078538195852776,9.699318398869586,0.8225152113846145,26,1.0,40,0.575,1.4280337213323053,4.242142364926011,0.10605355912315026,-5.254763340398806,0.525,19,0.5263157894736842,0.013750596880107602,-4.8859821941866315,9.96426547633122,2.3488757847251107,40,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601",202601,202602,"202602,202603",202603,thr0.400_maxday3,9938,1409,793,7.581872213748948,False,37,0.7027027027027027,2.9339048472285625,11.458453366049179,0.30968792881213997,-1.5489224595340296,0.5405405405405406,20,0.75,0.6986513302236883,-1.5489224595340296,9.24572125274417,0.8068908566786838,12,1.0,14,0.35714285714285715,0.6682456614994209,-1.6659500003707688,-0.11899642859791205,-2.625840416085551,0.14285714285714285,7,0.42857142857142855,-0.34473681568769154,-2.625840416085551,0.734049999629231,-0.4406194660499193,14,0.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602",202602,202603,"202603,202604",202604,thr0.000_maxday1,10554,1586,783,6.566618556821599,False,43,0.6046511627906976,2.0466260941662537,8.816288824703436,0.20502997266752176,-1.799999999999999,0.5116279069767442,43,0.6046511627906976,0.29644143050132477,-1.799999999999999,7.350719595546829,0.8337657422191014,21,1.0,20,0.35,0.6390492251720188,-2.5988455787614657,-0.12994227893807328,-3.8885217791838147,0.15,20,0.35,-0.6,-3.8885217791838147,3.82065342231855,-1.470134837383975,20,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603",202603,202604,"202604,202605",202605,thr0.289_maxday1,11347,1576,736,4.0845164867357395,False,38,0.5789473684210527,1.3170825967686388,3.0439929289789305,0.08010507707839291,-4.447061129108297,0.10526315789473684,38,0.5789473684210527,0.28772550281791875,-4.447061129108297,5.562615773296262,1.827407587034761,19,0.5,18,0.4444444444444444,0.9147622829897161,-0.511426302061704,-0.028412572336761335,-2.4,0.0,18,0.4444444444444444,-0.6,-2.4,4.082214657500938,-7.982019385871192,18,0.0

```

## Config

```json
{
  "args": {
    "data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_v1_SPXW",
    "tickers": [
      "SPXW"
    ],
    "train_tickers": [],
    "expiry_modes": [],
    "start_month": "202504",
    "end_month": "202606",
    "val_months": 2,
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