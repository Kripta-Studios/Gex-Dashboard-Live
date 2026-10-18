# Continuación de una política causal fija: propuesta acotada de tres fits

Redacción iniciada el 2026-10-18 18:00 UTC; comunicación del cierre metodológico a las18:04:39UTC. **MÉTODO FIJADO; MÓDULO PURO IMPLEMENTADO, FIT NO EJECUTADO**. El primer borrador y las fórmulas precedieron al módulo; el cierre formal/API final se solapó con su implementación: `causal_rollout.py` se creó a las18:04:33.5803206UTC, unos5segundos antes del cierre comunicado. Esta versión concuerda la API tras leer ese código y no afirma que todo su texto final precediera al módulo. Es posterior a los resultados anteriores, con revisión científica del diseño favorable. Sustituye únicamente el esbozo de siguiente método, no planes, fits o resultados existentes. La ruta elegida es tres regresores y rollout de una política fija; no se ejecutará conjuntamente una variante de cinco fits con V aproximado. Episodios quedan fuera para aislar el objetivo. Teacher sin h y learners con h constituyen el caso particular de una política común a ambos flags.

El usuario ha elegido libertad para decidir el momento de entrada y exige al menos un trade ejecutado por ticker y día. No se impone primera oportunidad obligatoria. Un día sin fill incumple el requisito; no se convierte una orden fallida en operación ni se garantiza conocer la última oportunidad futura. La penalización de entrenamiento especificada abajo ayuda a representar esa preferencia, pero no reemplaza el gate diario.

## Pregunta y separación causal

Se comparan dos regresores con idénticas features, filas, pesos, capacidad y periodo: retorno neto inmediato frente a ventaja de tomar una acción ahora y continuar con una **política causal fija**, comparada con esperar un minuto y continuar con esa misma política. El oracle de máximos retrospectivos no aporta etiquetas, muestreo o decisiones de continuación.

El retorno futuro de una política que decidió usando solo sus features disponibles puede emplearse como target histórico. No es lo mismo que elegir a posteriori la mejor operación futura. El estimando es una mejora de un paso respecto a una política de referencia, no Q óptima, FQI iterativo o MCTS. La política aprendida se ejecutará repetidamente con su propio scheduler; no hay garantía de mejora bajo aproximación, muestreo y drift.

## Datos disponibles e inspección realizada

Se inspeccionaron únicamente código, índice proyectado a ticker/fecha/status/número de acciones, schemas y footers, y cabeceras NPY; no valores de retornos ni nuevas métricas de test. Los archivos diarios de `features_v1` contienen 316 estados, índices 60–375 (10:30–15:45). Se verificaron cabeceras SPXW de 20230103, 20230705, 20240102, 20240701, 20250102 y 20260102.

| Bloque | Ticker-días disponibles | Acciones causales |
|---|---:|---:|
| 2023 H1 | 372 | 2.043.112 |
| 2023 H2 | 372 | 2.041.774 |
| 2024 H1 | 372 | 2.097.307 |
| 2024 H2 | 375 | 2.233.804 |
| 2025 H1 | 366 | 2.381.661 |
| 2025 H2 | 375 | 2.191.492 |
| 2026 H1 | 363 disponibles + 6 ausentes | 2.406.690 |

El training de los dos aprendices finales tiene 1.119 ticker-días y 6.372.885 acciones antes de muestrear. La selección tiene 741 ticker-días. El calendario 2026 exige 369, de los que faltan las fuentes Greek de SPY/QQQ de 20260401, 20260409 y 20260415. Ninguna nueva política puede acreditar una operación observada en esos seis días con este dataset.

Schemas relevantes existentes: `actions.parquet` aporta identidad y `state_i`; `labels.parquet` aporta `action_id`, `status`, `exit_i`, `net_base`, `net_adverse`, además de campos diagnósticos. La preparación necesita proyectar `status/exit_i/net_base` para transiciones, y `entry_ask` solo en H1 para la escala. `trigger_i`, precios de salida, hold, razón, labels y próxima fecha de decisión nunca son features actuales. En el ejemplo 20230103 SPXW hay 4.836 acciones, no 316: el estado se comparte entre ofertas.

