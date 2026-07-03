# Event Trade Union Config Selector

This result selects source variants, max trades per day, and cooldown walk-forward by test month using only prior out-of-sample months.

## Overall

```json
{
  "trades": 344,
  "win_rate": 0.49709302325581395,
  "profit_factor": 1.2816416850841272,
  "pnl_return": 28.287083987777727,
  "avg_return": 0.08222989531330735,
  "max_drawdown": -15.339197956007276,
  "call_rate": 0.37790697674418605,
  "days_with_trades": 119,
  "daily_win_rate": 0.5462184873949579,
  "median_daily_return": 0.18618963131931698,
  "daily_max_drawdown": -15.339197956007254,
  "top5_day_return": 24.43688280996149,
  "top5_share_of_pnl": 0.8638883675857211,
  "min_month_trades": 46,
  "positive_month_rate": 0.6666666666666666
}
```

## By Ticker

```json
{
  "QQQ": {
    "trades": 344,
    "win_rate": 0.49709302325581395,
    "profit_factor": 1.2816416850841272,
    "pnl_return": 28.287083987777727,
    "avg_return": 0.08222989531330735,
    "max_drawdown": -15.339197956007276,
    "call_rate": 0.37790697674418605,
    "days_with_trades": 119,
    "daily_win_rate": 0.5462184873949579,
    "median_daily_return": 0.18618963131931698,
    "daily_max_drawdown": -15.339197956007254,
    "top5_day_return": 24.43688280996149,
    "top5_share_of_pnl": 0.8638883675857211,
    "min_month_trades": 46,
    "positive_month_rate": 0.6666666666666666
  }
}
```

- Risk capital: $5,000
- Net PnL: $141,435

## Folds

```csv
ticker,month,mode,variants,selected_source,source_stream,source_path,max_day,cooldown,daily_order,select_months,select_score,select_trades,select_win_rate,select_profit_factor,select_pnl_return,select_avg_return,select_max_drawdown,select_call_rate,select_days_with_trades,select_daily_win_rate,select_median_daily_return,select_daily_max_drawdown,select_top5_day_return,select_top5_share_of_pnl,select_min_month_trades,select_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
QQQ,202601,SELECTED,"d25,d35,d65","d25,d35,d65",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,60,time_asc,"202507,202508,202509,202510,202511,202512",25.597263734866697,256,0.546875,1.5275247718070886,34.47983097315216,0.13468683973887563,-9.99415733458941,0.41015625,128,0.515625,0.013237998017581298,-9.415873557395738,21.71207227470516,0.6297035589185846,31,1.0,49,0.46938775510204084,1.553123789482679,8.628731115929792,0.1760965533863223,-7.1949799662892575,0.30612244897959184,20,0.55,0.34269865896596785,-6.610794070162775,15.468713024428649,1.7926984647686304,49,1.0
QQQ,202602,SELECTED,"d25,d35,d65","d25,d35,d65",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,15,time_asc,"202508,202509,202510,202511,202512,202601",27.040671173637016,343,0.5393586005830904,1.5214027274050188,46.97120617540509,0.1369422920565746,-14.15659275560714,0.36151603498542273,126,0.5634920634920635,0.5037451183413637,-14.156592755607143,25.493536666180468,0.5427481800441674,37,1.0,55,0.41818181818181815,0.6813115047290765,-5.852931480467999,-0.10641693600850907,-9.38223484171347,0.4909090909090909,19,0.5263157894736842,0.01695983052332395,-9.382234841713469,5.074235558393597,-0.8669562552247515,55,0.0
QQQ,202603,SELECTED,"d25,d35,d65","d25,d35,d65",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,15,time_asc,"202509,202510,202511,202512,202601,202602",25.23360062360923,342,0.52046783625731,1.4237993741634105,39.886241847251384,0.11662643814985785,-9.382234841713498,0.3333333333333333,124,0.5645161290322581,0.45822638093711604,-9.382234841713455,25.493536666180468,0.6391561472201539,37,0.8333333333333334,46,0.5869565217391305,2.130541811802596,12.021856766590744,0.2613447123171901,-3.421313676800576,0.5434782608695652,22,0.5,-0.031855482465816265,-2.430773232522803,13.095242817034329,1.0892862118792308,46,1.0
QQQ,202604,SELECTED,"d25,d50,d65,d80","d25,d50,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,999,0,time_asc,"202510,202511,202512,202601,202602,202603",29.24956875640071,495,0.5131313131313131,1.3839438622681226,52.72463595288014,0.10651441606642453,-7.508419731586091,0.3212121212121212,125,0.536,0.12441857402681922,-6.747053766358768,31.486536325840405,0.5971883116268424,59,1.0,93,0.43010752688172044,0.8396216421716827,-4.932801630338206,-0.05304087774557211,-15.339197956007254,0.3763440860215054,18,0.5,-0.2852970885599192,-15.339197956007254,10.961899838674011,-2.2222462324969743,93,0.0
QQQ,202605,SELECTED,"d25,d35,d50,d65","d25,d35,d50,d65",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,30,time_asc,"202511,202512,202601,202602,202603,202604",27.181815170266695,303,0.5313531353135313,1.6063940591497117,50.84776527261585,0.16781440684031634,-9.94364871139917,0.42244224422442245,120,0.575,0.25601295314920114,-9.65079148095964,25.484801173709904,0.5011980573202257,38,0.8333333333333334,46,0.5434782608695652,1.1606081993542088,2.023663311863028,0.04399268069267452,-2.619374016764606,0.30434782608695654,20,0.6,0.2670514679136497,-1.9559702056849484,6.904251301024051,3.4117588931667933,46,1.0
QQQ,202606,SELECTED,"d25,d35,d50,d65,d80","d25,d35,d50,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,0,time_asc,"202512,202601,202602,202603,202604,202605",28.354629600431394,351,0.5413105413105413,1.4416394682591473,41.51423360072523,0.11827416980263597,-7.275041096341731,0.39886039886039887,121,0.5619834710743802,0.2715898695514024,-6.958459812588018,22.238744198158656,0.5356896242393876,54,1.0,55,0.6,2.3140136284003936,16.398565904200368,0.29815574371273396,-2.5058139825009142,0.2545454545454545,20,0.6,0.2445538473613955,-2.5058139825009107,18.82465662227982,1.1479452979152298,55,1.0

```

