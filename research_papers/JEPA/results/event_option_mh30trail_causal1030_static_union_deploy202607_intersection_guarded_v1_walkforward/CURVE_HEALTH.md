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
| SPXW | True | 137,392 | 1.874 | 55.8% | -19,114 | 13.9% | 18.2% | 64.4% | 0 | 4 | 0.915 |
| SPY | True | 134,944 | 1.859 | 60.0% | -17,879 | 13.2% | 16.5% | 60.4% | 0 | 3 | 0.924 |

## Flags

- QQQ: none
- SPXW: none
- SPY: none

## Monthly Concentration

| Ticker | Largest Month | Largest Month PnL | Share Of Final PnL |
| --- | --- | ---: | ---: |
| QQQ | 202606 | $49,835 | 27.2% |
| SPXW | 202604 | $59,749 | 43.5% |
| SPY | 202602 | $41,187 | 30.5% |

## Prefix Health

| Ticker | First 2 Months | First 3 Months | First 4 Months |
| --- | ---: | ---: | ---: |
| QQQ | $44,454 / 24.3% | $70,168 / 38.3% | $85,703 / 46.8% |
| SPXW | $47,769 / 34.8% | $54,037 / 39.3% | $113,786 / 82.8% |
| SPY | $65,083 / 48.2% | $95,684 / 70.9% | $109,739 / 81.3% |

## Monthly

| Ticker | Month | Trades | WR | PF | PnL Return |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 30 | 53.3% | 1.422 | 3.544 |
| QQQ | 202602 | 31 | 61.3% | 1.808 | 5.346 |
| QQQ | 202603 | 33 | 51.5% | 1.536 | 5.143 |
| QQQ | 202604 | 26 | 46.2% | 1.370 | 3.107 |
| QQQ | 202605 | 30 | 60.0% | 2.321 | 9.514 |
| QQQ | 202606 | 33 | 54.5% | 2.107 | 9.967 |
| SPXW | 202601 | 20 | 60.0% | 2.132 | 5.433 |
| SPXW | 202602 | 19 | 52.6% | 1.763 | 4.120 |
| SPXW | 202603 | 22 | 45.5% | 1.184 | 1.254 |
| SPXW | 202604 | 20 | 60.0% | 3.490 | 11.950 |
| SPXW | 202605 | 20 | 60.0% | 1.445 | 2.135 |
| SPXW | 202606 | 19 | 57.9% | 1.539 | 2.586 |
| SPY | 202601 | 46 | 56.5% | 1.398 | 4.779 |
| SPY | 202602 | 46 | 60.9% | 1.783 | 8.237 |
| SPY | 202603 | 30 | 60.0% | 1.850 | 6.120 |
| SPY | 202604 | 26 | 46.2% | 1.335 | 2.811 |
| SPY | 202605 | 34 | 50.0% | 1.253 | 2.586 |
| SPY | 202606 | 27 | 48.1% | 1.292 | 2.455 |

## Artifacts

- `curve_health/ticker_cumulative_net_pnl.png`
- `curve_health/ticker_daily_pnl.png`
- `curve_health/ticker_daily_curve.csv`
- `curve_health/curve_health.json`