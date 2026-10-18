# Diagnóstico descriptivo de scores guardados

Fijado el 18 de octubre de 2026, antes de leer las predicciones de los aprendices para este diagnóstico. **No activo hasta `COMPLETED_CAUSAL_LEARNER_DEVELOPMENT`.** No ajusta modelos, genera predicciones, escoge umbrales, modifica selección ni reinterpreta 2026 como holdout nuevo.

Universo: todas las acciones ofrecidas con scores guardados en `{validation,test}/{ticker}_{YYYYMMDD}.npz`; 2025 y 2026H1 se informan por separado y por SPXW/SPY/QQQ. No es la distribución de trades ejecutados: varias acciones comparten estado, contrato, trayectoria y resultado; tampoco son millones de observaciones independientes.

Bindings antes del cálculo: estado COMPLETED del productor; `freeze.json` para normalizers y manifest de predicciones de validación; todos los SHA diarios del manifest correspondiente; IDs en orden exactamente iguales a `engine_v1/.../actions.parquet`; SHA de acciones/labels/advantages publicados en el índice completo sellado del motor. Verificar escalas positivas finitas y coincidencia de `summary.risk_scales_usd` con normalizers. La auditoría independiente de ejecución se incorpora mediante una constancia separada cuando exista; este diagnóstico no la sustituye ni reproduce modelos.

Verificar también igualdad exacta entre archivos NPZ realmente presentes, claves de manifest y días completos esperados; no ignorar archivos extra. La raíz del motor debe coincidir con la raíz auditada del freeze y el total de días consumidos con el índice. Opcionalmente aceptar una ruta de audit económico independiente: exigir estado PASS exacto, misma raíz de aprendices y hashes de summary/freeze/manifests/índice/completion, guardando su SHA. Si no se proporciona ese artefacto, informar `UNVERIFIED_AT_DIAGNOSTIC_RUN`; no aceptar una etiqueta PASS libre del llamante.

Modelos y targets, sin excepciones:

- `gbt_net`: score USD frente a `labels.net_base`.
- `tcn_teacher`: su score económico principal USD frente a `labels.net_base`; no usar probabilidad auxiliar.
- `gbt_advantage`: score USD frente a `advantages.dp_advantage`. Es imitación de una ventaja privilegiada del oracle, **no retorno esperado ni ventaja causal realizable**.

Dividir score y target por la misma `risk_scales_usd[ticker]` congelada en `normalizers.json`. Las escalas son constantes de entrenamiento, no capital actual por operación. Bins de score normalizado fijados ahora:

`[-inf, -0.1, -0.05, -0.02, 0, 0.02, 0.05, 0.1, inf]`.

Intervalos cerrados a izquierda y abiertos a derecha; un score exactamente cero pertenece a `[0,0.02)`. Scores/targets no finitos, IDs duplicados, ausencia de archivo, cobertura distinta o hash incorrecto fallan explícitamente; no se eliminan filas silenciosamente. No-fill mantiene el neto cero publicado; la etiqueta DP conserva su definición original.

Por ticker/modelo/periodo y bin: número de acciones, media de score y media de target normalizados. Para el grupo completo: número de acciones y días, medias, RMSE, sesgo `media(score−target)`, R² `1−SSE/SST` y fracción de scores estrictamente positivos. Si el target es constante, R² será `null`, sin forzar 0/1. Se conserva el número de scores cero. Todo pondera acciones por igual; no se aplican pesos del muestreo de entrenamiento al universo completo de predicción.

Acumular sumas y varianza del target de forma incremental por día, sin cargar el universo de acciones en RAM. Guardar CSV de grupos/bins, JSON y manifest de hashes propio. No bootstrap por acción, tests de significación iid, búsqueda de bins, calibradores o filtros económicos nuevos. Un buen RMSE no garantiza decisiones rentables; un sesgo positivo no prueba que restarle una constante mejore la política.

Comprobaciones sintéticas previas: bordes exactos de bins, signo de sesgo y errores conocidos, equivalencia de acumulación particionada frente a cálculo conjunto, R² indefinido con target constante, rechazo de valores no finitos y distinción explícita del target de `gbt_advantage`. El código y esta especificación se copian y hashean antes de la ejecución real, en una raíz nueva.
