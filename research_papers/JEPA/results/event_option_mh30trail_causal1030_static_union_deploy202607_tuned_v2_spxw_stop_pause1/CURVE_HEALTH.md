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
| SPY | True | 267,302 | 2.529 | 62.4% | -29,875 | 11.2% | 13.0% | 43.9% | 0 | 3 | 0.945 |

## Flags

- QQQ: none
- SPXW: negative_day_streak>4, first_3_month_share<0.2
- SPY: none

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202605 | $37,175 | 37.0% |
| SPXW | 202604 | $217,059 | 45.4% |
| SPY | 202603 | $72,884 | 27.3% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $17,988 / 17.9% | $27,385 / 27.2% | $46,174 / 45.9% |
| SPXW | $78,235 / 16.4% | $88,092 / 18.4% | $305,151 / 63.9% |
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
| SPXW | 202601 | 60 | 46.7% | 1.091 | 1.739 |
| SPXW | 202602 | 45 | 60.0% | 2.310 | 13.908 |
| SPXW | 202603 | 70 | 51.4% | 1.097 | 1.971 |
| SPXW | 202604 | 77 | 57.1% | 3.261 | 43.412 |
| SPXW | 202605 | 56 | 51.8% | 1.862 | 13.968 |
| SPXW | 202606 | 53 | 58.5% | 2.586 | 20.537 |
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