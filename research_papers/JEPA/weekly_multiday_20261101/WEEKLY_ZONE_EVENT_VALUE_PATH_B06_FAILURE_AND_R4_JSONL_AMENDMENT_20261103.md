# B06 fallido y corrección acotada del orden JSONL

Estado: DOCUMENTARY_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION.
El usuario reanudó expresamente la investigación el3-nov; goal activo confirmado.

B06 está cerrado, exit1 retenido por el launcher y por root (tool0e8b4a).
PID8616/creation1793644105.584635, exit1793679228.9527311,
35124.6120217segundos. metadata_error=null, changed_pins=[], retry=false y
resource_wait_invalid_evidence=[]. La raíz de output06 está ausente y no hay
proceso B06 vivo. No relanzar06 ni adoptar sus parciales.

El journal registra2784 footers,1620 SELECT,2768 STREAM_OPTION_SOURCE y2790
CACHE_SPOT_PATH completos. El fallo posterior es
`AuditError: cache_admission schema/order row 0` en compare_rows, antes de
compare_spot, summary y cierre general. Esos avances no constituyen BfullPASS.

Archivo inmutable externo:
D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_event_value_paths_audit_failure_archive_06.
Once payloads,15578491B. Manifest:
566e208feda94c1fba7858b85318bef5a921ae5e1cfe1ec6c14e3e882a6fe05c.
Recibo:8254c72369ab6971a0a6a7aa2f9c9aed59acecd6ddea32330a0ce0e567e00343.
Proyección13 archivos en REANUDACION_20261103/b06_failure. Diez pins actuales
de implementación coinciden con implementation_pins del launcher.

## Causa comprobada y alcance

El contrato B, e7cf56f8, exige JSON compacto con claves ordenadas (sección10).
weekly_zone_event_spot_paths.py0953d344 implementa sort_keys=True. La primera
fila cache_admission empieza por authority, mientras expected_cache_admission
construye ticker primero. compare_rows exige list(left)==list(right), por lo
que rechaza antes de comparar valores. También compare_spot usa compare_rows
para spot_coverage JSONL construido en un orden diferente. El orden de filas
fecha/ticker sigue siendo significativo y no cambia.

R3 effc36ce/120016B, tests30686f92 y helper33873bfa quedan intactos. R4 será
un archivo nuevo audit_weekly_zone_event_value_paths_v2r4.py, con tests focales
test_audit_weekly_zone_event_value_paths_v2r4.py y raíces nuevas audit_07,
audit_observer_07 y audit_launcher_observer_07 bajo la misma base D.

Único cambio de comparación permitido: un helper JSONL que ordene las claves
de cada fila reconstruida y delegue en compare_rows sin modificarlo. Se usa
exclusivamente en cache_admission y spot_coverage. No ordena filas, no elimina
campos, no redondea/coacciona valores y no modifica el productor ni sus archivos.
Las claves leídas deben seguir el orden canónico previsto; las ausentes/extra
fallan. El comparador float bits y los schemas/órdenes Parquet quedan intactos.
Los únicos cambios restantes son nombres de módulo/test y raíces07 exclusivas.
Selección, reconstrucción option/spot, calendarios, hashes, gates, espera600s/5s,
CPU0/TEN1/CUDA-1, flags y formato de resultados no cambian.

## Verificación y siguiente ejecución

Después de revisión documental y publicación exacta, implementar sólo ese diff.
Una suite focal nueva reproducirá el error R3 con JSON sort_keys, probará los
dos caminos corregidos, valores alterados, bits de float, campos extra/ausentes,
orden de filas y rechazo de orden Parquet incorrecto. Verificará por AST que
las funciones científicas heredadas no cambiaron, normalizando únicamente los
dos calls JSONL, el helper agregado y los tres literales de identidad permitidos.
No se repite la suite R3 de136 pruebas ni ningún experimento cerrado.

Antes del nuevo run largo, la suite tendrá una comprobación limitada de los dos
JSONL de metadata B02: hashes exactos,2790 filas cada uno,21/16 claves exactas y
orden canónico. Pins: cache_admission5104757B/e0b4512791adbe70642d8ca83391dd4f0379037aae02f2af4888242bab3b0e14;
spot_coverage1675844B/2ed4a4b63a2f49f7bb6c1737fb6ae7ab4f5225f7c767185889f7fb591c78b972.
No abre raw, NPZ ni Parquet y no constituye auditoría de sus valores.

Código, tests y harness observado requieren revisión/publicación antes de esa
suite; cada hijo conserva gates oficiales, handles, logs, snapshots y exit.
Después de PASS focal y revisión final se prepara/publica binding y launcher07.
El intento07 debe reconstruir y verificar B completo desde sus autoridades,
sin reanudar06 ni tomar sus resultados parciales. El tiempo de esa nueva auditoría
no está medido; no se promete una reducción respecto a06. No hay autorización
de datos reales C/D hasta BfullPASS y admisión final, ni PnL nuevo en este cambio.

No se amplía D V2, no se abre búsqueda de parámetros ni otro experimento.
Objetivo económico, ocho meses completos y septiembre parcial permanecen intactos.
Goal activo; selected_policy=null; promotion_approved=false.
