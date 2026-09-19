# Cierre de la revisión y cambio a fuentes locales

Fecha: 2026-09-19. Código publicado antes de ejecutar:
`16270c44468ef511c65220b385ac2a28d6d81e81`.

## Autoridad vigente: no hay API disponible

Después del intento único QQQ, el usuario comunica que ya no dispone de acceso
a la API ThetaData. El trabajo siguiente queda limitado a lo descargado en
`D:/ThetaData`, en particular `data_options` y `data_underlying_derived`.
No probar endpoints, renovar peticiones, arrancar Terminal, descargar datos ni
proponer una restauración del acceso como requisito de continuación. Conservar
los artefactos anteriores como evidencia; no presentarlos como capturas nuevas.

Esta instrucción sustituye la ruta de recuperación por API que podía deducirse
de documentos anteriores. La autorización `USER_QQQ_SINGLE_GET_20260919` se
consumió y no permite otro intento. Los contratos 19, 23 y 26 permanecen como
registro de su alcance y resultado, no como tareas pendientes de ejecución.

## Resultado de la auditoría offline 24

Root nuevo: `D:/GexResearchArtifacts/multiscale_v1r1/ib_offline_review_20260919_01`.
Duración: 91,930 s. Peticiones de red: cero. El auditor independiente reconstruyó
las fuentes selladas SPXW/SPY del piloto 23 sin importar sus cálculos productores.

| Fuente | Bytes anteriores | Auditoría | Alcance |
|---|---:|---|---|
| SPXW | 191.842.449 | PASS_COMPONENT_OFFLINE_AUDIT | 60 barras e IB exactos |
| SPY | 174.488.410 | PASS_COMPONENT_OFFLINE_AUDIT | 60 barras e IB exactos |
| QQQ | 82.837.504 | UNSEALED_BODY_COMPLETENESS_UNKNOWN | Copia y hash; sin parser |

Estado global: `INCOMPLETE_IB_PILOT` con auditoría `PASS_SEALED_COMPONENTS_ONLY`.
Los dos PASS no admiten QQQ, una sesión conjunta, D1–D5 ni economía.
El rehash posterior confirmó los 13 documentos originales y sus 13 copias.
No se añadió un manifest a QQQ antiguo ni se modificó su respuesta.

Evidencia versionada: [summary](ib_review_evidence/summary.json),
[audit](ib_review_evidence/audit.json), [catalog](ib_review_evidence/catalog.json)
y [publicación previa](ib_review_evidence/publication.json).

## Resultado de la solicitud única 26

Root nuevo: `D:/GexResearchArtifacts/multiscale_v1r1/qqq_ib_recovery_20260919_01`.
Inicio: 2026-09-19 08:51:53,867 UTC. El capturador invocó el transporte una vez.
La conexión terminó tras 21,210 s con `URLError / WinError 10060`, antes de
obtener una respuesta HTTP. Recibió cero bytes y no creó `response.bin`.
No conocemos una causa más específica a partir de ese error.

Resultado: `BLOCKED_QQQ_IB_CAPTURE`. No hubo reconstrucción, modelo, PnL o
segunda petición. El SHA vacío del manifest describe cero bytes contabilizados;
no significa que exista un cuerpo HTTP vacío válido.

Evidencia: [run manifest](qqq_recovery_evidence/run_manifest.json),
[manifest de transporte](qqq_recovery_evidence/manifest.json) y
[summary](qqq_recovery_evidence/summary.json).

## Integridad del empaquetado

El [registro de empaquetado](ib_review_evidence/packaging.json) distingue hashes
de origen y repositorio. Los cuatro JSON de revisión/publicación son idénticos
en bytes. Las tres copias documentales QQQ convierten CRLF a LF; se verificó que
esa es su única diferencia. Los originales de D: conservan sus bytes y hashes.
No recalcular un sello original con el hash de una copia normalizada.

## Verificación del software

- Suite inicial: 97 tests, 214,93 s, antes de los cambios.
- Suite final: `python -m pytest tests/multiscale_v1r1 -q`, 129 tests, 90,80 s.
- Ruff, compile de módulos cambiados y `git diff --check`: PASS.
- Revisión independiente del capturador, cierre offline y correcciones: aptos
  tras registrar la autorización y comprobar la publicación previa.

Se corrigieron duplicados contractuales con distinto texto de strike/zona
horaria y la discrepancia de validación de delta entre productor y auditor.
El hallazgo inicial sobre estados 15m se retiró: NUM-001 ya fija esa convención.
No se modificaron artefactos económicos previos ni parámetros del experimento.

## Estado que debe conservar el siguiente agente

El intento histórico original continúa `INVALIDATED/FAILED_AUDIT`. La economía
de la continuación sigue `NOT_EVALUATED`; `technical_ready=false`, validación
prospectiva `NOT_STARTED` y `promotion_approved=false`. Los 72 LightGBM reales
del informe 21 pertenecen a un fold sintético. No hay modelo rentable de mercado
acreditado por esta revisión ni ejecuciones confirmadas de bróker.

El informe 25 recoge la revisión por áreas. La siguiente evaluación de fuentes
debe ser LOCAL_ONLY: inventarios existentes, semántica de las muestras y admisión
por dependencias. Usar snapshots de un minuto como una nueva serie muestreada
sería un cambio material de contrato, no una reparación invisible del OHLC de
un segundo ni un PASS retrospectivo de V1R1.
