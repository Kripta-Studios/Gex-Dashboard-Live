# Continuidad técnica del aprendiz

El entrenamiento original y su protocolo permanecen congelados. `stage_recovery.py`
publica copias externas verificadas; `recover_learners.py` permite continuar una
interrupción técnica. No se ha ejecutado una recuperación del mercado: el proceso
original continúa normalmente. El fingerprint externo identifica PID, hora de
creación, comando, GPU/UUID, controlador, compute capability, CUDA, cuDNN, Python,
Torch, NumPy, pandas y LightGBM.

Snapshots actuales:
`D:/GexResearchArtifacts/level_oracle_20261018/learners_v1_recovery`.
Contienen muestra, matriz, normalizadores, código/protocolo, ambos GBT completos,
pares de checkpoints de época y modelo neural final cuando se publica. Cada copia
usa un temporal único, verifica hashes, hace fsync y publica mediante rename; el
manifest completo se publica al final. Los temporales de un fallo se conservan.
El watcher de esta ejecución es PID 10044, iniciado a 17:31:20 UTC, sesión de
herramienta 58628. Comprueba cada 30 segundos y termina cuando existe
`learners_v1_runtime_v2/completion.json`; no termina ni modifica el entrenador.
La captura read-only del modelo TCN final terminó a 17:41:05 UTC y verificó
igualdad de todos sus parámetros con el checkpoint de época 4.

## Comando de continuación

Sólo después de una interrupción técnica diagnosticada, con el proceso original
realmente detenido y recursos suficientes. Avisar al coordinador antes de ejecutarlo.
No ejecutar al mismo tiempo que el entrenamiento actual.

```powershell
python -u research_papers/JEPA/level_oracle_20261018/recover_learners.py `
  --output D:/GexResearchArtifacts/level_oracle_20261018/learners_v1 `
  --runtime D:/GexResearchArtifacts/level_oracle_20261018/learners_v1_runtime_v2 `
  --recovery D:/GexResearchArtifacts/level_oracle_20261018/learners_v1_recovery `
  --oracle-root D:/GexResearchArtifacts/level_oracle_20261018/engine_v1 `
  --feature-root D:/GexResearchArtifacts/level_oracle_20261018/features_v1 `
  --oracle-audit D:/GexResearchArtifacts/level_oracle_20261018/engine_v1_audit_v4/audit.json `
  --device cuda --reason process_interruption
```

Las otras razones técnicas admitidas son `resource_exhaustion` e `io_interruption`.
El helper rechaza proceso vivo, otro dueño del mismo output, hardware/software
distinto, cambios de autoridad/fuentes y fallos científicos/nonfinite. Un resultado
económico desfavorable nunca es una razón de recuperación.

La continuación reutiliza ambos GBT completos y sólo ajusta un GBT si no existe
evidencia de finalización. Conserva una pareja de época válida anterior si una
posterior está incompleta; restaura parámetros, AdamW y todos los RNG. Antes de la
primera época completa repite el TCN desde su semilla original. Desde época 4 sólo
exporta, sin nuevas actualizaciones; si existe snapshot final lo reutiliza.

La evaluación incompleta se archiva con hashes y motivo bajo
`output/recovery_attempts/<identificador>/`, comprobando rutas resueltas dentro del
output antes de mover. Sin freeze se repite validación completa con los mismos
modelos. Con freeze se conservan selección y modelos exactos y se repite sólo test.
No se selecciona a partir de resultados parciales ni del test. Los archivos previos
no se borran ni se sobrescriben. La recuperación vuelve a verificar fuentes y gates.

## Límites y pruebas

No hay checkpoint dentro de un árbol GBT ni dentro de una época: se puede perder el
trabajo del GBT o época en curso. El productor publica `.pt` y después `.json`, por
lo que ambos no son una transacción indivisible; los pares incompletos se rechazan.
La equivalencia exacta no se ofrece al cambiar hardware o versiones. Los snapshots
protegen frente a interrupciones de proceso, no sustituyen un backup en otro disco.
Un `summary.json` truncado se archiva como publicación incompleta; un resultado
completo verificado no se reejecuta. Cada continuación registra su propia identidad
de proceso y fallo. Los GBT que termine esa continuación publican evidencia y
snapshot inmediatamente para una eventual segunda interrupción. No se ha probado
una continuación CUDA de mercado: la igualdad experimental de recuperación es CPU.
El helper toma un bloqueo exclusivo de byte mediante Windows `msvcrt`: el sistema
operativo lo libera incluso si muere el proceso. Un archivo `recovery.lock`
persistente no implica un dueño vivo. Se conserva además el rechazo explícito del
entrenador original y de otro proceso que use el mismo output.

El snapshot `frozen_evaluation` conserva freeze, hashes y resumen de validación y
fuentes previas al test; verifica las predicciones originales, sin duplicarlas.
Permite restaurar esa autoridad exacta. Si no existe tal snapshot, un freeze
truncado sólo puede reconstruirse antes de empezar test, repitiendo validación
completa con los mismos modelos. Freeze ausente o incompleto con test existente falla cerrado.
La pérdida de predicciones originales de validación requiere diagnóstico, pues
el snapshot conserva sus hashes, no una segunda copia de todos esos NPZ.

Catorce pruebas sintéticas CPU/dobles pasan: no refit de GBT completos, ajuste sólo del GBT
pendiente con target/pesos exactos, continuación exacta de parámetros/Adam/orden y
RNG global NumPy/Torch/generador, rechazo de parejas corruptas/incompletas y fuentes
cambiadas, exportación real del productor desde época 4 con `optimizer.step`
prohibido, preservación de directorios con límites de ruta, rechazo de fallo
científico y copia atómica que conserva el destino previo. No son un replay de
mercado ni una nueva evaluación económica. También distinguen un summary truncado
de un resultado completo.
Los casos adicionales comprueban freeze parcial y exclusión/liberación de lock
mediante un subproceso que termina sin ejecutar limpieza Python.
También prueban fallo durante copia con temporal conservado, autoridad ausente tras
test y el controlador completo con productor doble: validación interrumpida se
repite con igual selección/ledger; test interrumpido conserva el freeze, sin llamar
a selección ni ajustes. Una métrica parcial artificial de +999.999.999 se conserva
como evidencia y nunca influye en la selección o ledger final.
