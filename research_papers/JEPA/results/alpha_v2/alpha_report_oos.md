# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 213 | 49.8% | 1.300 | +23,980.46 | -8,074.32 |
| gbt_jepa | 234 | 51.7% | 1.292 | +25,430.39 | -7,913.33 |
| jepa_only | 256 | 52.0% | 1.423 | +38,487.06 | -9,306.57 |
| jepa_permuted | 235 | 51.9% | 1.352 | +30,282.91 | -7,556.17 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +21 (1.099x baseline)
- PF delta: -0.008
- PnL delta: +1,449.93
- Drawdown ratio: 0.980x baseline

## Gate Reasons

- PF/PnL improvement threshold not met

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.060
- PnL candidate minus permuted: -4,852.52

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 86 | 51.2% | 1.229 | +7,825.47 | -6,117.50 |
| QQQ | gbt_jepa | 95 | 54.7% | 1.414 | +14,461.41 | -5,366.79 |
| QQQ | jepa_only | 112 | 56.2% | 1.538 | +21,430.69 | -6,210.71 |
| QQQ | jepa_permuted | 96 | 51.0% | 1.125 | +4,978.44 | -7,300.33 |
| SPX | baseline | 73 | 42.5% | 1.212 | +6,830.16 | -8,074.32 |
| SPX | gbt_jepa | 81 | 44.4% | 1.135 | +4,751.91 | -7,913.33 |
| SPX | jepa_only | 82 | 48.8% | 1.410 | +13,943.90 | -9,306.57 |
| SPX | jepa_permuted | 78 | 47.4% | 1.470 | +14,190.31 | -7,556.17 |
| SPY | baseline | 54 | 57.4% | 1.687 | +9,324.83 | -3,940.05 |
| SPY | gbt_jepa | 58 | 56.9% | 1.367 | +6,217.07 | -5,045.10 |
| SPY | jepa_only | 62 | 48.4% | 1.181 | +3,112.46 | -5,532.56 |
| SPY | jepa_permuted | 61 | 59.0% | 1.695 | +11,114.17 | -4,624.48 |
