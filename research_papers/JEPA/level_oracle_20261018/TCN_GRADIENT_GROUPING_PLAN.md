# Diagnóstico TRAIN de agrupación de gradientes

Medida sin actualizaciones autorizada después de observar el ajuste casi constante
en TRAIN completo y la capacidad de memorizar 128 ejemplos. No usa validación/test
ni selecciona checkpoint: usar exclusivamente FLAGS64 época4 previamente fijada.

Elegir 16 días TRAIN2023–24 por SHA256(`20261018|day_key`); en cada día elegir32
acciones de la muestra sellada por SHA256(`20261018|day_key|action_id`). Fallar si
alguno no tiene32; no buscar reemplazos por targets. Los512 ejemplos y sus IPW
son idénticos en ambas particiones:16 lotes diarios de32 versus16 lotes mezclados
de32, cada uno con dos acciones de cada día, respetando el orden hash por día.

Reconstruir seis entradas FLAGS64 idénticas. CPU4, arquitectura y loss originales,
denominador1024, sin optimizer, clip ni updates. Calcular gradientes anteriores
al clipping. Comparar normas, dispersión alrededor del gradiente medio, cosenos
entre lotes y respecto al medio, y pesos por lote. Informar adicionalmente normas
divididas por suma IPW, sólo como descripción: no cambia la loss ni los pesos.

Check crucial: las medias de gradientes daily y mixed deben coincidir con error
relativo L2 <=1e-4 (o absoluto L2 <=1e-7); mismas filas/pesos/denominador y modelo
determinista. Si no, marcar fallo técnico y no interpretar diferencias. Fixture
sintética comprueba partición exacta e invariancia de gradiente medio.

Sellar código/plan/checkpoint4/normalizadores/esquema/muestra y fuentes consumidas
antes de calcular gradientes; rehash final. Guardar identidades, SHA de entradas,
particiones y vectores de gradiente. No cambiar entrenamiento ni políticas, no
nuevo fit row-mixed. Variación menor de gradientes mezclados no prueba por sí sola
mejor optimización, generalización o rentabilidad; sólo informa esta hipótesis.
