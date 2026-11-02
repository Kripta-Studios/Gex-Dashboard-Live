# D independent auditor: second static candidate rejected

Status: FIX_FIRST_STATIC_ONLY. No candidate execution occurred.

Fresh reviewer `/root/d_auditor_mechanics_static_review02` inspected:

- auditor 46834 bytes, 5d30e3ce57b9cbfe73a303d90ac9a397e2dfdc5f4f84693b502e9cf3f997e0e7;
- tests 10964 bytes, 0dd7cf1d8d524929a133d4f8d31eb8775c9c35b797a32f501392e2eaf39ef570.

Root preserved exact copies under
`REANUDACION_20261102/d_auditor_mechanics_static_candidate02` before correction.
Required fixes are:

1. Entry debit already includes entry commission. Subtracting debit plus fee
   double-expenses it; reserve must contain principal only. The existing manual
   test incorrectly freezes this defect. Correct BASE fixture post-entry cash
   is 95191.9, principal reserve 4747, exit-fee obligation 61.1.
2. CONFIRMATION_RESET is permitted only from CONFIRM_ONE, not REVISITED before
   the first confirmation minute. Add repeated inner/fringe observations.
3. Reject string subclasses in all scalar/enumeration inputs. Complete exact
   output schema types, ranges, enums, nullability, foreign keys, canonical
   JSON/Decimal and ordering validation for all 39/47/19 columns.
4. Complete count equations: geometry and event-window partitions sum to plans;
   eligible revisit rows equal revisit rows; missing/ambiguous exits cannot
   exceed filled rows.
5. Replace float timestamp construction with integer arithmetic; isolate exact-H
   confirmation rather than retaining an earlier D confirmation. Expand manual
   IDs, four-book snapshots, EXIT/ENTRY ties, capital/lockout precedence,
   no-rescue overlaps, rearm/reset, geometry/no-trade and malformed input cases.

Root also requested removal of semicolon statements and lambda assignments that
would fail default Ruff. This is source inspection, not a lint execution.
The independent author may edit only its own two files using public contracts
and reviewer feedback; producer, accounting helper and their tests remain out
of scope. The reviewer confirmed no forbidden imports or algorithm borrowing.

No import, compile, lint, pytest, real replay or result adoption occurred.
Goal active; no market PnL improvement, selected_policy=null, promotion_approved=false.
