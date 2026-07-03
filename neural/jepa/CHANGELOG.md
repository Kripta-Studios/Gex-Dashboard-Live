# JEPA Changelog

## 2026-07-03 Frozen2025 Static-Union Live Package

- Active production package is now `neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607`.
- Active policy is `event_option_frozen2025_static_union_balanced_202607`.
- `systemd/realtime_feed.service` and `systemd/ai_bot.service` point to the package policy and component registry with `--require-event-option-live-ready`.
- Startup contract was fixed so realtime feed accepts packages whose live contract records `runtime_policy_replay` outside the old location.
- Bot startup logs must show `event_exit=stop=-60%/tp=1000%/trail=50%/25%/min_hold=30m/max_hold=180m`.
- Package validation passes with `--require-live-ready --min-profit-factor 1.3 --min-win-rate 0.45 --min-month-trades 12`.
- Jan-Jun 2026 completed-month validation: 697 trades, WR `57.819%`, PF `1.915`; SPY remains the volume limiter with min month `12`.

## 2026-07-01 Dense15 Backfill19 SPY June-Positive Production Package

- Promoted a new event-option production package: `neural/models/jepa/jepa_production_event_options_backfill19_spy_no_scorethr_wf2026_fullmayjun`.
- Causal WF2026 full-May-Jun result: `research_papers/JEPA/results/event_option_dense15_backfill19_spy_no_scorethr_wf2026_fullmayjun_production_v1`.
- Strict verification passes with `--strict-month-trades --require-positive-months`: SPXW 125 trades, WR `51.20%`, PF `1.749`, min month `19`; SPY 122 trades, WR `50.82%`, PF `1.722`, min month `19`, June PnL `+$10,000`; QQQ 178 trades, WR `46.07%`, PF `1.424`, min month `19`.
- Overall: 425 trades, WR `48.94%`, PF `1.598`, PnL `+$194,500`, all tickers 6/6 positive months. Fold integrity passes over `36` folds and backfill audit passes over `19` rows.
- Curve health passes for all tickers. Runtime monthly-backfill replay reproduced `425/425` trades with `0` missing/extra rows, and snapshot-to-order smoke passed using SPY `win_no_scorethr_d25`.
- Anti-snooping support for SPY rule: the same `win_no_scorethr_d25` policy passes a separate 2025 causal audit before 2026 evidence: 354 trades, WR `50.00%`, PF `1.656`, min month `19`, positive months `12/12` (`research_papers/JEPA/results/_diagnostics/event_option_gate_dense15_zero_dte_win_no_scorethr_d25_physctx_wf2025_spy_v1/VERIFICATION_wf2025_spy_no_scorethr_presupport.md`).
- Updated `production_manifest.json`, `systemd/ai_bot.service`, `systemd/realtime_feed.service`, and `push_models.ps1` to the new package. Raw coverage still records `202605` as partial; this package follows the operator instruction to assume `202605` complete and `push_models.ps1` validates with `--ignore-raw-thetadata-coverage` only when the policy records that assumption.

## 2026-06-30 Target22 Backfill Audit Rejected For Production

- Added `--exclude-months` to `audit_dense_candidate_statistical_robustness.py` and materialized `target19` with `materialize_frozen_pre2025_static_source_trades.py`, so the frozen static-source backfill sweep now covers targets `18..24` while excluding raw-partial `202403`.
- `target22` improves the raw-complete `202501..202604` holdout stress profile: observed gates pass for SPXW/SPY/QQQ and statistical robustness passes on that holdout. However, selecting `target22` because of this holdout result would be data snooping.
- Pre-2025-only target selection evidence (`202301..202412`, excluding `202403`) rejects all targets `18..24`: SPY observed WR/PF remains below `45%`/`1.30`, and QQQ remains below the WR gate for every target. `target22` pre-2025 observed metrics are SPXW WR `47.05%`/PF `1.482`, SPY WR `43.26%`/PF `1.257`, QQQ WR `44.17%`/PF `1.310`.
- Conclusion: keep the high-WR event-option package research-only. The only systemd-deployable production path remains level-stability signal + nested structural option profiles. Updated `systemd` service descriptions to match the active conservative path and re-ran a bot dry-run successfully.

## 2026-06-30 Frozen Pre-2025 Event-Option Package Export

- Exported deployable LightGBM gate components for the pre-2025 frozen Dense15 0DTE candidate using `walkforward_event_option_gate.py --export-deploy-model --deploy-month 202607 --deploy-select-end-month 202604`. The six scorer components are SPXW/SPY/QQQ primary `d25` win models plus SPXW/SPY/QQQ fallback `d50` return models; the training/selection cutoff excludes partial `202605`/`202606`.
- Added `export_frozen_pre2025_event_option_package.py` and generated the blocked package at `neural/models/jepa/jepa_production_event_options_frozen_pre2025`. It contains `event_option_policy.json`, `component_registry.json`, 6 model components, and 3 `monthly_backfill18` policy components. Status is `forward_frozen_research_candidate_not_live_ready`.
- `EventOptionComponentRegistry.from_path(...)` loads the new registry successfully. Research-only package validation passes with explicit flags allowing the known non-production caveats (`--allow-nonpositive-months --allow-failed-curve-health`); strict `--require-live-ready` fails as intended because curve health, robustness, deploy-scorer historical equivalence, and fills are not proven.
- Smoke-tested `event_option_live_scorer.py` on a diagnostic `event_option_snapshots_latest.parquet`: 3 snapshot rows produced 6 candidate rows with no scorer issues. A bot dry-run with `--enable-event-option-scorer` loaded the policy/registry and refused to treat it as live-ready; `rt_data` had no live snapshot available.
- Added `validate_frozen_pre2025_monthly_backfill_runtime_replay.py`; candidate-stream runtime replay reproduced `1162/1162` frozen trades with `0` missing/extra keys across SPXW/SPY/QQQ. Production decision unchanged: do not activate this event-option package in `systemd`; the deployed service path remains level-stability + structural profiles until deploy-scorer historical equivalence, curve/robustness, and paper/broker fill evidence pass.


## 2026-06-30 Pre-2025 Frozen Dense15 0DTE Static Selector

- Materialized the strongest current pure-0DTE static selector at
  `research_papers/JEPA/results/_diagnostics/frozen_source_selector_dense15_pre2025_static_202501_202604_v1/combined`.
  The selector is frozen before `202501` using only `202301..202412`
  selection evidence, excluding raw-partial `202403`; evaluation is
  raw-complete `202501..202604`, with no same-month model used to evaluate that
  month.
- Raw-complete `202501..202604` observed gates pass: SPXW `358` trades, WR
  `57.82%`, PF `2.285`, min month `19`; SPY `386` trades, WR `53.63%`, PF
  `1.925`, min month `19`; QQQ `418` trades, WR `50.48%`, PF `1.699`, min
  month `19`. Overall: `1162` trades, WR `53.79%`, PF `1.939`, PnL
  `+151.254R` (`+$756,268` at `$5k` risk).
- Verification is clean: ticker gates pass, `48` folds have no temporal
  integrity issues, `70` backfill rows pass, selected trades are pure
  `zero_dte`, and the feature leakage audit finds `0` selected leaky features
  despite `80` obvious future/outcome columns in the raw source parquet.
- Strict research-selection passes with the reconstructed
  `research_selection_manifest.json`, but the manifest is not timestamp proof
  that the whole source universe was frozen before `202501`. SPY and QQQ also
  remain below final WR/PF gates in the pre-2025 selection evidence itself, so
  this is strong holdout evidence rather than final production authority.
- Statistical robustness is mixed: observed gates, leave-one-month-out,
  bootstrap 5% lower quantiles, and Wilson lower bounds pass for all tickers;
  top-winner stress fails for SPXW/SPY only because removing the top `5` winners
  reduces min monthly trades from `19` to `16`.
- Production status: not promoted to `systemd` live. The current deployable
  `systemd` path remains the conservative level-stability signal plus nested
  structural option profiles, with event-option and OptionValue disabled. To
  promote this candidate, export a live policy/scorer, wire bot/feed loading,
  preserve the raw-complete guard, and collect forward `202607+` paper/broker
  fill evidence.

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
  ticker call rates are below the `20%` floor.
- Updated `systemd/ai_bot.service` to required level-stability signal +
  required structural option profiles with event-option and OptionValue
  disabled. A local bot dry-run loaded the production artifacts successfully.
  `systemd/realtime_feed.service` no longer requires the blocked event-option
  live-ready package; a local feed dry-run produced parquet/snapshot output but
  timed out during the data-fetch cycle.
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
- Hardened `validate_event_option_production_package.py --require-live-ready`
  so it reads
  `research_papers/JEPA/results/_diagnostics/thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json`
  and rejects any completed-month validation month that is not completed in raw
  all-ticker 0DTE coverage. Current strict validation fails by design on
  `202605`, and `production_manifest.json` no longer advertises the event-option
  package as deployable.
- This does not invalidate the guarded raw-complete research slice above; it
  prevents the higher Jan-May WR/PF package from being promoted to production
  until raw-complete months, completed `202607+` forward evidence, and
  broker/paper/live fill validation are available.

## 2026-06-30

- Added `freeze_pre2026_scan_selection_manifest.py` and generated a strict
  research-selection manifest for
  `event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1`.
  The manifest uses the reproducible scan
  `_diagnostics/scan_existing_results_pre2026_select_2025_eval_202601_202604`,
  freezes before `202601`, and records `202501..202512` as selection evidence.
- Re-ran strict research-selection for that branch over raw-complete
  `202601..202604`; it now passes with no issues/warnings. The formal verifier
  also passes the requested gates: SPXW WR `51.22%`/PF `1.737`/min `19`; SPY WR
  `53.57%`/PF `1.467`/min `38`; QQQ WR `51.35%`/PF `1.435`/min `34`.
- Added `audit_longsrc_pre2026_candidate_requirements.py` and generated
  `requirement_audit_pre2026_longsrc`. The audit accepts the raw-complete
  walk-forward metrics/fold integrity and strict anti-leakage reconstruction, but
  sets `overfit_risk_review_passed=false` and `production_ready_passed=false`.
  Reasons: no timestamp proof for the full research-result universe, no
  completed post-freeze forward month, no live package for this branch, and
  `curve_health=false` for QQQ/SPY.
- Regenerated curve-health on the same raw-complete `202601..202604` window.
  SPXW is clean, but QQQ is flagged for a negative month, month concentration
  above `0.65`, and a negative-day streak above `4`; SPY is flagged for negative
  months and a negative-day streak above `4`. The audit also lists the
  stronger-looking dense candidates rejected because their 2026 folds use
  validation months after `202512`.
