# SUMMARY-update — ledger científico compacto

## Checkpoint 2026-08-02 — Phase0 audit y familia multiscale en cola

El audit de Phase0 quedó committed/pushed en `691e172a`, con
`MULTISCALE_LEVEL_INTERACTION_SEQUENCE_V1_PHASE0_AUDIT_CONTRACT.md` y el
inventario compacto en
`research_papers/JEPA/results/_diagnostics/multiscale_level_interaction_sequence_v1_phase0_audit/INVENTORY.json`.
El inventario localiza 360804 archivos / 255.740 GiB; no existe un outer
histórico intacto. Todo hasta 2026-07-24 es `SEEN_DEVELOPMENT`, una afirmación
histórica favorable como máximo es `DEVELOPMENT_PASS_REQUIRES_SHADOW` y la
paridad histórica/live sigue bloqueada.

La binding `MULTISCALE_LEVEL_INTERACTION_SEQUENCE_V1_PREDECLARATION.md` está
escrita antes de abrir cualquier valor raw, outcome o modelo. La autorización
estrecha actual del usuario supersede el cierre de familia activa únicamente
para esta familia; las clausuras históricas, causalidad/paridad/shadow y
producción siguen vigentes. El contrato usa solo fuentes locales existentes,
sin descarga: un evento en 18 relojes fijos 11:30–12:55, tensor completo exacto
12x5m+8x15m, 59 slots fijos (53 antiguos + 6 call/put/delta), selección primaria
de árbol small2x2 y una ablación que elimina todos los canales de niveles. El sidecar separado de
24 payoffs es CALL/PUT×d25/35/50×60/90/120/180, mismo contrato ask→bid, con
slippage+commission base/adverse y `reject_while_open`. El test de desarrollo
es enero2025–junio2026 con selección mensual de seis meses. Solo habrá una
sensibilidad TCR-VIS actionless: NCE de misma trayectoria a temperatura 0.12 y
residuo temporal causal del evento con sliced-Wasserstein VIS de peso 0.04; no
puede rescatar el árbol. Aplican gates por ticker y auditor independiente.

Estado vinculante: `QUEUED_IMPLEMENTATION_OUTCOME_CLOSED`. No se abrió valor raw,
artefacto de feature/payoff, fit, predicción, métrica económica ni outer payoff.
La siguiente secuencia autoritativa es commit/push de predeclaración+hándoffs+
registro → implementar builder outcome-free, tests, evaluator y auditor y
versionarlos → ejecutar entonces el source/data gate; los outcomes permanecen
cerrados hasta gate, auditoría y freeze. Este checkpoint supersede solo
instrucciones `Siguiente:` obsoletas y no borra ni reescribe la evidencia
histórica.

2026-07-26, full nested one-shot `FAILED_DEVELOPMENT_FULL_GATES` desde
`5b0a44ad`: 18 folds×1.128.960 configs, ledger test-only370. QQQ
149/PF0,584706/WR35,570%/-23,412554/min18/1 mes positivo; SPXW
114/0,844375/38,596%/-6,336789/min17/3; SPY
107/1,083921/47,664%/+2,619171/min12/2. Auditor PASS refit36,
pred-hash36,winners18,ledger exacto, hold30–180/overlap0. Summary/audit SHA
`01074ce9...97c8`/`aa496662...e42c`. Familia cerrada; no live, no retune H1.
Evidencia completa publicada en `6b5fb863`.

2026-07-26, implementación preejecución del full nested lista. Evaluator carga
features sin outcomes futuros, ajusta cada fold con train, escanea select6m,
serializa winner/modelos/medianas/hashes y solo después abre test1m. Auditor
rehashea fuente, reconstruye features, refittea36 modelos y repite18 grids,
scheduler y ledger. Optimización exacta 70.560 bases×16 schedules=1.128.960;
cd0/15/30 equivalen con holds≥30 y desempate conserva cd0. Focal6/Ruff/compile
PASS; cero folds reales ejecutados. Commit/push código+hándoffs antes del run.

2026-07-26, predeclarado
`EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1`: fuente ask→bid
inmutable 44.169 filas/SHA `e6a19ef...51903`; perfiles QQQ/SPY d35-return y
SPXW d25-return. Por fold: fit antes de select6m, barrido exacto de 1.128.960
overlays/ticker solo en selección, freeze y test1m; ledger final solo test
202601–202606. Scheduler corrige el legacy con hold30–180 y
next_allowed=max(exit, entry+cooldown); SPXW stop_pause1, sin guard SPY posthoc.
Gates PF>1,20/WR>45%/neto>0/min13/6 meses positivos por ticker. GroupDRO
cerrado sin implementación/métrica. Primero versionar doc, luego
runner+auditor, único run y auditoría; live cerrado y 2026 development visto.

2026-07-26, intake OPRA cerrado sin ejecución por orden del usuario: no key,
endpoint, captura, seal, feature u outcome. Predeclarada una única falsificación
con el parquet executable_quote existente SHA `e6a19ef...51903`, 44.169 filas
20250102–20260630. Q-network pooled 289→128→64→12, acciones CALL/PUT
d15/25/35/50/65/80, GroupDRO ticker-mes, folds Jan–Jun expanding, argmax Q>0 y
scheduler reject_while_open/hold30–180. Gates simultáneos PF>1,20/WR>45%/
neto>0/min13 y 6/6 meses positivos por ticker. 2026 es development visto; no
live/VPS aunque pase sin shadow futuro.

2026-07-26, predeclaración de admisión externa: Massive Options Advanced es el
candidato documental por trades desde2014, quotes desde2022-03-07 y
REST+WebSocket. No está admitido: falta `MASSIVE_API_KEY`/plan y shadow
live↔REST5 sesiones. Histórico ns se trunca a ms; quote predecessor debe ser
estrictamente anterior y corrections/paridad exactas. Databento TCBBO empieza
28-mar-2023. Sin endpoint/datos/V8; próximo outer futuro.

2026-07-26, inventario post-V7 read-only: no fuente local nueva. QQQ/SPY
Greeks/IV/OHLC/OI cubren 250/252/250 sesiones 2023–2025, pero están cerradas;
quote size/ticks ya fallaron y V5 queda 1.364/1.504. Solo credenciales Theta,
sin tape/depth/futuros alternativos. No V8/retuning 2026; dependencia externa.

2026-07-26, V7 rolling12 one-shot `FAILED_DEVELOPMENT_NOT_STABLE`. H1
QQQ/SPXW/SPY PF0,812462/1,079783/1,031988, net
-585,329/+149,347/+61,076bps, min18, meses+1/2/3. Junio QQQ pasa pero
SPXW/SPY PF0,968/1,075; julio MTD solo QQQ positivo. Auditor PASS: refit7,
probabilidades/ledger394 exactos, mismatch0, summary SHA `260e05df...94fe`.
V7 `FAILED_ECONOMIC`; physical/live cerrado.

2026-07-26, V7 rolling12 predeclarada sin predicciones. V4R2 fue fit fijo
2023–2025. Diagnóstico post-outcome: correlaciones coef anuales
-0,143/0,095/0,146; marzo direct pooled +518,604bps pero model -273,230bps al
invertir74,60%. V7 conserva logistic29/C0,1, mapping, 394 eventos y clocks;
refit mensual con 12 meses anteriores, por lo que Feb–Jul incorpora solo 2026
previo. Sin sweep/descarga/filtro. 2026 development visto; physical/live cerrado.
Contrato `6ee8fc2f`; evaluator+auditor listos pre-run, tests11/Ruff/compile PASS.

2026-07-26, V4R2 outer one-shot FAIL auditado. H1 QQQ/SPXW/SPY:
PF0,969729/0,950957/0,955718, WR52,542/50,420/49,580%, net
-86,880/-97,917/-87,839bps, min18 y 2/6 meses positivos. Junio net positivo
pero QQQ/SPXW PF<1,20. Julio MTD: QQQ +341,973/PF3,453/12; SPXW
-39,351/PF0,807; SPY -123,162/PF0,496. Auditor refit/predictions exactos,
sources394/mismatch0, evaluation SHA `8de7e886...f12b`. Physical/live cerrado;
2026 consumido.

2026-07-26, reseal V4R1 PASS desde `46971a80`: Greek/IV/shared3.432,
unilaterales0, exclusiones retry0, red/outcomes false. Builder posterior cerró
sin output: QQQ 20260310 no CALL25, SPY 20260319 no PUT25, QQQ 20260630 asks
distintos y QQQ 20260722 Greek-only92. Usuario ordena no descargar y omitir.
V4R2 fija cuatro sensor-fecha pre-outcome; sensor262/targets394, counts QQQ
20/19/21/18/20/20/12 y SPXW/SPY20/19/21/18/20/21/13. Focal9/Ruff/compile
PASS. Gate real desde `f60f6282` PASS, features29, fuentes1.446/mismatch0,
10:36/13:36 false. Auditor real desde `09395b94` PASS, reparse10,
rehash1.446/mismatch0, feature view exacta, summary SHA `16988ecc...1aa3`.
Evidencia versionada `15b76868`. Freezer/evaluator/auditor pre-outcome listos:
fit2.217, predictions394, clocks exactos y auditor refit; tests16/Ruff/compile
PASS. Commit/push código → freezer → commit/push manifest → outer one-shot.
Código `7472f45d`; freeze real train2.217/events394, event SHA
`1df3753c...05cf`, model `e8caffde...202e`, manifest `f90dbcf6...45e6`;
open10:36/13:36 false. Versionar frozen antes de outer.

2026-07-26, retry V4R1 ejecutado una vez desde `aba363c3`: 10/10 respuestas
normalizadas, raw inmutable, features/outcomes false. El seal usable0 fue un
artefacto del lector (`timestamp[ns]` comparado con strings), no missingness.
Reparse offline exacto 10:30/10:35: cinco parejas PASS con filas
688/800/632/604/708, Greek-only0, IV-only0 y exclusiones0. Seal fuente SHA
`a18e0864...58f0`; no requery. Aclaración+lector+resealer pasan focal8/Ruff/
compile. Siguiente: commit/push, reseal v2 una vez, gate outcome-free y auditor;
10:36/13:36 permanecen cerrados.

2026-07-26, V4R1 predeclarada por orden posterior del usuario. Autoriza diez
requests exactos Greek+IV para los cinco IDs junio2026; si no quedan key-exact,
exclusión sensor-fecha antes de outcomes. No intersection/fill/overwrite.
Universo metadata 133 fechas 20260102–20260724, meses20/19/22/18/20/21/13,
532 captures, date SHA `7fb305c4...21c3`. V4 inmutable; V6 cerrada sin
predicción. Commit documental → código/gate/auditor committed → retry → seal →
freeze → outer2026 one-shot.

Implementación V4R1 pre-red lista: capturador10 lógico/atómico, builder exacto
de 29 features hasta10:35 y auditor raw+source+feature. Focal7/Ruff/compile
PASS; censo 92/516 reproducido. API y outcomes aún no abiertos; commit/push del
código precede al run.

2026-07-26, V6 predeclarada por autorización del usuario sobre los datasets V4
ya sellados y sin nuevas descargas. Único cambio: logistic→HistGB depth2 fijo;
mapping, 29 features, clocks, eventos y costes intactos. Folds dev 2023→2024 y
2023+2024→2025; gate completa en seis ticker-año y 72 celdas mensuales. Primero
versionar contrato, después evaluator+auditor preejecución. 2026/live cerrados
hasta PASS; cinco IDs Greek/IV permanecen fail-closed.

2026-07-26, V5 `FAILED_OUTCOME_FREE_SOURCE_CAPTURE_GATE`: universo1.504,
captures válidos1.364, fallos140 uniformes invalid/duplicate; QQQ32/25/8 y
SPY38/30/7 por año, enero2024=0/21 completo en ambos. Stagers0/no seal; no
features, opens ni outcomes. No requery/dedup/exclusión/evaluación parcial.
Auditor real PASS desde `c4318884`: rehash/reparse1.364, mismatch0,
unaccounted0, mínimo mensual0; summary/seal `39b417e0...fc77`/
`20f322c5...0297`. V5 `BLOCKED_DATA`, sin builder/evaluator. Bloqueo externo
formal: `CAUSAL_SOURCE_EXTERNAL_DEPENDENCY_BLOCK_20260726.md`.

