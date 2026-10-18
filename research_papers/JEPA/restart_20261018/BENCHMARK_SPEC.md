# Fixed exploratory zone benchmark — 2026-10-18

Performance-only technical restart: the first serial feature build was stopped
before any model fit, threshold selection, freeze, or test payoff construction.
Its original source/spec and abort record remain at the original output root.
The first restarted root zone_benchmark_parallel_v2 terminated with a
BrokenProcessPool during features, before fitting or test outcomes. Its cause is
unconfirmed; preserve the failure and do not claim a proven memory diagnosis.
The current root is zone_benchmark_parallel_v3. Two independent per-day workers
use an ordered map with bounded buffering, forced one-thread BLAS/Arrow settings,
native fault logs and immutable daily checkpoints; all formulas, candidates, chronology,
models, costs and decisions are unchanged. No economic result was consulted.

This is a new DEVELOPMENT experiment on previously seen history, authorized by
the user's request. It cannot establish an untouched outer result or live parity.
This specification is written before constructing outcomes or fitting models.
No ThetaData API, old output replacement, production changes, or historical
model/label reuse is permitted.

Use native timestamp 2023 0DTE Greeks and OI from D:/ThetaData/data_options for
SPXW, SPY, QQQ. Train January–June, validation July–September, test October–December.
One deterministic LightGBM parameter set: 150 trees, 15 leaves, depth 5,
minimum child 80, learning rate .04, lambda 10, seed 20261018, two CPU threads.
Two action regressors (CALL/PUT) per representation, no architecture search.
Exclude the known 2023 early-close sessions July 3 and November 24 before values.

Compare price path; price path plus authentic zones; price path plus placebo zones.
Before constructing any outcomes, review identified that a constant .37 IB shift
would be invertible by trees. The final placebo uses SHA256(seed|ticker|date):
first byte parity selects sign; bytes1:9 big-endian map uniformly to magnitude
[.2,.8] IB widths. Same event/action candidates and costs for all. The daily shift
is stored only in candidate diagnostics, never included as a model feature.
IB uses native sampled spot at 09:30 through 10:29, at least 57 valid minute
observations, strictly earlier than the decision. Invalid prices remain missing.
These are sampled extrema, not intraminute OHLC. Fixed Fibonacci ratios are
[-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,1.272,1.618,2].
Features include 12 previous 5m sampled returns and 8 previous 15m sampled
returns with missing history masked, 5m/15m sampled candle summaries, causal
volatility and IB width, continuous Gaussian zone influence at .10/.25 IB width,
nearest signed distance, prior approach/rejection, OI concentrations and migration.
OI is observed only when its reported timestamp is <= feature time. Its claimed
prior-close meaning is an unverified assumption; no dealer gamma is inferred.
All representations share nonspatial OI-weighted IV/delta/vega/theta context.
Authentic/placebo zones additionally include explicitly named Black–Scholes gamma
proxy concentrations, with r=q=0, decimal IV restricted to (0,5], and calendar
seconds to 16:00 divided by 365 days. Proxy dollar density is gamma*OI*100*S²*.01,
separately for calls and puts; it is not signed dealer exposure or a gamma flip.
IV unit plausibility is reported from source quantiles; absent vendor vintage
certification remains a limitation. All spatial gamma/OI/Fibonacci levels receive
the same placebo shift that ticker/day; shared nonspatial context remains identical.
This is a location-specificity control, not a complete matched scientific null.

Decisions are 10:35, 11:05, ..., 15:05 New York. Features use timestamps at or
before decision minus one minute. Select each side's contract nearest absolute
delta .50, tie by strike, from the exact feature minute. Use the selected SAME
contract at exact decision plus one minute for entry and 30 minutes later for
exit. Never select a replacement because future entry is missing. Valid quotes
require bid>=0, ask>0, bid<=ask; identities require same date and expiration;
duplicate contract/timestamp keys are excluded and counted. Spot timestamps
must not be future and spot age must be <=60 seconds. Zero/invalid spot is masked.
Missing entry is excluded and reported. Missing exit liquidates at zero and
charges exit commission, rather than deleting an adverse trade.

One contract, multiplier 100, buy ask/sell bid. Commission $1.30 per side;
base slippage .01 per side, adverse .02 per side. Each ticker rejects decisions
Exit proceeds are clipped to zero after slippage; liquidation cannot be negative.
while a position is open, including decision times earlier than entry+30m.
Choose action with highest predicted base net USD, CALL first on exact ties.
Select threshold from {0,5,10} on pooled validation net, requiring at least
10 trades per ticker; ties prefer lower threshold. Prediction must strictly exceed
the threshold. If no threshold qualifies, freeze NO_TRADE for test and report
the failed validation count gate. Models and
threshold/prediction hashes freeze before test labels are constructed.

All tickers/months and exclusion counters are reported. Save models, predictions,
ledgers, source SHA256, code/spec hashes, base/adverse economics and paired circular
five-session block bootstrap CIs (2000 resamples, seed20261018, common resample
indices for comparisons, complete full-session NYSE Q4 calendar including zero
event/trade days) for authentic minus price
and authentic minus placebo. No post-test rescue or re-fit. An apparent positive
result remains exploratory development evidence with unverified source/live
semantics. This trial tests a bounded representation; failure does not disprove
all approximate visual support/resistance hypotheses.
