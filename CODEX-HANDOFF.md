# CODEX-HANDOFF — estado autoritativo de investigación

## V7 rolling12 predeclarada — 2026-07-26

V4R2 fue fit2023–2025 fijo, no walk-forward 2026. Diagnóstico post-outcome:
coeficientes anuales casi no correlacionan (-0,143..0,146); marzo direct
+518,6bps pooled se convirtió en -273,2bps al invertir74,6%. V7 fija una única
adaptación mensual rolling12, mismo logistic29/C0,1 y mismos eventos/clocks.
Febrero–julio incorporan solo meses 2026 anteriores. Commit/push contrato antes
de evaluator+auditor; versionar ambos antes del run. Es development visto,
nunca promoción/payoff/live con 2026.

## V4R2 outer 2026 FAIL auditado — 2026-07-26

One-shot desde manifest `e826eb1e`, 394 trades: H1 PF QQQ/SPXW/SPY
0,970/0,951/0,956, net -86,9/-97,9/-87,8bps y solo2/6 meses positivos cada uno.
Junio positivo en tres pero QQQ/SPXW PF<1,20; julio MTD solo QQQ positivo,
SPXW/SPY pierden. Auditor PASS con refit/predictions exactos y 394 fuentes
mismatch0. Evidencia versionada en `8bd1d437`; V4R2 cerrada y 2026 visto.

## V4R2 fija cuatro exclusiones sin nuevas descargas — 2026-07-26

Reseal V4R1 real PASS: 3.432/3.432 keys Greek/IV, unilaterales0 y retry
exclusions0. El builder posterior cerró sin output por cuatro fuentes/sesiones
adicionales outcome-free: QQQ 20260310, SPY 20260319, QQQ 20260630 y QQQ
20260722. El usuario ordena ignorarlas y no reconsultar.

V4R2 congela esas cuatro exclusiones antes de 10:36/13:36; mapping/modelo/clocks
no cambian. Gate real desde `f60f6282` PASS: sensores262, targets394,
fuentes1.446/mismatch0 y clocks outcome false. Auditor desde `09395b94` PASS:
feature view exacta, reparse10 y rehash1.446/mismatch0; summary SHA
`16988ecc...1aa3`. Gate+audit versionados en `15b76868`.

Runner final pre-outcome listo: fit exacto2.217, events/predictions394,
manifest+model serializado, evaluator 10:36→13:36 one-shot y auditor con refit
independiente. V4R1+V4R2 tests16/Ruff/compile PASS. Primero commit/push del
código; luego freezer una vez, commit/push manifest y solo entonces outer2026.

Código publicado `7472f45d`; freeze real PASS: train2.217/events394, event
`1df3753c...05cf`, model `e8caffde...202e`, manifest `f90dbcf6...45e6`.
Verifier pre-outcome exacto y clocks outcome false. Versionar frozen+hándoffs;
después único outer y auditor.

## V4R1 retry materializada; corrección dtype pre-feature — 2026-07-26

La tanda única desde `aba363c3` produjo 10/10 raw+parquet válidos. El pair gate
inicial 0/5 no es autoridad económica: falló al filtrar una columna parquet
`timestamp[ns]` con strings. Sin red ni outcomes, la lectura exacta de 10:30 y
10:35 obtiene las cinco parejas completas: 688, 800, 632, 604 y 708 filas por
lado, sin Greek-only/IV-only; exclusiones0. Captura original inmutable, seal SHA
`a18e0864...58f0`.

La aclaración dtype, lector dual y resealer offline están implementados y pasan
focal8/Ruff/compile. Orden inmediato: commit/push explícito → ejecutar una vez
el reseal v2 → builder outcome-free → auditor independiente → versionar ambos.
No abrir 10:36/13:36 ni congelar/evaluar V4 hasta terminar ese orden.

## V4R1 autorizada: retry/exclusión 2026 — 2026-07-26

El usuario sustituye el veto a los cinco IDs junio2026: diez requests exactos
Greek+IV, una sola tanda, root nuevo y mismos endpoints/fallback que
`options_bulk.py`. Si una pareja no queda válida y key-exact, se excluye todo
el sensor-fecha antes de outcomes; SPY arrastra SPXW por mapping. No intersection,
fill ni overwrite. Universo metadata actualizado: 133 fechas hasta 20260724,
532 front/back captures y julio MTD13. Primero versionar contrato; después
capturador/gate/auditor antes de red. V4 no cambia y V6 cerró sin evaluación.

Código pre-red ya implementado: capturador atómico de diez requests, builder de
29 features hasta10:35 y auditor que reparsea raw/rehashea/reconstruye. Focal7,
Ruff y compile PASS; el test real de fuentes reproduce Greek-only92/IV-only516.
No se llamó la API. Siguiente: commit/push de estos archivos; después un único
run de captura al root V4R1.

## V6 predeclarada sobre artefactos V4 — 2026-07-26

La licencia es Options Standard básica: no volver a intentar endpoints sin
entitlement. Por autorización expresa del usuario, una única V6 continúa V4
sin descargar ni reconstruir datos. Mantiene mapping/features/clocks/eventos/
costes y sustituye únicamente logistic por HistGB depth2 fijo. Development
walk-forward: 2023→2024 y 2023+2024→2025, con gate estricta en los seis
ticker-año y todos los meses. Primero commit/push del contrato; después
evaluator+auditor committed antes de ejecutar. 2026 y live permanecen cerrados
hasta PASS. Autoridad:
`CROSS_VENUE_CALENDAR_RR_LEADER_V6_SHALLOW_HISTGB_PREDECLARATION.md`.

## V5 source gate FAILED — 2026-07-26, sin outcomes

Desde `e6bdac64`, 1.504 requests completos: 1.364 captures válidos y 140
fallos uniformes `invalid or duplicate V5 trade_quote response`; QQQ
32/25/8 y SPY38/30/7 por 2023/2024/2025. Enero2024 falla21/21 por sensor.
Stagers0, no seal, sin builder/features/opens/outcomes. No requery, dedup,
exclusión ni evaluación parcial. Auditor real desde `c4318884`:
`PASS_INDEPENDENT_AUDIT_OF_FAILED_SOURCE_CAPTURE_GATE`, rehash/reparse1.364,
mismatch0/unaccounted0/min mensual0; summary/seal `39b417e0...fc77`/
`20f322c5...0297`. V5 queda `BLOCKED_DATA`; no builder/evaluator. Bloqueo
terminal en `CAUSAL_SOURCE_EXTERNAL_DEPENDENCY_BLOCK_20260726.md`: se necesita
una fuente externa histórica/live nueva antes de cualquier familia posterior.

## V5 OPRA trade_quote predeclarada — 2026-07-25, sin datos

Implementación preejecución lista: capturador inmutable/resumible, builder y
auditor que reparsea raw sin importar el builder. El censo por nombres exact-0DTE
es QQQ=SPY=752 fechas, 250/252/250 por año, 1.504 captures, date SHA
`e7786a1a...b8f9`. Suite cross-venue: 113 PASS; Ruff/compile
PASS. Solo se consultó `/terminal/mdds/status=CONNECTED`; cero llamadas
`trade_quote`, valores o outcomes. Commit/push del código precede a la captura
workers2; gate+audit se versionan antes de cualquier open económico.

El inventario outcome-free encontró una sola fuente nueva compatible con
histórico y live: prints OPRA 0DTE de QQQ/SPY con tamaño/precio/condición y el
NBBO estrictamente anterior, servidos históricamente y por streams Standard del
mismo proveedor. No se inició Terminal ni se consultó endpoint, valor, feature,
open económico u outcome. Greek/IV no forma parte de V5 y los cinco IDs nuevos
de junio2026 permanecen fail-closed e intactos.

`CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_PREDECLARATION.md` congela mapping
QQQ←QQQ, SPY←SPY, SPXW←SPY, clocks de features 09:30–10:35, 24 features,
logistic pooled L2 C0,1, folds development 2024/2025 y la gate conjuntiva
completa por ticker-año/mes. Siguiente autoritativo: commit/push de estos
documentos; después data gate 2023–2025 y auditor independientes outcome-free,
versionados antes de abrir opens10:36/13:36. 2026 y producción siguen cerrados.

## Estado consolidado 2026-07-25 — leer antes que los checkpoints históricos

Los `Siguiente:` inferiores describen la secuencia que ya se completó; no se
deben volver a ejecutar. `main` contiene los outers, auditors, V4 development,
fallo outcome-free 2026 y cierre cash-only.
Cadena compacta: `00bf96c4` outer2024, `627f3b20` V3 development,
`cea5e076` outer2025, `6c858533` V4 development, `58facc5f` gate2026,
`3e4603e0` cash-only y `051a71bd` registro causal.

Ledger causal a 1bp, orden QQQ/SPXW/SPY:

- 2023 design ya visto: PF `1,173476/1,071604/1,072835`, WR
  `51,822/50,000/50,403%`, neto `+812,500/+268,657/+273,999bps`, min
  `19/19/19`, meses positivos `7/5/5`.
- 2024 outer V1 auditado: PF `0,866939/0,698912/0,693382`, WR
  `48,594/39,271/40,081%`, neto `-662,668/-1.220,988/-1.246,477bps`, min
  `19/18/18`, meses `6/5/5`; cerrado sin avance.
- 2024 V3 development post-outcome: PF `1,231750/1,395967/1,408300`, WR
  `51,406/55,870/56,680%`, neto `+964,402/+1.124,966/+1.153,375bps`, min
  `19/18/18`, meses `8/8/8`; incremental PASS, objetivo FAIL.
- 2025 outer V3 auditado: PF `0,655469/1,035567/1,039777`, WR
  `50,607/53,689/53,689%`, neto `-2.381,476/+163,026/+182,456bps`, min
  `18/17/17`, meses `5/6/6`; 2026 no se abrió.
- 2025 V4 development post-outcome auditado: PF
  `1,204351/1,247945/1,346342`, WR `51,8219/52,0492/53,2787%`, neto
  `+1.060,279/+1.030,091/+1.381,556bps`, min `18/17/17`, meses `7/8/8`.
  Es reproducible y prometedor, pero no OOS ni estable todos los meses.
- 2026 V4: sin outcomes. Gate vintage falla cerrado por cinco capture IDs
  nuevos, Greek-only92/IV-only516. Mantener `Greek∩IV` solo en los cuatro
  repairs V1R1 y fallar ante cualquier quinta discrepancia.

No hay policy promovible ni V5 activa. Cash-only falla transporte entre
2024/2025. La siguiente investigación debe comenzar por un inventario
outcome-free de una fuente causal nueva con histórico y contrato live, mantener
QQQ←QQQ, SPY←SPY, SPXW←SPY y predeclarar antes de materializar outcomes.
2024–2025 son development visto; 2026 solo puede abrirse como siguiente outer
después de gate, auditoría, freeze y commit. No tocar live/systemd. Ask→bid,
no-overlap, hold30–180m y `reject_while_open` preceden cualquier paper-only.

## V3 outer 2025 — cerrado y auditado

Freeze committed `91584706`; one-shot2025 `FAILED_OUTER_2025_2026_CLOSED`.
QQQ: 247 trades, WR50,607%, PF0,655469, -2.381,476bps, min18, 5/12 meses.
SPXW: 244, 53,689%, 1,035567, +163,026bps, min17, 6/12. SPY: 244, 53,689%,
1,039777, +182,456bps, min17, 6/12. No ticker llega a PF>1,20 y 12/12 meses;
2026 sigue sin abrir.

Auditor real PASS: 735 sources rehashed/mismatch0 y digests exactos; evaluation
summary `99346b5b...1dd5`. Force-add/commit/push outer+audit+hándoffs. Después,
solo puede explorarse una familia nueva declarando 2023–2025 development y
reservando 2026 como primer outer; no rescatar V3 ni tocar live/systemd.

## V4 elegida antes de cualquier dato 2026

Diagnóstico ya contaminado 2025: el pooled V2R1 fit 2023+2024 es la única
variante simple que pasa incremental en los tres: PF1,204/1,248/1,346,
WR51,8/52,0/53,3%, net +1.060/+1.030/+1.382 y min18/17/17; objetivo falla por
7/8/8 meses positivos. Online windows, confidence, weighted-logistic y ridge no
mejoran estabilidad/frecuencia.

Predeclaración V4 full-history logistic creada. Mismo modelo V2R1 pooled29/C0,1,
sin cambios ni refit. Commit/push doc antes de implementar development2025.
Después evaluator → auditor → solo data gate 2026 outcome-free. No leer 2026;
cualquier discrepancia Greek/IV nueva falla cerrado y no amplía los cuatro IDs.

Guardar como checkpoint numérico V4 development2025 a 1bp: QQQ
PF1,204351/WR51,8219%/+1.060,279bps/min18/7 meses; SPXW
1,247945/52,0492%/+1.030,091/min17/8; SPY
1,346342/53,2787%/+1.381,556/min17/8. Es el mejor resultado actual, pero fue
descubierto después de abrir 2025: reproducir y auditar antes del data gate 2026.

V4 evaluator+auditor publicados `b421acd3` y ejecutados una vez. Development
`PASS_INCREMENTAL_DEVELOPMENT_2026_DATA_NOT_OPENED`, train1482/dev735,
sources738/mismatch0. Auditor `PASS_INDEPENDENT_V4_DEVELOPMENT_AUDIT`, refit y
digests exactos; summary `a2beced1...21b`. Dataset/model/trades SHA
`87413fb1...d04b`/`f8412730...c98b`/`9742c229...335c`. Force-add/commit/push
evidencia. Luego solo data gate 2026 outcome-free; no outcomes 2026.

El censo vintage outcome-free 2026 cerró V4 antes del data gate: 508 capturas,
391.556 shared rows, pero cinco IDs nuevos suman Greek-only92/IV-only516 (QQQ
20260624/26 front y SPY 20260624/25/26 front). El contrato prohíbe ampliar los
cuatro repairs V1R1; no intersection/exclusión/recaptura. Documento autoritativo
`CROSS_VENUE_CALENDAR_RR_LEADER_V4_2026_VINTAGE_KEY_GATE_FAILURE.md`. Ningún
underlying value/outcome 2026 ni red fue abierto. Versionar handoffs; V4 closed.

Cash-only post-V4 también `CLOSED_NO_STABLE_CASH_ONLY_EDGE`. Resúmenes lineales,
spot, cross-cash, shallow HistGB/RF y secuencia35x1m fallan transportabilidad.
La secuencia pooled da PF2024 QQQ/SPXW/SPY 1,169/0,903/0,916 y PF2025
0,985/1,480/1,483; separar sensores no corrige 2024. Documento homónimo
`CROSS_VENUE_CALENDAR_RR_POST_V4_CASH_ONLY_DIAGNOSTIC.md`. No crear V5 ni
abrir 2026 desde estos resultados.

## V2 temporal orientation — predeclaración antes del nuevo feature read

Contrato nuevo post-outcome:
`CROSS_VENUE_CALENDAR_RR_LEADER_V2_TEMPORAL_ORIENTATION_PREDECLARATION.md`.
2023–2024 queda development; 2025 es el primer outer aún intacto. Un único
logistic L2 C0,1 predice si conservar/invertir `sign(signal_pressure)` usando
29 inputs fijos: ocho option-sensor, seis cash QQQ, seis cash SPY, seis cash
SPXW activas solo para target SPXW y tres one-hot. Los cash inputs usan solo 66
opens 09:30–10:35. DEV_A train2023/testH1; DEV_B train2023+H1/testH2. Commit/
push antes de leer los opens o implementar el runner. No 2025/2026/live.

Implementación V2 lista pero no ejecutada:
`neural/jepa/evaluate_cross_venue_calendar_rr_leader_v2.py`. Verifica runtime e
inputs SHA, exact-date mapping, 66 clocks open-only por fuente, modelo/predicción
y gates; escribe output inmutable. Focal7, cross-venue74, Ruff/compile PASS.
Commit/push explícito antes del único default run. Un fallo cierra 2025.

Primer run V2 falló antes del loader cash y no creó output: colisión de nombre
`signal_pressure` ledger/sensor. Fix namespaced `sealed_signal_pressure`, usado
solo para comprobar la paridad del mapping 2024. Focal8/cross-venue75 y checks
PASS. No se leyó ningún open nuevo; commit/push antes de reintentar.

Segundo run falló en el mismo tramo pre-cash: zeros exactos QQQ 20231116 y
20231215, ambos `NO_TRADE_ZERO_PRESSURE` ya sellados. Clarificación congelada
en `CROSS_VENUE_CALENDAR_RR_LEADER_V2_ZERO_PRESSURE_TRAINING_CLARIFICATION.md`:
excluir solo esos dos del fit, exigir set exacto y fallar cualquier tercero.
Train esperado739, predicciones2024 intactas. Commit doc antes del código.

Código ya aplica el set exacto y falla cualquier tercero; focal10,
cross-venue77, Ruff/compile PASS. Aún no alcanzó cash ni creó output. Commit/
push del fix antes de reintentar default.

Tercer run también pre-cash: merge redundante del campo ya namespaced. Fix
compara directamente la paridad 2024; focal11/cross-venue78/checks PASS, target
inexistente. Commit/push antes del siguiente intento.

