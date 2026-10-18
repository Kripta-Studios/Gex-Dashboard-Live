# Conservación, reproducción y publicación

## Estado operativo

Este documento es un inventario de recuperación, **no una orden de reanudar**. La investigación está pausada por el usuario. No ejecutar scripts de training, evaluación, captura, auditoría de mercado o auto-resume basándose en este runbook. La publicación en GitHub no despliega modelos ni cambia servicios.

## Entorno observado

Windows/PowerShell; Python3.14.2,NumPy2.3.5,Pandas2.3.3,PyArrow23,LightGBM4.6,PyTorch2.10cu128. MáquinaRyzen9955HX,16núcleos/32hilos,~31.18GiBRAM yGPURTX5070TiLaptop12GB. Los procesos usaron normalmenteBLAS1/LightGBM4/Torch4. Son versiones observadas, no garantía de reproducción bitexact con otras versiones, drivers o dispositivos.

Raíces:

- Repositorio: `C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live`.
- Descargas preexistentes: `D:/ThetaData`.
- Primer inventario/benchmark: `D:/GexResearchArtifacts/restart_20261018`.
- Motor, modelos y diagnósticos: `D:/GexResearchArtifacts/level_oracle_20261018`.

## Qué se publica

Se publican las dos carpetas de esta investigación: Markdown, códigoPython, fixtures,CSVdescriptivos,JSONde revisión y recibo de parada. Se incluye un archivo documental de resultados ya existentes y modelos/checkpoints seleccionados, sin recalcularlos. [ARTIFACTS](ARTIFACTS.md) relaciona cada copia con su ruta original, tamaño ySHA256. [DOCUMENT_INDEX](DOCUMENT_INDEX.md) indexa todos losMarkdown conservados.

Los binarios publicados son artefactos de investigación, no modelos listos para operar. La disponibilidad del archivo no cambia el resultado económico de su familia. `archive_stopped_research.py` sólo lee/copia evidencia existente; no importa productores ni ejecuta modelos. Rechaza sobrescribir una copia cuyo contenido no coincida y rehashea origen/copia.

No se suben todos los parquets originales, caches, matrices de variosGB o cada predicción por acción aGit. Permanecen localmente en las rutas registradas por los contratos y manifests. Por tanto, **clonar GitHub no basta para repetir el experimento completo sin esos datos locales**. Tampoco se incorporan cambios ajenos previos en `live_king_node.py`, `MASTER_KING_NODE_RECORD_V5.xlsx`, archivos de otros experimentos o temporales de producción. No se destruye ni revierte ninguno.

La regla local `.gitattributes` conserva bytes exactos sin conversiónLF/CRLF, porque los contratos de ejecución dependen deSHA256. Los archivosJSONde review que ignoraba la regla global se añaden explícitamente en estas carpetas. No se cambian los hashes documentados para adaptarlos a una serialización nueva.

## Mapa de artefactos locales

| Raíz relativa bajo `level_oracle_20261018` | Contenido y necesidad |
|---|---|
| `cache_v1` | Snapshots normalizados y procedencia Greek/OI, máscaras y reloj |
| `engine_v1` / `engine_v1_audit_v4` | Acciones, labels, oracleDP y auditoría completa original |
| `features_v1` | Arrays causales y metadatos; matrices originales derivadas |
| `session_clock_dataset_v1` / `_audit` | Universo explícito de sesiones completas/cortas y ausentes |
| `learners_v1`, `episode_learners_v1`, `tcn_flags_v1` | Modelos, normalizadores, muestras, scores, selección y resultados cerrados |
| `causal_rollout_v1` | Teacher/control/residual, muestras, targets, scores y ledgers |
| `causal_rollout_short_sessions_v1` | Inferencia de nueve sesiones cortas sin refit/reselección |
| `market_cue_control_v1` / `market_cue_comparison_v1` | Modelo152 y comparación fija auditada |
| `common_greek_train_v1` / `common_greek_control_resource_v1` | Matriz424 y modelo completo; sin evaluación temporal |
| `tcn_row_mixed_v1` | Cache de filas, cuatro checkpoints y modelo final; sin evaluación temporal |
| `monthly_walk_forward_v1` | Preparación, tres fits,enero2025; investigación interrumpida |
| `monthly_resource_overlay_v1` / `monthly_resource_transition_v1` | Gate2GB, recibos operativos y continuidad de hashes |
| `*_economic_audit*`, `*_logs`, `*_runtime*` | Auditorías, errores preservados y observaciones de recursos |

## Reanudación futura, condicionada a nueva orden

1. Comprobar la orden de usuario más reciente; esta parada no permite autoresume. Confirmar que no hay procesos duplicados mediante PID+línea de comandos, no sólo locks.
2. Rehashear el código y las autoridades exactas de la familia. Los modelos, normalizadores y fuentes deben coincidir con su contrato. Las rutas absolutas importan en los manifests; trasladarlos a otra máquina no autoriza regenerar hashes silenciosamente.
3. Distinguir `fit_started` de `complete`. Los tres fits mensuales tienen cierre válido; no repetirlos. Su cuarto fit no había comenzado. No relanzar un fit completado para obtener una semilla favorable.
4. La redrow-mixed ya completó las cuatro épocas: no necesita reanudar training. La siguiente tarea pendiente sería terminar/revisar su evaluador750+369, con controlFLAGSfullbitexact y nueve cortas explícitas antes de selección/freeze. No usar el evaluador741como sustituto.
5. El modelo424 ya está entrenado. Su comparación estaba revisada, pero el launcher escrito al final quedó sin ejecución/revisión final operativa. Antes de cualquier ejecución revisar código exacto y salida nueva; conservar control152bitexact y el gate2GB solicitado.
6. El mensual se detuvo en validación2025. No hay selección anual ni autorización implícita para saltar a2026. Su auditor exige cierre de los doce meses antes de emitir unPASSglobal.
7. La calibraciónOOF está preparada, no aplicada. Necesita completar las pruebas/revisión y consumir un mensual terminado/auditado, sellando scores antes de labels del mes. Ningún dato parcial de enero decide hiperparámetros.

Todo cierre y recuperación debe preservar resultados negativos, fallos, parciales y fuentes. Nunca eliminar una sesión porque pierda, llamarholdoutnuevoal2026visto, introducir bfill futuro o traducir una mejoraTRAIN a rentabilidad.

## Verificaciones de publicación

El cierre valida copias ySHA256, inventario del staging, formato de documentos, ausencia de archivos ajenos en el commit y equivalencia delSHAremoto traspush. No reentrena ni reevalúa estrategias. Los checks de publicación y el hash de commit se registran aparte porque no forman parte de una auditoría económica. La rama de trabajo es `research/multiscale-v1r1-net-usd`; se usa el remoto `origin` existente, sin force-push ni modificación de historia.
