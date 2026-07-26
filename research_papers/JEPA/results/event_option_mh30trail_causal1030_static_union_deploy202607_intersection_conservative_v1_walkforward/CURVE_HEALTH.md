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
| QQQ | True | 183,109 | 2.170 | 51.9% | -18,907 | 10.3% | 17.6% | 60.0% | 0 | 4 | 0.939 |
| SPXW | True | 187,906 | 2.069 | 46.1% | -17,991 | 9.6% | 17.6% | 61.2% | 0 | 4 | 0.923 |
| SPY | False | 117,070 | 1.526 | 56.0% | -31,054 | 26.5% | 24.4% | 89.2% | 0 | 3 | 0.788 |

## Flags

- QQQ: none
- SPXW: none
- SPY: top5_share>0.8

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202606 | $49,835 | 27.2% |
| SPXW | 202604 | $63,945 | 34.0% |
| SPY | 202606 | $46,453 | 39.7% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $44,454 / 24.3% | $70,168 / 38.3% | $85,703 / 46.8% |
| SPXW | $45,941 / 24.4% | $55,569 / 29.6% | $119,514 / 63.6% |
| SPY | $47,243 / 40.4% | $55,326 / 47.3% | $59,626 / 50.9% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 30 | 53.3% | 1.422 | 3.544 |
| QQQ | 202602 | 31 | 61.3% | 1.808 | 5.346 |
| QQQ | 202603 | 33 | 51.5% | 1.536 | 5.143 |
| QQQ | 202604 | 26 | 46.2% | 1.370 | 3.107 |
| QQQ | 202605 | 30 | 60.0% | 2.321 | 9.514 |
| QQQ | 202606 | 33 | 54.5% | 2.107 | 9.967 |
| SPXW | 202601 | 31 | 48.4% | 1.333 | 3.198 |
| SPXW | 202602 | 27 | 59.3% | 1.908 | 5.990 |
| SPXW | 202603 | 33 | 45.5% | 1.178 | 1.926 |
| SPXW | 202604 | 29 | 58.6% | 2.776 | 12.789 |
| SPXW | 202605 | 21 | 52.4% | 2.717 | 10.299 |
| SPXW | 202606 | 20 | 65.0% | 1.805 | 3.379 |
| SPY | 202601 | 51 | 56.9% | 1.672 | 8.872 |
| SPY | 202602 | 46 | 47.8% | 1.041 | 0.577 |
| SPY | 202603 | 20 | 55.0% | 1.299 | 1.617 |
| SPY | 202604 | 29 | 41.4% | 1.084 | 0.860 |
| SPY | 202605 | 33 | 54.5% | 1.244 | 2.198 |
| SPY | 202606 | 24 | 70.8% | 3.212 | 9.291 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`