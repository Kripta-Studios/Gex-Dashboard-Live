# H-IBQDYN1 data-gate contract

Status: frozen after the outcome-free tick preflight passed and while the full
capture was still incomplete. No physical label, option payoff or 2026 row was
read to define this contract.

This is the last measurement contract for H-IBQDYN1. It does not authorize a
new data family, feature sweep or post-hoc repair. The only allowed sequence is
full-capture seal, this data gate, the already predeclared F0/F1 physical test
and, only after a complete physical pass, one frozen ask-to-bid economic test.

## Exact F0 controls

F0 has exactly the following 18 causal fields:

- minute sine/cosine and resistance/support role;
- signed and absolute distance to the selected current-day IB/Fibonacci level;
- completed 1, 5, 15 and 30 minute spot returns plus absolute 1 minute return;
- realized volatility of the five and fifteen completed one-minute returns;
- signed distance change and absolute-distance approach over 5, 15 and 30
  minutes.

The selected level is the frozen `nearest_level_name` from the executable quote
source. Its price is reconstructed exactly from current spot and that level's
signed distance. Upper IB/Fibonacci levels are resistance/CALL and lower levels
are support/PUT. F0 may not contain option snapshot state, any closed H-FLOW,
H-IVSURF, H-QSIZE or H-QDYN field, or a missingness indicator.

Realized volatility uses only derived-underlying closes from bars starting
`t-w-1m` through `t-1m`; those bars are complete at the decision. The already
sealed 2,519-session source inventory must be hash-exact and each underlying
file is rehashed before and after use.

## Exact F1 and data gate

F1 is F0 plus the 20 fields frozen in
`H_IBQDYN1_FEATURE_SEMANTICS_CLARIFICATION.md`. Quality counters and conditions,
exchange changes, missingness and eligibility are audit-only.

The dataset preserves all 16,926 opportunity rows. The 74 events that failed
the exact `t-5m` listing proof stay explicit and invalid; they cannot be
replaced. The full capture must contain exactly 33,704 contracts for the 16,852
eligible events, two rights per event, and every raw response, parquet and
contract manifest is rehashed.

`PASS_DATA_GATE` requires all of the following:

- exact executable-source, listing-proof, capture-seal, code and runtime hashes;
- 16,926 unique events, no 2026 date and no outcome column read or emitted;
- finite F0 on every event;
- both-right valid coverage at least 80% in every ticker-year and 85% for every
  ticker, using all frozen events in the denominator;
- at least two finite distinct values for every one of the 20 F1 fields in
  every ticker-year among both-valid rows;
- the F0 and F1 experiments use the identical complete-case mask
  `ibqdyn_both_valid`.

Failure closes H-IBQDYN1 before labels. Passing only authorizes the single
physical LR/LightGBM comparison and is not evidence of alpha or profitability.

