# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3545 | 49.6% | 1.305 | +367,372.09 | -17,217.31 |
| gbt_jepa | 3858 | 48.8% | 1.213 | +290,583.34 | -31,267.62 |
| jepa_only | 4139 | 46.9% | 1.073 | +111,098.27 | -40,425.54 |
| jepa_permuted | 4201 | 47.8% | 1.123 | +187,880.44 | -33,417.75 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +313 (1.088x baseline)
- PF delta: -0.092
- PnL delta: -76,788.75
- Drawdown ratio: 1.816x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 1.816x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: +0.090
- PnL candidate minus permuted: +102,702.90

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 1295 | 48.8% | 1.233 | +116,221.94 | -17,217.31 |
| QQQ | gbt_jepa | 1572 | 46.1% | 1.033 | +22,013.25 | -31,267.62 |
| QQQ | jepa_only | 1849 | 45.4% | 1.006 | +4,405.36 | -40,425.54 |
| QQQ | jepa_permuted | 1699 | 46.1% | 0.991 | -6,624.07 | -33,417.75 |
| SPX | baseline | 1291 | 47.6% | 1.370 | +159,449.59 | -15,087.11 |
| SPX | gbt_jepa | 1320 | 48.4% | 1.469 | +199,673.96 | -11,272.54 |
| SPX | jepa_only | 1315 | 45.6% | 1.136 | +64,236.22 | -16,938.04 |
| SPX | jepa_permuted | 1433 | 46.6% | 1.320 | +156,180.99 | -11,594.80 |
| SPY | baseline | 959 | 53.4% | 1.333 | +91,700.56 | -12,964.02 |
| SPY | gbt_jepa | 966 | 53.6% | 1.246 | +68,896.13 | -14,806.05 |
| SPY | jepa_only | 975 | 51.7% | 1.145 | +42,456.69 | -14,902.73 |
| SPY | jepa_permuted | 1069 | 52.2% | 1.118 | +38,323.52 | -24,726.83 |
