# IB interrumpido: revisión offline y preservación

Fecha: 2026-09-19. Estado inicial: PREDECLARED_OFFLINE_REVIEW.

El usuario solicita revisar el repositorio mediante subagentes y continuar el
trabajo. Esta etapa resuelve evidencia ya capturada; no repite peticiones, no
amplía ventanas y no abre economía. Especificación y código deben publicarse
antes de ejecutar la reconstrucción offline descrita aquí.

## Hechos de entrada y alcance fijo

- HEAD de investigación inspeccionado: `4eb445368bb82888569f43842f5d6ae76ef93c9f`.
- Piloto 23 iniciado desde `60550cd1e783167a79134fcfb698e6ffd0d23f34`.
- Root original: `D:/GexResearchArtifacts/multiscale_v1r1/ib_source_pilot_20260918_01`.
- SPXW/SPY tienen `response.bin`, `manifest.json` e `initial_balance.json`.
- QQQ tiene `response.bin`, sin manifest de captura ni resultado de componente.
- No existe summary final ni se observó un proceso activo de ese piloto.

No se conoce la causa de la interrupción ni la completitud del cuerpo QQQ. El
tamaño de un archivo y su extensión no demuestran que la respuesta HTTP terminase.
No atribuir el incidente al proveedor sin evidencia adicional.

## Revisión autorizada

OFF-001: leer el conjunto de archivos existentes bajo handles coherentes Win32,
registrar hashes/tamaños y conservar copias de evidencia en un root nuevo. No
escribir, reparar, completar ni crear un summary en el root original. La ausencia
de archivos se documenta explícitamente.

OFF-002: verificar el run_manifest y las copias de código/especificación con sus
hashes. Contrastar el código de auditor ejecutado con la copia sellada del run;
no reinterpretar su resultado con una revisión distinta. Verificar también la
especificación actual, el código de esta revisión y el runtime utilizado.

OFF-003: SPXW y SPY deben tener manifest `complete=true`, HTTP 200, identidad y
parámetros exactos del piloto 23, tamaño y SHA correspondientes al cuerpo. El
auditor `audit_theta_ib_source_v1.reconstruct` reconstruye por csv/Decimal las
60 barras, reparación, disponibilidad, IB y Fibonacci desde cada respuesta
sellada; compara exactamente con `initial_balance.json`. No importar cálculos
del productor para verificar esos cálculos.

OFF-004: QQQ se cataloga como `UNSEALED_BODY_COMPLETENESS_UNKNOWN`. Calcular
hash y tamaño de los bytes existentes no los admite como fuente. No parsear
CSV, construir barras, deducir precios, completar un manifest HTTP retrospectivo
ni repetir una GET para QQQ. Si aparecen nuevos archivos inesperados, detener y
registrar cambio de estado, no adaptar el alcance automáticamente.

OFF-005: root de salida nuevo:
`D:/GexResearchArtifacts/multiscale_v1r1/ib_offline_review_20260919_01`.
Usar staging y rename dentro del mismo volumen. Conservar evidencia de fallo;
una interrupción no genera un resumen positivo. No sobrescribir outputs.

## Resultado y límites

El estado global, incluso si ambos componentes completos pasan, será
`INCOMPLETE_IB_PILOT`. Cada uno puede obtener `PASS_COMPONENT_OFFLINE_AUDIT`.
QQQ permanece no admitido. Ante discrepancias de fuente/código/reconstrucción,
el cierre debe identificar el fallo y no publicar un PASS del componente.

En todos los casos:

```text
original_vintage_verified = false
historical_economic_admission = false
economic_evidence_state = NOT_EVALUATED
prospective_validation_state = NOT_STARTED
promotion_approved = false
```

Persistir `catalog.json`, `audit.json` y `summary.json`, con runtime, hashes del
código/spec, tiempos y alcance. Publicar únicamente evidencia compacta y las
referencias con hashes; no raw de mercado. Los componentes del contrato 22 y el
intento original invalidado conservan sus bytes y estados.

## Pruebas previas

Fixtures sin red: root parcial esperado; cuerpo cuyo hash no coincide; parámetros
o código cambiados; manifest ausente/forjado; resultado de barra alterado con
checksums actualizados; prueba de que QQQ nunca llega al parser; output existente
rechazado. La revisión no debe importar ni ejecutar el capturador HTTP.

## Frontera posterior

Este cierre no habilita el CLI económico histórico. D1–D5, prior-close, prefijo
completo, snapshots de walls y cotizaciones de entrada/salida todavía necesitan
admisión por alcance bajo contrato de fuente reconstruida. La captura incompleta
QQQ no se reintenta bajo el contrato 23, que prohíbe retries. Cualquier nueva
captura necesita una autoridad y un presupuesto explícitos antes de ejecutarse.
