# CALENDAR_RISK_REVERSAL_PRESSURE_V1 — predeclaración

**Estado:** `PREDECLARED_OUTCOME_FREE_DATA_GATE`

**Fecha:** 2026-07-17 Europe/Madrid

**Base:** `90c08d5e`

## Pregunta económica

¿El cambio entre 10:30 y 10:35 de la demanda direccional 25-delta del 0DTE
respecto al siguiente vencimiento contiene información causal sobre el retorno
del subyacente a tres horas?

Esta medición es distinta de las familias cerradas:

- H-IVSURF1 midió deformación IV local alrededor de un wall únicamente 0DTE;
- DIRECTIONAL_OPTION_SURFACE_SPOT_V1 usó un panel 0DTE amplio con LightGBM;
- OPTION_PARITY_PRESSURE_V1 midió `CALL-PUT` en precio para el mismo strike;
- DIRECTIONAL_VOL_COMPLEX_V1 usó cierres diarios de índices de volatilidad.

V1 usa una diferencia de risk reversal entre dos expiraciones simultáneas y una
regla determinista, sin wall, OI, GEX, modelo, threshold o selección de columnas.

## Scope causal

Fuentes:

```text
D:/ThetaData/data_options/{QQQ,SPXW,SPY}/{greeks,iv}/YYYY/MM/*.parquet
D:/ThetaData/data_underlying_derived/{QQQ,SPXW,SPY}/YYYY/MM/*.parquet
```

Para cada ticker/sesión se exigen exactamente dos expiraciones del inventario:

- front: `expiration=trade_date`;
- back: el menor `expiration>trade_date` disponible ese día.

Desarrollo/data gate inicial: enero–diciembre 2023. El censo de schemas mostró
timestamp nativo en front y back durante 2023. Muchos ficheros 2024–2025 solo
tienen `underlying_timestamp`; quedan cerrados y no pueden entrar mediante
inferencia, as-of o subset de días nativos. Si 2023 pasa, un protocolo separado
debe congelar y completar el sidecar de reloj nativo para ambas expiraciones
antes de outer 2024–2025. Holdout 2026 permanece cerrado hasta PASS outer y otro
freeze. Producción no cambia.

Se excluyen por calendario 2023-07-03 y 2023-11-24 porque la salida 13:36 no cabe
en RTH. No se permite excluir otra sesión después de observar outcomes.

## Construcción exacta

Snapshots nativos `t0=10:30:00` y `t1=10:35:00` ET. Greeks e IV se unen con
igualdad exacta de:

```text
(symbol, expiration, trade_date, timestamp, strike, right)
```

No se usa `underlying_timestamp` como reloj de opción. Bid/ask son vintage y el
spot se toma del `open(t)` del underlying derivado validado.

En `t0`, por cada expiración se selecciona un CALL y un PUT:

- CALL objetivo `delta=+0,25`, PUT objetivo `delta=-0,25`;
- gap absoluto de delta <=0,10;
- precio `bid>0`, `ask>=bid`;
- `0 < bid_implied_vol <= ask_implied_vol < 5`;
- ranking fijo: gap de delta, moneyness log absoluta, strike ascendente.

Los mismos cuatro contratos elegidos en t0 deben existir y ser signable en t1;
no se reselecciona delta después de mover el spot. Para contrato `c`:

```text
mid_iv(c,t) = (bid_implied_vol(c,t) + ask_implied_vol(c,t)) / 2
RR(exp,t) = mid_iv(CALL25,exp,t) - mid_iv(PUT25,exp,t)
calendar_rr(t) = RR(front,t) - RR(back,t)
calendar_rr_pressure = calendar_rr(t1) - calendar_rr(t0)
```

Acción económica futura única si pasa el data gate:

```text
pressure > 0 -> LONG ticker
pressure < 0 -> SHORT ticker
pressure = 0 -> no trade
```

## Data gate outcome-free

El builder se commitea antes de leer retornos y debe exigir:

- inventario one-to-one Greek/IV para front y back;
- timestamp nativo y exacto en el 100% de las fuentes 2023 consumidas;
- cero keys duplicadas o joins many-to-many;
- cuatro contratos t0 válidos y persistentes en t1;
- cobertura >=90% por ticker y más de 12 eventos válidos en cada mes normal;
- pressure finito, missing cero, >=50 estados por ticker y zero fraction <99,5%;
- hashes de inputs/código/runtime, `outcome_accessed=false` y 2024–2026 cerrados.

Un fallo cierra la familia antes de labels. No se cambia delta, tolerancia,
expiración, reloj o regla tras el gate.

## Ledger económico, solo tras PASS_DATA_GATE

- decisión después de 10:35;
- entrada `open(10:36)`, salida `open(13:36)`, hold 180m;
- una posición por ticker/día, cero overlap y coste round-trip 1bp;
- controles no elegibles: signo inverso y always-long;
- por cada ticker y cada mes 2023: PF>1,20, WR>45%, trades>12 y net bps>0.

PF agregado por ticker >1 puede registrarse como progreso incremental, pero no
abre outer si falla una sola de las 36 celdas ticker-mes.

## Stop rule

No invertir el signo, elegir solo front/back, cambiar a 15/35/50 delta, mover
relojes, usar nivel en vez de cambio, seleccionar meses/tickers, añadir ML o
abrir 2024–2026 después de un fallo. El primer paso es exclusivamente capacity
y data gate 2023 sin outcomes.
