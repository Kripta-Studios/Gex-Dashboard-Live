# Qué muestra la calibración auditada de 152 frente a 424

23 de octubre de 2026. La ampliación produce cambios pequeños y mixtos en el
error por acción; las decisiones ejecutadas mantienen scores medios positivos
y netos realizados negativos. Esto describe el fallo de esta comparación fija.
No identifica una causa económica ni demuestra que añadir variables empeore
siempre un modelo.

Se utilizan únicamente las tablas de calibración ya auditadas de
[2025](continuation_20261023/common_greek_result/evidence/common_greek_comparison_v1/period2025.json)
y [2026 H1](continuation_20261023/common_greek_result/evidence/common_greek_comparison_v1/period2026.json).
Sus SHA256 son `b69569c62db5072e4bfb11b905b32d738c7f104159a57bb7c573ee38ef143de9`
y `a3ed43d019a692e844e0ea45318c9c8d58c15787e313cc1a881a2f5a17776f80`, ligados al
auditor02 `45caae6c11cdce9306284367e7742d9dbe17e03a8afeb52eff447b3408758a0d`.
No se generaron predicciones, se abrieron labels raw ni se ensayaron reglas.

## Comparar poblaciones equivalentes

`all_offers_action_weighted` cuenta cada oferta con peso uno: 4.592.687 ofertas
en 2025 y 2.406.690 en H1, idénticas para las dos políticas. No son operaciones
ejecutadas ni observaciones independientes; las alternativas incompatibles y
solapadas tampoco forman una cartera ejecutable. `all_offers_equal_day_state` usa
esas mismas ofertas, repartiendo peso igual entre estados con ofertas de cada
ticker-día y entre sus acciones; el peso total es 750 y 363, respectivamente.
Las seis ausencias H1 no entran como outcomes cero y permanecen NO_EVALUABLE.

La tabla agrega los nueve bins fijos de `policies.<policy>.ALL.calibration`.
Las cifras son USD netos base por contrato; residual significa **realizado menos
predicho**. ALL mezcla escalas monetarias de QQQ/SPXW/SPY, sin normalizar riesgo.
SPXW aporta entre el 97,54% y el 97,85% de la suma ponderada de errores cuadrados
por acción en estas cuatro combinaciones de modelo y periodo. Por tanto, el
agregado no representa una mejora o deterioro de igual magnitud relativa en
los tres tickers.

| Periodo / población | RMSE 152 | RMSE 424 | Residual medio 152 | Residual medio 424 |
|---|---:|---:|---:|---:|
| 2025 / por acción | 508,59 | 507,58 | -24,83 | -21,92 |
| 2025 / igual día-estado | 500,53 | 498,14 | -23,70 | -19,72 |
| 2026 H1 / por acción | 532,81 | 539,72 | -34,62 | -38,25 |
| 2026 H1 / igual día-estado | 514,79 | 520,54 | -30,30 | -32,17 |

La mejora descriptiva de 2025 no persiste en el agregado H1. Tampoco es uniforme
entre tickers: en H1 el RMSE por acción QQQ pasa de 114,34 a 114,19 USD y SPY de
91,42 a 91,25; SPXW pasa de 883,55 a 895,32. Estos contrastes conservan todo el
universo fijado; no seleccionan un ticker ni establecen significación estadística.

El [diagnóstico TRAIN](COMMON_GREEK_TRAIN_FIT_RESULT.md) había mostrado MSE IPW
normalizado 0,476395509 → 0,472848644, una reducción aproximada del 0,745% dentro
de la muestra. Sus unidades net/risk y pesos TRAIN difieren de los USD y pesos
anteriores: no cabe comparar directamente sus magnitudes ni tratar ese descenso
como validación temporal.

## Predicción por acción y política ejecutada

`selected_fills` compara el score con el neto base de los fills realmente
seleccionados. Cada fila tiene peso uno. Los modelos eligen poblaciones distintas;
comparar sus errores aquí no aísla la calidad del predictor sobre las mismas
acciones.

| Periodo / política | Fills | Score medio USD | Neto realizado medio USD | MAE USD | RMSE USD |
|---|---:|---:|---:|---:|---:|
| 2025 / 152 | 2569 | 61,42 | -29,91 | 354,36 | 779,67 |
| 2025 / 424 | 2506 | 59,76 | -37,48 | 347,62 | 670,29 |
| 2026 H1 / 152 | 1442 | 57,03 | -30,15 | 318,63 | 678,26 |
| 2026 H1 / 424 | 1389 | 67,55 | -25,44 | 349,57 | 620,19 |

La menor pérdida por fill de 424 en H1 convive con mayor score medio y MAE,
aunque baja el RMSE. Las cifras no dan un orden único de calidad y no convierten
la mejora relativa en rentabilidad. En H1 los tres tickers presentan score medio
positivo y realizado medio negativo con ambos modelos; por ejemplo, SPXW424
predice 133,19 USD por fill y realiza -47,02.

`selected_attempts` incluye también NO_FILL. Sólo difiere de fills en control152
de 2025: 2571 intentos frente a 2569 fills, por dos NO_FILL de neto cero. Allí
score/neto medios son 61,37/-29,89 USD y MAE/RMSE 354,09/779,37. En las otras
tres combinaciones política-periodo intentos y fills coinciden. Se conservan
ambas poblaciones; no se interpreta ausencia de fill como pérdida ficticia.

El ajuste de un error medio por acción no garantiza la rentabilidad de escoger
el máximo positivo en cada estado libre. La política además cambia los estados
posteriormente disponibles al bloquear posiciones hasta su salida. El requisito
de un fill diario tampoco se deduce de MAE, RMSE o media de scores. Aquí ambas
políticas pierden y fallan actividad diaria, como documenta el
[resultado completo](COMMON_GREEK_COMPARISON_RESULT_20261023.md). La brecha
descriptiva entre poblaciones no demuestra por sí misma sesgo causal de selección,
drift, sobreajuste o una causa concreta del fallo.

Para reproducir las cifras desde los JSON: sumar `weight` y `n` entre bins;
agregar cada media y MAE con `sum(weight*valor)/sum(weight)` y calcular
`sqrt(sum(weight*rmse_usd**2)/sum(weight))`. No se promedian RMSE sin ponderación
ni se interpreta el score como probabilidad; no procede Brier. Las tablas usan
costes base, mientras el resultado económico conserva ambos escenarios.

El alcance sigue siendo dado scores sellados, con histórico de desarrollo ya
visto. La auditoría no demuestra recepción histórica de quotes, equivalencia
live ni semántica histórica verificada de todas las griegas/TTE. Este análisis
no elige umbral, ticker, mes o feature; no ajusta calibrador, activa experimento
ni autoriza promoción. Root revisó el documento y recalculó los 16 agregados de
calibración, los RMSE por ticker de H1 y la contribución de SPXW desde los JSON
auditados, además de contrastar las cifras TRAIN con su informe publicado.
