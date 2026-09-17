# V1R1: cierre por FAILED_AUDIT, sin evaluación económica

El intento termina con `execution_state=INVALIDATED` y
`economic_evidence_state=FAILED_AUDIT`. El control previo había producido
`BLOCKED_DATA` por procedencia temporal insuficiente. Su reproducción completa
no se certificó: tres logs usados como fuentes cambiaron después del sello.
Se conservan el inventario original, los intentos y los hashes discordantes.
No se sustituyó el sello ni se abrió ningún outcome histórico.

## Código, documentos y alcance real

Se crearon los documentos 00–10, el contrato y schema, el lock del entorno,
el registro de elegibilidad, los paquetes `multiscale_v1r1` y
`multiscale_v1r1_audit`, y los tests sintéticos. Están implementados el inventario,
la admisión negativa y primitivas de tensor, ablación, contabilidad decimal,
scheduler, modelos, SSL, freeze y denegación de promoción.

**La implementación completa del plan está pendiente.** Faltan el builder de
59 niveles/estados, la orquestación económica mensual, el entrenamiento SSL/head,
baseline, bootstrap y auditor económico completo. El CLI deniega las etapas
posteriores; no puede producir un PASS de features o económico. El detalle está
en [09_IMPLEMENTATION_COVERAGE.md](09_IMPLEMENTATION_COVERAGE.md).

## Revisión y runtime

HEAD inicial: `29724f857185a046a09680b8edf9708d89949619`.
Predeclaración: `cc5f8b30`; lock: `3dfe3643`; productor: `5dd5a519`;
auditor corregido: `f771685c`. Rama: `research/multiscale-v1r1-net-usd`.
El push inicial a main fue rechazado por avance remoto. Fetch recuperó
`8355c816`; sus cambios de producción/frontend no se incorporaron a esta rama.

Python 3.14.2, LightGBM 4.6.0, NumPy 2.3.5, pandas 2.3.3, PyArrow 23.0.1,
PyTorch 2.10.0+cu128 y exchange_calendars 4.12. No se instalaron dependencias.
El runtime original permanece sellado; el cambio posterior del auditor tiene
su hash separado. No se atribuye al productor una ejecución desde ese cambio.

## Fuentes, cobertura y excepción SPXW

El inventario selló 30.899 parquet de las quince raíces autorizadas:
41.614.238.640 bytes (38,76 GiB), hasta la fecha de negociación 2026-09-11.
Solo se leyeron nombres, footers, scripts/logs de procedencia y bytes para SHA256.
Inventariar un archivo no acredita cobertura 0DTE, causalidad ni ejecutabilidad.

El calendario de construcción contiene 982 sesiones: 9 medias sesiones y
973 completas. El control previo dejó las 973 completas con procedencia
sin resolver; 32 además carecen de fuentes por nombre (29 en 2022 y 3 en abril
de 2026). No hay sesiones ni eventos admitidos/construidos. Las ausencias no son
abstenciones del modelo. Los motivos y totales mensuales permanecen en coverage
y en el resumen del gate original; este no tiene auditoría completa aprobada.

Los seis logs retenidos contenían 204 registros reconocidos, todos de julio a
septiembre de 2026, ninguno del periodo experimental. La inspección adicional
de 3.531 footers de subyacente encontró solo metadata estándar de pandas, sin
atributos de reparación. Es evidencia auxiliar del agente principal, no un PASS
del auditor. En ese archivo auxiliar, «admitted underlying» designa raíces
permitidas, no fuentes aprobadas.

La corrección `SPXW_INITIAL_ZERO_BAR` está admitida por contrato y probada con
fixtures de disponibilidad conocida. Falta recuperar el instante/cota de su
sustitución y su linaje histórico. Los scripts permiten reparaciones y bfill/ffill
y pueden sobrescribir parquet. La ausencia de logs no demuestra que haya habido
reparaciones indebidas, precios erróneos o lookahead; impide certificarlos.
No se reconstruyó ni sobrescribió raw y no se descargó ningún dato.

