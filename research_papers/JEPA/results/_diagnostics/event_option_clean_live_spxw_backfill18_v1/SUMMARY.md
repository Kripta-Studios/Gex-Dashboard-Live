# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 132,
  "win_rate": 0.3484848484848485,
  "profit_factor": 0.8914728682170543,
  "pnl_return": -2.8,
  "avg_return": -0.02121212121212121,
  "max_drawdown": -6.199999999999998,
  "call_rate": 0.36363636363636365,
  "days_with_trades": 110,
  "daily_win_rate": 0.4,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -5.899999999999999,
  "top5_day_return": 3.2,
  "top5_share_of_pnl": -1.142857142857143,
  "min_month_trades": 18,
  "positive_month_rate": 0.5
}
```

- Risk capital: $5,000
- Net PnL: $-14,000

## By Ticker

```json
{
  "SPXW": {
    "trades": 132,
    "win_rate": 0.3484848484848485,
    "profit_factor": 0.8914728682170543,
    "pnl_return": -2.8,
    "avg_return": -0.02121212121212121,
    "max_drawdown": -6.199999999999998,
    "call_rate": 0.36363636363636365,
    "days_with_trades": 110,
    "daily_win_rate": 0.4,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.899999999999999,
    "top5_day_return": 3.2,
    "top5_share_of_pnl": -1.142857142857143,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  }
}
```

## By Source

```json
{
  "clean_d25": {
    "trades": 87,
    "win_rate": 0.40229885057471265,
    "profit_factor": 1.1217948717948716,
    "pnl_return": 1.9000000000000001,
    "avg_return": 0.021839080459770118,
    "max_drawdown": -3.9999999999999964,
    "call_rate": 0.2413793103448276,
    "days_with_trades": 73,
    "daily_win_rate": 0.4520547945205479,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.6999999999999984,
    "top5_day_return": 3.5,
    "top5_share_of_pnl": 1.8421052631578947,
    "min_month_trades": 0,
    "positive_month_rate": 0.5
  },
  "clean_d50": {
    "trades": 45,
    "win_rate": 0.24444444444444444,
    "profit_factor": 0.5392156862745098,
    "pnl_return": -4.699999999999999,
    "avg_return": -0.10444444444444442,
    "max_drawdown": -6.499999999999998,
    "call_rate": 0.6,
    "days_with_trades": 41,
    "daily_win_rate": 0.2682926829268293,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -6.499999999999998,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.5319148936170214,
    "min_month_trades": 1,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 18 | 27.8% | 0.641 | -1.400 | -7,000 |
| 202602 | 18 | 11.1% | 0.208 | -3.800 | -19,000 |
| 202603 | 22 | 50.0% | 1.667 | 2.200 | 11,000 |
| 202604 | 22 | 50.0% | 1.667 | 2.200 | 11,000 |
| 202605 | 32 | 37.5% | 1.000 | 0.000 | 0 |
| 202606 | 20 | 25.0% | 0.556 | -2.000 | -10,000 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spxw_d25_wf2026_v1\\event_option_gate_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_d50_fallback_wf2026_v1\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spxw_backfill18_v1",
  "primary_name": "clean_d25",
  "fallback_name": "clean_d50",
  "ticker": "SPXW",
  "start_month": "202601",
  "end_month": "202606",
  "exclude_months": [],
  "min_month_trades": 18,
  "auto_partial_month_target": false,
  "partial_month_observed_floor": 0,
  "backfill_only_partial_months": false,
  "max_day": 3,
  "cooldown_minutes": 30,
  "min_entry_minute": 0,
  "risk_capital": 5000.0
}
```