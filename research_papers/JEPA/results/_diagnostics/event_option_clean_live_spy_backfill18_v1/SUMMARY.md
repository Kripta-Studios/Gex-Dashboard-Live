# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 123,
  "win_rate": 0.3252032520325203,
  "profit_factor": 0.8032128514056225,
  "pnl_return": -4.8999999999999995,
  "avg_return": -0.039837398373983736,
  "max_drawdown": -7.299999999999997,
  "call_rate": 0.3983739837398374,
  "days_with_trades": 120,
  "daily_win_rate": 0.325,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -7.299999999999997,
  "top5_day_return": 3.0,
  "top5_share_of_pnl": -0.6122448979591837,
  "min_month_trades": 19,
  "positive_month_rate": 0.5
}
```

- Risk capital: $5,000
- Net PnL: $-24,500

## By Ticker

```json
{
  "SPY": {
    "trades": 123,
    "win_rate": 0.3252032520325203,
    "profit_factor": 0.8032128514056225,
    "pnl_return": -4.8999999999999995,
    "avg_return": -0.039837398373983736,
    "max_drawdown": -7.299999999999997,
    "call_rate": 0.3983739837398374,
    "days_with_trades": 120,
    "daily_win_rate": 0.325,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.299999999999997,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": -0.6122448979591837,
    "min_month_trades": 19,
    "positive_month_rate": 0.5
  }
}
```

## By Source

```json
{
  "clean_d25": {
    "trades": 120,
    "win_rate": 0.325,
    "profit_factor": 0.8024691358024693,
    "pnl_return": -4.799999999999999,
    "avg_return": -0.039999999999999994,
    "max_drawdown": -7.299999999999997,
    "call_rate": 0.38333333333333336,
    "days_with_trades": 120,
    "daily_win_rate": 0.325,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -7.299999999999997,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.5208333333333335,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  },
  "clean_d50": {
    "trades": 3,
    "win_rate": 0.3333333333333333,
    "profit_factor": 0.8333333333333334,
    "pnl_return": -0.09999999999999998,
    "avg_return": -0.033333333333333326,
    "max_drawdown": -0.6,
    "call_rate": 1.0,
    "days_with_trades": 3,
    "daily_win_rate": 0.3333333333333333,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -0.6,
    "top5_day_return": -0.09999999999999998,
    "top5_share_of_pnl": 1.0,
    "min_month_trades": 0,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 21 | 33.3% | 0.833 | -0.700 | -3,500 |
| 202602 | 19 | 5.3% | 0.093 | -4.900 | -24,500 |
| 202603 | 22 | 40.9% | 1.154 | 0.600 | 3,000 |
| 202604 | 20 | 40.0% | 1.111 | 0.400 | 2,000 |
| 202605 | 20 | 35.0% | 0.897 | -0.400 | -2,000 |
| 202606 | 21 | 38.1% | 1.026 | 0.100 | 500 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spy_d25_nothr_wf2026_v1\\event_option_gate_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_d50_fallback_wf2026_v1\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spy_backfill18_v1",
  "primary_name": "clean_d25",
  "fallback_name": "clean_d50",
  "ticker": "SPY",
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