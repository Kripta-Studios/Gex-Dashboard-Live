# DIRECTIONAL_GLOBEX_ONLINE_EXPERT_V3 — predeclaración

Fecha: 2026-07-16. V3 se congela tras cerrar V2 en desarrollo 2025 y reutiliza
la misma fuente sellada; no crea ni descarga datos.

## Hipótesis

V1 mostró alpha aparente en 2025 pero cambió de signo en 2026; V2 lineal no
superó PF 1 en 2025. La hipótesis V3 es que ninguna combinación estática es
estable, pero la eficacia reciente de un conjunto pequeño de reglas causales
puede identificar si cada señal está en régimen momentum o reversión.

## Expertos y reloj

Para cada ticker y W1/W2 hay 14 señales base: constante LONG; retornos cash
1/5/15/30m, desde open y sesión previa; y del futuro emparejado (NQ para QQQ,
ES para SPX/SPY) retornos 1/3/6h, overnight, Asia, Europa y premarket. Cada señal
tiene su experto de signo y su inverso: 28 expertos fijos.

Antes de cada decisión, cada experto recibe sobre observaciones anteriores la
recompensa `clip(side * future_return_bps / 50, -1, 1)`. Sobre una memoria N se
suman recompensas y se aplica Hedge con
`eta=sqrt(2*log(28)/N)`. El voto ponderado determina LONG/SHORT; no hay
abstención, threshold, stop ni TP. W2 no usa el outcome W1 del mismo día porque
los historiales se separan por ventana y exigen fecha estrictamente anterior.

Único panel de memoria: 21, 42 y 63 observaciones. En 2025 se selecciona una
memoria global con el ranking ya congelado: peor/total de meses positivos, peor
PF, peor cuartil mensual y nombre. Se mantienen intersección estricta de todos
los tickers/futuros, W1/W2, coste 1 bp y cero solape.

Gate de avance por ticker: PF>1,10, WR>45%, >=8/12 meses positivos y >12
trades/mes. Si pasa, artefactos y selección se commitean antes del one-shot
enero–15 julio 2026. Gate final: PF>1,20, WR>45%, >12 trades en los siete meses
y PnL positivo en todos. Cualquier PASS es adaptativo y requiere shadow/live.
