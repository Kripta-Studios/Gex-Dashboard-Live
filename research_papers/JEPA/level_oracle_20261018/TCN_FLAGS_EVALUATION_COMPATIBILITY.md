# Compatibilidad numérica de inferencia TCN FLAGS

Corrección técnica declarada antes de la primera predicción de validación de FLAGS. El entrenamiento activo, los cuatro checkpoints, los normalizadores, los datos y la selección permanecen intactos. El proceso activo usa exclusivamente `--stage train` y termina antes de evaluar.

La rutina de inferencia del runner nuevo codificaba todos los estados del día y convertía la predicción a float64 antes de multiplicar por la escala de riesgo. La rutina original codifica únicamente `unique(all_si)`, recupera las posiciones mediante `inverse`, multiplica en float32 y después asigna a la salida float64. Aunque la red carece de dropout/BatchNorm y la operación es matemáticamente equivalente, los grupos de convolución y el redondeo pueden diferir.

`evaluate_tcn_flags_compat.py` sustituye exclusivamente esa rutina durante la fase de evaluación. Reproduce el orden, los grupos de estados, los lotes de acciones de 1024, el dtype de multiplicación y la asignación originales. Reutiliza el scheduler, costes, seis políticas, selección diaria y freeze del runner sellado. No vuelve a entrenar ni modifica archivos de entrenamiento.

Antes de predecir, guarda `evaluation_runtime.json` y copias del wrapper y esta nota, vinculadas por SHA al runner ejecutado, código original, modelo final de época4, normalizadores e identidad. Si existen predicciones sin ese binding previo, falla cerrado. Las recuperaciones requieren los mismos hashes. El freeze previo a test incluye esos artefactos; una comprobación final separada produce `evaluation_runtime_completion.json` y vincula también el completion económico sin reescribirlo.

Prueba sintética requerida: mismos pesos, pack, normalizadores y acciones que el helper original; estados repetidos/no contiguos, más de256 estados únicos y más de1024 acciones para atravesar ambas fronteras de lotes; comparación byte por byte de IDs y scores, además de caso vacío. Los dos GBT originales se sustituyen por dobles sin efecto en la salida TCN. Revisión focal independiente antes de usar datos de validación.

Los logs de la ejecución de evaluación deben guardarse fuera de la raíz de artefactos para que el freeze nunca incluya un archivo que siga creciendo. Esta corrección no autoriza cambios de arquitectura, target, loss, épocas, thresholds, calendario ni selección por resultados.