Cuarto run llegó a cash y falló antes del fit: única fuente inválida
`SPY|20230605`, open0 09:55/09:56, entre 1.487. V2R1 repara uniformemente a
10:00–10:35 (36/35 clocks/returns, horizons35m/15m/5m), sin fill ni excluir
fecha. Autoridad:
`CROSS_VENUE_CALENDAR_RR_LEADER_V2R1_EARLY_CLOCK_REPAIR_CLARIFICATION.md`.
Commit doc antes de código; no prediction/output/2025.

Código V2R1 listo: censo original exacto + matriz solo10:00–10:35, vector29
sin otros cambios. Focal12/cross-venue79/checks PASS; commit/push antes de run.

Run real desde `d2df1a61`: `PARTIAL_DEVELOPMENT_EDGE_2025_CLOSED`. DEV_A PF
QQQ0,667127/SPXW0,927526/SPY0,771943; DEV_B0,737891/0,991590/1,122964. Solo
SPY DEV_B pasa incremental; advance false. 743 trades, train739, sources1.487,
mismatches0. No 2025/2026.

Auditor V2 listo/unexecuted en
`audit_cross_venue_calendar_rr_leader_v2.py`: refit y paridad total más source
rehash; focal3/cross-venue82/checks PASS. Commit/push antes de auditar default;
luego versionar resultado+audit y cerrar V2.

Auditor real PASS desde `32f77c12`: refit/predictions/ledger/gates exactos,
1.487 source rehashes y mismatch0. Audit summary SHA de evaluación
`c79bddfe...f03a7`, source rehash `b2c8bdac...0a40c`. Compactos V2+audit listos
para force-add/commit/push. Solo después predeclarar V3; no abrir 2025 aún.

V2 ya cerrada/versionada en `3bdb389c`. Nueva V3 predeclarada:
`CROSS_VENUE_CALENDAR_RR_LEADER_V3_MONTHLY_ORIENTATION_PREDECLARATION.md`.
Usa solo majority hit pooled del mes anterior para DIRECT/INVERSE del mes
completo; no modelo/grid/feature cash. Development 2024, 2025 intacto. Siguiente:
commit doc → evaluator/auditor dev → evidencia committed → freezer 2025. No
outcome 2025 antes del manifest.

Evaluator V3 development listo/unexecuted:
`evaluate_cross_venue_calendar_rr_leader_v3.py`. Reproduce history/mapping,
states M-1, ledger1/2/3bps y gates; focal5/cross-venue87/checks PASS. Commit/
push antes del único default. No 2025.

V3 dev real `PASS_DEVELOPMENT_INCREMENTAL_2025_NOT_FROZEN`: PF
1,231750/1,395967/1,408300, WR51,406/55,870/56,680%, net positivo y min19/18/18;
solo8/12 meses positivos, objetivo FAIL. Auditor V3 listo/unexecuted,
focal3/cross-venue90/checks PASS. Commit/push auditor antes de run; no 2025.

Primer audit run falló sin output por dtype int de `prior_month`; valores
coinciden. Fix string explícito + test, commit/push antes de rerun. No 2025.

Auditor posterior PASS desde `64eb91bf`: 12 states/743 trades/gates exactos;
evaluation summary `6a688225...50f5`. Compactos V3 dev+audit listos para
force-add/commit/push. Solo después freezer 2025 outcome-free; no outcomes aún.

V3 dev+audit quedaron versionados en `627f3b20`. Implementados antes de abrir
2025: `freeze_cross_venue_calendar_rr_leader_v3_runner.py`, el runner outer
secuencial y `audit_cross_venue_calendar_rr_leader_v3_outer_2025.py`. El freeze
enumera solo paths/hashes 2025 y deriva enero desde diciembre2024; el runner
revalida hashes/código/event IDs/inventario/counts/estado antes de outcomes y
encadena cada M solo desde M-1. Focal9, suite cross-venue/native-clock100,
Ruff/compile PASS. Código publicado en `5fe51e70`.

Freezer default real PASS desde ese commit: 735 eventos, 36 ticker-meses,
mínimo17. Estado inicial 202412: 25/56 hits=0,446429 e `INVERSE`; manifest SHA
`f45e7f1b...646ed`, event/source digests `87d18fd6...cb8`/
`8308ef36...49e6`. `outcome_accessed=false`. Force-add/commit/push manifest y
handoffs; solo después one-shot2025 → auditor. No 2026/live/systemd.

## Cierre autoritativo — outer 2024 V1 sin edge

Freeze committed/pushed `b53dcaa3`; one-shot 2024:
`NO_AGGREGATE_EDGE_OUTER_2024_CLOSED`. Pooled 743 trades, WR42,665%,
PF0,761071, -3.130,133bps. QQQ PF0,866939/-662,668bps/min19; SPXW
PF0,698912/-1.220,988/min18; SPY PF0,693382/-1.246,477/min18. Meses positivos
6/5/5. `advance_to_2025=false`, así que V1 no puede abrir 2025 ni 2026.

El primer intento del auditor falló cerrado sin artefacto por comparar hashes
post-parse con los bytes CSV originales. Fix de identidad `95609e21` pushed;
suite cross-venue67, Ruff/compile PASS. Segundo intento
`PASS_INDEPENDENT_OUTER_2024_AUDIT`: trades743, fuentes743, size/hash
mismatches0, métricas/gates reproducidas. Versionar evaluación+auditoría y
hándoffs; producción permanece intacta.

El usuario pide continuar con aprendizaje 2023+parte de 2024. Nueva frontera:
V1 no se rescata. Debido a que ya se observó su agregado 2024, cualquier V2 usa
2023–2024 como development causal/walk-forward y reserva 2025 como primer outer
intacto; 2026 solo tras PASS+freeze. Predeclarar V2 antes de analizar variantes
y no tocar live/systemd.

## Checkpoint autoritativo — data gate V1R1 y auditor independiente PASS

El full audit está committed/pushed en `90ffd155`. El único builder posterior
terminó `PASS_DATA_GATE` desde ese mismo HEAD: rows/sessions1.506,
local-valid1.504, mapped-valid1.502, economic events1.478, sources16.566,
coverage mínima0,992063, distinct states237 y mínimo17 eventos/mes. Manifest
SHA `492f51c8...0452e`, feature view `d4335ad8...566062`, parquet
`fd2953bd...5d268`. Los dos errores locales son SPY 20241209/20241216 sin
CALL25 persistente; por QQQ←QQQ, SPY←SPY y SPXW←SPY se registran cuatro errores
mapped. No se excluye ningún otro día ni se acepta una quinta discrepancia.

El auditor independiente ejecutado después terminó
`PASS_INDEPENDENT_DATA_GATE_AUDIT`: 16.566 size/hash matches, gates y mapping
exact-date reproducidos, source-audit SHA `6d3180f1...08194`, mapping parity
`b19cb9eb...5f8ac` y audit summary `7700b087...e85dac`. No leyó underlying ni
outcomes. Compactos están preparados en los dos directorios diagnósticos V1R1.
Commit/push explícito antes de ejecutar
`freeze_cross_venue_calendar_rr_leader_v1_runner.py`; luego force-add/commit/
push del manifest y solo entonces el one-shot outer2024. No abrir 2025/2026 ni
tocar live/systemd antes de las gates secuenciales.

El precheck posterior encontró que `evaluate_cross_venue_calendar_rr_leader_v1.py`
aún nombraba el antiguo compacto V1. Corregir solo `DATA_GATE_DIR` al seal V1R1
versionado, añadir test, ejecutar suite cross-venue y commit/push antes del
freezer. No copiar los compactos a un alias y no abrir outcomes durante el fix.

Fix `811e729f` ya pushed, cross-venue `66 passed`, checks clean. El freezer
posterior creó el manifest único con status `PREEXECUTION_FROZEN`, 743 eventos
2024/743 sources, event IDs `2d56cf96...b124c4` y SHA de manifest
`339c0793...126b72c`. Runner commit y hashes de los tres inputs data-gate están
sellados; outcomes/ejecución/outer2024+ siguen false. Force-add/commit/push del
manifest y handoffs antes de ejecutar evaluator default una sola vez.

## Checkpoint autoritativo — 2026-07-22

V1 terminó `NO_SEAL` con 3.008 capturas atómicas y cuatro diferencias
Greek/IV ya identificadas; no modificarlo ni relanzarlo. V1R1 se capturó una
sola vez desde `0b7cc6dd` y pasó 4/4 con 2.828 shared rows, ocho unilaterales
audit-only y cero missing/revised/crossed. Seal/index/audit SHA
`81ded7dd...bd9d`/`670dd0ce...2fe0`/`910bac85...1c6a`; evidencia compacta
committed en `53872c39`. Ningún outcome fue abierto.

El próximo artefacto ya está implementado preejecución:
`neural/jepa/seal_cross_venue_calendar_rr_native_clock_composite_v1r1.py` y su
test. Revalida offline V1 3.008 + V1R1 4 con contratos, runtime, endpoint,
request params, provenance y hashes exactos; crea un índice lógico multi-root,
sin copiar raw ni leer underlying/outcomes. El primer run desde `a352d544`
falló cerrado antes del output por comparar RangeIndex CSV contra los índices
originales de las ocho rows audit-only; no hubo diferencia de valores/hashes.
Se normaliza solo ese índice y un test nuevo revalida los cuatro repairs reales.
Repairs+composite `13 passed`, suite cross-venue `63 passed`, Ruff/pycompile
PASS. El fix se publicó antes de reintentar el output default con workers8.

El fix quedó committed/pushed en `963f91c9` y el reintento terminó PASS:
3.012 captures, 1.506 sesiones, 7.246.230 rows, 2.415.402 shared keys, ocho
unilaterales audit-only, missing0, revised79 y crossed135. Seal/contract/index/
summary SHA `5b97ebc5...cf84f`/`68714d77...8c046`/
`e5a669b7...3a0e`/`41deb014...df65`. Root
`D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1r1_composite`;
2026/outcomes/live intactos.

Versionar/commit/push `_state/composite_contract.json`, `_seal/seal.json`,
`capture_index.csv`, `ticker_year_summary.csv` y el universo/resultado compacto.
Luego adaptar **antes de ejecutar** `audit_cross_venue_calendar_rr_native_clock_full.py`
y `build_cross_venue_calendar_rr_leader_v1.py`: hoy asumen root único y key-set
Greek=IV en todas las capturas. Deben resolver `storage_root` por fila y aceptar
`Greek∩IV` exclusivamente en los cuatro repair IDs, auditando las ocho
unilaterales sin incorporarlas. Después: full audit → data gate → auditoría
independiente → freeze → one-shot 2024. Solo PF>1/WR>45%/neto>0/min13 por
ticker abre 2025; meta final PF>1,20/WR>45%/min13/todos meses positivos.

La adaptación exacta ya está congelada pre-outcome en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_COMPOSITE_CONSUMER_CLARIFICATION.md`:
validar blobs compactos byte a byte, resolver `storage_root/generation`, exigir
Greek=IV en 3.008 V1 y aplicar los conteos exactos de intersección solo en los
cuatro IDs. Commit/push del documento antes de implementar; código committed
antes de ejecutar full audit o builder.

Auditor y builder ya implementan esa aclaración pre-run. Cambios clave:
default composite V1R1, validación de blobs compactos/locales, revalidación
V1/V1R1 por contrato, paths por role/root, inventario multi-root y alineación
modal con conteos exactos. El auditor resume también generación/shared/
unilaterales. Focal `15 passed`, suite cross-venue `65 passed`, Ruff/compile
PASS. Commit/push antes de ejecutar el full audit; builder/data gate sigue
dormido hasta que ese audit PASS se versione.

El full audit real ya pasó desde `2b33fe5a`: 3.012/3.012, sessions1.506,
rows7.246.230, raw bytes1.369.860.204, vintage sources6.024, shared2.415.402,
Greek-only2, IV-only6, missing0. `capture_revalidation` reproduce el index SHA
`e5a669b7...3a0e`; summary/inventory file SHA `ebd508d4...5d6e`/
`1ca51c14...0240`. No underlying ni outcomes. Versionar compactos y handoffs,
commit/push, y solo entonces ejecutar el builder default; outer 2024 cerrado.

## Respuesta y checkpoint 2026-07-17 03:09 Europe/Madrid

No afirmar rentabilidad de `CROSS_VENUE_CALENDAR_RR_LEADER_V1` en junio/julio
2026: no se ha abierto 2026. Captura PID42112 viva, 424/3.012 y errors0; no
duplicarla. Tras seal: full audit→data gate→commit compactos→freeze→outer 2024.

La celda histórica que puede causar confusión es `DIRECTIONAL_VOL_COMPLEX_V1`:
junio sí fue positivo QQQ/SPX/SPY (21 trades, PF1,249/1,779/1,764,
+161,459/+237,701/+233,476bps). Julio MTD fue positivo pero PF1,133/1,098/1,888
y 10 trades: QQQ/SPX fallan PF1,20 y todos frecuencia. Jan–Jun agregado
PF1,039/0,993/0,898 con meses positivos3/4/3. No promover ni traducir SPX cash
proxy como evidencia de fills SPXW.

Nuevo auditor pre-outcome
`neural/jepa/audit_cross_venue_calendar_rr_leader_v1_outer_2024.py` y test:
recalcula ledger/costes/tablas/gates, rehashea underlying y valida source-audit.
Suite cross-venue `50 passed`, Ruff/compile PASS. No ejecutarlo sin el output
one-shot outer 2024 comprometido.

Contrato siguiente ya congelado en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_DATA_GATE_CONTRACT.md`. Implementar
`build_cross_venue_calendar_rr_leader_v1.py` y tests sin modificar full/preflight
capturers. Debe negarse a correr sin `_seal` PASS, revalidar 3.012 captures
offline, certificar cada key vintage contra option timestamp nativo y usar solo
delta/IV/bid/ask vintage. Spot solo rows 10:30/10:35; prohibido cargar outcome
10:36/13:36. Aplicar exact-date SPY→SPXW y gates por ticker-año/mes. No ejecutar
el builder real hasta terminar/auditar la captura.

Builder y test ya implementados con ese contrato. Suite combinada
`python -m pytest -q tests/test_build_cross_venue_calendar_rr_leader_v1.py tests/test_build_calendar_risk_reversal_pressure_v1.py tests/test_capture_cross_venue_calendar_rr_native_clock_preflight.py tests/test_capture_cross_venue_calendar_rr_native_clock_full.py`
da `34 passed`; Ruff/py_compile clean. Hacer add explícito del builder, test,
siete handoffs y registry; commit/push. No ejecutar aún: full output parcial.
Cuando exista seal, auditar primero el capture y después lanzar el builder
default desde su commit limpio; si PASS, compactar antes del runner 2024.

El runner posterior está fijado en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_OUTER_2024_RUNNER_CONTRACT.md`. Se puede
implementar evaluator/freezer/tests pre-outcome, pero no ejecutar freezer hasta
que el gate real PASS esté committed. Outer 2024: sign fijo, open10:36→13:36,
hold180, 1bp; 2/3bps diagnóstico. Avance a 2025 requiere en los tres tickers
PF>1, WR>45%, neto>0 y min13/mes. La gate live PF>1,20/todos meses positivos
sigue separada.

Evaluator/freezer/tests ya implementados; suite total cross-venue/base capture
`45 passed`, Ruff/compile clean. Archivos nuevos:
`evaluate_cross_venue_calendar_rr_leader_v1.py`,
`freeze_cross_venue_calendar_rr_leader_v1_runner.py` y sus dos tests. Hacer add
explícito con siete handoffs+registry, commit/push. No ejecutar freezer: no
existe aún data gate PASS committed. Cuando exista, el orden es compactos ->
commit -> freezer -> force-add manifest -> commit -> único evaluator 2024.

Live audit read-only registrada en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_LIVE_PARITY_AUDIT.md`. No tocar servicios:
current feed back=weekly-Friday, no next-expiry; no endpoint bid/ask-IV; no
persistencia exacta de cuatro contratos 10:30→10:35; bot no tiene scheduler
one-shot cross-venue. Incluso cash PASS requiere después payoff option ask→bid
frozen. La futura implementación debe crear paquete/registry nuevo y conservar
paper intents, no reemplazar el package actual in-place.

Auditor post-seal nuevo:
`neural/jepa/audit_cross_venue_calendar_rr_native_clock_full.py` y test. Suite
combinada ahora `48 passed`; Ruff/compile clean. Quedan versionados con siete
handoffs y registry en este checkpoint. No ejecutar hasta `_seal`. Al completar:
`python neural/jepa/audit_cross_venue_calendar_rr_native_clock_full.py` ->
auditar summary/compactos -> force-add/commit/push evidencia -> data gate. El
auditor revalida raw/parquet/manifest y fuentes; no underlying/outcome.

Auditor data-gate nuevo:
`neural/jepa/audit_cross_venue_calendar_rr_leader_v1_data_gate.py` + test. Suite
combinada `53 passed`, Ruff/compile. Rehash 16.566 paths sin leer underlying,
recomputa gates/mapping y compara full capture index. Queda versionado con este
checkpoint. No ejecutar antes del builder real. Secuencia futura exacta: full
auditor -> commit compactos -> builder gate -> auditor gate -> commit compactos
-> freezer -> commit manifest -> outer 2024.

