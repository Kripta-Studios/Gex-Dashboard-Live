# DRAFT — admisión exacta de fuentes transitivas OOF V2

24 de octubre de 2026. Propuesta técnica, sin implementación, pruebas ni
autorización de ejecución. Corrige una incompatibilidad de admisión de rutas;
no modifica el experimento, productores, calibrador, replay, auditor económico,
modelos, políticas, calendario, umbral, costes o selección. El intento 01 y sus
bytes, revisiones y sellos permanecen inmutables.

## Fallo observado y cobertura que debe resolver

El proceso OOF 29704 terminó con exit 1 observado por handle retenido a las
04:24:25.474349 UTC. `correction_closure` de enero llamó a `verify_map` sobre
`202601.inputs.json`; `Request.allowed_file` rechazó `Input outside declared
roots`. La corrección había producido su cierre, pero no se emitió el recibo
de fase que habilita replay. No se presenta ese cierre como pipeline exitoso
ni como auditoría económica OOF.

El [diagnóstico metadata independiente](OOF_TRANSITIVE_SOURCE_FAILURE_DIAGNOSIS_20261024.md)
cuenta 1.542 de 6.473 inputs fuera de los roots admitidos, todos bajo
`engine_v1`: 741 actions + 741 labels de 2025 y 60 actions de enero de 2026,
sin labels TARGET. Los 1.542 coinciden en SHA con el audit mensual compuesto;
los 18 sidecars de las nueve sesiones cortas ya estaban dentro de session_root.

**El mapa mensual por sí solo no basta.** `MonthlyInputs.source_table` admite
actions/labels mediante `day_root` y sus hashes en el índice auditado, sin llamar
a `MonthlyInputs.verify`. El censo independiente del índice encuentra 126
sidecars de junio de 2026 —63 actions y 63 labels— ausentes de `verified_files`,
pero sellados por el índice. La intersección no tiene conflictos. El universo
202501–202606 tiene 1.113 ticker-días COMPLETE (1.104 full + 9 short), que
aportan 2.226 sidecars; las seis filas MISSING_SOURCE no aportan paths.
El archivo parcial de enero es diagnóstico, nunca autoridad de la lista nueva.

## Autoridades y mapa exacto propuesto

Se mantienen los vínculos externos ya cerrados:

- Audit mensual compuesto:
  `87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e`.
- Audit SessionClock:
  `678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9`.
- Índice SessionClock ligado por ambas autoridades:
  `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`.

La request V2, revisada y publicada con SHA externo, identifica esas mismas
autoridades y el índice. Primero se verifican sus pins, status, roots, contrato,
calendario y vínculos; después se construye un mapa determinista con procedencia:

1. `A`: unión de los grupos `verified_files` del audit mensual compuesto.
   Repetir el mismo path textual y SHA entre grupos es válido y conserva todos
   los grupos de procedencia; un SHA distinto para ese path falla. Construir y
   comparar `A` sólo procesa metadata JSON: no exige nuevos stat o rehash de
   los aproximadamente 48.000 payloads del inventario histórico.
2. `I`: exclusivamente `actions.parquet` y `labels.parquet` derivados de filas
   COMPLETE de 202501–202606 del índice sellado. Se proyectan sólo siete columnas:
   `ticker`, `date`, `status`, `close_i`, `day_root`, `actions_sha256`,
   `labels_sha256`. Se verifican claves únicas, tickers, relojes, fechas y
   cobertura; no se abre ningún sidecar para construir este mapa. MISSING_SOURCE
   conserva sus nulls y jamás se convierte en `Path(None)` o en retorno cero.
3. Unión exacta `A ∪ I`: toda intersección exige SHA idéntico. Se guarda el origen
   de cada miembro (audit/grupo o índice/fila/campo) y un digest canónico del mapa.
   La ampliación para sidecars externos queda acotada a las identidades de `I`;
   referencias de otras fechas en `A` no conceden acceso adicional a sidecars
   fuera de ese calendario. Los artefactos mensuales de fit/escala/modelo ya
   admitidos mantienen su autoridad y uso originales.

