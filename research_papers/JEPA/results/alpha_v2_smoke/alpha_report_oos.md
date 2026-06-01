# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 213 | 49.8% | 1.300 | +23,980.46 | -8,074.32 |
| gbt_jepa | 212 | 47.2% | 0.934 | -5,765.86 | -22,979.75 |
| jepa_only | 246 | 55.3% | 1.327 | +27,014.40 | -6,642.32 |
| jepa_permuted | 210 | 45.7% | 0.985 | -1,304.12 | -15,714.70 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: -1 (0.995x baseline)
- PF delta: -0.366
- PnL delta: -29,746.32
- Drawdown ratio: 2.846x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 2.846x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.051
- PnL candidate minus permuted: -4,461.73

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 86 | 51.2% | 1.229 | +7,825.47 | -6,117.50 |
| QQQ | gbt_jepa | 88 | 43.2% | 0.777 | -9,082.55 | -18,020.54 |
| QQQ | jepa_only | 114 | 54.4% | 1.211 | +8,874.07 | -6,642.32 |
| QQQ | jepa_permuted | 91 | 42.9% | 0.863 | -5,566.60 | -15,714.70 |
| SPX | baseline | 73 | 42.5% | 1.212 | +6,830.16 | -8,074.32 |
| SPX | gbt_jepa | 70 | 42.9% | 0.896 | -3,267.48 | -13,017.21 |
| SPX | jepa_only | 73 | 52.1% | 1.299 | +8,294.22 | -5,539.92 |
| SPX | jepa_permuted | 65 | 43.1% | 1.014 | +396.51 | -9,468.37 |
| SPY | baseline | 54 | 57.4% | 1.687 | +9,324.83 | -3,940.05 |
| SPY | gbt_jepa | 54 | 59.3% | 1.437 | +6,584.18 | -3,149.70 |
| SPY | jepa_only | 59 | 61.0% | 1.763 | +9,846.11 | -3,602.36 |
| SPY | jepa_permuted | 54 | 53.7% | 1.236 | +3,865.97 | -5,216.27 |
