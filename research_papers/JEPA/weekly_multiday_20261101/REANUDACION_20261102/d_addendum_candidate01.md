# D: addendum operativo para ledger, eventos y manifest

Estado: `NON_EXECUTABLE_DRAFT_PENDING_B_C_READMISSION_AND_REVIEW`
Fecha: 2026-11-02

## 1. Alcance y autoridad

Este addendum resuelve sólo las interfaces operativas que el borrador D dejó pendientes. No altera la receta científica sellada: `ENTRY_FROZEN`, una candidatura terminal por `(plan_id, anchor_id)`, primer evento por ticker y sesión, arms A/B/C, clocks, costes, outcomes y criterio de desarrollo visto.

No autoriza fixtures, implementación, lectura de B/C, apertura de arrays, eventos, replay, PnL, modelo ni publicación. Cualquier resultado futuro seguirá siendo `SEEN_DEVELOPMENT`. El criterio informado mantiene ocho meses completos positivos de enero a agosto bajo coste adverso y septiembre parcial separado. No hay modelo aceptado ni promoción autorizada.

| autoridad local verificada | bytes | SHA-256 |
|---|---:|---|
| dirección de revisitas | 16.596 | `6850f559c25d5d6d3352109e0bc7b33d0d48aa14e0d097fa7cfdbe8c9ac1f011` |
| borrador científico D | 14.258 | `4ea0fe7b149c04f8859ea1e3b7fa1058a2d826569b6b054fbefab10c5ba16dc7` |
| contrato de riesgo congelado | 5.663 | `9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b` |
| contrato H2 | 10.737 | `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5` |
| binding de riesgo congelado | 1.954 | `821ae641bba9f24e31410b9f9a11bb04e13eb09675eb39d25f52440827a1f61f` |
| resultado documental de riesgo | 4.468 | `b49931835494b846ff4c090e84611fd814e79b452389a41f8c59acd11d00aacb` |
| borrador operativo C | 20.544 | `88f76551957e73e37c5dd816b00ec17d035132186df5071be10a5c534368cb3f` |

Los pins finales de B y C quedan `PENDING`. Un intento, staging, parcial o copia de fixture no puede sustituirlos.

## 2. Prerrequisitos y entradas futuras

Un launcher D futuro rechaza antes de crear raíz, observer, journal o staging si falta alguno de estos símbolos:

- `<B_FINAL_PRODUCER_MANIFEST_SHA256_PENDING>`
- `<B_FINAL_AUDIT_MANIFEST_SHA256_PENDING>`
- `<B_FINAL_VALUE_PATHS_OUTPUT_MANIFEST_SHA256_PENDING>`
- `<C_FINAL_PRODUCER_MANIFEST_SHA256_PENDING>`
- `<C_FINAL_AUDIT_MANIFEST_SHA256_PENDING>`
- `<C_FINAL_GEOMETRY_STATES_SHA256_PENDING>`
- `<C_FINAL_GEOMETRY_LEVELS_SHA256_PENDING>`
- `<C_FINAL_COVERAGE_SHA256_PENDING>`
- `<D_BENCHMARK_ADAPTATION_ROOT_READMISSION_PENDING>`

B aportará los 1.620 planes `PLANNED`, sus dos `decision_id` CALL/PUT congelados a las 10:30, spot D/D1/H2 y clocks de opción. C aportará las 2.790 filas `geometry_states_1030` y anchors `geometry_levels_1030`. D consume sólo anchors C con `geometry_status=AVAILABLE_GEOMETRY`, `ENTRY_FROZEN` y `first_available_at` anterior o igual al instante de uso. D no redescubre calendario, cache, contrato weekly, wall ni geometría.

La integración C permanece pendiente de bindings separados: el productor usa estado `PASS_FINAL_C_RUNTIME_BINDING` y contratos/engines/B-final/runtime; el auditor usa `BOUND_REAL_C_GEOMETRY_1030` y closure pins. El wrapper futuro no precrea el observer C: el productor exige crearlo ausente y el auditor debe comprobar process, exit y journal bajo ese mismo parent observer.

## 3. Convenciones físicas e IDs

Las salidas usan Arrow schema explícito, Parquet 2.6, data-page v1, `zstd` nivel 9, `use_dictionary=false`, `write_statistics=true`, sin índice ni metadata pandas. Writer y PyArrow quedan `PENDING_IMPLEMENTATION_BINDING`.