2026-07-25, V5 predeclarada y aún sin datos. Inventario outcome-free: única
fuente nueva materialmente compatible = prints OPRA 0DTE QQQ/SPY con NBBO
estrictamente anterior, histórico `trade_quote` y Quote/Trade Stream Standard.
No se inició Terminal ni se consultó endpoint/valor/open/outcome. Contrato V5:
mapping QQQ←QQQ, SPY←SPY, SPXW←SPY; features09:30–10:35; logistic pooled
L2/C0,1; development fit2023→2024 y fit2023+2024→2025; gate conjunta estricta
en seis ticker-año y todos los meses. Commit/push documental precede al data
gate y auditor outcome-free. Greek/IV junio2026, outcomes y live siguen cerrados.

Implementación V5 preejecución: universe QQQ/SPY=752 fechas cada uno,
2023/2024/2025=250/252/250, captures1.504, date SHA `e7786a1a...b8f9`;
capturador atómico/resumible + builder + auditor raw independiente listos.
Suite cross-venue113, Ruff y compile PASS. Terminal status CONNECTED, pero
`trade_quote`/valores/outcomes siguen sin consultar. Commit/push antes del run.

2026-07-25, consolidado autoritativo. Los `pendiente` anteriores ya se
ejecutaron y no deben relanzarse. A 1bp y en orden QQQ/SPXW/SPY: design2023
PF1,173476/1,071604/1,072835, WR51,822/50,000/50,403%, neto
+812,500/+268,657/+273,999bps, min19/19/19, meses7/5/5; outer V1 2024
PF0,866939/0,698912/0,693382, neto negativo en los tres, min19/18/18,
meses6/5/5; V3 development2024 PF1,231750/1,395967/1,408300, WR>51%, neto
positivo, min19/18/18, meses8/8/8; outer V3 2025 PF
0,655469/1,035567/1,039777, neto -2.381,476/+163,026/+182,456bps,
min18/17/17, meses5/6/6; V4 development2025 auditado PF
1,204351/1,247945/1,346342, WR51,8219/52,0492/53,2787%, neto
+1.060,279/+1.030,091/+1.381,556bps, min18/17/17, meses7/8/8.

Ninguno pasa el objetivo mensual completo. V4 no abrió outcomes2026: gate
outcome-free falla por cinco IDs nuevos con Greek-only92/IV-only516. Whitelist
Greek∩IV limitada a los cuatro repairs V1R1; no intersectar/reparar/excluir/
recapturar. Cash-only no transporta 2024→2025, por tanto no hay V5 activa.
Siguiente: inventario outcome-free de una fuente causal nueva con historia y
paridad live; luego predeclaración → development walk-forward 2023–2025 → data
gate/auditor/freeze → primer outer posible 2026. Mapping QQQ←QQQ, SPY←SPY,
SPXW←SPY intacto. No live/systemd; ask→bid/no-overlap/hold30–180m/
`reject_while_open` antes de paper-only.

2026-07-22: V3 outer2025 desde manifest committed `91584706` cerró
`FAILED_OUTER_2025_2026_CLOSED`. QQQ 247/PF0,655/WR50,6%/-2.381,5bps/min18/
5 meses; SPXW244/1,036/53,7%/+163,0/min17/6; SPY244/1,040/53,7%/+182,5/
min17/6. Auditor PASS: sources735/mismatch0/digests exactos, summary
`99346b5b...1dd5`. 2026/live/systemd cerrados; versionar evidencia antes de V4.

V4 post-outcome predeclarada: pooled logistic V2R1 fijo, fit2023+2024 y
development2025 PF1,204/1,248/1,346, WR>51%, net positivo y min18/17/17; solo
7/8/8 meses positivos. 2025 es development visto, no OOS. Commit doc → evaluator
reproducible → auditor → data gate 2026 outcome-free. 2026 sigue sin abrir.

Checkpoint V4 exacto 1bp: QQQ PF1,204351/WR51,8219%/+1.060,279bps/min18/7m;
SPXW 1,247945/52,0492%/+1.030,091/min17/8m; SPY
1,346342/53,2787%/+1.381,556/min17/8m. Mejor resultado actual, pendiente de
reproducción/auditoría formal y no promocionable por ser post-outcome.

V4 real desde `b421acd3`: `PASS_INCREMENTAL_DEVELOPMENT_2026_DATA_NOT_OPENED`,
train1482/dev735/sources738/mismatch0. Auditor independiente PASS, refit/model/
dataset/ledger/gates exactos; summary `a2beced1...21b`. Evidencia pendiente de
commit/push; después solo data gate 2026 outcome-free. 2026 intacto.

Gate vintage2026 V4 `FAILED...CLOSED`: sensors QQQ/SPY 127 sesiones cada uno,
508 captures/shared391.556; cinco fronts nuevos con Greek-only92/IV-only516
(QQQ 20260624/26, SPY 20260624/25/26). Greek∩IV está limitado a los cuatro
repairs V1R1, así que no capture/data gate/outcomes2026. V4 cerrada outcome-free.

Cash-only post-V4 cerrado: logistic summaries/spot/cross-cash, shallow HistGB/RF
y raw35x1m no pasan seis ticker-año. Mejor raw pooled PF2024
1,169/0,903/0,916; PF2025 0,985/1,480/1,483. Cambio de régimen; no V5 ni 2026.

2026-07-22: V2 post-outcome predeclarada antes de nuevos opens cash. Modelo
único pooled logistic L2 C0,1, 29 features fijas y target direct-vs-inverse.
DEV_A train2023/test2024H1; DEV_B train2023+H1/testH2. Cash feature clocks
09:30..10:35 open-only; mapping QQQ←QQQ/SPY←SPY/SPXW←SPY intacto. 2024 es
solo development; 2025/2026/live cerrados hasta gates+freeze.

Evaluator V2 outcome-scoped implementado y aún no ejecutado: input/runtime SHA,
source rehash, pushdown 66 opens, dataset/modelos/ledger y gates inmutables.
Focal7/cross-venue74/Ruff/compile PASS. Commit/push antes del único run default.

Primer run V2: fail-closed pre-cash por colisión `signal_pressure` entre ledger
y sensor, output inexistente. Fix namespacea `sealed_signal_pressure` para
auditar paridad; focal8/cross-venue75/checks PASS. Cero nuevos opens/outcomes.

Segundo run pre-cash: zeros QQQ 20231116/20231215, ya no-trade en V1. Nueva
clarificación congela el set y los excluye solo del train; 739 filas fit, 743
predicciones 2024 sin cambio. Cualquier cero adicional falla. No output/cash.

Fix exact-set listo: focal10/cross-venue77/checks PASS; todavía pre-cash. Debe
commit/push antes del próximo default run.

Tercer run pre-cash/sin output: segundo merge redundante de pressure. Fix
direct-parity listo; focal11/cross-venue78/checks PASS.

Cuarto run: primer cash censo, fallo pre-fit por única fuente SPY20230605 con
opens0 09:55/09:56 (1/1.487). V2R1 predeclara ventana uniforme10:00–10:35,
36/35 clocks/returns y horizons35m/15m/5m. Sin fill/exclusión/output/2025.

V2R1 code ready: reproduce censo inválido original y usa solo36 opens válidos;
focal12/cross-venue79/checks PASS. Pendiente commit/push y run.

V2R1 real `PARTIAL_DEVELOPMENT_EDGE_2025_CLOSED`: DEV_A PF
0,667/0,928/0,772; DEV_B0,738/0,992/1,123 QQQ/SPXW/SPY. Solo SPY H2 pasa;
advance false, sources1.487 mismatch0. Auditor refit/rehash listo, suite82;
commit/push antes de audit default. 2025/2026/live cerrados.

Auditor V2 real PASS: refit/ledger/gates exactos, sources1.487 mismatch0,
evaluation summary `c79bddfe...f03a7`. Compactos listos; commit/push antes V3.

V2 evidence committed `3bdb389c`. V3 predeclarada: orientation mensual pooled
por hit-rate directo del mes anterior >=0,50; 2024 development, 2025 primer
outer. Sin ML/grid/cash extra. Implementar dev+audit+freeze antes de 2025.

Evaluator V3 dev listo/unexecuted, focal5/cross-venue87/checks PASS. Commit/
push antes de default; no path outcomes2025.

V3 dev real PASS incremental: PF1,232/1,396/1,408, WR51,4/55,9/56,7%, net
positivo, min19/18/18; solo8/12 meses positivos. Auditor listo suite90; commit/
push antes de audit y freezer. 2025 intacto.

Auditor V3 real PASS: states12/trades743/hashes/gates exactos, summary
`6a688225...50f5`. Compactos listos; commit/push antes de freezer 2025.

V3 dev+audit committed `627f3b20`. Freezer, runner secuencial outer2025 y
auditor independiente listos pre-outcome; manifest/inputs/código/events/counts/
estado inicial quedan fail-closed. Focal9, cross-venue/native-clock100 y checks
PASS; código committed `5fe51e70`. Freeze real: 735 eventos/min17, enero
INVERSE desde 25/56 hits diciembre2024; manifest `f45e7f1b...646ed`, outcomes
false. Commit manifest → one-shot2025 → audit. No 2026/live/systemd.

2026-07-22: runner frozen committed `b53dcaa3`; único V1 outer2024 cerrado
`NO_AGGREGATE_EDGE`. Pooled 743/PF0,761071/WR42,665%/-3.130,133bps. Por ticker:
QQQ249/PF0,866939/-662,668/min19/6 meses positivos; SPXW247/0,698912/
-1.220,988/min18/5; SPY247/0,693382/-1.246,477/min18/5. No advance a 2025.

Auditor inicial falló sin output por hash DataFrame post-CSV; fix `95609e21`
separa hash de bytes y recomputación semántica, suite67/checks PASS. Auditor
posterior `PASS_INDEPENDENT_OUTER_2024_AUDIT`, sources743, mismatches0. V1
cerrado; futura V2 trata 2023–2024 como development y mantiene 2025/2026
intactos hasta predeclaración+freeze secuencial. Live/systemd intactos.

2026-07-22: data gate cross-venue V1R1 ejecutado una sola vez desde `90ffd155`
y `PASS_DATA_GATE`. Sessions/rows1.506, captures3.012, local-valid1.504,
mapped-valid1.502, economic1.478, inventory16.566; min coverage0,992063,
distinct237, min month17. Manifest/feature SHA `492f51c8...0452e`/
`d4335ad8...566062`. Errores exactos: SPY 20241209/20241216 sin CALL25
persistente y su propagación mapped a SPXW; no hay quinta discrepancia.

Auditor independiente posterior PASS: hash/size mismatches0, mapping parity
PASS, source audit `6d3180f1...08194`, audit summary `7700b087...e85dac`.
Outcomes/underlying/outer2024+/live false. Compactos V1R1 listos para
commit/push; solo después freezer → commit manifest → one-shot outer2024.

Pre-freeze: evaluator apuntaba al nombre compacto V1 obsoleto. Fix permitido y
outcome-free: `DATA_GATE_DIR` → V1R1 committed + regresión; commit/push antes de
crear manifest. Cero cambios de señal/eventos/gates.

Fix pushed `811e729f`, suite66/checks PASS. Frozen runner ya generado:
`PREEXECUTION_FROZEN`, events/sources743/743, event IDs `2d56cf96...b124c4`,
manifest `339c0793...126b72c`, outcome/execution/outer flags false. Falta
force-add/commit/push antes del único outer2024.

2026-07-22: V1 queda inmutable `NO_SEAL` con 3.008 capturas y cuatro errores
Greek/IV congelados. V1R1 ya pasó 4/4 desde `0b7cc6dd`: shared2828,
unilateral8 audit-only, missing0, extras8, revised0, crossed0. Seal/index/audit
SHA `81ded7dd...bd9d`/`670dd0ce...2fe0`/`910bac85...1c6a`; compactos committed
en `53872c39`. Sin outcomes ni PF nuevo.

