# AI Agent Hand-off: Current Production Reality

Este repo ya no debe entenderse principalmente como el viejo pipeline GBT+RL. El sistema live actual es un stack de alertas/paper-trading para opciones 0DTE usando el paquete JEPA event-option static-union.

## Objetivo actual

Mantener y mejorar un sistema live rentable, causal y auditable para SPXW, QQQ y SPY 0DTE. El criterio de exito no es solo maximizar PnL en un backtest aislado; una promocion necesita:

- walk-forward o holdout causal sin leakage;
- equivalencia entre training/backtest/live;
- artefactos `production_live_ready`;
- servicios systemd arrancando con el mismo contrato que el backtest;
- evidencia diaria de drift/fills/paper-intents.

## Stack live

Servicios:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

Paquete activo:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

Policy:

```text
event_option_frozen2025_static_union_balanced_202607
```

Contrato runtime confirmado en VPS:

```text
event_exit=stop=-60%/tp=1000%/trail=50%/25%/min_hold=30m/max_hold=180m
entry_window=10:00-14:30 ET
risk=5000
paper_order_intents=true
```

El bot no envia ordenes al broker. Escribe intents y avisa por Discord/tracker.

## Politicas por ticker

| Ticker | Simbolo opciones | Bucket | Max trades/dia | Cooldown |
| --- | --- | --- | ---: | --- |
| SPX | SPXW | d25 | 4 | 0m |
| QQQ | QQQ | d35 | 2 | 30m |
| SPY | SPY | d35 | 1 | 0m |

SPXW usa `min_score=0.34`. Los otros gates viven en `event_option_policy.json`.

## Validacion actual

Comando canonico:

```bash
python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12
```

Metricas Jan-Jun 2026:

| Scope | Trades | WR | PF | Min month |
| --- | ---: | ---: | ---: | ---: |
| Overall | 697 | 57.819% | 1.915 | 103 |
| QQQ | 236 | 60.593% | 1.771 | 36 |
| SPXW | 355 | 55.211% | 2.037 | 51 |
| SPY | 106 | 60.377% | 1.769 | 12 |

El target ideal de 18 trades/mes/ticker no se cumple en SPY; la gate deployable actual es 12.

## Datos

Local:

```text
D:/ThetaData/data_options/SPXW
D:/ThetaData/data_options/QQQ
D:/ThetaData/data_options/SPY
D:/ThetaData/data_underlying_derived/SPXW
D:/ThetaData/data_underlying_derived/QQQ
D:/ThetaData/data_underlying_derived/SPY
```

VPS:

```text
rt_data/YYYYMMDD/
trades_jepa/
log_exports/
```

Los scripts de training/backtest deben leer datos historicos de ThetaData o parquets reproducibles. El live solo puede consumir snapshots y features observables hasta el timestamp actual.

## Reglas duras

- No usar datos futuros, labels, PnL futuro, high/low posterior, o columnas de outcome como features live.
- No seleccionar una politica usando el mismo mes que luego se reporta como OOS.
- No cambiar systemd sin validar arranque de ambos servicios.
- No hacer `git reset --hard` ni revertir cambios del usuario.
- No tratar `neural/run_pipeline.ps1` + PPO/RL como produccion actual sin una promocion nueva.
- No reentrenar diario por defecto; auditar diario y reentrenar/promocionar por mes completado.

## Deploy en VPS

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git pull --ff-only
python3 -m py_compile services/realtime_feed.py bots/tradingbot_wrapper_jepa.py neural/jepa/validate_event_option_production_package.py
python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12
sudo install -m 0644 systemd/realtime_feed.service /etc/systemd/system/realtime_feed.service
sudo install -m 0644 systemd/ai_bot.service /etc/systemd/system/ai_bot.service
sudo systemctl daemon-reload
sudo systemctl restart realtime_feed.service
sudo systemctl restart ai_bot.service
sudo systemctl status realtime_feed.service ai_bot.service --no-pager -l
```

No usar `reboot now` como despliegue normal.

## Areas legacy

`neural/rl/`, `backtest/backtest_rl.py`, `neural/train_walkforward.py`, `neural/hybrid_model.py`, `jepa_production_final_180m`, level-stability y structural profiles son utiles para investigacion y comparativas. No son el contrato live actual.

## Research activo — WALL_SURFACE_FLOW_AT_TOUCH_V1R1

Checkpoint 2026-07-12: implementación causal/pre-outcome completada; suite
relevante `55 passed`; producción y 2026 intactos. No existe todavía resultado
físico ni económico.

Bloqueo autoritativo: 1.441/2.519 sesiones 2022-08..2025-12 carecen de option
`timestamp` nativo. No aceptar `underlying_timestamp` por inferencia ni permitir
`PASS_DATA_GATE` con fallbacks. Usar únicamente el backfill sellado de
`neural/jepa/build_wall_native_quote_sidecar.py`, que exige Terminal local/JAR,
raw response hashes y timestamp/contract key-set exacto contra Greeks. Si el
proveedor revisa bid/ask, auditar mismatch sin reemplazar el histórico; F1 usa
bid/ask Greek originales. Crossed quotes se preservan pero son no-signable.
El sidecar debe cubrir 100% de keys Greek históricas; `native_extra_key_rows`
se archiva pero jamás amplía retrospectivamente el universo de F1.

Contratos nuevos obligatorios:

- decisiones normales hasta 14:30; medias jornadas hasta 12:55;
- labels no cruzan cierre RTH 16:00/13:00;
- QQQ/SPY option close 16:15/13:15 es un reloj distinto;
- grid flow 10:20–14:29 normal, 10:20–12:54 half-day;
- runtime exacto según `requirements-wall-surface-flow-v1r1.txt`;
- sizes del sidecar pertenecen a H-QSIZE1 separado y no pueden entrar en F1.
- underlying derivado debe pasar metadata/date, grid RTH, OHLC envelope,
  tick_count y spot parity <=0,001 bps; su productor histórico no está embebido.

Audit underlying completo: 2.519/2.519 pasan desde el primer timestamp consumible
10:19. Tres rows SPY 2023-06-05 09:54–09:56 son inválidos pero out-of-scope; se
cuentan, no se bfill ni se usa el hallazgo para excluir la sesión.

Backfill nativo completado y sellado en commit base `041b16c`: 1.441/1.441
sesiones, 125.557.990 filas, cero keys Greek históricas faltantes y cero errores.
Se auditan 500 keys extra sin incorporarlas, 5.720 crossed no-signable y 2.915
filas bid/ask revisadas en 24 sesiones; F1 conserva los precios Greek originales.

Secuencia vigente: commit/push del seal/index → full data gate → commit de sus
compactos → frozen runner manifest commit → una única evaluación física F0/F1.
El sidecar ya está integrado en el builder (`beb4435`). No abrir outcomes antes
del freeze ni crear `PLAN.md` sin una dirección rentable clara.

Primer full-gate attempt falló antes de outcomes por un bug escalar/Series al
leer `stored_timestamp_key_coverage_exact` desde CSV. Se corrigió fail-closed y
se añadió validación de booleanos JSON estrictos, hashes de los 1.441 raw responses
y manifests de sesión, consistencia de JAR y capturas no vacías. Relanzar solo
desde el commit que contiene este fix.

Segundo full-gate attempt también se detuvo antes de outcomes. El bridge comparaba
Greeks full-session con el sidecar research-only; ahora exige el grid explícito
10:20–14:29/12:54 y conserva 125.557.490 keys Greek compartidas más 500 extras
auditadas. Quedan dos fallos de spot reales: QQQ y SPY 2022-12-30. QQQ es un
snapshot vendor híbrido (`underlying_price(t)=open(t-1)` mientras bid/ask son de
`t`); SPY difiere 0,01 punto. No ampliar tolerancia ni excluir los días. Auditar
una reconstrucción causal de spot/exposiciones antes de otro full gate.

V1R2 queda predeclarada en
`WALL_SURFACE_FLOW_V1R2_EXACT_SPOT_REPAIR_PREDECLARATION.md`. El censo general
`audit_wall_spot_semantics_v1.py` pasó 2.518 sesiones/120.864 rows:
2.516 `exact_t`, dos `hybrid_spot_tm1` (QQQ/SPY 2022-12-30), cero unresolved.
Manifest commit `5c037ee`, census SHA `24d86299...ff832`, inventory underlying
SHA `7e7022d5...cf3d2`; compactos quedan versionados en `_diagnostics`.
El builder `build_wall_exact_greek_repair_sidecar.py` congela 671 contratos con
OI positivo (285/386; SHA `57c998...46c0`) y exige 48 snapshots first-order 1s
exactos por contrato, spot=open(t), bid/ask iguales al vintage almacenado y raw
HTTP/JAR/runtime/source hashes. Suite relevante ampliada: `68 passed`.

Captura exact-Greek completada y sellada sobre commit `4de62f5`: 671/671,
32.208 rows (QQQ 13.680, SPY 18.528), cero errores, spot/bid/ask max difference
`0.0`, 671 raw responses/4,013 GiB. Index SHA `7e5475f3...2100a`, seal SHA
`3c267f83...a8fc5`; provenance `CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`.

Builder de bundle implementado en
`build_wall_exact_greek_repair_artifacts.py`: revalida los 671 raw/snapshots,
reconstruye 96 wall rows y un grid físico completo de 96 controles desde
`open(t)/open(t-lag)`. El event view solo contiene 47 keys congeladas (QQQ27,
SPY20; SHA `41dae9ad...5201`), por lo que el output event-control/overlay debe ser
47 y jamás añadir las 49 ausentes. Bundle integrado en el surface builder antes
de `make_touch_candidates`, con hashes frozen y provenance persistida. Suite
relevante: `76 passed`.

Secuencia actual: commit/push de la integración V1R2 → full data gate. No parchear solo spot: IV/delta 1m también son
incoherentes con el spot de t.

Bundle real PASS sobre commit `65289e8`: wall repair 96 rows SHA `69a3d330...487d`,
event repair 47 rows SHA `937aa95e...051e`, manifest SHA `47dffb25...aec5a`;
paridad exact-Greek/control y wall/control `0.0`, non-target rows changed `0`.

Límite económico pre-outcome: first-touch H-FLOW tiene 10.078 timestamps únicos.
Incluso con oracle/caps y sin cooldown, QQQ no puede llegar a 18 trades en
202208–10 (14/9/9) y SPY falla 16/41 meses; SPXW min=30. H-FLOW no puede ser la
policy completa. Si pasa física, debe ser componente prioritario de una unión
fija con fallback causal OOS o evaluarse en un universo más amplio predeclarado.

Primer full V1R2: 2.519/2.519 sesiones, cero errores; coverage, grids, clocks,
spot y controls pasan. Único fallo: `distinctness_pass` porque QQQ 2022
`role_break_pressure_w1m` tiene 6 estados, rango [-1,1], zero 6,09%, missing 0,
y el código exigía 10 aunque la predeclaración solo decía nondegenerate. Antes de
labels se congeló `WALL_SURFACE_FLOW_V1R2_DATA_GATE_CLARIFICATION.md`: >=2
estados, zero<99,5%, missing=0. Relanzar a target nuevo; no reutilizar el manifest
REJECTED ni modificar el dataset in-place.

Checkpoint posterior: el relanzamiento inmutable V1R2R1 completó
`PASS_DATA_GATE` sobre commit `a13d589`, 2.519/2.519 sesiones y cero errores.
Dataset 2022-08..2025-12: 10.683 filas, 173 columnas, SHA
`6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b`;
source inventory 8.998 ficheros, SHA
`2a305a2910f83c42a3c32b455d9b3a93907c7d762c5168d0946f9ce1eae306e8`.
Todos los gates de causalidad, cobertura, timestamps, completed bars, spot,
controls y no-degeneración pasan. Producción y 2026 siguen intactos. Los
compactos se versionan en
`wall_surface_flow_at_touch_202208_202512_v1r2r1_data_gate/`; el parquet grande
permanece en `tmp/`. Siguiente paso único: congelar runner manifest con la
provenance exact-Greek y ejecutar F0/F1 una sola vez. Aún no hay resultado físico
ni rentabilidad nueva.

## Cierre científico H-FLOW1

Runner congelado en `d49ed79`; evaluación one-shot sobre 2024/2025 completada
sin tocar 2026 ni producción. H-FLOW1 queda **CERRADO**: 24/24 celdas válidas,
solo 4/24 mejoras, mediana ΔAUC `-0,029209`, Wilcoxon unilateral por
ticker-fold `p=0,984375`, 14 pérdidas conjuntas AP/log-loss y cero victorias en
las 12 celdas primarias 30/60m. Por ticker: QQQ 0/8, SPXW 3/8, SPY 1/8;
medianas ΔAUC `-0,045545/-0,018642/-0,022390`. `physical_mechanism_pass=false`,
`advance_to_option_payoff=false`. No entrenar option payoff ni rescatar por
horizonte/ticker/subgrupo. Esto falsifica el bloque predeclarado de
volume/count/close-notional firmado, full-surface y local, 1/5/15m cerca del
wall; no falsifica quote size/depth, IV/skew deformation ni futuros porque no
entraron en F1. Compactos versionados en
`wall_surface_flow_at_touch_physical_202208_202512_v1r2r1/`.

## Research activo — H-IVSURF1

Tras cerrar H-FLOW1 se auditó sin outcomes una cartera de fuentes nuevas.
H-QSIZE1 queda `DEFERRED_DATA_INCOMPLETE`: sizes en 0/2.519 Greeks y solo
1.441 sesiones del sidecar; 38-40% bid_size=0, paridad live bloqueada. ES/NQ,
VIX1D y VVIX carecen de histórico local; VIX es un proxy con contrato histórico
distinto del live. TLT tiene 859/859 sesiones pero sería expansión cross-asset
genérica y no se prioriza frente a una medición directa del mecanismo.

H-IVSURF1 fue predeclarado en commit `52c169c`: deformación midpoint-IV local a
un wall sobre contratos/strikes idénticos en `t,t-1,t-5,t-15`; 18 cambios de
nivel/skew/curvatura y cinco campos de calidad, sin features H-FLOW. LR es el
modelo físico primario; LightGBM solo sensibilidad no rescatable; p secuencial
`<0,025`. Código commit `9719ec2`, suite focal `39 passed`.

Build autoritativo V1R1: `PASS_DATA_GATE`, 10.683 filas/54 columnas, dataset SHA
`9d9404fd721df927c30ce4d6edeee800f528df81cf14639c23da1dc4008bc2b3`,
2.519 fuentes Greek revalidadas, minimum ticker-year both-valid `90,319%`,
minimum ticker overall `96,673%`, distinctness/control coverage PASS. 2026,
outcomes y producción intactos. Compactos en
`wall_iv_surface_deformation_at_touch_202208_202512_v1r1_data_gate/`.
Siguiente paso: commit compactos -> frozen runner commit -> una sola evaluación
física LR/LGBM. Aún no existe rentabilidad nueva H-IVSURF1.

### Cierre H-IVSURF1

Runner congelado `035e402`; one-shot 2024/2025 completado sobre 96 modelos.
H-IVSURF1 queda **CERRADO** sin payoff: LR 12/24 wins, mediana ΔAUC
`-0,001203`, p unilateral `0,890625`, 14 pérdidas conjuntas AP/log-loss.
LightGBM sensibilidad 9/24, mediana `-0,005822`, p `0,921875`. QQQ LR 3/8,
SPXW 4/8, SPY 5/8; solo SPY pasa la gate LR por ticker, pero LGBM SPY 3/8 y
0/4 primarias no confirma. No seleccionar SPY, lags, horizontes ni subgrupos
post-hoc. `physical_mechanism_pass=false`, `advance_to_option_payoff=false`.

Siguiente fuente: H-QSIZE1, ya separada antes de estos outcomes. Requiere una
captura sellada de las 1.078 sesiones no presentes en el sidecar para completar
2.519/2.519. Es top-of-book NBBO size snapshot, no update intensity ni depth de
libro. Debe predeclararse con corrección secuencial antes de labels y su live
parity sigue bloqueada hasta implementar/medir recepción de sizes.

### H-QSIZE1 / reparación H-QSIZE1R1

Captura complementaria sellada: 1.078/1.078 sesiones, 81.824.260 filas,
índice SHA `a9c3a8c0...eef9`, cero errores. Al combinarla con el sidecar previo
se cubren 2.519/2.519 sesiones. Provenance sigue
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`: se excluyen por clave Greek
exacta 63.500 filas añadidas retrospectivamente y se auditan 1.485.169 filas
bid/ask revisadas. Live parity permanece `BLOCKED`.

