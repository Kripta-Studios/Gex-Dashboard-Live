# Independent learner-economic audit result — 2026-10-18

Status: `PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT`.

Authority:
`D:/GexResearchArtifacts/level_oracle_20261018/learners_v1_economic_audit/audit.json`,
SHA-256 `238e6f0974025edf076d4023f134878340141271547e45e618026042539945bd`.

The audit was specified and tested before the learner producer completed. It
imports no producer scheduler, engine, trainer or economic-metric calculation.
It does not refit a model or regenerate predictions. It reconstructs economic
execution given the sealed saved prediction vectors.

## Scope and checks

The independent auditor rehashed the learner summary, freeze, 1,104 prediction
NPZs and manifests, the full oracle audit/index/completion, every consumed
action/label sidecar, and all 54 producer attempts, ledger and daily artifacts.
It verified exact NPZ membership, action-ID alignment and finite scores.

It independently reconstructed all nine model/threshold policies over 741
validation ticker-days and 363 test ticker-days:

- validation: 4,573,153 offered action scores, 6,272 attempts and 6,269 fills;
- test: 2,406,690 offered action scores, 3,634 attempts and 3,634 fills.

For every day it selected the maximum score at each state, broke score ties by
lower action ID, required strict `score > threshold`, advanced NO_FILL by one
state without rescue and FILLED by `exit_i + 1`. There were no overlap
violations. Exact selected action identities, attempts and ledgers matched.
Daily full-calendar zeros, pooled/ticker/month metrics, base/adverse costs,
TARGET/STOP/EOD diagnostics, holding times, PF, win rate and realized exit-order
drawdown all matched the producer within 1e-8 absolute tolerance.

The audit also reproduced CASH competition and stable policy ordering on 2025,
verified every pre-test freeze artifact and the full oracle authority, confirmed
that freeze preceded test prediction files, and independently reproduced the
selected-policy provisional gate.

## Economic result

The frozen 2025 selection is `gbt_advantage__10`, with normalized selection
score `0.06000000000000008`. It came from only two SPXW validation trades:
base +$40.80, adverse +$36.80, one win and one loss. SPY and QQQ had zero
validation trades for this policy. This is a sparse development selection.

The frozen selected policy made **zero trades** in 2026H1 for SPXW, SPY and QQQ.
Base and adverse net are therefore $0 for every ticker, all six months have zero
PnL, and the provisional gate fails. No other test candidate may replace or
rescue the frozen policy.

## Boundary

This PASS establishes correctness of economic scheduling and reporting given
the saved predictions. It does not independently reproduce training, feature
encoding, network inference or prediction values. Both validation and test are
seen development history. There is no demonstrated causal profitable learner,
receipt-time guarantee, live parity, prospective evidence or promotion basis:
`technical_ready=false`, `promotion_approved=false`.