Condición live añadida por el usuario: no desplegar el mapping cross-venue por
su diseño 2023. Tras el full sidecar/data gate/freeze, probar 2024 primero, 2025
secuencial y 2026 al final. Solo si cada ticker cumple PF>=1,20, WR>=45%, >=13
trades por mes completado y PnL positivo mensual con ask→bid/hold30–180/no
overlap, incluyendo junio 2026 cerrado positivo y julio 2026 MTD shadow
positivo, se puede modificar `services/realtime_feed.py`,
`bots/tradingbot_wrapper_jepa.py` y systemd. Julio a 17/07 no es mes completo.
La integración inicial debe conservar `paper_order_intents=true`, producir
artefactos live-ready, pasar paridad y smoke de ambos servicios, y dejar
comandos VPS exactos. Si falla, documentar cierre y no tocar producción.

No lanzar full capturer: ya corre PID42112 desde d013a299, workers2, output
`D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1`. Logs
`cross_venue_calendar_rr_native_clock_full_2024_2025_v1.{stdout,stderr}.log`.
Checkpoint 03:01:334/3012,errors0. Monitorizar PID/progress.json/stderr. No tocar
capture code/dependencies. Si termina PASS, auditar y compactar; si muere,
inspeccionar `.staging` y contrato antes de cualquier resume. No outcomes.

Full code listo: `capture_cross_venue_calendar_rr_native_clock_full.py` y test
nuevo, suite combinada16/Ruff/compile. Add explícito ambos códigos/tests+siete
handoffs, commit/push. Desde HEAD limpio verificar output default inexistente y
ningún mismo proceso; lanzar con `Start-Process -WindowStyle Hidden`, workers2,
stdout/stderr a D:/ThetaData logs separados. Registrar PID/checkpoint. No
ejecutar builder económico durante captura ni abrir 2024 outcomes.

Antes del full: usar count correction, no la constante del seal. Exactamente
502 sesiones/ticker=1.506 y 3.012 role captures; ID SHA
`447e771b391f12dcfd7cba3692e65a7586dd4db2f3205311034616ddc7de5ce4`.
Commit/push aclaración+handoffs antes de implementar. Full script debe descubrir
este universo, ser atomic/resumable y fallar si el count/hash cambia.

Preflight sellado PASS y auditado. Output D:/ThetaData, seal
`d33e01a6...eee6d`, index `c0eadebf...42ad`; 24 captures/64.632 rows, cero
missing/extra/revised/crossed. Full projection 3.006 captures/8,095M/1,425GiB.
Versionar compactos+`CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT_RESULT.md`
y siete handoffs, commit/push. Después implementar full capturer inmutable y
resumible reutilizando exact semantics; commit/push antes de lanzar. No outcomes.

Implementado offline sealer en el mismo capturador con flag
`--seal-existing-staging`; test suite11/Ruff/compile PASS. Usa `git show` para
hashes exactos del capture base167118b0 y valida/reconstruye 24 captures sin
requester. Hacer add explícito código/test+siete handoffs, commit/push. Después
ejecutar `python neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py --seal-existing-staging`
con timeout suficiente. No lanzar workers de red. Auditar seal/index/cost.

Capture preflight materialmente completo pero no sellado. PID42584 acabó 24/24
después del timeout del wrapper; staging default contiene manifests/raw/parquet,
sin errors, missing/extra/revised/crossed=0 en todos. Output final/index/seal no
existen. No relanzar ni borrar. Seguir exactamente
`CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT_SEAL_CLARIFICATION.md`: commit
doc; implementar/testear modo offline sobre staging, pin capture base
`167118b0`, commit/push, ejecutar seal sin red, auditar. No outcomes.

Preflight implementado en
`neural/jepa/capture_cross_venue_calendar_rr_native_clock_preflight.py`, tests
`test_capture_cross_venue_calendar_rr_native_clock_preflight.py`: 9 passed,
Ruff/compile clean. Sample real exacto 12 sessions/24 captures; source inventory
hashes se calculan al run. Remoto `91.99.90.39:25503/v3` CONNECTED. Hacer
git-add explícito de código/test+siete handoffs, commit/push. Solo desde HEAD
limpio ejecutar default con `--workers 2`; no usar output alternativo ni abrir
underlying outcomes. Si PASS, compactar evidencia y diseñar full capturer desde
el seal; si error, preservar staging y cerrar/auditar antes de reintentar.

Familia activa: `CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md`. Se crea
por orden del usuario tras diagnóstico post-outcome; 2023 no es OOS. SPXW/SPY
ret corr0,999733/sign246/246, pero pressure corr0,580247/action same148/246.
Mapping fijo QQQ←QQQ, SPY←SPY, SPXW←SPY produce en design PF
1,173476/1,072835/1,071604, WR>50 aproximadamente, netos positivos y min19.
Solo7/5/5 meses positivos: progreso PF>1, no promoción.

Siguiente acción estricta: commit/push predeclaración+cierres+handoffs; luego
implementar capturador outcome-free y tests para 12 sesiones congeladas (primera
y última normal por ticker-año 2024–2025), dos expiries cada una, quote wildcard
1m 10:30–10:35. Exigir exact vintage Greek/IV key set, raw/parquet/manifest
hashes, JAR/runtime/provenance y auditar revisions sin reemplazar precios. Solo
después de preflight PASS autorizar full sidecar/data gate; no outcomes todavía.

Component breadth e index-ETF calendar sources ya cerraron sin outcomes. El
calendar-RR base a 2bps es PF0,999. No abrir 2024 hasta data gate y runner
committed; 2025/2026 permanecen cerrados. Producción intacta.

Calendar-RR cerrado con progreso parcial: pooled 739/PF1,058294/WR0,500676/
+729,690bps/12 de 36 cells; QQQ1,173476, SPXW0,912372, SPY1,072835. Auditoría
rehasheó 741 sources y recomputó todo. No rerun/outer/rescate sobre esta señal.
Force-add ocho outputs+independent audit, closure+siete handoffs+registry,
commit/push. Próxima familia debe aportar un mecanismo independiente que mejore
SPXW y estabilidad, no filtrar calendar-RR post-hoc.

Manifest calendar-RR generado en
`calendar_risk_reversal_pressure_v1_development_runner_frozen/manifest.json`,
SHA `f00a7ef096a70c6bb3dd9496c84137d54dcef6da163f2762dc3b3a7193d35f79`,
runner commit `79dfe416`, 741 eventos, outcome false. Force-add manifest+siete
handoffs+registry, commit/push; solo entonces ejecutar evaluator default una vez.

Calendar-RR evaluator/freezer pre-outcome listos: 12 passed/Ruff/compile.
Archivos `evaluate_calendar_risk_reversal_pressure_v1.py`,
`freeze_calendar_risk_reversal_pressure_v1_runner.py` y dos tests. Añadirlos con
los siete handoffs+registry, commit/push. Después ejecutar freezer default desde
HEAD limpio; no ejecutar evaluator hasta force-add/commit/push de ese manifest.

Calendar RR full data gate PASS desde `ef489bac`. Compactos copiados a
`calendar_risk_reversal_pressure_v1_202301_202312_v1_data_gate/`: feature SHA
`de0ec4b3...2858b`, manifest file `604f53b2...a9c1`, source inventory
`6f81e4f8...184d8`. 747/750, min19/mes, 3 errors causales documentados. No
outcomes. Force-add los nueve compactos (incluido independent audit), result doc
y siete handoffs, commit/push. Luego implementar evaluator/freezer análogo al
parity runner pero con estos hashes; no ejecutar antes de otro commit+manifest.

Builder calendar-RR listo sin outcomes:
`neural/jepa/build_calendar_risk_reversal_pressure_v1.py` y
`tests/test_build_calendar_risk_reversal_pressure_v1.py`, 8 passed/Ruff/compile.
Discovery 750 rows (250/ticker, min19/mes); smoke 20230103 de los tres tickers
válido. Hacer git add explícito de builder/test+siete handoffs+registry,
commit/push; luego ejecutar default target
`tmp/calendar_risk_reversal_pressure_v1_data_gate_202301_202312_v1` una vez.

Nueva familia pre-outcome: `CALENDAR_RISK_REVERSAL_PRESSURE_V1_PREDECLARATION.md`.
Antes se cerró exact-expiry OI delta por capacidad: 752 0DTE/ticker pero solo
156 con observación del mismo expiry el día previo, min4/mes. Calendar RR usa
front0DTE/next-expiry, t0 10:30 selection CALL/PUT25d, mismos contratos t1 10:35
y presión de diferencia de RR. 2023 tiene schema native para ambos; 2024–2025
mezcla fallback y queda cerrado. Siguiente: git add explícito/commit/push, luego
auditor outcome-free de inventory/native clocks/coverage. No outcomes todavía.

`OPTION_PARITY_PRESSURE_V1` está cerrado. Resultado one-shot/auditado: pooled
730 trades, WR0,486301, PF0,874751, net -1689,310bps, 10/36 cells. Por ticker:
QQQ PF0,946778/4 meses; SPXW 0,842979/5; SPY 0,819330/1. Los 744 sources y todas
las identidades fueron rehasheadas/recalculadas. No ejecutar otra vez ni abrir
2024–2026; no usar inverse o always-long como rescate. Force-add los nueve
archivos de evidencia más `independent_audit.json`, closure y siete handoffs;
commit/push. Luego elegir una familia físicamente independiente pre-outcome.

Manifest frozen generado en
`option_parity_pressure_v1_development_runner_frozen/manifest.json`, SHA
`f3819d881fa86c10002f35e943f6b893ddff03cf33f418dea8bca166d6526972`, runner
commit `5cc1c936`, 744 eventos 2023, outcome false. Force-add solo este manifest
y los siete handoffs, commit/push. Luego ejecutar una vez el evaluator al target
default inmutable y auditar antes de actualizar cualquier otra fase.

Implementación parity pendiente de commit/freeze: evaluator
`evaluate_option_parity_pressure_v1.py`, freezer
`freeze_option_parity_pressure_v1_runner.py` y dos tests nuevos pasan `13/13`;
Ruff clean. El run real no ocurrió. Hacer commit/push explícito de estos archivos
y los siete handoffs; desde HEAD limpio ejecutar freezer a
`option_parity_pressure_v1_development_runner_frozen/manifest.json`, force-add,
commit/push, y solo entonces ejecutar el one-shot 2023.

## Acción inmediata — OPTION_PARITY_PRESSURE_V1

V1R1 completó `PASS_DATA_GATE` desde `e560d026`: 2.256/2.256 sesiones, cero
errores, 2.256x28, mínimo 18 eventos mensuales, mínimo 4 strikes comunes y
coverage/distinctness PASS. Hash feature `45bca098...d5100`; inventario 5.953
fuentes `4a1fe920...f556`; manifest file `2b36e576...5fbc7`. Compactos en
`option_parity_pressure_v1_202301_202512_v1r1_data_gate/`. No hay PF/WR/PnL.
Secuencia estricta: commit/push compactos+handoffs, implementar y commit/push
runner 2023, one-shot desarrollo. Si cualquiera de las 36 celdas ticker-mes
falla PF>1,20, WR>45%, trades>12 o PnL>0, cerrar sin abrir 2024–2026. Si todas
pasan, freeze outer 2024–2025; 2026 permanece holdout.

**Actualizado:** 17 de julio de 2026, 00:30 Europe/Madrid

**Checkpoint de captura nativa:** `041b16c research: freeze stored-universe native clock coverage`

**Producción:** intacta. **Estado económico:** ninguna policy nueva cumple la
gate vigente. **Checkpoint autoritativo más reciente:** sección final.

## Checkpoint 14-jul-2026 — rotación económica persistente

`EXISTING_DATA_EXECUTABLE_UTILITY_V1` está cerrada y no se reabre. El registro
de familias está en `research_papers/JEPA/ECONOMIC_FAMILY_REGISTRY.md`.
La única familia autorizada para trabajo es `CROSS_MARKET_TRANSMISSION_V1`.

Hipótesis: transmisión/underreaction intradía entre SPXW, SPY, QQQ y TLT,
medida sobre 30 barras 1m completadas exactas, puede cambiar la distribución
ask-to-bid CALL/PUT. X0 son los 30 Pairwise; X1 añade enteros 28 beta/residual/
relative-RV/lead-lag/basis-z. No usar `ctx_*`, as-of, VIX ni outcomes para
construirlos. Modelo congelable: nueve cuantiles LightGBM por lado, utilidad
integrada y p(win)>=0,50. Desarrollo solo 2023-04..12; outer 2024-2025 permanece
cerrado hasta manifest committed. H-TPOVALUE1 queda en cola, no activa.

Predeclaración:
`research_papers/JEPA/CROSS_MARKET_TRANSMISSION_V1_PREDECLARATION.md`.
No hay capturas, sidecars, cambios live, apertura 2026 ni runner económico activo.

V1 fue detenido por causalidad antes de outcomes: el master conserva eventos y
paths stale tras el cierre de la media jornada 2022-11-25. El primer vector
indefinido fue SPXW 13:35 con RV=0. En dev 2022-2023, 126/357 filas de medias
jornadas cruzan el cierre en al menos un lado. V1 queda `FAILED_CAUSALITY`.

V1R1, única activa, excluye las nueve sesiones early-close completas por lista
calendar-only: 1.072 filas, dejando 96.553. No selecciona por outcome ni cambia
las 28 features, cuantiles, inner, scheduler o gates. 2024/2025 siguen cerrados.

V1R1 también cerró antes de outcomes: en 2024-05-30 11:10, SPXW solo tenía un
retorno no cero y el lead/lag del par SPXW/SPY era indefinido. La predeclaración
impide cero/epsilon/remoción/exclusión. Estado `BLOCKED_DATA`; no hubo dev/freeze.

Única familia activa: H-TPOVALUE1, developing value TPO target-only. X1 añade
36 features congeladas (SHA `73903b48...7c9f5`) al E0; cuantiles/scheduler/gates
se mantienen. Fuente exacta 09:30..t-1, 96.553 filas normales. 2024/2025 cerrado.

Antes del builder se congelaron también lattice floor inclusivo, TPO de 1m,
igualdades/denominadores y distinctness por ticker-año; no quedan decisiones
semánticas abiertas autorizadas.

La aclaración V1R1 fija el centro de POC y bordes VA, `value_location` sin
clipping y efficiency sobre 15/30 transiciones exactas; denominadores inválidos
fallan cerrado. Se versionó antes de materializar una sola feature TPO.

Requisito operativo añadido por el usuario: todo build/training/backtest largo
debe persistir checkpoints atómicos y reanudables. H-TPO lo hace por
ticker-sesión, revalidando source, keys, código, protocolo y output antes de
reutilizar. Mantener `.md`, commit y push en cada hito recuperable.

El data gate H-TPOVALUE1 ya terminó `PASS_EXACT_TPO_VALUE_VIEW`: 96.553x69,
2.777/2.777 sesiones, vista SHA `fded87a...078fe`, manifest SHA
`693a1708...1331`; mínimo distinctness 4 y máximo modal `0,9243992606`.
Una auditoría separada revalidó todos los source/checkpoint hashes. No se leyó
ningún outcome durante el build: todavía no existe PF, WR o PnL H-TPO.

Siguiente paso único: añadir checkpoints atómicos por fold al runner económico,
commit/push y ejecutar desarrollo nested 2023-04..12. No crear otra fuente ni
abrir 2024/2025 salvo que desarrollo cumpla todos los gates. Los archivos
`live_king_node.py` y `MASTER_KING_NODE_RECORD_V5.xlsx` son referencias
separadas y no autorizan modificar post-hoc H-TPO.

Checkpointing económico ya implementado y probado antes de outcomes: unidad
`outer_month/ticker/arm`, cuatro CSV atómicos y manifest último, con identidad
sellada por hashes. La repetición de prueba reutilizó 6/6 folds; suite focal
`33 passed`, Ruff clean. Tras commit/push, ejecutar directamente el desarrollo
2023-04..12 en el mismo target reanudable.

El desarrollo se cerró económicamente en la primera celda requerida. SPXW
2023-04 X1 tuvo 0/42 grids que pasaran inner enero-marzo: enero y febrero 0/42,
marzo 6/42. Near-miss 70/50 pooled: 68 trades, PF 0,921718, -1,831R. El outer
abstuvo y no se abrió; como todos los ticker-mes eran obligatorios, se detuvo
tras 2/54 folds. H-TPO queda `FAILED_ECONOMIC_DEVELOPMENT_EARLY_STOP`, sin
2024/2025/2026 ni cambios live.

Rotación única en cola: `KING-GEX-SLOPE1`. Primero auditar sin outcomes si las
fuentes 2022-2025 permiten net-GEX slope/sign flip causal y paridad. No copiar
del script King Node el reloj UTC-4, IV CALL para ambos rights, signs dealer,
derived Greeks o calibraciones 2026. El workbook no fue auditado porque el
runtime spreadsheet requerido no está disponible; no inventar conclusiones.

La factibilidad outcome-free pasó y la familia está predeclarada. Usa el
wall-state existente SHA `94e311...8ef`, invierte su signed-log y calcula slope
45m exacta desde 11:20. 109.785 filas; todos los meses 2023 conservan al menos
19 sesiones de señal por ticker. K0 nivel; K1 candidato solo cuando signo de
slope y nivel coinciden, con momentum/reversión por ret15. Sin entrenamiento,
grid ni threshold. Siguiente: runner checkpointed commit/push y desarrollo 2023.

Runner ya implementado: 72 celdas mensuales, carga física limitada a 2023 y
checkpoint por month/ticker/arm con hashes de código/source/protocolo/output.
Suite conjunta `26 passed`, Ruff y py_compile clean. Tras commit/push, ejecutar
una vez a `tmp/king_gex_slope_v1/development_2023_v1`.

