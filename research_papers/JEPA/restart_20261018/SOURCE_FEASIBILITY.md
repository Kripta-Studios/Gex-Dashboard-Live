# Fuentes locales: viabilidad para una investigación nueva

Revisión: 2026-10-18. Solo lectura local; cero API, descargas, fits o métricas económicas en esta revisión. No modifica ni valida retrospectivamente experimentos anteriores.

**Actualización posterior:** la comparación empírica solicitada por el usuario en `CLOCK_EQUIVALENCE.md` encontró igualdad exacta de timestamp y underlying_timestamp en 1.889.312 filas de 15 archivos, y estructura compatible en 13 archivos sin timestamp. Por tanto, 2024–2026 sí deben tratarse como candidatos de investigación bajo una convención explícita de reloj. Las reservas de esta revisión sobre recuperar una columna nativa ausente no constituyen una prohibición de usar underlying_timestamp como reloj de snapshot asumido.

## Conclusión operativa

**2023 es el candidato inmediato coherente para un benchmark nuevo de SPXW/SPY/QQQ con precios muestreados, OI, delta/vega/IV y bid/ask del mismo contrato.** Los 144 footers representativos de 2023 examinados (primer y último archivo 0DTE de cada mes, tres tickers, Greeks/OI) conservan timestamp nativo. Nueve días completos de Greeks y nueve OI pasaron las comprobaciones descriptivas expuestas debajo. Esto no sustituye el control de todos los días del dataset que construya el benchmark.

No se puede certificar desde estas muestras un dataset de verdaderos OHLC de spot sin reparaciones, recepción histórica/live observada ni inventario firmado de dealers. Es viable investigar bajo supuestos explícitos; no es viable presentar esos supuestos como observaciones.

## Rutas y lectura

Patrones principales:

```text
D:/ThetaData/data_options/{ticker}/greeks/{YYYY}/{MM}/{ticker}_{expirationYYYYMMDD}_{tradeYYYYMMDD}_greeks.parquet
D:/ThetaData/data_options/{ticker}/oi/{YYYY}/{MM}/{ticker}_{expirationYYYYMMDD}_{tradeYYYYMMDD}_oi.parquet
D:/ThetaData/data_options/{ticker}/iv/{YYYY}/{MM}/{ticker}_{expirationYYYYMMDD}_{tradeYYYYMMDD}_iv.parquet
D:/ThetaData/data_options/{ticker}/ohlc/{YYYY}/{MM}/{ticker}_{expirationYYYYMMDD}_{tradeYYYYMMDD}_ohlc.parquet
D:/ThetaData/data_underlying_derived/{ticker}/{YYYY}/{MM}/{ticker}_{tradeYYYYMMDD}.parquet
```

Para 0DTE, expiration y trade date del nombre deben coincidir y verificarse contra las columnas. Usar SPXW para las opciones semanales de SPX: SPXW no es un ETF ni tiene volumen spot negociado equivalente a SPY/QQQ.

Greeks de 2023 contiene identidad `symbol, expiration, trade_date, strike, right`, `interval_used`, `timestamp`, `underlying_timestamp`, `underlying_price`, `bid`, `ask`, `delta`, `implied_vol`, `theta`, `vega`, `rho`, `epsilon`, `lambda`, `iv_error`. **No contiene gamma.** No llamar GEX observado a una transformación de esos campos. Gamma calculada mediante un modelo tendría que declararse estimada, con supuestos de carry, vencimiento y ejercicio.

OI contiene identidad, `interval_used=daily`, `timestamp`, `open_interest`. Las identidades canónicas deben normalizar CALL/PUT frente a C/P y strike numérico antes de unir; OI ausente no equivale a cero.

Los strings timestamp de las muestras son ISO naive con `T`, fracción de segundo opcional. Interpretar como hora America/New_York es una convención de archivo, no una observación de recepción. `pd.to_datetime(..., format='ISO8601')` admite ambas precisiones; la inferencia automática de pandas falló con OI mixto. `underlying_timestamp` describe otro reloj; no debe sustituir el timestamp ausente de la cotización.

## Comprobaciones nuevas y evidencia

Script reproducible: `source_probe.py`. Salida: `D:/GexResearchArtifacts/restart_20261018/source_probe/iso8601_parser/probe.json`. Incluye schemas, número de filas, metadata del índice, hashes SHA256 de los 18 archivos leídos por valores y resultados agregados. Total: 162 registros de schema, incluidos dos paths inexistentes, y 18 proyecciones de valores. Primera ejecución abortó por parsing de precisión ISO mixta; el directorio raíz vacío se conserva y el resultado corregido está en subdirectorio separado. No hubo resultado económico ni selección por resultado.

Se examinaron valores completos de 2023-01-03, 2023-06-01 y 2023-12-01 para cada ticker:

| Comprobación | Resultado |
|---|---|
| Intervalo Greeks | 1m en los nueve archivos |
| Relojes por archivo | 391, de 09:30 a 16:00; 390 antes de 16:00 |
| Claves contrato/timestamp duplicadas | 0 en las muestras |
| Underlying timestamp posterior a quote timestamp | 0 en las muestras |
| Discrepancia de spot entre contratos en un minuto | 0 en las muestras |
| Spot no positivo | Todos los contratos SPXW a 09:30 en los tres días; ninguno en SPY/QQQ |
| Bid positivo y ask >= bid | Solo una fracción de las filas de toda la cadena; filtrar al construir acciones |
| OI posterior a apertura | 0 en los nueve OI muestreados |
| Semántica OI de cierre previo verificada | No |