## Accesos, pruebas y resultado del auditor

Orden: predeclaración publicada → implementación y preflight publicados →
inventario de metadata → bloqueo de procedencia → intentos de auditoría.
No se leyeron columnas de valores de mercado ni features históricas; ningún
payoff de train, selection o test se creó o abrió. No hubo fit histórico.

Pasaron **42 tests sintéticos**, Ruff y compileall. Verifican primitivas,
admisión, barreras y alteraciones semánticas de evidencia. Incluyen el caso
de costes +1,40/−0,60 USD y la proyección SSL que oculta el reloj. No equivalen
a completar la matriz económica del plan.

Preflight sintético: 600 × 92.048, configuración A con 160 árboles;
819,734 s y pico de RAM observado de 1.676.472.320 bytes. La estimación del
proceso fue 23.918.586.464 bytes, inferior a 24 GiB; la de artefactos,
49.699.846.232 bytes más 20 GiB de reserva. Esto no certifica el pipeline completo.

Los intentos de auditoría quedan diferenciados:

1. Falló antes del rehash porque aparecieron 29 archivos de septiembre, fuera
   del periodo, sin desaparición de entradas selladas. La corrección publicada
   registra esas incorporaciones y mantiene la verificación de todas las fuentes
   originales. No amplía el experimento ni modifica sus exclusiones.
2. Se interrumpió sin artefacto final. El último progreso observado fue de
   4.000 fuentes; no constituye una auditoría completada.
3. Falló antes del rehash de parquet por `source log semantic reconstruction`.
   Los SHA256 de `descarga_QQQ.log`, `descarga_SPXW.log` y `descarga_SPY.log`
   difieren del sello. Permanecen las mismas 204 claves de registros reconocidos,
   pero los bytes de sus archivos ya no coinciden. No se atribuye este cambio
   a un proceso concreto ni se afirma que hayan cambiado los precios históricos.

No hay `PASS_INDEPENDENT_AUDIT` ni certificado de 30.899 rehashes completados.
`audit_summary.json` conserva la excepción y el diagnóstico del agente principal;
no se presenta como un artefacto exitoso del CLI. No se relajó la comparación de
logs ni se volvieron a sellar fuentes para convertir este fallo en PASS.

## Economía y estado prospectivo

| Ticker | Base USD/PF/WR | Adverso USD/PF/WR | Primario frente a ablación |
|---|---|---|---|
| SPXW | No evaluado | No evaluado | No evaluado |
| SPY | No evaluado | No evaluado | No evaluado |
| QQQ | No evaluado | No evaluado | No evaluado |

`technical_ready=false`, `prospective_validation_state=NOT_STARTED`,
`promotion_approved=false`, `approval_ref=null`. El registro local y su API están
preparados; los consumidores de producción no se modificaron. V1 y las familias
históricas conservan sus artefactos y resultados. No hubo órdenes, shadow,
despliegue ni cambios de bróker, services, bots, systemd, web o VPS.

No están validados la hipótesis económica, la aportación incremental, la paridad
live ni la cuenta compartida. Agosto/septiembre mantienen exposición global
desconocida. Octubre no se declara validado. Este intento se cierra conservando
su fallo; recuperar procedencia y disponer de fuentes estables sería trabajo
separado, sujeto a revisar la admisión y completar la implementación antes de
cualquier acceso económico.

## Evidencia conservada

Artefactos grandes: `D:/GexResearchArtifacts/multiscale_v1r1/run_20260917_01`.
El [catálogo](evidence/artifact_catalog.json) contiene tamaños, hashes y rutas;
no se añadió raw, tensores ni modelos grandes a Git. El resumen terminal está
en [evaluation_summary.json](evidence/evaluation_summary.json), y los hashes
discordantes en [audit_attempt_03.json](evidence/audit_attempt_03.json).
La carpeta de evidencia desactiva la conversión de finales de línea de Git para
preservar sus bytes y SHA256 al recuperar los archivos en Windows.
