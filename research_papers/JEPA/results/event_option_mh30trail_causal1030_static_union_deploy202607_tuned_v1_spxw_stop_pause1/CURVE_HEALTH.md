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
| QQQ | True | 100,600 | 1.577 | 51.4% | -23,607 | 23.5% | 27.1% | 72.6% | 0 | 3 | 0.660 |
| SPXW | False | 477,678 | 2.437 | 52.7% | -37,221 | 7.8% | 14.9% | 61.9% | 0 | 5 | 0.904 |
| SPY | False | 118,426 | 1.665 | 52.3% | -29,693 | 25.1% | 29.4% | 67.8% | 1 | 5 | 0.647 |

## Flags

- QQQ: none
- SPXW: negative_day_streak>4, first_3_month_share<0.2
- SPY: negative_months, negative_day_streak>4

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202605 | $37,175 | 37.0% |
| SPXW | 202604 | $217,059 | 45.4% |
| SPY | 202602 | $71,637 | 60.5% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $17,988 / 17.9% | $27,385 / 27.2% | $46,174 / 45.9% |
| SPXW | $78,235 / 16.4% | $88,092 / 18.4% | $305,151 / 63.9% |
| SPY | $89,734 / 75.8% | $100,501 / 84.9% | $107,691 / 90.9% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 28 | 57.1% | 1.496 | 3.572 |
| QQQ | 202602 | 32 | 53.1% | 1.003 | 0.026 |
| QQQ | 202603 | 42 | 57.1% | 1.174 | 1.879 |
| QQQ | 202604 | 31 | 58.1% | 1.505 | 3.758 |
| QQQ | 202605 | 26 | 69.2% | 2.549 | 7.435 |
| QQQ | 202606 | 34 | 52.9% | 1.380 | 3.450 |
| SPXW | 202601 | 60 | 46.7% | 1.091 | 1.739 |
| SPXW | 202602 | 45 | 60.0% | 2.310 | 13.908 |
| SPXW | 202603 | 70 | 51.4% | 1.097 | 1.971 |
| SPXW | 202604 | 77 | 57.1% | 3.261 | 43.412 |
| SPXW | 202605 | 56 | 51.8% | 1.862 | 13.968 |
| SPXW | 202606 | 53 | 58.5% | 2.586 | 20.537 |
| SPY | 202601 | 29 | 55.2% | 1.464 | 3.619 |
| SPY | 202602 | 31 | 74.2% | 4.007 | 14.327 |
| SPY | 202603 | 43 | 53.5% | 1.185 | 2.153 |
| SPY | 202604 | 34 | 55.9% | 1.160 | 1.438 |
| SPY | 202605 | 40 | 47.5% | 0.674 | -3.858 |
| SPY | 202606 | 30 | 60.0% | 1.871 | 6.005 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`