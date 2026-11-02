# D independent auditor: fifth static candidate and fixture corrections

Status: FIX_FIRST_STATIC_ONLY. No import, compilation, lint or test execution.

Immutable snapshot05 contains auditor67752B,
7bcfc1b5eb47b2f871183f055d6ce6b5d858c8f60d8c148410d7f0d2180108d8,
and tests35574B,03a8d550ef926c03bcba65df32ce49f21790fbe93e6a170cffbe72e098d76887.
Fresh reviewer `/root/d_auditor_mechanics_static_review02` found the bounded
source corrections coherent against the prior full review, but required:

1. Correct two B/ADVERSE manual tuples. At ask1, qty47 and slippage0.02,
   cash95144.9, principal reserve4794, exit-fee obligation61.1 and realized
   equity99938.9 are correct. The tests used the BASE reserve4747 and wrong
   equity99891.9. The source already computes each cost book separately.
2. Mutate only expiry_date to the ISO week-date string2026-W01-1 in the
   canonical-date regression. Changing trade_date while leaving civil endpoints
   unchanged lets the old parser reject for the unrelated clock mismatch.
3. Require AuditError for malformed trace hex such as not-hex, which distinguishes
   normalized parser rejection from the old raw ValueError. NaN alone is also
   rejected by later full-output comparison and does not isolate that fix.

The reviewer found the other mandatory capital, B-lockout, equal-time exit/entry,
physical-winner-no-rescue, Decimal-context and overnight cases coherent.
Separately, root source-only regex inspection found remaining single-line
control suites in both files that would violate default Ruff E701. The author
must expand those suites without changing control flow or algorithms. No Ruff
was executed and no runtime failure is claimed.

The author may correct only its two owned files. Producer/accounting/integration
code and their tests remain excluded. All previous candidates are preserved.
No independent auditor PASS or economic result exists. Goal active.
