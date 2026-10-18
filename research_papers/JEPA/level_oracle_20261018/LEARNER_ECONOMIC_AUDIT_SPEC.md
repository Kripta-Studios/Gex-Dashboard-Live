# Independent learner-economic audit specification — 2026-10-18

Status: `PREDECLARED_BEFORE_REAL_LEARNER_METRICS`.

This audit is independent of `run_policy.py`, `level_engine.py`, model training
and producer economic-metric functions. It does not refit a model or reproduce
network predictions. It audits economic execution **given** the saved, sealed
prediction vectors.

## Frozen inputs and periods

- learner root: `D:/GexResearchArtifacts/level_oracle_20261018/learners_v1`;
- oracle root: `D:/GexResearchArtifacts/level_oracle_20261018/engine_v1`;
- oracle authority: exact full independent PASS at `engine_v1_audit_v4/audit.json`;
- validation: calendar 2025; test: 2026-01-01 through 2026-06-30;
- three models in fixed order: `gbt_net`, `gbt_advantage`, `tcn_teacher`;
- thresholds in fixed order: 0, 5 and 10 USD; nine policies total.

Each prediction NPZ must be present exactly once for every COMPLETE ticker-day
in its period, absent for the six known missing-source cells, match
`prediction_hashes.json`, contain the exact offered `action_id` universe, and
provide finite float scores for all three models. Actions and labels must match
the hashes in the already-audited oracle index.

## Independent scheduler

At each state, rank finite scores descending and break ties by smaller action
ID. WAIT wins score equal to the threshold, so entry requires `score > threshold`.
Start flat at state 60. Once selected, a FILLED action advances to `exit_i + 1`;
a NO_FILL advances to `state_i + 1` without an alternative-contract rescue.
Reconstruct attempts and the FILLED-only ledger for every policy and day.

The audit compares exact selected action IDs, statuses, chronology and policy
identity against producer attempts/ledgers. Numeric scores and economic columns
use absolute tolerance 1e-8. It reconstructs daily full-calendar zero coverage,
pooled/ticker/month metrics, TARGET/STOP/EOD diagnostics, base/adverse PnL, PF,
win rate, realized exit-order drawdown and holding-time summaries.

## Selection, freeze and gate

Independently calculate each 2025 policy score as the sum over tickers of base
net USD divided by its frozen training risk scale. CASH score zero is first and
wins an exact tie. Remaining stable order is model order above, then lower
threshold. Verify `freeze.json` hashes all pre-test artifacts and contains the
same winner and validation choices before any test artifact timestamp.

On the frozen selected policy only, reconstruct the 2026 provisional gate per
ticker: base and adverse net positive, base PF at least 1.2 (or positive gain
with no loss), at least 60 trades, and at least three positive months. CASH
fails. All nine test candidates remain diagnostic and cannot replace the frozen
winner.

PASS requires learner completion, exact prediction/source/freeze seals, exact
attempt and ledger identities, all metric comparisons, selection and gate
agreement, and no overlap violations. The result will bind learner summary,
freeze, both prediction manifests, oracle index/completion/full-audit and the
auditor source hashes.

This scope does not independently reproduce training, model weights, feature
encoding or prediction inference. The test interval is seen development data.
No PASS establishes source receipt timing, live parity, prospective performance,
technical readiness or promotion.
