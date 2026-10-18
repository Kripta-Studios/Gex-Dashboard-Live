# Inventario local de volumen

Sí hay candidatos de volumen de opciones que no entran en las features
actuales. Esta revisión usa el censo existente y36 footers representativos,
sin leer filas de precios/volumen, ejecutar API, reconstruir features ni
entrenar. No acredita todavía calidad numérica o disponibilidad intraminuto.

## OHLC de opciones

Ruta canónica: `D:/ThetaData/data_options/{ticker}/ohlc/YYYY/MM/`.
Identidad por símbolo, vencimiento, fecha, strike y right; campos `volume`
e `count` int64, OHLC/VWAP float64 y `timestamp` string. Los24 footers
representativos del primer/último archivo de cada ticker-año2023–2026H1
declaran `interval_used=1m`, timestamps09:30–16:00 y vencimiento0DTE.
El descargador conserva los campos originales, sin convertir el volumen.
Su fallback permite1m→30s→5m: no se debe extender la comprobación de24
representantes a la resolución efectiva de todos los archivos sin revisarla.

| Ticker | 2023 | 2024 | 2025 | 2026H1 | Total /875 sesiones |
|---|---:|---:|---:|---:|---:|
| QQQ |250|252|250|120|872|
| SPXW |250|252|250|123|875|
| SPY |250|252|250|120|872|

Coincide por nombre con los2619 días disponibles, incluidas las24 medias
sesiones. Faltan exactamente QQQ/SPY20260401,20260409,20260415. Esto acredita
archivos y schemas, no cobertura válida de todos sus minutos o contratos.

La unidad almacenada es un contador entero asociado a un contrato de opción;
el parquet no documenta explícitamente su unidad económica. No es volumen de
acciones del subyacente ni dólares. Antes de convertirlo en una feature habría
que confirmar su definición de proveedor y distinguir volumen cero de fila
ausente. OHLC/count sólo pueden utilizarse cuando haya cerrado su intervalo;
el nombre timestamp no demuestra por sí solo que marque inicio o fin de barra,
ni la hora de recepción histórica. No hay reloj de recepción en este schema.

## Trades con tamaño ejecutado

Familia `cross_venue_opra_trade_quote_flow_v5_capture_2023_2025_v1`:
1364 archivos con `trade_timestamp` y `quote_timestamp` timestamp[us],
`sequence`, `condition`, `size`, `exchange`, precio y bid/ask con tamaños.
La convención local documentada interpreta size como contratos y calcula
`premium_dollars=price*size*100`; no se realizó ninguna nueva conversión aquí.

| Ticker |2023|2024|2025|Total|
|---|---:|---:|---:|---:|
| QQQ |218|227|242|687|
| SPY |212|222|243|677|

No aparecen SPXW ni2026 en esta familia. El capturador y los12 footers revisados
delimitan09:30≤trade_timestamp<10:35. Por tanto no ofrece tape para todo el
day trading de las10:30 al cierre. Enero2024 está ausente. La captura histórica
cerró con140 fallos estructurales y sin sello global; esta revisión no modifica
ese resultado ni admite automáticamente el subconjunto. La temporalidad entre
trade/quote, condiciones, cancelaciones y duplicados requiere comprobación por
fila antes de inferir dirección agresora. Los footers no la demuestran.

## Qué no es volumen

`data_underlying_derived` contiene `tick_count`. En
`script4_underlying_from_options.py:127`, éste se calcula con
`groupby(minute)[underlying_price].count()`: cuenta observaciones del precio,
no acciones negociadas. Lo mismo se arrastra a `data_training_input`.
`bid_size/ask_size` de capturas NBBO describen tamaño cotizado, no ejecutado.

Los OHLC permiten investigar intensidad de actividad de opciones junto a una
zona, una vez verificados reloj y unidades. No identifican por sí solos
absorción, órdenes límite persistentes o agresor comprador/vendedor. El tape
parcial contiene más información para ese diagnóstico, con los límites de
cobertura indicados. No se ha añadido ninguno de estos canales al modelo.

Evidencia reproducible: `inventory_volume_sources.py`; salida
`D:/GexResearchArtifacts/level_oracle_20261018/volume_source_inventory_v1/summary.json`,
SHA256 `a680969a54d9ce7cb703036b2b3d270a0ec648553f61eec6cbd4b5d5f516de54`.
La salida liga los hashes del censo/schema y contiene grupos, fechas exactas,
schemas y estadísticas de los36 footers. No rehashea todos los raw ni reemplaza
una admisión de valores. Se leyeron como texto `options_bulk.py`,
`thetadata_utils.py`, `script4_underlying_from_options.py`, el capturador V5 y
su predeclaración/informe de fallo; ninguno se ejecutó o modificó.
