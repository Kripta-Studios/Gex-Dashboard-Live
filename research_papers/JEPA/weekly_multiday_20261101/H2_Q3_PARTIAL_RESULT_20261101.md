# Weekly de dos sesiones: continuación de julio a septiembre de 2026

El mismo modelo congelado produce **+6.966,20 USD netos** con costes adversos
entre el 1 de julio y el 17 de septiembre de 2026. Son 28 operaciones, PF 1,5205
y caída máxima realizada de 6.902,40 USD. La reproducción numérica independiente
pasó. El resultado positivo sigue concentrado: todas las operaciones fueron
calls, sólo cinco ganaron y una aportó 16.383,40 USD. Sin esa operación, el neto
sería −9.417,20 USD. Esta sensibilidad no cambia el libro ni selecciona trades.

## Comparación con reglas congeladas

Cada política y coste comienza con un libro nuevo de 100.000 USD. Un contrato
por operación, máximo una posición por ticker y tres simultáneas. No hay carry
de efectivo o posiciones de H1. Salida a las 10:35 de la segunda sesión
oficial posterior, siempre antes del vencimiento; duración natural de 2–5 días.
Se permiten días sin operar. No se reajustan pesos, calibración, medias de
payoff, umbral, tickers ni costes después de observar este periodo.

| Política | Neto base USD | Neto adverso USD | Operaciones | PF adverso | Caída realizada adversa USD |
|---|---:|---:|---:|---:|---:|
| Probabilidades y EV | 7.018,20 | 6.966,20 | 28 | 1,5205 | 6.902,40 |
| Siempre CALL | −5.741,20 | −5.851,20 | 57 | 0,8474 | 18.187,10 |
| Siempre PUT | −9.662,00 | −9.758,00 | 50 | 0,6553 | 18.820,10 |
| Abstenerse | 0 | 0 | 0 | No aplica | 0 |

El retorno EV representa el 6,9662% del capital inicial hipotético, sin
anualizar. La caída valora las posiciones abiertas a coste; **no es una caída
mark-to-market** ni mide toda la exposición overnight. El neto incluye spread
ask→bid, comisión de 1,30 USD por lado y deslizamiento de 0,01 puntos por lado
en base o 0,02 en adverso, con multiplicador 100. Son supuestos de simulación.

| Contribución EV adversa | Neto USD | Operaciones |
|---|---:|---:|
| SPY | −616,60 | 11 |
| QQQ | −1.577,60 | 11 |
| SPXW | 9.160,40 | 6 |

Un contrato no iguala el riesgo monetario de los tres instrumentos. No se
convierte SPXW en una selección retrospectiva. Julio pierde 6.330,60 USD,
agosto gana 15.250 USD y septiembre hasta el día 17 pierde 1.953,20 USD:
un mes positivo de tres. Hubo 38 esperas por EV no positivo, 28 por posición
abierta y 65 eventos sin oportunidad local; estos últimos no son abstención
del modelo. Ninguna entrada elegida tuvo NO_FILL ni bloqueo de capital.
Cuatro salidas sin fuente se conservaron como pérdida total de prima más
costes: son cotas conservadoras, no ventas observadas a precio cero.

H1 había dado +11.486 USD adversos en 75 operaciones, PF 1,2625, tres meses
positivos de seis y caída realizada de 16.666,30 USD. Ambos tramos son positivos
bajo esta simulación. No se suman como si se hubiera ejecutado una sola cartera:
la continuación reinició capital y no constituye un holdout limpio.
[Resultado H1](H2_WEEKLY_RESULT_20261101.md) y
[sensibilidades H1](H2_ROBUSTNESS_RESULT_20261101.md).

## Modelo y datos

Regresión logística multinomial L2 entrenada en 2023–2024, con imputación y
escala de ese entrenamiento. Cinco escenarios: no-fill y cuatro intervalos
de retorno de la prima. La mezcla de probabilidades se fijó en 2025 en 70%
modelo y 30% prior de entrenamiento. El EV combina esas probabilidades con
medias de payoff por escenario, ticker y lado, regularizadas con shrinkage 20.
Sólo se elige la oferta con mayor EV adverso estrictamente positivo; empate
o EV no positivo lleva a WAIT. No hubo ajuste nuevo en H1 ni en esta extensión.

