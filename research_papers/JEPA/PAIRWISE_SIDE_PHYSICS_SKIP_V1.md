# PAIRWISE_SIDE_PHYSICS_SKIP_V1

Status: executed once; rejected; do not mine additional feature blocks on this OOS.

## Single factor

Control is corrected P1 unweighted. S1 keeps the shared opportunity head on the
original 30 features and changes only the feature matrix of the binary side head.
It adds current-time `phys_*` and `ctx_*` columns already present in the causal
physics parquet. It excludes:

- `phys_event_seq_in_day`, `phys_event_frac_in_day`,
  `phys_minutes_since_first_event`, `phys_spot_ret_from_first_event_bps`,
  `phys_same_day_event_count` (not reproducible live);
- absolute `ctx_*_spot` values;
- every future/outcome/exit/win column.

No feature is selected by correlation or outer results. Train-only medians are used.
Side labels, LightGBM parameters/seed, opportunity scores, folds, grid, scheduler and
all economic gates remain frozen. S1 must pass the same 99-cell scientific/economic
criteria. This is adaptive mechanism discovery and cannot promote without a new
untouched holdout. 2026 and production remain untouched.

## Result

S1 won balanced accuracy in `55/99` cells, median delta `+0.0039`, p=`0.3199`.
Spearman was positive in `61/99`, but 2024 median BA delta was negative and the
joint scientific gate failed. QQQ improved (median BA `0.522`, delta `+0.0385`),
while SPXW/SPY did not.

S1 selected one QQQ and one SPY fold. Outer QQQ: 38 trades, WR `34.21%`, PF
`0.4086`, PnL `-8.6909R`; SPY: 19 trades, WR `36.84%`, PF `0.8101`, PnL
`-1.2436R`. No cell passed. Further feature-block search on these outer months is
forbidden; the information expansion is rejected.
