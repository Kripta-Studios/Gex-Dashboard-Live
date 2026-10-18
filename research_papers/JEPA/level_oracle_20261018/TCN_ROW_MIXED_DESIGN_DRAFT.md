# Diseño pendiente: mezcla de filas, manteniendo el presupuesto de actualización

**CACHE_PREPARATION_AUTHORIZED; TRAIN_NOT_STARTED.** Diseño preparado después
del diagnóstico de memorización. La medida de gradientes del checkpoint 4 pasó
su check de invariancia; el coordinador autorizó construir la caché después de
revisar el código. El entrenamiento aún no está autorizado para ejecución y
FLAGS64 permanece intacto. No se cambian hiperparámetros por sus resultados.

Comparación propuesta: misma muestra TRAIN2023–24 de270377 acciones, arquitectura,
FLAGS64, máscaras, riesgo/IPW, targets, loss/1024, AdamW, clip1, seed y cuatro
épocas. Sin selección de época ni hiperparámetros con2026. Cambiar únicamente
la asignación de filas a minibatches para mezclar días.

Reconstruir exactamente el calendario original de tamaños: inicializar su RNG
NumPy20261018, permutar los1491 días en cada época y sus índices internos igual
que el productor original, dividir cada día en bloques de hasta1024. Guardar
la secuencia completa de tamaños y los estados RNG. No sustituir por265 lotes
de1024: deben conservarse1491 updates por época y las mismas270377 exposiciones.
Un RNG independiente y nombrado, también seed20261018, genera una permutación
global de las filas por época, que se divide usando dichos tamaños. Guardar
permutación, hash y curso RNG por época. Cada fila aparece exactamente una vez
por época; no cambian IPW, denominador, ni número de pasos Adam.

Preparación técnica propuesta: memmap sellado de las seis entradas normalizadas
de la muestra (aproximadamente16GB float32 en disco), construido en chunks de256
filas. Preservar identidad acción/día/estado y comparar bytes con neural_batch
original en fixtures y muestras deterministas de cada fuente. Nunca construir
usando val/test. La lectura por minibatch mantiene RAM acotada; los archivos se
sellan antes del primer update. La implementación compara cada fila escrita, no
sólo muestras. Las fuentes deben coincidir con la autoridad `training_complete`
de FLAGS64 SHA `bd17be758bdc9a5a430f48a162c6925dac5c89689ca506013b1548e53e76e18b`;
un hash nuevo de una fuente modificada no basta. Registrar dimensiones reales
y espacio requerido antes de reservarlos. Memmaps persistentes con sello por
día y hashes por chunks de 256 filas permiten reanudar días completos verificados.
Si un día iniciado carece de sello, preservar sólo sus filas antes de reescribirlas;
no reconstruir los 16 GB ni sobrescribir una caché completa válida.

El encoder debe reconocer estados únicos por (día,state_i), no sólo state_i;
conservar bloques de hasta256 estados del helper original y restaurar inversas
antes de score_actions. Probar explícitamente equivalencia de entradas/outputs
para un lote de un solo día contra el helper congelado. La composición del lote
mezclado y sus diferencias numéricas asociadas se documentan como tratamiento;
no introducir cambios adicionales de dtype, multiplicación, máscaras o inferencia.

Checkpoint completo por época: modelo, Adam, RNG Torch/NumPy/CUDA, generadores de
schedule y mezcla, permutaciones/tamaños, hashes de inputs/productores y métricas.
Reanudar sólo el siguiente límite verificado; recuperación conserva parciales.
Diagnóstico TRAIN fijo por época es observacional y conserva RNG/modo; usar
siempre época4, no el mejor error. Reutilizar inferencia original exacta revisada,
con binding explícito al nuevo productor/modelo; ningún cambio silencioso de helper.

Preparación autorizada en `tcn_row_mixed_v1`, sólo CPU, cuatro hilos y monitor de
RAM. Ocho fixtures y Ruff pasaron; revisión del coordinador CLEAR sobre productor
SHA `5c4adfe01e2a51f3eb0f16c96479edb326e2f06ea1f66b3721313ccaa9ab7ab2`.
Antes de un eventual fit faltan autorización de arranque, recursos libres y
contrato económico final; no existe entrada de inferencia/economía en este runner.
La economía sólo podría compararse con selección2025 fijada y test2026
de desarrollo ya visto; ninguna conclusión de rentabilidad prospectiva.
