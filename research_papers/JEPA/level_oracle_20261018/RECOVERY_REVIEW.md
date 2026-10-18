# Revisión independiente de recuperación — 2026-10-18

## Revisión del helper implementado

Leídos `stage_recovery.py`, `recover_learners.py` y sus fixtures. Reejecución
independiente final de los catorce tests CPU: **14 PASS, 3,98 s**. Incluyen no refit de
GBT completo, ajuste sólo del pendiente con target/pesos exactos, igualdad de
actualización CPU tras restaurar RNG global NumPy/generador/Torch y AdamW,
último par válido, exportación mediante el productor real desde época 4 con
`optimizer.step` prohibido, conservación de archivos dentro de raíz, rechazo
de fallo científico, resúmenes parciales y liberación del lock Windows tras
terminación de un subproceso. No se ejecutó recuperación real ni prueba GPU.

Los snapshots usan copia validada por hash y publicación atómica de manifest;
el controlador conserva parciales y comprueba identidad del proceso, software,
hardware y fuentes antes de continuar. La autoridad freeze recuperada evita
reseleccionar usando test. El caso detectado de freeze **ausente**, test existente
y ningún snapshot recuperable ya está corregido: se rechaza tanto autoridad
ausente como parcial. Fixture independiente cubre ambos estados.

Los fixtures añadidos inyectan un fallo durante copia y comprueban que el target
no se publica y el temporal se conserva. Dos recorridos del controlador con
productor reducido cubren validación parcial y test parcial: conservan un ledger
parcial artificial muy favorable, producen el ledger determinista previsto,
prohíben refit/reentrenamiento y llaman al selector una vez antes del freeze o
cero veces cuando ya existe. El validador económico/modelos de esos recorridos
son dobles; no equivalen a una recuperación de entrenamiento real ni prueban
continuidad numérica CUDA. No quedan fallos concretos abiertos en esta revisión.

Alcance: lectura de `train_models.py` congelado y de su fixture CPU de
checkpoint. Este documento especifica comprobaciones para un helper externo;
no cambia el entrenamiento, la selección ni los procesos en ejecución.

## Estado real del productor

- Cada GBT se guarda al terminar su ajuste y después emite `model_fit` al log.
  `gbt_config.json` se escribe después de los dos modelos. Una interrupción
  entre ambos puede dejar un primer GBT completo sin ese JSON global.
- Cada época TCN guarda pesos, AdamW, generador NumPy, estado global NumPy,
  RNG PyTorch CPU y todos los RNG CUDA cuando el modelo está en GPU. La carga
  sucede después de inicializar modelo y optimizer, y antes del siguiente
  barajado de días y filas. No se pierde el estado de AdamW.
- El `.pt` se escribe a un temporal y se publica con `os.replace`; su JSON de
  hash/identidad se escribe después directamente. **El par no es atómico.**
  Una interrupción puede dejar temporal, `.pt` huérfano o JSON truncado.
- La identidad compara raíz de salida, dispositivo, versiones Torch/NumPy/
  LightGBM y hashes de inputs, modelos GBT y código. El CLI original sólo
  admite el último `.pt` por nombre, sin TCN final ni validación/test iniciados.
  Por ello no resuelve por sí solo un último checkpoint huérfano.
- No existe checkpoint intra-GBT ni intra-época. Antes de completar la primera
  época, el trabajo TCN debe repetirse desde su semilla inicial. Entre épocas
  sólo se repite la época parcial; un GBT interrumpido necesita ajuste completo.
  No se garantiza tolerancia a pérdida de alimentación: no hay `fsync` explícito.

El fixture CPU existente demuestra igualdad exacta de pesos en la siguiente
actualización tras restaurar AdamW, Torch CPU y el generador NumPy. No demuestra
por sí solo continuidad numérica CUDA ni ejercita el RNG global de NumPy.

## Pruebas requeridas para el helper externo

| Interrupción o cambio | Resultado esperado |
| --- | --- |
| Modelo GBT válido y línea completa `model_fit` del intento correspondiente | Reutilizar bytes; un espía de `fit` debe demostrar que no se reajusta. |
| Modelo ausente/truncado, o modelo sin confirmación de fin | No admitirlo como completo; conservar evidencia y ejecutar sólo el ajuste pendiente. |
| Primer GBT completo, segundo ausente y configuración global aún ausente | Conservar el primero; producir segundo/configuración con parámetros congelados. |
| Ambos GBT completos, sin checkpoint TCN | Arrancar sólo TCN desde la semilla fija; no reconstruir ni alterar la muestra/normalizadores. |
| Último `.pt` con JSON ausente, inválido o hash distinto | No cargarlo; conservarlo y recuperar sólo el último par íntegro reconocido. |
| Temporal de checkpoint presente junto a un par anterior válido | Ignorar el temporal para selección; no eliminar evidencia. |
| JSON con `complete_epoch_boundary=false`, época fuera de 1–4 o historia incompatible | Rechazar antes de restaurar parámetros. |
| Checkpoint completo intermedio | Restaurar todos los RNG/AdamW y continuar época siguiente; no repetir épocas completas. |
| Época 4 completa, falta exportación TCN final | Exportar desde ese checkpoint, sin actualizaciones de optimizador. |
| TCN final huérfano o validación/test parcial | No interpretar existencia como completitud; preservar y aplicar una ruta explícita de recuperación de evaluación. |
| Identidad de código/input/dispositivo/versiones/raíz distinta | Rechazar antes de cualquier escritura o ajuste. |
| Dos intentos de recuperación concurrentes | El segundo no puede escribir ni entrenar sobre la misma raíz. |

Un marcador JSON nuevo puede publicarse atómicamente después del `.pt`, actuando
como commit del par; no debe describirse como escritura simultánea de dos
archivos. El helper debe documentar si conserva pares parciales en su ubicación
o los mueve a un archivo de recuperación dentro de la misma raíz. Los hashes
de artefactos completos reutilizados deben permanecer iguales.

La prueba CPU de continuidad debería incluir varios grupos de días, barajado
de filas, RNG global NumPy, dropout, clipping y AdamW. Comparar siguiente orden,
pesos y estado del optimizer contra una rama ininterrumpida. Se puede comprobar
el manejo de estados CUDA mediante dobles sin ocupar la GPU; eso verifica el
protocolo de guardado/carga, no equivalencia numérica de un ajuste CUDA real.

## Recuperación de evaluación

No elegir un modelo/época por pérdidas de entrenamiento, métricas parciales o
test. Validación completa debe seguir ejecutando las nueve políticas y CASH con
el mismo orden/desempate. Si ya existe freeze válido, su selección permanece
idéntica y no se recalcula usando test. Si una salida de evaluación no se puede
reutilizar con integridad demostrable, preservarla y repetir determinísticamente
la evaluación completa con los mismos modelos; no reajustar modelos.

Una fixture de evaluación interrumpida debe comparar resultados, hashes de
predicciones reutilizadas, selección y ledger con ejecución ininterrumpida.
Forzar una métrica parcial muy favorable no debe cambiar qué se recupera ni qué
política queda elegida. Un resumen terminal sólo se publica después de todos
los checks originales. Esta revisión no autoriza reiniciar un proceso activo.
