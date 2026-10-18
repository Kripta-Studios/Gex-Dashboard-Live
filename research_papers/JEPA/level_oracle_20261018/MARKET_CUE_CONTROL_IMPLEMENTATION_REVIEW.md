# Market-cue compact control implementation review

Status: `PASS_MARKET_CUE_CONTROL_IMPLEMENTATION_REVIEW`.

The implementation review covers only the compact representation, exact joins,
TRAIN matrix preparation, one-fit recovery rules, and synthetic fixtures. It is
not authorization or evidence for model fitting, validation/test evaluation,
economic performance, or promotion.

The reviewed representation contains 76 numeric values and 76 explicit validity
flags. Missing and observed zero remain distinguishable. Action/state joins bind
exact action IDs and decision minutes to the causal offered universe. The fast
factorized path is bitwise equal to the reference extractor in the synthetic
fixtures.

The runner preserves all 270,377 rows of the original sample in `sample_i` order,
uses the original IPW and ticker risk scales, and defines the unchanged target as
`net_base/risk_scale_usd`. Its loader rejects dates from 2025 onward. Checkpoints
seal source and code hashes, reject interrupted-fit adoption, and recheck sources
before publication.

The final authority fix requires the exact independent learner-audit SHA
`238e6f0974025edf076d4023f134878340141271547e45e618026042539945bd` and engine-audit SHA
`cbbe61d0a3fa7619447b7301d4c4b2fd52c487e11450d4904efee381fc3bf22d`
before loading source data, and propagates them into the run contract. Nineteen
focused fixtures and Ruff pass.

No prepare, fit, prediction, or economic evaluation was run for this review.
`technical_ready=false` and `promotion_approved=false`.
