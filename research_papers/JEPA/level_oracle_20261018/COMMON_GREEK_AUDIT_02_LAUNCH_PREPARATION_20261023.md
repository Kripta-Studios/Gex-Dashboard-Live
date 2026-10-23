# Preparación operativa del auditor 02

2026-10-23. Se preparó `launch_common_greek_audit_02.py`, sin ejecutar auditoría,
preflight real ni abrir resultados económicos. Los hashes finales de la revisión
V2 y el commit que incluya además este launcher deben suministrarse externamente.
Root informó que V2 y su review ya están publicados en
`8b6de01f818535714d58c940d040bf0fa81b32c2`; el launcher aún requiere revisión y
publicación propias. No se inventan valores provisionales ni se calcula el hash de un
archivo arbitrario para autoautorizarlo.

El launcher no cambia el auditor V2, las autoridades científicas originales,
el productor, sus scores, modelos, políticas o gates. El intento01 conserva su
fallo y sus recibos. Esta preparación tampoco constituye permiso autónomo de
ejecución: root coordina revisión, publicación, recursos y lanzamiento.

## Gates y recibos

El modo por defecto sólo valida y devuelve un recibo JSON por stdout, sin crear
roots ni proceso. Comprueba:

1. Salidas nuevas y ausentes `common_greek_comparison_v1_economic_audit_02` y
   `common_greek_comparison_v1_economic_audit_02_logs`.
2. SHA externo de `COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_REVIEW_20261023.json`.
   Su status debe ser `PASS_COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_IMPLEMENTATION_REVIEW`,
   decision `CLEAR`, scope `IMPLEMENTATION_ONLY` y `runtime_authorized=false`.
   Es una revisión técnica; la invocación explícita de root constituye la acción
   operativa separada y no cambia ese campo.
3. Los tres miembros exactos de `binding.reviewed_implementation` y el auditor
   original de `binding.original_auditor`. Comprueba sus bytes y los del propio
   launcher, revisión V2 y revisión científica contra objetos Git del commit
   completo de 40 caracteres suministrado por root. La verificación remota de
   publicación corresponde a root; el launcher no hace red ni afirma consultar
   GitHub de nuevo. También verifica los pins de las dos dependencias legacy,
   recibo del autor V2 y evidencia del fallo01 contenidos en la revisión V2.
4. Auditor original SHA `3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70`
   y review científica SHA `6270e38baa5fded3fd0a12d5b16b7969347e3a43b6c1cc068b95783c7efbb540`,
   sus 20 dependencias y seis autoridades. `--review` del hijo sigue apuntando
   a la review científica original, no a la revisión técnica V2.
5. Ocho pins del productor, incluidos los siete miembros principales y su
   marker global: completion `40cfdf576885eecd10785946687e5cf87cce228c1483e3ddd43cbd911207c824`,
   global `ad916c5695e165693c9843d206329732dde1d9149fc8ee0f9354818caf399d6d`,
   freeze, ambos reports/markers y test freeze. Verifica también pertenencia y
   binding. Los reports se rehashean como bytes, sin interpretar sus métricas.
6. RAM y commit disponibles de al menos **2.000.000.000 bytes**, con comprobación
   repetida inmediatamente antes de crear el hijo. El gate es de admisión y no
   reserva memoria ni detiene al hijo si otros procesos reducen los recursos.

El flag `--execute-reviewed-audit-02` habilita una sola llamada a `Popen`, sin
retry. Usa el script V2 y salida 02; todos los demás argumentos del auditor
conservan los de 01. El hijo no abre ventana, recibe los tres límites de hilos
BLAS/OMP a 1 y conserva stdout/stderr. Los recibos nuevos son `preflight.json`,
`admission.json`, `process.json` y `exit.json`. PID y tiempo de creación se
registran usando PID de `Popen` y `GetProcessTimes` sobre su handle retenido,
que sigue identificando al hijo aunque termine inmediatamente. La finalización
y exit code también proceden de ese handle. Antes de atribuir memoria mediante
psutil se compara su creación con la obtenida del handle; una diferencia impide
atribuir muestras del PID. Un fallo de observación se conserva como tal, sin
inventar recursos ni decidir el exit del hijo a partir de un PID reutilizado.

El monitor muestrea recursos cada segundo y preserva máximos/mínimos observados,
errores de monitor y duración. Conserva `sample_count`; si no hay ninguna
observación de memoria del proceso, ambos picos son null. El contador de muestras
del sistema distingue e incluye la lectura de admisión. Un exit 0 no dispara el reporter ni se convierte
por sí solo en un PASS económico: root comprobará el resultado del auditor.

## Comandos previstos después de revisión y publicación

Los placeholders siguientes no son valores autorizados ni comandos ejecutados:

```text
python -u research_papers/JEPA/level_oracle_20261018/launch_common_greek_audit_02.py --v2-review-sha256 <SHA256-EXTERNO-REVIEW-FINAL> --publication-commit <COMMIT-PUBLICADO-40-HEX>
```

El primer comando debe mostrar a root el recibo real de preflight. Sólo después
de su coordinación se puede añadir `--execute-reviewed-audit-02` a la misma
invocación, manteniendo idénticos los dos pins externos. No se generó todavía
ese recibo real durante esta preparación.

## Verificación sintética

```text
python -m pytest -q research_papers/JEPA/level_oracle_20261018/test_launch_common_greek_audit_02.py
12 passed in 0.35s
```

Las fixtures no acceden al mercado ni ejecutan el auditor. Una fixture lanza
solamente `python -c pass`, espera su exit 0 y comprueba que la creación leída
del handle sigue disponible e idéntica tras terminar; las demás usan dobles.
Comprueban ambos
límites de recursos, esquema CLEAR y separación de autorización, pin externo,
rechazo de objetos Git distintos, modo default sin hijo, CLI científica intacta,
segundo gate de memoria y exit 1 por handle sin retry. También comprueban hijo
rápido sin muestras, PID reutilizado y error del monitor conservando el exit 2
del handle. Ruff con `--select F` y
`py_compile` pasan para los dos archivos.

| Archivo | SHA256 preparado |
|---|---|
| `launch_common_greek_audit_02.py` | `96e659fd3acea266778ff4508470f47d68fcbd6d85bc542ea6e6873af65361c2` |
| `test_launch_common_greek_audit_02.py` | `fcc938409f3cf515931869b3d7e172cea17f56baa20aa7d36c5d98b2423f6522` |

Estado: **PREPARED_NOT_EXECUTED**. No auditor 02, reporte descriptivo, fit,
reinferencia, cambio de fuentes o promoción ocurrió durante esta preparación.
