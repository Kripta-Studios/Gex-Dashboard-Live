# CROSS_VENUE_CALENDAR_RR native-clock composite V1R1

Status: `PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_COMPOSITE_V1R1`

This is an outcome-free logical seal over two immutable storage generations:

- 3,008 original V1 captures;
- 4 V1R1 exact-key-intersection repairs;
- 3,012 captures / 1,506 ticker-sessions total;
- 7,246,230 quote rows;
- 2,415,402 shared Greek/IV key rows;
- 8 unilateral vintage rows retained as audit-only;
- 0 missing shared keys.

The sealer ran from commit `963f91c9fde298a8820e7dafa55c625f1220f88f`.
It performed offline raw/parquet/manifest reconstruction and did not query the
provider, read underlying outcomes, use 2026 or modify production. The logical
index records `storage_generation` and `storage_root`; no raw capture was copied
or rewritten.

The first attempt from `a352d544` failed closed before creating output because
the audit CSV's RangeIndex was compared with recomputed source indices. Values
and hashes agreed. Commit `963f91c9` normalized only that non-serialized index,
added a regression over all four real repairs and produced this immutable PASS.

## Exact hashes

| Artifact | SHA-256 |
| --- | --- |
| `seal.json` | `5b97ebc5fc867e06ef51d0fcd2956a48a4c06d2291828f5e3ca0e8ae1c9cf84f` |
| `composite_contract.json` | `68714d77ec693028f61b3cf08396ff896ff2415c24f7c21f169872916fd8c046` |
| `capture_index.csv` | `e5a669b7bf5fc17ac1dff62284b9d5c63751554812c0085cf23fc089f1943a0e` |
| `ticker_year_summary.csv` | `41deb0149075908052bfaf8f6069b10ae55760e8cf21639251a5e9fe6cf6df65` |
| `universe.csv` | `98d416ea810c5bde657b6c23a9d7c599885d5eedfef3e332cd1885f6ddee45f4` |

Descriptive source audits report 79 revised bid/ask rows and 135 crossed native
rows across the full V1/V1R1 composite. These are preserved audit facts, not
selection inputs; the eight V1R1 unilateral keys remain excluded.

## Next gate

Do not run the existing full auditor or data-gate builder unchanged. They still
assume one storage root and universal Greek/IV key equality. First make them
consume `capture_index.csv`, resolve each capture through its frozen root and
apply exact `Greek ∩ IV` semantics only to the four predeclared repair IDs.
Then run full audit, version its compact evidence, run the data gate and its
independent audit. No outer 2024 outcome may be opened before those steps and a
committed frozen runner manifest.
