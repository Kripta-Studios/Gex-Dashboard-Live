# Builder feature-only TRAIN, anterior a su ejecución

2026-10-18. Implementación separada; requiere review exacta antes de abrir datos
TRAIN nuevos. No CLI de fit, labels, target NPZ, VAL/TEST ni métricas económicas.

Reutiliza exactamente training_sample.parquet original, proyectando sólo
sample_i/day_key/ticker/date/action_id/state_i/weight. Exige270377 filas, orden
sample_i0..N−1, IDs únicos por día, pesosIPW positivos/mean1 y fechas2023–2024.
Preserva sus IDs, orden y pesos; no remuestrea ni une por posición implícita.

Autoridades: hashes fijados run_contract/matrix.complete/model.complete del
control compacto; modelo control cue_net.txt ligado pero no cargado; audits
FULL motor y económico learner; muestra y engine index ligados a esos hashes.
El prefijo152 procede de train_x.npy ya sellado y cada chunk original debe
reproducir IDs/state_i/sample_i y sus bytes del prefijo. No se recalcula152.
Los caches de cada día se verifican contra cache_npz_sha256/cache_meta_sha256
del índice auditado y metadatos de identidad. No autobaseline de raw actual.

Dinámicas: COMMON_GREEK_DYNAMICS_V1_DESIGN.md, módulo272campos. Se leen sólo
time/identity/spot/flags/IV/delta/vega/theta/OI; ningún bid/ask ni label. Cierre390
porque esta muestra contiene sesiones completas. Estado60..375. OI y Greek
usan sus máscaras propias; cobertura row_flags4 es nueva y se reporta, sin
heredar la disponibilidad del diagnóstico previo.

Checkpoints por ticker-día NPZ: sample_i,action_id,state_i,weight,x424. Incluyen
hashes exactos de fuentes. Resume verifica todos los miembros y su identidad;
un chunk completado no se recalcula. Parciales sin sello se conservan como
orphans antes de reescribir. Ensamblaje train_x.npy float32 Nx424 y row_keys.npz
sin targets; matrices incompletas pueden reensamblarse desde chunks terminados.
Se verifica prefijo bitexact152 y cobertura final por canal/Greek, tanto por
acciones como sumIPW y estados únicos. Finaliza sólo tras rehash de fuentes y
outputs. Lock de proceso exclusivo; segunda ejecución completada sólo verifica.

Un hilo, memoria de un día; matrix424 unos459MB decimales, sin caché16GB niGPU.
No arrancar ejecución hasta revisión del código/tests/sourcebindings. No fit
autorizado por este documento aunque la construcción termine correctamente.