H-QSIZE1 V1 queda **CERRADO antes de outcomes**: data gate 10.683x76, cobertura
PASS (mínimo ticker-año 98,477%), controles PASS, pero distinctness FAIL en seis
celdas de `local_signable_fraction_change_{1,5}m`, todas exactamente cero. No
se abrió label, AUC ni PnL. Compactos preservados en
`wall_quote_size_pressure_at_touch_202208_202512_v1_rejected_data_gate/`.

El fallo reveló un bug semántico concreto: el amendment prohibía calidad como
alpha pero aún dejaba signable fraction dentro del modelo. H-QSIZE1R1 queda
predeclarado antes de outcomes para mover sus 8 campos a audit-only y conservar
solo 32 mediciones reales qimb/bid-depth/ask-depth/relative-qimb. Las 32 pasan
distinctness outcome-free (mínimo 158 estados por ticker-año). No cambia ningún
row, reloj, contrato, radio, label, fold, modelo o gate; p sigue `<0,0167`.
Código causal commits `950d724` y `d1d48e3`; suite focal `14 passed`.

Secuencia única: commit/push de la reparación y compactos V1 -> rebuild inmutable
V1R1 -> commit compactos -> frozen runner commit -> one-shot físico. 2026,
producción y outcomes siguen intactos. No existe PF/WR/PnL nuevo todavía.

H-QSIZE1R1 ya superó `PASS_DATA_GATE` desde commit `0298578`: 10.683 filas,
76 columnas, dataset SHA
`f4ed7b2360dd2ff3676a23ac2da297c73554ccfd0f5486314b85cc88d0ef6c49`,
source inventory SHA
`9128ac471ef2061a7b27db19d3886d23b4d3ae492727af69d8a44c05c61ee8a3`.
Coverage, distinctness de las 32 pressure features, controles, exact keys y
2.519-session provenance pasan. Compactos en
`wall_quote_size_pressure_at_touch_202208_202512_v1r1_data_gate/`; parquet en
`tmp/`. Siguiente paso único: commit compactos, generar frozen runner desde el
nuevo HEAD y ejecutar el one-shot físico. Aún no hay outcomes/rentabilidad.

### Cierre H-QSIZE1R1

Frozen runner commit `81f1ba8`; one-shot completo sobre 96 modelos. H-QSIZE1R1
queda **CERRADO sin payoff**: LR 6/24 wins, mediana ΔAUC `-0,014823`, p
`0,890625`, 16 pérdidas conjuntas AP/log-loss. LightGBM 5/24, mediana
`-0,020959`, p `0,843750`. Por ticker LR: QQQ 1/8 (`-0,014823`), SPXW 4/8
(`-0,001402`), SPY 1/8 (`-0,016555`); primarias 30/60m 1/4, 2/4 y 0/4.
`frequency_pass=true`, pero `physical_mechanism_pass=false` y
`advance_to_option_payoff=false`. No entrenar payoff, seleccionar SPXW ni
rescatar lags/subgrupos. Snapshot NBBO size/imbalance/depth 1m cerca del wall no
añade información física estable.

Siguiente hipótesis nueva permitida: H-QDYN1, reposición/retirada e intensidad
intraminuto de quotes sobre contratos local-wall, si una auditoría outcome-free
confirma captura 1s/tick reproducible. No confundirla con H-QSIZE snapshot ni
descargar un wildcard 1s masivo sin una captura dirigida y predeclarada.

### Research activo — H-QDYN1

Preflight outcome-free de 24 contratos (primera decisión por ticker-año) confirma
tick NBBO causal: 100% exact-wall y timestamps predecisión, mediana
aprox. 1.750 rows/right/30s. Estimación completa: 37,4M rows y 6,34 GB raw.
H-QDYN1 queda predeclarado como fuente nueva. La allowlist conocida en `t-5m`
cubre 9.833/10.683 eventos; se captura exact wall `right=both` en `[t-32,t-2)`,
sin sustitución. Mide update intensity
y replenishment/withdrawal; same-millisecond collisions cuentan intensidad pero
no ordered deltas. Gate secuencial p `<0,0125`; live parity bloqueada.

Builder `build_wall_quote_tick_dynamics_sidecar.py` es inmutable/resumable,
raw+parquet+manifest hashed y exige Terminal/JAR local. Siguiente paso: commit y
push de predeclaración/builder/tests, captura completa outcome-free, data gate,
freeze y one-shot físico. No se ha abierto outcome H-QDYN1.

### Auditoría de rentabilidad y gate relajada — 2026-07-12

El usuario acepta como gate económica prospectiva `PF >= 1,30`, `WR >= 45%` y
`>=12 trades/mes`, siempre con walk-forward cronológico puro, ask de entrada,
bid de salida, hold 30–180m, no-overlap y scheduler live exacto. Esta relajación
no valida retrospectivamente resultados seleccionados con los meses reportados.

Los 697 trades/PF 1,915 del commit histórico `47fccbf` quedan invalidados como
evidencia causal: 338/697 decisiones eran 10:00–10:25 pero consumían el IB
completo 09:30–10:29 y sus Fibonacci. Filtrar post-hoc a >=10:30 deja 359 trades
y rompe SPY (PF 1,267) y SPXW mayo. No rescatar este resultado.

El paquete actual fue sustituido en `66731f6` y reporta 416 trades/PF 1,749,
pero el validador endurecido lo rechaza: selección 202601–202606 solapa los meses
reportados, labels `legacy_ohlc` en vez de `executable_quote`, 55 overlaps y falta
`position_overlap_policy=reject_while_open`. Su contrato empaquetado además es
QQQ 2/45m, SPXW 1/30m y SPY 4/30m con guards, distinto de la tabla declarada
4/0m, 2/30m, 1/0m; verificar el VPS antes de afirmar paridad.

Benchmark limpio más cercano:
`event_option_execquote_causal1030_nested_exploratory_202601_202605_v1` usa
0DTE, ask->bid, hold 30–180m, cero overlaps y folds cronológicos. Falla:
QQQ 94 trades/WR 44,68%/PF 0,984/min15; SPXW 107/42,99%/0,832/min10;
SPY 123/43,90%/0,919/min19. Con cap SPY=1, PF 0,972/min14. El artefacto está
untracked y el dataset en `tmp`, por lo que es benchmark diagnóstico, no seal.

El walk-forward legacy `intersection_guarded_v1_walkforward` muestra una curva
atractiva bajo gates relajadas, pero no es prueba: el overlay/policy se eligió
después de inspeccionar Jan–Jun 2026 y sus labels no certifican ask->bid. No hay
hoy una policy rentable que pase simultáneamente causalidad, selección y
ejecución. El único replayer económico válido debe partir del parquet
`executable_quote`, usar `walkforward_event_option_profile_selector.py` y el
scheduler común sin `--allow-overlapping-positions`.

### Checkpoint causal H-QDYN1R1

H-QDYN1 V1 fue detenido outcome-free al descubrir que proximidad a un wall en
`t-5m` no demostraba listing del contrato exacto. V1R1 exige presencia exacta
CALL+PUT 0DTE en los sidecars nativos sellados a `t-5m`, sin as-of ni nearest
strike. Audit completo 2.519/2.519: los 10.683 sí tenían ambos rights; 9.833
pasan también radio 150 bps. Proof SHA
`083a77f3a24225e9ad38b6c401b4382c17b8621f69b0af4563f1eadcf927623c`,
manifest SHA `2188a2cf6003c340a692220c24beeacc1be621aa171b88b2639d5a0593c021a5`,
eligible IDs SHA `f77dc2231f410679ad97737cc8a4af057e917224e31d2c5df3b6f1f8366a2eca`.
La captura parcial V1 en `D:/ThetaData/wall_quote_tick_dynamics_at_touch_202208_202512_v1`
es `REJECTED_CAUSAL_ALLOWLIST` y no puede reanudarse. Capturar solo a output
V1R1R1 nuevo con esos hashes; suite H-QDYN focal `30 passed`. El parcial V1R1
también queda `REJECTED_CAPTURE_SEMANTICS`: preservaba incorrectamente raw
non-finite y llamaba size-only a transiciones con cambio de exchange. V1R1R1
preserva raw, filtra solo al medir, exige strike exacto y excluye conditions de
alpha. Auditoría posterior corrigió también exchanges infinitos en transiciones;
suite focal `31 passed`, sin blockers materiales conocidos.

