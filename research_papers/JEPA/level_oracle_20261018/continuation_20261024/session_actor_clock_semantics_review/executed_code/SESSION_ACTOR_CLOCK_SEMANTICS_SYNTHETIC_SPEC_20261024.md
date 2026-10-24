# Verificación sintética de reloj y máscaras del actor de sesión

24 de octubre de 2026. Alcance exclusivamente matemático y sintético. Esta
extensión es nueva y aislada: no importa, modifica ni reejecuta el laboratorio
anterior, ni abre fuentes, matrices, modelos, scores o labels de mercado. No
activa una familia económica, arquitectura, optimizador, entrenamiento u OOF.
Root debe publicar esta especificación revisada antes de cualquier comparación
o test matemático. Los programas pueden prepararse antes sin ejecutarse.

La brecha documental procede de
[SESSION_ACTOR_DATA_FEASIBILITY_20261023.md](SESSION_ACTOR_DATA_FEASIBILITY_20261023.md):
la representación real de NO_FILL lleva `exit_i=t+1`, mientras el laboratorio
abstracto anterior usaba `exit=None`. Convertir todas las salidas en `exit_i+1`
saltaría indebidamente la decisión siguiente. La nueva prueba verifica esa
distinción con consecuencias artificiales; no admite un consumidor de datos.

## Semántica fijada

Estado `(t,h)`, inicialmente `(start,0)`, donde h indica si ya hubo algún fill.
Se conserva cada slot consecutivo del calendario de decisiones, incluidos los
inválidos y los válidos sin ofertas. No se comprime el reloj. Slots llevan
`state_valid` y máscaras booleanas pequeñas token/bar/map: se conservan por
identidad y orden. No son tensores del esquema productivo ni prueban sus shapes.
Un slot inválido carece de ofertas y sólo permite WAIT; un slot válido puede
tener máscaras parciales. Estas máscaras no dependen del resultado de ofertas.

Cada oferta existe en el soporte antes de consultar su status artificial;
NO_FILL sigue siendo una oferta elegible, no se elimina del softmax. WAIT
siempre existe. Se distinguen el número de intentos, el de fills y la
probabilidad de terminar sin ningún fill.

| Acción | Representación artificial | Próximo estado y recompensa |
| --- | --- | --- |
| WAIT | Sin oferta | `(t+1,h)`, cero |
| NO_FILL | `entry_i=exit_i=t+1`, neto cero | `(t+1,h)`, cero; cuenta un intento, cero fills |
| FILLED | `entry_i=t+1`, `t+2<=exit_i<=last_liquidation` | `(exit_i+1,1)`, neto artificial; un intento y un fill |

Después de `last_decision`, el valor terminal es `-lambda*(1-h)`. La
penalización permanece separada de PnL y no se convierte en coste o pérdida
económica. Lambda será **3 unidades artificiales** en todos los grafos, sin
elegir una penalización real. No hay estado artificial para una fuente ausente:
`NO_EVALUABLE` se rechaza y no equivale a un día WAIT de PnL cero.

## Grafos fijados antes de resultados

Los nombres de ofertas son únicos dentro de cada slot. Salvo las excepciones
indicadas, los slots son válidos, máscaras verdaderas y no tienen ofertas.
Las máscaras toy tienen cuatro elementos; un slot inválido conserva cuatro
false en cada máscara. El primer slot válido de cada grafo conserva además
la máscara parcial token `[true,false,true,false]`.

| Grafo | Decisiones; liquidación máxima | Ofertas `(t,status,exit_i,neto)` | Slots inválidos |
| --- | --- | --- | --- |
| wait_only | 0..3; 5 | ninguna | 1,2 |
| no_fill_only | 0..3; 5 | (0,NO_FILL,1,0), (2,NO_FILL,3,0) | 1 |
| mixed | 0..8; 10 | (0,NO_FILL,1,0); en 1 dos ofertas: (FILLED,3,+4), (NO_FILL,2,0); (4,FILLED,6,-2); (6,FILLED,8,+1) | 2,5 |
| full_clock | 60..375; 385 | (60,NO_FILL,61,0), (61,FILLED,63,+2), (375,FILLED,385,+1) | 62,374 |
| short_clock | 60..195; 205 | (60,NO_FILL,61,0), (61,FILLED,63,+2), (195,FILLED,205,+1) | 62,194 |
| retry_counterexample | 0..1; 3 | (0,NO_FILL,1,0), (1,FILLED,3,+7) | ninguno |

