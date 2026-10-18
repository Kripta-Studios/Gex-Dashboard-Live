# Aprender del oracle: redes, agentes y planificación causal

Revisión del 18 de octubre de 2026. Literatura primaria consultada en la web y revisión estática de `PROTOCOL.md`, `LEARNER_PLAN.md`, `features.py`, `level_engine.py`, `train_models.py` y `run_policy.py`. Este documento no ejecuta modelos, no abre nuevos resultados económicos y no cambia los entrenamientos actuales. Las propuestas posteriores no están implementadas ni evaluadas.

Sí es técnicamente posible entrenar una red y construir un agente que aprenda parte del comportamiento del oracle. La pregunta empírica es cuánto de sus decisiones se puede anticipar con el pasado disponible y cuánto beneficio conserva esa parte después de costes. Un oracle rentable no responde por sí solo a esa pregunta; tampoco la responde negativamente el fallo de una arquitectura concreta.

## Qué hace realmente nuestro oracle

Según el código, el oracle no dibuja una tesis ni identifica verbalmente un rebote. Primero recibe todas las acciones que pueden ofrecerse causalmente: minuto de entrada cercano a una zona, CALL/PUT, contrato disponible próximo a una de tres deltas, objetivo y stop conocidos. El objetivo elegido puede quedar más allá de niveles intermedios. El motor fija entonces la salida por target, stop o fin de sesión con la misma latencia y costes para todos.

Después, una programación dinámica mira los resultados futuros de esas acciones y elige la secuencia de mayor beneficio total, evitando solapamientos. Puede rechazar una operación individualmente positiva porque bloquearía otra posterior mejor. Está resolviendo conjuntamente **cuándo esperar, cuándo entrar, qué opción comprar y qué objetivo elegir**, con conocimiento retrospectivo de la sesión. No modifica libremente la salida minuto a minuto una vez elegido el contrato/target/stop.

El perfil económico observado —duraciones, objetivos, entradas, deltas, efectos de costes— pertenece al análisis de comportamiento separado. Aquí no se deducen esas frecuencias a partir del algoritmo ni se da por supuesto que el oracle opere como un humano. Tampoco se atribuye un mecanismo causal de cobertura de dealers a una coincidencia descriptiva con un wall.

## Lo que ya está definido para aprenderlo

La implementación actual compara dos GBT condicionados por acción y una red temporal/espacial. El primero aprende retorno neto; el segundo, ventaja del oracle frente a esperar. La red recibe las doce velas completas de cinco minutos y ocho de quince, mapas espaciales de niveles/exposiciones y la acción candidata; predice retorno neto y tiene una cabeza auxiliar de imitación. La probabilidad auxiliar no decide operaciones. Todos conservan WAIT, ejecución común y selección con CASH en 2025.

Son tres enfoques concretos, no una prueba de todas las redes ni de toda planificación. La red actual no es un JEPA, un Transformer preentrenado ni un simulador de futuros. Sus pesos no representan una política óptima conocida. Los resultados deben proceder de los artefactos de entrenamiento y evaluación, no de este documento.

## Qué aportaría un sistema de agentes

Hay tres componentes distintos que pueden combinarse:

| Componente | Aportación posible aquí | Información que debe recibir |
|---|---|---|
| Agente de investigación | Formular hipótesis, programar experimentos, comprobar errores y explicar resultados | Datos de desarrollo permitidos y registro de intentos |
| Agente operativo | Mantener inventario, consultar niveles/modelos, comparar planes y aplicar la política | Sólo snapshots y estado de cuenta disponibles hasta el reloj simulado |
| Red predictiva y planificador | Estimar distribuciones de resultados y decidir entre esperar o elegir contrato/objetivo | Historial causal, incertidumbre y reglas de ejecución |

Una conversación entre varios agentes no añade una observación del mercado que no exista en sus entradas. Puede mejorar el procesamiento de esa información, la organización de herramientas o la coherencia de una decisión; ese beneficio debe medirse. Un texto convincente sobre “el precio irá al call wall” no sustituye una probabilidad calibrada ni un retorno esperado verificable.

Para este dataset, el papel inmediato más sólido de un LLM sería trabajar sobre herramientas numéricas: obtener el estado causal, enumerar acciones válidas, solicitar predicciones y producir una explicación ligada a esos valores. No inventar precios ni escoger por su cuenta qué dato futuro consultar. Una prueba de una política LLM necesitaría prompts, memoria y herramientas congelados, latencia/coste medidos y un control de la contaminación histórica de su preentrenamiento. Ocultar fechas ayuda a reducir pistas, pero no demuestra ausencia de memoria del periodo. La investigación web actual no se convierte en una feature retrospectiva del trader.

## Literatura primaria y qué permite inferir

La selección siguiente es relevante para este problema; no es una clasificación universal de algoritmos de trading.

