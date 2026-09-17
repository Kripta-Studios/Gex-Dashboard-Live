# Backend real y piloto de fuentes ThetaData

El piloto de fuentes terminó y sus diagnósticos fueron reproducidos por un auditor
independiente. El fold sintético con 72 regresores LightGBM reales terminó con
PASS_REAL_BACKEND_SYNTHETIC_FOLD y 72 refits independientes exactos. No hay un
modelo demostrado rentable en mercado. Economía histórica NOT_EVALUATED, prospectivo
NOT_STARTED, technical_ready=false y promotion_approved=false.

## Fuentes y acceso realizado

El usuario confirmó que D:/ThetaData contiene toda la evidencia local disponible
y señaló options_bulk.py y script4_underlying_from_options.py como ejemplos de
ThetaData. Ambos se leyeron como texto, sin importarlos ni ejecutarlos. Se revisó
la documentación oficial y se utilizó el terminal ya configurado, sin modificar
su servicio, configuración o credenciales.

Las especificaciones 18/19/20 se publicaron antes de sus respectivas lecturas.
Se hicieron diez GET de metadatos y exactamente seis GET de valores de fuente,
sin retries, fallback o ampliación por los resultados. Los seis corresponden a
2022-08-01, SPXW/SPY/QQQ: primer minuto Greeks first_order a 1 segundo, version=1,
y OI del día. No se descargó el resto de la sesión, ni se construyeron barras,
IB, walls, features, scores, acciones o PnL sobre esos valores. No se leyeron
valores de los parquet antiguos. Cada respuesta conserva bytes, parámetros,
hashes y tiempos de consulta/recepción; estos últimos no acreditan recepción
original en 2022 ni ausencia de revisiones del proveedor.

El catálogo no lista ninguna de las 29 expiraciones ausentes de SPY/QQQ de 2022.
Son martes/jueves anteriores a los nuevos vencimientos de noviembre de ese año.
La explicación estructural concuerda con los avisos oficiales enlazados en
[la revisión API](18_THETADATA_API_REVIEW.md). Para 2026-04-01, 2026-04-09 y
2026-04-15, las seis combinaciones SPY/QQQ sí tienen fecha de cotización 0DTE.
Eso no demuestra cobertura completa de Greeks ni admite los archivos antiguos.
Las 32 fechas/122 ausencias siguen siendo las del inventario original, dentro
de sus 973 sesiones completas; no se suman como fechas adicionales.

## Resultado del piloto de admisión

| Fuente 2022-08-01 | SPXW | SPY | QQQ |
|---|---:|---:|---:|
| Filas Greeks del minuto | 19.886 | 18.666 | 14.396 |
| Contratos Greeks | 326 | 306 | 236 |
| Subyacente inicial cero/inválido | 326 | 0 | 0 |
| Primer precio positivo, ET | 09:30:01 | 09:30:00 | 09:30:00 |
| Filas OI | 324 | 306 | 236 |
| OI con timestamp posterior a apertura | 16 | 24 | 12 |
| De esos registros, OI positivo | 0 | 0 | 0 |
| OI positivo temprano y Greek válido | 179 | 199 | 162 |

Los tres Greeks pasan los controles reportados de schema, identidad y reloj:
sin duplicados, filas fuera de ventana ni underlying_timestamp posterior a quote.
Los tres OI fallan el chequeo de que **todas** las filas estén disponibles antes
de 09:30. El auditor certifica esa conclusión, no una admisión positiva.

El diagnóstico offline fijado en 20 reconstruyó los conteos por separado con
pandas y csv/Decimal: todos los OI tardíos son cero. El builder ya exigía OI
positivo y disponible antes de abrir; no se introdujo un filtro nuevo. SPXW
tiene además dos contratos con Greek válido sin OI. No se imputó ningún OI,
se adelantó su timestamp ni se convirtió el fallo del piloto en PASS.
Los conteos positivos tempranos delimitan una muestra; no admiten toda la fecha
ni todo el histórico, y no prueban paridad live.

script4 puede reparar OHLC parcialmente inválido con el close de la propia barra.
Por eso el primer precio positivo a 09:30:01 no identifica por sí solo el precio
sustituto del archivo antiguo. Una transformación nueva necesitaría conservar
el origen del close y esperar a su disponibilidad al terminar el minuto.
download_spot aplica otro orden de filtrado/agregación. No se atribuyó a cada
archivo antiguo una transformación sin evidencia y no se sobrescribió raw.

## Motor, pruebas y frontera pendiente

El código del backend real y su auditor se publicaron en d86aac9a antes de
ejecutar. El perfil 17 usa un fold técnico enero 2025: 600 filas train, 468
selection y 78 test; matrices completas de 92.048/488 columnas y seis plantillas
sintéticas. Se ajustan 24 modelos A, 24 B y 24 de ablación con parámetros V1R1.
El freeze precede a la generación de payoffs test. El auditor reconstruyó
features, dinero y selección y refitó los 72 modelos de forma independiente.
Resultado: PASS_INDEPENDENT_REAL_BACKEND_SYNTHETIC_AUDIT, seis matrices,
27.504 payoffs reconstruidos, un winner y cero discrepancias. Modelos y vectores
de predicción se reprodujeron exactamente. Winner del fixture: A / USD 0.
Runtime: Python 3.14.2, LightGBM 4.6.0, NumPy 2.3.5 y pandas 2.3.3.

