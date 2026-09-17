# Comandos de continuación A/B

Especificaciones publicadas en `ce06af99`: 13_RECOVERY_SPEC.md y
14_ENGINE_COMPLETION_SPEC.md. El intento antiguo no se reutiliza.

```powershell
python -m pytest tests/multiscale_v1r1 -q
python -m ruff check neural/jepa/multiscale_v1r1 neural/jepa/multiscale_v1r1_audit tests/multiscale_v1r1
python -m compileall -q neural/jepa/multiscale_v1r1 neural/jepa/multiscale_v1r1_audit
```

Después de publicar el código, recuperación estrictamente documental/metadata:

```powershell
python -m neural.jepa.multiscale_v1r1.continuation_cli recovery --root D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01/recovery --specification research_papers/JEPA/multiscale_v1r1/13_RECOVERY_SPEC.md --old-root D:/GexResearchArtifacts/multiscale_v1r1/run_20260917_01 --source-root D:/ThetaData
```

Circuito completo de fixtures con modelos dobles y auditoría independiente:

```powershell
python -m neural.jepa.multiscale_v1r1.continuation_cli synthetic-e2e --root D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01/engine_fast_01 --specification research_papers/JEPA/multiscale_v1r1/14_ENGINE_COMPLETION_SPEC.md
```

El perfil usa dos decisiones por día y trece días laborables artificiales por mes
para ejercitar los 18 folds, 24 acciones y cuatro combinaciones. Las seis plantillas
de tensor son completas, reconstruidas y auditadas desde fuentes sintéticas.
Los modelos dobles usan una proyección declarada de ese tensor; esto no certifica
el entrenamiento real de V1R1 ni genera evidencia económica de mercado.

La reanudación añade `--resume` al mismo comando únicamente tras un checkpoint
de fold íntegro. Verifica código, contrato y todos los archivos; no reutiliza el
rehash parcial del intento antiguo. Trabajo parcial posterior al checkpoint falla
y se preserva; el siguiente intento sintético utiliza otro root. No sobrescribir
raíces existentes ni modificar parámetros de investigación tras resultados.

Smoke real de dos regresores LightGBM, A y B, con 600 × 92.048 y exportación:

```powershell
python -m neural.jepa.multiscale_v1r1.continuation_cli real-component-smoke --root D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01/component_real_01 --specification research_papers/JEPA/multiscale_v1r1/14_ENGINE_COMPLETION_SPEC.md
```

Este smoke mide los componentes sobre una señal artificial de baja entropía.
No es un benchmark del entrenamiento histórico completo. Su estado se publica
separado del E2E rápido y del estado de admisión histórica. Los roots que fallen
conservan sus archivos y no reciben summary PASS. Ningún comando admite proveedor,
credencial, broker ni una ruta real para generar PnL histórico.