Primer run paró antes de payoff por join invertido. El master tiene 20.309 keys
elegibles y coverage wall exacta 100%; wall tiene 8.668 keys adicionales que no
son oportunidades. Aclaración congelada: master-left exacto, sin fallback. El
target no llegó a crearse. Corregir runner, incluir hash del amendment, tests,
commit/push y relanzar. Todavía no hay métrica King.

Fix ya listo: master-left exacto, census 20.309 y signal census K1 13.286
fail-closed; amendment incluido en protocolo/checkpoint. `5 passed`, Ruff y
compile clean. Falta solo commit/push y relaunch.

## 1. Objetivo y gates no negociables

Obtener una policy causal, reproducible y live-equivalente para opciones 0DTE de
`SPXW`, `QQQ` y `SPY`. Cada ticker debe cumplir simultáneamente en walk-forward:

- PF `>=1,30`;
- WR `>=50%`;
- `>=18` trades en cada mes;
- PnL positivo en todos los meses;
- hold realizado de cada trade `>=30m`;
- entrada ask, salida bid y una sola posición por ticker.

No aprobar por métricas overall ni usar un mes para seleccionar lo que luego se
presenta como OOS.

## 2. Contrato live que no debe cambiar durante research

Paquete activo:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

Servicios:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

Runtime confirmado:

```text
entry=10:00-14:30 ET
exit=stop -60% / TP 1000% / trail 50% activation, 25% drawdown
min_hold=30m / max_hold=180m
risk=5000
paper_order_intents=true
```

| Ticker | Opción | Bucket | Máx/día | Cooldown |
| --- | --- | --- | ---: | ---: |
| SPX | SPXW | d25 | 4 | 0m |
| QQQ | QQQ | d35 | 2 | 30m |
| SPY | SPY | d35 | 1 | 0m |

El feed adquiere cada minuto; la policy vigente decide cada cinco minutos. El bot
no envía órdenes al broker.

## 3. Datos y cómputo

```text
D:/ThetaData/data_options/{SPXW,QQQ,SPY}
D:/ThetaData/data_underlying_derived/{SPXW,QQQ,SPY}
```

Hardware: RTX 5070 Ti 12 GB, Ryzen 9 32 hilos, 32 GB RAM. Usar CUDA
determinista cuando haya entrenamiento secuencial que lo justifique; para builds
por sesión usar 16 procesos como máximo inicialmente y para LightGBM tabular 28
hilos secuenciales. Más cómputo no autoriza OOS tuning.

## 4. Realidad de producción

El paquete static-union sigue siendo el contrato operativo, pero sus métricas
enero–junio 2026 no son un holdout limpio: modelos entrenados en 2025 y reglas,
thresholds y filtros seleccionados sobre los mismos meses 2026 reportados.

Auditoría inversa oct–dic2025, entrenando solo hasta septiembre:

| Ticker | Trades | WR | PF | Meses positivos |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 75 | 41,33% | 1,158 | 2/3 |
| SPXW | 64 | 43,75% | 1,686 | 2/3 |
| SPY | 125 | 34,40% | 0,794 | 0/3 |

Producción no se desactiva por esta auditoría, pero tampoco sirve como evidencia de
promoción para la nueva investigación.

## 5. Ledger de experimentos cerrados

No repetir estas vías sobre los mismos periodos salvo que aparezca una fuente
causal nueva o se corrija un defecto demostrable.

| Familia | Evidencia principal | Dictamen |
| --- | --- | --- |
| Baseline executable nested | 324 trades, WR 43,83%, PF 0,909, -9,287R | Causal, no rentable |
| Flat vs modal Phys-TD-JEPA | PF 0,900 vs 0,858; modal no mejora OOF | Modal/MJEPA cerrada |
| Historia 2025 vs 2022 | PF 0,863 vs 0,764; representación mejora, PnL empeora | Más historia no crea alpha |
| SMM/VISReg/proto/Gram | SMM v1 tenía targets enmascarados; controles posteriores no promovibles | Cola cerrada |
| Portfolio Var-JEPA | 0 configs económicas; incertidumbre-error negativa | Rechazado |
| PatchCore | distancia-error 10/15, pero 0/1.470 configs | Solo drift diagnóstico |
| AdaJEPA shadow | mejora latente 15/15, downstream 0/210 | Representación ≠ rentabilidad |
| h1 vs h6 | 0/210 configs; h6 empeora | No barrer horizontes |
| Spot momentum skip | 0/210 configs | No encadenar bloques genéricos |
| Return vs win GBT | return 15/15 abstain; win opera dos folds SPY negativos | Objetivo genérico cerrado |
| Early causal 5m/1m | 5m SPXW PF 1,109; 1m SPXW enero PF 1,220 y drift; QQQ/SPY abstain | Cadencia no era el cuello |
| Directional nested 1m | 60 trades, WR 36,67%, PF 0,976 | Momentum/contrarian cerrado |
| Gates de régimen | mejoras aisladas en feb2026, ninguna estable todos los meses | No cumplen contrato |
| Pairwise P1 | BA + en 57/99, mediana +0,004, p=0,117 | Lado casi aleatorio |
| Magnitude-weighted | 48/99 wins, PF 0,430 | No probar otros caps |
| Physics side skip | 55/99 wins; QQQ PF 0,409, SPY 0,810 | No contenía Greek walls reales |

## 6. Bugs reales ya corregidos

1. `opt_exit_minutes` ya era duración elapsed. Pairwise restaba además el minuto
   de entrada y anulaba todos los holds. V1r1 usa directamente la duración.
2. La primera regla wall llamaba rejection a una mera proximidad. Solo 29–37% de
   esos eventos habían cruzado el nivel. Wall V1r1 exige pierce real y regreso al
   lado defendido.
3. Otros fixes ya consolidados: provenance de folds abstain, no solapamiento,
   paridad de rejilla/cupos/cooldowns y current-time IB solo después de 10:30.

## 7. Resultado wall/IB más reciente

La prueba nueva sí usa Greek walls e IB previos, ausentes del physics skip.

- Join exacto de 86.729 eventos ask→bid `202208..202512`.
- Paridad uno-a-uno y spot idéntico; hashes de inputs `d3c37b5...a408` y
  `5f908e1...13b5`.
- M0 de proximidad pierde en todos: PF `0,872/0,903/0,935`.
- E1 magnet/rejection/acceptance: PF SPXW/QQQ/SPY `0,865/0,832/0,899`.
- V1r1 con rejection correcto: `0,910/0,845/1,008`; SPY +1,118R, pero WR
  47,58%, mínimo mensual 17 y solo 54,17% de meses positivos.

Señal parcial, no seleccionable post hoc:

- acceptance CALL muestra ~58–63% de dirección spot correcta a 30m en varias
  muestras, pero PF ejecutable cercano a 1;
- resistance-rejection PUT V1r1: SPY PF 1,536, SPXW/QQQ ~1,09;
- magnet CALL: QQQ PF 2,230 (42 trades), SPY 1,307 (25 trades);
- ninguna subfamilia tiene frecuencia ni estabilidad para 18/mes.

No retunar horas, niveles o direcciones por ticker sobre este output.

Artefactos:

```text
research_papers/JEPA/WALL_INTERACTION_EXECQUOTE_PREDECLARATION_V1.md
research_papers/JEPA/WALL_INTERACTION_EXECQUOTE_V1R1_REJECTION_SEMANTICS.md
neural/jepa/audit_wall_interaction_execquote_v1.py
neural/jepa/diagnose_wall_interaction_failure_v1.py
research_papers/JEPA/results/_diagnostics/wall_interaction_execquote_v1*/
```

## 8. Causa actual y nueva línea de investigación

El feature contract solo conserva ubicación/distancia. Un wall económico necesita:

- GEX y DEX por strike separados CALL/PUT;
- magnitud y concentración;
- dominio del primer strike frente al segundo;
- persistencia, edad y migración intradía;
- confluencia con IB/Fibonacci actual y D1–D5;
- régimen que diferencie magnet, rechazo y ruptura acelerada.

El strike de máxima/mínima exposición delta no existe en las 182 features actuales.
No sustituirlo por buckets de delta de contratos.

## 9. Trabajo activo al reanudar

Predeclaración creada:

```text
research_papers/JEPA/WALL_STATE_GEX_DEX_DATASET_PREDECLARATION_V1.md
```

Módulo de primitivas implementado y validado localmente, todavía no publicado en
este checkpoint:

```text
neural/jepa/wall_state_features.py
```

Calcula por timestamp CALL/PUT gamma wall, CALL/PUT delta wall, max/min net
GEX/DEX/DGEX, magnitudes, concentración, HHI/effective strikes, separación y lags
causales 5/15/30m. `tests/test_wall_state_features.py`: `4 passed`; suite wall
combinada: `9 passed`. Incluye test de OI duplicado, orden determinista, walls
separados, resets por gap/sesión y rechazo de columnas future/2026.

Builder por sesión implementado y preflight real aprobado:

```text
neural/jepa/build_wall_state_dataset.py
tests/test_build_wall_state_dataset.py
```

Lee únicamente Greeks+OI, fuerza 0DTE/cutoff 2025, limita a 16 workers, persiste
errores por sesión y audita cobertura/spot contra la vista executable. Suite wall
total tras el builder: `14 passed`.

Preflight central 2024, una sesión por ticker: `144/144` filas, cero errores,
cobertura de eventos `100%` overall/por ticker y diferencia spot máxima
`0,000572 bps`. Delta wall no es alias de gamma: misma strike en `9,03%` CALL y
`37,50%` PUT, con 8/10 strikes delta distintos. El primer runner falló antes de
leer datos por `sys.path`; se corrigió y añadió test CLI. La auditoría también
excluye explícitamente 10:30 porque el contrato congelado comienza 10:35 tras
cerrar el IB. Suite final: `15 passed`.

Evidencia compacta:

```text
research_papers/JEPA/results/_diagnostics/wall_state_gex_dex_preflight_v1/manifest.json
```

### Build completo aprobado

Commit de código `635d3e7`; 2.816 sesiones procesadas con 16 workers en 156 s.
Dataset local de 135.120 filas × 148 columnas, 2022-01-03..2025-12-31, SHA
`94e311e0...df8ef` (109.167.919 bytes). Cobertura de 95.424 claves executable:
`100%` overall y por ticker; spot max `0,000572 bps`, rejilla total `99,964%`.

Una sesión se excluye y reporta sin imputar: QQQ 2023-12-27 trae strikes Greeks
`.78` pero strikes OI enteros; la vista executable tampoco tiene eventos ese día.
El primer full build detectó además 23 desvíos spot QQQ 2022-06-17: el builder
usaba el quote `:30` futuro dentro del mismo minuto. El fix exact-time `:00`
eliminó todos los desvíos >1 bps y quedó cubierto por test.

```text
tmp/wall_state_gex_dex_202201_202512_v1/wall_state.parquet
research_papers/JEPA/results/_diagnostics/wall_state_gex_dex_202201_202512_v1/manifest.json
```

### Siguientes acciones exactas

1. Publicar el data gate completo.
2. Ejecutar la separabilidad física ya congelada en
   `WALL_STATE_PHYSICAL_SEPARABILITY_PREDECLARATION_V1.md`: D0 distance-only,
   S1 state y S2 state+IB, holdouts anuales 2024/2025 y 48 celdas por arm.
3. **Resultado:** REJECTED. 26.090 candidatos; S1 gana 17/48, mediana ΔAUC
   `-0,00154`; S2 gana 22/48, mediana `-0,000077`, `p=0,567`. Rejection/break
   queda cerca de azar y falla frecuencia mensual. No entrenar payoff.
4. Auditar/predeclarar como nueva fuente un proxy intradía de surface flow con
   OHLC `volume/count` completado en `t-1` y quotes bid/ask actuales cerca del
   wall. Comparar contra D0 sin retunar el wall-state rechazado.

Factibilidad aprobada en tres sesiones: quote válido cubre 90,10%/95,44%/91,33%
de filas activas SPXW/QQQ/SPY y 96,98%/97,32%/99,58% del volumen. Experimento
at-touch congelado en `WALL_SURFACE_FLOW_AT_TOUCH_PREDECLARATION_V1.md`; pendiente
implementar. El signo es proxy close-vs-mid, no aggressor observado.

Resultado completo:

```text
research_papers/JEPA/results/_diagnostics/wall_state_physical_separability_202208_202512_v1/
```

## 10. Git y worktree

Checkpoint de código publicado y sincronizado antes del seal: `041b16c`.
Hay numerosos scripts y artefactos untracked de trabajos anteriores; no borrarlos,
no añadirlos en masa y no asumir que son parte del checkpoint. Versionar cada hito
con `git add` explícito, test, commit y push.

## 11. WALL_SURFACE_FLOW_AT_TOUCH_V1R1 — estado exacto

La predeclaración V1 fue sustituida antes de outcomes por
`WALL_SURFACE_FLOW_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md`. Implementación outcome-free:

```text
neural/jepa/surface_flow_features.py
neural/jepa/build_wall_surface_flow_dataset.py
neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py
neural/jepa/freeze_wall_surface_flow_runner_v1r1.py
neural/jepa/wall_surface_flow_environment.py
neural/jepa/build_wall_native_quote_sidecar.py
```

La suite combinada relevante pasa `76 passed` tras añadir el censo semántico,
el builder de bundle y
el sidecar exact-Greek V1R2, además de las regresiones wall-state. El preflight real posterior
provenance y runtime más `14` regresiones wall-state). El preflight real posterior
a las correcciones produjo 8 filas × 173 columnas, 3/3 sesiones, cero errores,
grid completo y hashes/runtime persistidos en
`tmp/wall_surface_flow_at_touch_preflight_v1r1_schedulelock/`.

Tras auditar completos `options_bulk.py`, `script4_underlying_from_options.py` y
`thetadata_utils.py`, se añadió un segundo preflight en
`tmp/wall_surface_flow_at_touch_preflight_v1r1_underlyinggate/`: 3/3 sesiones,
cero grids RTH incompletos y spot máximo 0,000519 bps. El productor underlying
actual usa 1s→floor-minute y contiene zero-repair con `bfill`; los Parquets
históricos no guardan hash/strike/right de productor, así que esa limitación de
linaje queda explícita aunque el gate de contenido pase.

Auditoría estructural completa underlying: 2.519/2.519 sesiones utilizables,
minimum tick_count desde 10:19 = 60. Única anomalía: tres rows SPY 2023-06-05
09:54–09:56, antes de cualquier timestamp que pueda entrar en F0/labels. Se
cuentan en manifest, no se rellenan ni excluyen el día post hoc.

Correcciones congeladas antes de outcomes:

- barras OHLC `[s,s+1m)` y solo `bar_end<=t`;
- quote exacta al inicio de barra, sin floor de subminuto;
- colapso gamma/delta, exclusión dual-role y primer episodio contiguo;
- true rejection requiere pierce y terminal exacto `t+h-1`;
- horizontes no pueden cruzar cierre RTH del underlying (16:00; 13:00 half-day);
- decisiones half-day terminan 12:55 aunque QQQ/SPY options cierren 13:15;
- fechas de timestamps deben coincidir con la sesión declarada;
- runtime exacto congelado en `requirements-wall-surface-flow-v1r1.txt`;
- el data gate autoritativo exige cero relojes de opción no verificados.

Bloqueo activo descubierto sin labels: solo 1.078/2.519 sesiones y
128.362.954/325.753.830 filas Greek almacenan `timestamp` nativo. Las 1.441
sesiones fallback (key SHA
`4d4335005bb1ad29dd9f59a873a8902edcf17f1eb64c006792b29b57dea9a579`)
no pueden pasar por regularidad de rejilla. Auditoría completa:
`NATIVE_QUOTE_TIMESTAMP_PROVENANCE_AUDIT_20260712.md`.

ThetaData `/option/history/quote` recuperó en muestras el reloj nativo, bid/ask
exactos y `bid_size/ask_size`. El sidecar implementado exige builder commiteado,
Terminal local/JAR hasheado, raw HTTP inmutable y cobertura del 100% del universo
Greek histórico almacenado en 1.441/1.441 sesiones. Keys nativas extra se auditan
pero no se incorporan. Sizes quedan archivados pero fuera de H-FLOW1; serían
H-QSIZE1 separado.

Durante el backfill se corrigieron dos supuestos sin outcomes: crossed quotes se
preservan pero son no-signable; revisiones bid/ask del proveedor se auditan sin
sobrescribir Greeks. Ejemplos: QQQ 2024-02-06, 2.437/65.500 crossed; QQQ
2024-03-11, keys 65.500/65.500 pero 77 precios revisados. El sidecar aporta solo
clock nativo; F1 usa bid/ask originales. Provenance histórica sigue
`CONDITIONAL` si hay revisiones, aunque el clock key-set sea completo.
QQQ 2025-08-28 añadió 250 rows actuales de un contrato que no existía en el
Greek congelado: se archivan como `native_extra_key_rows` y no entran en F1.
El gate exige cobertura 100% de keys históricas, no igualdad que permita ampliar
retroactivamente el universo.

Backfill completado el 12-07-2026 sobre el JAR
`4f93cd745c8af53d8cf70096abb104edb22494f5c48408b9d732b51e51dfbbea`:

