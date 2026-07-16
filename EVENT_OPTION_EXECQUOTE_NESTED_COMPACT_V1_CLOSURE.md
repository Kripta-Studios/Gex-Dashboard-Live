# EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1 — CLOSED_NO_EDGE

> Separate research note, 2026-07-17: the immutable parity V1R1 relaunch
> passed its outcome-free data gate on all 2,256 sessions. Its next permitted
> step is a 2023-only deterministic cash-proxy development ledger; 2024–2026
> remain unopened. This does not alter, rescue or reopen compact V1.

## Verdict

The frozen one-shot on commit `3722cbc9` completed all 18 ticker-month folds.
The compact nested selector fails decisively and is closed without rescue.

| Ticker | Trades | WR | PF | PnL (R) | Min trades/month | Positive months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 121 | 39.669% | 0.803623 | -8.3647 | 0 | 2/6 |
| SPXW | 110 | 38.182% | 0.793589 | -8.2230 | 14 | 2/6 |
| SPY | 107 | 35.514% | 0.797120 | -8.3235 | 0 | 1/6 |

Pooled: 338 trades, WR 37.870%, PF 0.798224 and -24.9112R. Four of
18 folds abstained because no inner-valid policy existed.

This is not a near miss. QQQ and SPY fail frequency, all three fail WR/PF/PnL,
and most test months lose despite every selected policy passing its six-month
inner gate.

## Monthly recomputation

| Ticker | Month | Trades | WR | PF | PnL (R) |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202601 | 0 | 0.00% | 0.000 | 0.000 |
| QQQ | 202602 | 16 | 43.75% | 1.100 | +0.574 |
| QQQ | 202603 | 38 | 55.26% | 1.724 | +6.280 |
| QQQ | 202604 | 18 | 33.33% | 0.942 | -0.329 |
| QQQ | 202605 | 18 | 38.89% | 0.665 | -2.255 |
| QQQ | 202606 | 31 | 22.58% | 0.200 | -12.634 |
| SPXW | 202601 | 19 | 26.32% | 0.435 | -4.307 |
| SPXW | 202602 | 19 | 31.58% | 0.973 | -0.214 |
| SPXW | 202603 | 14 | 57.14% | 1.300 | +1.028 |
| SPXW | 202604 | 19 | 31.58% | 0.848 | -1.100 |
| SPXW | 202605 | 20 | 45.00% | 1.036 | +0.248 |
| SPXW | 202606 | 19 | 42.11% | 0.416 | -3.878 |
| SPY | 202601 | 0 | 0.00% | 0.000 | 0.000 |
| SPY | 202602 | 19 | 36.84% | 1.300 | +2.118 |
| SPY | 202603 | 72 | 37.50% | 0.792 | -5.686 |
| SPY | 202604 | 16 | 25.00% | 0.285 | -4.756 |
| SPY | 202605 | 0 | 0.00% | 0.000 | 0.000 |
| SPY | 202606 | 0 | 0.00% | 0.000 | 0.000 |

## Independent integrity audit

- source rows are uniformly `option_price_mode=executable_quote`;
- entry is ask and the frozen source contract marks/exits at bid;
- observed hold is exactly 30–180 minutes;
- zero same-ticker position overlaps and zero daily-cap violations;
- zero chronology issues across training, six inner months and outer month;
- all 18 outer months are represented, including four explicit abstentions;
- independent PF/WR/PnL recomputation matches `metrics.json`.

Hashes:

- metrics: `c931bda6244e3f99d3d94c58a32544b24dccbb2f7b06969a8d7bb9711ed4be85`;
- selected folds: `6bf63bd9395bcacfe3b6df42a7a1b0aa629de939061097e4da76d5c0d156f12c`;
- trades: `e4c67b6952e5e13f4b2185f17dd6ddf334a796b63b1325532fac9e4062d8afbd`;
- policy provenance: `c340238995bbdb0b86ef6e84ffb1c987ac20dfb9b17761c2ef6d41f520016fc0`.

## Scientific interpretation and stop rule

The inner-selected LightGBM heads, 5/15-minute trend/counter-trend, completed
IB/Fibonacci geometry, current IV level and IV skew do not overcome spread and
theta for this 0DTE long-option payoff. The attractive historical static-union
metrics remain invalid because they used legacy labels and/or post-hoc 2026
policy selection.

Do not rescue this result by changing a delta, threshold, ticker, month, time
window, regime percentile or feature subset. Do not build another feature
dataset for this payoff.

