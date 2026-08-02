# MULTISCALE_LEVEL_INTERACTION_SEQUENCE_V1 — Phase-0 audit contract

**Status:** `BLOCKED_PREDECLARATION`

**Phase:** 0, documentation and source audit only

**Scope:** non-executable; no data values, models, labels, payoff/outcomes, API, network, or production access

**HEAD:** `origin/main=c942bde8601015383f11f74a4fb116bf2d007c87`

**Branch:** `main`

This artifact records the Phase-0 audit for the single user-authorized new
family. It is not the Phase-1 scientific predeclaration. Phase 1 must be
separately committed before any feature build, label access, model fit, payoff
read, or outer-period claim.

## Repository and source audit

- Before this artifact, tracked/staged changes were zero. The worktree had
  `6,795` untracked leaf entries from `git status --porcelain=v1 -uall`.
  Their NUL-stream SHA-256 is
  `117a8bb73ad3c8e7372681b7f967257b81f13b8a6d2d06871fe766ed78e7e942`.
  All are preserved.
- Read-only `D:/ThetaData` enumeration: `360,804` files, `84,618` directories,
  `274,598,759,093` bytes (`255.740 GiB`). By extension: parquet `229,349`
  files / `130.850 GiB`; ndjson `1,364` / `69.410 GiB`; json `105,986` /
  `55.090 GiB`. No full-content hash was computed; only targeted hashes below
  are authoritative.
- `data_options`: `152,918` files, `122.753 GiB`, 22 symbols. Coverage is
  `2022-01-03..2026-07-24`. QQQ and SPY each have Greeks/IV/OHLC `2,191`
  files over `1,136` dates and OI `2,205` files over `1,143` dates. SPXW has
  `2,255` files for each of Greeks/IV/OHLC/OI over `1,143` dates.
- QQQ/SPXW/SPY underlying each have `1,143` daily parquet files. Their schema
  is OHLC plus `tick_count`; there is no true underlying volume or VWAP.
  Option OHLC has volume/VWAP. These must not be conflated. OI is prior-close /
  daily, not 1-minute.
- First-order Greeks expose delta/theta/vega/rho/epsilon/lambda/IV/bid/ask and
  native/underlying timestamps, but no direct gamma. IV, OHLC, and OI are
  separate schemas. Stored timezone is not embedded; project documents call it
  ET, but parity has not been proven.
- `CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5` is incomplete and forbidden:
  `1,364/1,504` captures valid, `140` errors, `167,881,230` footer rows;
  contract SHA `210ea579...205a6`; errors SHA `3f575746...fbc3d3`.
  `data_training_input` is inadmissible and local historical/live parity is
  `BLOCKED`.

### Overlap and provenance constraints

- QDYN path counts: V1 `1,949`, V1R1 `518`, V1R1R1 `9,833`. V1R1 is contained
  in both V1 and V1R1R1; V1 is contained in V1R1R1. Duplicate tick payloads
  were verified by SHA `2bd33561...be2d9`.
- Native calendar manifest SHA is `e68ed58f...5b217`; parity remains blocked.
- H-IBQDYN manifest SHA is `05522061...7f0ec`; parity remains blocked.
- V4 retry original seal SHA is `a18e0864...758f`; offline reseal SHA is
  `99a33f56...7c169`, with five usable pairs, `3,432` shared rows and no
  network access. The original and reseal are distinct provenance artifacts.

## Phase-0 novelty decision

An ordered sequence alone is not novel: Phys-TD and price-only sequence families
already exist and are closed. The only defensible Phase-1 novelty is a joint
multiscale tensor whose tokens retain explicit level identity over a fixed full
level universe.

The old wall contract contains **53 minimum levels**: five Greek levels, eight
D0 IB/Fibonacci levels, and eight levels for each of D1–D5. The user-requested
CALL/PUT wall union must be frozen exactly in Phase 1; Phase 0 must not silently
choose a subset. This is a requirement/gap, not a final predeclaration.

### TCR-VIS assessment

