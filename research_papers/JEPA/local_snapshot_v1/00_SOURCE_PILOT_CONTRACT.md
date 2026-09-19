# LOCAL_TIMESTAMPED_OPTION_SNAPSHOT_V1: piloto de fuente local

Fecha: 2026-09-19. Estado previo: AUTHORIZED_SOURCE_PILOT_OUTCOMES_CLOSED.
Autoridad: el usuario confirma ausencia de API y responde «Autorizar una revisión
local nueva» a la propuesta de snapshots con reloj verificable, contrato y pruebas
publicados antes de resultados. Referencia: USER_LOCAL_SNAPSHOT_RESEARCH_20260919.

Esta revisión no reabre V1R1, no modifica sus gates y no selecciona un ticker por
rentabilidad pasada. Estudia si las muestras locales permiten una investigación
posterior con supuestos explícitos. El piloto no entrena ni calcula payoffs.

## LSP-001: entradas y presupuesto fijo

Usar solo seis archivos de `D:/ThetaData/data_options`: SPXW, SPY y QQQ,
tipos `greeks` y `oi`, fecha y expiración `20230103`. Patrón exacto:
`{ticker}/{kind}/2023/01/{ticker}_20230103_20230103_{kind}.parquet`.

La fecha es la primera sesión de calendario de 2023 y los seis schemas tienen
los campos requeridos. Se elige antes de abrir precios de este piloto, no por
outcomes. Los footers indican Greeks 1m y OI daily. No sustituir fecha, ticker,
expiración o archivo si falla. Máximo 64 MiB por archivo, seis archivos, reserva
de disco 2 GiB. Root nuevo fijo:
`D:/GexResearchArtifacts/local_snapshot_v1/source_pilot_20260919_01`.

Cero red de mercado, importación de descargadores, API, credenciales, modelos,
features económicas o lectura de labels. No acceder a `data_training_input`,
V5, servicios, bots, web, VPS o bróker. No modificar raw de D:/ThetaData.

## LSP-002: copia, publicación y lectura restringida

Publicar contrato, productor, auditor y tests antes del run real. Verificar HEAD
publicado y equivalencia del código local con HEAD, registrar hashes y runtime.
Copiar los seis parquets bajo handles coherentes que niegan escritura/borrado;
sellar tamaños y SHA. Productor y auditor leen esas copias. Un hash cambiado,
output existente o fuente fuera del allowlist detiene la ejecución.

Greeks: leer por filtro nativo únicamente `09:30 <= timestamp < 10:30` ET.
Proyectar symbol, expiration, trade_date, right, strike, interval_used, timestamp,
underlying_timestamp y underlying_price. No leer bid, ask, delta, IV, OHLC de
opciones ni salidas. Se permiten footers para validar schemas/intervalo/relojes;
no estadísticas de precios como sustituto de la proyección.

OI: leer symbol, expiration, trade_date, right, strike, interval_used, timestamp
y open_interest del archivo diario fijado. Todas las filas quedan en el ledger
de clasificación, incluidas las no elegibles. No consultar cotizaciones de acción.

Los seis archivos elegidos conservan timestamps ISO con separador T como
`large_string`. Fijar para Greeks el filtro lexical `>=2023-01-03T09:30:00` y
`<2023-01-03T10:30:00`, y validar después cada timestamp interpretado en ET.
Rechazar cualquier otro tipo/formato en este piloto; no autodetectar otro reloj.
Antes de leer underlying_price, leer exclusivamente la columna timestamp completa
y exigir en cada fila la gramática naive `2023-01-03THH:MM:SS[.ffffff]`, con
fracción opcional de 1 a 6 dígitos, horas/minutos/segundos válidos y sin offset.
Esta comprobación de reloj, fuera del filtro de precios, evita omisiones por
orden lexical distinto del cronológico. Registrar esa lectura en el access log.
Los parsers puros pueden normalizar aliases de zona en fixtures, pero el lector
real de estos seis archivos no los acepta como formato nativo del piloto.
Un filtro de fecha debe respetar el tipo real del timestamp. No reemplazar un
timestamp ausente por underlying_timestamp, el índice o el orden de filas. El
auditor vuelve a leer las columnas y el intervalo desde la copia sellada con un
camino separado; compartir formato o biblioteca I/O no autoriza compartir cálculos.

## LSP-003: identidad, relojes y muestras

Normalizar la identidad completa: ticker, fecha, expiración, CALL/PUT y strike
Decimal positivo finito. C/P son alias de CALL/PUT. Normalizar fechas ISO y
timestamp al instante; un campo naive se interpreta America/New_York como
convención declarada de archivo, no prueba de recepción live.

Greeks exige `interval_used=1m`, identidad del archivo y timestamp alineado a
minuto exacto. Una clave contractual/timestamp repetida falla, incluso con strike
100 frente a 100.0. Prohibido floor, nearest, deduplicación y cambio de intervalo.
Cada underlying_timestamp debe existir y ser <= timestamp de la muestra.

