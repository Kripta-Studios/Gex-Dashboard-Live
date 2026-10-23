# Validación matemática previa del actor de sesión

23 de octubre de 2026. **Especificación para revisión y publicación; sin código
implementado ni autorización de ejecución de mercado.** Comprueba únicamente
las identidades de [la nota existente](EXACT_SESSION_ACTOR_SCIENTIFIC_NOTE.md).
No activa una familia, configura una red, escoge una penalización económica ni
cambia las líneas mensual/OOF. Los grafos, recompensas y probabilidades serán
artificiales; no se leerán fuentes, matrices, modelos o outcomes de mercado.

## Objeto y referencia independiente

Un grafo finito acíclico representa decisiones flat en `(t,h)`, donde `h` indica
si ya hubo algún fill. La condición inicial es `(t0,0)`. Se distingue el último
instante de decisión del último instante permitido de liquidación. Toda oferta
de entrada tiene `entry=t+1`; si FILLED, exige `exit>=entry+1` dentro del horizonte
de liquidación y vuelve a decidir en `exit+1`. WAIT y NO_FILL avanzan a `t+1`,
con recompensa cero y sin cambiar `h`. FILLED añade su neto artificial y fija
`h=1`. NO_FILL nunca permite probar otra oferta del mismo instante.

En cada estado existe WAIT y puede haber ofertas adicionales. Un estado sin
ofertas sólo permite WAIT. Después del último instante de decisión:
`V(terminal,h)=-lambda*(1-h)`. La penalización se registra separadamente del
PnL. Para probabilidades fijadas, se contrastarán:

1. **Enumeración exhaustiva de trayectorias:** multiplicar probabilidades,
   acumular recompensas y penalización terminal. Será la referencia directa;
   no llamará a la recurrencia ni a sus helpers de transición.
2. **DP hacia atrás:** `V(s)=sum_a pi(a|s)Q(s,a)`, con las transiciones anteriores.
3. **Ocupaciones hacia delante:** probabilidad total de visitar cada estado,
   sumando todos los caminos que llegan a él.
4. **Adjunto:** `dJ/dz(s,a)=d(s)*pi(a|s)*(Q(s,a)-V(s))`, para logits softmax.

Los grafos tendrán como máximo ocho decisiones con ramificación y tres ofertas
además de WAIT por decisión; podrán incluir instantes de WAIT obligatorio.
Se enumerarán todos los caminos, sin Monte Carlo ni muestreo de acciones.

## Casos mínimos y resultados exigidos

| Caso artificial | Qué debe comprobar |
|---|---|
| Sólo WAIT; ninguna oferta o todas NO_FILL | PnL cero, `P(sin fill)=1`, `J=-lambda`; NO_FILL preserva `h`. |
| FILLED positivo o negativo; exits distintos | Una operación bloquea hasta `exit+1`; su duración altera qué decisiones son alcanzables. No hay solapamiento ni retorno al instante anterior. |
| Dos caminos confluyen en el mismo `(t,h)` | Las ocupaciones se suman, no se sobrescriben. Un estado inalcanzable tiene ocupación y contribución al gradiente cero. |
| Trayectorias con y sin fill, con ambos valores de `h` | `J=E[PnL]-lambda*P(sin fill)`. La penalización nunca entra en el PnL ni en los costes. |
| Tres fills posibles en una rama y ninguno en otra | `E[número de fills]>=1` puede coexistir con `P(sin fill)>0`; no acredita mínimo diario. |
| Ejemplo algebraico de la nota | Recuperar `J=-0,7`, `E[PnL]=0,65`, `P(sin fill)=0,45`, gradientes `1,08` y `0,225`. |

El último ejemplo conserva exclusivamente sus números sintéticos (`p=0,4`,
`q=0,25`, recompensas `+2/-1`, `lambda=3`). Habrá decisiones en `t=0` y `t=2`,
con WAIT obligatorio en `t=1`; el último instante de decisión será `2` y el de
liquidación será `4`. La oferta A en `t=0` tendrá entrada `1`, salida `4` y neto
`+2`; B en `t=2` tendrá entrada `3`, salida `4` y neto `-1`. Ambas llegan al
terminal en `t=5`; WAIT después de la última decisión termina con `h=0`.
Así se conserva el árbol de elección con tiempos válidos. Ese lambda es un
dato del ejemplo matemático, no una propuesta de
penalización para una estrategia real.

Además se rechazará explícitamente un grafo con entrada temprana, salida
anterior a `entry+1`, transición hacia atrás, probabilidades inválidas o una
acción inexistente. La suma de probabilidades terminales debe ser uno; las masas
de estados y ramas deben concordar con la enumeración.

## Gradientes y comprobación numérica

Se usará únicamente CPU y float64. Primero se tratará cada logit como variable
algebraica independiente; después se compartirán variables entre varios estados
mediante expresiones algebraicas pequeñas, sin arquitectura neuronal. Se
compararán el gradiente por autograd de la enumeración, el de la DP, la suma de
adjuntos por regla de la cadena y diferencias centrales con pasos
`1e-4`, `1e-5`, `1e-6`. Los casos diferenciables usarán probabilidades interiores;
las políticas deterministas sólo verificarán valores y ocupaciones.

Tolerancias previas: valores, masas y gradientes analíticos/autograd,
`atol=1e-10`, `rtol=1e-9`; diferencias centrales, `atol=1e-7`, `rtol=1e-5`.
Se informarán los tres pasos y cualquier fallo, sin escoger retrospectivamente
el favorable ni relajar tolerancias para declarar PASS.

La recomputación por bloques mantendrá exactamente las mismas variables y
logits entre pasadas. Se aplicarán adjuntos detenidos y se comprobará que el
gradiente agregado coincide con el grafo completo. No habrá optimizador,
actualización de parámetros, elección de checkpoint ni ajuste por resultado.

## Preguntas que permanecen sin elegir

Se documentará la identidad del softmax plano con logits iguales:
`P(TRADE)=N/(N+1)`. Aquí TRADE significa elegir o intentar una de las `N` ofertas,
incluidas las que producen NO_FILL; no es la probabilidad de obtener un fill.
Duplicar una oferta modifica esa masa; no se exigirá una falsa
invariancia a cardinalidad. Esto no elige entre softmax plano y una puerta
WAIT/TRADE separada: otra parametrización requeriría su propia derivación.

Tampoco se elige cómo extraer una política determinista. Mejor esperanza
estocástica no demuestra mejor ledger greedy. Una penalización finita y WAIT
con probabilidad positiva no garantizan un fill por día. Se preservan como
límites explícitos, no como problemas resueltos por estas pruebas.

La entrega matemática futura deberá incluir grafos completos, resultados de
todas las comparaciones, errores máximos y código/revisión identificados por
hash. Un PASS sólo acreditaría las identidades en esos casos artificiales bajo
transiciones exógenas. No demostraría calidad de datos, fills reales, suficiencia
del estado, generalización o rentabilidad. Implementar esas pruebas requerirá
primero la revisión y publicación de esta especificación por el coordinador.
