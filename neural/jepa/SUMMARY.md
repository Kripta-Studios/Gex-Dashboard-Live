# JEPA Summary

## 2026-07-01 Dense15 Backfill19 SPY June-Positive Production Package

- Promoted a new event-option production package: `neural/models/jepa/jepa_production_event_options_backfill19_spy_no_scorethr_wf2026_fullmayjun`.
- Causal WF2026 full-May-Jun result: `research_papers/JEPA/results/event_option_dense15_backfill19_spy_no_scorethr_wf2026_fullmayjun_production_v1`.
- Strict verification passes with `--strict-month-trades --require-positive-months`: SPXW 125 trades, WR `51.20%`, PF `1.749`, min month `19`; SPY 122 trades, WR `50.82%`, PF `1.722`, min month `19`, June PnL `+$10,000`; QQQ 178 trades, WR `46.07%`, PF `1.424`, min month `19`.
- Overall: 425 trades, WR `48.94%`, PF `1.598`, PnL `+$194,500`, all tickers 6/6 positive months. Fold integrity passes over `36` folds and backfill audit passes over `19` rows.
- Curve health passes for all tickers. Runtime monthly-backfill replay reproduced `425/425` trades with `0` missing/extra rows, and snapshot-to-order smoke passed using SPY `win_no_scorethr_d25`.
- Anti-snooping support for SPY rule: the same `win_no_scorethr_d25` policy passes a separate 2025 causal audit before 2026 evidence: 354 trades, WR `50.00%`, PF `1.656`, min month `19`, positive months `12/12` (`research_papers/JEPA/results/_diagnostics/event_option_gate_dense15_zero_dte_win_no_scorethr_d25_physctx_wf2025_spy_v1/VERIFICATION_wf2025_spy_no_scorethr_presupport.md`).
- Updated `production_manifest.json`, `systemd/ai_bot.service`, `systemd/realtime_feed.service`, and `push_models.ps1` to the new package. Raw coverage still records `202605` as partial; this package follows the operator instruction to assume `202605` complete and `push_models.ps1` validates with `--ignore-raw-thetadata-coverage` only when the policy records that assumption.

## 2026-06-30 Target22 Backfill Audit Rejected For Production

- Tested a fixed-source backfill target sweep `18..24` with pre-2025-only selection evidence (`202301..202412`, excluding raw-partial `202403`). This was required because `target22` looked strong on the `202501..202604` holdout, but choosing it from that holdout would be data snooping.
- Result: no target in `18..24` is selectable pre-2025 under the requested gates. `target22` pre-2025 observed metrics are SPXW WR `47.05%`/PF `1.482`, SPY WR `43.26%`/PF `1.257`, QQQ WR `44.17%`/PF `1.310`; SPY and QQQ fail before the evaluation window starts.
- Therefore `target22` is not promoted, even though its `202501..202604` holdout robustness is cleaner than `target18`. Current production remains the conservative `systemd` path: required level-stability signal + required structural option profiles, event-option disabled, OptionValue disabled.

## 2026-06-30 Frozen Pre-2025 Event-Option Package Export

- New blocked package: `neural/models/jepa/jepa_production_event_options_frozen_pre2025`. It packages the best pre-2025 frozen Dense15 0DTE research candidate as live-loadable components for deploy `202607`, trained/selected only through raw-complete `202604`.
- Contents: 6 exported LightGBM gate models, 3 `monthly_backfill18` policy components, `event_option_policy.json`, `component_registry.json`, and completed-month audit sidecars. Registry loading passes; scorer smoke on a diagnostic live snapshot produced candidates without issues.
- Research validation passes for the requested gates when known caveats are explicitly allowed: SPXW WR `57.82%`/PF `2.285`/min `19`; SPY WR `53.63%`/PF `1.925`/min `19`; QQQ WR `50.48%`/PF `1.699`/min `19`.
- Runtime policy replay now passes: `1162/1162` frozen trades reproduced with `0` missing/extra keys. Still not live-ready: curve health fails, statistical robustness fails, source-universe freeze is reconstructed rather than timestamp-proven, deploy-scorer historical replay is not proven, and no paper/broker fills exist. `systemd` stays on the conservative level-stability + structural-profile path.


## 2026-06-30 Pre-2025 Frozen Dense15 0DTE Static Selector

- Best current pure-0DTE holdout artifact:
  `research_papers/JEPA/results/_diagnostics/frozen_source_selector_dense15_pre2025_static_202501_202604_v1/combined`.
  Selection is frozen before `202501` using only `202301..202412` evidence
  excluding raw-partial `202403`; evaluation is raw-complete `202501..202604`.
- Observed gates pass on the evaluation window: SPXW WR `57.82%`/PF `2.285`/min
  `19` over `358` trades; SPY WR `53.63%`/PF `1.925`/min `19` over `386`
  trades; QQQ WR `50.48%`/PF `1.699`/min `19` over `418` trades. Overall:
  `1162` trades, WR `53.79%`, PF `1.939`, `+151.254R`.
- Audits pass for metric gates, `48` fold integrity rows, `70` backfill rows,
  pure `zero_dte` trade mode, feature leakage (`0` selected leaky features),
  and strict research-selection using the reconstructed manifest.
- Robustness is not fully production-clean: Wilson, bootstrap, and
  leave-one-month-out pass, but top-winner stress fails SPXW/SPY because min
  monthly trades drop from `19` to `16` after removing the top `5` winners.
- This candidate is not activated in `systemd` yet. It needs a production
  event-option policy/scorer export, live bot/feed integration, timestamped
  forward freeze evidence, and paper/broker fill evidence. The deployed systemd
  path remains level-stability signal plus nested structural option profiles
  with event-option and OptionValue disabled.

## 2026-06-30 Dense Frozen Guarded Candidate

- Added `audit_event_option_feature_leakage.py` and audited the raw-complete
  monthly walk-forward plus new 32-worker fixed-holdout variants. The source
  parquet contains `80` obvious future/outcome columns, but the deployed feature
  builder selects `0` leaky features; selected trades are pure `zero_dte`; and
  `24` raw-complete folds have no same-month or future-month lineage.
- Rechecked the true month-by-month walk-forward artifact
  `research_papers/JEPA/results/_diagnostics/dense_candidate_walkforward_2026_completed_jan_may_v1`
  on raw-complete `202601..202604`: observed gates pass, but robustness is
  `false` (`wilson`, `bootstrap`, leave-one-month-out, and top-winner stress
  are not all clean). This is causal evidence, not production evidence.
- Ran fixed pre-2026 holdout variants with `--lgb-jobs 32`.
  `dense_candidate_frozen2025_select12_eval_202601_202604_v1` passes observed
  gates but fails robustness; `select18` fails production gates because all
  ticker call rates are below the `20%` floor. No dense/event-option candidate
  is production-ready from this pass.
- Updated `systemd/ai_bot.service` to the canonical deployable path:
  required level-stability signal + required structural option profiles,
  event-option disabled, OptionValue disabled, and no legacy signal fallback.
  A local bot dry-run loaded
  `level_stability_ensemble_prod_202607` and
  `level_stability_ensemble_nested_structural_profiles_risk5000` successfully.
  `systemd/realtime_feed.service` no longer requires the blocked event-option
  live-ready package; a local feed dry-run produced live parquet/snapshot files
  but timed out during the data-fetch cycle, so it is not counted as a completed
  feed validation.
- Reclassified `research_papers/JEPA/results/_diagnostics/dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0` as the strongest current causal research candidate for the user objective. Raw-complete `202601..202604` verification passes per ticker: SPXW WR `61.18%`/PF `2.626`/min `20`; SPY WR `57.83%`/PF `2.286`/min `20`; QQQ WR `53.57%`/PF `1.923`/min `20`.
- Added `audit_dense_candidate_statistical_robustness.py` and wired it into the dense requirement audit/E2E. The guarded raw-complete slice still passes observed gates and leave-one-month-out, but robustness is explicitly `false`: QQQ Wilson WR lower bound is `42.98%`, QQQ bootstrap 5% WR is `44.05%`, and removing the top 5 winners breaks the monthly-volume gate for all three tickers. Treat the high WR/PF as thin research evidence, not production-proof robustness.
- Added `audit_existing_pre2026_lineage_robustness.py` for an aggregate overfit screen across the existing pre-2026 selection scan. It found `4` eligible pre-2026 + lineage-clean holdout rows, but `0` pass a 95% Wilson lower-bound test for all ticker WR >= `45%`; even the best any-lineage row has Wilson min `42.98%`. This reinforces that the high WR/PF should not be treated as robust production evidence.
- Added `audit_pre2026_lineage_tradelevel_robustness.py` to stress the `4` strict pre-2026 + lineage-clean rows at trade level with 32 workers. All `4` pass observed gates, but `0` pass robustness; all are mixed `front_weekly` + `zero_dte`, so they are not valid final candidates for the requested 0DTE-only system.
- Added `neural/jepa/freeze_static_multistream_manifest.py` and extended `audit_event_option_research_selection.py` so a fixed primary/fallback multi-stream family can pass strict research-selection only when a valid external manifest is frozen before the evaluated window and all evidence months are prior. The guarded dense candidate now has `research_selection_manifest.json` frozen before `202601` and strict research-selection passes for `202601..202604`.
- Re-ran curve-health on the same raw-complete window; all tickers pass with no flags. Re-ran anti-snooping for the guarded frozen directory; checks pass for fold chronology, frozen lineage, pre-2026 guard selection, strict research-selection, and feature leakage. Status artifact: `research_papers/JEPA/results/_diagnostics/dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/PRODUCTION_READINESS.md`.
- This is still not final live production. The exported dense candidate package remains `forward_frozen_research_candidate_not_live_ready`, targets deploy `202607`, and still needs completed `202607+` forward evidence plus live/broker fill validation.
- Updated `audit_dense_candidate_requirements.py`, `validate_dense_candidate_e2e.py`, `validate_dense_candidate_shadow_deployment.py`, and the dense candidate package metadata so `requested_walkforward_objective_passed=true` now means the guarded raw-complete `202601..202604` anti-snooping objective passed. `live_ready_passed` remains `false`. Current E2E evidence: `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/e2e_validation_true_0dte_schema_guard_20260630`.
- Added `validate_dense_candidate_trade_raw_coverage.py` and wired it into the
  dense requirement audit/E2E. It verifies `137/137` offline-fill, paper-order,
  and broker-shaped local payloads have raw 0DTE option parts plus underlying
  files for their selected May-2026 dates. This is trade/order-level coverage
  only and explicitly does not certify `202605` as a full completed month.
- Added `validate_dense_candidate_broker_fill_evidence.py` and wired it into
  the dense requirement audit/E2E. It validates broker/paper/live fills against
  the expected option-order contract; the current artifact fails by design with
  `47` expected orders, `0` fills checked, and `broker_submission_evidence=false`,
  so `live_ready_passed=false` despite the high research WR/PF.
