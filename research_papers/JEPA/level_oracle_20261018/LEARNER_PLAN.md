# Fixed causal learners after the level oracle

This plan is recorded before fitting market-data learners or examining their
validation/test economics. PROTOCOL.md defines the shared universe, causal
actions and level-driven execution. There is no fixed holding period. This is
seen development history, not untouched promotional evidence. Fit is blocked
until the independent FULL oracle audit has exact status
`PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT`. Synthetic tests are allowed.
The pilot audit cannot authorize fitting. The full audit must bind the canonical
engine root, engine and runner SHA256, final completion, final index, dataset
contract, cache contract and cache full-summary hashes, with exactly2595 available
and6 missing ticker-days. Recheck these identities before and after test evaluation.
Every consumed action/label/advantage sidecar is checked against the audited index;
feature packs must bind those same raw-cache hashes and causal action inputs.

Use 2023–2024 for fit, calendar 2025 for policy selection, and January–June 2026
for the frozen chronological development test. All three tickers share models.
The action set is exactly the oracle engine's causal offered set. Inference sees
state/action features only: no future fills, oracle-selected target, realized
exit, duration, reward, DP value or teacher label. Evaluate the chosen action
through the same engine; missing fills never trigger a replacement action.

There are exactly three candidate fits, seed 20261018 for each:

1. `gbt_net`: action-conditioned LightGBM L2 regression of realized net return.
2. `gbt_advantage`: identical estimator fitted to DP advantage versus waiting.
   This privileged-teacher diagnostic is not a causal Bellman-value estimate;
   expectation of a clairvoyant maximum can be optimistically biased.
3. `tcn_teacher`: a small causal temporal CNN over all 12 completed 5-minute and
   8 completed 15-minute candles, plus a CNN over all 20×5×64 spatial-map cells,
   conditioned on the causal action vector. Its main head predicts realized net
   return; a separate auxiliary binary head imitates the DP-best action at each
   state (strictly positive advantage, stable action-ID ties). The auxiliary
   target is training-only, and its probability is never a trading score.

LightGBM: 200 trees, 31 leaves, depth 6, minimum child 100, learning rate .04,
L2 penalty 10, max_bin63, deterministic column-wise training, four threads.
CNN: temporal channels32, kernel3, two residual causal layers at dilations1/2;
spatial channels8 then16, kernel3; action/context MLP64; joint MLP64→32.
AdamW lr0.001, weight_decay0.0001, four epochs, day-shuffled batches with at most
1024 actions, gradient-norm clipping1. No early stopping, validation epoch
selection, architecture sweep, seed sweep or test-driven refit.
Identical repeated states share one encoder calculation and backpropagate through
the action gathers; there is no dropout or batch normalization. Fixed20×4 average
pooling produces the same spatial8-bin output as adaptive pooling and permits
deterministic CUDA backward. Training feature-moment reductions use fixed256-row
chunks to bound temporary memory. These are prefit implementation choices.
At each completed neural epoch, save model, optimizer, NumPy generator/global
state and CPU/CUDA RNG states with training-artifact, source, audit and code
bindings. A technical resume may reuse only the latest complete epoch in the
same output root/device/software, before validation or a completed final TCN.
Resume never refits the GBTs or repeats committed epochs; it explicitly records
any replay of an uncommitted partial epoch. Keep prior partial files and logs.
An epoch checkpoint is recovery evidence, never an alternative validation choice.
Resume binds Torch, NumPy and LightGBM versions as well as code. A write interrupted
between checkpoint and metadata publication fails closed and requires preserving
the orphan before any recovery; this does not promise recovery from every crash.
The runtime launcher waits for the designated full-audit file, complete feature
packs, at least10GiB available RAM,12GiB free Windows commit and3072MiB free VRAM.
It sets OPENBLAS/MKL/NUMEXPR/OMP thread environment to1 before imports; the explicit
four LightGBM and Torch CPU threads remain unchanged. It records stage wall time
and sampled process-tree private/RSS peaks without changing other workloads.
Loss = importance-weighted squared scaled-net error + 0.1 times
importance-weighted auxiliary BCE. No reward clipping or dropping losing trades.
For every full or partial day batch, sum globally mean-one weighted row losses
and divide by the fixed denominator1024. Do not divide by batch size or the sum
of batch weights. The regression objective is population risk-normalized squared
error, not unscaled USD-squared error.

