# Magnitude-weighted pairwise side V1

- Cells: `99`
- Scientific pass: `False`
- Control valid folds: `1`
- Weighted valid folds: `1`
- Adaptive reuse; not promotable without a new holdout.

## Result

- Balanced-accuracy wins: `48/99`; median delta `-0.0001`; p=`0.6642`.
- Spearman positive: `54/99`; median `0.0103`.
- Scientific gate: FAIL.
- Both arms select only SPY/202410.
- Control: 23 trades, WR 34.78%, PF 0.4265, PnL -4.9301R.
- Weighted: 22 trades, WR 27.27%, PF 0.4299, PnL -5.1555R.
- Economic gate: FAIL. Do not tune weighting quantiles.
