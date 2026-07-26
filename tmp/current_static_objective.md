# Event Option Result Verification

- Passed: False
- Result dir: `research_papers\JEPA\results\event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1`

## Gates

```json
{
  "tickers": [
    "SPXW",
    "SPY",
    "QQQ"
  ],
  "months": [
    "202601",
    "202602",
    "202603",
    "202604",
    "202605",
    "202606"
  ],
  "min_win_rate": 0.5,
  "min_profit_factor": 1.3,
  "min_month_trades": 18,
  "strict_month_trades": true,
  "require_positive_months": true,
  "min_call_rate": 0.0,
  "max_call_rate": 1.0,
  "disallow_weak_fold_modes": true,
  "excluded_months": []
}
```

## Tickers

| Ticker | Passed | Trades | WR | PF | Min Month Trades | PnL Return | Call Rate | Positive Months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | True | 122 | 58.20% | 1.950 | 19 | 28.730 | 27.05% | 6/6 |
| SPY | False | 124 | 60.48% | 1.725 | 14 | 21.292 | 0.00% | 6/6 |
| QQQ | True | 170 | 55.88% | 1.626 | 22 | 27.516 | 72.94% | 6/6 |

## Integrity

```json
{
  "passed": true,
  "folds_checked": 18,
  "issues": []
}
```

## Backfill Audit

```json
{
  "passed": true,
  "rows_checked": 0,
  "issues": []
}
```

## Issues

- SPY failed checks: ['volume_ok']