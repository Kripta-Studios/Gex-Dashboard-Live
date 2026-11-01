# Continuación OOF: CLI iniciado y admisión en curso

La [reanudación autorizada](RESUMPTION_20261101.md) y el invocador de root se
publicaron en `b75dc7856a28598057d60ea32e77b89861bcd765`, verificado contra
origin antes de iniciar el proceso. Se lanzó una sola vez el CLI revisado con
`--execute-reviewed-continuation` a **2026-11-01 11:35:36 UTC**.

CLI PID **10596**, creation **1793532936.962302**, padre invocador **36848**,
sesión de herramienta root **16020**. La creación del CLI procede de
`psutil.Process.create_time`; su futuro exit se conservará mediante
`subprocess.Popen.wait()` sobre el handle retenido por el invocador.
No son los recibos Win32 del futuro proceso científico.

La observación de las **11:36:31 UTC** verificó PID, creation y argv exactos;
CPU0, 15,953125 segundos CPU acumulados, stderr vacío y sin exit del CLI.
El único descendiente observado era conhost, sin hijo científico todavía.
No existía aún el directorio de logs del lanzamiento científico; seguían
starts/receipts00–07 y no había completion global. Estado:
`CONTINUATION_CLI_RUNNING_ADMISSION_PENDING`. **No relanzar** por esa ausencia:
el CLI realiza varias verificaciones completas antes de crear el hijo.

Recursos previos al CLI: RAM11.815.448.576 y commit20.885.176.320 bytes.
El supervisor aplicará de nuevo su gate inmediatamente antes del proceso
científico; esta observación no garantiza recursos futuros. CPU0 y
OMP/OpenBLAS/MKL1 se establecieron antes de Popen.

## Recibos conservados

Originales bajo
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_user_stop_continuation_observer_20261029_01`.
Admission/process están en `execute_20261101_01`; la observación,
en `running_20261101_01.json`. Tres copias exactas, 4.262 bytes, se archivaron
en [launch_01](continuation_20261101/launch_01/archive_manifest.json):

| Recibo | SHA256 |
| --- | --- |
| Admission del CLI | `10639e7a3c47adabdf7f6575ea9b7c34eefd8d5a7d84bf1288552dceddc4c438` |
| Process del CLI | `64cb28a471db3ee71cdbae9ec0d2ebb1e8449db8a8765e804fd1a072c9e01269` |
| Observación | `b37c6cfd2752a350c172e45e9a10a7ec97b28b93f78c8208ce0856caa466fcbe` |
| Manifest de copias | `96d68ff294c420816a4bce7ed90618cf97af812abe352047749c5381b5642892` |

Los logs stdout/stderr siguen mutables y no se copiaron. No se fabricó un exit,
completion, admisión científica o resultado económico. El helper final
`b9ace22732899838891d91df64f93b208387785b5c16ea9ccfbdbc688f9457a5` fue revisado
por `resume_review` en lectura, con CLEAR condicionado a publicación previa;
esa condición se satisfizo. Root verificó AST, diff y seis archivos staged con
bytes idénticos. No se repitieron suites científicas o sintéticas cerradas.

## Lectura de los últimos resultados cerrados

Se releyeron los informes publicados, sin abrir economía OOF parcial:

- [Greek152/424](COMMON_GREEK_COMPARISON_RESULT_20261023.md): Greek424 perdió
  35.329,40 USD base en H1 frente a 43.482,20 del control152; la mejora relativa
  mantiene pérdidas y empeora el agregado2025. Ningún ganador.
- [TCN row-mixed](TCN_ROW_MIXED_CALENDAR_RESULT_20261023.md): las variantes
  0/5/10 perdieron 34.199/40.962,60/42.491 USD base H1. La mayor actividad no
  satisfizo rentabilidad y frecuencia conjuntas; selección null.
- [Auditoría mensual compuesta](MONTHLY_TEST_2026_COMPOSITE_AUDIT_RESULT_20261024.md):
  PASS de reconstrucción dados scores sellados, sin refit/reinferencia/raw ni
  promoción. La selección quedó null. Los resultados económicos del
  [reporte18meses](MONTHLY_18MONTH_REPORT_RESULT_20261024.md) son negativos en
  los tres modos agregados, tanto en2025 como enH1.

Son PnL simulados por operaciones de un contrato, no retornos de una cuenta.
No se agregan políticas como cartera ni se rescata un ticker o mes aislado.
H1 conserva369 ticker-días esperados,363 disponibles y6 NO_EVALUABLE.

La comparación OOF pendiente evalúa las seis políticas control/corrected de
static/expanding/rolling12, con calibración predeclarada y los mismos scores.
Puede cuantificar el efecto de esa calibración en todo H1; no garantiza resolver
la señal base ni acredita desempeño prospectivo. Primero completar mayo/junio,
después request/binding económico real revisado/publicado, auditoría FULL_H1 y
reporter. El actor permanece condicionado a esa evidencia y a un contrato nuevo.

El goal sigue **activo, no completado**. Producción/API/bróker/VPS intactos,
selección null, SEEN_DEVELOPMENT, technical_ready=false y promotion_approved=false.
