# B06/R3: enmienda operacional de espera acotada de recursos

**Estado: `NON_EXECUTABLE_PENDING_REVIEW`**  
**Fecha de autoridad documental: 2026-11-02**

Esta enmienda responde exclusivamente al cierre fallido de audit05 por déficit de RAM/free-commit después de aproximadamente 3469 segundos. Audit05 no produjo un resultado adoptable: no se reutiliza ningún output, unidad parcial, journal abierto ni observación anterior, y no se relanza o reanuda. La corrección B06/R3 no cambia ciencia, autoridades, pines, schemas, poblaciones, comparaciones, thresholds ni el mínimo oficial de `2_000_000_000` bytes.

No autoriza código, fixtures ni ejecución. Debe publicarse y recibir review documental byte-exacto antes de preparar implementación.

## 1. Identidad y raíces nuevas

Una futura continuación usará exclusivamente:

- `weekly_zone_event_value_paths_audit_06`;
- `weekly_zone_event_value_paths_audit_observer_06`;
- `weekly_zone_event_value_paths_audit_launcher_observer_06`.

Todas las raíces y evidencias 01–05 se preservan inmutables. B06 empieza desde admisión de autoridades bajo raíces ausentes; no hay resume, retry automático, adopción de parciales ni copia de estado científico. La única variación autorizable es scheduling previo al inicio de unidades.

## 2. Defecto operacional acotado

El `resource_gate` actual puede fallar antes de escribir `STARTED` y no conserva la observación rechazada. El camino manual `CACHE_SPOT_PATH` tiene la misma limitación. El helper oficial ofrece actualmente dos operaciones separadas, `observation()` y `gate(observation)`; B06 deberá bindear ambas identidades exactas y no sustituirlas, envolverlas o reimplementar sus umbrales.

La espera sólo es admisible cuando la observación es estructuralmente válida y el rechazo se explica únicamente por déficit numérico conocido. Los tres campos de decisión son:

- `available_ram_bytes`;
- `free_commit_bytes`;
- `disk_free_bytes`.

Cada uno debe ser `int` estricto, no `bool`, y `>=0`. Existe un rechazo esperable sólo si al menos uno es menor que `2_000_000_000`. Son fatales inmediatamente, sin espera: excepción del helper o de disk usage; schema ausente, extra o malformado en los campos requeridos; valor no entero, booleano o negativo; error de path, seguridad o identidad; error de lectura del disco; y cualquier fallo distinto del déficit numérico declarado. Un disco con métrica válida pero bytes insuficientes es esperable; una excepción al medirlo es fatal.

## 3. Protocolo de espera antes de cada unidad científica

Antes de cada unidad científica nueva, y antes de cualquier `stat`, `lstat`, apertura, hash o lectura de sus inputs, se ejecutará este protocolo:

1. Fijar `started_monotonic=monotonic()` y `deadline_monotonic=started_monotonic+600.0` una sola vez para esa unidad.
2. Obtener una observación contemporánea de RAM/free-commit mediante `official_helper.observation()` y de disco mediante la primitiva pineada.
3. Validar schema y tipos antes de clasificar el resultado.
4. Invocar `official_helper.gate(observation)` sobre exactamente la observación obtenida y comprobar el mismo threshold de disco.
5. Si ambos pasan, iniciar el `STARTED` normal del journal científico, incorporando la observación exacta que pasó y el estado de disco; sólo después se admiten paths o inputs.
6. Si el único fallo es déficit numérico conocido, persistirlo como `WAIT`, calcular el sueño acotado, dormir de forma interrumpible y volver al paso 2.

El budget lo gobierna exclusivamente `monotonic()`. UTC es metadata descriptiva y un salto del wall clock no amplía ni reduce los 600 segundos. Cada observación vuelve a consultar los tres recursos; no se arrastra un valor pasado ni se declara recuperación parcial.

El intervalo nominal es 5.0 segundos. Para cada fallo:

`remaining=max(0.0,deadline_monotonic-now_monotonic)`

`planned_sleep=min(5.0,remaining)`

El sueño debe ser interrumpible por señal, user stop o `KeyboardInterrupt`. No se hace busy-polling. Si `remaining==0`, se registra el último `WAIT` con `planned_sleep=0.0`, seguido de `TIMEOUT`; no se duerme ni se vuelve a observar.

## 4. Evidencia durable separada

Las observaciones rechazadas no entran en el journal científico. Se anexan a `resource_wait.jsonl` dentro del observer correspondiente, usando append, flush y file-`fsync` por fila. El archivo tiene una secuencia propia contigua, independiente del journal científico. Todas sus filas tienen exactamente el mismo keyset:

