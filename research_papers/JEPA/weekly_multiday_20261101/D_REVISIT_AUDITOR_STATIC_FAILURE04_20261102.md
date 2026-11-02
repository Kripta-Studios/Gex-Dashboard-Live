# D independent auditor: fourth static candidate requires bounded corrections

Status: FIX_FIRST_STATIC_ONLY. No import, compilation, lint or fixture ran.

Fresh reviewer `/root/d_auditor_mechanics_static_review02` inspected immutable
snapshot04 against public interface662147, trace27c5, draft4ea0,
addendumc567 and causal clarificationde8f:

- auditor66988 bytes, 6f3a7005b253d9f08d13bf10a0141c39e80614fc2ce3b15d4e06b11779a1969a;
- tests21537 bytes, 01f9c6f403e1fc713067a6c3d1b753595631d3a0194cdc38e4913198dfc80b6b.

Required bounded corrections:

1. Exact Gregorian YYYY-MM-DD validation: length/ASCII plus fromisoformat accepts
   alternate ISO week forms such as2026-W01-1. Require separator/digit structure
   and parsed.isoformat()==input before propagating dates.
2. Config values require exact built-in strings, not equality-only acceptance.
   Anchor provenance pins require their own strict pin validation before equality
   with the plan pins; equality-compatible objects must fail.
3. Trace spot_f64 parsing must catch ValueError/OverflowError as AuditError,
   reject nonfinite nan/inf and require canonical finite float.hex output.
4. The session-boundary fixture starts with an earlier D10:35 confirmation.
   Neutralize that sequence so the later close/open observations are reachable.

The reviewer found the previous substantive corrections coherent: principal-only
reserve, single entry-fee expense, CONFIRM_ONE-only reset, strict enumeration
strings, lexical ledger projection, output validation, count partitions and
chronological queue structure. This is source inspection, not runtime proof.

Root had independently requested completion of manual capital-exhaustion,
B-lockout, EXIT/ENTRY-tie, physical-winner-no-rescue and Decimal-context cases;
these known missing tests were not the reason for the review rejection. The
sole independent author may now correct the listed source defects and complete
the tests. It remains prohibited from reading producer/accounting code or tests.

All earlier candidates and failures remain preserved. No real B/C/D data,
market PnL or model acceptance results from this review. Goal active;
selected_policy=null; promotion_approved=false.
