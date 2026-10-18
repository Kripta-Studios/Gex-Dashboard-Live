# Diagnóstico modelo–oracle: decisiones y límites

Comparación descriptiva de dos modelos congelados, sin nuevos fits: control net0 y net+episodios0. Validación comprende los 741 ticker-días completos de 2025; TRAIN contiene 96 ticker-días elegidos por hash antes de inferir. TRAIN fue expuesto parcialmente durante ajuste; VAL está fuera del ajuste pero sigue siendo desarrollo observado. No se ha seleccionado una corrección con este informe.

El oracle maximiza el futuro realizado. Sus beneficios, decisiones y valores de continuación son una referencia con información privilegiada; no acreditan una expectativa causal alcanzable. La discrepancia no identifica por sí sola un fallo técnico o una relación de mercado aprendible.

## Trayectorias ejecutadas

| Periodo | Modelo | Ticker | Trayectoria | Trades | Días con trade/observados | Neto base USD |
|---|---|---|---|---:|---:|---:|
| validation | gbt_net | QQQ | model | 711 | 199/247 | -7250.60 |
| validation | gbt_net | QQQ | oracle | 3143 | 247/247 | 266684.20 |
| validation | gbt_net | SPXW | model | 1137 | 235/247 | -64058.20 |
| validation | gbt_net | SPXW | oracle | 3830 | 247/247 | 2672497.00 |
| validation | gbt_net | SPY | model | 607 | 174/247 | -6382.20 |
| validation | gbt_net | SPY | oracle | 3330 | 247/247 | 251843.00 |
| validation | gbt_net_episode | QQQ | model | 645 | 187/247 | -7110.00 |
| validation | gbt_net_episode | QQQ | oracle | 3143 | 247/247 | 266684.20 |
| validation | gbt_net_episode | SPXW | model | 1183 | 231/247 | -98345.80 |
| validation | gbt_net_episode | SPXW | oracle | 3830 | 247/247 | 2672497.00 |
| validation | gbt_net_episode | SPY | model | 570 | 169/247 | -8109.00 |
| validation | gbt_net_episode | SPY | oracle | 3330 | 247/247 | 251843.00 |
| train | gbt_net | QQQ | model | 36 | 18/32 | 1822.40 |
| train | gbt_net | QQQ | oracle | 391 | 32/32 | 21373.40 |
| train | gbt_net | SPXW | model | 105 | 28/32 | 12352.00 |
| train | gbt_net | SPXW | oracle | 469 | 32/32 | 234182.60 |
| train | gbt_net | SPY | model | 33 | 14/32 | 2065.20 |
| train | gbt_net | SPY | oracle | 424 | 32/32 | 21117.60 |
| train | gbt_net_episode | QQQ | model | 39 | 17/32 | 1084.60 |
| train | gbt_net_episode | QQQ | oracle | 391 | 32/32 | 21373.40 |
| train | gbt_net_episode | SPXW | model | 104 | 28/32 | 18482.60 |
| train | gbt_net_episode | SPXW | oracle | 469 | 32/32 | 234182.60 |
| train | gbt_net_episode | SPY | model | 34 | 15/32 | 1835.60 |
| train | gbt_net_episode | SPY | oracle | 424 | 32/32 | 21117.60 |

## Mismo estado y mismas acciones ofrecidas

Los porcentajes de acuerdo usan sólo estados en que ambos selectores eligen una acción; TRADE indica decisión, no necesariamente fill. Las cohortes model_free y oracle_free se calculan por separado. En oracle_free, la decisión del modelo puede ser una comparación hipotética mientras mantiene una posición.

