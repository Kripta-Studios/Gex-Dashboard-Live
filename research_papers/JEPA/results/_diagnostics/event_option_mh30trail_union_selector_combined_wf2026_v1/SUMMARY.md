# Combined Event Option Trade Streams

This artifact combines already generated causal OOS trade streams. It does not train or select any new trade.

## Overall

```json
{
  "trades": 624,
  "win_rate": 0.4791666666666667,
  "profit_factor": 1.1035988247198538,
  "pnl_return": 19.687592597041093,
  "avg_return": 0.031550629161924824,
  "max_drawdown": -36.43799666808694,
  "call_rate": 0.3108974358974359,
  "days_with_trades": 123,
  "daily_win_rate": 0.43089430894308944,
  "median_daily_return": -0.36666674945089217,
  "daily_max_drawdown": -33.12135633580089,
  "top5_day_return": 36.811147013504225,
  "top5_share_of_pnl": 1.8697637525797177,
  "min_month_trades": 55,
  "positive_month_rate": 0.6666666666666666
}
```

- Risk capital: $5,000
- Net PnL: $98,438

## By Ticker

```json
{
  "QQQ": {
    "trades": 218,
    "win_rate": 0.518348623853211,
    "profit_factor": 1.2655000874546343,
    "pnl_return": 16.45008951318505,
    "avg_return": 0.07545912620727087,
    "max_drawdown": -14.208886819592022,
    "call_rate": 0.42660550458715596,
    "days_with_trades": 119,
    "daily_win_rate": 0.5042016806722689,
    "median_daily_return": 0.0178558082992063,
    "daily_max_drawdown": -13.883639271467388,
    "top5_day_return": 14.851850452310433,
    "top5_share_of_pnl": 0.9028431389632502,
    "min_month_trades": 19,
    "positive_month_rate": 0.6666666666666666
  },
  "SPXW": {
    "trades": 161,
    "win_rate": 0.5093167701863354,
    "profit_factor": 1.2145267788146015,
    "pnl_return": 9.858149379757815,
    "avg_return": 0.06123074148917898,
    "max_drawdown": -8.274879688756576,
    "call_rate": 0.22981366459627328,
    "days_with_trades": 120,
    "daily_win_rate": 0.48333333333333334,
    "median_daily_return": -0.0749134069667644,
    "daily_max_drawdown": -8.017736796472654,
    "top5_day_return": 15.81722654188395,
    "top5_share_of_pnl": 1.6044823356361568,
    "min_month_trades": 17,
    "positive_month_rate": 0.6666666666666666
  },
  "SPY": {
    "trades": 245,
    "win_rate": 0.42448979591836733,
    "profit_factor": 0.9193832498104688,
    "pnl_return": -6.62064629590177,
    "avg_return": -0.02702304610572151,
    "max_drawdown": -17.36574477136985,
    "call_rate": 0.2612244897959184,
    "days_with_trades": 120,
    "daily_win_rate": 0.4083333333333333,
    "median_daily_return": -0.6,
    "daily_max_drawdown": -15.75659356978333,
    "top5_day_return": 18.467563433358137,
    "top5_share_of_pnl": -2.789389828118397,
    "min_month_trades": 19,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Monthly PnL Return

| Month | Ticker | Trades | WR | PF | PnL Return | PnL $ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | QQQ | 20 | 75.0% | 4.044 | 9.133 | 45,666 |
| 202601 | SPXW | 19 | 42.1% | 0.573 | -2.654 | -13,271 |
| 202601 | SPY | 20 | 40.0% | 0.858 | -1.020 | -5,100 |
| 202601 | TOTAL | 59 | 52.5% | 1.332 | 5.459 | 27,295 |
| 202602 | QQQ | 19 | 42.1% | 1.400 | 2.575 | 12,876 |
| 202602 | SPXW | 17 | 52.9% | 1.913 | 4.383 | 21,915 |
| 202602 | SPY | 19 | 26.3% | 0.313 | -5.769 | -28,846 |
| 202602 | TOTAL | 55 | 40.0% | 1.061 | 1.189 | 5,945 |
| 202603 | QQQ | 83 | 57.8% | 1.481 | 9.884 | 49,422 |
| 202603 | SPXW | 22 | 68.2% | 2.448 | 5.320 | 26,601 |
| 202603 | SPY | 44 | 54.5% | 1.372 | 4.269 | 21,345 |
| 202603 | TOTAL | 149 | 58.4% | 1.545 | 19.474 | 97,369 |
| 202604 | QQQ | 36 | 41.7% | 0.623 | -4.745 | -23,725 |
| 202604 | SPXW | 42 | 50.0% | 1.473 | 5.707 | 28,535 |
| 202604 | SPY | 84 | 41.7% | 0.866 | -3.771 | -18,857 |
| 202604 | TOTAL | 162 | 43.8% | 0.947 | -2.809 | -14,047 |
| 202605 | QQQ | 40 | 45.0% | 0.680 | -4.230 | -21,152 |
| 202605 | SPXW | 40 | 47.5% | 0.746 | -3.205 | -16,025 |
| 202605 | SPY | 57 | 38.6% | 0.813 | -3.809 | -19,045 |
| 202605 | TOTAL | 137 | 43.1% | 0.757 | -11.244 | -56,221 |
| 202606 | QQQ | 20 | 45.0% | 1.622 | 3.833 | 19,164 |
| 202606 | SPXW | 21 | 47.6% | 1.047 | 0.307 | 1,535 |
| 202606 | SPY | 21 | 47.6% | 1.527 | 3.480 | 17,400 |
| 202606 | TOTAL | 62 | 46.8% | 1.394 | 7.620 | 38,099 |

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
    "QQQ=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_union_selector_QQQ_wf2026_v1\\trade_union_config_selector_trades.csv",
    "SPXW=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_union_selector_SPXW_wf2026_v1\\trade_union_config_selector_trades.csv",
    "SPY=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_union_selector_SPY_wf2026_v1\\trade_union_config_selector_trades.csv"
  ],
  "fold_file": [
    "QQQ=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_union_selector_QQQ_wf2026_v1\\trade_union_config_selector_folds.csv",
    "SPXW=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_union_selector_SPXW_wf2026_v1\\trade_union_config_selector_folds.csv",
    "SPY=research_papers\\JEPA\\results\\_diagnostics\\event_option_mh30trail_union_selector_SPY_wf2026_v1\\trade_union_config_selector_folds.csv"
  ],
  "start_month": "202601",
  "end_month": "202606"
}
```