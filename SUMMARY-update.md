# SUMMARY-update — ledger científico compacto

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
