# Diagnóstico del entrenamiento TCN congelado

**El TCN aprendió algo, pero su regresión apenas mejora una constante incluso sobre su propia muestra de entrenamiento. Cuatro épocas con pérdida casi plana no demuestran que sea imposible aprender esta tarea, ni que entrenar más vaya a resolverla.** La evidencia deja abiertas limitaciones de optimización, representación y objetivo. No permite atribuir el fracaso a una sola causa.

Diagnóstico del 18 de octubre de 2026, solo 2023–2024. No se ajustó ningún modelo, cambió selección, abrió nueva predicción de 2025/2026 o utilizó GPU. Se evaluó una vez el modelo final guardado sobre las 270.377 acciones de su muestra TRAIN, con CPU/four threads y caché de un día. Este es un diagnóstico interno de ajuste, no una prueba de generalización o rentabilidad.

## Objetivo y referencias comparables

El código congelado usa `y = net_base / risk_scales_usd[ticker]`, con escalas SPXW=680, SPY=81 y QQQ=88 USD. Son medianas ponderadas del débito de entrada en TRAIN, no volatilidades del target ni capital de cada operación. La pérdida por lote es:

`sum(weight * ((prediction-y)^2 + 0.1*BCE(logit,state_optimal_action))) / 1024`.

La regresión estima el neto de una acción ofrecida y su salida definida; no aprende el máximo futuro entre todas las acciones. La auxiliar enseña una elección privilegiada del DP. No hay regularizador de ranking entre acciones del mismo estado, pérdida explícita de duración o objetivo económico directamente agregado por sesión. El scheduler usa la cabeza económica; la probabilidad auxiliar no decide entradas.

Referencias constantes calculadas analíticamente sobre los mismos targets y pesos: regresión igual a su media ponderada −0,0793209 y probabilidad BCE igual a la prevalencia ponderada 0,00953595. Las cifras siguientes usan exactamente las unidades de la suma registrada: suma de errores ponderados dividida por1024, no media por lote ni por época.

| Referencia/evaluación | Regresión | Auxiliar ×0,1 | Total |
|---|---:|---:|---:|
| Constante óptima pooled |156,63948|1,42207|158,06155|
| Constante óptima por ticker, suma |156,39424|1,42207|157,81631|
| TCN final, evaluación TRAIN fija |156,08274|1,16798|157,25072|

La cabeza económica mejora el SSE constante pooled un **0,3554%**. La auxiliar mejora su BCE constante un **17,8674%**. El total mejora un **0,5130%**. La auxiliar aporta solo el **0,743% de la pérdida final**; esta proporción escalar no equivale a su proporción de gradiente en parámetros compartidos.

Las pérdidas online guardadas fueron 159,25469 / 158,58916 / 160,37594 / 159,26891. Cada suma se midió mientras los pesos de la red iban cambiando, antes del update de cada lote. No son evaluaciones fijas del checkpoint correspondiente, y su fluctuación no es una curva de validación. La evaluación fija final157,25072 es menor que las cuatro sumas online. No se evaluaron retrospectivamente todos los checkpoints para elegir una época.

| TRAIN | Filas | R² ponderado contra constante propia | Media target | Media predicción | Desv. target | Desv. predicción |
|---|---:|---:|---:|---:|---:|---:|
| Pooled |270.377|0,003554|−0,07932|−0,07760|0,77022|0,02569|
| SPXW |95.632|0,002625|−0,03832|−0,05397|0,84584|0,02357|
| SPY |84.004|0,002006|−0,09665|−0,08820|0,70612|0,01586|
| QQQ |90.741|0,001122|−0,10617|−0,09253|0,74153|0,01533|

La salida económica tiene poca dispersión. Solo el0,2745% ponderado de acciones TRAIN obtiene score positivo. No es una red exactamente constante ni hay evidencia de que sus parámetros no se actualizaran. La media de probabilidad auxiliar es1,0463%, próxima a la prevalencia0,9536%; ninguna supera0,5. Con este desequilibrio, no superar0,5 no demuestra por sí solo un clasificador inútil.

## Muestreo, pesos y definición del teacher

