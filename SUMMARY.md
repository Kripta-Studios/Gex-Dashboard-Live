# SUMMARY.md — Auditoría causal, backtest/live y estado de correcciones JEPA

**Fecha del registro auditado:** 10 de julio de 2026
**Proyecto:** `Gex-Dashboard-Live`
**Ámbito principal:** sistema JEPA de opciones para `SPXW`/SPX, `SPY` y `QQQ`, incluyendo generación de dataset, entrenamiento, walk-forward, selección de policy, paquete de producción, feed en tiempo real y ejecución del bot.

> **Aviso de alcance:** este resumen se ha reconstruido a partir del registro de trabajo suministrado. El registro termina con trabajo todavía en curso y contiene algunas salidas truncadas. Por tanto, “implementado” significa **modificado en el worktree observado**, no necesariamente commiteado, pusheado, desplegado ni validado después de la última edición.

---

## 1. Estado ejecutivo

### Estado actual del paquete

**NO debe considerarse listo para producción ni causalmente certificado.**

El paquete ubicado en:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

se declara internamente como:

```text
status = production_live_ready
policy_profile = causal1030_intersection_guarded_v1
```

pero el validador endurecido lo rechaza. Los bloqueos confirmados al final del registro son:

1. La policy fue seleccionada reutilizando enero–junio de 2026, los mismos meses presentados como evidencia.
2. El artefacto histórico contiene **55 entradas solapadas** que el runtime live habría rechazado por existir una posición abierta.
3. `SPY` queda con **14 operaciones en su peor mes**, por debajo del requisito estricto de más de 18 operaciones mensuales.
4. Las métricas publicadas proceden de labels legacy que no reproducen correctamente la entrada al `ask` y la salida/stop/trailing mediante `bid`.
5. La reconstrucción causal ask→bid comenzó y produjo un nuevo dataset temporal, pero no se completó en el registro una selección anidada walk-forward ni una nueva promoción de policy.
6. Las últimas modificaciones del selector de perfiles introdujeron un error de colección de tests que no consta como resuelto.

### Conclusión operativa

La policy anterior puede tratarse como **candidata forward para julio de 2026**, porque seleccionar con datos cerrados hasta junio para operar julio es conceptualmente admisible. Lo que no puede afirmarse es que enero–junio sean validación OOS de esa misma policy ni que sus métricas legacy representen la ejecución live.

---

## 2. Identidad real de la policy y documentación desfasada

### Hallazgo

La documentación no describía de forma consistente la policy realmente activa.

Archivos que todavía hacían referencia a la policy anterior `balanced`:

```text
AGENTS.md
README.md
docs/README.md
docs/ARCHITECTURE.tex
docs/DEPLOYMENT_GUIDE.tex
```

Artefactos y commits posteriores apuntaban a:

```text
event_option_frozen2025_causal1030_intersection_guarded_v1_202607
causal1030_intersection_guarded_v1
```

Archivos de producción inspeccionados:

```text
systemd/ai_bot.service
systemd/realtime_feed.service
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
```

### Riesgo

Una documentación que afirma que se ejecuta `balanced` mientras el servicio carga `causal1030` dificulta:

- reproducir el entrenamiento;
- saber qué ventana horaria y filtros usa live;
- asociar métricas con el paquete correcto;
- detectar divergencias entre el runbook, systemd y los JSON desplegados.

### Implementado

Se verificó que el perfil real del registry era:

```text
causal1030_intersection_guarded_v1
```

### Pendiente

Actualizar de forma coherente:

```text
AGENTS.md
README.md
docs/README.md
docs/ARCHITECTURE.tex
docs/DEPLOYMENT_GUIDE.tex
docs/CODEX_LIVE_SENTINEL_RUNBOOK.md
```

y generar esos documentos desde una única fuente de verdad del paquete, evitando nombres hardcodeados.

---

## 3. Sobreajuste de selección y falsa validación OOS

### Severidad

**P0 — invalida la certificación estadística actual.**

### Hallazgo

La policy final fue elegida con un escáner que probó aproximadamente **1,13 millones de configuraciones por ticker** sobre enero–junio de 2026. Esos mismos meses se mostraban después como validación de la policy.

Archivo del escáner localizado:

```text
tmp/scan_causal1030_intersection.py
```

Resultados afectados:

```text
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1/
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1_walkforward/
```

