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
| QQQ | True | 61,000 | 1.739 | 56.0% | -9,500 | 15.6% | 8.2% | 38.5% | 0 | 3 | 0.968 |
| SPXW | True | 68,500 | 1.787 | 53.3% | -7,500 | 10.9% | 3.6% | 18.2% | 0 | 3 | 0.973 |
| SPY | True | 65,000 | 1.788 | 53.4% | -8,000 | 12.3% | 3.8% | 19.2% | 0 | 3 | 0.945 |

## Flags

- QQQ: none
- SPXW: none
- SPY: none

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202604 | $22,000 | 36.1% |
| SPXW | 202604 | $22,000 | 32.1% |
| SPY | 202605 | $23,500 | 36.2% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $16,000 / 26.2% | $28,500 / 46.7% | $50,500 / 82.8% |
| SPXW | $16,000 / 23.4% | $31,000 / 45.3% | $53,000 / 77.4% |
| SPY | $10,500 / 16.2% | $21,500 / 33.1% | $31,500 / 48.5% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 21 | 42.9% | 1.250 | 0.900 |
| QQQ | 202602 | 19 | 52.6% | 1.852 | 2.300 |
| QQQ | 202603 | 37 | 45.9% | 1.417 | 2.500 |
| QQQ | 202604 | 20 | 65.0% | 3.095 | 4.400 |
| QQQ | 202605 | 36 | 44.4% | 1.333 | 2.000 |
| QQQ | 202606 | 45 | 37.8% | 1.012 | 0.100 |
| SPXW | 202601 | 21 | 42.9% | 1.250 | 0.900 |
| SPXW | 202602 | 19 | 52.6% | 1.852 | 2.300 |
| SPXW | 202603 | 22 | 54.5% | 2.000 | 3.000 |
| SPXW | 202604 | 20 | 65.0% | 3.095 | 4.400 |
| SPXW | 202605 | 21 | 52.4% | 1.833 | 2.500 |
| SPXW | 202606 | 22 | 40.9% | 1.154 | 0.600 |
| SPY | 202601 | 21 | 38.1% | 1.026 | 0.100 |
| SPY | 202602 | 20 | 50.0% | 1.667 | 2.000 |
| SPY | 202603 | 22 | 50.0% | 1.667 | 2.200 |
| SPY | 202604 | 20 | 50.0% | 1.667 | 2.000 |
| SPY | 202605 | 19 | 68.4% | 3.611 | 4.700 |
| SPY | 202606 | 20 | 50.0% | 1.667 | 2.000 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`