# Archivo futuro de la auditoría compuesta — preparación

Sólo se prepara software a partir de los esquemas del auditor
`audit_monthly_walk_forward_test_index_v2.py` y del supervisor
`launch_monthly_test_index_v2_audit_20261024.py`. No se han abierto resultados
parciales. Root revisará este plan y el script, registrará sus SHA y entregará
los tres pins reales antes de autorizar su ejecución. No se añade otro CLI de
aprobación ni se inventan hashes futuros.

Entradas fijas bajo `D:/GexResearchArtifacts/level_oracle_20261018`:

- Auditor: `monthly_walk_forward_test_audit_20261024_01`.
- Supervisor: `monthly_test_index_v2_audit_launch_20261024_01`.
- Destino nuevo en repo: `continuation_20261024/monthly_test_2026_audit`.

CLI futuro de `archive_monthly_test_audit_20261024.py`:

```text
--audit-sha256 REAL_AUDIT_SHA
--supervisor-completion-sha256 REAL_SUPERVISOR_COMPLETION_SHA
--retained-exit-sha256 REAL_RETAINED_EXIT_SHA
```

Se requieren audit PASS del scope compuesto exacto, completion exitoso del
supervisor y exit 0 por handle retenido. Se comprueban sus bindings cruzados,
PID/creation time, cronología, preflight, los 18 meses exactos, los conteos
36 modelos/12 nuevos/369 ticker-días H1 con 363 disponibles y seis ausentes,
la herencia 2025 y los quince snapshots exactos. Un fallo de admisión no crea
el directorio. No se repite el auditor ni se calculan métricas.

Copias previstas: audit.json, launch.json, trece dependencias ejecutadas y dos
autoridades; completion, process, exit, preflight, admission y stdout/stderr del
supervisor; código/autoridades publicadas que el preflight liga por SHA. Sólo
se copian archivos compactos, con máximo 100 MB por archivo y verificación
hash de fuente/copia antes y después. Si aparece un archivo mayor, el copiador
falla para revisión; no configura LFS ni cambia el formato automáticamente.

El `.lock` del auditor y archivos transitorios no constituyen evidencia
económica; no se copian. No se busca código arbitrario ni se siguen todos los
paths de verified_files. Ese inventario completo ya está en audit.json y se
referencia como tal. Los 36 modelos están en los archivos anteriores de 2025
y del productor 2026: se coteja su mapa de hashes con el audit nuevo y se
documentan las rutas existentes, sin duplicar modelos ni afirmar un nuevo
rehash de esas copias. Matrices, inputs, targets, raw, features, scores y
ledgers permanecen en sus roots originales; el archivo no lee sus payloads.

Salida: `MANIFEST.json` con copias exactas y hashes de las tres autoridades,
`LOCAL_REFERENCES.json` con inventarios/modelos ya preservados y límites,
snapshots del propio script/plan. MANIFEST se escribe al final. Un fallo durante
copia conserva el root parcial, nunca lo adopta ni sobrescribe en otra ejecución.

El PASS futuro sólo tendría el alcance condicional «given sealed scores»:
sin refit ni repetición de inferencia, con reconstrucción 2025 heredada y
rehash de su inventario por el auditor compuesto. Este copiador no añade otra
auditoría de datos ni evidencia prospectiva; reporter, interpretación y
gráficas serán trabajo separado, posterior al cierre verificado.
