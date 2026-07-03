# Event Option Result Verification

- Passed: True
- Result dir: `research_papers\JEPA\results\event_option_dense15_backfill19_spy_no_scorethr_wf2026_fullmayjun_production_v1`

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
  "min_win_rate": 0.45,
  "min_profit_factor": 1.3,
  "min_month_trades": 18,
  "strict_month_trades": true,
  "require_positive_months": true,
  "min_call_rate": 0.2,
  "max_call_rate": 0.8,
  "disallow_weak_fold_modes": false,
  "excluded_months": []
}
```

## Tickers

| Ticker | Passed | Trades | WR | PF | Min Month Trades | PnL Return | Call Rate | Positive Months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | True | 125 | 51.20% | 1.749 | 19 | 13.700 | 29.60% | 6/6 |
| SPY | True | 122 | 50.82% | 1.722 | 19 | 13.000 | 44.26% | 6/6 |
| QQQ | True | 178 | 46.07% | 1.424 | 19 | 12.200 | 28.65% | 6/6 |

## Integrity

```json
{
  "passed": true,
  "folds_checked": 36,
  "issues": []
}
```

## Backfill Audit

```json
{
  "passed": true,
  "rows_checked": 19,
  "issues": []
}
```