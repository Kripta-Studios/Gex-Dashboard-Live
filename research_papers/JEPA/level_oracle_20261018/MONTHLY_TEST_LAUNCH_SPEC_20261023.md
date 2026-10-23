# Lanzamiento mensual test 2026: contrato operativo

2026-10-23. Componente nuevo; no cambia el wrapper test, review ni ciencia.
La revisión de implementación no autoriza runtime. Validación 2025 debe haber
terminado con exit0 observado por handle y auditoría independiente completa.
No se construyen ahora esas autoridades futuras ni se declara su PASS.

CLI: `launch_monthly_test_20261023.py --runtime-review <JSON publicado>
--runtime-review-sha256 <SHA externo> --expected-validation-audit-sha256 <SHA externo>
--publication-commit <40 hex>`. Por defecto sólo comprueba preflight e imprime
un recibo; no crea raíces de salida ni hijo. Únicamente
`--execute-reviewed-monthly-test` permite un lanzamiento, sin retry ni resume
automático del lanzador. La revisión de runtime del wrapper decide initial/resume;
el lanzador nunca adopta evidencia anterior por sí mismo.

Se reutiliza `run_monthly_test_resource_overlay.admit()` sin modificarlo: auditoría
2025, freeze (incluido selected_mode null), 24 modelos, contrato, once dependencias,
inventarios y cadena PID/creation_time/exit0 se verifican allí. La review del wrapper
conserva SHA `49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280` y el
wrapper SHA `f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1`.

La runtime-review concreta añadirá `launch_binding` con status
`REVIEWED_MONTHLY_TEST_ONE_SHOT_LAUNCH`, runtime_root y logs_root absolutos nuevos,
y published_files: mapa exacto de basenames a SHA de `publication_files()`.
Incluye launcher/tests/esta spec, wrapper/tests/spec, ambas reviews de implementación
y las once dependencias científicas. La propia runtime-review se liga por su SHA
externo para evitar autorreferencia. Roots disjuntos de ciencia/fuente/código y
autoridades. El fichero runtime-review debe estar en el repositorio y publicado.

launch_binding exige además launcher_review={path,sha256}, con el path fijo
`MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW_20261023.json` junto al código. Status
PASS_MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW, decision CLEAR, scope
IMPLEMENTATION_ONLY, runtime_authorized=false y files exacto de los tres archivos
nuevos. Ese JSON también entra en published_files y en la comprobación Git.
No se trata como permiso de runtime; éste requiere el binding concreto externo.

Los bytes actuales se contrastan con los objetos Git exactos del commit externo.
El coordinador comprueba y documenta la publicación remota antes de ejecutar;
este lanzador no usa red ni considera refs/cachés como prueba remota. HEAD puede
avanzar por trabajo ajeno si los objetos de alcance siguen idénticos. Git sólo
se usa para lectura de objetos durante preflight; ningún hijo científico se
crea antes de cerrar admisión. No se exige árbol global limpio ni se modifican
archivos ajenos. No se permiten Python optimizado ni PYTHONOPTIMIZE.

Comando del hijo fijo: intérprete actual, -u, wrapper test congelado,
--runtime-root, --implementation-review fija, --runtime-review y
--expected-validation-audit-sha256. Stage=test está fijado dentro del wrapper;
no hay argumento para elegir otra etapa. Se rehashean autoridades y cadena de
validación y se exige RAM y commit libres >=2.000.000.000 bytes justo antes de
Popen. Las variables científicas y de threads se heredan sin sobrescribirlas.

Logs nuevos guardan preflight, admission, stdout/stderr, process_binding,
monitor_open y monitored_exit. Se retiene el Popen y su handle original hasta
WaitForSingleObject y GetExitCodeProcess; creación obtenida del mismo handle
por GetProcessTimes, incluso si el hijo termina inmediatamente. El código de
salida puede ser no cero y nunca se infiere de ausencia de PID. Ctrl-C durante
observación se registra y se sigue reteniendo/observando, sin matar ni relanzar.
Si falla una escritura del monitor después de Popen, el handle se mantiene hasta
la terminación antes de propagar el error; no se fabrica una cadena completa.
Si falla la inicialización Win32 del monitor, se conserva el Popen y se espera con
su propio wait, ignorando Ctrl-C durante esa espera. Este fallback sólo evita
abandonar el hijo; no emite recibos falsos de GetExitCodeProcess. Un fallo al
escribir un log de interrupción tampoco termina la observación.

Los tres recibos comparten PID, creation_time y SHA de process_binding. Monitor
code es este launcher publicado. `process_chain.json` referencia también el
launch.json que escribe realmente el wrapper; no se fabrica si el hijo falla
antes de ese punto. Las claves son compatibles con verify_process_chain del
wrapper para la auditoría y un eventual resume externo. Ausencia de runtime_launch
se registra como cadena incompleta. Exit0 por sí solo no certifica completion,
auditoría, selección, rentabilidad ni promoción.
El SHA del monitor procede del pin publicado en preflight, no de una lectura
tardía usada como nueva autoridad. Se revalida antes de monitor_open y al cerrar,
junto a los recibos de binding/apertura; una mutación impide cadena completa.

Las fixtures son operativas y acotadas: admisión con dobles, verificador real de
cadena, publicación por objetos sintéticos, gates, roots, no retry, interrupción,
fallo de escritura y Python inocuo de salida inmediata 0/no cero para Win32.
No usan modelos, labels, outcomes ni procesos de mercado.