- Added a broad raw-complete verification sidecar for the dense candidate:
  `verification_raw_complete_202301_202604.json`. It evaluates `202301..202604`
  while excluding raw-partial `202403`; it passes ticker gates, but remains
  diagnostic because strict broad historical anti-snooping is still false and
  live promotion still requires completed `202607+` and valid fills.
- Hardened `export_event_option_production_policy.py` with the same raw ThetaData completed-month guard used by production validation. Normal exports now reject `completed_month_validation` windows containing raw-partial months such as `202605`; the legacy bypass is explicit via `--ignore-raw-thetadata-coverage`.
- Added `validate_event_option_export_raw_guard.py` and E2E evidence at `export_raw_guard_validation/export_raw_guard_validation.json`; it asserts the export rejects `202605` and allows raw-complete `202601..202604`.

## 2026-06-30 Event-Option Raw Coverage Guardrail

- Demoted `neural/models/jepa/jepa_production_event_options` from live-ready to
  `raw_coverage_blocked_not_live_ready`. The existing completed-month verifier
  included `202605`, but raw all-ticker 0DTE coverage marks `202605` as
  partial/non-official; official raw-complete SPXW/SPY/QQQ evidence currently
  stops at `202604`.
- Fixed `audit_thetadata_0dte_raw_coverage.py` so option coverage now counts
  true 0DTE files only (`expiration == quote_date`) and records schema v2
  0DTE/non-0DTE file counters. The stricter audit keeps the same completed
  month cutoff (`202604`), with `202605` and `202606` still partial; latest
  E2E with the schema guard passes at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/e2e_validation_true_0dte_schema_guard_20260630`.
- `validate_event_option_production_package.py --require-live-ready` now reads
  `research_papers/JEPA/results/_diagnostics/thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json`
  and rejects any completed-month validation month that is not completed in raw
  all-ticker 0DTE coverage. Current strict validation fails by design on
  `202605`, and `production_manifest.json` no longer advertises the event-option
  package as deployable.
- This keeps the higher Jan-May WR/PF evidence as a diagnostic until
  raw-complete months, completed `202607+` forward evidence, and
  broker/paper/live fill validation are available.

## 2026-06-30 Longsrc Pre-2026 Selection Manifest

- Added `neural/jepa/freeze_pre2026_scan_selection_manifest.py` to convert the
  reproducible pre-2026 scan into a machine-readable selection manifest for the
  top lineage-clean longsrc branch. The manifest is written at
  `research_papers/JEPA/results/event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1/research_selection_manifest.json`.
- Strict research-selection now passes for raw-complete `202601..202604` on that
  branch: `audit_event_option_research_selection.py --strict` reports no issues
  or warnings. The manifest freezes before `202601`, uses scan evidence months
  `202501..202512`, and the scan rank fields are pre-2026 only.
- Formal holdout verification still passes: SPXW WR `51.22%`/PF `1.737`/min
  `19`; SPY WR `53.57%`/PF `1.467`/min `38`; QQQ WR `51.35%`/PF `1.435`/min
  `34`; fold integrity `24` rows clean.
- Added `neural/jepa/audit_longsrc_pre2026_candidate_requirements.py` and wrote
  the status report at
  `research_papers/JEPA/results/event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1/requirement_audit_pre2026_longsrc`.
  It marks `walkforward_metric_and_integrity_passed=true` and
  `anti_leakage_reconstruction_passed=true`, but
  `overfit_risk_review_passed=false` and `production_ready_passed=false`.
- The suspicious higher-WR/PF dense candidates are explicitly demoted in the new
  audit because their 2026 folds include validation months after `202512`.
  Raw-complete `202601..202604` curve-health also fails for this longsrc branch:
  QQQ has `negative_months`, `max_month_pnl_share>0.65`, and
  `negative_day_streak>4`; SPY has `negative_months` and
  `negative_day_streak>4`.
- Ran four 32-worker daily-guard scans over the lineage-clean longsrc branches
  using a strict `202501..202506` select / `202507..202512` validation pretest
  before checking raw-complete `202601..202604`. Summary:
  `research_papers/JEPA/results/_diagnostics/longsrc_pre2026_guard_scan_2025split_summary.md`.
  Each scan had `2646` grid rows; `1760..1833` rows passed only the 2026 forward
  window, but `0` rows passed the 2025 pretest and `0` passed both pretest and
  forward. Any such 2026-only guard choice is therefore rejected as data
  snooping.
- Caveat remains: this is a retrospective reconstruction from the current
  existing-results universe. It proves the chosen branch is selected by a
  pre-2026-only scan and has clean fold lineage, but it does not prove the whole
  result-directory universe was timestamp-frozen before 2026.

## 2026-06-29 Dense Candidate Anti-Snooping Reclassification

- Added `audit_dense_candidate_anti_snooping.py` and wired it into the dense
  requirement audit and E2E validation. Current result: fold chronology,
  frozen pre-2026 lineage, raw-complete `202601..202604` holdout, and model
  feature leakage checks passed, but strict research-selection failed for the broad `202301..202605` table. The later frozen+guard `202601..202604` audit is handled in the 2026-06-30 section above.
- Reclassified the dense `202301..202605` table: `metric_walkforward_objective_passed=true`
  because WR/PF/volume gates pass, but `requested_walkforward_objective_passed=false`
  because the broad `202301..202605` table still lacks a pre-202301 research-selection proof. Treat the
  high WR/PF table as diagnostic, not production proof.
- New guard-specific audit:
  `neural/jepa/audit_dense_candidate_pre2026_guard_selection.py`. It checks the
  daily guard was selected by a rank function using only pre-2026 scan fields,
  asserts the guarded artifact config matches the rank-1 row, and verifies the
  raw-complete `202601..202604` guarded holdout. The E2E assertion
  `anti_snooping_pre2026_guard_selection=true` now covers this.
- Added an existing-results pre-2026 selection triage scan at
  `research_papers/JEPA/results/_diagnostics/scan_existing_results_pre2026_select_2025_eval_202601_202604`.
  It is now reproducible via
  `neural/jepa/scan_existing_event_option_pre2026_selection.py --workers 32`.
  The regenerated scan evaluated `754` dirs, selected only from
  `202501..202512` metrics, then evaluated raw-complete `202601..202604`;
  `11` dirs were eligible by 2025 and `4` also passed 2026 with lineage. The
  best lineage-clean branch is a simpler `longsrc_2024h2select` variant, but it
  still lacks a strict frozen research manifest, so it is a research lead rather
  than a production proof.
- Strongest current anti-lookahead evidence is the raw-complete frozen pre-2026
  holdout over `202601..202604`: SPXW WR `61.18%`/PF `2.626`/min `20`; SPY WR
  `58.33%`/PF `2.333`/min `20`; QQQ WR `53.57%`/PF `1.923`/min `20`. This
  was the strongest evidence before the 2026-06-30 static-manifest audit; use the frozen+guard section above for the current strict `202601..202604` status.

## 2026-06-29 Event-Option Production Package Guardrail

- Superseded by the 2026-06-30 raw coverage guardrail above. The previous
  event-option sidecar refresh matched policy
  `event_option_live_ready_current_sources_202607` and the Jan-May result
  `research_papers/JEPA/results/event_option_live_ready_current_sources_2026janmay_risk5000`
  (`497` trades, WR `48.69%`, PF `1.513`, PnL `+31.03R`), but it is now
  diagnostic because raw all-ticker 0DTE coverage marks `202605` as
  partial/non-official.
- The strict validator still rejects stale sidecars, mismatched result dirs,
  registry deploy-month drift, and policy chronology violations; it now also
  blocks validation months not completed in raw all-ticker 0DTE coverage before
  any event-option package can be advertised in `production_manifest.json`.
- The requirement audit now has an explicit `frozen_2025_to_2026_lineage`
  objective check for the user's requested 2026 walk-forward. It inspects
  `dense_candidate_frozen_through_202512_eval_202601_202605_v1/combined_folds.csv`
  and passes only if the expected `202601..202605` folds exist and all
  train/select/evidence months are `<=202512` and strictly before the tested
  month. The E2E suite now asserts this flag and passes.
- Raw local ThetaData coverage is now audited separately at
  `research_papers/JEPA/results/_diagnostics/thetadata_0dte_raw_coverage_spxw_spy_qqq`.
  It reaches latest common date `20260626` across SPXW/SPY/QQQ option parts and
  underlying files, but it is not official forward evidence. At the raw all-ticker
  0DTE level, completed months currently stop at `202604`; `202605` and `202606`
  are partial/non-official because SPY/QQQ are missing `20260529` 0DTE
  `greeks`/`iv`/`ohlc` files. Treat May/June dense checks as available-data
  diagnostics until those ETF files or later completed months exist.
- `evaluate_dense_candidate_forward_freeze.py` now uses that raw coverage audit
  when deciding completed months. Event-dataset availability alone is no longer
  enough: a month must be completed in both the event dataset and raw all-ticker
  0DTE coverage. The dense E2E regenerates the `202607` forward-freeze artifact
  with this rule and records `202605`/`202606` as partial only. It also generates
  raw-complete `202601..202604` suffixed verifications, which pass the target
  gates without relying on May rows: frozen-through-2025 SPXW WR `61.18%`/PF
  `2.626`/min `20`; SPY WR `58.33%`/PF `2.333`/min `20`; QQQ WR `53.57%`/PF
  `1.923`/min `20`.

## 2026-06-29 Dense 0DTE Uniform Strict Candidate

- New best causal research artifact:
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1`.
  It uses one uniform policy for SPXW/SPY/QQQ: strict d25 win-probability
  gate with per-fold threshold selection on prior validation months, then
  deterministic d50 `forcedmax3` monthly volume backfill to maintain at least
  18 trades/month.
- Formal verifier passes `202301..202605` gates (`WR >=45%`, `PF >=1.30`,
  `min_month_trades >=18`, call-rate 20%-80%, weak fold modes disallowed):
  SPXW WR `49.42%`/PF `1.632`/min `18`; SPY WR `46.94%`/PF `1.471`/min
  `18`; QQQ WR `47.17%`/PF `1.478`/min `18`. Overall: `2,985` trades, WR
  `47.87%`, PF `1.527`, PnL return `245.14R`.
- Integrity evidence: `246` folds checked with no prior-month violations,
  backfill audit checked `334` fallback rows with no issues, and the
  non-strict research-selection audit passes once backfill config rows are
  included as selector evidence.
- Caveat: strict retroactive freeze is impossible without backdating. A
  forward-only manifest exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_freeze_202607_v1`
  for months `>=202607`. Curve-health remains flagged for negative-month
  streak/early-prefix share despite low concentration and low DD/PnL, so this
  is not yet promoted into the live production bot path.
- Deploy artifacts for this candidate are now exported separately at
  `neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate`.
  That package includes six scoreable deploy models for `202607`, three
  monthly-backfill policy components, and candidate policy/registry JSON.
  `event_option_live_scorer.py` can now materialize those policies into
  primary/fallback live candidates, and the bot has a generic MTD-pace gate
  for fallback rows. It is still explicitly marked
  `forward_frozen_research_candidate_not_live_ready`; the current
  `neural/models/jepa/jepa_production_event_options` live-ready package was
  not overwritten.
- Stream-level runtime evidence now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/runtime_policy_replay`.
  `replay_dense_monthly_backfill_runtime_policy.py` replays the historical OOS
  primary/fallback streams through the bot's monthly pace, max-day, cooldown,
  and dedupe gates and exactly matches the official backfilled rows for all
  tickers and combined (`2,985/2,985`, zero numeric diffs). The separate batch
  snapshot-to-order smoke covers concrete contract selection on 15 historical
  live-schema cases; remaining live blockers are forward `202607+`,
  curve-health policy, and broker/order validation.
