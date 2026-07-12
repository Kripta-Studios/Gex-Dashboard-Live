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
manifest SHA `59ead62fd66064bda07e7594de82e21e49dad213b29275993f0b48ed318df342`,
eligible IDs SHA `f77dc2231f410679ad97737cc8a4af057e917224e31d2c5df3b6f1f8366a2eca`.
La captura parcial V1 en `D:/ThetaData/wall_quote_tick_dynamics_at_touch_202208_202512_v1`
es `REJECTED_CAUSAL_ALLOWLIST` y no puede reanudarse. Capturar solo a output
V1R1 nuevo con esos hashes; suite H-QDYN focal `20 passed`.