SessionClock no tiene `verified_files`: acredita el índice junto con el audit
mensual. Se verifica el SHA del índice antes/después de proyectar metadata y se
revalidan autoridades/mapa antes/después de las fases. No se reejecutan auditores
ni se adoptan hashes actuales como autoridad nueva.

Para un input transitivo fuera de los roots originales, se requiere **pertenencia
exacta de path y coincidencia del SHA declarado por el productor con el SHA de
la autoridad**; luego se conserva el rehash real que ya hace `verify_map`.
No se admiten prefijos de lectura completos de engine_v1, BASE o ThetaData.
Construir el mapa no rehashea todos los sidecars por anticipado; se mantienen
las comprobaciones de bytes efectivamente consumidos.

## Paths, conflictos y protección de outputs

Antes de resolver una ruta se exigen paths absolutos acotados, sin `..` ni
symlink/junction/reparse point en el archivo o sus ancestros. Se rechazan aliases
de la misma identidad Windows, incluidas variantes de mayúsculas, separadores
y enlaces duros. Repetición textual idéntica entre grupos no es un alias.
SHA inválido, conflicto, escape o alias fallan cerrado, conservando evidencia.

La comparación textual de `A` no dispara un recorrido físico de sus archivos.
Las comprobaciones de identidad, hardlinks y paridad entre ruta declarada y
resuelta se acotan a `I` (2.226 sidecars) y a los miembros efectivamente
consumidos. Para miembros existentes de ese conjunto se inspecciona metadata
de identidad, sin abrir valores. Una ausencia no se rellena ni se convierte en
prueba de corrupción histórica: se rechaza cuando ese miembro deba consumirse,
en su comprobación previa de lectura, igual que antes. Se repiten las guardas
de la ruta consumida y los hashes en sus fronteras de lectura/cierre; no se
promete atomicidad universal frente a cambios externos entre comprobaciones.

Pipeline, corrección compartida, seis roots de replay y logs nuevos deben ser
disjuntos entre sí y de código, autoridades, índice, locks, fuentes actuales y
todos los inputs transitivos y sus directorios contenedores. Se comprueba también
la identidad física dentro del conjunto acotado anterior. La protección de
outputs utiliza los paths declarados, sin leer payloads ni recorrer físicamente
todo `A`; no convierte los directorios protegidos en permisos de lectura.
Se rechaza una raíz de output que contenga, coincida o redirija hacia una fuente.
Los outputs propios siguen ligados a sus cierres/recibos: no se convierten en
inputs externos admitidos por pertenecer al nuevo mapa.

**Membresía no equivale a permiso temporal.** Un label TARGET puede figurar en
el índice porque el replay posterior lo necesita. Eso no autoriza leerlo durante
corrección. Permanecen intactos el cutoff del productor, TRAIN estricto,
`target_labels_read=false`, sellado antes del replay y validación del origen de
cada realized histórico. Tampoco se veta globalmente todo label de 2026: hacerlo
rompería el replay autorizado y las correcciones de meses posteriores. La V2
no sustituye controles causales por una comprobación de paths.

## Implementación mínima que se propone revisar

Se recomienda copiar a archivos nuevos el wrapper y el supervisor, con diff
acotado y revisión independiente:

- `run_oof_calibrated_pipeline_v2.py` y su test: admisión transitiva, comprobación
  de SHA externo en `verify_map`, guardas de paths/outputs y metadata de versión
  y dependencias V2. La secuencia de doce fases y las verificaciones científicas
  de corrección/replay deben conservar su lógica.
- `launch_oof_pipeline_v2_20261024.py` y su test: apuntar al wrapper/review V2,
  request/binding nuevos, dependencias publicadas y protección de outputs y logs
  frente al mismo conjunto transitivo. Preflight sólo de metadata; una ejecución
  del hijo, sin llamar calibración, replay o auditor desde el supervisor.

