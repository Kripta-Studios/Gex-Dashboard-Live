# Supervisor OOF: implementación y evidencia sintética

24 de octubre de 2026. Implementación nueva preparada; revisión independiente
de bytes finales a cargo de oof_reviewer. **No se ejecutó el pipeline OOF real,
MonthlyInputs, calibración, replay ni auditor económico.** La request documental
continúa no autorizante y los hashes futuros permanecen pendientes del cierre
mensual compuesto y de su salida real observada.

La [spec](OOF_PIPELINE_LAUNCH_SPEC_20261024.md), su revisión previa y el borrador
de request se publicaron, con remoto verificado por root, en
`c91639993fe1458f45f887dceef6184d7c54e296` antes del primer test. La spec conserva
SHA `eeb0dad0d0400bc273d5396c5ec6e6ca936bed8b2145e8a68af0b4e4f9df4770`.

## Resultado implementado

La admisión por defecto sólo verifica metadata y pins, sin crear roots o
lockfiles. Separa los 17 miembros de la request OOF del cierre de 48 archivos
de implementación/imports del supervisor. También exige los 13 pins del auditor
mensual y los once científicos originales del helper, ligados a sus reviews
congeladas. No instancia Request o MonthlyInputs del pipeline.

El binding operativo externo fija request/review, logs nuevos, roots permitidos,
publicación y seis pares `{path,sha256}` de upstream: preflight, process, exit,
completion supervisora, launch del auditor y audit compuesto. Estos valores
deben provenir de cierres reales revisados; este informe no los crea.
La comprobación compacta del audit reutiliza el checker publicado, sin su CLI
ni rehash masivo de fuentes. Sí rehashea contrato e índice actuales.

El padre sólo toma `oof_pipeline_launch.lock`; el hijo conserva la propiedad
de `oof_pipeline_runtime.lock`. Claim durable, gate RAM/commit inmediato antes
de Popen, comando fijo sin resume y handle retenido impiden reintentos implícitos.
El pin original del preflight anterior a Popen se conserva hasta el cierre.
Si una comprobación falla después de un exit real, ese exit se preserva y no se
emite completion supervisora. Fallar antes de iniciar el monitor drena al hijo
sin fabricar un recibo de exit retenido que no se observó.

El cierre exige doce starts/receipts encadenados, seis pares de cierres, contrato,
request y completion exactos. Comprueba particiones e inventario acumulado y
rehash streaming final de outputs, sin parsear payloads científicos ni repetir
la reconstrucción del pipeline. Sólo se excluye `.lock` directamente en cada
raíz de output; un `.lock` anidado es un miembro adicional y se rechaza.
El estado final sigue siendo pendiente de auditoría económica independiente,
sin selección de ganador, promoción o technical_ready.

## Hallazgos cerrados durante la revisión estática

Se corrigieron antes del primer pase, sin cambiar la spec o el pipeline:

| Hallazgo | Corrección y evidencia focal |
| --- | --- |
| O1: igualdad numérica aceptaba bool y tiempos podían carecer de zona | PID entero positivo, creación numérica finita positiva, exit entero y timestamps UTC aware. Negativos de exit False/no cero, PID bool, creación bool/NaN y timestamp naïve. |
| O2: resolver rutas no bastaba para excluir redirecciones | Rechazo de symlinks/junctions en ruta y ancestros; nueve raíces resueltas fijadas en preflight y comparadas al lanzar. Negativos de raíces del recibo cambiadas y junction de padre simulada. |
| O3: sólo tres salidas replay se comparaban con su cierre | Todos los miembros locales de closed.files concuerdan con el inventario; delta replay exacta y delta correction limitada a su raíz. Negativos con hashes re-sellados y salida anticipada en otra raíz. |
| O4: faltaba volver a comprobar rutas al consumir hashes | Se revalidan rutas al consumir el inventario final antes del hash; se rechazan las redirecciones simuladas en los puntos cubiertos. Negativo después de inventariar y antes de hashear; no acredita atomicidad frente a cualquier cambio concurrente. |
| O5: contrato/índice sólo se comparaban como referencias | Rehash real de ambos archivos con los pins del audit. Fixtures mutan sus bytes artificiales y exigen rechazo. |

