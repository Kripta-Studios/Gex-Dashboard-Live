# OptionValueJEPA Policy Switcher

Walk-forward dir: `.\research_papers\JEPA\results\jepa_full_pipeline_option_value_walkforward`
Meta-train months: `202308` to `202603`
OOS months: `202604` to `202605`

The switcher chooses one full policy per ticker-month using only prior months. It never selects a strike using the current month outcome.

## Selected Config

```json
{
  "scope": "global",
  "default_policy": "fixed_delta_0.70_hard",
  "lookback_months": 12,
  "min_history_trades": 30,
  "min_history_pf": 1.0,
  "min_history_wr": 0.45,
  "min_history_pnl": 0.0,
  "dd_penalty": 0.0,
  "pf_weight": 2500.0,
  "wr_weight": 2500.0,
  "switch_margin": 1500.0
}
```

## Meta-Train Comparison

| Policy | Trades | WR | PF | PnL | Max DD | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 1995 | 58.9% | 3.098 | +773,131 | -9,193 | 18 | 0 |
| policy_switcher | 1995 | 58.9% | 3.098 | +773,131 | -9,193 | 18 | 0 |
| oracle_best_delta_hard | 1995 | 59.0% | 7.552 | +1,487,642 | -3,925 | 18 | 0 |

## Apr/May OOS Comparison

| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 105 | 42.9% | 1.725 | +20,719 | -4,343 | 0.702 | 120.3 | 17 | 0 |
| policy_switcher | 105 | 42.9% | 1.725 | +20,719 | -4,343 | 0.702 | 120.3 | 17 | 0 |
| oracle_best_delta_hard | 105 | 42.9% | 4.092 | +54,238 | -2,950 | 0.513 | 103.0 | 17 | 0 |
| oracle_best_delta_oracle_exit | 105 | 87.6% | 140.828 | +167,995 | -350 | 0.464 | 89.2 | 17 | 0 |

## OOS Decisions

| Month | Ticker | Selected Policy | Reason | Past Months |
| --- | --- | --- | --- | --- |
| 202604 | ALL | fixed_delta_0.70_hard | selected | 202504,202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603 |
| 202605 | ALL | fixed_delta_0.70_hard | selected | 202505,202506,202507,202508,202509,202510,202511,202512,202601,202602,202603,202604 |

## Top Meta-Train Configs

| Rank | Scope | Lookback | MinPF | MinWR | DD Penalty | Margin | PF | WR | PnL | Score |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | global | 12 | 1.00 | 0.45 | 0.00 | 1500 | 3.098 | 58.9% | +773,131 | 777430.263 |
| 2 | global | 12 | 1.00 | 0.50 | 0.00 | 1500 | 3.098 | 58.9% | +773,131 | 777430.263 |
| 3 | global | 12 | 1.20 | 0.45 | 0.00 | 1500 | 3.098 | 58.9% | +773,131 | 777430.263 |
| 4 | global | 12 | 1.20 | 0.50 | 0.00 | 1500 | 3.098 | 58.9% | +773,131 | 777430.263 |
| 5 | global | 12 | 1.30 | 0.45 | 0.00 | 1500 | 3.098 | 58.9% | +773,131 | 777430.263 |
| 6 | global | 12 | 1.30 | 0.50 | 0.00 | 1500 | 3.098 | 58.9% | +773,131 | 777430.263 |
| 7 | global | 12 | 1.00 | 0.45 | 0.10 | 1500 | 3.098 | 58.9% | +773,131 | 776510.949 |
| 8 | global | 12 | 1.00 | 0.50 | 0.10 | 1500 | 3.098 | 58.9% | +773,131 | 776510.949 |
| 9 | global | 12 | 1.20 | 0.45 | 0.10 | 1500 | 3.098 | 58.9% | +773,131 | 776510.949 |
| 10 | global | 12 | 1.20 | 0.50 | 0.10 | 1500 | 3.098 | 58.9% | +773,131 | 776510.949 |
| 11 | global | 12 | 1.30 | 0.45 | 0.10 | 1500 | 3.098 | 58.9% | +773,131 | 776510.949 |
| 12 | global | 12 | 1.30 | 0.50 | 0.10 | 1500 | 3.098 | 58.9% | +773,131 | 776510.949 |
| 13 | ticker | 9 | 1.00 | 0.45 | 0.00 | 1500 | 2.998 | 57.0% | +771,431 | 775602.383 |
| 14 | ticker | 9 | 1.20 | 0.45 | 0.00 | 1500 | 2.998 | 57.0% | +771,431 | 775602.383 |
| 15 | ticker | 9 | 1.30 | 0.45 | 0.00 | 1500 | 2.998 | 57.0% | +771,431 | 775602.383 |

## Interpretation

- Promotion requires Apr/May OOS to beat fixed 0.70 on PF and PnL while maintaining the requested WR/volume gates.
- If the selected switcher only improves meta-train but not Apr/May, it remains research-only.
