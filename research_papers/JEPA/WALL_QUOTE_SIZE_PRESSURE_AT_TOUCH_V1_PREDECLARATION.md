# WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1 (H-QSIZE1)

Status: predeclared after the frozen failures of H-FLOW1 and H-IVSURF1, but
before completing the missing quote-size capture, constructing H-QSIZE1
features, joining physical labels, fitting a model or inspecting any
quote-size/outcome association.

## Question

Does observable top-of-book NBBO size pressure and withdrawal near a Greek wall
add stable causal information, beyond distance/approach/RV/time, about true
rejection versus accepted break?

H-QSIZE1 is a new measurement. The closed H-FLOW1 block used price, volume,
trade count and quote-relative signing but no bid/ask sizes. H-IVSURF1 used
midpoint-IV deformation but no sizes. This experiment measures one-minute NBBO
snapshots; it must never be called full book depth or quote update intensity.

## Sealed universe

- SPXW, QQQ, SPY; `20220801..20251231`; 2026 is forbidden.
- Exactly the 10,683 sealed first-touch candidates, SHA-256
  `6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b`.
- Only candidate keys, wall geometry and the 18 F0 controls are reused. All
  H-FLOW and H-IVSURF features are excluded.
- Canonical manifest SHA-256
  `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
- Existing fallback quote sidecar: 1,441 sessions / 125,557,990 rows, index SHA
  `0abe0ac2f9dcccec4574ee10e4f10ef2904000c80a0cf5fb8f5a90ef333f754a`.
- Frozen complement universe: exactly 1,078 sessions whose canonical Greek file
  already contains option `timestamp`, key SHA-256
  `10665f9070736651ee0d04a63f01a28165b3cd818c42e711437f256be342e3dd`:
  QQQ 393, SPXW 357, SPY 328.

The complement must be captured through the local frozen Theta Terminal/JAR,
one wildcard 0DTE quote request per session, interval 1m, research grid
10:20..14:29 regular and 10:20..12:54 half-day. Raw HTTP bytes, response,
Parquet, source Greek, session manifest, JAR, runtime and builder are hashed.
Stored Greek keys must have 100% exact timestamp coverage. Provider-added keys
are archived but never expand the frozen Greek universe. Bid/ask revisions are
reported; size has no historical vintage anchor, so provenance remains
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`.

No labels, future underlying bars, option payoff or 2026 files may be read by
capture or feature builders.

## Causal clock and quote validity

At decision `t`, the snapshot timestamp must be exact and `<=t`. Live/shadow
must later prove `feature_available_at <= score_at < order_at`; otherwise the
whole contract shifts to the latest previously received snapshot before any
holdout. No floor/asof/subminute join is allowed.

For each candidate anchor current wall `W_t`, spot `S_t`, expiration and Greek
contract universe. For each right, use identical expiration/right/strike keys at
`t,t-1,t-5,t-15`, restricted by `abs(K-W_t)/S_t <=150 bps`. No delta remapping,
contract replacement or temporal fill. Required per-row validity:

```text
finite bid, ask, bid_size, ask_size
bid > 0
ask >= bid
bid_size >= 0
ask_size >= 0
bid_size + ask_size > 0
```

Crossed/non-signable rows are invalid, not inverted. Missing/new/disappearing
contracts remain explicit and are never zero-filled. Candidate rows are always
preserved; invalid local surfaces receive NaN values plus quality fields.

## Frozen features

For valid shared local contracts define:

```text
qimb = (bid_size - ask_size) / (bid_size + ask_size)
local_qimb = median(qimb)
local_log_bid_depth = log1p(sum(bid_size))
local_log_ask_depth = log1p(sum(ask_size))
local_signable_fraction = valid local contracts / frozen local contracts
relative_qimb = local_qimb - median(qimb over valid contemporaneous same-right surface)
```

The allowlist contains, separately for CALL and PUT:

- current `local_qimb`, `local_log_bid_depth`, `local_log_ask_depth`,
  `relative_qimb`, `local_signable_fraction`;
- for each `h in {1,5,15}`, the current-minus-lag change of those five values.

That is 40 measurement features. Quality-only fields are current shared local
contract counts and CALL/PUT/both validity. No handcrafted support/resistance
direction, dealer sign assumption, H-FLOW, IV deformation, outcome or option
return enters the block.

## Outcome-free data gate

Before labels:

- 2,519/2,519 sessions covered exactly by the disjoint 1,441 + 1,078 indexes;
- exact frozen session and Greek key hashes; zero missing Greek keys;
- raw/session/index/seal/JAR/runtime/code hashes valid;
- 10,683 candidates preserved with no duplicate H-QSIZE key;
- coverage, zero rates, signability, distinctness and missingness by
  ticker/year/month;
- every ticker-year both-valid rate >=60% and each ticker overall >=70%;
- every numeric H-QSIZE feature has >=2 finite distinct values per ticker-year;
- F0 control coverage exact and no H-FLOW/H-IVSURF/outcome/2026 column read.

Failure closes H-QSIZE1 without outcomes. No post-hoc relaxation of radius,
quote validity, clocks, lags, aggregation or coverage is allowed.

## Frozen physical evaluation

Same labels, folds, wall identity, monthly accounting and ticker-day bootstrap as
H-FLOW1/H-IVSURF1. Train <=2023 -> outer 2024; train <=2024 -> outer 2025;
horizons 30/60/120/180m.

Primary: L2 Logistic Regression, `C=1`, `max_iter=5000`, seed `20260712`,
train-only median imputation + missing indicators + standardization. LightGBM
with the previous fixed parameters is sensitivity only and cannot rescue.

This is the third sequential wall-touch block on the same outer years, so paired
Wilcoxon requires `p < 0.0167`. All other gates remain:

- 24/24 valid pairs, >=16 wins, median ΔAUC >=+0.010;
- each ticker >=5/8 wins, positive median ΔAUC, median F1 AUC >=0.55;
- each ticker >=3/4 wins at 30/60m with positive primary median;
- monthly resolved coverage and both classes;
- <=12 joint AP/log-loss losses;
- LightGBM >=13/24 wins and positive median ΔAUC.

Outer selects nothing. No SPY-only, role, wall, month, lag, size regime or
threshold rescue is permitted.

## Economic boundary

No option payoff training unless every physical gate passes. Even then, evidence
is exploratory and conditional. A separate frozen runner must reproduce ask
entry, bid exit, 30-180m live exit, no overlap, caps 4/2/1 and QQQ cooldown 30m.
The first-touch stream cannot alone meet 18 trades in several QQQ/SPY months, so
a final policy requires a predeclared causal fallback; none is currently proven.