| Periodo | Modelo | Ticker | Cohorte | Estados ambos TRADE | Mismo lado | Mismo contrato | Mismo target | Rango mediano oracle por score |
|---|---|---|---|---:|---:|---:|---:|---:|
| validation | gbt_net | QQQ | model_free | 294 | 54.4% | 21.8% | 10.9% | 11.0 |
| validation | gbt_net | QQQ | oracle_free | 895 | 52.3% | 23.2% | 6.8% | 14.0 |
| validation | gbt_net | SPXW | model_free | 462 | 51.5% | 16.5% | 12.6% | 13.0 |
| validation | gbt_net | SPXW | oracle_free | 1534 | 52.0% | 15.6% | 9.0% | 18.0 |
| validation | gbt_net | SPY | model_free | 262 | 53.4% | 19.5% | 14.1% | 12.0 |
| validation | gbt_net | SPY | oracle_free | 610 | 52.6% | 21.8% | 9.2% | 13.0 |
| validation | gbt_net_episode | QQQ | model_free | 258 | 49.2% | 21.7% | 8.9% | 11.0 |
| validation | gbt_net_episode | QQQ | oracle_free | 900 | 51.2% | 24.8% | 6.3% | 14.0 |
| validation | gbt_net_episode | SPXW | model_free | 502 | 49.2% | 16.3% | 15.1% | 13.0 |
| validation | gbt_net_episode | SPXW | oracle_free | 1597 | 50.2% | 15.9% | 10.2% | 17.0 |
| validation | gbt_net_episode | SPY | model_free | 234 | 50.9% | 20.5% | 13.7% | 11.0 |
| validation | gbt_net_episode | SPY | oracle_free | 592 | 52.7% | 25.0% | 10.5% | 13.0 |
| train | gbt_net | QQQ | model_free | 10 | 60.0% | 20.0% | 0.0% | 11.0 |
| train | gbt_net | QQQ | oracle_free | 40 | 80.0% | 35.0% | 7.5% | 12.0 |
| train | gbt_net | SPXW | model_free | 41 | 39.0% | 12.2% | 12.2% | 13.0 |
| train | gbt_net | SPXW | oracle_free | 133 | 57.9% | 22.6% | 3.0% | 18.0 |
| train | gbt_net | SPY | model_free | 10 | 50.0% | 40.0% | 20.0% | 11.0 |
| train | gbt_net | SPY | oracle_free | 35 | 51.4% | 22.9% | 11.4% | 13.0 |
| train | gbt_net_episode | QQQ | model_free | 14 | 64.3% | 21.4% | 14.3% | 9.0 |
| train | gbt_net_episode | QQQ | oracle_free | 32 | 68.8% | 25.0% | 3.1% | 11.0 |
| train | gbt_net_episode | SPXW | model_free | 46 | 47.8% | 21.7% | 15.2% | 12.0 |
| train | gbt_net_episode | SPXW | oracle_free | 145 | 59.3% | 22.1% | 6.2% | 16.0 |
| train | gbt_net_episode | SPY | model_free | 11 | 54.5% | 18.2% | 9.1% | 11.0 |
| train | gbt_net_episode | SPY | oracle_free | 29 | 58.6% | 41.4% | 17.2% | 12.0 |

## Scores y operaciones realmente ejecutadas

Sólo trades con free y filled en su propia trayectoria. Los scores son estimaciones de neto individual USD; su suma no es una garantía de retorno. En oracle se muestran barreras y duración de su trayectoria realizada, sin atribuirle una predicción causal. Ratios con distancia de stop cero quedan indefinidos y contados en el CSV, no rellenados. Target/stop es un ratio geométrico entre centros de niveles respecto a spot; no equivale al ratio de beneficio/riesgo monetario de la opción.

