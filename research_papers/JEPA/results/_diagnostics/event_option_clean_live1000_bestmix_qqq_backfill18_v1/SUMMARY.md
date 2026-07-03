# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 172,
  "win_rate": 0.42441860465116277,
  "profit_factor": 1.2063239329523774,
  "pnl_return": 6.127820808685605,
  "avg_return": 0.035626865166776774,
  "max_drawdown": -4.999999999999998,
  "call_rate": 0.36046511627906974,
  "days_with_trades": 110,
  "daily_win_rate": 0.5454545454545454,
  "median_daily_return": 0.2,
  "daily_max_drawdown": -4.9999999999999964,
  "top5_day_return": 5.0,
  "top5_share_of_pnl": 0.8159507524947488,
  "min_month_trades": 10,
  "positive_month_rate": 0.5
}
```

- Risk capital: $5,000
- Net PnL: $30,639

## By Ticker

```json
{
  "QQQ": {
    "trades": 172,
    "win_rate": 0.42441860465116277,
    "profit_factor": 1.2063239329523774,
    "pnl_return": 6.127820808685605,
    "avg_return": 0.035626865166776774,
    "max_drawdown": -4.999999999999998,
    "call_rate": 0.36046511627906974,
    "days_with_trades": 110,
    "daily_win_rate": 0.5454545454545454,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -4.9999999999999964,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 0.8159507524947488,
    "min_month_trades": 10,
    "positive_month_rate": 0.5
  }
}
```

## By Source

```json
{
  "qqq_d25_win": {
    "trades": 161,
    "win_rate": 0.4161490683229814,
    "profit_factor": 1.164107120875376,
    "pnl_return": 4.627820808685604,
    "avg_return": 0.02874422862537642,
    "max_drawdown": -4.9999999999999964,
    "call_rate": 0.36645962732919257,
    "days_with_trades": 106,
    "daily_win_rate": 0.5188679245283019,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -4.999999999999998,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 1.0804221266769625,
    "min_month_trades": 7,
    "positive_month_rate": 0.5
  },
  "qqq_d50_return": {
    "trades": 11,
    "win_rate": 0.5454545454545454,
    "profit_factor": 2.0,
    "pnl_return": 1.5,
    "avg_return": 0.13636363636363635,
    "max_drawdown": -0.6,
    "call_rate": 0.2727272727272727,
    "days_with_trades": 10,
    "daily_win_rate": 0.5,
    "median_daily_return": 0.1,
    "daily_max_drawdown": -0.6,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": 2.0,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 22 | 59.1% | 2.407 | 3.800 | 19,000 |
| 202602 | 10 | 20.0% | 0.417 | -1.400 | -7,000 |
| 202603 | 43 | 46.5% | 1.449 | 3.100 | 15,500 |
| 202604 | 37 | 37.8% | 0.917 | -0.572 | -2,861 |
| 202605 | 21 | 47.6% | 1.515 | 1.700 | 8,500 |
| 202606 | 39 | 35.9% | 0.933 | -0.500 | -2,500 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d25_win_wf2026_v1\\event_option_gate_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d50_return_wf2026_v1\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_bestmix_qqq_backfill18_v1",
  "primary_name": "qqq_d25_win",
  "fallback_name": "qqq_d50_return",
  "ticker": "QQQ",
  "start_month": "202601",
  "end_month": "202606",
  "exclude_months": [],
  "min_month_trades": 18,
  "auto_partial_month_target": false,
  "partial_month_observed_floor": 0,
  "backfill_only_partial_months": false,
  "max_day": 3,
  "cooldown_minutes": 30,
  "min_entry_minute": 600,
  "risk_capital": 5000.0
}
```