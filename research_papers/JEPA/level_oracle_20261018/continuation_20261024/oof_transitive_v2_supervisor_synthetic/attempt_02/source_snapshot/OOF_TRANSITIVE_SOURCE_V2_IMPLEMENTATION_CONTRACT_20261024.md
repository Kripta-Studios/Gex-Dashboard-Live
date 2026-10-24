# Contrato de implementación OOF V2: admisión transitiva

24 de octubre de 2026. Autoriza preparar implementación nueva y, únicamente
después de publicar este contrato, sus fixtures sintéticas. No autoriza runtime
real, nuevos modelos o evaluación de mercado. Una ejecución posterior requiere
código/tests/reviews publicados, request y binding nuevos revisados y GO de root.

Autoridades documentales:

- [Diseño V2](OOF_TRANSITIVE_SOURCE_V2_DESIGN_20261024.md), SHA
  `485f557e4ea2d2eb94bfecfd383d59d02ec29381f0eac06a12178fdef9882cc3`.
- [Diagnóstico del fallo 01](OOF_TRANSITIVE_SOURCE_FAILURE_DIAGNOSIS_20261024.md), SHA
  `bd8bd3a8992c27203f0d67dd8ca0726a72615f30714096e0ffd177458b60cf23`.

## Archivos nuevos y diferencias permitidas

Sólo cuatro archivos de implementación/pruebas:

1. `run_oof_calibrated_pipeline_v2.py`.
2. `test_run_oof_calibrated_pipeline_v2.py`.
3. `launch_oof_pipeline_v2_20261024.py`.
4. `test_launch_oof_pipeline_v2_20261024.py`.

Se copian explícitamente los dos originales, que permanecen intactos:
wrapper SHA `26967e10c6b81cd5b84d7939bf6d0c81037934165daa91847d7ffd25de16ff57`;
supervisor SHA `e93ff7db48c86a6d569e70d18f845ec48575ba2cb226bbed981c28a58245e9a8`.
No se añade framework, preparador, tercer launcher ni monkeypatch de ciencia.

El diff permitido comprende: construcción/comprobación del mapa transitivo,
SHA consumido frente a autoridad, paths/aliases/links y protección de outputs;
versiones request/contrato V2; nombres, dependencias, reviews y pins operativos
correspondientes; metadata de procedencia/digest de admisión. El supervisor
apunta al wrapper V2 y protege también su root de logs. Conserva preflight de
metadata, un solo hijo, handle retenido, drenaje y rehash de cierre.

Se mantienen las doce fases correction/replay de enero–junio, tres modos y seis
políticas fijas, umbral cero, costes, selección nula, calendario y reglas causales.
Helpers de reconstrucción económica, checks de seals y protocolo de recibos
encadenados se compararán por AST/diff: sólo se permiten sustituciones de
metadata/versiones expresamente descritas, sin eliminar comprobaciones.
El cierre continúa pendiente de auditoría económica independiente.

## Autoridad exacta de fuentes y límites de I/O

Pins externos requeridos:

| Autoridad | SHA256 |
|---|---|
| Audit mensual compuesto | `87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e` |
| Audit SessionClock | `678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9` |
| Índice ligado por ambos audits | `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4` |

`A` es la unión de `verified_files` mensual, sólo como metadata JSON, sin stat
o rehash masivo de sus aproximadamente 48.000 payloads. `I` se deriva de las
siete columnas del índice fijadas en el diseño, sólo filas COMPLETE de
202501–202606: 2.226 sidecars actions/labels, incluidos 126 de junio ausentes
de `A`. Las seis ausencias conservan nulls. Índice y autoridades se rehashean
antes/después de leer metadata; no se leen sidecars para construir la unión.

`A ∪ I` rechaza conflictos. La ampliación de permiso para sidecars externos
se limita a identidades de `I`; exige path exacto, SHA del input igual al de la
autoridad y rehash de los bytes al consumir/verificar cierre. No admite raíces
enteras, hashes obtenidos como nueva autoridad ni miembros del intento parcial.
SessionClock acredita el índice; no se le atribuye `verified_files`.

Identidad física/hardlinks/paridad de paths se comprueban sólo para `I` y los
miembros consumidos, sin recorrer físicamente todo `A`. Se rechazan aliases,
links y escapes; la existencia requerida se comprueba antes de consumir el
miembro, sin rellenar faltantes. Outputs y logs son nuevos y disjuntos de fuentes,
autoridades, código y otros outputs; esa protección usa paths declarados y no
requiere leer payloads. No se promete atomicidad universal entre comprobaciones.

La membresía de un label TARGET no autoriza su lectura en corrección. Se
mantienen cutoff TRAIN, `target_labels_read=false` y cierre previo al replay;
el mismo label puede usarse legítimamente en replay o como pasado más adelante.

## Pins científicos inmutables

| Archivo | SHA256 |
|---|---|
| `monthly_oof_calibration_adapter.py` | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| `oof_maximum_calibration.py` | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |
| `evaluate_oof_calibrated_policy.py` | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| `audit_oof_calibrated_policy.py` | `e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b` |

Los conjuntos científicos de seis dependencias de corrección y ocho de replay
siguen idénticos. El mapa operativo V2 incluirá wrapper/test V2, este contrato,
diseño y diagnóstico, junto con las demás dependencias congeladas pertinentes;
su conjunto exacto se fija en review, sin forzar el recuento V1 de 17.

## Pruebas y revisión antes de runtime

Antes de cada intento sintético: publicación confirmada por root, pins exactos,
CPU 1 y RAM/commit disponibles de al menos 2.000.000.000 bytes; recibo y logs
nuevos. Se preservan fallos y versiones de todos los intentos. No se ejecutan
pruebas antes de esa confirmación ni se reintentan procesos económicos.

La batería debe conectar el wrapper/supervisor reales con fuentes artificiales
existentes, sin trainer: doce fases; sibling externo engine con labels TRAIN y
actions TARGET; junio index-only con actions/labels; sesiones short y ausencias
null; cero lectura de label TARGET en corrección y uso posterior válido en replay.
Los negativos cubren SHA incorrecto/conflicto/omisión, índice mutado, alias/link/
hardlink, miembro fuera de alcance, output/log que invade fuente, raíz existente,
contaminación parcial01, error de monitor/publicación y ausencia de retry/auditor
automático. Los fallos deben cruzar la admisión/cierre real, no sólo helpers.

Además se inspeccionará cobertura real sólo por metadata: 1.542 referencias
rechazadas inicialmente, 126 de junio index-only y 2.226 sidecars. No se repite
la auditoría histórica ni se abren arrays, modelos, scores o métricas para esto.

monthly_resume hará revisión independiente. Para evitar circularidad, se fija
primero la review del wrapper V2 y su mapa de dependencias; el supervisor nuevo
liga esa review por SHA y recibe después su propia revisión. Recibos previstos:
`OOF_TRANSITIVE_SOURCE_V2_RUNTIME_IMPLEMENTATION_REVIEW_20261024.json/.md` y
`OOF_TRANSITIVE_SOURCE_V2_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json/.md`.
Ninguna review de implementación autoriza por sí sola runtime.

El futuro intento tendrá ocho roots de payload/control y logs totalmente nuevos.
Empezará con corrección de enero desde cero: sin resume, adopción, copia o
reutilización de partials del intento 01. Mantiene locks globales y gate de
recursos; no borra evidencia ni autoejecuta el auditor económico. Código original,
reviews anteriores y resultados ya publicados permanecen inmutables.
