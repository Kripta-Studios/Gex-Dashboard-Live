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
| baseline_stop35_tp250 | 1995 | 58.9% | 3.098 | +773,131 | -9,193 | 136.3 | 18 | 0 |
| selected_exit | 1995 | 75.2% | 6.224 | +1,143,494 | -8,249 | 169.7 | 18 | 0 |

## Apr/May OOS

| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_stop35_tp250 | 105 | 42.9% | 1.725 | +20,719 | -4,343 | 120.3 | 17 | 0 |
| selected_exit | 105 | 56.2% | 2.033 | +28,115 | -3,982 | 161.0 | 17 | 0 |

## Top Train Grid Rows

| Rank | Stop | TP | Train WR | Train PF | Train PnL | OOS WR | OOS PF | OOS PnL | Score |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -0.60 | 2.50 | 75.2% | 6.224 | +1,143,494 | 56.2% | 2.033 | +28,115 | 1149121.258 |
| 2 | -0.60 | 3.00 | 75.2% | 6.224 | +1,143,387 | 56.2% | 2.019 | +27,738 | 1149014.061 |
| 3 | -0.60 | 10.00 | 75.2% | 6.210 | +1,140,491 | 56.2% | 1.994 | +27,050 | 1146112.741 |
| 4 | -0.60 | 4.00 | 75.2% | 6.210 | +1,140,491 | 56.2% | 2.047 | +28,482 | 1146112.741 |
| 5 | -0.60 | 2.00 | 75.2% | 6.201 | +1,138,331 | 56.2% | 2.159 | +31,537 | 1143948.264 |
| 6 | -0.60 | 1.50 | 75.3% | 6.054 | +1,106,121 | 56.2% | 2.149 | +31,253 | 1111679.573 |
| 7 | -0.50 | 2.50 | 71.7% | 5.025 | +1,071,296 | 54.3% | 2.177 | +29,486 | 1076177.303 |
| 8 | -0.50 | 3.00 | 71.7% | 5.025 | +1,071,189 | 54.3% | 2.162 | +29,109 | 1076070.103 |
| 9 | -0.50 | 10.00 | 71.7% | 5.014 | +1,068,293 | 54.3% | 2.134 | +28,421 | 1073168.683 |
| 10 | -0.50 | 4.00 | 71.7% | 5.014 | +1,068,293 | 54.3% | 2.192 | +29,853 | 1073168.683 |
| 11 | -0.50 | 2.00 | 71.7% | 5.005 | +1,065,827 | 54.3% | 2.314 | +32,908 | 1070697.558 |
| 12 | -0.50 | 1.50 | 71.8% | 4.883 | +1,033,513 | 54.3% | 2.302 | +32,623 | 1038323.493 |
| 13 | -0.60 | 1.00 | 75.4% | 5.662 | +1,017,830 | 56.2% | 1.947 | +25,769 | 1023289.220 |
| 14 | -0.45 | 2.50 | 68.9% | 4.369 | +1,005,764 | 49.5% | 1.902 | +24,931 | 1010302.800 |
| 15 | -0.45 | 3.00 | 68.9% | 4.368 | +1,005,657 | 49.5% | 1.888 | +24,554 | 1010195.595 |
| 16 | -0.45 | 10.00 | 68.9% | 4.359 | +1,002,761 | 49.5% | 1.863 | +23,866 | 1007294.037 |
| 17 | -0.45 | 4.00 | 68.9% | 4.359 | +1,002,761 | 49.5% | 1.915 | +25,298 | 1007294.037 |
| 18 | -0.45 | 2.00 | 68.9% | 4.353 | +1,000,972 | 49.5% | 2.026 | +28,353 | 1005501.598 |
| 19 | -0.45 | 1.50 | 68.9% | 4.244 | +968,519 | 49.5% | 2.015 | +28,068 | 972986.695 |
| 20 | -0.60 | 0.75 | 76.2% | 5.387 | +944,783 | 57.1% | 1.776 | +20,817 | 950242.539 |

## Interpretation

- This is not a model-fit improvement; it is an execution-contract improvement discovered on pre-OOS months and verified on Apr/May.
- The same entries and strikes are used, so trade volume is unchanged.
- Promotion requires the selected exit to beat the previous `-35%/+250%` contract OOS while keeping PF > 1.3, WR > 45%, and ticker-month volume near the target.