`trade_date` y `event_session_date` usan `date32[day]`. Los timestamps locales son `timestamp[ns]` sin zona, en el eje NY naive de B/C. Su representación de ID es `*_local_ns`: `int64` firmado de nanosegundos desde `1970-01-01T00:00:00` interpretado como civil NY naive, sin conversión UTC. Un SHA-256 es `utf8` de 64 hex minúsculas. Un `float64` no nulo debe ser finito. JSON usa UTF-8, `sort_keys=true`, separadores `(',', ':')`, `ensure_ascii=false` y `allow_nan=false`.

| ID | payload canónico exacto | unicidad |
|---|---|---|
| `revisit_id` | `{schema:"D_REVISIT_V1",plan_id,anchor_id}` | un registro por `(plan_id,anchor_id)` |
| `event_id` | `{schema:"D_EVENT_V1",revisit_id,confirmation_time_local_ns,departure_side}` | una confirmación por `revisit_id` |
| `intent_id` | `{schema:"D_INTENT_V1",event_id,decision_id,entry_quote_time_local_ns}` | una intención tras quote elegible |
| `ledger_id` | `{schema:"D_LEDGER_V1",intent_id,arm,cost}` | una fila por intención, arm y coste |

`confirmation_time` de events se mapea uno a uno a `confirmation_time_local_ns` en el payload de `event_id`; `entry_quote_time` se mapea uno a uno a `entry_quote_time_local_ns` en `intent_id`. Esos son los únicos timestamps de IDs. `revisit_id` existe sin confirmación. `event_id`, `intent_id` y `ledger_id` son nulos si su condición causal no ocurre. Un path, pin, ordinal de fila, outcome, quote posterior o PnL nunca participa en un ID.

## 4. `revisit_events.parquet`

La tabla contiene una fila por `revisit_id`, ordenada por `(calendar_ordinal, plan_id, anchor_id)`. Conserva la fila aunque no produzca evento, intención o fill.

| # | campo | Arrow | null | regla |
|---:|---|---|:---:|---|
| 1 | `calendar_ordinal` | `int32` | no | FK a calendario B/C |
| 2 | `plan_id` | `utf8` | no | identidad B admitida |
| 3 | `ticker` | `utf8` | no | `SPY`, `QQQ` o `SPXW` |
| 4 | `trade_date` | `date32[day]` | no | sesión D |
| 5 | `expiry_date` | `date32[day]` | no | expiry B congelado |
| 6 | `anchor_id` | `utf8` | no | ID C admitido |
| 7 | `cluster_ordinal` | `int16` | no | ordinal C |
| 8 | `center` | `float64` | no | ENTRY_FROZEN |
| 9 | `band` | `float64` | no | positiva, ENTRY_FROZEN |
| 10 | `source_mask` | `int16` | no | incluye FIB y WALL |
| 11 | `anchor_available_at` | `timestamp[ns]` | no | `first_available_at` C |
| 12 | `revisit_id` | `utf8` | no | ID determinista |
| 13 | `event_status` | `utf8` | no | enum siguiente |
| 14 | `armed_side` | `utf8` | sí | `ABOVE` o `BELOW` |
| 15 | `visit_time` | `timestamp[ns]` | sí | primera muestra interior |
| 16 | `departure_time` | `timestamp[ns]` | sí | primera departure válida |
| 17 | `departure_side` | `utf8` | sí | `ABOVE` o `BELOW` |
| 18 | `revisit_time` | `timestamp[ns]` | sí | primera revisita válida |
| 19 | `confirmation_time` | `timestamp[ns]` | sí | segundo minuto confirmado |
| 20 | `confirmation_time_local_ns` | `int64` | sí | payload de event ID |
| 21 | `event_id` | `utf8` | sí | ID de confirmación |
| 22 | `event_session_date` | `date32[day]` | sí | fecha de confirmación |
| 23 | `decision_id` | `utf8` | sí | CALL ABOVE, PUT BELOW |
| 24 | `side` | `utf8` | sí | `CALL` o `PUT` |
| 25 | `stop_spot` | `float64` | sí | regla D sellada |
| 26 | `target_anchor_id` | `utf8` | sí | target C determinista |
| 27 | `target_spot` | `float64` | sí | centro de target |
| 28 | `entry_quote_time` | `timestamp[ns]` | sí | primera ask posterior |
| 29 | `entry_quote_time_local_ns` | `int64` | sí | payload de intent ID |
| 30 | `event_entry_ask` | `float64` | sí | source ask B, sin redondeo |
| 31 | `intent_id` | `utf8` | sí | ID de intención |
| 32 | `terminal_reason` | `utf8` | no | enum siguiente |
| 33 | `overlap_rank_json` | `utf8` | no | ranking canónico |
| 34 | `transition_trace_json` | `utf8` | no | cada transición observada |
| 35 | `spot_coverage_status` | `utf8` | no | cobertura spot |
| 36 | `option_coverage_status` | `utf8` | no | cobertura quote |
| 37 | `label_available_at` | `timestamp[ns]` | sí | madurez de outcome |
| 38 | `b_plan_pin` | `utf8` | no | SHA B que admitió plan |
| 39 | `c_anchor_pin` | `utf8` | no | SHA levels C |

