# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3545 | 49.6% | 1.305 | +367,372.09 | -17,217.31 |
| gbt_jepa | 3787 | 50.5% | 1.301 | +390,076.47 | -22,373.26 |
| jepa_only | 4139 | 46.9% | 1.073 | +111,098.27 | -40,425.54 |
| jepa_permuted | 4152 | 48.1% | 1.143 | +212,521.33 | -32,444.60 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +242 (1.068x baseline)
- PF delta: -0.004
- PnL delta: +22,704.38
- Drawdown ratio: 1.299x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 1.299x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: +0.158
- PnL candidate minus permuted: +177,555.14

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 1295 | 48.8% | 1.233 | +116,221.94 | -17,217.31 |
| QQQ | gbt_jepa | 1532 | 49.0% | 1.166 | +101,541.08 | -22,373.26 |
| QQQ | jepa_only | 1849 | 45.4% | 1.006 | +4,405.36 | -40,425.54 |
| QQQ | jepa_permuted | 1675 | 47.0% | 1.049 | +33,349.15 | -32,444.60 |
| SPX | baseline | 1291 | 47.6% | 1.370 | +159,449.59 | -15,087.11 |
| SPX | gbt_jepa | 1292 | 50.0% | 1.515 | +208,821.61 | -11,426.36 |
| SPX | jepa_only | 1315 | 45.6% | 1.136 | +64,236.22 | -16,938.04 |
| SPX | jepa_permuted | 1409 | 46.2% | 1.275 | +132,735.93 | -17,318.54 |
| SPY | baseline | 959 | 53.4% | 1.333 | +91,700.56 | -12,964.02 |
| SPY | gbt_jepa | 963 | 53.8% | 1.286 | +79,713.78 | -11,732.04 |
| SPY | jepa_only | 975 | 51.7% | 1.145 | +42,456.69 | -14,902.73 |
| SPY | jepa_permuted | 1068 | 52.4% | 1.145 | +46,436.25 | -19,986.50 |