- Snapshot-to-order smoke evidence now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/snapshot_to_order_smoke`.
  `smoke_dense_live_snapshot_to_order.py` builds a live-schema day directory
  from historical ThetaData for `20260515 14:30`, runs the live snapshot
  builder, scores strict candidate features, and confirms the bot can select
  concrete SPX/SPY/QQQ 0DTE contracts with positive premiums. This is a
  point-in-time smoke, not a longitudinal proof.
- Batch snapshot-to-order evidence now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/snapshot_to_order_batch_smoke`.
  `batch_smoke_dense_live_snapshot_to_order.py` runs the same live-schema
  reconstruction/scoring/contract-selection path for five May-2026 dates and
  three cutoffs; all `15/15` cases pass with strict features and SPX/SPY/QQQ
  selected in every case. This proves broader runtime schema compatibility,
  not forward trading quality or broker fill behavior.
- Formal requirement audit now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/requirement_audit`.
  `audit_dense_candidate_requirements.py` now reports
  `metric_walkforward_objective_passed=true`, `requested_walkforward_objective_passed=false`,
  and `live_ready_passed=false`. The metric gates pass, but the requested
  no-leakage/no-snooping objective is not complete because strict research
  selection fails. The audit reads the forward-freeze evaluation artifact
  directly; current forward status is `pending_no_completed_forward_months`
  because the event dataset ends at `20260616` and raw coverage reaches
  `20260626`.
- Forward-freeze evaluation is now automated by
  `neural/jepa/evaluate_dense_candidate_forward_freeze.py`. The official
  `202607+` run includes the start month automatically once complete and
  currently writes
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_evaluation_202607_pending_v1`
  with status `pending_no_completed_forward_months`. The event dataset currently
  ends at `20260616` and raw all-ticker ThetaData coverage reaches `20260626`,
  so there are no completed `202607+` rows; partial-month inclusion is available
  only through an explicit diagnostic flag and is never official forward evidence.
- A dedicated completed-2026 walk-forward slice now exists at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_walkforward_2026_completed_jan_may_v1`.
  It verifies `202601..202605` from the existing OOS dense candidate result,
  independent of the `202607` forward-freeze package. The slice passes the
  requested gates with clean integrity: SPXW WR `54.55%`/PF `2.000`/min `19`;
  SPY WR `51.00%`/PF `1.735`/min `19`; QQQ WR `53.70%`/PF `1.933`/min `19`.
  `CAUSAL_WALKFORWARD_2026.md` documents the fold lineage and shows each test
  month uses only prior validation/selection months.
- A stricter frozen-pre-2026 holdout now exists at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_frozen_through_202512_eval_202601_202605_v1`.
  It uses only data through `202512`, with model fit on `202201..202506` and
  threshold/config selection on `202507..202512`, then applies the frozen
  components month by month to `202601..202605`. The formal verifier passes:
  SPXW WR `58.49%`/PF `2.348`/min `20`; SPY WR `58.25%`/PF `2.326`/min `19`;
  QQQ WR `51.46%`/PF `1.767`/min `19`. Integrity checks `30` folds and `25`
  backfill rows with no temporal issues.
- A fixed causal daily-guard overlay for that frozen-pre-2026 holdout is now
  documented at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0/CAUSAL_GUARD_SELECTION_2026.md`.
  The rule pauses a ticker for one business day after four completed losing
  active days, using only prior completed-day PnL. Pre-2026 scans support the
  rule without using 2026 outcomes. Applied to the frozen `202601..202605`
  holdout, it passes formal gates and strict holdout curve-health: SPXW WR
  `59.05%`/PF `2.403`/min `20`; SPY WR `57.84%`/PF `2.287`/min `19`; QQQ WR
  `50.98%`/PF `1.733`/min `18`; all tickers have `0` negative months and max
  negative-day streak `<=4`. This is forward-holdout risk evidence, not a
  live-ready promotion, because the full historical curve-health and broker
  validation gaps remain. The same fixed rule is now present in the
  candidate policy as optional bot runtime config, and
  `validate_bot_event_daily_loss_guard.py` passes by proving first-day
  blocking, state persistence, same-day repeat blocking, next-day resume,
  and ticker isolation.
- A stricter fixed-cutoff holdout now exists at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_fixed_holdout_select_through_202604_eval_202605_completed_v1`.
  `evaluate_dense_candidate_fixed_holdout.py` fits the dense15 d25 primary and
  d50 fallback components with training rows ending before the six-month
  selection window, selects only through `202604`, and evaluates the available
  `202605` rows. It passes: SPXW WR `60.00%`/PF `2.500`/min `20`; SPY WR
  `68.42%`/PF `3.611`/min `19`; QQQ WR `63.16%`/PF `2.857`/min `19`.
  The related `202605..202606` run with partial June also passes aggregate
  gates, but the June part is diagnostic only because the month is incomplete
  and June-only remains weak for SPXW and QQQ.
- `audit_dense_candidate_requirements.py` now includes both checks in the
  machine-readable requirement audit. The regenerated
  `requirement_audit.json` has `completed_2026_walkforward=true`,
  `fixed_holdout_may2026=true`, raw coverage evidence, and separates metric
  gates from the full request: `metric_walkforward_objective_passed=true`,
  `requested_walkforward_objective_passed=false`, `live_ready_passed=false`.
  The full request remains incomplete because strict anti-snooping/research
  selection fails.
- Shadow deployment validation now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/shadow_deployment_validation`.
  It confirms the candidate package is usable for controlled shadow testing
  while production guards and systemd configuration prevent accidental
  live-ready deployment.
- Reproducible validation runner:
  `neural/jepa/validate_dense_candidate_e2e.py`. The current passed output is
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/e2e_validation`.
  This is the fastest single command to re-check the candidate's formal gates,
  2026 completed walk-forward, frozen-pre-2026 holdout, guarded frozen-pre-2026
  holdout curve-health, fixed May holdout, bot daily-loss guard runtime,
  paper order payloads, broker-order contract preflight, requirement audit,
  shadow deployment guard, and partial-June non-official status.
- A fixed causal daily-streak guard diagnostic was tested at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_daily_streak_guard_l4p1_vp18`.
  It still passes the formal WR/PF/18-trades gates, but strict curve-health
  remains false for the same structural reasons: negative months, max negative
  daily streak above `4`, and weak early prefix share. Treat it as a rejected
  curve-health mitigation, not a production upgrade.
- A wider daily-streak/rolling-loss scan was also run at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_daily_streak_guard_scan_targeted_202301_202605`.
  It tested `1,260` causal configurations with selection `202301..202412` and
  validation `202501..202605`; none passed both windows. The best full-period
  diagnostic still passes formal gates but fails strict curve-health, so this
  family is not a production promotion path.
- A causal MTD PnL rescue backfill overlay was tested at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_monthly_pnl_rescue_scan_202301_202605`.
  It scanned `135` common-parameter configurations; none passed both
  selection `202301..202412` and validation `202501..202605`. The best
  full-period diagnostic passes WR/PF/18-trades gates but still fails strict
  curve-health, and its pure PnL-rescue fallback trades are negative overall.
  Treat it as rejected, not a production upgrade.
- A causal first-event daily regime gate was tested at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_daily_regime_gate_s3_202301_202605_v1`.
  It uses only prior-month day outcomes and a 3-month threshold-selection
  window. The stream remains profitable and WR/PF pass, but it fails the
  explicit monthly-volume requirement: SPXW min month `15`, SPY `14`, QQQ
  `13`. Fold/backfill integrity is clean, while strict curve-health still
  fails on negative months, negative-day streaks, and weak early prefix share.
  Treat this gate as rejected.
- Offline fill-path simulation now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/offline_fill_simulation`.
  `validate_dense_candidate_offline_fills.py` validates the `45` concrete
  May-2026 contracts selected by the batch smoke against 1-minute ThetaData
  greeks/OHLC and replays the `+50%/-30%/180m` event-option exit contract.
  Market-data path coverage passes (`45/45`) and strict execution-cost
  coverage passes after the runtime modeled entry premium is floored to the
  observed ask when available (`45/45` entries cover the ask). This is still
  not a substitute for broker/order fill validation.
- Paper order payload validation now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/paper_order_validation`.
  `validate_dense_candidate_paper_orders.py` converts the offline-fill
  selections into BUY_TO_OPEN limit payloads, rounds limits to cents, sizes
  integer contracts under the `$5,000` max debit, and checks ask coverage plus
  exit-path availability. It passes `45/45` payloads. This is not broker API
  acceptance, paper-account submission, or real exchange fill evidence.
- The bot now has an explicit opt-in `--paper-order-intents` mode. It writes
  BTO/STC JSONL order intents to `trades_jepa/paper_order_intents_jepa.jsonl`
  while keeping `broker_submission=false`. `validate_bot_paper_order_intents.py`
  validates the local intent schema, cent rounding, max-debit check, and
  paper-only status. This moves the wrapper from alert/tracker toward
  paper-automation, but still does not prove broker API acceptance or real
  fills.
- Broker-order contract preflight now exists at
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/broker_order_contract_validation`.
  `validate_dense_candidate_broker_order_contract.py` validates both surfaces
  above as canonical broker-shaped option orders: `45` BUY_TO_OPEN payloads
  from offline fills plus `2` bot intents, `47/47` passing. It checks OCC
  keys, 0DTE contract fields, limit/quantity/risk math, and confirms no
  broker submission occurred. This removes order-shape ambiguity, but still
  does not prove broker API acceptance, account buying-power checks, fills,
  partial fills, or acknowledgement latency.
- Local ThetaData has additional June files beyond the canonical dense
  artifact, but no completed July 2026 evidence. An isolated dense15 zero-DTE
  physics diagnostic was built for `20260617..20260626`, then combined with
  canonical June rows in
  `research_papers/JEPA/results/_diagnostics/dense_candidate_partial_20260601_20260626_eval_v1`
  using `evaluate_dense_candidate_partial_dataset.py`. That partial-month
  diagnostic is negative and non-official: `57` selected trades, WR `28.07%`,
  PF `0.650`, PnL `-4.3R`; it is not a production-promotion signal.

## 2026-06-28 Dense 0DTE ThetaData Gate Result

- Built a new dense zero-DTE ThetaData branch:
  `research_papers/JEPA/results/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1`
  and physics-enhanced
  `research_papers/JEPA/results/event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1_physics`.
  This is not the old near-level event universe. It covers SPXW/SPY/QQQ,
  15-minute candidates from 10:00 to 14:30 ET, `59,774` rows, and `358`
  physics-enhanced columns with no new leaky columns reported.
- Hardened `neural/jepa/build_event_option_dataset.py` so bad underlying rows
  with `prior_close <= 0` no longer crash return-feature generation.
- Best dense diagnostic over `202501..202605`:
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_mixed_d50d25_causal_2025_2026_v1`.
  It passes numeric gates and fold integrity: overall `1,785` trades, WR
  `46.39%`, PF `1.437`, min month `73`, PnL return `125.37R`, and `85/85`
  folds clean. Per ticker: SPXW WR `47.33%`/PF `1.486`/min `18`; SPY WR
  `45.38%`/PF `1.378`/min `18`; QQQ WR `46.57%`/PF `1.454`/min `24`.
