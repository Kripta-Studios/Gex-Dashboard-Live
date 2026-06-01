# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3545 | 49.6% | 1.305 | +367,372.09 | -17,217.31 |
| gbt_jepa | 5720 | 45.2% | 1.027 | +59,284.52 | -59,862.02 |
| jepa_only | 5872 | 44.9% | 0.961 | -88,892.39 | -111,699.08 |
| jepa_permuted | 5835 | 45.2% | 1.030 | +64,664.96 | -74,876.17 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +2175 (1.614x baseline)
- PF delta: -0.278
- PnL delta: -308,087.57
- Drawdown ratio: 3.477x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 3.477x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.002
- PnL candidate minus permuted: -5,380.44

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 1295 | 48.8% | 1.233 | +116,221.94 | -17,217.31 |
| QQQ | gbt_jepa | 2307 | 44.8% | 1.012 | +11,332.50 | -58,161.81 |
| QQQ | jepa_only | 2639 | 43.8% | 0.936 | -72,811.65 | -92,734.42 |
| QQQ | jepa_permuted | 2386 | 44.3% | 0.972 | -29,032.65 | -74,876.17 |
| SPX | baseline | 1291 | 47.6% | 1.370 | +159,449.59 | -15,087.11 |
| SPX | gbt_jepa | 2082 | 41.9% | 0.995 | -3,510.20 | -24,899.43 |
| SPX | jepa_only | 1809 | 42.8% | 1.003 | +2,252.66 | -52,979.26 |
| SPX | jepa_permuted | 2070 | 42.3% | 1.039 | +28,766.67 | -27,110.25 |
| SPY | baseline | 959 | 53.4% | 1.333 | +91,700.56 | -12,964.02 |
| SPY | gbt_jepa | 1331 | 51.1% | 1.124 | +51,462.22 | -30,754.97 |
| SPY | jepa_only | 1424 | 49.6% | 0.961 | -18,333.40 | -36,797.04 |
| SPY | jepa_permuted | 1379 | 51.2% | 1.153 | +64,930.94 | -23,366.92 |
