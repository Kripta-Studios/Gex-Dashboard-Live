# Wrapper de test mensual: implementación verificada sin ejecución real

2026-10-23. Se completó el wrapper operativo nuevo para llamar al productor
mensual congelado únicamente con `--stage test`. **No se ha ejecutado sobre
mercado, ni se ha emitido revisión de runtime con autoridades 2025 todavía
incompletas.** El coordinador sigue gestionando el productor de validación activo
y su monitor por separado; este recibo no modifica su estado/progress.

Los archivos nuevos son `run_monthly_test_resource_overlay.py`,
`test_monthly_test_resource_overlay.py` y
`MONTHLY_TEST_RESOURCE_OVERLAY_SPEC_20261023.md`. El wrapper cambia sólo la
función de espera de recursos durante el main original: 2.000.000.000 bytes
libres tanto de RAM como de commit. Restaura esa función y sys.argv en finally.
No modifica fit, modelos, CONFIG, muestras, ventanas, políticas, costes o
selección/null. Las once dependencias científicas permanecen exactamente iguales.

## Resultado final

Con gate previo de 2 GB o más de RAM y margen virtual y un hilo por backend numérico:

```powershell
python -m pytest research_papers/JEPA/level_oracle_20261018/test_monthly_test_resource_overlay.py -q -x
```

Resultado terminal recogido: **34 passed en 219,68 s (3 min 39 s), exit 0**.
Ruff completo y py_compile sobre los dos archivos nuevos: **PASS**.
Los hashes se comprobaron nuevamente después de las pruebas. No quedaron
procesos de prueba propios activos.

Las fixtures usan únicamente archivos/recibos sintéticos y un main doble.
La prueba de éxito crea los 12 modelos de texto adicionales y los seis cierres
mensuales artificiales para que `finish_science` real exija 36 modelos, 18 meses,
hashes de ambos informes y selección null intacta. Ningún modelo sintético se
ajusta o infiere, y no se consumen fuentes, labels o scores de mercado.

Cobertura comprobada: bordes decimales de RAM/commit, restauración normal y ante
fallo, CLI exclusivamente test, 24 modelos de validación, autoridad externa de la auditoría de 2025,
cadena monitor/handle/exit 0, PID reutilizado, source_launch de normalización,
freeze/null, primer intento sin evidencia 2026 previa, preparación 2026 sin outcomes
legítima, fit_started incompleto, resume de un modelo terminado con autoridad
explícita, inventario exacto, argv/dependencias originales, preservación de
modelos, locks del sistema operativo sin cambios de bytes, raíz nueva y cierre científico final.

## Intento previo conservado y correcciones

El primer pase terminó **1 failed / 13 passed en 97,37 s**. El fallo fue de la utilidad
de fixtures: `test_external_audit_hash_and_review_fail_closed` intentó cambiar
una revisión sintética usando `atomic_json` sin `replace=True`; el escritor
rechazó correctamente sobrescribir el archivo. Se corrigió solamente `put()`
del test para permitir sus mutaciones intencionadas en roots sintéticos.
No se relajó el escritor del producto ni se cambió un artefacto científico.

La revisión independiente detectó que source_launch era opcional aun cuando
el binding declaraba normalización. Se exige ahora en todas las cadenas
normalizadas, validación y reanudación de test, con hash exacto; también se rechaza un
source_launch cuyo hash falte en el binding. Las fixtures incluyen ambos casos
y la omisión en una cadena reanudada normalizada.

Se reforzó la identidad del comando: argv completo de validación/test, scope y
once dependencias del intento previo deben ser los originales. El probe del
lock científico normaliza como rechazo la lectura bloqueada por otro productor,
sin escribir sus bytes. El lock se libera antes del main y se readquiere para
comprobar/publicar el cierre. El main doble demuestra que el runner puede
adquirirlo; una llamada concurrente al probe es rechazada. No se borran locks
ni se detienen procesos.

Los planes/índices/calendarios, day_samples y feature_inputs 2026 sin outcomes
no se tratan como evaluación previa. Sí se incluyen en el inventario los fits/modelos con cortes 2026,
predicciones, meses, ledgers, report2026, completion global y day_chunks 2026 que
contienen targets y net labels. Esa distinción evita rechazar la preparación
legítima existente sólo por mencionar 2026.

## Hashes finales y conservación

| Archivo | SHA256 |
|---|---|
| run_monthly_test_resource_overlay.py | f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1 |
| test_monthly_test_resource_overlay.py | 3f8002125bfc35619d742fd039c48cc1c5a985613ab886b29b004f9cd7fc850b |
| MONTHLY_TEST_RESOURCE_OVERLAY_SPEC_20261023.md | 690a8389f53e6b0fc1599b806097edefe88afc67b74505ab89367dccc74f86a7 |
| run_monthly_walk_forward.py, conservado | 47a4df8b019d9d297ca1ee9b89fff63406409659336dbd7b0e4d7af01ed348bb |
| run_monthly_resource_overlay.py, conservado | ae596a0958511c3459885a2d1e04c800da93dfd7d0e1a540208a1ebb10155e34 |
| audit_monthly_walk_forward.py, conservado | e4a3be1c19b7f0af1226e71255c81116bd71a6a300aef36f61c688deb908df1f |

Comparación posterior contra `MONTHLY_RESOURCE_OVERLAY_REVIEW.json`:
**11 dependencias originales, diferencias 0**; los tres archivos propios del
overlay de validación original también tienen diferencias 0. Git diff del productor,
overlay de validación y auditor de 2025: vacío. No se modificaron esas autoridades ni
las salidas de sus procesos activos.

## Revisión y frontera pendiente

El revisor independiente `tcn_completion` leyó los nuevos bytes y el monitor
real de validación como texto, comprobando la cadena OpenProcess/GetProcessTimes/
WaitForSingleObject/GetExitCodeProcess. Confirmó estáticamente el cierre del
hallazgo source_launch y no comunicó nuevos bloqueos. Su rerun focal y revisión
final exacta se registran aparte; no se atribuyen estas 34 fixtures a otra ejecución.

La autorización general del usuario permite continuar sin volver a pedirla.
La dependencia pendiente es técnica: completar y auditar 2025, preservar el freeze y
observar exit 0 del proceso de validación mediante el handle; después fijar esos hashes en
la revisión de runtime y publicar los bytes revisados antes del test de 2026. La
completion del wrapper futuro no sustituye el recibo de salida del proceso ni
la auditoría independiente de 2026 dado scores sellados. El trabajo OOF conserva su
propia frontera. 2026 sigue como desarrollo visto; promoción false. API, datos
originales, producción, bróker y VPS permanecen fuera del alcance de este wrapper.
