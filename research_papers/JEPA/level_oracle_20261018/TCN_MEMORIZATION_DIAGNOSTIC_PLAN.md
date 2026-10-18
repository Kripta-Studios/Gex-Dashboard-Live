# TCN: capacidad de ajuste en 128 ejemplos TRAIN

Diagnóstico posterior a los resultados anteriores, separado del entrenamiento de
cuatro épocas en curso. No modifica su modelo, selección, muestras ni evaluación.
Se escribe antes de seleccionar o entrenar el bloque real de este diagnóstico.

Universo: la muestra TRAIN sellada de 270377 acciones de 2023–2024. Ordenar por
SHA256 de `20261018|day_key|action_id`, desempatar por identidad y tomar 128;
no estratificar ni filtrar por target. CPU, cuatro hilos, sin CUDA. Inicialización
desde cero con seed 20261018 y la arquitectura original LevelTCN. Usar exactamente
los normalizadores FLAGS64 ya fijados y sus máscaras, escalas de riesgo e IPW.
Full batch de 128 acciones, 500 actualizaciones AdamW lr=.001, weight_decay=.0001,
clip de norma 1. Loss original: suma IPW de (error cuadrático de net/riesgo +
.1 BCE del teacher state_optimal_action), dividida por 1024. La composición del
batch y la repetición del bloque son deliberadamente diferentes al fit completo.

Medir en updates 0,50,…,500 MSE ponderado/no ponderado, R² frente a la media
ponderada fija de targets, dispersión de predicciones y ambas pérdidas. Guardar
las 500 normas previas a clipping. Siempre finalizar en update500; ninguna época,
política ni hiperparámetro se selecciona usando este diagnóstico.

Comparar SHA por fila de las seis entradas normalizadas exactas, incluyendo dtype
y forma; contar entradas idénticas con targets net/teacher contradictorios y el
suelo MSE ponderado impuesto por targets diferentes para entradas idénticas.
Sellar código, plan, muestra, normalizadores, esquema y fuentes TRAIN consumidas
antes de actualizar pesos; rehash final. Guardar identidades, targets, métricas,
pesos iniciales/finales y optimizer. No leer predicciones, métricas ni labels de
validación/test. Una buena memorización sólo prueba capacidad en este bloque;
no demuestra generalización, rentabilidad ni causalidad live. Una mala tampoco
identifica por sí sola la causa. No cambiar el experimento principal en función
del resultado. Ejecutar una vez, en raíz nueva; sin barridos ni rescate.