- status `PASS_NATIVE_TIMESTAMP_BACKFILL`, 1.441/1.441 sesiones y cero errores;
- 125.557.990 filas: QQQ 30.687.030, SPXW 59.051.140, SPY 35.819.820;
- cero keys históricas faltantes; 500 extras (250 QQQ, 250 SPXW) archivadas;
- 5.720 crossed quotes no-signable;
- 2.915 filas revisadas en 24 sesiones, sin sustituir bid/ask Greek;
- índice SHA `0abe0ac2f9dcccec4574ee10e4f10ef2904000c80a0cf5fb8f5a90ef333f754a`.

Siguiente secuencia, sin abrir outcomes:

1. commitear/pushear el seal e índice compactos;
2. ejecutar el full data gate con el índice ya integrado (`beb4435`);
3. commitear los compactos del data gate;
4. crear/commitear frozen runner manifest con provenance `CONDITIONAL` y live
   parity `BLOCKED`;
5. solo entonces construir labels físicos y ejecutar una vez F0 contra F1.

El primer intento de full data gate falló antes de crear output por
`Series.map(_truthy)`: `_truthy` ya esperaba la Series completa. El fix usa
`_truthy(series).all()` y añade test CSV real. La misma auditoría endureció el
attach: booleanos del seal deben ser JSON `true/false` exactos; JAR del índice
debe coincidir con el seal; rows deben ser positivas; los 1.441 raw responses y
manifests de sesión deben existir y conservar sus hashes sellados.

El segundo intento procesó 2.519/2.519 y fue rechazado, también antes de labels.
De 1.443 errores, 1.441 eran un bug de alcance: Greek full-session frente a
sidecar sellado solo para 10:20–14:29/12:54. El bridge corregido exige el grid
programado exacto (no min/max), filtra únicamente esa ventana y prueba el
contraejemplo de primer minuto ausente. Auditoría completa: 125.557.490 keys
Greek in-window compartidas y 500 extras; cero missing.

Los dos fallos restantes son QQQ/SPY 2022-12-30. En QQQ, los cinco candidatos
difieren 0,757–19,688 bps del derived open(t). El campo `underlying_price` de la
fila Greek 1m estampada t coincide 390/390 con el open 1s de t-1, mientras bid/ask
coinciden con t: snapshot híbrido del vendor, no sidecar. SPY tiene una diferencia
de 0,01 punto (0,264 bps) a 13:40. No tolerar ni excluir. Antes de relanzar hay que
predeclarar/probar una reconstrucción de spot y walls causalmente consistente;
si no es posible, V1R1 queda bloqueada por procedencia.

### V1R2 pre-outcome

La regla general se congeló antes de labels en
`WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md`. El auditor
`audit_wall_spot_semantics_v1.py` comparó todas las 120.864 rows wall in-scope
contra derived `open(t)` y `open(t-1)`. La ejecución autoritativa pasó exactamente
2.516/2/0 sesiones `exact_t/hybrid/unresolved`, cero unknown, manifest commit
`5c037ee`, census SHA `24d86299bd6b778b6f7042e985ca19f7790d13e89fc2731d8fbd17b14b9ff832`
e inventory SHA `7e7022d5...cf3d2`. El builder
`build_wall_exact_greek_repair_sidecar.py` captura la superficie coherente
first-order 1s de los 671 contratos positivos-OI almacenados (QQQ 285/SPY 386,
key SHA `57c99891a37fcde939df4a88de7f45a7dffd5be544c8730046bae45e109846c0`).

Cada contrato debe aportar las 48 decisiones exactas 10:35..14:30, dual clocks
iguales, spot<=0,001 bps de derived open(t), bid/ask<=1e-9 del Greek congelado,
sin floor/asof ni sustitución de contrato. Raw HTTP, proceso/JAR/Java, runtime y
fuentes quedan hashados; seal solo 671/671. La procedencia seguirá
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`. Después del seal hay que
reconstruir tanto wall state como spot/returns del event control y rehacer todos
los touches; un overlay solo de spot es físicamente inválido porque IV/delta 1m
pertenecen al snapshot híbrido.

La captura terminó PASS sobre commit `4de62f5`: 671/671 contratos, 32.208 exact
rows, cero errores y diferencias máximas spot/bid/ask `0.0`. Raw archivado:
671 respuestas, 4,013 GiB. QQQ aporta 285/13.680 y SPY 386/18.528. Index SHA
`7e5475f36d2163e188d721ea2f015c9a636db5bfbfede41dd8d0065a9382100a`;
seal SHA `3c267f83e5108c75c9f148624983b11f3f0708fde12cb58a8742278d194a8fc5`.
Siguiente: commitear compactos, construir 96 wall rows + control causal, congelar
sus hashes e integrar el overlay antes del full data gate.

`build_wall_exact_greek_repair_artifacts.py` ya implementa y prueba esa fase:
revalida todos los raw/contract/snapshot hashes, recompone walls con OI congelado,
reconstruye el grid físico de 96 controles desde `open(t)/open(t-lag)` y prueba
que el overlay no cambia filas ajenas. El primer build real reveló que el event
view solo tiene 47 keys objetivo (QQQ27/SPY20), no 96. La corrección congela SHA
`41dae9ad...5201`: walls/full-control siguen 96, event repair es 47 y no inventa
las otras 49 decisiones. Pendiente commit y relanzamiento autoritativo.

El relanzamiento pasó sobre commit `65289e8`: manifest/wall/event SHA
`47dffb25...aec5a` / `69a3d330...487d` / `937aa95e...051e`; 96 walls, 47 event
controls, full physical control grid 96, paridades `0.0` y cero cambios non-target.
El surface builder ya exige el bundle indivisible, congela los tres SHA y aplica
96/47 antes de `make_touch_candidates`; `authoritative_inputs` no puede pasar sin él.

Auditoría de frecuencia sin outcomes: H-FLOW first-touch tiene 10.078 timestamps
únicos. Aun con oracle, caps y sin no-overlap/cooldown, QQQ 202208–10 solo admite
14/9/9 y SPY queda <18 en 16/41 meses; SPXW min=30. Por tanto no puede ser una
policy final standalone. Un PASS físico autorizaría usarlo como componente de
alta convicción con fallback causal OOS, no relajar la gate mensual.

El primer full V1R2 procesó 2.519/2.519 sin errores y pasó coverage/grids/clocks/
spot/controls. Solo falló distinctness: QQQ 2022 `role_break_pressure_w1m` tiene
6 estados, [-1,1], zero 6,09%, missing 0; el código exigía 10 aunque el protocolo
solo decía nondegenerate. Antes de labels se añadió el documento separado
`WALL_SURFACE_FLOW_V1R2_DATA_GATE_CLARIFICATION.md` (no cambia el hash de la
predeclaración repair): >=2 estados, zero<99,5%, missing=0. Relanzar en output
inmutable nuevo; el primer manifest queda REJECTED como evidencia.

No existe resultado físico ni económico de H-FLOW1 todavía. Producción y todo
2026 continúan intactos; no crear `PLAN.md` porque no hay dirección rentable clara.

## PASS_DATA_GATE V1R2R1

El relanzamiento desde `a13d589` terminó `PASS_DATA_GATE`: 2.519/2.519 sesiones,
10.683 first-touch rows, 173 columnas y cero errores. Dataset SHA
`6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b`;
source-hash inventory SHA
`2a305a2910f83c42a3c32b455d9b3a93907c7d762c5168d0946f9ce1eae306e8`.
Pasaron coverage, exact native timestamp, completed-bar, schedule/half-day,
spot <=0,001 bps, control coverage y distinctness predeclarada. El dataset es
idéntico byte a byte al attempt REJECTED; solo cambió la interpretación del gate
congelada antes de outcomes.

Compactos autoritativos:

```text
research_papers/JEPA/results/_diagnostics/wall_surface_flow_at_touch_202208_202512_v1r2r1_data_gate/
```

El parquet sellado grande está en
`tmp/wall_surface_flow_at_touch_202208_202512_v1r2r1/`. No abrir labels ni PnL
hasta versionar un runner manifest que persista también
`exact_greek_repair_provenance`. A la fecha de este checkpoint no existe edge
físico ni económico demostrado para H-FLOW.

## Cierre one-shot H-FLOW1

La evaluación congelada 2024/2025 terminó y la familia se cierra sin payoff ni
retuning. Resultado: 24/24 celdas válidas; 4/24 favorables; mediana ΔAUC
`-0,029209`; Wilcoxon unilateral agrupado por ticker-fold `p=0,984375`; 14
pérdidas conjuntas AP/log-loss. Las 12 celdas primarias 30/60m fueron negativas.

| Ticker | Wins/8 | Mediana ΔAUC | Mediana F1 AUC | Wins 30/60 |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 0 | -0,045545 | 0,527228 | 0/4 |
| SPXW | 3 | -0,018642 | 0,557416 | 0/4 |
| SPY | 1 | -0,022390 | 0,560275 | 0/4 |

`physical_mechanism_pass=false`, `authoritative_physical_success=false` y
`advance_to_option_payoff=false`. No existe rentabilidad H-FLOW que reportar.
No usar resultados aislados SPXW 120/180m o SPY 180m: serían selección post-hoc.
La conclusión soportada es que volume/count/close-notional firmado 1/5/15m no
añade información estable a distance/approach. H-QSIZE1 (quote size/depth),
deformación IV/skew y confirmación futures/vol-complex permanecen sin probar y
son mecanismos distintos.

Artefactos compactos:

```text
research_papers/JEPA/results/_diagnostics/wall_surface_flow_at_touch_physical_202208_202512_v1r2r1/
```

## Nueva familia H-IVSURF1

Feasibility outcome-free comparó tres fuentes. H-QSIZE1 requiere recapturar
1.078 sesiones y no tiene paridad live; ES/NQ/VIX1D/VVIX están ausentes; VIX
histórico es un proxy contract-substitution-risky. Se eligió IV deformation
porque existe en 2.519/2.519 sesiones y midpoint IV ya forma parte de first_order
live. TLT está completo, pero queda como alternativa independiente y no se mezcla.

Predeclaración `WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md`
(commit `52c169c`). Compara los mismos strikes exactos CALL/PUT a
`t,t-1,t-5,t-15` dentro de 150 bps del wall; solo cambios de nivel, skew y
curvatura. No entran static skew, H-FLOW, bid/ask sizes ni outcomes. LR primaria
con imputación/standardization train-only; LGBM sensibilidad no puede rescatar;
Wilcoxon unilateral `p<0,025` por ser la segunda familia secuencial.

Builder/evaluator/freezer commit `9719ec2`. Build autoritativo:

```text
status=PASS_DATA_GATE
rows=10683
columns=54
dataset_sha256=9d9404fd721df927c30ce4d6edeee800f528df81cf14639c23da1dc4008bc2b3
minimum_ticker_year_both_valid=0.9031935737
minimum_ticker_overall_both_valid=0.9667312661
```

Todos los 2.519 Greek hashes, native clock y exact repair fueron revalidados;
control coverage y distinctness pasan. Producción/2026/outcomes siguen intactos.
Compactos: `_diagnostics/wall_iv_surface_deformation_at_touch_202208_202512_v1r1_data_gate/`.
Pendiente inmediato: congelar runner y ejecutar una vez el experimento físico.
No existe todavía PF/WR/PnL H-IVSURF1.

## Cierre H-IVSURF1 y siguiente fuente

El one-shot congelado entrenó 96 modelos y falla. LR primaria: 12/24 wins,
mediana ΔAUC `-0,001203`, p `0,890625`, 14 pérdidas conjuntas AP/log-loss.
LightGBM: 9/24, mediana `-0,005822`, p `0,921875`.

| Ticker | LR wins/8 | LR mediana ΔAUC | LR wins 30/60 | Dictamen |
| --- | ---: | ---: | ---: | --- |
| QQQ | 3 | -0,013621 | 1/4 | fail |
| SPXW | 4 | -0,003605 | 1/4 | fail |
| SPY | 5 | +0,001772 | 3/4 | LR ticker pass, no confirmación LGBM |

No promover SPY post-hoc. `physical_mechanism_pass=false` y
`advance_to_option_payoff=false`; no hay PF/WR/PnL H-IVSURF1. Compactos:
`_diagnostics/wall_iv_surface_at_touch_physical_202208_202512_v1r1/`.

La siguiente fuente autorizable es H-QSIZE1, preexistente como bloque separado:
bid/ask top-of-book size e innovación exact-contract. El sidecar actual cubre
1.441 sesiones; faltan 1.078. Completar y sellar esas sesiones antes de cualquier
label. No llamar update intensity a snapshots 1m. Provenance seguirá
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION` y live parity está bloqueada.

## H-QSIZE1 data gate y reparación pre-outcome

El complemento quedó sellado 1.078/1.078, 81.824.260 rows, index SHA
`a9c3a8c0...eef9`; combinado 2.519/2.519. Se excluyen 63.500 provider-added
keys mediante pertenencia Greek exacta por timestamp. El primer build V1
preservó 10.683 candidatos y pasó coverage/control, pero fue `REJECTED_DATA_GATE`
porque seis ticker-year de `local_signable_fraction_change` eran constantes
cero. Minimum annual both-valid 0,984772; minimum ticker 0,988372. No labels ni
outcomes se abrieron.

La causa es un bug de contrato: signable fraction es calidad y contradecía el
amendment audit-only. V1R1 se predeclara sin outcomes y mueve los 8 campos de
signability al audit; F1 usa 32 qimb/depth fields, todos con >=158 valores por
ticker-año. La evaluación usa complete cases iguales F0/F1, sin missing
indicators/native missing branches. V1 rejected queda versionado en
`_diagnostics/wall_quote_size_pressure_at_touch_202208_202512_v1_rejected_data_gate/`.

Siguiente acción exacta: commit/push V1R1, rebuild a target nuevo, congelar data
manifest/runner y ejecutar una sola evaluación física LR/LGBM. 2026 y producción
siguen sin tocar; todavía no hay rentabilidad H-QSIZE.

H-QSIZE1R1 data gate ya es PASS: 10.683x76, dataset SHA `f4ed7b23...6c49`,
source SHA `9128ac47...e8a3`, minimum ticker-year both-valid 0,984772 y minimum
ticker 0,988372. Todos los 32 pressure fields pasan distinctness; 2.519 fuentes,
exact keys y controls pasan. Compactos están en
`_diagnostics/wall_quote_size_pressure_at_touch_202208_202512_v1r1_data_gate/`.
Congelar runner solo después de commitear/pushear esos compactos; luego ejecutar
una vez LR/LGBM. No abrir 2026 ni option payoff antes del physical PASS.

El runner congelado `81f1ba8` ya ejecutó el one-shot y H-QSIZE1R1 falla: LR
6/24, mediana ΔAUC -0,014823, p 0,890625; LGBM 5/24, mediana -0,020959.
QQQ/SPXW/SPY LR wins 1/8, 4/8, 1/8 y primarias 1/4, 2/4, 0/4. Frequency pasa,
pero physical/payoff son false. Cerrar snapshot QSIZE; no hay PF/WR/PnL nuevo.

Próxima fuente realmente distinta: dinámica intraminuto local (quote update
intensity, replenishment/withdrawal), solo tras preflight sin outcomes de API,
coste y live parity. No reutilizar el mismo snapshot block con otro modelo.

H-QDYN1 está predeclarado: tick NBBO exact-wall durante `[t-32s,t-2s)`, CALL+PUT,
28 features de intensidad/replenishment/withdrawal, sin snapshot levels. Un
preflight determinista 24/24 obtuvo wall exacto y timestamp causal; estimación
37,4M rows/6,34GB. Builder outcome-free e immutable listo; commit/push antes de
capturar. La allowlist causal `t-5m` cubre 9.833/10.683. Same-ms duplicates no
ordenan deltas. p secuencial `<0,0125`, 2026 y
live parity bloqueados.

Gate económica aceptada por el usuario el 2026-07-12: PF >=1,30, WR >=45% y
>=12 trades/mes pueden valer, pero solo en WF cronológico puro con ask->bid,
no-overlap y contrato live reproducible. La auditoría de lineage invalida los
697 trades antiguos: 338 usaban IB/Fibonacci completo futuro antes de 10:30.
El paquete causal actual de 416 trades también falla el validator actual por
selección 2026 solapada, `legacy_ohlc`, 55 overlaps y contrato no declarado.

El benchmark exacto existente
`event_option_execquote_causal1030_nested_exploratory_202601_202605_v1` sí usa
ask->bid, 0DTE, min/max hold y cero overlaps, pero pierde en los tres tickers:
QQQ PF0,984/WR44,68/min15; SPXW PF0,832/WR42,99/min10; SPY
PF0,919/WR43,90/min19. No existe artefacto que pase simultáneamente todos los
contratos. La curva legacy WF Jan-Jun no es OOS de policy y no es repricing
ejecutable. Continuar desde datos `executable_quote`; H-QDYN1 sigue siendo la
nueva medición causal predeclarada, no una rentabilidad demostrada.

Checkpoint H-QDYN1R1: auditor adversarial paró la captura V1 porque el radio
`t-5m` no probaba listing exacto. Amendment y builder exacto versionados; audit
2.519/2.519 PASS. Todos los 10.683 candidatos tenían CALL+PUT exactos en
`t-5m`; 9.833 sobreviven el radio. Proof SHA `083a77f3...927623c`, manifest
`2188a2cf...021a5`, eligible IDs `f77dc223...6a2eca`. Los parciales V1 y V1R1
quedan rechazados. Capturador V1R1R1 requiere proof, evidencia Terminal completa,
contract-block audit, quarantine de staging y revalidación integral. Feature
builder outcome-free y runner físico congelable listos. Suite focal `31 passed`;
sin labels ni PnL H-QDYN. Clarificación: raw non-finite/crossed se preserva,
size-only excluye cambios de exchange, conditions no entran como alpha y strike
usa igualdad literal.

