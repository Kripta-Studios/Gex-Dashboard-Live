# Read-only review of causal rollout preparation

2026-10-18. **PASS_PREPARE_ONLY_REVIEW**. Scope is the `--stage prepare`
integration, not the outcome-consuming learner, rollout evaluator or full
implementation approval. No historical preparation or fit was executed by this
reviewer. The parent may schedule the separate one-worker prepare pass.

Reviewed runner SHA256:
`f9768eb1546b5e36283725c0d6815d60dd99f05a86dae3942dfdd2963f9220d1`.
Sampler SHA256:
`8bc8cee2b89cf70490793b88d74dff558bbd60077d383a852392fcc2383c748c`.
Formal plan SHA256:
`4313fb6165d74bb50e8826a7b54ac7e961d9b273085c3fb7d2667dc89a13f939`.
Runner fixture file SHA256:
`9deec7f8074e98406537bf406b32edc250b155efb82db1fc3aca88b5448bc78c`.

The prepare call path uses its own SourceSeal, whose index projection contains
identity, source-completion status, roots and source hash strings. It does not
load the legacy full-index seal or invoke the legacy outcome-based sampler.
The only daily table values read are actions.action_id and actions.state_i.
Full action bytes are hashed before and after projection, against the audited
index; hashing is not parsing other columns into the sampler. Labels, oracle
advantages, teacher predictions and feature pack values are not read. The
existing audit binding and feature-contract file are metadata dependencies.
FeatureStore is instantiated only after the prepare branch returns.

The complete full-session calendar is checked before sampling: 867 sessions,
2601 expected ticker-days, 2595 available and exactly six declared missing
sources. Teacher is 2023 H1 (372 ticker-days); final learners use 2023 H2 plus
2024 (1119). The resulting 1491 training ticker-days are selected by period,
not outcome, fill or profitability. Global completion checks the two exact
day counts. Empty-day samples fail rather than silently dropping their mass.

The caller projects identities into the fixed sampler. Four population and
selected band counts, including zeros, are saved per day. Selected rows carry
canonical SHA256 identities and raw IPW weights. Teacher rows remain unique;
final rows pair h0/h1 adjacently with half weights and common mean-one fit
weights. IDs are retained for joins, not numerical model inputs. Every resume
reconstructs the selection from every offered source action and compares every
stored sample array exactly; it does not trust a previous top-K subset.

The output root has an OS-backed exclusive lock. NPZ and JSON publication uses
unique temporary files, fsync, atomic replacement and post-publication hashing.
Complete markers bind files to the run contract, including exact dependency,
source-audit and software versions. Corrupt completed artifacts fail; orphan
NPZs are preserved and rejected instead of silently adopted or overwritten.
Executed code snapshots are retained. Before publishing prepare.complete.json,
the runner rechecks code dependencies and the complete source-audit binding.
That marker binds both sample NPZs, day/row counts, source action hashes,
elapsed time, and labels_read/features_read=false.

The audited engine/source bindings retain the existing clock/availability
convention and decision bounds. This prepare stage neither replaces clock
semantics nor revalidates raw quote timestamps; that remains prior source
audit evidence. Offline full-day identity sampling is not a live decision
feature and is not prefix-invariant when later offered identities change.
It is independent of future labels and does not change retained causal features.

Verification: reviewer ran the 25 pure sampling fixtures successfully. The
initial combined runner check exposed six failures from one Windows issue:
fsync of a temporal descriptor reopened read-only. Owner corrected the private
temporary reopen to r+b; reviewer inspected the correction. Owner subsequently
reported all 15 runner fixtures and Ruff passing. Those fixtures include
identity-only projection/replay, tampering/orphan rejection, exclusive locks,
exact implementation bindings and checkpoint integrity. The final static
prepare review includes the corrected descriptor and the final dependency/
source rechecks and persistent completion marker. No unresolved prepare blocker
was found. A separate full learner audit is still required for economic stages.