Same-trajectory TCR/NCE is scientifically relevant: it cancels a session/level
static shortcut and is distinct from VISReg-only and factorized-JEPA controls.
However, the market representation is actionless. CALL/PUT, delta and hold are
payoff actions, not causes that change the next market state. TCR may be the one
sequence sensitivity only if Phase 1 freezes same-trajectory candidates,
causal-prefix-only temporal mean, temperature `0.12`, VIS weight `0.04`, 24
projections, RNG seed, no cross-fold trajectories, and the same economic gates.
It cannot rescue a failed primary tree. Existing batch-centered VISReg is not
equivalent. No TCR implementation or training is authorized in Phase 0.

## Leakage and execution audit

The following constraints must be frozen before Phase 1:

1. Completed-bar primitives exist, but the required new `12x5m` and `8x15m`
   level builders are absent.
2. Current IB is `09:30–10:29` and must be unavailable before `10:30`.
3. The old builder has only six Fibonacci extensions; the full required level
   set and contract are not yet frozen.
4. Moving walls require exact as-of identity per token; no floor join, silent
   deduplication, nearest, or inferred timestamp is allowed.
5. Existing executable-quote labels are 30m/stop/trailing labels and do not
   contain the exact fixed 24 payoff actions required by the new family; they
   cannot be reused without a separately frozen payoff contract.
6. The Phase-1 event key must include ticker, date, decision timestamp,
   expiration, right, strike, delta, entry-quote timestamp, and exit-quote
   timestamp.
7. The chronological `reject_while_open` primitive exists and must remain the
   scheduler contract.
8. The monthly feature → freeze → outer barrier exists. An independent auditor
   must reimplement the computation and may not import the evaluator.

## Terminal claim policy

- All historical dates through `2026-07-24` are `SEEN_DEVELOPMENT`; no
  historical outer period remains untouched for this family. Dates after the
  documented coverage are future/uncaptured, not a historical reserve.
- A favorable historical result may only be called
  `DEVELOPMENT_PASS_REQUIRES_SHADOW`.
- First promotion requires a frozen policy before a future complete calendar
  month, then a source/live shadow and parity audit. No historical result is
  live-ready.
- The user’s explicit request narrowly supersedes the prior no-active-family
  closure only for writing this Phase-0 contract. It does not reopen prior
  outcomes or supersede causal, parity, shadow, payoff, or production closures.
- `services/`, `bots/`, `systemd/`, VPS, web templates, and `README_PATCH.md`
  remain untouched. No API, model, outcome, or network value was read.

## Prior-family matrix

The machine-readable companion `results/_diagnostics/multiscale_level_interaction_sequence_v1_phase0_audit/INVENTORY.json`
contains one explicit object for every registry family name (34 rows). Metrics
are ordered QQQ/SPXW/SPY unless stated otherwise; unavailable metrics are JSON
`null` and are not inferred.

