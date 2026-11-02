# D mechanics: first static candidate rejected

Status: FIX_FIRST_STATIC_ONLY. No candidate execution occurred.

The independent read-only reviewer `/root/d_mechanics_candidate_static_review`
inspected the frozen copies in `REANUDACION_20261102/d_mechanics_static_candidate01`:

- `weekly_zone_revisit_mechanics.py`, 33030 bytes,
  `93b7b64ada8c2a052024ce058f7a9db828d33eec93a84f0e5ab03eaa4e944a65`;
- `test_weekly_zone_revisit_mechanics.py`, 7596 bytes,
  `59511b70ade9fa2aaa5bdec5ae4d9785b33e2e0c8c538071fa1a759d0bae20c0`.

Both snapshot hashes were unchanged at review. The host exposes broad filesystem
permissions; the reviewer followed the read-only restriction behaviorally.

The candidate is not executable under its own declared plan interface and does
not implement the frozen full comparison. It must not be published or run as a
ready implementation. The following defects require correction:

1. The scanner reads two entry-window keys absent from the input schema, binds H
   incorrectly to RTH close, rejects historical plans outside the entry window,
   and can confirm exactly at H without two consecutive confirmation minutes.
2. Plan-local D/D1/H2 support, D10:30 availability, physical-plan uniqueness and
   session/date consistency are incomplete.
3. Pre-fill cancellation searches through H before comparing the first ask,
   allowing a later trigger to cancel an entry that should already have filled.
4. The portfolio engine is absent: balances reset per row, several values are
   placeholders, and there is no coordinated four-book chronological queue,
   capital gate, conservative B lockout or WAIT. Zero credit uses unsafe
   truthiness instead of explicit null checks.
5. Events/ledger/plan coverage have 42/49/22 fields instead of 39/47/19. Enums,
   outcomes, superseded ranks, terminal propagation and count units are not the
   frozen schemas. Event-day evidence is always empty.
6. FSM absence states, post-scan trace records, source coverage and applicable
   ambiguity handling are incomplete. An armed sequence without a visit is
   NO_VISIT, not NO_DEPARTURE. No unobserved intraminute path may be invented.
7. The nine synthetic tests encode the wrong horizon and do not cover these
   material temporal, accounting, schema and coverage obligations.

Root independently found the missing portfolio engine, pre-fill lookahead,
historical-plan rejection and schema/horizon defects before accepting this
review. The author received the findings for complete correction, not a limited
formula-only replacement. Original candidate copies remain immutable.

No compile, lint, pytest, harness, real D input, event or economic result exists
for this candidate. Public-interface review and a new complete static review
must precede any observed synthetic suite. B06 remains in its original process;
this rejection does not authorize a rerun or adoption of partial B/C data.

Goal active; selected_policy=null; promotion_approved=false. This is a code
review failure, not evidence of profitable or unprofitable market behavior.
