# Revisión de continuación causal — propuesta, sin ejecución

2026-10-18. Revisión independiente de `NEXT_EPISODE_LEARNER_PLAN_DRAFT.md`.
No modifica el experimento de episodios, el motor, los modelos existentes ni
sus resultados. Las propuestas siguientes no se han implementado ni entrenado.

## Actualización autoritativa del diseño: mínimo diario de fills

El usuario ha elegido timing libre con **al menos un fill en cada ticker-día**.
No permite CASH como candidato seleccionable ni forzar la primera entrada.
El coordinador ha elegido la ruta de tres fits: maestro π0 con retorno directo
en 2023H1; control directo y alumno residual sobre las mismas filas de
2023H2–2024. La propuesta anterior de cinco fits queda como contraste de diseño,
sin ejecución conjunta. Este apartado sustituye las menciones anteriores a
CASH seleccionable, estado sin historial de ejecución y terminal siempre cero.

Se añade un estado propio `h ∈ {0,1}`: indica si ya ocurrió al menos un fill
en ese ticker durante la sesión. Reinicia en cero cada día. π0 puede continuar
usando sólo las 1954 features originales; control y alumno usan las mismas
1954 más h. El resto de memoria de operaciones propias sigue ausente.

La penalización terminal fija es `lambda_ticker = risk_scale_H1[ticker]`,
aprendida/congelada sólo con 2023H1. No es una comisión, un PnL ni una magnitud
que se barre por resultados. Para la continuación bajo π0:

```
G_pi(t,h) = -lambda * (1-h)                     si t > último_estado_operable
G_pi(t,h) = G_pi(t+1,h)                          si π0 espera o tiene NO_FILL
G_pi(t,h) = r_pi(t) + G_pi(exit_pi(t)+1,1)        si su acción tiene FILLED
```

Las etiquetas residuales correctas son:

```
FILLED:  A(t,a,h) = r(t,a) + G_pi(exit(t,a)+1,1) - G_pi(t+1,h)
NO_FILL: A(t,a,h) = 0 + G_pi(t+1,h) - G_pi(t+1,h) = 0
WAIT:    A(t,WAIT,h) = 0
```

Un fill con PnL cero o negativo cambia h a uno. Un intento sin ejecución no.
Aunque una posición salga después del último minuto de entrada, conserva su
recompensa completa y la continuación terminal con h=1 es cero. Aplicar terminal
cero para h=0 eliminaría precisamente el incentivo declarado. En los minutos
ocupados no se decide ni se vuelve a añadir la penalización.

El cambio a h resuelve la dependencia de la restricción respecto al historial:
`G_pi(t,0)` y `G_pi(t,1)` son continuaciones distintas. Como π0 no depende de h,
su diferencia es exactamente lambda cuando su rollout futuro no consigue ningún
fill, y cero cuando sí consigue alguno. Por tanto, para una acción que ejecuta,
el bonus del residual h=0 aparece sólo cuando esperar y seguir π0 dejaría el
requisito sin cumplir. Esta identidad ofrece una fixture independiente útil.

**Una penalización finita no garantiza el mínimo diario.** El modelo puede
esperar siempre, fallar el fill o elegir operaciones con pérdidas inferiores al
bonus. Deben mantenerse separados el target con penalización, el PnL económico
sin penalización y el hard gate por ticker-día. Si ninguna política satisface
la restricción en validación, el resultado es ninguna candidata elegible; no
se sustituye por CASH ni por la menos incumplidora. Los días sin fuentes siguen
en el calendario: no permiten acreditar cobertura universal, aunque se informe
también cobertura de los días observables. Eso no se arregla inventando fills.

