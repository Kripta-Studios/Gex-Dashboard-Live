# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3545 | 49.6% | 1.305 | +367,372.09 | -17,217.31 |
| gbt_jepa | 3843 | 51.1% | 1.335 | +439,787.40 | -18,996.89 |
| jepa_only | 3967 | 49.6% | 1.197 | +279,231.94 | -27,146.10 |
| jepa_permuted | 4233 | 47.2% | 1.109 | +168,117.52 | -33,558.53 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +298 (1.084x baseline)
- PF delta: +0.030
- PnL delta: +72,415.31
- Drawdown ratio: 1.103x baseline

## Gate Reasons

- PnL improved by +72,415.31 >= 10% baseline
- drawdown worsened too much: 1.103x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: +0.225
- PnL candidate minus permuted: +271,669.88

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 1295 | 48.8% | 1.233 | +116,221.94 | -17,217.31 |
| QQQ | gbt_jepa | 1587 | 48.5% | 1.185 | +117,033.42 | -18,996.89 |
| QQQ | jepa_only | 1729 | 47.4% | 1.129 | +89,900.29 | -27,146.10 |
| QQQ | jepa_permuted | 1717 | 45.8% | 1.022 | +15,797.30 | -33,558.53 |
| SPX | baseline | 1291 | 47.6% | 1.370 | +159,449.59 | -15,087.11 |
| SPX | gbt_jepa | 1274 | 50.9% | 1.569 | +231,025.78 | -13,032.67 |
| SPX | jepa_only | 1222 | 48.2% | 1.292 | +123,708.66 | -15,852.85 |
| SPX | jepa_permuted | 1421 | 46.4% | 1.236 | +117,008.21 | -18,647.49 |
| SPY | baseline | 959 | 53.4% | 1.333 | +91,700.56 | -12,964.02 |
| SPY | gbt_jepa | 982 | 55.6% | 1.331 | +91,728.21 | -9,586.22 |
| SPY | jepa_only | 1016 | 55.0% | 1.224 | +65,622.99 | -12,445.20 |
| SPY | jepa_permuted | 1095 | 50.6% | 1.105 | +35,312.02 | -18,792.60 |
