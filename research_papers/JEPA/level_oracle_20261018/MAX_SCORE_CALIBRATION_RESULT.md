# Calibración general y selección por máximo

Diagnóstico cerrado. Restar un sesgo constante conservaría el orden de los
scores y no recuperaría su discriminación; podría cambiar abstenciones, pero
no se ha aplicado ni evaluado ninguna corrección. No se entrenan modelos ni
se buscan umbrales adicionales en este diagnóstico.

Diagnóstico descriptivo cerrado sobre TRAIN96 y VAL741 ya vistos; dos modelos congelados, cero fits e inferencias nuevas. No cambia políticas ni el resultado económico anterior. Se verificaron scores/IDs/estado y traza de ejecución.

Cada día pesa igual; dentro de cada día pesan igual sus acciones, sus estados con candidatos o sus trades ejecutados, según cohorte. Los días sin unidades se cuentan y tienen media indefinida. Las medias de ejecución no coinciden necesariamente con la media por trade del diagnóstico anterior, que daba igual peso a cada trade. NO_FILL aporta neto0 en todasacciones/argmax.

Argmax se calcula por estado antes de umbral y sin restricciones por posición; incluye máximos negativos y conserva NO_FILL. No constituye una cartera ejecutable. La cohorte de trades ejecutados sí condiciona a ejecución observada y disponibilidad del scheduler. Error es score menos neto.

La correlación en todas las acciones va de 0.453 a 0.653 en TRAIN, y de -0.026 a 0.018 en VAL. Tras argmax, la correlación VAL va de -0.099 a -0.054. En 6 de 6 combinaciones ticker/modelo, elegir el máximo aumenta el error medio frente a todas las acciones. Hay por tanto degradación general observada y una amplificación al seleccionar máximos; no se reduce descriptivamente a un único desplazamiento constante de calibración. Esto es compatible con pérdida de generalización y optimismo de selección, sin demostrar el mecanismo causal ni que corregir uno baste para rentabilidad.

## train

| Modelo | Ticker | Cohorte | Días con unidades/esperados | Unidades | Score medio USD | Neto medio USD | Error USD | MAE | RMSE | Correlación |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gbt_net | QQQ | all_actions | 32/32 | 181809 | -11.119 | -12.127 | 1.008 | 35.041 | 54.627 | 0.4697 |
| gbt_net | QQQ | argmax_before_threshold | 32/32 | 4961 | -6.740 | -2.474 | -4.266 | 32.253 | 51.052 | 0.4086 |
| gbt_net | QQQ | executed_trades | 18/32 | 36 | 6.288 | 77.288 | -71.000 | 103.533 | 177.100 | 0.1563 |
| gbt_net_episode | QQQ | all_actions | 32/32 | 181809 | -11.315 | -12.127 | 0.812 | 35.231 | 55.037 | 0.4534 |
| gbt_net_episode | QQQ | argmax_before_threshold | 32/32 | 4961 | -7.162 | -3.540 | -3.622 | 31.627 | 47.368 | 0.4165 |
| gbt_net_episode | QQQ | executed_trades | 17/32 | 39 | 5.871 | 37.169 | -31.298 | 62.548 | 89.177 | 0.4099 |
| gbt_net | SPXW | all_actions | 32/32 | 180670 | -10.764 | 7.533 | -18.298 | 342.836 | 536.461 | 0.5526 |
| gbt_net | SPXW | argmax_before_threshold | 32/32 | 4490 | 33.822 | 181.991 | -148.169 | 383.382 | 645.577 | 0.6631 |
| gbt_net | SPXW | executed_trades | 28/32 | 105 | 90.358 | 128.937 | -38.578 | 428.426 | 613.221 | 0.6401 |
| gbt_net_episode | SPXW | all_actions | 32/32 | 180670 | -7.241 | 7.533 | -14.774 | 343.189 | 536.144 | 0.5579 |
| gbt_net_episode | SPXW | argmax_before_threshold | 32/32 | 4490 | 38.525 | 153.985 | -115.460 | 356.464 | 583.424 | 0.6555 |
| gbt_net_episode | SPXW | executed_trades | 28/32 | 104 | 94.117 | 199.352 | -105.235 | 522.603 | 777.465 | 0.5497 |
| gbt_net | SPY | all_actions | 32/32 | 171268 | -6.164 | -5.371 | -0.794 | 34.387 | 58.824 | 0.6437 |
| gbt_net | SPY | argmax_before_threshold | 32/32 | 4744 | 0.985 | 13.571 | -12.586 | 35.604 | 79.809 | 0.7854 |
| gbt_net | SPY | executed_trades | 14/32 | 33 | 22.919 | 94.138 | -71.219 | 116.534 | 212.820 | 0.8497 |
| gbt_net_episode | SPY | all_actions | 32/32 | 171268 | -6.183 | -5.371 | -0.812 | 34.288 | 58.560 | 0.6535 |
| gbt_net_episode | SPY | argmax_before_threshold | 32/32 | 4744 | 0.679 | 14.260 | -13.581 | 33.613 | 76.952 | 0.8046 |
| gbt_net_episode | SPY | executed_trades | 15/32 | 34 | 19.324 | 70.746 | -51.422 | 94.616 | 188.394 | 0.8988 |

