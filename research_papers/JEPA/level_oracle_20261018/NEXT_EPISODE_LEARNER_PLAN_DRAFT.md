# Borrador posterior a resultados: memoria de zona y continuación causal

Estado: **PROPUESTA; SIN IMPLEMENTACIÓN NI FIT NUEVO**. Redactado el 2026-10-18 desde las 17:50 UTC después de recibir los resultados de los aprendices actuales: la política seleccionada `gbt_advantage__10` no operó en test; el retorno directo mostró R² negativo y sobreestimación; el TCN emitió casi todos sus scores negativos. Estas observaciones fueron comunicadas por el coordinador; para este documento se comprobaron estructuras de artefactos y dimensión del modelo existente, sin calcular predicciones ni abrir labels o métricas adicionales. No es una predeclaración anterior a esos resultados y 2026 continúa siendo desarrollo ya visto.

Hay dos preguntas distintas. La primera es si una memoria explícita de contactos mejora la estimación de retorno de las mismas acciones. La segunda, más fundamental para coordinar entradas y esperas, es si se está aprendiendo el valor de una continuación que realmente puede ejecutar un agente causal. Añadir memoria no corrige por sí mismo un objetivo de continuación clarividente. Se propone primero una comparación pequeña y atribuible si se decide ejecutarla; la alternativa causal Q queda como otro experimento, sin mezclar cambios.

## Comparación limitada de representación

Control: **el `gbt_net` ya entrenado**, con pesos, muestra, escalas y configuración sellados. Variante: un único `gbt_net_episode` nuevo, que añade el bloque definido por `EPISODE_FEATURE_SPEC.md`. No reentrenar el control para escoger otra realización; reproducir sus scores con el artefacto existente. Una discrepancia de hashes o de reproducción es un fallo técnico, no una ocasión para cambiar el baseline.

El ensamblador actual `train_models.flatten_gbt` concatena exactamente:

| Bloque | Columnas |
|---|---:|
| Estado base | 81 |
| 20 tokens × 45 canales | 900 |
| 20 máscaras de token × 2 (token y barra existente) | 40 |
| 20 tiempos × 5 mapas × 8 bins espaciales | 800 |
| 20 tiempos × 5 máscaras de mapa | 100 |
| Acción causal | 33 |
| **Control real** | **1954** |
| 35 valores de episodio + 35 máscaras | 70 |
| **Variante propuesta** | **2024** |

Estas dimensiones incluyen la transformación de `FeatureStore` (`train_models.py:484`): apila `token_mask` y `bar_mask` en un último eje de tamaño 2 antes de `flatten_gbt`. Se verificaron el NPZ real SPXW/20230103, `normalizers.json` (gbt_columns=1954), la matriz existente (270377×1954) y la dimensión del modelo LightGBM. No añadir ni quitar bloques originales. Las 1954 primeras columnas deben ser idénticas al control en cada fila.

El bloque de episodio se une por `(ticker, date, state_i)` y se repite para todas las acciones ofrecidas en ese estado. Su artefacto outcome-free conserva valores float64 y máscaras booleanas; la matriz GBT sigue siendo float32, con conversión explícita y comprobación de finitud. Los 35 valores se añaden en el orden de `FEATURE_NAMES`, después sus 35 máscaras 0/1. Cero de almacenamiento con máscara falsa significa ausente, no observación cero. Los IDs, ordinals y traza diagnóstica quedan fuera. No seleccionar solamente estados con episodio abierto: el cierre del episodio no modifica la elegibilidad o las acciones.

Condiciones comunes que no cambian:

- Fit 2023–2024. Reutilizar **exactamente** `training_sample.parquet` con sus filas, orden, targets `net_base`, pesos de inclusión y `sample_i`; no remuestrear ni recalcular estratos por nuevos resultados. El muestreo previo distingue trayectoria oracle/resto y usa pesos para aproximar la población de acciones; este antecedente debe mantenerse visible.
- Reutilizar las escalas de riesgo por ticker aprendidas únicamente en training. Target `net_base / risk_scale[ticker]`; volver a USD antes de seleccionar. No añadir calibración, clipping, guardas de precio ni corrección del sesgo en esta variante.
- LightGBM L2, 200 árboles, 31 hojas, profundidad 6, mínimo 100 filas por hoja, learning_rate 0,04, reg_lambda 10, max_bin 63, seed 20261018, deterministic=True, force_col_wise=True, n_jobs=4. Sin early stopping, cambio de capacidad, sweep de seeds o ajuste posterior de lags/bandas.
- Mismo universo completo, seis ausencias preservadas, estados, contratos, objetivos y stops congelados, fills, costes base/adversos y scheduler. Se evalúa una sola posición por ticker; tras fill no se vuelve a decidir hasta `exit_i+1`, tras no-fill hasta `state_i+1`; no sustitución por otra acción.
- Misma inferencia por máximo score USD entre acciones disponibles, empate por action_id, umbrales estrictos 0/5/10 USD y WAIT de score cero. Los IDs solo desempatan, no son features. No se filtran ticker, mes, dirección o tipo de salida.

