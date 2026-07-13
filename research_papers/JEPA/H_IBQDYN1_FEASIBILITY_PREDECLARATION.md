# H-IBQDYN1 causal feasibility predeclaration

Status: frozen before reading any H-IBQDYN tick response, label, option payoff
or 2026 row. This is a new source/universe feasibility test, not a repair or
rescue of closed H-QDYN1.

## Question and separation from closed work

At a causally completed current-day Initial Balance/Fibonacci interaction, do
sub-minute NBBO update and displayed-size replenishment/withdrawal dynamics in
the exact executable 0DTE CALL and PUT contracts contain stable information
about defense versus break?

H-FLOW1, H-IVSURF1, H-QSIZE1R1 and Greek-wall H-QDYN1 are closed. Their data,
features and ticks cannot be relabelled or reused. H-IBQDYN1 uses a new event
universe (the complete fixed eight current-day IB/Fibonacci levels) and a new
directed capture of the actual execution-bucket contracts. Static proximity,
exchange identity and another model sweep are not the hypothesis.

## Frozen causal opportunity universe

The only event source is the already sealed executable-quote dataset:

```text
tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/
  event_option_dataset.parquet
SHA256=d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408
```

The feasibility builder may read only identity, current/past spot/level fields
and current contract identity/availability. It must never read a column whose
name contains `future`, `target`, `status`, `win`, `exit`, `ret` outside the
explicit past-return allowlist, `max_ret`, `min_ret`, `best_side` or any option
outcome suffix.

Frozen selection:

- SPXW, QQQ and SPY; `20220801..20251231`; 2026 forbidden;
- complete 0DTE/executable-quote rows only;
- current IB uses exactly all 60 completed bars 09:30..10:29;
- eight levels: IB high/low and 1.272/1.618/2.0 upper/lower extensions;
- source grid is 5 minutes; first decision 10:35 ET;
- last decision 14:30 regular day and 12:30 half-day, so a 30-minute hold
  cannot cross the 16:00/13:00 underlying close;
- retain the source's frozen `nearest_level_abs_bps <= 20` convention;
- divide the decision clock from 10:35 into fixed 30-minute blocks and retain
  the chronologically first source event in each ticker/session/block;
- execution bucket is SPXW d25, QQQ d35 and SPY d35, with the exact CALL and PUT
  strikes stored by the causal source row;
- no nearest-strike remap, threshold sweep, selected level subset or later row
  replacement when a contract is missing.

The resulting outcome-free universe is frozen at 16,926 events: QQQ 5,408,
SPXW 5,858 and SPY 5,660. All have both source bucket contracts available.

## Frequency capacity gate

Frequency is audited without labels by greedy chronological replay with a
30-minute open-position exclusion and the current caps SPXW=4, QQQ=2, SPY=1.
For each 2024/2025 ticker-month, the maximum feasible count must be at least 18.
The frozen preflight audit gives minima QQQ=35, SPXW=69 and SPY=19. This proves
capacity only; an eventual scored policy must itself retain at least 18 trades
in every reported outer month.

## Exact pre-subscription proof

At `s=t-5m`, use only the sealed native quote sidecars covering all 2,519
sessions. The live subscription rule is the complete exact listed 0DTE chain at
`s`, both rights. Each later source CALL/PUT contract must be present with exact
symbol, expiration, numeric strike and right at `s`. Presence is listing only;
bid, ask, size, signability or any later value cannot affect eligibility.

The proof must preserve every one of the 16,926 events, explicit per-right
listing flags, full-chain contract count and failure reason. No as-of, floor,
nearest, forward fill or query-at-t substitution is allowed. Live parity remains
`BLOCKED` until a prospective receiver measures full-chain subscription
acknowledgement, event time, arrival time, p99.9 latency and capacity.

## Frozen 12-event / 24-contract tick preflight

Before a full download, capture only the chronologically first frozen event for
each ticker-year. The sessions are:

| Ticker | 2022 | 2023 | 2024 | 2025 |
| --- | --- | --- | --- | --- |
| QQQ | 20220801 10:45 | 20230103 10:35 | 20240102 10:35 | 20250102 11:05 |
| SPXW | 20220801 10:45 | 20230103 10:35 | 20240102 10:35 | 20250102 10:35 |
| SPY | 20220801 10:45 | 20230103 10:35 | 20240102 10:35 | 20250102 10:35 |

For each event request the exact frozen CALL strike and PUT strike separately
from `/v3/option/history/quote`, `interval=tick`, over `[t-32s,t-2s)` encoded as
inclusive `start_time=t-32s` and inclusive `end_time=t-2.001s`. Preserve raw
bytes, normalized parquet, provider ordinal, HTTP headers, Terminal provenance,
source/proof/code/runtime hashes and an immutable manifest.

The preflight must reject missing/duplicate/substituted contract blocks,
timestamps outside the guarded interval, empty raw responses or mutation. It
reports row counts, raw/parquet bytes, required fields, collision rates and a
projection to the full eligible universe. Full capture is not authorized if the
projection exceeds 150 million rows or 20 GiB raw, or if either right is empty
in any frozen sample.

## Frozen future measurement block

If and only if feasibility passes, transitions are built independently for CALL
and PUT. Exact duplicate rows are removed from intensity. Same-millisecond
collisions count intensity but never ordered change. Ordered transitions require
strictly increasing timestamps that each occur once, finite positive non-crossed
prices, nonnegative sizes and finite exchange identifiers. A size change counts
as replenishment/withdrawal only while same-side price and exchange are stable.
Conditions and exchange-change rates are audit-only.

F1 contains, per right:

- log update count and 10-second-versus-prior-20-second acceleration;
- signed mid-price up/down transition pressure;
- signed spread narrowing/widening transition pressure;
- log bid replenishment, bid withdrawal, ask replenishment and ask withdrawal.

It additionally contains four fixed CALL-minus-PUT contrasts: update intensity,
signed mid pressure, bid replenishment balance and ask withdrawal balance. That
is 20 alpha fields. Raw counts, collisions, conditions, exchange changes,
validity and missingness are quality-only. Snapshot level/size, H-QSIZE,
H-QDYN, H-IVSURF and H-FLOW fields cannot enter F1.

A later full data gate must preserve all 16,926 rows, require both-right valid
coverage >=80% in every ticker-year and >=85% per ticker, at least two finite
states per alpha field/ticker-year, exact source/proof/capture hashes and
identical complete cases for F0/F1. Failure closes H-IBQDYN1 before labels.

## Frozen evaluation and economic authorization

Only after `PASS_DATA_GATE`, a separately committed frozen runner may compare F0
distance/approach/RV/time with F1 on train<=2023 -> 2024 and train<=2024 ->
2025, horizons 30/60/120/180m. The primary model is L2 logistic regression;
fixed LightGBM is non-rescuing. Since no H-QDYN or H-GREEK2 outcome was opened,
this remains the fourth physical outer family and requires paired one-sided
Wilcoxon `p<0.0125`, 24/24 valid cells, >=16 wins, median delta AUC>=0.010,
every ticker >=5/8 wins with positive median/F1 AUC>=0.55, every ticker >=3/4
wins at 30/60m, <=12 joint AP/log-loss losses and LightGBM >=13/24 with positive
median.

No option payoff is authorized without the complete physical pass. Any later
economic runner must be frozen first and use chronological walk-forward only,
ask entry, bid exit, exact shared scheduler, reject-while-open, hold 30..180m
and no June 2026. Promotion requires separately for SPXW, QQQ and SPY:
PF>=1.30, WR>=50%, at least 18 trades and positive PnL in every outer month.
