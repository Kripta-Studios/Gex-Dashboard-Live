# Fixed 0.70 Delta Exit Grid

Candidate labels: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\results\jepa_full_pipeline_option_policy\candidate_labels.parquet`
State rows: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\results\jepa_full_pipeline_option_value_walkforward\option_value_state_rows.parquet`
Meta-train end: `202603`
OOS start: `202604`

The grid keeps the same `base_jepa` entries and the same 0.70 delta strike selection, then changes only the option exit contract.

## Selected Config

```json
{
  "fixed_delta": 0.7,
  "hard_stop_pct": -0.6,
  "take_profit_pct": 2.5,
  "selection": "max meta-train score with PF>=1.3, WR>=45%, positive PnL"
}
```

## Meta-Train

| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_stop35_tp250 | 1995 | 58.8% | 3.097 | +773,133 | -9,193 | 136.2 | 18 | 0 |
| selected_exit | 1995 | 75.2% | 6.223 | +1,143,722 | -8,249 | 169.7 | 18 | 0 |

## Apr/May OOS

| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_stop35_tp250 | 104 | 43.3% | 1.736 | +20,776 | -4,302 | 120.4 | 16 | 0 |
| selected_exit | 104 | 56.7% | 2.031 | +27,946 | -3,697 | 160.9 | 16 | 0 |

## Top Train Grid Rows

| Rank | Stop | TP | Train WR | Train PF | Train PnL | OOS WR | OOS PF | OOS PnL | Score |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -0.60 | 2.50 | 75.2% | 6.223 | +1,143,722 | 56.7% | 2.031 | +27,946 | 1149347.689 |
| 2 | -0.60 | 3.00 | 75.2% | 6.222 | +1,143,615 | 56.7% | 2.017 | +27,569 | 1149240.492 |
| 3 | -0.60 | 2.00 | 75.2% | 6.209 | +1,140,759 | 56.7% | 2.076 | +29,168 | 1146378.746 |
| 4 | -0.60 | 4.00 | 75.2% | 6.209 | +1,140,719 | 56.7% | 2.045 | +28,313 | 1146339.173 |
| 5 | -0.60 | 10.00 | 75.2% | 6.209 | +1,140,719 | 56.7% | 1.992 | +26,881 | 1146339.173 |
| 6 | -0.60 | 1.50 | 75.2% | 6.062 | +1,108,444 | 56.7% | 2.069 | +28,989 | 1114004.970 |
| 7 | -0.50 | 2.50 | 71.7% | 5.024 | +1,071,524 | 54.8% | 2.175 | +29,317 | 1076437.579 |
| 8 | -0.50 | 3.00 | 71.7% | 5.024 | +1,071,417 | 54.8% | 2.160 | +28,940 | 1076330.379 |
| 9 | -0.50 | 10.00 | 71.7% | 5.013 | +1,068,521 | 54.8% | 2.132 | +28,252 | 1073428.961 |
| 10 | -0.50 | 4.00 | 71.7% | 5.013 | +1,068,521 | 54.8% | 2.190 | +29,684 | 1073428.961 |
| 11 | -0.50 | 2.00 | 71.7% | 5.012 | +1,068,255 | 54.8% | 2.224 | +30,539 | 1073161.961 |
| 12 | -0.50 | 1.50 | 71.7% | 4.891 | +1,035,836 | 54.8% | 2.217 | +30,359 | 1040682.813 |
| 13 | -0.60 | 1.00 | 75.4% | 5.666 | +1,019,323 | 56.7% | 1.903 | +24,478 | 1024783.267 |
| 14 | -0.45 | 2.50 | 68.8% | 4.368 | +1,005,992 | 50.0% | 1.899 | +24,762 | 1010557.575 |
| 15 | -0.45 | 3.00 | 68.8% | 4.368 | +1,005,885 | 50.0% | 1.886 | +24,385 | 1010450.370 |
| 16 | -0.45 | 2.00 | 68.8% | 4.360 | +1,003,400 | 50.0% | 1.944 | +25,984 | 1007960.603 |
| 17 | -0.45 | 10.00 | 68.8% | 4.358 | +1,002,989 | 50.0% | 1.861 | +23,697 | 1007548.814 |
| 18 | -0.45 | 4.00 | 68.8% | 4.358 | +1,002,989 | 50.0% | 1.913 | +25,129 | 1007548.814 |
| 19 | -0.45 | 1.50 | 68.9% | 4.251 | +970,842 | 50.0% | 1.937 | +25,804 | 975340.618 |
| 20 | -0.60 | 0.75 | 76.1% | 5.388 | +945,351 | 57.7% | 1.755 | +20,166 | 950809.789 |

## Interpretation

- This is not a model-fit improvement; it is an execution-contract improvement discovered on pre-OOS months and verified on Apr/May.
- The same entries and strikes are used, so trade volume is unchanged.
- Promotion requires the selected exit to beat the previous `-35%/+250%` contract OOS while keeping PF > 1.3, WR > 45%, and ticker-month volume near the target.
