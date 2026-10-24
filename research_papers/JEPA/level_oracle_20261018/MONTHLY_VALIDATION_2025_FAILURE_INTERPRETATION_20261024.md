# Qué demuestra el fallo mensual de 2025

24 de octubre de 2026. Análisis descriptivo del resultado ya auditado, con
`selected_mode=null`, `SEEN_DEVELOPMENT` y promoción no autorizada. Los tres
modos pierden en los tres tickers y ninguno cumple el requisito de al menos un
fill en cada ticker-día. La actualización mensual predeclarada no produjo una
mejora conjunta frente al control estático en este calendario. Esto no identifica
la causa del error ni demuestra que cualquier actualización futura deba fallar.

La autoridad es el [resultado de auditoría de 2025](MONTHLY_VALIDATION_2025_AUDIT_RESULT_20261024.md),
condicionado a scores sellados. El reporter terminó `COMPLETE`, con salida real
0 y audit SHA `ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc`.
No se ha abierto economía de 2026 para esta nota, ni repetido inferencia, ajuste,
scheduler, selección o reconstrucción de quotes.

## Actividad, pérdidas y costes

Los tres modos evalúan exactamente los mismos 750 ticker-días disponibles
(250 por ticker), sin ausencias en 2025. `ALL` suma USD nominales y operaciones;
no es una cartera con capital o riesgo igualado entre tickers ni un gate nuevo.
PF corresponde al ledger anual agregado, no al promedio de los PF mensuales.
Las cifras monetarias se redondean a dos decimales; el anexo conserva precisión.

| Modo | Trades | Neto base USD | Neto adverso USD | PF base | Neto base/trade USD | Días sin fill/750 | NO_FILL/intentos |
|---|---:|---:|---:|---:|---:|---:|---:|
| static | 2.994 | −49.152,40 | −55.127,40 | 0,8745 | −16,42 | 72 (9,6%) | 2/2.996 (0,0668%) |
| expanding | 3.043 | −75.243,80 | −81.319,80 | 0,8252 | −24,73 | 99 (13,2%) | 1/3.044 (0,0329%) |
| rolling12 | 3.529 | −122.081,40 | −129.124,40 | 0,7297 | −34,59 | 45 (6,0%) | 0/3.529 (0%) |

Hay actividad sustancial; el resultado no se explica como una política que casi
nunca opera. `rolling12` realiza más trades y deja menos días sin fill, pero
pierde más en total y por trade. `expanding` también pierde más por trade que
`static`. Son comparaciones descriptivas: las operaciones y trayectorias elegidas
no son idénticas. El mayor porcentaje de acierto agregado de `expanding`
(28,03%, frente a 25,65% de `static` y 23,80% de `rolling12`) tampoco acredita
mejor economía. No se añade un umbral de acierto.

Un día disponible sin fill no significa un intento de ejecución fallido. Puede
no haber oferta con score positivo; el scheduler sólo intenta el máximo positivo
y avanza un minuto tras NO_FILL. Los intentos NO_FILL observados son dos en
`static` y uno en `expanding`, todos en SPY, frente a 72 y 99 días sin fill.
En `rolling12` no hay ningún NO_FILL y sí 45 días sin fill. No hay evidencia
aquí de que los rechazos de ejecución expliquen la mayor parte de la falta de
actividad diaria. Esta distinción procede de las columnas auditadas, no de una
clasificación nueva de precios o de una imputación de ceros.

El contrato usa ask→bid, multiplicador 100, comisión de 1,30 USD por lado y
slippage de 0,01 base / 0,02 adverso por lado, con suelo cero en el bid de salida
tras slippage. Los netos ya incluyen esos costes. El escenario adverso resta
otros 5.975,00 / 6.076,00 / 7.043,00 USD respectivamente sobre las mismas
operaciones. Las pérdidas existen ya en base; esta comparación no calcula un
resultado sin costes ni permite atribuir toda la pérdida al spread, comisión o
slippage. No se ha alterado el escenario ni simulado otro fill.