Dimensión de estado GBT: 81 base + 20×45 tokens + 20×2 máscaras token/barra + 20×5×8 mapa + 20×5 máscaras = **1921**. Con las 33 features de acción actuales son **1954**, la dimensión del teacher π0. Añadir solo `has_filled_today` produce **1955 columnas** para control y residual finales. π0 no recibe h: su elección es idéntica para ambos flags. No añadir episodios, identidad numérica o características del futuro. `has_filled_today` vale cero al abrir cada sesión, pasa a uno cuando se observa un fill y no cambia con NO_FILL. Los packs actuales no se reescriben: el flag pertenece al estado del agente.

## Calendario y exactamente tres fits

1. **Teacher causal π0**: un LightGBM de retorno `net_base`, ajustado exclusivamente en 2023 H1. Su score se convierte a USD con escala de ese mismo periodo. En cada estado flat elige la acción de mayor score estrictamente mayor que cero, empate por action_id menor, o WAIT. Umbral fijo cero; no seleccionar π0 en 2025 ni cambiarlo por bloque. Se congela antes de producir cualquier target de continuación de H2/2024.
2. **Control net**: un LightGBM de `net_base` sobre la muestra fijada de 2023 H2 + 2024. WAIT tiene valor estructural cero. No reutilizar el viejo `gbt_net` como control principal: sus filas y periodo de fit son distintos. Su resultado anterior puede figurar únicamente como contexto histórico.
3. **Residual causal**: otro LightGBM sobre exactamente las mismas filas, orden y pesos del control, con target Aπ definido abajo. WAIT tiene ventaja estructural cero. Este es el único cambio entre los dos aprendices finales.

Los tres comparten seed 20261018 y configuración LightGBM: L2/regression, n_estimators=200, num_leaves=31, max_depth=6, min_child_samples=100, learning_rate=0,04, reg_lambda=10, max_bin=63, deterministic=True, force_col_wise=True, n_jobs=4. Son **600 árboles en tres fits**, sin early stopping, refit, ensemble, sweep de seeds ni ajuste de penalización. Si fallan, se conserva el intento; una recuperación técnica no elige otro modelo.

No hay fit sobre 2025. Se selecciona allí una política y se congelan pesos/umbrales antes de cualquier nueva evaluación de 2026. Todo 2026 sigue siendo desarrollo previamente visto. Las salidas, latencia, spread, comisiones, slippage, falta de fills y cierre EOD siguen exactamente el motor auditado.

## Muestreo sin oracle y escalas exclusivamente H1

La selección de filas usa únicamente `(seed,ticker,date,state_i,action_id)`, antes de abrir labels. Dividir los 316 estados en cuatro franjas fijas de 79 minutos: [60,138], [139,217], [218,296], [297,375]. Dentro de cada ticker-día/franja, conservar las min(32,M_db) acciones con menor SHA256 de la identidad canónica; desempate lexicográfico por identidad completa. No transferir presupuesto de una franja vacía o pequeña. Máximo **128 acciones únicas por ticker-día**.

La población objetivo da igual peso a cada ticker-día y, dentro del día, a cada acción ofrecida. Si un día tiene M_d acciones, una franja M_db y se seleccionan k_db, cada fila seleccionada tiene peso no normalizado `M_db / (M_d × k_db)`. Es la corrección IPW por probabilidad `k_db/M_db` dentro de la franja. La suma por día es uno. No confundir este objetivo con uno uniforme por estado: un estado con muchas ofertas contiene más acciones y recibe más masa dentro del día; se declara expresamente.

En la muestra final H2/2024, duplicar cada acción seleccionada con h=0 y h=1 y dividir su peso por dos. El teacher H1 usa acciones únicas, sin duplicación ni input h. Los dos flags finales son estados de agente contrafactuales: no afirman que h=1 fuese alcanzable a las 10:30 en la sesión real. Esta duplicación estima ambas ramas de la función; la ejecución real siempre arranca h=0 y solo cambia por fill. No se usa trayectoria oracle para escoger h. Normalizar finalmente los pesos a media uno dentro de cada fit; control y residual comparten vector exacto.

Para cada ticker, `risk_scale_H1` es la mediana ponderada de `100×entry_ask` de las acciones únicas seleccionadas en H1 con status FILLED y premium positivo, usando los pesos anteriores; no duplicar h al calcularla. Ausencia de una escala finita positiva falla técnicamente. La constante se congela con π0 y se reutiliza en todos los bloques, targets, scores y política. Ninguna mediana, desviación, calibración o normalizador usa H2/2024/2025 para generar targets de H2. GBT no requiere normalizar sus inputs; conserva la transformación causal existente float32.

