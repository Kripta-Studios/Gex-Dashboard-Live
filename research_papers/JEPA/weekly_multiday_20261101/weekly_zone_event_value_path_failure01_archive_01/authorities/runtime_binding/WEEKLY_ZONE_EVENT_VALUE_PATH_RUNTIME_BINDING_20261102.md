# Weekly zone-event value-path runtime binding

Date: 2026-11-02  
Status: `FINAL_BINDING_REQUIRES_BYTE_EXACT_PUBLICATION_BEFORE_ONE_RUN`  
Scope: one producer child only. It may materialize value paths; it does not authorize economic interpretation, fitting, selection, promotion or adoption before the separate independent audit passes.

## Frozen implementation and synthetic-suite evidence

| Authority | Bytes | SHA-256 |
|---|---:|---|
| `build_weekly_zone_event_value_paths.py` | 83,817 | `b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe` |
| `weekly_zone_event_spot_paths.py` | 40,814 | `0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38` |
| `test_build_weekly_zone_event_value_paths.py` | 28,614 | `ea5c7d0b0848e3cc4dc8fc6a9ac0e59505bf9e5244cbd775308a81b682ae72aa` |
| `test_weekly_zone_event_spot_paths.py` | 33,144 | `80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb` |
| `WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md` | 36,466 | `e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9` |
| `WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_REVIEW_20261102.md` | 2,340 | `ad118946f30d0681770c25840a4f40d89941030688882b74e23350d098b6b185` |
| `WEEKLY_ZONE_EVENT_VALUE_PATH_BUILDER_FINAL_REVIEW_20261102.md` | 1,381 | `b53b88a4991c752418732decc10a25ec6c5ec564607bc2a05cacf4ba06f8c47e` |
| `WEEKLY_ZONE_EVENT_SPOT_PATH_FINAL_REVIEW_20261102.md` | 1,486 | `221004483dd77fb5112bbb05ca2ec44191c31cfb19a26815b2950c82e721a140` |
| fixture archive `manifest.json` | 67,117 | `f4fae5286863eb7e1971f5efde3d74a3c92b9cde4c8d32ab0826fbcd580a90bd` |
| fixture archive `receipt.json` | 1,068 | `23d9473a919709aba883823e392ecede85713dd1b36573f1fbb64f6c953a676b` |
| archived `attempt03/receipt.json` | 4,397 | `fcc9aabf079747499d2aac231b6ceb6763a644e12525d741e58b4d41cef1c02a` |

The archive root is
`research_papers/JEPA/weekly_multiday_20261101/weekly_zone_event_value_path_fixture_archive_01`.
It contains 80 byte-exact source copies totalling 997,692 bytes, plus its manifest
and archive receipt. The preserved sequence is attempt01 failure at Ruff,
attempt02 failure at pytest, and attempt03 PASS with compile 0, Ruff 0 and
pytest 95 passed.

## Intended one-run interface

The reviewed launcher must invoke exactly:

```text
C:\Program Files\Python314\python.exe -X utf8 -u \
  research_papers\JEPA\weekly_multiday_20261101\build_weekly_zone_event_value_paths.py \
  --execute-reviewed-builder \
  --output-dir D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_01 \
  --observer-dir D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_observer_01 \
  --journal D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_observer_01\journal.jsonl \
  --implementation-pins-json D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_observer_01\implementation_pins.json
```

Both output and observer roots were absent when this binding was finalized and
must still be absent at launcher admission. The wrapper
alone creates the observer root. The builder requires the output root absent and
the wrapper-created observer directory present. No resume, retry, partial
adoption, fit, API access or broker access is authorized.

The wrapper must set CPU affinity to CPU 0 and set the ten thread variables to
`1`, with `CUDA_VISIBLE_DEVICES=-1`, before scientific imports. It must verify
and persist actual affinity and environment state, run the official resource
gate and the `D:` free-space gate of at least 2,000,000,000 bytes immediately
before `Popen`, use a hidden list-argument child, retain its handle through
`wait()`, and preserve process, logs, exit and closing-pin evidence.

## Required ten-key implementation pin document

The builder accepts exactly these keys, each with absolute `path`, integer
`bytes` and lowercase `sha256`:

1. `builder`
2. `spot_module`
3. `builder_tests`
4. `spot_tests`
5. `contract`
6. `builder_final_review`
7. `spot_final_review`
8. `runtime_binding`
9. `launcher`
10. `resource_helper`

## Admission and closure

The launcher must pin this binding, both final reviews, the implementation and
tests, the contract and review, the 80-copy archive manifest and receipt, the
attempt03 PASS receipt, the resource helper, the fixed Stage-A authorities and
the fixed admitted cache metadata. It must verify every repository authority is
byte-exact at local `HEAD`, that `HEAD` equals the remote branch head, and that
every external authority remains byte-exact before it creates the observer or
launches the child. It must revalidate all pins immediately before `Popen` and
again at closure.

The output is a single bounded producer batch. Source workers remain under the
builder's per-source CPU 0 and resource-journal discipline. Partial outputs are
never authorized for adoption. A child exit 0 is only producer closure; it is
not an audit PASS and conveys zero economic conclusion. No profitability,
eligibility or future result is asserted by this binding.

The final launcher and this binding require independent runtime-package review
and exact publication before the single run. Until publication is verified,
neither runtime root may be created.
