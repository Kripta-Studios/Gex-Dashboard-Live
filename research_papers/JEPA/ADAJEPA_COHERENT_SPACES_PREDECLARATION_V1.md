# Predeclaración — espacios coherentes AdaJEPA shadow v1

**Congelada antes del build:** 2026-07-11 CEST.

Este build no evalúa trading ni adapta modelos. Crea el sustrato causal necesario para comparar después predictor congelado frente a adaptación shadow sin mezclar coordenadas de encoders OOF distintos.

## Folds

| Test | Train encoder hasta | Inner posterior | Export coherente |
| --- | --- | --- | --- |
| 202601 | 202509 | 202510–202512 | 202501–202601 |
| 202602 | 202510 | 202511–202601 | 202501–202602 |
| 202603 | 202511 | 202512–202602 | 202501–202603 |
| 202604 | 202512 | 202601–202603 | 202501–202604 |
| 202605 | 202601 | 202602–202604 | 202501–202605 |

Cada fold entrena un encoder flat único solo hasta `train_end`, guarda state/config/normalizer y usa ese mismo checkpoint para re-encodear todo su rango. El export produce transiciones de cinco minutos `z_t`, `pred_z(t+1)` y `target_z(t+1)`; el target queda disponible únicamente en el timestamp siguiente.

## Presupuesto y contrato

- Fuente physics executable_quote SHA-256 `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- SPXW/QQQ/SPY 0DTE, features live, 10:30–14:30 ET/5m, context 6, horizontes 1/3/6/12.
- Flat, z32/phys12/delta16, hidden128, 2 capas, 8 épocas, batch1024.
- Seed base `20260618`, CUDA determinista, mismo presupuesto en cinco folds.
- Sin outcome/PnL en encoder/export; `target_z` no es feature live.
- Junio 2026 físicamente rechazado por el exportador.
- Checkpoints/parquets grandes no se añadirán a Git; manifest/hashes/métricas pequeñas sí.

## Hashes congelados

| Artefacto | SHA-256 |
| --- | --- |
| Trainer/export transition function | `C5F47AF154413FD1ADCDC651D7FD7460155A59E64D958EEBEAF4961E2E003AF5` |
| Aplicador checkpoint | `C1C0CDA63488BE6C2E665E6285A1FBD88B192BB655344FE0BE494661EADF98EC` |
| Runner | `0900B63B997B6136D09DB665187920262C89C23FCE4EFEA6478218674839E3BE` |
| Dataset | `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720` |

Tests previos: `17 passed`; parse PowerShell, compile y diff-check PASS.

## Paso posterior, no autorizado todavía

Tras auditar los cinco espacios se predeclarará aparte la comparación frozen vs adapter. No se elegirán learning rate, número de pasos o norma mirando test/PnL.

## Resultado del build

Los cinco folds terminaron en 125 s, con cutoffs/seeds/presupuesto correctos. Filas OOS: `1608/1109/1380/1553/1635`; todos los pares son +5m, contienen SPXW/QQQ/SPY y no incluyen junio. Manifest SHA-256 `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`.
