# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3545 | 49.6% | 1.305 | +367,372.09 | -17,217.31 |
| gbt_jepa | 5564 | 46.3% | 1.092 | +187,763.07 | -41,172.70 |
| jepa_only | 6141 | 44.6% | 0.979 | -49,181.46 | -126,168.10 |
| jepa_permuted | 5680 | 46.6% | 1.095 | +197,219.50 | -32,647.70 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: +2019 (1.570x baseline)
- PF delta: -0.213
- PnL delta: -179,609.02
- Drawdown ratio: 2.391x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 2.391x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.004
- PnL candidate minus permuted: -9,456.43

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 1295 | 48.8% | 1.233 | +116,221.94 | -17,217.31 |
| QQQ | gbt_jepa | 2160 | 45.7% | 1.055 | +50,123.83 | -41,172.70 |
| QQQ | jepa_only | 2835 | 44.4% | 0.983 | -20,819.08 | -93,808.21 |
| QQQ | jepa_permuted | 2185 | 46.1% | 1.049 | +44,519.70 | -32,647.70 |
| SPX | baseline | 1291 | 47.6% | 1.370 | +159,449.59 | -15,087.11 |
| SPX | gbt_jepa | 2060 | 42.2% | 1.060 | +44,438.92 | -21,594.81 |
| SPX | jepa_only | 2000 | 42.5% | 0.981 | -13,707.06 | -46,352.16 |
| SPX | jepa_permuted | 2073 | 43.2% | 1.110 | +80,311.27 | -20,024.87 |
| SPY | baseline | 959 | 53.4% | 1.333 | +91,700.56 | -12,964.02 |
| SPY | gbt_jepa | 1344 | 53.6% | 1.232 | +93,200.32 | -20,751.63 |
| SPY | jepa_only | 1306 | 48.2% | 0.966 | -14,655.33 | -26,466.64 |
| SPY | jepa_permuted | 1422 | 52.3% | 1.170 | +72,388.53 | -27,867.22 |
