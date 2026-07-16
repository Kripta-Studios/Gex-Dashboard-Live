# DIRECTIONAL_OPTION_SURFACE_SPOT_V1 — cierre en desarrollo

## Veredicto

`CLOSED_DEVELOPMENT_NO_EDGE`. No se abrió 2026 y no se creó otro dataset de
features. La superficie completa fue seleccionada sobre el control, pero falla
ampliamente la gate predeclarada.

| Perfil | Ticker | Trades | WR | PF | PnL | Meses positivos | Mínimo trades/mes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OPTION_SURFACE | QQQ | 589 | 46,69% | 0,853 | -985,75 bps | 5/12 | 36 |
| OPTION_SURFACE | SPX | 589 | 47,20% | 0,816 | -1.039,46 bps | 5/12 | 36 |
| OPTION_SURFACE | SPY | 589 | 47,71% | 0,804 | -1.110,48 bps | 4/12 | 36 |
| PRICE_LEVEL_CONTROL | QQQ | 589 | 49,41% | 0,981 | -121,08 bps | 5/12 | 36 |
| PRICE_LEVEL_CONTROL | SPX | 589 | 43,97% | 0,747 | -1.493,04 bps | 2/12 | 36 |
| PRICE_LEVEL_CONTROL | SPY | 589 | 49,41% | 0,910 | -476,51 bps | 7/12 | 36 |

El runner reutilizó el parquet executable-quote SHA
`11e26aaddd91fd441222d552e0362c1d4c2c4489a08d7a6de66479d6eb454fb1`,
filtró 289 features live-observable y calculó los retornos spot de 60 minutos en
memoria desde barras exactas. Cada decisión faltante se eliminó para los tres
tickers. Quedaron 1.917 decisiones comunes/5.751 filas pre-2026.

La inversión diagnóstica de las predicciones tampoco descubre una relación
contraria estable: PF 0,969/0,973/0,987 en QQQ/SPX/SPY. No se promueve esa
observación ni se rescatan relojes; 2026, julio y producción permanecen intactos.

La evidencia conjunta indica que el problema no es solamente theta 0DTE ni
solamente colapso espectral JEPA. Precio, breadth, VIX, superficie 0DTE y varias
mediciones de microestructura no han aportado dirección estable bajo ejecución
causal. Una continuación necesitaría una fuente genuinamente nueva con paridad,
no más recombinaciones de estas mismas columnas.