- The earlier mixed selected logic fails the broader `202301..202605` stress test:
  SPXW WR `43.34%`/PF `1.265`/min `18`; SPY WR `41.42%`/PF `1.165`/min
  `18`; QQQ WR `43.56%`/PF `1.287`/min `0`. The year split isolates 2023 as
  the weak regime. That branch is superseded by the uniform strict d25 win
  candidate above.

## 2026-06-28 Direct Event Gate And 7-Source Backfill Rejection

- Ran direct all19 LightGBM event-gate experiments on
  `research_papers/JEPA/results/event_option_dataset_full19_2022_2026_v1_physics_combined/event_option_dataset.parquet`
  using controlled parallelism near the 32-thread workstation limit. The most
  useful direct branch is
  `research_papers/JEPA/results/event_option_gate_direct_return_forcedvol_d80_physctx_call02_2025_2026_*_v1`,
  but it still misses gates: SPXW WR `44.83%`, PF `1.123`, min month `19`;
  SPY WR `46.92%`, PF `1.240`, min month `19`; QQQ WR `42.75%`, PF `1.128`,
  min month `17`.
- Rejected related direct variants: d65 return loses edge, validation-threshold
  selection creates abstain/volume failures, win-label classification only
  improves QQQ WR without enough PF, and core3-only training is weaker than
  all19 training.
- Added the direct SPY/SPXW/QQQ `d80_phys` gate as a seventh source to the
  rolling causal backfill selector. Thin 7-source outputs over
  `202501..202605` remain below target: SPXW WR `43.28%`/PF `1.060`/min
  `18`; SPY WR `47.55%`/PF `1.289`/min `17`; QQQ WR `42.33%`/PF `0.981`/min
  `0`.
- A focused 32-worker SPY volume-repair grid,
  `research_papers/JEPA/results/event_trade_union_backfill_selector_7src_physctx_s6_spy_repair_32w_v1`,
  degraded to WR `46.83%`, PF `1.208`, and min month `10`. This confirms the
  direct stream is a useful diagnostic but not a robust causal production
  component under the requested gates.
- Added `neural/jepa/append_xinput_oof_to_event_option_dataset.py` to append
  causal OOF XInputJEPA state features to the event-option dataset by
  `ticker/date/time`, mapping `SPXW` to `SPX` state rows. Generated
  `research_papers/JEPA/results/xinput_oof_ctx6_e3_202401_202606_eventdiag_v1`
  on CUDA and appended it into
  `research_papers/JEPA/results/event_option_dataset_full19_2022_2026_v1_physics_xinput_oof_202401_202606_v1`.
- Direct d80 gates with `phys/ctx/xjepa` are rejected: SPXW WR `44.43%`, PF
  `1.095`, min `19`; SPY WR `46.57%`, PF `1.212`, min `19`; QQQ WR `43.86%`,
  PF `1.167`, min `17`.
- QQQ `xjepa` validation-threshold selection shows capacity but not volume:
  WR `47.22%`, PF `1.435`, min `0`. Adding that stream to the rolling
  backfill selector as `d80_xjepa_val` remains rejected with WR `41.67%`, PF
  `0.982`, and min `0`.

## 2026-06-28 Static-Union Config Scan 32-Worker Formalization

- `scan_event_static_union_configs.py` now supports 32-worker process pools via
  `--workers`/`--chunksize`, scans `time_asc` and `score_desc` through
  `--daily-order-grid`, can require a minimum source count with
  `--min-sources`, and writes `selected_config_folds.csv` so combined results
  carry auditable `select_months` and source paths.
- Regenerated Oct-Dec 2025 selection scans for Jan-May 2026:
  `research_papers/JEPA/results/event_static_union_config_scan_octdec_scoredesc_spxw_2026janmay_32w_v1`,
  `research_papers/JEPA/results/event_static_union_config_scan_octdec_ordergrid_spy_2026janmay_32w_v1`,
  and
  `research_papers/JEPA/results/event_static_union_config_scan_octdec_ordergrid_qqq_3src_2026janmay_32w_v1`.
- Preferred combined diagnostic:
  `research_papers/JEPA/results/event_static_union_config_scan_octdec_scoredesc_spxw_combined_2026janmay_32w_v1`.
  Formal verification passes with weak fold modes disallowed: SPXW WR
  `57.99%`, PF `2.040`, min month `19`; SPY WR `50.63%`, PF `1.622`, min
  month `70`; QQQ WR `47.65%`, PF `1.368`, min month `72`. Overall:
  `1,139` trades, WR `50.22%`, PF `1.540`, PnL `+$354,669`, and `15/15`
  folds clean.
- Curve-health passes for all tickers on that preferred diagnostic: QQQ top5
  share `58.0%`, SPXW `61.8%`, SPY `67.6%`; no flags. The non-strict
  research-selection audit passes, but strict retroactive proof is still not
  available because no `research_selection_manifest.json` was frozen before
  `202601`.
- Forward-only freeze:
  `research_papers/JEPA/results/event_static_union_config_scan_octdec_scoredesc_spxw_202607_forward_freeze_manifest_v1`.
  It is valid only for months `>=202607`; a strict audit against
  `202601..202605` fails as intended because `frozen_before_month=202607`.
- The fully selector-ranked order-grid combined artifact
  `research_papers/JEPA/results/event_static_union_config_scan_octdec_ordergrid_combined_2026janmay_32w_v1`
  also passes numeric gates and fold integrity, but SPXW curve-health fails.
  Use it as evidence that Oct-Dec ranking can clear WR/PF/volume, not as the
  robust branch.

## 2026-06-28 Full20 2024-2026 Worker Stress

- `apply_event_trade_union_config_selector.py` now supports
  `--workers`/`--chunksize` for process-pool scoring of candidate configs
  inside each monthly rolling selection fold. The new `s3` and `s6` full20
  reruns used 8 workers per ticker in parallel batches, keeping total worker
  count near the 32-thread workstation limit.
- Rolling order-grid selector reruns over `202401..202606` remain rejected.
  The 2026 partial period can pass for some windows, but the completed 2025
  year does not clear PF `1.30`: SPXW best 2025 PF is `0.969`, SPY best is
  `1.204`, and QQQ best is `1.194`. Every full-range rolling run still has
  `min_month_trades=0`, so none satisfies the requested 2022-2026 style gates.
- Broader static scan:
  `research_papers/JEPA/results/event_static_union_config_scan_full20_2024select_2025_2026test_6src_ordergrid_32w_v1`.
  It scans all six full20 streams (`d80`, `d65win`, `d65ret`, `d80_front`,
  `d50ret`, `d80_zero`) with `max_sources=3`, order grid, score filter grid,
  and 32 workers. Result: `4,992` configs per ticker, `0` 2024 select-pass
  configs, and `0` 2025-pass configs for SPXW/SPY/QQQ.
- Best 2025 static candidates among rows with WR `>=45%` and min month `>=18`
  still miss PF: SPXW PF `1.157`, SPY PF `1.253`, QQQ PF `1.245`. This
  indicates the current full20 static/rolling union family does not contain a
  deployable 2025 solution under the user's gates; more CPU alone is not the
  blocker.

## 2026-06-28 H2-Only Audit And Rolling Backfill Selector

- Rebuilt the SPXW/SPY H2-only all10 static-union scan at
  `research_papers/JEPA/results/_diagnostics/spxw_spy_h2only_causal_rank_scan_all10_32w_v1`.
  The known qbackfill combined branch still passes the explicit
  `202501..202605` gates, but its SPXW row ranks `360` and its SPY row ranks
  `614` when sorted using selection-window-only evidence. This is not strict
  causal promotion evidence for 2025.
- Added `apply_event_trade_union_backfill_selector.py` for rolling monthly
  selection of a primary union plus deterministic volume fallback. The common
  verifier/curve-health/filter tools now load
  `trade_union_backfill_selector_trades.csv` and
  `trade_union_backfill_selector_folds.csv`.
- Initial 6-source `s6` rolling-backfill runs are rejected. Thin artifacts:
  SPXW WR `42.64%`, PF `1.109`, min `18`; SPY WR `47.99%`, PF `1.329`, min
  `17`; QQQ WR `43.33%`, PF `1.025`, min `0`. The SPY thin run has clean
  integrity/backfill audit but fails strict volume, and the broader 32-worker
  SPY volume-repair grid worsens to PF `1.241` and min `10`.

## 2026-06-28 SPXW/SPY H1/H2 Backfill Stress

- `scan_event_static_union_backfill.py` now supports
  `--prefilter-source-cache-dir`, reuses each loaded source inside a worker for
  both primary and fallback streams, and applies `--chunksize` through
  `ProcessPoolExecutor.map`. This is required for practical 32-worker scans on
  Windows because each spawned worker otherwise reloads the full source CSVs.
- SPY top-24 six-source H1/H2 monthly-backfill scans remain rejected:
  `_diagnostics/spy_static_union_h1h2_backfill_top24_6src_targets18_20_32w_v1.csv`
  evaluated `2,592` rows with `0` pretest-pass, `144` forward-pass, and `0`
  all-pass rows. The expanded target/max-day scan
  `_diagnostics/spy_static_union_h1h2_backfill_top24_6src_targets21_22_md1_4_cd0_15_30_32w_v1.csv`
  evaluated `3,456` rows with `0` pretest-pass, `160` forward-pass, and `0`
  all-pass rows.
- SPXW top-24 six-source scans are also rejected:
  `_diagnostics/spxw_static_union_h1h2_backfill_top24_6src_targets18_20_32w_v1.csv`
  evaluated `2,592` rows with `0` pretest-pass, `19` forward-pass, and `0`
  all-pass rows. The expanded scan
  `_diagnostics/spxw_static_union_h1h2_backfill_top24_6src_targets21_22_md1_4_cd0_15_30_32w_v1.csv`
  evaluated `3,456` rows with `0` pretest-pass, `21` forward-pass, and `0`
  all-pass rows.
- Interpretation: using more workers confirms the bottleneck is not runtime.
  The simple static-union/backfill family has forward-capacity rows, but the
  rows are not selectable from causal 2024 H1/H2 evidence. SPY's near-misses
  usually fail call-rate or forward monthly volume; SPXW's H1 selection slice
  still has month-volume failures, including `sel_min_month_trades=0`.
