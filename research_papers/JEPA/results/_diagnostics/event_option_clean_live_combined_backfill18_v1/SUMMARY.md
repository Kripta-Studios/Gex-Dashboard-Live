# Combined Event Option Trade Streams

This artifact combines already generated causal OOS trade streams. It does not train or select any new trade.

## Overall

```json
{
  "trades": 374,
  "win_rate": 0.35294117647058826,
  "profit_factor": 0.9040511128882015,
  "pnl_return": -6.965889204316586,
  "avg_return": -0.01862537220405504,
  "max_drawdown": -13.600000000000001,
  "call_rate": 0.3609625668449198,
  "days_with_trades": 123,
  "daily_win_rate": 0.3821138211382114,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -12.600000000000001,
  "top5_day_return": 8.2,
  "top5_share_of_pnl": -1.177164861439178,
  "min_month_trades": 55,
  "positive_month_rate": 0.5
}
```

- Risk capital: $5,000
- Net PnL: $-34,829

## By Ticker

```json
{
  "QQQ": {
    "trades": 119,
    "win_rate": 0.3865546218487395,
    "profit_factor": 1.033521040898786,
    "pnl_return": 0.7341107956834132,
    "avg_return": 0.006168998283053892,
    "max_drawdown": -4.6,
    "call_rate": 0.31932773109243695,
    "days_with_trades": 109,
    "daily_win_rate": 0.41284403669724773,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -4.6,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": 4.086576600752996,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  },
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
  },
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

## Monthly PnL Return

| Month | Ticker | Trades | WR | PF | PnL Return | PnL $ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | QQQ | 22 | 59.1% | 2.407 | 3.800 | 19,000 |
| 202601 | SPXW | 18 | 27.8% | 0.641 | -1.400 | -7,000 |
| 202601 | SPY | 21 | 33.3% | 0.833 | -0.700 | -3,500 |
| 202601 | TOTAL | 61 | 41.0% | 1.157 | 1.700 | 8,500 |
| 202602 | QQQ | 18 | 16.7% | 0.333 | -3.000 | -15,000 |
| 202602 | SPXW | 18 | 11.1% | 0.208 | -3.800 | -19,000 |
| 202602 | SPY | 19 | 5.3% | 0.093 | -4.900 | -24,500 |
| 202602 | TOTAL | 55 | 10.9% | 0.204 | -11.700 | -58,500 |
| 202603 | QQQ | 23 | 47.8% | 1.528 | 1.900 | 9,500 |
| 202603 | SPXW | 22 | 50.0% | 1.667 | 2.200 | 11,000 |
| 202603 | SPY | 22 | 40.9% | 1.154 | 0.600 | 3,000 |
| 202603 | TOTAL | 67 | 46.3% | 1.435 | 4.700 | 23,500 |
| 202604 | QQQ | 18 | 50.0% | 1.531 | 1.434 | 7,171 |
| 202604 | SPXW | 22 | 50.0% | 1.667 | 2.200 | 11,000 |
| 202604 | SPY | 20 | 40.0% | 1.111 | 0.400 | 2,000 |
| 202604 | TOTAL | 60 | 46.7% | 1.420 | 4.034 | 20,171 |
| 202605 | QQQ | 20 | 20.0% | 0.417 | -2.800 | -14,000 |
| 202605 | SPXW | 32 | 37.5% | 1.000 | 0.000 | 0 |
| 202605 | SPY | 20 | 35.0% | 0.897 | -0.400 | -2,000 |
| 202605 | TOTAL | 72 | 31.9% | 0.782 | -3.200 | -16,000 |
| 202606 | QQQ | 18 | 33.3% | 0.833 | -0.600 | -3,000 |
| 202606 | SPXW | 20 | 25.0% | 0.556 | -2.000 | -10,000 |
| 202606 | SPY | 21 | 38.1% | 1.026 | 0.100 | 500 |
| 202606 | TOTAL | 59 | 32.2% | 0.792 | -2.500 | -12,500 |

## Integrity

```json
{
  "passed": true,
  "folds_checked": 36,
  "issues": []
}
```

## Sources

```json
{
  "trade_file": [
    "SPXW=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spxw_backfill18_v1\\monthly_volume_backfill_trades.csv",
    "QQQ=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_qqq_backfill18_v1\\monthly_volume_backfill_trades.csv",
    "SPY=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spy_backfill18_v1\\monthly_volume_backfill_trades.csv"
  ],
  "fold_file": [
    "SPXW=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spxw_d25_wf2026_v1\\fold_configs.csv",
    "QQQ=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_qqq_d25_wf2026_v1\\fold_configs.csv",
    "SPY=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_spy_d25_nothr_wf2026_v1\\fold_configs.csv",
    "D50=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_d50_fallback_wf2026_v1\\fold_configs.csv"
  ],
  "start_month": "202601",
  "end_month": "202606"
}
```