# CROSS_VENUE_CALENDAR_RR_LEADER_V4R2 — exclusiones outcome-free fijas 2026

**Congelada:** 2026-07-26 Europe/Madrid, después de que V4R1 se detuviera en
el data gate de features, antes de leer open10:36, open13:36, retorno, label o
PnL 2026. El usuario ordena ignorar los días sin datos utilizables y no hacer
más descargas.

## Alcance único

V4R2 no cambia el modelo V4, sus 29 features, mapping, clocks, threshold,
costes ni universo nominal. Solo congela cuatro exclusiones de sensor-fecha
detectadas por validadores hasta 10:35:

| Sensor | Fecha | Motivo outcome-free | Targets afectados |
| --- | --- | --- | --- |
| QQQ | 2026-03-10 | no persistent signable CALL 25-delta | QQQ |
| SPY | 2026-03-19 | no persistent signable PUT 25-delta | SPY, SPXW |
| QQQ | 2026-06-30 | Greek/IV vintage ask values differ, back 2026-07-02 | QQQ |
| QQQ | 2026-07-22 | Greek/IV key-set mismatch, front; Greek-only 92 | QQQ |

No se reconsulta ThetaData para estos IDs. No se intersecta, repara, rellena,
deduplica ni usa nearest/as-of. Se elimina el sensor-fecha completo antes de
construir targets y antes de cualquier outcome. Las cinco parejas retry de
V4R1 permanecen usables e intactas; exclusiones retry0.

## Censo congelado

De 266 sensor-fecha nominales quedan 262. El mapping exacto QQQ←QQQ,
SPY←SPY y SPXW←SPY produce 394 target-fecha. Counts esperados:

| Ticker | Jan | Feb | Mar | Apr | May | Jun | Jul MTD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 20 | 19 | 21 | 18 | 20 | 20 | 12 |
| SPXW | 20 | 19 | 21 | 18 | 20 | 21 | 13 |
| SPY | 20 | 19 | 21 | 18 | 20 | 21 | 13 |

Todos los meses cerrados enero–junio conservan al menos 13 trades. Julio sigue
siendo MTD hasta 2026-07-24: QQQ tiene 12 observaciones tras la exclusión y no
se presenta como mes completo ni como PASS de frecuencia mensual.

## Orden causal restante

1. Versionar esta predeclaración, código del gate y auditor antes de reejecutar.
2. Ejecutar el data gate outcome-free una sola vez y auditarlo independientemente.
3. Versionar gate+auditor.
4. Congelar y versionar runner/modelo V4 exacto.
5. Solo entonces leer 10:36/13:36 una vez para el outer 2026.

La promoción exige en QQQ/SPXW/SPY, por enero–junio cerrado, PF>1,20,
WR>45%, neto>0, mínimo13 trades cada mes y PnL positivo en los seis meses.
Julio MTD debe ser neto positivo y se reporta separadamente. Payoff físico,
live, VPS y systemd permanecen cerrados.