Último audit: exchanges `inf` también quedan fuera de pares válidos; suite focal
`31 passed`, sin blockers materiales conocidos. H-QDYN V1R1R1 continúa captura.

H-GREEK2WALL-DIRECT-ALL-V1 queda predeclarado outcome-free como siguiente fuente
independiente. OI previo está resuelto por docs oficiales (~06:30, cierre día
previo) y ThetaData `/greeks/all` da directamente vanna/charm/vomma/zomma con
timestamp. Tras H-QDYN, ejecutar solo preflight 12 sesiones y medir coste/paridad;
no full build ni outcomes. IB/Fib estático/día-condicional está cerrado; solo
presión dinámica sobre los ocho niveles fijos sería nueva y exige otra captura.

Captura activa H-QDYN V1R1R1: output
`D:/ThetaData/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1`, PID
`36564`, checkpoint 5.257/9.833 (53,46%), cero errores al 2026-07-13 00:24
Europe/Madrid. No duplicar proceso. Siguiente secuencia: esperar seal, ejecutar
builder/data gate outcome-free, versionar compactos, freeze y un one-shot físico.

Checkpoint H-QDYN1R1R1 sellado: `PASS_QDYN_CAPTURE`, 9.833/9.833 eventos
elegibles de 10.683, 37.846.658 ticks (CALL 18.915.243; PUT 18.931.415), cero
errores y cero zero-right. Index SHA
`9a4924df1f60203d3f6ee1217520d4a0b0d287a82b816b898be3d2579e1b4f03`;
eligibility SHA
`09df83191ba83f0fe8db86e2a8bcc59b278c03668c1fd4506480123a585ee2e1`.
Provenance `CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`; no se abrió 2026,
outcomes ni producción.

El primer intento de data gate falló cerrado y pre-outcome: `set_index` quitaba
`event_id` antes de la revalidación. Fix + regression test commit `85de313`,
suite focal `26 passed`, pushed. El relaunch inmutable está corriendo. Esperar
`PASS_DATA_GATE`, commitear compactos, congelar runner en otro commit y ejecutar
una sola vez F0/F1. No hay resultado físico/económico y no se autoriza payoff
sin physical PASS.

H-QDYN1R1R1 queda `CLOSED_DATA_GATE` sin outcomes. El target inmutable
`tmp/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1` produjo 10.683x67,
dataset SHA `2a7147cc...fb265a`, source SHA `a65f4435...73398` y
`REJECTED_DATA_GATE`. Coverage sí pasa (mínimos anual/ticker
`0,8942084942084942/0,9072749691738594`); distinctness no: 16 fracciones de
cambio de exchange SPXW 2022–2025 son cero constante y dos state-change SPXW
2025 son uno constante. El contrato congela cierre ante cualquier feature con
menos de dos estados por ticker-año. No freeze, labels, modelo, payoff, retirada
de features ni rescate. `85de313` arregló un bug previo no causal; capture seal
válido. HEAD del cierre `d2c23ec`. Próxima acción única: preflight H-GREEK2WALL
de 12 sesiones.

H-QDYN closure ya está commit/push `30ba9d5`. El preflight H-GREEK2 fue
implementado y pushed en `2f6f262`, `e0a8116`, `54c6fb4`, `7201cfd`; `12 passed`.
Contrato: 12 sesiones congeladas, direct all-Greeks y direct OI atómicos, source
clarification y provenance remota. Inventory V1R2 PASS sobre `7201cfd`, hashes
CSV `829ef754...`, JSON `88b84f2a...`, builder `f8937f68...`; sin 2026,
outcomes ni cambios de producción.

Bloqueo operativo actual: local all-Greeks responde HTTP 403 porque STANDARD no
incluye el endpoint PROFESSIONAL. Remoto `91.99.90.39` llegó a MDDS CONNECTED,
pero devolvió 478 invalid session por sesión duplicada/stale. Ninguno creó
output. Terminal local detenido. En VPS había un launcher systemd
`thetadata_feed` PID 916/worker 1828 y realtime/ai activos. Sin sudo no se pudo
reiniciar; shutdown oficial OK mató solo el worker, launcher siguió activo y no
hubo restart systemd. Luego la IP origen perdió TCP 22/25503 con ping aún vivo,
posible filtro temporal. Restaurar servicio/Terminal remoto y capturar exactamente
12; si no hay entitlement/datos, marcar H-GREEK2 bloqueado. No hay alpha/PnL.
Gate económica PF1,3/WR45%/min12 aceptada pero todavía intocada.

H-GREEK2WALL queda cerrado `BLOCKED_SOURCE_ENTITLEMENT`. El remoto volvió con
un único Terminal PID 954, MDDS CONNECTED y los tres servicios
thetadata/realtime/ai activos. Inventory V1R3 PASS sobre `20b9325` (CSV
`829ef754...dce53`, JSON `88b84f2a...220f`, builder `bf8fda05...bad0`),
`13 passed` y Ruff clean. La primera sesión congelada SPXW 2022-08-01 recibió
HTTP 403 en el host remoto exacto: STANDARD no autoriza `/greeks/all`
PROFESSIONAL. Status SHA `1f914c43...dcc5`; error SHA `13650acb...1bb9`.
Falló antes de direct OI y no existe output/staging/raw/parquet que reanudar.
No hubo labels, modelo, payoff, acceso a 2026 ni cambios de producción.

No rescatar H-GREEK2 con fórmulas locales presentadas como fuente directa. La
siguiente fuente independiente ya separada es H-IBQDYN1: dinámica NBBO dirigida
sobre los ocho niveles IB/Fibonacci fijos, disponibles solo desde 10:30. Debe
tener predeclaración, listing proof y captura propios; no reutilizar H-QDYN.

Objetivo económico actual del usuario: cada ticker debe cumplir PF>=1,30,
WR>=50%, mínimo 18 trades en todos los meses, hold>=30m y PnL mensual positivo
en walk-forward; junio 2026 sigue cerrado. Esto sustituye como objetivo de esta
investigación la antigua relajación WR45%/min12, sin validar nada retroactivamente.

H-IBQDYN1 quedó predeclarado/pushed `9464c08` antes de cualquier tick nuevo;
`6 passed`, Ruff clean. Universo causal separado: ocho niveles IB/Fib completos,
10:35+, primera oportunidad por bloque de 30m, SPXW d25 y QQQ/SPY d35; 16.926
eventos sin outcomes. Listing proof completo PASS en 2.519/2.519 sesiones:
16.852 elegibles, SPXW 5.858/5.858, SPY 5.660/5.660 y QQQ 5.334/5.408. Los 74
QQQ ineligibles quedan explícitos (21 both, 31 CALL, 22 PUT), sin sustitución.
Los 12 eventos del preflight pasan. Proof SHA `b1fc6613...306d2`, eligible IDs
`8e68c12c...652e`, inventory `35a569bd...01c2`.

Capacidad OOS 2024/2025 con hold30/no-overlap y caps actuales: min mensual
QQQ35/SPXW69/SPY19, por lo que no está matemáticamente bloqueado aunque SPY solo
tiene margen uno. Compactos:
`research_papers/JEPA/results/_diagnostics/h_ibqdyn1_listing_feasibility_202208_202512_v1/`.
Siguiente: código commit/push para capturar únicamente 12 eventos/24 contratos,
then remote tick preflight and cost seal. Full capture solo si <=150M rows,
<=20GiB raw y ningún right vacío. Sin labels/PnL/2026/producción.

H-IBQDYN1 tick preflight ya es PASS. Captura commit `c823d86`, features commit
`68ed6b3`, full resumible commit `62b3d98`. Resultado: 24/24 contratos, 43.680
rows (21.297 CALL/22.383 PUT), cero errores/zero-right. Proyección 61.341.280
rows, 9,6427GiB raw, 1,1551GiB parquet, bajo gates 150M/20GiB. Index
`d0275e2d...06c5f`, cost `20c34643...2731`.

Audit de las 20 features outcome-free: 12/12 both-valid, todas finitas, 0/60
celdas ticker-feature degeneradas, distinctness min4; mínimos 597 alpha states
y 488 ordered pairs. Compactos en
`_diagnostics/h_ibqdyn1_tick_preflight_202208_202501_v1/`.

Full capture activa en `D:/ThetaData/h_ibqdyn1_ticks_202208_202512_v1`, PID
44892; inicio confirmado 100/33.704, cero errores. No duplicar. Secuencia única
después del seal: full feature/data gate -> commit compactos -> frozen LR/LGBM
F0/F1 -> un outcome físico -> si PASS completo, un payoff ask->bid. No otra
familia. Amendment 2026: Jan-May solo final fit/estrés tras PASS; junio sellado;
julio shadow. Todavía no hay modelo económico ni PF/WR/PnL H-IBQDYN1.

Data-gate contract/code quedaron preparados pre-outcome: F0=18 controles
distancia/aproximación/RV/hora; F1=F0+20 ticks. El builder rehashará 33.704
contratos, mantendrá 16.926 filas incluidas las 74 no listadas y exigirá >=80%
both-valid ticker-año, >=85% ticker, distinctness y máscara idéntica. Suite
focal `19 passed`. Captura PID44892 llegó a 2.200/33.704 a las 11:28, errors=0.

Evaluator/freezer físico también quedan listos pero bloqueados hasta compactos
PASS committed: LR L2 primario, LightGBM no rescatable, 24 celdas, p<0,0125.
Suite focal ahora `26 passed`. Captura 3.200/33.704, errors=0. No AUC/labels/PnL.

Payoff one-shot ya está predeclarado pero dormido hasta physical PASS: usa solo
LR F1 60m, boundary 0,5 y mapeo físico rejection/break a CALL/PUT; no entrena ni
selecciona con retornos. Scheduler causal ask->bid y gates del usuario exactas;
cualquier fallo cierra la traducción sin tuning.

Economic evaluator/freezer ya implementados y testados; verifican physical PASS
antes de outcomes, rehash de seis modelos LR y replay causal sin ranking/backfill.
Tests economic+physical+data `19 passed`. Captura 4.900/33.704, errors=0.

## H-IBQDYN1: primera pasada full y reparación 472 congelada

La primera pasada finalizó los 33.704 futures sin seal porque cuatro requests
agotaron tres intentos con HTTP 472. El directorio contiene exactamente 33.700
raw, 33.700 parquets y 33.700 manifests, todos sin staging; no queda capturador
Python activo y el túnel SOCKS `127.0.0.1:1081` sigue vivo. QQQ está completo.

Los cuatro ausentes son los dos rights de dos eventos `ib_low` a 10:35 ET del
2023-10-25: SPXW event `60d8c2b0bec9c102a94d851b` CALL4230/PUT4185 y SPY event
`f4a0e57699fbd8b67cee8937` CALL421/PUT418. Error file SHA
`e4dc58192b18944778fe819a397d03c9e4e5fb2a29870b7de63ca1b500859af7`;
inventory SHA `4a44551fde020af61174b9e70162122441b6c5736f3e274b988f6f66104238a7`.

Con MDDS CONNECTED se reintentaron las cuatro URLs exactas por el mismo túnel:
todas repitieron status 472 y cuerpo `No data found for your request`, body SHA
`101a4aa84466574e08fbb09d1405a816323a4674fd107dc28f3f0d29e3e3708c`.
La documentación oficial clasifica 472 como `NO_DATA`. No es válido ampliar 30s,
usar at-time/as-of, nearest strike ni otro contrato.

El full sealer ya permitía rows=0 y registra `zero_row_contracts`; el data gate
espera both-valid <100%. Se congeló antes de outcomes
`H_IBQDYN1_HTTP472_NO_DATA_AMENDMENT.md`: conservar byte-exact raw 472, parquet
vacío con schema, manifest V1R1 y `capture_kind=HTTP_472_NO_DATA` solo para esos
cuatro. Los 33.700 existentes no se reescriben y deben revalidarse con sus
hashes originales. Los dos eventos quedan explicitamente both-invalid, no son
missingness alpha y cuentan contra cobertura.

Próximo paso único: commit/push del protocolo; implementar/testar el sealer y
validator V1R1; producir index exacto 33.704 con cuatro zero-row, cero unresolved
y cero staging; luego actualizar handoffs/commit/push y ejecutar el data gate.
No hay outcome físico, PF/WR/PnL, acceso 2026 o cambio de producción.

## H-IBQDYN1 capture seal V1R1 PASS

El sealer committed `7a58259` terminó en 702,7s y publicó
`PASS_H_IBQDYN1_FULL_CAPTURE`. Revalidó integralmente los 33.700 artefactos
originales sin reescribirlos; los cuatro contratos congelados devolvieron tres
veces más HTTP472 exacto y quedaron como raw `response.txt` de 30 bytes,
parquet vacío con schema original y manifest V1R1.

Evidencia final:

- 33.704 contratos únicos y 16.852 eventos exactos;
- 58.212.529 ticks: CALL 28.761.918, PUT 29.450.611;
- cuatro `HTTP_472_NO_DATA`, cuatro zero-row, cero unresolved/errors;
- 33.704 parquets y manifests, 33.700 raw JSON + cuatro raw text;
- cero directorios staging y sin `errors_latest.json` residual;
- index SHA
  `a3841779c8603a96d4863a4e1495feec4a6c98d4fee490a204881b05d146e14c`;
- candidate SHA
  `684f68b1737a4c7cf82aa1974c9656946ffe79d92dfd6b0b2f04914fab4431e5`;
- raw/parquet bytes `9.841.523.910/1.177.902.621`;
- capture commit `7a58259ebd08936daa83370a24b8022e45b504a4`;
- provenance condicional remota y live parity bloqueada.

Compactos copiados a
`research_papers/JEPA/results/_diagnostics/h_ibqdyn1_ticks_202208_202512_v1r1_capture_seal/`.
La próxima acción es commit/push de esos compactos y los cuatro handoffs, luego
build/data gate outcome-free al target nuevo
`tmp/h_ibqdyn1_features_202208_202512_v1`. No congelar runner ni abrir labels
hasta `PASS_DATA_GATE`. No hay rentabilidad nueva ni acceso a 2026/producción.

## H-IBQDYN1: primer build detenido pre-output y reparado

El primer build leyó/revalidó las 2.506 sesiones subyacentes y construyó los
16.926 measurement rows, pero falló antes de escribir staging/output con
`final dataset missing ['causal_subscription_eligible']`. La causa fue una
colisión de la misma columna outcome-free en controls y measurements, que el
merge convertía en dos columnas sufijadas. No fue `REJECTED_DATA_GATE`, no hay
dataset parcial y no se abrió ningún label/outcome.

El commit pushed `781806d` añade un merge fail-closed: conserva la elegibilidad
del proof solo tras comprobar igualdad exacta one-to-one con la vista de
measurements y rechaza missing/mismatch. La regresión y toda la suite focal pasan
`43 passed`; Ruff está limpio. Siguiente comando único: relanzar desde HEAD
limpio al target nuevo `tmp/h_ibqdyn1_features_202208_202512_v1r1`, publicar el
compacto solo si resulta `PASS_DATA_GATE`, y abortar si falla coverage,
distinctness, identidad o complete-case. Aún no hay AUC, PF, WR ni PnL.

El relaunch V1R1 a 16 workers completó RV y alcanzó 12.000/16.926 eventos,
pero murió pre-output por `MemoryError` dentro de un worker al rehashear un raw.
No existe target/staging V1R1, no es `REJECTED_DATA_GATE` y no se abrieron
outcomes. La siguiente ejecución debe usar target inmutable
`tmp/h_ibqdyn1_features_202208_202512_v1r2` y `--workers 8`. Solo cambia el
paralelismo para limitar el pico RAM; no cambia ninguna observación, hash,
feature, gate o contrato. No repetir V1/V1R1 ni 16 workers.

## H-IBQDYN1 data gate V1R2 PASS

El relaunch con 8 workers completó en 2.590,4s y publicó `PASS_DATA_GATE` desde
commit `619ac5afcc85d885e159d9dd858768a93630fc21`. Resultado exacto: 16.926 filas,
72 columnas, 16.852 eventos causalmente elegibles y 16.849 both-valid. Dataset
SHA `675a760335b5d03085b3a66daec34598e95842fcd11899dde66a7c6e163d9a09`;
source inventory SHA
`70ff4cf6d8703dd22fbc20a4881d84bb0f0f5c43906c0cd968eaa789b04763c4`;
underlying inventory SHA `2a305a29...ae306e8` y capture index SHA
`a3841779...46e14c`.

Todos los gates outcome-free pasan: rows preservadas, cobertura, 18 controles,
20 alpha features, distinctness y complete-case parity F0/F1. Mínimo anual
both-valid `0,9631171921` (QQQ 2024), mínimo ticker `0,9861316568` (QQQ) y
distinctness mínima 79. Las tres invalidaciones explícitas son una QQQ 2025 y
los dos eventos 472 SPXW/SPY 2023; permanecen en el denominador.

