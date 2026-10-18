# Nine early-close sessions: completed inference extension

The extension completed with process exit 0. The selected policy executed at least one trade on all750 expected ticker-days in2025 when the nine early-close cases are added, but it lost money. There was no refit or reselection. `causal_residual__5` remains the policy selected from the original741 full ticker-days.

| Selected policy, fixed threshold5USD | Trades | Net base USD | Net adverse USD | Profit factor | Ticker-days with at least one fill |
|---|---:|---:|---:|---:|---:|
| Original2025 full sessions | 3,445 | -39,673.00 | -46,548.00 | 0.918464 | 741 / 741 |
| Added2025 early closes | 37 | -2,606.20 | -2,679.20 | 0.041838 | 9 / 9 |
| Combined2025 | 3,482 | -42,279.20 | -49,227.20 | 0.913590 | 750 / 750 |

The added cases are SPXW, SPY and QQQ on July3, November28 and December24,2025. Each uses close_i210, last decision195 and final forced exit205. Both original models scored the same six predeclared model/threshold policies. Scores were sealed before each day's outcomes. The observed daily fill flag, no-overlap scheduling, no-fill behavior, original scales and execution costs were preserved. No terminal training penalty enters economic PnL. The15 early-close ticker-days in2023–2024 were not retroactively added to training.

| Combined2025 selected policy | Trades | Net base USD | Profit factor | Positive months |
|---|---:|---:|---:|---:|
| SPXW | 1,385 | -20,805.00 | 0.949421 | 4 / 12 |
| SPY | 1,032 | -7,913.20 | 0.783928 | 2 / 12 |
| QQQ | 1,065 | -13,561.00 | 0.671875 | 1 / 12 |

All three economic gates remain false. Each of the six fixed policies has negative aggregate net both on the added nine cases and on the750-day union. Daily participation on this historical2025 population is independently reconstructed given sealed scores; it is not a profitability result or a guarantee of future fills. The original2026 development result remains unchanged:363 observable ticker-days with fills for the selected policy, six missing-source cases among369 expected ticker-days, and negative economics. There are no early-close sessions in January–June2026.

## Verification scope

The extension had a prior independent code review and17 synthetic fixtures passing. Its producer verified all73 exact completion members and external source hashes before and after publication. An additional read-only check after exit verified73/73 members against the final marker. The original741-day calendar counts and daily net totals agree with the original sealed evidence, and the selected-policy hash is unchanged.

The separate independent extension audit completed at2026-10-18 21:10:28UTC, exit0, with status `PASS_INDEPENDENT_CAUSAL_SHORT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES`. It reconstructed all six policies' nine daily attempts and ledgers, strict thresholds, stable action ties, h0/h1 transitions, short-session bounds and ask-to-bid costs. It verified the exact73 closure members and2,394 retained file hashes, reproduced the short9 and combined750 summaries/calendars, and matched the original741 days against their prior independent audit. The XNYS calendar independently supplied250 sessions×3tickers. Selected `causal_residual__5`, model hashes and the original selection freeze remained fixed.

Audit artifact: [audit.json](D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_short_sessions_v1_economic_audit/audit.json), SHA `a3ae3bcaa517c5add7cf0c1f4f7bfb3a59cf4e99ebddf49894447545807c5909`. Ten synthetic fixtures, Ruff and compile checks passed; runtime88.84seconds. The final audit was published atomically after input rehash.

Scope is **given sealed scores**, with zero independent refits or regenerated predictions. Raw feature values, raw quotes and barrier hits were not independently replayed here; costs were reconstructed from the independently audited source labels. The prior original audit remains the authority for the original741 days and2026 evaluation. This extension audit did not re-audit2026 source data or establish live receipt parity or future profitability.

## Artifacts

Output root: `D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_short_sessions_v1`. Original output root and models are unchanged. The isolated process was PID6376, started2026-10-18 20:59:41UTC; the completion marker was published at21:02:09.446440UTC, followed by a final rehash and successful process exit. Runtime performed only inference and aggregation; no fit occurred.

- Run-contract SHA: `8a783ffe47711fe8b2bae571e77fc8354a610c10467c2f1dc316ddc706a11fe0`.
- Completion JSON SHA: `cb24eaa3c1bfd462259a1758d19a4ec588e129edb7e009d9d888f54ed73c607f`.
- Completion marker SHA: `9aa94c1439407d9ab797136f4565a1b45ec0fe6c1a2be864f66848b0fd16c5b4`.
- Summary SHA: `cb362fd33b7cfa2f195dc01699861db8ec93f1d22ed14497756a8386af08d89a`.
- Source-hash manifest SHA: `3d3377033403a01cb6aff37b2419815eb1a5a5b7cd14e3a38b1397a17eae4eb3`.
- Prior implementation-review SHA: `6818076c98a5b7af826f1c73d0038c0a2b0a8d6e29eaa3de50c2bb6623bf1f64`.
- Original economic-audit SHA: `6dd69574ed50a5d3d26587b488b347874c40908d55ff8d8b19d2a95d9c581cd3`.
- Original policy-freeze SHA, preserved: `a5cda27adeade05f4e8f9577b8fd0e8483eb37690f812342a573b5cab849b6af`.

The extension was specified after the original results were known solely to complete the requested calendar coverage. Its outputs are historical development evidence and do not create an unseen evaluation period.