`event_status` admite exactamente `NOT_ARMED`, `ARMED`, `VISIT`, `DEPARTURE`, `REVISIT`, `CONFIRMED`, `CROSS_THROUGH`, `GAP_CROSSING`, `NO_TARGET`, `SUPERSEDED_FIRST_EVENT`, `PRE_FILL_TRIGGER_CANCELLED`, `NO_ENTRY_QUOTE` y `TOO_LATE`. `terminal_reason` admite exactamente `NO_VISIT`, `NO_DEPARTURE`, `CROSS_THROUGH`, `NO_REVISIT`, `NO_CONFIRMATION`, `NO_TARGET`, `SUPERSEDED_FIRST_EVENT`, `PRE_FILL_TRIGGER_CANCELLED`, `NO_ENTRY_QUOTE`, `TOO_LATE`, `OUTSIDE_EVALUATION_WINDOW`, `WAIT`, `NO_FILL`, `FILLED` y `NOT_EVALUABLE`.

`CONFIRMED` exige `event_id`, `decision_id` y stop, pero no target. Una confirmación sin target conserva `event_id`, escribe `terminal_reason=NO_TARGET` y no crea intención. Sólo una confirmación con target puede crear intención. Una intención que llena termina con `terminal_reason=FILLED`; WAIT y NO_FILL conservan sus razones propias. `overlap_rank_json` contiene exactamente `{eligible_event_session_date,confirmation_time_local_ns,cluster_ordinal,anchor_id,rank,winner_revisit_id,winner_event_id,decision}`. `decision` vale `WINNER`, `SUPERSEDED` o `NOT_COMPETING`. El ganador es el mínimo de `(confirmation_time, cluster_ordinal, anchor_id)`. Una candidatura que no confirma conserva rank, ganador y sus IDs como null.

`transition_trace_json` es un array JSON canónico no vacío, ordenado por `seq`, de objetos con exactamente `{seq,kind,time_local_ns,spot_f64,side,state_before,state_after,reason}`. `seq` es `int32` desde cero; `time_local_ns` es `int64` signed local; `spot_f64` es string `float(x).hex()` o null; `side` es `ABOVE`, `BELOW` o null. `kind` admite `ARMED_ABOVE`, `ARMED_BELOW`, `VISIT`, `DEPARTURE`, `REVISIT`, `CONFIRMATION_MINUTE_1`, `CONFIRMED`, `CROSS_THROUGH`, `GAP_CROSSING`, `MISSING_MINUTE`, `SESSION_BREAK`, `NO_TARGET`, `SUPERSEDED_FIRST_EVENT`, `PRE_FILL_TRIGGER_CANCELLED`, `NO_ENTRY_QUOTE` y `TOO_LATE`. La traza conserva todos los intentos de rearm, cruce y gap. Un `GAP_CROSSING` sólo registra ausencia de toque y conserva el estado previo: no arma ni rearma. Sólo un `CROSS_THROUGH` permite rearmar desde la muestra siguiente. Ningún registro infiere un toque, orden o fill intraminuto.

## 5. `revisit_replay_ledger.parquet`

Una intención común A/B produce cuatro filas: A-base, A-adverso, B-base y B-adverso. C no se copia ni recalcula en esta tabla. C se vincula desde `benchmark_binding` del manifest después de una decisión pre-outcome de root. Esto evita inventar un mapeo entre un evento D y una decisión benchmark de 10:30.