Composite sealer V1R1 implementado pre-run. Revalida offline 3.008 V1 + 4
repairs, incluyendo endpoint/request params/provenance/runtime/hashes, y genera
un índice lógico multi-root sin copiar raws. Primer intento desde `a352d544`
falló cerrado pre-output por RangeIndex del CSV unilateral frente al índice
original recomputado; valores/hashes iguales. Fix `reset_index(drop=True)` y
regresión sobre los cuatro repairs reales: repairs+composite `13 passed`, suite
cross-venue `63 passed`, Ruff/compile PASS. Fix committed `963f91c9`; reintento
PASS 3.012/3.012, sessions1.506, rows7.246.230, shared2.415.402, unilateral8,
missing0, revised79, crossed135. Seal/contract/index/summary SHA
`5b97ebc5...cf84f`/`68714d77...8c046`/`e5a669b7...3a0e`/
`41deb014...df65`. Pendiente inmediato: versionar/commit/push evidencia.

No ejecutar todavía full auditor ni data gate: ambos asumen un root único y
Greek=IV. Tras el composite hay que adaptarlos a `storage_root` por capture y a
`Greek∩IV` solo para los cuatro IDs; luego full audit → gate → auditoría →
freeze → outer2024. 2024–2026 y live siguen cerrados.

Clarificación composite-consumer congelada pre-outcome: hashes exactos, compact
byte-parity, rutas por capture, V1 Greek=IV y cuatro excepciones `Greek∩IV` con
conteos 0/2,2/0,0/2,0/2. Commit/push documento → implementar/testear auditor y
builder → commit/push código → ejecutar full audit; no outcomes.

Auditor+builder composite-aware implementados: default V1R1, compact/local
byte parity, revalidación por contrato, sidecar paths por role/root, inventario
multi-root y `align_vintage_modalities` con conteos frozen. Test real composite
y fallo estricto V1 incluidos. Focal15/combinada65, Ruff/compile PASS. Pendiente
commit/push → full audit default; data gate no ejecutado.

Full audit one-shot desde `2b33fe5a` PASS: captures3012, sessions1506,
rows7246230, raw bytes1369860204, sources6024, shared2415402, Greek-only2,
IV-only6, missing0. Revalidation SHA=index `e5a669b7...3a0e`; audit summary file
SHA `437483b0...4769`. Sin underlying/outcomes. Pendiente commit/push compactos
→ ejecutar builder default una vez; no outer2024.

Respuesta autoritativa junio/julio 2026: la familia activa cross-venue sigue
sin outcomes 2026 (captura 2024–2025 PID42112: 424/3.012, errors0 a las 03:09).
No se puede afirmar que sea rentable. El cerrado `DIRECTIONAL_VOL_COMPLEX_V1`
fue positivo en junio QQQ/SPX/SPY con 21 trades, WR57,14/61,90/61,90%,
PF1,249/1,779/1,764 y +161,459/+237,701/+233,476bps. Julio MTD tuvo 10 trades,
PF1,133/1,098/1,888 y PnL positivo; falla frecuencia y QQQ/SPX PF1,20. Jan–Jun
agregado PF1,039/0,993/0,898 y meses positivos3/4/3: no promovible.

Auditor outer-2024 independiente implementado pre-outcome: recompone economía,
tablas/gates, hashes de inventario/source-audit y contrato SPY→SPXW. Suite
cross-venue `50 passed`, Ruff/compile clean. No ejecutar antes del one-shot 2024.

Contrato data gate cross-venue congelado pre-outcome: 1.506 sesiones/3.012
captures, full seal obligatorio, revalidación offline raw/parquet/manifest y
sources. Sidecar certifica key+option timestamp 10:30/10:35; delta/IV/bid/ask
siguen vintage y native extras/sizes se excluyen. Mapping fijo QQQ←QQQ,
SPY←SPY, SPXW←SPY exact-date. Gates >=90% coverage ticker-año, >=50 estados,
zero<99,5%, >12 cada mes. El builder posterior debe respetarlo; no outcomes.

Builder cross-venue implementado pre-outcome:
`build_cross_venue_calendar_rr_leader_v1.py`. Exige seal PASS, verifica blobs
del capturador, revalida 3.012 raw/parquet/manifests/sources, lee solo spots
10:30/10:35 y aplica exact-date SPY→SPXW. Suite combinada `34 passed`, Ruff y
compile clean. No se ejecutó sobre captura parcial ni abrió outcomes.

Runner 2024 predeclarado: única policy sign/sensor ya congelados, cash
10:36→13:36/180m/1bp, 2–3bps solo sensibilidad. PF>1/WR>45/neto>0/min13 por
ticker permite abrir 2025; promoción conserva PF>1,20 y todos meses positivos.
Freezer/evaluator implementados, aún no ejecutados: exact two-row outcome read,
frozen event IDs y costes1/2/3. Suite combinada `45 passed`, checks clean. No
manifest hasta data gate PASS committed; 2024 outcomes cerrados.

Live parity audit `NOT_LIVE_READY`: feed usa weekly-Friday en vez de next-expiry,
no consulta bid/ask-IV y no persiste contratos t0→t1; bot tiene scheduler/caps
distintos. El cash proxy tampoco prueba payoff de opción ask→bid. No se tocó
live. Si pasa toda la secuencia, integrar paquete nuevo/paper-only con builder
compartido, next-expiry, IV exacta y un signal diario sincronizado.

Auditor full post-seal implementado: reconstruye/revalida 3.012 captures y
6.024 Greek/IV sources, compara capture index y produce evidencia compacta sin
underlying/outcomes. Falla antes de `_seal`. Suite combinada `48 passed`, checks
clean. Queda versionado en este checkpoint; no ejecutar durante capture.

Auditor data-gate implementado: rehash de 16.566 fuentes, equality completa
capture-index, gate recomputation, exact SPY→SPXW parity y schema outcome-free.
No lee underlying values. Suite combinada `53 passed`, checks clean. Queda
versionado en este checkpoint y se ejecuta solo después del gate real.

Nueva condición de promoción del usuario: si y solo si el mapping cross-venue
pasa causalmente 2024→2025→2026 en los tres tickers, integrar el contrato en
`realtime_feed`/`ai_bot` y systemd. Gate vigente: PF>=1,20, WR>=45%, >=13 por
mes completado, todos los meses positivos, ask→bid, hold30–180m y cero overlap.
Junio 2026 cerrado y julio 2026 MTD deben ser positivos; julio a día17 sigue
siendo shadow incompleto. Primer despliegue `paper_order_intents=true`, con
paridad/validador/smoke systemd y comandos VPS exactos. Producción no se toca
antes de PASS.

Full capture activo PID42112 desde d013a299/workers2. Checkpoint 03:01 334/3012,
errors0/stderr0. Output/logs D:/ThetaData. No duplicar; outcomes cerrados.

Full capturer cross-venue implementado pre-run: universo SHA exacto3.012,
atomic dirs, resume con revalidation, root contract/code/runtime/provenance y
seal solo 100%. Suite total16/Ruff/compile PASS. Falta commit/push y launch
único workers2; no hay outcome 2024.

Erratum full count sin outcomes: no1.503/3.006 sino1.506 sesiones/3.012
captures (502/ticker). Proyección 8.111.316 rows/1,428GiB, gate PASS. IDs SHA
`447e771b...5ce4`. Full capturer debe exigir el conteo corregido; no excluir.

Cross-venue native-clock `PASS_PREFLIGHT`: 12 sessions,24 captures,64.632 rows,
missing/extra/revised/crossed=0; independent hash audit PASS. Full projection
1.503/3.006,8,095M rows,1,425GiB raw. Capture167118b0/seal8828bd72; seal SHA
`d33e01a6...eee6d`. Autoriza full capture, no outcomes ni rentabilidad.

Sealer offline cross-venue listo: valida blob/hash base `167118b0`, 48 fuentes,
24 raw/parquet/manifests y exact keys, sin network. `11 passed`, Ruff/compile.
Falta commit/push y un único `--seal-existing-staging`; aún no PASS agregado.

Cross-venue preflight: 24/24 captures desde `167118b0`, missing/extra/revised/
crossed todos0, sin errors ni outcomes. Timeout externo cerró stdout antes de
index/cost/seal; staging preservado y aún no PASS. Única reparación autorizada:
sealer offline committed que rehash/rebuild todo sin red y renombra atómicamente.

Capturador cross-venue native-clock listo preejecución: 12 sesiones/24
front-back, exact wildcard1m 10:30–10:35, full vintage Greek/IV key coverage,
raw/parquet/manifest/JAR/runtime hashes y cost projection 3.006 captures.
`9 passed`, Ruff/compile clean; remoto CONNECTED. Falta commit/push antes del
único preflight. Outcomes/2026/producción intactos.

Nueva familia autorizada: `CROSS_VENUE_CALENDAR_RR_LEADER_V1`. Diagnóstico
2023 post-outcome: cash SPXW/SPY corr0,999733/sign246/246, pressure corr0,580247
y acciones iguales148/246. Mapping fijo QQQ←QQQ, SPY←SPY, SPXW←SPY deja
PF1,173/1,073/1,072, WR51,82/50,40/50,00%, netos positivos y min19; meses
positivos7/5/5, aún no promoción. 2023 es design, 2024 primera validación,
2025 secuencial y 2026 holdout.

Antes de outcomes: preflight quote-sidecar de 12 sesiones/24 front-back para
reparar option timestamps 2024–2025, exact clocks 10:30/10:35, full vintage key
set y raw/JAR/runtime hashes. No inferir `underlying_timestamp` ni reemplazar
vintage bid/ask. Alternativas breadth e index-ETF cerradas sin outcomes por
min3/min12 y ausencia NDX/NDXP/SPX-pairs. Calendar-RR base a 2bps PF0,999.

Calendar RR cerrado `PARTIAL_INCREMENTAL_EDGE`: 739 trades, WR50,07%, PF1,0583,
+729,69bps y 12/36 cells. QQQ PF1,173, SPY1,073, SPXW0,912; min19/mes. Auditoría
independiente PASS. Es progreso PF>1, pero no abre outer ni permite rescatar
ticker/mes/signo/delta. 2024–2026/producción intactos.

Calendar-RR runner manifest preejecución SHA `f00a7ef0...35f79`, base
`79dfe416`, 741 eventos, outcome false. Falta commit/push del seal; después un
solo development 2023. Outer/2026/producción intactos.

Calendar-RR evaluator/freezer implementados pre-outcome, `12 passed` y checks
clean. Scope fijo 741 eventos 2023, hash gate, sign pressure, open10:36→13:36,
hold180/coste1 y 36 gates. Pendiente commit y manifest freeze; aún no hay PnL.

Calendar RR `PASS_DATA_GATE`: 747/750, coverage mínima99,2%, min19/mes,
distinct states min233, 3.750 fuentes rehasheadas y 3 fallos explícitos de
quote/key. Feature SHA `de0ec4b3...2858b`, manifest `604f53b2...a9c1`.
`outcome_accessed=false`; siguiente etapa es commit compactos y freeze del
runner 2023. 2024–2026 intactos.

Builder calendar-RR implementado pre-outcome: `8 passed`, Ruff/compile clean.
Inventario 2023 750 sesiones/250 por ticker/min19 mensual; smoke real de tres
tickers pasa clocks/joins/contratos. Falta commit/push y full data gate inmutable;
no hay PnL ni acceso a 2024–2026.

Nueva rotación outcome-free. `EXACT_EXPIRY_OI_DELTA_V1` falla frecuencia:
156 pares exactos 2023–2025, mínimo4/mes, sin outcomes. Se predeclara
`CALENDAR_RISK_REVERSAL_PRESSURE_V1`: cambio 5m del RR25 0DTE menos next-expiry,
contratos t0 fijos, data gate/desarrollo 2023 y 2024–2026 cerrados. No existe aún
feature válida ni PF/WR/PnL.

`OPTION_PARITY_PRESSURE_V1` cerrado `NO_AGGREGATE_EDGE`. One-shot 2023: 730
trades, WR48,63%, PF0,874751, -1.689,31bps, 10/36 celdas. QQQ/SPXW/SPY PF
0,947/0,843/0,819 y todos gross negativos. Auditoría independiente rehasheó
744 fuentes y reprodujo ledger/gates. Stop: no invertir/rescatar ni abrir
2024–2026. Producción intacta.

Manifest de runner parity generado pre-outcome desde `5cc1c936`, SHA
`f3819d88...26972`: 744 eventos 2023, scope/policy/gates/hashes fijos,
`execution_started=false`. Falta commit/push del manifest; después procede un
solo desarrollo 2023. 2024–2026 siguen cerrados.