The previously sealed two-session weekly long-option oracle is also incapable
of meeting the monthly frequency contract under no-overlap (only 8–10 possible
trades/month), and always-CALL/PUT weekly policies were approximately break-even
or losing after ask-to-bid execution. Existing directional 0DTE credit-spread
walk-forwards also lost for all three tickers (PF below 1.0).

The only economically distinct next feasibility test is symmetric defined-risk
short premium (iron condor/iron fly) replayed directly from native bid/ask
quotes. It must produce only a trade ledger, not another feature dataset, and
must pass on pre-2026 months before 2026 or July is evaluated.

## Post-closure program evidence — 2026-07-16

The proposed economically distinct tests were executed or stopped by their
frozen data gates. This addendum does not rescue or alter the compact V1 result.

- Defined-risk short premium V1 encountered crossed native exits. V2 replaced
  path-dependent exits with fixed TIME30/60/90/120 while preserving exact
  four-leg bid/ask execution. After 100/1,506 sessions it already contained
  4,271 candidates and 13 unresolved exits, concentrated in QQQ 2024-02-06.
  Because the protocol forbids silently dropping an entry-resolvable structure,
  V2 is `REJECTED_DATA_GATE`; no PF/WR/PnL was opened.
- Equal-dollar long CALL+PUT 0DTE (`DUAL_LEG_EVENT_VOLATILITY_V1`) eliminated
  the side classifier but lost directly in 2025: 613 trades per ticker, PF
  QQQ/SPX/SPY 0.629/0.661/0.605 and WR 35.07/33.28/36.22%. Only 2/2/1 months
  were positive despite at least 40 trades per month.
- A new seven-futures Globex source produced a genuine 2025 near-miss (PF
  1.200–1.210, 9/12 positive months) but the frozen policy reversed in
  January–15 July 2026 (PF 0.873–0.899, only 2–3 positive months). Three online
  adaptations failed pre-2026 stability gates.
- Direct Initial-Balance breakout/fade execution retained 24–25 minimum monthly
  trades but failed in 2025 with PF 0.779–0.819 and WR 31–32%.

The expanded evidence strengthens, rather than changes, this closure: neither
adding model capacity/market context nor switching to long-vol, short-premium
or IB/Fibonacci created a stable causal policy. The current state is
`NO_PROFITABLE_CAUSAL_POLICY`; production remains unchanged.

## Research continuation note — 2026-07-17

This closure remains final and is not being rescued. The next predeclared test,
`CROSS_SESSION_RELATIVE_VALUE_V1`, changes both target and payoff: a ledger-only
QQQ-SPY equal-notional spread based on cross-session relative divergence, with
SPXW used only as a market anchor. It does not reuse the compact selector,
options outcomes, deltas, thresholds or 2026 results. Development is restricted
to 2022–2023 and production remains unchanged.

The relative-value runner is implemented pre-outcome and hard-stops its source
inventory at 2023. This is operational provenance only; it does not change or
reopen the compact-V1 evidence.

An outcome-free data clarification for the new family preserves the known
2023-06-05 source anomaly without using or repairing it. Compact V1 is still
unchanged.

The independent relative-value development subsequently failed (PF 0.627,
5/24 positive months). Its outer remained closed. This reinforces the program
state without changing any compact-V1 conclusion.

A subsequent predeclared test now isolates cash-session relative momentum
without any compact-V1 option feature or outcome. Compact V1 remains closed.

Its runner is now implemented independently and cannot read compact-V1 data.

Its first launch stopped at Python import before any source or outcome access.

The repaired opening-relative runner subsequently completed only its frozen
2022–2023 development scope. It closed `NO_AGGREGATE_EDGE` with 497 trades,
50.905% WR, 0.831 PF and -927.689 bps; only 4/24 months passed all gates. No
2024–2026 data or compact-V1 artifact was opened or changed. This result closes
that independent cash-ledger family and does not modify the compact-V1 verdict.

A later outcome-free protocol, `OPTION_PARITY_PRESSURE_V1`, studies only the
five-minute change in same-strike 0DTE CALL/PUT quote parity. It is currently at
its native-timestamp/data-coverage gate and has not read any return. It neither
reopens compact V1 nor changes its selector, payoff or evidence.

Before any parity outcome was read, the user narrowed that separate protocol to
2023–2026 because February 2022 had only twelve 0DTE expirations. Its staged
development/outer/holdout ordering remains independent of compact V1.

Its filename-only capacity audit passed with 752 exact-0DTE sessions per ticker
and a minimum of 18 per month. No quote or outcome was accessed, so compact V1
remains unaffected.

The parity data gate's first attempt stopped on an exact timestamp string
serialization mismatch (`.000`) before outcomes. Its narrowly frozen relaunch
does not alter or reopen compact V1.