La tabla se ordena por `(event_session_date, ticker, arm, cost, ledger_id)`.

| # | campo | Arrow | null | regla |
|---:|---|---|:---:|---|
| 1 | `ledger_id` | `utf8` | no | ID determinista |
| 2 | `intent_id` | `utf8` | no | FK events |
| 3 | `event_id` | `utf8` | no | FK events |
| 4 | `plan_id` | `utf8` | no | FK B |
| 5 | `ticker` | `utf8` | no | identidad |
| 6 | `event_session_date` | `date32[day]` | no | fecha evento |
| 7 | `arm` | `utf8` | no | A o B solamente |
| 8 | `cost` | `utf8` | no | `BASE` o `ADVERSE` |
| 9 | `admission_status` | `utf8` | no | enum siguiente |
| 10 | `fill_status` | `utf8` | no | enum siguiente |
| 11 | `decision_time` | `timestamp[ns]` | no | confirmation |
| 12 | `entry_quote_time` | `timestamp[ns]` | sí | idéntica A/B |
| 13 | `horizon_end` | `timestamp[ns]` | no | H2 10:35 estricto |
| 14 | `decision_id` | `utf8` | no | contrato B congelado |
| 15 | `right` | `utf8` | no | CALL o PUT |
| 16 | `entry_ask` | `float64` | sí | source ask B, sin redondeo |
| 17 | `slippage_dollars` | `utf8` | no | decimal canónico 0.01 o 0.02 |
| 18 | `unit_risk_cents` | `int64` | sí | fórmula congelada |
| 19 | `qty` | `int32` | sí | entera y fija |
| 20 | `entry_debit_decimal` | `utf8` | sí | Decimal exacto, sin redondeo |
| 21 | `exit_trigger_time` | `timestamp[ns]` | sí | A stop/target, B H2 |
| 22 | `exit_trigger_kind` | `utf8` | sí | enum siguiente |
| 23 | `exit_bid_time` | `timestamp[ns]` | sí | primera bid permitida |
| 24 | `exit_bid` | `float64` | sí | source bid B, sin redondeo |
| 25 | `accounting_exit_time` | `timestamp[ns]` | sí | hora que atribuye el neto |
| 26 | `exit_credit_decimal` | `utf8` | sí | Decimal exacto, bid cero si falta |
| 27 | `net_decimal` | `utf8` | sí | crédito menos débito, exacto |
| 28 | `outcome` | `utf8` | sí | sólo fills exitosos |
| 29 | `missing_exit_flag` | `bool` | no | bandera ortogonal |
| 30 | `ambiguous_flag` | `bool` | no | bandera ortogonal |
| 31 | `label_available_at` | `timestamp[ns]` | sí | madurez contable |
| 32 | `cash_before_entry_decimal` | `utf8` | no | caja realizada del libro |
| 33 | `reserve_before_entry_decimal` | `utf8` | no | principal reservado |
| 34 | `exit_fee_obligation_before_decimal` | `utf8` | no | comisión de salida comprometida |
| 35 | `realized_equity_before_decimal` | `utf8` | no | cash más reserve |
| 36 | `cash_after_entry_decimal` | `utf8` | sí | null sin fill |
| 37 | `reserve_after_entry_decimal` | `utf8` | sí | null sin fill |
| 38 | `exit_fee_obligation_after_entry_decimal` | `utf8` | sí | null sin fill |
| 39 | `realized_equity_after_entry_decimal` | `utf8` | sí | null sin fill |
| 40 | `cash_after_exit_decimal` | `utf8` | sí | null sin fill |
| 41 | `reserve_after_exit_decimal` | `utf8` | sí | null sin fill |
| 42 | `exit_fee_obligation_after_exit_decimal` | `utf8` | sí | null sin fill |
| 43 | `realized_equity_after_exit_decimal` | `utf8` | sí | null sin fill |
| 44 | `wait_reason` | `utf8` | sí | motivo admisión |
| 45 | `b_value_pin` | `utf8` | no | SHA B admitido |
| 46 | `c_geometry_pin` | `utf8` | no | SHA C admitido |
| 47 | `replay_contract_pin` | `utf8` | no | `9c387e9b…` |

