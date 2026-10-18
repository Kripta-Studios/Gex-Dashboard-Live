# Comando mensual preparado, no ejecutado

La etapa `prepare` terminó; las etapas económicas siguen sin lanzar. Esperar a que termine el residual causal y se libere su matriz row-mixed. El fit mensual conserva los gates congelados de 12 GiB RAM y 16 GiB de margen de commit; estos gates se comprueban después de construir la matriz, por lo que también se verificará disponibilidad antes de iniciar el proceso. No cambiar código, gates ni parámetros para acelerar.

Comando previsto desde la raíz del repositorio, sólo después de la coordinación del proceso principal:

```powershell
$env:OMP_NUM_THREADS='4'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:BLIS_NUM_THREADS='1'
python research_papers/JEPA/level_oracle_20261018/run_monthly_walk_forward.py `
  --engine-root D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1 `
  --feature-root D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1 `
  --source-audit D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1_audit/audit.json `
  --implementation-review research_papers/JEPA/level_oracle_20261018/MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json `
  --out D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_v1 `
  --stage validation `
  1> D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_v1_validation.stdout.log `
  2> D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_v1_validation.stderr.log
```

Un proceso, modelos secuenciales; LightGBM `n_jobs=4` y predicción `num_threads=4`. `validation` ejecuta **24 fits únicos** para 2025 y publica su selección/freeze. Un posterior `--stage test`, autorizado por separado y con logs propios, añade **12 fits** de 2026: **36** en total para 54 combinaciones lógicas de tres modos y 18 meses. El modo estático reutiliza su modelo; expanding de enero2025 comparte esa ventana. No ejecutar `--stage all` ahora.

Checkpoints: muestras y chunks por día; targets, matriz e inputs por ventana; `models/<fit_key>.fit_started.json`, `.txt` y `.complete.json`; predicciones selladas antes de outcomes, resultados `months/YYYYMM/daily`, y `validation_freeze`. Resume verifica hashes y reutiliza artefactos completos. Un fit iniciado sin completion queda preservado y **no admite refit automático**. No detener un fit para ahorrar tiempo ni eliminar sus markers.

Primer fit: `train_20230101_20250101_exclusive`. Medir su duración mediante `started_utc` del marker inicial y `completed_utc` del completion, además del tiempo de construir el primer conjunto de chunks/matriz. Actualizar ETA con esas medidas separadas y con el tamaño de las ventanas siguientes; todavía no existe una duración de fit mensual observada. Monitorizar PID propio, memoria privada, RAM disponible y commit sin tocar otros procesos.

Antes del lanzamiento, revalidar las once dependencias contra la revisión `0af3b223…32cdc7`, runner `47a4df8b…d348bb`, fuente auditada `678eb21b…f3b9` y run binding `7250620e…58f`. La revisión operativa no modifica los bytes congelados ni autoriza el lanzamiento.
