# CODEX-HANDOFF — estado autoritativo de investigación

**Actualizado:** 12 de julio de 2026

**Checkpoint de captura nativa:** `041b16c research: freeze stored-universe native clock coverage`

**Producción:** intacta. **Junio de 2026:** sellado.

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

La suite combinada relevante pasa `54 passed` (`40` pruebas nuevas de flow,
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

No existe resultado físico ni económico de H-FLOW1 todavía. Producción y todo
2026 continúan intactos; no crear `PLAN.md` porque no hay dirección rentable clara.
