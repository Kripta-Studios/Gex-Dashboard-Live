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
| SPXW | True | 219,195 | 2.741 | 52.7% | -15,443 | 7.0% | 18.5% | 61.4% | 0 | 4 | 0.970 |
| SPY | True | 267,302 | 2.529 | 62.4% | -29,875 | 11.2% | 13.0% | 43.9% | 0 | 3 | 0.945 |

## Flags

- QQQ: none
- SPXW: none
- SPY: none

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202605 | $37,175 | 37.0% |
| SPXW | 202606 | $78,812 | 36.0% |
| SPY | 202603 | $72,884 | 27.3% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $17,988 / 17.9% | $27,385 / 27.2% | $46,174 / 45.9% |
| SPXW | $54,198 / 24.7% | $86,303 / 39.4% | $137,594 / 62.8% |
| SPY | $92,590 / 34.6% | $165,474 / 61.9% | $191,766 / 71.7% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 28 | 57.1% | 1.496 | 3.572 |
| QQQ | 202602 | 32 | 53.1% | 1.003 | 0.026 |
| QQQ | 202603 | 42 | 57.1% | 1.174 | 1.879 |
| QQQ | 202604 | 31 | 58.1% | 1.505 | 3.758 |
| QQQ | 202605 | 26 | 69.2% | 2.549 | 7.435 |
| QQQ | 202606 | 34 | 52.9% | 1.380 | 3.450 |
| SPXW | 202601 | 19 | 47.4% | 1.477 | 2.861 |
| SPXW | 202602 | 18 | 50.0% | 2.478 | 7.979 |
| SPXW | 202603 | 32 | 62.5% | 1.892 | 6.421 |
| SPXW | 202604 | 29 | 55.2% | 2.420 | 10.258 |
| SPXW | 202605 | 23 | 52.2% | 1.084 | 0.558 |
| SPXW | 202606 | 21 | 66.7% | 4.753 | 15.762 |
| SPY | 202601 | 30 | 56.7% | 1.627 | 4.888 |
| SPY | 202602 | 35 | 74.3% | 3.540 | 13.630 |
| SPY | 202603 | 55 | 67.3% | 2.419 | 14.577 |
| SPY | 202604 | 43 | 62.8% | 1.548 | 5.258 |
| SPY | 202605 | 53 | 50.9% | 1.183 | 2.845 |
| SPY | 202606 | 31 | 77.4% | 3.919 | 12.262 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`