# Wide fixed exploratory zone benchmark — 2026-10-18

This separate experiment is specified before reading the native 2023 benchmark
results or constructing this experiment's outcomes. All dates are SEEN DEVELOPMENT.
The user's latest instruction explicitly admits 2024–2026 local files as research
candidates. No API, download, old model/label reuse, production change or promotion.

The native benchmark implementation SHA256
92c3e7c8de79528e6b8d8ea96d455cff00de7e6b0e598665dcedfba2567e7c4c
and BENCHMARK_SPEC.md define the unchanged representations, selected contracts,
costs, labels, models, thresholds, controls and scheduling. Copy this implementation
to wide_zone_benchmark.py; do not change or read its outputs. This document fixes
the expanded period and clock assumptions, not an outcome-driven alternative.

Train 2023–2024; validate calendar 2025; test January–June 2026. Use all expected
full NYSE sessions from the installed exchange_calendars XNYS calendar. Exclude
its early closes before reading values; preserve the exact calendar in output.
Report missing Greek/OI files, schema failures and unusable dates explicitly.
All expected test dates and all six months remain in coverage and zero-trade
reporting. No date selection based on outcomes.

For each Greek file, prefer its native timestamp. Only when absent, use the
stored underlying_timestamp as the declared research clock proxy, without
rounding, ceiling, interpolation or fabricated intraminute times. Record the
clock source per file. Validate exact minute-grid timestamps, same-date symbol,
expiration, strike, right and unique contract/time identities. This substitution
is supported by the independent local probe (15 paired files, 1,889,312 rows,
100% identical timestamp and underlying_timestamp); it does not prove historical
receipt times or certify unprobed files. Report paired-clock mismatches per file.

For OI with native timestamp, retain the original timestamp <= feature cutoff
filter. For missing OI timestamp, assume trade_date OI is prior-close information
available at 09:30 New York. Flag ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT per
file and per event. No observed intraday OI changes are inferred. Missing OI
contracts retain explicit count and fraction feature masks, even though weighted
aggregation uses zero contribution. Missing OI files exclude the date and are
reported. Current Theta documentation describes prior-close OI, but this does
not establish the vintage file's receipt time.

Unchanged fixed experiment: price/common context; authentic soft Fibonacci/OI/
Black–Scholes gamma-proxy zones; daily SHA256-shifted placebo zones. Sampled IB
09:30–10:29 requires 57/60 valid observations. Ratios
[-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,1.272,1.618,2]; soft widths .10/.25 IB.
Sampled 5m/15m paths are not intraminute OHLC. No signed dealer exposure claim.
Decisions 10:35 then every 30 minutes through 15:05. Information and same-contract
selection nearest abs(delta)=.50 at D-1 minute; fixed primary entry at D+1 minute,
exit entry+30 minutes. Valid bid>=0, ask>0, bid<=ask. Missing entry skips the
already chosen action, missing exit liquidates at zero. One long option contract,
multiplier100, commission1.30/side, slippage .01/side base and .02/side adverse,
clipped nonnegative exit proceeds; reject decisions while that ticker is open.
Only six LightGBM fits: CALL/PUT × three representations, 150 trees,15 leaves,
depth5,min_child80,lr.04,lambda10,seed20261018,CPU2. Choose threshold {0,5,10}
by validation pooled base net, >=10 trades each ticker, tie lower threshold;
strict prediction>threshold. No qualifying threshold freezes NO_TRADE.

Freeze all six models, features, candidate identities, predictions and chosen
primary thresholds before constructing any test payoffs. Additionally evaluate
entry delay D+2 and D+5 with the SAME frozen test predictions/actions/thresholds,
and exit 30 minutes after each delayed entry (latest15:40). Recompute no-overlap
scheduling for each delay. These are execution-entry-delay sensitivities, not
feature receipt guarantees and not separate models or threshold selections.
No posttest choice between delays is permitted.

Preserve per-file source hashes and clocks, stage freeze, code/spec copies,
logs/runtime, exclusions, complete monthly/ticker coverage, all three delay
ledgers and final source rehash. Primary paired circular five-session block
bootstrap uses 2000 seeded resamples over the complete expected full-session
2026 H1 calendar, including zero-trade days. No outcome-driven tuning or refit.
Any result remains exploratory with unverified historical receipt/live parity;
technical_ready=false and promotion_approved=false.

Implementation resource choice fixed before execution: six independent day
workers with Arrow CPU1, collected in deterministic ticker/date order. The
training fits remain CPU2 and sequential. This changes execution throughput,
not date membership, features, labels, selection or model hyperparameters.