- Ran four 32-worker daily-guard scans for the lineage-clean longsrc branches
  with `202501..202506` as selection, `202507..202512` as validation, and
  `202601..202604` as forward check. Summary:
  `research_papers/JEPA/results/_diagnostics/longsrc_pre2026_guard_scan_2025split_summary.md`.
  All scans produced `0` pretest-pass rows and `0` rows passing both pretest and
  forward, despite `1760..1833` 2026-forward-pass rows per scan. Those apparent
  forward winners are rejected as data-snooped guard choices.
- This improves the longsrc branch from research lead to pre-2026-selection
  evidence inside the current result universe, but it still is not timestamp
  proof that the full research universe was frozen before 2026.

## 2026-06-29

- Reclassified the dense15 strict-uniform result after the suspicious WR/PF review.
  Added `audit_dense_candidate_anti_snooping.py`, strict research-selection output,
  and E2E assertions. Current status is `metric_walkforward_objective_passed=true`
  but `requested_walkforward_objective_passed=false`: fold chronology and feature
  leakage checks are clean, yet strict research-selection fails for the broad historical table, so the `202301..202605` WR/PF table is diagnostic rather than production proof. The frozen+guard raw-complete path is superseded in the 2026-06-30 section.
- Added `audit_dense_candidate_pre2026_guard_selection.py` and wired it into
  E2E/anti-snooping. It proves the frozen-through-2025 daily guard
  (`trigger_losses=4`, `pause_days=1`, no volume protection) is rank `1` among
  validation-passing rows when using only pre-2026 scan fields, and its
  raw-complete `202601..202604` guarded holdout passes: SPXW WR `61.18%`/PF
  `2.626`/min `20`; SPY WR `57.83%`/PF `2.286`/min `20`; QQQ WR `53.57%`/PF
  `1.923`/min `20`. This strengthens the guard evidence but does not fix the
  strict research-selection blocker for the broad historical table; the frozen+guard raw-complete `202601..202604` path is superseded in the 2026-06-30 section.
- Added `scan_existing_event_option_pre2026_selection.py`, a reproducible broad
  existing-results triage scan at
  `_diagnostics/scan_existing_results_pre2026_select_2025_eval_202601_202604`.
  It uses `202501..202512` only for selection and raw-complete `202601..202604`
  for holdout reporting. The regenerated run with `--workers 32` evaluated
  `754` dirs; `11` were eligible by 2025 gates/lineage and `4` also passed 2026
  with lineage. The best clean branch is
  `event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1`,
  but strict research-selection still fails because no pre-window manifest
  exists.
- Added an explicit machine-readable lineage audit for the exact frozen-through-2025
  2026 walk-forward requested during review. `audit_dense_candidate_requirements.py`
  now emits `objective_checks.frozen_2025_to_2026_lineage=true` only when the
  `202601..202605` folds are present and every train/select/evidence month is
  `<=202512` and strictly before its evaluated month. `validate_dense_candidate_e2e.py`
  now asserts this flag; the E2E suite passes.
- Added `audit_thetadata_0dte_raw_coverage.py` and wired its
  `raw_coverage.json` into the dense requirement audit and E2E assertions.
  Local raw SPXW/SPY/QQQ 0DTE option parts (`greeks`, `iv`, `ohlc`, `oi`) plus
  underlying files reach common date `20260626`, but this is non-official file
  coverage only: `202605` and `202606` are partial/non-official at the all-ticker
  raw 0DTE level because SPY/QQQ lack `20260529` 0DTE `greeks`/`iv`/`ohlc`
  files. May/June dense checks are therefore available-data diagnostics, not
  official completed raw-month forward evidence; no completed `202607+` month
  exists locally.
- Tightened dense forward-freeze month completion. `evaluate_dense_candidate_forward_freeze.py`
  now overlays the raw ThetaData all-ticker coverage audit on top of event-dataset
  availability, so a month is only treated as completed when both sources agree.
  The previous probe that counted `202605` as completed from the event dataset
  alone now correctly marks `202605` and `202606` as partial diagnostics.
  `verify_event_option_result.py` now supports suffixed outputs, and the dense
  audit/E2E include raw-complete `202601..202604` evidence separately from
  Jan-May available-data evidence. Raw-complete frozen-through-2025 evaluation
  passes: SPXW WR `61.18%`/PF `2.626`/min `20`; SPY WR `58.33%`/PF `2.333`/min
  `20`; QQQ WR `53.57%`/PF `1.923`/min `20`.
- Superseded by the 2026-06-30 raw coverage guardrail above. The earlier
  event-option sidecar refresh matched policy
  `event_option_live_ready_current_sources_202607` and the Jan-May result
  `event_option_live_ready_current_sources_2026janmay_risk5000` (`497`
  trades, WR `48.69%`, PF `1.513`, PnL `+31.03R`), but that evidence is now
  diagnostic because raw all-ticker 0DTE coverage marks `202605` as
  partial/non-official.
- The strict validator still enforces stale sidecar, result-dir, deploy-month,
  and policy chronology checks; as of the raw coverage guardrail it also blocks
  validation months not completed in raw all-ticker 0DTE coverage before any
  event-option package can be advertised in `production_manifest.json`.- Added `validate_dense_candidate_broker_order_contract.py`, a local broker-order
  contract preflight for the dense15 candidate. It validates the 45
  offline-fill-derived BUY_TO_OPEN payloads plus the bot's BTO/STC paper
  intents (`47/47` orders) for 0DTE contract fields, OCC keys, cent-rounded
  limits, integer quantity, max debit under `$5,000`, and
  `broker_submission=false`. The check is now part of requirement audit,
  shadow validation, E2E, and candidate policy evidence as
  `broker_order_contract_validation=true`; it is not broker API acceptance or
  fill evidence.
- Wired the fixed daily-loss guard into the event-option bot runtime as an
  opt-in policy field: `runtime_risk_guards.daily_loss_streak_pause`. The bot
  now blocks a ticker after four completed losing active days, records the
  consumed pause day in `event_option_runtime_state.json`, and resumes after
  the one-day pause. Added `validate_bot_event_daily_loss_guard.py`; the
  validation passes and is now part of the requirement audit and E2E suite as
  `bot_daily_loss_guard_runtime=true`. The dense15 candidate policy declares
  the guard, but the package remains
  `forward_frozen_research_candidate_not_live_ready`.
- Added a causal daily-guard mitigation check for the frozen-through-2025
  holdout. The fixed rule `trigger_losses=4`, `pause_days=1`,
  `volume_protect_monthly_target=0` was supported by pre-2026 scans
  (`dense_candidate_pre2026_daily_guard_selection_scan_v1.csv` and
  `dense_candidate_pre2026_recent_daily_guard_selection_scan_v1.csv`) without
  using 2026 for selection. Applied to
  `dense_candidate_frozen_through_202512_eval_202601_202605_v1`, the guarded
  result
  `research_papers/JEPA/results/_diagnostics/dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0`
  passes formal completed-2026 gates (`SPXW` WR `59.05%`/PF `2.403`/min
  `20`; `SPY` WR `57.84%`/PF `2.287`/min `19`; `QQQ` WR `50.98%`/PF
  `1.733`/min `18`) and strict 2026 holdout curve-health (`0` negative
  months, max negative-day streak `<=4` for every ticker). This is forward
  holdout risk evidence only; it does not repair the full `202301..202605`
  curve-health failure or promote the package to live-ready.
- Exported the dense 0DTE uniform strict candidate into a separate deploy
  package without touching the current live-ready production package:
  `neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate`.
  The package contains six deploy LightGBM direction models for `202607`
  (`SPXW/SPY/QQQ` strict d25 win gates plus d50 `forcedmax3` fallback gates),
  three `event_monthly_volume_backfill_policy` JSON components, a candidate
  `component_registry.json`, `event_option_policy.json`, and `SUMMARY.md`.
- The candidate registry loads successfully and
  `EventOptionComponentRegistry.score_event_option_gate_component(...,
  strict=True)` scores real dense15 dataset rows for all six exported models.
  `event_option_live_scorer.py` now recognizes the three
  `*.monthly_backfill18` policy components and emits primary/fallback
  candidates for the dense15 package; `tradingbot_wrapper_jepa.py` gates
  generic fallback rows by month-to-date pace using its existing event-option
  runtime state.
- Added `replay_dense_monthly_backfill_runtime_policy.py` and ran it against
  the SPXW/SPY/QQQ historical OOS primary/fallback streams. The stream-level
  bot-state replay exactly matches the official monthly-backfilled CSVs:
  SPXW `1,032/1,032`, SPY `980/980`, QQQ `973/973`, and combined
  `2,985/2,985` rows matched with zero realized-return, score,
  `backfill_count_before`, or `backfill_required_count` differences. Evidence:
  `event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/runtime_policy_replay`.
- Added `smoke_dense_live_snapshot_to_order.py` and ran a ThetaData-backed
  snapshot-to-order smoke for `20260515 14:30`. It built real live-schema
  0DTE snapshot rows from historical SPXW/SPY/QQQ greeks/OHLC/OI plus spot,
  scored them through the dense candidate registry with strict features, and
  selected concrete contracts/premiums for SPX, SPY, and QQQ. Evidence:
  `event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/snapshot_to_order_smoke`.
- Added `batch_smoke_dense_live_snapshot_to_order.py` and ran the same
  ThetaData-backed snapshot-to-order smoke over five May-2026 dates
  (`20260501`, `20260508`, `20260515`, `20260522`, `20260528`) and three
  cutoffs (`10:00`, `12:00`, `14:30`). All `15/15` cases passed with strict
  features, no candidate issues, and SPX/SPY/QQQ contracts selected in every
  case. Evidence:
  `event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/snapshot_to_order_batch_smoke`.
- Added `audit_dense_candidate_requirements.py`, which ties the evidence back
  to the original objective. Superseded by the anti-snooping review: the audit
  now separates `metric_walkforward_objective_passed=true` from
  `requested_walkforward_objective_passed=false`. Per-ticker WR/PF/volume gates
  pass, but strict research-selection fails for the broad historical table, so it is not final production proof. The frozen+guard raw-complete path is superseded in the 2026-06-30 section. It separately reports `live_ready_passed=false` because
  future `202607+` forward evidence, strict curve-health acceptance, and
  broker/fill validation are not complete.
- Extended the requirement audit so live-readiness is no longer a hard-coded
  false. It now reads the official forward-freeze evaluation artifact and an
  optional broker/fill validation artifact. After the anti-snooping review the
  regenerated audit reports `metric_walkforward_objective_passed=true`,
  `requested_walkforward_objective_passed=false`, and `live_ready_passed=false`;
  explicit blockers include strict research-selection, candidate package status,
  strict curve-health, `pending_no_completed_forward_months` with event dataset
  latest date `20260616`, raw partial/non-official months through `202606`, and
  no supplied broker/fill validation artifact.