Las 18 variables describen el contrato y el mercado a las 10:30: ticker, lado,
DTE, día semanal, spot, strike, moneyness, bid/ask, spread, delta, IV, gamma,
theta, vega y rho. La selección busca delta absoluta próxima a 0,50, entrada
al ask de las 10:35 y salida fija H2 al bid. Este baseline todavía no utiliza
Fibonacci IB ni walls. Su beneficio realizado proviene de exposición alcista
convexa en pocas operaciones; no demuestra todavía una buena estimación
general de probabilidades o EV en regímenes diferentes.

Se usaron los archivos locales de D:/ThetaData/data_options, distinguiendo
fecha de observación y vencimiento. En SPXW/greeks/2025/04, por ejemplo,
SPXW_20250401_20250401_greeks.parquet corresponde a 0DTE y
SPXW_20250404_20250401_greeks.parquet a tres días al vencimiento. La carpeta
SPXW contiene ambas clases; el nombre de la carpeta no impone 0DTE.

La continuación conserva las 55 sesiones oficiales y 165 filas ticker/sesión.
La última entrada H2 posible es el 15 de septiembre. Hay 90 filas con dos
candidatos, 69 sin serie elegible y seis sin horizonte al final. Los 180
candidatos incluyen 155 salidas observadas, nueve NO_FILL y 16 salidas sin
fuente. Se leyeron 148 archivos presentes con timestamp nativo; ocho fuentes
de salida nominales faltan. No se restringió la muestra a días completos.

Todo el periodo lleva la etiqueta **Q3_PARTIAL_2026_SEEN_DEVELOPMENT**. Julio
ya había aparecido en investigaciones anteriores; el linaje de agosto y
septiembre tampoco acredita un periodo virgen. La aplicación es temporalmente
posterior con parámetros congelados, pero no una prueba OOS limpia.

## Comprobaciones y trazabilidad

Scorer único PID4540, exit0 retenido a 15:02:10.191223 UTC. El auditor independiente
PID45992 terminó exit0 a 15:11:06.188163 UTC. Restaura los parámetros de sklearn
sin llamar a fit y reproduce transform, probabilidades, calibración, EV, ocho
libros y mapa económico completo. Compara los 180 scores y verifica los hashes
de todos sus inputs al ingreso y cierre. El PASS está condicionado al modelo
y dataset sellados; no reproduce el ajuste ni toda la extracción desde raw.
Root comprobó separadamente 360 payoffs/débitos y los 180 horizontes H2.

- Dataset manifest: b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b.
- Scoring manifest: 7bd50a5a1fe5214df2c4281e785313f0fb016ca73d725d682788dcb78b283d8e.
- Audit PASS: ff62f16ea768d8116b48a99de4f5c6431a0c56acda86647044c001ed895302fd.
- Audit manifest: 1b337b375d7ec4cd13099a9b550ad6c13a306c88e9aa31f6a40a60a7dea6b236.

La mayor operación fue una CALL SPXW strike 7575 con vencimiento 7 de agosto.
Entrada el día 3 a las 10:35, ask 34,10; salida el día 5 a las 10:35, bid 198.
Spot almacenado: 7.570,15 → 7.770,05. La comprobación puntual independiente
leyó ambos parquets, con hashes estables antes y después, y reprodujo exactamente
el neto de 16.383,40 USD. PID39828 terminó exit0 a 15:11:21.176614 UTC.
Resultado 04424cf8aeddc02b809ac7b3be3bc1212739c6ae2305d4f4c67530108f2bf70e.
Esto acredita trazabilidad a snapshots guardados, no fills ni recepción live.

Código y bindings se publicaron antes de las ejecuciones. Se preservan los
intentos sintéticos fallidos y los resultados anteriores. Las copias compactas
están en q3_partial_scoring_evidence_01, q3_numeric_audit_evidence_01 y
q3_source_check_evidence_01. No relanzar el dataset, scorer ni auditor cerrados.

## Estado de la investigación

Tenemos dos tramos de backtest positivos con weekly y operaciones de varias
sesiones. Todavía no tenemos rentabilidad robusta acreditada: ambos dependen
de pocas ganancias grandes y de SPXW; la sensibilidad H1 con igual peso por
ticker era negativa. La siguiente hipótesis debe fijar antes de nuevos ajustes
un riesgo comparable entre instrumentos y analizar qué información presente
permite distinguir escenarios, incluyendo IB/walls donde el reloj sea causal.
No procede rescatar retrospectivamente un ticker, mes, duración o umbral.

Goal activo; technical_ready y promotion_approved false. Sólo datos locales,
sin API, cambios en producción, bróker o VPS. Ninguna operación real.