Metadatos afectados:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
```

En el registry se observaron componentes con:

```text
select_months = 202601..202606
deploy_month = 202607
```

### Por qué es un problema

Que los modelos base se entrenen solo con 2025 no basta. También son parámetros ajustados:

- threshold;
- dirección CALL/PUT/BOTH;
- ventana de entrada;
- máximo de operaciones;
- cooldown;
- filtros de proximidad;
- guards de riesgo;
- combinación/intersección de componentes.

Si esos elementos se eligen mirando enero–junio, esos meses pasan a ser **selection data**, no OOS.

### Implementado

En:

```text
neural/jepa/validate_event_option_production_package.py
```

se añadieron comprobaciones para:

- exigir `policy_selection_provenance`;
- diferenciar `fixed_pre_oos` y `nested_walk_forward`;
- rechazar intersecciones entre `selection_months` y meses reportados;
- revisar `select_months` de cada componente del registry;
- exigir que cada fold anidado use únicamente meses anteriores;
- exigir hashes/artefactos congelados por fold;
- no aceptar como evidencia OOS un replay de una policy elegida con ese mismo periodo.

Tests añadidos:

```text
tests/test_event_option_production_validator.py
```

Casos cubiertos:

- rechazo de una policy fija que reutiliza el mes evaluado;
- aceptación de folds anidados con fuentes estrictamente anteriores;
- detección de solapamientos entre selección y evaluación.

### Pendiente

Ejecutar una validación realmente causal:

1. Para cada mes `M`, entrenar con meses `< M`.
2. Seleccionar hiperparámetros/configuración solo con meses `< M`.
3. Congelar la policy del fold antes de evaluar `M`.
4. Guardar hash y metadatos de cada policy mensual.
5. Concatenar únicamente los trades OOS de cada fold.
6. No volver a elegir la policy final mirando el conjunto de meses reportado.

Julio de 2026 debe quedar completamente intacto si se usa como primer forward live.

---

## 4. Operaciones solapadas: backtest incompatible con live

### Severidad

**P0 — cambia directamente PnL, volumen y meses positivos.**

### Hallazgo

El backtest/materialización permitía abrir una nueva operación del mismo ticker antes de cerrar la anterior. El bot live mantiene una única posición por ticker y rechaza nuevas entradas mientras está abierta.

Artefacto auditado:

```text
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1/combined_trades.csv
```

Resultado cuantitativo:

```text
Trades publicados:           416
Entradas solapadas:            55
Trades reproducibles en live: 361
```

Al imponer la restricción real:

- `SPY` llegó a **10 operaciones** en el peor mes en uno de los replays;
- abril de 2026 pasó a aproximadamente **−1,999 R**;
- el validador final recomputó un mínimo mensual de `SPY = 14`, todavía por debajo del requisito `>18`.

### Archivos implicados

```text
neural/jepa/materialize_event_static_union.py
neural/jepa/apply_event_static_union_cooldown.py
neural/jepa/scan_event_static_union_configs.py
neural/jepa/walkforward_event_option_gate.py
backtest/backtest_gbt_parquet.py
bots/tradingbot_wrapper_jepa.py
```

### Implementado

En:

```text
neural/jepa/validate_event_option_production_package.py
```

se añadió una auditoría de intervalos:

```text
entry_minute -> entry_minute + exit_minutes
```

para contar cualquier entrada del mismo ticker y día que caiga antes del cierre de la posición anterior.

También se exige:

```text
live_contract.position_overlap_policy = reject_while_open
```

Test específico:

```text
tests/test_event_option_non_overlap.py
```

y test adicional del validador:

```text
tests/test_event_option_production_validator.py
```

### Pendiente

- Aplicar la misma función de no-solapamiento **durante la selección**, no solo al validar el CSV final.
- Regenerar todos los resultados.
- Reoptimizar los límites diarios y cooldown sobre el stream no solapado.
- Confirmar por ticker y mes:
  - PnL > 0;
  - WR > 50%;
  - PF > 1,3;
  - operaciones mensuales > 18.

La policy legacy no supera actualmente estas condiciones al reproducir el runtime.

---

## 5. Rejilla temporal: entrenamiento cada 5 minutos, live casi cada minuto

### Severidad

**P1 alta — cambia qué entrada consume el cupo y bloquea señales posteriores.**

### Hallazgo

El dataset/backtest se generaba en una rejilla de cinco minutos, pero live aceptaba candidatos en casi cualquier minuto.

Auditoría de candidatos live:

```text
Candidatos seleccionados: 876
Fuera de la rejilla:       706
En la rejilla:             170
```

Es decir, aproximadamente cuatro de cada cinco candidatos live no pertenecían al universo temporal de entrenamiento.

Con holds de 30–180 minutos y una sola posición, una entrada a `10:31` puede bloquear la entrada entrenada de `10:35`. El hold mínimo no hace irrelevante la divergencia; la amplifica.

### Archivos implicados

```text
neural/jepa/event_option_live_scorer.py
neural/jepa/event_option_live_snapshot.py
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/runtime_policy_replay_summary.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/QQQ_static_union_balanced/QQQ_static_union_balanced.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/SPXW_static_union_balanced/SPXW_static_union_balanced.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/SPY_static_union_balanced/SPY_static_union_balanced.json
```

### Implementado

Se añadió al filtro live:

```json
"entry_sample_minutes": 5,
"entry_sample_anchor_minute_et": "10:00",
"requires_complete_initial_balance": true
```

En:

```text
neural/jepa/event_option_live_scorer.py
```

`apply_candidate_universe_filter()` ahora:

- valida la cadencia;
- valida el anchor;
- rechaza si falta la columna `minute`;
- acepta únicamente minutos congruentes con la rejilla;
- falla cerrado si falta `initial_balance_complete`.

Test:

```text
tests/test_event_option_live_causality.py
```

### Pendiente

- Regenerar los artefactos de métricas con este filtro aplicado desde el principio.
- Evitar editar manualmente los JSON legacy; exportar un paquete nuevo desde una configuración versionada.
- Verificar en logs live que no aparece ninguna entrada off-grid.

---

## 6. Quotes de un segundo, deduplicación y merges muchos-a-muchos

### Severidad

**P1 alta — podía mezclar contratos y segundos distintos.**

### Hallazgo

En:

```text
neural/jepa/event_option_live_snapshot.py
```

los timestamps se truncaban al minuto antes de escoger una cross-section sincronizada. Esto convertía todos los segundos del minuto en la misma clave y podía generar:

- duplicados por `(strike, right)`;
- merges muchos-a-muchos con OHLC;
- selección de una quote obsoleta o parcial;
- mezcla de Greeks, bid/ask y volumen de segundos distintos.

### Implementado

En:

```text
neural/jepa/event_option_live_snapshot.py
```

se modificó:

- `_parse_datetime()` para preservar segundos;
- `_prepare_chain()` para elegir una sola cross-section completa;
- deduplicación por `(strike, right)`;
- merge OHLC agregado y validado como `one_to_one`;
- rechazo de snapshots incompletos;
- control de antigüedad y tolerancia futura;
- selección posterior del anchor exacto `HH:MM:00` para igualar el histórico.

En:

```text
services/realtime_feed.py
```

la ventana de ThetaData se ancla ahora al minuto exacto:

```text
snapshot_end = now_et.replace(second=0, microsecond=0)
```

en lugar de terminar en el segundo actual.

Tests:

```text
tests/test_event_option_live_causality.py
```

cubren:

- cross-section completa;
- ausencia de duplicados;
- no utilización del snapshot parcial posterior;
- timestamp exacto del minuto.

### Pendiente

- Ejecutar replay sobre varios días reales de `rt_data/`.
- Añadir métricas de runtime:
  - número de contratos por snapshot;
  - porcentaje de completitud;
  - edad;
  - duplicados descartados;
  - motivo de rechazo.

---

## 7. Lookahead intraminuto de hasta 59 segundos

### Severidad

**P1 media — no fue el mayor problema, pero cambia señales.**

### Hallazgo

El histórico asociaba Greeks/spot de inicio de minuto con el `close` completo de ese mismo minuto. Ese `close` no es observable en el instante de decisión y puede incorporar hasta 59 segundos de futuro.

Archivos implicados:

```text
neural/jepa/build_event_option_dataset.py
neural/jepa/event_option_live_snapshot.py
services/realtime_feed.py
```

### Medición realizada

La ablación reportó:

```text
Desplazamiento mediano del spot:       1,98 bps
Cambio de signo de ret_5m:            14,75% de los puntos
Cambio del gate de proximidad:         3,89% de los puntos
Sesgo direccional sistemático:         no observado
```

Conclusión: no parece explicar por sí solo todo el edge, pero sí cambia materialmente el universo de señales.

### Implementado

En:

```text
neural/jepa/build_event_option_dataset.py
```

para `option_price_mode="executable_quote"`:

- se usa `underlying_price` de la snapshot de Greeks;
- se usa el último bar subyacente ya completado para volumen;
- el OHLC de opciones se desplaza un minuto porque ThetaData etiqueta las barras por apertura;
- se evita usar el close del minuto todavía abierto.

En:

```text
neural/jepa/event_option_live_snapshot.py
```

live se ancla a `HH:MM:00`.

### Pendiente

- Reentrenar por completo con el dataset causal.
- Comparar señales legacy frente a causal, por ticker y mes.
- Documentar la ablación en un artefacto versionado.

---

## 8. Labels de opciones no ejecutables: `opt_close/high/low` frente a ask→bid

### Severidad

**P0 — el mayor deterioro de métricas observado.**

### Hallazgo

El backtest legacy:

- entraba mediante `opt_close`;
- no pagaba correctamente el `ask`;
- evaluaba stops/trailing con OHLC;
- no reproducía la ruta de bids ejecutables;
- podía tratar highs/lows de trades como si fueran precios realizables.

El runtime live:

- compra aproximadamente al `ask`;
- marca y sale al `bid`.

### Medición realizada

```text
Half-spread de entrada mediano: 0,775%
Half-spread p90:                1,389%
```

Cambiar solo entrada de `opt_close` a `ask`, manteniendo salidas legacy:

```text
PF total: 1,749 -> 1,596
```

La estrategia todavía quedaba por encima de 1,3 en los tres tickers bajo esa aproximación.

Pero al reproducir:

- entrada al ask;
- stop/trailing/salida con bids observados;

el replay cayó a:

```text
WR:                41,35%
PF:                 0,871
Retorno agregado: −18,19
Legacy agregado:  +77,54
```

Por tanto, el principal problema no era el spread aislado, sino la ruta de precios utilizada por el label.

### Archivos implicados

```text
neural/jepa/build_event_option_dataset.py
neural/jepa/walkforward_event_option_gate.py
neural/jepa/walkforward_event_option_profile_selector.py
bots/tradingbot_wrapper_jepa.py
services/realtime_feed.py
```

### Implementado

En:

```text
neural/jepa/build_event_option_dataset.py
```

se añadió/extendió:

- `option_price_mode` con modos `legacy_ohlc` y `executable_quote`;
- entrada usando ask;
- salida y stops mediante bid;
- aceptación de bid cero como pérdida total válida;
- `conservative_no_quote_label()`:
  - si no existe quote posterior ejecutable, fuerza retorno `−1.0`;
  - respeta el menor entre horizonte y cierre de mercado;
- inserción de un bid cero al final si la ruta se corta antes de la salida forzada;
- uso de `underlying_price` observable;
- uso de la barra anterior completada;
- columnas de disponibilidad del contrato;
- columna exacta de strike seleccionada.

En:

```text
neural/jepa/walkforward_event_option_gate.py
neural/jepa/walkforward_event_option_profile_selector.py
```

se añadió:

- validación de disponibilidad observable de CALL y PUT;
- error explícito si faltan columnas necesarias en datasets ejecutables;
- outcomes conservadores finitos;
- clipping solo en el target de regresión, no en el PnL usado para métricas.

En:

```text
bots/tradingbot_wrapper_jepa.py
```

se corrigió:

- bid cero como mark real, no como quote ausente;
- `NaN` para ausencia/ambigüedad de quote;
- no cerrar prematuramente por un dato ausente;
- cierre real por stop si el bid observable es cero.

Tests:

```text
tests/test_build_event_option_dataset.py
tests/test_jepa_bot_execution.py
```

### Pendiente

- Completar entrenamiento y nested walk-forward sobre `executable_quote`.
- Comparar los labels generados con ejecuciones paper reales.
- Modelar slippage adicional si se usan market orders.
- No promover ningún artefacto legacy como evidencia de rentabilidad live.

---

## 9. Contrato exacto: el bot podía ejecutar otro strike distinto del evaluado

### Severidad

**P1 alta — backtest y live podían referirse a contratos diferentes.**

### Hallazgo

La fila del modelo identificaba un contrato por delta, pero el bot volvía a seleccionar por delta al ejecutar. En empates o cambios rápidos podía elegir un strike distinto del usado para features y label.

Archivos implicados:

```text
neural/jepa/build_event_option_dataset.py
bots/tradingbot_wrapper_jepa.py
```

### Implementado

En el dataset se añadieron:

```text
call_dXX_strike
put_dXX_strike
```

En el bot:

- `_select_delta_option()` admite `strike_target`;
- el candidato live debe contener el strike seleccionado;
- si falta o es inválido, se rechaza;
- el bot ejecuta el strike exacto de la snapshot evaluada.

Test:

```text
tests/test_jepa_bot_execution.py
```

verifica que un empate de delta no sustituya el strike seleccionado.

### Pendiente

Añadir también al contrato verificable:

- símbolo OCC exacto;
- expiración;
- right;
- timestamp de quote;
- hash o identificador de snapshot.

---

## 10. Expiración incorrecta y snapshots de otro día

### Severidad

**P1 alta — una posición 0DTE podía valorarse con otro vencimiento o datos stale.**

### Hallazgo

Se detectaron riesgos de:

- posición persistida sin expiración;
- búsqueda ambigua de la quote;
- uso del snapshot más reciente aunque fuera de otra fecha;
- uso de initial balance del día anterior.

Archivos implicados:

```text
bots/tradingbot_wrapper_jepa.py
neural/jepa/event_option_live_snapshot.py
```

### Implementado

En el bot:

- se exige expiración para valorar la posición;
- si falta, se devuelve `NaN` y se rechaza la valoración ambigua;
- se filtran snapshots por la fecha ET actual;
- se filtra por expiración exacta;
- no se reutilizan filas stale de otra sesión.

En snapshot:

- el historial spot se restringe al mismo día de la snapshot;
- `_latest_spot_at()` ya no cae hacia una observación futura;
- se rechaza initial balance proveniente del día anterior;
- se aplican límites de edad de snapshot.

Tests:

```text
tests/test_event_option_live_causality.py
tests/test_jepa_bot_execution.py
```

### Pendiente

- Migrar o invalidar posiciones persistidas antiguas que no contengan expiración.
- Añadir versión de esquema al estado persistido.
- Incluir un procedimiento explícito de recuperación tras reinicio.

---

## 11. Initial Balance incompleto y fallback sintético

### Hallazgo

El snapshot live podía construir features aunque faltaran minutos de `09:30–10:29`, e incluso crear un fallback sintético a partir del spot actual.

Esto hacía que features de IB parecieran disponibles sin que el rango inicial estuviera completo.

Archivo:

```text
neural/jepa/event_option_live_snapshot.py
```

### Implementado

Se añadió:

```text
_initial_balance_complete()
```

que exige los 60 minutos `570..629`.

`build_snapshot_row()` ahora:

- devuelve `None` si el IB no está completo;
- deja de crear un historial sintético de una sola fila;
- publica `initial_balance_complete = 1` solo cuando el contrato se cumple.

El scorer falla cerrado si la columna requerida falta.

Tests:

```text
tests/test_event_option_live_causality.py
```

### Pendiente

Incluir en logs el minuto concreto ausente y diferenciar:

- feed todavía inicializando;
- hueco de datos;
- día de sesión reducida;
- mercado cerrado.

---

## 12. Contexto cross-index incorrecto: `front_weekly` frente a `zero_dte`

### Hallazgo

Al construir contexto cross-index live, la ordenación podía seleccionar `front_weekly` por orden léxico, mientras el entrenamiento usaba contexto del dataset `zero_dte`.

Archivo:

```text
neural/jepa/event_option_live_snapshot.py
```

### Implementado

Cuando hay filas `zero_dte`, se priorizan para el contexto de:

```text
SPXW
SPY
QQQ
```

Test:

```text
tests/test_event_option_live_causality.py
```

### Pendiente

Hacer explícito en la policy qué expiry mode alimenta cada contexto, en vez de depender de una prioridad implícita.

---

## 13. Feature de volumen incompatible entre histórico y live

### Hallazgo

Histórico usaba:

```text
tick_count
```

mientras live almacenaba la misma magnitud causal bajo:

```text
volume
```

Esto dejaba `underlying_volume = 0` en live.

Archivo:

```text
neural/jepa/event_option_live_snapshot.py
```

### Implementado

`_standardize_spot_frame()` mapea:

```text
volume -> tick_count
```

cuando `tick_count` no existe.

Además, para el instante de decisión se usa el volumen del último minuto completado.

Test:

```text
tests/test_event_option_live_causality.py
```

Resultado observado en replay de snapshot:

```text
underlying_volume = 60.0
```

### Pendiente

Renombrar la columna en origen o publicar un schema explícito para no depender de alias.

---

## 14. Features intradía no observables o inconsistentes en live

### Hallazgo

El selector de perfiles podía incluir features cuyo valor offline no estaba disponible o no era equivalente en el minuto de decisión live.

Archivos:

```text
neural/jepa/event_option_component_live.py
neural/jepa/walkforward_event_option_profile_selector.py
```

### Implementado

En:

```text
neural/jepa/walkforward_event_option_profile_selector.py
```

se añadió:

- filtro `live_observable_features_only=True`;
- `entry_start_minute_et`;
- exclusión por prefijos;
- consulta a `live_observable_feature_issues_for_columns()`;
- almacenamiento de `features_by_profile` en resultados;
- nuevo universo `production_zero_dte`;
- filtro mínimo de `positive_month_rate`.

En:

```text
neural/jepa/event_option_component_live.py
```

se dejó de eliminar completamente filas con NaN legítimos. Ahora:

- schema drift o columnas ausentes siguen siendo error;
- NaN ordinarios se imputan con las medianas congeladas del entrenamiento;
- se registra `imputed_rows` en vez de alterar silenciosamente el universo.

### Problema pendiente importante

Después de estas modificaciones se añadió un test en:

```text
tests/test_event_option_live_causality.py
```

pero su ejecución terminó dos veces con:

```text
ERROR during collection
```

Se intentó corregir el import dual paquete/script en:

```text
neural/jepa/walkforward_event_option_profile_selector.py
```

pero el registro no muestra una ejecución posterior exitosa.

Por tanto, esta parte debe considerarse **implementación incompleta/no validada**.

---

## 15. Validador demasiado permisivo y autocertificación por JSON

### Severidad

**P0 de proceso — permitía marcar como live-ready un paquete incompatible.**

### Hallazgo

El validador anterior:

- confiaba demasiado en métricas precalculadas dentro de JSON;
- aceptaba gates más laxas, como alrededor de 45% WR y 12 trades;
- no recalculaba todas las métricas desde trades;
- no auditaba selección temporal;
- no auditaba rejilla de entrada;
- no auditaba solapamientos;
- no exigía labels ejecutables.

Archivo:

```text
neural/jepa/validate_event_option_production_package.py
```

### Implementado

El validador ahora:

- carga el artefacto de trades;
- recalcula trades, WR, PF, PnL, mínimo mensual y tasa de meses positivos;
- incluye meses sin trades como conteo cero;
- restringe el cálculo a los meses declarados;
- compara las métricas recalculadas con las publicadas;
- exige como mínimo:
  - `WR >= 0.50`;
  - `PF >= 1.30`;
  - `min_month_trades > 18`;
  - `positive_month_rate = 1.0`;
- detecta entradas off-grid;
- detecta solapamientos;
- valida selección OOS;
- valida `executable_quote`;
- valida duración y columnas necesarias;
- rechaza artefactos vacíos o no recomputables.

Resultado sobre el paquete actual:

```text
FAIL
- SPY min_month_trades = 14
- 55 overlapping same-ticker entries
- selección solapada con meses reportados
- labels no ejecutables
```

Tests:

```text
tests/test_event_option_production_validator.py
```

### Pendiente

- Integrar el validador en `ExecStartPre=` de systemd o en el pipeline de despliegue.
- Impedir que un JSON conserve `production_live_ready` si la validación falla.
- Firmar/hashar los artefactos que el validador recomputa.
- Añadir una opción que escriba un informe JSON/Markdown de bloqueo.

---

## 16. Semántica del capital de riesgo de 5.000 USD

### Hallazgo inicial

Se señaló que el bot podía abrir un contrato cuyo débito superara 5.000 USD.

Archivo:

```text
bots/tradingbot_wrapper_jepa.py
```

### Decisión de diseño adoptada

Se reinterpretó `risk_capital_dollars` como **objetivo de sizing**, no como techo absoluto. Debido a que un contrato es indivisible, se permite al menos uno aunque su coste supere el objetivo.

Implementación:

```text
_contracts() -> max(1, floor(risk_capital / contract_cost))
```

si coste y capital son positivos.

La documentación interna del bot se ajustó para decir que un contrato indivisible puede exceder el target.

### Pendiente

La policy debe declarar de forma inequívoca uno de estos modos:

```text
hard_debit_cap
sizing_target_allow_one_contract
```

No debe inferirse por comentarios del código.

---

## 17. Rebuild causal generado, pero no promovido

### Dataset temporal generado

Se ejecutó:

```text
neural/jepa/build_event_option_dataset.py
```

con:

```text
option_price_mode = executable_quote
tickers = SPXW SPY QQQ
expiry_modes = zero_dte
periodo = 2025-01-01 .. 2026-06-30
manifest rows = 1.113
```

Salida temporal:

```text
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3/event_option_dataset.parquet
```

Después se enriqueció con:

```text
neural/jepa/enhance_event_option_dataset_physics.py
```

Salida:

```text
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/SUMMARY.json
```

Comprobaciones registradas:

```text
shape = (44169, 239)
duplicate key rows = 0
sha256 = 68ae45c89d521f71431261deea9bcc7e465feb294d17bf122afbddbb30a4c8f8
date_max = 20260630
```

### Estado

El dataset causal parece haberse construido y enriquecido, pero permanece bajo `tmp/`.

### Pendiente

- Verificar exhaustivamente todas las sesiones.
- Guardar manifiesto de fuentes y hashes.
- Mover a una ruta versionada de `research_papers/JEPA/results/_diagnostics/`.
- Ejecutar selección anidada.
- Generar trades OOS.
- Ejecutar validador estricto.
- Exportar un paquete nuevo; no sobrescribir silenciosamente el legacy.
- Comparar live replay con el nuevo dataset.

---

## 18. Tests y validaciones ejecutadas

### Ejecuciones exitosas observadas

En distintos puntos del registro:

```text
6 passed
7 passed
16 passed
16 passed
35/35 nuevas pruebas
40 passed
```

Suite de 40 tests:

```text
tests/test_build_event_option_dataset.py
tests/test_event_option_live_causality.py
tests/test_event_option_non_overlap.py
tests/test_event_option_production_validator.py
tests/test_jepa_bot_execution.py
```

También pasó `py_compile` para:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
neural/jepa/build_event_option_dataset.py
neural/jepa/event_option_live_snapshot.py
neural/jepa/event_option_live_scorer.py
neural/jepa/validate_event_option_production_package.py
neural/jepa/walkforward_event_option_gate.py
```

