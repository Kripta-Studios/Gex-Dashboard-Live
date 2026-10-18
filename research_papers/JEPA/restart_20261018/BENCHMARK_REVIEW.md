# Independent benchmark review — 2026-10-18

Status: PASS_INDEPENDENT_EXPLORATORY_BENCHMARK_AUDIT; economic result negative.

Reviewer owns this report and the independent auditor; no producer code or source files edited.
The specification and source feasibility report were read before implementation
appeared. Final reviewed producer SHA256:
`92c3e7c8de79528e6b8d8ea96d455cff00de7e6b0e598665dcedfba2567e7c4c`.
This review supports the bounded exploratory run; it is not an economic PASS.

## Scope and interpretation

The specification correctly labels 2023 as seen development, distinguishes sampled
IB from true intraminute extrema, separates OI concentrations from dealer positioning,
and fixes a small model/threshold budget before test outcomes. The original .37
IB-width placebo was rejected during preexecution review: direct distance features
would expose an invertible translation to trees. Before outcomes the producer
replaced it with a reproducible signed per-ticker-day hash shift of .2–.8 IB widths.
Shift metadata is excluded from model features. This remains a spatial negative
control, not a full matched null or a causal identification experiment.

## Preevaluation checks sent to producer

1. Select contract AND action from feature-time information. Future missing entry
   must create no fill for the already selected action, never substitute a contract
   or side. Future availability must not silently filter the inference universe.
2. Respect the actual trading session close, including 2023-07-03 and 2023-11-24.
   Do not manufacture expected late-session trades or zero-liquidation losses on
   early closes. The cutoff and treatment must be explicit before outcomes.
3. Validate native quote clock, same-date 0DTE identity, duplicate exclusion,
   underlying age and agreement across contracts. Only construct features from
   the timestamp prefix permitted by the specification.
4. Compare representations on identical candidates and common price/option context;
   authentic/placebo differ only in intended level geometry. Preserve common
   missingness and exclude neither ticker nor session by resulting PnL.
5. Train/validation chronology, calendar partitions and embargo must prevent any
   label crossing a boundary; freeze models and selected thresholds before test
   labels, then audit prediction and artifact hashes.
6. Reconstruct same-contract ask-to-bid net USD, both commissions/slippages,
   missing-entry no fill, missing-exit zero liquidation and no overlap independently.
7. Report all ticker/month cells including no-trade days. Bootstrap complete paired
   days for all arms/tickers with one common calendar, not separate traded-day samples.

## Findings resolved before outcomes

- Shared identity cleaning now validates symbol/date/expiry, normalizes numeric
  strike and C/P aliases before duplicate rejection, and checks minute-grid regular
  session clocks. Test quote reading applies the same identity exclusions.
- Sampled IB explicitly requires a completed first hour. Partial 5m/15m sampled
  candles expose observation fractions; IB exposes observed minute count.
- OI absence retains shared count/fraction features even though absent weights do
  not contribute to the exposure sum. OI is integer/nonnegative and timestamp-eligible.
- Base/adverse exit sale proceeds are floored at zero; commissions remain charged.
- Missing future entry preserves the selected action and causes no fill; no
  alternative side or contract is substituted. Fixed 31-minute decision-to-exit
  scheduler prevents the next 30-minute-grid decision overlapping the position.
- Both known 2023 early closes are excluded before feature/label construction.
- Direct IB position was removed from common price/context features and placed
  in each arm's corresponding true/shifted level representation.
- No qualifying validation threshold freezes NO_TRADE, now explicit in spec.
- The freeze hashes code/spec, source manifest, features, candidates, labels,
  models and predictions; a verifier runs before test payoff construction.
- Q4 paired bootstrap uses all full-session days and common circular five-session
  blocks, including zero-event/trade days; final source rehash is required.

Independent reviewer ran the first eight synthetic tests: 8 PASS. Producer reports
11 PASS after adding future-feature perturbation, normalized-identity/off-grid and
hashed-placebo tests. Final performance edits only restrict contract selection to
the already materialized feature-minute chain and quote dictionaries to candidate
entry/exit times. Code review found no remaining execution-blocking causal or
accounting error in this version.

Whole daily source columns, including test bid/ask and descriptive IV quantiles,
are physically loaded during feature construction. The verified barrier is on
test payoff construction/selection, not physical byte access to future quotes.
Features use prefixes and no test labels enter fits or threshold selection.
This distinction must remain explicit in interpretation.

## Independent output audit

`audit_zone_benchmark.py` is independent of producer imports. It recomputes
validation selection, scheduler, accounting, all ledger rows and reported
month/ticker metrics; reloads and independently refits six models; checks raw
same-contract test fills and feature-time contract selection; rehashes every
source; rebuilds daily/bootstrap results. It does not reconstruct all raw feature
values or certify historical receipt times/live fills. The output audit completed
successfully; exact scope and economic findings follow below.

## Performance-only continuation

The initial serial feature build was technically stopped before any model fit,
freeze or test payoff construction because its measured runtime implied roughly
48 minutes. Its original script/output root is preserved. No economic result was
used to change a feature, model, selection rule or calendar.

