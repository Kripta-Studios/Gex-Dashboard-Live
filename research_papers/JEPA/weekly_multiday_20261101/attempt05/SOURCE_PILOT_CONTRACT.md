# Weekly/multiday source pilot 01 — contract

Status objetivo: `COMPLETE_SOURCE_DIAGNOSTIC_NOT_ECONOMIC_EVALUATION`.

Este piloto sólo acredita si existe una trayectoria observable del **mismo
contrato** en cuatro cadenas semanales fijadas sin outcomes. No calcula labels,
delta, retornos, PnL, fills, señales ni selección de lado; no ajusta modelos y no
autoriza promoción. Las fuentes son únicamente Greeks locales nominales bajo
`D:/ThetaData/data_options/{SPY,QQQ,SPXW}/greeks/2025/{04,05}`. La salida real
única, reservada para una ejecución futura separada, es
`D:/GexResearchArtifacts/weekly_multiday_20261101/source_pilot_01`.

## Calendario predeclarado

Las cuatro cadenas son:

| entrada | vencimiento | sesiones exigidas |
| --- | --- | --- |
| 2025-04-04 | 2025-04-11 | 04, 07, 08, 09, 10, 11 de abril |
| 2025-04-11 | 2025-04-17 | 11, 14, 15, 16, 17 de abril |
| 2025-04-17 | 2025-04-25 | 17, 21, 22, 23, 24, 25 de abril |
| 2025-04-25 | 2025-05-02 | 25, 28, 29, 30 de abril; 01, 02 de mayo |

Se multiplican por los tres tickers: 69 identidades nominales. El calendario
queda fijado por este contrato. Root lo cotejó, sólo como metadata, contra
`ticker/date/close_i/status` del índice `SessionClock` con SHA-256
`7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`:
son exactamente 20 sesiones, `close_i=390` y cero `MISSING` entre 2025-04-04 y
2025-05-02. El consumidor no abrió ni verificó ese índice. Un
archivo ausente se registra como gap; jamás desplaza una sesión, acorta el
horizonte, cambia el vencimiento ni busca un sustituto disponible. Estos datos
ofrecen 6–8 DTE naturales; no se los presenta como una cadena 10 DTE.

## Lectura y relojes

Cada parquet se abre mediante `iter_batches` con una proyección cerrada:
`symbol`, `expiration`, `trade_date`, `strike`, `right`, los relojes disponibles
`timestamp`, `underlying_timestamp`, `interval_used`, y `bid`/`ask`. Ninguna
columna de outcome, PnL, retorno, delta o selección puede entrar en la
proyección o salir en el diagnóstico.

Los snapshots diagnósticos son exactamente 09:30, 10:30, 10:35 y 15:55
`America/New_York`: no nearest, floor, ceil ni forward-fill. Un `timestamp`
presente define `NATIVE_STORED_TIMESTAMP`; sólo si la columna no existe puede
`underlying_timestamp` definir `UNDERLYING_TIMESTAMP_PROXY`. Este último no
prueba quote clock ni recepción observada. Un reloj nativo presente pero
inválido no cae silenciosamente al proxy.

Se admiten únicamente valores Arrow timestamp o texto ISO completo. Un Arrow
timestamp sin zona y un ISO sin offset se interpretan por contrato como reloj
de pared `America/New_York`; un valor con zona/offset se convierte a esa zona.
Valores numéricos, unidades epoch inferidas y zonas desconocidas se rechazan.
La fecha local debe coincidir con `trade_date`. Las diferencias entre reloj
nativo y reloj del subyacente son sólo información: no se afirma edad ni
staleness.

La clave exacta es `(ticker, expiration, strike, right)` y vive en el namespace
de cada fecha. `expiration` y `trade_date` de las filas, y `symbol` normalizado,
deben coincidir con la identidad nominal. No hay rollover de vencimiento.
Duplicados de clave más snapshot invalidan la admisión; no se elige una fila.
DTE 0 en la sesión de vencimiento es válido.

`bid` y `ask` se usan sólo para clasificar quote válida: números finitos,
`bid >= 0`, `ask > 0` y `bid <= ask`. Crossed, ausente o inválida permanece
identidad observada pero no quote válida. No se emiten precios.

## Controles y resultados

Antes y después de leer se registra tamaño y SHA-256 de cada archivo; cualquier
cambio invalida la ejecución. Se guardan schema, filas, estado, intervalos,
conteos por clock/contrato/quote y, para cada entrada y sesión posterior hasta
vencimiento, intersecciones exactas de identidad y de quote válida al mismo
clock. Todos los gaps nominales permanecen visibles.

La ejecución real tiene dos fases del mismo consumidor. Primero
`--build-reviewed-inventory` crea `inventory.json` dentro del output reservado:
69 rutas nominales con size/SHA (nulos para missing), footer, rowcount y sólo el
schema proyectable, sin iterar batches. Después el diagnóstico exige
`--inventory` y `--inventory-sha256`, recalcula y compara ese inventario antes
de abrir el primer batch. Así el calendario, los paths y los bytes quedan
ligados externamente antes de leer valores; no se crean dos plataformas.

El consumidor rechaza rutas no nominales, archivos que resuelvan fuera del root
permitido, symlinks/reparse points, identidades internas distintas, escrituras
dentro de fuentes y una salida real distinta de la reservada. La salida debe no
existir y se publica al final. Staging y parciales son exclusivos, no se
sobrescriben ni se borran al fallar: conservan un `failure.json`. El manifest
final fija inventario, diagnóstico, código y contrato, y sólo se publica tras
rehash de cierre de las 69 identidades. El modo sintético sólo está disponible como API
de prueba con roots temporales explícitos; no relaja la proyección ni las reglas
de admisión.

El resumen siempre declara `fit_performed=false`, `profitability_evaluated=false`,
`promotion_approved=false`, `technical_ready=false`, `production_modified=false`
y `broker_or_api_used=false`. Un diagnóstico completo no es una evaluación
económica ni evidencia de rentabilidad.
