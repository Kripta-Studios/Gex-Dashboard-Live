# Weekly zone-event value-path V2R1 audit runtime binding

Status: `FINAL_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION`  
Date: 2026-11-02

One independent audit child is authorized only after byte-exact publication and
fresh gates. No producer rerun, economic interpretation or partial adoption is
authorized. Auditor `audit_weekly_zone_event_value_paths_v2r1.py` is 115,418B,
SHA `ef2bdd340c3e87ce9edd7d9b45b256ece02208646fa7fe095f167b24127a8122`;
tests are 41,783B, SHA
`f291c190833dfe3eff4ccd086e3fe323374f21f582ab9c97aaaa45fca79fe82b`;
final review is 2,509B, SHA
`3c366ebf331e811ada1a58e2f4f701caf1cb250c93b79b703d6c5c0e5682a0b5`.
The formal suite passed compile, Ruff and 91 tests, including actual pinned
metadata admission for all 29 authorities without raw/Parquet reconstruction.

R1 amendment/review pins are `2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3`
and `886c0a83e25a65d8d63aef3ef26b530da984d224613d04139b590b78ac787a17`.
Fixture archive manifest/receipt/PASS pins are respectively
`553fa549a38ca5ce2e7c7e15d07d0b57b1d2ec2d9836e8649eb99e4ee565e431`,
`30a6237620c9cc0b113bee5560548524ba626bed60e9225968c0acad4b2f7025`,
and `1a0c2bb3595f4957dc47359a5ade399fa5a17dc75b653d0986a0463edb1037e4`.

Producer02 manifest/retained exit, all eight outputs, 29 authority inputs and
compact closure archive remain immutable. Failed audit02 is preserved and
non-adoptable via exact exit/failure/journal plus failure archive pins; R1 must
not mutate or reuse its roots.

Fresh exclusive roots are audit03, audit_observer03 and the separate
audit_launcher_observer03. The wrapper verifies local HEAD equals remote and
all repository bytes equal `git show` before roots; it snapshots every pin,
rechecks all producer outputs and failed02 evidence immediately pre-child and
at closure, sets CPU0/TEN=1/CUDA=-1, applies official RAM/free-commit and D:>=2GB
gates, launches hidden list arguments, retains PID/creation/logs/exit, and never
retries. The legacy `value_child_exit_code` evidence field is retained unchanged
as wrapper compatibility metadata.

Only an R1 audit exit0 with complete retained closure may authorize later
interpretation. This binding asserts no economics.