The day calculation was extracted without formula changes into isolated workers;
an ordered four-process map preserves original ticker/day/row ordering and each
day has its own counters and prior-wall state. Reviewed parallel producer SHA256:
`9d36b0f67b6c56c4be213b447605428ddcfec610bdfa152e8b8324eaa1a5e041`.
Producer reports 11 tests PASS for this version.

Independent equivalence check on the already-read SPXW 2023-01-03 training day
compared the preserved serial builder with the extracted worker: feature values,
candidate contracts, training labels, source hashes, counters and IV diagnostics
matched exactly. No economic metrics or test labels were computed in that check.
Evidence: `D:/GexResearchArtifacts/restart_20261018/native_parallel_equivalence/equivalence.json`.
The reviewer cleared the parallel continuation under the same exploratory contract.

The four-worker continuation then failed with `BrokenProcessPool` during feature
construction, again before fit/freeze/test payoff construction. Its root and failure
record are preserved. A new two-worker continuation adds per-day local checkpoints,
native fault logs and explicit one-thread native math settings; it does not change
features, labels, selection or models. Independent AST comparison verified all
26 existing functions except the orchestration-only `build` function unchanged.
The new checkpoint wrapper serializes each unchanged day result, and ordered map
restores the same row sequence. Producer reports 11 tests PASS. Reviewed V3 SHA256:
`5ce55460051cccf3aa91160180e29474b61b717abc6c452cbf344db7e120ca51`.
V3 was cleared as a technical continuation, not a new economic variant.

## Completed independent audit

The auditor exited successfully with
`PASS_INDEPENDENT_EXPLORATORY_BENCHMARK_AUDIT` on 2026-10-18 15:24 UTC.
Evidence root:
`D:/GexResearchArtifacts/restart_20261018/zone_benchmark_parallel_v3/independent_audit_01/`.
Its `audit.json`, independently rebuilt ledger and source-rehash manifest are
preserved separately from producer outputs.

Verified:

- 1,488 original source files independently rehashed; zero mismatches.
- Fixed configuration, frozen code/spec/input/model/prediction hashes, calendar
  split, placebo hash and diagnostic exclusion from model features.
- 14,880 action-label accounting rows with Decimal-based ask/bid, floor, slippage
  and commissions; missing-entry/missing-exit coverage counters matched.
- Six independent model refits, each with 3,720 training rows, exactly reproduce
  all 44,640 predictions across the three arms and two sides. Saved model loading
  independently produced the same predictions.
- Every validation threshold choice, selected threshold, no-overlap schedule,
  and all 2,676 ledger rows across arms and validation/test reproduced, together
  with every reported ticker/month metric. These are separate simulated policies,
  not 2,676 trades of one combined portfolio.
- 793 unique selected test event-side contracts independently checked against raw
  data: nearest-delta contract choice at feature time, same-contract entry ask,
  exit bid and missing-exit state. Shared trades across arms were checked once.
- Both paired five-session bootstrap comparisons rebuilt on the complete common
  62-day Q4 calendar, including zero-trade days.

Producer summary SHA256:
`8131c315ebbcfbfde6e7853f7cfd1f174ff5c781c7ca581a147da4a9c8bcf863`.
Auditor script SHA256:
`e9230ac084727de6cb086a15e499bbc2fc23af2f01e3453c5d58664f7bcfa128`.

Audit scope does not include reconstruction of every raw feature, every training
quote, original historical receipt times, executable market fills or live parity.
The positive audit status certifies the listed reproduction checks; it does not
make the negative economic result profitable or the historical split untouched.

## Economic result reproduced

Q4 2023, one option contract per trade, base/adverse costs specified in the contract:

| Representation | Test trades | Base net USD | Adverse net USD | Base PF |
|---|---:|---:|---:|---:|
| Price + shared nonspatial option context | 429 | -9,963.40 | -10,820.40 | 0.713 |
| Authentic soft zones | 433 | -13,123.80 | -13,988.80 | 0.624 |
| Shifted placebo zones | 509 | -10,533.40 | -11,549.40 | 0.697 |

Authentic zones by ticker: SPXW 199 trades / -10,635.40 USD / PF 0.639;
SPY 126 / -994.60 / 0.624; QQQ 108 / -1,493.80 / 0.463.
All three lose over the quarter under both cost scenarios. SPXW authentic October
was positive (+254.20 base), but November and December losses overwhelm it;
that isolated month is not an eligible rescue.

Authentic minus price is -3,160.40 USD; paired bootstrap 95% interval
[-12,256.91, +5,434.82]. Authentic minus placebo is -2,590.40 USD; interval
[-9,997.55, +5,914.29]. These intervals span zero and provide no reliable
incremental improvement evidence. The zero-trade cash alternative beats all three
realized simulated policies over this test period.

This result rejects profitability for this fixed GBT/soft-field/30-minute 0DTE
formulation. It does not establish that every visual, multiscale or wall-based
strategy lacks edge. This benchmark uses return sequences and the latest sampled
candle summaries, not a full chart-image model or the original complete multiscale
OHLC tensor. Its continuous `rejection` score measures moving away from a level;
it does not certify an observed prior touch. Threshold selection pools nominal
one-contract dollars, so the separate ticker results remain essential.
