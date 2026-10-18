# Inventario local nuevo — 18 de octubre de 2026

Hay material suficiente para investigar el comportamiento de niveles, exposición
y opciones con datos locales: **366.555 archivos, 260,373 GiB, 235.018 parquets y
37 schemas estructurales**. El censo terminó a las 14:55 UTC, en 1.404 segundos,
sin errores de enumeración ni lectura de footer. No prueba rentabilidad ni
completitud económica de las sesiones.

Se enumeró todo `D:/ThetaData`, incluidos nombres, tamaños y fechas de modificación;
se leyeron todos los footers parquet, sus schemas, filas y metadata de índices.
No se deserializaron páginas de valores de mercado, no hubo API, descargas,
entrenamiento ni modificación de fuentes. Los JSON/CSV/NDJSON se inventariaron por
nombre y tamaño; este censo no inspecciona su contenido. No se hizo hash de los
279.573.867.874 bytes de fuentes ni se afirma un snapshot atómico del árbol.

## Evidencia reproducible

Root: `D:/GexResearchArtifacts/restart_20261018/inventory/`.

- `files.csv`: las 366.555 entradas individuales, 81.412.765 bytes.
- `schemas.json`: 37 descriptors con tipos, campos temporales, índices pandas y
  ejemplo de ruta. La presencia de una columna no verifica sus valores.
- `summary.json`: totales por familia, errores y hash del programa ejecutado.
- `groups.json`: agrupación original por familia/ticker/tipo/año/schema.
- `zero_dte_dates.json`: fechas canónicas de opciones por ticker/tipo.
- **`review_summary.json`**: agrupación final autoritativa para clasificación de
  ticker y fechas; se deriva de los dos primeros archivos, sin releer las fuentes.
- `artifact_hashes.json`: catálogo original de los cinco archivos iniciales.
- `review_artifact_hashes.json`: catálogo posterior separado, que añade las
  versiones de revisión y copias de código; el catálogo original permanece intacto.

[inventory_evidence.json](inventory_evidence.json) conserva en el repositorio
32.969 bytes de evidencia compacta: totales, cobertura, schemas por reloj,
sidecars y hashes. El CSV de 81 MB queda únicamente en el root local de artefactos.
SHA256 de `review_summary.json`:
`b076851c90f28d9db9b504e4ae8a99d234242459f25838fb4bff99bff6954d42`.

La revisión corrigió 2.361 etiquetas de ticker en derivados TLT/UNH y 35 etiquetas
de fecha de parquets cuyos event IDs contenían ocho dígitos confundibles con una
fecha. Los conteos/bytes/schemas y las fechas canónicas `data_options` no cambian.
Se conservan el CSV y agrupaciones originales y el primer resumen de revisión;
para fechas de sidecars usar `review_summary.json`, no `groups.json`.
`inventory_local.executed.py` conserva exactamente el código ejecutado, SHA256
`b27fd5eea28ea4be137a66a07552014d0e913b2b7b3eae7bd72c058e3af187cc`.
La versión en el repositorio incluye después esas correcciones de clasificación
y elimina un import sin uso. `summarize_inventory.py` reproduce la revisión a
partir del CSV existente. No se repitió el censo para corregir etiquetas.
Verificación final PASS: hashes originales, identidad del código ejecutado,
conteo/suma de bytes del CSV, suma de parquets y totales por familia; Ruff y
compilación de ambos programas PASS.

## Mapa de datos

Los GiB de la tabla incluyen todos los formatos de cada carpeta, no solamente
los parquets. Las copias/capturas relacionadas no son muestras independientes.

