# Event Trade Union Config Selector

This result selects source variants, max trades per day, and cooldown walk-forward by test month using only prior out-of-sample months.

## Overall

```json
{
  "trades": 484,
  "win_rate": 0.5206611570247934,
  "profit_factor": 1.4291651334982742,
  "pnl_return": 58.02940112749136,
  "avg_return": 0.11989545687498215,
  "max_drawdown": -7.598487814484095,
  "call_rate": 0.30785123966942146,
  "days_with_trades": 121,
  "daily_win_rate": 0.5289256198347108,
  "median_daily_return": 0.28634483814219935,
  "daily_max_drawdown": -6.032525594257688,
  "top5_day_return": 32.19082747060889,
  "top5_share_of_pnl": 0.5547330636737955,
  "min_month_trades": 53,
  "positive_month_rate": 1.0
}
```

## By Ticker

```json
{
  "SPXW": {
    "trades": 484,
    "win_rate": 0.5206611570247934,
    "profit_factor": 1.4291651334982742,
    "pnl_return": 58.02940112749136,
    "avg_return": 0.11989545687498215,
    "max_drawdown": -7.598487814484095,
    "call_rate": 0.30785123966942146,
    "days_with_trades": 121,
    "daily_win_rate": 0.5289256198347108,
    "median_daily_return": 0.28634483814219935,
    "daily_max_drawdown": -6.032525594257688,
    "top5_day_return": 32.19082747060889,
    "top5_share_of_pnl": 0.5547330636737955,
    "min_month_trades": 53,
    "positive_month_rate": 1.0
  }
}
```

- Risk capital: $5,000
- Net PnL: $290,147

## Folds

```csv
ticker,month,mode,variants,selected_source,source_stream,source_path,max_day,cooldown,daily_order,select_months,select_score,select_trades,select_win_rate,select_profit_factor,select_pnl_return,select_avg_return,select_max_drawdown,select_call_rate,select_days_with_trades,select_daily_win_rate,select_median_daily_return,select_daily_max_drawdown,select_top5_day_return,select_top5_share_of_pnl,select_min_month_trades,select_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPXW,202601,SELECTED,"d25,d35,d50,d65","d25,d35,d50,d65",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,999,0,time_asc,"202507,202508,202509,202510,202511,202512",28.563647514111814,748,0.536096256684492,1.2588079464743713,52.55307047689374,0.0702581156108205,-11.409537530302394,0.3074866310160428,128,0.546875,0.2506880734923996,-10.46683680047694,36.98084466317037,0.7036857090858263,69,0.8333333333333334,91,0.4725274725274725,1.3844779608243118,10.89827043025111,0.11976121351924296,-6.635624124919007,0.16483516483516483,20,0.5,0.13164082561901883,-5.447878634076396,18.063749565769943,1.657487734533463,91,1.0
SPXW,202602,SELECTED,"d25,d50,d65,d80","d25,d50,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,999,0,time_asc,"202508,202509,202510,202511,202512,202601",29.99790348363838,694,0.5403458213256485,1.353757272653795,63.848470002060196,0.09200067723639797,-11.702635220839909,0.2968299711815562,126,0.5634920634920635,0.3941071944083224,-11.102635220839872,44.437564057300364,0.6959847911134989,53,1.0,84,0.5357142857142857,1.3524448142398866,7.87113955879396,0.09370404236659476,-6.032525594257683,0.27380952380952384,19,0.42105263157894735,-0.11783125815042328,-6.032525594257687,19.747838634343516,2.5088919446588163,84,1.0
SPXW,202603,SELECTED,"d25,d35,d50,d80","d25,d35,d50,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,999,15,time_asc,"202509,202510,202511,202512,202601,202602",28.72205796257518,512,0.51953125,1.335928395076286,48.41581356962229,0.09456213587816853,-8.70137232214364,0.216796875,124,0.5241935483870968,0.12743317420154432,-8.358671592318206,33.02220613605702,0.6820541410209053,59,1.0,112,0.48214285714285715,1.2507230396163296,8.436965289544819,0.07533004722807875,-7.598487814484063,0.6339285714285714,22,0.4090909090909091,-0.26111718752509117,-5.872998404672522,17.770994991388434,2.106325483335868,112,1.0
SPXW,202604,SELECTED,"d25,d50,d65,d80","d25,d50,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,999,0,time_asc,"202510,202511,202512,202601,202602,202603",29.03199716756324,612,0.5196078431372549,1.3458121545095239,58.575356023315656,0.09571136605116937,-11.702635220839904,0.2647058823529412,125,0.528,0.3152173913043479,-11.102635220839876,42.5317072291741,0.726102410922514,53,1.0,86,0.5813953488372093,1.8077570545056065,16.619712040289134,0.19325246558475737,-3.8431479535927373,0.3953488372093023,21,0.7619047619047619,0.5597770002116801,-3.243147953592741,16.4203870423436,0.9880067117010009,86,1.0
SPXW,202605,SELECTED,"d25,d35,d50","d25,d35,d50",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,0,time_asc,"202511,202512,202601,202602,202603,202604",30.575192627650008,351,0.5441595441595442,1.617687083171746,59.12724234346378,0.1684536818902102,-9.993957835037259,0.3076923076923077,122,0.5409836065573771,0.13545758440841377,-9.475674788049758,36.11753672027779,0.6108442621165201,54,1.0,58,0.6206896551724138,1.7327826857517987,9.672731451923742,0.16677123192971968,-3.599999999999998,0.06896551724137931,20,0.65,0.6503708074772964,-3.0,11.883069045382761,1.2285122464574803,58,1.0
SPXW,202606,SELECTED,"d25,d35,d50","d25,d35,d50",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,0,time_asc,"202512,202601,202602,202603,202604,202605",31.230269172964995,355,0.5521126760563381,1.6462759626685708,61.229715032350065,0.17247807051366215,-9.993957835037211,0.23098591549295774,123,0.5528455284552846,0.15683596018541612,-9.475674788049762,36.11753672027779,0.5898694237135593,56,1.0,53,0.4528301886792453,1.2647861516728542,4.530582356688594,0.08548268597525649,-4.690640447952553,0.03773584905660377,19,0.42105263157894735,-0.6,-3.864066299415089,16.02096586126597,3.5361824595493516,53,1.0

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
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_val2_configsel_m6_wf202601_202606_SPXW_v2",
  "ticker": "SPXW",
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