- Revalidated the deployed event-option package:
  `python neural/jepa/validate_event_option_production_package.py --require-live-ready`
  passes for `event_option_live_ready_current_sources_202607`, with
  live-ready registry status, curve-health pass, and no missing
  live-equivalence or invalidated components.
- Improved `freeze_event_option_research_manifest.py` so forward-freeze
  manifests record actual prior evidence months from columns such as
  `select_months`, instead of always recording evaluated `test_month`s.
- Created forward-only freeze
  `research_papers/JEPA/results/event_static_union_pretest_octdec_scorecap5_202607_forward_freeze_manifest_v1`
  for the stronger Oct-Dec scorecap5 static-union diagnostic
  `event_static_union_pretest_octdec_selected_scorecap5_2026janmay_risk5000_v2`.
  That diagnostic passes Jan-May 2026 WR/PF/month-volume gates, fold integrity,
  and curve-health, but its new freeze is valid only from `202607` onward. A
  strict audit against `202601..202605` fails as intended because the manifest
  was frozen after that window.
- `audit_event_option_research_selection.py` now handles relative manifest
  paths from the current working directory before falling back to result-dir
  relative lookup, which makes explicit forward-freeze audit commands less
  error-prone.
- Rolling scorecap5-pool trade-union selector v2:
  `research_papers/JEPA/results/event_trade_union_config_selector_scorecap5pool_monthly_s3_spxw_spy_qqq_2026janmay_v2`.
  It selects source variants and max-day/cooldown from the previous three OOS
  months for each evaluated month, and now writes explicit audit columns for
  selected sources and source paths. Jan-May 2026 formal verification passes
  with weak modes disallowed: SPXW WR `47.93%`, PF `1.377`, min month `19`;
  SPY WR `50.81%`, PF `1.562`, min month `54`; QQQ WR `47.33%`, PF `1.303`,
  min month `72`. Overall: `1,065` trades, WR `48.64%`, PF `1.415`,
  `+$272,973`, and `15/15` folds clean.
- Audit status for that rolling selector: non-strict research-selection audit
  passes and identifies causal selector evidence for all tickers. Strict
  retroactive proof is still not available because no manifest was frozen
  before `202601`; the new forward freeze
  `research_papers/JEPA/results/event_trade_union_config_selector_scorecap5pool_monthly_s3_202607_forward_freeze_manifest_v2`
  is valid only for months `>=202607`.
- Robustness status: the same rolling selector fails curve-health. SPY is
  healthy, but QQQ is flagged for `top5_share=85.4%` and one negative month,
  while SPXW is flagged for `top5_share=123.6%`, DD/PnL `65.3%`, and one
  negative month. This keeps it as causal numeric evidence rather than a
  production promotion.
- Daily streak guard overlay is rejected for this branch. Diagnostic
  `_diagnostics/scorecap5_monthly_s3_v2_daily_streak_guard_scan_s2v2f1_small_16w.csv`
  used Jan-Feb 2026 selection, Mar-Apr validation, and May forward. It scanned
  `420` rows: `6` passed selection+validation, `0` passed May forward, and `0`
  passed both. The guard cannot be used to rescue SPXW/QQQ curve issues without
  forward damage.
- `apply_event_trade_union_config_selector.py` now supports
  `--daily-order-grid` so each monthly fold can select either the previous
  `time_asc` cap or the `score_desc` cap used by static-union diagnostics.
  The order is selected only from prior OOS months.
- Order-grid selector diagnostic:
  `research_papers/JEPA/results/event_trade_union_config_selector_scorecap5pool_monthly_s3_ordergrid_spxw_spy_qqq_2026janmay_v1`.
  It passes the formal Jan-May verifier: SPXW WR `56.21%`, PF `1.950`, min
  month `19`; SPY WR `49.73%`, PF `1.505`, min month `54`; QQQ WR `47.02%`,
  PF `1.309`, min month `52`; overall PF `1.462`, `+$294,020`. SPXW becomes
  curve-healthy, but QQQ top5 `89.8%` and SPY top5 `85.7%` keep this combined
  artifact below promotion quality.
- Strongest current diagnostic:
  `research_papers/JEPA/results/event_option_mixed_ordergrid_spxw_spyrolling_qqqstatic_scorecap5_2026janmay_v1`.
  It combines SPXW order-grid rolling selector, SPY rolling selector v2, and
  QQQ pretest static scorecap5 union. Formal verifier passes: SPXW WR
  `56.21%`, PF `1.950`, min month `19`; SPY WR `50.81%`, PF `1.562`, min
  month `54`; QQQ WR `47.65%`, PF `1.368`, min month `72`. Overall: `1,116`
  trades, WR `50.00%`, PF `1.508`, `+$332,625`, `25` folds clean.
- Curve-health passes for the mixed diagnostic: QQQ top5 `58.0%`, SPXW top5
  `64.9%`, SPY top5 `78.3%`, with no flags. Non-strict research-selection
  audit passes and identifies selector evidence for all tickers.
- Remaining caveat: strict retroactive proof still fails because no manifest
  existed before `202601`. New forward freeze
  `research_papers/JEPA/results/event_option_mixed_ordergrid_spxw_spyrolling_qqqstatic_scorecap5_202607_forward_freeze_manifest_v1`
  is valid only for months `>=202607`; a strict Jan-May audit fails as intended
  because SPXW/SPY selection evidence includes Jan-Apr 2026.
- Component meta-selection work:
  `apply_event_trade_union_window_meta_selector.py` now accepts general
  `combined_*`/`static_union_*` candidates, records `candidate_daily_order`,
  and has `--score-top5-target` for concentration-aware ranking. The selection
  auditor recognizes `selected_meta_window_candidate` as selector evidence.
- Extended OOS component candidates were generated from `202510..202605` for
  SPXW/SPY/QQQ, with both `time_asc` and `ordergrid` variants. This gives the
  meta-selector Oct-Dec 2025 history to choose Jan 2026 components without
  looking at Jan.
- Causal component meta-selector diagnostic:
  `research_papers/JEPA/results/event_trade_union_component_meta_selector_scorecap5pool_s3_2026janmay_v1`.
  It selects per ticker/month from the prior three OOS months. Formal verifier
  passes: SPXW WR `54.44%`, PF `1.789`, min month `19`; SPY WR `49.73%`, PF
  `1.505`, min month `54`; QQQ WR `47.33%`, PF `1.303`, min month `72`;
  overall PF `1.442`; `15/15` folds clean. Non-strict research-selection audit
  passes with selector evidence.
- Rejection reason for that causal meta-selector: curve-health fails. QQQ has
  top5 `85.4%` and one negative month; SPY has top5 `85.7%`. A strong
  top5-penalty variant fails QQQ PF (`1.259`), so the penalty does not solve
  the issue.
- Predeclared QQQ static candidate:
  `research_papers/JEPA/results/event_static_union_qqq_d80_win80_ptdj80_scoredesc_m8_2025julsep_select_2025oct_2026may_v1`.
  It is causal from Jul-Sep selection into Oct-May test, but Jan 2026 is
  negative and the meta-selector still prefers `qqq_time`. The robust QQQ
  static path still requires Oct-Dec selection and is therefore a forward
  freeze path, not a pre-Jan meta-selected component.

## 2026-06-26 Frozen Action Routers

- Added `walkforward_event_action_return_router.py`. It trains one
  `HistGradientBoosting` model per ticker/action from fit months, selects
  threshold/max trades per day on a later select window, and freezes the result
  for forward tests.
- Return target artifact:
  `research_papers/JEPA/results/event_action_return_router_full19_2022fit_2024select_2025_2026test_d65d80_v1`.
  SPXW/SPY have no 2024 select-pass config. QQQ passes 2024 select (WR
  `46.6%`, PF `1.389`, min month `24`) but fails forward with PF `0.990` in
  2025 and `0.929` in 2026.
- Win target artifact:
  `research_papers/JEPA/results/event_action_win_router_full19_2022fit_2024select_2025_2026test_d65d80_v1`.
  No SPXW/SPY/QQQ config passes the 2024 select gates. SPXW/SPY top candidates
  have WR near `40%`; QQQ misses monthly volume.
- Existing pairwise-router scans:
  `_diagnostics/pairwise_2025select_2026_config_gate_scan.csv` and
  `_diagnostics/pairwise_config_per_ticker_2025_2026_gate_scan.csv`.
  They confirm there is no config passing both 2025 validation and 2026 test
  per ticker. The closest 2026-only config still fails SPY PF by a few bps and
  has weak 2025 selection evidence.
- Follow-up regime-gate diagnostics on the near-miss
  `lgbm_soft_diff_abs_mt0_me0p0` stream are negative. The stream was chained as
  OOS 2024-2026, and `apply_event_daily_regime_gate.py` now has
  `--fail-closed-on-select-fail` so failed selection windows abstain. Strict
  2025-2026 overlays with 2/3/6-month selection all miss the system gates:
  min monthly trades remain `0`; SPY PF is only `1.129` with 2 months and
  `1.053` with 3 months.
- Daily-source router replay is also negative when validated from 2024 history
  into 2025-2026. Direct 2025-2026 PF is SPXW `1.115`, SPY `1.056`, QQQ
  `1.146`. A strict confidence gate with deterministic `d80` backfill and
  fail-closed selection leaves too few passing folds: best selected counts are
  SPXW `39` trades/PF `0.969`, SPY `30`/PF `2.072`, QQQ `128`/PF `1.604`,
  but every ticker has min monthly trades `0`.
- Added `scan_event_static_union_configs.py` for fixed-priority/cooldown
  unions over OOS source streams. It supports strict gate ranking and a
  continuous near-miss ranking, but both selection modes are causal because
  only the declared select window is used for ranking.
- Static-union scans over `event_option_variant_streams_full20_2022_2026_v1`
  are negative. Single-source 2024 selection has zero pass configs. With 2025
  selection, the best causal near-miss pairs are still below target in 2026:
  SPXW `d80,d80_front` PF `1.127`, SPY `d65win,d80` PF `1.267`, and QQQ
  continuous-selected `d80,d80_front,d50ret` PF `1.050`.
- Capacity-only 2026 oracle rows show why this branch is tempting but not
  valid: QQQ `d65win,d80` reaches WR `54.7%`, PF `1.503`, min month `55`;
  SPXW `d65ret,d80` reaches WR `49.7%`, PF `1.414`, min month `30`; SPY
  `d65win,d80` reaches WR `53.6%`, PF `1.418`, min month `18`. None have
  adequate 2025 selection evidence, so do not promote them.
- Rolling monthly trade-union config selection now has one 2026 numeric-pass
  diagnostic:
  `research_papers/JEPA/results/event_trade_union_config_selector_full20_2026_numeric_pass_diag_v1`.
  It combines SPXW `select_months=12`, SPY `select_months=12`, and QQQ
  `select_months=3` from the small source grids. The canonical verifier passes
  Jan-Jun 2026 with clean folds: SPXW WR `51.99%`, PF `1.366`, min month
  `30`; SPY WR `51.44%`, PF `1.336`, min month `19`; QQQ WR `53.09%`, PF
  `1.435`, min month `49`; integrity `18/18` folds. This is capacity evidence
  only because those window choices were selected after looking at 2026.
  The same combined family fails 2025/full-range PF gates.
