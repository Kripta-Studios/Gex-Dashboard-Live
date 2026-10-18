# Oracle quote-anomaly panel specification

This extends the fixed SPY/20250102 diagnostic without changing any metric,
threshold, exclusion, trade, or PnL. It uses exactly the 96 TRAIN ticker-days
already fixed in `oracle_model_diagnostic_v1/training_days_preinference.csv` and
all 741 observable 2025 full-session ticker-days already evaluated there. Dates
are not selected by oracle value, model result, or quote diagnostic.

For every day the populations are unique offered action-entry quotes, sealed
oracle ledger entry/exit legs, and the original `gbt_net` threshold-zero control
attempts reconstructed from the sealed matched-state diagnostic. A control
attempt includes `NO_FILL`; its invalid entry remains in the diagnostic. Filled
control attempts contribute an exit leg. Membership is based on stored action IDs
and scheduler state, never on PnL.

Metrics and thresholds are identical to
`ORACLE_QUOTE_ANOMALY_DIAGNOSTIC_SPEC.md`: approximate intrinsic, spread/ask,
zero bid, identical observed runs at 3/5 minutes, and approximate same-strike
midpoint parity residual at $0.10/$0.25/$0.50. Summaries are reported by split,
ticker, population and pooled. Daily counts establish complete coverage.

The runner must verify the full oracle audit, engine index, the predeclared
TRAIN selection, oracle-model diagnostic identity/summary, each day checkpoint,
each consumed control-state artifact, and each cache/action/oracle-ledger hash.
It processes one day at a time. Estimated compressed input is 1.23 GiB across
837 days; the largest cache file is below 5 MiB. With one worker, memory is
bounded to one uncompressed day plus the accumulated diagnostic table. The
preflight observed 16.62 GiB free physical memory and 18.59 GiB free virtual
memory, so no parallelism is needed.

This is descriptive development evidence. Repetition is not quote age; parity
is approximate and not proof of arbitrage; proxy receipt clocks remain
unverified. No result can create a source filter, remove an existing trade,
rewrite PnL, or justify promotion.

