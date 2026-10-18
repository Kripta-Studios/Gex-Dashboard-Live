# Operational recovery proposal — not activated

The scientific producer remains `train_causal_rollout.py` SHA d031eca08c71ad89324619e096dcc9be3966ddea23d52061019018ff6ff58a43. The model, feature schema, sample, targets, normalization, seed, weights, candidate policies, calendar and selection stay unchanged. This proposal is solely a reviewed launcher around already completed checkpoints and a smaller teacher memory gate. PID38048 is presently retained.

## Admission without repeating the top-K computation

Pin the original run-contract SHA66ef48eca5aadca70726b1c66997c93dd513ebf7a32283e07e26fc7e3c129a9d, prepare marker SHA681447d60f6e1b39c9f484e550c2573f33c0bbe7e1e556e21776ebfaf09767a8, teacher sample SHA3659955947ed2b603af78aa562b1526dea674f266a44b1583c81baf691bc0e19 and final sample SHA6811c520993c0c0baa4f3dd38e45612d92298631dc991141b62313b6ca55ed7a. Require the existing implementation review and all nine source-code hashes to match. Preserve the original run contract and marker bytes.

The original `main` still validates the independent source audit, exact calendar and run contract. Replace only the repeated sampling admission with a checkpoint verifier that:

1. Verifies the complete prepare marker and both sample markers/bytes against the pinned hashes.
2. Derives the exact372teacher/1119final day keys from the independently admitted calendar; their union must equal the1491 entries in the prepare marker's `source_action_hashes`.
3. Rehashes **every full actions.parquet file** using `SourceSeal.check`; each SHA must equal both the immutable engine index and the pinned prepare source map. No subset-only validation.
4. Checks sample role/day counts, dimensions, weights and key arrays as already sealed; any missing or differing source/checkpoint fails closed. No fallback sampling, repair or adoption.

This proves that the complete input population, deterministic sampler/configuration and sampled output bytes are identical to the already executed full reconstruction. It does not infer top-K from the selected subset. The expensive6.37M+2.04M identity serialization/hash/sort operations need not be rerun when **all their inputs and outputs are byte-identical**. Expected cost is sequential hashing of1491files, not the roughly13minute full reconstruction. Actual duration must be measured.

## Teacher-only cached-chunk admission

The original teacher stage already completed all372chunks, risk scales and teacher matrix before waiting. Its normal restart would decompress/validate feature packs again for approximately5minutes even though it does not rebuild any complete chunk. A further optional optimization can provide a **teacher-only hash-verifying store** to the unmodified original `teacher_stage`:

- Require every teacher chunk, feature-input manifest, matrix and risk-scale checkpoint complete before using this path.
- `get(day)` verifies the feature-input manifest marker and rehashes all four original feature/metadata files. The original first-use manifest was produced only after full `FeatureStore` validation against the audited cache; its bytes, raw-cache/index binding and dependencies must be unchanged.
- The original teacher stage continues to rehash the day's realized-label source, load complete chunks, reconstruct targets/scales and call the original `fit_once`.
- `rows()` must fail unconditionally: this recovery path cannot construct new features or silently fill an incomplete chunk. Original `VerifiedFeatureStore` remains in use for every subsequent rollout/evaluation stage.

If this extra adapter is not reviewed, simply retain the normal teacher stage and accept its approximately5minute replay. Full source hashes, existing artifacts and scientific calculations remain authoritative in either case.

## Resource gate and process transition

Teacher only:8GiB available RAM and10GiB free Windows commit, based on the nonformal allocation estimate in `CAUSAL_ROLLOUT_RESOURCE_NOTE.md`. Final models retain the original12/16GiB gate. The launcher scopes its replacement of `wait_resources` only around the original `fit_once('teacher',...)` and restores the original function in a `finally` block. No estimator/configuration/target function is replaced. Record the launcher's hash, authority, old/new PID, checkpoint hashes and observed RAM/commit; retain5second process-memory telemetry.

Do not terminate PID38048 while it could be starting a fit. After review and explicit parent activation, suspend **only that owned process**, then inspect whether `models/teacher.fit_started.json` or a teacher model has appeared. If either exists, resume the original process and abandon this transition. Only when both are absent and the recorded state is WAITING_RESOURCES may it be terminated and replaced by the reviewed launcher. Preserve every original partial/file and the fact that this was an operational pre-fit interruption, not a model failure. The original OS lock is released by process exit; the replacement must acquire it normally. Interrupted fits remain non-retriable automatically.

Required fixtures before activation: unchanged complete source/checkpoints accepted; changed unselected action file rejected; changed sample/prepare/dependency rejected; missing chunk rejected; teacher lower gate restored before either final fit; cached feature metadata replacement rejected; no estimator call before the new resource gate; no refit after fit_started. Independent review should bind the launcher and this operational proposal. No change has yet been activated.
