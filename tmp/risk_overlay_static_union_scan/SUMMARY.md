# Risk Overlay Static Union Scan

- Trades: research_papers\JEPA\results\event_option_mh30trail_frozen2025_static_union_deploy202607_production_v1\combined_trades.csv
- Labels: research_papers\JEPA\results\_diagnostics\event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics\event_option_dataset.parquet
- Months: 202601, 202602, 202603, 202604, 202605, 202606
- Select split: 202601, 202602, 202603
- Test split: 202604, 202605, 202606
- Configs scanned: 24603

## Baseline

{
  "full": {
    "trades": 697,
    "win_rate": 0.5781922525107605,
    "profit_factor": 1.9152565398141204,
    "pnl_return": 160.1258673092688,
    "avg_return": 0.22973582110368554,
    "max_drawdown": -12.681639056061876,
    "call_rate": 0.31420373027259685,
    "days_with_trades": 121,
    "daily_win_rate": 0.6033057851239669,
    "median_daily_return": 0.8571264933487905,
    "daily_max_drawdown": -12.022185463356386,
    "top5_day_return": 62.56635192975472,
    "top5_share_of_pnl": 0.39073232189845625,
    "min_month_trades": 103,
    "positive_month_rate": 1.0
  },
  "select": {
    "trades": 342,
    "win_rate": 0.5994152046783626,
    "profit_factor": 1.9080887330458145,
    "pnl_return": 74.03473709116801,
    "avg_return": 0.21647583944785967,
    "max_drawdown": -12.681639056061876,
    "call_rate": 0.41228070175438597,
    "days_with_trades": 61,
    "daily_win_rate": 0.639344262295082,
    "median_daily_return": 0.882417185911599,
    "daily_max_drawdown": -12.022185463356386,
    "top5_day_return": 41.42880773707606,
    "top5_share_of_pnl": 0.5595860722252544,
    "min_month_trades": 103,
    "positive_month_rate": 1.0
  },
  "test": {
    "trades": 355,
    "win_rate": 0.5577464788732395,
    "profit_factor": 1.921511664451477,
    "pnl_return": 86.09113021810082,
    "avg_return": 0.24251022596648117,
    "max_drawdown": -6.226862095903051,
    "call_rate": 0.21971830985915494,
    "days_with_trades": 60,
    "daily_win_rate": 0.5666666666666667,
    "median_daily_return": 0.6540453417112599,
    "daily_max_drawdown": -6.021347569694953,
    "top5_day_return": 57.71342594607448,
    "top5_share_of_pnl": 0.6703759818214133,
    "min_month_trades": 109,
    "positive_month_rate": 1.0
  },
  "skips": {}
}

## Best full-sample configs with gates

                                                                                              name  full_trades  full_win_rate  full_profit_factor  full_pnl_return  full_daily_max_drawdown  test_trades  test_profit_factor  test_pnl_return  test_daily_max_drawdown  skipped
                                                combo_global_stop_pause2_post_loss_cooldown_spxw30          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
                      combo_global_stop_pause2_post_loss_cooldown_spxw30_spxw_second_min_score0p34          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
                          combo_global_loss_limit-1p0_global_stop_pause2_post_loss_cooldown_spxw30          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
combo_global_loss_limit-1p0_global_stop_pause2_post_loss_cooldown_spxw30_spxw_second_min_score0p34          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
                          combo_global_loss_limit-1p2_global_stop_pause2_post_loss_cooldown_spxw30          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
combo_global_loss_limit-1p2_global_stop_pause2_post_loss_cooldown_spxw30_spxw_second_min_score0p34          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
                          combo_global_loss_limit-1p5_global_stop_pause2_post_loss_cooldown_spxw30          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
combo_global_loss_limit-1p5_global_stop_pause2_post_loss_cooldown_spxw30_spxw_second_min_score0p34          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
                          combo_global_stop_pause2_post_loss_cooldown_spxw30_ticker_loss_limit-1p0          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
combo_global_stop_pause2_post_loss_cooldown_spxw30_spxw_second_min_score0p34_ticker_loss_limit-1p0          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
                            combo_global_stop_pause2_post_loss_cooldown_spxw30_spxw_loss_limit-1p2          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59
  combo_global_stop_pause2_post_loss_cooldown_spxw30_spxw_loss_limit-1p2_spxw_second_min_score0p34          638       0.603448            2.157658       174.056074               -10.222185          329            2.160497        94.492053                -5.421348       59

## Best select-period configs and their holdout

                                                                    name  select_trades  select_profit_factor  select_pnl_return  select_daily_max_drawdown  test_trades  test_profit_factor  test_pnl_return  test_daily_max_drawdown  skipped
                                                     global_stop_pause_2            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
                      combo_global_stop_pause2_spxw_second_min_score0p34            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
                          combo_global_loss_limit-1p0_global_stop_pause2            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
combo_global_loss_limit-1p0_global_stop_pause2_spxw_second_min_score0p34            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
                          combo_global_loss_limit-1p2_global_stop_pause2            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
combo_global_loss_limit-1p2_global_stop_pause2_spxw_second_min_score0p34            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
                          combo_global_loss_limit-1p5_global_stop_pause2            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
combo_global_loss_limit-1p5_global_stop_pause2_spxw_second_min_score0p34            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
                          combo_global_stop_pause2_ticker_loss_limit-1p0            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
combo_global_stop_pause2_spxw_second_min_score0p34_ticker_loss_limit-1p0            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
                            combo_global_stop_pause2_spxw_loss_limit-1p2            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56
  combo_global_stop_pause2_spxw_loss_limit-1p2_spxw_second_min_score0p34            311              2.146944           79.74479                 -10.222185          330            2.144693        93.892053                -6.021348       56