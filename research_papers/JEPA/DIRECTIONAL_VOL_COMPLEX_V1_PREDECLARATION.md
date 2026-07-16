# DIRECTIONAL_VOL_COMPLEX_V1 — predeclaración

## Hipótesis independiente

DIRECTIONAL_SEMANTIC_JEPA_V1 demostró que el estado price-only a 10:35 no basta
para controlar el tamaño de los errores a tres horas. V1-VOL no cambia su reloj,
label, encoder, coste ni scheduler: añade una fuente independiente que el modelo
anterior no vio, el estado intradía de VIX y la estructura temporal oficial del
complejo de volatilidad.

No es un sweep de otro JEPA. Reutiliza exactamente el encoder/normalizer sealed
en `directional_semantic_jepa_v1_development_202208_202512` y construye todo en
memoria. La única pregunta es si volatilidad implícita contemporánea y su curva
reducen los errores direccionales/magnitud de QQQ, SPX y SPY.

## Fuentes nuevas

### VIX intradía local

```text
D:/ThetaData/data_underlying_derived/VIX/YYYY/MM/VIX_YYYYMMDD.parquet
```

Se exige el mismo grid 09:30–16:00, OHLC envelope y clocks 10:35 que en los
subyacentes. Es una reconstrucción ThetaData del underlying de las opciones VIX
y se considera proxy histórico hasta probar paridad contra Cboe. No se presenta
como feed live equivalente.

### Snapshot oficial Cboe

Una única captura inmutable descarga los CSV de daily index history publicados
por Cboe:

- `VIX1D_History.csv`;
- `VIX9D_History.csv`;
- `VIX_History.csv`;
- `VIX3M_History.csv`;
- `VIX6M_History.csv`;
- `VIX1Y_History.csv`;
- `VVIX_History.csv`.

Base URL:

```text
https://cdn.cboe.com/api/global/us_indices/daily_prices/{file}
```

Se preservan bytes HTTP exactos, URL, SHA256, headers útiles, rango de fechas y
manifest hash-last. El target no puede existir. No se usa DataShop de pago ni se
confunde backtest VIX1D intradía licenciado con estos cierres diarios públicos.

## Data gates

- Las siete series deben cubrir desde antes de 2022-08-01 hasta 2026-07-15.
- Fechas únicas, valores positivos/finitos y OHLC válido cuando exista OHLC.
- En cada decisión se usa el último cierre con `source_date < trade_date`;
  jamás el close del día actual. Lag calendario máximo siete días.
- Paridad local VIX 16:00 versus Cboe VIX close del mismo día se audita en
  2022-08..2025: mediana absoluta <=0,25 vol points y p99 <=1,50. Si falla,
  VIX intradía queda bloqueado y no se abren outcomes.
- Los hashes del encoder, runner price-only, predeclaración y fuentes quedan
  fijados antes del desarrollo.

La paridad close no demuestra equivalencia tick/live; solo evita mezclar un
índice distinto. Incluso un PASS económico conservará `live_parity=BLOCKED`
hasta implementar el mismo feed observable en producción.

## Features nuevas causales

VIX intradía, observadas hasta 10:35:

- nivel 10:35;
- retornos 1/5/15/30/60m y desde open;
- RV/rango/close-location 5/15/30/60m;
- gap contra el close RTH previo;
- divergencias VIX-vs-SPX en 5/15/30/60m;
- correlación y beta VIX/SPX de retornos 1m en 15/30/60m.

Complejo Cboe lagged:

- cierres previos VIX1D/VIX9D/VIX/VIX3M/VIX6M/VIX1Y/VVIX;
- cambios 1 y 5 observaciones;
- ratios 1D/9D, 9D/30D, 30D/3M, 3M/6M, 6M/1Y;
- slopes en vol points entre nodos adyacentes;
- curvatura corta `(VIX1D - 2*VIX9D + VIX)`;
- VVIX/VIX.

No se usan high/low/close oficiales del día de la operación, VIX futuro, VIX1D
intradía, VX futures, outcomes de opciones ni PnL como features.

## Profiles y selección

Se mantienen Ridge de persistencia y LightGBM Huber residual de V1, con sus
hiperparámetros exactos. Dos profiles seleccionables:

1. `VIX_INTRADAY_RESIDUAL`: técnicas + JEPA sealed + VIX intradía;
2. `VOL_COMPLEX_RESIDUAL`: lo anterior + complejo Cboe lagged.

Desarrollo: walk-forward enero–diciembre 2025, entrenando solo con días
anteriores. Orden por ticker idéntico a V1: más meses positivos, mayor q25 net
mensual, mayor PF agregado y nombre lexicográfico. La selección y provenance se
committed antes de abrir outcomes 2026 de estos profiles.

## Holdout

One-shot 2026-01-01..2026-07-15 con profile congelado por ticker, retrain mensual
causal y encoder inmóvil. Contrato económico sin cambios: features hasta 10:35,
fill spot-proxy open 10:36→open 13:36, hold 180m, una operación/día, no overlap,
coste 1bp.

Gate enero–junio por ticker: WR>45%, PF>1,20, >12 trades cada mes y PnL positivo
en los seis meses. Julio se reporta MTD. Esto sigue siendo una gate spot, no
futuros ejecutables.

Si falla, no rescatar niveles VIX, ratios, ventanas, thresholds, tickers, meses,
seeds, costes o subsets. Siguiente fuente distinta exigiría futuros/basis real o
un feed adicional; no otra transformación del mismo VIX.

