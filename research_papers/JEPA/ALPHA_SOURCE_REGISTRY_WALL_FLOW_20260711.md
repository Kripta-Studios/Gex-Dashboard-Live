# Alpha-source registry and Stage 0/1 audit — 2026-07-11

## 2026-07-22 cross-venue source repair

The full native-clock source ended unsealed at 3,008/3,012 captures. Four
captures contain exactly one Greek/IV unilateral contract repeated at 10:30
and 10:35; this was discovered before any outer outcome. V1R1 freezes an exact
`Greek∩IV` signable set for only those IDs, keeps all unilateral rows audit-only
and captures the four missing quote responses to a separate immutable overlay.
The 3,008 V1 captures must not be modified. A composite 3,012 seal is required
before data gate or outer 2024. No new alpha/PF/WR/PnL exists yet.

## 2026-07-17 profitability clarification

`CROSS_VENUE_CALENDAR_RR_LEADER_V1` has not opened 2026; its 2024–2025 exact
clock capture was 424/3,012 with zero errors at 03:09 Europe/Madrid. The closed
`DIRECTIONAL_VOL_COMPLEX_V1` was profitable in June 2026 for QQQ/SPX/SPY (PF
1.249/1.779/1.764, 21 trades each) and net-positive July MTD, but July had only
10 trades and PF 1.133/1.098/1.888. Jan–Jun stability failed, so this is not a
promotable source. SPX cash proxy is not SPXW executable-option evidence.

An independent post-one-shot outer-2024 auditor is now implemented before any
new outcome access. It recomputes economics and gates and rehashes sources; the
cross-venue suite passes 50 tests. It remains unexecuted until the frozen 2024
ledger exists.

This registry was built without reading outcomes, option PnL or any 2026 market
data.  Production files are unchanged.  It separates economic mechanisms and
prevents a model/feature sweep from masquerading as a new source.

## 1. Repository and evidence audit

- Branch `main`; Stage-0 checkpoint at audit start
  `dfebdab6f5d6e8960c978845622c9862525ce12d`, synchronized with `origin/main`.
- No tracked changes and no active Python/research PowerShell process at audit
  start.  Numerous unrelated untracked legacy artifacts were preserved.
- Production targets had no diff:
  `services/realtime_feed.py`, `bots/tradingbot_wrapper_jepa.py`, both systemd
  units, the active package and production validator.
- June 2026 remains sealed and was not read.
- `WALL_SURFACE_FLOW_AT_TOUCH_V1` initially consisted only of prose.  It had no
  builder, exact allowlist, runner, tests or execution manifest.

Reusable audited implementations:

| Contract | Reusable code |
| --- | --- |
| Ask entry / future bid exit | `build_event_option_dataset.executable_quote_path_label` |
| Scheduler, caps, cooldown, one position | `walkforward_event_option_gate.DeployConfig`, `deploy`, `position_exit_minute` |
| Economic metrics | `walkforward_event_option_gate.metrics` |
| Live-equivalence artifact audit | `validate_event_option_production_package.assert_trade_artifact_live_equivalence` |
| Wall snapshot primitives | `wall_state_features.py` |
| Wall/event exact-key audit | `build_wall_state_dataset.py` and physical V1 tests |

The current task is Stage 2 physical separability only.  Economic scheduler code
must not be connected unless the physical gate and provenance blockers pass.

## 2. Independent hypothesis registry

| ID | Mechanism | Independent measurement | Status | Next falsifiable test |
| --- | --- | --- | --- | --- |
| H-FLOW1 | Completed option-surface pressure at first wall touch | 1m OHLC volume/count/close signed versus exact bar-start NBBO proxy; full/local 1/5/15m | Feasible; blocked on 1,441-session native timestamp backfill | Seal quote sidecar, then frozen F0 versus F1 physical test |
| H-SURF1 | Intraday surface deformation | Exact current/lagged local IV, bid/ask-IV, skew and curvature on fixed causal grid | Available, not part of H-FLOW1 | Separate data gate after H-FLOW1 closes; no combined first model |
| H-LIQ1 | Execution-liquidity degradation | Current spread, valid-quote density, completed volume/count | Partly available; no depth | Execution-feasibility block, not directional alpha claim |
| H-FUT1 | ES/NQ flow confirmation | Signed futures flow/acceleration/divergence | Blocked | Acquire raw contract-level ES/NQ archive plus roll map |
| H-BASIS1 | Cash/future basis displacement | Synchronized cash and active ES/NQ contract | Blocked | Same new feed as H-FUT1 with causal roll selection |
| H-VOL1 | VIX1D/VIX/VVIX/term displacement | Timestamped volatility-complex curve | Blocked/partial | Acquire VIX1D, VVIX and futures term data; `vix_spot` proxy alone is insufficient |
| H-QSIZE1 | Top-of-book size imbalance at wall | Native 1m historical bid_size/ask_size snapshots | Newly available; not in H-FLOW1 | Separate predeclaration after full sidecar coverage; no outcome inspection now |
| H-QDEPTH1 | Full depth/update intensity | NBBO sequence/update timestamps or book events | Blocked | New OPRA event feed; 1m size snapshots are not depth or update intensity |
| H-UND1 | Underlying signed flow | Trade volume/aggressor/depth | Blocked | New underlying or futures microstructure feed |
| H-RV1 | Realized acceleration/volatility | Completed underlying OHLC/tick count | Available only as frozen control | Do not revive generic spot momentum as alpha family |

