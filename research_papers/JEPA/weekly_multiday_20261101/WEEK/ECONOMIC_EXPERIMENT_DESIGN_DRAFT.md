# WEEKLY/MULTIDAY — borrador mínimo de experimento económico causal

Estado: `DRAFT_NOT_EXECUTABLE_NOT_AUTHORIZED`. Todas las decisiones de este
documento son **propuestas para revisión**, no resultados, selección, GO ni
autorización para leer outcomes. El piloto de fuente debe cerrar primero. Todo el
periodo disponible es `SEEN_DEVELOPMENT`; no se llamará holdout a ninguna parte.

## 1. Pregunta y límites

Pregunta única propuesta: ¿una política causal que puede elegir `CALL`, `PUT` o
`WAIT`, manteniendo una opción semanal durante una, dos o tres sesiones oficiales,
produce valor esperado y PnL neto robustos después de costes?

- Universo: `SPY`, `QQQ`, `SPXW`; compras de una opción, nunca posiciones cortas.
- Fuente: sólo archivos locales admitidos bajo `D:/ThetaData`; sin API, bróker,
  producción o VPS.
- No se modifica ni repite el oracle histórico. Su
  `CLOSED_ORACLE_GATE/advance=false` permanece como historia y no selecciona
  lado, horizonte, clock, modelo o umbral de esta prueba.
- No se busca una arquitectura. Se propone una sola familia probabilística, un
  replay secuencial y controles fijos.
- `WAIT` está permitido todos los días y no existe mínimo diario de operaciones.
  Una fuente ausente es `NO_EVALUABLE`, no `WAIT` ni retorno cero.

## 2. Gate de fuente antes de economía

El `SOURCE_PILOT_CONTRACT.md` sólo puede acreditar continuidad observable del
mismo `(ticker, expiration, strike, right)`, clocks y validez de quotes; no
rentabilidad. Para abrir este experimento debe cerrar sin diferencias y mostrar
soporte suficiente por ticker para contratos y quotes exactas a través de las
sesiones. Un archivo ausente nunca desplaza el horizonte hacia el siguiente
archivo disponible.

El piloto cuenta `10:35`, pero el fill causal propuesto requiere `10:36`. El
preflight económico deberá comprobar focalmente, dentro de los mismos archivos y
sin crear otra capa de datos, cobertura exacta de cada minuto que realmente use
el replay: decisión, fill `+1`, triggers y liquidación. Si el intervalo almacenado
no permite ese desfase, la propuesta debe volver a revisión; no se redondea el
clock ni se infiere una quote.

## 3. Calendario, contrato y ofertas causales

### 3.1 Identidad y elegibilidad propuestas

La identidad persistente es `(ticker, expiration, strike, right)`. No hay
rollover, nearest-strike futuro ni sustitución `SPX`/`SPXW`. La sesión y su cierre
proceden del calendario oficial ya sellado, no de la presencia de archivos.

En cada sesión evaluable, a las `10:35 America/New_York`, se admiten contratos con
`1..8` DTE naturales conocidos entonces. Para cada `right` se propone escoger uno
causalmente:

1. quote de decisión finita, `bid >= 0`, `ask > 0`, `bid <= ask`;
2. signo de delta correcto y mínimo `abs(abs(delta)-0.50)`;
3. empate por menor spread relativo y luego strike ascendente.

Por cada contrato seleccionado se generan tres ofertas de horizonte fijo
`H in {1,2,3}` sesiones oficiales. Una oferta existe sólo si su sesión de salida
programada es **estrictamente anterior** a la fecha de expiración y todas las
identidades de calendario son conocidas al decidir. Esto evita settlement,
ejercicio automático y selección retrospectiva por supervivencia. El experimento
no afirma que el riesgo de ejercicio temprano de ETF sea nulo; deberá reportarse
como limitación aunque sólo se compren opciones.

### 3.2 Entrada y clock fallback propuestos

La selección usa exclusivamente el snapshot `10:35`. La entrada intenta comprar
el mismo contrato al ask exacto de `10:36`. Propuesta de fallback, sujeta a que el
piloto/preflight acredite la granularidad: primera quote válida entre
`10:36..10:40`, sin cambiar contrato ni recalcular delta. Se persisten
`decision_at`, `attempted_fill_at`, `actual_fill_at`, retraso y base de reloj
(`NATIVE_STORED_TIMESTAMP` o `UNDERLYING_TIMESTAMP_PROXY`). Si ninguna existe, el
resultado es `NO_FILL`, neto cero y capital no comprometido. No hay nearest,
backfill ni forward-fill.

