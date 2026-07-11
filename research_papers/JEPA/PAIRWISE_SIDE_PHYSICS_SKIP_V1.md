# PAIRWISE_SIDE_PHYSICS_SKIP_V1

Status: predeclared exploratory information test; not executed at this checkpoint.

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
