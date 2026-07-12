# H-QSIZE1R1 quality-only repair

Status: frozen after the outcome-free H-QSIZE1 data gate was rejected and before
reading physical labels, fitting any model, inspecting any outer score or
computing any option payoff.

## Why V1 was rejected

The immutable V1 build preserved all 10,683 candidates and passed source,
causality, coverage and control gates. Its `distinctness_pass` failed only for
six ticker-year cells of `local_signable_fraction_change_{1,5}m`. In every
failed cell the feature was identically zero; no outcome was opened.

This exposes a concrete protocol bug rather than an unfavorable model result.
The causal amendment says availability/validity fields are audit-only, but V1
still put `local_signable_fraction` and its changes into the model measurement
allowlist. Signability is quote quality, not bid/ask size pressure.

## Frozen one-factor repair

H-QSIZE1R1 changes only the classification of fields:

- F1 model block: 32 fields — current and 1/5/15-minute changes of
  `local_qimb`, `local_log_bid_depth`, `local_log_ask_depth` and
  `relative_qimb`, separately for CALL and PUT;
- audit-only block: the 8 current/change `local_signable_fraction` fields plus
  the 5 existing validity/count fields;
- dataset rows, candidate keys, clocks, exact contract membership, radius,
  aggregation, quote validity, controls, labels, folds, models and gates remain
  unchanged;
- sequential Wilcoxon remains `p < 0.0167`; this is not a fourth outcome test
  because V1 stopped before outcomes;
- the rejected V1 manifest and profiles remain immutable evidence and their
  hashes are recorded in the V1R1 manifest.

The 32 repaired pressure fields were checked outcome-free: every ticker-year
cell has at least 158 finite distinct values. No further feature deletion,
addition or relaxation is permitted after this freeze. If V1R1 fails either the
data gate or physical gate, snapshot quote-size pressure is closed without
payoff training.