## 3. Data-availability matrix

Canonical cutoff `20220801..20251231` contains 2,519 0DTE sessions:

| Source | Paths | Exact available fields | Coverage | Missing measurements / caveats |
| --- | --- | --- | --- | --- |
| Option Greeks/quote | `D:/ThetaData/data_options/{ticker}/greeks/YYYY/MM/*` | strike, right, bid, ask, underlying price, delta, theta, vega, rho, epsilon, lambda, IV, timestamps | SPXW 145,339,783 rows; QQQ 87,331,805; SPY 93,082,242 | No sizes/aggressor; gamma/higher Greeks not stored; 1,441 sessions lack native option `timestamp` |
| Option OHLC | `.../{ticker}/ohlc/YYYY/MM/*` | open/high/low/close/VWAP, volume, count, timestamp | SPXW 83,263,450; QQQ 47,392,719; SPY 48,662,296 | Bar close is not paid premium; timestamp is bar open |
| Option IV | `.../{ticker}/iv/YYYY/MM/*` | bid/ask IV, IV, midpoint, bid/ask, underlying | Available all tickers | Not row-identical to Greeks; exact-key join required |
| Daily OI | `.../{ticker}/oi/YYYY/MM/*` | strike, right, open_interest | SPXW 368,595; QQQ 222,156; SPY 236,728 | Prior-close OI, normally reported ~06:30 ET; not intraday inventory flow |
| Derived underlying | `D:/ThetaData/data_underlying_derived/{ticker}/YYYY/MM/*` | 1m OHLC, tick_count, bar-open timestamp | Complete canonical sessions | No signed volume, quote or depth |
| Executable event view | `tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/` | exact keys, spot, causal returns, ask-to-bid labels | SHA `d3c37b5...a408` | Outcome columns must never be loaded by flow builder |
| Wall state | `tmp/wall_state_gex_dex_202201_202512_v1/` | reconstructed CALL/PUT gamma/delta walls and state | 135,120 rows; SHA `94e311e0...df8ef` | Daily-OI wall state already failed incremental physical test |
| ES/NQ/futures | none frozen locally | none | absent | Generator code is not historical data availability |
| VIX1D/VVIX/term | none frozen locally | only derived `vix_spot` elsewhere | absent | Timestamp/provenance not adequate |
| Native quote sidecar | ThetaData `/option/history/quote` | timestamp, bid, ask, bid_size, ask_size | Six-session quote/Greek recovery audit; full 1,441-session backfill pending | Current provider response can revise history; raw response and frozen Terminal hashes required |
| Quote depth/update stream | none | none | absent | 1m top-of-book size cannot reconstruct event intensity or full depth |

One central session per ticker-month (123 sessions) showed complete 250-minute
10:20–14:29 grids, no duplicate/non-boundary OHLC keys and 100% exact contract
join presence.  Valid bid/ask row/volume coverage on positive-volume,
positive-close bars was SPXW 92.20%/97.109%, QQQ 94.914%/98.609% and SPY
93.279%/99.253%.  This is feasibility only; no outcome association was measured.

## 4. Causal-risk matrix