## Candidate Configs

```json
[
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 1,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 2,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 3,
    "cooldown": 60,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 0,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 15,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 30,
    "daily_order": "score_desc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "time_asc"
  },
  {
    "variants": [
      "d25",
      "d35",
      "d50",
      "d65",
      "d80"
    ],
    "max_day": 999,
    "cooldown": 60,
    "daily_order": "score_desc"
  }
]
```

## Config

```json
{
  "trade_source": [
    "d25=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\\event_option_gate_trades.csv",
    "d35=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\\event_option_gate_trades.csv",
    "d50=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\\event_option_gate_trades.csv",
    "d65=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\\event_option_gate_trades.csv",
    "d80=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\\event_option_gate_trades.csv"
  ],
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_val2_configsel_m6_wf202601_202606_QQQ_v2",
  "ticker": "QQQ",
  "history_start_month": "202504",
  "start_month": "202601",
  "end_month": "202606",
  "max_source_group_size": 5,
  "max_day_grid": [
    1,
    2,
    3,
    999
  ],
  "cooldown_grid": [
    0,
    15,
    30,
    60
  ],
  "daily_order_grid": [
    "time_asc",
    "score_desc"
  ],
  "workers": 2,
  "chunksize": 32,
  "select_months": 6,
  "min_select_trades": 108,
  "min_select_month_trades": 18,
  "score_pf_weight": 3.0,
  "score_pf_cap": 4.0,
  "score_win_weight": 20.0,
  "score_return_weight": 0.1,
  "score_positive_month_weight": 4.0,
  "score_volume_weight": 0.1,
  "score_daily_dd_penalty": 0.05,
  "score_top5_penalty": 0.25,
  "risk_capital": 5000.0,
  "deploy_month": "",
  "deploy_select_end_month": "",
  "export_deploy_config": false,
  "skip_walkforward": false,
  "allow_invalid_deploy_selection": false
}
```