# C auditor wrapper: first static review

Verdict: FIX_FIRST. No fixture or real C execution occurred.

Fresh independent reviewer `/root/c_audit_wrapper_static_review` inspected the
four candidate files after parent inspection. The immutable snapshot is
`c_audit_wrapper_pre_suite_candidate01`; its manifest SHA-256 is
71cc3cd57cdd08ebd92db54239f842f76131ae234ed1d2d4c202c74a54ae57c9.

Reviewed launcher: 29480 bytes,
44efe3f7cd02abb8970d502bf2ce61d3d258cdf3c8b2f22ca82e204dbb7165f3.
Tests: 14546 bytes,
bb91afcb64ffb339b289bb6d71bad0913492998a636075583ae4c65badb43326.
Contract: 6148 bytes,
52bca4508587de08867e0c68c118a97a01f01ada5a170d20795f3043fe6fe1f5.
Harness: 15062 bytes,
0563cf8c548a8d7c4bdc4ec8ab9ff370f983091aea308d6b7d2575a488956746.

Required corrections:

1. Cross-check binding calendar/cache pins against admitted final B; enforce
   immutable canonical authority and engine pins before a child can start.
2. Anchor producer manifest, output members, journal and process/exit mirrors
   to the designated producer output/observer roots.
3. Reject coerced row counts, require exact integer types, and validate counts
   and contract crosslinks in the producer manifest.
4. Make the mirror-negative fixture reach the mirror check; add positive
   binding admission and process.json-write failure with retained wait/exit.
5. Correct the documentation: the wrapper starts one canonical auditor child
   after admission. The publication receipt is a derived object with only its
   nested exit path repinned; only the exit copy is byte-exact. Remove stray A.

These are preparation/integration findings, not economic evidence. The
approved C producer wrapper and 13-pass closure, C science 69-pass suite, and
R3 136-pass suite remain immutable and were not repeated. B06 was untouched.
Review was behaviorally read-only under danger-full-access/disabled host
policy, with no Python/imports, lint, tests, runtime or Git mutation.