| Carpeta bajo D:/ThetaData | Parquets | GiB | Contenido candidato |
|---|---:|---:|---|
| `data_options` | 157.650 | 127,378 | Greeks/IV, OHLC de opciones y OI; múltiples vencimientos |
| `data_underlying_derived` | 22.135 | 0,260 | OHLC de spot derivado, con linaje de reparación |
| `data_training_input` | 1.605 | 0,094 | Features históricas ya transformadas |
| `cross_venue_opra_trade_quote_flow_v5_capture_2023_2025_v1` | 1.364 | 73,986 | Trades QQQ/SPY con timestamps trade/quote y bid/ask |
| `cross_venue_calendar_rr_native_clock_2024_2025_v1` | 3.008 | 1,380 | Quotes de ventanas front/back seleccionadas |
| `wall_native_quote_sidecar_202208_202512_v1r1` | 1.441 | 20,658 | Quotes con reloj explícito y tamaños |
| `wall_quote_size_native_complement_202208_202512_v1` | 1.078 | 13,506 | Quotes complementarias con tamaños |
| `h_ibqdyn1_ticks_202208_202512_v1` | 33.704 | 10,434 | Ticks alrededor de eventos IB seleccionados |
| `wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1` | 9.833 | 6,478 | Ticks alrededor de touches seleccionados |
| `wall_exact_greek_repair_20221230_v1r2` | 671 | 4,024 | Capturas Greek específicas del 30-dic-2022 |

Hay también versiones previas, preflights, reparaciones y diez parquets de retry
2026, todos conservados en el resumen íntegro. Los contextos de futuros Yahoo
60m y complejo de volatilidad Cboe tienen archivos no parquet; no se ha inferido
su cobertura intradía a partir del nombre de la carpeta.

`data_options` contiene 22 símbolos: AAPL, AMZN, GLD, GOOGL, HOOD, IWM, META,
MSFT, NDX, NDXP, NFLX, NVDA, PLTR, QQQ, SLV, SPX, SPXW, SPY, TLT, TSLA, UNH y
VIX. El inventario completo permite usarlos como contexto sin mezclarlos con el
universo de ejecución. SPX y SPXW son carpetas distintas: para esta investigación
0DTE se informa explícitamente SPXW, sin relabelar todos los contratos SPX.

## Cobertura nominal 0DTE y relojes

Las fechas siguientes se extraen del nombre canónico
`TICKER_EXPIRACION_FECHA_TIPO.parquet`; 0DTE significa expiración=fecha.
No son una afirmación de que cada minuto o cada strike esté disponible.

| Año | QQQ Greek | SPY Greek | SPXW Greek | Spot derivado por cada uno de los tres |
|---|---:|---:|---:|---:|
| 2022 | 170 | 170 | 220 | 251 |
| 2023 | 250 | 250 | 250 | 250 |
| 2024 | 252 | 252 | 252 | 252 |
| 2025 | 250 | 250 | 250 | 250 |
| 2026 hasta 17-sep | 169 | 169 | 178 | 178 |
| Total | 1.091 | 1.091 | 1.150 | 1.181 |

Greek, IV y OHLC tienen exactamente el mismo conjunto nominal de fechas 0DTE en
cada target. OI tiene 1.100 fechas para QQQ/SPY y 1.150 para SPXW. Los nueve días
2026 con OI pero sin los otros tres tipos en QQQ y SPY son: 01-abr, 09-abr,
15-abr, 01-jul, 07-jul, 10-jul, 16-jul, 26-ago y 01-sep. No se han rellenado.

**Los archivos actuales tienen mezcla de schemas; no corresponde repetir que
todos los Greeks 2024–2026 carecen de `timestamp`.**

| Año | QQQ con timestamp / total | SPY con timestamp / total | SPXW con timestamp / total |
|---|---:|---:|---:|
| 2022 | 170/170 | 170/170 | 220/220 |
| 2023 | 250/250 | 250/250 | 250/250 |
| 2024 | 20/252 | 0/252 | 0/252 |
| 2025 | 45/250 | 0/250 | 0/250 |
| 2026 | 154/169 | 139/169 | 148/178 |

Los **3.332 Greeks 0DTE** de los tres targets contienen `underlying_timestamp`,
`underlying_price`, `bid` y `ask`; 1.816 contienen además `timestamp` y 1.516 no.
No tienen columna `gamma`. Las ausencias de `timestamp` de OI coinciden en
conteo con esos 1.516 casos; OI no posee `underlying_timestamp` alternativo.

Por instrucción actual del usuario, los archivos sin reloj de opción explícito
siguen siendo candidatos bajo la hipótesis de investigación
`quote_clock := underlying_timestamp`. Se debe guardar la procedencia del reloj
(`explicit_timestamp` o `underlying_proxy`) junto al ejemplo. La presencia o
equivalencia observada de los campos no acredita un reloj de recepción live.
La comparación cuantitativa de relojes corresponde al informe de factibilidad
de esta revisión; este inventario solo establece schemas y cobertura nominal.

