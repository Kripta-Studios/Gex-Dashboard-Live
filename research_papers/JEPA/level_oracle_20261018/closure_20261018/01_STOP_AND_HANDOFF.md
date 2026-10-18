# Parada solicitada y estado definitivo

## Orden y alcance

El usuario ordenó detener todo, todos los subagentes y procesos de la investigación, documentar extensamente el trabajo en Markdown y hacer push a GitHub. Se interrumpieron los cinco subagentes que seguían activos: `data_inventory`, `oracle_design_audit`, `source_feasibility`, `wide_audit` y `zone_benchmark`. `monthly_performance_review` y `wide_benchmark` ya habían terminado; `past_research` estaba detenido por capacidad del proveedor. No se delegó trabajo nuevo tras la orden.

Se identificaron los procesos por PID y línea de comandos. El proceso mensual PID38676 era el único proceso de investigación aún activo en el primer censo de parada; se detuvo explícitamente y se guardó [USER_STOP_PROCESS_RECEIPT.json](../USER_STOP_PROCESS_RECEIPT.json). Una segunda inspección ya no mostró procesos de este experimento. Servicios MCP y procesos de otro proyecto no eran entrenamientos de esta investigación y se conservaron. La documentación y Git son las únicas operaciones posteriores autorizadas.

El objetivo persistente se marcó `paused`, no `complete`: la rentabilidad causal solicitada no está demostrada. No debe reactivarse automáticamente por documentos antiguos ni por un archivo de progreso residual.

## Estado por línea de trabajo

| Línea | Estado al detener | Evidencia y continuación pendiente, sólo si se autoriza de nuevo |
|---|---|---|
| Inventario y benchmarks iniciales | Completos, negativos, auditados | `restart_20261018`; no repetir ni reinterpretar como modelos por salida de niveles |
| Oracle y features originales | Completos y auditados por alcance | `engine_v1`, `features_v1`; oracle no operable |
| Aprendices originales, episodios, FLAGS64 | Completos, sin solución diaria rentable | Informes y auditores correspondientes preservados |
| Continuación causal y nueve sesiones cortas | Completos, auditados, económicamente negativos | Los fills diarios observados no compensan las pérdidas |
| Compacto152 | Comparación y auditoría completas | Informe mensual de108 filas y resultado negativo publicados |
| Griegas424 | TRAIN completo; evaluación no iniciada | `common_greek_control_resource_v1`; el directorio `common_greek_comparison_v1` no existía al cierre |
| TCN row-mixed | TRAIN completo antes de la orden de parada | Cuatro checkpoints y modelo final. Evaluador nuevo750+369 incompleto, sin PnL |
| Mensual | Interrumpido por usuario, sin cuarto fit | Tres modelos completos; enero2025 calculado; no selección anual ni test2026 |
| OOF de máximos | Implementación sin ejecución real | Revisión estática y pruebas anteriores; rerun final de23 fixtures pendiente |
| Fuente adicional1–8DTE | Inventario y diseño únicamente | No features, modelo ni payoff de esa familia |

## Red temporal: terminó antes de ser detenida

PID15156 terminó con exit0 a **21:34:57.935454 UTC**, según `tcn_row_mixed_v1_train_logs_01/process_exit.json`. La marca `training_complete.json` existe, contiene exactamente épocas1–4 y1491 actualizaciones por época, y vincula el modelo final. No se atribuye ese éxito técnico a una evaluación de mercado.

- Modelo final SHA256: `2b55e783c8a7989fa6a579bc6b903f1eddd8b6d40e365aeada687aef630bc87e`.
- Completion SHA256: `2c7b350edcfbaa0d2bf769d1e3e808c50a152d8a4f2a46140f23928979520d95`.
- Checkpoint04 SHA256: `d37d86e399d4396841d32764bfd8574cff68916badf6d2829b0af4c3a7cfd0e9`.

El modelo siempre era la cuarta época, no la mejor escogida a posteriori. El evaluador anterior para741 sesiones de validación no se ejecutó. Se estaba preparando otro para750, incluyendo nueve cierres cortos antes de selección/freeze. Su código se archiva como trabajo sin completar; no se ejecuta durante este cierre.

## Mensual: lo que se conserva

Tres fits completos:

| Ventana TRAIN, límite superior exclusivo | Filas | Columnas | Modelo SHA256 |
|---|---:|---:|---|
| 20230101–20250101 | 191033 | 1954 | `fa802378a6af275948a8310ef2c01244b62458fb8e364b38631b8b9d61341732` |
| 20240101–20250101 | 95804 | 1954 | `dfb0a9e50127febea023e70c0d968e2b3f0dadc76f030b00f2196275fcce70ee` |
| 20230101–20250201 | 198713 | 1954 | `55ea5d22d46a1771134a612ca798ef11a72d77655646d710ced04165f55a0b8b` |

Los marcadores `.fit_started.json` de esos tres modelos tienen `.complete.json` correspondientes. No se observó cuarto fit ni un fit parcial activo al detener. Enero2025 tiene marcadores de predicciones, resultados diarios y economía. **No existe auditoría económica mensual completa**, y no se abrió una comparación anual para escoger un procedimiento. Los resultados de enero se documentan como parciales, sin extrapolarlos.

El `progress.json` original conservaba `WAITING_RESOURCES` de21:15:57UTC incluso después de haber progresado. Es un estado antiguo, no prueba de un proceso actual ni una instrucción de reinicio. El cierre operativo es esta parada y la ausencia de PID vivo.

## Recursos y recuperación

Por orden del usuario, los lanzadores operativos nuevos bajaron su mínimo a **2000000000 bytes libres de RAM y commit**; el de TCN también comprobaba VRAM. El código científico congelado se conservó mediante wrappers explícitos. El mensual cambió sólo la espera, no ventanas, modelos ni resultados. Se preservaron6084 hashes de checkpoints en la transición anterior a esta parada.

Los checkpoints neuronales guardan pesos, AdamW y RNG; los modelos de árboles completados se guardan y comprueban por hash. Un proceso de LightGBM interrumpido en mitad de `fit` no equivale a un modelo entrenado reanudable: hay que distinguir marcador de comienzo y cierre. No se borran parciales ni locks para simular éxito. No se vuelve a entrenar automáticamente un modelo que ya tiene cierre válido.

La carpeta local sigue siendo la evidencia de ejecución completa. La copia publicada en GitHub contiene código, documentación, revisiones y evidencia seleccionada identificada por hash; no sustituye las matrices, caches y fuentes grandes externas.
