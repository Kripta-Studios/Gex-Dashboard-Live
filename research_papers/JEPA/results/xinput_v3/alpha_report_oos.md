# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 213 | 49.8% | 1.300 | +23,980.46 | -8,074.32 |
| gbt_jepa | 227 | 48.0% | 1.094 | +8,762.90 | -6,154.20 |
| jepa_only | 249 | 54.6% | 1.406 | +34,800.48 | -6,478.98 |
| jepa_permuted | 230 | 50.4% | 1.355 | +28,544.32 | -5,871.60 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +14 (1.066x baseline)
- PF delta: -0.207
- PnL delta: -15,217.56
- Drawdown ratio: 0.762x baseline

## Gate Reasons

- PF/PnL improvement threshold not met

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.262
- PnL candidate minus permuted: -19,781.42

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 86 | 51.2% | 1.229 | +7,825.47 | -6,117.50 |
| QQQ | gbt_jepa | 94 | 47.9% | 1.078 | +3,188.14 | -5,291.47 |
| QQQ | jepa_only | 109 | 53.2% | 1.334 | +13,846.73 | -6,349.68 |
| QQQ | jepa_permuted | 92 | 53.3% | 1.437 | +14,577.68 | -5,871.60 |
| SPX | baseline | 73 | 42.5% | 1.212 | +6,830.16 | -8,074.32 |
| SPX | gbt_jepa | 77 | 44.2% | 1.076 | +2,711.12 | -6,154.20 |
| SPX | jepa_only | 80 | 52.5% | 1.474 | +14,578.96 | -6,478.98 |
| SPX | jepa_permuted | 77 | 49.4% | 1.372 | +10,834.19 | -4,370.01 |
| SPY | baseline | 54 | 57.4% | 1.687 | +9,324.83 | -3,940.05 |
| SPY | gbt_jepa | 56 | 53.6% | 1.165 | +2,863.64 | -5,904.02 |
| SPY | jepa_only | 60 | 60.0% | 1.468 | +6,374.79 | -2,669.25 |
| SPY | jepa_permuted | 61 | 47.5% | 1.176 | +3,132.45 | -5,107.90 |
