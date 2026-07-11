# PAIRWISE_MAGNITUDE_WEIGHTED_SIDE_V1

Status: predeclared exploratory mechanism test; not executed at this checkpoint.

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
