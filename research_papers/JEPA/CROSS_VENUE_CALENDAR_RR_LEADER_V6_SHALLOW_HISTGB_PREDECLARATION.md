# CROSS_VENUE_CALENDAR_RR_LEADER_V6_SHALLOW_HISTGB — predeclaración

> **Cerrada sin evaluación el 2026-07-26.** El usuario priorizó una recaptura
> exacta y, en su defecto, exclusión outcome-free para evaluar el V4 inmutable
> en 2026. No se implementó ni calculó ninguna predicción o métrica V6.

**Congelada:** 2026-07-26 Europe/Madrid, después de observar y auditar V1–V5,
antes de calcular una sola predicción o métrica V6.

## Autoridad y papel causal

El usuario autoriza continuar la vía económica V4 con los artefactos ya
disponibles bajo Options Standard. Esta autorización sustituye únicamente el
bloqueo de investigación interna posterior a V5; no reabre V1–V5, no convierte
2023–2025 en OOS y no autoriza datos de mayor entitlement.

V6 es una única falsificación development post-outcome. Mantiene exactamente
la información, mapping, eventos, clocks, labels y costes de V4 y cambia una
sola dimensión: el clasificador lineal por un árbol boosted superficial fijo
capaz de representar interacciones no lineales. No se descargan datos, no se
reconstruyen Greeks/IV y no se consultan clocks u outcomes 2026.

```text
new_market_source_accessed=false
outcome_2026_accessed=false
production_modified=false
v1_v5_rerun=false
development_2023_2025_post_outcome=true
```

## Inputs sellados

| Autoridad | Filas | SHA-256 |
| --- | ---: | --- |
| V2 `development_dataset.parquet` 2023–2024 | 1.482 | `459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b` |
| V2 `SUMMARY.json` auditado | — | `c79bddfe476a3fa8670a38d79480d4727d195d091aa5e206c013e357338f03a7` |
| V4 `development_dataset.parquet` 2025 | 735 | `87413fb1c605c221aa8f225ad9877ccbdb6d5eca45877f4fa97a5b60d321d04b` |
| V4 `SUMMARY.json` auditado | — | `a2beced1f021e156b53deaed3932dafc0af18f18f582d0b9af5db1a0762bd21b` |
| Predeclaración V4 | — | `0c1a18b745072fb5265e83209e9267a41aa0387024f988831835bdc7272e5062` |
| Registry base | — | `17ef0c74f0485566f5e4ba47905003c4d3c558b457bec775691580d0bebf0796` |
| HEAD base | — | `ffbb0f28022dc05e72bd4ad82a91b3c61983063f` |

El evaluator debe exigir esos bytes exactos, los summaries PASS previos, las
filas exactas, ausencia de duplicados ticker/fecha, features finitas y paridad
`base_gross_bps > 0 == direct_win`. No abre fuentes raw ni vuelve a producir
features. Cualquier discrepancia cierra antes del fit.

## Mapping, features, target y ejecución

Mapping inmutable:

- QQQ ← sensor QQQ;
- SPY ← sensor SPY;
- SPXW ← sensor SPY.

Las 29 columnas, en orden, son exactamente:

```text
signal_pressure
abs_signal_pressure
calendar_rr_t0
front_rr_t0
back_rr_t0
front_rr_change
back_rr_change
option_spot_return_5m_bps
qqq_return_1000_1035_bps
qqq_return_1020_1035_bps
qqq_return_1030_1035_bps
qqq_open_return_std_bps
qqq_open_range_bps
qqq_positive_open_return_fraction
spy_return_1000_1035_bps
spy_return_1020_1035_bps
spy_return_1030_1035_bps
spy_open_return_std_bps
spy_open_range_bps
spy_positive_open_return_fraction
spxw_return_1000_1035_bps
spxw_return_1020_1035_bps
spxw_return_1030_1035_bps
spxw_open_return_std_bps
spxw_open_range_bps
spxw_positive_open_return_fraction
ticker_QQQ
ticker_SPXW
ticker_SPY
```

No se añaden lags, mes, probability V4, métricas de calidad, outcome rolling,
volatilidad futura, payoff de opción ni features nuevas. Target:
`direct_win = 1[base_gross_bps > 0]`. Si la probabilidad es `>=0,5`, se usa
`base_side`; si es `<0,5`, se invierte. No hay abstención, filtro de confianza,
threshold tuning, tamaño variable ni selección de ticker/fecha.

La entrada/salida sigue siendo open10:36→open13:36, hold180m, una posición por
ticker/día y no-overlap. Coste primario round-trip1bp; 2/3bps son sensibilidades
no selectivas. `reject_while_open` se exige en una fase física posterior, nunca
se infiere de este cash proxy.

## Modelo único congelado

Runtime: Python/scikit-learn ya versionados en el repositorio. Modelo exacto:

```python
HistGradientBoostingClassifier(
    loss="log_loss",
    learning_rate=0.05,
    max_iter=100,
    max_leaf_nodes=None,
    max_depth=2,
    min_samples_leaf=20,
    l2_regularization=1.0,
    max_features=1.0,
    max_bins=255,
    categorical_features=None,
    monotonic_cst=None,
    interaction_cst=None,
    warm_start=False,
    early_stopping=False,
    scoring="loss",
    validation_fraction=0.1,
    n_iter_no_change=10,
    tol=1e-7,
    verbose=0,
    random_state=0,
    class_weight=None,
)
```

No scaler, imputer, weights, calibration, ensemble, grid, seed sweep, refit
mensual o cambio posterior de parámetros. El evaluator serializa todos los
params, `classes_`, `n_iter_`, train hashes y probabilidades.

## Folds development walk-forward

- `D2024`: fit pooled con todas las filas 2023 del dataset V2; test con todas
  las filas 2024 del mismo dataset.
- `D2025`: fit pooled con las 1.482 filas 2023–2024 V2; test con las 735 filas
  2025 V4.

Los folds son independientes: D2025 no reutiliza el modelo D2024. Se persiste
D2024 antes de computar D2025. Ambos años son development visto y no pueden
llamarse outer/OOS.

## Gates conjuntivas

Para cada uno de QQQ/SPXW/SPY y cada año 2024/2025, simultáneamente a 1bp:

- PF `>1,20`;
- WR `>45%`;
- neto `>0`;
- mínimo `13` trades en cada mes;
- PnL `>0` en cada uno de los doce meses.

Se reportan las 72 celdas ticker-año-mes. Un solo fallo produce
`CLOSED_DEVELOPMENT_GATE`, cierra V6 y prohíbe cualquier nueva variante,
threshold, seed, profundidad, feature o selección por año/ticker.

Un auditor independiente debe volver a cargar los dos datasets, refittear ambos
modelos, comparar params/probabilidades/acciones/ledger/costes/meses/gates y
rehash de todos los outputs. Evaluator y auditor se committed/pushed antes de
ejecutar el evaluator; resultados y audit se versionan después.

## 2026 y producción

2026 permanece cerrado incluso si development pasa. V6 no permite ampliar
`Greek∩IV` más allá de los cuatro repairs V1R1, ni intersectar, reparar,
recapturar, excluir o hacer nearest/as-of sobre los cinco IDs nuevos de junio
2026. Un PASS development solo autorizaría un nuevo gate 2026 outcome-free que
debe satisfacer el contrato exacto sin tocar esos IDs; si no puede, V6 queda
`BLOCKED_DATA` sin outer.

No se modifican `services/`, `bots/`, `systemd/` ni live. Payoff físico
ask→bid, no-overlap, hold30–180m y `reject_while_open` solo se consideran tras
un outer2026 PASS auditado y committed.
