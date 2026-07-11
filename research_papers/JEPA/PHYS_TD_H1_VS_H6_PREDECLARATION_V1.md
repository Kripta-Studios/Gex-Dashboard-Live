# Predeclaración — Phys-TD horizon h1 vs h6 downstream v1

**Congelada antes de ejecutar la corrida completa:** 2026-07-11 CEST.

## Hipótesis y factor único

El payoff exacto realiza holds de 30–180 minutos, mientras el downstream anterior solo recibió movimiento Phys-TD h1=5 minutos. Los encoders congelados ya fueron entrenados conjuntamente con horizontes `1/3/6/12`; h6=30 minutos alinea el pronóstico con el hold mínimo sin reentrenar ni cambiar arquitectura.

Control: `z_t + (pred_z_h1-z_t)`. Variante: `z_t + (pred_z_h6-z_t)`. No se añade h6 a h1: se reemplaza una motion por la otra. No se probarán h3, h12, combinaciones multi-horizon, Ada adapter ni pérdidas nuevas a partir de esta corrida.

## Paridad obligatoria

- Mismos cinco encoders/checkpoints y normalizadores por fold.
- Mismas filas exactas que el export h1 observado; h6 se calcula current-time sin requerir `target_z_h6`.
- El export nuevo debe reproducir `z_t` y `pred_z_h1` previos con diferencia absoluta máxima <=`1e-6` antes de entrenar.
- Mismos labels, ask de entrada, trayectoria/salida bid, contratos d25 SPXW/d35 QQQ-SPY y holds >=30m.
- Mismo head determinista hidden128/latent16, MSE clipped ±2, 40 épocas, batch512, AdamW, seeds `20260618+YYYYMM`, CUDA determinista y threshold grid.
- Mismos folds test `202601..202605`, tres meses internos, una posición/ticker, caps `4/2/1`, cooldowns `0/30/0` y grid observable dentro de 10:30–14:30 ET/5m.
- Junio de 2026 permanece físicamente sellado.

## Gates y decisión

Selección inner por ticker exige simultáneamente PF>=1,3, WR>=50%, al menos 54 trades en tres meses, mínimo 18 en cada mes y todos los meses positivos. Sin threshold válido se congela abstain antes del test.

h6 solo avanza si, en walk-forward externo, cada uno de SPXW/QQQ/SPY cumple PF>=1,3, WR>=50%, mínimo 18 trades en cada mes y 100% meses positivos. PnL agregado no puede seleccionar arquitectura. Si h6 falla, se rechaza y no se prueban otros horizontes post hoc.

Siempre `production_live_ready=false`; esta prueba no modifica live/systemd.

## Inputs y hashes

| Artefacto | SHA-256 |
| --- | --- |
| Dataset physics | `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720` |
| Manifest de espacios | `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8` |
| Exportador current horizons | `884E743E0CB994B21E6BA51E233B0B21F820AD5BE88148120A8F285C071C5BAF` |
| Downstream h1/h6 | `0ECFEA3767225098C96EE137F86DE0A5DFFD005CBCBF969B655518CF65427F52` |
| Test exportador | `FA0592E5B44EAFB91455ED79CD5F3E672FB15C9197176B8267602C015AE3BA76` |
| Test downstream | `C225C06F902BF16497FA1B62B8ACB67B84FC6DFACA1589596F8D0560AE2208D2` |
| Helper/test selector compartido | `D10EFDB23275CAB69057E453E2B3844099711476FB9A157D32D51679100CDE52` |
| Runner único | `559CEFB80AA86464CA36AF49DA437ED7B2C462CB541E558058BB2901B5C4D061` |

Tests focalizados `13 passed`; compile, PowerShell parse y diff-check PASS. Smoke CUDA de enero: 1.684 contextos current-time, 1.608 filas h1 alineadas, max diff z/h1 `0/0`, tres tickers, sin target futuro. El smoke vive solo en `tmp/phys_td_horizon_export_smoke_20260711` y no se reutiliza como evidencia.
