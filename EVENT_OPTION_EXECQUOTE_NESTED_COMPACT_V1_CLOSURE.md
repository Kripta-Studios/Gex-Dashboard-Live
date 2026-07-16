# EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1 — CLOSED_NO_EDGE

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