`admission_status` admite `ADMITTED`, `WAIT`, `EVENT_RISK_BUDGET`, `CAPITAL_BLOCKED` y `OPEN_POSITION`. `fill_status` admite `FILLED`, `NO_FILL`, `PRE_FILL_TRIGGER_CANCELLED` y `NOT_APPLICABLE`. `exit_trigger_kind` admite `TARGET`, `STOP`, `H2`, `MISSING_EXIT` y `NOT_APPLICABLE`. `outcome` es null salvo `fill_status=FILLED`; para un fill admite `TARGET_FIRST_OBSERVED`, `STOP_FIRST_OBSERVED` o `TIMEOUT_H2`. Un NO_FILL, WAIT o cancelación no recibe outcome ni timeout sintético.

La cantidad conserva exactamente la regla congelada:

```text
unit_risk_cents = ceil((Decimal(str(event_entry_ask)) + Decimal("0.02")) * 10000 + 260)
qty = 500000 // unit_risk_cents
```

El productor instala `decimal.Context(prec=1000)` local con `context.traps[decimal.Inexact]=True` para cada conversión, ecuación y suma de libro. El `ceil` de admisión es la única operación de redondeo permitida y explícitamente congelada. El productor toma cada quote source `float64` sin modificar y calcula `Decimal(str(entry_ask))` o `Decimal(str(exit_bid))`. Para qty `q`, slippage `s` y bid ausente sustituido sólo en la ecuación por Decimal(0), las ecuaciones exactas son:

```text
entry_debit = q * ((entry_ask + s) * 100 + 1.30)
exit_credit = q * (max(exit_bid - s, 0) * 100 - 1.30)
net = exit_credit - entry_debit
```

Los importes `*_decimal` son `utf8` decimal canónico: sin exponente, signo sólo si negativo, sin ceros fraccionales sobrantes y `0` para cero. Se obtiene con `format(value,"f")` y eliminación textual de ceros, sin operación Decimal ni redondeo de contexto. Ninguna columna monetaria fuerza dos decimales. Una bid ausente deja `exit_bid=null`, fija `missing_exit_flag=true`, usa Decimal(0) sólo en `exit_credit` y por tanto conserva la comisión negativa `q*(-1.30)`; nunca escribe crédito cero. A/B comparten `intent_id`, quote, ask, riesgo, qty, admisión y fill.

Sólo un fill puede tener `TARGET_FIRST_OBSERVED`, `STOP_FIRST_OBSERVED` o `TIMEOUT_H2`. Sólo A puede tener los dos primeros. Stop y target simultáneos escriben `STOP_FIRST_OBSERVED` y `ambiguous_flag=true`. B llena con `TIMEOUT_H2`. `accounting_exit_time=exit_bid_time` cuando existe bid observada; para salida missing es `horizon_end`, el instante en que su ausencia queda conocida. `label_available_at` es `exit_bid_time` al liquidar una salida observada o `horizon_end` para H2 y salida missing.

El criterio 8/8 atribuye cada `net_decimal` de fill al mes NY naive de `accounting_exit_time`; enero-agosto son los ocho meses completos y septiembre es parcial. Un diagnóstico por cohorte del mes de entrada puede reportarse separado, sin sustituir el criterio ni rescatar meses.

## 6. `plan_coverage.parquet`, ventana de evaluación y manifest

`plan_coverage.parquet` contiene exactamente 1.620 filas, una por `plan_id` B, ordenadas por `(calendar_ordinal,plan_id)`. Esta tabla mantiene cobertura cuando C no tiene geometría válida, cuando no existe confluencia FIB+WALL, o cuando ningún anchor produce evento. No fabrica un anchor para esos casos.

| # | campo | Arrow | null | regla |
|---:|---|---|:---:|---|
| 1 | `calendar_ordinal` | `int32` | no | FK B |
| 2 | `plan_id` | `utf8` | no | único |
| 3 | `ticker` | `utf8` | no | identidad B |
| 4 | `trade_date` | `date32[day]` | no | sesión D |
| 5 | `expiry_date` | `date32[day]` | no | expiry B |
| 6 | `geometry_partition` | `utf8` | no | enum siguiente |
| 7 | `c_anchor_count` | `int32` | no | todos los anchors C del plan |
| 8 | `eligible_anchor_count` | `int32` | no | anchors FIB+WALL |
| 9 | `revisit_row_count` | `int32` | no | filas events emitidas |
| 10 | `confirmed_event_count` | `int32` | no | event IDs no nulos |
| 11 | `first_physical_event_id` | `utf8` | sí | descriptivo, no cap |
| 12 | `first_physical_event_time` | `timestamp[ns]` | sí | descriptivo, no cap |
| 13 | `outside_evaluation_event_count` | `int32` | no | confirmations fuera de ventana |
| 14 | `in_evaluation_event_count` | `int32` | no | winners dentro de ventana |
| 15 | `economic_intent_count` | `int32` | no | 0..3, una por día físico |
| 16 | `event_day_evidence_json` | `utf8` | no | array canónico por día |
| 17 | `terminal_status_counts_json` | `utf8` | no | conteos canónicos |
| 18 | `b_plan_pin` | `utf8` | no | SHA B |
| 19 | `c_geometry_pin` | `utf8` | no | SHA C |