| Registry family | Hypothesis / source and features | Labels/payoff and validation | Metrics / failure | Terminal status | Evidence paths |
|---|---|---|---|---|---|
| Baseline executable nested y objetivos return/win | Generic executable-quote 0DTE controls; return versus win objectives, early cadence/regime variants. | Ask→bid, 30–180m; chronological inner selection and 2026 Jan–May tests. | QQQ/SPXW/SPY PF `0.984/0.832/0.919`, WR `44.68/42.99/43.90%`; early 5m SPXW PF `1.109`; no stable monthly gate. | `FAILED_ECONOMIC` | `EXACT_OBJECTIVE_RETURN_VS_WIN_PREDECLARATION_V1.md`; `EARLY_CAUSAL_*`; `SUMMARY-update.md` |
| Early cadence/directional/regime | 1m early snapshots, backward spot momentum, IV-skew/spread/abs-return/IB gates. | Same executable labels; nested Jan–May 2026, inner-only gate selection. | 1m directional 60 trades, WR `36.67%`, PF `0.976`; isolated regime cells only; no stability. | `FAILED_ECONOMIC` | `EARLY_CAUSAL_CADENCE_1M_PREDECLARATION_V2.md`; `EARLY_CAUSAL_DIRECTIONAL_NESTED_1M_PREDECLARATION_V1.md`; `REGIME_GATE_ABLATION_PREDECLARATION_V1.md` |
| Pairwise P1 y magnitude/physics variants | CALL/PUT side and opportunity differences on executable quote data. | Ask→bid labels, 2022–2025; nested grids and fixed scheduler. | P1 positive 57/99, median +0.004, `p=0.117`; magnitude PF `0.430`; physics skip QQQ/SPY PF `0.409/0.810`. | `FAILED_ECONOMIC` | `PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_PREDECLARATION_V1.md`; `PAIRWISE_MAGNITUDE_WEIGHTED_SIDE_V1.md`; `PAIRWISE_SIDE_PHYSICS_SKIP_V1.md` |
| Wall interaction executable V1/V1R1 | Magnet/rejection/acceptance at Greek/IB/Fibonacci walls. | Executable ask→bid, 30–180m; 2024–2025 replay. | V1 PF `0.865/0.832/0.899`; V1R1 `0.910/0.845/1.008`; correction still lacks frequency/stability. | `FAILED_ECONOMIC` | `WALL_INTERACTION_EXECQUOTE_PREDECLARATION_V1.md`; `WALL_INTERACTION_EXECQUOTE_V1R1_REJECTION_SEMANTICS.md` |
| H-FLOW1 | Signed flow/count/close-notional near a wall. | Physical AUC F0/F1, 2024–2025; no payoff after gate. | 4/24 improvements, median ΔAUC `-0.029209`, `p=0.984375`. | `CLOSED` | `WALL_SURFACE_FLOW_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md` |
| H-IVSURF1 | Local fixed-strike IV deformation at 1/5/15m. | LR primary/LGBM sensitivity, physical 2024–2025 folds. | LR 12/24, ΔAUC `-0.001203`, `p=0.890625`; LGBM 9/24, `-0.005822`. | `CLOSED` | `WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md` |
| H-QSIZE1R1 | NBBO size/imbalance/depth snapshot. | Physical F0/F1, 2024–2025; no payoff. | LR 6/24, median `-0.014823`; LGBM 5/24, `-0.020959`. | `CLOSED` | `WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md`; `WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1R1_QUALITY_REPAIR_PREDECLARATION.md` |
| H-QDYN1R1R1 | Tick replenishment/withdrawal at exact Greek walls. | Source/data gate before labels or payoff. | Distinctness fails in 18 SPXW cells; no economic metrics. | `FAILED_CAUSALITY` | `WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1_PREDECLARATION.md`; `WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1R1_DATA_GATE_CLOSURE.md` |
| H-IBQDYN1 | Tick pressure on eight completed IB/Fibonacci levels. | Physical F0/F1, then economic replay only if physical PASS. | LR 7/24, ΔAUC `-0.004032`; LGBM 8/24, `-0.005847`; no PF/WR. | `CLOSED` | `H_IBQDYN1_FEASIBILITY_PREDECLARATION.md`; `H_IBQDYN1_ECONOMIC_TRANSLATION_PREDECLARATION.md` |
| H-GREEK2WALL direct | Native higher Greeks/direct OI. | 12-session source preflight; no labels/payoff. | HTTP 403 STANDARD entitlement; no data values. | `BLOCKED_DATA` | `H_GREEK2WALL_DIRECT_ALL_V1_FEASIBILITY_PREDECLARATION.md`; `H_GREEK2WALL_DIRECT_ALL_V1_FEASIBILITY_CLOSURE.md` |
| EXISTING_DATA_EXECUTABLE_UTILITY_V1 | Existing causal union with hurdle/Huber heads. | Nested 2024–2025 executable ask→bid. | E1 144/144 abstain; E0 only 4/144 cells trade; pooled PF `1.464809` but min month 0. | `FAILED_ECONOMIC` | `EXISTING_DATA_EXECUTABLE_UTILITY_V1_PREDECLARATION.md` |
| CROSS_MARKET_TRANSMISSION_V1 | Beta-neutral/lead-lag/basis transmission. | Exact 1m 30-bar features; source gate before outcomes. | Half-day post-close paths make statistics undefined; no output. | `FAILED_CAUSALITY` | `CROSS_MARKET_TRANSMISSION_V1_PREDECLARATION.md`; `CROSS_MARKET_TRANSMISSION_V1_DATA_GATE_CLOSURE.md` |
| CROSS_MARKET_TRANSMISSION_V1R1 | Same hypothesis with calendar-only half-day exclusion. | Repaired 2022–2025 source gate. | Normal-session constant return makes lead/lag undefined; no epsilon/removal. | `BLOCKED_DATA` | `CROSS_MARKET_TRANSMISSION_V1R1_HALF_DAY_REPAIR.md`; `CROSS_MARKET_TRANSMISSION_V1R1_DATA_GATE_CLOSURE.md` |
| H-TPOVALUE1 | TPO/POC/VAH/VAL migration/value location. | Quantile model, causal 2023 development. | First SPXW 2023-04 cell 0/42 grids; near-miss PF `0.921718`, −1.831R. | `FAILED_ECONOMIC` | `H_TPOVALUE1_EXECUTABLE_PREDECLARATION.md` |
| KING-GEX-SLOPE1 | Net-GEX sign plus 45m slope. | Fixed K0/K1, 2023. | K1 PF `0.804`, WR `42.22%`, 2/36 cells. | `FAILED_ECONOMIC` | `KING_GEX_SLOPE1_EXECUTABLE_PREDECLARATION.md` |
| KING-GEX-EXIT1 | Fixed stops/trails/horizons. | 32 policy replay, 2023. | 0/32 eligible; none PF≥1.0. | `FAILED_ECONOMIC` | `KING_GEX_EXIT1_EXECUTABLE_PREDECLARATION.md` |
| KING-GEX-MANAGE30-V1 | Causal +30m management choice over 17 exits. | M0/M1 LightGBM Huber, 72 folds, 2023. | M0/M1 PF `0.905/0.901`, WR `38.90/39.08%`; outer closed. | `FAILED_ECONOMIC` | `KING_GEX_MANAGE30_V1_PREDECLARATION.md`; `KING_GEX_MANAGE30_V1_DATA_GATE_CLARIFICATION_V1R2.md` |
| EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1 | Compact long-option 0DTE selector. | Ask→bid 30–180m nested 2026. | PF `0.794–0.804`, WR `35.5–39.7%`; no stability. | `FAILED_ECONOMIC` | `results/_diagnostics/event_option_execquote_nested_compact_v1_202601_202606/` |
| DIRECTIONAL_GLOBEX_CROSS_ASSET_V1 y adaptaciones | Seven continuous Globex futures plus cash direction. | 2025 development, Jan–Jul 2026 outer/MTD; no broker-grade futures parity. | 2025 PF `1.200/1.206/1.210`; 2026 PF `0.873/0.899/0.888`; V2/V3/V4 also fail stability. | `FAILED_ECONOMIC` | `DIRECTIONAL_GLOBEX_CROSS_ASSET_V1_PREDECLARATION.md`; `DIRECTIONAL_GLOBEX_ONLINE_LINEAR_V2_PREDECLARATION.md`; `DIRECTIONAL_GLOBEX_ONLINE_EXPERT_V3_PREDECLARATION.md`; `DIRECTIONAL_GLOBEX_META_HEDGE_V4_PREDECLARATION.md` |
| Payoffs alternativos long-vol/short-premium/IB | Dual-leg long-vol, short-premium, direct IB/Fib. | Exact executable legs where possible; 2025 or source gate. | Long-vol PF `0.629/0.661/0.605`; short-premium unresolved exits; IB PF `0.779/0.785/0.819`. | `CLOSED` | `DUAL_LEG_EVENT_VOLATILITY_V1_PREDECLARATION.md`; `SHORT_PREMIUM_DEFINED_RISK_V1_CLOSURE.md`; `DIRECTIONAL_IB_BREAKOUT_FADE_V1_CLOSURE.md` |
| CROSS_SESSION_RELATIVE_VALUE_V1 | QQQ-SPY reversal versus SPY/SPXW anchor. | Underlying-only 180m/2bps, 2022–2023. | 496 trades, WR `41.532%`, PF `0.627276`, −2,349.329bps, 5/24 positive. | `FAILED_ECONOMIC` | `CROSS_SESSION_RELATIVE_VALUE_V1_PREDECLARATION.md`; `CROSS_SESSION_RELATIVE_VALUE_V1_CLOSURE.md` |
| OPENING_RELATIVE_MOMENTUM_V1 | QQQ-SPY cash impulse continuation. | 10:36→13:36/180m/2bps, 2022–2023. | 497 trades, WR `50.905%`, PF `0.831462`, −927.689bps, 7/24 positive. | `FAILED_ECONOMIC` | `OPENING_RELATIVE_MOMENTUM_V1_PREDECLARATION.md`; `OPENING_RELATIVE_MOMENTUM_V1_CLOSURE.md` |
| OPTION_PARITY_PRESSURE_V1 | Same-strike CALL/PUT synthetic-forward change. | Deterministic 2023, ask→bid 180m/1bp. | 730 trades, WR `48.630%`, PF `0.874751`, −1,689.310bps; 10/36 cells. | `FAILED_ECONOMIC` | `OPTION_PARITY_PRESSURE_V1_PREDECLARATION.md`; `OPTION_PARITY_PRESSURE_V1_CLOSURE.md` |
| EXACT_EXPIRY_OI_DELTA_V1 | Same-contract OI change before expiry. | Inventory-only 2023–2025; no values/outcomes. | 156 pairs, min 4 events/month. | `FAILED_FREQUENCY` | `EXACT_EXPIRY_OI_DELTA_V1_FEASIBILITY_CLOSURE.md` |
| CALENDAR_RISK_REVERSAL_PRESSURE_V1 | Front-minus-back 25d RR change. | Deterministic ask→bid development 2023. | Pooled PF `1.058294`, +729.690bps, 12/36; QQQ/SPXW/SPY PF `1.173476/0.912372/1.072835`, min 19. | `FAILED_ECONOMIC` | `CALENDAR_RISK_REVERSAL_PRESSURE_V1_PREDECLARATION.md`; `CALENDAR_RISK_REVERSAL_PRESSURE_V1_CLOSURE.md` |
| CROSS_VENUE_CALENDAR_RR_LEADER_V1/V3 | Fixed QQQ←QQQ, SPY←SPY, SPXW←SPY mapping; fixed/monthly sign. | V1 outer 2024; V3 development 2024 and outer 2025. | V1 PF `0.866939/0.698912/0.693382`; V3 outer PF `0.655469/1.035567/1.039777`; stability fails. | `FAILED_ECONOMIC` | `CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md`; `CROSS_VENUE_CALENDAR_RR_LEADER_V3_MONTHLY_ORIENTATION_PREDECLARATION.md` |
| CROSS_VENUE_CALENDAR_RR_LEADER_V4/V4R1/V4R2 | Pooled 29-feature logistic with retries/four exclusions. | V4 development 2025; V4R2 outer 2026. | V4 dev PF `1.204351/1.247945/1.346342`; V4R2 outer PF `0.969729/0.950957/0.955718`, positive months `2/2/2`. | `FAILED_ECONOMIC` | `CROSS_VENUE_CALENDAR_RR_LEADER_V4_FULL_HISTORY_LOGISTIC_PREDECLARATION.md`; `CROSS_VENUE_CALENDAR_RR_LEADER_V4R2_OUTER_2026_FAILURE.md` |
| CROSS_VENUE post-V4 cash-only | Cash summaries/spot/cross-cash/shallow trees/raw 35×1m. | 2024–2025 development comparisons; no 2026. | No candidate passes all six ticker-year blocks. | `FAILED_ECONOMIC` | `CROSS_VENUE_CALENDAR_RR_POST_V4_CASH_ONLY_DIAGNOSTIC.md` |
| CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5 | Executed OPRA prints paired to strictly prior NBBO. | Source gate 2023–2025 before features/outcomes. | 1,364/1,504 valid, 140 invalid/duplicate; no PF/WR. | `BLOCKED_DATA` | `CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_PREDECLARATION.md`; `CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_SOURCE_CAPTURE_GATE_FAILURE.md` |
| EXTERNAL_OPRA_SOURCE_INTAKE | Historical/live OPRA tape admission. | Credential/shadow/source gate only. | No endpoint, capture, feature, model or outcome. | `CLOSED` | `EXTERNAL_OPRA_SOURCE_INTAKE_PREDECLARATION_20260726.md`; `EXTERNAL_OPRA_SOURCE_INTAKE_CLOSED_NO_EXECUTION_20260726.md` |
| EXECUTABLE_CONTEXTUAL_BANDIT_GROUPDRO_V1 | Pooled 12-action Q-network with ticker-month GroupDRO. | Executable quote, but runner intentionally never executed. | No prediction or metric. | `CLOSED` | `EXECUTABLE_CONTEXTUAL_BANDIT_GROUPDRO_V1_PREDECLARATION.md` |
| EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1 | Exhaustive monthly LightGBM CALL/PUT overlay search. | 1,128,960 logical configs/fold; six-month select then Jan–Jun 2026 test. | PF `0.584706/0.844375/1.083921`; positive months `1/3/2`; 370 trades, audit exact. | `FAILED_ECONOMIC` | `EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_PREDECLARATION.md`; `EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_FAILURE.md` |
| CROSS_VENUE_CALENDAR_RR_LEADER_V6 | Fixed HistGradientBoosting depth 2 over V4 features. | No implementation/prediction/metric. | Not run. | `CLOSED` | `CROSS_VENUE_CALENDAR_RR_LEADER_V6_SHALLOW_HISTGB_PREDECLARATION.md` |
| CROSS_VENUE_CALENDAR_RR_LEADER_V7 | Rolling-12 monthly pooled logistic. | Monthly refit, Jan–Jul 2026 development/MTD. | PF `0.812462/1.079783/1.031988`; positive months `1/2/3`; audit PASS, economics fail. | `FAILED_ECONOMIC` | `CROSS_VENUE_CALENDAR_RR_LEADER_V7_ROLLING12_MONTHLY_LOGISTIC_PREDECLARATION.md`; `CROSS_VENUE_CALENDAR_RR_LEADER_V7_ROLLING12_MONTHLY_LOGISTIC_FAILURE.md` |