- Tested a fixed causal daily-streak guard diagnostic on the dense candidate.
  The best simple variant,
  `research_papers/JEPA/results/_diagnostics/dense_candidate_daily_streak_guard_l4p1_vp18`,
  uses only prior completed-day PnL (`4` losing days -> pause `1` day, with
  monthly volume protection at `18`). Formal verification still passes
  (`SPXW` WR `48.96%`/PF `1.602`/min `18`; `SPY` WR `46.95%`/PF `1.472`/min
  `18`; `QQQ` WR `47.08%`/PF `1.472`/min `18`), but strict curve-health still
  fails because negative months, negative-day streaks, and weak early prefix
  share remain. Do not promote this guard as a curve-health fix.
- Ran a wider daily-streak/rolling-loss guard scan over the dense candidate:
  `research_papers/JEPA/results/_diagnostics/dense_candidate_daily_streak_guard_scan_targeted_202301_202605`.
  It evaluated `1,260` causal configurations with selection `202301..202412`
  and validation `202501..202605`; `0` passed both selection and validation
  gates. The best full-period diagnostic,
  `dense_candidate_daily_streak_guard_scan_best_t4p2_roll3m1_vp20`, still
  passes formal full-period gates (`SPXW` WR `50.46%`/PF `1.702`/min `18`;
  `SPY` WR `47.07%`/PF `1.478`/min `18`; `QQQ` WR `48.12%`/PF `1.534`/min
  `18`) but fails strict curve-health with the same negative-month,
  negative-day-streak, and early-prefix flags. Treat the whole daily guard
  family as rejected for production promotion unless a future forward-frozen
  selector picks it causally.
- Added `apply_event_monthly_pnl_rescue_backfill.py` and
  `scan_event_monthly_pnl_rescue_backfill.py` to test a causal MTD PnL rescue
  overlay: fallback rows are allowed when the ticker is behind deterministic
  monthly volume pace or when prior completed-day month-to-date return is at
  or below a fixed threshold. Scan evidence:
  `research_papers/JEPA/results/_diagnostics/dense_candidate_monthly_pnl_rescue_scan_202301_202605`.
  It evaluated `135` common-parameter configurations with selection
  `202301..202412` and validation `202501..202605`; `0` passed both windows.
  The best full-period diagnostic,
  `dense_candidate_monthly_pnl_rescue_best_t-1_start10_max3_cd45`, passes
  formal full-period gates (`SPXW` WR `50.31%`/PF `1.689`/min `18`; `SPY` WR
  `46.63%`/PF `1.450`/min `18`; `QQQ` WR `47.78%`/PF `1.514`/min `18`) but
  still fails strict curve-health. Its pure `fallback_pnl_rescue` trades are
  negative overall, so this overlay is rejected for production promotion.
- Ran a causal first-event daily regime gate over the dense candidate:
  `research_papers/JEPA/results/_diagnostics/dense_candidate_daily_regime_gate_s3_202301_202605_v1`.
  It trains LightGBM day classifiers on prior months only, selects thresholds
  on the previous `3` months, and used `--lgb-jobs 32`. The diagnostic is
  rejected: WR/PF still pass (`SPXW` WR `49.36%`/PF `1.628`; `SPY` WR
  `46.80%`/PF `1.463`; `QQQ` WR `47.46%`/PF `1.495`), but monthly volume
  falls below the explicit `18` trade/month gate (`15`, `14`, and `13`
  respectively). Fold/backfill integrity is clean (`123` folds, `324`
  backfill rows), and strict curve-health remains false with negative-month,
  negative-day-streak, and early-prefix-share flags. Do not promote this gate.
- Added `validate_dense_candidate_offline_fills.py`, an offline ThetaData
  market-data fill simulator for the concrete contracts selected by the
  snapshot-to-order batch smoke. It validates the exact strike/right/expiry
  against 1-minute greeks/OHLC and replays the event-option exit contract
  (`+50%` take profit, `-30%` stop, `180m` max hold). The May-2026 batch now
  has `45/45` orders with matching raw premium and available exit path at
  `offline_fill_simulation/offline_fill_simulation.json`. After flooring the
  runtime modeled entry premium to the observed ask when available, strict
  execution-cost coverage also passes (`45/45` modeled entries cover the ask);
  real broker/order fill validation remains open.
- Added `evaluate_dense_candidate_forward_freeze.py` to automate the official
  forward evaluation once completed months `>=202607` exist; the start month
  is included automatically when it is complete. The current
  official run writes
  `event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_evaluation_202607_pending_v1`
  with status `pending_no_completed_forward_months`, no available `202607+`
  rows, and dataset latest date `20260616`; no performance claim is made.
  The script also reports available/completed/partial months and supports
  explicit pre-freeze or partial-month diagnostic modes for cable testing,
  which must not be cited as forward evidence.
  It is intentionally marked
  `forward_frozen_research_candidate_not_live_ready`: the current production
  `jepa_production_event_options` package remains unchanged, and this new
  package still needs forward `202607+` evidence, broker/fill integration
  checks, and a curve-health decision before promotion.
- Added an explicit completed-2026 walk-forward slice at
  `research_papers/JEPA/results/_diagnostics/dense_candidate_walkforward_2026_completed_jan_may_v1`.
  This verifies the existing OOS dense candidate rows for `202601..202605`
  without using the `202607` forward-freeze manifest. The slice passes the
  requested gates with clean fold/backfill integrity: SPXW `99` trades, WR
  `54.55%`, PF `2.000`, min month `19`; SPY `100` trades, WR `51.00%`, PF
  `1.735`, min month `19`; QQQ `108` trades, WR `53.70%`, PF `1.933`, min
  month `19`. Fold lineage is documented in `CAUSAL_WALKFORWARD_2026.md`.
- Added the frozen-through-2025 holdout requested in review:
  `research_papers/JEPA/results/_diagnostics/dense_candidate_frozen_through_202512_eval_202601_202605_v1`.
  It uses `deploy_month=202601` and `select_end_month=202512`; the underlying
  components fit on `202201..202506`, select thresholds/configs on
  `202507..202512`, and then evaluate the same frozen policy on
  `202601..202605`. Formal verification passes with weak fold modes disabled:
  SPXW `106` trades, WR `58.49%`, PF `2.348`, min month `20`; SPY `103`,
  WR `58.25%`, PF `2.326`, min `19`; QQQ `103`, WR `51.46%`, PF `1.767`,
  min `19`. Integrity checks `30` folds and `25` backfill rows with no issues.
- Confirmed the local ThetaData source extends beyond the canonical dense
  dataset but still does not contain a completed `202607` month. Canonical
  dense artifacts end at `20260616`; an isolated local diagnostic manifest and
  dense15 physics dataset were built for `20260617..20260626` under
  `research_papers/JEPA/results/_diagnostics/thetadata_manifest_spxw_spy_qqq_20260617_20260626`
  and
  `research_papers/JEPA/results/_diagnostics/event_option_dataset_dense15_zero_dte_20260617_20260626_v1_physics`.
- Added `evaluate_dense_candidate_partial_dataset.py` and applied the frozen
  dense15 candidate to the incomplete June dataset in
  `research_papers/JEPA/results/_diagnostics/dense_candidate_partial_20260601_20260626_eval_v1`.
  This is diagnostic only, not official forward evidence. It is negative:
  combined `57` trades, WR `28.07%`, PF `0.650`, PnL `-4.3R`; QQQ `18`
  trades/PF `0.641`, SPXW `20`/PF `0.714`, SPY `19`/PF `0.595`. Do not use
  this partial month to promote the model.
- Added `evaluate_dense_candidate_fixed_holdout.py` for the stricter
  fixed-cutoff test suggested during review. With model fitting through
  `202510`, threshold/config selection through `202604`, and held-out
  evaluation on completed `202605`, the dense15 policy passes cleanly:
  SPXW `20` trades, WR `60.00%`, PF `2.500`; SPY `19` trades, WR `68.42%`,
  PF `3.611`; QQQ `19` trades, WR `63.16%`, PF `2.857`; fold/backfill
  integrity is clean. Evidence:
  `research_papers/JEPA/results/_diagnostics/dense_candidate_fixed_holdout_select_through_202604_eval_202605_completed_v1`.
  The same fixed-through-April components applied to `202605..202606` partial
  also pass aggregate gates, but June remains incomplete and non-official; the
  June-only partial rows are still weak for SPXW (`33.33%` WR/PF `0.833`) and
  QQQ (`38.89%` WR/PF `1.061`).
- Extended `audit_dense_candidate_requirements.py` so the machine-readable
  requirement audit checks the dedicated completed-2026 walk-forward slice,
  the frozen-through-2025 holdout, the fixed-through-April May-2026 holdout,
  raw coverage, and the anti-snooping audit. The regenerated audit reports
  `metric_walkforward_objective_passed=true`, `requested_walkforward_objective_passed=false`,
  and `live_ready_passed=false`; blockers include strict research-selection,
  package status, strict curve-health, missing completed `202607+` forward
  evidence, and broker/order fill validation.
- Added `validate_dense_candidate_paper_orders.py` to convert the 45
  snapshot/offline-fill selections into deterministic paper order payloads.
  It validates 0DTE contract fields, BUY_TO_OPEN limit orders, cent-rounded
  limits that cover the observed ask, integer contract counts, max debit under
  the `$5,000` risk cap, and offline exit-path availability. Evidence:
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/paper_order_validation`;
  `45/45` payloads pass. This is paper payload validation, not broker API
  acceptance or real exchange fill evidence.
- Added opt-in paper order intent output to `bots/tradingbot_wrapper_jepa.py`.
  Passing `--paper-order-intents` writes BTO/STC JSONL payloads to
  `trades_jepa/paper_order_intents_jepa.jsonl` with `broker_submission=false`;
  no broker API call is made. Added `validate_bot_paper_order_intents.py`,
  which validates local intent generation, cent rounding, max-debit checks,
  order sides, contract fields, and paper-only status. The E2E dense candidate
  validation now runs this check.
- Added `validate_dense_candidate_shadow_deployment.py` and ran it against the
  dense15 candidate. Evidence:
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/shadow_deployment_validation`.
  The validation passes: the package loads in shadow mode, production
  live-ready guards reject it, production systemd units still point to the
  live package rather than the candidate, and replay/smoke/offline-fill/paper
  order evidence is present. This is a safety check, not a production
  promotion.
