# TCN FLAGS V1: flags y cobertura en escala natural

Estado: **PREDECLARED_NO_FIT**. Esta variante se implementa después de observar el resultado del TCN original y su diagnóstico TRAIN. No representa una prueba histórica intacta. No se entrena hasta revisión del runner y coordinación de GPU/RAM con el responsable de los experimentos CPU.

## Única intervención de aprendizaje

Conservar el TCN, la muestra original de 270.377 acciones TRAIN 2023–2024, orden y pesos IPW, escalas de riesgo originales, targets, arquitectura, batch denominador 1024, AdamW(lr=.001, weight_decay=.0001), clip global 1, semilla 20261018 y cuatro épocas. No hay early stopping ni elección de checkpoint por métricas. Se usa siempre la cuarta época.

Cambiar exclusivamente la normalización de los **64 canales semánticos** siguientes: media 0 y desviación 1, de modo que sus valores naturales [0,1] pasen intactos. La lista deriva del schema y la construcción de features, no de valores observados, desviaciones pequeñas ni resultados test. El runner exige el schema exacto y valida los rangos; no recorta valores.

**Base, 17 bits:** `spot_valid`, `ib_valid`, `change_1m_valid`, `change_5m_valid`, `change_15m_valid`; `call_oi_top1_valid`, `call_oi_top2_valid`, `call_oi_top3_valid`; `put_oi_top1_valid`, `put_oi_top2_valid`, `put_oi_top3_valid`; `call_gamma_top1_valid`, `call_gamma_top2_valid`, `call_gamma_top3_valid`; `put_gamma_top1_valid`, `put_gamma_top2_valid`, `put_gamma_top3_valid`.

**Base, 15 fracciones de cobertura:** `ib_valid_fraction`; `current_call_quote_valid_fraction`, `current_call_iv_valid_fraction`, `current_call_oi_known_fraction`, `current_call_present_fraction`, `current_call_delta_valid_fraction`, `current_call_vega_valid_fraction`, `current_call_theta_valid_fraction`; los siete nombres correspondientes `current_put_quote_valid_fraction`, `current_put_iv_valid_fraction`, `current_put_oi_known_fraction`, `current_put_present_fraction`, `current_put_delta_valid_fraction`, `current_put_vega_valid_fraction`, `current_put_theta_valid_fraction`.

**Tokens, 15 fracciones de cobertura:** `spot_valid_fraction`; `call_quote_valid_fraction`, `call_iv_valid_fraction`, `call_oi_known_fraction`, `call_present_fraction`, `call_delta_valid_fraction`, `call_vega_valid_fraction`, `call_theta_valid_fraction`; `put_quote_valid_fraction`, `put_iv_valid_fraction`, `put_oi_known_fraction`, `put_present_fraction`, `put_delta_valid_fraction`, `put_vega_valid_fraction`, `put_theta_valid_fraction`.

**Acción, 17 bits:** `is_put`, `quote_valid`, `iv_valid`, `greek_present`, `delta_valid`, `vega_valid`, `theta_valid`; `target_source_fib`, `target_source_call_oi`, `target_source_put_oi`, `target_source_call_gamma`, `target_source_put_gamma`; `stop_source_fib`, `stop_source_call_oi`, `stop_source_put_oi`, `stop_source_call_gamma`, `stop_source_put_gamma`.

Las cuatro fracciones de OI positivo conservan zscore: describen contenido económico entre OI conocido, no disponibilidad. Los bits de procedencia son multi-hot, no categorías mutuamente excluyentes.

Todos los demás medios/std se copian sin alteración del entrenamiento original. Permanecen estandarizados tiempos, edades, `abs_delta_mean`, `selected_delta`, `delta_bucket`, fracciones de masa fuera de la rejilla, precios, griegas y mapas. No hay clipping de continuos ni nueva multiplicación por máscaras. Las máscaras finite añadidas por el normalizador y las máscaras token/bar/map independientes conservan su representación original y su lugar en la arquitectura.

## Fuentes y separación

