# Revisión antes de preparar caché row-mixed

El coordinador revisó el productor aislado y dio CLEAR para construir la caché,
sin autorizar todavía el entrenamiento GPU. SHA revisado:
`5c4adfe01e2a51f3eb0f16c96479edb326e2f06ea1f66b3721313ccaa9ab7ab2`.

Dos hallazgos se corrigieron antes de leer/construir datos reales de esta variante:
comparación de cada fuente con hashes previos de FLAGS64 TRAIN, y reanudación de
la caché por días/chunks sin reconstruir el conjunto completo. El código fija
también el hash de esa autoridad TRAIN. Se verifican los días completos y se
preservan únicamente las filas de un día iniciado sin sello antes de reescribirlas.

Ocho fixtures PASS: replay del RNG y tamaños originales, límites1024/parciales,
separación de estados del mismo minuto en días distintos, equivalencia exacta
del helper y diagnóstico, pesos/Adam/RNG al reanudar, plan parcial preservado,
rechazo de nuevos hashes que no coinciden con la autoridad, y recuperación por
día con detección de corrupción. Ruff PASS. No hubo cache real ni fit antes de
esta revisión. El plan actualizado se incluye en el binding de preparación.

Revisión de código/fixtures, no auditoría de resultados de mercado. Los controles
de ejecución futura y la revisión económica siguen siendo tareas separadas.
