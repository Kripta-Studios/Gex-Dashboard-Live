# Revisión independiente del diseño de continuación OOF tras la parada

29 de octubre de 2026. **CLEAR, sólo revisión documental**. No autoriza un
lanzamiento, no acredita una implementación ni admite por sí misma los outputs
reales del prefijo. `runtime_authorized=false`.

Documento revisado:
[OOF_USER_STOP_CONTINUATION_DESIGN_20261029.md](OOF_USER_STOP_CONTINUATION_DESIGN_20261029.md),
SHA256 `ae9d7466aa09f2c43e694fca86a5216d3222e0cff0042b035d7c8d057f54d109`.
El recibo machine-readable compañero contiene los pins de los archivos
consultados y nueve comprobaciones independientes de la cadena antigua.

## Conclusión y fundamento

La adaptación está acotada a supervisión y procedencia operativas. Conserva los
bytes del wrapper R1, su request científico original, las dependencias científicas
y el auditor. La opción existente `--resume` comprueba el prefijo antes de iterar
`phases()[count:]`; la nueva admisión debe exigir exactamente ocho fases, de modo
que sólo se invoquen correction/replay de mayo y junio. Las validaciones de los
meses anteriores y la lectura histórica que requiere el calibrador congelado no
son una nueva ejecución de esas fases.

El launcher original exige destinos ausentes y un comando sin `--resume`. Su
supervisor económico exige una única cadena con exit0. El diseño reconoce ambas
incompatibilidades y crea archivos operativos nuevos. No falsifica un cierre del
primer proceso ni relaja las reglas de su implementación publicada.

Se examinó el código de `completed_prefix`, las validaciones de cierres y el
bucle de continuación del wrapper; los controles del launcher original y la
admisión upstream del supervisor económico; los contratos R1/V2 y las pruebas
existentes de continuidad, mutación y huérfanos. Estas pruebas sólo se leyeron:
no se ejecutó ninguna suite o fixture durante esta revisión.

## Comprobaciones documentales

1. Request original y sus 18 dependencias permanecen exactos. No se cambian
   modelos, calendario, selección, costes, threshold, políticas o scheduler.
2. La autoridad nueva identifica la autorización actual, el snapshot, ocho
   starts/receipts, tail SHA y las cuatro fases pendientes. El permiso antiguo no
   basta para admitir la continuación.
3. El preflight admite metadatos y hashes, exige igualdad completa del árbol y
   del inventario del prefijo, rechaza stages parciales, huérfanos, enlaces,
   aliases y SHA divergentes, y conserva la admisión transitiva R1 exacta.
4. La adopción exige 18 controles iniciales sin failure del pipeline ni
   completion. Esto permite conservar el validador final original de 27 controles
   y doce cierres; no introduce una excepción general para fallos científicos.
5. Los ocho cierres previos, fuentes consumidas, outputs y cinco locks de raíz
   se preservan por bytes y membresía. Los payloads locales se distinguen de las
   copias compactas que realmente se archiven.
6. Primer process/exit/failure/stop y logs originales se pinnean y conservan.
   La identidad retenida process↔exit es exacta; la correlación con el observer
   usa el límite explícito de un microsegundo para su distinta representación.
7. Starts00–07 se ligan a creación/exit originales; starts08–11 a la nueva
   identidad. Las dos cadenas permanecen visibles en el cierre nuevo.
8. El comando futuro añade únicamente `--resume` al wrapper y request originales.
   La supervisión atribuye el monitor al archivo nuevo, sin monkeypatch o
   reasignaciones de autoridades del launcher anterior.
9. Se conservan el lock operativo compartido y el lock runtime del wrapper.
   Los logs nuevos se crean exclusivamente bajo el lock operativo y permanecen
   tras cualquier fallo como marca durable de uso único.
10. CPU0 se impone y verifica en el padre antes de Popen, con evidencia sintética
    de herencia desde la primera instrucción del hijo. Se mantienen threads1,
    gate RAM/commit de 2.000.000.000 bytes, ventana oculta, handle y drain.
11. Después del exit0 real se usa la validación final original y se rehashea el
    baseline, incluidos logs/stop/snapshot y locks. Cualquier diferencia impide
    un completion válido. No existe retry automático ni auditor automático.
12. La auditoría posterior conserva el auditor científico FULL_H1. Su nueva
    admisión operativa exige dos cadenas explícitas; sólo puede admitir el
    failure histórico exacto. Un fallo nuevo o ajeno permanece excluyente.

Los cuatro detalles precisados antes del pin final —CPU0 previo al child, cinco
locks, logs exclusivos durables y cronología de ambas tandas de fases— quedan
explícitos en la versión revisada. No quedan hallazgos documentales bloqueantes.

## Evidencia independiente limitada

Se verificaron nueve relaciones de los recibos originales: igualdad de identidad
y autoridades process/exit, exit entero15, enlace SHA exit→process,
process→preflight, pins de request, binding y monitor, correlación PID/comando con
la parada y ausencia de completion del supervisor antiguo. Las nueve cumplen.

El observer registra creation `1792819783.1543567`; el handle retenido registra
`1792819783.154357`. La diferencia es `2.384185791015625e-7` segundos. No se
reescribió ninguno de los dos recibos. La tolerancia documental es adecuada para
esta correlación y no se aplica a la igualdad entre process y exit retenidos.

El árbol de control enumerado tiene request, contract y starts/receipts00–07,
sin completion o failures. Esta enumeración y los nueve checks compactos no
constituyen una auditoría del contenido científico del prefijo. En esta revisión
no se rehashearon sus 8.726 outputs ni todas sus fuentes, ni se interpretaron
calibraciones, scores, PnL o métricas. La verificación completa real tiene su
evidencia separada y sigue siendo requisito de admisión.

## Validación futura suficiente y límites

Las diez familias de fixtures del diseño cubren las fronteras necesarias. Deben
demostrar especialmente: prefijo8 exacto y DEFAULT sin escritura; rechazo de
mutación/hueco/huérfano/alias; cuatro llamadas restantes una sola vez con productores
artificiales; locks y claim durable; CPU0 desde el inicio y gate vigente;
fallos del monitor, exit y drift tardío sin completion; y preservación de las dos
cadenas para la auditoría posterior. No hace falta repetir una evaluación
científica real para probar estas fronteras.

La implementación, sus pruebas y revisión independiente deberán publicarse antes
del request/binding concreto y de su preflight real. El snapshot, las parejas
original/copia, el inventario real completo y la fuente de autorización deben
quedar fijados externamente. La revisión documental no sustituye ninguno de esos
pasos ni afirma que ya estén terminados.

La implementación del supervisor económico puede recibir su propia revisión y
publicación después: su ejecución sigue bloqueada hasta doce cierres, exit0 y
binding real nuevo. Esta dependencia explícita basta para continuar preparando
el supervisor del pipeline. `technical_ready=false`, selección nula y
`promotion_approved=false` permanecen intactos.
