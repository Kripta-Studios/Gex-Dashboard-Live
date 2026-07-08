# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 121,
  "win_rate": 0.5537190082644629,
  "profit_factor": 1.4681898927920876,
  "pnl_return": 15.156547325475705,
  "avg_return": 0.1252607216981463,
  "max_drawdown": -3.3055016561191373,
  "call_rate": 0.19008264462809918,
  "days_with_trades": 109,
  "daily_win_rate": 0.5412844036697247,
  "median_daily_return": 0.2602040717026832,
  "daily_max_drawdown": -3.3055016561191373,
  "top5_day_return": 15.555293333588306,
  "top5_share_of_pnl": 1.0263084988651983,
  "min_month_trades": 18,
  "positive_month_rate": 1.0
}
```

- Risk capital: $5,000
- Net PnL: $75,783

## By Ticker

```json
{
  "SPY": {
    "trades": 121,
    "win_rate": 0.5537190082644629,
    "profit_factor": 1.4681898927920876,
    "pnl_return": 15.156547325475705,
    "avg_return": 0.1252607216981463,
    "max_drawdown": -3.3055016561191373,
    "call_rate": 0.19008264462809918,
    "days_with_trades": 109,
    "daily_win_rate": 0.5412844036697247,
    "median_daily_return": 0.2602040717026832,
    "daily_max_drawdown": -3.3055016561191373,
    "top5_day_return": 15.555293333588306,
    "top5_share_of_pnl": 1.0263084988651983,
    "min_month_trades": 18,
    "positive_month_rate": 1.0
  }
}
```

## By Source

```json
{
  "clean_d35": {
    "trades": 28,
    "win_rate": 0.4642857142857143,
    "profit_factor": 1.2576091687211024,
    "pnl_return": 2.318482518489919,
    "avg_return": 0.08280294708892567,
    "max_drawdown": -4.083934090998915,
    "call_rate": 0.21428571428571427,
    "days_with_trades": 27,
    "daily_win_rate": 0.4444444444444444,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -4.083934090998915,
    "top5_day_return": 8.650201173280854,
    "top5_share_of_pnl": 3.730975370439683,
    "min_month_trades": 1,
    "positive_month_rate": 0.5
  },
  "prod_static_union": {
    "trades": 93,
    "win_rate": 0.5806451612903226,
    "profit_factor": 1.5492772556954229,
    "pnl_return": 12.838064806985782,
    "avg_return": 0.13804370760199766,
    "max_drawdown": -3.277095154744031,
    "call_rate": 0.1827956989247312,
    "days_with_trades": 93,
    "daily_win_rate": 0.5806451612903226,
    "median_daily_return": 0.2889610027699905,
    "daily_max_drawdown": -3.277095154744031,
    "top5_day_return": 11.465716913534648,
    "top5_share_of_pnl": 0.8931032118871703,
    "min_month_trades": 9,
    "positive_month_rate": 0.8333333333333334
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 18 | 55.6% | 2.152 | 5.530 | 27,651 |
| 202602 | 20 | 55.0% | 1.195 | 1.050 | 5,249 |
| 202603 | 22 | 59.1% | 1.553 | 2.987 | 14,937 |
| 202604 | 19 | 57.9% | 1.024 | 0.117 | 587 |
| 202605 | 21 | 52.4% | 1.456 | 2.739 | 13,694 |
| 202606 | 21 | 52.4% | 1.455 | 2.733 | 13,665 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\event_option_mh30trail_frozen2025_static_union_deploy202607_production_v1\\combined_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_clean1000_nopool_d35_return_wf202504_202606_val2_gpu_v1_SPY\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\goal_spy_prod_backfill_clean_d35_target18_max2_v1",
  "primary_name": "prod_static_union",
  "fallback_name": "clean_d35",
  "ticker": "SPY",
  "start_month": "202601",
  "end_month": "202606",
  "exclude_months": [],
  "min_month_trades": 18,
  "auto_partial_month_target": false,
  "partial_month_observed_floor": 0,
  "backfill_only_partial_months": false,
  "max_day": 2,
  "cooldown_minutes": 30,
  "min_entry_minute": 0,
  "risk_capital": 5000.0
}
```