# D — Borrador de replay mecánico de revisita y salidas por zonas

Estado: `NON_EXECUTABLE_DRAFT_PENDING_B_C_AND_REVIEW`  
Fecha: 2026-11-02

## 1. Propósito y límites

Este documento predeclara el diseño del primer experimento D: un replay
mecánico, sin fit, calibración, filtro EV, optimización ni selección mensual,
para comprobar si una revisita causal a una confluencia Fibonacci+wall contiene
información económica en opciones weekly. Un resultado futuro sería
`SEEN_DEVELOPMENT` y no autorizaría promoción.

Este borrador no autoriza abrir datos, producir eventos, implementar código,
ejecutar PnL ni adoptar outputs. Una ejecución requeriría antes el cierre
productor y auditor de B y C, sustitución de todos los bindings pendientes,
review byte-exacto y publicación remota verificada. El diseño puede prepararse
documentalmente mientras esas evidencias están pendientes, pero ninguna raíz
parcial o resultado no auditado las sustituye.

Un replay RAW perdedor no demuestra por sí solo que el valor esperado
condicional sea inexistente. Una etapa EV posterior podría estudiar
heterogeneidad causal y WAIT aunque RAW pierda, siempre mediante contrato nuevo,
sin seleccionar retrospectivamente thresholds, meses, tickers o lados. Del
mismo modo, RAW ganador no basta para acreditar EV calibrado ni promoción.

## 2. Autoridades congeladas y bindings pendientes

- Dirección:
  `WEEKLY_MULTIDAY_ZONE_REVISIT_RESEARCH_DIRECTION_20261102.md`, 16.596 B,
  SHA-256 `6850f559c25d5d6d3352109e0bc7b33d0d48aa14e0d097fa7cfdbe8c9ac1f011`.
- B: `WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md`, 36.466 B,
  SHA-256 `e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9`.
- Enmienda calendario B:
  `WEEKLY_ZONE_EVENT_VALUE_PATH_V2_CALENDAR_AMENDMENT_20261102.md`, 15.276 B,
  SHA-256 `65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146`.
- C científico: `C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md`, 14.617 B,
  SHA-256 `c28572543c1658ab87b1083d60bfdfbdc059c57960c5240c54f98bef5cdd8027`.
- Borrador operativo C: `C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102.md`,
  20.544 B, SHA-256
  `88f76551957e73e37c5dd816b00ec17d035132186df5071be10a5c534368cb3f`;
  no es autoridad ejecutable hasta cierre, review y publicación.
- H2: `ECONOMIC_H2_CONTRACT.md`, 10.737 B, SHA-256
  `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5`.
- Clocks: `H2_CLOCK_FILTER_V2_AMENDMENT.md`, 2.692 B, SHA-256
  `9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb`.
- Riesgo y costes: `EQUAL_RISK_FROZEN_REPLAY_CONTRACT_20261101.md`, 5.663 B,
  SHA-256 `9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b`.

Permanecen obligatoriamente `PENDING`: bundle y review finales B;
manifest/exit/audit/review finales C; nombres y pines exactos de sus outputs; y
la autoridad byte-exacta del benchmark original del arm C. Este documento no
inventa un pin para ese benchmark.

## 3. Población, identidad y colisiones

La población nominal son exactamente los 1.620 planes `PLANNED` sellados por B,
cada uno con `plan_id`, ticker, `entry_date`, expiry y dos `decision_id` CALL/PUT
seleccionados causalmente a las 10:30. D exige unicidad de `plan_id` y
correspondencia uno-a-uno entre plan y `(ticker, entry_date)`; todo conflicto
falla cerrado.

La única geometría es `ENTRY_FROZEN`: los anchors C formados a las 10:30 de D
conservan el mismo `anchor_id`, centro y band durante D, D1 y H2. No se usa
`SESSION_1030_RESET` ni actualización intradía.

