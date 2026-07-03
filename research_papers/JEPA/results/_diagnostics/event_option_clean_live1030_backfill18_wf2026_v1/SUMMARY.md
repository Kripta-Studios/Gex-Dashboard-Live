# Event Monthly Volume Backfill

This result takes a primary causal OOS trade stream and adds fallback trades only when month-to-date selected count is below the deterministic pace needed to reach the monthly volume floor.

## Overall

```json
{
  "trades": 331,
  "win_rate": 0.3716012084592145,
  "profit_factor": 0.9769290981626138,
  "pnl_return": -1.437159883327439,
  "avg_return": -0.004341872759297399,
  "max_drawdown": -12.843978045133728,
  "call_rate": 0.2537764350453172,
  "days_with_trades": 104,
  "daily_win_rate": 0.375,
  "median_daily_return": -0.09999999999999998,
  "daily_max_drawdown": -12.343978045133735,
  "top5_day_return": 9.0,
  "top5_share_of_pnl": -6.262351255701911,
  "min_month_trades": 54,
  "positive_month_rate": 0.3333333333333333
}
```

- Risk capital: $5,000
- Net PnL: $-7,186

## By Ticker

```json
{
  "QQQ": {
    "trades": 110,
    "win_rate": 0.35454545454545455,
    "profit_factor": 0.9028832711007102,
    "pnl_return": -2.0582124950932097,
    "avg_return": -0.018711022682665543,
    "max_drawdown": -6.165030656899499,
    "call_rate": 0.2,
    "days_with_trades": 101,
    "daily_win_rate": 0.37623762376237624,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -6.1650306568995,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": -1.4575754481872096,
    "min_month_trades": 18,
    "positive_month_rate": 0.3333333333333333
  },
  "SPXW": {
    "trades": 111,
    "win_rate": 0.38738738738738737,
    "profit_factor": 1.0539215686274508,
    "pnl_return": 1.1000000000000003,
    "avg_return": 0.009909909909909913,
    "max_drawdown": -3.799999999999998,
    "call_rate": 0.2972972972972973,
    "days_with_trades": 104,
    "daily_win_rate": 0.40384615384615385,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.4999999999999982,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": 2.7272727272727266,
    "min_month_trades": 18,
    "positive_month_rate": 0.5
  },
  "SPY": {
    "trades": 110,
    "win_rate": 0.37272727272727274,
    "profit_factor": 0.976862445012839,
    "pnl_return": -0.4789473882342319,
    "avg_return": -0.0043540671657657445,
    "max_drawdown": -3.578947388234231,
    "call_rate": 0.2636363636363636,
    "days_with_trades": 101,
    "daily_win_rate": 0.39603960396039606,
    "median_daily_return": -0.3,
    "daily_max_drawdown": -3.3,
    "top5_day_return": 3.0,
    "top5_share_of_pnl": -6.263736004616927,
    "min_month_trades": 18,
    "positive_month_rate": 0.3333333333333333
  }
}
```

## By Source

```json
{
  "fallback_d50": {
    "trades": 276,
    "win_rate": 0.39492753623188404,
    "profit_factor": 1.077267338757811,
    "pnl_return": 3.862840116672557,
    "avg_return": 0.013995797524175931,
    "max_drawdown": -7.5439780451337315,
    "call_rate": 0.2608695652173913,
    "days_with_trades": 88,
    "daily_win_rate": 0.4090909090909091,
    "median_daily_return": -0.09999999999999998,
    "daily_max_drawdown": -7.043978045133736,
    "top5_day_return": 9.0,
    "top5_share_of_pnl": 2.329891926190459,
    "min_month_trades": 6,
    "positive_month_rate": 0.3333333333333333
  },
  "primary_d25": {
    "trades": 55,
    "win_rate": 0.2545454545454545,
    "profit_factor": 0.5691056910569106,
    "pnl_return": -5.299999999999999,
    "avg_return": -0.09636363636363635,
    "max_drawdown": -6.099999999999998,
    "call_rate": 0.21818181818181817,
    "days_with_trades": 20,
    "daily_win_rate": 0.3,
    "median_daily_return": -0.35,
    "daily_max_drawdown": -5.799999999999999,
    "top5_day_return": 3.6000000000000005,
    "top5_share_of_pnl": -0.6792452830188681,
    "min_month_trades": 0,
    "positive_month_rate": 0.0
  }
}
```

## Monthly

| Month | Trades | WR | PF | PnL Return | PnL $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 202601 | 54 | 31.5% | 0.766 | -2.600 | -13,000 |
| 202602 | 54 | 48.1% | 1.568 | 4.707 | 23,534 |
| 202603 | 54 | 51.9% | 1.795 | 6.200 | 31,000 |
| 202604 | 54 | 35.2% | 0.870 | -1.365 | -6,825 |
| 202605 | 61 | 26.2% | 0.572 | -5.779 | -28,895 |
| 202606 | 54 | 31.5% | 0.766 | -2.600 | -13,000 |

## Config

```json
{
  "primary_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_d25_combined_wf2026_v1\\combined_trades.csv",
  "fallback_trades": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_d50_fallback_wf2026_v1\\event_option_gate_trades.csv",
  "output_dir": "research_papers\\JEPA\\results\\_diagnostics\\event_option_clean_live1030_backfill18_wf2026_v1",
  "primary_name": "primary_d25",
  "fallback_name": "fallback_d50",
  "ticker": "",
  "start_month": "202601",
  "end_month": "202606",
  "exclude_months": [],
  "min_month_trades": 18,
  "auto_partial_month_target": false,
  "partial_month_observed_floor": 0,
  "backfill_only_partial_months": false,
  "max_day": 3,
  "cooldown_minutes": 30,
  "min_entry_minute": 630,
  "risk_capital": 5000.0
}
```