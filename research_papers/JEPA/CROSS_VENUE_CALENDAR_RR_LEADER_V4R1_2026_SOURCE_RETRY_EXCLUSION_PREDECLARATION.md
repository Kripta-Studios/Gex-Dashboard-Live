# CROSS_VENUE_CALENDAR_RR_LEADER_V4R1 — retry/exclusión de fuente 2026

**Congelada:** 2026-07-26 Europe/Madrid, después del fallo vintage V4 y de la
autorización explícita del usuario, antes de reconsultar la API, abrir una
feature económica 2026 o leer un outcome 2026.

## Autoridad y cambio permitido

El usuario sustituye expresamente el veto anterior a recapturar/excluir los
cinco IDs nuevos de junio de 2026. Autoriza:

1. reconsultar una sola vez sus fuentes Greek e IV mediante los mismos
   endpoints y fallback de `D:/ThetaData/options_bulk.py`, en un root nuevo;
2. si una pareja sigue siendo inaccesible, inválida o con key-set desigual,
   excluir el sensor-fecha completo antes de outcomes;
3. evaluar una sola vez el V4 ya fijado sobre el resto de 2026 disponible hasta
   el último día común local de julio.

La autorización no permite intersecar Greek/IV, hacer fill, nearest/as-of,
mezclar una mitad vintage con otra current, seleccionar por rentabilidad ni
retunear el modelo con 2026.

V6 queda cerrada antes de evaluación y sin una sola predicción. V4R1 no es una
familia de modelo nueva: es una revisión outcome-free del contrato de fuente
para el V4 inmutable.

    network_retry_started=false
    feature_2026_opened=false
    outcome_2026_opened=false
    production_modified=false

## Modelo V4 inmutable

Se reconstruye exactamente el logistic pooled V2R1/V4:

- train: las 1.482 filas selladas de 2023–2024;
- vector: las mismas 29 features y el mismo orden V4;
- pipeline: median imputer + StandardScaler + LogisticRegression L2,
  `C=0.1`, `solver=liblinear`, `max_iter=2000`, `random_state=0`;
- target: `direct_win = 1[base_gross_bps > 0]`;
- orientación DIRECT si `p>=0.5`, INVERSE si `p<0.5`;
- sin abstención, threshold tuning, sizing, filtro, refit o selección de ticker.

Mapping inmutable: QQQ←QQQ, SPY←SPY y SPXW←SPY. Entrada/salida cash proxy
open10:36→open13:36, hold180m y coste primario1bp; 2/3bps son sensibilidad no
selectiva.

Autoridades byte-exactas:

- V2 development dataset:
  `459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b`;
- V4 development dataset:
  `87413fb1c605c221aa8f225ad9877ccbdb6d5eca45877f4fa97a5b60d321d04b`;
- V4 evaluation summary:
  `a2beced1f021e156b53deaed3932dafc0af18f18f582d0b9af5db1a0762bd21b`;
- predeclaración V4:
  `0c1a18b745072fb5265e83209e9267a41aa0387024f988831835bdc7272e5062`.

## Universo outcome-free actualizado

El inventario por nombres de archivos, sin leer valores, fija 133 fechas
comunes QQQ/SPY entre 2026-01-02 y 2026-07-24. Counts:

    202601=20  202602=19  202603=22  202604=18
    202605=20  202606=21  202607=13
    sensor_sessions=266
    front_back_captures=532
    date_sha256=7fb305c4d6905393d4ab23fcc3518550cd1be1bbd0cb1686dd2f75a82f2921c3
    capture_id_sha256=5b2fb9eede8a7c620419edc16cf4e2bfabb1a6a9a1a79be09db8662cb2b1f6b1

Julio termina el 24 en este inventario y se reporta únicamente como MTD. No es
un mes completo ni participa en el gate de seis meses cerrados.

## Retry exacto y atómico

IDs:

| Capture ID | Fallo vintage conocido |
| --- | ---: |
| `QQQ|20260624|front|20260624` | Greek-only80 |
| `QQQ|20260626|front|20260626` | IV-only28 |
| `SPY|20260624|front|20260624` | Greek-only12 |
| `SPY|20260625|front|20260625` | IV-only484 |
| `SPY|20260626|front|20260626` | IV-only4 |

Para cada ID se hacen exactamente dos requests, sin tocar los parquets
existentes:

    /v3/option/history/greeks/first_order
    /v3/option/history/greeks/implied_volatility

    symbol, expiration, date, strike=*, right=both, format=json
    fallback interval=1m -> 30s -> 5m

Root inmutable:
`D:/ThetaData/cross_venue_calendar_rr_v4r1_source_retry_2026`.
Se preservan raw response, status, params, intervalo usado, parquet normalizado,
hashes y manifest por request. Cero retries científicos después de completar
esta única tanda; los retries HTTP técnicos son los mismos tres intentos del
helper existente y quedan auditados.

Una pareja es usable solo si ambas respuestas son válidas, únicas, contienen
los valores V4 necesarios, y sus keys
`symbol/expiration/trade_date/underlying_timestamp/strike/right` son
exactamente iguales en 10:30 y 10:35. No se permite `Greek∩IV`.

## Regla fail-closed de exclusión

Si el retry de un ID no es usable, se excluye todo el sensor-fecha:

- QQQ 20260624 o 20260626 afecta únicamente al target QQQ de esa fecha;
- SPY 20260624, 20260625 o 20260626 afecta conjuntamente a SPY y SPXW por el
  mapping congelado.

La exclusión se decide solo con el gate de fuente, antes de leer open10:36,
open13:36, retorno, label o PnL. No se excluye ningún otro día. Junio conserva
como mínimo 19 eventos QQQ y 18 SPY/SPXW si fallan los cinco retries, por encima
del mínimo13.

## Secuencia causal

1. Commit/push de esta predeclaración y los handoffs.
2. Implementar capturador retry, data gate y auditor outcome-free; tests y
   commit/push antes de red.
3. Ejecutar una sola tanda de diez requests.
4. Sellar retry o exclusiones exactas; construir 29 features hasta10:35 y
   auditar independientemente, sin outcomes.
5. Versionar gate+auditor.
6. Congelar, serializar y versionar el V4 exacto y el universo evaluable.
7. Leer opens10:36/13:36 2026 una sola vez y auditar ledger/modelo/costes/gates.

Gate de promoción en cada QQQ/SPXW/SPY para enero–junio cerrado: PF>1,20,
WR>45%, neto>0, mínimo13 trades cada mes y PnL positivo los seis meses. Julio
MTD debe ser además neto positivo, pero no se presenta como mes completo.

No hay despliegue por un PASS cash proxy. Después se exige payoff físico de
opción ask→bid, hold30–180m, no-overlap, `reject_while_open` y paridad exacta de
features backtest/live. Solo entonces puede prepararse integración
`paper_order_intents=true`; VPS real requiere permiso posterior.