Teacher y control ajustan `net_base/risk_scale_H1`; residual ajusta `Aπ/risk_scale_H1`. Sus scores vuelven a USD antes del scheduler. NO_FILL y pérdidas siguen en la muestra con sus pesos; no filtrar por fill, retorno, alcance futuro del target o teacher seleccionado. El filtro de FILLED solo define la constante de escala H1, no las filas de aprendizaje.

## Rollout completo de π0 y targets

Sea s un minuto de decisión flat, h el flag de fill previo y τ la próxima decisión permitida tras una acción. Para cada ticker-día de H2/2024, **predecir todas las acciones una vez** con π0 congelada; guardar elección causal `π0(s)` común a ambos flags y sus hashes antes de consultar los labels usados por su rollout. No usar solo las acciones muestreadas para elegir la continuación. Cuando no hay oferta, π0 espera.

Fijar una única penalización de entrenamiento `λ_ticker = risk_scale_H1[ticker]`, equivalente a una unidad del target escalado. Para s>375, definir `Gπ(s,h)=−λ×1[h=0]`. Es penalización por terminar sin fill; **no es comisión, PnL de mercado o pérdida económica observada**. No variar λ para cumplir el gate de 2026.

Calcular hacia atrás el retorno realizado de las decisiones **ya congeladas**, para todos los 316 estados y ambos h:

```
si π0(s) = WAIT:
    Gπ(s,h) = Gπ(s+1,h)
si π0(s) = a y status(a) = NO_FILL:
    Gπ(s,h) = Gπ(s+1,h)
si π0(s) = a y status(a) = FILLED:
    Gπ(s,h) = net_base(a) + Gπ(exit_i(a)+1,1)
```

No hay `max` sobre retornos realizados. El cálculo retrospectivo eficiente evalúa una política fija; no la sustituye por el oracle. Un mismo precio futuro puede contribuir a muchos targets de training correlacionados; eso no son muestras independientes de mercado. No se generan Gπ de H1 con la política ajustada sobre H1 para reintroducirlos como targets propios.

Para cada acción de la muestra H2/2024 y cada h:

```
si FILLED: Aπ(s,a,h) = net_base(a) + Gπ(exit_i(a)+1,1) − Gπ(s+1,h)
si NO_FILL: Aπ(s,a,h) = 0 exactamente
WAIT: Aπ(s,WAIT,h) = 0 exactamente
```

Esta expresión compara un compromiso de entrada ahora con esperar un minuto y luego seguir π0. En NO_FILL ambas ramas llegan al mismo estado/h sin recompensa; no existe reemplazo inmediato por otra acción. La siguiente decisión es s+1, según el motor. Una operación FILLED cambia h a uno; se bloquea hasta `exit_i+1`. Si τ>375, la continuación ya es terminal aunque existan precios hasta 16:00. Horizonte de sesión finito y **descuento 1**; no se introduce un holding fijo.

El predictor residual solo recibe `(x_s,a,h)` y aprende la expectativa de ese target. En inferencia no consulta Gπ, labels, τ, fill futuro, precio futuro ni `x_(s+1)`. WAIT es una acción estructural explícita de score cero y no requiere filas de regresión artificiales. El flag h y el índice del reloj son observables; la penalización terminal futura no es input.

π0 puede esperar toda la sesión: entonces su Gπ con h=0 incluye −λ. El residual puede valorar una operación negativa menos que λ como mejora de cumplimiento respecto a esa espera. Eso **no la vuelve rentable**. El gate diario y los resultados económicos sin penalización deben reportarse por separado. Una penalización finita tampoco garantiza que el aprendiz opere diariamente.

## Selección, libertad de timing y evaluación

Dos brazos finales × umbrales estrictos 0/5/10 USD = **seis candidatos**. Cada uno recorre su propio scheduler y su propio h, sin copiar la trayectoria π0. El score del control es retorno estimado; el del residual es Aπ estimada; en ambos WAIT=0. El mismo umbral USD no vuelve idénticos sus estimandos; se reporta esa diferencia. No cambiar disponibilidad, targets/stops o costes entre brazos.

Un candidato es admisible para selección solo si produce al menos un **FILLED** por cada uno de los 741 ticker-días esperados de 2025. Ordenar los admisibles por suma del neto económico base ejecutado dividido por escala H1 del ticker; empate favorece control y después menor umbral. Ninguna penalización λ entra en ese score. CASH se conserva como referencia económica cero, pero incumple el requisito diario y no es candidato admisible.