## Period ledger

| Period | Evidence state |
|---|---|
| 2022-01..2023-12 | Underlying outcomes opened for Cross-Session Relative Value and Opening Relative Momentum; 2023 option parity, Calendar-RR, TPO and King development also opened. |
| 2022-08..2025-12 | Wall-state/interaction, H-FLOW, H-IVSURF, H-QSIZE, H-QDYN, H-IBQDYN and other physical/source families inspected; several physical labels opened, but not all option payoffs. |
| 2024 | Cross-venue V1 outer opened; cross-market V1/V1R1 failed before economic outcomes. |
| 2025 | Cross-venue V3 outer and V4 development, Globex, directional, dual-leg and IB outcomes opened. |
| 2024-01..2025-12 | Existing-data utility nested run opened; short-premium stopped at execution/source gates. |
| 2026-01..2026-05 | Baseline executable, Phys-TD, AdaJEPA, PatchCore/Var-JEPA, h1/h6, spot-skip and early 1m families opened outcomes. |
| 2026-01..2026-06 | V4R2 outer, V7, Semantic/Factorized/Breadth/Surface/Vol directional families opened outcomes. |
| 2026-07-01..2026-07-24 | July MTD outcomes were inspected by several families; this is not a complete monthly validation. |
| OPRA V5 / external intake | Source gate/intake only; no model, label, payoff or outcome. |
| After 2026-07-24 and 2027+ | Future/uncaptured in the documented inventory; not an untouched historical outer reserve. |

## Exact handoff and registry obligations

1. Separately commit a Phase-1 predeclaration before any build or outcome read.
2. Add one explicit row for the new family to
   `research_papers/JEPA/ECONOMIC_FAMILY_REGISTRY.md`; preserve terminal status,
   evidence path, and source/economic distinction.
3. Version outcome-free source/data gate, independent audit, model/prediction
   freeze manifest, economic result and closure/failure artifact.
4. Keep these five handoffs synchronized after every seal/result/closure:
   `AGENTS.md`, `CODEX-HANDOFF.md`, `SUMMARY.md`, `SUMMARY-update.md`,
   `SUMMARY-articles.md`.
5. Commit/push compact evidence and registry/handoff updates before the next
   stage. Do not add large parquet/model artifacts without explicit authority.
6. Leave `README_PATCH.md`, services, bots, systemd, VPS and web untouched;
   no live/paper integration follows from this Phase-0 artifact.
