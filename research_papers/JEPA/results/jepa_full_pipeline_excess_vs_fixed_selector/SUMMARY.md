# Excess-Vs-Fixed Option Selector Research

Candidate labels: `.\research_papers\JEPA\results\jepa_full_pipeline_option_policy\candidate_labels.parquet`
Train cutoff: `20260331`
Test start: `20260401`

This selector directly predicts candidate excess PnL versus the fixed 0.70 delta candidate for the same signal. It falls back to fixed 0.70 unless validation-selected predicted edge clears the margin.

## Best Validation Config

```json
{
  "fixed_delta": 0.7,
  "delta_floor": 0.1,
  "beat_weight": 0.5,
  "best_weight": 0.25,
  "delta_bias": -0.25,
  "margin": 362.46071001337725
}
```

## OOS Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 105 | 42.9% | 1.725 | +20,719 | -5,095 | 0.702 | 120.3 |
| excess_vs_fixed_selector | 105 | 39.0% | 1.717 | +18,748 | -5,614 | 0.651 | 111.2 |
| oracle_best_delta_hard | 105 | 42.9% | 4.092 | +54,238 | -1,965 | 0.513 | 103.0 |
| oracle_best_delta_oracle_exit | 105 | 87.6% | 140.828 | +167,995 | -342 | 0.464 | 89.2 |

## Per Ticker OOS

| Policy | Ticker | Trades | WR | PF | PnL | Avg Delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | QQQ | 35 | 42.9% | 1.372 | +2,384 | 0.702 |
| fixed_delta_0.70_hard | SPX | 36 | 52.8% | 2.222 | +17,888 | 0.703 |
| fixed_delta_0.70_hard | SPY | 34 | 32.4% | 1.060 | +448 | 0.701 |
| excess_vs_fixed_selector | QQQ | 35 | 42.9% | 1.372 | +2,384 | 0.702 |
| excess_vs_fixed_selector | SPX | 36 | 41.7% | 2.333 | +16,076 | 0.559 |
| excess_vs_fixed_selector | SPY | 34 | 32.4% | 1.038 | +288 | 0.696 |
| oracle_best_delta_hard | QQQ | 35 | 42.9% | 2.837 | +11,092 | 0.528 |
| oracle_best_delta_hard | SPX | 36 | 52.8% | 7.906 | +29,952 | 0.502 |
| oracle_best_delta_hard | SPY | 34 | 32.4% | 2.841 | +13,195 | 0.510 |
| oracle_best_delta_oracle_exit | QQQ | 35 | 85.7% | 75.537 | +50,516 | 0.432 |
| oracle_best_delta_oracle_exit | SPX | 36 | 91.7% | 246.060 | +81,364 | 0.543 |
| oracle_best_delta_oracle_exit | SPY | 34 | 85.3% | 189.403 | +36,115 | 0.415 |

## Top Validation Rows

| Rank | Score | Floor | BeatW | BestW | DeltaBias | Margin | Trades | WR | PF | PnL |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 13.085 | 0.10 | 0.50 | 0.25 | -0.25 | 362.5 | 182 | 45.1% | 1.831 | +37,977 |
| 2 | 13.054 | 0.10 | 1.00 | 0.25 | -0.25 | 750.0 | 182 | 46.2% | 1.815 | +38,818 |
| 3 | 13.049 | 0.10 | 1.00 | 0.50 | -0.25 | 750.0 | 182 | 46.7% | 1.818 | +38,649 |
| 4 | 12.921 | 0.10 | 1.50 | 1.00 | -0.25 | 1000.0 | 182 | 46.2% | 1.801 | +38,238 |
| 5 | 12.833 | 0.10 | 0.25 | 0.25 | -0.25 | 196.6 | 182 | 44.0% | 1.815 | +36,513 |
| 6 | 12.831 | 0.10 | 0.25 | 0.25 | -0.25 | 250.0 | 182 | 46.7% | 1.794 | +37,683 |
| 7 | 12.772 | 0.10 | 0.25 | 0.50 | -0.25 | 126.3 | 182 | 42.9% | 1.826 | +34,979 |
| 8 | 12.763 | 0.50 | 1.50 | 0.00 | -0.25 | 996.7 | 182 | 45.6% | 1.776 | +37,715 |
| 9 | 12.760 | 0.10 | 0.25 | 1.00 | -0.25 | 0.0 | 182 | 41.8% | 1.835 | +34,656 |
| 10 | 12.760 | 0.10 | 0.25 | 1.00 | -0.25 | -1000000000.0 | 182 | 41.8% | 1.835 | +34,656 |
| 11 | 12.744 | 0.50 | 0.25 | 0.00 | -0.25 | 197.0 | 182 | 45.6% | 1.772 | +37,743 |
| 12 | 12.737 | 0.10 | 1.50 | 0.50 | -0.25 | 1000.0 | 182 | 45.6% | 1.780 | +37,490 |
| 13 | 12.721 | 0.50 | 1.00 | 0.00 | -0.25 | 673.8 | 182 | 45.6% | 1.771 | +37,567 |
| 14 | 12.690 | 0.40 | 1.00 | 0.25 | -0.25 | 750.0 | 182 | 47.3% | 1.761 | +38,042 |
| 15 | 12.688 | 0.40 | 0.25 | 0.00 | 0.25 | 111.6 | 182 | 46.2% | 1.758 | +38,055 |

## Interpretation

- This is a reversible research layer and does not modify production artifacts.
- Promotion requires beating fixed 0.70 OOS and in rolling walk-forward.
- If validation selects a high margin or fixed-only behavior, that means the model did not find robust override alpha.
