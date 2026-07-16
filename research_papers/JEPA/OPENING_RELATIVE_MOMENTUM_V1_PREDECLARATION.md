# OPENING_RELATIVE_MOMENTUM_V1 — predeclaración

**Estado:** `PREDECLARED_PRE_OUTCOME`

**Fecha:** 2026-07-17 Europe/Madrid

**Base previa:** `093f7cea`

## Hipótesis

La reversión de la divergencia cross-session quedó cerrada con PF 0,627. Su
control de signo opuesto obtuvo PF 1,075 agregado, pero no puede rescatarse ni
promoverse post-hoc. Esta familia formula una pregunta nueva y más estrecha:

> El impulso relativo generado durante la sesión cash, desde el open 09:30
> hasta el último bar completado a 10:34, continúa entre 10:36 y 13:36.

No usa el cierre previo ni el gap overnight. Por tanto no invierte simplemente
la misma señal cerrada. El payoff sigue siendo un spread spot QQQ-SPY
equal-notional y SPXW actúa solo como segunda ancla de mercado.

Un PASS sería señal de factibilidad, no una policy final por ticker ni evidencia
de fills broker-grade. La meta final PF>1,20/WR>45%/>12 trades/mes/todos los
meses positivos por ticker permanece sin relajar.

## Fuente y scope

- `D:/ThetaData/data_underlying_derived/{QQQ,SPXW,SPY}`.
- Parquets 1m existentes; ningún download ni dataset nuevo.
- Desarrollo: `2022-01-03..2023-12-29` únicamente.
- `2024-01..2025-12` es outer cerrado hasta un freeze posterior.
- Todo 2026 y producción permanecen cerrados/intactos.

El loader debe rehashar cada fuente y exigir schema, metadata/date, grid exacto
09:30–16:00, timestamps compartidos, OHLC envelope y `tick_count>=0`.

Exclusiones congeladas antes de outcomes:

- medias jornadas actuales 2022-11-25, 2023-07-03 y 2023-11-24, porque 13:36
  está fuera de su RTH;
- `2023-06-05` completo, porque las barras SPY 09:54–09:56 inválidas están
  dentro de la señal cash-open;
- ninguna exclusión por retorno, PnL, tamaño del impulso o acción.

Como no existe dependencia cross-session, el día posterior a una exclusión se
evalúa normalmente y no consume ningún precio del día excluido.

## Señal fija

Para cada ticker `i` en el día `d`:

```text
opening_move_i = log(close_i(10:34) / open_i(09:30)) * 10.000
market_anchor = 0,5 * (opening_move_SPY + opening_move_SPXW)
relative_impulse = opening_move_QQQ - market_anchor
```

Acción primaria única, momentum:

```text
relative_impulse > 0  -> long QQQ / short SPY
relative_impulse < 0  -> short QQQ / long SPY
relative_impulse == 0 -> no trade registrado
```

No hay previous close, gap, beta, z-score, threshold, percentile, ranking,
abstention, modelo, fit ni selección por ticker/mes. La acción mean-reversion y
el spread fijo long-QQQ/short-SPY son controles no elegibles.

## Ejecución y coste

- Entrada: `open` exacto 10:36 ET de QQQ y SPY.
- Salida: `open` exacto 13:36 ET.
- Hold: 180 minutos exactos.
- Equal notional: retorno signed QQQ + retorno signed SPY.
- Coste: 1 bp round-trip por pata, 2 bps por spread.
- Máximo una posición por día; cero overlap por construcción.
- No stops, trailing, targets, borrow, slippage adicional ni market impact.

## Desarrollo y estados

Se ejecuta una sola vez 2022–2023 después de commit/push del runner.

La gate final de desarrollo exige en cada uno de los 24 meses:

- PF `>1,20`;
- WR `>45%`;
- más de 12 trades;
- PnL neto positivo;
- cero fallos de reloj, fuente, coste u overlap.

Para medir avance sin redefinir éxito se registran estados secundarios:

- `NO_AGGREGATE_EDGE`: PF agregado `<=1`;
- `INCREMENTAL_EDGE_ONLY`: PF agregado `>1` pero falla alguna gate mensual;
- `PASS_DEVELOPMENT_GATE_OUTER_NOT_OPENED`: los 24 meses pasan.

Solo el tercer estado autoriza congelar un runner outer en otro commit. Un PF
agregado >1 es progreso diagnóstico, no promoción ni permiso para retunar.

## Stop rule

Si no pasan los 24 meses:

- no abrir 2024–2026;
- no elegir mean-reversion, meses, ancla o ticker;
- no añadir threshold, beta, z-score, filtro de gap, stop, ML o nuevo clock;
- no traducir a opciones ni tocar producción.

Cualquier continuación debe ser otra hipótesis predeclarada y conservar la meta
final completa por ticker.
