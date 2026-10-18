# Ejecución TCN row-mixed con caché ya sellada

Esta adenda operativa continúa el diseño científico congelado, sin editarlo. Un
único fit CUDA de cuatro épocas,1491updates por época, mismos270377ejemplos,
arquitectura, targets, IPW, normalización FLAGS64, AdamW, seed y diagnóstico TRAIN.
La única intervención científica sigue siendo mezclar filas entre días manteniendo
la secuencia de tamaños original. Siempre se usa época4.

Reutilizar `tcn_row_mixed_v1/cache_complete.json` SHA2671fda58cb1f26df2b6f440749e43b644de84196dd14c7bac526d1a91272c3d
y `run_tcn_row_mixed.py` SHA5c4adfe01e2a51f3eb0f16c96479edb326e2f06ea1f66b3721313ccaa9ab7ab2.
No reconstruir caché. El runner verifica los hashes completos antes de updates y
por época. El launcher revalida primero manifest/dependencias de código y review.

Por instrucción del usuario, gate operativo2.000.000.000bytes libres de RAM,
commit y VRAM de GPU0. Medir VRAM con nvidia-smi; no identificar GPU como vacía,
no cerrar ni modificar procesos ajenos. Rechazar otro productor TCN nuestro
CUDA activo, comprobado antes de lanzar. BLAS/OMP/NUMEXPR1; Torch4 ya fijado por
el productor. CUBLAS_WORKSPACE_CONFIG=:4096:8, como el modelo original.

Proceso hijo único, monitor1s RAM/commit/RSS/privada y VRAM. Logs/stdout/stderr,
PID/exit y snapshots separados en `tcn_row_mixed_v1_train_logs_01`. Registrar
hash de cada par checkpointpt/json al publicarse. El runner conserva modelo,
Adam, RNGCPU/CUDA, orden/tamaños y generadores schedule/mixed por época. No
reinicio automático del fit tras fallo; continuación posterior explícita con
`--resume` y nuevos logs, reutilizando el último checkpoint verificado.

La comprobación final del launcher enlaza training_complete y checkpoints con
su revisión/runtime sin modificar los markers científicos del productor. No
evaluación VAL/TEST desde este launcher. El evaluator revisado aparte mantiene
FLAGS64 como control y los umbrales/gates fijados; no se cambia por TRAIN.
