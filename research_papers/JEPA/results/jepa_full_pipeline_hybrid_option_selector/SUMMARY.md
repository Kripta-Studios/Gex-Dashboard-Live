# Hybrid Option Selector Research

Candidate labels: `.\research_papers\JEPA\results\jepa_full_pipeline_option_policy\candidate_labels.parquet`
Train cutoff: `20260331`
Test start: `20260401`

## Best Validation Config

```json
{
  "delta_floor": 0.1,
  "best_weight": 0.0,
  "win_weight": 0.0,
  "delta_bias": 0.1,
  "margin": 0.05102573113917468
}
```

## OOS Results

| Policy | Trades | WR | PF | PnL | Max DD | Avg Delta | Avg Hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | 105 | 42.9% | 1.725 | +20,719 | -5,095 | 0.702 | 120.3 |
| hybrid_override_070 | 105 | 41.0% | 1.541 | +15,886 | -5,095 | 0.680 | 117.0 |
| oracle_best_delta_hard | 105 | 42.9% | 4.092 | +54,238 | -1,965 | 0.513 | 103.0 |
| oracle_best_delta_oracle_exit | 105 | 87.6% | 140.828 | +167,995 | -342 | 0.464 | 89.2 |

## Per Ticker OOS

| Policy | Ticker | Trades | WR | PF | PnL | Avg Delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| fixed_delta_0.70_hard | QQQ | 35 | 42.9% | 1.372 | +2,384 | 0.702 |
| fixed_delta_0.70_hard | SPX | 36 | 52.8% | 2.222 | +17,888 | 0.703 |
| fixed_delta_0.70_hard | SPY | 34 | 32.4% | 1.060 | +448 | 0.701 |
| hybrid_override_070 | QQQ | 35 | 42.9% | 1.383 | +2,432 | 0.693 |
| hybrid_override_070 | SPX | 36 | 47.2% | 1.833 | +12,890 | 0.657 |
| hybrid_override_070 | SPY | 34 | 32.4% | 1.075 | +564 | 0.692 |
| oracle_best_delta_hard | QQQ | 35 | 42.9% | 2.837 | +11,092 | 0.528 |
| oracle_best_delta_hard | SPX | 36 | 52.8% | 7.906 | +29,952 | 0.502 |
| oracle_best_delta_hard | SPY | 34 | 32.4% | 2.841 | +13,195 | 0.510 |
| oracle_best_delta_oracle_exit | QQQ | 35 | 85.7% | 75.537 | +50,516 | 0.432 |
| oracle_best_delta_oracle_exit | SPX | 36 | 91.7% | 246.060 | +81,364 | 0.543 |
| oracle_best_delta_oracle_exit | SPY | 34 | 85.3% | 189.403 | +36,115 | 0.415 |

## Top Validation Rows

| Rank | Score | Floor | BestW | WinW | DeltaBias | Margin | Trades | WR | PF | PnL |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 13.633 | 0.10 | 0.00 | 0.00 | 0.10 | 0.051 | 182 | 46.2% | 1.891 | +40,922 |
| 2 | 13.596 | 0.30 | 0.00 | 0.00 | 0.00 | 0.073 | 182 | 46.2% | 1.886 | +40,784 |
| 3 | 13.582 | 0.10 | 0.50 | 0.00 | 0.00 | 0.000 | 182 | 46.2% | 1.894 | +40,110 |
| 4 | 13.582 | 0.10 | 0.50 | 0.00 | 0.00 | -1000000000.000 | 182 | 46.2% | 1.894 | +40,110 |
| 5 | 13.560 | 0.30 | 0.00 | 0.00 | 0.10 | 0.051 | 182 | 46.2% | 1.881 | +40,670 |
| 6 | 13.533 | 0.10 | 0.00 | 0.00 | 0.00 | 0.075 | 182 | 46.2% | 1.882 | +40,407 |
| 7 | 13.434 | 0.10 | 0.00 | 0.00 | 0.25 | 0.020 | 182 | 46.2% | 1.869 | +40,092 |
| 8 | 13.405 | 0.30 | 0.00 | 0.00 | 0.25 | 0.019 | 182 | 46.2% | 1.861 | +40,171 |
| 9 | 13.314 | 0.10 | 0.00 | 0.00 | 0.25 | -1000000000.000 | 182 | 45.1% | 1.852 | +39,776 |
| 10 | 13.314 | 0.10 | 0.00 | 0.00 | 0.25 | 0.000 | 182 | 45.1% | 1.852 | +39,776 |
| 11 | 13.274 | 0.30 | 0.00 | 0.00 | 0.25 | 0.000 | 182 | 45.1% | 1.846 | +39,626 |
| 12 | 13.274 | 0.30 | 0.00 | 0.00 | 0.25 | -1000000000.000 | 182 | 45.1% | 1.846 | +39,626 |
| 13 | 13.254 | 0.10 | 0.00 | 0.00 | 0.00 | 0.001 | 182 | 44.0% | 1.844 | +39,424 |
| 14 | 13.226 | 0.10 | 0.00 | 0.00 | 0.00 | -1000000000.000 | 182 | 44.0% | 1.842 | +39,293 |
| 15 | 13.226 | 0.10 | 0.00 | 0.00 | 0.00 | 0.000 | 182 | 44.0% | 1.842 | +39,293 |

## Interpretation

- This is a reversible research layer on top of candidate labels; it does not modify production artifacts.
- The selector falls back to fixed 0.70 unless validation finds enough predicted edge to override it.
- Promotion requires beating fixed 0.70 OOS and in rolling walk-forward, not just this split.
