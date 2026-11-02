# D producer: final static review before its first suite

Status: CLEAR_STATIC_PRE_SUITE_D_REVISIT_MECHANICS.

Fresh reviewer `/root/d_producer_mechanics_static_review02` inspected the complete
candidate02 and returned FIX_FIRST for target overflow and four missing fixture
cases. Root preserved that candidate and its findings, made the bounded fixes,
then obtained SHIP after a focal review of the exact diff and all four new cases.

Final pins:

- weekly_zone_revisit_mechanics.py, 38277 bytes,
  4dd7831194be70805028e4c5646d763f907767ad77095d24b5746314afb0f313;
- test_weekly_zone_revisit_mechanics.py, 23950 bytes,
  c8386a3060677e2c6b96a4570f4e2bb08a6fadb533025fcd7b98f98cd94c98ba;
- weekly_zone_revisit_accounting.py, 18783 bytes,
  9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb.

The complete review covered exact input types and foreign keys, plan-local
D/D1/H2 clocks, FSM cross/rearm/reset, first physical ticker/day priority without
rescue, causal ask/trigger ordering, prefix coverage, portfolio integration,
39 event/47 ledger/19 coverage fields and all 39 numeric counts. It checked the
manual four-book quantities, costs and net calculations using artificial values.

The final diff replaces potentially overflowing distance subtraction with direct
center ordering. Additional fixtures cover extreme finite target centers, PUT
STOP with missing bid and exit commission, three physical winning days from one
plan with conservative B lockout, and invalid quotes preserving NO_ENTRY_QUOTE.
The reviewer confirmed the rest of the previous source snapshot unchanged.

Root owns producer integration and its tests under the documented audit route;
the accounting helper and independent auditor have separate implementation lanes.
The independent auditor author must not read this producer or its tests/helper.

No Python import, compile, Ruff, pytest, data decode or real replay was executed.
This approval is source review only. A separately reviewed and byte-exactly
published observed harness, contemporary official resource gates, retained child
closure and closing source pins must precede acceptance of the first synthetic
suite. Real D still requires complete B and C admission and a reviewed adapter.
No market profitability is demonstrated. Goal active; selected_policy=null;
promotion_approved=false.
