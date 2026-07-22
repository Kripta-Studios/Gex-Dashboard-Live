# CROSS_VENUE_CALENDAR_RR composite full audit V1R1

Status: `PASS_COMPOSITE_CAPTURE_AUDIT_V1R1`

The one-shot offline audit ran from commit
`2b33fe5af1b3994efbb04fe807e944d333dbb825` and independently consumed the
sealed multi-root composite without network or outcome access.

## Revalidated scope

- 3,012/3,012 captures and 1,506 ticker-sessions;
- 7,246,230 native quote rows;
- 1,369,860,204 raw bytes and 102,236,252 parquet bytes;
- 6,024 vintage Greek/IV source files inventoried;
- 2,415,402 shared Greek/IV keys;
- 2 Greek-only plus 6 IV-only rows, all confined to the four frozen repairs;
- 0 missing shared keys;
- 8 native extras, 79 revised bid/ask rows and 135 crossed native rows retained
  as audit facts.

The capture revalidation dataframe has the same canonical SHA-256 as the sealed
composite index: `e5a669b7bf5fc17ac1dff62284b9d5c63751554812c0085cf23fc089f1943a0e`.

## Exact file hashes

| Artifact | SHA-256 |
| --- | --- |
| `audit_summary.json` | `437483b0489d54534666b8f8e9f4fe59eb986f1bec2459dfa71018de7aff4769` |
| `capture_revalidation.csv` | `89f28857baeb40f6d4ce82ee574294fef3f274f2390594645d10d11ce4ba0163` |
| `ticker_year_summary.csv` | `ebd508d42bc24959434a426332a2f2cc878cab3587d54b03c90b7bcf97335d6e` |
| `vintage_source_inventory.csv` | `1ca51c14f9bf348c852f5a93ba4a8febc769a515d740b5fe345a9ea0eb140240` |
| `seal.json` | `5b97ebc5fc867e06ef51d0fcd2956a48a4c06d2291828f5e3ca0e8ae1c9cf84f` |
| `capture_index.csv` | `e5a669b7bf5fc17ac1dff62284b9d5c63751554812c0085cf23fc089f1943a0e` |
| `composite_contract.json` | `68714d77ec693028f61b3cf08396ff896ff2415c24f7c21f169872916fd8c046` |
| `universe.csv` | `98d416ea810c5bde657b6c23a9d7c599885d5eedfef3e332cd1885f6ddee45f4` |

Flags remain `outcome_accessed=false`, `underlying_accessed=false`,
`outer_2024_opened=false`, `outer_2025_opened=false`,
`holdout_2026_opened=false` and `production_modified=false`.

## Next action

Commit and push these compact artifacts and the updated handoffs. Only then run
`build_cross_venue_calendar_rr_leader_v1.py` once at its default immutable V1R1
output. That builder may read underlying only at 10:30/10:35 and must not read
the 10:36/13:36 outcome clocks. A PASS data gate still requires an independent
audit and a committed frozen runner before outer 2024 can be opened.
