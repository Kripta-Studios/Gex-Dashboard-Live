# Event Option Causal 10:30 Tuned Static Union

## Overall

```json
{
  "trades": 761,
  "win_rate": 0.557161629434954,
  "profit_factor": 1.7015157762513569,
  "pnl_return": 139.34081880123722,
  "avg_return": 0.1831022586087217,
  "max_drawdown": -12.165975681009442,
  "call_rate": 0.47174770039421815,
  "days_with_trades": 120,
  "daily_win_rate": 0.5916666666666667,
  "median_daily_return": 0.7586718212959704,
  "daily_max_drawdown": -10.96597568100939,
  "top5_day_return": 67.5238340334032,
  "top5_share_of_pnl": 0.4845947843160202,
  "min_month_trades": 108,
  "positive_month_rate": 1.0
}
```

## By Ticker

```json
{
  "QQQ": {
    "trades": 193,
    "win_rate": 0.5751295336787565,
    "profit_factor": 1.4178934590358365,
    "pnl_return": 20.119926203175968,
    "avg_return": 0.10424832229624854,
    "max_drawdown": -4.882806747587935,
    "call_rate": 0.8911917098445595,
    "days_with_trades": 105,
    "daily_win_rate": 0.5142857142857142,
    "median_daily_return": 0.0993669873723414,
    "daily_max_drawdown": -4.7214775479492825,
    "top5_day_return": 14.60558655446276,
    "top5_share_of_pnl": 0.7259264475909082,
    "min_month_trades": 26,
    "positive_month_rate": 1.0
  },
  "SPXW": {
    "trades": 361,
    "win_rate": 0.5401662049861495,
    "profit_factor": 1.969263033428641,
    "pnl_return": 95.53562968096843,
    "avg_return": 0.2646416334652865,
    "max_drawdown": -7.444139199683249,
    "call_rate": 0.2853185595567867,
    "days_with_trades": 110,
    "daily_win_rate": 0.5272727272727272,
    "median_daily_return": 0.18044031657705334,
    "daily_max_drawdown": -7.444139199683349,
    "top5_day_return": 59.14058871461719,
    "top5_share_of_pnl": 0.6190422244780424,
    "min_month_trades": 45,
    "positive_month_rate": 1.0
  },
  "SPY": {
    "trades": 207,
    "win_rate": 0.5700483091787439,
    "profit_factor": 1.4562147859217562,
    "pnl_return": 23.685262917092835,
    "avg_return": 0.11442155998595573,
    "max_drawdown": -5.93850362994413,
    "call_rate": 0.4057971014492754,
    "days_with_trades": 107,
    "daily_win_rate": 0.5233644859813084,
    "median_daily_return": 0.05869561007758839,
    "daily_max_drawdown": -5.938503629944108,
    "top5_day_return": 16.060564126978054,
    "top5_share_of_pnl": 0.6780825774742699,
    "min_month_trades": 29,
    "positive_month_rate": 0.8333333333333334
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL R | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 117 | 51.28% | 1.261 | 8.930 | 44,652 |
| 202602 | 108 | 62.04% | 2.168 | 28.261 | 141,305 |
| 202603 | 155 | 53.55% | 1.140 | 6.004 | 30,020 |
| 202604 | 142 | 57.04% | 2.364 | 48.608 | 243,039 |
| 202605 | 122 | 54.10% | 1.534 | 17.545 | 87,727 |
| 202606 | 117 | 57.26% | 2.037 | 29.992 | 149,960 |

## Verification Issues

```json
[
  "SPY.positive_month_rate 0.8333333333333334 < 1.0"
]
```