`geometry_partition` admite `C_MISSING_SOURCE`, `C_INVALID_IB`, `C_INVALID_STATE60`, `NO_CONFLUENT_ANCHOR` y `ELIGIBLE_ANCHOR_SET`; estas cinco partitions se excluyen mutuamente y suman 1.620 planes. `first_physical_event_*` es sólo descriptivo. No limita candidaturas, eventos ni intenciones posteriores. Cada plan puede tener hasta tres intents ganadores, uno por `(ticker,event_session_date)` físico dentro de D/D1/H2, sujeto a admisión; una candidatura `(plan,anchor)` sigue siendo terminal por separado.

`event_day_evidence_json` es un array JSON canónico ordenado por `(event_session_date,confirmation_time_local_ns,cluster_ordinal,anchor_id)`, con exactamente un objeto por confirmación candidata del plan y claves `{event_session_date,confirmation_time_local_ns,revisit_id,event_id,overlap_decision,winner_event_id,window_status,terminal_reason,intent_id,economic_intent_status}`. `window_status` admite `OUTSIDE_EVALUATION_WINDOW` e `IN_EVALUATION_WINDOW`; no particiona el plan. `terminal_status_counts_json` es un objeto canónico con exactamente las claves `NO_VISIT,NO_DEPARTURE,CROSS_THROUGH,NO_REVISIT,NO_CONFIRMATION,NO_TARGET,SUPERSEDED_FIRST_EVENT,PRE_FILL_TRIGGER_CANCELLED,NO_ENTRY_QUOTE,TOO_LATE,OUTSIDE_EVALUATION_WINDOW,WAIT,NO_FILL,FILLED,NOT_EVALUABLE` y valores `int32` no negativos. Los conteos y el array reconstruyen toda terminalidad sin una etiqueta singular de plan.

Todos los eventos se detectan y conservan para cobertura. La prioridad selecciona como máximo una intención por `(ticker,event_session_date)` físico, antes de capital o fill; no existe rescate de otra zona para ese mismo día. Esa selección no impone un máximo por plan: otros anchors y otros días físicos siguen su propia terminalidad. Una confirmación anterior a `2026-01-02T00:00:00` o posterior a `2026-09-17T23:59:59.999999999` escribe `OUTSIDE_EVALUATION_WINDOW` y no abre posición. Una confirmación pre-2026 consume sólo su propio `(plan_id,anchor_id)`; no consume otros anchors ni días posteriores. Un plan puede por ello tener eventos fuera y dentro de ventana, que los dos contadores y el array conservan. Una confirmación válida dentro de ventana puede usar geometría ENTRY_FROZEN de D anterior sólo cuando sigue dentro de su cobertura D/D1/H2. D no abre posición antes del 2 de enero. Ninguna posición se fuerza más allá de su H2 original ni más allá de la fuente B admitida.

Para D solamente se predeclara, antes de outputs, un libro económico continuo por arm y coste desde 2026-01-02 hasta 2026-09-17, sin reset de julio: caja inicial `Decimal("100000")`, cero posiciones y cero reserva/obligación al inicio, con carry H1 a Q3. Esta es una enmienda temporal para comparabilidad con Semanal RAW. `EQUAL_RISK_FROZEN_REPLAY_CONTRACT_20261101.md` mantiene sus dos bloques H1/Q3 independientes; D no afirma que el contrato antiguo ya autorizase el libro continuo. La enmienda no altera ecuaciones, riesgo, costes, arms ni política de selección, y queda `PENDING_INDEPENDENT_DOCUMENTARY_REVIEW`.

## 7. Cobertura y manifest