Runner económico parity implementado, aún pre-outcome: evaluator+freezer,
`13 passed` y Ruff clean. Hash-check del data gate, rutas de retorno limitadas a
2023, manifest frozen obligatorio, ledger signo/10:36→13:36/180m/1bp y 36
celdas exactas. Falta commit/push y freeze; no existe resultado económico.

## Checkpoint OPTION_PARITY_PRESSURE_V1 V1R1

`PASS_DATA_GATE`: 2.256/2.256 sesiones, cero errores, mínimo 18 eventos/mes,
cobertura anual 1,0 y mínimo 199 estados distintos por ticker-año. Feature
parquet 2.256x28 SHA `45bca098...d5100`; inventario de 5.953 fuentes SHA
`4a1fe920...f556`. Outcomes y 2026 siguen cerrados. Próximo paso: congelar
runner determinista y ejecutar una sola evaluación de desarrollo 2023; outer
2024–2025 exige PASS en las 36 celdas mensuales y 2026 exige después PASS outer.

**Corte:** 17 de julio de 2026, 00:30 Europe/Madrid

**Objetivo:** policy 0DTE causal y live-equivalente para SPXW, QQQ y SPY.

**Gate económica vigente por ticker:** PF `>1,20`, WR `>45%`, más de 12
trades/mes y PnL positivo en todos los meses walk-forward. La antigua gate
PF `>=1,3`, WR `>=50%`, `>=18` trades/mes y hold `>=30m` se conserva como
objetivo estricto, pero no debe mezclarse con la gate solicitada más reciente.

**Enero–15 julio 2026:** ya consultado por varias familias adaptativas; no es un
holdout confirmatorio nuevo. **Producción:** intacta.

## Rotación posterior a EXISTING_DATA_EXECUTABLE_UTILITY_V1

La unión causal general quedó `FAILED_ECONOMIC`; no se retunea. La siguiente
familia focal es `CROSS_MARKET_TRANSMISSION_V1`: E0 Pairwise frente a E0 más 28
dinámicas exactas beta-neutral/lead-lag sobre SPXW-SPY, QQQ-SPY, QQQ-SPXW y
target-TLT. La fuente son parquets underlying 1m ya existentes; cada decisión
exige 30 barras cerradas exactas y no permite as-of/floor/nearest.

El modelo económico predeclarado usa nueve cuantiles LightGBM por lado para
reconstruir utilidad y probabilidad de retorno positivo. El desarrollo se limita
a 2022-2023. 2024/2025, todo 2026 y producción continúan cerrados en este
checkpoint; todavía no existe resultado económico de esta familia.

V1 no pasó el data gate: el master contiene decisiones post-cierre en medias
jornadas y produce RV cero/paths stale. El build se detuvo sin vista ni outcome.
V1R1 predeclara la única reparación causal: excluir completas nueve sesiones
early-close por calendario (1.072 filas), conservando 96.553 sesiones normales.
No se modifica el mecanismo ni se abre 2024/2025.

V1R1 encontró además lead/lag indefinido por SPXW plano en una ventana normal;
queda `BLOCKED_DATA` sin desarrollo. La rotación activa es H-TPOVALUE1:
developing POC/VAH/VAL y migración TPO target-only, 36 campos en bloque, mismo
modelo quantile y mismo contrato económico. Aún no hay resultado económico.

La semántica TPO quedó completa antes del build: bins, fronteras, touches,
denominadores, period=1m y distinctness están congelados; no se seleccionarán
después de ver labels.

V1R1 explicita también el centro de POC, los bordes VAL/VAH,
`value_location=(close-VAL)/(VAH-VAL)` y efficiency sobre h transiciones 1m.
No hay fallback para denominadores inválidos.

El builder TPO es reanudable por ticker-sesión: parquet atómico y manifest
último, con hashes de source, claves, builder, protocolo, allowlist y features.
Una segunda pasada real reutilizó el checkpoint exacto; los full runs no deben
reiniciarse desde cero tras una interrupción.

El build completo terminó `PASS_EXACT_TPO_VALUE_VIEW`: 96.553x69 y
2.777/2.777 sesiones, vista SHA `fded87a...078fe`, manifest SHA
`693a1708...1331`. Las 36 variables pasan 432 celdas de finite/distinctness
(mínimo 4 estados; máximo modal `0,9243992606`). Esto es solo un gate causal:
no se han calculado PF, WR, frecuencia ni PnL. La investigación pasa ahora al
desarrollo económico reanudable 2023-04..12; no se abrirá otro dataset.

El backtest económico también es reanudable: cada mes/ticker/brazo queda sellado
por manifest-last y hashes de inputs, código y outputs. Una prueba construyó 6
folds y la repetición reutilizó 6/6; suite focal `33 passed`. Ya no hay una fase
de datos pendiente antes de medir rentabilidad.

La medición económica ya ocurrió y H-TPO falló en la primera celda obligatoria:
SPXW 2023-04 X1, 0/42 grids pasan inner enero-marzo. El near-miss tuvo 68 trades,
PF pooled 0,922 y -1,831R; enero y febrero perdieron. Outer abstuvo. Como el
criterio exigía todos los ticker-mes, el desarrollo se cerró matemáticamente y
se detuvo tras 2/54 folds; no se abrieron 2024/2025/2026.

La única idea en cola es `KING-GEX-SLOPE1`: pendiente/sign flip de net GEX como
mecanismo, tomada conceptualmente de `live_king_node.py`, no sus calibraciones o
defectos de implementación. Todavía no es evidencia ni familia activa.

El preflight causal ya la activó: fuente wall-state existente, 109.785
observaciones con lag45 exacto y mínimo 19 sesiones de señal/mes en 2023. La
prueba económica es fixed-rule, no otro modelo: K0 nivel de gamma; K1 exige nivel
y pendiente alineados y decide momentum/reversión con ret15. No hay payoff aún.

El replayer ya está implementado y testeado (`26 passed`), con 72 checkpoints
mensuales reanudables y lectura limitada físicamente a outcomes 2023. Falta
únicamente commit/push del código y su ejecución económica.

El primer intento no calculó payoff: falló porque exigía que 8.668 timestamps
wall extra existieran en el master. Las 20.309 oportunidades master sí tienen
wall exacto 100%. Se congeló master-left one-to-one como única corrección; no
hay aún PF/WR/PnL King.

El fix revalida además el census K1 de 13.286 señales y el hash del amendment;
regression `5 passed`. Sigue pendiente el relanzamiento económico.

Este documento conserva resultados y decisiones. La operación live y los pasos de
reanudación están en `CODEX-HANDOFF.md`; la literatura está resumida en
`SUMMARY-articles.md`.

## 1. Evidencia base

### Dataset causal executable-quote

- ThetaData 0DTE con entrada ask y salida bid.
- Rejilla principal 10:35–14:30/5m; vista early 1m separada ya construida.
- Stop -60%, TP 1000%, trailing 50%/25%, hold 30–180m.
- Cupos/cooldowns y una posición por ticker equivalentes a runtime.
- Dataset wall/pairwise sellado hasta 2025:
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.

Baseline nested causal enero–mayo2026:

| Scope | Trades | WR | PF | PnL R | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 324 | 43,83% | 0,909 | -9,287 | 48 | 40% |
| QQQ | 94 | 44,68% | 0,984 | -0,492 | 15 | 40% |
| SPXW | 107 | 42,99% | 0,832 | -5,816 | 10 | 40% |
| SPY | 123 | 43,90% | 0,919 | -2,979 | 19 | 40% |

## 2. Por qué el paquete productivo no es el nuevo baseline científico

El static-union live sigue operativo, pero thresholds/reglas fueron elegidos sobre
enero–junio2026, los mismos meses usados para reportar su rentabilidad. La auditoría
pre-2026 entrenó hasta septiembre y aplicó reglas fijas a oct–dic2025:

| Ticker | Trades | WR | PF | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | 75 | 41,33% | 1,158 | 21 | 2/3 |
| SPXW | 64 | 43,75% | 1,686 | 19 | 2/3 |
| SPY | 125 | 34,40% | 0,794 | 26 | 0/3 |

El volumen existe; fallan dirección y estabilidad.

## 3. Experimentos de representación cerrados

| Prueba | Resultado | Decisión |
| --- | --- | --- |
| Flat runtime | 481 trades, PF 0,900, -15,094R | Rechazado |
| Modal runtime | 491, PF 0,858, -21,989R | No MJEPA intra/cross-modal |
| Historia 2025 | 495, PF 0,863, -20,174R | Control |
| Historia 2022 | 440, PF 0,764, -31,476R | Mejor OOF, peor economía |
| Portfolio Var-JEPA | 0 configs, incertidumbre-error mediana -0,180 | Cerrado |
| PatchCore | correlación error 10/15; 0/1.470 configs | Drift solamente |
| AdaJEPA shadow | error latente mejora 15/15 y 277/281 días | Downstream requerido |
| AdaJEPA downstream | 0/210 configs, 30 abstain | No live |
| h1→h6 | 0/210; h6 peor MAE/RMSE/dirección | No otros horizontes |
| Spot skip | 0/210 en ambos arms | No más bloques por tanteo |

Conclusión: mejores embeddings no trasladaron edge al payoff.

## 4. Reconstrucción del mecanismo executable

### Objetivo, IB temprano y cadencia

- GBT return abstuvo 15/15; GBT win operó dos folds SPY negativos.
- El PnL dense15 legacy estaba concentrado antes de 10:30, pero usaba IB completo
  09:30–10:30, hasta 30 minutos futuros.
- Vista early causal sin IB: 5m solo SPXW, 39 trades, PF 1,109; QQQ/SPY abstain.
- Cadencia 1m añadió 62.280 filas con paridad exacta. SPXW enero: 20 trades,
  WR 40%, PF 1,220; después drift y abstención. QQQ/SPY 0/5.
- Selector direccional 1m: 60 trades, WR 36,67%, PF 0,976, -0,572R.

Conclusión: más candidatos no arreglan la dirección.

### Gates de régimen

IV skew/spread/abs-return/IB range mejoraron folds aislados. Ejemplo: SPXW febrero
R1, 9 trades, PF 1,452. Ningún arm mantuvo las gates todos los meses. Replay C0 y
thresholds auditados con equivalencia exacta.

## 5. Pairwise opportunity/side

Vista 2022–2025, 97.625 filas, 99 celdas científicas.

- P1 vs C0: balanced-accuracy wins `57/99`, mediana `+0,004`, `p=0,117`;
  Spearman positivo `58/99`, mediana `0,0303`.
- Oracle side no causal: PF `4,55..11,73`, WR `73,5..86,7%`; headroom existe.
- Always CALL/PUT y momentum/contrarian pierden.

Bug corregido: `opt_exit_minutes` era duración, pero se restaba el minuto de
entrada. Tras corregir:

| Arm | Scope | Trades | WR | PF | PnL R |
| --- | --- | ---: | ---: | ---: | ---: |
| C0 V1r1 | SPY | 61 | 45,90% | 0,998 | -0,040 |
| P1 V1r1 | SPY | 23 | 34,78% | 0,427 | -4,930 |

SPXW/QQQ abstienen. Frecuencia inner pasa en 85–97% de configs P1; PF/WR son el
cuello.

Cambios aislados posteriores:

- magnitude-weighted: 48/99 BA wins, PF 0,430;
- physics/context 154 features: 55/99; QQQ PF 0,409, SPY 0,810;
- estas 154 features no incluían distancias a Greek walls ni IB previos.

## 6. Wall interaction executable V1/V1r1

Se unieron las labels ask→bid con `training_data_spx_qqq_spy.parquet`:

- 86.729 filas útiles `202208..202512`;
- join uno-a-uno y spot exactamente igual;
- feature input hash `5f908e11090ea6566e3eadeba0a436ab5d01cf99955d6acc5050eae264fe13b5`;
- sin 2026.

### V1

Regla fija `magnet/rejection/acceptance` con max/min gamma, zero gamma, max/min
DGEX, IB/Fibonacci actual y D1–D5.

| Ticker | Trades | WR | PF | PnL R | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1.564 | 40,54% | 0,865 | -75,366 | 52 | 37,50% |
| QQQ | 903 | 44,41% | 0,832 | -49,816 | 30 | 33,33% |
| SPY | 496 | 44,76% | 0,899 | -15,422 | 17 | 45,83% |