- `schema="weekly_zone_event_value_path_resource_wait_v1"`;
- `seq:int`;
- `status`, enum exacto `WAIT|TIMEOUT|INTERRUPTED`;
- `stage:utf8` e `identity:utf8` de la futura unidad;
- `attempt:int` cero-based dentro de esa espera;
- `utc:utf8` sólo informativo;
- `elapsed_monotonic_seconds:float64` y `remaining_monotonic_seconds:float64`;
- `threshold_bytes=2000000000`;
- `observation:object|null`, copia exacta de la última observación oficial estructuralmente válida;
- `disk_free_bytes:int|null`;
- `deficient_fields:list<utf8>` ordenada lexicográficamente y limitada a los tres nombres declarados;
- `planned_sleep_seconds:float64|null`;
- `final_wait_seq:int|null`;
- `interruption_type:utf8|null`.

Para `WAIT`, `observation` y `disk_free_bytes` no son null, `deficient_fields` es no vacía, `planned_sleep_seconds` está en `[0,5]`, y los dos campos finales son null. Para `TIMEOUT`, se repiten la observación, disco y campos deficientes del último `WAIT`, `planned_sleep_seconds=0.0`, `final_wait_seq` es exactamente el `seq` del `WAIT` inmediatamente anterior e `interruption_type=null`. Para `INTERRUPTED`, `planned_sleep_seconds=null`, `final_wait_seq` es el último `WAIT` de esa unidad o null, e `interruption_type` es el nombre no vacío de la interrupción; `observation`, disco y deficient fields conservan el último valor válido o son respectivamente null, null y lista vacía si la interrupción ocurrió antes de completar la primera observación. `attempt` siempre es el índice de observación que estaba en curso o acababa de registrarse.

Toda observación numérica fallida debe aparecer, incluso la última. No se compactan repeticiones. Tras agotar el budget se añade la fila `TIMEOUT` exacta y entonces se eleva error fatal. No se escribe `STARTED` científico ni se abre un input de la unidad pendiente. Si el fallo ocurre después de que unidades anteriores hayan creado staging u outputs parciales, éstos se preservan como `UNADOPTABLE_INCOMPLETE`; no se promete ausencia de output ni se reutiliza lo ya escrito.

Una recuperación no necesita una fila `READY` en `resource_wait.jsonl`: la observación exacta que pasa el gate oficial y el disco se conserva obligatoriamente en los detalles del `STARTED` científico. Así el journal existente mantiene sus lifecycles `STARTED/COMPLETED/ERROR` sin admitir estados WAIT.

Ante una interrupción capturable (`KeyboardInterrupt`, user stop cooperativo o señal entregada al runtime) después de existir observer, se intenta anexar y hacer durable la fila `INTERRUPTED` exacta; después se propaga la interrupción original. Nunca se convierte en PASS, timeout o retry. En Windows, `TerminateProcess`, force-kill, caída del host o pérdida de energía no garantizan ejecutar un handler ni escribir la última fila: en esos casos la evidencia disponible es best-effort y el cierre externo del launcher/herramienta debe registrar el exit retenido o la pérdida del child; la ausencia de `INTERRUPTED` nunca autoriza adopción. Si append, flush o `fsync` falla, la corrida falla cerrada inmediatamente; no se inicia la unidad ni se afirma que la observación fue preservada.

## 5. Relación con el journal científico

`resource_wait.jsonl` es evidencia operacional del observer, no output científico. Sus filas no cambian schemas, conteos ni lifecycles del journal científico. Un PASS sigue exigiendo para cada unidad científica exactamente el `STARTED/COMPLETED` previsto, cero `ERROR` y ninguna unidad pendiente.

El protocolo se aplica a todos los callsites que hoy pueden iniciar una unidad: autoridades, normalización, footer/source, selección, trayectorias, cada `CACHE_SPOT_PATH` manual, passes, escrituras y cierres. La implementación debe demostrar cobertura de callsites; no basta con modificar el context manager general y olvidar el camino manual de cache.

El child auditor cierra y hace file-`fsync` de su `resource_wait.jsonl` antes de terminar, pero su audit observer no inventa manifest ni exit propios. Después del `wait()` retenido del child, el launcher valida archivo regular/no enlazado y, antes de aceptar un pin de cierre, parsea UTF-8 JSONL completo, exige al menos una fila, keyset exacto, `seq` contiguo desde cero y todos los invariantes de tipo/status/referencia definidos en el apartado 4. Sólo entonces file-pinea y rehashea su propio `resource_wait.jsonl` y el del audit observer, si existen. Su `exit.json` contiene exactamente `resource_wait_pins={"launcher":pin|null,"audit_child":pin|null}`. Cada pin tiene exactamente `path`, `bytes` y `sha256`. No se crea un archivo vacío de forma proactiva. Un null sólo es válido si `resource_wait.jsonl` no existe porque ese observer no persistió ninguna fila; si existe con una o más filas `WAIT`, `TIMEOUT` o `INTERRUPTED`, el pin es obligatorio y `rows>0`. Un archivo truncado o inválido por force-kill se preserva y hashea como evidencia de fallo bajo `resource_wait_invalid_evidence`, obliga exit no cero y no puede poblar un pin de cierre válido ni aparentar PASS. Esta evidencia no se copia al output científico ni se incorpora al manifest de audit output.