`coverage.json` es JSON compacto terminado en LF con estas claves exactas:

```text
status,data_scope,plan_rows,plan_coverage_rows,plans_c_missing_geometry,plans_c_invalid_geometry,plans_no_confluent_anchor,plans_with_eligible_anchor,plans_no_confirmed_event,plans_with_only_outside_evaluation_events,plans_with_only_in_evaluation_events,plans_with_mixed_evaluation_events,geometry_state_rows,geometry_level_rows,eligible_revisit_rows,ineligible_nonconfluence_rows,revisit_rows,confirmed_rows,no_visit_rows,no_departure_rows,cross_through_rows,no_revisit_rows,no_confirmation_rows,no_target_rows,superseded_first_event_rows,pre_fill_trigger_cancelled_rows,no_entry_quote_rows,too_late_rows,not_evaluable_rows,common_intent_rows,admitted_intent_rows,wait_rows,event_risk_budget_rows,capital_blocked_rows,open_position_rows,no_fill_rows,filled_rows,missing_exit_rows,ambiguous_rows,a_base_ledger_rows,a_adverse_ledger_rows,b_base_ledger_rows,b_adverse_ledger_rows,c_benchmark_rows,benchmark_policy_status,coverage_complete,event_rules_adopted,benchmark_policy_adopted
```

Los contadores se derivan de tablas y no eliminan ausencia, WAIT, cancelación, pérdida o conflicto. `plan_rows=plan_coverage_rows=1620`; las geometry partitions suman 1.620. Los cuatro contadores de eventos de plan son excluyentes y suman 1.620: sin confirmación, sólo fuera, sólo dentro, o mixto fuera/dentro. `coverage_complete=true` exige que cada plan B, estado C y anchor relevante sea admitido, ineligible o terminado por una razón enumerada. Las banderas de adopción son false hasta el cierre D futuro.

`manifest.json` es JSON compacto terminado en LF con exactamente:

```text
status,schema,contract,implementation,authorities,authority_pins,b_bindings,c_bindings,benchmark_binding,evaluation_policy,input_count,inputs_digest,outputs,counts,coverage,scientific_flags,journal_closure,resource_policy,created_at_utc,no_fit,no_ev_filter,no_parameter_search,data_scope
```

`outputs` tiene cuatro miembros exactos: `plan_coverage.parquet`, `revisit_events.parquet`, `revisit_replay_ledger.parquet` y `coverage.json`, cada uno `{path,bytes,sha256,rows}` con `rows=null` para coverage. El manifest no se autopinea. `inputs_digest` es SHA-256 de la lista canónica ordenada por path de `{path,bytes,sha256,physical_identity}`. `scientific_flags` es exactamente `{entry_frozen:true,session_1030_reset:false,intraday_wall_updated:false,arms:["A_EVENT_ZONE_EXIT","B_IDENTICAL_EVENT_ENTRY_H2","C_ORIGINAL_1035_H2"],fourth_arm:false}`. `evaluation_policy` es exactamente `{event_coverage:"ALL_1620_PLANS",entry_start_local:"2026-01-02T00:00:00",entry_end_local:"2026-09-17T23:59:59.999999999",initial_cash_decimal:"100000",initial_positions:"NONE",carry_h1_to_q3:true,july_reset:false,end_rule:"ORIGINAL_H2_ONLY",temporal_amendment_status:"PENDING_INDEPENDENT_DOCUMENTARY_REVIEW"}`.

`benchmark_binding` es exactamente `{root_manifest_path,root_manifest_sha256,root_manifest_bytes,audit_path,audit_sha256,audit_manifest_path,audit_manifest_sha256,audit_exit_path,audit_exit_sha256,policy_key,block,ledgers,selection_rationale,selection_authority_pin}`. `ledgers` tiene exactamente `BASE` y `ADVERSE`; cada valor es `{path,bytes,sha256}`. La rationale sólo puede citar continuidad cronológica y una autoridad o cierre pre-outcome.

## 8. Benchmark C sellado: Semanal RAW

Root ha fijado provisionalmente C con `policy_key="WEEKLY_RAW"`, cuyo nombre sellado de output es `ledger_weekly_raw_base.jsonl` y `ledger_weekly_raw_adverse.jsonl`. `WEEKLY_RAW` figura como policy key en `ADAPTATION_WALKFORWARD_CONTRACT_20261101.md`; el metadata auditado conserva sus dos basenames lower-case. Se eligió por continuidad cronológica con la referencia weekly cerrada inmediatamente anterior a la comparación DAILY rechazada, no por neto, PF, drawdown, mes, ticker, side ni mayor trade. Es el arm C ya definido, no un cuarto arm.

