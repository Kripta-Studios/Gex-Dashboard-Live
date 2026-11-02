# V2R1 audit attempt03 closed at historical footer admission

The single real V2R1 audit launched from published/remote-verified
ed8f71b63002b1f3ddb0da193892d25c1236ef84,41 exact files, failed and is closed.
Root session50917 returned exit1 via retained toolb5c0fa. Child PID3448,
creation1793629377.7723744, started2026-11-02T14:22:57.770849Z and returned
exit1 at14:23:15.027984Z, elapsed17.257152099999075s. No metadata error or
changed pins. The failed03 observers must not be reused; output03 is absent.

The Stage A correction passed real admission. Calendar normalization completed
with unchanged2790 identities and canonical digest13bc456a. The code then
validated producer02 manifest/implementation/journal and reached the first
historical footer: QQQ_20230106_20230103_greeks.parquet. It failed at
reconstruct_sources line1554 with historical footer projection. Journal has
eight rows: admission and normalization pairs, outer and first-file footer
STARTED, then first-file and outer ERROR. No selection, option value streaming,
spot reconstruction, audit result, fit or economic replay was reached.

The raw file was hashed and its first footer opened during this failed audit.
Subsequent diagnosis was code and compact metadata only; it did not reopen raw
Parquet/NPZ. The auditor compares all stored schema fields in physical order
against an authority that stores a deliberate ordered projection. Producer02
uses schema_descriptor(schema, projection), where the projection is the
declared identity/value column order. The historical descriptor for this file
has16 fields. This is a second integration defect; the first R1 correction
remains valid. It does not establish numerical value correctness or an edge.

Read-only diagnosis by /root/value_paths_auditor reconciled2784 source-admission
rows against the compact authorities without differences in authority lists,
binding kind, projected schemas, Stage A stats or identities. Population is
2765 HISTORICAL/3 FIRST_AUTHORITY/16 MISSING. The historical metadata has three
variants:1454 large_string native16,1203 large_string proxy15,108 string native16.
First-authority full-schema descriptors have one variant across three files.
No other current metadata incompatibility was found. This is not a replacement
for the stopped independent value audit.

Exit357B/SHA1c875a80a7265d39e331da010f26cb8cabaa6c767f42cdc673f5ce5e3f196776;
failure305B/SHA32b88636a1915b41beeb3541be245a02d2597bee79e477fb26a014367d6841c3;
journal4636B/SHA128ecab9a92c99a68382c45abc61b8c248b7df5e4c6ef51f64e4dbf583d09352.
Archive weekly_zone_event_value_path_v2r1_audit_failure_archive_01 contains
ten exact copies/68905B,12 total files. Manifest8246B/SHA
f859a148c7cb1a5237db1dff78b75cf05727036d69a3fbaf5a417aa028e7dda1;
receipt545B/SHA0c6e6739858564b4aa1c34ea305f1dfba9ed00134b4cc2875a3c0440d36f1ab6.
Pre-child CPU0/TEN1/CUDA-1 and official RAM11352395776/free_commit11134111744/
disk26214191104 bytes passed. This is not a resource block.

Next bounded proposal is a separately predeclared R2 helper that derives the
historical projection from the original contractual identity/value sequence,
then compares actual footer types and that exact order to the pinned descriptor.
Do not reuse the auditor batch-reading column order. Change only the
historical comparison; retain the full-schema signature elsewhere, selection,
streaming, masks, clocks, output schemas, counts and equality rules. Regressions
must use the three real metadata shapes with reordered synthetic Arrow columns
and extras, plus missing/type/descriptor mutations, and exercise the actual
comparison path. No producer rerun or permissive schema fallback. This proposal
has no implementation or execution authority yet: amendment/review/publication,
new code/tests/fixtures/reviews/binding and fresh roots are still required.

Producer02 and failed02/03 evidence stay immutable. C geometry remains a
non-executable design. No new profitability result; goal active,
selection=null, technical_ready=false, promotion_approved=false.