| Periodo | Modelo | Ticker | Trayectoria | Score medio USD | Neto medio USD | Score suma USD | Neto suma USD | Target/stop mediano | Hold mediano |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| validation | gbt_net | QQQ | model | 15.08 | -10.20 | 10724.00 | -7250.60 | 3.540 | 20.0 |
| validation | gbt_net | QQQ | oracle | NA | 84.85 | NA | 266684.20 | 1.257 | 9.0 |
| validation | gbt_net | SPXW | model | 74.58 | -56.34 | 84791.98 | -64058.20 | 3.307 | 16.0 |
| validation | gbt_net | SPXW | oracle | NA | 697.78 | NA | 2672497.00 | 1.235 | 7.0 |
| validation | gbt_net | SPY | model | 8.66 | -10.51 | 5256.17 | -6382.20 | 2.708 | 19.0 |
| validation | gbt_net | SPY | oracle | NA | 75.63 | NA | 251843.00 | 1.290 | 8.0 |
| validation | gbt_net_episode | QQQ | model | 16.19 | -11.02 | 10444.03 | -7110.00 | 4.193 | 22.0 |
| validation | gbt_net_episode | QQQ | oracle | NA | 84.85 | NA | 266684.20 | 1.257 | 9.0 |
| validation | gbt_net_episode | SPXW | model | 77.41 | -83.13 | 91573.90 | -98345.80 | 2.987 | 15.0 |
| validation | gbt_net_episode | SPXW | oracle | NA | 697.78 | NA | 2672497.00 | 1.235 | 7.0 |
| validation | gbt_net_episode | SPY | model | 9.29 | -14.23 | 5296.98 | -8109.00 | 2.645 | 19.0 |
| validation | gbt_net_episode | SPY | oracle | NA | 75.63 | NA | 251843.00 | 1.290 | 8.0 |
| train | gbt_net | QQQ | model | 6.64 | 50.62 | 238.98 | 1822.40 | 4.857 | 35.0 |
| train | gbt_net | QQQ | oracle | NA | 54.66 | NA | 21373.40 | 1.227 | 10.0 |
| train | gbt_net | SPXW | model | 100.93 | 117.64 | 10597.21 | 12352.00 | 4.119 | 18.0 |
| train | gbt_net | SPXW | oracle | NA | 499.32 | NA | 234182.60 | 1.284 | 8.0 |
| train | gbt_net | SPY | model | 22.02 | 62.58 | 726.77 | 2065.20 | 4.612 | 29.0 |
| train | gbt_net | SPY | oracle | NA | 49.81 | NA | 21117.60 | 1.310 | 8.0 |
| train | gbt_net_episode | QQQ | model | 6.53 | 27.81 | 254.66 | 1084.60 | 1.949 | 22.0 |
| train | gbt_net_episode | QQQ | oracle | NA | 54.66 | NA | 21373.40 | 1.227 | 10.0 |
| train | gbt_net_episode | SPXW | model | 106.74 | 177.72 | 11100.86 | 18482.60 | 3.621 | 19.0 |
| train | gbt_net_episode | SPXW | oracle | NA | 499.32 | NA | 234182.60 | 1.284 | 8.0 |
| train | gbt_net_episode | SPY | model | 17.43 | 53.99 | 592.61 | 1835.60 | 5.736 | 33.0 |
| train | gbt_net_episode | SPY | oracle | NA | 49.81 | NA | 21117.60 | 1.310 | 8.0 |

## Interpretación de las diferencias

Las tablas decision_categories.csv separan WAIT, entradas y cambios de acción. Para cada día se verificó que la suma de regret V−Q en los estados libres del modelo coincide con oracle neto menos modelo neto. Su descomposición inmediata y de continuación evita atribuir todo a la dirección del trade. El término de continuación sigue usando el futuro privilegiado del oracle.

Los estados oracle bloqueados por una posición del modelo se cuentan, pero sus oportunidades superpuestas no se suman como beneficio recuperable. Las comparaciones ±1/2/5 minutos requieren contrato, target, stop y banda idénticos. Las filas no comparables se mantienen; se separan estados de fill. Estas variaciones temporales son hindsight, no políticas evaluadas o mejoras seleccionadas.

Los CSV adjuntos conservan distancias target/stop en unidades IB, delta, duración posterior y fracciones de labels/predicciones positivas. Los primeros ejemplos cronológicos por categoría se eligieron por fecha, nunca por beneficio. Los inputs causales anteriores a la entrada pueden describir una acción; no convierten la elección retrospectiva del oracle en una justificación causal.

## Integridad

Identidad SHA256: `3dd07074a229c972248e08906329c9f7b4d3e5b3a1cbef7202aa5ef7836b2552`.
Summary final SHA256: `74f955f535e9a26cb85f281a8bc78c1405767e85219a1fc51262c0630372b6ad`.
Se verificaron los hashes de todos los outputs diarios utilizados por este informe. El productor verificó alineación de IDs, trayectorias oracle, ausencia de regret negativo material y descomposición/telescoping por día. Esto no sustituye una auditoría independiente completa del diagnóstico ni prueba paridad histórica/live.

El primer intento preservó741díasVAL completos y falló sólo al serializar dos flags booleanos del agregado temporal. La continuación revisada normalizó únicamente su representación nullable, conservando valores, filas, cálculos y productor original. El registro está en technical_repairs/timing_nullable_boolean_v1.
