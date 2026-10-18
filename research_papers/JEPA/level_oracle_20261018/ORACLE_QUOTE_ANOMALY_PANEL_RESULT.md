# Oracle quote-anomaly panel result

## Result

`COMPLETE_PREDECLARED_ORACLE_QUOTE_ANOMALY_PANEL`

The panel covered all 96 predeclared TRAIN ticker-days and all 741 observable
2025 validation ticker-days. It produced 744,926 diagnostic rows from sealed
caches and existing engine/control artifacts. No raw parquet, new model fit,
trade filter, or PnL rewrite was used.

Artifact root:
`D:/GexResearchArtifacts/level_oracle_20261018/oracle_quote_anomaly_panel_v1`

## Entry findings

Across 75,720 TRAIN offered entries and 1,284 oracle entries, the oracle selected
no ask below approximate intrinsic, zero bid, spread/ask at least 25%, or repeated
three-minute quote. The offered population contained 28 spreads at least 25% and
496 three-minute repetitions.

Across 640,774 validation offered entries and 10,303 oracle entries, neither
population contained an ask below approximate intrinsic. The oracle selected one
SPY entry with zero bid and spread/ask at least 50%. This is 0.0097% of oracle
validation entries, versus 0.0045% for spread/ask at least 50% among all offered
entries. One event is insufficient to establish systematic exploitation. Oracle
three-minute repetitions were less frequent than offers: 0.1165% versus 0.4014%.

Approximate parity residuals are strongly ticker-dependent. In validation SPXW,
58.90% of oracle entries and 58.34% of offered entries exceeded $0.25 absolute;
27.52% and 26.86% exceeded $0.50. The close oracle/offered rates and the much
smaller QQQ/SPY rates show that this metric primarily reflects instrument and
approximation differences, rather than an oracle-specific anomaly. It must not
be interpreted as proven arbitrage.

The original `gbt_net__0` control had 174 TRAIN and 2,455 validation attempts.
Its approximate SPXW parity residual rates were generally as high as or higher
than the oracle's. Control exit legs also had more wide-spread observations than
oracle exits. These comparisons do not support a broad claim that the oracle's
entry value comes from the predeclared quote anomalies.

## Exit and interpretation limits

Eighty validation oracle exits had ask below approximate intrinsic, including 77
SPXW exits. Exit time is determined by the target/stop path rather than selected
as a favorable quote by the oracle. The diagnostic uses ask for the plausibility
flag even though economic liquidation uses bid. European-style exercise and
settlement, rates, dividends, clock approximation, and synchronization can all
affect the simple spot-intrinsic comparison. Fourteen control validation exits
also carried this flag.

The panel does not validate option quote age: identical stored rows are only
repeated observations. It does not validate receipt time, and the parity formula
ignores rates, dividends, exercise style and settlement. The six 2026 source
missing days and test economics were outside this panel. SPY's benign fixed-day
result was not extrapolated to SPXW; all ticker results are reported separately.

No exclusion or economic rescue follows. The oracle remains a clairvoyant
development ceiling; `technical_ready=false` and `promotion_approved=false`.
