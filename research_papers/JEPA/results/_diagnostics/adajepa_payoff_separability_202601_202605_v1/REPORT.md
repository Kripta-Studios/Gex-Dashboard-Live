# Auditoría de separabilidad del payoff AdaJEPA v1 — resultado

## Dictamen

Las dos gates predeclaradas fallan en ambos arms. El head no separa de forma estable CALL/PUT frente a una elección constante train-only y su score casi no ordena retorno realizado. Por tanto, esta evidencia no autoriza probar una nueva loss de calibración/ranking.

| Arm | Side wins vs constante | Mediana Δ side accuracy | Spearman positivo | Mediana Spearman | Gate side | Gate event-score |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| frozen | 7/15 | `-0,01349` | 7/15 | `-0,00684` | FAIL | FAIL |
| adapted | 8/15 | `+0,01877` | 9/15 | `+0,01505` | FAIL | FAIL |

Se exigían >=10/15 side wins y mediana positiva; para event-score, >=10/15 correlaciones positivas y mediana >0,10.

## Evidencia por ticker

Las métricas siguientes usan todos los eventos disponibles y solo diagnostican separabilidad; no aplican policy, thresholds ni runtime caps y no son PnL promocionable.

| Arm | Ticker | Eventos | Side acc | WR head | PF head | Retorno medio head | Retorno medio constante | Retorno medio oracle-side | Spearman score-retorno |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| frozen | QQQ | 2.077 | 49,64% | 40,35% | 0,789 | -0,0762 | -0,1134 | +0,3913 | +0,0081 |
| frozen | SPXW | 2.625 | 52,02% | 39,23% | 0,802 | -0,0744 | -0,1329 | +0,3765 | -0,0067 |
| frozen | SPY | 2.583 | 51,26% | 42,31% | 0,847 | -0,0533 | -0,0968 | +0,4010 | +0,0186 |
| adapted | QQQ | 2.077 | 50,34% | 41,02% | 0,813 | -0,0710 | -0,1134 | +0,3913 | +0,0279 |
| adapted | SPXW | 2.625 | 52,36% | 39,18% | 0,828 | -0,0652 | -0,1329 | +0,3765 | -0,0098 |
| adapted | SPY | 2.583 | 52,53% | 43,72% | 0,891 | -0,0394 | -0,0968 | +0,4010 | +0,0148 |

Solo 2/15 celdas frozen y 3/15 adapted tienen retorno medio head positivo; ninguna celda frozen pasa WR50/PF1,3 y adapted pasa WR50 en 2/15 pero PF1,3 en 0/15.

## Interpretación causal

El techo oracle-side es fuerte: la mediana de eventos con exactamente un lado positivo es 71,95%, y el oracle obtiene retorno medio aproximado `+0,38..+0,40` por ticker. Esto demuestra headroom en los labels, no predictibilidad causal. El head está prácticamente en azar de side y su score no ordena outcomes.

El mismatch más directo es temporal: el contrato de salida mantiene posiciones 30–180 minutos, pero este downstream recibe solo `pred_z_h1-z_t`, un pronóstico de cinco minutos. Los mismos checkpoints fueron entrenados con horizontes `1/3/6/12`; h6 corresponde exactamente a 30 minutos. Esto justifica una futura ablación aislada h1 frente a h6, no un sweep de horizontes. No justifica h3, h12, una nueva loss ni adaptación live.

## Integridad

- 5/5 meses y 15/15 celdas por arm; 7.285 eventos idénticos frozen/adapted.
- Baseline constante elegida solo con train anterior a los tres meses internos.
- Oracle marcado no causal; no hubo selección de policy.
- Checkpoints verificados por hashes; fuente `AB144DBA...F720`, manifest `F398B110...F7B8`, downstream `9B7007DA...BC0D`.
- Junio ausente, `production_live_ready=false`, ningún proceso huérfano.

| Artefacto | SHA-256 |
| --- | --- |
| `summary.json` | `984EFF37FE81469450D1C26D4050DA0FCF3E59D0EFFCD9491A1A924E831CA21B` |
| `ticker_month_decomposition.csv` | `A6EA9C62F7202DD64C366067C3A71B6B4108E60985A6E3E739191A9534D98F4E` |
| `artifact_manifest.csv` | `31CDEA8161BF841217FCFCA2B316A4949836F9947666E7BF47AC44EC65546A06` |

## Decisión

- `side_signal_supported=false` para frozen y adapted.
- `event_score_signal_supported=false` para frozen y adapted.
- `advance_to_calibration_or_ranking_loss=false`.
- Siguiente hipótesis admisible: reemplazar exclusivamente movimiento h1 por h6 con mismas filas, z, contratos, head, folds, seeds, presupuesto y gates. Debe predeclararse y no puede combinarse todavía con el adapter.
