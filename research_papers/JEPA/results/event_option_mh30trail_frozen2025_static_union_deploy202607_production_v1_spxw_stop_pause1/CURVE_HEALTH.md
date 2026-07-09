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
  "max_negative_streak": 6,
  "min_first_two_month_share": 0.1,
  "min_first_three_month_share": 0.2
}
```

## Summary

| Ticker | Healthy | PnL $ | Daily PF | Active-Day WR | Max DD $ | DD/PnL | Top1 Share | Top5 Share | Neg Months | Max Neg Streak | R2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | True | 211,801 | 2.233 | 57.1% | -24,966 | 11.8% | 12.9% | 40.8% | 0 | 6 | 0.968 |
| SPXW | True | 513,799 | 2.566 | 51.9% | -28,343 | 5.5% | 14.6% | 45.3% | 0 | 5 | 0.967 |
| SPY | True | 96,803 | 1.769 | 60.4% | -16,418 | 17.0% | 13.8% | 61.5% | 0 | 5 | 0.943 |

## Flags

- QQQ: none
- SPXW: none
- SPY: none

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202601 | $56,728 | 26.8% |
| SPXW | 202606 | $172,776 | 33.6% |
| SPY | 202603 | $20,253 | 20.9% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $74,145 / 35.0% | $118,753 / 56.1% | $152,213 / 71.9% |
| SPXW | $124,313 / 24.2% | $199,177 / 38.8% | $290,599 / 56.6% |
| SPY | $31,410 / 32.4% | $51,663 / 53.4% | $57,499 / 59.4% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 40 | 67.5% | 2.533 | 11.346 |
| QQQ | 202602 | 37 | 64.9% | 1.457 | 3.484 |
| QQQ | 202603 | 44 | 56.8% | 1.787 | 8.922 |
| QQQ | 202604 | 36 | 58.3% | 1.763 | 6.692 |
| QQQ | 202605 | 40 | 65.0% | 1.794 | 6.672 |
| QQQ | 202606 | 39 | 51.3% | 1.460 | 5.245 |
| SPXW | 202601 | 49 | 65.3% | 2.719 | 17.530 |
| SPXW | 202602 | 50 | 60.0% | 1.611 | 7.333 |
| SPXW | 202603 | 50 | 56.0% | 2.134 | 14.973 |
| SPXW | 202604 | 54 | 55.6% | 2.319 | 18.284 |
| SPXW | 202605 | 62 | 48.4% | 1.525 | 10.085 |
| SPXW | 202606 | 61 | 62.3% | 3.504 | 34.555 |
| SPY | 202601 | 12 | 66.7% | 2.641 | 3.937 |
| SPY | 202602 | 18 | 55.6% | 1.491 | 2.345 |
| SPY | 202603 | 22 | 63.6% | 1.844 | 4.051 |
| SPY | 202604 | 15 | 66.7% | 1.389 | 1.167 |
| SPY | 202605 | 20 | 55.0% | 1.727 | 3.928 |
| SPY | 202606 | 19 | 57.9% | 1.819 | 3.933 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`