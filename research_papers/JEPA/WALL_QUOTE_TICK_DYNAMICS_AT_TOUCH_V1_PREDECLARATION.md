# WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1 (H-QDYN1)

Status: predeclared after the frozen failure of H-QSIZE1R1 and before capturing
the H-QDYN1 source, building features, joining physical labels, fitting a model
or inspecting any H-QDYN1/outcome association.

## Question and novelty

Does observable sub-minute NBBO update, displayed-size withdrawal and increase
at a Greek-wall strike add stable causal information, beyond distance and
approach, about true rejection versus accepted break?

H-QSIZE1R1 used last 1-minute sizes and failed. H-QDYN1 uses every OPRA NBBO
quote report in a completed 30-second predecision window. It measures message
intensity and queue-state transitions, not another architecture.

## Causal subscription universe

- SPXW, QQQ, SPY; `20220801..20251231`; 2026 forbidden.
- Exactly 10,683 sealed candidates, SHA
  `f4ed7b2360dd2ff3676a23ac2da297c73554ccfd0f5486314b85cc88d0ef6c49`.
- At `t-5m`, form a live subscription allowlist containing both rights for every
  listed 0DTE strike within 150 bps, relative to spot at `t-5m`, of any of the
  four call/put gamma/delta walls then observable.
- At `t`, the exact `candidate_wall_strike` may be read from the buffer only if
  it belonged to that prior allowlist. No nearest-strike substitution.
- The proof uses wall-state SHA
  `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`.
  Exactly 9,833 candidates are eligible; eligible-event-id SHA
  `f77dc2231f410679ad97737cc8a4af057e917224e31d2c5df3b6f1f8366a2eca`.
  The other 850 candidates remain explicit invalid rows.

Historical capture materializes only the eligible exact wall contract, both
rights, because allowlist membership proves that live could already have held
it in its buffer. One request per eligible event uses ThetaData
`/option/history/quote`, `interval=tick`, expiration=trade date and raw bytes.

## Causal clock

For decision `t`, the feature interval is `[t-32s,t-2s)`: inclusive vendor
`start_time=t-32s`, inclusive `end_time=t-2.001s`. The frozen 2-second arrival
guard prevents reliance on a quote stamped just before `t` but received after
the score. Shadow must later verify p99.9 arrival latency and record provider
event time, arrival time and subscription acknowledgment. Until then parity is
`BLOCKED` and provenance is `CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`.

No `t` quote, floor join, future/partial second, fill, remap or post-entry update
is permitted. Capture hashes raw response, normalized parquet, provider ordinal,
eligibility, event manifest, source datasets, code/protocol/runtime, active
Terminal JAR and process evidence. It is immutable/resumable and seals only at
9,833/9,833 eligible captures with zero errors plus all 10,683 eligibility rows.

## Duplicate and quote-validity rules

Tick responses can contain multiple states at one millisecond without sequence.
Provider ordinal is preserved for audit, but ties never establish order. Exact
duplicate rows are removed from model intensity and counted quality-only.
Collision bursts are audited; ordered transitions require two consecutive raw
rows whose timestamps each occur exactly once and strictly increase. No
transition is inferred from a state before window start to the first tick.

Raw crossed/zero/non-finite quotes are preserved. A model transition requires
finite bid/ask/size/exchange, `bid>0`, `ask>=bid`, nonnegative sizes. Never
invert. A displayed-size increase/decrease is classified only if same-side price
and exchange are unchanged. It is not called dealer inventory.

## Frozen feature block

Separately for CALL and PUT over `[t-32,t-2)`:

- `log_update_count` after exact-row deduplication;
- `log_unique_timestamp_count`;
- `timestamp_collision_fraction`;
- `update_acceleration_10s_vs_prior20s`, `[t-12,t-2)` versus `[t-32,t-12)`;
- `unambiguous_state_change_fraction`;
- `unambiguous_price_change_fraction`;
- `unambiguous_size_only_change_fraction`;
- `log_bid_size_increase`, `log_bid_size_decrease`,
  `log_ask_size_increase`, `log_ask_size_decrease`;
- `bid_exchange_change_fraction`, `ask_exchange_change_fraction`;
- `log_last_update_age_ms` relative to `t-2s`.

That is 28 dynamic measurements. Quality-only fields are raw/dedup rows, exact
duplicates, collisions, unambiguous-pair count, CALL/PUT/both validity and
subscription eligibility. F1 receives only 28 measurements; F0/F1 use identical
complete cases. No snapshot level, H-QSIZE/H-IV/H-FLOW feature, dealer sign,
outcome or missingness enters F1.

Validity requires >=20 deduplicated rows and >=5 unambiguous adjacent pairs per
right. Data gate preserves 10,683 candidates, requires exact 9,833 subscriptions,
both-valid >=80% in every ticker-year and >=85% per ticker, every dynamic feature
>=2 finite values per ticker-year, exact hashes and finite F0. Failure closes
H-QDYN1 without labels.

## Frozen physical evaluation

Same labels/folds as prior wall tests: train <=2023 -> 2024, train <=2024 ->
2025; 30/60/120/180m. Primary L2 LR (`C=1`, seed `20260712`) with train-only
median, no missing indicators, standardization. Fixed LightGBM is non-rescuing.

This is the fourth outer test, so paired Wilcoxon requires `p < 0.0125`. Other
gates remain: 24/24, >=16 wins, median ΔAUC>=+0.010; every ticker >=5/8 wins,
positive median and F1 AUC>=0.55; every ticker >=3/4 wins at 30/60m; <=12 joint
AP/log-loss losses; LightGBM >=13/24 and positive median; >=18 resolved
complete-case episodes per primary month.

No payoff is authorized unless every physical gate passes. A physical pass is
still conditional until a live tick receiver demonstrates parity.
