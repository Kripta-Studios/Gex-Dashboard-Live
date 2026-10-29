# Supervisor de continuación OOF tras la parada del usuario

Estado del autor: **IMPLEMENTED_SYNTHETICALLY_VERIFIED_NOT_RUNTIME_AUTHORITY**.
Alcance: implementación operativa y fixtures artificiales. La revisión
independiente es otra autoridad; este resultado no admite ni ejecuta el prefijo
real y no constituye un resultado económico.

Se añadieron únicamente el supervisor
`launch_oof_pipeline_user_stop_continuation_20261029.py` y su test homónimo,
además de estos resultados y evidencia nueva. El wrapper científico, los
productores, los supervisores anteriores y sus recibos permanecen sin editar.
No se ejecutaron productores reales, auditor económico, API, fit o inferencia.

| Miembro final | SHA256 |
| --- | --- |
| Supervisor | `599f6d5c347ebdc3801bbe8cc21de55603a80a46858a8bad1d20729d307eee11` |
| Tests | `e1dc93402ee08eb53e1aaae850efc9b789f0d68fc2ddf05639a285a199471b2b` |
| Resultado JSON | `d43d8f88f93a51417b3fb3937a7469933875b55889030608d2a8ea79d7498286` |
| Manifest de copias | `7523b55f54d898e85cab99de6511c4f1e031efde8658cce85fa125858122f860` |
| Evidencia CPU0 final | `0c67f501b2750986e7f0c519e4139e26d0e57d8ef6ca977b7f97eaaf15558da8` |

El mapa de implementación contiene 60 miembros, incluidas las 18 dependencias
científicas originales. Está en
`continuation_20261029/oof_user_stop_continuation_implementation/final_checks/implementation_files.json`.
Los módulos operativos se importan sólo después de verificar sus pins y comparar
su cierre completo con el mapa del review original pineado. Se vuelven a
verificar después de importar; no hay monkeypatch, reasignación de módulos
congelados ni llamadas a los CLIs antiguos en el supervisor.

## Comportamiento implementado

DEFAULT realiza admisión de metadatos y hashes y declara `executed=false`.
La autoridad operativa fija request/binding originales, autorización del 29,
review independiente del prefijo, snapshot, la cadena retenida con exit15 y
failure original, ocho fases adoptadas, el tail, la unión transitiva original
y cuatro fases pendientes. Los esquemas de request, binding y manifest son
conjuntos exactos de campos definidos en el código.

La admisión exige los 18 controles originales y ocho closures, sus contratos y
mapas de fuentes, membresía e integridad de outputs, cómputo de bytes por fase,
cinco locks originales y dos copias exactas por miembro compacto. Los payloads
económicos se verifican como bytes. La prueba usa incluso summary/controls con
bytes que no son JSON para comprobar que la admisión externa no los interpreta.
Las fuentes deben pertenecer a las raíces originales o al mapa transitivo
exacto; enlaces, aliases, hardlinks, conflictos de SHA y fuentes no admitidas
son rechazados por los helpers pineados y los controles nuevos.

`launch()` conserva el lock operativo original, comprueba la disponibilidad
real del lock del wrapper y repite el preflight bajo el lock. Sólo crea la
carpeta nueva de logs con `exist_ok=False`; cualquier fallo posterior preserva
esa marca de uso. La única orden permitida es el wrapper original, request
original y su SHA, con `--resume` al final. CPU0 se impone y verifica en el padre
antes de Popen; OMP/OpenBLAS/MKL reciben un hilo y el child es oculto. El gate
RAM/commit sigue siendo 2.000.000.000 bytes.

El monitor conserva el handle real, registra su PID y creación, comprueba la
afinidad del child y obtiene su exit del mismo handle. Una carrera de salida
o un fallo de observación no fabrica ni borra el exit retenido. Si no pudo
verificar identidad/afinidad inicial, o detecta deriva de afinidad, publica
`monitor_valid=false` y no puede cerrar con completion. Toda excepción después
de Popen drena el child.

Después de exit0 válido, el validador original exige los doce cierres y 27
controles. El supervisor nuevo comprueba además el proceso y exit del monitor,
los cuatro starts dentro de su intervalo, la conservación del baseline,
la composición exacta de los seis logs previos a completion y la membresía
de logs/observer/snapshots protegidos. La presencia de un failure nuevo impide
completion. El cierre mantiene `auditor_executed=false`, selección nula y
`technical_ready=false`/`promotion_approved=false`.

## Verificación por intento