Construir exactamente 60 posiciones de rejilla 09:30..10:29. Una posición sin
filas queda con mask=false y motivo MISSING_SAMPLE; no se rellena. En una misma
posición, todas las filas deben coincidir en underlying_price y underlying_timestamp.
Un desacuerdo queda mask=false/CROSS_CONTRACT_DISAGREEMENT, no se escoge una fila.
Precio no finito o <=0 queda mask=false/INVALID_PRICE. Conservar esos contadores;
un primer cero SPXW no se sustituye por la muestra posterior.
Si coexisten precio inválido y desacuerdo, INVALID_PRICE tiene precedencia;
MISSING_SAMPLE se aplica solo a una posición sin filas. Esta regla es previa a
los datos y ambos caminos deben probar el caso mixto.

Para muestra válida, guardar precio Decimal serializado, timestamp de quote,
underlying_timestamp, antigüedad del subyacente y número de filas fuente. Cada
muestra hereda el SHA `sources.greeks` del objeto de su ticker; no duplica el hash
como un campo adicional por fila. El manifest relaciona ese SHA con la copia.
El número de filas es actividad de esta fuente de opciones, no volumen spot.
Los timestamps admiten como máximo precisión de microsegundos. Serializar en
ISO ET con offset; antigüedad en milisegundos como texto Decimal exacto, sin
redondear mediante float. Una máscara conserva quote_timestamp y disponibilidad,
pero price/underlying_timestamp/antigüedad son null; reason es null si mask=true.

Fijar `research_available_at = quote_timestamp + 1 minuto`. Es una demora
conservadora de investigación, etiquetada `ASSUMED_DELAY_NOT_OBSERVED_RECEIPT`;
no demuestra disponibilidad live ni vintage original. Consultar antes de esa
hora rechaza la muestra. La muestra 10:29 estará disponible a10:30.

El resultado es una serie de precios muestreados, nunca OHLC intraminuto, 60
segundos observados por minuto o IB exacto de V1R1. Este piloto no calcula rangos,
Fibonacci, retornos ni futuros targets a partir de la serie.

## LSP-004: ledger OI y unión diagnóstica

OI exige interval_used=daily, identidad de archivo y clave única por contrato;
open_interest debe ser entero finito >=0 y timestamp de la fecha de sesión.
Duplicados, identidades incompatibles o valores malformados fallan cerrado.
Clasificar en orden: timestamp>09:30 -> AFTER_OPEN; OI=0 -> ZERO_OI; resto ->
ELIGIBLE_REPORTED_PREOPEN. Conservar simultáneamente los flags de cero/tardío.

La última clase describe el reloj reportado. No asigna disponibilidad observada
ni certifica as_of prior-close: `prior_close_semantics_verified=false` en este
piloto. El adaptador futuro necesita evidencia documental y su contrato antes
de introducir estos registros en walls. No inventar una hora común de 06:30.

Informar contratos de la primera hora sin OI y contratos con OI no elegible, sin
borrarlos de la cobertura y sin construir acciones. No emitir wall snapshots.

## LSP-005: oráculo y resultado

Auditor en módulo separado; no importa productor, loader semántico ni sus
funciones de normalización/clasificación. Reconstruye muestras y ledger desde
los parquets sellados, comprueba hashes y compara objetos exactos. Un desacuerdo
es FAILED_AUDIT. El productor no corrige sus resultados después de ver al auditor.

Resultado máximo: LOCAL_SOURCE_DIAGNOSTIC_COMPLETE con auditor independiente
PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT. El informe incluye por ticker filas, muestras
válidas/enmascaradas, motivos y conteos OI. Una conclusión de calidad se expresa
por esos conteos; el nombre de estado acredita completar el diagnóstico, no
admitir un histórico económico. Un error estructural queda BLOCKED_LOCAL_SOURCE.

Persistir manifest, access log, source_diagnostic.json, audit.json y summary.json
en root nuevo. Mantener `historical_economic_admission=false`,
`original_vintage_verified=false`, economía NOT_EVALUATED,
prospectivo NOT_STARTED, technical_ready=false y promotion_approved=false.

## LSP-006: pruebas previas y cierre

Fixtures: reloj ausente; intervalo30s/5m; identidad errónea; duplicado numérico
y por zona horaria; dependencia futura; minuto ausente; precio cero/NaN;
desacuerdo entre contratos; OI cero/tardío/duplicado/malformado; acceso anticipado;
mutación de fuente sellada; resultados alterados; output existente. Un test I/O
incluye una columna bid prohibida y filas posteriores a10:30: ni productor ni
auditor deben entregarlas a los cálculos. Verificar proyección y filtro con
Parquet real sintético, no solo mocks.

No convertir un resultado negativo en otra fecha o un umbral menor. Un resultado
de diagnóstico favorable tampoco autoriza PnL. Antes de ampliar el alcance:
calendario/cobertura local por relojes verificables, contrato económico nuevo,
definición de features muestreadas, ejecución quote-sampled, costes, baseline,
ablación, métricas y separación temporal publicadas. Cualquier evidencia histórica
seguirá siendo desarrollo ya visto; esta revisión no crea un outer intacto.

Referencia I/O: [proyección por columnas en ParquetFile](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html).
