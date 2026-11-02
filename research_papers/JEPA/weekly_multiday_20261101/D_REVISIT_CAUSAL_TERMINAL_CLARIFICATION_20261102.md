# D revisit mechanics: causal terminal and pre-fill closure

Status: PREOUTCOME_CANDIDATE_REQUIRES_INDEPENDENT_REVIEW_AND_PUBLICATION.
No real D event, trade, label or outcome has been read or calculated.

## Observed ambiguity and authority

The frozen scientific draft4ea0fe7b defines H2 at10:35 NY time and prohibits
extending the horizon. Its section6 describes confirmations or first asks at or
after that terminal as TOO_LATE. The operative addendumc5671160 section5 makes
absence labels mature at horizon_end, prohibits later reasons from changing an
already closed terminal, and section9 requires future-mutation invariance.

Without an explicit observation cutoff, a later H2-afternoon quote could change
NO_ENTRY_QUOTE, or a later spot could change NO_CONFIRMATION, after the declared
label maturity. Likewise a batch implementation could classify a prior zone
trigger as PRE_FILL_TRIGGER_CANCELLED only if a later ask eventually exists.
Removing that later ask would then change a label whose claimed maturity is the
earlier trigger. Those readings conflict with the user's causal objective.

This pre-outcome clarification fixes those two implementation ambiguities. It
adds no threshold, horizon, arm, cost, market selection or outcome-based rule.
The original draft/addendum remain immutable and are read together with this
explicit correction after independent review and publication.

## Economic terminal and observation support

H is exactly the plan's original horizon_end:10:35:00 NY-naive on H2, the third
admitted trading session D/D1/H2. H is not the RTH close and not D1. The plan's
three session identities and their admitted RTH bounds remain explicit inputs;
weekends and SHORT sessions are not inferred from elapsed calendar days.

For that plan, D mechanics consume observed samples from their causal start
through H inclusive. Samples strictly after H cannot affect its transition
trace, event IDs, terminal reason, coverage, label, economic intent or ledger.
The same physical sample may remain eligible for a different still-active plan;
there is no global truncation of the ticker's stream.

A first confirmation exactly at H is recorded for coverage, with its event ID,
and is TOO_LATE to create an economic intent. A first valid ask exactly at H
likewise cannot fill. Samples later than H do not reopen absence terminals.
If there is no confirmation by H, retain the appropriate terminal of the state
machine: NO_VISIT, NO_DEPARTURE, CROSS_THROUGH, NO_REVISIT, NO_CONFIRMATION or
NOT_EVALUABLE. They are not collapsed into a single absence class.

Existing filled-position rules are unchanged: A zone triggers must be strictly
after fill and strictly before H. Its permitted exit bid is strictly after the
trigger and at or before H. B uses the valid bid exactly at H. If A has no earlier
zone trigger it also uses the H2 timeout convention. Missing exit accounting and
label maturity remain H; observed bid0 is distinct from missing bid.

## Pre-fill cancellation is an observed event

For a winning, in-window confirmation before H with a valid target, process
subsequent spot/quote observations in timestamp order. Before fill, the first
observed stop/target at a time strictly after confirmation and strictly before H
cancels immediately. Its maturity is that trigger time, whether or not a valid
ask appears later. At an equal eligible timestamp the zone trigger takes
precedence over the ask, as already required by the conservative pre-fill rule.

If no earlier trigger has cancelled and no ask has filled before H, a valid
first ask exactly at H yields TOO_LATE with maturity H; otherwise the absence
terminal is NO_ENTRY_QUOTE with maturity H. A spot trigger exactly at H does not
replace that terminal, since the economic entry window has closed. Quotes or
spots after H cannot revise it. No missing or cancelled entry produces a ledger.

Target/stop construction, same-contract quote validity, fixed quantity and
common A/B portfolio admission remain as predeclared. A quote is admissible only
when the inherited B quote-validity condition holds: finite0<=bid<=ask, ask>0.
Bid0 is admissible when that condition holds. Invalid source observations remain
in coverage but cannot supply an entry or exit price; no nearest or forward fill.

## Total terminal precedence for confirmed candidates

Compute every confirmation's identity, side, stop and available target, and the
predeclared physical ticker/day ordering from confirmations observed within each
plan's support. Keep all candidates and their ranking metadata. The terminal
reason is resolved in this order:

1. A nonwinner is SUPERSEDED_FIRST_EVENT; another zone is never rescued.
2. A winner outside the fixed entry-evaluation window is OUTSIDE_EVALUATION_WINDOW.
3. A winner confirmed exactly at H is TOO_LATE.
4. A remaining winner without a valid target is NO_TARGET.
5. Otherwise use the causal pre-fill event ordering above. Only an eligible ask
   before H creates an intent and reaches the already frozen quantity/portfolio
   admission precedence: qty0, then OPEN_POSITION, then CAPITAL_BLOCKED, then fill.

These branches determine reporting and causal maturity; they do not inspect net
results, later winners or later prices to rescue a candidate. FIRST_PHYSICAL
ordering and one terminal confirmation per plan/anchor remain unchanged.

## Verification before any real integration

Synthetic fixtures must mutate, append and remove post-H observations without
changing the completed plan result; retain exact-H boundary tests; and remove or
alter later quotes after a pre-fill cancellation without changing that event,
its reason or maturity. Include two overlapping plans whose different H values
ensure plan-local support, missing ask, valid bid0, crossed/invalid quote pairs,
and preserved distinct absence states. The independently authored auditor must
reconstruct these rules without producer helpers.

This note requires review/publication before either implementation is accepted
or a formal suite runs. Real D still requires full B/C admission and the separate
real adapter, binding, integration fixtures and runtime gates. All current inputs
and diagnostics are artificial. No profitability claim follows.