El universo TRAIN tiene 8.415.997 acciones: 20.377 en la trayectoria efectivamente elegida por el oracle y 8.395.620 restantes. La muestra contiene todas las20.377 primeras y250.000 de las restantes. Cada fila de trayectoria pesa0,03212656 y cada otra fila1,07888943; la media global del peso es1. El peso de una fila de trayectoria es33,58 veces menor.

Por eso oversampling no convierte el objetivo en entrenamiento equilibrado de ganadoras/perdedoras: restaura aproximadamente el objetivo de población por acción. La trayectoria pasa de7,5365% de la muestra a0,2421% del peso. El target auxiliar `state_optimal_action` pasa de8,1960% de las filas a0,9536% del peso. Son etiquetas distintas:

- `teacher_selected` identifica las acciones de la trayectoria diaria ejecutada por el DP; se usa para muestrear.
- `state_optimal_action` identifica la acción que el DP elegiría estando libre en ese estado, aunque su trayectoria diaria no llegue libre a él; se usa en BCE.
- Una acción omitida de la trayectoria no es necesariamente negativa para BCE. Tampoco una ganancia aislada positiva implica ser óptima frente a WAIT y futuras oportunidades.

No se detectó confusión entre ambas columnas en el entrenamiento. La distinción está expresamente fijada en LEARNER_PLAN.md y en el motor. El objetivo auxiliar privilegia una etiqueta rara, pero su ponderación es una decisión del diseño congelado, no un error de implementación probado.

## Escala efectiva de actualizaciones y colas

La red tiene64.010 parámetros. Se usa AdamW, learning rate0,001, weight decay0,0001, clip de norma global1, sin dropout, batch normalization, early stopping o selección de época. Los checkpoints confirman1491/2982/4473/5964 pasos de optimizer. Hubo1.491 días por época, no solo unas centenas de pasos en total.

Todos los días caben en un solo lote: mínimo11, mediana181, máximo365 filas. La suma de pesos/1024 varía de0,00852 a0,36412, mediana0,17531. Dividir por1024 mantiene la suma objetivo declarada, pero hace que el gradiente previo al clipping tenga una escala dependiente del día respecto de una media ponderada del lote. Adam introduce adaptación y no puede traducirse esto en una simple multiplicación exacta del learning rate. Los días se barajan; no se mezclan varios días dentro de un batch.

No se guardaron normas de gradiente antes/después de clipping, frecuencia de clipping, normas de updates ni pérdidas separadas por cabeza durante el entrenamiento. **No es posible afirmar retrospectivamente que el clipping saturó o que faltaron gradientes.** La pérdida finita solo descarta la interrupción por NaN/Inf prevista en el código.

Hay una cola de netos considerable: target ponderado p1/p50/p99 ≈−1,280/−0,230/+3,008, p99,9≈5,710 y máximo18,714 escalas. El1% de filas con mayor residuo absoluto frente a la constante explica34,52% del SSE ponderado. La MSE pone peso fuerte en esos casos. TRAIN contiene270.357 FILLED y20 NO_FILL; el neto cero representa0,0080% ponderado, por lo que una masa enorme de no-fills no explica la salida casi constante.

## Normalización y máscaras: problema concreto a investigar

La normalización aplica media/std a todos los canales, incluidos flags binarios y fracciones casi siempre1. Solo sustituye std por1 cuando std<1e−6. Esto produjo extremos reales de TRAIN:

| Canal | Valor raw | Media/std TRAIN | z aproximado |
|---|---:|---|---:|
| base.change_15m_valid |0|0,99999589 /0,00202710|−493,31|
| base.change_5m_valid |0|0,99999202 /0,00282499|−353,98|
| action.iv_valid |0|0,99999577 /0,00205620|−486,33|
| base.current_call_quote_valid_fraction |0,49618|0,99998139 /0,00264945|−190,15|

También existen extremos continuos: action.spread_over_spot≈135,33σ, tokens.upper_wick_ib≈59,21σ. No hay clipping numérico de inputs. Los extremos mayores no proceden de una griega enorme: proceden de indicadores de validez casi constantes. Es una hipótesis concreta de mala condición de la optimización, aunque no hemos medido su contribución a gradientes históricos ni probado que causen el resultado.

Todos los valores numéricos suministrados en los cuatro bloques son finitos. El builder usa placeholders cero y máscaras explícitas; por tanto, las máscaras `isfinite` que añade el normalizador son constantes1 en esta muestra y no identifican los faltantes originales. Token/bar masks y map masks siguen presentes:97,01% y96,96% de sus celdas son no-cero, respectivamente, contadas sin ponderar y por acción. Las fracciones de mapas no son necesariamente booleanas.

