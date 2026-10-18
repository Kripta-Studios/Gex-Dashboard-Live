# Fixed causal continuation: completed development experiment

The original three-fit experiment completed with process exit 0 at 2026-10-18 20:18:50 UTC. It did not find a profitable policy. The independent audit completed with PASS at 20:58:32.851 UTC, reconstructing the economic results given sealed scores. This is an integrity/reconstruction PASS, not a profitability PASS.

The frozen 2025 selection chose `causal_residual__5`. Both residual thresholds 0 and 5 executed at least one trade on every observed full-session ticker-day in 2025. Eligibility concerned daily participation; its selection score and economic return were negative. The selected policy was frozen before any 2026 evaluation by this run. All six predeclared policies were subsequently evaluated as development diagnostics, without reselection.

| Selected policy | Trades | Net base USD | Profit factor | Win rate | Observed ticker-days without a trade |
|---|---:|---:|---:|---:|---:|
| 2025 validation | 3,445 | -39,673.00 | 0.918464 | 21.51% | 0 / 741 |
| 2026 January–June development | 1,623 | -46,085.80 | 0.819035 | 22.30% | 0 / 363 |

The selected policy's adverse-cost net was -46,548.00 USD in validation and -49,324.80 USD in development. The terminal no-trade penalty is a training target component only and is excluded from every economic figure. Position size and execution conventions remain those in the original method; aggregate USD does not imply a financed account return.

| Ticker, selected policy in 2026 | Trades | Net base USD | Profit factor | Positive months |
|---|---:|---:|---:|---:|
| SPXW | 641 | -33,938.60 | 0.839266 | 1 / 6 |
| SPY | 471 | -5,196.60 | 0.702276 | 1 / 6 |
| QQQ | 511 | -6,950.60 | 0.733338 | 1 / 6 |

All three ticker economic gates fail. None of the six candidate policies has positive aggregate net in either evaluation period. The direct-net control at threshold 0 had a smaller aggregate loss in 2026 (-36,076.60 USD) but missed ten observable ticker-days; it was not eligible under the 2025 daily requirement. These diagnostic comparisons cannot change the frozen selected policy.

The expected full-session 2026 universe contains 369 ticker-days, of which six have missing sources: SPY and QQQ on 2026-04-01, 2026-04-09 and 2026-04-15. Thus the selected policy has zero no-trade days among 363 observable ticker-days, but six failures to demonstrate execution across the 369 expected ticker-days. The original experiment also excludes early-close sessions: 24 ticker-days across the complete 2023–2026 H1 period, including nine in 2025. It therefore does not establish the user's universal requirement of a trade on every trading day. A separately specified, inference-only extension may assess those nine 2025 cases without changing this experiment.

The fixed teacher's realized continuation replaces clairvoyant maximization in the training label. This removes that particular target mismatch; it does not guarantee profitability or repeated policy improvement when the learner is deployed at every subsequent decision. The residual model predicts h0 < h1 on 647,688 of 2,406,690 development actions (about 26.9%), although the exact constructed residual labels have the opposite weak ordering. This was a predeclared diagnostic only: no clipping or correction was applied.

## Independent audit and its limits

Status: `PASS_INDEPENDENT_CAUSAL_ROLLOUT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES`.
Artifact: [audit.json](D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_v1_economic_audit/audit.json).
SHA256: `6dd69574ed50a5d3d26587b488b347874c40908d55ff8d8b19d2a95d9c581cd3`.

The audit independently reconstructed the canonical sampling and IPW weights, H1 risk scales, fixed-policy Gπ and Aπ targets, paired h0/h1 matrix columns versus sealed chunks, and the three fit signatures/configurations. It then reproduced all six policies' attempts, fills, ledgers, economic summaries and calendars for 741 validation and 363 observable development ticker-days. The 2025 selection of `causal_residual__5`, its pre-test freeze and the six separate NO_EVALUABLE missing-source cases were confirmed. The terminal penalty was excluded from economic PnL. All 33,786 retained artifacts were rehashed at completion without discrepancies.

There were **zero independent refits**, **no regenerated model predictions**, and **no independent reconstruction of raw feature values**. Matrix/chunk agreement and sealed provenance do not substitute for those checks. The audit does not establish observed historical receipt, live parity, a fill on missing or excluded sessions, or future profitability. Its full-session calendar confirms participation on available sessions only; the six absent development ticker-days and the early-close scope limitation remain unchanged.

Auditor SHA256: `3286a1bae8d2525129a608c0924b6124ad19af4d92974bd4b44f1d8c186ffd33`.
Auditor runtime was 2,340.481 seconds; the supervising process closed with exit 0 after 2,346.600 seconds. Sampled peak private memory was 593,711,104 bytes and peak RSS 2,702,786,560 bytes, including mapped matrix pages. The separate runtime and detailed review are in `causal_rollout_v1_economic_audit_runtime` and `CAUSAL_ROLLOUT_ECONOMIC_AUDIT_REVIEW.md`.

## Execution and provenance

All stages used the original PID 38048 and unchanged scientific runner. No resource recovery wrapper or relaxed gate was activated. Teacher, control and residual fits used four CPU threads sequentially; 1,119 teacher rollouts and 1,119 final matrix chunks completed. The prepared teacher contains 47,430 rows × 1,954 columns; final learners share exactly 285,286 rows × 1,955 columns and the same weights. Runtime measurements are documented separately in `CAUSAL_ROLLOUT_RESOURCE_NOTE.md`.

- Output root: `D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_v1`.
- Run binding: `66ef48eca5aadca70726b1c66997c93dd513ebf7a32283e07e26fc7e3c129a9d`.
- Runner SHA: `d031eca08c71ad89324619e096dcc9be3966ddea23d52061019018ff6ff58a43`.
- Implementation-review JSON SHA: `0ca688d835814ac22ff9700b2b89861e0b52994e869dbfb5d269d7e7c89cfe9f`.
- Teacher model SHA: `e9af185ca8e1d6f963ef4c31b0e9e9aaa99ccb4136b835c9622c128e6b7e1be0`.
- Net-control model SHA: `12b8d5a00d06bb482fc6de66263e8c270929d0d276e226a9889e283a801a09ef`.
- Residual model SHA: `9fe6a42d2a04459b5eff4b018518a224865b58f2af89ca5903b6e77651303117`.
- Validation summary SHA: `390c13f507ffbc4901dae7ca40cd2c81a5a59e3edd87d1f5e726e14a99c79283`.
- Selection freeze SHA: `a5cda27adeade05f4e8f9577b8fd0e8483eb37690f812342a573b5cab849b6af`; completion timestamp 20:13:59.418719 UTC.
- Development summary SHA: `01e9e17d7d088ce03b87280a85403c834adb1115409068a0456e5986a0dfbc63`.
- Development h diagnostic SHA: `572dc767d9611fe25e02755f28a951bc486a5f9576f788d84aa1c9ae02055c4d`.
- Closed five-second process-memory log SHA: `70c186af047231a5fa51554c6f6b26411327b02ad55e0748b257301482e26379` at `D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_runtime_v1/pid38048_memory.jsonl`.

2026 remains previously seen development data. This result provides no prospective profitability claim or authorization to operate a live strategy. Existing data, earlier attempts and production remain unchanged.
