# Entrenador aislado de 424 variables

Implementación técnica del plan científico ya congelado. No modifica ese plan ni
sus nueve dependencias. Una sola ejecución posterior a revisión y autorización;
este documento y el código no autorizan un fit por sí solos.

Entrada: `common_greek_train_v1` COMPLETE, 270377 filas float32 de 424 columnas;
primeras 152 idénticas bit a bit a `market_cue_control_v1/train_x.npy`. Se verifican
las siete claves de fila contra la muestra original y las etiquetas y pesos contra
`market_cue_control_v1/targets.npz`, sellado por su matrix.complete. Se reutilizan
las escalas TRAIN y CONFIG exactamente, sin normalizar de nuevo, seleccionar
hiperparámetros ni reentrenar el control.

La revisión fija los SHA de la matriz terminada, del contrato del builder, del
control y de sus etiquetas. El contrato nuevo registra todas las fuentes, código
revisado, configuración, esquema, escalas y versiones. Se rehashean las fuentes
antes del ajuste y antes del cierre. Salida separada `common_greek_control_v1`:
`common_greek_net.txt`, `run_contract.json`, `fit_started.json`,
`train_readback_predictions.npy`, `export.complete.json`, `model.complete.json`.
Las predicciones TRAIN sólo certifican igualdad exacta del modelo en memoria y
su lectura desde disco; no se usan para selección o cambio de parámetros.

Checkpoint: publicación atómica y fsync del modelo y predicciones, después marker
export. Si existe un export completo se finaliza sin ningún update/refit; si sólo
hay un fit_started o export parcial se conserva el intento y se rechaza el refit
automático. Un modelo completo se verifica y reutiliza. Bloqueo exclusivo por
raíz evita escritores concurrentes. El gate de recursos hereda 12 GiB RAM y
16 GiB commit libres del control. No carga ni evalúa validación/test.

Las fixtures incluyen unión exacta de filas/targets/IPW, mutación de autoridades,
prefijo alterado, export/readback real LightGBM, continuación sin refit tras export
y rechazo de ajuste interrumpido. El evaluator independiente se implementa aparte.