| Modo | Ticker | Trades | Neto base USD | Neto adverso USD | PF base | Días sin fill/250 | Meses positivos/12 |
|---|---|---:|---:|---:|---:|---:|---:|
| static | SPXW | 1.291 | −27.401,60 | −29.981,60 | 0,9171 | 2 (0,8%) | 4 |
| static | SPY | 856 | −10.084,60 | −11.793,60 | 0,6493 | 37 (14,8%) | 1 |
| static | QQQ | 847 | −11.666,20 | −13.352,20 | 0,6390 | 33 (13,2%) | 3 |
| expanding | SPXW | 1.361 | −53.452,60 | −56.171,60 | 0,8540 | 10 (4,0%) | 1 |
| expanding | SPY | 724 | −8.652,40 | −10.097,40 | 0,6823 | 59 (23,6%) | 2 |
| expanding | QQQ | 958 | −13.138,80 | −15.050,80 | 0,6467 | 30 (12,0%) | 2 |
| rolling12 | SPXW | 1.465 | −93.080,00 | −96.006,00 | 0,7548 | 3 (1,2%) | 1 |
| rolling12 | SPY | 1.027 | −15.080,20 | −17.130,20 | 0,5577 | 26 (10,4%) | 1 |
| rolling12 | QQQ | 1.037 | −13.921,20 | −15.988,20 | 0,6333 | 16 (6,4%) | 1 |

SPXW aporta el 55,75% / 71,04% / 76,24% de la pérdida anual nominal de cada
modo. Sin embargo, los otros dos tickers también pierden; la agregación no
esconde un ticker anual rentable. El menor daño nominal de `expanding` en SPY
coincide con menos operaciones y más días sin fill; no autoriza elegir esa
combinación. Los porcentajes de contribución no miden riesgo equivalente ni
información predictiva: los contratos tienen escalas monetarias diferentes.

## Distribución temporal y concentración

Todos los meses se muestran, sin descartar meses desfavorables. El
[anexo reproducible](continuation_20261024/monthly_validation_2025_interpretation/descriptive_reconciliation.json)
contiene las 144 combinaciones de modo × grupo (tres tickers y ALL) × mes,
con netos base/adversos, trades y días sin fill.

| Mes de 2025 | static, neto base USD | expanding, neto base USD | rolling12, neto base USD |
|---|---:|---:|---:|
| Enero | −8.854,00 | −8.854,00 | −14.698,60 |
| Febrero | −14.044,20 | −4.473,00 | −11.808,40 |
| Marzo | 4.358,60 | −6.638,80 | −15.328,00 |
| Abril | 427,80 | −9.749,20 | −24.705,00 |
| Mayo | −4.764,00 | −13.420,20 | −17.645,20 |
| Junio | −6.007,00 | −12.089,20 | −14.676,80 |
| Julio | 4.295,80 | −4.609,00 | −1.228,80 |
| Agosto | −4.960,20 | −6.199,20 | −12.289,00 |
| Septiembre | −8.191,80 | −4.016,40 | −14.331,40 |
| Octubre | −4.863,40 | 5.976,60 | −1.643,20 |
| Noviembre | 4.386,20 | −131,80 | 10.209,40 |
| Diciembre | −10.936,20 | −11.039,60 | −3.936,40 |

La concentración siguiente usa **netos mensuales**: suma las magnitudes de los
meses negativos y los netos de los meses positivos. No son pérdidas y ganancias
brutas por trade y no deben usarse para reconstruir el PF. La cuota de los tres
meses más negativos se calcula igual para todos los grupos, sólo para describir
la concentración; no elimina esos meses ni produce una política alternativa.

| Modo, ALL | Meses positivos/negativos | Suma meses positivos USD | Magnitud meses negativos USD | Cuota de los tres meses más negativos |
|---|---:|---:|---:|---:|
| static | 4 / 8 | 13.468,40 | 62.620,80 | 54,03% |
| expanding | 1 / 11 | 5.976,60 | 81.220,40 | 45,00% |
| rolling12 | 1 / 11 | 10.209,40 | 132.290,80 | 43,60% |

La pérdida se distribuye por varios meses, no sólo por una observación mensual
extrema. Los meses positivos de `static` son marzo, abril, julio y noviembre;
marzo, julio y noviembre concentran el 96,82% de esa suma positiva. Para
`expanding` la ganancia mensual positiva agregada está toda en octubre; para
`rolling12`, en noviembre. Por ticker, ningún grupo tiene más de cuatro meses
positivos. El anexo conserva máximos, mínimos y concentración de los doce
grupos, incluidos todos sus meses. No se ha estudiado concentración por trade
individual ni hecho inferencia estadística con doce observaciones mensuales.