Tiempo E2E medido: **2.152,748 s**; auditoría incluida: **1.038,521 s**.
Pico RSS observado a intervalos de 50 ms: **2.107.822.080 bytes**, aproximadamente
1,96 GiB. El presupuesto de proceso declarado es 24 GiB; histogram_pool_size no
limita toda la RAM. Construir las seis plantillas tardó 46,694 s y las matrices
1,894 s. Fit incluye bins; guardado/carga/predicción están medidos por modelo en
sus manifests. Estos tiempos de seis estados de baja entropía no garantizan los
recursos del histórico ni equivalen a los 18 folds con LightGBM reales.
El catálogo posterior registra **193 archivos / 542.365.152 bytes** para el run
y los chequeos suplementarios. Suma de fits A/B/ablación: 364,383 / 324,238 /
1,796 s. No incluye en esas tres sumas los refits del auditor. El catálogo de
fuentes y metadatos conserva otros 39 archivos / 8.824.529 bytes. Son tamaños
medidos de esos roots; no un presupuesto de todas las copias del proyecto.

Resultados exclusivamente del fixture, iguales para cada ticker SPXW/SPY/QQQ:

| Política artificial | Trades por ticker | WR base/adverso | PF base/adverso | USD base/adverso |
|---|---:|---:|---:|---:|
| Primario | 13 | 100% / 100% | infinito / infinito | 655,20 / 629,20 |
| Ablación | 13 | 53,85% / 53,85% | 1,1855 / 1,0943 | 55,20 / 29,20 |
| Baseline | 13 | 46,15% / 46,15% | 0,8368 / 0,7724 | -57,80 / -83,80 |

La señal se diseñó para ser aprendible y distinta de los controles sin niveles.
Estos números prueban ese escenario artificial, no una ventaja económica de
Fibonacci o walls en el mercado. Los 18 folds previos siguen identificados como
modelos dobles; no se rebautizan como regresores reales por este resultado.

Suite sintética completa: **71 tests PASS en 80,62 s**, Ruff y compile PASS.
Incluye los cinco tests nuevos del backend real y once del piloto de fuente.
Las pruebas no abren datos ThetaData durante importación o recogida.

Tras el PASS, se rechazaron dos perturbaciones en memoria: texto de modelo y
threshold ganador. Los archivos originales y sus hashes permanecieron intactos;
el rechazo provino de las comparaciones semánticas. Este chequeo suplementario
usó dobles que cargan modelos guardados y reutilizó las reconstrucciones ya
auditadas de tensor/payoffs: **no** son otros 72 entrenamientos reales. Su
[informe](real_backend_evidence/fault_checks.json) identifica esa modalidad.

El intento run_20260917_01 permanece INVALIDATED/FAILED_AUDIT. Los tres logs
originales siguen sin recuperarse. El snapshot documental nuevo y estas nuevas
respuestas no restauran los bytes ni la procedencia del intento antiguo.

Para avanzar sobre mercado se necesita una especificación nueva de fuentes y
transformación, admisión por alcance con auditor positivo, adaptador histórico,
presupuesto del workload real y piloto técnico publicado antes de abrir PnL.
No basta con recuperar una muestra ni con entrenar modelos sobre fixtures.
No se reabre el CLI histórico cerrado, se promociona un comparador ni se cambia
el contrato V1R1 por los hallazgos. SSL/RANGE completos siguen fuera del circuito
básico. Producción, órdenes, servicios y VPS no se modificaron.

## Evidencia

- [Captura y auditoría de seis fuentes](api_intake_evidence/source_pilot_summary.json).
- [Diagnóstico independiente de OI](api_intake_evidence/oi_diagnostic_summary.json).
- [Catálogo de 39 artefactos de fuente y metadatos](api_intake_evidence/api_artifact_catalog.json).
- [Diagnóstico del catálogo de expiraciones](api_intake_evidence/metadata_diagnosis.json).
- [Resultado del backend real](real_backend_evidence/summary.json).
- [Auditoría independiente de 72 refits](real_backend_evidence/audit.json).
- [Métricas exclusivamente sintéticas](real_backend_evidence/metrics.json).
- [Catálogo de modelos, matrices y demás artefactos](real_backend_evidence/artifact_catalog.json).
- [Tests y preservación de 18 artefactos terminales](api_intake_evidence/verification.json).

Los cuerpos de mercado permanecen en D:/GexResearchArtifacts/multiscale_v1r1,
en roots theta_metadata_20260918_01, theta_source_pilot_20260918_01 y
theta_oi_diagnostic_20260918_01. El E2E está en real_backend_20260918_01.
Git contiene evidencia compacta y referencias
con hashes, sin copiar raw, matrices o grandes modelos.