- Added `apply_event_trade_union_window_meta_selector.py` to remove the manual
  `select_months` choice. It chooses among rolling selector outputs using only
  earlier OOS months, either monthly or frozen for a deployment period.
- Strongest current candidate:
  `research_papers/JEPA/results/event_trade_union_window_meta_selector_full20_2026_frozen_2025select_s3s6s12_m18relax_v1`.
  It freezes the meta-window choice from 2025, requires prior min-month volume
  when any candidate satisfies it, and relaxes that filter only when all
  candidates fail it. Jan-Jun 2026 passes the canonical verifier: SPXW WR
  `51.99%`, PF `1.366`, min month `30`; SPY WR `51.44%`, PF `1.336`, min
  month `19`; QQQ WR `53.65%`, PF `1.373`, min month `49`; integrity `18/18`
  folds clean.
- This is still not final evidence. The identical frozen meta rule selected
  from 2024 fails 2025 badly:
  `research_papers/JEPA/results/event_trade_union_window_meta_selector_full20_2025_frozen_2024select_s3s6s12_m18relax_v1`
  has SPXW PF `0.837`/min month `0`, SPY PF `0.967`, and QQQ PF `1.183`/min
  month `0`. Treat the 2026 pass as a deploy-month candidate needing
  forward/frozen validation, not as a promoted production system.
- Formal rule scan:
  `research_papers/JEPA/results/event_trade_union_window_meta_rule_scan_full20_2025val_2026test_s3s6s12_v1`.
  It evaluates `432` causal meta-rules using 2025 as validation and 2026 as
  test. Results: `0` validation-pass rules, `41` test-pass rules, `0` passing
  both. The best rule chosen only by 2025 near-miss score still passes 2026
  verification, but the absent 2025 pass is the current blocker for claiming a
  stable no-snooping policy.
- Source-capacity diagnostics are negative for 2025. No individual source in
  `event_option_variant_streams_full20_2022_2026_v1` passes 2025 gates for all
  three tickers; the all-six-source `s12` rolling replay improves SPY 2026 but
  worsens 2025 validation and does not solve SPXW.
- Static feature profiles remain weak. The wide 2024-2026 physics static scan
  found zero SPXW profiles passing 2025 before it was stopped for runtime, and
  a reduced SPY/QQQ d80 smoke found zero 2025 select-pass profiles.
- Direct learned-gate and stream-filter follow-ups remain negative. The
  completed `event_option_gate_full20_physics_pooled_2025full_d80_win_fullgrid_call05_minmonth18_v1`
  diagnostic reaches only overall PF `1.024`; SPXW fails with WR `44.94%`,
  PF `0.873`, PnL `<0`, and min month `0`. The causal stream-filter scans
  `event_stream_trade_filter_scan_full20_2024select_2025_2026test_tiny_v1`
  and
  `event_stream_trade_filter_scan_full20_2024select_2025_2026test_action_windows_v1`
  find `0` 2024 select-pass configs and `0` 2025 pass configs. Their few
  2026-only passing cuts are low-volume or one-sided and are not production
  evidence.
- Added `scan_event_daily_cap_overlay.py` for deterministic cap overlays over
  existing event-option streams. The first scan,
  `_diagnostics/pre2026_daily_cap_overlay_scan_frozen_sources.csv`, uses
  `202510..202512` to evaluate caps `1..12` over the frozen SPXW `vol25phys`,
  SPY `topk`, and QQQ `balanced65` sources, then reports Jan-May 2026. Result:
  SPXW has multiple caps passing selection and test; SPY has one selection-pass
  cap (`time_asc`, cap `2`) but it fails test monthly volume; QQQ has zero
  selection-pass caps. Score-based caps can improve Jan-May SPXW concentration,
  but the overlay is not a multi-ticker no-snooping fix.
- Added `scan_event_source_transfer.py`; the
  `_diagnostics/source_transfer_2025h2_octdec_to_2026janmay_literal.csv` audit
  confirms only SPXW `vol25phys` passes both Oct-Dec 2025 selection and Jan-May
  2026 test as a single source. SPY and QQQ need fixed source unions rather
  than source-level promotion.
- Added `materialize_event_static_union.py` and materialized
  `research_papers/JEPA/results/event_static_union_pretest_octdec_selected_scorecap5_2026janmay_risk5000_v2`.
  Fixed rules: SPXW `vol25phys` ordered by score with cap `5`; SPY
  `topk,ptdj35,cons22`; QQQ `d80,win80,ptdj80`. Jan-May verification passes
  WR/PF/month-volume/call-rate gates with clean fold chronology: SPXW WR
  `57.99%`, PF `2.040`, min month `19`; SPY WR `50.63%`, PF `1.622`, min
  month `70`; QQQ WR `47.65%`, PF `1.368`, min month `72`. Overall is
  `1,139` trades, WR `50.22%`, PF `1.540`, and `+70.934R`.
- Curve-health now passes for all three tickers on v2. Strict research
  selection still fails without a manifest frozen before `202601`, so this
  remains a high-quality pretest diagnostic and a forward-freeze candidate,
  not retroactive no-snooping promotion evidence.
- New stronger long-source diagnostic:
  `research_papers/JEPA/results/event_static_union_longsrc_2025select_2026janmay_risk5000_v1`.
  It scans only full20 2022-2026 variant/consensus streams, selects from full
  2025 with the formal gates plus select top5-day share `<=0.35`, then applies
  the selected fixed unions to Jan-May 2026. Formal verifier passes: SPXW WR
  `53.33%`, PF `1.615`, min month `36`; SPY WR `52.67%`, PF `1.517`, min
  month `44`; QQQ WR `52.08%`, PF `1.327`, min month `34`; integrity `41`
  rows clean. Overall: `649` trades, WR `52.70%`, PF `1.490`, `+31.391R`.
- Caveats for the long-source diagnostic: strict research-selection audit still
  needs a manifest/freeze process, and curve-health flags SPXW/QQQ for one
  negative month each. This is the best current no-same-month evidence branch,
  but promotion still needs 2024->2025 replay or a forward freeze.
- New 2024H2-selected long-source replay:
  `research_papers/JEPA/results/event_static_union_longsrc_2024h2select_2025_2026janmay_risk5000_v1`.
  It freezes fixed unions from `202407..202412` and tests them unchanged over
  `202501..202605`. Verifier passes the requested gates for all tickers with
  weak fold modes disallowed: SPXW WR `49.71%`, PF `1.402`, min month `19`;
  SPY WR `48.24%`, PF `1.373`, min month `23`; QQQ WR `50.70%`, PF `1.358`,
  min month `34`. Overall: `1,868` trades, WR `49.36%`, PF `1.374`,
  `+72.812R` / `+$364,060`, integrity `104/104` clean.
- This materially improves the no-same-month evidence because the forward test
  spans full 2025 plus Jan-May 2026. It is still not final promotion evidence:
  no manifest was actually frozen before `202501`, SPXW's 2024H2 selection
  call-rate is `18.75%`, and curve-health still flags negative months and
  negative-day streaks, although concentration is no longer the main issue.
- Added causal daily streak guard script:
  `neural/jepa/apply_event_daily_streak_guard.py`. The first materialized guard
  is
  `research_papers/JEPA/results/event_static_union_longsrc_2024h2select_2025_2026janmay_daily_guard_l5p2_risk5000_v1`,
  with `trigger_losses=5` and `pause_days=2`. It keeps all requested gates over
  `202501..202605`: SPXW WR `50.29%`, PF `1.451`, min month `18`; SPY WR
  `48.33%`, PF `1.373`, min month `23`; QQQ WR `50.72%`, PF `1.367`, min
  month `32`. It is a modest risk overlay; curve-health still fails on
  negative months/streaks.
- Forward-only freeze manifests now exist for the base and guarded variants:
  `research_papers/JEPA/results/event_static_union_longsrc_202607_forward_freeze_manifest_v1`
  and
  `research_papers/JEPA/results/event_static_union_longsrc_daily_guard_l5p2_202607_forward_freeze_manifest_v1`.
  These only validate future months from `202607` onward; they do not turn the
  reconstructed 2025/2026 replay into historical freeze evidence.
- Dynamic monthly source ranking is rejected:
  `research_papers/JEPA/results/event_static_union_dynamic_source_rank_longsrc_2025_2026janmay_diag_v1`
  falls to overall PF `1.185`, with SPY PF `1.160` and QQQ PF `1.122`.
- Objective-only 2024H2 scan audit: SPXW's selected row is defensible as the
  top all-period all-pass row when `min_score=0.0`; SPY has a simpler top
  all-pass two-source row `d65win,d80_zero`; QQQ remains the weakest
  anti-snooping point because `d80,d80_front` is the only all-period all-pass
  row but not a simple top-rank selection.
- Simpler-SPY replay:
  `research_papers/JEPA/results/event_static_union_longsrc_2024h2select_2025_2026janmay_objpass_simpler_spy_risk5000_v1`.
  It passes `202501..202605`: SPXW WR `49.71%`, PF `1.402`, min month `19`;
  SPY WR `49.45%`, PF `1.408`, min month `19`; QQQ WR `50.70%`, PF `1.358`,
  min month `34`; overall `1,715` trades, WR `49.97%`, PF `1.389`,
  `+67.639R`.
- Simpler-SPY plus `l5p2` daily guard:
  `research_papers/JEPA/results/event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1`.
  Formal verifier passes with SPXW WR `50.29%` / PF `1.451` / min `18`, SPY
  `49.93%` / `1.428` / `19`, and QQQ `50.72%` / `1.367` / `32`; overall
  `1,678` trades, WR `50.30%`, PF `1.412`, `+69.652R`. Curve-health still
  fails due negative months and max negative-day streak `5`; strict audit is
  intentionally not backdated with a pre-2025 manifest.
- Forward-only freeze for that latest guarded variant:
  `research_papers/JEPA/results/event_static_union_longsrc_objpass_simpler_spy_daily_guard_l5p2_202607_forward_freeze_manifest_v1`.
  It is only valid from `202607` onward.
- Added static-union window stability scanner:
  `neural/jepa/scan_event_static_union_window_stability.py`. It recomputes a
  fixed source union over explicit select/validation/test windows and reports
  `pretest_*` and `all_*` pass flags without using forward months for ranking.
- QQQ static-only stability audits are negative. The current QQQ
  `d80,d80_front` time-asc cap `2` passes 2024H2 and the later replay, but it
  fails 2024H1 gates (WR `43.95%`, PF `1.036`, min month `20`, call-rate
  `17.49%`) and fails a 2023-selected -> 2024-validation audit on 2024
  PF/call-rate. Broader QQQ static-only grids over cap `1..3` and both
  `time_asc`/`score_desc` have `0` rows passing 2024H1+2024H2 pretests and the
  combined `202501..202605` forward gates; the best near-miss is PF `1.295`
  with min month `17`.