## Qué explicaciones siguen siendo hipótesis

**Población y actualización.** No hay cambio de calendario evaluado entre modos.
Sí cambia el conjunto de entrenamiento por diseño: `static` usa 2023–2024,
`expanding` incorpora meses cerrados desde 2023 y `rolling12` desplaza doce meses.
Además, cada refit recalcula la escala por ticker desde el premium de su muestra
TRAIN; no es una comparación de pesos nuevos manteniendo escala constante.
El [plan predeclarado](MONTHLY_WALK_FORWARD_PLAN.md) fija esto, así como la
reutilización exacta del fit de enero por `static` y `expanding`, coherente con
su resultado idéntico en enero. La diferencia posterior no identifica por sí
sola un efecto causal de tamaño de muestra, recencia o calibración.

**Error de estimación y objetivo.** El código de
[entrenamiento](train_causal_rollout.py) configura regresión por oferta;
el [runner mensual](run_monthly_walk_forward.py) ajusta neto/escala con muestreo
de hasta 128 ofertas por día e IPW, y evalúa todas las ofertas causales. Puntuar
el máximo y bloquear hasta exit+1 induce una trayectoria distinta de la
distribución de filas del ajuste. IPW conserva el objetivo de muestreo declarado;
no garantiza precisión en máximos seleccionados ni maximiza directamente el
neto de sesión. El estado de haber operado se contabiliza, pero no es una feature
del modelo. Son propiedades verificables del diseño; sobreestimación del máximo,
error de ranking o desajuste de objetivo son explicaciones posibles, no causas
medidas por estas tablas. No se calcularon residuos ni calibración de scores.

**Deriva temporal.** Meses con resultados distintos y reglas de actualización
que no mejoran conjuntamente son compatibles con deriva, pero también con
error de estimación, cambios de muestra, escala o decisiones seleccionadas.
No se ha medido aquí la estabilidad de la distribución condicional ni aislado
esos mecanismos. Un refit mensual fallido no demuestra ausencia de señal ni
prueba que un actor por sesión la recuperaría.

**Datos y alcance de la auditoría.** El PASS verifica el replay económico dado
scores y labels sellados, bajo los relojes, demora de un minuto, bid/ask y costes
contractuales. No sustituye una auditoría nueva de refit, una medición de latencia
real, de capacidad de ejecución o de paridad live. Las cifras no representan
recepción observada ni trading prospectivo. La nota tampoco extiende el PASS a
2026. Conserva el freeze nulo: no elige un ticker, mes, umbral o inversión para
rescatar estos resultados, ni activa otra familia.

## Evidencia de esta lectura

El [script descriptivo](describe_monthly_validation_2025_failure.py), SHA
`6d2cc347c54608bb3857278c26ab33b581800f0657e00b63710da7160811f111`,
se ejecutó una vez con salida 0. Ruff pasó. No importa productores, auditores,
modelos o librerías de mercado. Verifica los pins externos del manifest COMPLETE
(`66108b5eb4e678569dcc82a46ebaa92f569a3601e160a2ab1ac781725313db0f`)
y exit (`4f4987abc7ca1c4a10d08bbba3af6dcbec92fc5033411049bc33d441930852ef`),
y los hashes/tamaños de cuatro outputs consumidos: summary, periods, monthly y
daily. Reconcilia netos/trades/intentos entre días, meses y año; comprueba claves
exactas, ausencia de duplicados diarios y calendario común. Rehashea los seis
archivos consumidos al terminar.

Resultado: `PASS_DESCRIPTIVE_RECONCILIATION_2025_ONLY`, anexo SHA
`dccdb3fcf17be44cf9e70b9896b12b2fd925b305218a478e59ebdeade37006a5`.
Este PASS es sólo de aritmética y consistencia documental. El anexo guarda todas
las rutas locales y hashes consumidos; no se leyeron matrices, modelos, raw,
scores, ledger Parquet ni outcomes de 2026. Los archivos fuente permanecen
intactos y no se ha repetido su auditoría masiva.