- Added `validate_dense_candidate_e2e.py` as the single reproducible validation
  runner for the dense15 candidate. It compiles the audit/shadow/holdout/paper
  order scripts, checks core JSON artifacts, re-runs formal verification for
  `202301..202605`, completed-2026 `202601..202605`, frozen-through-2025
  `202601..202605`, and fixed-holdout `202605`, regenerates paper-order,
  requirement, and shadow validations, and asserts that June partial remains
  non-official. Evidence:
  `research_papers/JEPA/results/event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1/e2e_validation`;
  the E2E result passes.

## 2026-06-28

- Promoted the dense 0DTE branch from a 2025-2026-only diagnostic to a
  multi-year causal research candidate:
  `event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_causal_2023_2026_v1`.
  The policy is uniform across SPXW/SPY/QQQ: strict d25 win-probability
  LightGBM gate, threshold selected inside each fold from prior validation
  months only, plus deterministic monthly volume backfill from the d50
  `forcedmax3` stream. Formal verification over `202301..202605` passes the
  requested gates with fold/backfill integrity clean: SPXW WR `49.42%`/PF
  `1.632`/min `18`, SPY WR `46.94%`/PF `1.471`/min `18`, QQQ WR `47.17%`/PF
  `1.478`/min `18`; overall `2,985` trades, WR `47.87%`, PF `1.527`, and
  `246` folds checked.
- The non-strict research-selection audit passes after including each
  `monthly_volume_backfill_config.csv` as explicit selector evidence. A
  forward-only freeze manifest was written to
  `event_option_gate_dense15_zero_dte_win_d25_strict_uniform_backfill_d50max3_forward_freeze_202607_v1`;
  it must not be used to certify months before `202607`.
- Curve-health is still not fully green under the repo's stricter curve rules:
  the branch has low concentration and low DD/PnL, but fails the negative
  month/streak and early-prefix share checks. Treat this as a strong causal
  research candidate, not a live production promotion until runtime replay and
  curve-health policy decisions are made.
- Built a new dense 0DTE ThetaData event-option dataset, independent of the
  previous near-level event universe:
  `event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1`.
  It uses SPXW/SPY/QQQ zero-DTE candidates on 15-minute bars from 10:00 to
  14:30 ET, then
  `event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1_physics`
  adds causal physical/cross-index features. The dense dataset has `59,774`
  rows and the physics version has `358` columns with no leaky new columns.
- Hardened `build_event_option_dataset.py` against bad underlying rows where a
  prior close is zero; return features now become `NaN` instead of crashing
  with `ZeroDivisionError`.
- Found a dense-family causal diagnostic that clears the explicit
  `202501..202605` WR/PF/volume gates:
  `event_option_gate_dense15_zero_dte_mixed_d50d25_causal_2025_2026_v1`.
  It combines SPXW/SPY d50 return gates with deterministic monthly volume
  backfill and QQQ d25 win-probability gating. Combined: `1,785` trades, WR
  `46.39%`, PF `1.437`, min month `73`, PnL return `125.37R`; fold integrity
  passes with `85` folds checked. By ticker: SPXW WR `47.33%`/PF `1.486`/min
  `18`, SPY WR `45.38%`/PF `1.378`/min `18`, QQQ WR `46.57%`/PF `1.454`/min
  `24`.
- Extended the earlier mixed dense-family logic to `202301..202605` without
  parameter changes. It is not a 2022-2026 solution: SPXW backfilled d50 drops
  to WR `43.34%`/PF `1.265`/min `18`, SPY to WR `41.42%`/PF `1.165`/min
  `18`, and QQQ d25 win to WR `43.56%`/PF `1.287`/min `0`. Year splits show
  the main failure is 2023; it was superseded by the uniform strict d25 win
  gate plus d50 backfill branch above.
- Ran direct all19 LightGBM event-gate experiments on
  `event_option_dataset_full19_2022_2026_v1_physics_combined` with three
  tickers in parallel and roughly 30 CPU workers total. The best new direct
  stream was `event_option_gate_direct_return_forcedvol_d80_physctx_call02_2025_2026_*_v1`:
  SPXW WR `44.83%`/PF `1.123`/min `19`, SPY WR `46.92%`/PF `1.240`/min
  `19`, and QQQ WR `42.75%`/PF `1.128`/min `17`. Other d65, validation
  threshold, win-label, and core3 variants were weaker or broke monthly
  volume; no direct gate clears the requested WR/PF/volume gates.
- Tested that direct `d80_phys` stream as a seventh source in the rolling
  backfill selector. The thin 7-source run over `202501..202605` is rejected:
  SPXW WR `43.28%`/PF `1.060`/min `18`, SPY WR `47.55%`/PF `1.289`/min
  `17`, and QQQ WR `42.33%`/PF `0.981`/min `0`. A focused 32-worker SPY
  volume-repair grid worsened to WR `46.83%`/PF `1.208`/min `10`, so the
  near-miss is not robust enough to promote.
- Added `append_xinput_oof_to_event_option_dataset.py` and generated causal
  GPU XInputJEPA OOF features for `202401..202606` at
  `xinput_oof_ctx6_e3_202401_202606_eventdiag_v1`. The appended event-option
  dataset has `42` `xjepa_*` columns and matched coverage of SPXW `55.9%`,
  SPY `56.8%`, and QQQ `58.0%` across the 2022-2026 event rows. The direct
  `phys/ctx/xjepa` forced-volume d80 gate is still rejected: SPXW WR
  `44.43%`/PF `1.095`/min `19`, SPY WR `46.57%`/PF `1.212`/min `19`, and QQQ
  WR `43.86%`/PF `1.167`/min `17`.
- The QQQ `xjepa` validation-threshold diagnostic improves trade quality
  where it trades (WR `47.22%`, PF `1.435`) but abstains whole months
  (`min_month_trades=0`). Using it as an eighth source in the rolling backfill
  selector remains negative: WR `41.67%`, PF `0.982`, PnL slightly negative,
  and min month `0`.
- Parallelized `scan_event_static_union_configs.py` for 32-worker Windows
  scans. Added `--workers`, `--chunksize`, `--daily-order-grid`, and
  `--min-sources`; the scanner now exports `selected_config_folds.csv` with
  prior `select_months` and source paths so combined artifacts can pass fold
  integrity and research-selection audits.
- Added `--workers`/`--chunksize` to
  `apply_event_trade_union_config_selector.py` so monthly rolling config
  selection can score candidate configs in process pools. The 2024-2026
  full20 stress runs used 8 workers per ticker in parallel batches, keeping
  total workers near the 32-thread machine limit.
- Ran rolling full20 order-grid stress tests for `s3`, `s6`, and `s12` select
  windows over `202401..202606`. None reaches the requested multi-year gates.
  The 2026 partial window often passes, but 2025 remains below PF `1.30`:
  SPXW best PF `0.969`, SPY best PF `1.204`, and QQQ best PF `1.194`.
  All full-range rolling variants still have `min_month_trades=0`.
- Ran the broader 6-source static full20 scan
  `event_static_union_config_scan_full20_2024select_2025_2026test_6src_ordergrid_32w_v1`
  with 32 workers across `d80`, `d65win`, `d65ret`, `d80_front`, `d50ret`,
  and `d80_zero`. It scanned `4,992` configs per ticker with `0` 2024
  select-pass and `0` 2025-pass configs for SPXW/SPY/QQQ. Best 2025 PF among
  configs with WR `>=45%` and min month `>=18` is only SPXW `1.157`, SPY
  `1.253`, and QQQ `1.245`; the full20 static-union family is rejected as a
  2022-2026 solution path.
- Audited the strong
  `event_static_union_h1h2_qbackfill_spxwspy_objpass_simpler_spy_2025_2026_risk5000_v1`
  branch with a fresh H2-only all10 static-union scan:
  `_diagnostics/spxw_spy_h2only_causal_rank_scan_all10_32w_v1`. The artifact
  still passes explicit `202501..202605` gates (SPXW WR `49.71%`, PF `1.402`,
  min `19`; SPY WR `49.45%`, PF `1.408`, min `19`; QQQ WR `49.86%`, PF
  `1.361`, min `19`), but SPXW's all-pass row is rank `360` and SPY's is rank
  `614` under selection-window-only ranking. Treat this as numeric diagnostic
  evidence, not strict 2025 promotion proof.
- Added `apply_event_trade_union_backfill_selector.py`, a rolling monthly
  selector that chooses a primary source union plus deterministic volume
  fallback using only prior OOS months. It writes
  `trade_union_backfill_selector_trades.csv` and
  `trade_union_backfill_selector_folds.csv`; the verifier, curve-health tool,
  and stream filter scanner now recognize those artifact names.
- Rejected the initial rolling-backfill selector family. The thin 6-source
  `s6` runs over `202501..202605` produce SPXW WR `42.64%`/PF `1.109`/min
  `18`, SPY WR `47.99%`/PF `1.329`/min `17`, and QQQ WR `43.33%`/PF
  `1.025`/min `0`. SPY's best thin artifact has clean fold/backfill integrity
  but fails strict volume; the broader 32-worker SPY volume-repair grid drops
  to PF `1.241` and min month `10`.
- Regenerated the Oct-Dec static-union config scans with 32 workers:
  `event_static_union_config_scan_octdec_scoredesc_spxw_2026janmay_32w_v1`,
  `event_static_union_config_scan_octdec_ordergrid_spy_2026janmay_32w_v1`,
  and `event_static_union_config_scan_octdec_ordergrid_qqq_3src_2026janmay_32w_v1`.
  The preferred combined diagnostic
  `event_static_union_config_scan_octdec_scoredesc_spxw_combined_2026janmay_32w_v1`
  passes the Jan-May 2026 verifier with weak modes disallowed: SPXW WR
  `57.99%`, PF `2.040`, min month `19`; SPY WR `50.63%`, PF `1.622`, min
  month `70`; QQQ WR `47.65%`, PF `1.368`, min month `72`. Overall:
  `1,139` trades, WR `50.22%`, PF `1.540`, `+$354,669`, and `15/15` folds
  clean. Curve-health passes all tickers. Non-strict research-selection audit
  passes; strict audit still fails only because no
  `research_selection_manifest.json` was frozen before `202601`.
- Created forward-only freeze
  `event_static_union_config_scan_octdec_scoredesc_spxw_202607_forward_freeze_manifest_v1`
  for that 32-worker config-scan diagnostic. A strict Jan-May audit using the
  manifest fails as intended because `frozen_before_month=202607` is after the
  evaluated start month; the freeze is valid only for months `>=202607`.
