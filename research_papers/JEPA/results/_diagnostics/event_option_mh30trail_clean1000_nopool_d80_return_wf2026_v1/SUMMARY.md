# Event Option Gate Walk-Forward

Causal diagnostic over event-level option-chain features. Models predict CALL/PUT option returns; thresholds are selected only on prior validation months.

## Overall

```json
{
  "trades": 524,
  "win_rate": 0.4847328244274809,
  "profit_factor": 1.045688066756527,
  "pnl_return": 5.862967784986543,
  "avg_return": 0.011188869818676608,
  "max_drawdown": -10.301449663692354,
  "call_rate": 0.3015267175572519,
  "days_with_trades": 121,
  "daily_win_rate": 0.48760330578512395,
  "median_daily_return": -0.010122417839205644,
  "daily_max_drawdown": -16.545291137702005,
  "top5_day_return": 29.802773925257124,
  "top5_share_of_pnl": 5.083223210192947,
  "min_month_trades": 48,
  "positive_month_rate": 0.6666666666666666
}
```

## Per Ticker

```json
{
  "QQQ": {
    "trades": 158,
    "win_rate": 0.4936708860759494,
    "profit_factor": 1.0527839454796526,
    "pnl_return": 2.025618260823091,
    "avg_return": 0.012820368739386651,
    "max_drawdown": -8.316230958120617,
    "call_rate": 0.3227848101265823,
    "days_with_trades": 103,
    "daily_win_rate": 0.4854368932038835,
    "median_daily_return": -0.08741259061886208,
    "daily_max_drawdown": -7.976478578936034,
    "top5_day_return": 10.808909688672344,
    "top5_share_of_pnl": 5.3361039924078515,
    "min_month_trades": 7,
    "positive_month_rate": 0.8333333333333334
  },
  "SPXW": {
    "trades": 194,
    "win_rate": 0.4690721649484536,
    "profit_factor": 0.9896918620621411,
    "pnl_return": -0.5115662078844645,
    "avg_return": -0.0026369392158993015,
    "max_drawdown": -7.639029632337996,
    "call_rate": 0.24742268041237114,
    "days_with_trades": 117,
    "daily_win_rate": 0.4358974358974359,
    "median_daily_return": -0.11201629676014879,
    "daily_max_drawdown": -7.639029632338001,
    "top5_day_return": 11.617778318703268,
    "top5_share_of_pnl": -22.710214513088214,
    "min_month_trades": 21,
    "positive_month_rate": 0.5
  },
  "SPY": {
    "trades": 172,
    "win_rate": 0.4941860465116279,
    "profit_factor": 1.1078521019289227,
    "pnl_return": 4.3489157320479155,
    "avg_return": 0.025284393790976252,
    "max_drawdown": -10.301449663692356,
    "call_rate": 0.3430232558139535,
    "days_with_trades": 101,
    "daily_win_rate": 0.46534653465346537,
    "median_daily_return": -0.09246574447669087,
    "daily_max_drawdown": -9.900870421592826,
    "top5_day_return": 12.927699463898342,
    "top5_share_of_pnl": 2.972625882040408,
    "min_month_trades": 17,
    "positive_month_rate": 0.6666666666666666
  }
}
```

## Fold Configs