Se agregó además la comprobación explícita de review mensual49a3/once
dependencias científicas originales, aparte de los 17 OOF y trece del auditor.
Los casos de junction usan monkeypatch declarado: **no son pruebas de creación
de junctions reales de Windows**. La prueba adicional final activa esa simulación
después de crear un hijo Python real y comprueba conservación de exit0/failure
y ausencia de completion. No se modificó código tras el primer pase.

## Validación del autor y versiones preservadas

| Intento | Alcance | Resultado pytest | Versión de tests |
| --- | --- | --- | --- |
| 01 | Suite de metadata/textos y procesos Python inocuos | 34 PASS, 30,72 s | 36e938bc…f78bc |
| 02 | Fallo de publicación inmediatamente postPopen y CLI por defecto | 2 PASS, 34 deselected, 6,07 s | 663f2dcd…a00e3 |
| 03 | Junction simulada después de crear el hijo | 1 PASS, 36 deselected, 6,88 s | 8e5a9df1…65890 |

Los 37 casos se cubrieron por esos tres pases; **no se afirma una ejecución
única de la suite final de 37**. Los dos pases focales añadieron cobertura exigida
sin repetir una integral ya aprobada. Ruff completo y compile PASS en los tres
intentos. No hubo prueba fallida. El supervisor conserva los mismos bytes en
los tres; cada versión de tests y sus logs permanece identificada por hash.

Las fixtures construyen autoridades, doce fases de recibos y payloads de texto
artificiales. La admisión positiva ejecuta los schemas/checkers reales; sólo
se sustituye la frontera Git y las autoridades de fixture. Al probar launch,
se sustituye el comando científico por `python -c pass` o un exit7 controlado.
No es una ejecución integrada de las doce fases OOF científicas ni una medida
de su duración, memoria o I/O. Los hijos se drenan y no quedan procesos de tests.

Recursos Windows registrados **antes de pytest**, bytes:

| Intento | RAM disponible | Commit libre |
| --- | ---: | ---: |
| 01 | 7.020.814.336 | 4.992.708.608 |
| 02 | 6.938.689.536 | 4.852.670.464 |
| 03 | 7.017.639.936 | 4.685.623.296 |

Cada gate exigió al menos 2.000.000.000 bytes por recurso. Son observaciones,
no reservas ni picos. Pins/copias de fuentes, comandos y recursos se capturaron
antes de cada intento; todos coincidieron después. Los 17/13/11 miembros
congelados conservaron sus hashes.

Raíces originales:
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_supervisor_synthetic_20261024_01`,
`_02` y `_03`. El [manifiesto compacto](continuation_20261024/oof_pipeline_supervisor_synthetic/manifest.json)
contiene 48 copias exactas, 244.588 bytes, SHA256
`d22aa864b60e3b91c5aab22eabcb1f8703f2a344f043bd6a0210bb5774e0a5be`.
Incluye los snapshots iniciales y todos los admissions/stdout/stderr/recibos,
sin sustituir intentos anteriores.

## Bytes finales y límites

| Archivo | SHA256 |
| --- | --- |
| launch_oof_pipeline_20261024.py | e93ff7db48c86a6d569e70d18f845ec48575ba2cb226bbed981c28a58245e9a8 |
| test_launch_oof_pipeline_20261024.py | 8e5a9df15149b4afa3c2bab8293624da5a2bd9a27ef75301c0f8dcf0a1c65890 |
| OOF_PIPELINE_LAUNCH_SPEC_20261024.md | eeb0dad0d0400bc273d5396c5ec6e6ca936bed8b2145e8a68af0b4e4f9df4770 |

La revisión independiente de implementación documenta sus focales y ad hoc
separadamente de los resultados anteriores del autor. Este recibo no es review de runtime,
audit compuesto, request autorizada ni permiso de lanzamiento. No se tocaron
pipeline congelado, fuentes, modelos, políticas, producción o API. OOF real
requiere cierre mensual auditado con exit real, request y binding externos
revisados/publicados y decisión final de root.
