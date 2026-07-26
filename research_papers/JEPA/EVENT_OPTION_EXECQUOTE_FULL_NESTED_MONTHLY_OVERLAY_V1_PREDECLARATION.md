# EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1 — predeclaración

**Fecha:** 2026-07-26
**Estado:** `PREDECLARED_DEVELOPMENT_ONLY`
**Outcomes abiertos por esta familia:** no
**Producción/live:** cerrada

## Pregunta y límite de inferencia

Se evalúa exactamente la regla pedida por el usuario:

1. para cada mes test se usa únicamente información cerrada antes de ese mes;
2. se busca la mejor policy sobre los meses de selección anteriores;
3. la ganadora queda congelada;
4. se ejecuta sin cambios durante el mes test;
5. el ledger final concatena exclusivamente operaciones de los meses test.

La prueba responde si el **algoritmo de reentrenamiento y selección mensual**
transporta cronológicamente. No vuelve OOS a 2026: la familia y su espacio se
formularon después de ver otras pruebas de enero-junio. Por ello, incluso un
PASS completo es development y requiere un mes futuro intacto antes de poder
llamarse promocionable.

Esta prueba sustituye antes de ejecución a
`EXECUTABLE_CONTEXTUAL_BANDIT_GROUPDRO_V1`: GroupDRO se cierra sin runner,
modelo, predicción ni métrica. No se ejecutan ambas familias.

## Fuente física inmutable

Único parquet:

`tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`

- SHA-256:
  `e6a19efba1edb055c733aab4967843f7a4b5f1d2c8238a7a243fc5bbc2251903`;
- bytes: `74.638.331`;
- filas: `44.169`;
- fechas: `20250102..20260630`;
- tickers: `QQQ`, `SPXW`, `SPY`;
- 371 columnas, 0DTE;
- `option_price_mode=executable_quote`;
- entrada al ask y salida, stop o trailing al bid;
- holds físicos observados entre 30 y 180 minutos.

No hay descarga, rebuild, recapture, deduplicación, intersección ni mezcla con
otro parquet. Greek/IV cross-venue y sus repair IDs no participan.

## Modelo base mensual

Se mantienen los tres perfiles de la arquitectura `causal1030`:

- QQQ: `target_zero_dte_d35_return`;
- SPXW: `target_zero_dte_d25_return`;
- SPY: `target_zero_dte_d35_return`.

Cada ticker ajusta dos regresores LightGBM independientes, CALL y PUT. Parámetros
fijos: `objective=regression_l1`, `n_estimators=160`,
`learning_rate=0.035`, `num_leaves=31`, `min_child_samples=60`,
`subsample=0.85`, `colsample_bytree=0.85`, `reg_lambda=5`,
`seed=20260617`. La semilla CALL de cada fold es `seed + MM` del mes test y la
semilla PUT suma además 10.000. Se fijan `deterministic=true` y
`force_col_wise=true`. El target se recorta a `[-5,5]` únicamente para fit; el
ledger usa el retorno físico original.

Las features son las 289 columnas live-observable devueltas por
`walkforward_event_option_profile_selector.build_features`, con clocks desde
10:30 ET y SHA-256 del JSON canónico:

`b4f038f75cb029c4ba2d1e4e4aab5266a45d86e9c2d86ac527a69be521c852ca`.

Todos los transformadores, medianas y modelos se ajustan exclusivamente con el
bloque training. Quedan prohibidas columnas de future/win/status/exit/return y
relojes posteriores como features. Mapping económico: QQQ←QQQ, SPY←SPY y
SPXW←SPY para contexto cash; el contrato y payoff de SPXW siguen siendo SPXW.

## Folds congelados

Cada fold usa todo el bloque `training` para ajustar los dos LightGBM, los seis
meses siguientes para buscar el overlay y un único mes posterior como test:

| Test | Training del modelo | Selección del overlay |
| --- | --- | --- |
| 202601 | 202501–202506 | 202507–202512 |
| 202602 | 202501–202507 | 202508–202601 |
| 202603 | 202501–202508 | 202509–202602 |
| 202604 | 202501–202509 | 202510–202603 |
| 202605 | 202501–202510 | 202511–202604 |
| 202606 | 202501–202511 | 202512–202605 |

Así, enero no interviene en la búsqueda de enero; sí puede intervenir en la
búsqueda de febrero. El mismo principio se repite hasta junio. Ningún modelo,
threshold, filtro, ranking o guard ve el mes test antes de su freeze.

## Espacio exhaustivo del overlay

Se evalúan exactamente `1.128.960` configuraciones por ticker y fold:

- score threshold:
  `[-0.10,0,0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40]`;