El control de proximidad también pierde: PF `0,872/0,903/0,935`.

### V1r1

La atribución demostró que solo 29–37% de los rejection habían cruzado el nivel.
V1r1 exige pierce real y regreso al lado defendido:

| Ticker | Trades | WR | PF | PnL R | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1.557 | 42,32% | 0,910 | -48,846 | 52 | 29,17% |
| QQQ | 894 | 44,18% | 0,845 | -45,816 | 30 | 33,33% |
| SPY | 496 | 47,58% | 1,008 | +1,118 | 17 | 54,17% |

Diagnóstico, no policy seleccionable:

- acceptance CALL: ~58–63% de acierto spot a 30m en varias muestras, PF opción ~1;
- resistance-rejection PUT: SPY PF 1,536; SPXW/QQQ ~1,09;
- magnet CALL: QQQ PF 2,230/42 trades, SPY PF 1,307/25;
- señal insuficiente para 18 trades mensuales y estabilidad completa.

No retunar subfamilias/horas/direcciones sobre este output.

Commit autoritativo: `b4b22d4`.

## 7. Causa actual

Las 182 features live describen distancia y algunos flags, pero no el estado real
del wall:

- falta DEX por strike y wall CALL/PUT de delta;
- falta magnitud de cada wall;
- falta concentración y diferencia top1/top2;
- falta persistencia/edad/migración;
- se mezclan soporte, resistencia, magnet y acelerador sin medir régimen.

Una ubicación sin fuerza no prueba la hipótesis económica.

## 8. Trabajo activo: wall-state GEX/DEX

Predeclaración:

```text
research_papers/JEPA/WALL_STATE_GEX_DEX_DATASET_PREDECLARATION_V1.md
```

Primitivas implementadas:

```text
neural/jepa/wall_state_features.py
```

Primitivas y builder por sesión ya implementados: `15 passed` en la suite wall.
Se cubren duplicados OI, orden determinista, separación de walls, persistencia
causal, cutoff future/2026, join de OI, selección de preflight y auditoría de
cobertura y entrada CLI directa. El preflight ThetaData real pasó: 144/144 filas,
cero errores, cobertura de eventos 100% en los tres tickers, spot máximo a
0,000572 bps y delta walls materialmente distintos de gamma.

Build completo aprobado: 135.120 × 148, 2.815 sesiones, SHA `94e311e0...df8ef`.
Cobertura de las 95.424 claves executable 100% por ticker y spot máximo
0,000572 bps. Se excluyó QQQ 2023-12-27 por strikes Greeks `.78` frente a OI
entero, sin imputación ni eventos perdidos. Un primer build descubrió y corrigió
uso futuro de quotes `:30` al redondearlos a minuto; ahora solo usa `HH:MM:00`.

Diseño congelado de separabilidad física V1: cuatro walls
CALL/PUT gamma/delta, magnet/rejection/break a 30/60/120/180m, D0 vs S1 vs S2
state+IB, holdouts 2024/2025 y gates fijas sobre 48 celdas por arm.

Resultado ejecutado: REJECTED. 26.090 candidatos, 48/48 celdas válidas. S1 gana
17/48 (mediana ΔAUC -0,00154); S2 gana 22/48 (mediana -0,000077; p=0,567), AP
19/48 y log-loss 17/48. Magnet hit ya es separable por distancia (D0 mediana AUC
0,805), pero rejection/break queda 0,511/0,519/0,516 para D0/S1/S2. Mínimo
mensual resuelto 30m QQQ/SPXW/SPY 6/0/0; 60m 14/4/5. No se autoriza payoff.

Nueva fuente predeclarada, aún no ejecutada: flow-at-touch con bar de opción
completado `[t-1,t)`, sign proxy close-vs-mid, agregación 1/5/15m full-surface y
30 bps alrededor del wall. Feasibility de volumen capturado 96,98–99,58%. F1 debe
superar F0 en 16/24 celdas y mantener >=18 resoluciones mensuales a 30/60m.

Debe producir, solo con snapshot actual:

- CALL/PUT gamma wall;
- CALL/PUT delta wall;
- max/min net GEX, DEX y DGEX;
- strike, distancia, magnitud signed-log, concentración, HHI, effective strikes,
  dominancia y separación;
- same/move/magnitude-change a 5/15/30m y edad causal del wall.

Manifest fuente: `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
Cutoff físico: `<=20251231`. Build por sesión con hasta 16 workers.

Después del data gate se predeclaran labels físicos del subyacente
`magnet_hit/true_rejection/accepted_break` a 30/60/120/180m. Solo si wall state
supera distance-only en los tres tickers se autoriza un payoff head ask→bid.

## 9. Invariantes

- No outcomes, future highs/lows o labels como features.
- No abrir junio de 2026.
- No modificar paquete productivo/systemd durante research.
- No relajar gates por ticker.
- No seleccionar con el mismo mes reportado como OOS.
- Versionar predeclaración, tests, resultados compactos y handoff con commits
  explícitos; no añadir artefactos untracked ajenos.

## 10. Wall-surface flow V1R1: implementación y bloqueo de procedencia

V1R1 quedó implementado y predeclarado antes de outcomes. Introduce un único
bloque F1 de volumen/count/close-notional quote-relative en ventanas completadas
1/5/15m, comparado con F0 distance/approach/RV/time. La evaluación física sigue
siendo rejection versus accepted break; no se ha conectado option payoff.

La suite relevante pasa `55 passed`. Se corrigieron half-days, cierre RTH de
labels, fechas de fuente, duplicados, alias, episodios, pierce verdadero,
denominadores/missingness y lock exacto de Python/dependencias. Preflight real:
8 × 173, 3/3 sesiones, cero errores.

El censo de 325.753.830 filas Greek descubrió 1.441/2.519 sesiones sin timestamp
nativo. Es una falla de procedencia, no evidencia contra el mecanismo. El data
gate ahora las bloquea. El endpoint nativo de quotes permite backfill falsable y
aporta bid_size/ask_size; se implementó sidecar inmutable con raw/JAR/source
hashes, cobertura 100% de keys históricas y extras auditadas sin incorporación.
No se autoriza label runner hasta congelar dataset+runner manifest.

La auditoría del productor underlying confirmó 1s→floor-minute y un reparador
con `bfill` para filas totalmente nulas. Los ficheros históricos carecen de hash
de productor/contrato fuente; por ello se añadió gate de contenido completo.
Preflight: 0 grids RTH incompletos, OHLC/tick_count válidos y spot máximo
0,000519 bps. La limitación de linaje se conserva, no se oculta.
El audit completo pasó 2.519/2.519; registró tres ceros 09:54–09:56 de SPY
2023-06-05 fuera del primer timestamp consumible 10:19, sin imputar ni excluir.

El backfill terminó con `PASS_NATIVE_TIMESTAMP_BACKFILL`: 1.441 sesiones,
125.557.990 filas, cero missing keys/errores, 500 keys extra, 5.720 crossed y
2.915 revisiones bid/ask en 24 sesiones. Índice SHA
`0abe0ac2f9dcccec4574ee10e4f10ef2904000c80a0cf5fb8f5a90ef333f754a`.

Estado científico: `H-FLOW1 = NATIVE_CLOCK_SEALED_DATA_GATE_PENDING`,
`H-QSIZE1 = AVAILABLE_NOT_TESTED`.
No hay rentabilidad nueva que reportar; 2026 y producción siguen intactos.

Backfill counterexamples: crossed quotes son raw válido pero no-signable; precios
revisados por el proveedor no sustituyen el histórico. QQQ 2024-03-11 conserva
65.500/65.500 keys de clock y solo 77 bid/ask distintos. El builder combina clock
sidecar con bid/ask Greek originales; `timestamp_key_set_exact` y
`stored_bid_ask_exact` quedan separados.
QQQ 2025-08-28 mostró 250 keys nativas extra pero cubrió las 50.750 históricas;
extras se auditan y no amplían el universo F1.

El primer full-gate attempt detectó un bug pre-outcome al aplicar `_truthy` a
escalares CSV aunque su contrato era vectorizado. El fix queda cubierto por un
test de attach real y el gate verifica además booleanos estrictos del seal,
consistencia del JAR, capturas positivas y hashes de raw/session manifests.

El segundo attempt detectó dos defectos pre-outcome. El bridge usaba todo el día
Greek contra un sidecar limitado al research window; se corrigió con grid
programado exacto y test de truncamiento inicial. Después de descontar sus 1.441
errores quedan QQQ/SPY 2022-12-30. QQQ mezcla `underlying_price` de t-1 con quote
de t (máximo 19,688 bps); SPY difiere 0,01 punto. No se autoriza tolerancia,
exclusión ni label runner hasta reconstruir y auditar un spot/wall consistente.

V1R2 predeclara esa reconstrucción sin outcomes. El censo reproducible confirmó
2.518 sesiones/120.864 wall rows, con solo QQQ/SPY 2022-12-30 híbridas y cero
unresolved (census SHA `24d86299...ff832`, commit `5c037ee`).
No se sustituye solo spot: se recapturan S/IV/delta first-order 1s coherentes para
los 671 contratos Greek∩OI positivo (285/386), 48 timestamps exactos cada uno.
Bid/ask debe permanecer idéntico al histórico; cualquier revision bloquea. Los
builders dejan la suite relevante en `76 passed`.

La captura ya selló 671/671 y 32.208 exact rows con cero errores y diferencia
máxima `0.0` en spot/bid/ask. Raw: 671 respuestas/4,013 GiB; index SHA
`7e5475f3...2100a`, provenance condicional. Falta construir/commitear las 96
wall rows y controles causales, luego repetir el full gate.

El builder de bundle ya está implementado: valida todo el sidecar, reconstruye
96 walls y el grid físico completo de 96 controles. El event view contiene solo
47 keys objetivo (27/20; SHA `41dae9ad...5201`), así que el patch/overlay se
restringe a esas 47 y no añade 49 decisiones inexistentes. Pendiente relanzar y
congelar los tres hashes.

Bundle real PASS: 96 walls SHA `69a3d330...487d`, 47 controls SHA
`937aa95e...051e`, manifest `47dffb25...aec5a`; spot parity `0.0`, non-target
changed `0`.
La integración aplica el bundle antes de seleccionar touches y exige los tres
SHA frozen; ninguna key nueva entra al event view.

Frecuencia estructural: 10.078 timestamps first-touch. QQQ máximo 14/9/9 en
202208–10 y SPY <18 en 16/41 meses incluso antes de cooldown/no-overlap; SPXW
min=30. H-FLOW debe ser señal prioritaria con fallback causal o ampliarse mediante
un protocolo nuevo, nunca presentarse solo como policy que cumple 18/mes.

Full V1R2 attempt: 2.519/2.519, cero source errors y todos los gates salvo uno.
QQQ 2022 `role_break_pressure_w1m` posee 6 estados no degenerados, pero el código
pedía 10. Antes de labels se congeló una aclaración objetiva: >=2 estados,
zero<99,5%, missing=0. No se cambian features/candidatos ni se usa PnL; el output
REJECTED se conserva y el relanzamiento usa target nuevo.

V1R2R1 ya superó el data gate completo desde `a13d589`: 2.519 sesiones,
10.683 filas, 173 columnas, cero errores, dataset SHA
`6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b` y
source inventory SHA `2a305a2910f83c42a3c32b455d9b3a93907c7d762c5168d0946f9ce1eae306e8`.
Los compactos están congelados en `_diagnostics`; el dataset grande queda en
`tmp`. Siguiente hito: commit del runner manifest y una sola evaluación física
F0/F1. Todavía no se ha observado outcome ni rentabilidad H-FLOW.

El one-shot ya se ejecutó desde el runner congelado y H-FLOW1 queda cerrado:
4/24 celdas favorables, mediana ΔAUC `-0,029209`, p unilateral `0,984375` y
cero wins primarios 30/60m en QQQ, SPXW y SPY. QQQ 0/8, SPXW 3/8, SPY 1/8.
`physical_mechanism_pass=false` y `advance_to_option_payoff=false`; no se permite
entrenar payoff ni retunar subgrupos. La próxima búsqueda debe introducir una
medición nueva ya separada del bloque: quote size/depth, IV/skew deformation o
una fuente futures/vol-complex causal.

La auditoría posterior seleccionó H-IVSURF1 sin outcomes: QSIZE está incompleto
(1.441/2.519), ES/NQ/VIX1D/VVIX ausentes y VIX no tiene paridad histórica/live.
H-IVSURF1 mide cambios fixed-strike de nivel/skew/curvatura a 1/5/15m y excluye
H-FLOW/static skew. Predeclaración `52c169c`, código `9719ec2`.

El build autoritativo pasó: 10.683x54, SHA
`9d9404fd721df927c30ce4d6edeee800f528df81cf14639c23da1dc4008bc2b3`,
minimum ticker-year valid 90,319%, minimum ticker 96,673%, 2.519 fuentes y todos
los gates causales/coverage/distinctness/control PASS. Falta frozen runner y el
one-shot físico LR/LGBM; todavía no hay rentabilidad nueva.

El one-shot H-IVSURF1 falló: LR 12/24, mediana ΔAUC -0,001203, p 0,890625;
LightGBM 9/24, mediana -0,005822. QQQ/SPXW fallan; SPY pasa solo LR pero no la
sensibilidad, por lo que no puede seleccionarse post-hoc. No se autorizó payoff
y no existe rentabilidad nueva. Próxima medición nueva: H-QSIZE1; completar
1.078 sesiones para llegar a 2.519/2.519 antes de labels.

El backfill QSIZE ya completó 1.078/1.078 sesiones y 81.824.260 rows. El data
gate V1 fue rechazado sin outcomes: coverage mínimo ticker-año 98,477% y control
PASS, pero seis celdas de cambios de `local_signable_fraction` son constantes
cero. No se entrenó ningún modelo ni se calculó PnL.

Esto descubrió un bug semántico pre-outcome: signable fraction es calidad, aunque
V1 aún la incluía entre las 40 mediciones. V1R1 la mueve a audit-only; quedan 32
features de qimb/depth/relative-qimb, con mínimo 158 valores distintos por
ticker-año. La reparación no cambia datos, clocks, contratos, labels, folds ni
gates y conserva p secuencial `<0,0167`. Próximo paso: rebuild V1R1, freeze y
one-shot físico. Rentabilidad nueva: aún no demostrada.

V1R1 ya pasó el data gate: 10.683x76, SHA dataset `f4ed7b23...6c49`, cobertura
mínima ticker-año 98,477%, distinctness/control/exact-key PASS y cero errores.
Falta únicamente commitear el sello, congelar runner y abrir el one-shot físico.

El one-shot ya cerró H-QSIZE1R1: LR 6/24, mediana ΔAUC -0,014823, p 0,890625;
LightGBM 5/24, mediana -0,020959. Ningún ticker pasa y no se autoriza payoff.
La próxima medición debe ser dinámica intraminuto, no otra reformulación de
snapshot size. Rentabilidad nueva: no demostrada.

Nueva fuente H-QDYN1 predeclarada sin outcomes: todos los NBBO ticks del contrato
CALL/PUT en el wall durante `[t-32s,t-2s)`, solo si el strike ya pertenecía a
la allowlist causal conocida en `t-5m` (9.833/10.683 candidatos).
Preflight 24/24 exact/causal; coste estimado 37,4M rows y 6,34GB. Próximo hito:
captura sellada y data gate, no payoff.

Auditoría económica 2026-07-12: se acepta prospectivamente PF>=1,30, WR>=45% y
12 trades/mes, sin relajar ask->bid/no-overlap/hold/scheduler. Los 697 trades
antiguos tenían fuga IB: 338 decisiones anteriores a 10:30 consumían el IB
completo 09:30–10:29. El paquete actual de 416 trades tampoco prueba edge por
selección sobre Jan-Jun, labels legacy y 55 overlaps. El benchmark exacto nested
ask->bid da PF QQQ/SPXW/SPY 0,984/0,832/0,919: aún no rentable. La buena curva
WF legacy queda solo como hipótesis, no como policy promotable.

H-QDYN V1 se detuvo antes de outcomes por una brecha de listing en `t-5m`.
V1R1 auditó exact CALL+PUT en 2.519 sidecars: 10.683/10.683 listados y 9.833
elegibles tras el radio congelado. Proof `083a77f3...927623c`, suite `30 passed`.
Los parciales V1/V1R1 son rechazados; relanzar a output V1R1R1 nuevo. Sin PnL.

H-QDYN V1R1R1 está capturando con suite `31 passed`. En paralelo se identificó
una fuente realmente nueva: ThetaData direct `/greeks/all` para migración de
vanna/charm/vomma/zomma; OI diario es previo y causal según docs oficiales.
Solo hay preflight 12 sesiones predeclarado, aún no ejecutado. IB/Fib estático no
muestra alpha incremental; presión dinámica en los ocho niveles queda futura.

Checkpoint captura H-QDYN V1R1R1: 5.257/9.833 (53,46%), PID 36564, cero errores;
outcomes y PnL siguen cerrados hasta data gate y freeze.

H-QDYN1R1R1 ya completó y selló la captura `PASS_QDYN_CAPTURE`: 9.833/9.833
eventos elegibles de 10.683 y 37.846.658 ticks (CALL 18.915.243; PUT
18.931.415), sin errores ni zero-right. Index SHA `9a4924df...1b4f03` y
eligibility SHA `09df8319...ee2e1`; provenance
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`. 2026/outcomes/producción siguen
cerrados. El primer data gate se detuvo pre-outcome por `set_index` eliminando
`event_id`; fix fail-closed `85de313`, `26 passed`, pushed. Relaunch inmutable
activo. Falta PASS_DATA_GATE -> compactos -> frozen runner -> único F0/F1; no
hay resultado físico, PF, WR o PnL nuevo.

