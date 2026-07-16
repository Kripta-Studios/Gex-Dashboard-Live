# CROSS_SESSION_RELATIVE_VALUE_V1 — predeclaración

**Estado:** `PREDECLARED_PRE_OUTCOME`

**Fecha:** 2026-07-17 Europe/Madrid

**Base previa:** `d02b1ad9`

## Pregunta económica

La investigación direccional y los payoffs 0DTE existentes están cerrados. Esta
familia pregunta algo económicamente distinto: si una divergencia cross-session
de QQQ frente al mercado amplio revierte durante las siguientes tres horas en
un spread QQQ-SPY equal-notional.

SPXW se usa únicamente como segunda ancla observable del mercado amplio. No es
una pata ejecutada ni se le atribuyen fills. Esta V1 es una prueba de señal spot;
un PASS no autoriza opciones, futuros, live ni producción sin un contrato de
ejecución broker-grade separado.

## Fuentes congeladas

- `D:/ThetaData/data_underlying_derived/{QQQ,SPXW,SPY}`.
- Solo Parquets 1m existentes entre `2022-01-03` y `2025-12-31`.
- Inventario outcome-free observado antes de esta predeclaración: `1.003`
  sesiones por ticker y schema común `symbol,date,timestamp,open,high,low,close,tick_count`.
- No downloads, Yahoo, VIX, options, labels JEPA ni datasets de features.
- El runner leerá las sesiones en memoria y materializará únicamente ledger,
  métricas, inventario y manifest compactos.

Cada sesión debe tener metadata exacta, timestamps únicos, grid 09:30–16:00,
OHLC envelope válido, `tick_count>=0` y paridad de fechas/timestamps entre los
tres tickers. Cualquier discrepancia falla cerrado.

Se excluyen como calendario/fuente, antes de outcomes:

- las nueve medias jornadas 2022–2025 ya congeladas en el programa, porque el
  exit 13:36 no pertenece a su sesión RTH;
- `2023-06-05` completo para los tres tickers, porque las barras SPY inválidas
  09:54–09:56 caen dentro de la ventana de señal;
- la primera sesión del inventario, que carece de cierre previo en el scope.

No se excluye una fecha por su retorno, spread realizado o PnL.

## Reloj y señal exactos

Para el día `d` y ticker `i`:

```text
prior_close_i = close RTH de la sesión inmediatamente anterior
decision_close_i = close de la barra [10:34,10:35)
cross_session_i = log(decision_close_i / prior_close_i) * 10.000
market_anchor = 0,5 * (cross_session_SPY + cross_session_SPXW)
relative_shock = cross_session_QQQ - market_anchor
```

El prior close es 16:00 en sesión normal y 13:00 si la sesión anterior fue una
media jornada. No se usa el close/high/low de 10:35 ni ninguna barra posterior.

La policy primaria única es mean reversion:

```text
relative_shock > 0  -> short QQQ / long SPY
relative_shock < 0  -> long QQQ / short SPY
relative_shock == 0 -> no trade, registrado explícitamente
```

No hay z-score, beta fit, threshold, percentile, ranking, feature subset,
abstention gate, ticker choice ni hiperparámetro. La policy opuesta momentum y
el spread fijo long-QQQ/short-SPY pueden calcularse solo como controles
diagnósticos; nunca pueden sustituir o rescatar la primaria.

## Ejecución y payoff

- Entrada de ambas patas al `open` exacto de 10:36 ET.
- Salida de ambas patas al `open` exacto de 13:36 ET.
- Hold exacto: 180 minutos.
- Equal notional: retorno de la pata long menos retorno de la pata short.
- Coste congelado: `1 bp` round-trip por pata, `2 bps` por trade spread.
- Una única posición spread por día; no existe overlap intradía ni ranking.
- No se modelan borrow, market impact ni fills broker. Por ello el resultado es
  signal feasibility, no `production_live_ready`.

## Fases y gates

Desarrollo único: `2022-01` a `2023-12`. El runner debe detenerse tras producir
el ledger de desarrollo y no puede leer retornos 2024–2026.

La familia solo autoriza freeze outer si la policy mean-reversion cumple en el
ledger completo y en cada mes de desarrollo:

- PF `>1,20`;
- WR `>45%`;
- más de 12 trades;
- PnL neto positivo;
- hold exacto 180m;
- cero violaciones de reloj, fuente o overlap.

Un mes con cero trades o una igualdad en el umbral es FAIL. Métricas pooled no
compensan un mes fallido. Los controles no participan en la gate.

Solo un PASS completo permitiría otro commit que congele el runner antes de un
one-shot `2024-01..2025-12`. Enero–julio 2026 permanece cerrado y ya no es un
holdout prístino del programa.

## Stop rule

Si desarrollo falla, `CROSS_SESSION_RELATIVE_VALUE_V1` se cierra sin:

- invertir la regla;
- escoger meses o una de las anclas;
- cambiar 10:36/13:36, coste o hold;
- añadir rolling beta, z-score, thresholds, stops o ML;
- abrir 2024–2026;
- traducir el resultado a opciones.

Una continuación posterior requeriría una hipótesis nueva predeclarada y una
fuente/ejecución con paridad live. Esta predeclaración no modifica producción.
