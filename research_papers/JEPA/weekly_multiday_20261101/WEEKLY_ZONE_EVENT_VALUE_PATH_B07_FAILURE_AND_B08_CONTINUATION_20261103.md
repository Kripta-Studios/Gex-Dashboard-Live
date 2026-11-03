# B07 cerrado: fallo del seguimiento y continuación08

DOCUMENTARY_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION.
Goal activo. B07 FALLIDO/CERRADO, no relanzar ni adoptar parciales.
Root sesión33599 terminó exit1 retenido tool93abd2. PID50544,
creation1793695999.8273456, exit1793696318.0144825 (08:58:38.0144825UTC),
elapsed318.637613400002s. metadata_error=null, changed_pins=[], retry=false,
resource_wait_invalid_evidence=[]. Output07 ausente y proceso ya terminal.

Journal cerrado:2784footers completos y157/1620SELECT_1030_SOURCE.
No STREAM_OPTION_PATHS/CACHE_SPOT_PATH ni auditoría completa o PnL.
Stderr4568B acredita PermissionError abriendo journal.jsonl en modo append,
primero al registrar COMPLETED de una unidad y después ERROR del contenedor.
El seguimiento root43dde8 abrió el journal vivo con System.IO.File.ReadLines;
su lectura coincidió con el error08:58:37.6084018UTC. Ese lector usa un handle
que no comparte escritura en Windows. El fallo operativo es atribuible al
seguimiento root; no se presenta como error de datos ni de recursos.

Archivo externo weekly_zone_event_value_paths_audit_failure_archive_07:
10payloads4971576B, manifest3667B/c062e14df1fee30cb6f97ff10b2482782727320ec03169723bab1e09eb21aac7,
receipt310B/bf358185671e744a2cf36dd4451629a355a38897ed66cd5a75131e4ad219391d.
Doce proyecciones exactas en REANUDACION_20261103/b07_failure.
Fallos06 y07 se preservan; no reanudar, reparar journals ni adoptar parciales.

## Corrección operativa y alcance08

Mientras un productor/auditor esté vivo, root no abrirá ni leerá contenido de
sus journals o logs. Sólo polling del mismo handle/sesión, CIM de PID+creation,
y metadata de filesystem (existencia/tamaño/mtime) para seguimiento. Leer
contenido únicamente tras cierre terminal confirmado por handle; un timeout
de observación no es cierre y no autoriza otro run. Esto evita repetir el
conflicto de handles del monitor sin alterar ni reintentar escrituras del auditor.
No se introduce retry de journal, no se relajan gates y no se cambia ciencia.

Nuevo clon audit_weekly_zone_event_value_paths_v2r4_attempt08.py del R4
120329B/3340a357e2456eabe4c65fffba0b95c4b523e6665534a9781d82d8e9fd821af5:
únicamente dos literales OUTPUT/OBSERVER cambian07 a08. TESTS permanece
test_audit_weekly_zone_event_value_paths_v2r4.py/f9193711; sus20focales cerrados
y R3136 se heredan, sin repetición. Helper JSONL y todas las funciones intactos.
Raíces nuevas audit_08/audit_observer_08/audit_launcher_observer_08.

Suite nueva test_audit_weekly_zone_event_value_paths_v2r4_attempt08.py,
limitada a identidad: bytes exactos salvo dos literales, AST equivalente,
defaults parser08, rechazo de raíces07 antes de IO y rechazo de otras raíces
antes de IO. No datos reales/raw/NPZ/Parquet ni repetición20/136.
Harness observado nuevo con CPU0/TEN1/CUDA-1 y gates oficiales2GB antes
de cada hijo, Git/source pins, snapshots, logs y handles retenidos.

Revisión documental y publicación antes de crear clon/tests/harness.
Revisión/publicación antes de suite focal única, después revisión final y
binding/launcher08 revisados/publicados y GO root con gates contemporáneos.
Launcher08 deriva del FINAL07b4f49ea4: sólo identidades/pins de08 y nuevas
autoridades de este fallo/cierre; conserva CLI, WAIT600s/5s, gates y cierre.
Debe mantener audit tests argument f9193711 para el auditor y fijar por
separado la suite de identidad08. No ejecutarlo con evidencia final pendiente.

08 será auditoría completa desde autoridades originales B02, no recuperación
de07. Su coste temporal no está medido. Sólo BfullPASS/cierre/admisión final
permite C real y auditoríaC; después D A/B/C y EV causal. Sin ampliación D V2.
Goal activo, selected_policy=null, promotion_approved=false. No PnL nuevo.
