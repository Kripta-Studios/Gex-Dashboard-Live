# Session clock extension

This separate implementation adds NYSE 13:00 sessions without altering the
frozen cache, engine, features, data or previous results. It has no market CLI.
Only synthetic fixtures have executed the short-session economic functions.

`session_clock.py` defines immutable clocks: full close390, states60–375,
EOD385; short close210, states60–195, EOD205. Both begin09:30 and retain the
same first-hour IB, sampled-price semantics, costs, level rules and action
schemas. The final short decision is12:45, next-minute entry12:46, last
possible trigger12:54 and liquidation12:55. The13:00 boundary is retained
as an observation but cannot be used by an offered action.

`session_cache.normalize_day(greek, oi, ticker, date, clock)` delegates full
sessions unchanged. For shorts it removes Greek effective-clock records and
native OI reports strictly after13:00 BEFORE the frozen parser constructs the
contract union. Native quote timestamps take priority; otherwise the existing
underlying snapshot clock assumption applies. Timestamp-less OI keeps the
explicit assumed09:30 availability. Invalid clocks remain invalid. The result
contains211 observations; neither repeated positive postclose quotes nor
postclose-only contracts survive. Input frames remain unchanged. Removal
counters describe source coverage, not model features.

`session_level_engine` exposes the original pure API with a final `clock`
argument (default FULL). Full calls delegate unchanged; short calls use explicit
local clock parameters, with no monkeypatching or runtime source rewriting.
Gamma remains an unsigned BS dollar-gamma proxy and expires at the declared
NYSE close; it does not estimate dealer positioning. OI invalidation, causal
known-contract denominators and missing-quote rules remain unchanged. Short DP
buffers contain207 physical minute slots and remain zero after state195.

`session_features.build_day_feature_cache(raw, clock)` retains the clock in
short intermediates; `encode_state(cache, minute)` and `encode_states(cache, indices)`
use it. `action_features(raw, actions, clock=...)` requires the caller to pass
SHORT for a short session. Shapes remain B81,20×45 candles,20×5×64 maps,A33;
the number of states is136 or316. Minute and bar age keep physical /390 units;
remaining time is `(close_i-minute)/390`, so a short day is not stretched.
Completed5/15-minute bars end strictly before each decision. IB uses only0:60;
past map normalization and explicit missingness are unchanged.

Thirteen synthetic tests pass, including exact full cache metadata/arrays,
full states/levels/actions/labels/DP/scheduler/features, native and proxy tail
filtering before duplicate/identity checks, short boundaries, independent
gamma arithmetic, future values plus future-only contract perturbations at
60/119/195, OI invalidation and NO_FILL without same-minute rescue. Ruff passes.
Full source implementations remain unmodified. The next bounded step is a
separate incremental dataset wrapper, preserving the old full-session paths
and building only24 short ticker-days. No new market fits or short-session
economic execution are authorized by this document.

The separate `build_session_dataset.py` now implements that incremental wrapper.
It requires the explicit `--build` CLI flag; it has not executed on market data.
The fixed all-session index has2625 identities:2595 full-day references,24 new
short days and the same six missing-source identities, marked NO_EVALUABLE.
There are no new fitting or selection operations. Full-day NPZ/parquet paths
remain original; only small feature metadata sidecars normalize the shared
schema/dependency contract. Index columns give direct cache, feature, action
feature and metadata paths, plus engine day_root, close_i and their hashes.

Short days publish states/levels/actions and both feature packs before a causal
seal, then construct labels. Complete markers enumerate consumed files and
hashes. Resume validates membership, binding and hashes; incomplete directories
are preserved under unique names. A kernel writer lock prevents concurrent
writers. Writes use temporary files, fsync and atomic replacement. The builder
uses one process and never replaces previous roots. Four additional synthetic
disk fixtures pass, including tamper rejection, missing seal membership,
incomplete evidence preservation and explicit calendar coverage. Dataset
execution and its independent review remain a separate next action.