Nueva fuente independiente outcome-free registrada: H-GREEK2WALL-DIRECT-ALL-V1.
ThetaData v3 ofrece `/option/history/greeks/all` con gamma, vanna, charm, vomma,
zomma y otros campos nativos a 1m. La documentación oficial confirma que OI se
publica ~06:30 ET y representa el cierre del día previo, por lo que es causal
después de 10:20. Se permite solo un preflight de 12 sesiones congeladas tras
terminar H-QDYN; no outcomes ni full download. La hipótesis autorizable es
deformación/migración del perfil vanna/charm/vomma/zomma, no niveles estáticos,
totales o confluencia Fib. Protocolo en
`H_GREEK2WALL_DIRECT_ALL_V1_FEASIBILITY_PREDECLARATION.md`.

IB/Fibonacci: la construcción causal requiere las 60 barras 09:30–10:29 y no
puede decidir antes de 10:30. Proximidad/confluencia estática y elección de
extensiones según el día ya están representadas/cerradas; S2 no añadió valor
físico estable. Solo sería nueva una medición dinámica H-IBQDYN1 sobre el set
fijo completo de ocho niveles, con captura dirigida propia; no reutilizar ni
re-etiquetar el sidecar Greek-wall H-QDYN.

Checkpoint operativo 2026-07-13 00:24 Europe/Madrid: captura H-QDYN V1R1R1
activa en `D:/ThetaData/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1`,
PID Python `36564`, 5.257/9.833 eventos (53,46%) y cero errores reportados. No
arrancar otro capturador ni usar los directorios V1/V1R1 rechazados. Tras seal:
data gate -> commit compactos -> freeze runner -> único one-shot físico.

### Checkpoint sellado H-QDYN1R1R1 — 2026-07-13

La captura V1R1R1 terminó `PASS_QDYN_CAPTURE`: 9.833/9.833 eventos elegibles
de 10.683 candidatos, 37.846.658 ticks (CALL 18.915.243; PUT 18.931.415), cero
errores y cero eventos sin algún right. Index SHA
`9a4924df1f60203d3f6ee1217520d4a0b0d287a82b816b898be3d2579e1b4f03`;
eligibility SHA
`09df83191ba83f0fe8db86e2a8bcc59b278c03668c1fd4506480123a585ee2e1`.
Provenance: `CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`; 2026, outcomes y
producción siguen intactos.

El primer data-gate se detuvo antes de outcomes porque `set_index` eliminaba
`event_id` y el revalidador intentaba leerlo como columna. El fix fail-closed y
su regression test están en `85de313`, suite focal `26 passed`, ya pushed. El
relaunch a target inmutable está ejecutándose. No existe aún resultado físico
ni económico. Secuencia única: esperar `PASS_DATA_GATE` -> commit de compactos
-> commit del frozen runner -> un solo one-shot físico F0/F1. No abrir payoff
salvo physical PASS.

### Cierre H-QDYN1R1R1 — `CLOSED_DATA_GATE`

El relaunch inmutable terminó `REJECTED_DATA_GATE` sin abrir outcomes. Dataset
`tmp/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1`: 10.683x67, SHA
`2a7147ccaa60bb41419a3c1b100e1857a701249c970dc276a602f10147fb265a`;
source inventory SHA
`a65f4435820f504529f5684055c50db8428b095f837238e0f8ffe86291673398`.
Coverage pasa (mínimo anual both-valid `0,8942084942084942`, ticker
`0,9072749691738594`), pero distinctness falla en 18 celdas: SPXW 2022–2025
tiene constantes cero las cuatro fracciones CALL/PUT de cambio de exchange
(16), y SPXW 2025 tiene constantes uno las dos
`unambiguous_state_change_fraction` CALL/PUT (2).

La predeclaración exige >=2 estados finitos/distintos por feature y ticker-año;
por tanto H-QDYN1 queda cerrado sin freeze, labels, modelo, payoff ni rescate por
quitar features. El bug `set_index` corregido en `85de313` no causó este fallo y
el capture seal sigue válido. Cierre detallado en
`WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1R1_DATA_GATE_CLOSURE.md`. Siguiente paso:
preflight predeclarado de 12 sesiones H-GREEK2WALL.

### Checkpoint H-GREEK2WALL preflight — 2026-07-13

El cierre H-QDYN quedó commit/push `30ba9d5`. H-GREEK2 preflight está
versionado/pushed en `2f6f262`, `e0a8116`, `54c6fb4` y `7201cfd`; suite focal
`12 passed`. Congela 12 sesiones y exige captura atómica de direct all-Greeks +
direct OI, source clarification y provenance remota. El source inventory V1R2
es PASS sobre `7201cfd`: CSV SHA `829ef754...`, JSON SHA `88b84f2a...`, builder
SHA `f8937f68...`; no 2026, outcomes ni producción.

No existe captura aún. Terminal local devolvió HTTP 403: entitlement STANDARD,
endpoint all-Greeks requiere PROFESSIONAL, y no produjo output. En remoto
`91.99.90.39`, MDDS conectó pero all-Greeks devolvió 478 invalid session por
sesión duplicada/stale; tampoco produjo output. El Terminal local quedó parado.
En remoto se observó un único launcher systemd `thetadata_feed` PID 916 con
worker 1828; realtime/ai seguían activos. No había sudo para restart. El shutdown
oficial respondió OK pero solo terminó el worker; el launcher siguió vivo y
systemd no reinició. Poco después la IP de origen perdió TCP 22/25503 aunque el
host seguía respondiendo ping, posiblemente filtrado temporal.

Siguiente acción: restaurar Terminal/servicio remoto y después capturar y sellar
exactamente las 12 sesiones. Si entitlement o datos siguen ausentes, bloquear
H-GREEK2. No afirmar captura, alpha, PF, WR o PnL. La gate deployable aceptada
PF>=1,30, WR>=45% y mínimo 12 trades/mes permanece intacta y no se ha evaluado
con esta fuente.

### Cierre H-GREEK2WALL — `BLOCKED_SOURCE_ENTITLEMENT`

El Terminal remoto se recuperó con PID único `954`, MDDS `CONNECTED`, y
`thetadata_feed`, `realtime_feed` y `ai_bot` activos. Source inventory V1R3
PASS sobre `20b9325`: CSV SHA `829ef754...dce53`, JSON SHA
`88b84f2a...220f`, builder SHA `bf8fda05...bad0`; suite `13 passed` y Ruff
clean. La primera captura congelada, SPXW 2022-08-01, llegó al host remoto exacto
mediante transporte SSH y devolvió HTTP 403: tanto local como remoto tienen
suscripción STANDARD y `/greeks/all` exige PROFESSIONAL. Error SHA
`13650acb...1bb9`; status CONNECTED SHA `1f914c43...dcc5`.

El fallo ocurrió antes de direct OI y no creó output, staging, raw ni parquet.
H-GREEK2 queda cerrado por fuente ausente, sin datos, labels, modelos, payoff,
2026 o cambios de producción. No sustituir por higher Greeks derivados y
llamarlos directos. Una futura licencia Professional sería un cambio externo y
solo permitiría continuar prospectivamente el protocolo ya congelado.

Siguiente fuente independiente permitida: H-IBQDYN1, presión NBBO intraminuto
dirigida sobre el conjunto fijo completo de ocho niveles IB/Fibonacci calculados
solo después de completar 09:30–10:29. Requiere predeclaración, proof de listing
y captura propios; no reutilizar ni relabelar ticks Greek-wall H-QDYN.

Objetivo económico vigente del usuario, más estricto que la antigua gate
deployable: por ticker PF>=1,30, WR>=50%, >=18 trades en cada mes, hold>=30m y
PnL positivo en todos los meses walk-forward; junio 2026 permanece cerrado.

### Checkpoint H-IBQDYN1 listing feasibility

H-IBQDYN1 fue predeclarado y pushed en `9464c08` antes de leer un tick nuevo;
suite focal `6 passed`, Ruff clean. Usa el universo nuevo de los ocho niveles
IB/Fibonacci actuales completos desde 10:35, primera oportunidad por bloque fijo
de 30m y contratos ejecutables SPXW d25 / QQQ-SPY d35. Son 16.926 eventos
outcome-free (5.408/5.858/5.660 QQQ/SPXW/SPY); no reutiliza H-QDYN.

El proof exacto t-5m terminó `PASS_H_IBQDYN1_LISTING_FEASIBILITY`: 2.519/2.519
sesiones, cero errores, 16.852 elegibles. SPXW 5.858/5.858 y SPY 5.660/5.660;
QQQ 5.334/5.408, con 74 fallos explícitos sin as-of/nearest (21 both, 31 CALL,
22 PUT). Los 12 eventos congelados de preflight pasan ambos rights. Proof SHA
`b1fc6613...306d2`, eligible IDs SHA `8e68c12c...652e`, inventory SHA
`35a569bd...01c2`. Capacidad 2024/2025 bajo hold30/no-overlap/caps actuales:
mínimos mensuales QQQ35, SPXW69, SPY19; pasa frecuencia matemática, no alpha.

Compactos en
`h_ibqdyn1_listing_feasibility_202208_202512_v1/`. Siguiente acción única:
implementar y congelar captura inmutable de solo los 12 eventos/24 contratos,
capturar quotes tick `[t-32s,t-2s)` con provenance remota, sellar coste/campos y
autorizar full capture solo si <=150M rows, <=20GiB raw y ambos rights no vacíos.
No labels, payoff, 2026 ni producción; aún no existe rentabilidad H-IBQDYN1.

### H-IBQDYN1 tick preflight PASS y full capture activo

Capturador preflight commit `c823d86`; semántica de 20 features congelada en
`68ed6b3`; full capturer resumible commit `62b3d98`. El preflight remoto terminó
24/24 contratos, 43.680 rows (CALL 21.297/PUT 22.383), cero errores y cero
rights vacíos. Proyección full: 61.341.280 rows, 9,6427 GiB raw y 1,1551 GiB
parquet, PASS frente a 150M/20GiB. Index SHA `d0275e2d...06c5f`, cost SHA
`20c34643...2731`.

Audit outcome-free de features: 12/12 CALL y PUT válidos, 20/20 alpha fields
finitos, cero de 60 celdas ticker-feature degeneradas; distinctness mínima 4,
mínimos 597 estados y 488 pares. Esto valida medición/coste, no alpha.

Full capture única activa en
`D:/ThetaData/h_ibqdyn1_ticks_202208_202512_v1`, PID `44892`; checkpoint inicial
100/33.704 contratos, cero errores. No lanzar duplicado. Tras seal: data gate ->
frozen physical F0/F1 -> solo si PASS, un payoff ask-to-bid walk-forward. No
abrir otra familia/sweep. Enero-mayo 2026 solo final-fit tras PASS histórico;
junio cerrado y julio shadow. Aún no existe PF/WR/PnL H-IBQDYN1.

Contrato final de data gate ya congelado antes de labels: F0 son exactamente 18
controles distancia/aproximación/RV/hora y F1 añade solo las 20 variables tick.
Builder `build_h_ibqdyn1_dataset.py` revalida los 33.704 raw/parquet/manifests,
preserva los 74 eventos ineligibles y falla cerrado por cobertura, distinctness
o complete-case. Suite focal `19 passed`. Checkpoint de captura 11:28: 2.200/
33.704, cero errores; PID 44892 sigue activo. Aún no se abrió outcome.

Runner físico y freezer ya están implementados pre-outcome en
`evaluate_h_ibqdyn1_physical.py`/`freeze_h_ibqdyn1_physical_runner.py`; no pueden
ejecutarse sin manifest/compactos `PASS_DATA_GATE` committed. Arquitectura única
LR L2 primaria + LightGBM confirmatorio, 24 celdas 2024/2025 y p<0,0125. Suite
H-IBQDYN focal `26 passed`; captura checkpoint 3.200/33.704, cero errores.

La traducción económica única quedó predeclarada antes de outcomes en
`H_IBQDYN1_ECONOMIC_TRANSLATION_PREDECLARATION.md`: LR F1 físico 60m, umbral
0,5, mapeo rechazo/break a CALL/PUT, sin fit de payoff ni threshold; scheduler
cronológico exacto, ask->bid, hold 30..180m, caps/cooldown actuales y gates
estrictas PF1,30/WR50%/18/mes/PnL mensual positivo. No admite rescate post-hoc.

