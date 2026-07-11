# PAIRWISE_MAGNITUDE_WEIGHTED_SIDE_V1

Status: executed once; rejected; do not tune weight cap.

## Hypothesis and single factor

V1 optimized an unweighted binary side label and achieved near-random outer side
metrics. The non-causal oracle shows that large side advantages contain economic
headroom. W1 changes only the training weight of the P1 side classifier:

```text
raw_weight = abs(call_return - put_return)
cap = train-only 95th percentile(raw_weight)
sample_weight = min(raw_weight, cap) / mean(min(raw_weight, cap))
```

Control P1 uses no weights. Both arms share the same opportunity model, side labels,
LightGBM architecture/parameters/seed, 30 features/hash, 12/3/1 folds, grid,
selector, corrected hold semantics and scheduler. No hyperparameter sweep is added.

## Criteria and limitation

W1 must improve balanced accuracy over control in >=60% of 99 cells, have positive
median delta, positive Spearman in >=60%, positive median Spearman and positive
annual median delta in 2023/2024/2025. Economic promotion still requires every
ticker/month PF>=1.3, WR>=50%, >=18 trades, PnL>0 and every hold>=30m.

Because Pairwise V1/V1r1 results over 2022–2025 motivated this weighting, this run is
adaptive mechanism discovery and cannot promote a live model even if it passes. A
new untouched holdout would remain mandatory. 2026 and production stay untouched.

## Result

W1 improved balanced accuracy in only `48/99` cells, median delta `-0.0001`,
Wilcoxon `p=0.6642`; annual median was negative in 2023 and zero in 2024.
Unweighted and weighted each selected only SPY/202410. Weighted outer: 22 trades,
WR `27.27%`, PF `0.4299`, PnL `-5.1555R`, worse than the already rejected control.
No economic cell passed. Magnitude weighting is rejected; do not sweep quantiles.