Un día físico puede ser D de un plan y D1/H2 de planes anteriores. Cada
candidatura conserva `(plan_id, anchor_id)`, pero se admite como máximo una
intención por `(ticker, event_session_date)`. Entre todos los planes activos
cuyo intervalo ENTRY_FROZEN incluye esa sesión gana la primera confirmación por
orden exacto `(confirmation_time, cluster_ordinal, anchor_id)`. Las demás quedan
`SUPERSEDED_FIRST_EVENT`; no se rescata otra zona aunque la primera termine en
`NO_TARGET`, cancelación, falta de quote o bloqueo económico.

Cada `(plan_id, anchor_id)` puede emitir como máximo una
`CONFIRMATION_CANDIDATE` durante todo D/D1/H2. La primera confirmación es
terminal para el par, incluso si después falla, queda superseded, no tiene
target, se cancela o no se llena. El único rearm permitido ocurre antes de esa
confirmación, después de `CROSS_THROUGH`, y comienza en la muestra siguiente.

## 4. Zona elegible y máquina causal

Una zona es elegible sólo si su geometría C válida contiene al menos un
componente semántico `kind=FIB` y al menos uno `kind=WALL`. No se infiere
confluencia de nombres ni de PnL. Sea centro `z` y banda positiva `b`.

Los spot son sólo muestras observadas de B, ordenadas por minuto RTH válido. No
se interpola, no se usan OHLC intraminuto y “primero” significa siempre
`first_observed`.

Estados por `(plan_id, anchor_id)`:

1. `ARMED_ABOVE` si la primera muestra elegible cumple `spot > z+2b`;
   `ARMED_BELOW` si cumple `spot < z-2b`. La franja intermedia no arma.
2. `VISIT` es la primera muestra posterior con `abs(spot-z) <= b`.
3. `DEPARTURE` es la primera muestra posterior fuera de la banda exterior. Es
   válida sólo si vuelve al lado de aproximación: ABOVE exige `spot > z+2b` y
   BELOW exige `spot < z-2b`.
4. Si esa primera salida exterior es por el lado opuesto, se registra
   `CROSS_THROUGH`, se invalida la secuencia y sólo puede rearmarse desde la
   muestra siguiente. La muestra de cruce no satisface dos estados.
5. `REVISIT` es la primera muestra posterior con `abs(spot-z) <= b` tras una
   departure válida.
6. `CONFIRMATION` exige, después de REVISIT, dos minutos RTH válidos físicamente
   consecutivos fuera de `2b` por el lado guardado de departure. Missing minute,
   overnight o cambio de sesión rompe la racha; el estado puede persistir entre
   sesiones, pero no se inventa movimiento durante el cierre.
7. Después de REVISIT y antes de completar la confirmación, cualquier primera
   salida exterior por el lado opuesto es otro `CROSS_THROUGH`: invalida la
   secuencia completa y permite rearmar sólo desde la muestra siguiente. La
   muestra de cruce no puede iniciar el nuevo armado ni confirmar. Esto elimina
   la ambigüedad de un cruce opuesto durante la racha de confirmación.

Un salto ABOVE→BELOW sin muestra dentro es `GAP_CROSSING`, no VISIT. Una muestra
posterior dentro acredita visita sólo en su timestamp. No se afirma toque
continuo ni orden intraminuto.

El lado operativo nace de `departure_side`: ABOVE→CALL y BELOW→PUT. Se usa el
`decision_id` del mismo right y plan congelado a las 10:30; nunca se
reseleccionan strike, expiry o right con información posterior.

## 5. Stop, target y evento seleccionable

En confirmación se congelan:

- ABOVE/CALL: `stop = z-2b`; target = centro del anchor C distinto más cercano,
  de la misma geometría ENTRY_FROZEN, estrictamente mayor que el spot de
  confirmación.
- BELOW/PUT: `stop = z+2b`; target = centro distinto más cercano estrictamente
  menor que el spot de confirmación.

