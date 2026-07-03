# Combined Event Option Trade Streams

This artifact combines already generated causal OOS trade streams. It does not train or select any new trade.

## Overall

```json
{
  "trades": 57,
  "win_rate": 0.2807017543859649,
  "profit_factor": 0.6504065040650406,
  "pnl_return": -4.3,
  "avg_return": -0.07543859649122807,
  "max_drawdown": -6.099999999999998,
  "call_rate": 0.22807017543859648,
  "days_with_trades": 20,
  "daily_win_rate": 0.3,
  "median_daily_return": -0.35,
  "daily_max_drawdown": -5.799999999999999,
  "top5_day_return": 4.6000000000000005,
  "top5_share_of_pnl": -1.0697674418604652,
  "min_month_trades": 0,
  "positive_month_rate": 0.0
}
```

- Risk capital: $5,000
- Net PnL: $-21,500

## By Ticker

```json
{
  "QQQ": {
    "trades": 18,
    "win_rate": 0.16666666666666666,
    "profit_factor": 0.3333333333333334,
    "pnl_return": -2.9999999999999996,
    "avg_return": -0.16666666666666663,
    "max_drawdown": -2.999999999999999,
    "call_rate": 0.1111111111111111,
    "days_with_trades": 18,
    "daily_win_rate": 0.16666666666666666,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -2.999999999999999,
    "top5_day_return": 0.8999999999999999,
    "top5_share_of_pnl": -0.3,
    "min_month_trades": 0,
    "positive_month_rate": 0.0
  },
  "SPXW": {
    "trades": 20,
    "win_rate": 0.35,
    "profit_factor": 0.8974358974358977,
    "pnl_return": -0.39999999999999986,
    "avg_return": -0.019999999999999993,
    "max_drawdown": -1.9000000000000001,
    "call_rate": 0.35,
    "days_with_trades": 20,
    "daily_win_rate": 0.35,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -1.9000000000000001,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -6.250000000000003,
    "min_month_trades": 0,
    "positive_month_rate": 0.0
  },
  "SPY": {
    "trades": 19,
    "win_rate": 0.3157894736842105,
    "profit_factor": 0.7692307692307694,
    "pnl_return": -0.8999999999999999,
    "avg_return": -0.047368421052631574,
    "max_drawdown": -2.3,
    "call_rate": 0.21052631578947367,
    "days_with_trades": 19,
    "daily_win_rate": 0.3157894736842105,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -2.3,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -2.777777777777778,
    "min_month_trades": 0,
    "positive_month_rate": 0.0
  }
}
```

## Monthly PnL Return

| Month | Ticker | Trades | WR | PF | PnL Return | PnL $ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | QQQ | 0 | nan% | nan | 0.000 | 0 |
| 202601 | SPXW | 0 | nan% | nan | 0.000 | 0 |
| 202601 | SPY | 0 | nan% | nan | 0.000 | 0 |
| 202601 | TOTAL | 0 | nan% | nan | 0.000 | 0 |
| 202602 | QQQ | 0 | nan% | nan | 0.000 | 0 |
| 202602 | SPXW | 0 | nan% | nan | 0.000 | 0 |
| 202602 | SPY | 0 | nan% | nan | 0.000 | 0 |
| 202602 | TOTAL | 0 | nan% | nan | 0.000 | 0 |
| 202603 | QQQ | 0 | nan% | nan | 0.000 | 0 |
| 202603 | SPXW | 0 | nan% | nan | 0.000 | 0 |
| 202603 | SPY | 0 | nan% | nan | 0.000 | 0 |
| 202603 | TOTAL | 0 | nan% | nan | 0.000 | 0 |
| 202604 | QQQ | 0 | nan% | nan | 0.000 | 0 |
| 202604 | SPXW | 0 | nan% | nan | 0.000 | 0 |
| 202604 | SPY | 0 | nan% | nan | 0.000 | 0 |
| 202604 | TOTAL | 0 | nan% | nan | 0.000 | 0 |
| 202605 | QQQ | 18 | 16.7% | 0.333 | -3.000 | -15,000 |
| 202605 | SPXW | 20 | 35.0% | 0.897 | -0.400 | -2,000 |
| 202605 | SPY | 19 | 31.6% | 0.769 | -0.900 | -4,500 |
| 202605 | TOTAL | 57 | 28.1% | 0.650 | -4.300 | -21,500 |
| 202606 | QQQ | 0 | nan% | nan | 0.000 | 0 |
| 202606 | SPXW | 0 | nan% | nan | 0.000 | 0 |
| 202606 | SPY | 0 | nan% | nan | 0.000 | 0 |
| 202606 | TOTAL | 0 | nan% | nan | 0.000 | 0 |

## Integrity

```json
{
  "passed": true,
  "folds_checked": 18,
  "issues": []
}
```

## Sources

```json
{
  "trade_file": [
    "SPXW_D25=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_spxw_d25_wf2026_v1\\event_option_gate_trades.csv",
    "QQQ_D25=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_qqq_d25_wf2026_v1\\event_option_gate_trades.csv",
    "SPY_D25=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_spy_d25_wf2026_v1\\event_option_gate_trades.csv"
  ],
  "fold_file": [
    "SPXW_D25=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_spxw_d25_wf2026_v1\\fold_configs.csv",
    "QQQ_D25=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_qqq_d25_wf2026_v1\\fold_configs.csv",
    "SPY_D25=research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_spy_d25_wf2026_v1\\fold_configs.csv"
  ],
  "start_month": "202601",
  "end_month": "202606"
}
```