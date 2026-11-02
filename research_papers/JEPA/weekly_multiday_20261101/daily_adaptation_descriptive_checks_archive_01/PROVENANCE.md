# DAILY/WEEKLY descriptive check provenance

This archive preserves the evidence that already existed after the read-only
descriptive verification. It does not reconstruct missing receipts, exits,
logs, or source snapshots. No producer, auditor, renderer, fit, inference,
replay, or economic selection was run to create this archive.

## Attempt 01

Runtime root:
`D:/GexResearchArtifacts/weekly_multiday_20261101/daily_vs_weekly_descriptive_verification_01`.
The directory exists and is empty. There is no retained stdout/stderr log,
exit JSON, receipt, resource observation, or script snapshot for this attempt.

The interactive tool transcript, which is not a persistent artifact, recorded
three technical launcher/harness failures before any completed descriptive
calculation:

1. PowerShell `Tee-Object` could not create the requested log because the
   runtime directory did not yet exist: `Could not find a part of the path
   'D:\GexResearchArtifacts\weekly_multiday_20261101\daily_vs_weekly_descriptive_verification_01\stdout.log'.`
2. The first direct invocation stopped at the input-pin check because the
   repository parent was resolved incorrectly: `RuntimeError: Pinned input
   differs: C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\research_papers\JEPA\level_oracle_20261018\launch_monthly_test_index_v2_audit_20261024.py`.
3. After correcting only that path, the invocation stopped while setting the
   Windows affinity mask: `RuntimeError: Could not set CPU affinity to CPU 0`.

These strings are transcribed from the tool transcript for transparency. They
are not claimed to be retained logs or receipts. Intermediate script bytes for
these failures were overwritten in place and were not snapshotted, so they are
not recoverable from the evidence roots.

## Attempt 02

Runtime root:
`D:/GexResearchArtifacts/weekly_multiday_20261101/daily_vs_weekly_descriptive_verification_02`.
Its only retained file is `resource_observation.json`, archived byte-for-byte
as `attempt02/resource_observation.json` (889 bytes; SHA-256
`5a40f4cb7868f318829dbb549a2dcf2e65b433d7e1dcfee456b822eb4000a027`).
It records CPU 0, eight thread variables set to one, the official helper pin,
and a passing resource observation at `2026-11-02T10:06:55.472670+00:00`.

The exact final exception line shown by the interactive tool was:
`RuntimeError: FROZEN_CONTEXT182/base: realized_max_drawdown_usd differs`.
There is no retained stdout/stderr log, exit JSON, receipt, or attempt-specific
script snapshot. The error text is therefore transcript provenance, not a
fabricated persistent record. The technical correction changed the independent
drawdown reconstruction from exit-net accumulation to the ledger's
`equity_realized` path; it did not change or rerun producer/auditor artifacts.

## Attempt 03

Runtime root:
`D:/GexResearchArtifacts/weekly_multiday_20261101/daily_vs_weekly_descriptive_verification_03`.
Its only retained file is `resource_observation.json`, archived byte-for-byte
as `attempt03/resource_observation.json` (889 bytes; SHA-256
`3dc5cedaa0109c966238a74eeee2c719e6968312d752fe23628d40728d3a1b95`).
It records the same controls and a passing resource observation at
`2026-11-02T10:07:10.492060+00:00`.

The exact final exception line shown by the interactive tool was:
`RuntimeError: MONTHLY_RAW/base: monthly_net_usd keys differ`.
There is no retained stdout/stderr log, exit JSON, receipt, or attempt-specific
script snapshot. The error text is transcript provenance. The technical
correction compared the predeclared nine-month grid to
`monthly_net_including_zeros`, preserving the zero February value; it did not
change or rerun producer/auditor artifacts.

## Final attempt 04

Runtime root:
`D:/GexResearchArtifacts/weekly_multiday_20261101/daily_vs_weekly_descriptive_verification_04`.
The two retained files are archived byte-for-byte under `final04/`:

- `resource_observation.json`: 889 bytes, SHA-256
  `2c13003c1b6cc611fc08aa0f61839abfd88b3c2d3e7c949a96c5dc61409e3610`.
- `verification.json`: 36,933 bytes, SHA-256
  `88bc0580ade859e7da2ac1fd3c9f4219d670e7b2af3259c7f1a62498d9b63c41`.

The resource observation is dated `2026-11-02T10:07:24.395800+00:00` and
records CPU 0, eight thread variables set to one, available RAM
15,411,159,040 bytes, and free commit 31,058,911,232 bytes. The verification
receipt reports `PASS_READ_ONLY_DAILY_VS_WEEKLY_DESCRIPTIVE_VERIFICATION`.
There is no separate persistent stdout/stderr log or exit JSON for attempt 04;
the JSON receipt and resource observation are the complete retained runtime
evidence.

The final script content is archived as
`verify_daily_vs_weekly_descriptive_20261102.py` (19,225 bytes; SHA-256
`630c02a4a96911bd0d64ca13db32587e37b9af3da5ec92cc53f12e9eebddc8f9`).
Its live source path at archival time was
`research_papers/JEPA/weekly_multiday_20261101/verify_daily_vs_weekly_descriptive_20261102.py`.
No earlier script version or source snapshot exists in the retained evidence.

This archive is a byte-preservation and provenance record only. Independent
review is still required before describing the descriptive check as finally
archived or scientifically accepted.