Solo la variante necesita un fit nuevo. El resultado de la anterior competición entre tres familias no es el control adecuado de esta intervención: comparar episodios contra el `gbt_advantage` seleccionado cambiaría simultáneamente representación y objetivo.

## Selección y comparación que seguirían siendo válidas

La selección mecánica utiliza exclusivamente 2025. Fijar siete políticas: CASH, los tres umbrales del control `gbt_net` y los tres de `gbt_net_episode`. Score idéntico al actual: suma por ticker del neto base ejecutado de 2025 dividido por su escala fija de training. CASH tiene cero y gana empates; después desempata control antes que variante y umbral menor. No añadir mínimos o penalizaciones después de ver su efecto. Congelar la tabla 2025, los siete IDs y la selección única antes de cualquier evaluación nueva de 2026.

Para atribución se conservarán también, sin refit, las comparaciones por **el mismo umbral** control/variante y la mejor política de cada brazo frente a CASH seleccionada solo con 2025. La ganadora conjunta es la única candidata seleccionada; ninguna política diagnóstica del test puede sustituirla. Si gana CASH, el resultado no constituye un modelo rentable.

Evaluar enero–junio de 2026 como desarrollo visto, con todos los días y tickers. Reportar neto base/adverso, número de intentos/fills/no-fills, PF con su estado indefinido explícito, meses positivos, drawdown realizado y distribución de TARGET/STOP/EOD y duración. Mostrar diferencias emparejadas por ticker-día y por mes, incluidos ceros: más trades por sí solos no prueban mejora. Una diferencia de PnL seleccionada no debe confundirse con un efecto estable de representación.

Mantener sin relajación el gate económico del plan original: en **cada uno de los tres tickers**, neto base y adverso positivos, PF base ≥1,2, al menos 60 trades y al menos 3/6 meses positivos. Reportar dos conclusiones separadas: si la variante supera al control seleccionado en neto normalizado total bajo ambos costes; y si la política conjunta pasa el gate completo. Ninguna de ellas convierte 2026 en holdout intacto, acredita recepción de fuentes o autoriza promoción. El número de nuevas variantes y el conocimiento previo del periodo deben acompañar el resultado.

Diagnósticos secundarios de selección de acciones: sesgo, error/R² y calibración de retorno sobre todas las acciones de 2025/2026, junto con acciones efectivamente elegidas por el scheduler. La población exhaustiva de acciones sobrepondera estados con muchas ofertas respecto a una política; por eso esos errores no son el criterio económico principal. No ajustar thresholds o calibradores a partir de diagnósticos de 2026.

## Qué información añade realmente el episodio

| Componente | Relación con la representación existente |
|---|---|
| Edad, ocupación, contactos, reentradas y cruces | Codifican orden de observaciones minuto a minuto que una OHLC agregada no recupera. Los fixtures con iguales OHLC y distintos contactos muestran la diferencia de representación, no su rentabilidad. |
| Centro/banda/tipos de apertura persistentes | Conservan qué zona inició la interacción aunque migre la zona elegible. El baseline conserva niveles actuales e históricos agregados, pero no esta identidad de episodio explícita. |
| Penetración y recuperación por lado | Resumen extremos desde apertura y retorno a partir de ellos. Se solapan con mechas/rangos, pero el origen temporal y espacial es el episodio, no una vela fija. |
| Distancia y cambio 1/5m | Hay solapamiento importante con spot/IB y cambios existentes. Añaden escala del ancla y máscaras que exigen continuidad dentro del episodio; no son nuevos precios ni señal independiente garantizada. |
| Tipos y geometría de zona elegible actual | El baseline incluye procedencia de target/stop y mapas/top-3, pero no la zona de entrada explícita. Parte puede inferirse, especialmente con Fibonacci estáticos. |
| Máscaras | Conservan ausencia, discontinuidades y disponibilidad causal. Algunas serán constantes en segmentos; no deben eliminarse adaptativamente mirando test. |

El episodio es una transformación de datos ya disponibles, no una fuente nueva. Puede reducir el esfuerzo del árbol para reconstruir una interacción; también puede duplicar información, fragmentar la muestra o amplificar ruido. La decisión de limitarse a 35 canales mantiene atribuible el cambio, pero no establece que sean óptimos. No se añade masa por strike, nuevos mapas, embeddings, etiquetas de rechazo o filtros visuales. Si esta prueba falla, no se rescata un ticker o un mes ni se cambian los parámetros del episodio dentro del mismo intento.

## Prioridad conceptual posterior: aprender una continuación ejecutable

El oracle actual calcula, para la trayectoria futura realmente observada, `V_oracle(s)=max(WAIT, retorno(a)+V_oracle(salida(a)+1))`. La etiqueta de ventaja resta `V_oracle(s+1)`. Esa espera dispone de las mejores oportunidades futuras elegidas **después de conocerlas**. Una operación con retorno positivo y razonablemente predecible puede recibir ventaja negativa porque ocupa minutos durante los que el oracle captura una oportunidad mayor que el agente no puede anticipar.

