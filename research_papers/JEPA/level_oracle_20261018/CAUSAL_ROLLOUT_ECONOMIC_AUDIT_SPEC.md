# Independent audit given sealed causal rollout scores

2026-10-18. Written before auditor implementation and before its market run.
This audit does not fit, select alternative methods or modify producer outputs.
It imports no producer scheduler, rollout, sampler or metrics function.
Generic Python, NumPy and pandas implement the independent reconstruction.

Admission requires completed model, sampling, matrix, target, risk-scale,
validation, validation-freeze, test-summary and test-diagnostic checkpoints.
The auditor binds the run contract, executed dependency snapshots, engine
index/source hashes and all consumed complete markers. It verifies original
outputs before parsing them. Outputs go to a fresh audit root; failures are
recorded and are not overwritten by a later pass.

The primary scope is economic reconstruction **given saved scores**. It checks
finite two-flag scores against all causal action IDs/states and their sealed
model hashes. It does not refit models or recompute every prediction from raw
feature packs. Saved prediction and input provenance are checked, not replaced
by a claim of independent neural/tree inference or raw feature recomputation.

For each state 60..375 and flag, independently rank actions by descending score
and then smallest action_id. A score must strictly exceed 0/5/10 USD. Begin
each day flat with h=0. NO_FILL advances one minute, preserves h and never tries
the second action at that minute. FILLED, including a zero-net or losing fill,
sets h=1 and blocks until exit_i+1. WAIT advances one minute. Reconstruct all
six policies and compare every attempted action, fill, score, h, label and
ledger field. The audit never chooses actions using realized rewards.

Recompute base/adverse net, PF/infinite convention, WR, realized drawdown,
holding and exit-reason summaries, ticker/month summaries and original economic
gates. Economic PnL contains labels.net_base/net_adverse only, never terminal
lambda. Independently construct the full-session daily calendar, retaining the
six missing SPY/QQQ April-2026 sessions as NO_EVALUABLE. Observed zero-fill days
are separate. The producer's full-calendar zero count includes absent fills on
missing dates; it means failure to evidence the requirement, not observed zero
market opportunity. Both producer-compatible counts and explicit audit coverage
statuses are reported.

Recompute the 2025 hard daily eligibility and scale-normalized net ranking;
ties prefer control then the lower threshold. If none passes daily coverage,
selected_policy must be null with six frozen candidate IDs. Verify that the
freeze binds final models, H1 scales and validation summary and predates every
test score checkpoint. A null freeze does not authorize selecting from test.

Additional training evidence is reconstructed with bounded memory: canonical
identity SHA256 top32 per fixed band and all population counts; teacher unique
weights, final paired h/half weights and global mean-one weights; H1 premium
scales from sampled filled positive-premium entries; fixed-teacher choices from
saved scores; independent finite-horizon policy returns and sampled net/A
targets; final targets/divisors/weights; matrices against complete day chunks,
paired h columns and target/weight/matrix hashes in fit-start records. Matrix
columns are not independently regenerated from raw source/features. All three
fit signatures and their 200-tree common configuration are checked, without
refits. Teacher producer must precede every continuation checkpoint.

Comparisons use exact identities, flags, schemas, counts, hashes and sampling
weights; recomputed arithmetic permits atol1e-8/rtol1e-10. Fixtures use only
synthetic values: strict threshold/ties, losing and zero fills, no-fill/no
replacement, h-dependent choices, no overlap, no lambda in PnL, null selection,
tie ordering, missing versus observed-zero calendars, corrupted joins/scores,
checkpoint tampering/order, and independent rollout/target identities.

The real audit may run only after completed economic checkpoints exist and the
parent requests it. One process, sequential days, no full-day feature matrix
collection, no training, no API, no changes to original files or production.