| Risk | Severity | Failure mode | Frozen control |
| --- | --- | --- | --- |
| Current incomplete option bar | Critical | Bar `t` contains trades after decision `t` | Windows include only bar starts `<t`; assert `bar_end<=t` |
| Minute-floor quote leakage | Critical | `t-1:30` signs bar stamped `t-1:00` | Exact timestamp equality only; sub-minute rows cannot sign |
| Wrong label horizon | Critical | Exclude bar `t`, include bar `t+h` | Use exact starts `t<=s<t+h`, terminal close at `t+h-1` |
| Fake rejection | Critical | Defended close without pierce | `true_rejection` requires actual/current pierce |
| Gamma/delta alias duplication | High | Same physical level counted twice | Collapse same-role same-strike aliases |
| Dual support/resistance role | High | Complementary labels for one path | Exclude simultaneous opposite-role same-strike levels |
| Repeated five-minute touch | High | Serial rows inflate sample/significance | First causal episode only; day-block bootstrap |
| Missing native option timestamp | Critical | Underlying time substituted for quote time | Require exact timestamp/contract key-set recovery for all 1,441; use original Greek bid/ask |
| Provider historical revision | High | Current requery silently replaces old bid/ask | Preserve both hashes; sidecar supplies clock only; report mismatch rows/sessions |
| Contract/expiration substitution | Critical | Different expiry/strike appears as flow | Include symbol/expiration/right/strike/time in keys; exact 0DTE only |
| Duplicate API rows | High | Volume/count double-counted | Fail closed; never sum duplicate normalized raw keys |
| Nonpositive close or missing count | Medium | Missingness masquerades as pressure | Retain unsigned volume; separate price/count/signable coverage |
| Full-surface universe drift | High | Live ATR filter differs from history | Frozen full chain; sidecar must use `strike=*` |
| Poll/availability latency | Critical for payoff | Retrospective entry at scheduled `t` | Record `feature_available_at`; any entry occurs afterwards |
| Futures roll/basis | Critical | Contract substitution creates change | Block until raw contracts and causal roll map exist |
| Multiple hypotheses | High | Post-hoc subgroup selection | One block per experiment; fixed 24 cells and global gate |
| 2026/holdout exposure | Critical | Selection contamination | Builder and tests reject 2026; holdout remains unopened |

## 5. Closed families not to repeat

- flat/modal/more-history JEPA;
- semantic masking, VISReg, SIGReg, prototypes and Gram anchoring;
- variational JEPA/uncertainty abstention;
- PatchCore trading filters;
- AdaJEPA downstream;
- h1/h6 or generic horizon sweeps;
- generic spot momentum/contrarian skips;
- 1m versus 5m cadence as the mechanism;
- return versus win objective without new information;
- IV-skew/spread/absolute-return/IB-range regime gates;
- absolute versus pairwise CALL/PUT heads and magnitude weighting;
- generic physics/context expansion;
- static wall proximity and daily-OI strength/concentration/migration;
- wall magnet/rejection/acceptance rules based only on location and daily OI.

H-SURF1 is not a license to rerun the closed generic IV-skew gate.  It would need
timestamped local surface *change/deformation* with stable contract/grid identity.

## 6. Exact implementation audit after V1R1 corrections

New outcome-free code:

```text
neural/jepa/surface_flow_features.py
neural/jepa/build_wall_surface_flow_dataset.py
neural/jepa/build_wall_native_quote_sidecar.py
neural/jepa/wall_surface_flow_environment.py
tests/test_surface_flow_features.py
tests/test_build_wall_surface_flow_dataset.py
tests/test_build_wall_native_quote_sidecar.py
tests/test_wall_surface_flow_environment.py
```

Frozen physical runner code:

```text
neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py
tests/test_evaluate_wall_surface_flow_at_touch_v1.py
```

At the current checkpoint, 36 focused tests pass.  They cover exact completed
windows, current-bar exclusion, sub-minute quote rejection, nonpositive-close
and missing-count denominators, unknown rights, duplicate/interval/timestamp
fail-closed behavior, event-grid coverage, alias/episode collapse, dual-role
exclusion, completed-only volatility, true pierce, exact future-bar alignment,
current-beyond semantics, half-day/regular RTH horizon closure, wrong-calendar
sources, schedule-aware data gate, runtime lock, raw quote immutability, exact
native quote/Greek key sets, deterministic day bootstrap and the joint
AP/log-loss gate.

Current live parity remains blocked.  `realtime_feed.py` omits explicit option
`interval=1m`, retains only short overwritten windows, discards the bar-start
quote, applies an ATR strike filter and does not share frozen wall identities.
A separate append-only shadow collector is required; production is not modified
during this research stage.

## 7. Rotación calendar-RR posterior — 2026-07-17

La familia `CALENDAR_RISK_REVERSAL_PRESSURE_V1` cerró desarrollo 2023 con edge
parcial, no promocionable: pooled PF `1,058294`, QQQ `1,173476`, SPY `1,072835`
y SPXW `0,912372`; solo 12/36 celdas pasan. No se abre 2024–2026 ni se selecciona
un ticker o mes post-hoc.

Dos extensiones independientes se auditaron sin outcomes y quedan cerradas:

| ID | Fuente propuesta | Estado | Razón autoritativa |
| --- | --- | --- | --- |
| COMPONENT-CALENDAR-RR-BREADTH-V1 | RR calendarizado de 14 componentes/ETF e IWM | `FAILED_FREQUENCY` | Componentes min3/mes; IWM min12, pero la gate exige >12 |
| INDEX-ETF-CALENDAR-RR-PARITY-V1 | NDX/NDXP↔QQQ y SPX↔SPY | `BLOCKED_LOCAL_SOURCE` | NDX/NDXP sin Greeks; SPX sin ninguna fecha front0DTE+back |

Los cierres autoritativos son
`COMPONENT_CALENDAR_RR_BREADTH_V1_FEASIBILITY_CLOSURE.md` e
`INDEX_ETF_CALENDAR_RR_PARITY_V1_FEASIBILITY_CLOSURE.md`. No hacer forward-fill
semanal, nearest-expiry ni reutilizar SPXW/QQQ/SPY como si fueran una fuente
nueva. El universo temporal vigente empieza en 2023; 2026 permanece holdout
hasta superar desarrollo 2023 y outer 2024–2025.

Por instrucción posterior del usuario se autoriza una única continuación
cross-venue, registrada como hipótesis generada post-outcome:

| ID | Mapping | Evidencia de diseño | Estado |
| --- | --- | --- | --- |
| CROSS-VENUE-CALENDAR-RR-LEADER-V1 | QQQ←QQQ, SPY←SPY, SPXW←SPY | 2023 PF 1,173/1,073/1,072, pero solo 7/5/5 meses positivos | `PREDECLARED_NATIVE_CLOCK_FEASIBILITY` |

2023 no puede validar esta regla. La primera prueba es 2024 tras construir un
sidecar exacto front/back; 2025 y 2026 siguen cerrados. Predeclaración:
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md`. No abrir grids
own/leader/consensus ni reemplazar los precios vintage con una recaptura actual.

Preflight native-clock posterior: `PASS`, 24/24 captures y 64.632 rows con cero
missing/extra/revisions/crossed. Full 2024–2025 proyectado 8,095M rows/1,425GiB
raw para 3.006 requests. Esto desbloquea solo el full sidecar/data gate; no hay
outcome OOS nuevo. Resultado autoritativo:
`CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT_RESULT.md`.

Erratum pre-full: discovery completo cuenta 1.506 sesiones/3.012 captures, no
1.503/3.006. ID SHA `447e771b...5ce4`; proyección corregida 8,111M rows/1,428GiB
raw, aún PASS. No excluir sesiones para reproducir la constante antigua. Véase
`CROSS_VENUE_CALENDAR_RR_FULL_UNIVERSE_COUNT_CLARIFICATION.md`.

El data gate outcome-free posterior queda congelado en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_DATA_GATE_CONTRACT.md`: full seal 3.012,
revalidación offline, option-clock key proof y valores económicos vintage. No
autoriza outcomes ni producción.

Builder implementado pre-outcome en
`neural/jepa/build_cross_venue_calendar_rr_leader_v1.py`: full-seal required,
3.012-capture offline revalidation, target-only spot reads y exact-date mapping.
Suite combinada `34 passed`; no se ejecutó sobre el sidecar parcial.

Runner one-shot 2024 predeclarado en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_OUTER_2024_RUNNER_CONTRACT.md`; PF>1 es gate
incremental para abrir 2025, no promoción. No existe manifest ni outcome.

Evaluator/freezer implementados pre-outcome; suite combinada `45 passed` y
target-only read 10:36/13:36. Siguen sin manifest hasta data gate PASS committed.

Live audit: `NOT_LIVE_READY`. Weekly≠next-expiry, first-order IV≠bid/ask-IV y no
hay estado de contratos t0→t1. Payoff option ask→bid queda requerido después de
cash PASS; servicios/producción intactos.

Auditor full post-seal implementado en
`audit_cross_venue_calendar_rr_native_clock_full.py`; revalida 3.012 captures y
6.024 sources antes del data gate. Suite combinada `48 passed`; no ejecutado.

Auditor independiente del data gate implementado: 16.566 source hashes, full
index equality, mapping/gates/schema recomputation. Suite combinada `53 passed`;
no ejecutado y sin acceso a underlying values/outcomes.

Full capturer preejecución implementado: universo hash locked, capture atómica,
resume con revalidation y seal solo 3.012/3.012. Suite combinada `16 passed`.
Aún no existe full sidecar ni outcome 2024; commit/push precede al launch.