Replayer/freezer económico implementados en
`evaluate_h_ibqdyn1_economic.py`/`freeze_h_ibqdyn1_economic_runner.py`. Verifican
physical PASS y hashes antes del primer acceso a `opt_exit_ret`, cargan solo los
seis LR F1 60m OOS, y aplican scheduler cronológico sin ranking futuro. Tests
focales economic+physical+data `19 passed`. Captura 4.900/33.704, errors=0.

### H-IBQDYN1 full capture: cierre de primera pasada y NO_DATA V1R1

La primera pasada outcome-free terminó los 33.704 intentos: existen 33.700
raw/parquet/manifests válidos, cero staging y cuatro fallos HTTP 472. Son ambos
rights de SPXW y SPY del 2023-10-25 10:35, nivel `ib_low`: SPXW CALL4230/
PUT4185 y SPY CALL421/PUT418. QQQ quedó 10.668/10.668. El error JSON SHA es
`e4dc5819...59af7`; los cuatro contract ids SHA `4a44551f...38a7`.

MDDS seguía CONNECTED y el retry exacto devolvió otra vez 472 con cuerpo
`No data found for your request` (SHA `101a4aa8...3708c`). ThetaData define
472 como `NO_DATA`. El full contract ya admite rows=0 y el data gate usa
coverage explícita; el bug es que la capa HTTP no materializaba la ventana
vacía. El amendment pre-outcome
`H_IBQDYN1_HTTP472_NO_DATA_AMENDMENT.md` congela una reparación V1R1 solo para
esos cuatro: raw text exacto + parquet vacío tipado + manifest versionado,
sin filas sintéticas, ampliar ventana ni sustituir contratos. Los dos eventos
quedan both-invalid y cuentan contra coverage.

Secuencia: commit/push del amendment y handoffs -> implementar/testar sealer
V1R1 -> revalidar los 33.700 existentes y materializar solo los cuatro 472 ->
exigir index 33.704, cuatro zero-row exactos, cero unresolved/staging y seal ->
commit/push -> data gate. Aún no se abrieron labels, AUC, PF, WR, PnL, 2026 ni
producción.

### H-IBQDYN1 full capture V1R1 sellada

El sealer versionado en `7a58259` revalidó raw/parquet/manifest de los 33.700
contratos originales y materializó los cuatro 472 exactos como raw text real y
parquet vacío, tras tres nuevos retries por contrato. Resultado
`PASS_H_IBQDYN1_FULL_CAPTURE`: 33.704 contratos/16.852 eventos, 58.212.529 ticks
(CALL 28.761.918; PUT 29.450.611), cuatro zero-row `HTTP_472_NO_DATA`, cero
unresolved/errors/staging. Index SHA
`a3841779c8603a96d4863a4e1495feec4a6c98d4fee490a204881b05d146e14c`;
candidate SHA `684f68b1...431e5`. Raw 9.841.523.910 bytes, parquet
1.177.902.621 bytes. Provenance sigue
`CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION`, live parity `BLOCKED`.

Una auditoría independiente contó 33.704 ids/parquets/manifests, 33.700
`response.json` + cuatro `response.txt`, verificó body/hash 472, filas cero y
ausencia de staging/`errors_latest`. Compactos en
`h_ibqdyn1_ticks_202208_202512_v1r1_capture_seal/`. Siguiente paso único:
commit/push de compactos/handoffs -> ejecutar `build_h_ibqdyn1_dataset.py` al
target inmutable -> abortar si cualquier gate outcome-free falla. Todavía no se
abrieron labels, AUC, PF, WR, PnL, 2026 ni producción.

El primer build outcome-free procesó las 2.506 sesiones de RV y los 16.926
eventos, pero se detuvo antes de crear output porque control y measurement
aportaban ambos `causal_subscription_eligible` y pandas la sufijaba. No fue un
fallo de datos ni se abrieron labels. El fix fail-closed `781806d` exige paridad
exacta de elegibilidad antes de eliminar la copia redundante; suite focal
`43 passed`, Ruff clean. Relanzar solo a target inmutable nuevo
`tmp/h_ibqdyn1_features_202208_202512_v1r1`; no reutilizar V1 ni congelar runner
hasta `PASS_DATA_GATE`. Sigue sin existir PF/WR/PnL H-IBQDYN1.

El relaunch V1R1 con 16 workers llegó a 2.506/2.506 sesiones RV y
12.000/16.926 eventos, pero un worker lanzó `MemoryError` al rehashear raw. El
proceso terminó sin target ni staging; no es data-gate rejection ni abrió
outcomes. Relanzar a target nuevo V1R2 con `--workers 8`. Es solo una reducción
de paralelismo por pico RAM; universo, bytes, hashes, features y gates quedan
idénticos. No volver a ejecutar V1/V1R1 ni usar 16 workers en este build.

V1R2 con 8 workers terminó `PASS_DATA_GATE` desde commit base `619ac5a`:
16.926 filas x 72 columnas, dataset SHA
`675a760335b5d03085b3a66daec34598e95842fcd11899dde66a7c6e163d9a09`,
source inventory SHA
`70ff4cf6d8703dd22fbc20a4881d84bb0f0f5c43906c0cd968eaa789b04763c4`.
Se preservan 16.852 elegibles y 16.849 both-valid; mínimos de cobertura
ticker-año/ticker `0,963117/0,986132`, distinctness mínima 79, controles y
complete-case parity PASS. Compactos en
`h_ibqdyn1_features_202208_202512_v1r2_data_gate/`; parquet grande queda en
`tmp/`. Siguiente paso único: commit/push compactos y handoffs -> congelar
runner físico desde HEAD limpio -> abrir labels F0/F1 una sola vez. Aún no hay
AUC, PF, WR o PnL; 2026 y producción siguen intactos.

Runner físico H-IBQDYN1 congelado `PREEXECUTION_FROZEN` sobre commit
`3f19eb4`: manifest SHA
`f80f967a17a7b30fa7c6f728d620d343d1dd076c36dba8790a0e0f9c407ac85a`.
F0=18 controles continuos + 8 identidades de nivel (26 columnas); F1=F0 + 20
variables tick (46). LR L2 primaria, LightGBM solo sensibilidad; folds 2024/2025
y horizontes 30/60/120/180 exactos. `holdout_2026_opened=false`, producción
intacta y payoff no autorizado al freeze. Tras commit/push del manifest,
ejecutar exactamente un physical one-shot; no modificar código/protocolo.

### Cierre H-IBQDYN1 — `CLOSED_PHYSICAL_GATE`

El one-shot congelado corrió desde `72dff1c` sobre 96 modelos y cerró la familia.
LR primaria: 7/24 wins frente a 16 requeridos, mediana ΔAUC `-0,004032`
frente a `+0,01` y Wilcoxon unilateral `p=0,921875` frente a `<0,0125`.
QQQ/SPXW/SPY: 3/8, 3/8 y 1/8 wins; medianas ΔAUC
`-0,001953/-0,002884/-0,008276`; primarias 30/60m 1/4, 2/4 y 0/4. Ningún
ticker pasa. LightGBM tampoco confirma: 8/24, mediana `-0,005847`, p `0,890625`.

La frecuencia física sí pasa (mínimo mensual resuelto 45), pero
`physical_mechanism_pass=false`, `research_payoff_authorized=false` y
`advance_to_option_payoff=false`. Por tanto no ejecutar economic replayer, no
reportar PF/WR/PnL y no abrir Jan-May/junio 2026. No rescatar seleccionando QQQ
120m, SPXW LightGBM 30/60m, ticker, nivel Fibonacci, horizonte o subgrupo.
Compactos en `h_ibqdyn1_physical_202208_202512_v1/`; parquets/predictions/modelos
grandes quedan en `tmp/`. H-IBQDYN1 queda cerrado: la dinámica NBBO de 30s en
los contratos ejecutables alrededor de la geometría IB/Fib completa no añade
separación física estable a F0. No hay modelo rentable nuevo.

### EDGE-FIRST EXISTING-DATA SPRINT V1 — benchmark/oracle

El sprint económico reutiliza exclusivamente el parquet executable-quote
2022-01..2025-12 existente; no abrió outcomes 2024/2025 ni leyó labels nuevos de
2026 en este checkpoint. El benchmark publicado fue reproducido exactamente:
QQQ 94 trades/WR 44,68%/PF 0,983707/PnL -0,492R; SPXW 107/42,99%/
0,831520/-5,816R; SPY 123/43,90%/0,919499/-2,979R. El artefacto publicado usaba
cap SPY=2; al imponer el contrato vigente SPY=1 quedan 93 trades, PF 0,971936,
PnL -0,773R y mínimo mensual 14.

La descomposición oracle se ejecutó solo en abril-diciembre 2023 con el control
Pairwise C0 congelado. El baseline causal pierde en los tres tickers (PF
SPXW/QQQ/SPY 0,828/0,794/0,862); conservar oportunidades causales y usar lado
oracle eleva PF a 5,838/9,811/8,315. Los controles always-CALL, always-PUT y
random seed fijo también pierden. Headroom pooled diagnosticado: +573,553R por
error de lado y +1.159,030R por error de oportunidad. Execution drag no es
identificable sin una label midpoint/no-spread emparejada y no se inventa.
Siguiente secuencia: predeclarar `EXISTING_DATA_EXECUTABLE_UTILITY_V1`, congelar
E0/E1 y validar el runner en 2022-2023 antes del único nested 2024-2025.

`EXISTING_DATA_EXECUTABLE_UTILITY_V1` ya está predeclarado y el runner pasó un
smoke nested completo en outer 2023-12 para E0/E1, hurdle LightGBM y Huber
directo. Ningún arm/modelo tuvo una pareja threshold/margin que pasara los tres
meses inner, por lo que los 12 ticker-arm-model folds fueron `ABSTAIN_OUTER`; es
diagnóstico de desarrollo, no resultado 2024/2025. La vista temporal outcome-free
preserva 97.625/97.625 keys y pesa 235.156.345 bytes, SHA
`52bac061216dd8aac7423449c442577882484aad0c4220bddaabc14544faad36`.

Join audit congelable: base/pairwise current-time/legacy live/wall-state son
exactos; H-IBQDYN entra solo en sus 16.926 keys exactas con un flag causal de
aplicabilidad. H-FLOW1/H-IVSURF1/H-QSIZE1R1 son `UNSAFE_JOIN` por multiplicidad
sin `wall_identity`; H-QDYN1 se omite por gate rechazada y H-GREEK2 por source
missing. Se detectaron dos PUT outcomes ausentes de SPXW 2022-02-22 solo en
train: se preservan y jamás se rellenan; cada head usa sus targets finitos y
inner/outer exige ambos lados. E0=30 SHA `b68b6c2e...6cbe38`; E1=527 SHA
`e15469c0...8986abc`. Siguiente paso único: commit del runner/predeclaración,
freeze manifest E0/E1 desde HEAD limpio y luego one-shot 2024-2025.

Freeze económico `PREEXECUTION_FROZEN` generado sobre `c1dee47`: manifest SHA
`579fe8ce6759b8f235c5a4f63c7710acfa6280a09444c922878035f83c8a0c0b`,
runner protocol SHA
`22a87b18801289eef1b48107f2f72ab9d6f2b9d985f2b34bcbfdbedfcb3f498f`.
Congela los 30/527 nombres ordenados, dos formulaciones, grid train-only, ranking
inner, scheduler, ejecución, 24 outer months y hashes de todo el código activo.
El smoke 2023-12 se repitió byte-for-metric con el protocolo final. Tras
commit/push de este manifest, la única acción autorizada es el one-shot nested
2024-01..2025-12; no modificar runner, features o thresholds.

### Cierre EXISTING_DATA_EXECUTABLE_UTILITY_V1 — `NO_EDGE_IN_EXISTING_DATA`

El one-shot frozen 2024-01..2025-12 completó 288 folds y 12.096 grids inner.
E1, único candidato, tuvo cero grids que pasaran los tres meses inner tanto en
hurdle como Huber: 144/144 cells `ABSTAIN_OUTER`, cero trades. E0 produjo solo
cuatro cells trade de 144: hurdle SPXW 202403 17 trades/PF 1,404/WR 58,82%/
+1,761R (falla frecuencia), QQQ 202409 33/1,516/57,58%/+4,080R (único PASS),
SPY 202502 18/1,440/44,44%/+2,501R (falla WR); Huber SPY 202502
19/0,589/31,58%/-3,156R. Los otros 284 cells abstienen.

