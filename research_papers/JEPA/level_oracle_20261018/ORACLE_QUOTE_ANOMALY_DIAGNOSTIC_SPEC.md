# Oracle quote-anomaly diagnostic specification

## Purpose and fixed pilot

This diagnostic asks whether the hindsight oracle selected unusual option quote
observations more often than the actions offered to it or an already frozen
causal control. It does not change source admission, labels, trades, PnL, or the
oracle. The first and only pilot under this specification is `SPY/20250102`,
chosen before calculation. It uses the sealed cache and engine outputs plus the
original learner policy `gbt_net__0`; it reads no new raw parquet.

The fixed populations are:

- `OFFERED_ENTRY`: one row per unique `(entry_i, contract_i)` appearing in the
  day's complete action table;
- `ORACLE_ENTRY` and `ORACLE_EXIT`: the two quote legs of every sealed oracle
  ledger trade;
- `CONTROL_ENTRY` and `CONTROL_EXIT`: the two quote legs of the sealed
  `gbt_net__0` validation ledger on this ticker-date.

Population membership is determined without PnL. No observation is removed
because a diagnostic looks implausible.

## Per-observation metrics

For a valid synchronized spot, define approximate spot intrinsic value as
`max(spot-strike,0)` for calls and `max(strike-spot,0)` for puts. Report
`ask-intrinsic`, `bid-intrinsic`, and whether `ask+1e-12 < intrinsic`. This is a
diagnostic comparison, not an arbitrage declaration.

Report absolute spread and `(ask-bid)/ask`, plus flags for zero bid and spread
ratios at least 0.25 and 0.50. Count the consecutive observed one-minute rows,
ending at the sampled minute, with exactly unchanged valid bid and ask. Thresholds
of at least 3 and 5 are reported as repeated observations; they are not quote age
or receipt staleness because the files lack an independent option update clock.

When a valid opposite-right quote exists at the same strike and minute, compute
midpoint residual

`call_mid - put_mid - (spot - strike)`.

Report availability and signed/absolute residual distributions with absolute
thresholds 0.10, 0.25, and 0.50 USD. This deliberately ignores rates, dividends,
exercise style, settlement details, and microstructure. SPY options are American
style and dividend-bearing, while SPX-family interpretation differs; therefore
the residual is approximate and cannot prove arbitrage.

## Comparisons and evidence boundary

For each population report counts, missing diagnostic components, event rates,
and min/p10/median/mean/p90/max continuous summaries. Compare oracle entry rates
and medians descriptively with offered entries and control entries. Small fixed-day
counts receive no significance or generalization claim.

Before reading arrays, bind the full oracle audit, original learner economic
audit, engine index, cache, action table, labels, oracle ledger, and control
ledger by their published hashes. Save a source manifest, observation table, and
summary. The implementation and synthetic fixtures must be complete before the
fixed pilot runs.

This diagnostic cannot validate receipt timing, fallback clock freshness, OI
availability, live parity, profitability, or deployment. It creates no new
exclusion rule and leaves `technical_ready=false` and `promotion_approved=false`.

