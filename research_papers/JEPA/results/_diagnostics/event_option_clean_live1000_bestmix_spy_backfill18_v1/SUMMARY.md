# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 158,
  "win_rate": 0.4240506329113924,
  "profit_factor": 1.2271062271062272,
  "pnl_return": 6.2,
  "avg_return": 0.039240506329113925,
  "max_drawdown": -3.6999999999999997,
  "call_rate": 0.3860759493670886,
  "days_with_trades": 111,
  "daily_win_rate": 0.5225225225225225,
  "median_daily_return": 0.2,
  "daily_max_drawdown": -3.6999999999999997,
  "top5_day_return": 5.0,
  "top5_share_of_pnl": 0.8064516129032258,
  "min_month_trades": 18,
  "positive_month_rate": 0.8333333333333334
}
```

- Risk capital: $5,000
- Net PnL: $31,000

## By Ticker

```json
{
  "SPY": {
    "trades": 158,
    "win_rate": 0.4240506329113924,
    "profit_factor": 1.2271062271062272,
    "pnl_return": 6.2,
    "avg_return": 0.039240506329113925,
    "max_drawdown": -3.6999999999999997,
    "call_rate": 0.3860759493670886,
    "days_with_trades": 111,
    "daily_win_rate": 0.5225225225225225,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -3.6999999999999997,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 0.8064516129032258,
    "min_month_trades": 18,
    "positive_month_rate": 0.8333333333333334
  }
}
```

## By Source

```json
{
  "spy_d15_return": {
    "trades": 126,
    "win_rate": 0.46825396825396826,
    "profit_factor": 1.4676616915422884,
    "pnl_return": 9.399999999999999,
    "avg_return": 0.07460317460317459,
    "max_drawdown": -2.099999999999998,
    "call_rate": 0.4603174603174603,
    "days_with_trades": 88,
    "daily_win_rate": 0.5795454545454546,
    "median_daily_return": 0.2,
    "daily_max_drawdown": -2.0999999999999988,
    "top5_day_return": 5.0,
    "top5_share_of_pnl": 0.5319148936170214,
    "min_month_trades": 0,
    "positive_month_rate": 0.8333333333333334
  },
  "spy_d50_win": {
    "trades": 32,
    "win_rate": 0.25,
    "profit_factor": 0.5555555555555556,
    "pnl_return": -3.1999999999999993,
    "avg_return": -0.09999999999999998,
    "max_drawdown": -4.799999999999999,
    "call_rate": 0.09375,
    "days_with_trades": 31,
    "daily_win_rate": 0.25806451612903225,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -4.799999999999999,
    "top5_day_return": 2.5,
    "top5_share_of_pnl": -0.7812500000000002,
    "min_month_trades": 0,
    "positive_month_rate": 0.16666666666666666
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 20 | 40.0% | 1.111 | 0.400 | 2,000 |
| 202602 | 18 | 16.7% | 0.333 | -3.000 | -15,000 |
| 202603 | 40 | 40.0% | 1.111 | 0.800 | 4,000 |
| 202604 | 21 | 47.6% | 1.515 | 1.700 | 8,500 |
| 202605 | 39 | 43.6% | 1.288 | 1.900 | 9,500 |
| 202606 | 20 | 65.0% | 3.095 | 4.400 | 22,000 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d15_return_wf2026_v1\\event_option_gate_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_nopool_d50_win_wf2026_v1\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1000_bestmix_spy_backfill18_v1",
  "primary_name": "spy_d15_return",
  "fallback_name": "spy_d50_win",
  "ticker": "SPY",
  "start_month": "202601",
  "end_month": "202606",
  "exclude_months": [],
  "min_month_trades": 18,
  "auto_partial_month_target": false,
  "partial_month_observed_floor": 0,
  "backfill_only_partial_months": false,
  "max_day": 3,
  "cooldown_minutes": 30,
  "min_entry_minute": 600,
  "risk_capital": 5000.0
}
```