No hay inputs aleatorios. Se usan ambos valores de h en cada slot, incluso si
alguno es inalcanzable. Los calendarios full/short reproducen sólo los límites
documentados, con unas pocas ramas artificiales; no son sesiones de mercado.

Contraejemplo determinista: intentar ambas ofertas de retry_counterexample da
PnL 7, dos intentos, un fill y objetivo 7. La regla errónea NO_FILL→exit_i+1
salta t=1 y produce PnL 0, un intento, cero fills y objetivo -3. La diferencia
se presenta como detección de un bug matemático, nunca como mejora de estrategia.

## Referencias independientes y derivadas

La enumeración exhaustiva expande caminos directamente, sin llamar a DP,
ocupaciones ni helpers de transición. Multiplica probabilidades, acumula neto,
intentos y fills, y calcula masas de visita, rama y terminal. Su derivada
analítica independiente aplica producto/suma sobre probabilidades de caminos:
masa × utilidad terminal × suma de derivadas de log-probabilidad. No utiliza
valores Q ni ocupaciones del algoritmo contrastado.

DP inversa y ocupación hacia delante se implementan por separado sobre todos
los slots. Adjunto softmax: `d(s)*pi(a|s)*(Q(s,a)-V(s))`. Se comparan objetivos,
PnL, intentos, fills, probabilidad sin fill, masas de estados/ramas/terminales,
suma terminal uno y separación de la penalización. Slots WAIT y estados
inalcanzables deben conservar su presencia; estos últimos aportan gradiente cero.

Se ensayan logits independientes de cada acción en estados con ofertas, y tres
variables compartidas por expresiones lineales fijas. WAIT obligatorio tiene
probabilidad uno y no necesita parámetro. Valores independientes iniciales
siguen el layout por t ascendente, h=0 y luego h=1, WAIT primero y ofertas
en el orden declarado en la tabla (en t=1 de mixed: FILLED y luego NO_FILL).
Los estados WAIT obligatorios se conservan en el calendario y no añaden logits.
Los valores independientes son
`(i mod 7 - 3)/5`; compartidos `[0.2,-0.3,0.4]`. Para índice de logit i:
`z_i=(1+(i mod 3)/4)*theta[i mod 3]+0.1*theta[(i+1) mod 3]`.
No se actualiza ninguna variable. El adjunto compartido se acumula mediante
regla de la cadena, sin pesos mitad heredados de otro aprendiz.

Además de la derivada analítica de enumeración se calculan diferencias
centrales del objetivo enumerado con **los tres pasos 1e-4, 1e-5 y 1e-6**.
Float64 CPU (float nativo Python). Tolerancias fijadas: valores, masas y
derivadas analíticas `atol=1e-10, rtol=1e-9`; diferencias centrales
`atol=1e-7, rtol=1e-5`. Se registran todos los errores y pasos; no se relajan
tolerancias ni se escoge sólo el paso favorable. Políticas deterministas se
usan para el contraejemplo y límites de reloj, sin exigir derivada de log cero.

Negativos mínimos: calendario comprimido o desordenado; índice booleano;
máscara no booleana; oferta en slot inválido; NO_FILL con salida errónea o
recompensa no cero; FILLED demasiado temprano o después del cierre; status
desconocido; oferta omitida o inventada; política no normalizada; fuente ausente.
La oferta NO_FILL y una versión FILLED válida deben conservar el mismo soporte
de nombres, aunque sus consecuencias y ocupaciones cambien.

## Evidencia y límites

Archivos nuevos: `session_actor_clock_semantics_validation.py`,
`test_session_actor_clock_semantics_validation.py`, esta spec y recibos separados.
Antes de cada intento se capturan en root local nuevo los SHA de código/tests/
spec, comando y recursos Windows. Gate: RAM disponible y commit libre cada uno
>=2.000.000.000 bytes, antes de pytest o CLI. Se conservan stdout/stderr, exit,
duración y cualquier fallo; pins se revalidan después. No se sobrescribe un
intento ni se lanza automáticamente otro. La revisión independiente corresponde
a scientific_review y distingue sus pruebas de las del autor.

Un PASS sólo verifica estos grafos artificiales y la representación de reloj
descrita. No valida joins, dtype/shape de packs reales, paridad de fuente,
admisión histórica, suficiencia de `(t,h)` fuera de reglas fijas, ni rentabilidad.
Arquitectura, extractor determinista, cardinalidad efectiva, penalización real,
entrenamiento y una nueva hipótesis económica siguen sin elegir. No se reabren
políticas cerradas ni se sustituye el cierre mensual y OOF pendientes.
