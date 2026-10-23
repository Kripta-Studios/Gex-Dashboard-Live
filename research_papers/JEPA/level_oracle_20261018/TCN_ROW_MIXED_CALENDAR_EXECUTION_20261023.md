# Ejecución autorizada de la comparación TCN con calendario completo

Fecha: 2026-10-23. Autoridad de usuario: RESUMPTION_20261023.md.
Root autoriza ejecutar una vez el evaluador ya revisado, después de publicar
su código y el auditor separado. No se repite el entrenamiento de cuatro épocas.

La revisión de implementación conservada tiene alcance IMPLEMENTATION_ONLY y
execution_authorized=false: esos bytes no se cambian. Este documento añade la
instrucción operativa posterior, una vez cerrado el auditor independiente.

Identidades previas obligatorias:

- Evaluador: a6c68f4ef7486b538b8119b5dfdb035b3dc078bae274c6aa10cc922f6596b33c.
- Review del evaluador: cbd8efc6680144ae81afff8d5ac7bab4502bb7d35ef5ef5900fc8e6fd8fe7302.
- Auditor: 7a39395977568193764ae9c4b3e837d05e0d510ac45cc0e5649a77732c4e5b57.
- Modelo final de época cuatro: 2b55e783c8a7989fa6a579bc6b903f1eddd8b6d40e365aeada687aef630bc87e.

Se preservan las seis políticas, umbrales, costes, normalizadores y selección
fijados. Evaluar 750 ticker-días de 2025, congelar selección incluso nula y sólo
después evaluar 369 esperados de 2026, con seis NO_EVALUABLE. Los 1.104 controles
completos deben ser exactos respecto a FLAGS64; nueve controles cortos requieren
la inferencia nueva explícita del modelo original. Todo sigue SEEN_DEVELOPMENT.

Comando:

```powershell
python -u research_papers/JEPA/level_oracle_20261018/evaluate_tcn_row_mixed_calendar.py `
  --training-root D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_v1 `
  --flags-root D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1 `
  --control-audit D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1_economic_audit/audit.json `
  --session-root D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1 `
  --session-audit D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1_audit/audit.json `
  --implementation-review research_papers/JEPA/level_oracle_20261018/TCN_ROW_MIXED_CALENDAR_IMPLEMENTATION_REVIEW.json `
  --output D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_calendar_v1_evaluation
```

Antes de lanzar: salida nueva, ausencia de otro proceso de esta evaluación,
hashes exactos y al menos 2.000.000.000 bytes libres de RAM y commit. Comprobar
también al menos esa memoria libre de GPU para el dispositivo CUDA original.
CPU Torch cuatro hilos; BLAS uno; caché de un día. Registrar PID, creation_time,
comando, código, lecturas de recursos y logs en una raíz hermana nueva.

La comparación griegas observada consume aproximadamente 250 MB de RAM y el
mensual está revalidando checkpoints; los fits mensuales continúan seriales.
La coexistencia sólo se admite bajo esos gates y seguimiento de recursos. No
alterar procesos ajenos para obtener memoria. Estos mínimos de lanzamiento no
representan cotas garantizadas de consumo durante toda la evaluación.

Un fallo se conserva sin borrar parciales ni reintentar automáticamente. Tras
completion, ejecutar el auditor revisado en una salida independiente y nueva,
según su especificación. No publicar métricas parciales como resultados finales,
no escoger políticas con 2026 y no modificar producción.
