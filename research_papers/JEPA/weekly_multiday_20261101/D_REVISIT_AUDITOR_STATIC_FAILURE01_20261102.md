# Independent D auditor: first static candidate rejected

Status: FIX_FIRST_STATIC_ONLY. No execution occurred.

Read-only reviewer `/root/d_auditor_mechanics_static_review01` inspected the
immutable copies under REANUDACION_20261102/d_auditor_mechanics_static_candidate01:

- audit_weekly_zone_revisit_mechanics.py, 40858 bytes,
  dce9dc4cbdc200e08eeabec1ed79c08287020df09a9e43312c2b4eb5d1329f49;
- test_audit_weekly_zone_revisit_mechanics.py, 7314 bytes,
  cae7bca778b037a37f624e9d6574ff33cf899248e697918fca4888c6b3e6d875.

It read no producer, accounting helper or their tests. Root also identified the
reserve/entry-fee error before requesting the independent review. Required fixes:

1. Reject duplicate plan IDs, separate anchor-ID/cluster-ordinal identity sets,
   validate exact civil ns endpoints, all quote signed-int64 clocks even after H,
   and nonfinite arithmetic results in z+/-2b before emitting finite fields.
2. A valid nonconfirming minute must break CONFIRM_ONE. Rearm clears scalar
   attempt fields; GAP reason is NO_INTERIOR_SAMPLE. Serialize trace after
   terminal annotations. Shared trace-vocabulary ambiguity is resolved only by
   a separately reviewed/published public clarification, not by invented enums.
3. Exact-H confirmation retains option coverage TOO_LATE. ENTRY tie ordering
   includes plan_id before event_id and intent_id.
4. Reserve only principal, not entry fee; expense entry fee once through cash.
   All book arithmetic and equity sums use local Decimal precision1000 and
   Inexact trap. Every qty0 row must retain all four before-balance fields.
5. Apply the complete chronological EXIT/ENTRY order, including ticker and
   ledger-ID EXIT ties and chronological final drain, not insertion order.
6. Recheck coverage/intent/ledger partition equations as output invariants.
7. Ordinary Python equality admits True==1, 1==1.0 and signed-zero drift.
   Strict recursive validation/comparison must enforce exact built-in types,
   schemas, ranges, nullable fields, enums, canonical JSON/Decimal and exact
   float representation before accepting any observed result.
8. The four tests largely audit the reconstructor's own output. Add manually
   calculated accounting/ID/trace/coverage expectations and substantial negative
   cases covering capital/lockout/clock ties, all FSM boundaries, missing fees,
   rounding, geometry/no-trade coverage and future invariance. Fixture clocks
   must use integer arithmetic, not float total_seconds()*1e9.
9. Remove the dead _target stub/unused local and make the corrected code readable.
   No lint outcome is claimed; lint has not run.

The causal first-candidate grouping and no-rescue ordering were structurally
present; this does not rescue the rejected audit. No synthetic or real result
may be adopted from this candidate. Corrected implementation requires fresh
review, publication and observed gated fixtures before acceptance.

The independent-author documentary discovery incident is recorded separately in
D_REVISIT_INDEPENDENT_AUTHOR_SCOPE_NOTE_20261102.md. No producer algorithm was
read by that author. Goal active; no new PnL or accepted model.
