# AdaJEPA shadow adapter v1

Comparación causal entre el predictor Phys-TD congelado y un adaptador diagonal residual de 64 parámetros, reseteado por ticker/día. Cada update usa únicamente la transición anterior ya observada. No se empleó PnL ni se modificó ninguna policy.

## Resultado

- 7.285 transiciones OOS, 281 ticker-días y 15 celdas ticker×mes.
- Adapter gana 15/15 celdas; mediana RMSE adapter−frozen `-0,002121`; Wilcoxon unilateral `p=3,0518e-05`.
- Adapter gana 277/281 días, pierde 2 y empata 2; mediana diaria `-0,002348`; `p=9,1398e-48`.
- Wins diarios QQQ/SPXW/SPY: `88/90`, `96/97`, `93/94`.
- Rollbacks: 0. Norma máxima observada: `0,021298`, muy por debajo del límite 0,5.
- Junio de 2026 ausente; primera predicción de cada ticker/día usa 0 updates y norma 0.

## Decisión

`representation_improved_reproducibly=true` y `advance_to_separate_downstream_ablation=true`. `production_live_ready=false`.

La magnitud es modesta y no demuestra edge económico. La siguiente prueba debe ser una única ablación downstream donde control y variante compartan encoder, datos, head, thresholds, folds y seeds; solo cambia predicción frozen frente a predicción adaptada disponible causalmente. `target_z` y errores futuros permanecen excluidos de features.