Pooled E0 hurdle: 68 trades, PF 1,464809, WR 54,41%, +8,342R, pero mínimo
mensual 0, positive-month rate 4,17% y 69/72 cells abstain; no es candidato.
E0 Huber pierde. Auditoría independiente `PASS_RESULT_AUDIT`: hashes, 288
folds/month cells, selección frozen, cronología, payoffs ask-to-bid, caps,
cooldown/no-overlap y métricas recomputadas. SUMMARY SHA
`52b83fdbd3780ae6947bd9f3678b31c26336d38f2d2318976b044cc1c79a3871`;
AUDIT SHA `0a013154dcc73f8ae23e94802f7a68a02360ad64364e03be630fc64ceb0337bf`.
Stress no autorizado, 2026 cerrado y producción intacta. No iniciar otra familia
de datos para rescatar este sprint.

### Sprint persistente — CROSS_MARKET_TRANSMISSION_V1

El cierre anterior no autoriza retuning, pero el objetivo económico persistente
rota a mecanismos causales materialmente nuevos. Registro autoritativo en
`ECONOMIC_FAMILY_REGISTRY.md`. La única familia ejecutable ahora es
`CROSS_MARKET_TRANSMISSION_V1`; H-TPOVALUE1 queda solo en cola.

La nueva familia reutiliza barras 1m existentes SPXW/SPY/QQQ/TLT y el master
ask-to-bid, sin capturas ni datasets fuente nuevos. Exige las 30 barras cerradas
exactas `[t-30,t)` y añade al E0 Pairwise el bloque completo de 28 campos:
beta, residuo 1/5/15m, RV relativa, lead/lag y basis z-score para SPXW-SPY,
QQQ-SPY, QQQ-SPXW y target-TLT. No reutilizar los `ctx_*` as-of live ni añadir
VIX. Modelo único predeclarado: nueve LightGBM cuantiles por lado, utilidad
integrada y p(win) >=50%, con grid inner train-only y scheduler exacto.

2022-2023 son desarrollo; 2024-2025 siguen cerrados hasta commit/freeze; 2026 y
producción intactos. Si el único outer falla, cerrar y rotar sin cambiar pares,
ventanas, features, modelo, grid o gates.

V1 abortó outcome-free: SPXW 2022-11-25 a las 13:35 tenía 30 closes idénticos
después del cierre de media jornada. El master incluye paths no certificables
post-cierre; en 2022-2023, 126/357 filas de tres medias jornadas cruzan el cierre
en al menos un lado. No usar epsilon ni seleccionar por exit. V1 queda
`FAILED_CAUSALITY`.

V1R1 omite completas y por calendario congelado las nueve medias jornadas
2022-2025: 1.072 filas, dejando 96.553. Es la única reparación autorizada; no
cambia features/modelo/folds/grid/scheduler. Predeclaración:
`CROSS_MARKET_TRANSMISSION_V1R1_HALF_DAY_REPAIR.md`.

V1R1 volvió a parar outcome-free en QQQ event 2024-05-30 11:10: SPXW tenía un
solo retorno no cero y `std(returns[1:])=0`, por lo que lead/lag no existe. No
usar epsilon, cero, remover feature o excluir fila. Cross-market queda
`BLOCKED_DATA` sin desarrollo económico.

Familia activa: H-TPOVALUE1. Usa 36 campos de developing TPO/POC/VAH/VAL sobre
el propio underlying, master elegible 96.553, X0 vs X0+TPO y el modelo quantile
ya predeclarado. Fuente exacta 09:30..t-1, sin cross-market. Predeclaración:
`H_TPOVALUE1_EXECUTABLE_PREDECLARATION.md`. 2024/2025 y 2026 siguen cerrados.

Clarificación outcome-free previa al builder: TPO period=1m; lattice por floor
inclusivo sin tolerancia; igualdad/denominadores de value, tails y crosses
exactos; gate 100% finite, >=2 estados y valor modal <99,5% por ticker-año.
V1R1 fija además centros/bordes POC-VA, `value_location=(close-VAL)/(VAH-VAL)`
sin clipping y efficiency 15/30m sobre exactamente h transiciones. Cualquier
denominador no definido aborta; todavía no se ha construido ninguna fila TPO.
El builder debe usar checkpoints atómicos por ticker-sesión y revalidar hashes
de source/keys/código/protocolo/features al reanudar; no relanzar desde cero.

### Checkpoint H-TPOVALUE1 data gate — 2026-07-15

El build outcome-free terminó `PASS_EXACT_TPO_VALUE_VIEW` sobre `5cca9e0`:
96.553 filas, 69 columnas y 2.777 sesiones fuente. Vista SHA
`fded87a10bdf038cb3c0d9fdd03de7e62f1f4dab987d8fbc25d93a0b9f3078fe`;
manifest SHA
`693a1708084b6157164c8fe87e763f23f30458969b2163ef3e1c5dd9074b1331`.
Las 36 features son finitas; las 432 celdas ticker-año-feature pasan con mínimo
4 estados y máximo modal `0,9243992606284658`. Auditoría independiente: 2.777
hashes source/checkpoint exactos. El parquet grande queda en `tmp/`; compactos
en `h_tpovalue1_executable_202201_202512_v1_data_gate/`.

Esto no es rentabilidad: aún no se abrió PF/WR/PnL. Acción única: hacer
reanudable y commit/push del runner económico, ejecutar desarrollo causal
2023-04..12 y cerrar la familia si no cumple gates. Solo si desarrollo pasa se
permite congelar y abrir una vez 2024-2025. 2026 y producción siguen intactos.

Runner económico reanudable implementado pre-outcome: checkpoint atómico por
mes/ticker/brazo, manifest-last y hashes de vista/master/protocolo/modelo/código/
outputs. Regression real construye 6/6 folds y un segundo run reutiliza 6/6;
suite conjunta builder/runner/modelo `33 passed`, Ruff clean. Debe commit/push
antes de ejecutar desarrollo.

### Cierre económico H-TPOVALUE1 — 2026-07-15

La primera celda requerida, SPXW outer 2023-04 con inner 2023-01..03, cerró X0
y X1 `ABSTAIN_OUTER`: 0/42 grids pasan los tres meses. En X1 ningún grid pasa
enero o febrero y 6/42 pasan marzo. Near-miss 70/50: 68 trades, PF pooled
0,921718 y -1,831R; enero PF 0,529/WR44,44%/-3,228R, febrero
0,759/33,33%/-2,366R, marzo 1,560/61,54%/+3,763R. La gate exige cada celda, por
lo que desarrollo ya era imposible y se detuvo tras 2/54 folds sellados.

Estado `FAILED_ECONOMIC_DEVELOPMENT_EARLY_STOP`. No se abrió outer porque el
inner abstuvo; QQQ/SPY, meses siguientes, 2024/2025 y 2026 permanecen cerrados.
Compactos en `h_tpovalue1_executable_development_early_stop_202304_v1/`. No
rescatar TPO por grid/ticker/mes.

Siguiente rotación permitida: factibilidad outcome-free `KING-GEX-SLOPE1`,
inspirada por net GEX slope/sign flip de `live_king_node.py`. No usar sus
calibraciones Jan-Jun 2026, fixed UTC-4, CALL-IV compartida, signs dealer
supuestos ni higher Greeks derivados como si fueran nativos. El Excel sigue
siendo referencia no auditada hasta disponer del runtime spreadsheet exigido.

### KING-GEX-SLOPE1 predeclarada — 2026-07-15

Fuente existente wall-state exacta, sin download: 109.785 decisiones con lag45
contiguo; QQQ/SPXW/SPY 35.919/37.908/35.958. Mínimo 19 sesiones con señal por
mes/ticker en 2023; capacidad hold30/caps mínima 38/76/19. Live parity sigue
`RESEARCH_PROXY_LIVE_PARITY_BLOCKED` por diferencias frente a King Node.

Reglas sin fit ni sweep: K0 usa signo de net GEX para momentum (negativo) o
reversión (positivo); K1, único candidato, exige además signo de pendiente 45m
alineado con el nivel. Momentum es ret15 causal. Desarrollo fixed-rule completo
2023, ask->bid y scheduler común; cualquier celda fallida cierra. Runner siempre
checkpoint por mes/ticker/brazo antes de outcomes.

Runner económico `evaluate_king_gex_slope_v1.py` implementado pre-outcome:
revalida source/protocolo, solo carga outcomes 2023, deriva acciones fijas y
persiste 72 checkpoints manifest-last. Tests conjuntos King/TPO/quantile
`26 passed`; Ruff/py_compile clean. Debe commit/push antes de ejecutar.

Primer intento detenido antes de acción/payoff/scheduler/métrica: el runner
exigía wall->master total. Censo correcto: 20.309 claves master elegibles, cero
sin wall, 28.977 wall válidas y 8.668 extras sin oportunidad executable. Freeze
`KING_GEX_SLOPE1_DATA_GATE_CLARIFICATION.md`: master LEFT exact wall, exigir
20.309 both y omitir extras. K1 queda 13.286 señales; QQQ mínimo 16 días pero
cap2 capacidad 32, SPY mínimo 19. No existe aún PF/WR/PnL King.

Fix master-left implementado con census hard 20.309 y K1 13.286 señales; hash
del amendment forma parte del checkpoint. Regression `5 passed`, Ruff/compile
clean. Commit/push antes del relaunch; target anterior inexistente.

### Cierre económico KING-GEX-SLOPE1 — 2026-07-15

La idea de `live_king_node.py` se tradujo a una regla fija executable sobre el
proxy histórico de net GEX: K0 usa nivel y K1 exige además pendiente 45m alineada
con el signo. El replay 2023 está cerrado `CLOSED_FAILED_ECONOMIC`. K1: 1.324
trades, WR 42,22%, PF 0,804 y -89,845R; pasa solo 2/36 ticker-meses. K0:
1.443 trades, WR 43,10%, PF 0,810 y -94,144R. Frecuencia y concentración pasan;
el fallo es alpha direccional.

Auditoría independiente revalidó 72/72 checkpoints, hashes/filas, scheduler y
métricas. En los mismos timestamps K1, el lado elegido bate al contrario solo
49,02%; invertir también pierde (PF 0,904). El oracle de lado da PF 7,320, por
lo que existe movimiento potencial pero no una orientación causal demostrada.
No rescatar por CALL-only, signo/ticker, thresholds o meses favorables. 2024,
2025, todo 2026 y producción permanecen cerrados/intactos. Seal en
`king_gex_slope1_executable_development_2023_v1/`.

El workbook `MASTER_KING_NODE_RECORD_V5.xlsx` permanece no auditado a nivel de
celdas por falta del runtime spreadsheet requerido; no afirmar que sus fórmulas
o resultados hayan sido validados. Una siguiente prueba debe atacar el cuello
de botella CALL/PUT con una hipótesis nueva y predeclarada, no ampliar esta
familia post-hoc.

### Research activo — KING-GEX-EXIT1

El diagnóstico exacto muestra que WR 42-43% podría ser viable, pero el payoff
ratio es solo 1,10-1,12. En K1, 749 negative triggers restan -455,108R y 546
positive triggers suman +363,076R; 96,51% del gross loss viene de exits <=-55%.
El brazo totalmente invertido también pierde tras rehacer scheduler: 1.304
trades, WR 43,02%, PF 0,850 y -67,677R; solo 1/36 celdas pasa.

`KING_GEX_EXIT1_EXECUTABLE_PREDECLARATION.md` congela antes de recalcular paths
16 configuraciones globales de stop/trail/horizonte, siempre min hold 30m,
max 180m, entry ask, exit bid y mismo scheduler. Debe reproducir exactamente
el baseline por evento/right antes de cualquier alternativa y checkpoint por
ticker-mes y dirección/config. Solo una pareja que pase las 36 celdas puede
congelarse para outer 2024/2025. No seleccionar exit por ticker/mes/signo/side.

Runner `evaluate_king_gex_exit_v1.py` implementado pre-alternate-outcome. Hashea
Greeks/OI/OHLC por ticker-mes, revalida contrato exacto y paridad B00 de return,
hold, status, max/min para ambos rights antes de persistir las 16 alternativas.
Checkpoints manifest-last: 36 source cells y 32 direction/config policies. Suite
King exit+slope `13 passed`, Ruff/compile clean. Commit/push antes de ejecutar.

