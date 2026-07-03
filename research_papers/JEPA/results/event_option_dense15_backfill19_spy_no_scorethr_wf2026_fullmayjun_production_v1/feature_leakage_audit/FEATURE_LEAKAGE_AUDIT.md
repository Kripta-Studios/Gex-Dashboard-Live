# Event Option Feature Leakage Audit

- Passed: `False`
- Data: `research_papers\JEPA\results\_diagnostics\visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1_physics\event_option_dataset.parquet`
- Result dir: `research_papers\JEPA\results\event_option_dense15_backfill19_spy_no_scorethr_wf2026_fullmayjun_production_v1`
- Months: `202601, 202602, 202603, 202604`

## Feature Audit

- Raw columns: `358`
- Raw leaky/outcome columns present: `80`
- Selected features: `162`
- Selected leaky features: `0`
- Live feature-contract issues: `2`

## Trade And Lineage

- Trade file pure 0DTE: `True`
- Expiry modes: `['zero_dte']`
- Fold lineage passed: `True`
- Folds checked: `24`

## Issues

- live feature contract: selected_features: uses live-inconsistent intraday state features ['phys_event_frac_in_day', 'phys_event_seq_in_day', 'phys_minutes_since_first_event', 'phys_same_day_event_count', 'phys_spot_ret_from_first_event_bps']
- live feature contract: selected_features: uses initial-balance/fib features before IB completion (entry_start_minute_et=600); features=ctx_qqq_ib_range_bps, ctx_qqq_nearest_level_abs_bps, ctx_spx_ib_range_bps, ctx_spx_nearest_level_abs_bps, ctx_spy_ib_range_bps, ctx_spy_nearest_level_abs_bps, dist_fib_127_dn_bps, dist_fib_127_up_bps, dist_fib_161_dn_bps, dist_fib_161_up_bps, dist_fib_200_dn_bps, dist_fib_200_up_bps ... +20