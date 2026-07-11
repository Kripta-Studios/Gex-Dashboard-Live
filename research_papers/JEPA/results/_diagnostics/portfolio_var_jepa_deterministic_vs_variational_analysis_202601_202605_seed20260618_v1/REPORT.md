# Portfolio Var-JEPA: deterministic vs variational payoff head

Comparación nested walk-forward sellada en enero-mayo de 2026. Junio de 2026 no se leyó.
El encoder de mercado flat OOF permanece congelado y actionless; solo cambia el head de payoff.
La incertidumbre se registró como diagnóstico y no participó en thresholds ni selección.

## Decisión

- Mejora reproducible de representación: `false`.
- Diagnóstico de incertidumbre apoyado: `false`.
- Avanzar a ablación de abstención por incertidumbre: `false`.
- Cumple gate downstream completo por ticker: `false`.
- `production_live_ready=false`.

## Representación OOS pareada

| Métrica | Pares | Wins Var | Mediana Var-Control | Wilcoxon p unilateral |
| --- | ---: | ---: | ---: | ---: |
| mae | 15 | 9 | -0.013979 | 0.488983 |
| rmse | 15 | 9 | -0.004596 | 0.380768 |
| mae_to_train_mean_ratio | 15 | 9 | -0.022681 | 0.467041 |
| directional_accuracy | 15 | 7 | -0.003241 | 0.423462 |
| effective_rank_ratio | 15 | 0 | -0.156054 | 1 |

## Incertidumbre

Spearman incertidumbre-error fue positivo en 1/15 celdas; mediana `-0.180431`.

## Gates downstream por ticker

| Arm | Ticker | Trades | WR | PF | Min mes | Meses positivos | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| deterministic | SPXW | 0 | nan% | nan | 0 | nan | FAIL |
| deterministic | QQQ | 0 | nan% | nan | 0 | nan | FAIL |
| deterministic | SPY | 0 | nan% | nan | 0 | nan | FAIL |
| variational | SPXW | 0 | nan% | nan | 0 | nan | FAIL |
| variational | QQQ | 0 | nan% | nan | 0 | nan | FAIL |
| variational | SPY | 0 | nan% | nan | 0 | nan | FAIL |

No se selecciona arquitectura por PnL agregado. El downstream es evidencia secundaria; la continuación a uncertainty-abstention exige primero mejora de predicción en celdas ticker×mes y una relación incertidumbre-error reproducible.