Todos los intentos están preservados individualmente bajo
`D:/GexResearchArtifacts/level_oracle_20261018/oof_user_stop_continuation_implementation_20261029_01`.
No se suman versiones o ejecuciones como si fueran una sola suite.

| Intento | Resultado | Alcance y causa |
| --- | --- | --- |
| 01 | 1 FAIL, 25 deselected | RED inicial: la aserción de ausencia falló antes de crear el supervisor. |
| 02 | 25 PASS, 1 FAIL | El fixture Win32 omitía los tipos del pseudo-handle y no comprobaba el BOOL de la API; mask0 no acreditaba un fallo real de herencia. |
| 03 | 1 PASS, 3 FAIL, 25 deselected | Fixture CPU corregido PASS; tres RED nuevos reprodujeron carreras de salida, fallo de muestreo y deriva de afinidad. |
| 04 | 44 PASS, 1 FAIL | El test de snapshot compartía el dict esperado y el mutado. Se corrigió el fixture con copias independientes. La integración de cuatro fases pasó. |
| 05 | 7 PASS, 2 FAIL, 45 deselected | Se detectó y corrigió la ausencia del guard de membresía exacta de logs nuevos. El lock ocupado ya rechazaba con RuntimeError; se corrigió el tipo esperado por el fixture. |
| 06 | 54 PASS, 106,97 s | Suite nueva completa, supervisor `bf781067…56d897`, tests `c4197f4f…7c992f2`. |
| 07 | 1 FAIL, 54 deselected | RED del nombre del nuevo supervisor económico como proceso competidor. |
| 08 | 2 PASS, 53 deselected, 0,16 s | Rechazo del competidor y observación CPU0/threads1 sobre los bytes finales de la tabla superior. |

El único delta de implementación después del intento06 es añadir el nombre
del nuevo supervisor económico a la observación de competidores. Se verificó
con su focal RED/GREEN y se volvió a fijar la prueba CPU con los hashes finales.
No se repitieron suites antiguas cerradas.

Los intentos04/05/06/08 ejecutaron gate RAM/commit y fijaron CPU0 antes de pytest,
con threads1 en el entorno. Los primeros RED/focales y el intento02 no se
presentan como pruebas del protocolo operativo de recursos. La observación CPU
del intento08 registra `mask=1`, los tres hilos a `"1"`, afinidad del padre y
hashes finales. Su archivo publicable es
`continuation_20261029/oof_user_stop_continuation_implementation/attempt_08/cpu0_inheritance.json`.

La integración usa el wrapper congelado con callbacks de productores
artificiales de calendarios vacíos. Adopta el prefijo8 y llama exactamente a
`202605/correction`, `202605/replay`, `202606/correction`, `202606/replay`, una vez
cada uno. Conserva los controles, fuentes, outputs y locks anteriores; el
validador original acepta el cierre final12/27. Otra integración recorre el
supervisor nuevo y un child artificial retenido, incluyendo los fallos de gate,
exit7, afinidad, publicación, deriva posterior, failure extranjero y lock ocupado.

Ruff `F,E9` y compilación sin escribir pyc pasan en los dos archivos finales.
Se copiaron y rehashearon 47 miembros compactos, 575.048 bytes, incluidas todas
las versiones fallidas y sus stdout/stderr/exit. El manifest no se cuenta a sí
mismo. La evidencia no contiene ni atribuye una ejecución del OOF real.

## Contrato que consumirá el binding

`implementation_review.files` debe igualar el mapa de 60 miembros. La propiedad
`cpu0_inheritance_test` tiene exactamente `status` y `evidence`, donde evidence
es `{path,sha256}` y apunta al JSON publicable descrito arriba.

`binding.allowed_read_roots` debe ser exactamente la unión de las siete raíces
del binding original y las dos raíces de snapshot. `binding.published_files`
contiene el mapa de implementación por rutas absolutas, review de implementación,
request operativo, autorización, review independiente del prefijo y su MD,
evidencia CPU, manifest de snapshot del repositorio y sus originales/copias
que residen en el repositorio. El binding se añade a la verificación de
publicación mediante su pin CLI externo; se excluye de su propio mapa interno.
Las copias y el manifest locales se verifican pero no se atribuyen a Git.

Quedan separados la revisión independiente de esta implementación, su publicación,
el binding operativo concreto revisado/publicado, DEFAULT real y su inspección,
el lanzamiento único y la futura auditoría económica FULL_H1. Ninguna de esas
acciones se afirma realizada por este resultado del autor.
