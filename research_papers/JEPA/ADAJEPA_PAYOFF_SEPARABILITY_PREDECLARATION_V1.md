# Predeclaración — auditoría de separabilidad del payoff AdaJEPA v1

**Congelada antes de leer estas métricas:** 2026-07-11 CEST.

## Pregunta

El downstream frozen/adapted se abstuvo en todos los folds aunque adapted redujo MAE. Esta auditoría no entrena, no elige thresholds y no crea una policy: descompone si el cuello de botella está en elegir CALL/PUT, en ordenar/calibrar eventos o en que los labels exactos no contienen headroom suficiente.

## Inputs sellados

- Physics `executable_quote` ask→bid: `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Espacios coherentes: `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`.
- Resultado downstream inmutable: `9B7007DA7C25469FFF1971487D91E9435D7694475501D130F0753C00FD41BC0D`.
- Checkpoints exactos frozen/adapted ya entrenados; cada hash se verifica contra `selected_folds.csv` antes de inferencia.
- Test `202601..202605`, SPXW d25 y QQQ/SPY d35, mismos eventos y labels; junio se rechaza físicamente.

## Métricas predeclaradas

Por arm y celda ticker×mes:

1. exactitud de side del head frente al side con mayor retorno realizado;
2. baseline causal de side constante, elegido solo por la media CALL/PUT del train anterior a los tres meses internos;
3. retorno/WR/PF de head, baseline constante y oracle-side sobre los mismos eventos;
4. regret de side `oracle - head`;
5. MAE/RMSE de las dos acciones y Spearman entre score elegido y retorno realizado;
6. tasas de exactamente un side positivo, ambos positivos o ninguno.

El oracle usa outcome futuro y es exclusivamente un techo no causal. Las métricas sobre todos los eventos tampoco son replay de trading: no se usarán como policy, PnL promocionable ni sustituto de caps/cooldowns.

## Regla para la siguiente hipótesis

- `side signal supported`: el head supera la exactitud de side constante en al menos 10/15 celdas y la mediana de la diferencia es positiva.
- `event-score signal supported`: Spearman score-retorno es positivo en al menos 10/15 celdas y su mediana supera `0,10`.
- Si side pasa y event-score falla, la siguiente ablación admisible cambiará solo el objetivo de ranking/calibración de eventos.
- Si side falla, no se probará una pérdida de calibración: la representación/head no separa acción de forma estable y se requiere una hipótesis causal nueva.
- Si ambos pasan pero las gates siguen fallando, podrá predeclararse un único objetivo robusto de cola; no se hará sweep de pérdidas.

Ninguna rama autoriza relajar PF/WR/18 trades/mes/meses positivos, abrir junio, tocar live/systemd o marcar `production_live_ready`.

## Implementación congelada

| Artefacto | SHA-256 |
| --- | --- |
| Analizador | `B2B8CB0C4E9C9466209C4494031567B190FCB8D1D8B8BC6CA4FD4D76F0CBA1C3` |
| Tests | `60C27B4EAB8E0A456CA5351C90AAADB8D35D5810F0D122848EFC3AA4AA6A436A` |
| Runner | `4638FB1E1CBF4E6D8B20A4F8C0AE0C3F1C5A5875F59B23A481490D962F40A708` |

El exportador rápido implementa algebraicamente el mismo SGD diagonal float32 y tiene paridad con la referencia Torch (`atol=2e-7`, `rtol=2e-6`). Tests focalizados `7 passed`; parse y compile PASS. La CPU Ryzen ejecuta la secuencia pequeña con menos overhead que miles de kernels GPU; no hay entrenamiento en esta auditoría.

## Resultado final

Frozen/adapted obtuvieron solo `7/15` y `8/15` wins de side frente a constante. Spearman score-retorno fue positivo en `7/15` y `9/15`, con medianas `-0,00684/+0,01505`; ambas gates fallan. `advance_to_calibration_or_ranking_loss=false`.

El oracle no causal sí muestra headroom y 71,95% de eventos con exactamente un side positivo. El mecanismo pendiente es el mismatch h1=5m frente a hold>=30m; solo h1→h6 puede predeclararse como siguiente factor. Informe: `results/_diagnostics/adajepa_payoff_separability_202601_202605_v1/REPORT.md`.
