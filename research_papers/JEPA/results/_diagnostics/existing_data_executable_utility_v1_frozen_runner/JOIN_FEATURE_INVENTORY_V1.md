# Existing-data exact-join audit V1

Outcome-free audit: no executable return, win, label, future price, physical outcome, or 2024/2025 economic metric was read.

Master: `tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet`; 97,625 unique rows; SHA `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.

| Block | Classification | Exact evidence |
| --- | --- | --- |
| `base_pairwise_e0` | `EXACT_JOIN_AVAILABLE` | self/master; one row per (ticker,trade_date,minute) |
| `pairwise_current_time_physics_context` | `EXACT_JOIN_AVAILABLE` | self/master |
| `legacy_live_feature_surface` | `EXACT_JOIN_AVAILABLE` | exact (ticker mapped SPX->SPXW,date,time->minute); no as-of/floor/nearest |
| `wall_state_gex_dex_dgex` | `EXACT_JOIN_AVAILABLE` | exact one-to-one (ticker,trade_date,minute); rows=135,120, unique keys=135,120, multi-keys=0 |
| `h_flow1` | `UNSAFE_JOIN` | touch-event source has one-to-many decision keys and master has no wall_identity; aggregation was never frozen; rows=10,683, unique keys=10,079, multi-keys=598 |
| `h_ivsurf1` | `UNSAFE_JOIN` | touch-event source has one-to-many decision keys and master has no wall_identity; aggregation was never frozen; rows=10,683, unique keys=10,079, multi-keys=598 |
| `h_qsize1r1` | `UNSAFE_JOIN` | touch-event source has one-to-many decision keys and master has no wall_identity; aggregation was never frozen; rows=10,683, unique keys=10,079, multi-keys=598 |
| `h_ibqdyn1` | `NOT_APPLICABLE_BY_CAUSAL_GEOMETRY` | exact one-to-one (ticker,trade_date,minute); event_id is unique but not required; rows=16,926, unique keys=16,926, multi-keys=0 |
| `h_qdyn1` | `UNSAFE_JOIN` | explicitly excluded and REJECTED_DATA_GATE; do not reuse any fields |
| `h_greek2wall` | `SOURCE_MISSING` | BLOCKED_SOURCE_ENTITLEMENT; no direct all-Greeks data exist |
| `executable_option_path_summaries` | `EXACT_JOIN_AVAILABLE` | targets/execution diagnostics only; never alpha |

## Freeze-ready arms

- E0: 30 fields; ordered-list SHA `b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38`.
- E1: 527 fields; ordered-list SHA `e15469c0d1dce8176afd5c7fd48af4c477f830b4fc58651fb982f89fb8986abc`.
- E1 preserves all master rows, prefixes joined fields, leaves source-missing/not-applicable values null, and uses only the two declared applicability flags.
- H-FLOW1/H-IVSURF1/H-QSIZE1R1 are omitted rather than aggregated; H-QDYN1 and H-GREEK2 are omitted entirely.

The full ordered lists and exact source hashes are in `join_feature_inventory_v1.json`.
