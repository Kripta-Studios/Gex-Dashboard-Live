# CROSS_VENUE_CALENDAR_RR_LEADER_V1 data gate V1R1

Status: `PASS_DATA_GATE`

Executed once from commit `90ffd155292801230d9a20bdb0dc15be03deb34f`
after the composite full audit was committed and pushed.

- sessions / rows: 1,506
- captures revalidated: 3,012
- local-valid / mapped-valid: 1,504 / 1,502
- economic events: 1,478
- source inventory rows: 16,566
- minimum local/mapped coverage: 0.9920634920634921
- minimum distinct states: 237
- maximum zero fraction: 0.012145748987854251
- minimum monthly valid events: 17
- feature view SHA-256:
  `d4335ad85e3242f45dad3708f2a6f571ad8b2f820fa3c66d1cf2e7003a566062`
- manifest SHA-256:
  `492f51c8a80b5e03c453486da185bd6cad85ef1c913a9510366cb19455d0452e`

The only local feature failures are SPY 2024-12-09 and 2024-12-16, both for a
missing persistent signable CALL 25-delta contract. They also invalidate the
mapped SPXW rows because the frozen sensor mapping is QQQ<-QQQ, SPY<-SPY and
SPXW<-SPY. No fallback, as-of, nearest contract or day exclusion was used.

The four V1R1 repair IDs use only their sealed Greek/IV intersections. All
3,008 V1 captures retain exact Greek=IV equality, and no fifth discrepancy is
accepted.

`labels_built=false`, `outcome_accessed=false`,
`underlying_outcome_clocks_read=false`, `outer_2024_opened=false`,
`holdout_2026_opened=false` and `production_modified=false`.
