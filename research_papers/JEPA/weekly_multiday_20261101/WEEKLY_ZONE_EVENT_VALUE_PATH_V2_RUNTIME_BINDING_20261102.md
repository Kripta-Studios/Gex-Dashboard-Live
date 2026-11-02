# Weekly zone-event value-path V2 runtime binding

Date: 2026-11-02  
Status: `FINAL_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION`

This binding authorizes at most one producer child after independent review and
byte-exact publication. It authorizes no economic interpretation, fitting,
selection, promotion or adoption before the separate V2 auditor passes.

## Frozen implementation

| Authority | Bytes | SHA-256 |
|---|---:|---|
| `build_weekly_zone_event_value_paths_v2.py` | 91,830 | `ed260c55a62fecce729dadce170b5dec5c98049be92580495131e007a7ffd5ab` |
| `test_build_weekly_zone_event_value_paths_v2.py` | 36,127 | `5d92d42c65defa5030c2b8c20d6060b2cabc66d4855decdb2246b9a8a9413d14` |
| `weekly_zone_event_spot_paths.py` | 40,814 | `0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38` |
| `test_weekly_zone_event_spot_paths.py` | 33,144 | `80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb` |
| V2 amendment | 15,276 | `65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146` |
| V2 calendar review | 1,677 | `b8b2080bb1f717f6f68be586cf3c28bd13cd3ea54ece3a427a2830bcdd52d60a` |
| V2 builder final review | 1,867 | `7a1c56c140b03f60cbfbc5ddffd72417d0408640822eca46e99644f16105f7f6` |
| spot final review | 1,486 | `221004483dd77fb5112bbb05ca2ec44191c31cfb19a26815b2950c82e721a140` |

The formal V2 suite passed compile, Ruff and 106 pytest tests. Its exact archive
is `weekly_zone_event_value_path_v2_fixture_archive_02`: manifest 25,384 bytes,
SHA `0ddaddb71c93b3fba333046f980f04478c034e90e79bc6cbc2ec5384e1be6913`;
receipt 978 bytes, SHA `2d529e36702f270ec62834b8133233d355816be71b6ebc00a64e09311d39ef06`;
nested preparation PASS receipt 3,846 bytes, SHA
`23fa4c3468a971596c3fe078246733b92676f5b70289f6eba56dc6622e8b66dd`.
Archive01 is preserved as non-adoptable failed archive evidence because its
root receipt collided with the copied preparation receipt.

## Runtime contract

The exact roots are
`D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_02`
and `...\weekly_zone_event_value_paths_observer_02`; both must be absent at
admission. Journal and `implementation_pins.json` belong under observer02. The
implementation document has exactly ten keys: builder, spot_module,
builder_tests, spot_tests, contract, builder_final_review, spot_final_review,
runtime_binding, launcher and resource_helper.

The launcher must validate the 29 V2 authority inputs: the original 25 plus the
immutable V1 contract and the three retained producer01 exit/failure/journal
records as specified by the amendment. Producer01 remains failed and forbidden
for adoption. The launcher must also verify all repository, fixture archive,
Stage-A and admitted-cache pins, local HEAD equals the remote branch and every
repository byte equals `git show`, before creating roots.

CPU affinity is CPU 0; the ten thread variables equal `1`; CUDA is disabled.
The official RAM/free-commit gate and D: free-space gate of 2,000,000,000 bytes
must pass contemporaneously immediately before the hidden list-argument child.
The handle, PID/creation metadata, logs, journal, exit and closing full pin
rehash are retained. There is no retry or partial adoption.

An exit 0 closes only the producer batch. Results remain uninterpreted and
unusable until the independent V2 audit passes.
