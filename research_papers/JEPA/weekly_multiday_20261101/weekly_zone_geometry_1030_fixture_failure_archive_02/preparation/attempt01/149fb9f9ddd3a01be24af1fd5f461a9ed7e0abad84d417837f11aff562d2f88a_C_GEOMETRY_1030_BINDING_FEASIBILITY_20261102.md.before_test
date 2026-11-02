# C geometry bindings: physical files versus semantic identities

Status: DOCUMENTARY_CANDIDATE_NON_EXECUTABLE_PENDING_B_CLOSURE.
This note follows C contract c2857254 and draft88f76551 without changing either.
Their references to active B04 are historical: audit04 failed on resources;
audit05 is now the sole running attempt. No partial B state is admitted by C.
The mapping was inspected independently by /root/next_stage_metadata; root
inspected the producer manifest's keys, flags and calendar envelope, not values.

## Identified candidates, not final C authority

Let WB denote D:/GexResearchArtifacts/weekly_multiday_20261101.

| Concept | Actual candidate | Bytes | SHA-256 / state |
|---|---|---:|---|
| producer manifest | WB/weekly_zone_event_value_paths_02/manifest.json | 3134113 | a30376cec17aa649b2869efe1bba8f4a19f901e3a10399942df70c7fe2a42f33 |
| cache admission | WB/weekly_zone_event_value_paths_02/cache_admission.jsonl | 5104757 | e0b4512791adbe70642d8ca83391dd4f0379037aae02f2af4888242bab3b0e14 |
| raw calendar file | WB/h2_boundary_bridge_01/unified_calendar.json | 232573 | be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6 |
| canonical calendar semantic bytes | No separate file; deterministic JSONL representation | 137640 | 13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929 |
| audit manifest | WB/weekly_zone_event_value_paths_audit_05/manifest.json | unknown | PENDING complete PASS/exit/closure |
| final bundle | Proposed real file named below | unknown | PENDING complete PASS/exit/closure |
| final closure review | Future review of complete audit and bundle | unknown | PENDING complete PASS/exit/closure |

The cache identity above comes from sealed producer metadata; this note does
not reopen its contents. The six draft FINAL bindings all remain formally
PENDING until independent B closure, review and publication. The existing
AUDIT05_FINAL_REVIEW is a pre-run implementation review and cannot satisfy
B_FINAL_REVIEW. The producer closure archive manifest2161419b is a producer
bundle and cannot substitute for a final B bundle containing the audit closure.

The original contract's B02_FINAL_VALUE_PATHS_OUTPUT_MANIFEST and the draft's
B_FINAL_PRODUCER_MANIFEST are two roles resolved by the same producer02
manifest.json pin: it already contains the eight output records. There is no
second physical output-manifest. The other B02_FINAL_* symbols map to their
corresponding producer, audit, cache and bundle roles above; this note does not
silently drop a contractual placeholder.

## Calendar resolution

Resolve the ambiguous B_FINAL_CALENDAR binding as two distinct typed objects.
The raw file is a normal file pin. The canonical representation is an explicitly
named semantic digest, without a path and without claiming a nonexistent file.
Both must match the complete producer and auditor calendar_normalization envelopes.

The raw file has schema weekly_h2_boundary_unified_calendar_v1 and2790 rows
of exactly {close_i,date,ticker}, ordered ticker-major QQQ/SPXW/SPY then date.
The canonical copy preserves those triples and orders by date ascending and
ticker ordinal SPY=0,QQQ=1,SPXW=2. Its JSONL is one sorted-key compact UTF-8
JSON object plus LF per row, with no extra fields or blank records. The known
length/digest above are semantic expectations, not output-file hashes. The
canonical first/last identities are SPY:20230103 and SPXW:20260917. These rules
come from the immutable B normalization, not fresh source discovery.

The future C implementation must verify raw file identity, schema, domains,
unique ticker/date keys,930 dates per ticker, identical date sets,24 SHORT and
2766 FULL, then verify exact canonical bytes/digest and preserved close_i.
Use that order for calendar_ordinal. This note does not execute normalization.

## Proposed final B bundle: definition before outcome inspection

After complete audit05 PASS only, create the actual repository file
WEEKLY_ZONE_EVENT_VALUE_PATHS_FINAL_ADMISSION_20261102.json beside this note.
No placeholder JSON is created now. This is a closure artifact, not a new
scientific dataset. Its exact top-level keys will be:

schema, status, producer, auditor, authority_inputs, calendar, flags, data_scope.

schema=weekly_zone_event_value_paths_final_admission_v1;
status=PASS_FINAL_B_ADMISSION; data_scope=SEEN_DEVELOPMENT.
All normal file pins are exactly {path,bytes,sha256}: absolute nominal paths,
integer byte counts and lowercase full SHA-256. Preserve existing nominal
paths and independently check their canonical/physical identities; do not
rewrite producer artifacts. Serialize sorted keys, compact separators, UTF-8,
ensure_ascii=false, allow_nan=false, then one LF. No timestamps are invented.

producer has exactly manifest, outputs, observer. manifest pins the original
producer02 manifest. outputs has exactly these eight keys, each a normal file
pin obtained by projecting the existing producer output record onto the three
pin fields without changing their values: cache_admission.jsonl,
decision_contracts.parquet, option_quote_observations.parquet,
segment_coverage.parquet, source_admission.jsonl, spot_coverage.jsonl,
spot_paths.parquet, summary.json. Row counts remain in the pinned manifest;
the bundle does not reinterpret them. observer has exactly exit,process,journal,
all from WB/weekly_zone_event_value_paths_observer_02. The producer journal
is pinned directly: the auditor records its validated counts, but its final
manifest does not bind that journal's SHA.

auditor has exactly audit,manifest,exit,process,journal. audit and manifest
come from WB/weekly_zone_event_value_paths_audit_05. exit/process come from
WB/weekly_zone_event_value_paths_audit_launcher_observer_05. journal comes
from WB/weekly_zone_event_value_paths_audit_observer_05. Do not substitute the
wrapper's nominal JOURNAL path. A historical process.wait_pending=true does
not contradict terminal exit; the retained exit and journal establish closure.

authority_inputs is the complete unchanged29-entry mapping, exactly equal
between producer and audit manifests. calendar has exactly raw_file_pin,
semantic_jsonl,identity_set_preserved,close_i_preserved. Both preservation
flags are true. raw_file_pin is the raw calendar triple above. semantic_jsonl
has exactly bytes,sha256,order,rows with the known137640/digest,
DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW and2790; it has no path. Each field must
reconcile against both sealed calendar_normalization envelopes.
The bundle has47 file-pin occurrences and46 distinct files. The raw calendar
pin duplicates authority_inputs.unified_calendar and must be exactly equal;
this intentional role duplication is not a second physical input or alias.

flags must equal the complete producer/auditor flags object, not a shortened
claim. Its exact18 keys are actions_read,candidates_read,
context_feature_arrays_read,economic_evaluation_performed,fit_performed,
inference_performed,labels_read,models_read,option_raw_values_read,outcomes_read,
parquet_footers_read,pnl_computed,promotion_approved,replay_performed,
risk_or_qty_computed,selected_policy,spot_cache_arrays_read,technical_ready.
Only option_raw_values_read,parquet_footers_read,spot_cache_arrays_read are true;
selected_policy is null; the other14 booleans are false.

Before constructing the bundle require producer COMPLETE_OUTCOME_FREE_VALUE_PATHS,
auditor PASS, exact schemas/keysets, both retained effective and child exits0,
metadata_error=null,changed_pins=[], correct process identities and complete
consistent journals. Bundle construction rehashes only its explicitly bound
files and compares sealed mappings and closure evidence exactly. Sealed B
output Parquet files are hashed as bytes, without decoding their values.
Do not reopen or rehash upstream option raw files or cache NPZ, reconstruct
paths, or reprobe missing-source paths. Independent auditor PASS, retained
exits and complete journals supply those closure proofs. No partial
reconstruction or manifest-only shortcut satisfies this requirement.

The bundle does not include its own hash, the subsequent review or a future
publication commit. The postclosure independent review pins the completed
bundle and audit evidence. The final C launcher pins bundle, that review and
the published operative binding separately. This avoids cyclic identities.
Actual bytes, hashes, file paths and final publication must replace every
remaining PENDING symbol before any C code/fixtures/runtime.

No new B run, C array read, fixture, model, label, EV or PnL is authorized.
Goal active; selection=null, technical_ready=false,promotion_approved=false.