- Added parallel backfill scanner:
  `neural/jepa/scan_event_static_union_backfill.py`. The focused QQQ 24-worker
  scan `_diagnostics/qqq_static_union_pre2025_backfill_scan_focused_v1.csv`
  found a pretest-selected monthly backfill: primary `cons_m2s1c45,d65win,d80`
  score-desc cap `1`, fallback `d80_front`, target `18`, max-day `2`, cooldown
  `0`. This row is rank `1` by pretest score among `704` pretest-pass rows;
  QQQ forward `202501..202605` is WR `49.73%`, PF `1.313`, min month `19`
  with `21` audited fallback rows.
- Wider 32-worker QQQ checks now cover all 10 fallback sources. The deduped
  scan `_diagnostics/qqq_static_union_pre2025_backfill_scan_full10fb_32w_v1.csv`
  evaluated `4,800` tasks, and the no-dedupe scan
  `_diagnostics/qqq_static_union_pre2025_backfill_scan_full10fb_nodedupe_32w_v1.csv`
  evaluated `9,600` tasks. The same QQQ source-set remains the top all-pass
  selection by pretest score; no alternate source order improves the causal
  selection evidence.
- New combined diagnostic:
  `research_papers/JEPA/results/event_static_union_pre2025_qbackfill_spxwspy_objpass_simpler_spy_2025_2026_risk5000_v1`.
  Formal verifier passes `202501..202605`: SPXW WR `49.71%` / PF `1.402` /
  min `19`; SPY `49.45%` / `1.408` / `19`; QQQ `49.73%` / `1.313` / `19`;
  overall `1,438` trades, WR `49.58%`, PF `1.384`, `+57.226R` / `+$286,130`.
  Fold integrity checks `111` rows and backfill audit checks `21` rows clean.
- Remaining caveats: curve-health still fails on negative months and max
  negative-day streaks. Non-strict research-selection audit passes, but strict
  audit fails because there was no manifest frozen before `202501`. Forward-only
  freeze for validation from `202607` onward:
  `research_papers/JEPA/results/event_static_union_pre2025_qbackfill_spxwspy_202607_forward_freeze_manifest_v1`.
- Improved H1/H2-robust QQQ backfill:
  `research_papers/JEPA/results/_diagnostics/qqq_static_union_h1h2_backfill_top64_full10fb_targets18_22_32w_v1.csv`.
  The 32-worker scan evaluated `4,500` deduped tasks; `1,636` passed H1/H2
  pretest and `355` passed both pretest and forward gates. Selected QQQ uses
  primary `d65win,d80,d80_zero` score-desc cap `1` plus `d80_front` monthly
  volume backfill, target `18`, max-day `2`, cooldown `15`. H1 select:
  WR `49.22%`, PF `1.508`, min `20`; H2 validation: WR `55.22%`, PF `1.515`,
  min `21`; forward `202501..202605`: WR `49.86%`, PF `1.361`, min `19`.
- New best formal-pass diagnostic:
  `research_papers/JEPA/results/event_static_union_h1h2_qbackfill_spxwspy_objpass_simpler_spy_2025_2026_risk5000_v1`.
  Formal verifier passes `202501..202605`: SPXW WR `49.71%` / PF `1.402` /
  min `19`; SPY `49.45%` / `1.408` / `19`; QQQ `49.86%` / `1.361` / `19`;
  overall `1,435` trades, WR `49.62%`, PF `1.395`, `+58.939R` / `+$294,697`.
  Fold integrity checks `102` rows and backfill audit checks `23` rows clean.
  Non-strict research-selection audit passes; strict still fails because no
  manifest existed before `202501`. Forward-only freeze:
  `research_papers/JEPA/results/event_static_union_h1h2_qbackfill_spxwspy_202607_forward_freeze_manifest_v1`.
  Curve-health remains the blocker: all tickers still fail on negative months
  and max negative-day streaks.
- H2-2024-selected daily streak guard is rejected:
  `research_papers/JEPA/results/event_static_union_pre2025_qbackfill_spxwspy_guard_t4p2_roll5m2_2025_2026_risk5000_v1`.
  It was selected by `_diagnostics/pre2025_h2_daily_streak_guard_scan_qbackfill_v1.csv`,
  but forward verification fails because SPXW min month drops to `16` and QQQ
  PF drops to `1.290`.
- Added a volume-aware variant of the causal daily streak guard plus
  `neural/jepa/scan_event_daily_streak_guard.py` for parallel guard scans. H2
  32-worker scans evaluated `648` target-18 tasks and `972` target-19/20/21
  tasks; no pretest-pass row clears curve-health flags or max negative-day
  streak `<=4`.
- Volume-protected guards are also rejected. Target 18
  `research_papers/JEPA/results/event_static_union_pre2025_qbackfill_spxwspy_guard_vprotect_roll3le0_p3_t18_2025_2026_risk5000_v1`
  fails forward because QQQ min month is `17`. Target 19
  `research_papers/JEPA/results/event_static_union_pre2025_qbackfill_spxwspy_guard_vprotect_t4p2_roll5m2_t19_2025_2026_risk5000_v1`
  restores min month `19`, but fails because QQQ PF is `1.272`; curve-health
  remains unhealthy for all tickers. The unguarded qbackfill branch remains
  the current formal-pass diagnostic.

## 2026-06-26 Full-History Event Profiles

- Added `scan_event_option_static_profiles.py` for causal frozen profile
  scans over event-option datasets. Profiles derive thresholds from fit
  months, are selected on a later select window, and are then frozen for
  forward test windows.
- Inventoried event datasets into
  `research_papers/JEPA/results/_diagnostics/event_option_dataset_inventory_20260626.csv`.
  The reusable full-history source is
  `research_papers/JEPA/results/event_option_dataset_full19_2022_2026_v1_physics_combined/event_option_dataset.parquet`
  with `695,053` rows across `2022-01-03..2026-06-22`.
- Exact compact static scans are negative:
  `event_option_static_profiles_full19_2022fit_2024select_2025_2026test_d80_small_v1`
  and
  `event_option_static_profiles_full19_2022fit_2024select_2025_2026test_d65_small_v1`
  found zero SPXW/SPY/QQQ profiles passing 2024 select gates at WR `>=45%`,
  PF `>=1.3`, and min `18` trades/month.
- Relaxed d80 near-miss diagnostic
  `event_option_static_profiles_full19_2022fit_2024select_2025_2026test_d80_small_relaxed_diag_v1`
  confirms instability. The best 2024-selected profiles degrade in 2025/2026:
  SPXW PF `0.938`/`0.876`, SPY PF `1.151`/`0.906`, QQQ PF `0.953`/`0.914`.
- Interrupted LightGBM diagnostics
  `event_option_gate_full19_d80_win_pooled_alltickers_val12_2025test_v1` and
  `event_option_gate_full19_d80_win_core_state_val12_2025test_v1` are partial
  only and should not be cited as completed walk-forward evidence.
- `event_option_gate_full19_d80_win_core_state_val12_2025test_v1` was resumed
  with `--resume`, but remained negative before timeout: SPXW has all `12`
  2025 folds and fails the requested gates (PF `1.219`, WR `43.2%`, min month
  `0`), while SPY has only `7` folds and already shows repeated validation
  abstentions plus a losing deployed April. Leave this branch as incomplete and
  non-promotable.

## 2026-06-26 Structural Profile Stability

- Rejected strict nested structural selector
  `research_papers/JEPA/results/level_stability_nested_structural_profiles_risk5000_strict_wr45_pf13_m18_2026janmay_v1`.
  Fold integrity passes (`15` folds / `303` selected rows), but gate metrics
  fail badly: SPX WR `33.0%`, PF `0.796`, PnL `-74.8k`, min month `0`; SPY
  WR `27.7%`, PF `0.665`, PnL `-66.8k`, min month `0`; QQQ abstains.
- Added causal H2-2025 -> Jan-May-2026 diagnostic
  `research_papers/JEPA/results/level_stability_option_structural_profiles_risk5000_h2_to_2026janmay_wr45_pf13_m18_v1`.
  With thresholds built only from H2 2025, profiles passing both train and
  test gates are SPX `0`, SPY `1`, QQQ `0`. The SPY-only survivor has test WR
  `46.2%`, PF `1.468`, PnL `127.0k`, min month `20`, but cannot support a
  multi-ticker production claim.
- Added non-causal oracle capacity check
  `research_papers/JEPA/results/level_stability_option_structural_profiles_risk5000_janmay_oracle_capacity_diag_v1`.
  Same-window Jan-May thresholds produce gate-passing profiles for SPX/SPY/QQQ
  (`1`/`3`/`28` pass profiles), so the profile family can express a 2026 edge
  only when it is allowed to look at the evaluated period. Do not promote it.
- Added partial forward replay
  `research_papers/JEPA/results/level_stability_option_structural_profiles_risk5000_janmay_oracle_forward_202606_partial_v1`.
  Jan-May oracle profiles fail as pre-2026 evidence (H2 PF SPX `1.062`, SPY
  `0.785`, QQQ `0.844`). Partial June does not rescue them: SPX loses 4/4,
  SPY has no trades, and QQQ has only 7 trades.
- Implication: the current structural profile grid is not the missing causal
  selector. Further work should target regime/OOD selection, more pre-2026
  candidate history, or new OOF state encoders rather than larger same-family
  threshold sweeps.

## 2026-06-26 Research Continuation

- Added explicit trailing-exit labeling to `build_event_option_dataset.py` via
  `--option-exit-mode trailing`; default fixed labels are unchanged. The new
  mode mirrors hard stop, peak-minus-drawdown trail, and emergency TP with
  conservative same-bar handling.
- Built trailing live-exit SPXW/SPY/QQQ dataset:
  `research_papers/JEPA/results/event_option_dataset_spxw_spy_qqq_trailing_liveexit_2024_2026_v1`
  (`136,061` rows, `2024-01-02..2026-06-22`, hard stop `-60%`, trail
  `+50%/25%`, emergency TP `+1000%`). Raw `d80` is the best delta, but
  202507-202606 unconditional PF remains below 1 for all tickers.
- Rejected trailing-label `d80 return` gates:
  `event_option_gate_trailing_liveexit_2024train_2025h2_2026jun_d80_return_v1`
  is fold-clean but fails PF for every ticker (SPXW PF `0.898`, SPY `0.867`,
  QQQ `0.855`; SPY also min month `17`).
- Stricter high-threshold replay
  `event_option_gate_trailing_liveexit_2024train_2025h2_2026jun_d80_return_strict_v1`
  also fails: SPXW PF `0.602`, SPY PF `1.111`, QQQ PF `0.822`, and all have
  min month `0`.
- Implication: the live-like trailing label is not the missing edge. Because
  `d65/d50` are weaker than `d80` before modeling, do not spend more cycles on
  this label family without a materially new state/regime feature.

## 2026-06-25 Research Continuation

- `audit_event_option_research_selection.py` now expands monthly-volume
  backfill config rows into auditable primary/fallback source rows by month,
  so QQQ partial/backfill chains are no longer skipped by strict audits.