```csv
ticker,month,test_month,train_months,train_month_max,first_val_month,val_months,val_month_max,deploy_config,train_rows,val_rows,test_rows,val_score,abstained_invalid_val,val_trades,val_win_rate,val_profit_factor,val_pnl_return,val_avg_return,val_max_drawdown,val_call_rate,val_days_with_trades,val_daily_win_rate,val_median_daily_return,val_daily_max_drawdown,val_top5_day_return,val_top5_share_of_pnl,val_min_month_trades,val_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.050_maxday2,4362,4797,779,5.78936961456234,False,255,0.5607843137254902,1.2588375137310903,13.53527039970503,0.05307949176354914,-6.686857641181529,0.38823529411764707,128,0.515625,0.04094376542887457,-6.587614053626023,9.166544451443961,0.6772339362827746,37,0.8333333333333334,40,0.575,1.2889850092058428,2.304451300033454,0.057611282500836344,-1.9681936163115443,0.575,20,0.55,0.19150225659659226,-1.9681936163115437,5.2841770628432165,2.2930304766112894,40,1.0
SPXW,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.000_maxday2,5225,4713,616,5.3503138341249645,False,251,0.549800796812749,1.2427191678172922,13.737473888428546,0.054730971667046,-8.007052211918134,0.02390438247011952,126,0.48412698412698413,-0.07695595510886716,-7.562224638865366,13.48122492031692,0.9813467184583716,37,0.6666666666666666,38,0.39473684210526316,0.9742756127769171,-0.30707676369042314,-0.00808096746553745,-4.261363607628614,0.0,19,0.3684210526315789,-0.5305913408140622,-4.261363607628614,10.066938751976032,-32.78313419417476,38,0.0
SPXW,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.050_maxday1,6003,4551,793,4.810835268155994,False,124,0.5403225806451613,1.1380523813817423,3.5148502557188466,0.028345566578377796,-3.298717716562166,0.75,124,0.5403225806451613,0.13497812509573381,-3.298717716562166,4.680617371082063,1.331669069960079,19,0.6666666666666666,22,0.5,1.6751052364858858,2.773457708033859,0.12606625945608452,-1.5406424457023076,0.5909090909090909,22,0.5,0.011097626903821434,-1.5406424457023076,4.881526310887521,1.7600868031076269,22,1.0
SPXW,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.400_maxday3,6817,4530,793,7.429576147327895,False,195,0.5897435897435898,1.6253273619395643,26.097787589297248,0.1338348081502423,-6.4215216716195425,0.10256410256410256,88,0.5227272727272727,0.12950224188822995,-6.421521671619541,16.00566471867016,0.61329584601394,28,0.8333333333333334,33,0.45454545454545453,1.0126604411095952,0.08861992363852245,0.0026854522314703772,-2.464907707472203,0.0,15,0.4666666666666667,-0.12207871214423927,-2.4649077074722023,5.044803419103531,56.92628939380615,33,1.0
SPXW,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.050_maxday2,7669,4471,783,8.676978551072711,False,245,0.6081632653061224,1.6616221716311474,30.591291707712173,0.12486241513351908,-3.981785692487442,0.31020408163265306,123,0.5691056910569106,0.19615387549767116,-3.981785692487443,14.577128207398408,0.4765123469344533,37,1.0,40,0.5,0.765570729986134,-2.5256374195461015,-0.06314093548865254,-5.1468971846754314,0.225,20,0.4,-0.16581443634005122,-5.1468971846754314,5.24306541747943,-2.0759374947896103,40,0.0
SPXW,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.066_maxday1,8317,4606,736,6.705790231666691,False,124,0.5967741935483871,1.6080490482361416,13.74795658881544,0.11087061765173742,-2.7544364725696813,0.4112903225806452,124,0.5967741935483871,0.23156280434098486,-2.7544364725696813,7.595477016682171,0.5524804335548616,19,0.8333333333333334,21,0.3333333333333333,0.636811161522674,-2.8453809563537775,-0.13549433125494179,-5.52806076051319,0.14285714285714285,21,0.3333333333333333,-0.6,-5.52806076051319,4.178036632053076,-1.468357557789743,21,0.0
QQQ,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr0.000_maxday1,3966,4515,692,5.881562166671548,False,126,0.5952380952380952,1.552475955728468,11.930961529931439,0.09469017087247174,-5.679715309627657,0.47619047619047616,126,0.5952380952380952,0.25771622100030867,-5.679715309627657,5.292829524053101,0.4436213720725588,19,0.8333333333333334,19,0.5263157894736842,1.400981386500141,1.5204121788627178,0.08002169362435357,-2.9004342417899416,0.42105263157894735,19,0.5263157894736842,0.07541899069288438,-2.9004342417899416,4.408019487160605,2.8992266363308423,19,1.0
QQQ,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.429_maxday2,4763,4410,550,5.406941625819621,False,229,0.4890829694323144,1.2032903133856314,10.94950614951387,0.0478144373341217,-6.691667658399114,0.0,117,0.49572649572649574,-0.01681548448939929,-6.69166765839912,16.984947297753617,1.5512066997202159,28,0.8333333333333334,36,0.5833333333333334,1.5159050071067344,3.9257047520332717,0.10904735422314643,-2.8464285498877766,0.0,19,0.47368421052631576,-0.17800006866455076,-2.846428549887776,8.375700644836728,2.1335533805741846,36,1.0
QQQ,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.300_maxday1,5518,4205,764,6.077769585362249,False,37,0.6216216216216216,2.0151653106903717,7.205188100428148,0.1947348135250851,-2.119801520840558,0.05405405405405406,37,0.6216216216216216,0.302287610726343,-2.119801520840558,5.602339154659399,0.777542387037265,4,0.8333333333333334,7,0.5714285714285714,1.7598367546443725,1.0043515754056913,0.14347879648652734,-0.6,0.14285714285714285,7,0.5714285714285714,0.4205336206157395,-0.6,2.1093020657807804,2.1001630479135383,7,1.0
QQQ,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr-0.100_maxday2,6313,4174,636,7.301581828847987,False,249,0.5381526104417671,1.44429628651377,23.617871947884073,0.09485089135696415,-5.297339523399076,0.20883534136546184,125,0.536,0.06615336629724089,-5.297339523399065,16.17387873972047,0.6848152439563672,37,0.8333333333333334,36,0.3333333333333333,0.49347177020883354,-6.181672215058732,-0.17171311708496478,-6.896311536992263,0.19444444444444445,18,0.3888888888888889,-0.6658238655617233,-6.5565591578076825,4.177964714498432,-0.6758631918917973,36,0.0
QQQ,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr-0.100_maxday2,7115,4008,706,7.494625569744432,False,239,0.5564853556485355,1.5144973736154612,24.649458907009354,0.10313581132639897,-5.180799830972612,0.4602510460251046,120,0.55,0.07769409767217184,-5.1807998309726155,12.001465593319487,0.4868855595814614,36,0.8333333333333334,40,0.525,1.1351336009639204,1.0903970620526462,0.027259926551316156,-3.3881149947594933,0.7,20,0.5,-0.022767865655389574,-3.3881149947594933,6.73236882942944,6.174236031740509,40,1.0
QQQ,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr-0.100_maxday1,7739,4090,617,7.84787323897516,False,121,0.6115702479338843,1.9641328679662546,18.34404693671039,0.15160369369182142,-2.0404726293022684,0.6115702479338843,121,0.6115702479338843,0.21478067472569196,-2.0404726293022684,6.417382177213512,0.3498345920807119,18,1.0,20,0.5,1.1238769001929536,0.6664249075274992,0.03332124537637496,-2.712171647417959,0.35,20,0.5,0.022420206669580445,-2.712171647417959,4.5267187374790865,6.7925413446409895,20,1.0
SPY,202601,202601,"202501,202502,202503,202504,202505,202506",202506,202507,"202507,202508,202509,202510,202511,202512",202512,thr-0.100_maxday2,4331,4822,778,7.543527239244416,False,255,0.5882352941176471,1.4773011949017951,21.90708820236999,0.08591014981321565,-4.320103251514624,0.5882352941176471,128,0.59375,0.18145452626325315,-4.320103251514606,11.03357814609133,0.5036533401503207,37,1.0,40,0.625,2.1746938884098532,6.110730108635183,0.15276825271587957,-2.1215027312575554,0.675,20,0.6,0.30136470384092434,-1.2188722528457974,6.081272544015771,0.9951793706978181,40,1.0
SPY,202602,202602,"202501,202502,202503,202504,202505,202506,202507",202507,202508,"202508,202509,202510,202511,202512,202601",202601,thr0.200_maxday2,5201,4730,615,6.182567340386131,False,250,0.548,1.2881776370928182,15.480117131404619,0.06192046852561847,-6.675826613218426,0.036,126,0.5,-0.002727373675778133,-6.410453187583936,15.091137597169622,0.9748723132432977,37,1.0,38,0.4473684210526316,0.9591588561724,-0.4441411786916919,-0.011687925755044523,-4.374447138181468,0.0,19,0.42105263157894735,-0.4892537795590265,-4.374447138181468,8.839159500696432,-19.90168875296358,38,0.0
SPY,202603,202603,"202501,202502,202503,202504,202505,202506,202507,202508",202508,202509,"202509,202510,202511,202512,202601,202602",202602,thr0.228_maxday2,5987,4559,799,5.222082055760113,False,145,0.5724137931034483,1.261937804880995,7.633721570892142,0.05264635566132512,-5.329560297418521,0.6,84,0.5238095238095238,0.12884450997932928,-5.329560297418521,7.5070440442632815,0.9834055348426789,19,0.8333333333333334,19,0.47368421052631576,1.0887893250858323,0.41892613178332117,0.022048743778069535,-3.671229927938641,0.7368421052631579,11,0.2727272727272727,-0.19942075790046931,-3.27065068583911,3.5329970590867457,8.433460677296917,19,1.0
SPY,202604,202604,"202501,202502,202503,202504,202505,202506,202507,202508,202509",202509,202510,"202510,202511,202512,202601,202602,202603",202603,thr0.245_maxday2,6807,4538,689,7.3480500510010955,False,131,0.6183206106870229,1.6899761475597088,17.298614956360495,0.1320504958500801,-2.7383464464379976,0.2748091603053435,80,0.575,0.36821414765418936,-2.7383464464379967,10.174927730312968,0.5881932025183189,17,1.0,17,0.29411764705882354,0.30531619305112395,-4.293477481722616,-0.25255749892485974,-4.442879997004365,0.0,11,0.36363636363636365,-0.5098039124022075,-4.442879997004364,0.9553335136840891,-0.22250809926241727,17,0.0
SPY,202605,202605,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510",202510,202511,"202511,202512,202601,202602,202603,202604",202604,thr0.100_maxday2,7659,4375,775,7.3114590280414875,False,233,0.575107296137339,1.4887146377558624,22.209558634667285,0.09531999414020294,-4.66511886521619,0.30472103004291845,119,0.5714285714285714,0.20299528436633418,-4.665118865216165,15.21801250942369,0.6852010325711575,35,0.8333333333333334,37,0.4594594594594595,1.1825926796489463,1.4992746054358967,0.040520935282051265,-2.8894982213076212,0.35135135135135137,19,0.42105263157894735,-0.09246574447669087,-2.8894982213076212,8.16596499554981,5.446610624859914,37,1.0
SPY,202606,202606,"202501,202502,202503,202504,202505,202506,202507,202508,202509,202510,202511",202511,202512,"202512,202601,202602,202603,202604,202605",202605,thr0.000_maxday1,8306,4503,724,6.724693341655316,False,121,0.5537190082644629,1.5733743746188873,12.806330752203435,0.10583744423308623,-2.7670163773873497,0.4628099173553719,121,0.5537190082644629,0.11346157196710926,-2.7670163773873497,8.978425272404586,0.7010927209466126,18,1.0,21,0.5714285714285714,1.2059028668034342,1.0576035466078257,0.0503620736479917,-2.606459933829406,0.23809523809523808,21,0.5714285714285714,0.2634615719671092,-2.606459933829406,3.5638793131890436,3.3697686856477422,21,1.0

```

## Config

```json
{
  "args": {
    "data": "research_papers\\JEPA\\results\\_diagnostics\\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics\\event_option_dataset.parquet",
    "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d80_return_wf2026_v1",
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