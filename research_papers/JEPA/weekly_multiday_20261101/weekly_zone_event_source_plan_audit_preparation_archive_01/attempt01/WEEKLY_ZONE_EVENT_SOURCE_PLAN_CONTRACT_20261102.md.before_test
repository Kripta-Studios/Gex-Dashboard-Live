# Plan de fuentes para eventos weekly entre sesiones

Estado: contrato de planificación de fuentes, anterior a valores. Esta fase A
resuelve el soporte nominal completo de una hipótesis nueva: ejecución weekly
activada por un evento de nivel observado por minuto, con geometría causal y
posible salida anterior a H2. No repite las familias cerradas de ruptura IB,
stop/trailing, delta/horizonte ni la comparación de frecuencia DAILY. No se elige
una política o configuración por los resultados2026 ya vistos.

## Alcance y separación

El producto es SOURCE_PLAN_NOT_VALUE_ADMISSION. Lee únicamente JSON de metadata
sellada y stat/lstat de rutas nominales; no abre contenido, hashes ni footers de
Parquets de mercado, arraysNPZ, candidates, labels, scores, ledgers o PnL. Hash
antes/después sólo de las autoridades compactas, contrato, código/tests y helper.
No hay entrenamiento, inferencia, replay, selección, cotización ni probabilidad.

La fase siguiente, bajo otro contrato publicado, deberá admitir hashes actuales,
footers/proyecciones y caches causales, y luego validar relojes/minutos/quotes.
Existencia o tamaño de un archivo no acredita ningún minuto válido, identidad de
fila, quote ejecutable o cobertura continua. Los SHA históricos de fuentes se
conservan como EXPECTED_UPSTREAM_PIN_NOT_CURRENTLY_REHASHED, nunca como comprobación
actual. Un stat estable tampoco prueba inmutabilidad del contenido.

La pregunta económica sigue abierta. Todos2025/2026 son SEEN_DEVELOPMENT;
selecciónnull, technical_ready=false y promotion_approved=false. Se preserva el
criterio8/8 meses completos netos positivos y septiembre parcial separado para
futuros experimentos; este plan no tiene resultado económico ni criterio8/8.

## Autoridades exactas

Raíz de metadata B=D:/GexResearchArtifacts/weekly_multiday_20261101.
Todos los archivos siguientes son JSON, con SHA256 obligatorio:

| Relativo a B | SHA256 |
|---|---|
| h2_dataset_v2_01/inventory.json | 099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12 |
| h2_dataset_v2_01/inventory_manifest.json | c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899 |
| h2_dataset_v2_01/manifest.json | bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8 |
| h2_dataset_v2_extension_2026q3_partial_01/inventory.json | f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c |
| h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json | 5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f |
| h2_dataset_v2_extension_2026q3_partial_01/manifest.json | b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b |
| h2_boundary_bridge_01/inventory.json | 599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161 |
| h2_boundary_bridge_01/inventory_manifest.json | 0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2 |
| h2_boundary_bridge_01/manifest.json | 9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86 |
| h2_boundary_bridge_01/unified_calendar.json | be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6 |

Validar schemas, status y crosspins publicados de inventories/manifests; no abrir
los restantes outputs referenciados por ellos. Las implementaciones selladas son
proveniencia, no módulos importados. El calendario unified tiene exactamente
2790filas {ticker,date,close_i},930sesiones comunes20230103–20260917, tickers
SPY/QQQ/SPXW. Sus primeras2625filas lógicas coinciden por identidad/close_i con
calendar_rows H1; las165Q3 también coinciden. Unicidad y orden se verifican por
claves, sin confiar en orden físico. H1 contiene24sesiones cortas por ticker-día,
Q3 todas completas. Sólo close_i210/390, sin inferir calendario de nombres.

## Congelación de ofertas nominales

Combinar coverage_plan H1(2625) y Q3(165). Overlay bridge exactamente sobre los
seis ticker-días20260629/20260630, que eran HORIZON_OUTSIDE_CALENDAR en H1.
No modificar las demás filas. BridgeJun29 es PLANNED para los tres, expiryJul2,
H2Jul1; Jun30 es NO_SERIES para los tres, H2Jul2. Los últimos seis ticker-días
Sep16/17 siguen HORIZON_OUTSIDE_CALENDAR. La población resultante conserva2790:
1620PLANNED,1164NO_SERIES,6HORIZON_OUTSIDE_CALENDAR.

La expiración viene de esos planes anteriores sin nueva búsqueda/reselección.
Conserva la regla upstream: mínimo expiry local1–8DTE natural con H2<expiry,
elegido desde fuentes del día de decisión, antes de mirar el futuro. Esta fase
comprueba los límites1–8DTE/H2<expiry y el vínculo al plan sellado; no pretende
reconstruir la elección mínima sin enumerar todo el universo original. No
interpreta una fuente futura existente/ausente como elegibilidad del día inicial.