- The latest Jan-Jun event-option diagnostics can pass WR/PF/volume gates, but
  strict research-selection audit still fails without a pre-evaluation
  manifest. Treat them as diagnostic or forward-freeze candidates only.
- Direct full20 0DTE gate validation with a 12-month pre-2026 window was
  rejected: `event_option_gate_full20_d65_win_val12_2026janjun_v1` abstained
  every 2026 fold because 2025 validation metrics failed PF/WR/month gates.
- Existing stream scan artifacts:
  `research_papers/JEPA/results/_diagnostics/stream_2025_2026_scan.csv` and
  `_diagnostics/stream_pre2026_short_window_scan.csv`. No individual generated
  stream currently passes both pre-2026 evidence and 2026 strict gates.
- `market_state_expert_router.py` now correctly treats `active_win` as a
  classifier. The small market-state abstention scan
  `event_option_market_state_router_win_active_abstain_small_202501_202512_select_2026test_v1`
  found no direct volume-complete config that satisfies the exact user gates.
- Exploratory fixed backfill
  `event_option_market_state_returnk1_backfill_wink2_m19_2026janjun_v1`
  passes the Jan-Jun 2026 numeric gates (SPXW 49.82%/PF 1.436/min 28; SPY
  50.18%/PF 1.384/min 19; QQQ 52.23%/PF 1.444/min 26), but the same fixed
  policy fails 2025 (`event_option_market_state_returnk1_backfill_wink2_m19_2025test_v1`,
  QQQ 42.19%/PF 0.939). Do not promote it as pre-2026 evidence.
- Follow-up market-state validation:
  `event_option_market_state_router_win_active_abstain_small_202401_202412_select_2025test_v1`
  adds `active_win` and threshold configs for a 2025 holdout selected only from
  pre-2025 data. No direct config passes the target gates.
- Pair scans over common/top market-state backfills also fail:
  `_diagnostics/market_state_pair_backfill_common_m19_md8_2025_select_2026_scan.csv`
  has two 2026 passes but none pass 2025, and
  `_diagnostics/market_state_pair_backfill_top8_m19_md8_2025_select_2026_scan.csv`
  has zero 2026 passes.
- A broader package/stream scan found no existing multi-ticker package or
  per-ticker stream with both pre-2026 evidence and 2026 gates. Recombining the
  current streams is exhausted; the next work should generate materially new
  per-ticker 0DTE streams or stronger OOF state features.
- Rebuilt a 2025H2-through-2026 locked candidate with QQQ meta-gate history
  included:
  `event_option_candidate_spxw_spy_qqq_unionmeta_2025h2_2026jun_with2025h2_risk5000`.
  The same-side delta ranker speed run
  `event_option_delta_ranker_rawhist2024_same_side_2025h2_2026jun_candidate_with2025h2_risk5000_n120_combined`
  has clean fold integrity (`36/36` leak-ok) but fails selection evidence:
  2025H2 overall WR `42.0%`, PF `0.992`, PnL `-$3.8k`. Jan-Jun 2026 passes
  SPXW only (SPXW WR `53.8%`, PF `1.301`, min month `24`; SPY WR `43.2%`,
  PF `1.104`; QQQ WR `42.2%`, PF `1.168`, min month `14`).
- Focused scan
  `research_papers/JEPA/results/_diagnostics/focused_2025h2_2026_stream_gate_scan.csv`
  confirms no scanned 2025H2->2026 stream passes both validation and test
  under WR >= 45%, PF >= 1.3, PnL > 0, and min 18 trades/month.
- TDVP follow-up is negative. The nested profile selector
  `event_option_profile_selector_narrow_tdvp_13ticker_spyqqq_2025h2_2026jun_n120`
  selected only two SPY folds and produced 56 trades at WR `25.0%`, PF `0.556`,
  min month `0`; existing SPY/QQQ TDVP gates also miss the target gates.
- Full20 202501-history daily source routers replayed over 2025H2->2026 are
  not promotable. SPY fails outright (WR `39.9%`, PF `0.812`). QQQ reaches
  WR `50.8%` but misses PF (`1.278`) and monthly volume (`0` over the full
  range; Jan-Jun alone has min `17`).
- QQQ full20 `d80` plus an intraday side circuit is the closest new diagnostic:
  `event_option_qqq_full20_d80_intraday_side_circuit_2025hist_2025h2_2026jun_risk5000`.
  The verifier passes Jan-Jun 2026 (WR `53.87%`, PF `1.531`, min `34`) with
  clean fold integrity, but the full 202507-202606 run fails PF (`1.277`) and
  H2 is weak (WR `43.32%`, PF `0.979`). A monthly source-selector scan found
  zero rules that pass H2 and 2026 separately.
- Literal-gate pre-2026 capacity diagnostic:
  `event_option_pre2026_literal_gates_spxwvol25_spytopk_qqqbalanced_2026janmay_risk5000`.
  It combines existing causal streams and passes the user's exact Jan-May 2026
  gates when only WR `>=45%`, PF `>=1.3`, and min month `>=18` are enforced:
  SPXW WR `49.61%`, PF `1.404`, min `31`; SPY WR `48.05%`, PF `1.626`,
  min `19`; QQQ WR `52.86%`, PF `1.476`, min `18`; fold integrity passes.
  This is not a production promotion: strict research-selection audit fails
  without a pre-2026 family freeze manifest, and curve-health fails due to
  concentration/negative-month flags.
- Frozen-source follow-up:
  `event_option_pre2026_frozen_selectors_literal_gates_2026janmay_risk5000`.
  `apply_event_stream_selector.py` now supports
  `--frozen-select-start-month` / `--frozen-select-end-month`, selecting one
  source from a fixed pre-test window and replaying it unchanged for all test
  months. With `202510..202512` as the selection window it chooses SPXW
  `vol25phys`, SPY `topk`, and QQQ `balanced65`. Jan-May 2026 again passes
  the user's literal gates with weak fold modes disallowed: SPXW WR `49.61%`,
  PF `1.404`, min `31`; SPY WR `48.05%`, PF `1.626`, min `19`; QQQ WR
  `52.86%`, PF `1.476`, min `18`; integrity passes `15/15`.
  Non-strict research-selection audit now has explicit `FROZEN_SELECTED`
  selector evidence and passes with warnings, but strict audit still fails
  because no `research_selection_manifest.json` was frozen before `202601`.
  Curve-health
  also fails from daily/monthly concentration and SPXW/SPY negative-month
  flags, so the result is capacity evidence, not final no-snooping evidence.

## Current State

The production contract is now:

- event-option live scorer `event_option_live_ready_current_sources_202607`
  for entries;
- level-stability ensemble signal and nested structural 0DTE option profiles
  remain required guarded context artifacts;
- risk capital `$5,000`;
- bot requires event-option policy/registry live-ready metadata and runtime
  replay evidence at startup.

Primary artifacts:

```text
neural/models/jepa/jepa_production_level_stability/level_stability_signal.json
neural/models/jepa/jepa_production_structural_options/structural_option_profiles.json
neural/models/jepa/jepa_production_event_options/event_option_policy.json
neural/models/jepa/jepa_production_event_options/component_registry.json
neural/models/jepa/production_manifest.json
```

The live bot no longer silently uses the legacy JEPA 180m signal or
OptionValue fallback. Fallback requires explicit diagnostic flags.
`push_models.ps1` also excludes legacy fallback artifacts unless
`-IncludeLegacyFallback` is passed.

Formal report:

```text
research_papers/JEPA/JEPA_PRODUCTION_REPORT.pdf
```

## Production Build

```powershell
.\neural\jepa\run_pipeline.ps1 -DailyProduction -Workers 32
```

For a fixed month:

```powershell
.\neural\jepa\run_pipeline.ps1 -DailyProduction -ProductionDeployMonth 202606 -Workers 32
```

Verified command:

```powershell
.\neural\jepa\run_daily_production_pipeline.ps1 -DeployMonth 202606 -Workers 32 -SkipSmoke
```

## Validation Snapshot

Live-ready event-option package:

- Policy: `event_option_live_ready_current_sources_202607`.
- Strict validator:
  `python neural\jepa\validate_event_option_production_package.py --require-live-ready`.
- Completed-month validation window: `202601..202605`; June 2026 remains
  partial and is excluded from promotion evidence.
- Overall: 497 trades, WR 48.69%, PF 1.513, PnL +31.030R / +$155,148, min
  monthly trades 75, positive months 5/5.
- SPXW: 146 trades, WR 51.37%, PF 1.659, min monthly trades 18.
- SPY: 177 trades, WR 45.20%, PF 1.412, min monthly trades 22.
- QQQ: 174 trades, WR 50.00%, PF 1.517, min monthly trades 25.
- Integrity: 30 folds and 2 backfill rows checked, no temporal leakage issues.
- Runtime replay: stateful policy replay exactly matches expected SPXW, SPY,
  QQQ, and combined trade rows.
- Research-selection audit caveat: a strict retroactive audit of Jan-May fails
  because no source-family freeze manifest existed before `202601`. The current
  source pool is now frozen for forward validation from `202607` onward at
  `research_papers/JEPA/results/event_option_live_ready_current_sources_202607_freeze_manifest/research_selection_manifest.json`;
  June 2026 is partial and excluded from the freeze evidence.

Historical level-stability structural baseline:

Clean Jan-May 2026 nested result:

- Overall: 640 trades, WR 37.8%, PF 1.227, PnL +248,910.
- Gates: PF >= 1.10, WR >= 35%, PnL > 0, min 15 trades/month, long-rate 20%-80%.
- SPX: 227 trades, WR 37.9%, PF 1.181, PnL +69,884, min monthly trades 17.
- SPY: 204 trades, WR 35.8%, PF 1.157, PnL +59,688, min monthly trades 17.
- QQQ: 209 trades, WR 39.7%, PF 1.361, PnL +119,338, min monthly trades 22.
- Integrity: 15 folds and 640 selected trades checked, no temporal leakage found.

Production `deploy_month=202606` signal fit:

- SPX: `L5_S5_maxday12`, validation PF 1.150.
- SPY: `L1_S8_maxday12`, validation PF 1.271.
- QQQ: `L8_S1_maxdayall`, validation PF 1.251.

## Verification

- `validate_event_option_production_package.py --require-live-ready` passes
  for the current policy and component registry.
- `py_compile` passes for production bot/feed/signal/profile/event-option
  scripts.
- `systemd/ai_bot.service` starts the bot with `--require-event-option-policy`,
  `--require-event-option-component-registry`, `--require-event-option-live-ready`,
  `--enable-event-option-scorer`, and `--strict-event-option-features`.
- Bot dry-run loads the level-stability context artifacts with
  `legacy_signal=disabled`; live entries use the event-option scorer.
- Live rule smoke reproduces SPY `20260601 09:30` as LONG `fib_wall_t25-250_s20_m570`.
- `production_manifest.json` uses repo-relative paths.
- Non-canonical generated Markdown under `research_papers/JEPA/results` is archived as non-production evidence.

## Deprecated

Old Alpha/Temporal JEPA wrappers and ad hoc diagnostics were removed. Historical details remain in git history and in generated research result folders when needed.
