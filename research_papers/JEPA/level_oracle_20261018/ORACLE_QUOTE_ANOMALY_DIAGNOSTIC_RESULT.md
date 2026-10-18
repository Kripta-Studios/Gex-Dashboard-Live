# Fixed oracle quote-anomaly diagnostic result

## Result

`COMPLETE_FIXED_ORACLE_QUOTE_ANOMALY_DIAGNOSTIC`

The predeclared pilot used only the sealed SPY cache and outputs for 2025-01-02.
It changed no source admission, trade, label, or PnL. The frozen causal comparison
was the original `gbt_net__0` policy.

Artifact root:
`D:/GexResearchArtifacts/level_oracle_20261018/oracle_quote_anomaly_diagnostic_spy_20250102_v1`

## Observations

The day contained 733 unique offered action-entry quote observations, 14 oracle
trades, and 10 control trades. Every sampled entry and exit had a valid synchronized
spot and a valid same-strike opposite-right quote.

None of the 733 offered entries, 14 oracle entries, 14 oracle exits, 10 control
entries, or 10 control exits had any of the following predeclared flags:

- ask below approximate spot intrinsic;
- zero bid;
- spread at least 25% or 50% of ask;
- three or five consecutive identical observed minute quotes;
- approximate put-call residual magnitude at least $0.10, $0.25, or $0.50.

Oracle entry spread/ask had median 1.51% and maximum 2.58%, versus median 1.43%
and maximum 8.33% among offered entries and median 1.33% and maximum 4.29% for
control entries. Oracle entry ask minus approximate intrinsic had median $0.89,
versus $0.91 for offered entries and $0.90 for control entries. Approximate
absolute put-call residual had median $0.0075 and maximum $0.035 for oracle
entries, versus median $0.010 and maximum $0.045 for offered entries.

This fixed-day evidence does not show the oracle selecting the predeclared quote
anomalies more often than the offered or control observations. It also does not
validate the entire history or explain the oracle's large aggregate hindsight
value.

## Limits

An unchanged value across stored one-minute rows is only a repeated observation;
it is not option quote age. The stored fallback clock is not observed receipt
time. The parity residual ignores rates and dividends and does not resolve SPY's
American exercise features or SPX-family settlement conventions, so it is not
an arbitrage test. The intrinsic comparison is likewise descriptive.

No exclusion rule follows from this result. The original trades and PnL remain
unchanged, and `technical_ready=false` and `promotion_approved=false`.
