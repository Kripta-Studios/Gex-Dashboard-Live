# WALL_INTERACTION_EXECQUOTE_V1

Status: executed once; rejected; failure attributed before V1r1 correction.

## Question

Test whether price interaction with observable Greek exposure walls and Initial
Balance/Fibonacci levels contains stable CALL/PUT information. This is a mechanism
test, not an architecture comparison and not a production promotion.

The recent pairwise physics arm did not contain `dist_to_max_gamma`,
`dist_to_min_gamma`, `dist_to_zero_gamma`, `dist_to_max_dgex`,
`dist_to_min_dgex`, prior-day IB levels, or wall-event state. Therefore this is a
new causal source of alpha rather than another feature subset of that arm.

## Sealed inputs

- Executable outcomes:
  `tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet`
  (already sealed through 2025; no 2026 rows), SHA-256
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- Live-equivalent wall features:
  `training_data/training_data_spx_qqq_spy.parquet`, SHA-256
  `5f908e11090ea6566e3eadeba0a436ab5d01cf99955d6acc5050eae264fe13b5`.
- Common usable interval: `20220801..20251231`, minutes `635..870` on the
  existing five-minute grid. Current-day IB is complete before the first eligible
  minute.
- Join key is exactly `(ticker, trade_date, minute)`, mapping only `SPXW -> SPX`.
  Both inputs must be unique on the key, every event must match, and spot must
  agree within `1e-9` bps.

Only these executable buckets are used: SPXW d25, QQQ d35, SPY d35. Entry is ask,
exit is bid, stop/TP/trailing labels are frozen, and `opt_exit_minutes` is elapsed
duration. Production caps/cooldowns and one-position-at-a-time replay are fixed:

| Ticker | Max/day | Cooldown |
| --- | ---: | ---: |
| SPXW | 4 | 0m |
| QQQ | 2 | 30m |
| SPY | 1 | 0m |

## Observable level universe

- Greek: max/min gamma, zero gamma, max/min DGEX.
- Current day: IB high/low and Fibonacci 1.272/1.618/2.0 extensions.
- Prior sessions D1-D5: IB high/low and the same extensions reconstructed from
  the two stored, live-observable IB distances.

Roles are frozen: max gamma, IB highs and upper Fibonacci extensions are
resistance; min gamma, IB lows and lower extensions are support; zero gamma and
max/min DGEX are role-neutral magnets. A level value is reconstructed only from
the current row's spot and signed distance. Previous prices are compared with the
current level, so movement of the identity of a Greek wall cannot fabricate a
price crossing.

Per-strike max/min delta exposure is not present in the current 182-column feature
contract. V1 must report that as a data-contract gap and must not substitute
absolute option delta buckets for a delta wall.

## Fixed causal event states

All lags are within ticker/session and must be exactly contiguous at 5, 10 and 15
minutes. Thresholds come from the existing live level convention and are not
selected on outcomes:

- touch radius: 15 bps;
- accepted-side buffer: 5 bps;
- magnet band: 15..80 bps;
- minimum 15-minute approach: 3 bps;
- confluence radius: 15 bps.

States:

1. `magnet`: price is 15..80 bps from a level, has reduced absolute distance by
   at least 3 bps in 15 minutes, and 15-minute momentum points toward it.
2. `rejection`: price touched a role-specific level during the last 15 minutes,
   is now at least 5 bps back on the defended side, and five-minute momentum is
   moving away. Support rejection selects CALL; resistance rejection selects PUT.
3. `acceptance`: current and prior two five-minute closes are all at least 5 bps
   beyond a role-specific level with 15-minute momentum continuing through it.
   Acceptance above resistance selects CALL; acceptance below support selects PUT.

Priority is rejection (3), acceptance (2), magnet (1). Confluence adds at most
0.75 to priority (`0.25` per additional nearby level, capped at three). Proximity
adds a deterministic sub-score below 0.1. Highest score wins; an exact opposing
tie abstains.

## Arms and success criteria

- `M0 nearest-magnet`: direction toward the nearest level in the 15..80 bps band,
  without approach/event requirements. This is a descriptive control.
- `E1 wall-event`: the fixed state machine above.

No model, threshold fitting, grid search, or outer-month policy selection is
allowed. Results are reported monthly and by year. The economic gate is the full
contract for E1 separately on every ticker over the fixed evaluation window
`202401..202512`: PF >=1.3, WR >=50%, at least 18 trades in every month, positive
PnL in every month, and every realized hold >=30 minutes. M0 cannot pass or be
promoted; it only attributes whether event semantics improve on proximity alone.

The earlier `202208..202312` rows are reported as mechanism characterization, not
used to modify rules. The entire experiment is adaptive discovery because these
years have been used elsewhere. Even a pass requires a genuinely new holdout
before promotion. June 2026 remains sealed and production is untouched.

## Result

The join passed exactly on 86,729 in-window rows and both input hashes matched.
E1 failed on every ticker over `202401..202512`:

| Ticker | Trades | WR | PF | PnL (R) | Min month | Positive months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1,564 | 40.54% | 0.865 | -75.366 | 52 | 37.50% |
| QQQ | 903 | 44.41% | 0.832 | -49.816 | 30 | 33.33% |
| SPY | 496 | 44.76% | 0.899 | -15.422 | 17 | 45.83% |

M0 also lost on all tickers (PF `0.872/0.903/0.935`), proving that proximity
alone is not the edge. Post-run attribution found that only 29–37% of scheduled
"rejections" had actually crossed the level. That semantic defect is isolated in
V1r1; no other V1 result is retuned.
