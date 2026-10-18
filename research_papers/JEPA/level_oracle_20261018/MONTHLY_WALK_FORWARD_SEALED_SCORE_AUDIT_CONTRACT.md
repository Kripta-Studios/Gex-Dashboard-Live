# Contrato del auditor mensual sobre scores sellados

Fecha: 2026-10-18. Este contrato cubre un auditor nuevo e independiente de la
validación mensual V1. No modifica ni se importa desde
`run_monthly_walk_forward.py`, no toca el proceso activo y no abre resultados
reales antes de que los doce meses de validación estén completos.

El estado terminal admisible es
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`. La frase
`GIVEN_SEALED_SCORES` es parte del alcance: el auditor no refittea LightGBM ni
repite inferencia. Rehashea contrato, auditor e índice de fuente, cierres,
features, matrices, targets, modelos, firmas de fit, scores, manifests y
ledgers. Los sidecars actions/labels se rehashean contra el índice
independientemente sellado; el resultado los representa de forma compacta con
el hash del índice y contadores, no con miles de entradas duplicadas.

Para cada ventana reconstruye, sin importar el productor, el calendario
static/expanding/rolling12, la muestra determinista por identidad, IPW, unión de
labels, chunks, orden de matriz, escalas, target net/scale y pesos de fit. Exige
que cada dependencia diaria pertenezca al `input_hashes` del fit. Comprueba la
firma de matriz/target/pesos y el modelo sellado, pero esa firma no demuestra
que los bytes del modelo sean el resultado de un refit independiente.

Para cada mes exige que todos los scores de los dos fits únicos estén dentro del
manifest conjunto anterior a cualquier ledger. Verifica identidad, modelo y
escala de cada score sellado; luego reconstruye el scheduler, attempts, ledger,
economía y registro diario desde actions, labels y esos scores. Finalmente
reconstruye la selección sólo con 2025, su freeze y el informe anual.

El JSON final expone `binding.monthly_root`, hashes del contrato, auditor de
sesiones e índice, los doce `completed_months` y `verified_files` categorizado.
Es el contrato de entrada para adaptadores posteriores. El PASS no certifica
timestamps raw, paridad live, ejecución prospectiva, rentabilidad futura ni
promoción.

Antes de cualquier ejecución real son obligatorios los fixtures sintéticos,
Ruff, compilación y una revisión separada de estos bytes. La ejecución debe usar
un directorio de salida nuevo y sólo comenzar después del cierre completo de la
validación V1. Un resultado parcial, una ausencia de artifacts o cualquier hash
distinto falla cerrado.
