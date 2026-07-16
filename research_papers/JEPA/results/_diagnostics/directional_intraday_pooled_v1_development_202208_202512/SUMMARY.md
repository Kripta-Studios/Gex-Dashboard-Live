# DIRECTIONAL_INTRADAY_POOLED_V1 — cierre en desarrollo

## Veredicto

`CLOSED_DEVELOPMENT_NO_EDGE`. No se abre la evaluación 2026.

El perfil global `POOLED_BREADTH_TRANSMISSION` domina claramente al control
`POOLED_TARGET_ONLY`, pero no alcanza rentabilidad ni estabilidad suficiente en
el walk-forward 2025. El estado `PASS_DEVELOPMENT_FREEZE` de `metrics.json`
significa que la selección terminó y quedó congelada; no es una gate económica.

| Perfil seleccionado | Ticker | Trades | WR | PF | PnL | Meses positivos | Mínimo trades/mes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pooled breadth | QQQ | 1.434 | 49,86% | 0,986 | -241,15 bps | 3/12 | 78 |
| Pooled breadth | SPX | 1.434 | 48,95% | 0,954 | -673,75 bps | 3/12 | 78 |
| Pooled breadth | SPY | 1.434 | 49,86% | 0,964 | -530,86 bps | 3/12 | 78 |

El control target-only es peor: PF mínimo 0,776 y entre cero y dos meses
positivos. El panel de 15 tickers, el pooling entre targets y el incremento de
muestra no recuperan una señal direccional ejecutable a 53–60 minutos.

Por ventana, H2–H4 contienen contribuciones positivas, mientras H1/H5/H6 son
negativas. No se permite eliminar estas ventanas tras observar el outcome ni
crear V1R1 para rescatar ese subconjunto. La familia price/breadth intradía queda
cerrada sin usar 2026, sin dataset nuevo y sin cambios de producción.
