# Independent level-oracle review — 2026-10-18

Status: `PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT`.

The reviewer owns this document, `audit_engine.py`, its fixtures and the full
dataset audit launchers. Producer engine, cache, features, learners and raw
sources were not edited. The oracle is a same-day hindsight upper bound; this
review makes no predictive, receipt-time, live-parity or promotion claim.

## Design and pilot review

The protocol freezes causal levels, contract, target and stop at the decision
minute. Execution is next-minute ask entry, first target/stop crossing with stop
priority, next-minute bid exit, and EOD fallback. Intermediate levels do not
exit the trade. Missing entry is `NO_FILL` with zero PnL and no rescue; missing
or invalid exit liquidates at zero. The oracle uses one-position scheduling and
may choose CASH.

Before the pilot, review found that state counts exposed the full-day contract
axis. The producer changed this to a causal known-contract mask: Greek identity
becomes known at its first observed row and OI identity only at its stored
availability. A future-only contract perturbation leaves all earlier states,
levels and actions unchanged.

The immutable 2023-01-03 pilot for SPXW, SPY and QQQ passed independent
reconstruction of 15,728 actions, 28 selected raw fills, causal identity/OI,
target/stop geometry, delta-bucket contracts, outcome labels, dynamic program,
trajectory and advantages. Its preserved result is
`D:/GexResearchArtifacts/level_oracle_20261018/engine_pilot_v1_audit_v2/audit.json`.
The positive pilot values are mechanically expected from a clairvoyant optimizer
over thousands of offered actions and are not evidence of a causal edge.

## Full audit corrections preserved

Three failed auditor attempts remain immutable and emitted no PASS:

- `engine_v1_audit`: zero completed days. A NumPy array was tested as a scalar
  boolean in the independent contract-universe check. The exact ndarray path is
  now a regression fixture.
- `engine_v1_audit_v2`: twelve completed day files. On SPXW 2023-01-19,
  Decimal reconstruction collapsed binary-float rewards for action IDs 4956
  and 4959 to the same $35.40, while the frozen arithmetic produced
  35.39999999999988 and 35.400000000000055. The auditor now independently
  reconstructs the specified binary-float operation order for exact DP/action
  identity and separately checks every distinct price pair against Decimal at
  1e-8 tolerance. The detailed failure is in `failure_diagnostic.json`.
- `engine_v1_audit_v3`: 190 completed day files. On SPXW 2023-10-02 state 89,
  an optimization reassociated `(center - spot) < boundary` into
  `center < spot + boundary`. Binary rounding excluded the valid 4280 stop and
  selected 4282.2636. The auditor restored the frozen subtract-then-compare
  order and added the complete boundary values as a fixture. Its diagnostic is
  preserved in that root.

Review also fixed a preexecution raw-fill check: a present row with an invalid
bid/ask is a missing exit, while bid zero with a positive noncrossed ask is a
valid exit. Entry quotes must be present and independently valid. Nine focused
auditor fixtures, Ruff and compilation pass after the final correction.

## Full result

The authoritative result is
`D:/GexResearchArtifacts/level_oracle_20261018/engine_v1_audit_v4/audit.json`,
SHA-256 `cbbe61d0a3fa7619447b7301d4c4b2fd52c487e11450d4904efee381fc3bf22d`.
It binds the engine root and SHA, original dataset runner, producer completion,
index, dataset/cache contracts and cache full summary. The producer completion
also binds runtime-03 SHA
`6b6496c622fba7e837beccf7c596c2aff38ac216ef2aa2a6e2bbc8ed132ae7f0`.

The audit independently verified:

- 2,601 expected full-session ticker-days: 2,595 complete and the exact six
  missing-source cells; 2,595 sealed day audit files and no v4 failure file.
- 15,395,840 action outcomes and contract/target definitions.
- 36,019 oracle trades and all 36,019 selected raw entry/exit fills.
- exact oracle action identities, trajectories and teacher advantages; DP values
  agree within the declared 1e-8 absolute tolerance.
- aggregate base oracle PnL $9,190,416.60 and same-path adverse PnL
  $9,118,378.60, matched to producer day, index and global summaries.
- every referenced cache, metadata, causal-freeze, source, day summary, index and
  completion seal, with zero source-hash mismatch.

The final auditor core SHA is
`04443b619d145e630ee03094214c1920ca13bd46ecca2c57b20f03e35449b7b5` and
the dataset audit runner SHA is
`73b2484e6671bc3c67f33745cff26e50cd2db04d9896956c96a8a488d15816d2`.
Scheduling moved from four to eight workers only after measuring memory; native
thread pools stayed at one. Runtime changes did not alter scientific code or
reuse unchecked days.

## Scientific boundary

This audit reconstructs every action label, economic result, oracle schedule and
selected raw fill. It does not independently rebuild the full feature tensor.
The observed $9.19 million is an in-sample clairvoyant ceiling, not a strategy
result. A learner must remain causal, bind this exact full PASS, freeze before
test labels, and survive its own independent audit. Receipt timing, live parity,
prospective performance and deployability remain unverified:
`technical_ready=false`, `promotion_approved=false`.
