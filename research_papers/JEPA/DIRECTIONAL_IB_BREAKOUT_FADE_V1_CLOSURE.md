# DIRECTIONAL_IB_BREAKOUT_FADE_V1 — cierre

Estado: `CLOSED_DEVELOPMENT_GATE`. Runner congelado en `b0f0bdcf`; evaluación
walk-forward única sobre 2025. No se abrió 2026 ni se modificó producción.

El panel outcome-free conserva 829 sesiones comunes entre los 15 tickers y
produce 4.349 eventos. La frecuencia pasa holgadamente, pero la economía falla:

| Ticker | Trades | WR | PF | PnL bps | Meses + | Mín/mes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 406 | 31,281% | 0,779 | -1.136,73 | 2/12 | 25 |
| SPX | 432 | 32,407% | 0,785 | -850,25 | 3/12 | 24 |
| SPY | 432 | 31,944% | 0,819 | -712,49 | 4/12 | 24 |

El modelo eligió mayoritariamente breakout; incluso ese subconjunto queda bajo
PF 1 (QQQ 0,891; SPX 0,811; SPY 0,841) y fade es peor. Los stops concentran la
pérdida, pero quitar/cambiar stops, targets, lags o reglas después de observar
el resultado sería un rescate post-hoc prohibido. Se cierra la familia exacta
IB-breakout/fade con escala 0,236/0,618 y 0,272/0,500; esto no falsifica una
hipótesis independiente overnight, multi-day o relative-value.

Los artefactos compactos están en
`results/_diagnostics/directional_ib_breakout_fade_v1_development_202208_202512/`.
El ledger identifica cada fill, modo, side y motivo de salida. El source
inventory sella que los faltantes se excluyeron para todos, sin nuevos datos.