Si ninguno cumple el requisito diario en 2025, el resultado es `FAILED_DAILY_REQUIREMENT_VALIDATION`, sin ganador alternativo por menor número de fallos. No escoger una política de 2026. Congelar expresamente `selected_policy=null` y los seis IDs antes de diagnósticos2026, claramente separados de una selección inexistente. Si existe ganador, congelarlo antes de nueva evaluación2026.

En 2026 reportar simultáneamente:

- Gate de calendario completo: un fill por cada ticker-día esperado; las seis ausencias de fuente impiden acreditarlo con estos datos. No eliminarlas del denominador ni inventar operaciones.
- Gate de cobertura observable: un fill por cada uno de los 363 ticker-días con fuentes. Es un diagnóstico parcial, **no cumplimiento del requisito universal**.
- Economía real de cada candidato y del elegido: neto base/adverso, PF, WR, drawdown realizado, intentos/no-fills, días cero, meses y tickers, TARGET/STOP/EOD y duración. Nunca sumar −λ a ese PnL.

Mantener también el gate económico original por los tres tickers (neto base y adverso positivo, PF base≥1,2, mínimo60 trades, al menos3/6 meses positivos), sin rescatar un ticker o cambiar thresholds por test. El mínimo diario es un requisito adicional más fuerte sobre frecuencia. La historia 2026 vista no sirve para promoción aunque mejore alguno de estos indicadores.

## Presupuesto, checkpoints y condiciones técnicas

Límites deterministas: π0 tiene como máximo372×128 = **47.616 filas** con1954float32; cada learner final como máximo1119×128×2 = **286.464 filas**, con1955float32. Son aproximadamente0,35GiB y2,09GiB de matrices, respectivamente; los dos learners finales comparten la misma matriz y cambian solo el target. Algunas franjas pueden contener menos de32acciones; no completar cupos con otra franja. Gπ ocupa1119×317×2float64, unos5,4MiB incluyendo terminal. El scoringπ0 cubre6.372.885acciones una vez; se hace por día/batches, sin materializar su matriz completa.

Un único proceso de fit, cuatro hilos LightGBM, sin GPU ni fits paralelos. La futura implementación debe usar memmap y batch≤256 para ensamblar/scorar, cache de como máximo dos días y registrar private bytes además de RSS. Umbral de arranque propuesto: al menos12GiB RAM disponible y16GiB de commit libre; si faltan recursos se espera sin cambiar modelos ni tocar otros procesos. Estos son límites operativos, no hiperparámetros seleccionables.

Checkpoints separados e inmutables:

1. Spec final revisada, código/fixtures, hashes del motor/features/labels auditados, universo/calendario y manifiesto de muestreo causal; no depender de archivos de métricas vistos.
2. Muestra/escala H1, teacherπ0 y configuración congelados; fecha máxima H1 vinculada. Prohibido regenerar el teacher tras observar rollouts.
3. Por día, scores/elecciones π0 sellados antes del sidecar de Gπ; hashes de política y labels, dos flags, estado de completitud. Reanudar solo días completos verificados, sin mezclar versiones.
4. Muestra final y matriz común, targets net/Aπ, pesos y hashes; pruebas de NO_FILL=0, WAIT=0, terminal h y scheduler. Los targets pueden contener futuro de training; la whitelist de inputs no.
5. Exactamente dos modelos finales y sus hashes; no elegir checkpoints según validación.
6. Seis resultados2025, gate diario y ganador o fallo terminal; freeze antes de nuevos resultados2026.
7. Evaluación y auditor independiente; preservar fallos, ausencias y diario completo.

El estado actual es **METHOD_FIXED_PURE_MODULE_IMPLEMENTED_NO_FIT**: root implementó `causal_rollout.py` y siete fixtures sintéticos, reportados PASS con Ruff. La lectura independiente de su código confirma las recurrencias y separación choices/outcomes; la auditoría pura adicional continúa por otra vía. No hay builder de mercado, launcher o fit de esta familia ejecutado. Disponer de datos o recursos no activa un fit; antes deben verificarse implementación y auditoría correspondientes, sin una confirmación nueva del usuario.

## API pura congelada para implementación

