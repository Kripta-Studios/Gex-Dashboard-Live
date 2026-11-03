# Revisión independiente del cierre B06 y enmienda R4

Veredicto: SHIP_DOCUMENTARY_B06_CLOSURE_AND_R4_JSONL_AMENDMENT.
Revisor: /root/d_scale_auditor_static_review, sólo lectura; retorno3-nov2026.
Root acepta el alcance documental, no una implementación ni datos auditados.

Enmienda revisada:4663B,
5cc7f605d99c271380bfd32523b87885316d1c4c9c8badc6b4c5eb83de2c24fe.
Archivo externo06:11payloads15578491B; manifest
566e208feda94c1fba7858b85318bef5a921ae5e1cfe1ec6c14e3e882a6fe05c;
receipt8254c72369ab6971a0a6a7aa2f9c9aed59acecd6ddea32330a0ce0e567e00343.
Las13proyecciones coinciden byte/hash con el archivo, manifest y recibo.

Verificados exit1, PID8616/creation1793644105.584635, exit1793679228.9527311,
rootchunk0e8b4a, metadata_error=null, changed_pins=[], retry=false;
output06 ausente y PID no vivo. Journal:2784footers completos (16sinlectura),
1620SELECT,2768STREAM_OPTION_SOURCE,2790CACHE_SPOT_PATH. Stderr acredita
cache_admission schema/order row0 antes de spot comparison, summary o cierre.
No se admite ningún parcial ni se permite relanzar06.

La corrección sólo ordena claves de filas esperadas JSONL en dos calls;
compare_rows permanece intacto. Conserva claves leídas canónicas, campos,
valores, comparación float y orden de filas; no modifica schemas Parquet.
La matriz focal cubre los dos calls, fallo R3, valores, floats, campos,
orden de filas, rechazo Parquet y equivalencia AST de todo lo heredado.
La integración previa se limita a los dos JSONL metadata pineados de2790filas
y21/16claves, sin raw/NPZ/Parquet y sin admisión de valores reales.

Publicar esta revisión y la enmienda antes de implementar R4. Código, tests
y harness requieren revisión/publicación antes de suite focal observada;
después PASS y revisión final, binding/launcher07 revisados y publicados,
gates contemporáneos y un único07 completo. CPU0/TEN1/CUDA-1, gates2GB,
wait600s/5s y ciencia heredada permanecen intactos. No reabrir R3136 ni B02.
No BfullPASS, C/D real o PnL nuevo. Goal activo, sin selección/promoción.