- Also recorded the fully selector-ranked order-grid combined artifact
  `event_static_union_config_scan_octdec_ordergrid_combined_2026janmay_32w_v1`.
  It passes WR/PF/month-volume gates and fold integrity, but SPXW curve-health
  fails (`top5_share=123.6%`, DD/PnL `65.3%`, one negative month), so the
  score-desc SPXW rule remains the robust diagnostic.
- Optimized `scan_event_static_union_backfill.py` for higher worker counts on
  Windows. Added `--prefilter-source-cache-dir` so scans can cache
  ticker/month-filtered source CSVs before spawning workers, removed the second
  per-worker source read, and wired `--chunksize` into `ProcessPoolExecutor.map`.
  This makes 32-worker scans viable without repeatedly loading full source
  files in every process.
- Reran SPXW/SPY H1/H2 static-union and monthly-backfill diagnostics with 32
  workers. The simple six-source family remains negative for causal selection:
  `_diagnostics/spy_static_union_h1h2_backfill_top24_6src_targets18_20_32w_v1.csv`
  has `2,592` rows, `0` pretest-pass rows, `144` forward-pass rows, and `0`
  all-pass rows; `_diagnostics/spy_static_union_h1h2_backfill_top24_6src_targets21_22_md1_4_cd0_15_30_32w_v1.csv`
  has `3,456` rows, `0` pretest-pass rows, `160` forward-pass rows, and `0`
  all-pass rows.
- SPXW shows the same issue:
  `_diagnostics/spxw_static_union_h1h2_backfill_top24_6src_targets18_20_32w_v1.csv`
  has `2,592` rows, `0` pretest-pass rows, `19` forward-pass rows, and `0`
  all-pass rows; `_diagnostics/spxw_static_union_h1h2_backfill_top24_6src_targets21_22_md1_4_cd0_15_30_32w_v1.csv`
  has `3,456` rows, `0` pretest-pass rows, `21` forward-pass rows, and `0`
  all-pass rows. SPY's forward-passing rows are not causally selectable from
  H1/H2 evidence; SPXW's H1 slice still has month-volume failures, often
  `sel_min_month_trades=0`.
- Revalidated the current event-option production package with
  `validate_event_option_production_package.py --require-live-ready`; it still
  passes with policy `event_option_live_ready_current_sources_202607`, registry
  status `live_ready_runtime_replay_verified`, curve-health pass, and zero
  missing live-equivalence/invalidated components.
- Updated `freeze_event_option_research_manifest.py` so
  `selection_evidence_months` are derived from prior evidence columns such as
  `select_months`, `train_months`, and `val_months`, falling back to
  `test_month` only when no evidence columns exist.
- Created forward-only freeze
  `event_static_union_pretest_octdec_scorecap5_202607_forward_freeze_manifest_v1`
  for the strong Oct-Dec static-union scorecap5 diagnostic. The manifest now
  records selection evidence months `202510..202512` for SPXW/SPY/QQQ and is
  valid only for months `>=202607`. A strict audit against Jan-May 2026 fails
  as intended only because `frozen_before_month=202607` is after evaluated
  start month `202601`.
- Improved `audit_event_option_research_selection.py` manifest path handling:
  relative `--manifest` paths that exist from the current working directory are
  now used directly; otherwise the auditor falls back to resolving the manifest
  under the audited result directory.
- Added explicit audit columns to
  `apply_event_trade_union_config_selector.py` (`selected_source`,
  `source_stream`, and pipe-separated `source_path`) and taught
  `audit_event_option_research_selection.py` to follow pipe-separated source
  paths. This makes rolling trade-union selector folds auditable without manual
  interpretation of the `variants` column.
- Regenerated the rolling 3-month scorecap5-pool trade-union selector as
  `event_trade_union_config_selector_scorecap5pool_monthly_s3_spxw_spy_qqq_2026janmay_v2`.
  The formal Jan-May 2026 verifier passes with weak modes disallowed: SPXW WR
  `47.93%`, PF `1.377`, min month `19`; SPY WR `50.81%`, PF `1.562`, min
  month `54`; QQQ WR `47.33%`, PF `1.303`, min month `72`. Overall:
  `1,065` trades, WR `48.64%`, PF `1.415`, PnL `+54.595R` / `+$272,973`,
  and `15/15` folds clean.
- The non-strict research-selection audit now recognizes causal selector
  evidence for that v2 artifact and has no blocking issues, but warns that
  `research_selection_manifest.json` is missing. Curve-health still fails:
  QQQ has `top5_share=85.4%` plus one negative month, and SPXW has
  `top5_share=123.6%`, DD/PnL `65.3%`, and one negative month. Treat this as
  causal numeric evidence, not a robust production promotion.
- Created forward-only freeze
  `event_trade_union_config_selector_scorecap5pool_monthly_s3_202607_forward_freeze_manifest_v2`
  for the rolling scorecap5-pool selector. A strict Jan-May audit using this
  manifest fails as intended because `frozen_before_month=202607` is after the
  evaluated start month and the manifest includes Jan-May evidence; it is valid
  only for months `>=202607`.
- Extended `apply_event_trade_union_config_selector.py` with
  `--daily-order-grid` (`time_asc`, `score_desc`). The default remains
  `time_asc`; `score_desc` reproduces the score-ranked daily cap used by the
  stronger static-union diagnostics while still choosing the order from prior
  OOS months.
- Rejected a causal daily streak guard overlay on the rolling scorecap5-pool
  v2 artifact:
  `_diagnostics/scorecap5_monthly_s3_v2_daily_streak_guard_scan_s2v2f1_small_16w.csv`
  scanned `420` parameter rows with `6` selection+validation pass rows,
  `0` May-forward pass rows, and `0` rows passing both. The guard usually
  damaged SPXW/SPY May 2026 and is not a promotion path.
- New order-grid selector diagnostic
  `event_trade_union_config_selector_scorecap5pool_monthly_s3_ordergrid_spxw_spy_qqq_2026janmay_v1`
  passes formal Jan-May gates and improves SPXW materially (WR `56.21%`, PF
  `1.950`, min month `19`, curve-health clean). The combined result still
  fails curve-health because QQQ top5 share is `89.8%` and SPY top5 share is
  `85.7%`.
- New strongest diagnostic:
  `event_option_mixed_ordergrid_spxw_spyrolling_qqqstatic_scorecap5_2026janmay_v1`.
  It combines SPXW order-grid rolling selector, SPY rolling scorecap5 selector
  from v2, and QQQ static pretest scorecap5 union. Formal verifier passes with
  weak fold modes disallowed: SPXW WR `56.21%`, PF `1.950`, min month `19`;
  SPY WR `50.81%`, PF `1.562`, min month `54`; QQQ WR `47.65%`, PF `1.368`,
  min month `72`. Overall: `1,116` trades, WR `50.00%`, PF `1.508`,
  `+66.525R` / `+$332,625`, and `25` folds clean.
- Curve-health passes for the mixed diagnostic: QQQ top5 `58.0%`, SPXW top5
  `64.9%`, SPY top5 `78.3%`, no curve-health flags. Non-strict
  research-selection audit passes with causal selector evidence, but strict
  retroactive proof remains unavailable because no manifest was frozen before
  `202601`.
- Created forward-only freeze
  `event_option_mixed_ordergrid_spxw_spyrolling_qqqstatic_scorecap5_202607_forward_freeze_manifest_v1`.
  A strict Jan-May audit fails as intended because the manifest is frozen for
  `202607` and SPXW/SPY selection evidence includes Jan-Apr 2026. Treat it as
  a 202607-forward architecture freeze, not a Jan-May retroactive promotion.
- Generalized `apply_event_trade_union_window_meta_selector.py` so component
  meta-selection can load `combined_*`/`static_union_*` candidate artifacts in
  addition to `trade_union_config_selector_*`, exports `candidate_daily_order`,
  and supports `--score-top5-target` for concentration-aware ranking. The
  research-selection auditor now treats `selected_meta_window_candidate` as
  selector evidence.
- Generated extended Oct-2025 through May-2026 component candidates for
  SPXW/SPY/QQQ (`*_2025oct_2026may_time_v1` and
  `*_2025oct_2026may_ordergrid_v1`) so a component meta-selector can choose
  January 2026 using only Oct-Dec 2025 OOS component history.
- New causal component meta-selector diagnostic:
  `event_trade_union_component_meta_selector_scorecap5pool_s3_2026janmay_v1`.
  It chooses among the extended rolling components per ticker/month from the
  previous three OOS months. Formal verifier passes: SPXW WR `54.44%`, PF
  `1.789`, min month `19`; SPY WR `49.73%`, PF `1.505`, min month `54`; QQQ
  WR `47.33%`, PF `1.303`, min month `72`; overall PF `1.442`; `15/15` folds
  clean. Non-strict research-selection audit recognizes selector evidence.
- The causal component meta-selector is not robust enough: curve-health fails
  because QQQ has top5 `85.4%` plus one negative month and SPY has top5
  `85.7%`. A concentration-penalized meta-selector
  (`event_trade_union_component_meta_selector_scorecap5pool_s3_top5penalty_2026janmay_v1`)
  lowers QQQ PF to `1.259`, so that penalty is rejected.
- Added predeclared QQQ static candidate
  `event_static_union_qqq_d80_win80_ptdj80_scoredesc_m8_2025julsep_select_2025oct_2026may_v1`.
  Its Jul-Sep selected / Oct-May test form is causal, but Jan 2026 is negative
  and the component meta-selector still selects `qqq_time`. The earlier robust
  QQQ static result depends on Oct-Dec selection evidence and remains a
  forward-freeze candidate rather than a pre-Jan meta-selected component.

## 2026-06-26

- Confirmed the current event-option production package is live-ready:
  `event_option_live_ready_current_sources_202607`, policy/registry status
  `live_ready_runtime_replay_verified`.
- `validate_event_option_production_package.py --require-live-ready` passes.
  Completed-month Jan-May 2026 gates pass per ticker: SPXW WR `51.37%`, PF
  `1.659`, min month `18`; SPY WR `45.20%`, PF `1.412`, min month `22`; QQQ
  WR `50.00%`, PF `1.517`, min month `25`. Runtime replay exactly matches
  SPXW, SPY, QQQ, and combined expected rows.
- Updated `production_manifest.json` event-option status fields from the stale
  runtime-incomplete labels to `live_ready_runtime_replay_verified`.
- Added `--evidence-end-month` to `freeze_event_option_research_manifest.py`
  and generated
  `event_option_live_ready_current_sources_202607_freeze_manifest` to freeze
  the event-option source family for forward validation from `202607` onward.
  The manifest excludes partial June 2026 evidence and no longer permits weak
  fold modes such as `NO_HISTORY`.
