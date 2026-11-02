# B06/R3 resource-wait implementation: static review

Date: 2026-11-02. Status: `CLEAR_STATIC_PRE_SUITE`.

Final independent reviewer `/root/daily_producer_review` returned SHIP for refreeze4. Earlier verdicts with an incorrect RuntimeError assumption are superseded. Root accepts the corrected verdict after reading the auditor delta and helper implementation; no formal suite has yet run.

Exact scope:

- `bounded_resource_wait.py`: 17,926 bytes; SHA-256 `33873bfab0549f390cd3973ab3d9af07a19d5df643f44d483bd17c74140c07a9`.
- `audit_weekly_zone_event_value_paths_v2r3.py`: 120,016 bytes; SHA-256 `effc36ce5cc496698f9aca1ea496046c89ca0d8e0deabe3f354dd892a94a5643`.
- `test_audit_weekly_zone_event_value_paths_v2r3.py`: 51,568 bytes; SHA-256 `1988d35201c102c9166bd1ed03ff4dde20c49cd1bdc89dc251beeeb8597a531d`.
- `test_bounded_resource_wait.py`: 18,185 bytes; SHA-256 `5ef18abcad8fb1a8653b447da404311d5199a423a6c6f62de2dce2c26962342a`.

The implementation preserves the scientific reconstruction of R2/attempt05. Changes are roots06, exact official helper binding, bounded pre-unit waiting, external wait evidence, and moving the source stat/observation-Parquet opening behind their own unit gates. The monotonic budget is 600 seconds with at most five-second sleeps; the 2 GB thresholds are unchanged.

Review closed: all relevant gate callsites including manual CACHE_SPOT_PATH; no pre-gate source stat or observation-Parquet opening; strict canonical wait-record schemas/types/timing/references; global rejection of records after TIMEOUT/INTERRUPTED; durable writes and stable evidence hashing; and actual official exception compatibility.

The pinned official helper raises exactly `ValueError("2GB RAM/commit gate unmet")`. Only that exception combined with a structurally valid numeric RAM/commit deficit is waitable. Other exceptions remain fatal. The focused tests bind the actual pinned official gate and call it with artificial dictionaries, without calling its observation function. This replaces an earlier incorrect RuntimeError stub; no runtime using that stub was launched.

Other artificial fixtures cover threshold equality, individual/combined deficits, recovery, timeout with an injected clock, interruption, malformed observations, disk/helper/fsync errors, truncated evidence, callsite ordering and scientific AST equivalence. The inherited R2 suite remains a required part of formal validation.

Scope is implementation-only. Compile/Ruff/pytest require their reviewed and published fixture harness and contemporary gates. Real B06 still requires full fixture PASS, final independent review, concrete published runtime binding/launcher and separate root GO. Failed audits01-05 remain immutable; no C admission, economic result or promotion follows from this static review.
