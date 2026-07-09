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
| SPXW | True | 143,651 | 1.950 | 58.2% | -18,930 | 13.2% | 17.4% | 60.9% | 0 | 4 | 0.942 |
| SPY | True | 106,458 | 2.166 | 58.1% | -13,691 | 12.9% | 21.0% | 65.6% | 0 | 2 | 0.929 |

## Flags

- QQQ: none
- SPXW: none
- SPY: none

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202606 | $50,349 | 36.6% |
| SPXW | 202604 | $47,040 | 32.7% |
| SPY | 202603 | $49,767 | 46.7% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $39,587 / 28.8% | $58,912 / 42.8% | $70,649 / 51.4% |
| SPXW | $45,344 / 31.6% | $64,951 / 45.2% | $111,991 / 78.0% |
| SPY | $28,900 / 27.1% | $78,667 / 73.9% | $85,011 / 79.9% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 22 | 59.1% | 2.224 | 6.079 |
| QQQ | 202602 | 28 | 53.6% | 1.255 | 1.838 |
| QQQ | 202603 | 40 | 52.5% | 1.339 | 3.865 |
| QQQ | 202604 | 23 | 52.2% | 1.356 | 2.347 |
| QQQ | 202605 | 27 | 55.6% | 1.461 | 3.316 |
| QQQ | 202606 | 30 | 63.3% | 2.526 | 10.070 |
| SPXW | 202601 | 20 | 60.0% | 1.741 | 3.555 |
| SPXW | 202602 | 19 | 63.2% | 2.313 | 5.514 |
| SPXW | 202603 | 22 | 59.1% | 1.780 | 3.921 |
| SPXW | 202604 | 21 | 57.1% | 2.742 | 9.408 |
| SPXW | 202605 | 20 | 55.0% | 1.343 | 1.852 |
| SPXW | 202606 | 20 | 55.0% | 1.830 | 4.480 |
| SPY | 202601 | 16 | 56.2% | 1.656 | 2.755 |
| SPY | 202602 | 14 | 64.3% | 2.021 | 3.025 |
| SPY | 202603 | 33 | 75.8% | 3.074 | 9.953 |
| SPY | 202604 | 17 | 47.1% | 1.235 | 1.269 |
| SPY | 202605 | 21 | 52.4% | 1.326 | 1.953 |
| SPY | 202606 | 23 | 56.5% | 1.389 | 2.336 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`