La protección de outputs debe funcionar tanto en preflight como en el wrapper.
Una rutina pequeña en cada archivo, contrastada por revisión/fixtures, evita
otro launcher, preparador o framework. Se reutilizan sin cambios los helpers
publicados de handle retenido, drenaje, recursos y locks.

No se propone monkeypatch del wrapper V1: una subclase sola tampoco cambia el
`Request` usado por su `pipeline`. La copia explícita permite comparar AST/diff:
helpers económicos y faseado iguales salvo metadata declarada; cuatro pins de
adapter/calibrador/replay/auditor literales e idénticos, sin cambiar sus contratos.

Request/contrato de pipeline distinguen V2, con mapa de dependencias exacto en
la nueva review, sin forzar el recuento antiguo de 17. Seis dependencias de
corrección y ocho de replay siguen intactas. Procedencia/digest de admisión se
registran en metadata operativa, sin alterar outputs científicos o sus seals.

## Fixtures necesarias antes de considerar runtime

No se ejecuta ninguna ahora. La cobertura propuesta debe incluir:

- Grafo sintético de fuentes con `engine_v1` como sibling externo: labels TRAIN
  y actions TARGET válidos, sidecars short bajo session_root y cierre completo
  que pasa por el `verify_map` real del wrapper, no sólo por un helper aislado.
- Junio con actions y labels presentes sólo en el índice auditado: admisión
  exacta válida; omitirlos o cambiar su SHA falla. El fixture debe recorrer
  corrección y replay para detectar el fallo tardío que enero no cubría.
- Label TARGET no leído ni añadido a inputs de corrección, incluso si su hash
  consta en la autoridad para replay. Instrumentar la frontera de lectura en
  fixtures, sin cambiar productores; después comprobar su uso legítimo en replay.
- Miembro externo no auditado, SHA consumido distinto de autoridad, conflicto
  entre grupos/índice, índice alterado durante lectura, duplicate key/alias,
  symlink/junction/hardlink y fuente fuera del calendario admitido: rechazos.
- MISSING_SOURCE con paths/hashes null, short/full y cobertura exacta; ninguna
  imputación ni omisión de ausencias para satisfacer frecuencia.
- Outputs/logs dentro de fuentes transitivas, raíces ya existentes, contaminación
  por intento 01 y partials/huérfanos: rechazo sin borrado o adopción.
- Ciclo sintético de las doce fases con productores sin cambios y supervisor
  retenido; errores de creación/monitor/publicación conservan al hijo hasta su
  salida real. Puede reutilizar las fuentes artificiales existentes, sin repetir
  trainer. Verificar un único lanzamiento y ausencia de auditor automático.

La review confrontará por metadata los 1.542 miembros rechazados, los 126 de
junio exclusivos del índice y los 2.226 sidecars, sin arrays ni valores.

## Orden y límites de una eventual continuación

Primero publicar diagnóstico y este DRAFT; después contrato V2, implementación
y fixtures; revisión independiente y publicación de código/tests/reviews; sólo
entonces una request/binding concretos, revisados y publicados, y GO de root.
Ni este diseño ni el futuro contrato de continuación aprueban por sí solos
runtime. La V2 no convierte la corrección de admisión en reauditoría histórica.

El futuro intento usará pipeline, corrección, seis replays y logs totalmente
nuevos. Comenzará con corrección de enero desde cero, sin resume, copiar,
reseñar o reutilizar outputs parciales del intento 01. Mantendrá meses/modes,
locks, gate de 2 GB RAM/commit, ejecución serial y ausencia de retries automáticos.
Un cierre seguirá siendo `PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT`;
la auditoría económica posterior exige su propia admisión. No se lanza ni se
adapta ese auditor en esta propuesta. Todo continúa como desarrollo visto y
sin promoción.