Primer run V1 detenido tras solo SPXW-202301 source checkpoint, antes de policy
metrics: el loop pandas por config proyectaba horas. Aclaración runtime V1R1
autoriza solo vectorización semánticamente equivalente, con test escalar vs array
y nuevo target `development_2023_v1r1`. No reutilizar el target V1.

V1R1 vectorizada implementada: igualdad escalar/array `1e-12` sobre 160 paths-
config aleatorios, además de la paridad obligatoria con master. Suite focal
`14 passed`, Ruff/compile clean. Commit/push y relanzar solo al target V1R1.

### Cierre económico KING-GEX-EXIT1 — 2026-07-15

El replay V1R1 completó 36/36 source checkpoints, 425.152 outcomes por
evento/right y 32/32 policy checkpoints. Auditoría independiente revalidó los
hashes, 1.152 celdas ticker-mes y el scheduler. Estado `FAILED_ECONOMIC`: cero
parejas pasan 36/36; 2024/2025/2026 y producción permanecen cerrados/intactos.

La inversión B00 queda en 1.304 trades, WR 43,02%, PF 0,850 y -67,677R. El
mejor PF, stop 30%, mejora a 0,925 y -30,131R pero hunde WR a 35,96%. Stop 50%
maximiza celdas aprobadas con solo 6/36 y PF 0,873. Trail temprano alcanza WR
48,13% pero PF 0,799. Ninguna de las 32 variantes llega siquiera a PF 1,0.

El tradeoff queda localizado: S30 reduce pérdidas y mejora 24,275R en las
1.083 entradas comunes frente a B00, pero convierte 96 ganadoras B00 en
perdedoras y cero perdedoras en ganadoras. Un oracle no causal B00-vs-S30 llega
solo a PF 1,239. Los exits fijos quedan cerrados; la siguiente pregunta permitida
es una decisión causal en +30m entre cerrar y continuar, no otro sweep de stops.
Resultados/checkpoints versionados en
`king_gex_exit1_executable_development_2023_v1r1/`; source seal
`432b0fd5...c4cc53e4`.

`neural/stats.py` sí permite derivar gamma/vanna/charm/vomma/zomma desde los
inputs históricos de ThetaData. No confundir estas variables
`SYNTHETIC_MODEL_DERIVED` con `/greeks/all` nativo ni con inventario dealer:
OI/volumen no contienen el signo comprador/vendedor. Además, la unión E1 de
527 features ya incluyó niveles, cambios y ratios de esas griegas sintéticas,
walls, IB/Fibonacci y movimiento de precio; sus 144 celdas GBT
hurdle/Huber abstuvieron por falta de estabilidad inner. Repetirlas en entry no
es fuente nueva. Su uso a +30m para decidir continuación sí sería una pregunta
distinta y debe predeclararse antes de abrir outer.

### Research activo — KING-GEX-MANAGE30-V1

El oracle exacto posterior al cierre EXIT1 corrige el diagnóstico matched:
D1 B00-vs-S30 con scheduler real da PF 1,190/WR43,60%/+65,326R y solo 13/36
celdas; este selector binario queda descartado incluso como oracle. El oracle
entre las 16 gestiones da PF 2,357/WR54,67%/+324,783R y 32/36 celdas. No es una
policy, pero autoriza investigar elección de gestión en +30m.

`KING_GEX_MANAGE30_V1_PREDECLARATION.md` congela D1 invertido, mismo contrato
ask->bid y una decisión a la primera quote exacta elapsed 30..31 entre las 16
gestiones más E30. Dos brazos fijos: M0 path/contrato y M1 con dinámica de
higher Greeks sintéticas; LightGBM Huber por ticker, target de ventaja vs B00,
train expandido y ningún threshold/grid. Desarrollo walk-forward 2023 entrena
solo con meses previos desde 2022; outer 2024/2025 y 2026 siguen cerrados.

Censo outcome-free 2022-2025: 49.400 K1 (QQQ15.475/SPXW17.033/SPY16.892),
2.721 sesiones con Greeks/OI/OHLC presentes. El data gate debe validar snapshot,
contrato y quote de decisión; existencia de fichero no basta. Gate económica
vigente del objetivo: PF>1,30, WR>45%, trades>12 y PnL>0 en cada ticker-mes.

Antecedente cerrado: `walkforward_option_path_exit_model.py` sobre otro universo
dio PF0,811/WR33,85%/-89.652 y no tenía contrato live equivalente. No reutilizar
sus thresholds/delta/holds. MANAGE30 usa contrafactuales King exactos y min hold
30. Siguiente secuencia: commit/push de predeclaración -> builder/test resumible
-> data gate train/dev -> commit -> runner walk-forward 2023. No abrir outer si
ninguno de M0/M1 pasa las 36 celdas.

Builder train/dev implementado pre-label en
`build_king_gex_manage30_v1.py`: hard-stop 2022-01..2023-12, 22.273 K1,
checkpoint manifest-last por sesión con hashes raw/código/protocolo, paridad
B00 obligatoria, estado exacto 30..31, E30 y 16 contrafactuales. Calcula M0 y
M1 desde quotes observadas; los lags ausentes quedan NaN, nunca as-of. Suite
builder+EXIT1 `16 passed`, Ruff/compile clean. Commit/push antes de cualquier
build real; target previsto `tmp/king_gex_manage30_v1/train_dev_202201_202312_v1`.

Primer intento detenido pre-path/pre-label: el master 10:30 se unía antes de
aplicar la ventana King 11:20–14:30. Aclaración V1R1 congela filtrar 680..870
antes del join: 33.902/33.902 master keys y los mismos 22.273 K1. Target V1 solo
tiene RUN_CHECKPOINT y queda rechazado. Fix suite `7 passed`, Ruff/compile clean;
commit/push y relanzar a `train_dev_202201_202312_v1r1`.

### Checkpoint operativo KING-GEX-MANAGE30-V1 — 2026-07-15 16:47

Runner walk-forward reanudable ya pushed en `b8fa50c8`. Congela 72 folds de
desarrollo (12 meses 2023 x 3 tickers x M0/M1), LightGBM Huber y selección de
17 gestiones por ventaja vs B00. Cada fold persiste modelo, medianas,
predicciones, trades, métricas y manifest hash-last. Suite combinada
builder/runner/EXIT1 `22 passed`, Ruff y `py_compile` clean.

Build válido activo en
`tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1`: 843 sesiones selladas
al checkpoint y cero errores reportados. No lanzar duplicado; si muere, el mismo
comando con `--workers 4` revalida/reutiliza manifests. Debe terminar en 22.273
rows y `PASS_DATA_GATE`; auditar cobertura decision/M1 antes de ejecutar el
runner. Aún no existe PF/WR/PnL causal de M0/M1 y 2024-2026 siguen cerrados.

Nuevo handoff canónico detallado en `SUMMARY.md`. El workbook
`MASTER_KING_NODE_RECORD_V5.xlsx` sigue no auditado: la skill está presente pero
su dependencia obligatoria `load_workspace_dependencies/@oai/artifact-tool` no
está expuesta. No buscar/installar sustitutos. Cuando exista, la auditoría será
read-only y cualquier idea separada de MANAGE30/outcomes.

### Corrección causal MANAGE30 V1R2 — 2026-07-15

V1R1 se detuvo fail-closed con 1.265/1.267 sesiones y queda
`REJECTED_CAUSAL_SNAPSHOT_SEMANTICS`: QQQ 2022-06-17 tiene quotes :00/:30 y el
builder agrupaba por minuto, pudiendo usar hasta 30s futuros y mezclar superficies
M1. Exact `quote_dt==timestamp` reproduce 6/6 eventos QQQ. SPXW 2022-02-22
11:20 PUT no tiene contrato d25 ejecutable y es la única rejection train-only;
censo fuente 22.273, rows esperadas 22.272, cero exclusiones 2023.

Aclaración frozen `9a8e0b41`, SHA `35e09f5a...e39a844`; implementación pushed
`a996f260`, suite `24 passed`, Ruff/compile clean. V1R2 activo en
`tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r2`. No duplicar ni usar
los 1.265 checkpoints V1R1. Aún no hay data gate o rentabilidad M0/M1.

### Cierre MANAGE30 y weekly multi-día — 2026-07-16

MANAGE30 V1R2 terminó data gate (22.272 executable, SHA `2c7ff048...000b`) y
falló el único desarrollo 2023. M0 PF0,905/WR38,90%/-34,942R/3 de 36 celdas;
M1 PF0,901/WR39,08%/-36,299R/5 de 36. Ningún brazo elegible; no abrir
2024–2026, neural net o rescate post-hoc.

Por petición explícita anti-bucle, weeklies se limitó a un oracle sellado sin
dataset/modelo: delta 0,50, ask 10:35, exact contract, bid dos sesiones después,
no-overlap, 2022–2025. Cobertura 2.361/2.364. El oracle futuro obtiene PF
12,277/13,960/13,876 y PnL positivo en todos los meses para QQQ/SPXW/SPY, pero
falla WR>50% en 16/144 ticker-meses y solo hay 8–10 trades/mes; 18 es
incompatible con hold dos sesiones y una sola posición. Always-CALL queda en
PF1,042–1,056 y always-PUT <0,81. Status `CLOSED_ORACLE_GATE`; no barrer otros
horizontes/deltas ni abrir dataset weekly. Producción y 2026 siguen intactos.

### Cierre EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1 — 2026-07-16

El one-shot compacto reutilizó sin rebuild el parquet sellado ask-to-bid de
44.169 eventos y completó 18 folds nested Jan-Jun 2026 con seis meses inner,
hold 30–180m, cero overlaps y gates PF>=1,20, WR>=45%, >=13 trades/mes y todos
los meses positivos. Queda `CLOSED_NO_EDGE`: QQQ 121 trades/WR39,67%/PF0,804/
-8,365R/min0/2 de 6 meses positivos; SPXW 110/38,18%/0,794/-8,223R/min14/2 de
6; SPY 107/35,51%/0,797/-8,324R/min0/1 de 6. Cuatro folds abstuvieron. La
recomputación independiente coincide y no hay fallos de cronología, hold o
scheduler. Freeze `3722cbc9`; cierre en
`EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1_CLOSURE.md`.

No rescatar compras 0DTE con más datasets, deltas, thresholds, features IB/Fib,
IV/skew ni filtros de tendencia. El oracle weekly dos sesiones solo permite
8–10 trades/mes sin overlap y no puede cumplir frecuencia; las policies weekly
causales always-CALL/PUT no tienen edge. Los credit spreads direccionales ya
cerrados tienen PF<1. La única factibilidad económica distinta permitida es
short premium simétrico de riesgo definido (iron condor/iron fly) leído
directamente de bid/ask y materializado solo como ledger de trades, con gate
pre-2026 antes de abrir 2026/Julio. No crear otro feature dataset.

### Cierre SHORT_PREMIUM_DEFINED_RISK_V1 — 2026-07-16

El one-shot sobre `ff4fb06f` revalidó 1.506/1.506 sesiones selladas y acumuló
65.512 candidatos en memoria, pero cerró `CLOSED_DATA_EXECUTION_GATE` antes de
selección, métricas u output. QQQ y SPY 2025-10-22 tienen los bid/ask Greek
originales cruzados en 13:35; sus once estructuras de entrada por ticker dejan
44 perfiles unresolved cada una, 88 total. El reloj/contrato exacto existe y
SPXW no falla, pero una pata no-signable invalida el cierre simultáneo. No usar
quote previo, midpoint, exclusión del día ni precios revisados del sidecar como
rescate post-hoc. No existen PF/WR/PnL de V1 y 2026/producción siguen intactos.
Cierre detallado en `SHORT_PREMIUM_DEFINED_RISK_V1_CLOSURE.md`.

La siguiente vía permitida por petición explícita es auditar direccionalidad del
subyacente a 180–240m, primero como señal spot/futuros sin theta. Debe reutilizar
datos ya existentes, probar causalidad/live parity y walk-forward por
ticker-mes; no crear sucesivos datasets ni presentar el viejo
`jepa_production_final_180m` legacy como evidencia validada.

### Auditoría direccional 180m legacy — 2026-07-16

