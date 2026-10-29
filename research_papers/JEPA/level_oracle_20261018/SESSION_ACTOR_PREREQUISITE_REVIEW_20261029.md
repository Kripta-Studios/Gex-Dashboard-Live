# Revisión documental de prerrequisitos del actor de sesión

29 de octubre de 2026. Revisor: `/root/actor_prerequisite_review`.
Estado: **DOCUMENTARY_READ_ONLY_REVIEW — RESEARCH_PAUSED**.

Este documento conserva la revisión de notas, contratos y código realizada antes
de la nueva orden de pausa. Su escritura forma parte del cierre documental
solicitado por el usuario. No activa una familia económica, arquitectura,
consumidor, entrenamiento o evaluación. Cualquier continuación requiere una nueva
reanudación expresa del usuario; el actor seguiría condicionado al cierre y la
interpretación completos del OOF pendiente.

## Evidencia heredada y alcance nuevo

La [nota científica](EXACT_SESSION_ACTOR_SCIENTIFIC_NOTE.md) define una DP para
la esperanza de una política estocástica sobre un tape exógeno y el adjunto
`d·pi·(Q−V)`. El [laboratorio matemático](EXACT_SESSION_ACTOR_MATH_VALIDATION_RESULT_20261023.md)
documenta 49 pruebas y 204 comparaciones entre enumeración independiente, DP,
ocupaciones, adjuntos, autograd y diferencias centrales. La
[extensión del reloj](SESSION_ACTOR_CLOCK_SEMANTICS_RESULT_20261024.md) documenta
38 pruebas y 188 comparaciones sobre seis grafos artificiales. Sus
[revisiones matemáticas](SESSION_ACTOR_MATH_VALIDATION_REVIEW_20261023.md) y
[del reloj](SESSION_ACTOR_CLOCK_SEMANTICS_IMPLEMENTATION_REVIEW_20261024.md)
separan evidencia del autor y del revisor.

Esos conteos son resultados publicados heredados: esta revisión no reejecutó
pruebas ni revalidó sus artefactos numéricos. La exactitud es condicional al
simulador exógeno y a la suficiencia de `(t,h)`. Capital variable, límites
acumulados o memoria dependiente de acciones exigirían ampliar el estado.
Recomputar por bloques exige conservar parámetros y reproducir exactamente los
logits. Nada de ello demuestra ejecución real, generalización o rentabilidad.

La aportación nueva es la lectura cruzada de esa documentación con `features.py`,
`session_clock.py`, el lector mensual y el validador sintético. No se abrieron
arrays, modelos, scores, outcomes OOF ni valores de datos originales; tampoco se
hicieron extracciones, fits, llamadas externas o cambios de código.

## Soporte diario pendiente de admisión

La [factibilidad publicada](SESSION_ACTOR_DATA_FEASIBILITY_20261023.md) y el
[resultado SessionClock](SESSION_CLOCK_DATASET_RESULT.md) documentan 2.625
identidades: 2.619 disponibles, incluidos 24 días cortos, y seis ausencias. Los
823.284 estados programados y 15.445.024 ofertas son conteos heredados, no un
censo nuevo. La [auditoría SessionClock](SESSION_CLOCK_DATASET_AUDIT_REVIEW.md)
vincula las sesiones completas a la auditoría original y reconstruye las cortas;
no vuelve a calcular toda la economía full.

El índice auditado debe determinar universo y referencias. Las muestras
mensuales cubren aproximadamente el 2,15 % de las ofertas; ni sus chunks ni el
caché TCN sustituyen sesiones completas. IPW no reconstruye exactamente el
softmax ni las ocupaciones de ofertas omitidas. Existe soporte reutilizable,
pero aún no está admitido un consumidor nuevo para el actor.

Se requieren joins uno a uno por `(ticker, fecha, action_id)`, igualdad exacta
del soporte y orden explícito por estado/acción. Igualdad de longitudes u orden
físico no basta. IDs y `contract_i` son claves, nunca features. Deben conservarse
B81, velas `20×45`, mapas `20×5×64`, A33, máscaras y `bar_end_i < state_i`, según
[FEATURES.md](FEATURES.md).

## Diferencia concreta entre máscaras toy y reales

El [validador sintético](session_actor_clock_semantics_validation.py) exige cuatro
booleanos por máscara y todas falsas en slots inválidos. Esa restricción
pertenece a los grafos toy predeclarados. El productor [features.py](features.py)
conserva `map_mask` como fracciones float32 y calcula las máscaras históricas
independientemente de `state_valid`, que depende de IB y spot actuales.

Por tanto, un estado actual inválido puede conservar historia válida. Un
consumidor real no debe borrar esa historia, convertir fracciones a booleanos
ni rechazarla copiando la condición toy. Debe preservar los dtypes y significados
reales. Esta diferencia delimita el alcance sintético: **no establece un bug
productivo** ni invalida las comparaciones matemáticas publicadas.

## Reloj y frontera causal

Conservar todos los slots: full `60..375`, short `60..195`, liquidación hasta
`385/205`. WAIT y NO_FILL avanzan a `t+1` conservando `h`; FILLED avanza a
`exit_i+1` y fija `h=1`. La label NO_FILL guarda `entry_i=exit_i=t+1`, sin bloquear
otro minuto. No hay rescate de otra oferta en el mismo instante.

Estados inválidos o válidos sin ofertas mantienen WAIT. Un día disponible sin
ofertas no se excluye; el sampler mensual rechaza ese caso y su admisión no se
traslada automáticamente. Una fuente ausente sigue siendo `NO_EVALUABLE`, nunca
una sesión WAIT artificial. Las consecuencias pueden compartirse entre `h=0/1`,
pero ocupaciones y probabilidades pueden diferir; no aplicar pesos mitad.

Features y ofertas deben sellarse antes de labels. Status, duración, salida,
netos y elecciones del oracle no definen soporte ni alimentan inferencia.
La DP futura pertenece al objetivo de TRAIN; inferencia usa sólo el actor
causal. Transformaciones usan pasado; política/scores se congelan antes de
outcomes de evaluación. Persisten los límites de reloj proxy y recepción OI.

## Secuencia futura condicional, sin autorización de ejecución

Tras nueva reanudación del usuario y cierre e interpretación completos del OOF:

1. Contrato revisado de admisión: referencias/hashes, alcance de auditorías,
   schemas/dtypes, joins, máscaras, reloj, días sin ofertas y ausencias.
2. Consumidor separado validado contra artefactos auditados, con fixtures de
   soporte omitido, duplicados, orden, NO_FILL, máscaras fraccionarias e historia
   válida en estados inválidos; sin atribuir una nueva auditoría de raw.
3. Metadata de escala y perfil del consumidor bajo ese contrato: distribución
   diaria y máximos de ofertas aún no medidos. Las cuentas publicadas de memoria
   no son RSS ni fijan batch, arquitectura o concurrencia.
4. Sólo si la evidencia completa justifica la hipótesis, predeclarar arquitectura,
   probabilidades, extractor, penalización, épocas, semillas, periodos y freeze.

No se ha elegido ninguna de esas decisiones. Penalización no es PnL; normalizar
retornos cambia el objetivo. Mejor esperanza estocástica no garantiza ledger
greedy rentable ni un fill diario. Los históricos siguen `SEEN_DEVELOPMENT`,
`technical_ready=false` y `promotion_approved=false`. No hay actor económico
activado ni evidencia operable nueva.
