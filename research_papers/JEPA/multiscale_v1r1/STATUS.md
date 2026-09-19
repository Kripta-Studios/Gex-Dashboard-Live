# Backend real verificado; fuentes sin admisión histórica

### Checkpoint 2026-09-19 — piloto local auditado, economía aún cerrada

Autoridad: research_papers/JEPA/local_snapshot_v1/02_SOURCE_PILOT_RESULT.md.
Desde 2755d198, una ejecución sin API de seis parquets Greek/OI del20230103:
LOCAL_SOURCE_DIAGNOSTIC_COMPLETE y PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT,
mismatch0. Muestras válidas SPXW/SPY/QQQ59/60/60; SPXW09:30 queda INVALID_PRICE
enmascarado, sin imputación. OI positivos reportados preapertura269/168/126;
OI cero19/74/60; faltan dos contratos OI en SPY y dos en QQQ, conservados.
No se abrió bid/ask/delta/IV, PnL o entrenamiento de esta familia.

Seis originales y seis copias rehasheados. Tests nuevos56 y suite completa185
PASS; Ruff/compile/revisión PASS. La demora de1min es supuesto de investigación,
no recepción observada; prior_close_semantics_verified=false. Este piloto no
admite todas las sesiones ni prueba la paridad live. No repetirlo o rellenarlo.

La API no está disponible por instrucción del usuario: solo D:/ThetaData local.
Siguiente frontera: contrato de cobertura multisesión y significado OI, luego
features muestreadas y contrato económico nuevo antes de modelos/outcomes.
El runbook local01 contiene dependencias. V1R1 mantiene INVALIDATED/FAILED_AUDIT;
economía nueva NOT_EVALUATED, technical_ready=false, prospectivo NOT_STARTED,
promotion_approved=false. No hay modelo rentable operando acreditado; producción,
bróker y VPS permanecen intactos. Los documentos de captura son historia cerrada.

### Checkpoint 2026-09-19 — revisión local nueva autorizada, antes de valores

El usuario autoriza una revisión nueva de snapshots locales con reloj verificable:
USER_LOCAL_SNAPSHOT_RESEARCH_20260919. Contrato:
research_papers/JEPA/local_snapshot_v1/00_SOURCE_PILOT_CONTRACT.md; runbook01.
Seis archivos locales Greek/OI 0DTE del 20230103, SPXW/SPY/QQQ. Primera hora
de underlying_price muestreado, sin leer bid/ask/delta ni payoffs. Productor y
auditor separados, fixtures y publicación antes del único piloto. Aún sin valores
reales de esta familia ni entrenamiento. No API, credenciales o descargadores.

Censo descriptivo de 6.066 schemas 0DTE 2024–2026: 3.032 Greeks/IV sin reloj de
quote ni índice/campo alternativo; OHLC no tiene bid/ask. En 2023, los 750 Greeks
0DTE inspeccionados sí tienen timestamp. Eso permite estudiar una fuente local
nueva, no admitir el histórico ni sustituir relojes. El censo no sella raw.
V1R1 sigue cerrado; economía NOT_EVALUATED, technical_ready=false,
prospectivo NOT_STARTED, promoción false. Solo el piloto del contrato00 está
definido; cualquier evaluación económica requiere otro contrato previo.

### Checkpoint 2026-09-19 — IB auditado por componente; continuación solo local

Autoridad: multiscale_v1r1/27_OFFLINE_AUDIT_AND_QQQ_TRANSPORT_RESULT.md.
Desde 16270c44: auditoría offline SPXW/SPY PASS, 60 barras cada uno; QQQ antiguo
82.837.504 bytes sin sello, no parseado. Global INCOMPLETE_IB_PILOT, cero GET
offline; 13 originales y sus copias rehasheados sin diferencias.

La GET única QQQ autorizada se consumió: WinError10060, 21,210 s, cero bytes,
sin HTTP ni response.bin. BLOCKED_QQQ_IB_CAPTURE, sin retry ni reconstrucción.
El usuario comunica DESPUÉS que ya no dispone de API ThetaData: trabajar solo
con descargas D:/ThetaData/data_options y data_underlying_derived. No llamadas,
reintentos, status, nuevas descargas ni restauración del Terminal. Las fuentes
anteriores se preservan; esta instrucción sustituye cualquier ruta API pendiente.

Suite 129 tests PASS; Ruff/compile/diff-check PASS. Identidad contractual/delta
corregidas con fixtures; hallazgo15m retirado porque NUM-001 ya fija la regla.
Siguiente: evaluación LOCAL_ONLY de fuentes existentes; cualquier cambio de
OHLC intraminuto a precios muestreados necesita contrato nuevo antes de outcomes.
Histórico original INVALIDATED/FAILED_AUDIT; economía nueva NOT_EVALUATED;
technical_ready=false, prospectivo NOT_STARTED, promotion_approved=false.
No modelo de mercado rentable acreditado. Producción/VPS/órdenes intactos.

