# Market evidence before oracle imitation

User steering, 2026-10-18: oracle trades should be supported by market ratios,
Greeks and observed values. This is a new diagnostic and subsequent research
direction, not a rewrite of the original oracle or a profitable-policy claim.

## What must be distinguished

1. **Admissible action:** the entry, target, stop and contract satisfy the existing
   level and execution rules. The original oracle already enforces these rules.
2. **Observable setup:** numerical evidence existed before the decision, such as
   price approaching a known zone, a completed candle rejecting it, or changing
   concentration of unsigned gamma near a proposed target.
3. **Predictive setup:** the same observable evidence distinguishes subsequent
   outcomes on later dates, including cases where the setup loses. This cannot
   be established by explaining only profitable oracle trades.
4. **Executable policy:** those forecasts produce positive net PnL after fills,
   costs and non-overlap scheduling, with the daily activity requirement met.

Only stages 1 and 2 can be assessed from a single illustrative session. A
constrained oracle still uses future outcomes for its choice among admissible
actions. Restricting its choices does not make the oracle causal.

## Immediate deliverable

An outcome-free extractor receives only the current action features and the
existing causal state representation. It returns numerical values, validity,
missing reasons and descriptive tags. It has no PnL, exit time, oracle action,
future path or future best-action input. It may not invent a supporting reason
when a feature is unavailable or contradicts the proposed trade.

For the already fixed illustration SPY20250102, extract **all candidate actions**
and seal their evidence before loading oracle/model membership. Join membership
by action identity into a separate overlay afterwards. Preserve candidates not
selected and states where the model waits. This illustration does not select a
new threshold, filter, feature or profitable subset.

Evidence families:

- Price geometry: IB coordinate, distances to visible levels, band width,
  target/stop distance ratio and visible confluence.
- Completed price history: direction of recent moves, candle body/wicks and
  observed interactions with zones. No unfinished 5m/15m candle or final daily
  high/low; IB is available only after the first hour closes.
- Options context: available call/put OI, unsigned gamma concentration and their
  observed history; option delta, IV, theta, vega and validity fractions.
- Contract economics observable at decision: bid/ask spread relative to premium,
  target distance and expiry clock. Current quotes are not the next-minute fill.

Do not describe target/stop distance as monetary reward/risk. Do not interpret
unsigned gamma times OI as dealer positioning, or daily OI as intraday order
flow. Do not extrapolate theta/vega to dollars until their source units are
verified. Selected-contract gamma is not present in the current action vector;
report that absence instead of substituting aggregate gamma.

## Comparative analysis after the illustration

Freeze cue formulas without evaluating their profitability. Use the existing
identity-selected TRAIN diagnostic sample, and report later dates separately.
For each oracle-selected action, retain comparisons with alternative actions at
the same ticker/date/state, plus same-side/similar-time opportunities on other
dates. Do not match on realized exit, PnL or a future regime. Comparisons must
distinguish direction, contract, target and timing; many alternatives at one
state are correlated observations, not independent market trials.

Report missingness, feature distributions and setup frequency for oracle,
model and unselected candidates. When assessing predictive outcomes, include
winning and losing candidates with the same setup. Preserve equal day influence
and uncertainty grouped by session; row counts must not imply independent
sample size. Oracle membership is a hindsight label, not evidence of a market
mechanism. No-fit descriptive comparisons precede any new predictor.

Any learned scoring or restriction uses earlier dates only, with its parameters
frozen before the next evaluation month. All already observed 2025/2026 outcomes
remain development evidence. Do not select rules because they recover the
largest amount of the known oracle profit.

## Subsequent constrained teacher and learner

A candidate restriction must be computed before the oracle dynamic program
reads outcomes, from the same evidence available to the learner. Preserve the
unrestricted oracle as an upper-bound control. Keep the same execution, costs,
target choice, intermediate-level traversal and end-of-session rules.

Report the fraction of oracle actions retained, the new hindsight upper bound,
the causal learner's results, and every day without a fill. A day with no
eligible setup is a failure of the requested daily-operation condition; it may
not disappear from the denominator or be repaired with a retrospectively chosen
fallback trade. Missing source days remain separately NO_EVALUABLE.

An interpretable intermediate model is an option for later investigation:
market concepts -> target/stop/end-of-session probabilities and duration ->
option-value distribution and causal scheduling. It has not been implemented or
shown to outperform the current regressors. Human-readable concepts alone do
not establish causal identification or profitability. The concept-bottleneck
literature motivates inspectable intermediates, not a trading-performance claim:
[Koh et al., ICML 2020](https://proceedings.mlr.press/v119/koh20a.html).

## Current status

Extractor and fixtures in implementation; no new market-cue restriction, model
fit or economic result. The original learner experiments keep their frozen
definitions. The user request changes the research priority, not past results.
