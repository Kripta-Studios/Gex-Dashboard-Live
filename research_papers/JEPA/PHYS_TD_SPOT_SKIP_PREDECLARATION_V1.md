# Predeclaración — Phys-TD direct spot momentum skip v1

**Congelada antes de ejecutar:** 2026-07-11 CEST.

## Hipótesis y único factor

La compresión `z+h1` no separó CALL/PUT, aunque los tres retornos spot backward-looking forman parte del input observable del encoder. La prueba compara:

- control: 79 features `z_t + pred_z_h1-z_t + contrato/contexto`;
- variante: las mismas 79 más el bloque fijo `ret_5m_bps`, `ret_15m_bps`, `ret_30m_bps`, renombrado como `direct_spot_momentum_*`.

El bloque es una única skip connection temporal ordenada 5/15/30m. No se añaden ret1m, skew, flow, niveles, cross-asset, h6, Ada ni nueva loss. Las tres columnas se eligieron por mecanismo y alineación temporal antes de mirar outcomes de esta ablación, no por correlación OOS.

## Causalidad/live

`event_option_live_snapshot._ret_bps` toma el último spot con `minute <= current_minute-lookback`; nunca lee un bar posterior. El dataset physics contiene las tres columnas en 36.796/36.796 filas, con variación no nula y junio ausente. Son parte de los 277 `feature_cols` del checkpoint y se regeneran live con el mismo contrato.

La variante usa el preprocesador fit solo en train. Ningún outcome, target, high/low posterior, PnL o `target_z` entra al input.

## Paridad sellada

- Fuente SHA `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Espacios SHA `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`.
- Horizon manifest h1 SHA `F21336B1941508E382B6097CE44CEA9863253F07E5899374A5B9CC59BD361BDE`.
- Mismas filas h1, labels, contratos d25/d35, executable_quote ask→bid, hold>=30m, una posición/ticker, caps `4/2/1`, cooldowns `0/30/0` y grid 10:30–14:30/5m.
- Mismo head hidden128/latent16, MSE ±2, 40 épocas, batch512, optimizador, thresholds, folds `202601..202605`, tres meses inner y seeds `20260618+YYYYMM`.
- CUDA determinista; junio de 2026 sellado.

## Gates

Cada policy inner requiere PF>=1,3, WR>=50%, >=54 trades en tres meses, mínimo18/mes y todos los meses positivos. Si no existe threshold válido, abstain antes del test.

La variante solo avanza si cada ticker cumple externamente PF>=1,3, WR>=50%, mínimo18 trades en todos los meses y 100% meses positivos. No se selecciona por PnL agregado. Si falla, no se añadirán otros bloques skip a partir de este resultado.

`production_live_ready=false` siempre.

## Hashes

| Artefacto | SHA-256 |
| --- | --- |
| Downstream | `EC4B683704B83878895FB82AC026F6FDD2942A949EB1A1EC9A734C03915B06B9` |
| Test | `00A28EBD268B878F75A3CC7ED45B418384DAD6E2EFD2FADF3A36B52BEAC1DC6A` |
| Runner | `3DCE5DADB11136C4AF76AFF20945274503E95BC2B8AF084567E543D39CC0E173` |

Suite focalizada `11 passed`; compile, parse y diff-check PASS. Aún no lanzado.
