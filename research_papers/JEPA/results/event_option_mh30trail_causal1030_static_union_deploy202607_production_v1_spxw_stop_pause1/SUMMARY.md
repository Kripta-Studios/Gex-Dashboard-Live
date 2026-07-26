# Event Option Causal 10:30 Static Union

This artifact retrains/export-selects the event-option components with entry_time_min_et=10:30 and materializes the runtime static union with SPXW stop-pause-1.

## Overall

```json
{
  "trades": 562,
  "win_rate": 0.5213523131672598,
  "profit_factor": 1.4291066549275722,
  "pnl_return": 67.89054434172263,
  "avg_return": 0.12080168032334988,
  "max_drawdown": -11.60959577191494,
  "call_rate": 0.48576512455516013,
  "days_with_trades": 120,
  "daily_win_rate": 0.5166666666666667,
  "median_daily_return": 0.0516905291425378,
  "daily_max_drawdown": -11.476471385037136,
  "top5_day_return": 50.99388974545458,
  "top5_share_of_pnl": 0.7511191763138643,
  "min_month_trades": 78,
  "positive_month_rate": 0.6666666666666666
}
```

## By Ticker

```json
{
  "QQQ": {
    "trades": 229,
    "win_rate": 0.5109170305676856,
    "profit_factor": 1.1093524830215484,
    "pnl_return": 7.11329395338166,
    "avg_return": 0.031062419010400265,
    "max_drawdown": -9.196929526149583,
    "call_rate": 0.7248908296943232,
    "days_with_trades": 116,
    "daily_win_rate": 0.4224137931034483,
    "median_daily_return": -0.14666668946544315,
    "daily_max_drawdown": -8.30881980029999,
    "top5_day_return": 16.394293407731467,
    "top5_share_of_pnl": 2.3047400424015403,
    "min_month_trades": 35,
    "positive_month_rate": 0.5
  },
  "SPXW": {
    "trades": 226,
    "win_rate": 0.5,
    "profit_factor": 1.6589521520758368,
    "pnl_return": 44.67695591074172,
    "avg_return": 0.19768564562275096,
    "max_drawdown": -9.599999897862656,
    "call_rate": 0.28761061946902655,
    "days_with_trades": 86,
    "daily_win_rate": 0.4883720930232558,
    "median_daily_return": -0.1702271559198405,
    "daily_max_drawdown": -8.672222169142199,
    "top5_day_return": 40.390216541620276,
    "top5_share_of_pnl": 0.9040503256827581,
    "min_month_trades": 25,
    "positive_month_rate": 0.6666666666666666
  },
  "SPY": {
    "trades": 107,
    "win_rate": 0.5887850467289719,
    "profit_factor": 1.634757995954787,
    "pnl_return": 16.100294477599242,
    "avg_return": 0.15047004184672189,
    "max_drawdown": -4.365845304338928,
    "call_rate": 0.3925233644859813,
    "days_with_trades": 107,
    "daily_win_rate": 0.5887850467289719,
    "median_daily_return": 0.2983870502565211,
    "daily_max_drawdown": -4.365845304338928,
    "top5_day_return": 11.00581201951002,
    "top5_share_of_pnl": 0.6835783056528992,
    "min_month_trades": 15,
    "positive_month_rate": 0.6666666666666666
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL R | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 87 | 54.02% | 1.634 | 14.656 | 73,279 |
| 202602 | 78 | 55.13% | 1.559 | 11.616 | 58,080 |
| 202603 | 113 | 47.79% | 0.908 | -3.214 | -16,071 |
| 202604 | 97 | 51.55% | 1.680 | 18.647 | 93,233 |
| 202605 | 98 | 48.98% | 0.913 | -2.537 | -12,685 |
| 202606 | 89 | 57.30% | 2.272 | 28.723 | 143,617 |

## Integrity

```json
{
  "passed": true,
  "issues": [],
  "runtime_risk_guard": "spxw_stop_pause_1",
  "candidate_universe_filter": {
    "near_level_abs_bps_max": 20.0,
    "min_entry_time_et": "10:30",
    "requires_complete_initial_balance": true
  },
  "source_component_dirs": {
    "QQQ": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1030_frozen2025_select2026_d35_return_deploy202607_QQQ_v1",
    "SPXW": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1030_frozen2025_select2026_d25_return_deploy202607_SPXW_v1",
    "SPY": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1030_frozen2025_select2026_d35_return_deploy202607_SPY_v1"
  },
  "label_data": "research_papers/JEPA/results/_diagnostics/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_minhold30_sl60_trail050_025_tp1000_v1_physics/event_option_dataset.parquet",
  "skipped_trades": 48,
  "skip_reason": "known SPXW event_option_stop_loss_60% earlier same day",
  "pre_1030_trades": 0,
  "near_level_filter_violations": 0
}
```