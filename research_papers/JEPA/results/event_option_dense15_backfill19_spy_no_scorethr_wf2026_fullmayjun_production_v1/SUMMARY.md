# Event Option Dense15 WF2026 Full-May-Jun, SPY No-Score-Threshold Backfill19 Variant

Causal Jan-Jun 2026 walk-forward. SPY primary uses the no-score-threshold d25 win model; fallback only enforces monthly volume to 19. SPXW/QQQ use the prior full-May-Jun backfill18 streams.

## Overall

```json
{
  "trades": 425,
  "win_rate": 0.4894117647058824,
  "profit_factor": 1.5975422427035335,
  "pnl_return": 38.89999999999999,
  "avg_return": 0.09152941176470586,
  "max_drawdown": -3.4000000000000004,
  "call_rate": 0.3341176470588235,
  "days_with_trades": 121,
  "daily_win_rate": 0.5619834710743802,
  "median_daily_return": 0.4,
  "daily_max_drawdown": -3.3999999999999995,
  "top5_day_return": 9.4,
  "top5_share_of_pnl": 0.24164524421593836,
  "min_month_trades": 58,
  "positive_month_rate": 1.0
}
```

## By Ticker

```json
{
  "QQQ": {
    "trades": 178,
    "win_rate": 0.4606741573033708,
    "profit_factor": 1.4236111111111114,
    "pnl_return": 12.2,
    "avg_return": 0.06853932584269662,
    "max_drawdown": -1.9000000000000092,
    "call_rate": 0.28651685393258425,
    "days_with_trades": 109,
    "daily_win_rate": 0.5596330275229358,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -1.9000000000000004,
    "top5_day_return": 4.7,
    "top5_share_of_pnl": 0.3852459016393443,
    "min_month_trades": 19,
    "positive_month_rate": 1.0
  },
  "SPXW": {
    "trades": 125,
    "win_rate": 0.512,
    "profit_factor": 1.7486338797814203,
    "pnl_return": 13.7,
    "avg_return": 0.10959999999999999,
    "max_drawdown": -1.500000000000007,
    "call_rate": 0.296,
    "days_with_trades": 120,
    "daily_win_rate": 0.5333333333333333,
    "median_daily_return": 0.5,
    "daily_max_drawdown": -1.500000000000007,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": 0.18248175182481752,
    "min_month_trades": 19,
    "positive_month_rate": 1.0
  },
  "SPY": {
    "trades": 122,
    "win_rate": 0.5081967213114754,
    "profit_factor": 1.7222222222222219,
    "pnl_return": 12.999999999999998,
    "avg_return": 0.10655737704918031,
    "max_drawdown": -1.600000000000005,
    "call_rate": 0.4426229508196721,
    "days_with_trades": 116,
    "daily_win_rate": 0.5344827586206896,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -1.600000000000005,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": 0.19230769230769235,
    "min_month_trades": 19,
    "positive_month_rate": 1.0
  }
}
```

## Monthly

| Month | Ticker | Trades | WR | PF | PnL $ |
| --- | --- | ---: | ---: | ---: | ---: |
| 202601 | QQQ | 21 | 42.9% | 1.250 | 4,500 |
| 202601 | SPXW | 21 | 42.9% | 1.250 | 4,500 |
| 202601 | SPY | 21 | 38.1% | 1.026 | 500 |
| 202601 | TOTAL | 63 | 41.3% | 1.171 | 9,500 |
| 202602 | QQQ | 19 | 52.6% | 1.852 | 11,500 |
| 202602 | SPXW | 19 | 52.6% | 1.852 | 11,500 |
| 202602 | SPY | 20 | 50.0% | 1.667 | 10,000 |
| 202602 | TOTAL | 58 | 51.7% | 1.786 | 33,000 |
| 202603 | QQQ | 37 | 45.9% | 1.417 | 12,500 |
| 202603 | SPXW | 22 | 54.5% | 2.000 | 15,000 |
| 202603 | SPY | 22 | 50.0% | 1.667 | 11,000 |
| 202603 | TOTAL | 81 | 49.4% | 1.626 | 38,500 |
| 202604 | QQQ | 20 | 65.0% | 3.095 | 22,000 |
| 202604 | SPXW | 20 | 65.0% | 3.095 | 22,000 |
| 202604 | SPY | 20 | 50.0% | 1.667 | 10,000 |
| 202604 | TOTAL | 60 | 60.0% | 2.500 | 54,000 |
| 202605 | QQQ | 36 | 44.4% | 1.333 | 10,000 |
| 202605 | SPXW | 21 | 52.4% | 1.833 | 12,500 |
| 202605 | SPY | 19 | 68.4% | 3.611 | 23,500 |
| 202605 | TOTAL | 76 | 52.6% | 1.852 | 46,000 |
| 202606 | QQQ | 45 | 37.8% | 1.012 | 500 |
| 202606 | SPXW | 22 | 40.9% | 1.154 | 3,000 |
| 202606 | SPY | 20 | 50.0% | 1.667 | 10,000 |
| 202606 | TOTAL | 87 | 41.4% | 1.176 | 13,500 |