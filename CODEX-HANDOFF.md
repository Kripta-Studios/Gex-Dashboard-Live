# CODEX-HANDOFF — estado autoritativo de investigación

**Actualizado:** 13 de julio de 2026

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
