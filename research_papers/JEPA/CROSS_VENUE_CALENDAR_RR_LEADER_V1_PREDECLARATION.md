# CROSS_VENUE_CALENDAR_RR_LEADER_V1 — predeclaración

**Estado:** `PREDECLARED_NATIVE_CLOCK_FEASIBILITY`

**Fecha:** 2026-07-17 Europe/Madrid

**Origen de la hipótesis:** diagnóstico post-outcome de desarrollo 2023. Esta
familia no puede presentar 2023 como validación independiente.

## Motivación y arquitectura fija

SPXW y SPY tienen retorno 10:36→13:36 casi idéntico en 2023: correlación
`0,999733`, mismo signo en 246/246 fechas y diferencia absoluta mediana
`0,523bps`. Sin embargo, sus presiones calendar-RR correlacionan solo `0,580247`
y emiten la misma acción en 148/246 fechas. En los 98 desacuerdos, la policy
local SPXW pierde PF `0,752601` mientras la local SPY alcanza `1,170042`.

La hipótesis económica es que la superficie de opciones SPY puede ser un sensor
líder más estable para el factor S&P compartido. V1 congela exactamente este
mapping, sin estimación ni grid:

```text
QQQ action  = sign(QQQ calendar_rr_pressure)
SPY action  = sign(SPY calendar_rr_pressure)
SPXW action = sign(SPY calendar_rr_pressure)
```

SPXW solo opera si tanto su feature/payoff como la feature SPY del mismo trade
date son válidos. No hay as-of, nearest date, forward-fill, threshold, consenso,
ponderación, selector por mes, ML ni cambio de signo.

## Evidencia de diseño 2023, no OOS

Aplicar el mapping una vez sobre el ledger ya abierto produce:

| Ticker | Sensor | Trades | WR | PF | Neto bps | Mín/mes | Meses positivos |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | QQQ | 247 | 51,822% | 1,173476 | +812,500 | 19 | 7/12 |
| SPY | SPY | 248 | 50,403% | 1,072835 | +273,999 | 19 | 5/12 |
| SPXW | SPY | 246 | 50,000% | 1,071604 | +268,657 | 19 | 5/12 |

Es el primer mapping reciente que deja PF>1, WR>45%, neto positivo y más de 12
trades/mes en los tres tickers agregados. Sigue lejos de promoción: ninguno
alcanza PF>1,20 y fallan meses. Estos números generaron la hipótesis y no pueden
usarse para probarla.

## Scope cronológico

- 2023: design/training evidence ya contaminada, cerrada.
- 2024: primera validación congelada de V1.
- 2025: permanece sin evaluar. Solo puede abrirse con V1 inmutable si 2024 deja
  PF>1, WR>45%, neto positivo y mínimo 13 trades/mes en cada ticker; si se diseña
  una V2 usando 2024, debe predeclararse antes de abrir 2025.
- 2026: holdout final; no se abre antes de una gate estricta en 2025 y otro
  freeze. El programa ya ha visto outcomes 2026 en otras familias, por lo que la
  evidencia sería trial-level walk-forward, no un holdout virgen global.

La gate de promoción nunca se rebaja: para cada ticker PF>1,20, WR>45%, más de
12 trades en cada mes y PnL positivo en todos los meses. El gate PF>1 anterior
solo autoriza investigación secuencial, no live ni `production_live_ready`.

## Bloqueo de datos y sidecar nativo

Los parquets Greek/IV 2024–2025 suelen contener `underlying_timestamp` pero no
`timestamp` de opción. No se permite tratar ambos como equivalentes. Antes de
outcomes debe capturarse un sidecar inmutable de `/option/history/quote` para
front 0DTE y back inmediato, `strike=*`, `right=both`, `interval=1m`, clocks
10:30–10:35 ET.

El sidecar solo certifica reloj/keys. Delta, IV y bid/ask de la feature siguen
siendo los valores vintage almacenados; una revisión actual del proveedor se
audita y no los reemplaza. Por trade date/expiry se exige:

- raw response, parquet y manifest hasheados antes de sellar;
- timestamp nativo exacto 10:30 y 10:35;
- key set completo `symbol,expiration,strike,right` contra todas las filas
  vintage Greek/IV de ambos clocks, no solo los contratos finalmente elegidos;
- cero duplicates/many-to-many y CALL/PUT no vacíos;
- revisiones bid/ask contadas por fila/sesión;
- provenance `CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`;
- runtime/JAR/endpoint/request hashes y outputs inmutables.

Primero se permite solo un preflight outcome-free de 12 sesiones congeladas
(primera y última sesión normal por ticker-año 2024–2025). El full backfill se
autoriza únicamente si las 24 capturas front/back pasan y el coste proyectado es
acotado. No se lee ningún open 10:36/13:36 durante captura o data gate.

## Ejecución económica futura

Sin cambios respecto al mecanismo fuente: decisión después de 10:35, entrada
cash proxy `open(10:36)`, salida `open(13:36)`, hold180, una posición por día y
coste round-trip 1bp. Debe reportarse además sensibilidad congelada 2/3bps, pero
no selecciona la policy.

## Stop rule

No comparar durante 2024 variantes own/leader/consensus, no escoger meses,
thresholds, magnitudes, deltas, clocks o costes. Un fallo de cobertura nativa
cierra el gate sin outcome. Un PF<=1 o WR<=45% agregado en cualquier ticker de
2024 cierra V1 sin abrir 2025. Un resultado incremental PF>1 puede informar una
V2 predeclarada, pero no puede llamarse promoción ni abrir 2026.