### Último estado de tests

Después de añadir la exclusión de features no observables al selector:

```text
tests/test_event_option_live_causality.py
```

falló durante collection dos veces.

Por tanto:

- el bloque anterior estaba verde;
- el estado final del worktree **no estaba completamente verde**;
- falta capturar y corregir el traceback final.

### Tests nuevos relevantes

```text
tests/test_event_option_live_causality.py
tests/test_event_option_production_validator.py
tests/test_build_event_option_dataset.py
tests/test_jepa_bot_execution.py
tests/test_event_option_non_overlap.py
```

---

## 19. Estado de Git y versionado

### Commits existentes antes de las correcciones

```text
66731f6 Deploy causal 10:30 JEPA event option policy
4ad505c Add causal policy verification artifacts
153f1a7 Update live sentinel runbook for causal policy
```

Al reiniciarse la sesión posterior:

```text
HEAD = 153f1a7
origin/main = 153f1a7
```

### Estado observado

Había numerosos archivos tracked modificados y varios artefactos untracked, entre ellos:

```text
bots/tradingbot_wrapper_jepa.py
services/realtime_feed.py
backtest/backtest_gbt_parquet.py
neural/jepa/build_event_option_dataset.py
neural/jepa/event_option_live_snapshot.py
neural/jepa/event_option_live_scorer.py
neural/jepa/event_option_component_live.py
neural/jepa/validate_event_option_production_package.py
neural/jepa/walkforward_event_option_gate.py
neural/jepa/walkforward_event_option_profile_selector.py
neural/jepa/apply_event_static_union_cooldown.py
tests/test_event_option_live_causality.py
tests/test_event_option_production_validator.py
tests/test_build_event_option_dataset.py
tests/test_event_option_non_overlap.py
tests/test_jepa_bot_execution.py
tmp/
```

