# DIRECTIONAL_IB_BREAKOUT_FADE_V1 — predeclaración

Fecha de congelación: 2026-07-16. La búsqueda outcome-free del repositorio no
encontró una evaluación anterior de ejecución directa del Initial Balance (IB):
los estudios existentes usaron IB/Fibonacci como features o midieron quotes
cerca de esos niveles, pero no operaron causalmente su ruptura o fallo.

## Hipótesis y universo

Una salida del rango 09:30–10:29 puede continuar cuando la amplitud transversal
confirma el movimiento y revertir cuando la ruptura carece de confirmación. Un
modelo entrenado solo con eventos pasados decidirá entre dos acciones fijas:
`BREAKOUT` (seguir la ruptura) y `FADE` (operarla en sentido contrario).

Se usan como objetivos QQQ, SPXW (reportado SPX) y SPY, y como contexto causal
los 15 tickers del panel ya sellado: los tres objetivos más AAPL, AMZN, GOOGL,
META, MSFT, NFLX, NVDA, TSLA, IWM, TLT, GLD y SLV. Si falta o es inválido un
día para cualquiera, se elimina ese día para todos. No se descarga ni se crea
otro dataset y no se imputan días, semanas o minutos.

## Eventos, reloj y fills

El IB usa exactamente las 60 barras completas 09:30–10:29. Hay como máximo dos
eventos no solapados por ticker y sesión:

- W1: primer close fuera del IB entre 10:30 y 12:28; entrada en el open del
  minuto siguiente y cierre forzoso en el close 12:59.
- W2: primer close fuera del IB entre 13:00 y 15:28; entrada en el open del
  minuto siguiente y cierre forzoso en el close 15:59.

La señal superior es `+1` y la inferior `-1`; no se usa el high/low del minuto
de decisión para decidir. `BREAKOUT` opera en el sentido de la señal y `FADE`
en el contrario. Los niveles ejecutables, medidos desde el fill con el rango IB
`R`, quedan congelados:

- breakout: stop `0,236 R`, objetivo `0,618 R`;
- fade: stop `0,272 R`, objetivo `0,500 R`.

El stop está activo desde la entrada; el objetivo solo puede ejecutarse tras 30
minutos. Si stop y objetivo aparecen en la misma barra se asigna el stop. Los
gaps de stop salen al open adverso; los objetivos salen al nivel, no al mejor
open. Cierre forzoso al close indicado y coste total fijo de 1 bp. W1 termina
antes de comenzar W2.

## Features y modelo

Todas las features se calculan al close que disparó el evento: signo y exceso
de la ruptura, ancho/dirección/localización del IB, minuto, retornos y RV
1/5/15/30m del objetivo, retorno desde apertura y desde 10:29, volumen relativo,
estado equivalente de los 15 tickers, fracciones transversales por encima/debajo
del IB y retornos alineados con la señal. Se incluyen `window_id` y día semanal.
No entra ningún high/low, retorno, exit, PnL o label posterior a la decisión.

Por ticker y mes se entrena un LightGBM binario de parámetros fijos con todos
los eventos de meses anteriores. El label histórico es si `BREAKOUT` obtuvo
mayor PnL neto que `FADE` bajo los dos contratos de ejecución anteriores. En el
mes test, `p>=0,5` elige breakout; de lo contrario fade. No hay abstención,
threshold sweep, selección de nivel, stop, target, ventana, ticker o subgrupo.

Parámetros: 180 árboles, learning rate 0,025, 7 hojas, depth 3, min child 50,
subsample/colsample 0,8, L1 0,05, L2 0,5 y seed 20260716.

## Secuencia y gates

Primero se ejecuta un único walk-forward mensual 2025, entrenando con
2022-08..mes anterior. 2026 no puede abrirse si cualquiera de QQQ/SPX/SPY no
cumple en 2025: PF>1,10, WR>45%, mínimo >12 trades en cada mes y al menos 8/12
meses con PnL positivo.

Solo tras PASS, artefactos, runner y hashes se preservan y se ejecuta una vez
enero–15 julio 2026, reentrenando cada mes solo con meses anteriores. Gate final
por ticker: WR>45%, PF>1,20, >12 trades en cada mes y PnL positivo en los siete
meses. Debido a resultados 2026 ya conocidos de otras familias, un eventual
PASS será evidencia adaptativa, no confirmatoria ni autorización de producción.