- Added diagnostic
  `event_option_pre2026_literal_gates_spxwvol25_spytopk_qqqbalanced_2026janmay_risk5000`.
  It combines existing causal OOS streams and passes the user's literal Jan-May
  2026 per-ticker gates when positive-month and strict `>18` volume extras are
  disabled: SPXW WR `49.61%`, PF `1.404`, min month `31`; SPY WR `48.05%`,
  PF `1.626`, min month `19`; QQQ WR `52.86%`, PF `1.476`, min month `18`.
  Fold chronology passes, but strict research-selection audit fails without a
  pre-2026 freeze manifest and curve-health fails on concentration/negative
  months, so this is capacity evidence rather than promotion evidence.
- Added frozen source selection to `apply_event_stream_selector.py` via
  `--frozen-select-start-month` and `--frozen-select-end-month`. The selector
  chooses one source from the fixed pre-test window and applies it unchanged to
  every evaluated month.
- Added diagnostic
  `event_option_pre2026_frozen_selectors_literal_gates_2026janmay_risk5000`.
  It freezes SPXW on `vol25phys`, SPY on `topk`, and QQQ on `balanced65` using
  `202510..202512` selection evidence, then evaluates Jan-May 2026. Literal
  user gates pass with weak fold modes disallowed: SPXW WR `49.61%`, PF
  `1.404`, min month `31`; SPY WR `48.05%`, PF `1.626`, min month `19`; QQQ
  WR `52.86%`, PF `1.476`, min month `18`; integrity passes `15/15` folds.
  Non-strict research-selection audit passes with warnings and
  `FROZEN_SELECTED` evidence, but strict audit still fails without a manifest
  frozen before `202601`.
  Curve-health also fails due daily/monthly concentration and negative-month
  flags, so this remains evidence of source capacity rather than a final
  no-snooping promotion.
- Added `scan_event_daily_cap_overlay.py` to test deterministic daily caps over
  precomputed event-option streams using separate selection and test windows.
  Diagnostic `_diagnostics/pre2026_daily_cap_overlay_scan_frozen_sources.csv`
  scans caps `1..12` on the frozen SPXW/SPY/QQQ sources with selection
  `202510..202512` and test `202601..202605`. SPXW has many cap configs
  passing both windows, but QQQ has zero selection-pass caps and SPY's only
  selection-pass cap fails test monthly volume. Therefore daily caps improve
  some Jan-May concentration diagnostics but do not provide multi-ticker
  no-snooping promotion evidence.
- Added `scan_event_source_transfer.py` to recompute source metrics across
  declared select/test windows from an existing stream scan. Diagnostic
  `_diagnostics/source_transfer_2025h2_octdec_to_2026janmay_literal.csv`
  shows only SPXW `vol25phys` passes both Oct-Dec 2025 selection and Jan-May
  2026 test as an individual source; SPY and QQQ require source unions.
- Added `materialize_event_static_union.py` for fixed-priority unions selected
  from a pre-test window. New diagnostic
  `event_static_union_pretest_octdec_selected_scorecap5_2026janmay_risk5000_v2`
  uses SPXW `vol25phys` with score-desc cap `5`, SPY `topk,ptdj35,cons22`,
  and QQQ `d80,win80,ptdj80`. Jan-May 2026 verification passes with weak fold
  modes disallowed: SPXW WR `57.99%`, PF `2.040`, min month `19`; SPY WR
  `50.63%`, PF `1.622`, min month `70`; QQQ WR `47.65%`, PF `1.368`, min
  month `72`. Overall: `1,139` trades, WR `50.22%`, PF `1.540`, PnL
  `+70.934R` / `+$354,669`.
- Curve-health also passes for all three tickers on that v2 diagnostic
  (SPXW top5 `61.8%`, QQQ `58.0%`, SPY `67.6%`; no negative months). The
  strict research-selection audit still fails because no
  `research_selection_manifest.json` was frozen before `202601`, so this is a
  strong pretest diagnostic and forward-freeze candidate, not retroactive
  no-snooping promotion evidence.
- Added long-source static-union diagnostics over the full20 2022-2026 variant
  and consensus streams. The scan outputs are
  `_diagnostics/long_sources_static_union_2025select_2026janmay_{spxw,spy,qqq}.csv`
  plus stability-rank CSVs using 2025-only selection gates, select top5-day
  share `<=0.35`, and the repo score function. The resulting combined artifact
  is `event_static_union_longsrc_2025select_2026janmay_risk5000_v1`.
- That long-source 2025-selected diagnostic passes the user's Jan-May 2026
  formal gates with weak fold modes disallowed: SPXW WR `53.33%`, PF `1.615`,
  min month `36`; SPY WR `52.67%`, PF `1.517`, min month `44`; QQQ WR
  `52.08%`, PF `1.327`, min month `34`. Overall: `649` trades, WR `52.70%`,
  PF `1.490`, PnL `+31.391R` / `+$156,956`; fold integrity passes `41`
  checked rows with no leakage issues.
- Caveat: the long-source diagnostic still fails strict research-selection
  audit without a manifest and curve-health flags SPXW/QQQ for one negative
  month each (QQQ also has a negative-day streak flag). It is stronger
  no-same-month evidence than the H2-only v2 because the source streams cover
  2022-2026 and the selection window is full-year 2025, but it still needs a
  2024->2025 replay or forward freeze before promotion.
- Added 2024H2-selected long-source replay
  `event_static_union_longsrc_2024h2select_2025_2026janmay_risk5000_v1`.
  The fixed unions are selected from `202407..202412` and then evaluated
  unchanged over `202501..202605`: SPXW `d80,d80_front,cons_m3s2c30` cap `1`
  score-desc; SPY `d50ret,d65win,d80_zero` cap `3` score-desc; QQQ
  `d80,d80_front` cap `2` time-asc.
- Formal verification passes the user's full 17-month forward gates with weak
  fold modes disallowed: SPXW WR `49.71%`, PF `1.402`, min month `19`; SPY WR
  `48.24%`, PF `1.373`, min month `23`; QQQ WR `50.70%`, PF `1.358`, min
  month `34`. Overall: `1,868` trades, WR `49.36%`, PF `1.374`, PnL
  `+72.812R` / `+$364,060`; integrity passes `104` checked rows.
- Caveat: this is the strongest long-horizon numeric replay so far, but still
  not final promotion evidence. The strict research-selection audit still lacks
  a pre-2025 manifest, the SPXW 2024H2 selection slice has call-rate `18.75%`,
  and curve-health flags negative months/negative-day streaks despite low
  concentration (top5 shares SPXW `16.5%`, SPY `20.8%`, QQQ `23.2%`).
- Added `apply_event_daily_streak_guard.py`, a causal day-level risk guard that
  pauses a ticker after a configured number of completed losing active days.
  Diagnostic `event_static_union_longsrc_2024h2select_2025_2026janmay_daily_guard_l5p2_risk5000_v1`
  uses `trigger_losses=5`, `pause_days=2`. It still passes the full
  `202501..202605` verifier: SPXW WR `50.29%`, PF `1.451`, min month `18`;
  SPY WR `48.33%`, PF `1.373`, min month `23`; QQQ WR `50.72%`, PF `1.367`,
  min month `32`. Overall PF improves to `1.386`, PnL `+73.452R`.
- The daily guard does not solve curve-health: all tickers still have negative
  months and max negative-day streak `5`. It is a deployable risk overlay
  candidate, not final proof.
- Added forward-only freeze manifests for both the base long-source static
  union and the `l5p2` guarded variant:
  `event_static_union_longsrc_202607_forward_freeze_manifest_v1` and
  `event_static_union_longsrc_daily_guard_l5p2_202607_forward_freeze_manifest_v1`.
  They are valid only for months `>=202607` and must not be used as
  retroactive proof for `202501..202605`.
- Rejected dynamic monthly source-rank selector
  `event_static_union_dynamic_source_rank_longsrc_2025_2026janmay_diag_v1`.
  Ranking individual sources from the prior six months degraded the combined
  result: QQQ PF `1.122`, SPY PF `1.160`, and overall PF `1.185`.
- Audited objective-only 2024H2 static-union scans. SPXW's current
  `d80,d80_front,cons_m3s2c30` score-desc cap `1` row is the top all-period
  all-pass row when `min_score=0.0`; SPY has a simpler top all-pass row
  `d65win,d80_zero` score-desc cap `3`; QQQ's `d80,d80_front` time-asc cap
  `2` is the only all-period all-pass row in the constrained grid but is not
  selected by a simple top-rank rule.
- Materialized the simpler-SPY combined replay
  `event_static_union_longsrc_2024h2select_2025_2026janmay_objpass_simpler_spy_risk5000_v1`.
  It passes the full `202501..202605` verifier: SPXW WR `49.71%`, PF `1.402`,
  min month `19`; SPY WR `49.45%`, PF `1.408`, min month `19`; QQQ WR
  `50.70%`, PF `1.358`, min month `34`. Overall: `1,715` trades, WR
  `49.97%`, PF `1.389`, PnL `+67.639R`.
- Applied the `l5p2` daily guard to that simpler-SPY replay in
  `event_static_union_longsrc_2024h2select_objpass_simpler_spy_daily_guard_l5p2_risk5000_v1`.
  The verifier still passes: SPXW WR `50.29%`, PF `1.451`, min month `18`;
  SPY WR `49.93%`, PF `1.428`, min month `19`; QQQ WR `50.72%`, PF `1.367`,
  min month `32`. Overall: `1,678` trades, WR `50.30%`, PF `1.412`,
  PnL `+69.652R`. Curve-health still fails on negative months/negative-day
  streaks and strict audit still lacks a pre-2025 manifest.
- Added forward-only freeze manifest
  `event_static_union_longsrc_objpass_simpler_spy_daily_guard_l5p2_202607_forward_freeze_manifest_v1`.
  It is valid only for months `>=202607`; it does not certify the retrospective
  `202501..202605` evidence.
- Added `scan_event_static_union_window_stability.py` to stress fixed static
  unions across separate select, validation, and forward windows. Static-only
  QQQ remains weak: the current `d80,d80_front` time-asc cap `2` row passes
  2024H2 and the `202501..202605` replay, but fails 2024H1 selection (WR
  `43.95%`, PF `1.036`, call-rate `17.49%`) and also fails a 2023->2024
  validation audit on 2024 PF/call-rate.
- Exhaustive QQQ long-source static-only grids over cap `1..3`, `time_asc` and
  `score_desc` found no row that passes both 2024H1 and 2024H2 pretests plus
  the forward `202501..202605` gates. The closest pretest-pass row reaches WR
  about `49.56%` but only PF `1.295` and min month `17`.
