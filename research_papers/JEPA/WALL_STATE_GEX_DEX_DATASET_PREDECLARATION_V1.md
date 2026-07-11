# WALL_STATE_GEX_DEX_DATASET_V1

Status: predeclared before building the full dataset or inspecting any new wall-state label.

## Purpose

The previous wall-interaction audit proved that distance to a level is not enough.
The current live feature contract omits the state variables required by the
economic hypothesis: exposure magnitude at the wall, concentration, dominance,
persistence/migration and per-strike delta walls. This build adds that information
without changing production and without using any future outcome as a feature.

This is a data/mechanism experiment, not a model or architecture comparison.

## Inputs and sealed period

- Canonical ThetaData roots:
  `D:/ThetaData/data_options/{SPXW,QQQ,SPY}` and
  `D:/ThetaData/data_underlying_derived/{SPXW,QQQ,SPY}`.
- Source manifest:
  `tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/filtered_manifest.csv`,
  SHA-256 `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
- Executable event view used only for key/spot coverage audit:
  SHA-256 `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- Physical cutoff: `20220101..20251231`; rows beginning with `2026` are rejected.
- Tickers: `SPXW`, `QQQ`, `SPY`; expiry mode strictly `zero_dte`.
- Decision grid: `10:35..14:30 ET`, five-minute rows. Current-day IB is already
  complete, although IB/Fibonacci is joined in a later causal stage rather than
  recomputed inside the wall surface.
- Historical decisions use only the exact `HH:MM:00` Greeks snapshot, matching
  the executable event builder. A later sub-minute quote such as `HH:MM:30` is
  future information for that row and is excluded rather than floor-joined.

Open interest is required. Historical daily OI is treated as the value observable
for that trading session, matching the existing collector/live convention.

## Exposure definitions

The implementation reuses the exact Black-Scholes exposure functions in
`training_data/stats.py` and the constants `r=0.0325`, `q=0.0150` already used by
`services/compute_features.py`.

For each quote timestamp and strike:

- gamma exposure: `gamma * OI * S^2`; CALL positive, PUT negative for net GEX;
- delta exposure: signed Black-Scholes delta times `OI * S`;
- DGEX: gamma exposure times absolute unit delta; CALL positive, PUT negative;
- IV must be finite in `(0, 2)`, OI positive, strike/spot/T positive.

The following wall identities are materialized from current-time rows only:

- CALL gamma wall: largest CALL gamma exposure;
- PUT gamma wall: largest absolute PUT gamma exposure;
- CALL delta wall: largest positive CALL delta exposure;
- PUT delta wall: largest absolute negative PUT delta exposure;
- max/min net gamma, max/min net delta and max/min net DGEX strikes.

For every identity persist strike, signed distance in bps, signed-log magnitude,
share of total absolute family exposure, top-one vs top-two dominance gap and
number of active strikes. Global features include signed totals, CALL/PUT balance,
HHI, entropy/effective-strike count and wall separation.

## Causal temporal state

Within `(ticker, trade_date)` and only across exact contiguous five-minute rows,
derive for CALL/PUT gamma and delta plus max/min DGEX:

- same-strike flags at 5/15/30m;
- strike migration in bps at 5/15/30m;
- signed-log magnitude change at 5/15/30m;
- wall age in minutes, reset on a strike change, gap or new session.

No backfill, centered window, future shift, daily final wall or outcome column may
enter the feature parquet.

## Build and hardware contract

- Per-session processing; never concatenate raw multi-day option chains.
- Up to 16 process workers on the 32-thread Ryzen, leaving memory headroom within
  32 GB RAM. Each worker reads a single session and returns only aggregated rows.
- Output written as a reproducible parquet plus a JSON manifest with code/input
  hashes, row counts, coverage and date assertions.
- CUDA is not used for this deterministic aggregation. The RTX 5070 Ti is reserved
  for a later sequence model only if the physical labels demonstrate alpha.

## Preflight and acceptance

Before the full build, run at least one real session per ticker and require:

- every requested row has finite positive spot and at least two active strikes per
  CALL/PUT family;
- wall strikes exist in the same timestamp's chain;
- concentrations/HHI lie in `[0,1]`, effective strikes are positive;
- delta walls are not aliases of fixed delta buckets;
- temporal state resets at session boundaries and gaps;
- no 2026 row and no outcome/future column in the feature schema.

For the full build, coverage against the sealed executable event view must be at
least 99% overall and 98% per ticker, with spot disagreement <=1 bps. Missing rows
are reported, never imputed from a future snapshot.

## Next decision, frozen now

After the data gate passes, the first evaluation is physical rather than option
PnL: predict/measure `magnet_hit`, `true_rejection` and `accepted_break` over
30/60/120/180 minutes using future underlying prices only as labels. Selection is
nested and prior-month only. A payoff/side model is authorized only if wall-state
features beat the distance-only control reproducibly and direction is above chance
in every ticker. Exact statistical/economic gates will be predeclared before that
label evaluation.

June 2026 remains sealed. No production policy, service or package is modified.