No hay obligación matemática de que `E[ventaja_oracle | información causal]` coincida con la ventaja de la política causal. El máximo clarividente suele sobrevalorar continuación respecto a elegir antes de conocer el futuro; en una **diferencia** entre dos continuaciones el sesgo no tiene por qué tener siempre el mismo signo. La buena predicción de un target privilegiado puede coexistir con una política que espera siempre. El resultado observado es compatible con ese desajuste; por sí solo no demuestra que sea su única causa. El GBT directo tampoco resuelve coordinación: estima retorno de la operación y trata WAIT como cero, ignorando el coste de oportunidad esperado de permanecer ocupado.

Una alternativa separada es fitted Q/semi-Markov sobre estados **flat** y las mismas acciones completas de entrada/contrato/target/stop. WAIT es una acción explícita. La posición mantiene las salidas congeladas del motor; no se introducen decisiones intratrade.

Para una transición de training `(x_s, a, r, x_tau)`:

- WAIT: recompensa cero, siguiente estado `s+1`.
- Operación con fill: recompensa `net_base(a)`, siguiente decisión `exit_i+1`.
- No-fill: recompensa cero, siguiente decisión `s+1`, igual que el scheduler actual; no se reemplaza la acción fallida.
- Después del último estado de entrada permitido: continuación terminal cero. El objetivo de horizonte finito es USD netos de la sesión; descuento 1 evita inventar una preferencia por duración distinta de la ocupación efectiva.

Objetivo conceptual: `y_k = r + V_{k-1, causal, OOF}(x_tau)`. La continuación se calcula con un estimador congelado de Q sobre **features disponibles en x_tau**, no con el DP de máximos realizados ni con la mejor operación posterior observada. En inferencia se compara `Q(x_s,a)` con `Q(x_s,WAIT)`; no se necesita conocer duración, fill o siguiente estado de la operación aún no ejecutada. Esas variables solo forman transiciones históricas de training. Si se mantuvieran umbrales, se aplicarían a la diferencia Q(acción)−Q(WAIT), no al Q absoluto.

Esto exige una acción WAIT con máscara explícita de contrato/target/stop ausentes y estados flat incluso cuando no hay ofertas. No basta reutilizar únicamente las filas de operaciones muestreadas actuales. Un cambio de distribución de entrenamiento o de objetivo es precisamente la razón para separarlo del experimento de episodios.

### Evitar reutilización optimista de targets bootstrap

La siguiente propuesta necesitaría fijar antes de ejecutar un calendario de bloques forward dentro de 2023–2024. Una partición inicial razonable para diseño es primer semestre 2023 como warm-up y bloques posteriores semestrales; las decisiones exactas sobre presupuesto, iteraciones y longitud de warm-up quedarían congeladas en su propio plan, sin barrer 2026.

Para cada bloque B, el modelo que produce la continuación de sus transiciones debe haberse ajustado únicamente con sesiones anteriores a B, cuyos resultados ya terminaron antes de B. Todas las acciones de un mismo ticker-día y sus transiciones permanecen juntas; no hacer split aleatorio por acción. Durante la producción de targets del bloque, su política de continuación queda congelada. La cadena de modelos bootstrap también debe respetar ese corte: no vale entrenar un Q global con todo 2023–2024 y después llamar OOF a sus predicciones sobre esos mismos meses. El warm-up sin productor pasado necesita una inicialización explícita, por ejemplo continuación cero; no una predicción entrenada sobre su propio futuro.

Tras producir targets causales OOF se puede ajustar el predictor final con training, preservando hashes de cada productor, sus fechas de fit y transiciones. Usar un estimador para elegir la acción de continuación y otro independiente para valorarla —o un Q de política fija con evaluación separada— puede reducir optimismo del máximo sobre estimaciones ruidosas. Esa elección sería otra especificación previa; ni cross-fitting ni doble estimación garantizan eliminar sesgo de aproximación o drift.

Mantener 2025 separado para calibración/selección de política y 2026 como desarrollo. Si se incorpora un calibrador, su entrenamiento y la selección posterior deben separarse temporalmente dentro de 2025; no calibrar y escoger con las mismas etiquetas sin reconocer esa dependencia. El modelo de continuación que genera targets de training nunca accede a 2025/2026. La coordinación se evalúa recorriendo los estados que visita el propio scheduler, no reproduciendo la trayectoria del oracle.

Los históricos ofrecen resultados simulados de todas las acciones disponibles bajo ausencia de impacto de mercado; eso facilita construir transiciones, pero no acredita fills reales ni elimina cobertura insuficiente, estado parcialmente observado, dependencia entre acciones del mismo día o error del reloj proxy. Aprender una Q causal es una hipótesis mejor alineada con coordinación ejecutable, **no una promesa de rentabilidad**. Antes de activarla harán falta especificación acotada, fixtures terminal/WAIT/no-fill, trazabilidad temporal del bootstrap y comparación con retorno directo; aquí no se implementa ni entrena.

## Estado de ejecución

La construcción outcome-free de `episode_features_v1` se gestiona por separado y no constituye un fit. Este documento solo fija una comparación propuesta y describe la alternativa de continuación. No modifica `LEARNER_PLAN.md`, `train_models.py`, `features.py`, motor, caché, episodios congelados o los resultados actuales.