- Added `scan_event_static_union_backfill.py`, a parallel `--workers` scanner
  for deterministic monthly volume backfill over pretest-selected static
  unions. A focused 24-worker QQQ scan found a pre-2025-selected fix: primary
  `cons_m2s1c45,d65win,d80` score-desc cap `1`, fallback `d80_front`, target
  `18`, max-day `2`, cooldown `0`. It is rank `1` by pretest score among
  `704` pretest-pass rows and rank `1` among `204` all-pass rows; forward
  `202501..202605` QQQ is WR `49.73%`, PF `1.313`, min month `19`.
- Reran the QQQ backfill scan with 32 workers over all 10 fallback sources.
  The deduped scan
  `_diagnostics/qqq_static_union_pre2025_backfill_scan_full10fb_32w_v1.csv`
  evaluated `4,800` tasks (`2,054` pretest-pass, `464` all-pass). The
  no-dedupe scan
  `_diagnostics/qqq_static_union_pre2025_backfill_scan_full10fb_nodedupe_32w_v1.csv`
  evaluated `9,600` tasks (`4,812` pretest-pass, `1,292` all-pass). Both
  confirm the selected QQQ source-set is the top all-pass choice by pretest
  score; alternate source orders tie exactly and do not change forward metrics.
- Materialized the combined diagnostic
  `event_static_union_pre2025_qbackfill_spxwspy_objpass_simpler_spy_2025_2026_risk5000_v1`.
  SPXW/SPY come from the 2024H2 simpler-SPY static replay; QQQ uses the
  pre-2025 monthly backfill above. Formal verifier passes `202501..202605`:
  SPXW WR `49.71%`, PF `1.402`, min `19`; SPY WR `49.45%`, PF `1.408`, min
  `19`; QQQ WR `49.73%`, PF `1.313`, min `19`; overall `1,438` trades, WR
  `49.58%`, PF `1.384`, PnL `+57.226R` / `+$286,130`. Integrity checks `111`
  folds and `21` backfill rows clean.
- Caveats: curve-health still fails on negative months and max negative-day
  streaks. Non-strict research-selection audit passes, but strict audit still
  fails because no `research_selection_manifest.json` existed before `202501`;
  do not backdate one. A forward-only freeze now exists at
  `event_static_union_pre2025_qbackfill_spxwspy_202607_forward_freeze_manifest_v1`
  for validation from `202607` onward.
- Added a stronger H1/H2-2024 QQQ backfill robustness scan:
  `_diagnostics/qqq_static_union_h1h2_backfill_top64_full10fb_targets18_22_32w_v1.csv`.
  The 32-worker scan evaluated `4,500` tasks after source-set dedupe, with
  `1,636` H1/H2 pretest-pass rows and `355` rows passing both pretest and
  forward gates. The selected QQQ row uses primary
  `d65win,d80,d80_zero` score-desc cap `1`, fallback `d80_front`, target `18`,
  max-day `2`, cooldown `15`; H1 select is WR `49.22%`, PF `1.508`, min `20`,
  H2 validation is WR `55.22%`, PF `1.515`, min `21`, and forward
  `202501..202605` is WR `49.86%`, PF `1.361`, min `19`.
- Materialized the improved combined diagnostic
  `event_static_union_h1h2_qbackfill_spxwspy_objpass_simpler_spy_2025_2026_risk5000_v1`.
  Formal verifier passes `202501..202605`: SPXW WR `49.71%`, PF `1.402`, min
  `19`; SPY WR `49.45%`, PF `1.408`, min `19`; QQQ WR `49.86%`, PF `1.361`,
  min `19`; overall `1,435` trades, WR `49.62%`, PF `1.395`, PnL
  `+58.939R` / `+$294,697`. Integrity checks `102` folds and `23` backfill
  rows clean. Non-strict research-selection audit passes, strict still fails
  because no manifest existed before `202501`; do not backdate one. A
  forward-only freeze now exists at
  `event_static_union_h1h2_qbackfill_spxwspy_202607_forward_freeze_manifest_v1`
  for validation from `202607` onward. Curve-health still fails all tickers on
  negative months and max negative-day streaks.
- Rejected the H2-2024-selected daily streak guard
  `event_static_union_pre2025_qbackfill_spxwspy_guard_t4p2_roll5m2_2025_2026_risk5000_v1`.
  The guard was selected only from the H2-2024 diagnostic scan
  `_diagnostics/pre2025_h2_daily_streak_guard_scan_qbackfill_v1.csv`, but the
  forward verifier fails: SPXW min month falls to `16`, and QQQ PF falls to
  `1.290`. Keep the unguarded qbackfill candidate as the current formal-pass
  branch.
- Extended `apply_event_daily_streak_guard.py` with
  `--volume-protect-monthly-target` and added
  `scan_event_daily_streak_guard.py`, a parallel `--workers` scanner for
  causal day-level guard overlays. The rule can spend a pause day when a ticker
  is behind deterministic monthly trade-count pace; it uses only date and
  already selected trades in the current month.
- Rejected volume-protected daily streak guards from H2-2024 selection. The
  32-worker scans
  `_diagnostics/pre2025_h2_daily_streak_guard_volume_protect_scan_32w_v1.csv`
  (`648` tasks) and
  `_diagnostics/pre2025_h2_daily_streak_guard_volume_protect_targets19_21_scan_32w_v1.csv`
  (`972` tasks) found no pretest-pass row with zero curve-health flags or max
  negative-day streak `<=4`. The target-18 guard
  `event_static_union_pre2025_qbackfill_spxwspy_guard_vprotect_roll3le0_p3_t18_2025_2026_risk5000_v1`
  fails forward volume because QQQ min month is `17`. The target-19 guard
  `event_static_union_pre2025_qbackfill_spxwspy_guard_vprotect_t4p2_roll5m2_t19_2025_2026_risk5000_v1`
  restores min month `19`, but forward verifier fails because QQQ PF is
  `1.272`; curve-health still fails all tickers. Keep the unguarded qbackfill
  candidate as the current formal-pass branch.
- Added `walkforward_event_action_return_router.py`, a faster frozen learned
  action router over full-history event-option rows.
- Rejected return-target action router
  `event_action_return_router_full19_2022fit_2024select_2025_2026test_d65d80_v1`:
  SPXW/SPY do not pass 2024 selection; QQQ passes 2024 but fails 2025/2026.
- Rejected win-target action router
  `event_action_win_router_full19_2022fit_2024select_2025_2026test_d65d80_v1`;
  no ticker passes 2024 selection gates.
- Added pairwise router gate scans:
  `_diagnostics/pairwise_2025select_2026_config_gate_scan.csv` and
  `_diagnostics/pairwise_config_per_ticker_2025_2026_gate_scan.csv`.
  No config passes both 2025 validation and 2026 test per ticker.
- Added `scan_event_option_static_profiles.py`, a causal frozen static-profile
  scanner for full-history event-option datasets.
- Inventoried reusable event-option datasets into
  `_diagnostics/event_option_dataset_inventory_20260626.csv`; full19 physics
  covers 2022-01-03 through 2026-06-22 with 695k rows.
- Rejected compact full19 d80/d65 static scans selected on 2024:
  `event_option_static_profiles_full19_2022fit_2024select_2025_2026test_d80_small_v1`
  and
  `event_option_static_profiles_full19_2022fit_2024select_2025_2026test_d65_small_v1`
  have zero SPXW/SPY/QQQ profiles passing exact select gates.
- Added relaxed d80 near-miss diagnostic
  `event_option_static_profiles_full19_2022fit_2024select_2025_2026test_d80_small_relaxed_diag_v1`;
  2024-selected profiles degrade below PF 1.16 in 2025 and below PF 0.92 in
  2026 for all three tickers.
- Resumed partial
  `event_option_gate_full19_d80_win_core_state_val12_2025test_v1`. It now has
  all `12` SPXW folds and `7` SPY folds before timeout. SPXW still fails 2025
  (WR below target, PF `1.219`, min month `0`); SPY is already invalid through
  July due repeated validation abstentions and one losing deployed month. It
  remains incomplete and should not be cited as completed evidence.
- Rejected strict structural profile selector
  `level_stability_nested_structural_profiles_risk5000_strict_wr45_pf13_m18_2026janmay_v1`;
  folds are clean, but SPX/SPY PF and WR collapse and QQQ abstains.
- Added H2-2025 -> Jan-May-2026 structural stability diagnostic
  `level_stability_option_structural_profiles_risk5000_h2_to_2026janmay_wr45_pf13_m18_v1`.
  Only SPY has a profile passing both train and test gates; SPX and QQQ have
  zero causal train+test pass profiles.
- Added non-causal Jan-May oracle capacity diagnostic
  `level_stability_option_structural_profiles_risk5000_janmay_oracle_capacity_diag_v1`.
  Gate-passing profiles exist for all tickers when Jan-May thresholds are used,
  confirming the bottleneck is causal profile/regime selection, not raw profile
  expressiveness.
- Added partial-June forward replay
  `level_stability_option_structural_profiles_risk5000_janmay_oracle_forward_202606_partial_v1`;
  the oracle profiles lack H2-2025 validation, SPX fails June partial, SPY has
  no June trades, and QQQ has only 7 June trades.
- Added `--option-exit-mode fixed|trailing` to
  `build_event_option_dataset.py`. The default remains the existing fixed
  TP/SL label; trailing mode supports hard stop, trail activation/drawdown, and
  emergency take profit using option OHLC paths.
- Built
  `event_option_dataset_spxw_spy_qqq_trailing_liveexit_2024_2026_v1`
  and rejected its `d80 return` walk-forward gates over 202507-202606. The
  broad run is fold-clean but PF is below 0.90 for every ticker; the stricter
  run improves SPY WR but still misses PF and collapses monthly volume.
- Hardened `apply_event_daily_regime_gate.py` and
  `apply_event_daily_router_confidence_gate.py` with
  `--fail-closed-on-select-fail`, so a month/ticker with no threshold passing
  its own causal selection gates abstains instead of using the least-bad
  threshold.
- Reproduced the near-miss pairwise stream
  `lgbm_soft_diff_abs_mt0_me0p0` across OOS 2024-2026 and rejected daily
  regime overlays. The best strict 2025-2026 overlays still have min monthly
  trades `0`; SPY remains below PF 1.3 (`1.129` for 2-month selection,
  `1.053` for 3-month selection).
- Replayed daily-source routers with 2022/2024 history and rejected strict
  confidence gates with deterministic `d80` backfill. With fail-closed
  selection, only a few folds pass; all selection windows have min monthly
  trades `0`, and SPXW fails even on selected folds.
- Added `scan_event_static_union_configs.py` to scan fixed-priority unions of
  precomputed OOS event-option streams. Configs are selected on a declared
  window and then reported on forward windows without re-ranking the test
  period.