### Checkpoint 2026-09-19 — revisión paralela y cierre IB offline preejecución

Cinco subagentes revisaron fuentes, motor, features/SSL, registro científico y
ejecución desde 4eb44536. Suite inicial97 PASS. El componente22 tiene PASS
limitado a tres barras/866 OI; catálogo23 artefactos rehasheado, mismatch0.
Su evidencia compacta se incorpora sin modificar los archivos originales.

El piloto23 quedó interrumpido: SPXW/SPY con respuestas y resultados sellados;
QQQ tiene82.837.504 bytes sin manifest, completitud desconocida y sin summary
global. No se observó proceso activo. Autoridad nueva24_IB_INTERRUPTED_OFFLINE_REVIEW_SPEC:
verificar offline dos componentes, catalogar QQQ sin parsearlo y cerrar en root
nuevo como INCOMPLETE_IB_PILOT. Publicar código/spec antes de ejecutar; no GET.

La revisión25 identifica adaptación histórica/OI y entrenador SSL pendientes.
NUM-001 ya fija el alcance de estados15m; se retira ese hallazgo inicial.
Se corrigen con fixtures identidad contractual
numérica y delta de entrada en productor/auditor. No cambia contrato económico.
Contrato26 autorizado por el usuario: USER_QQQ_SINGLE_GET_20260919, una GET QQQ
nueva con límites fijos, aún no ejecutada. Publicar antes de capturar; no retry.
Sin entrenamiento/PnL históricos nuevos,
economía NOT_EVALUATED, technical_ready=false, prospectivo NOT_STARTED,
promotion_approved=false. Intentos antiguos y producción permanecen intactos.

### Checkpoint 2026-09-18 — 72 LightGBM reales auditados; piloto de fuentes cerrado

Autoridad: research_papers/JEPA/multiscale_v1r1/21_REAL_BACKEND_AND_SOURCE_REPORT.md.
Desde d86aac9a, un fold técnico sintético completó 48 LightGBM A/B y 24 de ablación,
matrices completas 92.048/488, freeze antes de payoff test y 72 refits independientes
exactos. PASS_REAL_BACKEND_SYNTHETIC_FOLD; 27.504 payoffs reconstruidos, mismatch0.
2.152,748 s E2E, pico RSS 2.107.822.080 bytes. 71 tests/Ruff/compile PASS.
No equivale a 18 folds históricos ni a rentabilidad demostrada; las seis plantillas
artificiales tienen baja entropía. El E2E previo con dobles conserva su modalidad.

El usuario confirma que no hay originales/backups fuera de D:/ThetaData. Se leyeron
options_bulk.py y script4_underlying_from_options.py como texto. Specs18/19/20
publicadas antes de diez GET de metadatos, seis capturas de fuente 20220801 y un
join offline. Raw nuevo y auditor independiente preservados. Ningún payoff real.
Las 29 ausencias de 2022 preceden a expiraciones martes/jueves de SPY/QQQ; las tres
fechas de abril2026 sí figuran en el catálogo quote. No modificar los 32 casos viejos.
Greeks del primer minuto 1s pasan checks reportados; SPXW inicia cero hasta09:30:01.
OI contiene16/24/12 filas tardías SPXW/SPY/QQQ y falla el check universal preapertura.
Todas esas filas tardías tienen OI cero; el join independiente no detecta positivos
tardíos. OI positivo temprano + Greek válido:179/199/162. Esto no admite la sesión.
La reparación script4 puede depender del close de la propia barra: primer positivo
no identifica el valor sustituto antiguo. No hubo reparación o resample real.

Los 18 artefactos terminales anteriores conservan hashes. Original sigue INVALIDATED/
FAILED_AUDIT; tres logs ORIGINAL_EVIDENCE_NOT_RECOVERED. Histórico sin admitir,
economía NOT_EVALUATED; prospectivo NOT_STARTED; technical_ready=false; promoción false.
Las seis peticiones del piloto están consumidas: no repetir/ampliar por los resultados.
Siguiente frontera: contrato nuevo de fuente/transformación, admisión por alcance y
piloto técnico publicado antes de PnL. No reabrir el CLI histórico ni familias cerradas.
Producción, órdenes, servicios y VPS intactos. Este checkpoint sustituye acciones
pendientes anteriores, conservando todas las evidencias y sus límites.