Compactos copiados byte-identical a
`research_papers/JEPA/results/_diagnostics/h_ibqdyn1_features_202208_202512_v1r2_data_gate/`;
el parquet de 5,54MB permanece en `tmp/h_ibqdyn1_features_202208_202512_v1r2/`.
Siguiente secuencia: commit/push compactos+handoffs; generar manifest del runner
físico desde ese HEAD limpio; commit/push del freeze; ejecutar exactamente una
evaluación F0/F1. Todavía no se abrió label, AUC, PF, WR, PnL ni 2026.

El freezer ya produjo el manifest `PREEXECUTION_FROZEN` sobre HEAD `3f19eb4` en
`_diagnostics/h_ibqdyn1_physical_202208_202512_v1_frozen_runner/manifest.json`;
SHA `f80f967a17a7b30fa7c6f728d620d343d1dd076c36dba8790a0e0f9c407ac85a`.
Congela F0=26 columnas (18 controles + 8 level identities), F1=46 (F0+20 tick),
LR L2 primaria, LightGBM confirmatorio no rescatable, folds 2024/2025 y
horizontes 30/60/120/180. Registra 2026 cerrado, producción intacta y payoff no
autorizado. Siguiente acción: force-add/commit/push del manifest y ejecutar una
sola vez `evaluate_h_ibqdyn1_physical.py`; ese será el primer acceso a labels.

## Cierre científico H-IBQDYN1

El único one-shot se ejecutó desde commit `72dff1c` y publicó 96 modelos, 24/24
celdas pareadas válidas y `CLOSED_PHYSICAL_GATE`. La LR primaria falla de forma
clara: 7 wins (gate 16), mediana ΔAUC `-0,0040319288` (gate `>=0,01`) y
Wilcoxon unilateral `p=0,921875` (gate `<0,0125`). Tuvo 10 pérdidas conjuntas
AP/log-loss; esto queda dentro del máximo 12 pero no compensa los otros fallos.

| Ticker | Wins | Mediana ΔAUC | Mediana AUC F1 | Wins 30/60m |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 3/8 | -0,001953 | 0,549042 | 1/4 |
| SPXW | 3/8 | -0,002884 | 0,532689 | 2/4 |
| SPY | 1/8 | -0,008276 | 0,543853 | 0/4 |

LightGBM sensibilidad también falla: 8/24, mediana ΔAUC `-0,0058472586`,
p `0,890625`; QQQ/SPXW/SPY 2/8, 4/8, 2/8. El aparente SPXW 3/4 en 30/60m
LightGBM no pasa el ticker completo y no puede rescatar la LR.

Frequency gate pasa: 288 month cells, todas con dos clases y mínimo 45 episodios
resueltos frente a 18. El fallo no es falta de oportunidades; es ausencia de
mejora física estable de F1 sobre F0. Resultado final:
`physical_mechanism_pass=false`, `authoritative_physical_success=false`,
`research_payoff_authorized=false`, `advance_to_option_payoff=false` y
`production_live_ready=false`.

No ejecutar el economic replayer ni inventar PF/WR/PnL. Jan-May 2026, junio
2026 y producción permanecen intactos. No rescatar por QQQ 120m, SPXW LGBM,
nivel/ticker/horizonte/subgrupo. Compactos byte-identical en
`research_papers/JEPA/results/_diagnostics/h_ibqdyn1_physical_202208_202512_v1/`;
manifest SHA `13cd1e35b7b17bc59ff40496cc71482a0cd9cb202962d8c8c9a9efe38bc7af41`,
summary SHA `4c0b651d...e701566`. H-IBQDYN1 queda cerrado y no existe un modelo
rentable nuevo. No hay otra familia activa autorizada; la siguiente investigación
debe ser una hipótesis causal realmente distinta y predeclarada, no una variante
de las familias cerradas enumeradas en este handoff.

## EDGE-FIRST EXISTING-DATA SPRINT V1 — checkpoint económico 1

Se reprodujo byte-for-metric el benchmark executable-quote publicado sin abrir
outcomes 2024/2025: QQQ PF 0,983707 (94 trades), SPXW 0,831520 (107) y SPY
0,919499 (123). La búsqueda publicada permitía dos SPY/día; el replay diagnóstico
con el scheduler actual de uno/día deja SPY en 93 trades, PF 0,971936, PnL
-0,773R y mínimo mensual 14. No hay solapes, holds fuera de 30-180m ni violaciones
de cooldown en las trades reproducidas.

El oracle dev-only abril-diciembre 2023 separó error de oportunidad y lado. El
baseline causal pierde en los tres tickers; lado oracle sobre oportunidades
causales produce PF 5,838/9,811/8,315 (SPXW/QQQ/SPY). Always CALL, always PUT y
random congelado pierden. El drag de ejecución no puede estimarse con los
artefactos disponibles porque no existe payoff midpoint emparejado. Código,
manifest, trades y métricas están en
`existing_data_edge_sprint_v1_benchmark_oracle/`; suite `4 passed`, Ruff clean.
2026 y producción permanecen intactos.

## EDGE-FIRST V1 — predeclaración y runner dev

La única familia `EXISTING_DATA_EXECUTABLE_UTILITY_V1` está predeclarada. E0
conserva los 30 features Pairwise ordenados; E1 tiene 527 al añadir bloques
existentes completos y exactos. H-FLOW1/H-IVSURF1/H-QSIZE1R1 quedan fuera por
join one-to-many no congelado; H-QDYN1/H-GREEK2 quedan fuera por rejected gate/
source missing. La vista outcome-free exacta conserva 97.625 keys, SHA
`52bac061216dd8aac7423449c442577882484aad0c4220bddaabc14544faad36`, y es la
única transformación temporal autorizada.

El runner implementa hurdle expected utility primario y Huber return directo
alternativo, percentiles train-only, tres meses inner estrictos, expanding train,
scheduler contractual y `ABSTAIN_OUTER` cuando ninguna pareja pasa. El smoke
2023-12 completó 12 folds ticker/arm/modelo; todos abstuvieron porque cero grids
pasaron los tres inner. Dos PUT outcomes SPXW 2022-02-22 faltan solo en train:
no se rellenan ni se elimina el universo; los heads se ajustan por lado con
targets finitos. Inner/outer falla cerrado ante cualquier missing. No se abrió
2024/2025 ni 2026. Falta freeze manifest committed antes del one-shot outer.

El freeze ya fue materializado sobre HEAD/origin `c1dee47` con status
`PREEXECUTION_FROZEN`. Manifest SHA `579fe8ce...a0c0b`; protocol SHA
`22a87b18...3f498f`. Contiene allowlists completos, hashes de sources/view,
model specs, código, grid, selección inner, scheduler y los 24 meses outer. El
smoke 2023-12 final volvió a ser determinista y todos los folds abstuvieron.
Siguiente paso único tras commit/push: ejecutar una sola vez el modo
`frozen_outer`; no editar ningún archivo de la closure antes de terminar.

## Cierre EDGE-FIRST EXISTING_DATA SPRINT V1

El nested frozen terminó y la familia queda `NO_EDGE_IN_EXISTING_DATA`. E1
hurdle/Huber: 72/72 outer cells abstain por modelo, cero trades, porque ningún
grid pasó simultáneamente los tres inner meses. E0 hurdle operó solo SPXW
202403, QQQ 202409 y SPY 202502; únicamente QQQ pasó la gate outer. E0 Huber
solo operó SPY 202502 y perdió. Pooled E0 hurdle parece positivo (68 trades,
PF 1,464809, WR 54,41%, +8,342R), pero tiene mínimo mensual 0, solo 3/72 cells
trade y 4,17% positive months; no puede promocionarse.

Auditoría independiente PASS sobre 288 folds, 12.096 grids, 288 month cells y
87 trades: selección inner exacta, expanding chronology, payoff ask-to-bid,
scheduler y métricas coinciden. Solo 1/288 cells pasa outer. Resultados en
`existing_data_executable_utility_v1_202401_202512/`; SUMMARY SHA
`52b83fdb...a3871`, AUDIT SHA `0a013154...0337bf`. Stress y 2026 no se abrieron;
junio sigue sellado y producción intacta. No retunar ni iniciar otro dataset.

## Cierre KING-GEX-SLOPE1

La primera traducción executable de `live_king_node.py` ya tiene resultado
económico y queda cerrada. En desarrollo 2023, K0 nivel produce 1.443 trades,
WR 43,10%, PF 0,810 y -94,144R; K1 nivel+pendiente alineada produce 1.324,
42,22%, 0,804 y -89,845R. K1 solo pasa QQQ 202310 y SPY 202307: 2/36 celdas.
No se abrieron 2024/2025/2026.

El runner es resumible y la auditoría revalidó 72/72 manifests, todos los
hashes/rows, las 72 métricas y el scheduler por brazo. El diagnóstico central es
dirección, no frecuencia: K1 cumple >=19 trades/mes y concentración, pero el
lado elegido supera al contrario solo 49,02%. El contrario también pierde
(PF 0,904/-42,624R); el oracle de lado no causal llega a PF 7,320/+657,492R.
No invertir por ticker, elegir CALL-only ni rescatar signos/meses.

Compactos y checkpoints en
`research_papers/JEPA/results/_diagnostics/king_gex_slope1_executable_development_2023_v1/`.
SUMMARY JSON SHA `4e568618...3290cb`, trades SHA `72f779ce...1534e`. La
siguiente familia rentable debe resolver selección de lado o monetizar
movimiento sin escoger lado, con contrato fijo ask-to-bid y checkpoints. El
workbook King continúa no auditado por ausencia del runtime spreadsheet.

## Research activo KING-GEX-EXIT1

El usuario señaló correctamente que WR ~44% puede ser rentable si PF alcanza
1,30. La descomposición identifica el fallo: K1 gana en promedio +66,11% y
pierde -60,29%, payoff ratio 1,0965; requiere aproximadamente 1,78 al mismo WR.
Los 749 negative triggers concentran -455,108R y el 96,51% del gross loss está
en exits <=-55%. Los horizons baseline no son el problema: 29 trades, PF 1,513
y +2,187R.

La inversión exacta completa, con scheduler rehecho, tampoco renta: 1.304 trades,
WR 43,02%, PF 0,850, -67,677R y 1/36 celdas. Se congela ahora un grid pequeño de
16 contratos de exit que separa stop 30-100%, horizonte 60-180m y trails más
tempranos/estrechos o tardíos/anchos. Ambos lados D0/D1 son desarrollo 2023 ya
abierto, no OOS. Replayer debe usar raw Greeks ask->bid, reproducir B00 exacto y
tener checkpoints por ticker-mes y policy. 2024-2026 permanecen cerrados.

El replayer ya está implementado pre-outcome alternativo. Cada source checkpoint
sella hashes raw Greeks/OI/OHLC y falla si el contrato o cualquiera de las cinco
métricas B00 difiere del master. Tras construir 36 ticker-meses, rehace scheduler
para 32 direction/config policies y solo promueve 36/36. Suite focal `13 passed`,
Ruff/compile clean. Debe commit/push antes del primer source cell real.

La ejecución V1 fue detenida tras el único checkpoint SPXW-202301, antes de
cualquier policy metric/ranking. Era correcto pero demasiado lento por repetir
pandas 16 veces por path. `KING_GEX_EXIT1_RUNTIME_CLARIFICATION.md` congela una
optimización array-only con equivalencia escalar y relanzamiento a V1R1; el
target V1 no se reutiliza.

La vectorización V1R1 ya está implementada y compara las 16 configuraciones
contra el algoritmo escalar en paths aleatorios con tolerancia `1e-12`; suite
total `14 passed`. Falta commit/push y relaunch inmutable V1R1.

## Cierre KING-GEX-EXIT1 y siguiente pregunta

V1R1 completó y queda `FAILED_ECONOMIC`. Se sellaron 36 source checkpoints
(425.152 rows) y 32 policy checkpoints; auditoría independiente recomputó
1.152 ticker-meses y el scheduler sin diferencias. Cero policies son elegibles;
outer 2024/2025, 2026 y producción no se abrieron.

Near-miss principales D1 invertido: B00 1.304 trades/WR43,02%/PF0,850/
-67,677R; S30 1.496/35,96%/0,925/-30,131R; S40
1.431/38,92%/0,914/-35,679R; H60 1.450/40,28%/0,896/-41,562R. Stop 50% pasa
más celdas, solo 6/36. T30D15 sube WR a 48,13% pero baja PF a 0,799. Ninguna
variante llega a PF1,0. No rescatar exits/tickers/meses.

En 1.083 entradas comunes, S30 mejora +24,275R frente a B00 pero sacrifica 96
ganadoras y rescata cero perdedoras; el oracle ex-post entre ambas alcanza PF
1,239. Esto justifica estudiar un selector causal `exit_now` vs `continue` a
+30m, no un grid mayor.

ThetaData local y `neural/stats.py` permiten calcular higher Greeks sintéticas,
pero E1 ya usó gamma/vanna/charm/vomma/zomma/vega/delta, cambios, ratios
0DTE-weekly, walls, IB/Fib y precio dentro de 527 features. Los 144 cells E1
GBT abstuvieron. Nueva hipótesis: evolución observable de contrato/precio/griegas
entre entrada y +30m para continuación. Marcar siempre
`SYNTHETIC_MODEL_DERIVED`; OI unsigned no demuestra presión dealer.

Resultados completos en
`research_papers/JEPA/results/_diagnostics/king_gex_exit1_executable_development_2023_v1r1/`.
El workbook `MASTER_KING_NODE_RECORD_V5.xlsx` continúa sin inspección de celdas:
el runtime obligatorio `@oai/artifact-tool` no está disponible; no atribuirle
ninguna métrica.

## Research activo KING-GEX-MANAGE30-V1

Se amplió el oracle con scheduler exacto. D1 eligiendo solo B00/S30 no puede
cumplir el objetivo ni con futuro: 1.429 trades, PF1,190, WR43,60%, +65,326R y
13/36 cells. No construir ese clasificador. El oracle D1 de las 16 gestiones sí
tiene techo: 1.337, PF2,357, WR54,67%, +324,783R y 32/36; falla SPXW 202306,
QQQ 202306/202308 y SPY 202307.

Predeclaración nueva en `KING_GEX_MANAGE30_V1_PREDECLARATION.md`, SHA
`b534cd8857833285010dccc0ae440f89a4ca8235dd4d2e7c99dd17a731d74948`.
Dirección D1 fija, contrato original, estado exacto +30m y 17 acciones
(EXIT1+E30). M0 usa path/contrato; M1 añade exposiciones sintéticas entrada/+30.
Target es ventaja clipped vs B00; LGBM Huber fijo por ticker. Train inicial
2022, folds expandidos 2023; solo un PASS 36/36 abre 2024/2025.

Inventario outcome-free: 49.400 eventos K1 y 2.721 sesiones 2022-2025; todos
los paths Greeks/OI/OHLC existen. El modeling view existente solo tiene exact
+30 para 36.452/49.400, por lo que el builder debe usar raw y no as-of/zeros.

El legacy path exit debe constar como fracaso separado: metrics SHA
`d122cc30...c14c5eb6`, 1.690 trades/PF0,811/WR33,85%/-89.652. Mezclaba delta,
hold 5/15/30, otro universo y otra ejecución. No es evidencia contra MANAGE30
ni fuente de calibración. Siguiente trabajo: commit/push predeclaración y luego
builder resumible con tests de causalidad/paridad; no abrir outer/2026.

Builder ya implementado pre-label: `build_king_gex_manage30_v1.py`. Solo acepta
2022/2023, espera 22.273 eventos, selecciona el right D1/strike frozen, exige
paridad B00 y persiste una sesión de forma atómica con hashes Greeks/OI/OHLC.
Extrae features solo hasta primera quote 30..31, 16 outcomes+E30 y exposiciones
sintéticas compartidas. Missing exact lag permanece NaN; missing decision usa
B00. Suite focal `16 passed`, Ruff/compile clean. Debe commit/push antes del
primer build real.

Primer build no abrió paths/outcomes: join falló porque master incluía 10:30
antes de la ventana King. `KING_GEX_MANAGE30_V1_DATA_GATE_CLARIFICATION.md`
congela master minute 680..870 antes del exact join. Censo outcome-free:
33.902/33.902 joins, 22.273 K1 sin cambio. V1 tiene solo RUN_CHECKPOINT y es
`REJECTED_PRE_PATH_LABEL`; relanzar tras commit a target V1R1. Suite `7 passed`.

## MANAGE30 runner y build activo — 2026-07-15 16:47

El evaluador causal/resumible está implementado en
`neural/jepa/evaluate_king_gex_manage30_v1.py` y pushed en `b8fa50c8`. No abre
outer: entrena 2022 para 202301 y expande exclusivamente con meses anteriores
hasta 202312. Son 72 folds por ticker/M0-M1. Modela 17 contrafactuales como
ventaja clipped vs B00; B00 se fija a cero y solo cambia por predicción >0.
Después rehace scheduler con el hold seleccionado, por lo que la duración
afecta causalmente qué oportunidades posteriores sobreviven.

Checkpoints fold manifest-last contienen `model.txt`, medianas, predicciones,
trades y métricas; identidad incluye hashes de dataset, resumen, código y ambos
documentos congelados. Tests combinados builder/runner/EXIT1: `22 passed`; Ruff
y compilación clean. No hay resultado económico aún.

El builder V1R1 sigue activo en
`tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1`; checkpoint observado:
843 manifests de sesión, cero errores, última escritura 16:47. No lanzar otra
instancia. Si el proceso muere, relanzar exactamente:

```powershell
python neural/jepa/build_king_gex_manage30_v1.py `
  --output-dir tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1 `
  --workers 4
```