El target no necesita ser confluencia, pero sí anchor C válido y disponible
desde D 10:30. Empates de distancia se resuelven por el menor
`(cluster_ordinal, anchor_id)`. Si no existe target, el evento queda
`NO_TARGET`; no hay trade ni rescate de otra zona. El par `(plan_id, anchor_id)`
permanece terminal.

## 6. Entrada y cancelación pre-fill

`decision_time = confirmation_time`. `entry_quote_time` es la primera
observación del mismo contrato con ask válida y timestamp estrictamente
posterior. No hay nearest, forward-fill, quote del mismo minuto, contrato
sustituto ni reintento.

Si stop o target se observa antes de, o en el mismo timestamp que, esa primera
quote, se registra `PRE_FILL_TRIGGER_CANCELLED` y no hay fill. Esta convención
conservadora evita adjudicar a la posición un movimiento ya observado. La quote
debe ser estrictamente anterior a las 10:35:00 ET de H2. No se extiende expiry
ni horizonte; confirmaciones o quotes en o después del terminal son `TOO_LATE`.

## 7. Cantidad, costes y admisión económica común A/B

Se hereda la economía del contrato de riesgo `9c387e9b…`, no su reloj literal
10:30/10:35 para la entrada. Con `event_entry_ask` causal:

`unit_risk_cents = ceil((Decimal(str(event_entry_ask)) + Decimal('0.02')) * 10000 + 260)`

`qty = 500000 // unit_risk_cents`

Qty se fija una vez antes del fill contable, usando slippage adverso 0,02 y las
dos comisiones de 1,30 USD por contrato/lado. `qty < 1` produce
`EVENT_RISK_BUDGET`. No hay resize, partial fill, retry ni sustitución. Los
libros base/adverso usan slippage 0,01/0,02 y las fórmulas exactas de
débito/crédito de `9c387e9b…`. Una salida sin quote conserva bid 0 y la
operación; nunca se elimina.

Para aislar la salida, A y B tienen entradas, contratos, timestamps, qty y
admisión idénticos. Primero se construye una lista común de intenciones. Una
intención se admite sólo si ambos arms y ambos libros de costes satisfacen
conjuntamente capital y el lockout conservador de B: una posición por ticker
hasta H2 y máximo tres globales; salidas antes de entradas y prioridad
SPY, QQQ, SPXW. Una salida temprana de A no habilita una entrada adicional que B
no pueda tomar. Si cualquiera falla, A y B registran el mismo WAIT. C no
participa en esta admisión matched.

## 8. Tres arms exactos

- `A_EVENT_ZONE_EXIT`: entrada del evento; tras el fill, primer stop/target
  observado estrictamente posterior. Sólo triggers con tiempo `< H2 10:35`
  activan salida de zona. Se usa la primera bid válida del mismo contrato
  estrictamente posterior al trigger y no posterior al terminal; si falta,
  bid 0 y cota conservadora.
- `B_IDENTICAL_EVENT_ENTRY_H2`: misma intención, contrato, fill y qty que A;
  ignora triggers y sale exactamente a la bid H2 10:35. Missing bid = 0. Es el
  control de entry-time emparejado y la única ablación de la salida.
- `C_ORIGINAL_1035_H2`: benchmark original preservado, con decisión 10:30,
  entrada 10:35, qty, guard, scheduler H2 y política ya sellados. No se
  reconstruye ni altera con eventos D. Su fuente y pin byte-exacto permanecen
  `PENDING` y son obligatorios antes de ejecución. B frente a C mezcla timing,
  dirección, elegibilidad y exposición; es un benchmark descriptivo, no un
  efecto causal puro de timing.

No existe cuarto arm ni variante de thresholds.

## 9. Outcomes y banderas ortogonales de cobertura

