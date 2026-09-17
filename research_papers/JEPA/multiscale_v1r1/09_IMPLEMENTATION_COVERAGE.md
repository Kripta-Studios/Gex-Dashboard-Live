# Actual implementation coverage

This is an admission-first release, not a completed historical economic engine.
`technical_ready=false` remains binding. A negative dependency result terminates
the current work without claiming completion of downstream implementation.

Implemented and exercised with synthetic fixtures:

- Immutable constants, explicit slots/channels/action order, eighteen fold dates.
- Canonical tensor validation/flattening, strict completed-bar aggregation,
  no-level projection and explicit initial-SPXW repair availability validation.
- Net-dollar Decimal accounting, native entry/exit selection, missing-exit penalty,
  chronological per-ticker replay and separate scenario metrics/gates.
- Fixed LightGBM parameters/action-fit primitive and full-width synthetic preflight.
- SSL clock projection, encoder/predictor, causal residual, within-event NCE and VIS
  primitives. No historical SSL training or utility head was executed.
- Artifact immutability/hash-chain logging, freeze integrity primitive, local
  default-deny promotion API, restricted source reader.
- Reproducible source inventory and a negative source-provenance admission check.
  The separate auditor reconstructs that negative check without evaluator imports.

Not implemented or certified in this release:

- Complete 59-level exposure/state/tensor builder and positive feature data gate.
- Eighteen-fold orchestration, winner/refit pipeline, baseline, SSL/head training,
  monthly payoff writer, paired bootstrap, full model/feature/economic auditor.
- Historical economic perturbation matrix, because no such historical artifacts
  exist. The checked perturbations concern source provenance, coverage and access.
- Historical/live parity, prospective shadow, account simulation or deployment.

The CLI retains the requested downstream command names but denies execution.
It cannot issue a positive feature gate or economic result, even if somebody edits
a status flag. No empty module is presented as a working implementation.

The source/provenance check is an upstream dependency check, not Stage C's complete
tensor/data gate. Stage B as a whole is therefore not marked PASS. Only an
independently verified blocking conclusion can close this admission-first release.
If source availability evidence is recovered later, it requires documented review
and completion/publication of the remaining implementation before any labels.

Publication: initial main push was rejected non-fast-forward. Fetch recovered
remote `8355c816` and four predecessor commits affecting production/frontend.
They were not merged or overwritten. Research lives on
`research/multiscale-v1r1-net-usd`, based on actual initial `29724f85`.