## validation

| Modelo | Ticker | Cohorte | Días con unidades/esperados | Unidades | Score medio USD | Neto medio USD | Error USD | MAE | RMSE | Correlación |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gbt_net | QQQ | all_actions | 247/247 | 1548580 | -6.558 | -11.690 | 5.132 | 56.021 | 93.996 | -0.0222 |
| gbt_net | QQQ | argmax_before_threshold | 247/247 | 38871 | 1.556 | -11.599 | 13.155 | 50.210 | 77.776 | -0.0691 |
| gbt_net | QQQ | executed_trades | 199/247 | 711 | 11.711 | -2.469 | 14.180 | 79.970 | 115.116 | 0.0207 |
| gbt_net_episode | QQQ | all_actions | 247/247 | 1548580 | -6.721 | -11.690 | 4.969 | 55.961 | 94.005 | -0.0190 |
| gbt_net_episode | QQQ | argmax_before_threshold | 247/247 | 38871 | 1.221 | -11.554 | 12.775 | 50.100 | 78.065 | -0.0677 |
| gbt_net_episode | QQQ | executed_trades | 187/247 | 645 | 13.308 | -4.545 | 17.853 | 87.128 | 125.320 | -0.0058 |
| gbt_net | SPXW | all_actions | 247/247 | 1581790 | -16.197 | -53.079 | 36.882 | 488.780 | 846.949 | 0.0086 |
| gbt_net | SPXW | argmax_before_threshold | 247/247 | 38522 | 33.072 | -55.218 | 88.290 | 425.743 | 679.837 | -0.0702 |
| gbt_net | SPXW | executed_trades | 235/247 | 1137 | 67.339 | -18.538 | 85.876 | 541.907 | 825.923 | -0.0264 |
| gbt_net_episode | SPXW | all_actions | 247/247 | 1581790 | -16.319 | -53.079 | 36.760 | 488.080 | 845.447 | 0.0177 |
| gbt_net_episode | SPXW | argmax_before_threshold | 247/247 | 38522 | 33.237 | -56.111 | 89.349 | 430.623 | 722.723 | -0.0698 |
| gbt_net_episode | SPXW | executed_trades | 231/247 | 1183 | 71.089 | -51.578 | 122.668 | 561.879 | 862.373 | -0.1134 |
| gbt_net | SPY | all_actions | 247/247 | 1442783 | -7.110 | -10.770 | 3.660 | 48.420 | 85.699 | -0.0084 |
| gbt_net | SPY | argmax_before_threshold | 247/247 | 36817 | -2.265 | -9.913 | 7.648 | 38.859 | 68.554 | -0.0545 |
| gbt_net | SPY | executed_trades | 174/247 | 607 | 7.123 | -5.157 | 12.280 | 68.842 | 102.958 | -0.0323 |
| gbt_net_episode | SPY | all_actions | 247/247 | 1442783 | -7.086 | -10.770 | 3.684 | 48.516 | 85.893 | -0.0261 |
| gbt_net_episode | SPY | argmax_before_threshold | 247/247 | 36817 | -2.356 | -10.033 | 7.677 | 36.865 | 60.494 | -0.0992 |
| gbt_net_episode | SPY | executed_trades | 169/247 | 570 | 7.467 | -5.521 | 12.988 | 68.614 | 102.168 | -0.0126 |

## Contrastes fijados

Diferencia entre medias diarias usando sólo días con ambas cohortes definidas. No confundir el aumento de error condicionado al máximo con una causa demostrada o con una reparación seleccionada.