El diseño nuevo elimina muestreo por trayectoria oracle: hasta 128 acciones por
día, 32 por cada uno de cuatro bloques de 79 minutos, selección por hash sin
outcomes y pesos IPW para igual peso ticker-día/acción dentro del día. Si
`N_db` es el número de acciones del bloque, `N_d` el del día y
`p_db=min(1,32/N_db)`, cada fila por h tiene peso proporcional a
`1/(2*N_d*p_db)`. Los bloques vacíos no generan filas ficticias. Normalizar
globalmente por una constante es compatible con mantener esa población.
Control y residual usan exactamente la misma muestra, ambos h y pesos mitad.
WAIT queda estructural en cero, sin fila adicional que cambie la masa muestral.

Duplicar h=1 en el primer estado, aunque no sea alcanzable desde la condición
inicial real, es un contrafactual de la función valor y no una fuga de futuro.
Debe declararse que la población de entrenamiento uniforme en h no reproduce
su ocupación real. No filtrar h mediante eventos futuros. En inferencia sólo se
usa el h de las ejecuciones realmente observadas. Los rollouts del maestro
necesitan todos los estados/ofertas para calcular continuaciones; el cap limita
las filas de ajuste, no las decisiones que puede tomar π0.

Fixtures adicionales: reset diario; h0/h1 difieren por lambda sólo si no hay
fill futuro de π0; fill de beneficio cero cuenta; NO_FILL no cuenta; última
acción ejecutada recibe su PnL íntegro; una sesión sin fill paga lambda una sola
vez en el target y cero veces en el ledger; política sin mínimo diario no puede
ganar selección; ninguna reconstrucción de h usa el futuro de inferencia.

## Conclusión

Sustituir continuación clarividente por continuación de una política ejecutable
está bien motivado. Sin embargo, una cadena pequeña de Q/V entrenados en prefijos
sucesivos añade varios errores de aproximación y mezcla políticas diferentes.
Recomiendo concretar primero una mejora por rollout de **una política fija**,
con target relativo a esperar un minuto. Aprovecha que el simulador actual ofrece
las consecuencias de cada acción sobre la misma trayectoria exógena y evita
estimar un V intermedio. No demuestra edge ni resuelve falta de información.

## Lo que debe corregirse o explicitarse en una versión FQI

1. **WAIT no vale cero en una Q de sesión.** Su valor es la continuación esperada
   desde `t+1`, condicionado por el estado observable actual. El Q de una acción
   debe compararse con Q(WAIT), no con cero absoluto. Tiempo restante, régimen,
   disponibilidad de acciones e historia observable pueden modificar ese coste
   de oportunidad; duración realizada y estado de salida no se conocen al entrar.

