# D producer: second static candidate preserved

Status: FIX_FIRST_STATIC_ONLY. No import, compile, lint, pytest or replay ran.

Fresh reviewer `/root/d_producer_mechanics_static_review02` examined immutable
`REANUDACION_20261102/d_producer_mechanics_static_candidate02`:

- producer 38249 bytes, 3006dd46cf6f04dbd34906ebda465cd30f34f7f305a3c9f760ccf3265272765e;
- tests 20320 bytes, e7b90249e9303ad468ddb47738d0295bd12e1b992cee0c60f42f1a175f169538.

The review found that subtracting finite float centers from spot may overflow
to infinity, falsely tying distinct target distances. Direct center ordering
is required: ascending ABOVE, descending BELOW, then cluster ordinal/anchor ID
for actual center ties. Four fixtures were missing: finite extreme ordering,
PUT/BELOW A STOP with missing exit bid and negative commission, three different
physical winning days from one plan, and invalid/crossed quotes preserving the
NO_ENTRY_QUOTE terminal.

The remaining integration was coherent under source review: exact input types
and foreign keys, plan-local clocks, FSM, physical priority without rescue,
ask/trigger causality, prefix coverage, 39/47/19 schemas and count equations.
The hand-calculated example is synthetic, not a market PnL result.

Root corrected only target ordering and added the four fixtures. A focal fresh
review remains required before any observed suite. Original copies remain
immutable. No failed runtime exists for this candidate and no market result
is admitted. Goal active; selected_policy=null; promotion_approved=false.