El proxy de subyacente es una convención de investigación, no una afirmación de
quote clock o recepción live. Un timestamp nativo presente pero inválido nunca
cae al proxy.

## 4. Geometría, salida y labels

Se reutiliza únicamente la geometría causal de `level_engine.py`: IB completo y
niveles Fibonacci/walls conocidos a las 10:35. `target_center`, `stop_center` y
`band` quedan congelados al entrar; no se recalculan con niveles de días futuros.
Si no existen target y stop causales válidos, no hay oferta.

Tras el fill se examina el subyacente en minutos admitidos de las sesiones
oficiales hasta la salida programada. El primer snapshot que cruza target o stop
crea el trigger; si ambos aparecen cruzados en el mismo primer snapshot —incluido
un gap de apertura— prevalece `STOP`. El precio del nivel nunca se usa como fill.
La liquidación intenta el bid del mismo contrato un minuto después del trigger,
con la misma escalera transparente de hasta cinco minutos.

Si falta quote de salida, la fila y la pérdida potencial permanecen. Se busca la
primera quote válida posterior del mismo contrato sólo hasta el clock de salida
programado. Si no existe, `missing_exit=true` y se propone `exit_bid=0` como
liquidación conservadora; nunca se elimina la operación ni se cambia de strike o
vencimiento. Si no hubo trigger, se liquida en la sesión `H` con decisión a
`10:35` y bid causal `10:36..10:40`.

Los cuatro escenarios excluyentes propuestos son
`NO_FILL/TARGET/STOP/TIME_EXIT`. `TIME_EXIT` es el análogo multiday del antiguo
`EOD`, pero se renombra para no afirmar cierre diario. Cada label incluye
`label_available_at=actual_exit_at` (o el final de la búsqueda fallida), netos
base/adverso y capital comprometido. Ningún label puede entrar en `X`.

## 5. Costes, capital y scheduler

Se propone conservar, para comparabilidad, la fórmula larga existente:

`net_usd = (max(exit_bid - slip, 0) - entry_ask - slip) * 100 - 2.60`.

`base` usa `slip=0.01` y `adverse` `slip=0.02` por opción. Son propuestas heredadas,
no costes weekly validados; comisión, multiplier y moneda deberán verificarse por
producto antes del GO. Al salir antes de expiración no se imputan settlement o
ejercicio como fills ficticios.

- Una opción por operación.
- Máximo una posición abierta por ticker; máximo tres en cartera.
- Capital reservado por posición: `entry_ask*100 + coste de entrada`; no se
  reutiliza hasta `label_available_at`.
- En cada clock, primero se procesan salidas y después entradas.
- Entre ofertas compatibles, la política elige una por ticker; WAIT gana empates.
- Se reportan PnL y drawdown sobre un ledger cronológico ejecutable, además de
  retorno sobre prima reservada. No se suman trades incompatibles.

## 6. Modelo de escenarios y decisión EV

Una sola familia propuesta, con dependencias locales ya presentes:

1. clasificador multinomial regularizado para
   `P(NO_FILL/TARGET/STOP/TIME_EXIT | X,a)`;
2. una regresión regularizada por escenario y coste para
   `E[net_usd_c | escenario,X,a]`, ajustada sólo donde ese escenario se observa
   en TRAIN;
3. calibración escalar de probabilidades en CAL, congelada antes de EVAL.

No se fija todavía implementación si una clase carece de soporte; eso es un
resultado de admisión que debe causar `NO_EVALUABLE_MODEL`, no smoothing secreto.
Para coste `c`:

`EV_c(X,a)=sum_s P(s|X,a)*E[net_usd_c|s,X,a]`.

La política propuesta puntúa exhaustivamente las seis ofertas causales
`CALL/PUT x H1/H2/H3`, escoge la de mayor `EV_adverse` sólo si es estrictamente
positiva y cabe en capital/no-overlap; de lo contrario elige `WAIT`. No se ajusta
un umbral con EVAL. `EV_base` se informa, pero no gobierna la entrada.

