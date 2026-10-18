# Independent market-cue comparison economic audit specification

The auditor reconstructs the complete economic comparison from sealed prediction
arrays. It must not import `evaluate_market_cue_control.py`,
`market_cue_comparison.py`, or any producer scheduler/metric helper. It performs
no fit and no new inference.

The fixed policies are `original_net__0` and `cue_net__0`, both at strict USD
threshold zero. There is no winner selection. For every state, rank score
descending and action ID ascending before reading labels. A score must be greater
than zero. WAIT advances one minute; NO_FILL records the attempt and advances one
minute without a replacement action; FILLED blocks through `exit_i` and resumes at
`exit_i+1`. Reconstruct `has_filled_before`, attempts, ledger, base/adverse
economics, daily coverage, and all period aggregates.

Coverage must be exactly 750 ticker-days in 2025, including nine short sessions,
and 369 in 2026H1: 363 available and the exact six missing SPY/QQQ dates. Missing
days remain `NO_EVALUABLE` with no fabricated prediction, attempt, trade, or PnL.

For every full session, the sealed `original_net__0` action IDs, state IDs, dtype,
shape and score bytes must equal the previously audited original `gbt_net`
prediction NPZ and its manifest. The nine short 2025 sessions have no legacy
prediction reference; they must carry the explicit no-reference marker and bind
the independently audited SessionClock actions/features. This distinction must
appear in the result.

Reconstruct the four calibration populations using fixed TRAIN risk-unit edges
`[-1,-.5,0,.1,.25,.5,1,2]`: all offers action-weighted, all offers with equal
day-state weight, selected attempts, and selected fills. Verify every daily
calibration accumulator and every ticker/pooled period report.

The audit rehashes the comparison freeze, completion/period markers, prediction
and daily markers, arrays, attempts, SessionClock index/actions/labels/features,
original prediction manifests, model completions, and independent learner,
engine and SessionClock audit authorities. Predictions must be sealed with
`outcomes_read=false` before their corresponding daily economic artifact.

Synthetic fixtures cover score/action ties, strict threshold, WAIT, NO_FILL,
FILLED blocking, short/full clocks, missing days, calibration weights and bins,
baseline byte identity, and mutation failures. A PASS establishes economic
execution given sealed predictions. It does not reproduce either model's fit or
inference and does not make 2025/2026 prospective.