Para cada intención se conservan todos los estados pre-fill: `NO_VISIT`,
`NO_DEPARTURE`, `CROSS_THROUGH`, `NO_REVISIT`, `NO_CONFIRMATION`, `NO_TARGET`,
`SUPERSEDED_FIRST_EVENT`, `PRE_FILL_TRIGGER_CANCELLED`, `NO_ENTRY_QUOTE`,
`TOO_LATE`, `WAIT`, `NO_FILL` y `NOT_EVALUABLE`.

Para todo fill, `outcome` tiene exactamente una de tres clases mutuamente
excluyentes:

- `TARGET_FIRST_OBSERVED`;
- `STOP_FIRST_OBSERVED`;
- `TIMEOUT_H2`.

En A, target o stop sólo ganan por la primera muestra observada posterior al
fill; si ninguno aparece antes del terminal, el outcome es `TIMEOUT_H2`. B y C
son `TIMEOUT_H2` por diseño. No existe una clase excluyente `MISSING_EXIT`: la
bandera booleana `missing_exit_flag` es ortogonal al outcome y conserva bid 0 y
la exposición cuando falta la quote de salida. Tampoco existe una clase
excluyente `AMBIGUOUS`: `ambiguous_flag` es metadata de cobertura y nunca elimina
la exposición ni cambia denominadores.

Si la misma marca temporal hace observables simultáneamente ambos predicados o
el muestreo no permite ordenar un cruce, se fija la convención conservadora
`STOP_FIRST_OBSERVED` y `ambiguous_flag=true`; no se interpola ni se fuerza el
resultado favorable. Un missing de salida fija `missing_exit_flag=true` sin
sobrescribir el outcome observado. Ambas banderas pueden coexistir.

Ausencias D/D1/H2, spot u option quote permanecen en denominadores de cobertura
y estados; nunca se excluyen por conocer el futuro. Cada label conserva
`event_time`, `fill_time`, `horizon_end` y `label_available_at`; ningún uso
posterior puede entrenar o calibrar antes de `label_available_at`.

## 10. Salida, comparaciones y falsabilidad

El replay futuro informaría, por arm y coste, población completa, transiciones,
intenciones, fills, WAIT, exposición, outcomes y flags, neto, PF, drawdown
realizado, meses, ticker, side, mayor trade, concentración y resultado sin el
mayor ganador. A-vs-B es la comparación primaria de salida con entradas
idénticas. B-vs-C es el benchmark descriptivo conjunto.

No hay selección EV en D: la política RAW toma sólo el primer evento causal por
ticker/día sujeto a gates. No se ajustan parámetros, no se elige mes/ticker/side
y no se exige una operación diaria. Si A no mejora de forma distribuida frente
a B bajo costes adversos, o depende de un trade, mes o ticker, la hipótesis RAW
de salida por zonas queda debilitada. Eso no se convierte en una prohibición de
estudiar EV condicional: cualquier estudio posterior deberá predeclarar por
separado sus features, calibración, incertidumbre y WAIT, y podrá concluir que
no existe valor. Ni un agregado RAW positivo ni una señal condicional autorizan
promoción. El criterio histórico de ocho meses positivos puede reportarse como
diagnóstico, pero no es requisito lógico para abrir una hipótesis EV posterior
y todo este periodo sigue siendo desarrollo visto.

## 11. Condiciones antes de implementación o ejecución

Antes de código ejecutable deben sustituirse por pines reales el bundle/review
final B, los manifest/exit/audit/review finales C y la autoridad exacta del
benchmark C original. Un review independiente debe verificar las 1.620
identidades, solapamientos, máquina causal, terminalidad por anchor, tres arms,
clocks, qty, admisión común A/B, bid 0 por missing y ausencia de selección con
outcomes.

Siguen pendientes sólo los formatos operativos: schema exacto del ledger y
manifest D, procedimiento de fixtures/publicación y auditor independiente. Esos
formatos no pueden cambiar la receta científica ni añadir thresholds. La
evidencia B/C es obligatoria para ejecutar, pero no impide revisar y completar
este diseño documental. No hay retry, adopción parcial, output real ni permiso
de ejecución bajo este borrador.
