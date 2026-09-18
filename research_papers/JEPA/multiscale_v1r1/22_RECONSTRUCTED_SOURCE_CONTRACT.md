# THETA_RECONSTRUCTED_SOURCE_V1 — admisión por componente, sin economía

Autoridad: continuación explícita del usuario tras el informe 21. Revisión nueva
de fuentes, no modificación de V1/V1R1 ni restauración del intento invalidado.
Objetivo inmediato: transformar las seis respuestas selladas del piloto 19 en
una primera barra y un ledger de elegibilidad OI con linaje verificable.
Publicar este documento y el código antes de leer de nuevo los valores.

## Alcance y significado

SRC-001: solo los seis cuerpos y manifests cuyo catálogo está publicado en
600c959b, fecha 2022-08-01. Cero red, cero parquet antiguos, cero modelos o
payoffs. Root nuevo: D:/GexResearchArtifacts/multiscale_v1r1/source_components_20260918_01.
No seleccionar una fecha alternativa si falla. No sobrescribir respuestas.

SRC-002: la fuente es la reconstrucción histórica del proveedor recibida en 2026.
`provider_event_timestamp`, `reported_available_at`, `received_at` y
`materialized_at` son campos distintos. `original_vintage_verified=false`.
Un PASS se denomina PASS_RECONSTRUCTED_SOURCE_COMPONENTS: acredita identidad,
transformación y dependencias según los relojes reportados, **no** certifica
qué revisión vio el mercado originalmente ni paridad live. La clasificación del
histórico antiguo sigue UNVERIFIABLE_FOR_CAUSAL_REPLAY. Esta capacidad no abre
el gate económico V1R1. Una futura evaluación con reconstrucciones necesita su
propio contrato que explicite esta limitación antes de modelos/outcomes.

SRC-003: productor y auditor capturan/verifican el mismo conjunto de bytes bajo
handles Win32 que impiden escritura/borrado, y luego leen copias. Se valida SHA,
tamaño, petición/identidad y version=1 frente al catálogo publicado. Un cambio
en una dependencia, código o manifest invalida el resultado. Escritura en root
nuevo, staging y rename; una interrupción no puede dejar un summary PASS.

## Primera barra

BAR-001: [09:30:00,09:31:00) ET, etiquetas por inicio, exactamente los 60 segundos
del intervalo presentes. La fila 09:31:00 pertenece a la barra siguiente y no
contribuye. No floor de cotizaciones, deduplicación, relleno temporal ni consultas
posteriores. Duplicar una clave contractual/segundo falla. En cada segundo,
precios/tiempos del subyacente deben ser concordantes entre contratos; divergencia
se registra como bloqueo, sin elegir una quote conveniente.

BAR-002: OHLC first/max/min/last por timestamp reportado; tick_count es el número
de filas de opciones que aportan a la barra, un proxy de actividad de esta fuente,
no volumen ni número de operaciones del subyacente. Aritmética de precios Decimal,
serialización decimal exacta. Registrar número de segundos y contratos aparte.
Todo underlying_timestamp debe ser <= quote timestamp. Ninguna dependencia de
la barra puede situarse en o después de 09:31. La disponibilidad reportada de
la barra completa es 09:31, nunca 09:30.

BAR-003: única reparación permitida: SPXW_INITIAL_ZERO_BAR, primera barra con
OHLC parcialmente cero/inválido y close finito positivo. Sustituir exclusivamente
campos inválidos por el close de esa misma barra, como el caso local autorizado.
Conservar OHLC previo, filas/instantes exactos que originaron el close, campos
reparados y disponibilidad 09:31. Prohibir bfill/ffill entre barras, otros tickers
y close inválido. Un precio inválido fuera del primer segundo inicial se rechaza.
El auditor verifica disponibilidad contra cada endpoint de uso; pedir 09:30:59
debe fallar. El resultado es barra reparada, nunca OHLC original observado.

## OI por registro

OI-001: identidad exacta símbolo/expiración/strike/derecho, única. Entero >=0,
timestamp timezone-aware de la fecha de sesión; sin moverlo a 06:30. Semántica
de as_of = cierre de la sesión XNYS anterior, según documentación del endpoint,
con referencia documental explícita y original_reception_observed=false.
Usar exchange_calendars 4.12 y sellar la sesión anterior elegida.

OI-002: aplicar la elegibilidad **ya existente** en levels.py: OI>0 y tiempo
reportado <=09:30. Registrar todos los demás con motivo ZERO_OI o AFTER_OPEN;
ninguno se imputa o entra en walls. Esta clasificación no cambia el fallo previo
del chequeo universal del piloto 19. La falta de OI en una quote se mantiene
MISSING_OI. No extrapolar una muestra de contratos al universo completo.

## Verificación y cierre de este componente

AUD-001: auditor separado, csv/Decimal/datetime; no importar cálculos del productor.
Reconstruir barra, repair, disponibilidad y todos los registros OI desde copias.
Igualdad exacta de valores, identidades, timestamps, motivos y dependencias.
Fixtures: cierre futuro, hueco de segundo, duplicado nativo, desacuerdo entre
contratos, primer cero permitido, cero posterior/otro ticker prohibido, OI tardío
positivo/cero, OI duplicado, mutación tras captura, uso anticipado de la barra y
alteración de reparación o clasificación OI con hashes recalculados.

Salida: manifests, first_bars.json, oi_eligibility.json, lineage.json, audit.json
y summary.json. El informe separa integridad, reconstrucción por componente,
vintage original, admisión económica y promoción. Economy NOT_EVALUATED;
historical_economic_admission=false; promotion_approved=false.

Fuentes primarias consultadas:
- https://docs.thetadata.us/operations/option_history_greeks_first_order.html
- https://docs.thetadata.us/operations/option_history_open_interest.html
