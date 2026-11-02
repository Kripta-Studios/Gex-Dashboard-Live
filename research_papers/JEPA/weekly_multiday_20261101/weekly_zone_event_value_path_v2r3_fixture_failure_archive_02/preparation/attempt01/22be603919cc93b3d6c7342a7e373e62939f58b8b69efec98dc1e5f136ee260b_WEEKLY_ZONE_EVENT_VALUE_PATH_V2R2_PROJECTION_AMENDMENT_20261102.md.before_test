# V2R2 independent audit: historical schema projection correction

This bounded operational amendment follows the closed audit03 failure and
review in WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_FAILURE_20261102.md and
WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_FAILURE_REVIEW_20261102.md. Producer02,
failed02/03 and V1/V2/V2R1 implementations stay immutable. There is no audit
output to resume. This amendment changes neither the research population nor
any model, scenario, execution or economic rule.

## Exact correction

The original B contract stores a historical projected_schema, not the physical
full Arrow schema. R1 erroneously compares all stored columns against that
ordered projection. R2 must independently derive the canonical projection
from these exact contractual sequences, filtered only by physical presence:

- Identity: symbol, expiration, trade_date, strike, right.
- Value: timestamp, underlying_timestamp, interval_used, underlying_price,
  bid, ask, delta, implied_vol, gamma, theta, vega, rho.

The new pure helper returns ordered name/type records from actual Arrow field
types. It must reject ambiguous duplicate projected field names. Existing
validate_option_schema remains mandatory before this comparison and continues
to reject absent required columns and inappropriate numeric types. Compare
the resulting list exactly with the pinned historical descriptor, preserving
field order, type strings and schema shape. Do not sort, compare sets, follow
an arbitrary supplied order, ignore type differences, accept full-schema
fallbacks or reuse the different batch-reading projection order.

Only the historical comparison in reconstruct_sources changes. Keep its
byte/SHA/row-count checks, footer reading, resource gates and final2784/2768
population gate unchanged. Keep parquet_schema_signature, its
scan_option_source caller, first-authority full_schema validation, selection,
clocks, masks, row ordering, schemas, streaming and all closing checks intact.
No producer/spot imports or reuse of producer computations are permitted.

## New identities and invariant proof

Use new audit_weekly_zone_event_value_paths_v2r2.py and
test_audit_weekly_zone_event_value_paths_v2r2.py. Preserve29 scientific PINS
and10 producer implementation identities exactly. Keep the R1 admission fix
and its separate amendment pin; add this R2 amendment as another separate
implementation pin verified before authority admission. AST comparison against
frozen R1 must permit only the new projection helper and changed admit_pins
(new amendment pin) and reconstruct_sources (historical comparison). Runtime
path/test identities and the two contractual column constants may change.

New real roots under D:/GexResearchArtifacts/weekly_multiday_20261101 are
weekly_zone_event_value_paths_audit_04,
weekly_zone_event_value_paths_audit_observer_04 and the wrapper's separate
weekly_zone_event_value_paths_audit_launcher_observer_04. Producer02 remains
the sole input. Failed03 observers are evidence, never reusable roots.

## Required regression evidence before a real audit

Retain the R1 suite and its actual29-authority metadata integration. Add three
real synthetic Parquet prefix tests: native large_string16, proxy large_string15
without timestamp, and native string16. Write one synthetic row with extra
nonprojected columns and a deliberately noncanonical physical column order.
The fixtures represent metadata shapes, not the unobserved full physical
schema of the failed historical file. Prove the old full signature differs
from the exact canonical descriptor and the new helper matches it.

Exercise reconstruct_sources itself on the single temporary synthetic source,
using real bytes/SHA/row count and actual Parquet footer. Only redirect
SOURCE_ROOT to the temporary root; do not substitute file_pin, sha256_file,
guard_file, pq.ParquetFile, schema validators, comparison functions or the
population constants. Bind the existing official resource helper in the
formal fixture environment. The positive prefix must reach exactly the final
AuditError('source population') after passing admission. Catching any other
error is failure. This verifies the corrected path, not a full-population PASS.

Negative prefix tests must fail before that sentinel for missing required
columns, wrong numeric types, altered expected field order or type, and a
malformed/duplicated expected descriptor. Assert specific applicable errors.
Keep separate coverage that full_schema and scan_option_source behavior did
not change, including an AST invariant against R1.

A metadata-only assertion may use the already admitted three historical
inventories to deduplicate exact paths, reconcile duplicate descriptors, and
check2765 present historical projections:1454 native large_string16,
1203 proxy large_string15,108 native string16, all in canonical order. This
reads only the existing29 pinned authorities, not source_admission, raw
Parquet/NPZ, candidates, outcomes or producer value tables. No new authority
discovery or scientific file is admitted by these fixtures.

## Operational sequence and limits

Publish this amendment and its review before implementation/fixtures. Then
publish reviewed new code/tests and fixture launcher; retain one formal suite
with CPU0, ten thread variables1, CUDA=-1, official RAM/freecommit>=2GB and
disk>=2GB gates, hidden list-argument children, handles/logs/exits/snapshots.
Preserve failures and stop; no automatic retry or stale gate substitution.
Passing fixtures require final review and a separate reviewed/published real
binding/launcher that also pins failed03 evidence before one fresh audit04.

This amendment permits preparation after publication, not a real-run GO.
No producer rerun, partial audit adoption or C geometry execution. No events,
labels, fits, probabilities, EV, PnL, API, broker or production actions.
Goal active; selection=null, technical_ready=false, promotion_approved=false.
