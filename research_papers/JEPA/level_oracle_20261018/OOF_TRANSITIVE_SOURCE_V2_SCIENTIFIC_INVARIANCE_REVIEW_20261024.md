# V2: revisión estática de invariancia científica

24 de octubre de 2026. **CLEAR**, limitado a diff/AST y hashes del código.
No es revisión completa de admisión ni autorización runtime. La admisión la
revisa separadamente monthly_resume. No ejecuté tests, módulos científicos,
preflight o valores de mercado; los resultados del autor no son pruebas propias.

Original: `26967e10c6b81cd5b84d7939bf6d0c81037934165daa91847d7ffd25de16ff57`.
V2 final: `213eb744b8e295688622955187227df66a56f9121252bd765b7054324e4cceae`.
Tests asociados: `ac1a1e43f7bcc553c7f06af67f0efe6203f515eb0fdc9d2db7c2c0bbf7c5f2d3`.
Los tres SHA se comprobaron antes y después de esta lectura.

Veintidós nodos originales conservan exactamente su AST, incluidos phases,
correction_closure, replay_closure, completed_prefix, pipeline_result, inventory,
starts/receipts y validación del árbol de control. Request.source también es
idéntico. El cuerpo de pipeline coincide exactamente tras normalizar sólo dos
literales OOF_PIPELINE_V2 a V1 y retirar las dos claves source_admission_sha256
de sus contratos. No se normalizó ninguna operación económica ni otra expresión.

PINS, MONTHS, HISTORY, MODES, GLOBAL_LOCK y MIN_FREE son idénticos. Los cuatro
pins científicos se comprobaron contra bytes locales; las dependencias del
adaptador (seis) y replay (ocho) coinciden con la autoridad publicada original.
Las llamadas a adapter/evaluator son las mismas. Por tanto, las doce fases,
cutoffs, umbral cero, calibración, scheduler, costes y payloads de recibos
mantienen su lógica para los inputs que superen la nueva admisión.

Los cambios funcionales están en Request, absolute, verify_map y cinco helpers
de admisión de rutas/identidad/metadata. No se afirma igualdad del conjunto de
inputs admitidos: ésa es precisamente la reparación técnica y requiere la otra
revisión. EXTRA_CODE referencia V2 y sus documentos; el mapa runtime pasa a
18 dependencias. No se debe reutilizar un supervisor que exija las 17 originales
ni relajar su igualdad para aceptar V2.

El [JSON de evidencia](OOF_TRANSITIVE_SOURCE_V2_SCIENTIFIC_INVARIANCE_REVIEW_20261024.json)
contiene los mapas y las comparaciones exactas. No hay hallazgos científicos
abiertos en estos bytes. OOF01 conserva su fallo; cualquier nueva ejecución
requiere autoridades operativas, revisión y publicación separadas.
