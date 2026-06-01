# JEPA Alpha Report

Gate A: FAIL

## Overall Metrics

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3545 | 49.6% | 1.305 | +367,372.09 | -17,217.31 |
| gbt_jepa | 3448 | 48.9% | 1.232 | +276,393.20 | -37,328.36 |
| jepa_only | 3949 | 44.9% | 0.962 | -58,715.65 | -99,570.09 |
| jepa_permuted | 3518 | 48.8% | 1.233 | +280,948.64 | -33,285.70 |

## Delta: GBT + JEPA vs Baseline

- Trades delta: -97 (0.973x baseline)
- PF delta: -0.073
- PnL delta: -90,978.90
- Drawdown ratio: 2.168x baseline

## Gate Reasons

- PF/PnL improvement threshold not met
- drawdown worsened too much: 2.168x

## Permutation Check

- This compares the candidate model against the same model/data after OOS JEPA feature permutation.
- PF candidate minus permuted: -0.001
- PnL candidate minus permuted: -4,555.44

## Per Ticker

| Ticker | Run | Trades | WR | PF | PnL | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | baseline | 1295 | 48.8% | 1.233 | +116,221.94 | -17,217.31 |
| QQQ | gbt_jepa | 1168 | 47.7% | 1.136 | +62,806.94 | -37,328.36 |
| QQQ | jepa_only | 1866 | 44.4% | 0.972 | -22,712.43 | -61,858.38 |
| QQQ | jepa_permuted | 1202 | 46.6% | 1.096 | +45,593.33 | -33,285.70 |
| SPX | baseline | 1291 | 47.6% | 1.370 | +159,449.59 | -15,087.11 |
| SPX | gbt_jepa | 1300 | 46.9% | 1.316 | +139,459.32 | -15,974.13 |
| SPX | jepa_only | 1132 | 42.1% | 0.913 | -38,281.79 | -56,872.54 |
| SPX | jepa_permuted | 1306 | 47.8% | 1.391 | +170,057.82 | -13,936.26 |
| SPY | baseline | 959 | 53.4% | 1.333 | +91,700.56 | -12,964.02 |
| SPY | gbt_jepa | 980 | 52.9% | 1.257 | +74,126.93 | -9,066.97 |
| SPY | jepa_only | 951 | 49.3% | 1.007 | +2,278.58 | -21,720.03 |
| SPY | jepa_permuted | 1010 | 52.7% | 1.221 | +65,297.48 | -11,349.14 |