| Periodo | Modelo | Ticker | Contraste | Días comunes | Δscore USD | Δneto USD | Δerror USD |
|---|---|---|---|---:|---:|---:|---:|
| train | gbt_net | QQQ | argmax_before_threshold_MINUS_all_actions | 32 | 4.380 | 9.653 | -5.273 |
| train | gbt_net | QQQ | executed_trades_MINUS_argmax_before_threshold | 18 | 10.852 | 75.023 | -64.171 |
| train | gbt_net_episode | QQQ | argmax_before_threshold_MINUS_all_actions | 32 | 4.153 | 8.587 | -4.433 |
| train | gbt_net_episode | QQQ | executed_trades_MINUS_argmax_before_threshold | 17 | 10.279 | 35.522 | -25.243 |
| train | gbt_net | SPXW | argmax_before_threshold_MINUS_all_actions | 32 | 44.587 | 174.458 | -129.871 |
| train | gbt_net | SPXW | executed_trades_MINUS_argmax_before_threshold | 28 | 43.494 | -76.074 | 119.568 |
| train | gbt_net_episode | SPXW | argmax_before_threshold_MINUS_all_actions | 32 | 45.766 | 146.452 | -100.685 |
| train | gbt_net_episode | SPXW | executed_trades_MINUS_argmax_before_threshold | 28 | 42.572 | 23.519 | 19.053 |
| train | gbt_net | SPY | argmax_before_threshold_MINUS_all_actions | 32 | 7.149 | 18.942 | -11.792 |
| train | gbt_net | SPY | executed_trades_MINUS_argmax_before_threshold | 14 | 11.005 | 56.539 | -45.534 |
| train | gbt_net_episode | SPY | argmax_before_threshold_MINUS_all_actions | 32 | 6.862 | 19.631 | -12.769 |
| train | gbt_net_episode | SPY | executed_trades_MINUS_argmax_before_threshold | 15 | 8.931 | 35.399 | -26.468 |
| validation | gbt_net | QQQ | argmax_before_threshold_MINUS_all_actions | 247 | 8.115 | 0.092 | 8.023 |
| validation | gbt_net | QQQ | executed_trades_MINUS_argmax_before_threshold | 199 | 7.834 | 9.939 | -2.105 |
| validation | gbt_net_episode | QQQ | argmax_before_threshold_MINUS_all_actions | 247 | 7.942 | 0.136 | 7.806 |
| validation | gbt_net_episode | QQQ | executed_trades_MINUS_argmax_before_threshold | 187 | 8.968 | 8.171 | 0.796 |
| validation | gbt_net | SPXW | argmax_before_threshold_MINUS_all_actions | 247 | 49.268 | -2.139 | 51.408 |
| validation | gbt_net | SPXW | executed_trades_MINUS_argmax_before_threshold | 235 | 29.705 | 38.241 | -8.536 |
| validation | gbt_net_episode | SPXW | argmax_before_threshold_MINUS_all_actions | 247 | 49.556 | -3.032 | 52.589 |
| validation | gbt_net_episode | SPXW | executed_trades_MINUS_argmax_before_threshold | 231 | 31.817 | 7.587 | 24.230 |
| validation | gbt_net | SPY | argmax_before_threshold_MINUS_all_actions | 247 | 4.845 | 0.857 | 3.988 |
| validation | gbt_net | SPY | executed_trades_MINUS_argmax_before_threshold | 174 | 7.342 | 5.613 | 1.729 |
| validation | gbt_net_episode | SPY | argmax_before_threshold_MINUS_all_actions | 247 | 4.730 | 0.737 | 3.993 |
| validation | gbt_net_episode | SPY | executed_trades_MINUS_argmax_before_threshold | 169 | 7.541 | 6.005 | 1.537 |

## Integridad y límites

Summary SHA256 `5ec075276e48d493cc5f5133e6fda70edf8e91f6794ac6951b721bdc9820b832`; fuentes verificadas `5027`; duración `52.334s`.

Los CSV conservan conteos FILLED/NO_FILL, días vacíos, momentos diarios y contrastes MAE/error². La correlación se obtiene de momentos ponderados conjuntos, no del promedio de correlaciones diarias. TRAIN comparte exposición al ajuste y no es un holdout. VAL sigue siendo desarrollo visto. Cambios de calibración general, composición, selección del máximo y generalización son explicaciones compatibles; este diseño observacional no separa sus causas ni acredita rentabilidad futura.