Al terminar, exigir `SUMMARY.json status=PASS_DATA_GATE`, dataset 22.273 rows,
keys únicas y B00 finito/hold30..180. Revisar `decision_coverage` y
`synth_complete_coverage`; no asumir que existencia de fuentes equivale a
cobertura. Solo después ejecutar el runner al target nuevo
`research_papers/JEPA/results/_diagnostics/king_gex_manage30_development_2023_v1`.

`SUMMARY.md` en raíz es ahora el handoff canónico compacto/detallado. Mantenerlo
sincronizado con AGENTS, este archivo, SUMMARY-update y SUMMARY-articles tras
cada data seal, resultado o cierre. El Excel King sigue bloqueado: la skill
exige `load_workspace_dependencies/@oai/artifact-tool`, no expuesto en esta
sesión, y prohíbe rutas/instalación/librerías alternativas. No git-add ni
modificar; una futura auditoría read-only no puede retocar MANAGE30.

## MANAGE30 V1R2 exact snapshots

V1R1 terminó antes de combinar dataset: 1.265/1.267 manifests, sin SUMMARY,
modelos o métricas. Falló paridad en QQQ 2022-06-17 porque `dt=floor(quote_dt)`
unía :00 y :30; por ejemplo entry 13:55 debía usar ask 0,71 pero eligió la
quote futura :30 ask 0,74. Esto es leakage causal. No reutilizar ningún
checkpoint V1R1 aunque individualmente pasara B00.

La auditoría exacta detectó además solo `SPXW/20220222/680/PUT` sin contrato
ejecutable; master strike/returns ya eran NaN. Aclaración V1R2 commit
`9a8e0b41`, SHA `35e09f5a...e39a844`: exact snapshots entry/decision, una
rejection allowlisted, 22.273 source y 22.272 executable. Cualquier otra
rejection falla cerrado.

Código commit `a996f260`; QQQ 6/6 y SPXW 30/31 reales pasan, suite `24 passed`.
Nuevo build activo:

```powershell
python neural/jepa/build_king_gex_manage30_v1.py `
  --output-dir tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r2 `
  --workers 4
```

No ejecutar evaluator hasta `PASS_DATA_GATE` V1R2 y auditoría de coberturas.
2024-2026/producción intactos; PF M0/M1 inexistente todavía.

## Cierres 2026-07-16 — MANAGE30 y weekly multi-día

MANAGE30 V1R2 pasó data gate con 22.272 executable rows y SHA
`2c7ff048...000b`, pero el único desarrollo 2023 falló: M0 PF0,905/WR38,90%/
-34,942R/3 de 36 celdas; M1 PF0,901/WR39,08%/-36,299R/5 de 36. Status
`FAILED_ECONOMIC_DEVELOPMENT`, cero brazos elegibles, outer 2024–2026 cerrado.
No reintentar con una red neuronal ni rescatar acciones/tickers post-hoc.

El usuario pidió evitar generar datasets sin fin. Se hizo un único audit weekly
sin dataset de features, congelado en `cf536c53`: delta 0,50, exact contract,
ask 10:35 -> bid 10:35 dos sesiones después, no-overlap, 2022–2025. Cobertura
2.361/2.364. El oracle de side tiene PF12,277/13,960/13,876 para QQQ/SPXW/SPY
y PnL positivo todos los meses, pero falla WR>50% en 16/144 celdas y solo
permite 8–10 trades/mes. `CLOSED_ORACLE_GATE`; no abrir policy/dataset weekly,
ni variar hold/delta/clock. Always-CALL apenas PF1,042–1,056; always-PUT pierde.

2026 y producción intactos. No hay policy causal rentable/promovible. Los
compactos están en `weekly_multiday_oracle_202201_202512_v1/` y
`king_gex_manage30_development_2023_v1/`.

## Checkpoint autoritativo 2026-07-16 18:30 — no hay familia activa

Todo lo anterior conserva cronología, pero los bloques que dicen “research
activo” están cerrados. No existe hoy una policy que cumpla simultáneamente por
QQQ/SPX/SPY PF>1,20, WR>45%, >12 trades en cada mes y PnL positivo en todos
los meses enero–15 julio 2026. El paquete live/paper no fue sustituido.

### Fuente Globex sellada

Bundle externo inmutable:

```text
D:/ThetaData/futures_yahoo_60m_20240717_20260715_v1
```

Símbolos `ES=F,NQ=F,YM=F,RTY=F,ZN=F,GC=F,CL=F`; capture manifest SHA
`dad8dc52c08ea29cbea35aedcc706c7cf51fb937436b88706642141236c2dcb7`.
Seal commit `eaa56342`. La fila Yahoo exactamente en `period2` se conserva en
raw y se excluye del periodo congelado. No usar `VX=F` (404), no inventar VIX y
no llamar a estos continuos fills de futuros. Yahoo impidió extender 60m antes
de 2024-07-17 por su límite de 730 días.

El runner exige intersección exacta de siete futuros y 15 cash tickers. Faltas
de barra/día/semana se eliminan para todos, sin forward fill. V1 seleccionó
Globex en 2025 (PF 1,200/1,206/1,210; 9/12 meses positivos) y falló el one-shot
2026-julio (PF 0,873/0,899/0,888; 2/3/3 meses positivos). Commits principales:
`73320dd8`, `5de742ec`, `eaa56342`, `a0154724`, `b679919c`, `f7f09f93`.

V2/V3/V4 quedaron cerrados en desarrollo y no abrieron 2026:

- V2 online linear: PF 0,980/0,976/0,996; commits `fdf63b59`,`bec721d8`;
- V3 online expert: PF 1,140/1,137/1,098, 5/6/5 meses; `9c7f1707`,`0b0cf093`;
- V4 meta-Hedge: PF 1,161/0,933/0,965, 4/5/5 meses; `30145354`,`e3e17bd0`.

No abrir memorias adicionales, seleccionar W1/W2, invertir un ticker o mezclar
expertos post-hoc.

### Payoffs alternativos cerrados

`SHORT_PREMIUM_FIXED_HORIZON_V2` (`d1f86f7b`,`cb3966b4`) usa exits exactos
TIME30/60/90/120 y exige cuatro patas ejecutables. El log externo
`D:/ThetaData/short_premium_fixed_horizon_v2.stdout.log` alcanzó 100/1.506
sesiones, 4.271 candidatos y 13 unresolved ya invalidantes. No hay output dir,
PF, WR o PnL. Estado: `REJECTED_DATA_GATE`; no reanudar para descartar filas.

`DUAL_LEG_EVENT_VOLATILITY_V1` (`d96b4530`,`edcd18c3`) cerró 2025 con 613
trades/ticker, PF 0,629/0,661/0,605, WR 35,07/33,28/36,22% y min40. Artefactos:
`results/_diagnostics/dual_leg_event_volatility_v1_development_2025/`.

`DIRECTIONAL_IB_BREAKOUT_FADE_V1` (`b0f0bdcf`,`6dbe157d`) cerró 2025 con PF
0,779/0,785/0,819, WR 31,28/32,41/31,94% y min25/24/24. Usa 829 sesiones
comunes de 15 tickers y no creó dataset nuevo. Artefactos en
`directional_ib_breakout_fade_v1_development_202208_202512/`.

### Diagnóstico y disciplina de continuación

Factorized innovation+VISReg corrigió el colapso espectral (rango efectivo
z/dz 53,54%/42,67%) sin rentabilidad. No repetir VISReg, JEPA corruption,
breadth, option surface, memoria Globex, stop/Fib, weekly hold/delta o selección
de meses sobre los mismos outcomes.

No hay proceso de captura/research relevante que deba reanudarse. Los procesos
Python observados al redactar este checkpoint pertenecen a otro workspace.
Preservar todos los untracked del usuario, especialmente
`MASTER_KING_NODE_RECORD_V5.xlsx`, `live_king_node.py`, tarballs, `tmp/` y los
artefactos JEPA existentes; no hacer reset/clean.

La siguiente familia solo puede activarse con predeclaración de un mecanismo
independiente o una fuente broker-grade con paridad live. Candidatos conceptuales
no autorizados todavía: cross-session/overnight o relative-value entre índices.
No descargar otra fuente ni abrir 2026 para uno de ellos sin freeze y desarrollo
pre-2026. Estado final: `NO_PROFITABLE_CAUSAL_POLICY`, producción intacta.

## Checkpoint autoritativo 2026-07-17 — CROSS_SESSION_RELATIVE_VALUE_V1

Se completó la lectura/reconciliación de AGENTS, los tres SUMMARY, este handoff y
el cierre/predeclaración compact V1. HEAD/origin parten de `d02b1ad9`, tracked
clean. No tocar los untracked históricos. El family registry stale se corrige:
King ya no está activo.

La nueva predeclaración está en
`research_papers/JEPA/CROSS_SESSION_RELATIVE_VALUE_V1_PREDECLARATION.md`.
Contrato: una operación diaria equal-notional QQQ-SPY que revierte la divergencia
QQQ frente a `0,5*(SPY+SPXW)` acumulada desde el cierre RTH previo hasta el
close 10:34. Entrada open 10:36, salida open 13:36, hold 180m y 2 bps de coste
total. SPXW es ancla, no pata ejecutada. No hay dataset, model, threshold,
z-score, beta fit, stop ni abstention.

Inventario outcome-free: 1.003 Parquets por ticker 2022–2025 con schema 1m
común. Próximo paso único: implementar tests de reloj/source/payoff sin abrir
2024+, commit/push del runner y ejecutar una sola vez desarrollo 2022–2023.
Gate mensual: PF>1,20, WR>45%, >12 trades y PnL>0. Si cualquier mes falla,
cerrar y no abrir 2024–2026 ni opciones. Producción permanece intacta.

Implementación pre-outcome lista: `evaluate_cross_session_relative_value_v1.py`
y `test_cross_session_relative_value_v1.py`. El runner fija cutoff 20231231 sin
CLI mutable, valida/rehashea cada Parquet, usa solo close 10:34 y opens exactos,
escribe outputs atómicos y separa controles no elegibles. Antes del run real:
pytest focal, Ruff, py_compile, git add explícito, commit y push.

Aclaración pre-outcome adicional:
`CROSS_SESSION_RELATIVE_VALUE_V1_DATA_GATE_CLARIFICATION.md`. El 2023-06-05 se
excluye como trade; solo sus tres rows SPY 09:54–09:56 pueden fallar envelope y
no se usan. El close 16:00 válido se conserva como prior close de 06-06. Runner
hashea ambos documentos y cualquier anomalía extra aborta.

## Cierre CROSS_SESSION_RELATIVE_VALUE_V1 — autoritativo

Runner committed/pushed `5e2dc677`; development real 2022–2023:
`FAILED_ECONOMIC_DEVELOPMENT`. Resultado 496 trades, WR 41,532%, PF 0,627276,
-2.349,329 bps, min19 trades/mes, 5/24 meses positivos y 2/24 PASS. Control
momentum PF1,075340/+365,329 bps; fijo long QQQ/short SPY PF0,921644. Ningún
control es elegible y momentum tampoco pasa PF1,20.

Auditoría independiente: fechas 20220104..20231229, hold único 180, coste único
2 bps, cero overlap/future rows y métricas/hash exactos. Trades SHA
`48459a8c...80dfc0`, monthly SHA `75c76e2a...15a9af`, source inventory SHA
`0311dc5c...9eb57`. Compactos en
`cross_session_relative_value_v1_development_202201_202312/`.

No abrir outer/2026, no invertir policy ni añadir beta/z-score/threshold/ML.
Actualizar registry/handoffs, commit/push y dejar estado
`NO_PROFITABLE_CAUSAL_POLICY`, producción intacta, ninguna familia activa.

## Nueva familia activa — OPENING_RELATIVE_MOMENTUM_V1

Predeclaración:
`research_papers/JEPA/OPENING_RELATIVE_MOMENTUM_V1_PREDECLARATION.md`.
La señal usa exclusivamente la divergencia cash 09:30→close10:34; no consume
prior close ni overnight y por ello no reabre el cross-session mean-reversion.
Acción momentum QQQ-SPY, SPXW ancla, opens 10:36/13:36, hold180, coste2bps.

Solo desarrollo 2022–2023. Registrar PF agregado>1 como progreso diagnóstico,
pero no abrir outer salvo que los 24 meses pasen PF>1,20, WR>45%, >12 trades y
PnL>0. Secuencia: predeclaración commit/push -> implementar runner/tests ->
commit/push -> one-shot development -> auditoría/handoffs. Todo 2024–2026 y
producción siguen cerrados.

Runner listo pre-outcome:
`neural/jepa/evaluate_opening_relative_momentum_v1.py`; tests en
`tests/test_opening_relative_momentum_v1.py`. Importa solo validación/hash/IO del
runner anterior y sella su SHA como dependencia; no importa su señal. No expone
cutoff mutable. Ejecutar pytest/Ruff/compile, commit/push y solo entonces el
target inmutable `opening_relative_momentum_v1_development_202201_202312`.

El primer launch falló antes de fuente/output por `ModuleNotFoundError: neural`;
target inexistente. Fix permitido: bootstrap de repo root + test subprocess de
CLI directa. Commit/push y relanzar el mismo comando solo tras suite verde.

## Cierre OPENING_RELATIVE_MOMENTUM_V1 — autoritativo

El fix fue committed/pushed en `ca9bb9c2`; el único relaunch 2022–2023 completó
`NO_AGGREGATE_EDGE`. Resultado: 497 trades, WR50,905%, PF0,831462,
-927,689bps, min19, 7/24 meses positivos y 4/24 PASS. Controles:
mean-reversion PF0,812876/-1.060,311bps y long-QQQ/short-SPY fijo
PF0,924384/-398,799bps.

Auditoría independiente confirmó fechas 20220103..20231229 con exclusiones
predeclaradas, hold180, coste2, cero overlaps/future rows y métricas exactas.
Trades SHA `b119ab24...750384`, monthly `48070dad...9a474`, inventory
`0311dc5c...9eb57`. Evidencia en
`opening_relative_momentum_v1_development_202201_202312/`; cierre en
`OPENING_RELATIVE_MOMENTUM_V1_CLOSURE.md`.

No abrir 2024–2026 ni rescatar signo, beta/z-score, threshold, stop, ML o reloj.
Registry queda sin familia activa. Próximo trabajo permitido: predeclarar un
mecanismo independiente que ataque asimetría de pérdidas de forma causal; no
confundir WR50,9% con edge porque PF y PnL son negativos. Producción intacta.

## Nueva familia activa — OPTION_PARITY_PRESSURE_V1

El audit del workbook King volvió a quedar bloqueado: la skill de spreadsheets
requiere `@oai/artifact-tool` y el loader/runtime no está disponible. No usar
otra librería ni inferir fórmulas del XLSX.

Predeclaración outcome-free:
`research_papers/JEPA/OPTION_PARITY_PRESSURE_V1_PREDECLARATION.md`. La señal
empareja CALL/PUT 0DTE exactos por strike/timestamp, usa los mismos strikes
<=100bps a 10:30/10:35 y toma la mediana del cambio de synthetic-forward basis
normalizado por spread. Greek vintage conserva bid/ask; native sidecar solo
certifica reloj/keys; spot viene del underlying derivado.

Fase autorizada: commit/push docs -> builder/tests outcome-free -> data gate
2022–2023. Requisitos: >=3 strikes comunes, coverage >=90% por ticker-año,
>12 eventos cada mes, presión finita/no degenerada y cero timestamps inferidos.
No labels/PnL/2024–2026/producción. Si PASS, congelar runner deterministic sign,
open10:36→13:36/180m/1bp antes del único desarrollo.

Scope amendment por orden explícita del usuario, congelado antes de outcomes:
ignorar todo 2022 y usar 2023–2026 en fases. Motivo físico: febrero 2022 ofrece
12 0DTE exactos por ticker y una operación/día no puede superar `>12`. Nuevo
orden: data gate 2023–2025 -> desarrollo 2023 -> outer 2024–2025 si PASS ->
freeze -> 2026 si PASS. No abrir etapas posteriores anticipadamente. Documento:
`OPTION_PARITY_PRESSURE_V1_SCOPE_AMENDMENT.md`.

Capacity audit committed/pushed `314d16e1` y ejecutado una vez: PASS, 2.256
fuentes exactas/752 por ticker, mínimo18 sesiones mensuales, cero fallos. No
leyó quotes/outcomes. Compactos en
`option_parity_pressure_v1_capacity_202301_202512/`; hashes manifest
`eebdc7d9...4f590`, monthly `e8dfc2e4...c5e7`, inventory
`9c6ddb40...9392d`. Siguiente: commit/push compactos/handoffs -> builder
outcome-free con timestamp nativo y pares exactos. No abrir economía todavía.

Full V1 desde `b0cbba80` terminó REJECTED con 104 errores pre-label
(QQQ103/SPXW1). Causa auditada: strings `.000` no coincidían con el filtro sin
milisegundos; los minutos exactos existen. V1 manifest SHA `47cb9ad2...91869`,
errors `ee68d9eb...235c`, preservado en `tmp`. Clarificación:
`OPTION_PARITY_PRESSURE_V1_NATIVE_STRING_CLOCK_CLARIFICATION.md`. Siguiente:
commit doc -> fix/regresión -> commit/push -> target nuevo V1R1. No retocar
formula/gates ni usar V1 parcial.
