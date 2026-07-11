# Predeclaración v1 — objetivo exacto return vs win

## Pregunta causal

¿El edge del pipeline dense15 histórico procedía de optimizar la probabilidad de resultado positivo en vez de regredir el retorno asimétrico? Se cambia un único factor del head supervisado: `return regression_l1` frente a `win probability`. No se cambia arquitectura, feature set, universo, bucket, ejecución ni selector.

## Datos y sellado

- Dataset: `tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics/event_option_dataset.parquet`.
- SHA-256: `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`.
- Train acumulativo desde 2022; tres meses internos inmediatamente anteriores a cada test.
- Tests externos: `202601..202605`. Junio de 2026 queda excluido y sellado.
- Labels: entrada ask, salida bid; stop -60%, trailing 50%/25%, take-profit de emergencia 1000%, hold mínimo 30m y máximo 180m.

## Contrato fijo

| Ticker | Bucket | Cap/día | Cooldown |
| --- | ---: | ---: | ---: |
| SPXW | d25 | 4 | 0m |
| QQQ | d35 | 2 | 30m |
| SPY | d35 | 1 | 0m |

Cada celda usa entrenamiento `target`, features live-observables idénticos, LightGBM 240 árboles, LR 0,035, 31 leaves, min child 80, subsample/colsample 0,85, lambda 5 y seed 20260618. Solo cambia classifier binario frente a regressor L1. Thresholds son las rejillas ya declaradas en el selector; no se agregan thresholds después de ver resultados.

## Selección y gates

Cada fold selecciona threshold exclusivamente en sus tres meses internos. Una policy solo opera el mes externo si la validación cumple simultáneamente por ticker:

- PF `>=1,3`;
- WR `>=50%`;
- al menos 18 trades en cada mes;
- PnL positivo en los tres meses.

El éxito final exige las mismas gates agregadas por ticker, mínimo 18 trades en cada uno de los cinco meses OOS, PnL positivo en todos y hold observado `>=30m`. Abstención no cuenta como rentabilidad.

## Interpretación predeclarada

- Si `win` cumple todas las gates y `return` no, el siguiente factor será backfill d50 sobre el win head, elegido solo con inner validation.
- Si ninguno cumple, no se abrirá otra arquitectura: se descompondrá la diferencia con el legacy sobre las mismas filas (label simplificado frente a executable return, bucket y filtro/cupo) para corregir el mecanismo responsable.
- Si ambos cumplen, se preferirá el que tenga mayor PF mínimo por ticker; el otro queda control.
- Ningún resultado modifica o promociona producción.

## Implementación congelada

- Selector con allowlist exacta: `neural/jepa/walkforward_event_option_profile_selector.py`.
- Analizador: `neural/jepa/analyze_exact_objective_ablation.py`.
- Runner: `run_exact_objective_ablation_v1.ps1`.
- CPU: Ryzen 9, 28 hilos LightGBM; la medición previa mostró que OpenCL GPU era más lento para este workload. La RTX queda reservada para modelos tensoriales posteriores justificados.

Hashes SHA-256 congelados:

```text
selector  95279496D6C0A1820522AB2244F70EEEEEA916300486AE87BD7A76D628B8C2AA
analyzer  47FDEDACE21A053DC703AD4E991662739CC5C320FD301C4F05DB3D0575B4FB75
test      EA4F3A99EF07C1BCCDE03F6A48A175AA65A5E39F079E735F425005CAD783E3B3
runner    148189944C4313C284A16B5F1236B68B6FC2EBDAEADE0252A3B3AFD7A8DAF010
```