El relaunch final H-QDYN1R1R1 cerró `REJECTED_DATA_GATE` pre-outcome: 10.683x67,
SHA dataset `2a7147cc...fb265a`, source `a65f4435...73398`. Coverage pasa
(mínimos anual/ticker 89,421%/90,727%), pero 18 celdas SPXW son degeneradas:
16 exchange-change fractions constante cero en 2022–2025 y dos state-change
fractions constante uno en 2025. La gate exigía >=2 estados por feature y
ticker-año. H-QDYN1 queda cerrado sin labels/modelo/payoff ni rescate; no existe
rentabilidad H-QDYN. El capture seal sigue válido y el bug `85de313` no causó el
fallo. Siguiente: preflight H-GREEK2WALL de 12 sesiones.

H-QDYN closure fue pushed en `30ba9d5`. H-GREEK2 preflight code está pushed
(`2f6f262`, `e0a8116`, `54c6fb4`, `7201cfd`), `12 passed`; inventory V1R2 PASS
en `7201cfd` (CSV `829ef754...`, JSON `88b84f2a...`, builder `f8937f68...`).
Congela 12 sesiones y direct all-Greeks+OI atómicos, sin 2026/outcomes/prod.
No hay captura: local STANDARD recibió 403 (requiere PROFESSIONAL); remoto MDDS
CONNECTED recibió 478 por sesión duplicada/stale. Shutdown remoto terminó solo
worker 1828, no launcher systemd PID 916, y sin sudo no hubo restart; después
TCP22/25503 quedó inaccesible desde la IP origen aunque ping funciona. Restaurar
servicio y capturar/sellar 12 o bloquear por entitlement/datos. Sin alpha/PnL;
gate PF1,3/WR45%/min12 permanece aceptada pero no evaluada.

H-GREEK2WALL cerró `BLOCKED_SOURCE_ENTITLEMENT`: remoto sano, Terminal único
PID954 y MDDS CONNECTED, pero la primera sesión congelada SPXW 2022-08-01
devolvió HTTP403 porque la suscripción remota también es STANDARD y
`/greeks/all` requiere PROFESSIONAL. Inventory V1R3 PASS sobre `20b9325`,
`13 passed`; status SHA `1f914c43...dcc5`, error SHA `13650acb...1bb9`.
No se creó output/staging/raw/parquet ni se abrió direct OI, labels, modelos,
payoff, 2026 o producción. No sustituir direct higher Greeks por fórmulas
locales. Siguiente fuente separada: H-IBQDYN1 sobre ocho niveles IB/Fib fijos,
con predeclaración/listing/captura propios y sin reutilizar H-QDYN.

Objetivo económico vigente: PF>=1,30, WR>=50%, >=18 trades por mes y ticker,
hold>=30m y PnL positivo en cada mes walk-forward; junio 2026 continúa cerrado.

H-IBQDYN1 está predeclarado/pushed `9464c08`, `6 passed`, Ruff clean. Nuevo
universo outcome-free de ocho niveles IB/Fib completos desde 10:35, primera
oportunidad por bloque 30m y buckets SPXW d25/QQQ-SPY d35: 16.926 eventos.
Listing exacto t-5m PASS 2.519/2.519, cero errores, 16.852 elegibles; SPXW/SPY
100%, QQQ 5.334/5.408 con 74 ineligibles explícitos. Los 12 eventos congelados
pasan. Proof SHA `b1fc6613...306d2`, eligible IDs `8e68c12c...652e`. Capacidad
OOS mínima QQQ35/SPXW69/SPY19 trades/mes bajo caps/hold30. Compactos versionados;
siguiente: captura sellada 12 eventos/24 contratos y gate de coste <=150M rows/
20GiB. No ticks nuevos, labels, PnL, 2026 ni producción todavía.

Preflight tick H-IBQDYN1 PASS: 24/24 contratos, 43.680 rows, cero errores y
zero-right; proyecta 61,34M rows/9,64GiB raw/1,16GiB parquet. Las 20 features
congeladas son finitas en 12/12 eventos; 0/60 celdas ticker-feature degeneradas,
distinctness min4, >=597 states y >=488 pairs. Full capturer resumible `62b3d98`
activo en D: PID44892, checkpoint inicial 100/33.704, cero errores. Secuencia
cerrada a data gate -> F0/F1 -> payoff solo si PASS. Jan-May 2026 final-fit solo
después de PASS, junio cerrado, julio shadow. Aún no hay rentabilidad nueva.

El último puente outcome-free ya está congelado: F0 tiene 18 controles y F1
añade exactamente las 20 mediciones tick; el data gate revalida todos los
artefactos y no permite reparaciones. Suite `19 passed`. Captura 2.200/33.704,
cero errores a las 11:28; todavía sin labels, PF, WR o PnL.

Runner físico/freezer preparados y bloqueados por PASS committed; arquitectura
LR L2 + LightGBM confirmatorio, 24 celdas y p<0,0125. Suite `26 passed`; captura
3.200/33.704, cero errores. Outcomes siguen cerrados.

Traducción económica única predeclarada: F1 LR 60m/0,5, mapping físico a side,
sin threshold ni payoff fit; replay ask->bid/no-overlap y gates estrictas. Sigue
dormida hasta physical PASS y no se ha leído rentabilidad.

Replayer/freezer económico ya listos y bloqueados por physical PASS; tests de
la cadena data+physical+economic `19 passed`. Captura 4.900/33.704, cero errores.

La primera pasada full H-IBQDYN1 ya terminó: 33.700/33.704 contratos tienen
raw/parquet/manifest y no existe staging. Cuatro requests exactos del
2023-10-25 10:35 (CALL+PUT de SPXW y SPY) devolvieron 472 tras tres intentos;
un retry posterior con MDDS CONNECTED repitió el cuerpo oficial `NO_DATA`.
Hashes: errors `e4dc5819...59af7`, cuatro ids `4a44551f...38a7`, body
`101a4aa8...3708c`. No es un error de permiso/conexión ni autoriza sustitución.

El contrato full ya admite filas cero. El amendment pre-outcome HTTP472 V1R1
congela materializar exclusivamente esas cuatro ventanas como raw text real,
parquet vacío y manifest auditable. Los dos eventos permanecen both-invalid y
en el denominador; coverage/distinctness/modelos no cambian. Falta implementar
y congelar el sealer V1R1, revalidar los 33.700, producir seal 33.704/33.704 y
solo entonces ejecutar el data gate. No hay AUC, PF, WR o PnL H-IBQDYN1.