El ledger local de 1.649 trades confirma un mecanismo prometedor pero no una
policy validada. Su 2026 enero–mayo con holds EOD truncados da QQQ PF1,138/min11/
3 de 5 meses positivos; SPX PF1,451/min29/4 de 5; SPY PF1,253/min17/3 de 5.
Solo 894/1.649 trades duran 180m; hay 755 entradas después de 13:00 y 50 holds
<30m. Restringido diagnósticamente a 180m exactos, 2026 da QQQ PF1,333/min5/5
de 5, SPX PF1,619/min15/4 de 5 y SPY PF1,526/min10/5 de 5. Es mejor que 0DTE
long pero falla frecuencia/todos los meses y usa spot+1bp, no fills futuros.

El encoder `xinput_v3_pipeline` fue entrenado hasta 2025-09-11 y seleccionado
con validación 2025-09-12..2026-03-31, incluyendo CE sobre `target`; 2025 y
enero-marzo 2026 no son holdout JEPA limpio. Abril-mayo son posteriores pero
insuficientes. La fuente termina 2026-06-05. Además el resumen frozen de 179
trades/PF1,405 está desincronizado de sus artefactos actuales (20/PF0,267).
Dictamen `PROMISING_BUT_NOT_VALIDATED`; detalle en
`DIRECTIONAL_180M_LEGACY_AUDIT_20260716.md`.

### Freeze DIRECTIONAL_SEMANTIC_JEPA_V1 — 2026-07-16

Nueva prueba price-first predeclarada antes de abrir sus outcomes. Lee en
memoria `data_underlying_derived`, decide con barras hasta 10:35, usa open 10:36
→ open 13:36, hold exacto 180m, una posición/día y 1bp. Features técnicas
incluyen tendencia/RV, sesión previa, IB completo 09:30–10:29 y ocho extensiones
Fib fijas. JEPA GRU student/teacher EMA aprende ventanas +15/+60/+180m con
masking temporal, ticker y canal; no usa direction label, target 0DTE o PnL.

El encoder se selecciona train 2022-2024/val 2025 y se final-fit solo hasta
2025. Downstream residual TECH vs SEMANTIC se elige por ticker únicamente en
walk-forward 2025; selección y hashes deben committed antes de abrir 2026.
Después, one-shot enero-junio y julio MTD con retrain mensual causal. No se crea
dataset de features y no hay sweep/threshold/abstención. Es señal spot, no fills
de futuros.

Preflight físico outcome-free: 2.976 ficheros, 992 sesiones por ticker hasta
2026-07-15, inventory digest `66f8954f...ddd7ec`; grid exacto y OHLC pasan en
991 sesiones comunes. Se excluye causalmente 2023-06-05 para los tres tickers:
las tres barras SPY 09:54–09:56 inválidas conocidas sí caen dentro de esta
secuencia, por lo que no se imputan. Suite focal `8 passed`, Ruff/compile clean.
Siguiente secuencia única: commit/push freeze → fase development hasta 2025 →
commit manifest/selección → one-shot 2026. Aún no existe resultado V1.

### Freeze de desarrollo DIRECTIONAL_SEMANTIC_JEPA_V1

Fase development completada sin leer 2026: `PASS_DEVELOPMENT_FREEZE`. Encoder
train 602 fechas 2022-2024/val 247 fechas 2025, `best_epoch=2`, loss val
0,170433; final-fit 8.490 ventanas solo hasta 2025. Inventario 2.577 fuentes SHA
`dc19b72e...058c2`; modelo SHA `876f36c2...bc607`; ledger 2.964 rows/4 perfiles
SHA `e0b4be91...8b8a2`. Hold exacto 180m y min mensual 18.

JEPA mejora al residual técnico en desarrollo, pero sigue débil: QQQ 247 trades/
WR53,85%/PF1,063/+346,4bps/7 de 12 meses; SPX 51,82%/1,033/+152,3/4 de 12;
SPY 53,04%/1,038/+175,7/4 de 12. La regla frozen selecciona
`SEMANTIC_RESIDUAL` para los tres. No reinterpretar esto como rentabilidad; el
valor es que la elección queda fijada antes del holdout. Siguiente paso único:
commit/push de artefactos y one-shot 2026, sin cambiar perfil o parámetros.

### Cierre DIRECTIONAL_SEMANTIC_JEPA_V1 — `CLOSED_2026_GATE`

One-shot 2026 ejecutado con `SEMANTIC_RESIDUAL` frozen para los tres, open
10:36→13:36, hold 180m exactos, 1bp y cero overlaps. Enero–junio: QQQ 123
trades/WR52,85%/PF0,794/-678,2bps/min19/2 de 6 meses positivos; SPX 123/
50,41%/0,906/-202,1/min19/3 de 6; SPY 123/49,59%/0,794/-468,9/min19/2 de 6.
Frecuencia pasa, economía falla claramente. Julio MTD (10 trades) es positivo:
QQQ PF1,133/+38,0bps, SPX 1,922/+111,1, SPY 1,888/+107,1; no repara la gate ni
cumple aún frecuencia mensual.

Ledger 399 rows SHA `0f08765d...2ab3a`; monthly SHA `024019f6...7b98`;
inventory 2.976 fuentes SHA `66f8954f...ddd7ec`. Este cierre demuestra que el
fracaso 0DTE no era solo theta: el JEPA price-only apenas domina el signo y no
los tamaños adversos. No rescatar seeds/máscaras/horas/thresholds/subsets. Una
hipótesis posterior debe incorporar una fuente causal nueva (options surface,
VIX o futuros) con paridad real; no otro dataset price-only.

### Predeclaración DIRECTIONAL_VOL_COMPLEX_V1

Siguiente hipótesis independiente: añadir al encoder price-only ya sealed el
VIX intradía local y estructura oficial Cboe lagged de VIX1D/VIX9D/VIX/VIX3M/
VIX6M/VIX1Y/VVIX. No reentrena JEPA ni cambia reloj/label/coste: open 10:36→
13:36, 180m, 1bp. Cboe daily close siempre usa `source_date<trade_date`; no se
usa close/high/low del mismo día ni VIX1D intradía licenciado.

La captura inmutable conserva los siete CSV HTTP exactos y manifest. Data gate
antes de outcomes exige cobertura 2022-08..2026-07-15, OHLC/fechas válidas y
paridad VIX local 16:00 vs Cboe 2022-2025 con mediana abs<=0,25 y p99<=1,50 vol
points. Profiles únicos: `VIX_INTRADAY_RESIDUAL` y `VOL_COMPLEX_RESIDUAL`;
selección walk-forward 2025, commit y one-shot 2026. Live parity sigue BLOCKED.
Predeclaración/capturador/test listos; suite capture `4 passed`, Ruff/compile
clean. No se abrió asociación VIX→outcome nueva todavía.

Primer capture attempt se detuvo en memoria y no creó output: VIX official tiene
47 envelopes inválidos antiguos (desde 1992); VIX3M/VIX6M/VIX1Y uno cada uno.
Todos tienen cero fallos en el scope 2022-08..2026-07-15. Aclaración pre-outcome
congela preservar bytes completos, contar fallos históricos y exigir cero
in-scope. No cambia features/modelo/gates. Relanzar solo tras commit/push.

Captura oficial completada `PASS_CBOE_VOL_COMPLEX_CAPTURE`: manifest externo
SHA `5c5e5c8b...473ce`, siete CSV hasta 2026-07-15 con hashes compactos
versionados. Paridad VIX local 16:00 vs Cboe sobre 856 sesiones: mediana abs
0,07, p99 0,58, PASS frente a 0,25/1,50.

Coverage amendment pre-outcome: VIX local falta en 18 sesiones 2022 y
2026-05-18/19; 2025 completo. No as-of/imputar/excluir. El modelo VOL entrena
solo con VIX exacto y en test missing usa la predicción padre
`SEMANTIC_RESIDUAL`, registrando fallback. Ficheros VIX en festivos se ignoran.
Commit/push del compact seal/amendment antes de implementar desarrollo; aún no
se abrió asociación VOL→outcome.

Runner VOL implementado pre-outcome en
`neural/jepa/evaluate_directional_vol_complex_v1.py`: reutiliza exactamente el
encoder/normalizer padre, construye 30 features VIX hasta 10:35 y 33 de curva
Cboe estrictamente lagged, y conserva fallback padre para VIX missing. Dos
profiles únicos, LightGBM/Ridge/reloj/coste idénticos a V1. Tests de no-futuro,
lag estricto, feature contract y fallback: suite conjunta `18 passed`; Ruff y
compile clean. Siguiente secuencia: commit/push del runner congelado -> desarrollo
walk-forward 2025 -> commit selección -> one-shot 2026. Outcomes VOL siguen
cerrados hasta el commit del runner.

### Development freeze DIRECTIONAL_VOL_COMPLEX_V1

Runner congelado/pushed en `f6f3e8e9`; desarrollo walk-forward 2025 completado
sin consultar 2026. Son 247 trades por ticker/profile, mínimo mensual 18 y cero
fallbacks en 2025. Selecciones: QQQ `VIX_INTRADAY_RESIDUAL` (WR 53,04%, PF
1,031, +172,7 bps, 6/12 meses positivos); SPX `VOL_COMPLEX_RESIDUAL` (52,23%,
1,061, +280,4, 6/12); SPY `VIX_INTRADAY_RESIDUAL` (52,63%, 1,074, +338,9,
7/12). Ledger SHA `16092230...9f284`; provenance SHA `c80019a1...86a0d`.

La mejora es débil: QQQ empeora al JEPA padre y SPX/SPY solo mejoran agregado,
sin estabilidad mensual. La predeclaración no tenía gate de desarrollo; congelar
y commit/push de todos los artefactos antes del único one-shot 2026. No cambiar
profiles, ventanas, features ni modelo tras estos resultados.

### Cierre DIRECTIONAL_VOL_COMPLEX_V1 y diagnóstico de colapso

One-shot 2026 desde selección commit `3c5f41e9`: `CLOSED_2026_GATE`. Jan–Jun:
QQQ 123 trades/WR 55,28%/PF 1,039/+113,6bps/min19/3 de 6 meses positivos;
SPX 123/51,22%/0,993/-13,9/min19/4 de 6; SPY
123/50,41%/0,898/-219,6/min19/3 de 6. Julio MTD 10 trades: PF
1,133/1,098/1,888 QQQ/SPX/SPY. Seis fallbacks exactos en 2026-05-18/19.
No rescatar: el overlay solo cambió el lado 3/2/1 días sobre 133 por ticker.

Diagnóstico post-holdout: el contexto input tiene rango efectivo 86,77, pero z
solo 3,44–3,72 de 24 (14,3–15,5%) y dz 11,2–11,8%; no hay dims muertas y la
proyección/GRU tienen rango matricial completo. Es colapso espectral aprendido,
no colapso constante. Aun así no explica todo: probe JEPA corr 2025
+0,046..+0,052 cambia a -0,041..-0,068 en 2026; PF probe 2026
0,788/0,930/0,927. Raw Ridge post-hoc conserva QQQ (PF 1,337) pero falla
SPX/SPY (0,857/0,869) y tiene R² muy negativo; no es promocionable.

VISReg previo elevó rango mediano SMM 10,73%→14,68%, todavía bajo gate 40% y
sin alpha. No aplicar VISReg solo: una futura reparación debe separar common y
residuos por ticker/modalidad, predecir innovaciones, usar corruption semántica
y exigir rango z/dz >=40% outcome-free antes de labels. Diagnóstico:
`PARTIAL_SPECTRAL_COLLAPSE_PLUS_OBJECTIVE_MISALIGNMENT`.

### Cierres direccionales posteriores — 2026-07-16

`DIRECTIONAL_FACTORIZED_INNOVATION_JEPA_V1` corrigió el colapso espectral con
common/residuos/innovaciones y VISReg por bloques: rango efectivo z 53,54% y dz
42,67%, sin dims muertas. Aun así el one-shot 2026 enero–junio falla: QQQ
PF0,846/-492,8bps/2 de 6 meses positivos; SPX PF0,906/-202,1/3 de 6; SPY
PF0,835/-366,8/3 de 6. Julio MTD es positivo pero tiene 10 trades. Dictamen: el
colapso era real pero no era la causa económica suficiente; price-only queda
cerrado para el hold 180m.

