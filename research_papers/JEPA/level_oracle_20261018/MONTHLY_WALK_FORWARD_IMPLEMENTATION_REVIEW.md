# Revisión preejecución del walk-forward mensual

Estado: `PASS_MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW` para las dependencias
exactas del JSON adjunto. No se abrieron resultados reales, no se ajustó ningún
modelo y no se leyó ninguna métrica económica durante esta revisión.

La admisión exige el PASS independiente del dataset full+short, root y hashes
de índice/contratos/completion, 2.619 días disponibles, seis ausentes exactos y
las24 filas de media sesión. Antes de cargar un array, contrasta contra el índice
auditado los hashes del NPZ de estados, su metadata, el NPZ de acciones y su
metadata. El manifest externo se incorpora a los checkpoints de predicción y
diarios y se vuelve a hashear al reanudar.

Para cada mes se ajustan primero las ventanas causales; después se generan y
sellan scores de los tres modos para todos los días disponibles. Sólo tras el
checkpoint conjunto se abren labels del mes y se ejecuta el scheduler. Los
empates usan el menor `action_id`, el umbral es estrictamente mayor que cero,
NO_FILL avanza un minuto y un fill avanza a `exit_i+1`.

La selección usa únicamente los doce meses de2025 y las escalas de la ventana
TRAIN común; congela una selección nula cuando ninguna alternativa cumple el
requisito diario. La ruta2026 reproduce ese freeze y no puede reseleccionar. Las
fuentes ausentes se conservan como `NO_EVALUABLE`; una economía positiva en los
días observables no satisface por sí sola el requisito diario de calendario.

Los15 fixtures reportados cubren sellado previo a labels, reanudación sin refit,
mutación de features incluso con metadata coherente, propagación de manifests,
NO_FILL, límites de media sesión, selección/freeze y cobertura completa. La
auditoría económica posterior deberá reconstruir fits, predicciones, ledgers y
métricas; este PASS sólo autoriza la ejecución de desarrollo desde estos bytes.
