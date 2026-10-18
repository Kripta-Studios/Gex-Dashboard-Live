# Modelos probados, resultados y trabajo incompleto

## Convenciones de lectura

Todos los importes económicos son USD netos de operaciones de un contrato. No se suman variantes como una cartera. «Validación2025» y «test2026H1» describen separación temporal respecto al ajuste, pero ambos periodos ya son desarrollo observado. Un PASS de auditoría significa reconstrucción dentro de su alcance, no rentabilidad. La exigencia posterior del usuario es al menos un fill por ticker-día, con libertad de elegir el momento; no se fuerza la primera entrada.

## 1. Benchmarks iniciales de zonas

Se entrenaron dos LightGBM por representación, CALL/PUT, comparando precio/contexto, zonas auténticas y zonas desplazadas mediante hash. Entradas cerca de delta.50, ask→bid y costes. Esos experimentos iniciales usaban salida fija30m; se conservan por transparencia, pero no satisfacen la especificación posterior de salida por niveles.

| Prueba posterior al ajuste | Precio/contexto | Zonas auténticas | Zonas desplazadas |
|---|---:|---:|---:|
| Octubre–diciembre2023 | -9963.40 | -13123.80 | -10533.40 |
| Enero–junio2026 | -18796.40 | -34135.80 | -36986.60 |

La prueba ampliada ajustó2023–24 y seleccionó en2025. Retrasar la entrada2o5minutos tampoco produjo beneficio agregado. Los intervalos bootstrap pareados de mejora incremental incluyeron cero. Las auditorías reprodujeron seis ajustes en cada prueba y sus predicciones, además de contabilidad/scheduler y subconjuntos de raw; no reconstruyeron todas las features desde raw ni acreditaron recepción live. Véanse los dos informes y reviews en `restart_20261018`.

## 2. Primeros aprendices del oracle de niveles

Muestra común de270377acciones TRAIN2023–24; matriz tabular1954columnas; normalización y escalas de prima sólo TRAIN: QQQ88,SPXW680,SPY81USD. Las etiquetas incluyen neto directo y ventaja frente a WAIT con continuación retrospectiva. Se preservaron acciones perdedoras y pesos IPW; no se entrenó exclusivamente con entradas ganadoras.

Dos GBT de200árboles,31hojas,profundidad6,min_child100,learning_rate.04,L2=10,max_bin63,seed20261018 y4hilos. Uno predice neto y otro ventaja DP. El modelo neuronal `LevelTCN` tiene dos ramas temporales5m/15m con32canales y bloques causales de dilatación1/2; rama espacial Conv2d10→8→16 para mapas; rama de acción64; MLP64→32 y dos cabezas de neto y teacher. Usa máscaras explícitas, no imágenes de pantalla. Cuatro épocas fijas con AdamW, objetivo combinado de regresión y clasificación del óptimo por estado, clipping de gradiente1. El teacher no se usa como feature.

Las nueve políticas corresponden a tres scorers×umbrales0/5/10USD. El selector original eligió `gbt_advantage__10`: sólo dos tradesSPXW en validación,+40.80USD, y **cero trades en2026**. No es una señal acreditada. El control net0 perdió77691.00USD en las741sesiones2025 y34449.40USD en2026. Un diagnóstico TCN>5 sumó+2490.60USD en2026 con19trades,14ticker-días y sin operar SPY; no era la política seleccionada, no cumple mínimo diario y no se rescató mirando test.

Resultado completo: [LEARNER_RESULT](../LEARNER_RESULT.md). Auditoría económica `238e6f09…5945bd`, dadas predicciones selladas; no refit neuronal independiente.

## 3. Representación de episodios

Se añadieron35variables y35máscaras de contactos, penetraciones, rechazos y recuperación, manteniendo exactas las1954columnas originales. Un fit GBT con2024columnas y las mismas270377filas. El control reutilizó modelo/scores sin refit. La hipótesis era expresar mejor el comportamiento aproximado observado visualmente, no exigir toques exactos.

En comparación fija net0, la variante perdió113564.80USD en2025 frente a77691.00del control; en2026 perdió36323.80 frente a34449.40. Ninguna política satisfizo la actividad diaria; selección nula. El fallo de rutas tras el primer fit se reparó mediante wrapper específico, preservando modelo y fallo, con cero refits. Auditoría `260d0850…190d4a` pasó y confirmó el resultado negativo. [Informe completo](../EPISODE_LEARNER_RESULT.md).

## 4. FLAGS64 y diagnóstico del aprendizaje neuronal