## Lectura y transformaciones a reconstruir

Rutas canónicas:

```text
D:/ThetaData/data_options/{ticker}/{greeks|iv|oi|ohlc}/{year}/{month}/{ticker}_{expiration}_{trade_date}_{kind}.parquet
D:/ThetaData/data_underlying_derived/{ticker}/{year}/{month}/{ticker}_{trade_date}.parquet
```

Usar `pyarrow.parquet.read_schema(path)` para descubrir columnas y
`pyarrow.parquet.read_table(path, columns=[...])` para lecturas proyectadas.
Identidad de contrato: ticker, expiración, strike y right normalizados; fecha y
tipo por nombre/campos. Mantener ambos relojes cuando existan, sin sobrescribirlos.
`interval_used` existe como columna en la familia original: el schema no indica
qué intervalo tiene cada fila. `options_bulk.py:51` usa endpoints OHLC, IV,
first_order y OI; `thetadata_utils.py:36` declara fallback 1m→30s→5m.

El código local leído como texto muestra decisiones relevantes:

- `script4_underlying_from_options.py:126` agrupa `underlying_price` en OHLC de
  minuto. Solicita muestras 1s, pero los originales 1s no están contenidos en
  el parquet OHLC guardado. En líneas 156–175 reemplaza ceros con valores de la
  misma fila (preferencia por close) y aplica `bfill().ffill()` a gaps. Esto
  explica el linaje posible, no demuestra que cada barra haya sido reparada.
- `script8_corrector.py` implementa reparación análoga sobre los archivos.
  El spot derivado sirve para exploración visual con esa procedencia declarada;
  una alternativa es reconstruir velas de precios muestreados desde Greek,
  conservando ceros/faltas y sin inventar extremos intraminuto.
- `mega_data_factory.py:95` calcula IB con máximos/mínimos de **closes**, incluyendo
  10:30; no coincide exactamente con high/low de la primera hora 09:30–10:29.
  Línea 127 redondea relojes; línea 143 rellena features hacia delante y atrás.
  `master_parquet.py:15` sustituye timestamp por underlying_timestamp. Por eso
  conviene reconstruir las features desde fuentes, conservando estas salidas
  anteriores como evidencia de otra transformación.
- Gamma/walls se reconstruyen desde IV, spot, tiempo y OI en
  `mega_data_factory.py:46`/`stats.py:34`. El signo calls positivo/puts negativo
  es una convención analítica; la base no observa posiciones de dealers.
  `data_options/ohlc` es OHLC de opciones y no contiene bid/ask: no reemplaza
  las quotes para simular compra al ask y venta al bid.

## Fuentes de ejecución complementarias

Los sidecars de quotes tienen `timestamp` físico, bid/ask y tamaños; los ticks
añaden exchanges/conditions y algunos `decision_dt`. Su selección por ventana,
contrato o touch limita dónde se pueden reutilizar. No se presupone tape completo.

| Familia | QQQ parquets / fechas | SPY parquets / fechas | SPXW parquets / fechas |
|---|---:|---:|---:|
| Calendar native clock 2024–2025 | 1.002/502 | 1.004/502 | 1.002/502 |
| Wall native quote | 437/437 | 502/502 | 502/502 |
| Quote size complement | 393/393 | 328/328 | 357/357 |
| IB ticks | 10.668/817 | 11.320/827 | 11.716/858 |
| Touch ticks v1r1r1 | 2.890/643 | 3.680/708 | 3.263/655 |
| OPRA V5 trades | 687/687 | 677/677 | — |

Las fechas de esta tabla proceden de directorios de sesión exactos, después de
corregir la confusión con event hashes. La presencia de bid/ask permite evaluar
costes de spread bajo un contrato explícito; este censo no mide staleness,
cruces, liquidez, fills o rentabilidad. OI debe incorporarse con una regla de
disponibilidad declarada y sin convertir automáticamente un máximo diario en
información de preapertura. Las comprobaciones de valores y los experimentos
se documentan separadamente.