Runner separado `run_tcn_flags.py`; no editar `train_models.py` ni el bundle original `learners_v1`. Reutilizar desde ese bundle las funciones de features, normalización, arquitectura y scheduler. Registrar hashes del wrapper, este plan, código compartido, muestra, normalizadores originales/ajustados, schema, autoridades de auditoría y cada pack consumido. El binding debe declarar qué funciones proceden del original y qué bucle instrumentado es nuevo.

Nueva raíz prevista: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1`. El control usa exclusivamente los vectores `tcn_teacher` ya guardados y sellados de `learners_v1`; no se reentrena ni vuelve a inferir el control. La variante produce predicciones causales nuevas; cada vector se guarda antes de abrir sus labels de ejecución. Las decisiones conservan el horario libre del scheduler original, sin primera entrada forzada.

## Instrumentación y checkpoints

Por época registrar norma global de gradiente antes de clipping, frecuencia con norma >1, distribución de normas y número de updates, además de pérdidas online por cabeza. Evaluar el checkpoint de esa época sobre la misma muestra TRAIN fija, sin gradientes: MSE ponderada, BCE ponderada, suma/1024, media y dispersión de predicción, R² frente a constante ponderada y referencias constantes pooled/por ticker. Estas métricas no seleccionan época, hyperparámetros o políticas.

Cada frontera de época guarda modelo, optimizer, epoch/history, generador de shuffle NumPy, RNG NumPy global/Python/Torch CPU/CUDA, entorno y hashes de fuentes. Escribir checkpoint y metadata mediante temporales y reemplazo atómico, nunca sobrescribir un checkpoint completo; mantener puntero al último completo. Resume únicamente desde el último checkpoint completo y verificado, con mismo dispositivo/entorno/código/inputs. Una época parcial puede repetirse desde su frontera anterior, nunca una época completa. La inferencia y evaluación también conservan progreso por día con hashes; no reutilizar artefactos parciales silenciosamente.

## Selección 2025 y evaluación 2026H1

Seis políticas predefinidas: control original y variante, cada una con thresholds 0,5,10 USD. Selección conjunta sólo con 2025. Para ser candidata, una política debe ejecutar al menos una operación FILLED **en cada ticker-día del calendario**. NO_FILL no cuenta. Registrar además cobertura de días observables por separado. Una ausencia de fuentes es `NO_EVALUABLE` y falla la cobertura total; las seis ausencias de 2026 no se borran y nunca permiten declarar PASS completo.

Entre candidatas diarias seleccionar máximo `sum_ticker(PnL_base_2025 / risk_scale_ticker)`. Empates exactos: control antes de variante, después menor threshold. CASH no satisface la exigencia diaria y no es una política aprobable. Si ninguna cumple, `selected_policy=null`; congelar también el mejor score descriptivo con etiqueta explícita `diagnostic_best_not_approved`, sin convertirlo en política aprobada.

Congelar selección/ausencia de selección, seis resultados de validación, modelo final, normalizadores, manifiestos de predicción y hashes antes de evaluar ejecución nueva 2026H1. Informar seis políticas test sólo como diagnóstico, el comparador pareado al mismo threshold y el mejor de cada brazo fijado por 2025. No rescatar un threshold, brazo, ticker o mes por 2026.

El gate económico adicional conserva la definición anterior por ticker: neto base y adverso positivos, PF base >=1.2 (o ganancias positivas sin pérdidas), >=60 trades y >=3 meses positivos. Exigir también el hard gate diario y cobertura total. Toda conclusión sigue siendo development visto, sin promoción, recepción de quotes acreditada o rentabilidad prospectiva.

## Verificaciones antes de fit

Pruebas sintéticas de lista semántica/rangos, identidad de los continuos, ausencia de dependencia en datos test para la normalización, equivalencia del bucle instrumentado con el original cuando recibe los mismos normalizadores, checkpoint/resume con optimizer y RNG, selección diaria/NO_FILL/ausencias/empates y schema de outputs. Revisión independiente del cambio y recursos libres antes de cualquier fit real. No barrer arquitecturas, loss, epochs o learning rate en este intento.