`X` se limita a información conocida a las 10:35: ticker, calendario, DTE,
right/horizonte, quote y spread de decisión, delta/IV/theta/vega admitidas,
underlying, IB y distancias/máscaras a niveles congelados. Se excluyen quotes
posteriores, duración realizada, reason, exit, PnL y agregados del día posteriores
al clock.

## 7. Splits y disponibilidad de labels

Propuesta simple acorde con la cobertura ya censada:

- TRAIN: 2023-01-03..2024-12-31.
- CAL: 2025-01-01..2025-12-31.
- EVAL: 2026-01-01..2026-06-30.

Los tres son `SEEN_DEVELOPMENT`. Una fila pertenece a TRAIN/CAL sólo si
`label_available_at` es estrictamente anterior al inicio del bloque siguiente.
Se purgan entradas cuyo horizonte pueda cruzar el corte y se aplica un embargo de
tres sesiones oficiales después del último label del bloque anterior. Features,
normalización, selección de columnas, modelos de retorno y calibrador se ajustan
sólo en su bloque permitido. EVAL se reproduce una sola vez con bytes congelados;
no retroalimenta ninguna decisión.

## 8. Controles y métricas predeclaradas

Controles no seleccionables por resultados:

- `ALWAYS_CALL_H1/H2/H3`: misma selección causal de contrato y scheduler.
- `ALWAYS_PUT_H1/H2/H3`.
- `ALWAYS_ABSTAIN`: ledger cero, sin convertir gaps en WAIT.

Ningún control elige side u horizonte usando el futuro. El oracle histórico se
presenta aparte y nunca como benchmark desplegable.

Probabilidad/calibración: soporte por escenario, log loss, Brier multiclase,
reliability/ECE y diferencia predicted-versus-observed, totales y por
ticker/right/horizonte. EV: bins de EV predicho frente a neto realizado por coste,
MAE/sesgo y cobertura de intervalos si se predeclaran después.

Economía secuencial: trades y abstention rate, net USD base/adverse, PF,
max drawdown USD y duración, meses positivos, peor mes, capital máximo/reservado,
retorno sobre prima, exposición overnight, duración, `NO_FILL`, `missing_exit`,
gaps de trigger y fallback-clock usage. Todo se informa pooled y por ticker,
side, horizonte, mes y escenario, sin rescatar subgrupos.

## 9. Reutilización mínima y piezas nuevas

Reutilizable por referencia, no copiando una plataforma:

- calendario full/short y semántica `WAIT` de `session_clock.py`;
- IB, niveles causales, geometría target/stop y prioridad conservadora de
  `level_engine.py`/`session_level_engine.py`;
- validación de identidad/reloj/quote y hashes del source pilot;
- joins fail-closed, splits mensuales, métricas PF/drawdown y patrón de auditoría
  independiente ya locales.

Necesario y nuevo: un ensamblador de trayectorias por identidad contractual, un
replay que atraviese sesiones, labels `TIME_EXIT`, scheduler de capital multiday y
el modelo/calibrador de escenarios. No se reutilizan `contract_i`, tau hasta EOD,
EOD intradía, ni el emparejamiento `ordered[index+2]` del oracle histórico.

## 10. Dudas que bloquean un contrato ejecutable

1. ¿El piloto acredita suficiente continuidad y quotes exactas, especialmente
   `10:36..10:40`, para los tres tickers y horizontes?
2. ¿`timestamp` y el proxy permiten ordenar todos los minutos sin ambigüedad ni
   staleness no medida?
3. ¿Existen underlying/IB y niveles causales sincronizados para cada sesión de
   trigger, incluidas sesiones cortas y gaps?
4. ¿Multiplier, comisión y slippage heredados son correctos por producto weekly?
5. ¿La muestra soporta las cuatro clases por ticker/right/horizonte en TRAIN y
   CAL sin fusionar clases o elegir subgrupos después de ver EVAL?
6. ¿Debe el preflight excluir fechas ex-dividend ETF o sólo declarar el riesgo de
   ejercicio temprano? No se decidirá sin evidencia local y contrato revisado.

Sólo tras resolver estas dudas, cerrar el piloto y revisar este diseño tendría
sentido preparar código económico. Este borrador no crea outcomes ni acredita
rentabilidad weekly.