## 6. Launcher y creación de procesos

Como delta operacional explícito, el gate inicial del launcher se mueve antes de crear su observer y permanece fail-fast. No existe todavía un lugar durable para esperar. Este único rechazo puede carecer de `resource_wait.jsonl`; se conserva mediante el exit de la herramienta o launcher exterior que retiene el proceso. No se usa una observación histórica para superar ese gate.

Una vez creado `weekly_zone_event_value_paths_audit_launcher_observer_06`, el gate inmediatamente anterior a crear el hijo usa el mismo protocolo bounded-WAIT y su propio `resource_wait.jsonl`. No se crea child, output científico ni audit observer hasta que una observación contemporánea pase helper oficial y disco. Timeout o interrupción conserva el launcher observer y termina sin hijo.

Dentro del auditor, `weekly_zone_event_value_paths_audit_observer_06` debe existir antes de cualquier espera por unidad y aloja su `resource_wait.jsonl` separado. El `STARTED` de cada unidad conserva el PASS exacto. No se añaden workers, procesos de polling ni loops de retry del child: la espera ocurre en el mismo proceso responsable de iniciar la unidad.

## 7. Criterios de fixtures futuros

Antes de una corrida real deberán existir pruebas sintéticas y revisión independiente que cubran, como mínimo:

1. PASS inmediato y igualdad exacta en el threshold para RAM, free-commit y disco.
2. Déficit aislado y combinado de RAM, free-commit y disco con tipos enteros válidos.
3. Secuencia low→recover: todos los `WAIT` durables y exactamente un `STARTED`, posterior al PASS.
4. Always-low: budget monotónico completo de 600 segundos mediante reloj/sleeper inyectados, `WAIT` final más `TIMEOUT`, cero `STARTED` y cero open/stat/hash de inputs de esa unidad; cualquier parcial anterior se preserva no adoptable.
5. Schema malformado, campo no entero/booleano/negativo, excepción del helper y error de disk/path: fatal inmediato sin sleep.
6. Saltos hacia delante y atrás del wall clock que no cambian deadline, elapsed, remaining ni número de sleeps.
7. Sueños de 5 segundos y último remainder menor o igual a 5, sin overshoot intencional.
8. Interrupción durante observación y sleep, más fallo de append/flush/`fsync`, siempre fail-closed y sin swallow.
9. Cobertura explícita del camino manual `CACHE_SPOT_PATH` y de todos los tipos de unidad existentes.
10. Launcher: gate inicial fail-fast sin observer; gate pre-child bounded-WAIT con observer; ningún hijo ni audit observer antes de PASS.
11. Prueba de que bajo low no se llama `stat`, `lstat`, open, hash, lectura o creación de output de inputs científicos.
12. Con recursos always-pass, equivalencia de la proyección científica normalizada: mismos conteos de reconstrucción y comparación; mismos schemas, filas, valores y orden; y mismos hashes de los outputs del productor admitidos. Se excluyen roots, UTC, observaciones de recursos, pines de implementación y evidencia operacional. Los journals científicos deben ser equivalentes por secuencia de `kind/identity`, orden y conteo de lifecycles, después de proyectar fuera timestamps y detalles de recursos; no se exige igualdad byte a byte de journals ni outputs de auditoría.
13. AST/diff limitado a raíces 06, plumbing de espera, binding exacto `observation+gate` y aceptación/pin de `resource_wait.jsonl`; sin cambio científico.

Las fixtures usarán reloj, observaciones, disk probe y sleeper artificiales. No esperarán 600 segundos reales ni abrirán raw, Parquet o NPZ de mercado.

## 8. Invariantes científicas y condición de no ejecución

No cambian contratos elegidos, quotes, clocks de mercado, geometrías, escenarios, modelos, probabilidades, selección, EV, PnL, costes, riesgo o promoción. La espera no convierte un dato missing en presente, no modifica el orden científico de unidades y no permite que una unidad use una observación de recursos tomada para otra.

La implementación y el auditor anteriores permanecen autoridades científicas; B06 sólo puede añadir raíces y plumbing operacional descrito. La publicación y el review documental de esta enmienda preceden a código y fixtures. Después se requieren código/tests nuevos, reviews estáticos, suite formal, binding/launcher publicados y GO separado. Este documento no autoriza ejecución, retry de audit05 ni adopción de ningún resultado.
