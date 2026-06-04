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
  "policy_family": "hard",
  "hard_stop_pct": -0.6,
  "take_profit_pct": 10.0,
  "trail_activation_pct": null,
  "trail_drawdown_pct": null,
  "selection": "max meta-train score with PF>=1.3, WR>=45%, positive PnL"
}
```

## Meta-Train

| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_stop35_tp250 | 3667 | 54.2% | 2.684 | +1,205,603 | -9,963 | 99.9 | 28 | 0 |
| selected_exit | 3667 | 71.3% | 5.010 | +1,905,127 | -5,302 | 126.7 | 28 | 0 |

## Apr/May OOS

| Policy | Trades | WR | PF | PnL | Max DD | Avg Hold | Min Trades/Ticker-Month | Low-Volume Cells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_stop35_tp250 | 169 | 32.5% | 1.162 | +8,522 | -12,117 | 85.1 | 22 | 0 |
| selected_exit | 169 | 44.4% | 1.357 | +18,863 | -9,723 | 119.0 | 22 | 0 |

## Top Train Grid Rows

| Rank | Family | Stop | TP | Trail Act | Trail DD | Train WR | Train PF | Train PnL | OOS WR | OOS PF | OOS PnL | Score |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | hard | -0.60 | 10.00 | nan | nan | 71.3% | 5.010 | +1,905,127 | 44.4% | 1.357 | +18,863 | 1910407.873 |
| 2 | trail | -0.60 | 10.00 | 2.00 | 1.50 | 71.3% | 4.988 | +1,894,001 | 44.4% | 1.357 | +18,863 | 1899271.316 |
| 3 | trail | -0.60 | 10.00 | 1.50 | 1.50 | 71.3% | 4.978 | +1,891,137 | 44.4% | 1.357 | +18,863 | 1896401.325 |
| 4 | hard | -0.60 | 4.00 | nan | nan | 71.3% | 4.973 | +1,887,520 | 44.4% | 1.357 | +18,863 | 1892782.311 |
| 5 | hard | -0.60 | 3.00 | nan | nan | 71.3% | 4.967 | +1,884,813 | 44.4% | 1.353 | +18,698 | 1890072.445 |
| 6 | trail | -0.60 | 10.00 | 1.00 | 1.50 | 71.1% | 4.944 | +1,884,010 | 44.4% | 1.387 | +20,021 | 1889253.459 |
| 7 | trail | -0.60 | 10.00 | 0.50 | 1.50 | 71.1% | 4.934 | +1,882,975 | 44.4% | 1.387 | +20,021 | 1888213.048 |
| 8 | trail | -0.60 | 10.00 | 0.75 | 1.50 | 71.1% | 4.934 | +1,882,975 | 44.4% | 1.387 | +20,021 | 1888213.048 |
| 9 | trail | -0.60 | 10.00 | 2.00 | 0.75 | 71.3% | 4.963 | +1,882,421 | 44.4% | 1.363 | +19,216 | 1887679.566 |
| 10 | trail | -0.60 | 10.00 | 2.00 | 0.50 | 71.3% | 4.951 | +1,876,580 | 44.4% | 1.360 | +19,032 | 1881832.364 |
| 11 | trail | -0.60 | 10.00 | 2.00 | 1.00 | 71.3% | 4.950 | +1,875,909 | 44.4% | 1.360 | +19,038 | 1881160.150 |
| 12 | hard | -0.60 | 2.50 | nan | nan | 71.3% | 4.936 | +1,870,005 | 44.4% | 1.377 | +19,928 | 1875248.708 |
| 13 | trail | -0.60 | 10.00 | 1.50 | 0.75 | 71.4% | 4.932 | +1,867,699 | 44.4% | 1.305 | +16,137 | 1872942.131 |
| 14 | trail | -0.60 | 10.00 | 2.00 | 0.35 | 71.3% | 4.930 | +1,866,813 | 44.4% | 1.370 | +19,561 | 1872054.959 |
| 15 | trail | -0.60 | 10.00 | 1.50 | 1.00 | 71.4% | 4.928 | +1,865,355 | 44.4% | 1.338 | +17,901 | 1870595.628 |
| 16 | trail | -0.60 | 10.00 | 2.00 | 0.25 | 71.3% | 4.915 | +1,859,691 | 44.4% | 1.395 | +20,896 | 1864925.344 |
| 17 | hard | -0.60 | 2.00 | nan | nan | 71.3% | 4.902 | +1,853,097 | 44.4% | 1.424 | +22,404 | 1858324.273 |
| 18 | trail | -0.60 | 10.00 | 1.50 | 0.50 | 71.4% | 4.898 | +1,851,492 | 44.4% | 1.301 | +15,931 | 1856717.775 |
| 19 | trail | -0.60 | 10.00 | 1.50 | 0.35 | 71.4% | 4.876 | +1,840,845 | 44.4% | 1.307 | +16,242 | 1846059.808 |
| 20 | trail | -0.60 | 10.00 | 1.00 | 1.00 | 71.3% | 4.886 | +1,838,080 | 46.2% | 1.413 | +20,781 | 1843265.771 |

## Interpretation

- This is not a model-fit improvement; it is an execution-contract improvement discovered on pre-OOS months and verified on Apr/May.
- The same entries and strikes are used, so trade volume is unchanged.
- Promotion requires the selected exit to beat the previous `-35%/+250%` contract OOS while keeping PF > 1.3, WR > 45%, and ticker-month volume near the target.