The feature builder supplies a complete causal state tensor and masks. GBT uses
the causal base, the full candle tensor and masks, plus 8 fixed equal-width
spatial-bin means per map channel/time and map masks. The CNN receives the full
maps and candles. Missing values remain explicit through masks; CNN numerical
imputation and standardization use training-only statistics. Neither model
receives historical receipt guarantees from the source proxy-clock flags.

Training row budget is fixed before outcomes: split all training actions into
the actual base-oracle trajectory actions and all remaining actions. In each
stratum keep the 250,000 smallest deterministic hashes of
seed|ticker|date|action_id, or every row when that stratum is smaller. Unused
budget is not transferred. Inclusion weight is population stratum size divided
by selected size, normalized to weighted mean1 for fitting. These weights
preserve the population action-regression objective; they are not balanced
winner/loser training. Both GBTs and the CNN use the identical sampled rows.
The auxiliary per-state teacher label is distinct from the trajectory sampling
stratum. No validation/test sampling: score every offered action.
The priority implementation is SplitMix64 applied to action_id XOR the first
eight big-endian bytes of SHA256(seed|ticker|date). Exact hash ties use
ticker/date/action_id order. IDs are join/sampling keys only, never features.
The cache's contract axis can contain contracts not yet observed; contract_i,
action_id, total-day contract counts and level ordinals are prohibited inputs.

For each ticker, define a fixed training risk scale as the importance-weighted
median actual entry premium (entry_ask×100) among positive, filled sampled
training rows. This is a historical training constant, never a future state
feature. A missing/nonpositive scale fails closed. Both regression targets use
net/scale or DP-advantage/scale; predictions are converted back to USD before
trading thresholds. The CNN feature moments and all target/risk scalers are fit
only on the sampled training rows, with the same importance weights.

At every flat state select maximum predicted USD score, stable lowest action ID
on ties, against WAIT=0. Candidate thresholds are exactly 0,5,10 USD; an action
must strictly exceed its threshold. Inventory, target, stop, latency, missingness
and exit_index+1 re-entry follow the shared engine, not the oracle trajectory.

Select once on 2025 from CASH and the nine model/threshold policies. Score is
sum of executed validation net USD divided by that ticker's fixed training risk
scale. CASH has exact score0 and wins all ties. Model order for remaining exact
ties is gbt_net, gbt_advantage, tcn_teacher, then lower threshold. Thus all
nonpositive validation scores select CASH. Report raw USD, costs, trades and
per-ticker results as well as the normalized selection score; a winning
normalized score is not itself evidence of broad profitability.

Freeze models, sampling manifest, training scalers, feature/action schemas,
validation comparison and selected policy before computing learner test
economics. Test oracle outcomes already exist as descriptive privileged labels;
the learner-selection code must not use them. Report all nine frozen candidate
policies diagnostically and the single selected policy, clearly separately.
No test candidate can replace the selected policy. CASH is not a profitable
learner merely because it avoids losses.

The parent's provisional economic gate is simultaneous in SPXW/SPY/QQQ over
2026H1: base and adverse net positive, base PF≥1.2, at least60 trades per ticker,
and at least3 of6 positive months. Passing remains development evidence, not
live parity, observed source arrival, prospective validation or promotion.
Preserve every fit and result, including failure or CASH selection.
Require the entire declared 2,595 available ticker-day universe before a market
fit; the six known missing Greek ticker-days remain zero-trade days on the full
NYSE calendar. Report daily and monthly results for every candidate. Drawdown
uses realized trade net in exit-time order, not unobserved intratrade mark-to-market.
Report TARGET/STOP/EOD trade counts and base/adverse net separately, together with
minimum/median/maximum holding minutes, for every candidate and ticker. These
diagnostics do not alter selection and distinguish level exits from forced EOD.
