# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 213 | 49.8% | 1.300 | +23,980.46 | -8,074.32 |
| gbt_jepa | 189 | 46.6% | 1.049 | +3,808.80 | -11,927.33 |
| jepa_only | 251 | 49.0% | 1.185 | +17,480.48 | -9,159.58 |
| jepa_permuted | 198 | 49.5% | 1.064 | +4,894.46 | -12,091.54 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: -24 (0.887x baseline)
- PF delta: -0.251
- PnL delta: -20,171.66
- Drawdown ratio: 1.477x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- trade count ratio too low: 0.887
- drawdown worsened too much: 1.477x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.015
- PnL candidate minus permuted: -1,085.66

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 86 | 51.2% | 1.229 | +7,825.47 | -6,117.50 |
| QQQ | gbt_jepa | 71 | 40.8% | 0.748 | -8,482.96 | -11,927.33 |
| QQQ | jepa_only | 109 | 49.5% | 1.120 | +5,217.05 | -9,159.58 |
| QQQ | jepa_permuted | 82 | 46.3% | 0.847 | -5,318.14 | -12,091.54 |
| SPX | baseline | 73 | 42.5% | 1.212 | +6,830.16 | -8,074.32 |
| SPX | gbt_jepa | 66 | 42.4% | 1.182 | +5,411.68 | -8,816.70 |
| SPX | jepa_only | 85 | 48.2% | 1.337 | +11,431.87 | -8,060.17 |
| SPX | jepa_permuted | 63 | 42.9% | 1.062 | +1,729.65 | -8,998.74 |
| SPY | baseline | 54 | 57.4% | 1.687 | +9,324.83 | -3,940.05 |
| SPY | gbt_jepa | 52 | 59.6% | 1.502 | +6,880.08 | -3,654.21 |
| SPY | jepa_only | 57 | 49.1% | 1.048 | +831.56 | -3,495.04 |
| SPY | jepa_permuted | 53 | 62.3% | 1.634 | +8,482.95 | -3,774.20 |