`DIRECTIONAL_BREADTH_TRANSMISSION_V1` incorporó todas las fuentes locales
disponibles: QQQ/SPXW/SPY + AAPL/AMZN/GOOGL/META/MSFT/NFLX/NVDA/TSLA/IWM/TLT/
GLD/SLV. Se usó intersección estricta: cualquier fecha faltante o inválida se
eliminó para los 15 tickers, sin imputar ni descargar. Quedaron 962 sesiones
comunes hasta 2026-07-15. Breadth fue elegido para los tres solo con 2025, pero
2026–julio cierra: QQQ 266 trades/WR48,87%/PF0,956/-282,2bps/3 de 7 meses;
SPX 48,87%/0,964/-162,5/3 de 7; SPY 50,38%/1,049/+214,7/3 de 7. Min20
trades/mes. Freeze/cierre commits `fe5ac97a`, `aa9107ad`, `df08a1a3`.

`DIRECTIONAL_INTRADAY_POOLED_V1` probó el mismo panel en seis ventanas no
solapadas de 53–60m y fit pooled. Se cerró antes de 2026: el perfil breadth
seleccionado da en 2025 QQQ PF0,986/3 de 12 meses, SPX 0,954/3 y SPY 0,964/3,
con 1.434 trades/ticker. No rescatar H2–H4 post-hoc. Commit de cierre
`171d9d6e`.

`DIRECTIONAL_OPTION_SURFACE_SPOT_V1` reutilizó, sin crear dataset nuevo, el
parquet 0DTE executable-quote SHA `11e26aad...54fb1`; 289 features
live-observable de superficie/contexto y labels spot 60m calculados en memoria.
Intersección exacta por `(fecha,reloj)` para QQQ/SPXW/SPY: 1.917 decisiones/
5.751 filas pre-2026. Cerrado antes de 2026: OPTION_SURFACE 2025 QQQ 589
trades/WR46,69%/PF0,853/5 de 12 meses; SPX 47,20%/0,816/5; SPY
47,71%/0,804/4. Invertir la predicción también queda bajo PF1. Commit cierre
`62eb20d2`.

Conclusión acumulada: corregir colapso, cambiar a 60m, usar breadth de 15
tickers y añadir IV/delta/theta/vega/OI/volumen/spreads no produce dirección
estable. El problema no es solo decay 0DTE; es falta de información causal
direccional estable en las fuentes actuales.

Fuente nueva auditada: ThetaData no ofrece futuros ES/NQ en su catálogo. El
endpoint stock `trade_quote` sería una vía outcome-free de order flow, pero el
Terminal remoto devuelve HTTP 403 para SPY/QQQ (sin entitlement stocks) y el
Terminal local no puede autenticarse no-interactivamente. No descargar ni abrir
otra familia hasta disponer de una fuente externa de futuros/order flow con
histórico y live parity. El proceso local de preflight fue cerrado; VPS y
producción no se tocaron.

### Cierre DIRECTIONAL_IB_BREAKOUT_FADE_V1 — 2026-07-16

La ejecución directa de Initial Balance/Fibonacci no existía en los cierres
previos y se congeló en `b0f0bdcf`: IB exacto 09:30–10:29, dos ventanas no
solapadas, entrada al open siguiente, stops/targets 0,236/0,618 para breakout y
0,272/0,500 para fade, objetivo no antes de 30m, stop-first y coste 1 bp. Usa
el panel común de 15 tickers; cualquier día faltante se quita para todos.

El one-shot walk-forward 2025 queda `CLOSED_DEVELOPMENT_GATE` sin abrir 2026:
QQQ 406 trades/WR 31,281%/PF 0,779/2 meses positivos/min25; SPX 432/32,407%/
0,785/3/min24; SPY 432/31,944%/0,819/4/min24. Frecuencia PASS pero economía
claramente negativa. No rescatar post-hoc quitando stops, cambiando Fib,
seleccionando meses o usando solo breakout. Producción intacta.

### Checkpoint consolidado posterior — Globex, payoffs alternativos e IB

Estado autoritativo al 2026-07-16: no existe una policy nueva rentable ni
promovible. La gate económica solicitada más reciente es, por ticker, PF>1,20,
WR>45%, más de 12 trades en cada mes y PnL positivo en todos los meses
walk-forward hasta 2026-07-15. La antigua meta PF>=1,30/WR>=50%/>=18 sigue
siendo un objetivo más estricto, no debe confundirse con la gate vigente.

Fuente externa nueva sellada: Yahoo continuous futures 60m, periodo exacto
2024-07-17..2026-07-15, `ES=F/NQ=F/YM=F/RTY=F/ZN=F/GC=F/CL=F`. Manifest SHA
`dad8dc52...dcb7`; captura commit `eaa56342`. `VX=F` no existía (HTTP 404) y
Yahoo rechazó ampliar 60m más allá de 730 días. Son continuos de investigación,
no contratos ni fills broker-grade. Cada decisión exigió los siete futuros y
los 15 tickers cash exactos; cualquier falta se eliminó conjuntamente.

`DIRECTIONAL_GLOBEX_CROSS_ASSET_V1` fue el único near-miss serio: desarrollo
2025 seleccionó Globex con 412 trades/ticker, min22, 9/12 meses positivos y PF
QQQ/SPX/SPY 1,200/1,206/1,210. El one-shot enero–15 julio 2026 cambió de signo:
251 trades/ticker, min20, PF 0,873/0,899/0,888, WR 46,61/47,81/47,81%, PnL
-804/-455/-503 bps y solo 2/3/3 meses positivos. Cierre `f7f09f93`.

Las reparaciones adaptativas no abrieron 2026: V2 logistic online queda en
desarrollo PF 0,980/0,976/0,996 y 5/6/6 meses positivos; V3 Hedge de reglas
mejora agregado a 1,140/1,137/1,098 pero solo 5/6/5 meses; V4 meta-Hedge queda
1,161/0,933/0,965 y 4/5/5. Cierres `bec721d8`, `0b0cf093`, `e3e17bd0`. No
rescatar memorias, ventanas, expertos o inversas post-hoc.

Payoffs no direccionales también quedan cerrados:

- `SHORT_PREMIUM_FIXED_HORIZON_V2` preservó cuatro patas exactas y exits
  30/60/90/120m. Tras 100/1.506 sesiones ya había 4.271 candidatos y 13 exits
  no ejecutables, concentrados en QQQ 2024-02-06. Su contrato declaraba que una
  estructura resoluble al entrar pero no al salir invalida el run; por tanto es
  `REJECTED_DATA_GATE`, sin PF/WR/PnL ni exclusión del día.
- `DUAL_LEG_EVENT_VOLATILITY_V1`, CALL+PUT 0DTE equal-dollar y scheduler global
  sin solape, falla 2025 con 613 trades/ticker: PF QQQ/SPX/SPY
  0,629/0,661/0,605, WR 35,07/33,28/36,22%, 2/2/1 meses positivos y min40.
  Cierre `edcd18c3`; 2026 no se abrió.
- `DIRECTIONAL_IB_BREAKOUT_FADE_V1` queda cerrado en `6dbe157d` con las métricas
  de la sección anterior. El Initial Balance/Fibonacci directo no arregló la
  dirección y falló antes de 2026.

Diagnóstico JEPA final: el colapso espectral era real pero no suficiente. La
arquitectura factorized innovation+VISReg elevó rango efectivo z/dz a
53,54%/42,67% y aun así dio PF<1 en los tres tickers en 2026. No aplicar más
VISReg, corrupciones o capacidad sobre las mismas features como rescate. La
evidencia conjunta apunta a no estacionariedad/falta de información causal
estable, no solo a theta 0DTE.

Estado: `NO_PROFITABLE_CAUSAL_POLICY`. No hay familia activa autorizada ni
cambio de producción. Una continuación debe
predeclarar un mecanismo económicamente independiente (p. ej. cross-session o
relative-value) o incorporar una fuente broker-grade con paridad live; no puede
ser otro dataset de las mismas features, una memoria Globex adicional, otro
stop/Fib, otro delta/horizonte weekly ni selección de ticker/mes observada.

### Research activo — CROSS_SESSION_RELATIVE_VALUE_V1 (2026-07-17)

Se leyó y reconcilió el handoff completo sobre `d02b1ad9`. El worktree tracked
estaba limpio/sincronizado; los numerosos untracked históricos pertenecen al
usuario y no deben añadirse. El registry estaba stale al marcar King activo;
queda corregido sin reabrir resultados.

La nueva familia económicamente independiente está predeclarada antes de abrir
retornos futuros en `CROSS_SESSION_RELATIVE_VALUE_V1_PREDECLARATION.md`. Usa
solo los Parquets underlying existentes (1.003 sesiones por ticker 2022–2025),
no crea dataset: una operación diaria QQQ-SPY equal-notional que revierte la
divergencia desde el cierre previo hasta 10:34, con SPXW solo como ancla. Entrada
10:36, salida 13:36, hold 180m y coste 2 bps total. No hay modelo, threshold,
grid, z-score, beta fit ni abstención.

Fase autorizada única: implementar/testar runner ledger-only y ejecutar desarrollo
2022–2023. Gate mensual del spread: PF>1,20, WR>45%, >12 trades y PnL>0 en
todos los meses. 2024–2026, opciones y producción permanecen cerrados. Si falla
un mes, cerrar sin invertir la regla ni rescatar clocks/costes/anclas.

Runner y tests sintéticos implementados pre-outcome en
`evaluate_cross_session_relative_value_v1.py` y
`test_cross_session_relative_value_v1.py`. El runner no acepta cutoff mutable,
hashea cada fuente, exige grid/metadata/OHLC exactos, materializa solo ledger y
controles no rescatables, incluye meses sin trades y mantiene 2024+ cerrado.
Debe pasar tests/Ruff/compile y commit/push antes de ejecutarse sobre datos reales.

Aclaración data-gate congelada pre-outcome: `2023-06-05` no genera trade, pero
su close 16:00 válido puede servir como prior close del 06-06. El loader permite
únicamente las tres anomalías SPY conocidas 09:54–09:56, sin consumirlas ni
imputarlas; cualquier otra fila inválida aborta. Suite sintética ampliada a
seis regresiones.

### Cierre CROSS_SESSION_RELATIVE_VALUE_V1 — 2026-07-17

El one-shot committed en `5e2dc677` cerró `FAILED_ECONOMIC_DEVELOPMENT`:
496 trades, WR 41,532%, PF 0,627276, -2.349,329 bps, mínimo 19 trades/mes,
5/24 meses positivos y solo 2/24 PASS. Frecuencia pasa; falla alpha. Auditoría
independiente confirmó clocks, coste 2 bps, hold 180m, cero overlaps y cero filas
post-2023. Hash trades `48459a8c...80dfc0`, monthly `75c76e2a...15a9af`.

El momentum opuesto fue solo control y tampoco pasa PF (1,075340); no invertir
post-hoc. No abrir 2024–2026, options o producción. Estado de nuevo:
`NO_PROFITABLE_CAUSAL_POLICY`, sin familia activa. Una continuación debe ser un
mecanismo nuevo, no beta/z-score/threshold/ML sobre esta divergencia.

### Research activo — OPENING_RELATIVE_MOMENTUM_V1

El objetivo persistente exige avanzar desde PF>1 hasta la gate completa sin
redefinir éxito. Se predeclara una señal distinta del cross-session cerrado:
solo movimiento relativo cash `open(09:30)->close(10:34)`, momentum QQQ-SPY con
SPXW como ancla, entrada 10:36, salida 13:36, hold180 y coste2bps. No usa prior
close/gap, threshold, beta, z-score, modelo o abstención.

Desarrollo único 2022–2023; 2024–2026 cerrado. Se registra `INCREMENTAL_EDGE_ONLY`
si PF agregado>1 pero cualquier mes falla, sin autorizar outer ni tuning. Solo
24/24 meses con PF>1,20, WR>45%, >12 trades y PnL>0 permiten freeze posterior.
Siguiente acción: commit/push de predeclaración, luego runner/tests sintéticos.

Runner pre-outcome implementado en `evaluate_opening_relative_momentum_v1.py`.
Reutiliza únicamente el loader causal hasheado del ledger anterior, no su señal
ni outcomes; el manifest sella ambos códigos. Tests sintéticos verifican señal
cash-only, acción/payoff, primera sesión elegible, exclusiones, cutoff inmutable
y diferencia entre PF>1 incremental y PASS mensual completo. Commit/push antes
del run real.

Primer launch detenido antes de imports de fuente/output/outcomes por
`ModuleNotFoundError: neural` al ejecutar el path directo. Target inexistente.
Fix runtime-only añade repo root a `sys.path` antes del import y una regresión
subprocess `script --help`; no cambia señal/universo/gates. Commit/push antes del
relaunch al mismo target aún virgen.
