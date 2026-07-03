# Combined Event Option Trade Streams

This artifact combines already generated causal OOS trade streams. It does not train or select any new trade.

## Overall

```json
{
  "trades": 469,
  "win_rate": 0.40298507462686567,
  "profit_factor": 1.1169978667700666,
  "pnl_return": 9.827820808685605,
  "avg_return": 0.02095484180956419,
  "max_drawdown": -9.499999999999996,
  "call_rate": 0.35607675906183367,
  "days_with_trades": 123,
  "daily_win_rate": 0.4878048780487805,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -9.099999999999998,
  "top5_day_return": 10.2,
  "top5_share_of_pnl": 1.0378699610584547,
  "min_month_trades": 46,
  "positive_month_rate": 0.8333333333333334
}
```

- Risk capital: $5,000
- Net PnL: $49,139

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
  },
  "SPXW": {
    "trades": 139,
    "win_rate": 0.35251798561151076,
    "profit_factor": 0.9074074074074076,
    "pnl_return": -2.4999999999999996,
    "avg_return": -0.017985611510791363,
    "max_drawdown": -5.899999999999999,
    "call_rate": 0.31654676258992803,
    "days_with_trades": 115,
    "daily_win_rate": 0.391304347826087,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -5.899999999999999,
    "top5_day_return": 4.5,
    "top5_share_of_pnl": -1.8000000000000003,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  },
  "SPY": {
    "trades": 158,
    "win_rate": 0.4240506329113924,
    "profit_factor": 1.2271062271062272,
    "pnl_return": 6.2,
    "avg_return": 0.039240506329113925,
    "max_drawdown": -3.6999999999999997,
    "call_rate": 0.3860759493670886,
    "days_with_trades": 111,
    "daily_win_rate": 0.5225225225225225,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -3.6999999999999997,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 0.8064516129032258,
    "min_month_trades": 18,
    "positive_month_rate": 0.8333333333333334
  }
}
```

## Monthly PnL Return

| Month | Ticker | Trades | WR | PF | PnL Return | PnL $ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | QQQ | 22 | 59.1% | 2.407 | 3.800 | 19,000 |
| 202601 | SPXW | 21 | 33.3% | 0.833 | -0.700 | -3,500 |
| 202601 | SPY | 20 | 40.0% | 1.111 | 0.400 | 2,000 |
| 202601 | TOTAL | 63 | 44.4% | 1.333 | 3.500 | 17,500 |
| 202602 | QQQ | 10 | 20.0% | 0.417 | -1.400 | -7,000 |
| 202602 | SPXW | 18 | 5.6% | 0.098 | -4.600 | -23,000 |
| 202602 | SPY | 18 | 16.7% | 0.333 | -3.000 | -15,000 |
| 202602 | TOTAL | 46 | 13.0% | 0.250 | -9.000 | -45,000 |
| 202603 | QQQ | 43 | 46.5% | 1.449 | 3.100 | 15,500 |
| 202603 | SPXW | 22 | 50.0% | 1.667 | 2.200 | 11,000 |
| 202603 | SPY | 40 | 40.0% | 1.111 | 0.800 | 4,000 |
| 202603 | TOTAL | 105 | 44.8% | 1.351 | 6.100 | 30,500 |
| 202604 | QQQ | 37 | 37.8% | 0.917 | -0.572 | -2,861 |
| 202604 | SPXW | 42 | 38.1% | 1.026 | 0.200 | 1,000 |
| 202604 | SPY | 21 | 47.6% | 1.515 | 1.700 | 8,500 |
| 202604 | TOTAL | 100 | 40.0% | 1.074 | 1.328 | 6,639 |
| 202605 | QQQ | 21 | 47.6% | 1.515 | 1.700 | 8,500 |
| 202605 | SPXW | 18 | 44.4% | 1.333 | 1.000 | 5,000 |
| 202605 | SPY | 39 | 43.6% | 1.288 | 1.900 | 9,500 |
| 202605 | TOTAL | 78 | 44.9% | 1.357 | 4.600 | 23,000 |
| 202606 | QQQ | 39 | 35.9% | 0.933 | -0.500 | -2,500 |
| 202606 | SPXW | 18 | 33.3% | 0.833 | -0.600 | -3,000 |
| 202606 | SPY | 20 | 65.0% | 3.095 | 4.400 | 22,000 |
| 202606 | TOTAL | 77 | 42.9% | 1.250 | 3.300 | 16,500 |

## Integrity

```json
{
  "passed": false,
  "folds_checked": 0,
  "issues": [
    "no fold files supplied"
  ]
}
```

## Sources

```json
{
  "trade_file": [
    "QQQ_BEST=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_bestmix_qqq_backfill18_v1\\monthly_volume_backfill_trades.csv",
    "SPXW_BEST=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_bestmix_spxw_backfill18_v1\\monthly_volume_backfill_trades.csv",
    "SPY_BEST=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_bestmix_spy_backfill18_v1\\monthly_volume_backfill_trades.csv"
  ],
  "fold_file": [],
  "start_month": "202601",
  "end_month": "202606"
}
```