Se corrigió la escala de64canales de flags/cobertura a0–1, conservando muestra, arquitectura, objetivos, optimizador, presupuesto y seed. La cuarta época tuvo R²TRAIN0.001436/MSE0.592389, cerca del predictor constante. La variante>0 operó tres veces en un único díaSPY2025 y perdió22.80USD; en2026 no operó. Los otros umbrales tampoco proporcionaron política diaria. La auditoría económica pasó; [resultado](../TCN_FLAGS_V1_RESULT.md).

Se hicieron dos diagnósticos TRAIN, sin selección económica:

- Memorización de128ejemplos escogidos por hash: R²0.999411 tras500updates fijos. La red podía ajustar un conjunto pequeño; esto no prueba generalización.
- Dispersión de gradientes en512filas: mezclar días redujo aproximadamente63.4%la dispersión, manteniendo el promedio. Motivó cambiar el orden de minibatches, no las etiquetas ni el presupuesto.

### TCN con filas mezcladas: final completado al parar

Se conservan las270377filas, pesos y tamaños de batch, pero las filas se mezclan entre días con RNG separado. Misma arquitectura FLAGS64, AdamWlr.001/wd.0001, pérdida fija con denominador1024, clipping1, cuatro épocas×1491updates=5964. No se eligió mejor época. La cache de filas (~16.19GB) evita reconstruir entradas en cada update.

| Época | Updates | MSE TRAIN IPW | R² TRAIN IPW | Desviación predicción |
|---|---:|---:|---:|---:|
| 1 | 1491 | 0.574862376 | 0.030980694 | 0.116768402 |
| 2 | 1491 | 0.542010020 | 0.086358414 | 0.305362178 |
| 3 | 1491 | 0.494230806 | 0.166897658 | 0.375747375 |
| 4 | 1491 | 0.455734558 | 0.231789028 | 0.352417015 |

El entrenamiento terminóexit0 a21:34:57UTC. R²TRAIN final por ticker: QQQ0.202024,SPXW0.261526,SPY0.214469. Es una mejora clara del **ajuste TRAIN**, no una demostración de predictibilidad temporal ni rentabilidad. No se produjo ninguna predicción/evaluación temporal de esta variante. Checkpoints y comparaciónTRAIN se archivan. El evaluador calendario750+369 quedó en preparación al parar.

## 5. Coordinación mediante continuación de política causal

Para evitar enseñar sólo continuación clarividente, se ajustó un teacherπ0 de neto en2023H1 (372días,47430filas). En2023H2–2024 se generó su continuación realizada para un control directo y un alumno residual, con285286filas pareadas h0/h1 y1955columnas. `h` indica si ya hubo fill en el día. La muestra se elige por identidad/hash y bandas de tiempo, sin seguir la trayectoria oracle.

La etiqueta residual es retorno inmediato más continuación deπ0 tras salida menos continuación de esperar. El terminal h0 recibe una penalización fija basada sólo en primaTRAIN, para incentivar al menos un fill. La penalización **no entra en el PnL económico**. NO_FILLno cambia h. Una penalización finita no garantiza la restricción: ésta se comprueba aparte.

El selector2025 eligió `causal_residual__5`; la familia completa fue negativa. Resultado de la seleccionada:

| Alcance | Trades | Neto base | Neto adverso | PF | Días observados sin fill |
|---|---:|---:|---:|---:|---:|
| 2025,741completos | 3445 | -39673.00 | -46548.00 | 0.918464 | 0 |
| Nueve cortas2025, extensión sin reselección | 37 | -2606.20 | -2679.20 | — | 0 |
| Unión2025,750días | 3482 | -42279.20 | -49227.20 | 0.913590 | 0 |
| 2026H1,363disponibles | 1623 | -46085.80 | -49324.80 | 0.819035 | 0 |

Se cumple actividad en días observables pero se pierde dinero. Los6faltantes2026impiden acreditar cobertura universal. En2026: SPXW−33938.60,SPY−5196.60,QQQ−6950.60USD; cada ticker sólo1/6mesespositivo. Se detectó además h0<h1predicho en≈26.9%deacciones pese a la ordenación opuesta débil de las etiquetas; se informó sin corregir a posteriori. Auditorías completas dentro del alcance de scores sellados: `6dd69574…581cd3` y extensión `a3ae3bca…c5909`.

## 6. Representación compacta152

Mantiene muestra, target directo, IPW, configuraciónGBT y escalas. Resume contexto de mercado, geometría y griegas en152variables. El ajusteTRAIN dio R²0.196961804. Comparación fija de umbral0, sin elegir ganador, frente al net0original; calendario750/369:

| Periodo | Original net0 | Compacto152 | Días sin fill compacta |
|---|---:|---:|---:|
| 2025 | -79189.60 | -76834.40 | 178/750 |
| 2026H1 | -34449.40 | -43482.20 | 37/363 |

Auditoría `c16a381b…9d6c2` PASS; informe mensual108filas. La compacta mejora algo2025, empeora2026 y sobreestima trades seleccionados: predicción media2026+57.03USD frente a−30.15realizados. [Resultado detallado](../MARKET_CUE_COMPARISON_RESULT.md). No se cambió la siguiente variante424 por este resultado.

## 7. Griegas sobre contratos comunes:424variables

Se encontró que la validez demasiado estricta de la dinámica antigua de gamma hacía casi inobservable su canal de cambio: exigía IV válida en todos los contratos/minutos de la barra. No significa que los modelos carecieran de gamma estática o historia de mapas. La corrección usa contratos válidos comunes en extremos separados5/15minutos, con validez específica por griega, cobertura y composición explícitas.

272variables nuevas=4griegas×2lados×2lags×17estadísticos, concatenadas al prefijo152exacto. Se separan cambios de la griega, OI reportado y composición. En los pares comunes observados no hubo cambios de OI; no se denominó flujo dealer. Vega se expresa como raw/100; delta/theta conservan signo; gamma requiereIV. La coberturaTRAIN fue≈99.936% y se conservó≈99.3–99.7%de la masa gamma observable según diagnóstico/ponderación, no exposición desconocida.

Un fit con270377×424 terminóexit0, mismoGBT y mismos targets/pesos. MSETRAIN0.472848644,R²0.202940593 frente a0.196961804compacto: reducciónMSE≈0.745%. Modelo `10b1c409…e82c`; readbackTRAINexacto y rehashfinal. Evaluador revisado para750+369 y control152bitexact1113sesiones, pero **no llegó a ejecutarse**. No hay PnLni evidencia de generalización424.

## 8. Walk-forward mensual, incompleto

Tres procedimientos predefinidos: estático2023–24, expanding mensual y rolling12meses. Muestra causal hasta128acciones/día con cuatro bandas e IPW; no es idéntica a la muestra original270377. La preparación produjo332472acciones muestreadas de15445024ofertas sobre2619días disponibles. Folds ajustan sólo pasado y guardan modelo/scores antes de labels del mes. Se planeaban24fits2025, selección/freeze y posteriormente evaluación2026; se detuvo antes.

Sólo enero2025 tiene cierre del productor. Las cifras siguientes son **parciales y no tienen auditoría mensual independiente completa**:

| Enero2025 | Trades | Neto base | Neto adverso | PF |
|---|---:|---:|---:|---:|
| Estático | 280 | -8854.00 | -9413.00 | 0.742609 |
| Expanding | 280 | -8854.00 | -9413.00 | 0.742609 |
| Rolling12 | 316 | -14698.60 | -15329.60 | 0.560425 |

Estático y expanding comparten el mismo modelo en enero. No sumarlos ni inferir que doce meses fallan o pasan a partir de uno. El tercer fit es expanding parafebrero; no hay resultadofebrero cerrado. Se preservan matrices, muestras, modelos y marcadores. El auditor mensual estaba implementado y revisado, sin ejecutarse sobre el año incompleto.

## 9. Calibración OOF y diseños no ejecutados

El diagnóstico encontró correlaciónpredicción/neto0.453–0.653enTRAIN y−0.026–0.018enVAL; después de elegir máximos,−0.099–−0.054enVAL. La selección aumenta el optimismo en las6combinaciones modelo/ticker. Restar un sesgo constante no reordena acciones ni garantiza actividad diaria.

Se implementó un calibrador prequential de residuos de máximos por procedimiento y ticker: escoge argmax antes de labels, incluye negativos/NO_FILL, pondera igual día/estado y sólo usa meses pasados con resultado ya disponible al cierre+1minuto declarado. El evaluador debía reproducir primero controles bitexact y después toda la trayectoria corregida, no sólo restar costes a trades originales. No hubo ejecución real. Revisión estática corrigió raíz de resume sin contrato; rerun final23pruebas pendiente al parar.

JEPA, transformers, agentesLLM, modelos de mundo y búsqueda tipoMuZero/AlphaZero se investigaron en literatura y diseños, **no se entrenaron como una nueva familia exitosa en esta sesión**. El inventario1–8DTE es sólo una posible fuente adicional; no se abrió entrenamiento/payoff de esa familia. Las propuestas se preservan sin convertirlas en resultados.
