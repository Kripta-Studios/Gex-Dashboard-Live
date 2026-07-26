# Event Option Result Verification

- Passed: True
- Result dir: `research_papers\JEPA\results\event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1_walkforward`

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
| SPXW | True | 120 | 55.83% | 1.874 | 19 | 27.478 | 25.83% | 6/6 |
| SPY | True | 209 | 54.55% | 1.476 | 26 | 26.989 | 0.00% | 6/6 |
| QQQ | True | 183 | 54.64% | 1.744 | 26 | 36.622 | 38.25% | 6/6 |

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