# Independent audit of the nine short-session extension

Fixed before this auditor runs: reconstruct all six frozen policies on the nine
2025 short ticker-sessions, given their sealed h0/h1 scores. No fits, inference,
selection refresh or producer imports. Reuse the independent original auditor's
hash, comparison and economic aggregation primitives. Independently implement
the short horizon scheduler: decisions60..195, fills exit<=205, close210;
strict threshold, lower action ID ties, NO_FILL retries next minute without
changing h, a fill changes h to1 and resumes exit+1. Recompute ask-to-bid costs
from source labels (one contract100 multiplier, commission2.60, slippage .01/.02
each side, liquidation floored at zero); audited labels remain the authority for
barrier detection and raw quotes, which this audit does not independently replay.

Require the original audit PASS and its exact hash, fixed models/selection,
source dataset audit/index binding, exact73-member final closure, all source
manifest hashes, prediction identity/schema/finiteness and prediction-before-daily
checkpoint ordering. Reconstruct the nine attempts/ledgers and compare every
column. Verify old741 attempts/ledgers against the original independent audit;
do not reconstruct old scores again. Recompute short9 and union750 summaries,
monthly results, six calendars and gates. Independently obtain the exact250
XNYS sessions in2025, including three short dates; require750 unique ticker-days
and exact preservation of the old4446 policy/calendar rows.

Synthetic fixtures precede execution: horizon bounds, strict ties, NO_FILL/h
transitions, no same-minute replacement, cost floor, score identity mismatch,
closure corruption and calendar duplicate/missing rejection. Report PASS only
given sealed scores; no raw feature/quote recomputation, independent refit,
reinference or live receipt claim. Retain a separate audit root and final input
rehash. The already selected residual5 stays selected even if economics fail.
