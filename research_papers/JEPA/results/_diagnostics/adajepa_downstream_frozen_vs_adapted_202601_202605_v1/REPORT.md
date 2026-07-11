# AdaJEPA downstream frozen vs adapted v1 — informe final

## Dictamen

La adaptación causal mejora parcialmente el head de payoff como regresor, pero no genera una policy seleccionable. Ambos arms tienen `0/210` candidatos que cumplan simultáneamente PF >= 1,3, WR >= 50%, al menos 18 trades en cada mes interno y todos los meses internos positivos. Los 15 folds de cada arm congelaron `ABSTAIN_NO_VALID_THRESHOLD`; por ello no hay trades OOS y no se permite promoción.

Decisión congelada:

- `adapted_meets_full_ticker_gate=false`;
- `production_live_ready=false`;
- no retunar LR del adapter, head, thresholds ni gates con estos resultados;
- no modificar la policy live ni systemd.

## Contrato reproducido

- Fuente physics `executable_quote`, ask de entrada y trayectoria/salida bid, SHA-256 `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Manifest de cinco espacios coherentes SHA-256 `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`.
- Folds externos `202601..202605`; tres meses internos; seeds `20463219..20463223` derivados de `20260618+YYYYMM`.
- SPXW d25, QQQ/SPY d35; hold >=30m; una posición por ticker; cupos `4/2/1`; cooldowns `0/30/0`; rejilla 10:30–14:30 ET cada cinco minutos.
- Mismo head hidden128/latent16, 40 épocas, batch512, CUDA determinista y presupuesto para ambos arms. El único factor es `frozen_dz` frente a `adapted_dz`.
- `target_z`, error latente, outcome y PnL futuro no entran en features. Junio de 2026 está físicamente ausente.
- Provenance y runtime replay pasan en ambos arms; no hubo fallback ni proceso huérfano.

## Resultado del selector interno

Cada ticker aporta 70 candidatos por arm (14 thresholds × 5 folds). Las columnas muestran cuántos candidatos pasan cada gate por separado; ninguna fila pasa las cinco a la vez.

| Arm | Ticker | Volumen >=54 | Mínimo mensual >=18 | PF >=1,3 | WR >=50% | Todos meses positivos | Gate conjunto |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen | QQQ | 62 | 54 | 2 | 1 | 0 | 0/70 |
| frozen | SPXW | 65 | 64 | 1 | 0 | 0 | 0/70 |
| frozen | SPY | 47 | 15 | 0 | 0 | 0 | 0/70 |
| adapted | QQQ | 64 | 59 | 0 | 0 | 0 | 0/70 |
| adapted | SPXW | 65 | 63 | 2 | 0 | 0 | 0/70 |
| adapted | SPY | 48 | 16 | 0 | 0 | 5 | 0/70 |

Los máximos aislados no forman una policy válida. Frozen alcanzó PF máximo `1,729/1,366/1,213` en QQQ/SPXW/SPY; adapted `1,014/1,479/1,272`. Ningún arm consiguió simultáneamente estabilidad, WR y frecuencia. Como todos los folds se abstienen, los ceros OOS significan ausencia de policy seleccionable, no un PnL cero promocionable.

## Diagnóstico del head OOS

Sobre las mismas 15 celdas ticker×mes, adapted frente a frozen:

| Métrica | Wins adapted | Mediana adaptado−frozen | Wilcoxon unilateral |
| --- | ---: | ---: | ---: |
| MAE | 13/15 | `-0,005331` | `p=0,006226` |
| RMSE | 7/15 | `+0,003113` | `p=0,680664` |
| Directional accuracy | 10/15 | `+0,008571` | `p=0,053497` |
| MAE / baseline train mean | 13/15 | `-0,009246` | `p=0,006226` |

La mejora representacional previa sí reduce errores pequeños/medios, pero no las colas cuadráticas ni la selección económica. Esto rechaza la traducción directa `adapted_dz -> mismo payoff MSE -> policy`; no invalida el adapter como monitor shadow.

## Integridad y hashes

| Artefacto | SHA-256 |
| --- | --- |
| `summary.json` | `9B7007DA7C25469FFF1971487D91E9435D7694475501D130F0753C00FD41BC0D` |
| frozen candidate grid | `B3F43A30F14823EF83017B5BED73C4BA13616397D8DB209369C5680FBCF8D0F4` |
| adapted candidate grid | `9118579DDAF91C520B359473DC96BB44924B4687C30A3B06994AECD14D7DF813` |
| frozen fold summary | `E64A62A3C22661D59D615CE70F84B5ED56C6CEDBC3CDE5488F7A8E42E2E86E28` |
| adapted fold summary | `5172F981387F528496FE747BC2931B8B8D9D80E916A387F1551928A00BB334CE` |
| frozen representation diagnostics | `7302B1CA4FE7D37B08BFF16E2BE71B86BCD2C72F8479B4DFCF25173B9E1863C7` |
| adapted representation diagnostics | `9298CB0662C894780DCC7A802DDD9F1405B4C9AF5AC27967B6E4BDAF34A817B2` |
| frozen provenance | `EB196CF9699B168A84EB48BF8D3C753875C0A1D49ABC4972D56A232287F90883` |
| adapted provenance | `2433562791213EAB48AEAAA48A39D3F8CF0AB2D9380F5306CFD235F0E703F68B` |

Los diez checkpoints de ~136 KB se preservan localmente para auditoría, pero no se versionan. Un bug post-run podía dejar vacías las métricas-resumen de un ticker cuando todos sus scores inválidos empataban por redondeo en `-1e18`; el grid siempre conservó las métricas correctas. Se corrigió con `best_seen` y test sin reentrenar, reseleccionar ni cambiar trades.

## Siguiente paso admisible

La cola literaria Var-JEPA, PatchCore y AdaJEPA queda cerrada. Antes de proponer otro entrenamiento se debe medir, sin seleccionar policy ni abrir junio, la separabilidad disponible en los labels exactos d25/d35: oracle causal por evento, baseline de media de train y descomposición de error de elección CALL/PUT frente a error de calibración/cola. Solo si esa auditoría identifica un cuello de botella concreto se predeclarará una ablación de un único factor en el objetivo del payoff head, manteniendo representación, datos, folds, seeds y runtime congelados.
