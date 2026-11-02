# Cierre de la integración sintética D

Estado: CLEAR_FINAL_IMPLEMENTATION_D_INTEGRATION_FIXTURES_ONLY.

La primera ejecución conjunta de productor, contabilidad y auditor independiente
cerró con compile0, Ruff0 y **8 pruebas aprobadas en 1,21 segundos**. Son cinco
funciones de prueba con parametrización. No se repitieron las suites cerradas de
los componentes. El revisor independiente `/root/d_integration_harness_review`
confirmó SHIP tras comprobar cierres, archivos, snapshots y proyecciones.

La ejecución partió del commit publicado
`e2d38b2cb86d587dab766052836a45cc0eb1e48a`. Los 21 pins de admisión,
snapshots, cierre y fuentes actuales coinciden en bytes/SHA y bytes Git.
No hay `failure.json`, cambios de pins ni reintentos.

| Componente | Bytes | SHA-256 |
|---|---:|---|
| Productor | 38317 | 6c8677453d08699825c4c5cc2439af6eb0f48e7433dab6dea7d812c8c07c34a7 |
| Auditor independiente | 68119 | c6c77b1e12b166796c06335621b606b03006617e3dc0a374a2bc2d489ec554d7 |
| Contabilidad | 18783 | 9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb |
| Integración | 10675 | ee549203a778545ac0ed07546135a67526b1b65fe92bb758caaad38b914c8ead |
| Harness01 | 21933 | f64f9653b80b70ce2a4fc411ba9fcba467b17758799093002435988d333253ad |

Compile PID19252, Ruff PID65120 y pytest PID26748 tienen salida retenida por
handle, código hijo/efectivo cero, CPU0, metadata_error=null, changed_pins=[]
y retry=false. Pytest: creation1793660353.229248, exit1793660360.3008645.
Los gates inicial y por hijo de RAM/free_commit/disco superaron 2GB; diez
variables de hilos valían1 y CUDA=-1. Todos los stderr están vacíos.
Compile/Ruff abarcaron sólo integración y harness; pytest sólo integración.

El recibo formal es d_revisit_integration_fixture_closure_v1/PASS_CLOSED,
1513B, SHA b3be7b6bc810ee5fa187195f85e40bd9fcae715cecd67e1cb760e1ae3afd0713.
Exit retenido de pytest:117B,
6a447ed46f98359013cfb08bf51e6f5388071c21be5beab889055bd577a499cc.

Limitación de procedencia: la salida exterior de exec_command se truncó durante
la compactación del contexto. No se conserva aquí evidencia de exit/session/chunk
del launcher raíz y **no se afirma root exit0**. Sí se conservan los tres cierres
de hijos y la escritura final de closure/recibo. El revisor consideró suficiente
esta evidencia para el cierre limitado de integración artificial. No se relanzó
el intento para reconstruir la observación exterior perdida.

Archivo externo: D:/GexResearchArtifacts/weekly_multiday_20261101/
weekly_zone_revisit_integration_fixtures_archive_01. Contiene34 payloads únicos,
353533B, exactos respecto a las fuentes y plain files. Manifest14040B:
9cd9fa65cec62c31be3a7551666140a5fbe1db586d664fee1a24427680800bff.
Recibo521B:ce61f723081aa9526458ac7aa328f827549e96ef32dff4754f61f7447ee40e64,
estado PASS_ARCHIVED_CHILD_CLOSURES_VERIFIED, root_exit/chunk=null.
Las15 proyecciones en REANUDACION_20261102/d_integration_fixtures01 son copias
exactas de13 archivos del observer y los dos metadatos del archivo.

La prueba acredita acuerdo completo de registros artificiales: CALL y costes,
PUT y bid ausente, bloqueo común hastaH2 aunque A ya haya salido, cobertura
histórica/sin geometría, y rechazo de registros alterados. No abre cotizaciones
reales ni benchmark. No demuestra rentabilidad, cobertura real ni validez futura.

Accounting10PASS, productor23PASS+32subtests, auditor19PASS+167subtests,
C69PASS y R3136PASS permanecen cerrados. Los fallos previos se conservan.
B06 sigue en su única ejecución: a23:04:20UTC PID8616/creation1793644105.584635,
sesión35709,1093/2768 STREAM_OPTION_SOURCE completos, stderr0 y exit ausente.
Todavía no hay BfullPASS, C real, D real ni PnL de revisitas. Siguiente secuencia:
cierre/auditoría/admisión B, ejecución y auditoría C, y adaptación real D para
comparar A salida por zonas, B misma entrada/qty salidaH2 y C benchmark10:35/H2.
Goal activo, selected_policy=null, promotion_approved=false.
