# DIRECTIONAL_GLOBEX_ONLINE_LINEAR_V2 — predeclaración

Fecha de congelación: 2026-07-16. V2 se declara después de cerrar V1 en 2026 y
es por tanto un diagnóstico adaptativo, no evidencia confirmatoria nueva.

## Diagnóstico e hipótesis

V1 seleccionó Globex en 2025 con PF 1,20–1,21 pero cayó a PF 0,87–0,90 en
enero–julio 2026. La frecuencia pasó y el daño se concentró en inestabilidad
direccional, especialmente W2. La hipótesis V2 es que un LightGBM pooled de 430
variables con solo unos meses de historia de futuros aprendió interacciones no
estables. Un clasificador lineal, compacto, por ticker/ventana y actualizado
diariamente puede generalizar y adaptarse mejor.

No se descarga ni construye otro dataset. Se reutilizan byte por byte el bundle
sellado Yahoo 60m V1 y la intersección cash de 15 tickers. Yahoo rechazó con
HTTP 422 el preflight 2022-08..2024-07 porque 60m solo está disponible dentro de
los últimos 730 días; esas fechas se excluyen para todos los tickers.

## Contrato causal

Se mantienen sin cambios W1/W2, coste 1 bp, dos posiciones no solapadas, reloj
de barras completadas y eliminación conjunta de cualquier decisión incompleta.
Cada modelo usa solo filas con `trade_date` anterior; ni W2 consume el outcome
de W1 del mismo día. Siempre emite LONG/SHORT, sin abstención, stops, TP ni
threshold seleccionable.

Features cash fijas (18): retornos 1/5/15/30m y desde open; RV, rango, body y
location 15/30m; retorno/rango/location previos; seno/coseno del día. Features
Globex (14) del futuro emparejado — NQ para QQQ y ES para SPX/SPY — más los cinco
spreads de seis horas ya congelados. Total: 37. No entran los otros 290 campos
cash, los otros seis futuros completos ni ninguna feature outcome.

Modelo: `StandardScaler` + logistic regression L2, `C=0,05`, solver LBFGS,
ponderación por magnitud futura recortada a [5,150] bps. Se entrena por separado
para ticker y W1/W2 antes de cada día. Tres memorias fijas son el único panel:

- `ONLINE_LINEAR_ROLL63`: últimas 63 observaciones válidas;
- `ONLINE_LINEAR_ROLL126`: últimas 126;
- `ONLINE_LINEAR_EXPANDING`: todas las anteriores.

Se requieren al menos 50 observaciones y ambas clases. En 2025 se elige una sola
memoria global por peor número de meses positivos, total de meses positivos,
peor PF, peor cuartil mensual y nombre. Solo avanza si cada ticker logra PF>1,10,
WR>45%, al menos 8/12 meses positivos y más de 12 trades por mes.

Si avanza, la selección y hashes se commitean antes de evaluar una vez
enero–15 julio 2026. Gate final por ticker: PF>1,20, WR>45%, más de 12 trades en
cada uno de los siete meses y PnL positivo en todos. Debido a que V1 ya abrió
2026, incluso un PASS V2 sería evidencia adaptativa que requeriría shadow/live.