SPXW presenta además IV sentinel `21474.83646` y delta inválida económicamente cuando spot es cero. Un valor no nulo no basta para admitir Greeks. Hay IV cero y bid/ask cero en strikes extremos; no rellenarlos ni escoger ex post el contrato que sí tuvo buena salida.

OI positivo por ticker en enero/junio/diciembre: SPXW 269/252/387; SPY 168/170/245; QQQ 126/170/235. Que sus timestamps sean preapertura no prueba cuándo se publicó el dato originalmente ni si representa exactamente el cierre anterior. Una unión que lo use debe declarar disponibilidad y semántica asumidas, conservar missingness y restringirse a registros elegibles antes de cada decisión.

## Los años 2024–2026 no tienen un reloj uniforme recuperable

Los seis archivos Greeks/OI de 2024-01-02 carecen de `timestamp`; también los cuatro SPXW/SPY de 2025-01-02. Sus footers pandas dicen `index_columns=[]`, sin índice físico alternativo. `options_bulk.py` líneas 343–363 elimina columnas symbol/expiration/date del payload antes de insertar metadatos y serializa con `preserve_index=False`. No hay reloj oculto en un índice que pueda rescatarse.

No obstante, **no todos los archivos posteriores carecen de reloj**: QQQ Greeks/OI de 2025-01-02 sí lo tienen, y SPXW Greeks/OI de 2026-07-01 también. SPY/QQQ Greeks 0DTE de 2026-07-01 no existen en los paths probados, aunque sus OI sí. El inventario exhaustivo debe decidir qué tramos posteriores pueden añadirse; no cabe deducirlos por año solamente.

Reconstruir timestamp por orden de filas o asumir 391 muestras para cada contrato sin comprobarlas inventaría información. Utilizar underlying_timestamp como reloj de snapshot requiere una convención explícita, ahora respaldada por la comparación descrita en `CLOCK_EQUIVALENCE.md`; no se lo debe presentar como una columna quote recuperada o recepción observada. Los OHLC de opciones sí tienen timestamp, pero no incluyen bid/ask.

Hay capturas complementarias con reloj nativo: `wall_native_quote_sidecar_202208_202512_v1r1/{ticker}/{date}/quotes.parquet` contiene bid/ask/sizes, identidad y timestamp. Muestra SPY 2024-01-02: 54.000 filas, primera 10:20. Los directorios `cross_venue_calendar_rr_native_clock_2024_2025_v1` y `...v1r1_repairs` contienen front/back quotes para ventanas específicas (muestras 10:30), no una cadena de Greeks de jornada completa. Estas fuentes pueden ampliar pruebas de ejecución dentro de su cobertura propia; no permiten asignar retrospectivamente un reloj a Greeks de otro archivo por proximidad o igualdad de precios.

## Por qué no usar las barras derivadas como verdad primaria

`script4_underlying_from_options.py` líneas 127–148 agrupa `underlying_price` de Greeks por minuto y usa first/max/min/last. El capturador solicita 1s para un strike central, primer C/P exitoso y una expiración disponible. No es un feed de trades consolidado de spot. El raw intermedio no queda guardado por ese código.

Líneas 155–175 sustituyen ceros por NaN, reparan campos con el close de la propia fila y rellenan filas vacías con `bfill().ffill()`. Líneas 290–298 aplican esa reparación antes de guardar. El script demuestra la posibilidad de relleno; no demuestra qué filas concretas de cada histórico se repararon. `tick_count=60` cuenta muestras, no volumen de negociación ni prueba 60 cambios de precio. Por ello no sirve como certificado del máximo/mínimo exacto de la primera hora ni de causalidad sin inspeccionar el linaje específico.

## Dataset mínimo y límites del benchmark

1. Partir de 2023 y validar por archivo timestamp nativo, identidad, duplicados, edad de spot, precios finitos y reglas de cotización. Conservar la máscara de SPXW 09:30 y las ausencias de OI; no imputar.
2. Formar velas **muestreadas** 5m/15m y un **IB muestreado** sobre [09:30,10:30). Declarar que no es el IB de extremos intraminuto completos; SPXW tiene una muestra de apertura faltante. Publicar ese coverage en cada evento.
3. Construir zonas suaves alrededor de IB/Fibonacci y concentraciones OI call/put; añadir trayectoria de delta/vega/IV válidas. Los walls OI son aproximaciones de concentración, no prueba de signo o comportamiento de dealers.
4. Todas las features usan solo muestras anteriores a la decisión bajo demora asumida; 5m/15m completas antes de la decisión. Ejecutar sobre bid/ask posteriores y del contrato elegido con información de entrada; salida fija, costes declarados, ausencia de overlap. Una quote observada no garantiza fill sin depth/sizes.
5. Separar cronológicamente ajuste, selección y test; no interpretar un split nuevo de 2023 como evidencia nunca vista por el proyecto. Comparar precio solo, zonas reales y niveles placebo desplazados con idéntico presupuesto de modelos. Esto responde si la geometría de zonas aporta algo adicional a la trayectoria y al régimen.

Este camino permite medir una hipótesis nueva bajo supuestos reproducibles ahora mismo. Un resultado favorable seguiría siendo evidencia de desarrollo y requeriría un tramo futuro congelado y validación de ejecución antes de operar.