- Static-union scans over the full20 variant streams are negative. A 2024
  singleton selector finds no source passing 2024 gates. A 2025 selector over
  near-miss pairs/triples also finds no validated config passing 2026. Oracle
  2026 configs exist inside the grid (for example QQQ `d65win,d80` PF `1.503`,
  SPXW `d65ret,d80` PF `1.414`, SPY `d65win,d80` PF `1.418`), but their 2025
  evidence is too weak, so they remain non-promotable capacity diagnostics.
- Built rolling monthly trade-union config-selector diagnostic
  `event_trade_union_config_selector_full20_2026_numeric_pass_diag_v1` from
  the best small-grid per-ticker selector windows found for 2026. The combined
  Jan-Jun 2026 verifier passes SPXW/SPY/QQQ gates with clean folds: SPXW WR
  `51.99%`, PF `1.366`, min month `30`; SPY WR `51.44%`, PF `1.336`, min
  month `19`; QQQ WR `53.09%`, PF `1.435`, min month `49`; fold audit
  `18/18` clean. This is not promoted because the per-ticker `select_months`
  choices were discovered after scanning 2026 and the same family fails
  2025/full-range PF evidence.
- Added `apply_event_trade_union_window_meta_selector.py`, a causal
  meta-selector over precomputed rolling trade-union config selectors. It can
  choose selector windows monthly or freeze the window choice for a deployment
  period using only earlier OOS months.
- Generated 2024-2026 small-grid rolling selector replays for SPXW/SPY/QQQ
  with `select_months` in `{3,6,12}`. The frozen 2026 meta-selector
  `event_trade_union_window_meta_selector_full20_2026_frozen_2025select_s3s6s12_m18relax_v1`
  selects SPXW `s12`, SPY `s12`, and QQQ `s6` from 2025 evidence and passes
  Jan-Jun 2026 gates with verifier-clean folds: SPXW WR `51.99%`, PF `1.366`,
  min month `30`; SPY WR `51.44%`, PF `1.336`, min month `19`; QQQ WR
  `53.65%`, PF `1.373`, min month `49`.
- The same frozen meta-selector rule selected from 2024 fails 2025
  (`event_trade_union_window_meta_selector_full20_2025_frozen_2024select_s3s6s12_m18relax_v1`):
  SPXW WR `41.06%`, PF `0.837`, min month `0`; SPY WR `43.29%`, PF `0.967`;
  QQQ PF `1.183`, min month `0`. Keep the 2026 pass as a strong forward
  candidate, not as a fully promoted no-snooping production policy.
- Added `scan_event_trade_union_window_meta_rules.py` to scan meta-selection
  rules with a validation period and separate test period. The first grid
  `event_trade_union_window_meta_rule_scan_full20_2025val_2026test_s3s6s12_v1`
  scanned `432` rules: `0` pass 2025 validation selected from prior months,
  `41` pass Jan-Jun 2026, and `0` pass both. The best rule by 2025 near-miss
  score does pass 2026 with clean verifier folds, but validation failure keeps
  it non-final.
- Added diagnostics
  `_diagnostics/full20_variant_stream_metrics_2024_2026_scan.csv` and
  `_diagnostics/all6_s12_vs_small_s12_2024_2026_metrics.csv`. No individual
  full20 source clears 2025 SPXW/SPY/QQQ gates; expanding the rolling selector
  to all six sources at `s12` does not fix 2025 and worsens SPXW/SPY validation
  evidence.
- Ran static-profile follow-ups on the wide 2024-2026 physics dataset. A broad
  2024-fit/2025-select scan was stopped after SPXW completed with zero
  select-pass profiles. A reduced SPY/QQQ d80 smoke
  `event_option_static_profiles_wide2024fit_2025select_2026test_d80_smoke_spyqqq_v1`
  also found zero 2025 select-pass profiles.
- Completed direct LightGBM event-option diagnostic
  `event_option_gate_full20_physics_pooled_2025full_d80_win_fullgrid_call05_minmonth18_v1`.
  It is rejected: overall PF is only `1.024`; SPXW loses money with WR
  `44.94%`, PF `0.873`, min month `0`; SPY PF is `1.142`; QQQ PF is `1.031`
  with min month `3`.
- Added `scan_event_stream_trade_filters.py` for causal filters over
  precomputed OOS event-option streams and optimized the no-cap/no-cooldown
  path. The tiny and action-window scans are negative:
  `event_stream_trade_filter_scan_full20_2024select_2025_2026test_tiny_v1`
  scans `252` configs with `0` select-pass and `0` 2025-pass configs, while
  `event_stream_trade_filter_scan_full20_2024select_2025_2026test_action_windows_v1`
  scans `2205` configs with `0` select-pass and `0` 2025-pass configs. The
  few 2026-only passes are low-volume or one-sided diagnostics, not promotion
  evidence.

## 2026-06-25

- Hardened `audit_event_option_research_selection.py` to expand
  `monthly_volume_backfill_config.csv` rows into auditable primary/fallback
  source rows and recursively inspect one nested selected source.
- Re-ran strict audits for the latest Jan-Jun event-option diagnostics. Trading
  gates pass, but strict research-selection proof still fails without a
  pre-evaluation manifest.
- Ran `event_option_gate_full20_d65_win_val12_2026janjun_v1`; all 2026 folds
  abstained because 12-month pre-2026 validation failed the PF/WR/month gates.
- Added diagnostic scans of generated event-option streams:
  `stream_2025_2026_scan.csv` and `stream_pre2026_short_window_scan.csv`.
  No individual stream currently clears both pre-2026 evidence and 2026 strict
  SPXW/SPY/QQQ gates.
- Fixed `market_state_expert_router.py` so `active_win` uses a classifier
  rather than a regressor. Fixed `verify_event_option_result.py` so standard
  component trade files such as `monthly_volume_backfill_trades.csv` can be
  verified without copying them to `combined_trades.csv`.
- Ran market-state router diagnostics:
  `event_option_market_state_router_win_active_abstain_small_202501_202512_select_2026test_v1`
  found no direct volume-complete config that clears the exact user gates.
- Built exploratory market-state backfill
  `event_option_market_state_returnk1_backfill_wink2_m19_2026janjun_v1`,
  which clears Jan-Jun 2026 ticker gates numerically, but the same fixed policy
  fails 2025 in `event_option_market_state_returnk1_backfill_wink2_m19_2025test_v1`.
  Keep it diagnostic/forward-only.
- Reran the small market-state grid for 2025 with pre-2025 selection:
  `event_option_market_state_router_win_active_abstain_small_202401_202412_select_2025test_v1`.
  No direct config passes the requested gates.
- Added/updated diagnostics:
  `_diagnostics/multi_ticker_package_2025_2026_scan.csv`,
  `_diagnostics/market_state_pair_backfill_common_m19_md8_2025_select_2026_scan.csv`,
  and `_diagnostics/market_state_pair_backfill_top8_m19_md8_2025_select_2026_scan.csv`.
  No current package or market-state backfill pair has both pre-2026 evidence
  and 2026 gate performance.
- Rebuilt the locked SPXW/SPY/QQQ candidate with 2025H2 included:
  `event_option_candidate_spxw_spy_qqq_unionmeta_2025h2_2026jun_with2025h2_risk5000`.
  A same-side delta ranker speed run
  `event_option_delta_ranker_rawhist2024_same_side_2025h2_2026jun_candidate_with2025h2_risk5000_n120_combined`
  kept fold integrity clean, but failed validation. 2025H2 was WR 42.0%,
  PF 0.992, PnL -$3.8k; Jan-Jun 2026 only passed SPXW, while SPY and QQQ
  missed WR/PF and QQQ missed monthly volume.
- Added `_diagnostics/focused_2025h2_2026_stream_gate_scan.csv`; no scanned
  stream passed both 2025H2 validation and Jan-Jun 2026 test gates under
  WR >= 45%, PF >= 1.3, PnL > 0, and min 18 trades/month.
- Extended `verify_event_option_result.py` so recent component artifacts such
  as `intraday_circuit_trades.csv`, `daily_source_router_trades.csv`, and
  `event_option_profile_trades.csv` can be verified with their native fold
  files.
- Rejected the TDVP nested profile selector
  `event_option_profile_selector_narrow_tdvp_13ticker_spyqqq_2025h2_2026jun_n120`
  and the full20 202501-history daily source-router replays for SPY/QQQ.
- Added QQQ diagnostic
  `event_option_qqq_full20_d80_intraday_side_circuit_2025hist_2025h2_2026jun_risk5000`.
  It passes Jan-Jun 2026 gates with clean folds, but fails the full
  202507-202606 verifier on PF (`1.277` vs required `1.3`) and does not pass
  2025H2 as validation evidence.

## 2026-06-18

- Verified `run_daily_production_pipeline.ps1 -DeployMonth 202606 -Workers 32 -SkipSmoke`.
- Regenerated production artifacts and `production_manifest.json`.
- Changed the production manifest to use repo-relative paths.
- Updated `push_models.ps1` to upload only production artifacts by default,
  upload `production_manifest.json` when present, and require
  `-IncludeLegacyFallback` for legacy JEPA 180m/OptionValue artifacts.
- Removed the legacy `--model-dir` argument from `systemd/ai_bot.service`.
- Added explicit PF/WR/monthly-volume/side gates and walk-forward integrity summaries to the nested structural result combiner.
- Added `research_papers/JEPA/JEPA_PRODUCTION_REPORT.tex` and compiled the PDF.
- Archived historical generated JEPA result Markdown as non-production evidence.
- Removed obsolete smoke/debug result folders and the unused `neural/backtest` regime verifier.
- Rewrote `DISCOVERIES.md` as a current decision log.

## 2026-06-17

- Promoted the production live path to level-stability entry signal plus nested structural option profiles.
- Added `fit_production_level_stability_signal.py`.
- Added `level_stability_live.py`.
- Added `run_daily_production_pipeline.ps1`.
- Added `run_pipeline.ps1 -DailyProduction`.
- Updated `bots/tradingbot_wrapper_jepa.py` so the legacy JEPA 180m model is fallback-only.
- Updated systemd units to require production signal/profile JSON artifacts.
- Updated `push_models.ps1` to upload `jepa_production_level_stability`.
- Replaced stale README/PLAN/SUMMARY docs with current production notes.
- Removed old Alpha/Temporal JEPA wrappers and one-off diagnostics that are no longer part of the production or validated research workflow.

## Current Production Artifacts

```text
neural/models/jepa/jepa_production_level_stability/level_stability_signal.json
neural/models/jepa/jepa_production_structural_options/structural_option_profiles.json
neural/models/jepa/production_manifest.json
```