`ActionRows(action_id,state_i)` y `OutcomeRows(action_id,status,exit_i,net_base)` contienen vectores alineados. `freeze_choices(actions,scores,threshold=0,first=60,last=375)` recibe exclusivamente keys y scores finitos shape(n_acciones,2), no outcomes, y devuelve choices int64 shape(316,2), readonly: −1WAIT o una acción de ese estado. El helper es genérico y admite scores distintos porh; este plan duplica la predicción única del teacher1954 en ambas columnas y exige que sus choices coincidan. Scores y choices se producen y sellan antes de consultar labels.

`fixed_policy_values(actions,outcomes,choices,penalty,first=60,last=375)` devuelve G float64 shape(317,2), **índices relativos**: `G[s−60,h]` para estados60..375; última fila `G[316]=[−penalty,0]` representa terminal376. Todos los valores son finitos; no existen filas artificiales previas a60. FILLED usa `min(exit_i+1−60,316)`,h1; WAIT/NO_FILL avanzan una fila conservando h. El helper permite penalty0 para fixtures; el runner de esta propuesta exige la escalaH1 finita positiva. Valida IDs, joins, status, recompensa finita, NO_FILL reward0 y salida FILLED posterior al estado. Los límites físicos del motor (`exit_i≥state_i+2`, `exit_i≤385`) deben verificarse en el adaptador/índice auditado: el helper genérico no impone ese techo y deliberadamente permite clamping después del horizonte de decisiones.

`residual_targets(actions,outcomes,values,first=60,last=375)` devuelve float64 shape(n_acciones,2) en el orden de ActionRows, columnas A_h0/A_h1. NO_FILL devuelve ceros exactos y no modifica `outcomes.net_base`. Los helpers no cargan archivos, entrenan, deciden actions mediante outcomes o realizan selección económica. Duplicados, joins incompletos y choices de otro estado fallan; no se reparan silenciosamente.

Fixtures obligatorios antes de datos: rollout directo desde cada estado frente al cálculo hacia atrás; WAIT y NO_FILL; fill con pérdida o neto cero cambia h a1; salida posterior al último estado usa terminal376; política WAIT todo el día; discrepancia de IDs/state; inputs causales invariantes ante perturbación de labels futuros; muestreo/IPW por franja; gate diario y freeze null. Como π0 es independiente de h, `G(s,1)−G(s,0)` debe ser λ si su rollout desde s no logra fill y cero si logra alguno. Para acción FILLED, `A_h0−A_h1` es λ solo cuando WAIT+π0 no conseguiría fill; para NO_FILL ambos son cero. Estas identidades verifican la penalización, no rentabilidad.

## Por qué esta ruta y qué se deja fuera

La ruta de cinco fits también puede ser causal: π0 H1; V_A regresado sobre Gπ de H2 para generar targets2024H1; V_B sobre H2+2024H1 para2024H2; control y Q finales2024. V tendría1922columnas con h y Q1956si WAIT se aprendiera como fila mediante `is_wait`. Cada target tendría productores estrictamente anteriores. Sin embargo, descarta H2 como datos del learner final y añade error de aproximación de V y de la diferencia de continuaciones. Por eso se elige aquí el residual de rollout directo: mismas etiquetas de política fija, menos fits y menos piezas.

Cambiar π0 por cada bloque temporal introduciría una mezcla de políticas de referencia; la variación de targets no sería únicamente drift de mercado. Esta propuesta mantiene π0 fija en H2/2024. Aun así, la relación entre features y retorno cambia entre años, y los targets de diferentes estados del día están correlacionados. La congelación elimina auto-contaminación de la política de referencia con las etiquetas de esos días; no elimina no-estacionariedad, error supervisado o sobreajuste del learner final. La evaluación temporal2025 es necesaria y no se usa para reentrenarπ0.

Double-Q puede reducir sesgo del máximo de Q estimadas al separar selector/evaluador, pero aquí no se maximiza una Q bootstrap dentro del target: se ejecutaπ0 ya fija y se usa su retorno realizado. Añadir Double-Q ahora sumaría fits y otro cambio metodológico. FQE iterativo con políticas cambiantes o fittedQ de varias iteraciones requeriría otro diseño de targets cross-fitted, no llamar OOF a predicciones de un modelo que vio la misma fila. Ninguna de esas alternativas se ejecuta como rescate de esta variante.

Los seis días sin fuente, las cotizaciones proxy, el muestreo de spot, ausencia de tape/impacto de mercado y los datos ya vistos siguen limitando la conclusión. Un método de continuación mejor alineado no garantiza un trade diario, expectativa positiva, recepción real o rentabilidad prospectiva.