### Conclusión

El registro **no muestra ningún `git commit` ni `git push` posterior a estas correcciones**.

### Pendiente

Separar en commits revisables:

1. `fix: align live snapshot timestamps and 5m sampling`
2. `fix: enforce exact option contract and expiration`
3. `fix: add executable ask-to-bid labels`
4. `fix: enforce no-overlap in backtest and validation`
5. `fix: require causal policy-selection provenance`
6. `test: add JEPA live/backtest regression suite`
7. `data: add causal dataset manifest and hashes`
8. `model: add nested walk-forward production candidate`
9. `docs: synchronize production policy and runbooks`

No hacer push de datasets grandes o `tmp/` sin revisar `.gitignore` y tamaño.

---

## 20. Prioridad recomendada para continuar

### P0 — antes de cualquier despliegue

1. Corregir el error de collection introducido en el selector.
2. Ejecutar la suite completa.
3. Congelar y versionar el dataset `executable_quote`.
4. Implementar selección nested walk-forward.
5. Aplicar no-solapamiento durante selección y evaluación.
6. Validar todos los meses con gates estrictas.
7. Exportar un paquete nuevo con nombre distinto.
8. Ejecutar el validador estricto y un replay equivalente a live.
9. Solo entonces cambiar systemd.

### P1 — robustez live