- edge `abs(pred_call-pred_put)`:
  `[0,0.05,0.10,0.15,0.20,0.30,0.40]`;
- lado: `[BOTH,CALL,PUT]`;
- 16 ventanas inclusivas:
  `630-870,630-840,630-810,660-870,660-840,660-810,`
  `690-870,690-840,690-810,690-780,720-870,720-840,`
  `720-810,750-870,750-840,750-810`;
- distancia máxima al nivel: `[10,15,20]` bps;
- momentum:
  `[NONE,SELF_COUNTER_5M,SELF_SAME_5M,SPX_COUNTER_5M,`
  `SPX_SAME_5M,QQQ_COUNTER_5M,QQQ_SAME_5M]`;
- máximo diario: `[1,2,3,4]`;
- cooldown: `[0,15,30,45]` minutos.

La acción base es CALL si `pred_call_return >= pred_put_return`, PUT en caso
contrario; `score=max(pred_call_return,pred_put_return)`. El empate exacto va a
CALL. No se añade ninguna configuración, guard de SPY ni regla descubierta
después del test. SPXW conserva como parte fija de la arquitectura el
`stop_pause1` causal: después de observar un stop, no abre otra posición ese
día.

El script histórico `tmp/scan_causal1030_intersection.py`, SHA-256
`0e71f1b3dd71f67fa8b61e259acdd84317337c36d847dc5736afdcaf1e846d3a`,
solo documenta el grid. No se usa como runner: su selección miraba todo H1 y
su cooldown no imponía no-overlap físico.

## Scheduler y física

Los candidatos se ordenan por fecha, minuto y score descendente. Tras aceptar
una entrada:

`next_allowed = max(entry_minute + cooldown, entry_minute + exit_minutes)`.

Esto implementa `reject_while_open`; no hay posiciones superpuestas por
ticker. El hold debe ser finito y estar en `[30,180]`. Se aplica el máximo
diario después de los filtros. Para SPXW, un stop observado activa
`stop_pause1` desde su exit y hasta el fin de la sesión. Toda decisión usa solo
estado conocido en ese instante.

Los campos físicos de acción son los `call/put_d25/d35_opt_exit_ret`,
`*_opt_exit_minutes` y `*_opt_exit_status` de `executable_quote`. No se
reconstruyen fills ni se usan labels legacy.

## Elegibilidad, ranking y freeze

Para ser elegible en selección, una configuración debe producir al menos 13
trades en **cada uno** de los seis meses. Se escoge una única ganadora por
ticker y fold con este orden lexicográfico descendente, calculado solo sobre
selección:

1. número de meses con PnL estrictamente positivo;
2. peor PnL mensual;
3. profit factor agregado;
4. PnL agregado;
5. win rate agregado;
6. mínimo mensual de trades;
7. menor `grid_index` como desempate determinista.

No se exige que selección pase los gates económicos para poder congelar una
ganadora; esos campos forman parte del ranking y el test decide. Si ninguna
configuración alcanza frecuencia 13/mes, el fold-ticker queda
`ABSTAIN_NO_FREQUENCY_ELIGIBLE` y aporta cero trades. No se rescata cambiando
ventana, ticker, profile o ranking.

Cada winner y cada pareja de modelos se serializa y hashea antes de materializar
su mes test. El resultado económico concatena únicamente los 18 ledgers test
(seis meses × tres tickers), nunca operaciones de training o selección.

## Gates development

Para cada ticker sobre enero-junio concatenado:

- PF `>1,20`;
- WR `>45%`;
- PnL neto `>0`;
- mínimo 13 trades en cada mes;
- PnL estrictamente positivo en los seis meses.

También deben pasar:

- fuente y feature hash exactos;
- seis folds y seis freezes por ticker;
- entry ask→exit bid certificado;
- hold 30–180m;
- cero overlap y cero `reject_while_open` violations;
- auditor independiente que refittee 36 modelos, repita el grid winner y
  reproduzca config, predicciones, scheduler, trades, métricas y hashes.

No se selecciona por ticker o mes tras el run. Un único fallo cierra la familia.

## Orden autorizado

1. commit/push de esta predeclaración, cierre GroupDRO, registro y handoffs;
2. implementar runner, freezer por fold y auditor sin evaluación económica;
3. tests, Ruff y compile; commit/push del código;
4. una sola ejecución enero-junio;
5. auditor independiente y commit/push de evidencia;
6. solo si todo pasa, congelar un shadow para el siguiente mes intacto y probar
   paridad exacta backtest/live;
7. solo después se puede desarrollar integración `paper_order_intents=true`.

`services/`, `bots/`, `systemd/` y el paquete live no se modifican durante los
pasos 1–5.