Para cada identidad definir D, D+1 y D+2 exclusivamente por posición en el
calendario común; D+2 es el H2 original. Para PLANNED, generar las tres rutas:
D:/ThetaData/data_options/{ticker}/greeks/{YYYY}/{MM}/
{ticker}_{expiration}_{trade_date}_greeks.parquet.
La ruta D y D+2 debe coincidir canónicamente con entry_path/exit_path upstream.
Cada referencia conserva rol ENTRY_DAY/INTERMEDIATE_DAY/H2_DAY, trade_date,
close_i y la identidad del plan. NO_SERIES conserva el calendario pero no
inventa expiry/rutas; HORIZON conserva las sesiones posteriores disponibles
sin crear días fuera del calendario. No abrir candidatos, elegir strikes o lados.

## Inspección nominal y límites de identidad

Deduplicar por ruta absoluta canónica. Permitir sólo la raíz exacta de opciones
y plantilla de ticker/expiry/trade_date. Rechazar traversal, enlaces simbólicos,
reparse points y archivos no regulares; inspeccionar ancestros hasta la raíz.
No resolver un alias para admitirlo silenciosamente. Dos referencias nominales
al mismo archivo físico con rutas diferentes fallan cerrado. Las barras dobles
históricas se normalizan con Path; entradas que colapsan al mismo path deben
traer el mismo binding histórico o fallar por conflicto.

Por fuente registrar path, ticker, expiration, trade_date, lista completa de
referencias, expected_upstream_bindings y observación contemporánea:
exists, bytes, mtime_ns, physical_id=[st_dev,st_ino]. Ausente deja bytes/mtime/id
null. Distinguir ya inventariada upstream y nueva INTERMEDIATE_DAY sin binding.
Un missing upstream que ahora existe, o viceversa, se conserva como discrepancia
de metadata explícita; no cambia planes ni habilita valores. Diferencia de bytes
actuales frente al binding previo también se informa. Fuentes sin discrepancia
no se llaman verificadas por SHA. No se leen ni proyectan columnas de mercado.

Repetir únicamente stat/lstat al cierre y exigir observación idéntica a la inicial
para cada path; si cambia, fallo cerrado sin manifest de éxito. Esto es control
de estabilidad de metadata, no prueba de contenido. Rehash final de todas las
autoridades JSON. No sobrescribir ni adoptar output parcial tras fallo.

## Salidas y recuentos

Nueva raíz exclusiva B/weekly_zone_event_source_plan_01. No modificar artefactos
anteriores. Salidas exactas:
- entry_plan.jsonl:2790filas ordenadas(date,ordenSPY/QQQ/SPXW), sin outcomes.
- weekly_sources.jsonl:rutas únicas ordenadas lexicográficamente, referencias
  completas y metadata;4860referencias desde1620planes×3, ningún join incompleto.
- summary.json:recuentos porstatus/ticker/año/rol, fuentesúnicas presentes/ausentes,
  bytes nominales agregados, número nuevo frente a inventarios previos,
  discrepancias y flags. No sumar bytes por referencia como almacenamiento único.
- manifest.json:schema weekly_zone_event_source_plan_manifest_v1, status
  SOURCE_PLAN_NOT_VALUE_ADMISSION, pins de inputs/código/tests/contrato y los
  tres outputs anteriores, flags raw_values_read=false, raw_files_hashed=false,
  parquet_footers_read=false, arrays_read=false, outcomes_read=false,
  fit_performed=false,inference_performed=false,replay_performed=false,
  selected_policy=null,technical_ready=false,promotion_approved=false.

No se incorpora todavía metadata de caches H1/Q3 a esta autoridad de valores.
La existencia previa de esos caches facilita la fase posterior, que deberá
admitir por separado su índice y hashes, sin reutilizar el oracle como señal.

## Implementación, fixtures y ejecución

Archivos nuevos build_weekly_zone_event_source_plan.py y
 test_build_weekly_zone_event_source_plan.py. Librería estándar; sin importar
productores, modeladores, pyarrow/numpy/pandas ni leer Parquet/NPZ. Funciones puras
para validar calendarios, overlay y rutas; adaptador stat separado e inyectable.
La CLI real exige --execute-reviewed-plan y hashes propios/tests/contrato,
raíces fijas y ausencia de output. Fixtures usan autoridades artificiales aisladas.

Publicar este contrato y revisión antes de fixtures. Probar: calendario duplicado
/desigual, shortdays, H2 por sesiones, overlayexacto y fuera de alcance, finales,
NO_SERIES,1–8DTE/expiry>H2, rutas D/D2alteradas, conflicto de pins, ausencia del
intermedio sin reselección, tamaño/presencia cambiados, reparse/hardlink/traversal,
stat cambiante al cierre y ninguna lectura de contenido de mercado. La prueba de
no-lectura debe hacer fallar cualquier intento de abrir un path de mercado.

CPU[0], diez variables de threads1, helper oficial
level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py
SHA3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046,
RAM/commit libres>=2GB antes de hijos. Observación persistida también si rechaza.
Fixtures con snapshots previos/logs/exit retenido, sin retries automáticos;
fallo se preserva y root decide corrección. Código/tests/review/binding/launcher
publicados y remoto verificado antes de único runtime. Observer nuevo
B/weekly_zone_event_source_plan_observer_01; Popen oculto/listargs, identidad,
handle retenido, logs y exit efectivo. Auditoría independiente posterior sólo
metadata: reconstruye2790planes/4860refs y contrasta conteos/crosspins; nunca
abre valores para este plan. Un PASS de metadata no significa rentabilidad.
