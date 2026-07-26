# Event Option Curve Health

This report audits daily net-PnL curve quality. It does not train or select trades.

## Gates

```json
{
  "months": [
    "202601",
    "202602",
    "202603",
    "202604",
    "202605",
    "202606"
  ],
  "excluded_months": [],
  "risk_capital": 5000.0,
  "max_top1_share": 0.45,
  "max_top5_share": 0.8,
  "max_drawdown_to_pnl": 0.45,
  "max_month_pnl_share": 0.65,
  "max_negative_streak": 4,
  "min_first_two_month_share": 0.1,
  "min_first_three_month_share": 0.2
}
```

## Summary

| Ticker | Healthy | PnL $ | Daily PF | Active-Day WR | Max DD $ | DD/PnL | Top1 Share | Top5 Share | Neg Months | Max Neg Streak | R2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | True | 137,578 | 1.969 | 55.3% | -16,021 | 11.6% | 23.4% | 58.2% | 0 | 4 | 0.923 |
| SPXW | False | 214,914 | 2.327 | 44.9% | -16,777 | 7.8% | 15.4% | 58.4% | 0 | 3 | 0.924 |
| SPY | False | 97,615 | 1.634 | 54.2% | -26,899 | 27.6% | 25.7% | 89.3% | 0 | 3 | 0.913 |

## Flags

- QQQ: none
- SPXW: first_2_month_share<0.1
- SPY: top5_share>0.8

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202606 | $50,349 | 36.6% |
| SPXW | 202604 | $84,229 | 39.2% |
| SPY | 202603 | $34,619 | 35.5% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $39,587 / 28.8% | $58,912 / 42.8% | $70,649 / 51.4% |
| SPXW | $17,429 / 8.1% | $43,848 / 20.4% | $128,077 / 59.6% |
| SPY | $26,411 / 27.1% | $61,030 / 62.5% | $63,865 / 65.4% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 22 | 59.1% | 2.224 | 6.079 |
| QQQ | 202602 | 28 | 53.6% | 1.255 | 1.838 |
| QQQ | 202603 | 40 | 52.5% | 1.339 | 3.865 |
| QQQ | 202604 | 23 | 52.2% | 1.356 | 2.347 |
| QQQ | 202605 | 27 | 55.6% | 1.461 | 3.316 |
| QQQ | 202606 | 30 | 63.3% | 2.526 | 10.070 |
| SPXW | 202601 | 24 | 41.7% | 1.038 | 0.317 |
| SPXW | 202602 | 19 | 52.6% | 1.587 | 3.169 |
| SPXW | 202603 | 31 | 51.6% | 1.587 | 5.284 |
| SPXW | 202604 | 32 | 59.4% | 3.160 | 16.846 |
| SPXW | 202605 | 20 | 55.0% | 2.684 | 9.096 |
| SPXW | 202606 | 21 | 47.6% | 2.253 | 8.272 |
| SPY | 202601 | 17 | 58.8% | 2.102 | 4.630 |
| SPY | 202602 | 13 | 61.5% | 1.217 | 0.652 |
| SPY | 202603 | 31 | 61.3% | 2.006 | 6.924 |
| SPY | 202604 | 27 | 33.3% | 1.053 | 0.567 |
| SPY | 202605 | 31 | 51.6% | 1.150 | 1.346 |
| SPY | 202606 | 25 | 72.0% | 2.287 | 5.404 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`