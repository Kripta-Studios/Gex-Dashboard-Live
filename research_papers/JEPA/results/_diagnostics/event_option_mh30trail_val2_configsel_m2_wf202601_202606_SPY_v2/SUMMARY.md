# Event Trade Union Config Selector

This result selects source variants, max trades per day, and cooldown walk-forward by test month using only prior out-of-sample months.

## Overall

```json
{
  "trades": 251,
  "win_rate": 0.5179282868525896,
  "profit_factor": 1.2397643968164567,
  "pnl_return": 16.955510534796847,
  "avg_return": 0.06755183479998744,
  "max_drawdown": -3.931787227729062,
  "call_rate": 0.3147410358565737,
  "days_with_trades": 120,
  "daily_win_rate": 0.5416666666666666,
  "median_daily_return": 0.23973515125141856,
  "daily_max_drawdown": -3.575000027939687,
  "top5_day_return": 16.909709480992806,
  "top5_share_of_pnl": 0.9972987511222356,
  "min_month_trades": 20,
  "positive_month_rate": 0.5
}
```

## By Ticker

```json
{
  "SPY": {
    "trades": 251,
    "win_rate": 0.5179282868525896,
    "profit_factor": 1.2397643968164567,
    "pnl_return": 16.955510534796847,
    "avg_return": 0.06755183479998744,
    "max_drawdown": -3.931787227729062,
    "call_rate": 0.3147410358565737,
    "days_with_trades": 120,
    "daily_win_rate": 0.5416666666666666,
    "median_daily_return": 0.23973515125141856,
    "daily_max_drawdown": -3.575000027939687,
    "top5_day_return": 16.909709480992806,
    "top5_share_of_pnl": 0.9972987511222356,
    "min_month_trades": 20,
    "positive_month_rate": 0.5
  }
}
```

- Risk capital: $5,000
- Net PnL: $84,778

## Folds

```csv
ticker,month,mode,variants,selected_source,source_stream,source_path,max_day,cooldown,daily_order,select_months,select_score,select_trades,select_win_rate,select_profit_factor,select_pnl_return,select_avg_return,select_max_drawdown,select_call_rate,select_days_with_trades,select_daily_win_rate,select_median_daily_return,select_daily_max_drawdown,select_top5_day_return,select_top5_share_of_pnl,select_min_month_trades,select_positive_month_rate,test_trades,test_win_rate,test_profit_factor,test_pnl_return,test_avg_return,test_max_drawdown,test_call_rate,test_days_with_trades,test_daily_win_rate,test_median_daily_return,test_daily_max_drawdown,test_top5_day_return,test_top5_share_of_pnl,test_min_month_trades,test_positive_month_rate
SPY,202601,SELECTED,"d25,d35","d25,d35",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,999,30,time_asc,"202511,202512",30.120213004183668,150,0.58,1.8488487661333197,32.08648335983951,0.21390988906559674,-5.800935423683793,0.32666666666666666,41,0.6341463414634146,0.4762662801701856,-4.699632604004799,21.49891119225874,0.6700301479334901,61,1.0,79,0.5063291139240507,1.4666743538758604,10.437053963697878,0.13211460713541617,-3.6762120140172474,0.27848101265822783,20,0.55,0.40740761406010106,-2.648941900220125,13.322542423877888,1.2764657987029966,79,1.0
SPY,202602,SELECTED,"d25,d35,d50","d25,d35,d50",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,2,60,score_desc,"202512,202601",28.667487199675378,82,0.6097560975609756,2.1720077830787585,22.50254943511217,0.27442133457453866,-2.5499999255702197,0.24390243902439024,42,0.5476190476190477,0.14868180654501809,-1.8782608858325527,19.436183070914268,0.8637324907099969,38,1.0,21,0.42857142857142855,0.8736187040750769,-0.9099453306594487,-0.04333073003140232,-3.3317872277290683,0.19047619047619047,19,0.42105263157894735,-0.6,-3.1280894972670303,4.936116743680592,-5.424630005083192,21,0.0
SPY,202603,SELECTED,"d25,d35,d50,d80","d25,d35,d50,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d25_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,15,score_desc,"202601,202602",25.75716489700684,98,0.5612244897959183,1.7360332196525372,17.228408039957024,0.1758000820403778,-3.6327868541243546,0.29591836734693877,39,0.5384615384615384,0.1475844540398277,-3.599999999999998,18.487140468776555,1.073061447459348,38,1.0,64,0.5625,1.3622933676439117,6.012093762272832,0.093938965035513,-2.7493321061408538,0.453125,22,0.6363636363636364,0.43494281302051013,-2.749332106140854,8.984756251822526,1.4944471272560294,64,1.0
SPY,202604,SELECTED,"d35,d50,d65,d80","d35,d50,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,3,0,score_desc,"202602,202603",26.507979712722662,116,0.5948275862068966,1.5138918882167374,13.193606036450365,0.11373798307284798,-5.330898981512353,0.39655172413793105,41,0.6341463414634146,0.3739459714896485,-4.698112127388009,13.96953115543156,1.0588106933644619,50,1.0,46,0.5,0.9679249049724984,-0.4220469774174489,-0.009174934291683671,-3.5369566783731505,0.2608695652173913,18,0.5555555555555556,0.17248596399917834,-3.1834321691979017,5.520322022617387,-13.079875743683404,46,0.0
SPY,202605,SELECTED,"d35,d50,d65,d80","d35,d50,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d50_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,1,0,time_asc,"202603,202604",27.45234259385151,40,0.675,2.432349913331424,9.331990701953613,0.23329976754884033,-1.5581243267624298,0.425,40,0.675,0.30576931717833433,-1.5581243267624298,6.930332894847741,0.7426424989254334,18,1.0,20,0.7,2.26730034848715,4.56228125455374,0.22811406272768703,-1.3603447460816374,0.45,20,0.7,0.3521917432618012,-1.3603447460816374,5.0721013806615085,1.1117467551126758,20,1.0
SPY,202606,SELECTED,"d35,d65,d80","d35,d65,d80",event_trade_union_config_selector,research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d65_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv|research_papers\JEPA\results\_diagnostics\event_option_mh30trail_clean1000_nopool_d80_return_wf202504_202606_val2_gpu_combined_v1\event_option_gate_trades.csv,1,0,time_asc,"202604,202605",28.02008553785776,38,0.7105263157894737,2.4057110986041996,8.604431635597734,0.22643241146309828,-1.360344746081636,0.39473684210526316,38,0.7105263157894737,0.3312812376782362,-1.360344746081636,6.283365269492471,0.7302475672532874,18,1.0,21,0.38095238095238093,0.6507787003011918,-2.7239261376507065,-0.12971076845955745,-3.5750000279396765,0.14285714285714285,21,0.38095238095238093,-0.6,-3.5750000279396765,4.455725823250843,-1.6357733646528883,21,0.0

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
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_val2_configsel_m2_wf202601_202606_SPY_v2",
  "ticker": "SPY",
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
  "select_months": 2,
  "min_select_trades": 36,
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