2. **Pocas iteraciones no representan todo el horizonte.** Con inicialización
   cero, una iteración incorpora una recompensa/transición adicional. Una
   operación puede saltar muchos minutos; WAIT sólo uno. Dos iteraciones FQI no
   resuelven por sí mismas una sesión de hasta 316 decisiones flat. Tiempo en
   features ayuda a aproximar, pero no sustituye la propagación del horizonte.
   FQI es una secuencia de regresiones Bellman; sus garantías publicadas no se
   transfieren automáticamente a LightGBM y este estado parcialmente observado.
   [Ernst, Geurts y Wehenkel, JMLR 2005](https://www.jmlr.org/beta/papers/v6/ernst05a.html).

3. **OOF temporal no elimina el sesgo del máximo.** Predecir con un modelo pasado
   evita que su ajuste conozca los outcomes del bloque, pero el máximo de cientos
   de estimaciones aún favorece errores positivos. Double-Q separa selección de
   valoración; dos copias idénticas del mismo ajuste determinista no aportan esa
   separación. Tampoco garantiza ausencia de sesgo con modelos correlacionados
   y distribución cambiante. No añadir varios estimadores si no se define qué
   incertidumbre resuelven y cómo se generan sin nuevo tuning.
   [Van Hasselt, NeurIPS 2010](https://papers.neurips.cc/paper_files/paper/2010/hash/091d584fced301b442654dd8c23b3fc9-Abstract.html).

4. **Prefijos distintos no definen una política única.** Si π del warm-up,
   π de 2023 completo y π hasta junio 2024 generan distintos retornos, el modelo
   final aprende una mezcla de sus continuaciones. Puede ser una heurística
   razonable de aprendizaje por políticas sucesivas, pero no debe llamarse
   evaluación exacta de π_final ni FQE de una única política. FQE mantiene fija
   la política cuyo valor intenta aproximar; control y evaluación son tareas
   distintas. [Le, Voloshin y Yue, ICML 2019](https://proceedings.mlr.press/v97/le19a.html).

5. **Muestreo no equivale a cobertura de decisiones.** El IPW existente corrige
   probabilidades de inclusión de acciones en los estratos oracle/resto bajo
   su población objetivo, pero no convierte acciones en estados uniformes ni
   elimina dependencia dentro de una sesión. Estados con muchas ofertas pesan
   más bajo riesgo por acción. WAIT falta en esa muestra; no debe inventarse
   una sola fila por cada operación, duplicándolo miles de veces. Si se usa Q
   explícita, incluir una fila WAIT por minuto flat y fijar su peso relativo
   al bloque de acciones. Si se quiere riesgo uniforme por estado, declarar
   pesos proporcionales a `1/(probabilidad_inclusión × número_acciones_estado)`.
   Ese cambio requiere control con los mismos pesos; no es una mejora gratis.

6. **El problema no es usar futuros como etiquetas.** `r`, estado de salida y
   retorno posterior son targets legítimos de training. Hay fuga si esos campos
   entran en las features actuales, si el productor de la etiqueta fue escogido
   usando ese bloque futuro, o si una decisión del rollout inspecciona el fill
   futuro antes de escoger acción. Las features de `x_tau` pueden contener lo
   conocido a `tau` para construir una etiqueta; no se pasan como inputs de
   inferencia en `t`.

## Alternativa concreta: ventaja frente a WAIT bajo continuación fija

Entrenar una política causal π en 2023H1, con retorno directo y parámetros
predeterminados; fijar antes de producir labels su umbral, desempate y pesos.
No utilizar el modelo actual entrenado hasta diciembre 2024 como productor de
etiquetas de 2023/2024. Como presupuesto inicial acotado: **tres fits** en total,
maestro H1, alumno residual y control directo con las mismas filas que el alumno.

Sobre 2023H2–2024, calcular scores de π para **todos** los estados y ofertas, no
sólo los que visita una trayectoria desde apertura. Guardar su elección causal
antes de consultar labels. Definir `G_pi(t)` como retorno realizado desde estar
flat en `t` y seguir π hasta fin de sesión:

```
G_pi(t) = G_pi(t+1)                         si π espera o intenta NO_FILL
G_pi(t) = r_pi(t) + G_pi(exit_pi(t)+1)       si su acción ejecuta
G_pi(t) = 0                                después del último estado operable
```

Se puede calcular hacia atrás por eficiencia, pero **sin ningún máximo sobre
outcomes**: cada acción ya quedó fijada por π utilizando sólo el estado de su
minuto. Para cada acción ofrecida en `t`, producir:

```
Y(t,a) = r(t,a) + G_pi(next(t,a)) - G_pi(t+1)
```

Es el resultado de tomar esa acción una vez y después seguir π, menos esperar
un minuto y después seguir la misma π. WAIT tiene etiqueta cero por construcción;
NO_FILL también, dado que recompensa cero y transición `t+1` son exactas aquí.
No hace falta entrenar otro regresor WAIT/V. La resta emparejada usa la misma
trayectoria y puede cancelar parte del ruido posterior, sin garantía general
de menor varianza. Se conservan acciones perdedoras y no-fills.

El alumno predice `E[Y|features_t, acción]`, elige máximo score frente a WAIT=0
y mantiene exactamente las salidas del motor. Esto es una mejora aproximada
por desviación de una acción respecto a π, **no** una predicción de ventaja del
oracle ni de Q óptima. Su política puede desviarse otra vez al volver a estar
flat; con estimación imperfecta y observación parcial no se garantiza mejora.
Las familias de mejora por rollout reducen el control a aprendizaje supervisado;
aquí se propone una adaptación, no aplicar su garantía teórica al trading.
[Dimitrakakis y Lagoudakis, 2008](https://arxiv.org/abs/0805.2027).

El control directo usa `r` en vez de `Y`, mismos días H2/2024, filas, pesos,
features y capacidad. Así se atribuye la comparación al coste de oportunidad
causal, en lugar de cambiar simultáneamente objetivo y cobertura temporal.
Mantener las escalas aprendidas sólo con training y reportar explícitamente
el antecedente de muestreo oracle/IPW si se reutiliza la muestra histórica.
No añadir episodios a un brazo solamente. Como opción aún más simple de
muestreo, declarar uno uniforme causal y reutilizarlo en ambos brazos; no
comparar ese cambio directamente como si fuese sólo una modificación de target.

La selección 2025 debe fijarse antes del fit: CASH y un conjunto pequeño ya
declarado de umbrales/ambos brazos. No buscar semillas, ventanas o variantes
de target para rescatar 2026, que sigue siendo desarrollo visto. La política
maestra puede fallar o quedarse en CASH: si siempre espera en un segmento,
`G_pi=0` y el residual coincide allí con retorno directo. Eso es un resultado
informativo; no se reemplaza retrospectivamente el maestro por otro más activo.

## Condiciones específicas de este simulador

### Revisión de la concreción posterior de cinco fits

El implementador de diseño propuso después π0 fija ajustada en 2023H1; V_A
ajustado a retornos de π0 en 2023H2 para producir continuaciones de 2024H1;
V_B ajustado en 2023H2+2024H1 para producir las de 2024H2; Q final y control
directo con las mismas filas de 2024. Son cinco fits, sin inicializar targets
Q con un V vacío. **No hay inconsistencia causal esencial en ese calendario.**

V_A y V_B son regresores Monte Carlo de la misma política fija, no iteraciones
de FQE convergidas. Sus normalizadores/escalas también deben proceder sólo de
sus prefijos y sus predicciones deben volver a USD antes de construir targets
Q. En inferencia Q(WAIT) se estima desde `x_t`; no se consulta `x_(t+1)`.
Continúa el riesgo de aproximar una diferencia pequeña mediante dos Q grandes,
así como elegir pesos relativos WAIT/acciones. La alternativa de tres fits
anterior elimina ese paso V aproximado, pero no se propone ejecutar ambas
familias para escoger retrospectivamente. Esta revisión no activa ninguna.

Reutilizar `G_pi(tau)` entre ramas es válido aquí sólo mientras el mercado y las
features sean independientes de nuestra operación, π no use memoria de trades
propios, y el estado flat no arrastre restricciones de capital, pérdidas diarias,
cooldowns o posiciones de otros tickers. Si se añaden esos elementos, deben
formar parte del estado y el rollout de cada rama puede cambiar. El marco de
entradas exógenas permite aprovechar trayectorias observadas para contrafactuales,
pero no acredita ejecución, impacto nulo o recepción de datos en mercado.
[Sinclair et al., ICML 2023](https://proceedings.mlr.press/v202/sinclair23a.html).

Fixtures mínimos antes de usar datos: π=CASH implica Y=r; NO_FILL implica Y=0;
operación que impide un trade posterior de π descuenta exactamente esa
oportunidad; continuación que pierde no se sustituye por otra ganadora;
último minuto/fin de sesión terminal; empate WAIT antes de consultar fill;
perturbar precios futuros cambia labels pero nunca scores/elecciones previas
de π; repetir scheduler desde cada estado reproduce `G_pi` calculado hacia atrás.

Diagnósticos exclusivamente 2025: error y sesgo residual por estados/acciones,
calibración de acciones elegidas, diferencias por día frente a control y π,
ocupación temporal y tradeoffs de entrar/esperar. Separar error de predicción
de rentabilidad y no tratar millones de acciones correlacionadas como millones
de muestras independientes. Live necesitaría la misma semántica de relojes,
latencia, máscaras, targets congelados y scheduler; esta propuesta no la prueba.
