# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 119,
  "win_rate": 0.3865546218487395,
  "profit_factor": 1.033521040898786,
  "pnl_return": 0.7341107956834132,
  "avg_return": 0.006168998283053892,
  "max_drawdown": -4.6,
  "call_rate": 0.31932773109243695,
  "days_with_trades": 109,
  "daily_win_rate": 0.41284403669724773,
  "median_daily_return": -0.3,
  "daily_max_drawdown": -4.6,
  "top5_day_return": 3.0,
  "top5_share_of_pnl": 4.086576600752996,
  "min_month_trades": 18,
  "positive_month_rate": 0.5
}
```

- Risk capital: $5,000
- Net PnL: $3,671

## By Ticker

```json
{
  "QQQ": {
    "trades": 119,
    "win_rate": 0.3865546218487395,
    "profit_factor": 1.033521040898786,
    "pnl_return": 0.7341107956834132,
    "avg_return": 0.006168998283053892,
    "max_drawdown": -4.6,
    "call_rate": 0.31932773109243695,
    "days_with_trades": 109,
    "daily_win_rate": 0.41284403669724773,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -4.6,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": 4.086576600752996,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  }
}
```

## By Source

```json
{
  "clean_d25": {
    "trades": 59,
    "win_rate": 0.4406779661016949,
    "profit_factor": 1.3131313131313131,
    "pnl_return": 3.0999999999999996,
    "avg_return": 0.05254237288135593,
    "max_drawdown": -3.399999999999997,
    "call_rate": 0.4406779661016949,
    "days_with_trades": 59,
    "daily_win_rate": 0.4406779661016949,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.399999999999997,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": 0.8064516129032259,
    "min_month_trades": 0,
    "positive_month_rate": 0.3333333333333333
  },
  "clean_d50": {
    "trades": 60,
    "win_rate": 0.3333333333333333,
    "profit_factor": 0.8028425663069512,
    "pnl_return": -2.365889204316585,
    "avg_return": -0.03943148673860975,
    "max_drawdown": -4.5658892043165835,
    "call_rate": 0.2,
    "days_with_trades": 53,
    "daily_win_rate": 0.3584905660377358,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -4.5658892043165835,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": -1.2680221857077982,
    "min_month_trades": 1,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 22 | 59.1% | 2.407 | 3.800 | 19,000 |
| 202602 | 18 | 16.7% | 0.333 | -3.000 | -15,000 |
| 202603 | 23 | 47.8% | 1.528 | 1.900 | 9,500 |
| 202604 | 18 | 50.0% | 1.531 | 1.434 | 7,171 |
| 202605 | 20 | 20.0% | 0.417 | -2.800 | -14,000 |
| 202606 | 18 | 33.3% | 0.833 | -0.600 | -3,000 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_qqq_d25_wf2026_v1\\event_option_gate_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_d50_fallback_wf2026_v1\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live_qqq_backfill18_v1",
  "primary_name": "clean_d25",
  "fallback_name": "clean_d50",
  "ticker": "QQQ",
  "start_month": "202601",
  "end_month": "202606",
  "exclude_months": [],
  "min_month_trades": 18,
  "auto_partial_month_target": false,
  "partial_month_observed_floor": 0,
  "backfill_only_partial_months": false,
  "max_day": 3,
  "cooldown_minutes": 30,
  "min_entry_minute": 0,
  "risk_capital": 5000.0
}
```