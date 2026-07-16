# OPTION_PARITY_PRESSURE_V1 — predeclaración

**Estado:** `PREDECLARED_OUTCOME_FREE_DATA_GATE`

**Fecha:** 2026-07-17 Europe/Madrid

**Base:** `3c62373c`

## Pregunta

¿El cambio predecisión del precio relativo CALL/PUT 0DTE, expresado como
synthetic forward frente al spot, contiene presión direccional causal a tres
horas para QQQ, SPXW y SPY?

Esta familia no afirma arbitraje de paridad. SPXW es europeo/cash-settled y
QQQ/SPY son americanos; financiación, dividendos y microestructura pueden
desplazar el nivel. Por ello la señal usa el **cambio en cinco minutos** sobre
los mismos strikes, no el nivel estático, y su interpretación es presión
relativa de quotes.

Es independiente de H-IVSURF1: no usa implied volatility, skew, curvatura,
walls, GEX, OI ni sus features. También es distinta del modelo genérico de
superficie direccional: es una identidad cross-right determinista, sin ML,
threshold, ranking o selección de columnas.

## Fuentes y provenance

- Greeks vintage: `D:/ThetaData/data_options/{QQQ,SPXW,SPY}/greeks/`.
- Spot causal: `D:/ThetaData/data_underlying_derived/{QQQ,SPXW,SPY}/`.
- Timestamp nativo: columna original cuando existe; en las 1.441 sesiones sin
  ella, join exacto al sidecar sellado
  `wall_native_quote_sidecar_202208_202512_v1r1`.
- El sidecar solo certifica timestamp/keys. Bid/ask siempre son los del Greek
  vintage; revisiones actuales se auditan pero jamás reemplazan esos precios.
- Scope físico/económico inicial: 2022-01-03..2023-12-29.
- 2024–2025 queda outer cerrado; todo 2026 y producción permanecen intactos.

No se usa `underlying_timestamp` como sustituto de timestamp de opción. Crossed
quotes se preservan en auditoría y son no-signable. Sizes, IV, delta y outcomes
no entran en la señal.

## Vista exacta y señal

Snapshots `t0=10:30:00` y `t1=10:35:00` ET. Para cada ticker/día se exigen
CALL y PUT 0DTE con igualdad exacta de:

```text
(symbol, expiration=trade_date, timestamp, strike)
```

Una pata es signable solo si `bid>0`, `ask>=bid` y todos los campos son finitos.
Se conservan únicamente strikes comunes a ambos timestamps y dentro de 100 bps
log-moneyness del spot en ambos relojes. Deben quedar al menos tres strikes.

Para cada strike `K` y timestamp `t`:

```text
Cmid = (Cbid + Cask) / 2
Pmid = (Pbid + Pask) / 2
joint_half_spread = ((Cask-Cbid) + (Pask-Pbid)) / 2
parity_z(K,t) = (K + Cmid - Pmid - spot(t)) / joint_half_spread
```

`joint_half_spread` debe ser estrictamente positivo. El spot es el `open(t)`
exacto del underlying derivado, con metadata/date/grid/OHLC/tick_count ya
auditados; no se consume el `underlying_price` híbrido de 2022-12-30.

Señal primaria única:

```text
parity_pressure = median_K[parity_z(K,10:35) - parity_z(K,10:30)]
parity_pressure > 0 -> LONG ticker
parity_pressure < 0 -> SHORT ticker
parity_pressure = 0 -> no trade
```

No hay otra ventana, radio, ponderación, clipping, threshold, beta, z-score
temporal, modelo o abstención.

## Data gate outcome-free

Antes de calcular labels o PnL, un builder inmutable debe revalidar fuentes,
hashes y joins y publicar solo features/quality/provenance. PASS exige:

- cero keys duplicadas y cero uso de timestamp inferido;
- al menos tres strikes comunes signables por evento;
- cobertura both-valid >=90% en cada ticker-año;
- más de 12 eventos signables en cada mes tras excluir solo medias jornadas que
  no permiten una salida 13:36;
- `parity_pressure` finito, al menos 50 estados distintos por ticker-año,
  fracción exactamente cero <99,5% y missing=0 entre eventos elegibles;
- identidad exacta con bid/ask vintage y spot derivado;
- cero acceso a retornos posteriores, 2024–2026 o producción.

Un fallo cierra `OPTION_PARITY_PRESSURE_V1` antes de outcomes. No se eliminan
features ni se relaja radio/cobertura/distinctness después del gate.

## Contrato económico congelado, solo si PASS_DATA_GATE

El runner debe commitearse después del data gate y antes de abrir outcomes:

- decisión con snapshots hasta 10:35;
- entrada spot-proxy `open` exacto 10:36;
- salida spot-proxy `open` exacto 13:36;
- hold 180 minutos, una posición diaria por ticker, cero overlap;
- coste round-trip 1 bp por ticker;
- acción determinista igual al signo de `parity_pressure`;
- controles no elegibles: signo inverso y always-long.

Desarrollo único 2022–2023. Por cada ticker y cada uno de los 24 meses debe
cumplir PF>1,20, WR>45%, más de 12 trades y PnL neto positivo. PF agregado>1
puede registrarse como progreso incremental, pero no abre outer si falla un solo
mes. Solo un PASS completo autoriza un freeze separado para 2024–2025.

Un PASS spot seguiría sin ser una policy live: requeriría traducción ejecutable
ask-to-bid o fills de futuros con paridad histórica/live antes de promoción.

## Stop rule

No rescatar por ticker, mes, inversión de signo, otro lag/radio/reloj, nivel
estático de paridad, threshold, spread filter o ML. Si falla, la identidad
cross-right 0DTE fija queda cerrada y 2024–2026 permanecen sin abrir.