1. Añadir telemetría de snapshots incompletos/stale/off-grid.
2. Versionar el estado persistido de posiciones.
3. Validar símbolos, expiración, strike y right exactos.
4. Añadir smoke test de arranque equivalente a systemd.
5. Verificar rutas y permisos del usuario del servicio.

### P2 — documentación y proceso

1. Actualizar documentación desfasada.
2. Generar documentación desde el manifest de producción.
3. Hacer commits atómicos y push.
4. Crear un checklist de promoción y rollback.

---

## 21. Criterios de aceptación del siguiente paquete

El siguiente paquete solo debe marcarse `production_live_ready` si cumple simultáneamente:

### Causalidad

- Cada mes se evalúa con modelo y policy congelados antes de ese mes.
- Ningún mes evaluado aparece en train, selection o tuning de su fold.
- Features observables en el minuto de decisión.
- No se usan barras todavía abiertas.
- Entrada y salida usan precios ejecutables.

### Equivalencia live

- Rejilla de cinco minutos idéntica.
- Una sola posición por ticker.
- Mismos límites diarios y cooldown.
- Mismo contrato exacto.
- Misma expiración.
- Misma semántica de bid cero y quote ausente.
- Mismo tratamiento de missing values.

### Métricas por ticker

Para cada uno de:

```text
SPXW
SPY
QQQ
```

y para cada mes OOS:

```text
PnL mensual > 0
Win rate > 50%
Profit factor > 1,3
Trades mensuales > 18
```

### Artefactos

- Dataset y manifest con SHA-256.
- Configuración por fold.
- Hash de policy por fold.
- Trades OOS concatenados.
- Métricas recomputables desde CSV/Parquet.
- Validador estricto en PASS.
- Tests completos en PASS.
- Commit y tag de release.
- Runbook y rollback actualizados.

---

## 22. Dictamen final

La auditoría encontró problemas reales y cuantitativamente relevantes. El mayor no fue el pequeño spread ni el desfase medio de spot, sino la combinación de:

1. selección de policy sobre el mismo periodo reportado;
2. operaciones solapadas imposibles en live;
3. labels basados en OHLC que no reproducían bids ejecutables;
4. universo temporal live distinto del entrenamiento;
5. contrato exacto y expiración no completamente fijados;
6. validador que permitía autocertificación.

Una parte sustancial de las defensas ya fue implementada en el worktree y cubierta por tests. También se generó un dataset causal ask→bid temporal. Sin embargo, al final del registro faltaban:

- resolver el último error de tests;
- completar el nested walk-forward;
- obtener métricas que satisfagan los objetivos;
- exportar una policy nueva;
- validar systemd;
- hacer commit y push.

**Estado recomendado: `BLOCKED_FOR_PRODUCTION`.**