Los pins sellados son:

| objeto | path sellado | bytes | SHA-256 |
|---|---|---:|---|
| producer manifest | `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_adaptation_01/manifest.json` | 17.599 | `e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23` |
| ledger base | `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_adaptation_01/ledger_weekly_raw_base.jsonl` | 172.114 | `0a57a116abb7eda55bee04a1fc21b95b823951468a35f65758a1d3553383a22d` |
| ledger adverso | `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_adaptation_01/ledger_weekly_raw_adverse.jsonl` | 174.233 | `3029a1e7fdcfd1de435dcfc91210df25fa2a32d437ab77d1dfebb0be6f20fa58` |
| auditor independiente | `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_adaptation_audit_04/audit.json` | 9.646 | `9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a` |
| audit manifest | `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_adaptation_audit_04/manifest.json` | 270 | `770dbddbbfb53c5c2d726f50a1d7e6bb36941dd89e3d4228de53695f7f9a1627` |
| audit exit | `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_adaptation_audit_observer_04/exit.json` | 910 | `5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420` |

El auditor declaró `PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT`. El benchmark mantiene decisión 10:30, entrada 10:35, qty y guard de riesgo congelados, scheduler H2 y dos costes. Su bloque es el libro continuo 2026-01-02 a 2026-09-17, con septiembre parcial. D lo informa sólo como C descriptivo; B frente a C sigue mezclando timing, dirección, elegibilidad y exposición.

El borrador D original no nombra `FROZEN_CONTEXT182`, `EV_TOP1_H2`, una policy CALL/PUT, ni el root `h2_equal_risk_frozen_01` como baseline obligatorio. Sólo exige un benchmark original 10:35/H2, policy sellada y pin byte-exacto. Por tanto la elección Semanal RAW no altera una regla científica material ni los tres arms. La futura admisión debe rehashear los seis objetos anteriores; hasta entonces el binding operativo sigue pendiente y D no ejecuta C.

## 9. Fixtures futuras y auditoría independiente

Una suite futura, sólo sintética, debe cubrir: target primero ABOVE; stop BELOW con bid missing y crédito negativo de comisión; GAP_CROSSING que registra no-toque y conserva estado; rearm sólo después de un CROSS_THROUGH posterior; dos anchors que confirman y resuelven por prioridad; confirmación sin target que conserva event ID; trigger antes de ask que cancela pre-fill; minuto missing u overnight que rompe confirmación; empate stop/target; fronteras `ceil`, `qty=1` y `qty=0`; trap Inexact y serialización sin redondeo; accounting exit observado y missing H2; mutación posterior a `label_available_at`; plan C missing y plan sin confluencia; un plan con confirmación fuera y otra dentro; tres días físicos ganadores del mismo plan sin cap plan-level; y binding C con root válido pero policy nula que rechaza antes de output.

El auditor no importa productor. Re-admite B/C, reconstruye las 1.620 filas plan coverage y cada transición de events, incluidos gap, cross y rearm. Recalcula IDs y sus `*_local_ns`, prioridad por día físico sin cap por plan, targets, clocks, ventana de evaluación, admisión común A/B, qty, ecuaciones Decimal, caja, reserva, obligación de comisión, equity realizada, bid cero, accounting exit, outcomes y madurez. Ejerce el contexto Decimal de precisión 1000 con trap Inexact y rechaza cualquier serialización que redondee. Verifica tipos, orden, nulabilidad, rechazo de columnas extra, hashes, digest, journal y ecuaciones de coverage. Debe comprobar que C coincide byte a byte con `benchmark_binding` y que C no interviene en admitir A/B. También debe revisar documentalmente la enmienda temporal continua D frente a los bloques independientes del contrato de riesgo. Drift de pin, schema, orden, ID, clock o conteo falla toda la corrida.

La ejecución requiere contrato operativo revisado, publicación byte-exacta, implementación y fixtures revisadas, binding runtime y gate contemporáneo de RAM, free commit y disco de al menos 2 GB. Hasta entonces este documento no es GO, no crea raíz y no produce resultado económico.
