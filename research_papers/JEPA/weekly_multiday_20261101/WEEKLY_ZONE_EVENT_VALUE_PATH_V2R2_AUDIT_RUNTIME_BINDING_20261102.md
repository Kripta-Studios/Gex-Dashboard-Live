# Weekly zone-event value-path V2R2 audit runtime binding

Status: `FINAL_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION`  
Date: 2026-11-02

One independent audit child is authorized only after byte-exact publication and
fresh gates. No producer rerun, economic interpretation or partial adoption is
authorized. Auditor `audit_weekly_zone_event_value_paths_v2r2.py` is 116,851B,
SHA `414d80331301c82404f81e366a63682b029f4f51cc7c0d659e370d6c20886d83`;
tests are 51,396B, SHA
`d02eba1fa017b46e0c22727b13153db6a36e08ed7bd99ff89f1397d232fa6eb4`;
final review is 2,674B, SHA
`0e3be7b719c8e7540630132414ae1ba4b29c9ccdc3bd22f962a25d2746c377d0`.
The formal suite passed compile, Ruff and 104 tests, including metadata29,
three synthetic Parquet prefix cases and duplicate canonical-field rejection.

R2 amendment/review pins are `22be603919cc93b3d6c7342a7e373e62939f58b8b69efec98dc1e5f136ee260b`
and `8cc822668fabb5f51cfc0f114ff8dab7c932af69247eae6f346ab4c7604e1abb`.
R1 amendment/review remain explicit immutable predecessors:
`2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3`
and `886c0a83e25a65d8d63aef3ef26b530da984d224613d04139b590b78ac787a17`.
Fixture archive manifest/receipt/PASS pins are `ea3da7c348d4490db2bcbf5a1de068b150b66ea5eedd4ca6b2b0ab9c4d6586b5`,
`ecebe93f742bcb797a6658a914544f0d94de0827f9d5dd668d29147493ba3b9c`,
and `13a684c979d6b6c2954a8809616d043837f4fbf82d2a2307ae098d0a746e8e85`.

Producer02 manifest/exit, all eight outputs, 29 authority inputs and closure
archive remain immutable. Failed audits02 and03 remain non-adoptable and are
pinned by direct exit/failure/journal plus both failure archives.

Fresh roots are audit04, audit_observer04 and separate launcher_observer04.
The wrapper verifies HEAD=remote and git-show bytes before roots, snapshots and
rehashes all pins pre-child/closure, sets CPU0/TEN=1/CUDA=-1, applies official
RAM/free-commit and D:>=2GB gates, launches hidden list arguments, retains
PID/creation/logs/exit and never retries. Legacy `value_child_exit_code` remains
compatibility metadata. Only a complete audit exit0 can authorize later
interpretation; this binding asserts no economics.
