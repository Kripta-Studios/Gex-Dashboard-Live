# CROSS_VENUE_CALENDAR_RR_LEADER_V1 — contrato del data gate

**Estado:** `PREDECLARED_BEFORE_2024_OUTCOMES`

**Fecha:** 2026-07-17 Europe/Madrid

Este documento congela el único data gate permitido para materializar la
arquitectura ya definida en
`CROSS_VENUE_CALENDAR_RR_LEADER_V1_PREDECLARATION.md`. No autoriza leer el
retorno 10:36→13:36, labels, PnL ni ningún dato de 2026.

## Entradas inmutables

- Universo Greek∩IV 2024–2025: 502 sesiones por ticker, 1.506 sesiones y
  3.012 capturas front/back.
- Capture-ID SHA-256:
  `447e771b391f12dcfd7cba3692e65a7586dd4db2f3205311034616ddc7de5ce4`.
- Sidecar default:
  `D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1`.
- El builder falla si no existe un full seal PASS de 3.012/3.012, si cambia su
  índice, el contrato raíz o cualquier raw/parquet/manifest/source hash.
- Se reconstruye y revalida offline cada captura con el validador ya congelado;
  no se consulta la red durante el data gate.

## Puente de reloj permitido

Los parquets vintage conservan `underlying_timestamp` pero no option
`timestamp`. Ese campo no se acepta por inferencia. Para cada ticker, fecha,
expiración, strike, right y clock 10:30/10:35 se exige primero un join exacto
uno-a-uno contra las keys con timestamp de opción del sidecar nativo. Solo tras
esa prueba la fila vintage puede entrar en el cálculo.

El sidecar certifica reloj y keys, pero jamás sustituye valores económicos:

- delta, bid y ask proceden del parquet Greek vintage;
- bid/ask IV proceden del parquet IV vintage;
- las revisiones de bid/ask del proveedor actual son solo auditoría;
- bid/ask size no entra en la feature;
- los extras nativos no amplían el universo vintage.

El spot se lee únicamente en los dos rows exactos 10:30 y 10:35 del underlying
derivado. El data gate no carga ni inspecciona los opens 10:36/13:36.

## Feature y mapping congelados

Se conserva exactamente la selección V1: CALL/PUT más cercanos a |delta|=0,25
en t0, gap máximo 0,10, quotes/IV signables y mismo contrato persistente en t1.
La feature local es:

```text
pressure = Δ5m[(CALL25 - PUT25)_front0DTE
               - (CALL25 - PUT25)_next_expiry]
```

El mapping no admite variantes:

```text
QQQ  <- pressure QQQ
SPY  <- pressure SPY
SPXW <- pressure SPY del mismo trade_date
```

SPXW solo es válido cuando su sesión local y la sesión SPY de esa fecha son
válidas. No hay as-of, nearest date, forward-fill, threshold, magnitude gate,
consenso, cambio de signo, ML ni selector mensual.

## Gates outcome-free

Se excluyen del reloj económico las medias jornadas `20240703`, `20241129`,
`20241224`, `20250703`, `20251128` y `20251224`; permanecen en auditoría.

El estado solo puede ser `PASS_DATA_GATE` si simultáneamente:

- cobertura local y mapped por ticker-año `>=90%`;
- al menos 50 estados finitos distintos de signal pressure por ticker-año;
- fracción exacta de ceros `<99,5%` y cero missing en rows válidos;
- más de 12 eventos válidos en cada ticker-mes completo;
- 1.506 rows uno-a-uno, sin fechas 2023/2026 y con join SPY→SPXW exacto;
- full seal, capture index, raw, sidecar parquet, manifests, vintage Greek/IV y
  underlying source inventory revalidados por hash.

Un fallo produce `REJECTED_DATA_GATE` sin abrir outcomes. No se permite quitar
features, sesiones, meses o tickers para rescatarlo.

## Secuencia posterior

Tras un PASS: versionar manifest y compactos, congelar desde un commit posterior
el runner económico V1 y ejecutar una sola vez 2024. Solo PF>1, WR>45%, neto
positivo y mínimo 13 trades/mes en cada ticker permiten abrir 2025 con V1
inmutable. La promoción final mantiene PF>1,20, WR>45%, mínimo 13 por mes y PnL
positivo en todos los meses de cada ticker. Producción/systemd permanecen
intactos hasta superar la secuencia 2024→2025→2026 y la paridad live.
