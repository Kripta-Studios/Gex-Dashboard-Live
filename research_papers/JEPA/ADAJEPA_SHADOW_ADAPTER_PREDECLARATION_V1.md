# Predeclaración — AdaJEPA shadow adapter v1

**Congelada antes de evaluar:** 2026-07-11 CEST.

## Factor único

Control: `pred_z(t+1)` del encoder/predictor mensual congelado. Variante: el mismo `pred_z` más un adaptador diagonal residual de 64 parámetros (`motion_scale[32]`, `bias[32]`). El adapter se inicializa a cero y se resetea por ticker/día.

En cada timestamp se emite la predicción con el estado actual. Solo antes de la predicción siguiente se permite un paso SGD usando la transición anterior cuyo `target_z` ya es observable. No hay buffer futuro, outcome, PnL, acción ni modificación del encoder/predictor/policy.

## Configuración única, no seleccionada con test

- Learning rate `0.05`.
- Un paso SGD por transición observada.
- MSE latente media, gradient clip `1.0`.
- Norma máxima conjunta `0.5`; update no finito/excesivo hace rollback.
- Adaptador diagonal; sin búsqueda de arquitectura, LR, pasos o memoria.
- CUDA para evaluación; seed no interviene porque init es cero y no hay sampling.

## Datos y evaluación

- Cinco espacios coherentes del manifest SHA `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`.
- Test `202601..202605`, 15 celdas ticker×mes, 1.109–1.635 transiciones mensuales.
- Junio sellado; target disponible exactamente +5m.
- Métrica primaria: RMSE vectorial latente por ticker×mes.
- Secundaria: error medio por ticker/día y persistencia `z_t`.

Avanzar a una ablación downstream separada exige: adapter gana >=10/15 celdas, mediana RMSE favorable y Wilcoxon unilateral `p<0,05`; además mediana diaria favorable y Wilcoxon diario `p<0,05`. No se usa PnL para esta decisión. `production_live_ready=false` siempre.

## Hashes

| Artefacto | SHA-256 |
| --- | --- |
| Evaluador | `DE4BFBD9D3D324EF342B153A78A2398B8598AA2F50EDAE673DB1AF8A421AADEB` |
| Tests | `890FD54994CAD470423D92EECB532251A3B41E270F328F044B48842CBE25C080` |
| Runner | `5EA632B8AF4089B80F6FA4AE56D2F5F5F431722AF5FC07800368D80E3B701736` |
| Manifest spaces | `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8` |

Tests focalizados antes de lanzar: `19 passed`; parse, compile y diff-check PASS.
