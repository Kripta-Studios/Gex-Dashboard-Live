# OOF V2R1: corrección de admisión de ausencias declaradas

24 de octubre de 2026. Contrato técnico previo a implementación y pruebas.
`runtime_authorized=false`. Su publicación y confirmación por root permiten
implementar y verificar la reparación acotada descrita aquí; no permiten ejecutar
el pipeline real ni el auditor económico. No cambia ningún contrato económico.

## Evidencia y defecto

El preflight de metadata V2 en
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_v2_metadata_preflight_20261024_01`
terminó con exit 1 antes de crear el hijo pipeline: `Missing-source sidecar must
remain null`. El stderr tiene SHA256
`327e280cbf032bdae851a60b6da8fd2d2685263e147a0f0629f6d371e968b37e`.
El recibo `missing_source_metadata_diagnosis.json` de ese mismo directorio,
SHA `4edb23c994bcdcd00d7c7c549f6f5cb5f2cb489c416dd9b7df57532b45ee672e`,
documenta el único censo de siete columnas realizado por root, con índice
`7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`
idéntico antes y después. No se repite ese censo.

Las seis filas QQQ/SPY × 20260401, 20260409 y 20260415 son `MISSING_SOURCE`,
con `close_i=390`, `day_root` declarado bajo `engine_v1` y ambos SHA de sidecars
nulos. El builder conserva la fila antigua mediante `**oldrow` y marca
`NO_EVALUABLE`; el auditor de sesión verifica ese estado y continúa. El adaptador
exige `COMPLETE` antes de resolver o leer sidecars. No existe un requisito de
nulidad de `day_root` en esas fronteras.

La guarda V2 incorporó indebidamente `day_root` a la comprobación de nulidad.
Su fixture usó una ausencia con los tres campos nulos y no cubrió la forma real.
Es un defecto de admisión y cobertura sintética; no demuestra corrupción de
datos ni aporta un resultado económico. Se preservan el fallo y sus recibos.

## Única reparación funcional y archivos nuevos

Para una fila `MISSING_SOURCE`, exigir únicamente `actions_sha256` y
`labels_sha256` nulos y continuar inmediatamente. `day_root`, declarado o nulo,
es metadata ignorada: no se resuelve, admite, inspecciona físicamente ni abre.
La fila no añade miembros a `I`, permiso de payload ni outputs. Un SHA no nulo
sigue fallando. Ausencia continúa siendo `NO_EVALUABLE`, nunca retorno cero.

Copias nuevas, sin editar los cuatro archivos V2 publicados:

- `run_oof_calibrated_pipeline_v2r1.py` y `test_run_oof_calibrated_pipeline_v2r1.py`.
- `launch_oof_pipeline_v2r1_20261024.py` y `test_launch_oof_pipeline_v2r1_20261024.py`.

Procedencia exacta de los wrappers V2: pipeline
`213eb744b8e295688622955187227df66a56f9121252bd765b7054324e4cceae`;
supervisor `26de981666975ffc3a6c75aa30d7279a133361786a0a6df475ed57017ebae411`.
Además de la guarda se permiten sólo sustituciones operativas explícitas de
nombres, versiones V2R1, contratos, reviews y mapas/pins correspondientes.
La comparación AST/diff debe demostrar que el resto de la lógica permanece.
Los mapas se fijan por igualdad exacta en reviews nuevas; no se relaja un
recuento ni se admite un superconjunto para acomodar la revisión.

El mismo contrato cubre la adaptación posterior, también en archivos nuevos,
`launch_oof_economic_audit_v2r1_20261024.py` y
`test_launch_oof_economic_audit_v2r1_20261024.py`. Sólo cambia su identidad
operativa upstream y pins/reviews hacia V2R1. Conserva todas las comprobaciones
del [contrato del supervisor económico V2](OOF_ECONOMIC_AUDIT_V2_LAUNCH_CONTRACT_20261024.md),
incluida igualdad del digest de admisión entre recibos y pin externo, sin volver
a construir A ∪ I. No se modifica el auditor científico.

## Invariantes y validación suficiente

Sigue vigente el [contrato de implementación V2](OOF_TRANSITIVE_SOURCE_V2_IMPLEMENTATION_CONTRACT_20261024.md),
SHA `85c8bd20107e6a2ee6cf0d6e00bb8d16a7d6b5d1c6bce5839f542266e4c17a8c`,
excepto la precisión de nulidad y las identidades operativas aquí declaradas.
Sus cuatro pins científicos y dependencias de seis/ocho archivos no cambian.
Se mantienen A sólo como metadata, I sólo COMPLETE, autoridad path→SHA exacta,
guardas de alias/links/identidad, disjunción de outputs, cutoffs TRAIN/TARGET,
doce fases, modelos, políticas, costes, selección y scheduler. No se lee ningún
sidecar real, array, score, modelo o métrica para reparar esta frontera.

Fixtures focales pequeñas deben cruzar `Request` y el preflight reales con las
seis identidades anteriores y rutas artificiales declaradas del mismo esquema:

- Ambos SHA nulos: admisión válida, seis ausencias contadas y cero miembros de I
  procedentes de ellas; ninguna resolución/stat/lectura de sus sidecars ni
  creación de destinos. Las rutas declaradas no necesitan existir.
- Cada SHA no nulo por separado: rechazo antes del hijo y sin outputs.
- La forma anterior con `day_root` nulo sigue válida; las filas COMPLETE y su
  admisión no cambian. Los helpers duplicados conservan equivalencia por AST.

No se repiten las doce fases, calibración ni suites completas por este cambio
de metadata. El supervisor económico tendrá sólo focales de esquema/pins V2R1
y rechazo de identidad anterior o digest divergente, sin ejecución científica.
Cada intento conserva pins, comando, logs y exit real en destino nuevo, con
CPU 1 y RAM/commit disponibles de al menos 2.000.000.000 bytes antes de ejecutar.
Un fallo se conserva; nuevas pruebas se limitan a la corrección justificada.

## Revisión y frontera de ejecución

Primero se publica este contrato; después se implementa, prueba y revisa de
forma independiente el wrapper, luego su supervisor con la review ya fijada.
La adaptación del supervisor económico usa esas autoridades finales y recibe
su propia review. Código, pruebas y reviews se publican antes de cualquier uso
real. No hace falta otro contrato para esas sustituciones operativas acotadas.

Request y binding futuros tendrán nombres/versiones y nueve roots nuevos
explícitos `v2r1_01`, mapas exactos y reviews nuevas. Cualquier ejecución real
requiere revisión/publicación de esos materiales y GO de root. Comenzará enero
desde cero: sin resume, adopción ni reutilización de partials de OOF01 o V2.
Se conservan locks, gates, handle retenido, drenaje, comprobaciones de cierre y
ausencia de retry automático. Los originales, snapshots, reviews y fallos
publicados permanecen inmutables.
