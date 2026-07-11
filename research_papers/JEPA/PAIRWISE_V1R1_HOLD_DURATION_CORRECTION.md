# PAIRWISE V1R1 — hold-duration semantics correction

Status: executed once; correction verified; economic result rejected.

## Defect in V1

`call/put_dXX_opt_exit_minutes` is elapsed holding duration. The builder sets it to
`elapsed` and the common scheduler correctly computes `entry_minute + duration`.
Pairwise V1's inner gate incorrectly computed `exit_minutes - entry minute`, treating
duration as an absolute clock minute. With entries from 635 onward this made every
hold negative and forced all 12,474 grid rows to fail.

Direct audit after valid-label filtering:

| Ticker/bucket | CALL duration | PUT duration | Rows below 30m |
| --- | ---: | ---: | ---: |
| SPXW d25 | 30..180 | 30..180 | 0 |
| QQQ d35 | 30..180 | 30..180 | 0 |
| SPY d35 | 30..180 | 30..180 | 0 |

## Frozen correction

V1r1 changes exactly one expression: `min_hold = min(exit_minutes)`. Dataset,
features/hash, labels, 12/3/1 folds, C0/P1 models, seeds, LightGBM parameters,
threshold/margin grid, lexicographic selector, scheduler and all five gates remain
unchanged. The original V1 output is preserved and never overwritten.

Output:

```text
research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1r1_hold_fix/
```

Scientific model-level metrics must reproduce V1 because the correction is applied
only to inner policy validity. Economic metrics/trades are authoritative only in
V1r1. No 2026 data and no production files may be read or modified.

Canonical command after commit/push:

```powershell
pwsh -File run_pairwise_opportunity_side_v1r1_hold_fix.ps1
```

## Result

V1r1 completed 99/99 cells in 282.3 seconds. Scientific metrics reproduced V1
exactly, confirming that only policy validity changed. Valid inner policies:

- C0: SPY outer identities `202409`, `202410`, `202502`.
- P1: SPY `202410` only.
- SPXW/QQQ: none in either arm.

Outer C0: 61 trades, WR `45.90%`, pooled PF `0.9978`, PnL `-0.0396R`.
Outer P1: 23 trades, WR `34.78%`, PF `0.4265`, PnL `-4.9301R`.
No ticker/month cell passed the full outer contract. The correction is valid, but
the model remains rejected. Do not retune V1r1.