El seal V1R1 ya es PASS desde `7a58259`: 33.704/33.704 contratos, 16.852
eventos, 58.212.529 ticks (28.761.918 CALL/29.450.611 PUT), cuatro NO_DATA
zero-row y cero errors/unresolved/staging. Index SHA `a3841779...46e14c`,
candidate SHA `684f68b1...431e5`; raw/parquet 9.841.523.910/1.177.902.621
bytes. La auditoría independiente volvió a contar todos los artefactos y hashes.
Compactos en `_diagnostics/h_ibqdyn1_ticks_202208_202512_v1r1_capture_seal/`.
Siguiente hito: commit/push y data gate outcome-free; aún no hay labels ni
rentabilidad H-IBQDYN1.

El primer build completo se detuvo antes de output tras procesar 2.506 sesiones
y 16.926 eventos: la elegibilidad causal existía en ambas ramas del merge y
quedó sufijada, por lo que faltaba el nombre canónico. No se abrieron outcomes ni
se produjo dataset parcial. Fix fail-closed pushed en `781806d`: compara
elegibilidad one-to-one, falla ante missing/mismatch y conserva una sola columna.
Suite focal `43 passed`, Ruff clean. Relanzar a
`tmp/h_ibqdyn1_features_202208_202512_v1r1`; solo un `PASS_DATA_GATE` autoriza
freeze físico. Rentabilidad nueva: todavía no demostrada.

El V1R1 con 16 workers completó RV y 12.000/16.926 eventos, pero se detuvo
pre-output con `MemoryError` al rehashear raw. No dejó target/staging ni abrió
outcomes. Relanzar solo como V1R2 con 8 workers; es una corrección de paralelismo
por RAM, sin cambio científico. Aún no hay resultado del gate ni rentabilidad.

V1R2 terminó `PASS_DATA_GATE` desde `619ac5a`: 16.926x72, dataset SHA
`675a7603...3d9a09`, source SHA `70ff4cf6...763c4`, 16.852 elegibles y 16.849
both-valid. Cobertura mínima ticker-año/ticker `96,312%/98,613%`, distinctness
mínima 79, controles y complete-case parity PASS. Compactos versionables en
`h_ibqdyn1_features_202208_202512_v1r2_data_gate/`; dataset en `tmp/`. Falta
commit del data seal -> freeze commit -> one-shot físico. Outcomes, PF/WR/PnL,
2026 y producción siguen cerrados/intactos.

Frozen runner físico ya generado sobre `3f19eb4`, manifest SHA
`f80f967a...7ac85a`: F0=26 (18 controles+8 identidades), F1=46 (F0+20 ticks),
LR L2 primaria/LightGBM sensibilidad, folds 2024/2025 y 30/60/120/180m. 2026,
producción y payoff permanecen cerrados. Commit/push del manifest y luego un
único physical F0/F1; aún no se abrieron labels ni rentabilidad.

H-IBQDYN1 queda `CLOSED_PHYSICAL_GATE` tras el one-shot `72dff1c`. LR: 7/24
wins, mediana ΔAUC `-0,004032`, p `0,921875`; por ticker QQQ/SPXW/SPY
3/8, 3/8, 1/8 y primarias 30/60m 1/4, 2/4, 0/4. LightGBM: 8/24, mediana
`-0,005847`, p `0,890625`. Ningún ticker ni modelo pasa. Frequency sí pasa con
mínimo 45 episodios resueltos por month-cell, así que falla alpha, no capacidad.
`advance_to_option_payoff=false`: no se ejecutó replay, no hay PF/WR/PnL y 2026/
producción siguen intactos. Compactos en
`h_ibqdyn1_physical_202208_202512_v1/`. No rescatar por horizonte, ticker, nivel
o SPXW LightGBM. Rentabilidad nueva: no demostrada.

EDGE-FIRST V1 ya completó su primer diagnóstico económico sin abrir 2024/2025.
El benchmark existente se reproduce exactamente: PF QQQ/SPXW/SPY
0,983707/0,831520/0,919499 y PnL negativo en los tres. El benchmark publicado
usaba cap SPY=2; con el cap contractual SPY=1 queda PF 0,971936 y mínimo mensual
14. En 2023 dev-only, el baseline causal también pierde; los oracles muestran
headroom grande tanto en selección de oportunidad como de lado, mientras
always-CALL/PUT/random pierden. No se cuantifica execution drag porque falta un
payoff midpoint/no-spread emparejado. Siguiente hito: freeze económico E0/E1 y
runner nested; 2026 y producción siguen intactos.

`EXISTING_DATA_EXECUTABLE_UTILITY_V1` está predeclarado y ejecutable en 2023.
E0=30 features (`b68b6c2e...6cbe38`); E1=527 (`e15469c0...8986abc`). La vista
temporal outcome-free preserva las 97.625 keys exactas, SHA `52bac061...aad36`.
H-FLOW/IVSURF/QSIZE se omiten por joins one-to-many no congelados; QDYN/GREEK2
por rejected gate/source missing. El smoke outer 2023-12 terminó: hurdle y Huber,
E0/E1, los tres tickers, todos `ABSTAIN_OUTER` al no pasar ningún grid los tres
meses inner. Dos PUT 2022 training-only ausentes no se rellenan. 2024/2025 y
2026 siguen cerrados; falta freeze E0/E1 committed y one-shot económico.

Freeze `PREEXECUTION_FROZEN` listo sobre `c1dee47`: manifest SHA
`579fe8ce...a0c0b`, protocol SHA `22a87b18...3f498f`, E0/E1 completos y dos
modelos económicos exactos. El smoke final 2023-12 fue determinista. Tras
commit/push, solo queda el one-shot nested 2024-2025; no se permite retocar
features, modelo, grid, ranking o scheduler. 2026/producción siguen intactos.

EDGE-FIRST V1 queda cerrado `NO_EDGE_IN_EXISTING_DATA`. E1 hurdle y Huber
abstuvieron los 144 cells: cero grids inner completos y cero trades. E0 hurdle
solo operó 3/72 cells (68 trades pooled, PF 1,464809, +8,342R), pero únicamente
QQQ 202409 pasó outer; mínimo mensual 0 y positive-month rate 4,17%. E0 Huber
operó un cell y perdió PF 0,589/-3,156R. Auditoría PASS: 288 folds, 12.096
grids, 87 trades, cronología/scheduler/payoffs/métricas exactos. Stress y 2026
no autorizados; producción intacta. No abrir otra familia de datos como rescate.

KING-GEX-SLOPE1 cerró `FAILED_ECONOMIC` en desarrollo 2023. K1 pendiente
alineada: 1.324 trades, WR 42,22%, PF 0,804, -89,845R y solo 2/36 meses/ticker
pasan; K0: 1.443, 43,10%, 0,810, -94,144R. Los 72 checkpoints y métricas fueron
auditados. Frecuencia/concentración pasan, pero el lado elegido bate al contrario
solo 49,02%; invertir también pierde PF 0,904. El oracle de lado PF 7,320 indica
headroom de movimiento, no una policy. 2024-2026 y producción siguen intactos.
No rescatar King por ticker/side/threshold; siguiente hipótesis debe resolver o
eliminar la decisión CALL/PUT bajo ejecución ask-to-bid.

La primera diagnosis de gestión KING-GEX localiza el PF bajo: K1 tiene payoff
ratio 1,0965 (+66,11% win medio / -60,29% loss medio), 749 negative triggers
aportan -455,108R y 96,51% del gross loss viene de exits <=-55%. Invertir todo
y rehacer scheduler mejora a PF 0,850 pero sigue -67,677R y solo 1/36 celdas
pasa. `KING-GEX-EXIT1` congela 16 variantes globales de stop/trail/horizonte,
min hold 30m y max 180m, con replay raw ask->bid y checkpoints. Aún no existe
resultado alternativo; 2024-2026 siguen cerrados.

El runner KING-GEX-EXIT1 ya implementa checkpoints manifest-last para 36 source
cells y 32 policies. Hashea raw, exige paridad exacta B00 por evento/right y
rehace scheduler para cada exit; tests focales `13 passed`. Todavía no se ha
ejecutado un path alternativo y debe commit/push antes de hacerlo.

V1 se detuvo tras un único source checkpoint SPXW-202301 y antes de PF/WR/PnL
por policy: el loop pandas era demasiado lento. V1R1 permite solo vectorizar el
mismo algoritmo con equivalencia testada y exige target nuevo; no cambia el grid.

V1R1 vectorizada ya pasa equivalencia escalar/array `1e-12`, 14 tests y Ruff/
compile. Falta commit/push y relanzar el desarrollo completo.

KING-GEX-EXIT1 completó V1R1 y queda `FAILED_ECONOMIC`: 36 source checkpoints,
425.152 outcome rows, 32 policies y 1.152 ticker-meses auditados. Cero elegibles.
El mejor PF es D1/S30 0,925 (WR35,96%, -30,131R); B00 invertido queda PF0,850,
WR43,02%, -67,677R. Trail temprano sube WR48,13% pero PF cae a 0,799. Ninguna
variante alcanza PF1,0; 2024-2026 y producción no se abrieron.

El oracle no causal entre B00/S30 sobre entradas comunes llega PF1,239: existe
tradeoff de continuación, no una policy rentable. Siguiente hipótesis permitida:
decidir en +30m `cerrar/continuar` con evolución causal del precio, contrato y
griegas sintéticas. Estas pueden derivarse con `neural/stats.py`, pero entry-E1
ya probó 527 features con higher Greeks/walls/IB-Fib/precio y sus 144 celdas GBT
abstuvieron. No repetir la misma representación ni presentar OI unsigned como
inventario dealer. El Excel King sigue no auditado por runtime spreadsheet
ausente.

KING-GEX-MANAGE30-V1 queda predeclarado tras medir el techo exacto: oracle D1
B00/S30 PF1,190/WR43,60% y 13/36, por lo que se descarta ese binario; oracle
16-exits PF2,357/WR54,67%/+324,783R y 32/36 autoriza una gestión causal más
amplia. Se congela decisión +30m entre 16 exits+E30, M0 path y M1 higher Greeks
sintéticas, LGBM Huber fijo por ticker y train expandido 2022->cada mes 2023.
49.400 eventos/2.721 sesiones tienen fuentes raw presentes. Gate: PF>1,30,
WR>45%, trades>12 y PnL>0 en las 36 celdas. Outer 2024-2026 cerrado.

No repetir el legacy path-exit: en otro universo dio 1.690 trades, PF0,811,
WR33,85% y -89.652. Siguiente: commit del freeze, builder/test con checkpoints
de sesión y data gate train/dev; después runner mensual 2023.

Builder MANAGE30 implementado pre-label y resumible por sesión: universo
hardcoded 2022-2023/22.273 eventos, hashes raw, paridad B00, estado exacto
30..31 y M0/M1+17 outcomes. `16 passed`, Ruff/compile clean. Falta commit/push
antes del primer build real.

Primer build MANAGE30 paró pre-path: faltaba filtrar master a 11:20–14:30 antes
del join. Aclaración V1R1 preserva 22.273 K1 y logra 33.902/33.902 exact joins.
V1 rechazado con solo RUN_CHECKPOINT; fix `7 passed`. Commit/push -> target V1R1.

MANAGE30 ya tiene runner mensual reanudable pushed en `b8fa50c8`. Son 72 folds
2023, por ticker y M0/M1, LightGBM Huber fijo, target de ventaja por acción y
scheduler rehecho tras seleccionar hold. Cada fold sella modelo/medianas/
predicciones/trades/métricas. Suite combinada `22 passed`, Ruff/compile clean.

Build train/dev V1R1 activo: 843 checkpoints de sesión a las 16:47 del
2026-07-15, cero errores reportados. No duplicar. Debe producir 22.273 rows y
`PASS_DATA_GATE`; después auditar coverage y ejecutar una única evaluación
2023. Rentabilidad causal nueva: aún no existe. Los valores PF2,357/WR54,67%
son oracle futuro y no una policy. 2024-2026 y producción permanecen cerrados.

Se añadió `SUMMARY.md` de continuidad con evidencia, fallos, commits, comandos,
gates y próximos pasos. Mantenerlo junto a los cuatro handoffs. El workbook King
sigue no auditado: la skill exige `load_workspace_dependencies` y
`@oai/artifact-tool`, no expuestos; prohíbe instalar/buscar/sustituir. Una futura
auditoría read-only será separada y nunca podrá retunar MANAGE30.