El relleno cero entra en las medias/std. Tras estandarizarlo, ya no suele ser cero. Las máscaras se proporcionan como canales/contexto, pero no multiplican explícitamente los valores normalizados ni excluyen posiciones del average pooling. La red puede aprender a distinguirlos, aunque no tiene una garantía algebraica de ignorarlos. Esto no constituye leakage ni demuestra que se hayan perdido todas las máscaras. No se reconstruyeron fuentes raw para este diagnóstico.

## Hipótesis próximas, sin activarlas aquí

1. **Aislar primero la optimización:** mantener el target económico y representación, tratar flags/máscaras en[0,1] y normalizar solo continuos; registrar MSE/BCE fijas en TRAIN, una validación cronológica interna de2023–2024, normas de gradiente y frecuencia de clipping. Comprobar sobreajuste de un pequeño bloque TRAIN fijo como prueba de capacidad/gradientes. Esto permite decidir si más épocas aportan aprendizaje, sin usar2026 para escogerlas.
2. **Examinar robustez del objetivo:** una pérdida Huber puede reducir la dominancia de la cola, pero ya no tiene exactamente el mismo óptimo que la media bajo MSE. No vender una caída de Huber como mejora de retorno esperado; conservar evaluación de neto en USD y comparar cola/ranking por estados. Del mismo modo, retorno relativo al débito o a riesgo causal por acción cambia la ponderación económica; requiere explicitar ese cambio y conservar las cuentas originales.
3. **Una descomposición de eventos como alternativa científica:** aprender probabilidad de TARGET/STOP/EOD y neto condicionado/duración puede separar geometría y payoff de opciones. Tocar TARGET no garantiza beneficio en la opción, por lo que el clasificador de evento necesita evaluación económica posterior; no basta maximizar acierto del toque. Es una propuesta, no una nueva selección entrenada.

No se propone una búsqueda indiscriminada de arquitecturas. La inferencia actual es más estrecha: el aprendizaje de la cabeza económica fue débil incluso en TRAIN, la auxiliar aprendió algo y hay un problema específico de escala en flags que merece una prueba controlada. Ni la rentabilidad del oracle ni este diagnóstico hacen desaparecer el sesgo retrospectivo o convierten2026 en un holdout nuevo.

## Evidencia y alcance de reproducción

Código fuente congelado leído: `learners_v1/train_models.py`, SHA `a5192737abd1c0b3e4a6a6cd391117d97a014c06b6cd528201ba1f5df0ef6808`. Referencias en el repositorio: `train_models.py:302` muestreo, `:591` normalización/risk scales, `:658` arquitectura, `:709` normalizador, `:867` entrenamiento, `:945` pérdida/clipping; `level_engine.py:596` elección/trayectoria y `:628` etiquetas; `features.py:74` placeholders y `:209` máscaras.

Script del diagnóstico: `diagnose_tcn_optimization.py`, ejecutado SHA `88ec659a8f78f99787088c7390a6c4a9e58e912d46fdd948fb9086e359562c44`. Salida: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_optimization_diagnostic_v2`; summary SHA `214e1c4d1c1b70f7b765d28b3a86a9070dd0872469b106c8ba356a4efbec1f15`. Incluye hashes de inputs, checkpoints, features consumidas y predicciones TRAIN guardadas. `standardized_extremes.json` identifica canales y filas; train_x SHA `1967e31fdf8a7ff7562a71cad65b79040c542b2c7b40cb7de2a2a6b29bc64b38`.

La inferencia utiliza la implementación congelada del propio modelo; no es un refit ni un auditor independiente de arquitectura. Se verificaron hashes de checkpoints contra metadata, sample contra manifest, packs contra metadata y que ninguna fecha de sample alcance2025. Las fuentes del learner se rehashearon al terminar. Compile y Ruff del diagnóstico PASS. El intento técnico v1 falló al importar el dataclass antes de leer TRAIN; conserva script y failure.json, sin métricas. V2 corrigió únicamente el registro de módulo importado y completó exit0. Fuentes, pesos, modelos y decisiones originales permanecen intactos.