| Trabajo y fecha comprobada | Resultado pertinente | Límite de la extrapolación |
|---|---|---|
| [Hindsight Learning for MDPs with Exogenous Inputs](https://proceedings.mlr.press/v202/sinclair23a.html), ICML 2023 | Usa trazas exógenas y planificación retrospectiva para aprender decisiones; caracteriza el sesgo que introduce el conocimiento del futuro | Sus experimentos son asignación de recursos, no opciones; la observación parcial del mercado exige cuidado adicional |
| [TD-MPC2](https://proceedings.iclr.cc/paper_files/paper/2024/hash/cf73d57b6dcda32b293df7c2d5341f49-Abstract-Conference.html), ICLR 2024 | Planificación con modelos latentes, evaluada en 104 tareas de control continuo | No valida un simulador financiero ni sus costes |
| [Provable Partially Observable RL with Privileged Information](https://arxiv.org/abs/2412.00985), NeurIPS 2024; versión revisada 20-02-2025 | Formaliza problemas de destilar un experto privilegiado y condiciones bajo las que resulta eficiente | Las garantías requieren supuestos específicos; no certifican nuestro histórico |
| [Dreamer: Mastering diverse control tasks through world models](https://www.nature.com/articles/s41586-025-08744-2), publicado 02-04-2025 | Aprende un modelo del entorno y mejora la política mediante escenarios imaginados | Sus tareas de control no prueban capacidad de anticipar retornos de mercado |
| [V-JEPA 2](https://arxiv.org/abs/2506.09985), enviado 11-06-2025 | Une predicción latente auto-supervisada y adaptación condicionada por acciones para planificación robótica | Los vídeos y acciones de robots no equivalen a velas ni a incertidumbre de cotizaciones |
| [To Distill or Decide?](https://arxiv.org/abs/2510.03207), enviado 03-10-2025; NeurIPS 2025 | En sus modelos y experimentos, la estocasticidad afecta la comparación entre destilación y RL; el mejor experto privilegiado no siempre es el mejor para destilar | No demuestra imposibilidad de aprender nuestro oracle |
| [Guided Policy Optimization](https://arxiv.org/abs/2505.15418), enviado 21-05-2025; revisión 13-03-2026 | Coentrena un guía privilegiado y un aprendiz procurando que las políticas permanezcan alineadas | Es una vía para estudiar teachers imitables, no una rentabilidad financiera ya demostrada |
| [V-JEPA 2.1](https://arxiv.org/abs/2603.14482), enviado 15-03-2026; revisión 11-06-2026 | Mejora representaciones visuales densas y su estructura espacial/temporal | El resultado es visual/robótico, no un benchmark financiero |
| [FF-JEPA](https://arxiv.org/abs/2606.09311), preprint 08-06-2026 | Propone subobjetivos latentes y planificación jerárquica; resultados preliminares en PushT | Evidencia inicial en un entorno concreto; no fundamento suficiente para priorizar un gran entrenamiento local |

El encaje con procesos exógenos es una **inferencia para nuestro diseño**: bajo el supuesto de operar un contrato sin impacto, comprar una CALL cambia nuestro inventario, pero no hace que SPY suba en la reproducción histórica. Por ello pueden compararse acciones alternativas sobre la misma trayectoria local sin inventar un libro de órdenes interactivo. Este supuesto no acredita fills reales ni escalabilidad de capital.

Los agentes LLM financieros sí tienen antecedentes. [TradingAgents](https://arxiv.org/html/2412.20138v7), enviado en diciembre de 2024 y revisado en junio de 2025, presenta analistas y debates especializados; su evaluación descrita usa acciones y decisiones diarias durante enero–marzo de 2024. Ese resultado no establece ventaja en opciones 0DTE a un minuto con nuestras fuentes, Greeks y ejecución ask→bid. Es una referencia de organización, no evidencia transferible de rentabilidad.

## Planificar sin consultar el futuro real

[MuZero](https://www.nature.com/articles/s41586-020-03051-4), publicado en Nature en 2020, combina un modelo aprendido con búsqueda en árbol. Esa búsqueda no es búsqueda binaria. En nuestro caso sería lícito explorar **predicciones** de escenarios producidas por un modelo entrenado con pasado. Consultar las velas reales siguientes para puntuar las ramas sólo sería lícito dentro del oracle retrospectivo.

Un modelo financiero debería representar varios futuros posibles, no una única trayectoria suave. La simulación debe propagar precio, IV, spread y tiempo restante, o al menos resultados económicos suficientes para la decisión. Un spot que alcanza el objetivo no garantiza beneficio en una opción comprada al ask: la trayectoria y el paso del tiempo importan. Un planner que maximiza dentro de un simulador mal calibrado puede seleccionar sus errores más optimistas.

Por ello, la comprobación previa a aumentar profundidad de búsqueda sería medir en 2025 la calibración de eventos y precios/retornos proyectados. Hasta disponer de un modelo validado para esa tarea, puntuar las acciones conocidas directamente es una alternativa más sencilla y auditable. La planificación también puede aportar valor al coste de oportunidad de mantener una posición, aunque no mejore la predicción del siguiente movimiento.

## Diagnósticos de aprendibilidad, sin seleccionar sobre 2026

Todo ajuste de estos diagnósticos usaría 2023–2024, con cortes temporales completos por sesión; la evaluación de diseño sería 2025. Los datos de 2026 seguirían siendo desarrollo ya visto y nunca justificarían rescatar un candidato, ticker, horario o umbral. Las métricas siguientes aún no se han calculado en este documento.

1. **Predecibilidad de decisiones separada de PnL.** Evaluar WAIT/entrada, lado y ranking de objetivos con log-loss, precisión/recobrado y distribución de clases. Accuracy alta por predecir siempre WAIT no demuestra aprendizaje. Comparar contra frecuencias basadas sólo en ticker/hora y contra acciones elegibles uniformes. Usar todas las acciones con sus pesos, no únicamente las ganadoras del oracle.

2. **Equivalencia práctica entre acciones.** Medir también si la elección cae en un conjunto casi óptimo fijado antes del diagnóstico; equivocarse entre dos targets de PnL parecido no equivale a escoger una gran pérdida. El conjunto usa labels retrospectivos sólo para evaluar, nunca para filtrar las acciones del trader.

3. **Calibración económica.** Para bandas de predicción definidas con train, comparar retorno predicho y realizado de todas las acciones y, por separado, de las realmente elegidas. Mostrar target/stop/EOD, no-fill y pérdidas. Una tasa alta de TARGET puede coexistir con PnL negativo. La unidad independiente para incertidumbre es la sesión, no millones de acciones correlacionadas.

4. **Brecha de imitación frente a brecha económica.** Con V del oracle, para cada decisión efectivamente visitada por el aprendiz se puede calcular el diagnóstico retrospectivo V(t)−[R(a)+V(siguiente estado operable)], incluyendo WAIT y no-fill. La suma telescópica reproduce V(inicio)−PnL del aprendiz bajo el mismo motor. Permite localizar decisiones costosas sin afirmar que esa diferencia fuera evitable con información causal. Este diagnóstico es una derivación del DP del repositorio.

5. **Ablaciones del privilegio.** Sobre train/validación, restringir por separado el oracle a relojes de cinco minutos, un solo bucket delta o el target más próximo; mantener fills y costes. Medir cuánto techo depende de sincronización exacta, selección contractual o saltarse niveles. No interpretar el mejor oracle restringido como estrategia operable. Una perturbación de entrada debe reconstruir la elegibilidad causal en ese nuevo minuto, no conservar una entrada que ya no cumple las reglas.

6. **Dependencia de exposición y geometría.** Comparar modelos de capacidad equivalente con y sin mapas de niveles, o con un placebo construido antes de outcomes; hacerlo como experimento posterior separado. Un buen oracle con Fib no demuestra que Fib aporte información por encima de la oportunidad de escoger entre muchas operaciones. Una mala ablación tampoco prueba que cualquier representación visual vaya a fallar.

7. **Estabilidad y datos suficientes.** Revisar curvas de aprendizaje por años/bloques y variación entre meses, con todos los resultados. Patrones distintos ante estados aparentemente parecidos pueden indicar observación incompleta, ruido, drift o una representación insuficiente. No estimar un límite matemático de aprendibilidad a partir de una sola red o de una accuracy baja.

## Siguiente alternativa acotada si falla la política actual

Primero completar y conservar los tres fits actuales. La siguiente hipótesis propuesta sería que **aprender eventos y distribución económica conjuntamente resulta más útil que imitar una única acción clarividente**. Usaría el mismo encoder temporal/espacial, las mismas acciones y el mismo motor; dos brazos de arquitectura/capacidad comparable: retorno directo sin teacher auxiliar y retorno acompañado por objetivos de no-fill, TARGET/STOP/EOD y distribución de retornos. No introduce una salida fija ni cambia los objetivos después de observar el futuro.

Esos eventos son labels de entrenamiento. En inferencia sólo entran el historial y cada acción causal. La rentabilidad se sigue evaluando con quotes reales del replay y el scheduler, no sumando probabilidades de acierto. Arquitectura, pérdidas, presupuesto, calibración y regla de abstención tendrían que quedar fijados antes de entrenar esa familia; CASH y costes adversos seguirían presentes. El documento no autoriza elegir hiperparámetros por el resultado de 2026.

Si los diagnósticos muestran predicciones de operación útiles pero mala coordinación temporal, la alternativa posterior sería aprender continuaciones de una **política causal**: retorno de la operación más valor de la siguiente oportunidad bajo esa política. Eso distingue coste de oportunidad de V-oracle, que supone conocer todo el futuro. Sólo después de calibrar esa parte tendría sentido probar un world model y búsqueda más profunda. JEPA puede servir como preentrenamiento del encoder, comparándolo con el mismo encoder supervisado; su pérdida auto-supervisada no es por sí misma una métrica de trading.

La utilidad operativa de un agente dependerá finalmente de conservar esa separación: percepción y memoria causal, predicciones cuantificadas, elección entre acciones permitidas y ejecución reproducible. Que encuentre razones plausibles para una operación no basta; que aprenda una fracción estable y rentable del comportamiento del oracle sí sería evidencia útil, y es lo que habría que medir.