MANAGE30 V1R1 falló correctamente antes de dataset/modelos: 1.265/1.267
sesiones. Agrupar quotes :00/:30 por minuto introducía hasta 30s futuros en QQQ
2022-06-17 y superficie M1. Exact timestamp corrige 6/6 eventos. Una sola señal
train-only SPXW 2022-02-22 11:20 PUT carece de contrato ejecutable y se rechaza
sin sustitución: 22.273 source -> 22.272 executable; desarrollo 2023 intacto.

Aclaración `9a8e0b41`, código `a996f260`, suite `24 passed`. Build V1R2 activo
en target nuevo; V1R1 completo rechazado/no reusable. Aún no hay data gate ni PF.

Actualización 2026-07-16: V1R2 pasó data gate (22.272 executable, SHA
`2c7ff048...000b`) pero MANAGE30 falló el one-shot 2023: M0 PF0,905/WR38,90%/
-34,942R y M1 PF0,901/WR39,08%/-36,299R; cero brazos elegibles y outer cerrado.

Se aplicó el límite anti-datasets del usuario. Un único oracle weekly multi-día
sellado en `cf536c53` validó exact contract ask->bid dos sesiones, delta0,50 y
no-overlap sobre 2022–2025. Cobertura 2.361/2.364; PF oracle 12,277–13,960 y
PnL mensual siempre positivo, pero 16/144 celdas no superan WR50% y la capacidad
es 8–10 trades/mes. Always-CALL solo PF1,042–1,056; always-PUT pierde. Gate
cerrada: no dataset/modelo semanal ni sweep. No existe policy promovible nueva.

## Checkpoint 16-jul-2026 — fuente Globex y cierres posteriores

Se incorporó una sola fuente externa outcome-free: continuos Yahoo 60m
`ES/NQ/YM/RTY/ZN/GC/CL`, 2024-07-17..2026-07-15, seal `eaa56342`, manifest SHA
`dad8dc52...dcb7`. `VX=F` no existe en esa API y el histórico 60m anterior al
límite de 730 días fue rechazado por Yahoo. Los siete futuros y 15 tickers cash
se exigen exactos; faltantes se quitan conjuntamente, sin imputación.

El primer modelo Globex pasó desarrollo 2025 con 412 trades/ticker, min22,
9/12 meses positivos y PF QQQ/SPX/SPY 1,200/1,206/1,210. Al abrir una vez
enero–15 julio 2026 cayó a PF 0,873/0,899/0,888, WR 46,61/47,81/47,81%,
2/3/3 meses positivos y PnL -804/-455/-503 bps. La frecuencia pasa; falla la
estabilidad direccional.

V2 online linear cerró 2025 en PF 0,980/0,976/0,996; V3 expert Hedge llegó a
1,140/1,137/1,098 pero solo 5/6/5 meses positivos; V4 meta-Hedge quedó
1,161/0,933/0,965 y 4/5/5. Ninguno abrió 2026. No seleccionar memorias,
ventanas, inversas o expertos después de ver estos resultados.

El short-premium V2 de exits fijos quedó `REJECTED_DATA_GATE`: tras 100/1.506
sesiones había 4.271 candidatos y 13 salidas de cuatro patas no ejecutables,
principalmente QQQ 2024-02-06. No se excluye el día ni se reporta economía.

El payoff long-vol dual-leg 0DTE también falla 2025: 613 trades/ticker, PF
0,629/0,661/0,605, WR 35,07/33,28/36,22% y solo 2/2/1 meses positivos.
Finalmente, IB breakout/fade directo conserva min24–25 trades/mes pero queda PF
0,779/0,785/0,819 y WR ~31–32%. Ambos cerraron antes de 2026.

Diagnóstico final: VISReg/factorización corrigió el rango latente (z 53,54%, dz
42,67%) sin corregir PF. No era solo colapso JEPA ni solo theta 0DTE. La fuente,
el objetivo y la relación causal son inestables. Estado actual:
`NO_PROFITABLE_CAUSAL_POLICY`, producción intacta y ninguna familia activa.

## Checkpoint 17-jul-2026 — relative-value predeclarado

Tras reconciliar los siete handoffs, `main`/`origin/main` estaban en `d02b1ad9`
y el worktree tracked limpio. Los untracked históricos se preservan. El registro
de familias se corrigió: King, Globex, compact 0DTE y payoffs alternativos siguen
cerrados; no existe rentabilidad nueva.

`CROSS_SESSION_RELATIVE_VALUE_V1` queda predeclarado pre-outcome como mecanismo
independiente y ledger-only. Usa 1.003 sesiones underlying existentes por ticker
en 2022–2025. La policy única revierte el shock QQQ frente al promedio SPY/SPXW
medido desde el cierre previo hasta el close 10:34; opera QQQ-SPY equal-notional
open 10:36 -> open 13:36, coste 1 bp por pata. No crea dataset, no usa ML,
threshold, z-score, beta ni options outcomes.

Solo se autoriza desarrollo 2022–2023. Debe cumplir PF>1,20, WR>45%, >12 trades
y PnL positivo en cada mes. 2024–2026 y producción permanecen cerrados hasta un
PASS completo y un freeze posterior; cualquier mes fallido cierra V1 sin rescate.

El runner ledger-only y cinco regresiones sintéticas ya están implementados sin
abrir datos reales de salida. Verifican señal 10:34, fill 10:36/13:36, coste por
pata, close 13:00 de la sesión previa half-day, exclusiones y gates estrictas con
meses cero. El código debe commit/push antes del one-shot de desarrollo.

Antes del run se congeló una aclaración de procedencia: el día SPY 2023-06-05
queda fuera del ledger, las tres barras 09:54–09:56 siguen inválidas/sin imputar,
pero su close 16:00 válido conserva el prior session exacto para 06-06. Solo esa
terna puede exceptuar el envelope; una cuarta anomalía falla cerrado.

El desarrollo único ya cerró `FAILED_ECONOMIC_DEVELOPMENT`: 496 trades,
WR41,532%, PF0,627276, -2.349,329 bps, min19 y 5/24 meses positivos; solo
202210 y 202306 pasan las cuatro gates. La recomputación independiente coincide
y no existe fila posterior a 2023. Momentum opuesto PF1,075 fue control
predeclarado/no elegible y tampoco cruza PF1,20. No outer, options, 2026 o
producción. Registry vuelve a cero familias activas.

Nueva rotación pre-outcome: `OPENING_RELATIVE_MOMENTUM_V1`. No invierte la
misma señal cerrada: elimina completamente prior close/overnight y usa solo el
impulso QQQ frente a SPY/SPXW entre 09:30 y el close 10:34. Opera momentum
QQQ-SPY 10:36→13:36, 180m/2bps, sin fit o filtros. Desarrollo 2022–2023;
2024–2026 cerrado. PF agregado>1 se registra como avance incremental, pero solo
24/24 meses completos autorizan outer.

Runner/tests ya implementados pre-outcome. El runner no acepta end-date, hashea
predeclaración, dependency de carga y 1.503 fuentes development, y materializa
solo ledger/meses/controles. Los tests separan explícitamente
`INCREMENTAL_EDGE_ONLY` de `PASS_DEVELOPMENT_GATE`; falta validar, commit/push y
solo después ejecutar datos reales.

El primer comando real no abrió datos: falló al importar `neural` desde el path
directo y no creó target. El fix añade repo root antes del import y testea la CLI
en subprocess; es una reparación de arranque pre-outcome, sin cambio científico.

El relaunch committed completó 2022–2023 y cerró `NO_AGGREGATE_EDGE`: 497
trades, WR50,905%, PF0,831462, -927,689 bps, mínimo19, 7/24 meses positivos y
4/24 PASS. Los controles mean-reversion y lado fijo dan PF0,813/0,924. Auditoría
independiente confirmó hold180, coste2bps, cero overlap/futuro y hashes exactos.
No se abrió 2024–2026. Registry queda sin familias activas y producción intacta.

Nueva familia activa solo outcome-free: `OPTION_PARITY_PRESSURE_V1`. Congela el
cambio 10:30→10:35 de `(K+Cmid-Pmid-spot)/joint_half_spread` sobre pares
CALL/PUT 0DTE exactos y strikes comunes <=100bps. No usa IV/walls/ML ni outcomes.
Primero debe pasar cobertura, >12 eventos/mes, distinctness, timestamp nativo y
paridad bid/ask vintage; 2024–2026 siguen cerrados.

Scope enmendado por orden explícita, todavía pre-outcome: se ignora 2022 porque
2022-02 tiene exactamente 12 expiraciones 0DTE y no puede cumplir `>12` con una
operación/día. Data gate pasa a 2023–2025; desarrollo es 2023, outer 2024–2025
y 2026 solo se abre tras PASS y freeze de las dos fases anteriores.

El capacity audit committed `314d16e1` pasó: 2.256 exact-0DTE, 752 por ticker y
mínimo18 sesiones/mes en 2023–2025. `outcome_accessed=false` y
`quote_content_accessed=false`. Próximo gate: pares CALL/PUT/timestamp/spot y
distinctness; no hay PF/WR/PnL nuevo.

Primer full gate V1 detenido outcome-free con 104 errores de filtro: 103 QQQ y
uno SPXW serializan timestamps con `.000`. Las filas exactas existen; no es un
data gap. Aclaración congelada permite solo con/sin `.000`, conserva sidecar
one-to-one y exige relaunch inmutable V1R1. No se abrió economía/2026.


### Checkpoint 2026-09-17 — multiscale V1R1 predeclared, outcomes closed

User-authorized V1R1 supersedes queued V1 before execution; V1 has no economic
result and its contract remains immutable. Binding authority:
`research_papers/JEPA/multiscale_v1r1/01_PREDECLARATION.md`.
One-contract net USD, L2 trees, USD0/5 thresholds, zero+mask, adverse WR
recomputed, SSL clock projection and provenance-gated initial SPXW repair.
Initial HEAD `29724f857185a046a09680b8edf9708d89949619` (not unavailable8355c816).
Execution PENDING; evidence NOT_EVALUATED; no raw/features/payoffs/fit/predictions.
Sequence: publish docs → implement/test/preflight/publish → outcome-free gate
and independent audit/publish → monthly freeze/publish BEFORE test payoff.
Five handoffs and multiscale_v1r1/STATUS.md govern current state. No production
consumer changed; promotion_approved=false; shadow NOT_STARTED.


### Checkpoint 2026-09-17 — V1R1 admission implementation and synthetic preflight

V1R1 docs published cc5f8b30/3dfe3643 on research/multiscale-v1r1-net-usd.
Main push rejected non-fast-forward; remote8355c816 recovered, not merged.
38 synthetic tests/Ruff/compile PASS; 600x92048 A160 synthetic fit PASS,
819.734s, peak1.561GiB; maximum process estimate22.276GiB below24GiB.
Admission primitives and independent negative-source auditor implemented;
complete feature/economic pipeline is NOT implemented or certified (see
research_papers/JEPA/multiscale_v1r1/09_IMPLEMENTATION_COVERAGE.md).
Possible blocker: historical underlying repair/availability provenance.
Next after publication: metadata-only inventory and dependency audit, no labels.
Economic state NOT_EVALUATED; technical_ready=false; shadow NOT_STARTED;
promotion_approved=false. No historical fit/features/payoffs or production changes.


### Checkpoint 2026-09-17 — V1R1 source blocker; auditor-only retry clarification

Producer5dd5a519 sealed30,899 files/41,614,238,640 bytes; source admission
BLOCKED_DATA:973 full sessions have unresolved underlying lineage,9 half days,
32 sessions also miss named sources. No raw value columns/features/payoffs read.
The first auditor stopped before source rehash:29 SPXW September files appeared
outside the fixed experiment period; no sealed path disappeared. Failed attempt
and exact name difference are preserved. TIME-002 already excludes those dates.
Auditor-only fix records post-period additions and still rehashes all original
inputs; historical additions/deletions/mutations fail.42 synthetic tests/Ruff/
compile PASS. Publish this fix before independent retry; no economic access.
The source BLOCKED_DATA conclusion is pending audit; technical_ready=false,
shadow NOT_STARTED,promotion_approved=false. Full economic engine incomplete.
