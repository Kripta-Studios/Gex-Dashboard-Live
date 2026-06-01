# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 213 | 49.8% | 1.300 | +23,980.46 | -8,074.32 |
| gbt_jepa | 226 | 48.7% | 1.195 | +16,948.24 | -11,272.54 |
| jepa_only | 256 | 52.0% | 1.423 | +38,487.06 | -9,306.57 |
| jepa_permuted | 242 | 49.2% | 1.270 | +24,157.37 | -10,448.68 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +13 (1.061x baseline)
- PF delta: -0.105
- PnL delta: -7,032.22
- Drawdown ratio: 1.396x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 1.396x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.075
- PnL candidate minus permuted: -7,209.13

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 86 | 51.2% | 1.229 | +7,825.47 | -6,117.50 |
| QQQ | gbt_jepa | 89 | 48.3% | 1.031 | +1,148.52 | -6,936.49 |
| QQQ | jepa_only | 112 | 56.2% | 1.538 | +21,430.69 | -6,210.71 |
| QQQ | jepa_permuted | 99 | 44.4% | 1.011 | +466.42 | -10,448.68 |
| SPX | baseline | 73 | 42.5% | 1.212 | +6,830.16 | -8,074.32 |
| SPX | gbt_jepa | 81 | 43.2% | 1.124 | +4,437.20 | -11,272.54 |
| SPX | jepa_only | 82 | 48.8% | 1.410 | +13,943.90 | -9,306.57 |
| SPX | jepa_permuted | 82 | 47.6% | 1.404 | +12,887.18 | -7,973.22 |
| SPY | baseline | 54 | 57.4% | 1.687 | +9,324.83 | -3,940.05 |
| SPY | gbt_jepa | 56 | 57.1% | 1.827 | +11,362.52 | -3,940.05 |
| SPY | jepa_only | 62 | 48.4% | 1.181 | +3,112.46 | -5,532.56 |
| SPY | jepa_permuted | 61 | 59.0% | 1.678 | +10,803.76 | -4,624.48 |
