# SHORT_PREMIUM_DEFINED_RISK_V1 — predeclaración económica

## Propósito y límite anti-bucle

Este es el único replayer permitido tras cerrar las compras 0DTE, los spreads
direccionales y el oracle weekly de dos sesiones. No construye un dataset de
features ni entrena una red: lee directamente las cadenas 0DTE ya almacenadas y
produce solamente ledgers de candidatos y de operaciones seleccionadas.

La evaluación inicial termina en 2025-12-31. Enero-julio de 2026 permanecen
cerrados hasta que la política walk-forward supere **todos** los requisitos de
2025 para QQQ, SPXW y SPY. Si falla, no se rescatan deltas, anchos, horas,
stops, tickers, meses o subgrupos después de ver el resultado.

## Fuentes y reloj ejecutable

- Greeks/quotes originales:
  `D:/ThetaData/data_options/{ticker}/greeks/YYYY/MM/`.
- Universo de desarrollo/evaluación: sesiones 0DTE exactas de
  `2024-01-01..2025-12-31`: 502 sesiones por ticker, 1.506 en total.
- El reloj de cada clave histórica se prueba contra la unión disjunta sellada:
  - `wall_native_quote_sidecar_202208_202512_v1r1`, 1.441 sesiones;
  - `wall_quote_size_native_complement_202208_202512_v1`, 1.078 sesiones.
- Los sidecars suministran **solo** la prueba del timestamp/contract key. Los
  precios son siempre el bid/ask del Greek histórico hash-exacto; los precios
  revisados por el proveedor y sus claves extra no sustituyen el vintage.
- Entrada exacta `10:35 ET`, después del Initial Balance 09:30–10:29.
- Primer exit permitido `t+30m`; exit programado `t+180m` o el último minuto
  sellado de una media jornada, lo que ocurra antes. Nunca se cruza sesión.
- No hay as-of, forward-fill, nearest-time, midpoint, OHLC ni precio sintético.
  Una entrada resoluble cuyo exit programado no tenga las cuatro patas exactas
  invalida el run en lugar de desaparecer del ledger.

La reconstrucción de reloj del proveedor conserva provenance
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`; incluso un PASS económico sería
evidencia histórica condicionada y requeriría shadow/paper antes de capital.

## Estructuras congeladas

Cada estructura vende CALL y PUT con el mismo objetivo de delta absoluta. La
pata corta minimiza primero el error de delta, después el spread relativo y por
último el strike. CALL y PUT deben dejar una región interior no negativa.

Iron condor:

- deltas cortas: `0.15`, `0.20`, `0.25`;
- anchos CALL/PUT iguales y exactos:
  - SPXW: `5`, `10`, `20` puntos;
  - QQQ/SPY: `1`, `2`, `5` puntos.

Iron fly:

- un único strike corto común minimiza conjuntamente la distancia de CALL y
  PUT a delta absoluta `0.50`;
- anchos: SPXW `10` y `20`; QQQ/SPY `2` y `5`.

Las alas deben existir en el strike exacto, no en el más cercano. Las cuatro
patas deben ser distintas y tener quotes finitas, no cruzadas, con `ask>0` y
`bid>=0`; las patas cortas además requieren `bid>0`. El crédito debe ser
positivo e inferior al ancho. El riesgo máximo es
`width - entry_credit + 0.08` puntos.

## Fills, fricción y salidas

Entrada executable:

```text
credit = short_call_bid + short_put_bid - long_call_ask - long_put_ask
```

Cierre executable:

```text
debit = short_call_ask + short_put_ask - long_call_bid - long_put_bid
net_pnl_points = credit - debit - 0.08
net_pnl_R = net_pnl_points / max_risk_points
```

Los `0.08` puntos son una fricción fija conservadora de 8 USD por condor de un
contrato, adicional al cruce completo del spread NBBO. No modela leg risk,
slippage por tamaño ni fills parciales; por ello el resultado sigue siendo un
techo optimista de ejecución simultánea.

Perfiles de salida congelados:

1. `PT25_SL100`: toma 25% del crédito, stop con pérdida de 100% del crédito;
2. `PT50_SL100`: toma 50%, mismo stop;
3. `PT50_SL200`: toma 50%, stop con pérdida de 200% del crédito;
4. `TIME180`: sin profit target ni stop.

Los triggers usan PnL bruto observable y solo se comprueban desde `t+30m`. Si
el mercado salta el nivel, se contabiliza el debit executable observado, no el
precio del umbral.

## Selector walk-forward congelado

Para cada ticker y mes de 2025 se usan exactamente los 12 meses completos
anteriores. Cada combinación estructura/salida se resume por mes en R.

Cobertura mínima seleccionable: 12/12 meses y al menos 13 trades en cada mes.
Un candidato es `robust_eligible` si además tiene PnL agregado positivo,
PF>1,00 y al menos 8/12 meses positivos. Si existe alguno, la selección se hace
solo entre ellos; si no, se usa el conjunto con cobertura completa y se registra
`coverage_fallback` sin abstenerse.

Orden determinista:

1. mayor percentil 25 del PnL_R mensual;
2. mayor mediana del PnL_R mensual;
3. mayor PF agregado;
4. `profile_id` lexicográfico.

No se usa ninguna observación del mes evaluado para elegir su perfil.

## Gate que permite abrir 2026

Sobre las 12 predicciones mensuales concatenadas de 2025, **cada ticker** debe
cumplir simultáneamente:

- `WR > 45%` agregado;
- `PF > 1.20` agregado;
- al menos 13 trades en cada mes;
- `PnL_R > 0` en cada mes.

Se reportan concentración del top-5 de ganancias y drawdown, pero no se cambian
las gates tras verlos. Solo un PASS conjunto autoriza una captura sellada para
las sesiones 2026 sin timestamp nativo y un segundo run con el mismo algoritmo.
Un resultado de julio antes de terminar el mes se etiqueta obligatoriamente
`MTD`, nunca como julio completo.
