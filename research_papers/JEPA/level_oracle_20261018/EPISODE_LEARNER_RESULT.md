# GBT con episodios causales: resultado de desarrollo

Estado de selección: `FAIL_NO_DAILY_COMPLIANT_POLICY`. Política seleccionada: `ninguna`. Diagnóstico congelado: `gbt_net__10`.
Gate combinado: **False**; promoción: false.

Auditoría independiente: **PASS_INDEPENDENT_EPISODE_LEARNER_ECONOMIC_AUDIT**.
Artefacto: `D:/GexResearchArtifacts/level_oracle_20261018/episode_learners_v1_economic_audit/audit.json`,
SHA256 `260d08506210e8ff40cd6b3e1dec123c4efba9a943e2dd5bbe81fd8e67190d4a`.
Reconstruyó la matriz270377×2024, las seis políticas en validación/test, los agregados,
selección nula y gatefalse; verificó reparación de rutas/runtime/cero refits.
Es PASS de reconstrucción e integridad, no de rentabilidad.

Una variante, un fit de 200 árboles, muestra original de 270.377 acciones. Las primeras 1.954 columnas son bit a bit idénticas al control; se añaden 35 valores de episodios y 35 máscaras. El control reutiliza modelo y scores verificados, sin refit. Train 2023–2024; selección 2025; contraste enero–junio 2026 ya visto. Es investigación post-resultados, sin outer intacto.

El modelo elige cuándo entrar dentro del universo causal de zonas. No se fuerza una entrada: cada día disponible sin ejecución incumple el requisito. Las fuentes ausentes permanecen NO_EVALUABLE y fallan cobertura por separado. Las salidas siguen target/stop por niveles o EOD, sin hold fijo.

El gate diario se calcula sobre el universo congelado de sesiones completas. El requisito universal de operar cada día bursátil queda NO_ACREDITADO: las medias sesiones están fuera de ese universo y existen seis ticker-días test sin fuente. Esta limitación no cambia retrospectivamente la selección 2025 ni los resultados del experimento.

Alcance calendario: se excluyen dos medias sesiones en 2023, tres en 2024 y tres en 2025: 24 ticker-días en total. Validación contiene 741 ticker-días frente a los 750 del calendario NYSE completo. H1 2026 no tiene medias sesiones: 369 ticker-días esperados, 363 disponibles y seis NO_EVALUABLE. La existencia de candidatos raw para medias sesiones no los incorpora retroactivamente a este experimento.

El primer runtime terminó tras el fit por cuatro joins erróneos de rutas de metadatos, antes de publicar nuevas predicciones o abrir labels de validación. Un wrapper separado y revisado corrigió sólo esas rutas. El código original, fallo y modelo permanecen preservados; continuación con constructor de fit prohibido y cero refits verificados.

## validation

| Política | Días disponibles sin fill | No evaluables | Viable |
|---|---:|---:|---|
| gbt_net__0 | 133 | 0 | False |
| gbt_net__5 | 222 | 0 | False |
| gbt_net__10 | 289 | 0 | False |
| gbt_net_episode__0 | 154 | 0 | False |
| gbt_net_episode__5 | 230 | 0 | False |
| gbt_net_episode__10 | 293 | 0 | False |

| Política | Ticker | Trades | Días sin fill / disponibles | No evaluables | Neto base USD | Neto adverso USD | PF base | Meses positivos | Hold min/med/max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| gbt_net__0 | SPXW | 1137 | 12/247 | 0 | -64058.20 | -66325.20 | 0.796 | 2/12 | 1.0/16.0/324.0 |
| gbt_net__0 | SPY | 607 | 73/247 | 0 | -6382.20 | -7594.20 | 0.727 | 3/12 | 1.0/19.0/324.0 |
| gbt_net__0 | QQQ | 711 | 48/247 | 0 | -7250.60 | -8665.60 | 0.757 | 2/12 | 1.0/20.0/324.0 |
| gbt_net__5 | SPXW | 1063 | 16/247 | 0 | -64352.80 | -66471.80 | 0.788 | 4/12 | 1.0/17.0/324.0 |
| gbt_net__5 | SPY | 371 | 122/247 | 0 | -5403.60 | -6143.60 | 0.685 | 2/12 | 1.0/23.0/321.0 |
| gbt_net__5 | QQQ | 532 | 84/247 | 0 | -7574.20 | -8631.20 | 0.701 | 3/12 | 1.0/22.0/324.0 |
| gbt_net__10 | SPXW | 1014 | 20/247 | 0 | -56133.40 | -58155.40 | 0.810 | 5/12 | 1.0/17.0/324.0 |
| gbt_net__10 | SPY | 252 | 155/247 | 0 | -4288.20 | -4790.20 | 0.669 | 2/12 | 1.0/24.0/304.0 |
| gbt_net__10 | QQQ | 378 | 114/247 | 0 | -6053.80 | -6806.80 | 0.703 | 4/12 | 1.0/24.5/324.0 |
| gbt_net_episode__0 | SPXW | 1183 | 16/247 | 0 | -98345.80 | -100710.80 | 0.705 | 3/12 | 1.0/15.0/324.0 |
| gbt_net_episode__0 | SPY | 570 | 78/247 | 0 | -8109.00 | -9247.00 | 0.653 | 4/12 | 1.0/19.0/324.0 |
| gbt_net_episode__0 | QQQ | 645 | 60/247 | 0 | -7110.00 | -8396.00 | 0.763 | 5/12 | 1.0/22.0/324.0 |
| gbt_net_episode__5 | SPXW | 1134 | 17/247 | 0 | -106670.40 | -108937.40 | 0.674 | 3/12 | 1.0/15.0/324.0 |
| gbt_net_episode__5 | SPY | 357 | 122/247 | 0 | -5288.20 | -6000.20 | 0.696 | 4/12 | 1.0/24.0/324.0 |
| gbt_net_episode__5 | QQQ | 476 | 91/247 | 0 | -6106.60 | -7054.60 | 0.753 | 4/12 | 1.0/25.0/324.0 |
| gbt_net_episode__10 | SPXW | 1063 | 19/247 | 0 | -106258.80 | -108383.80 | 0.665 | 3/12 | 1.0/16.0/324.0 |
| gbt_net_episode__10 | SPY | 240 | 155/247 | 0 | -6620.00 | -7098.00 | 0.530 | 2/12 | 1.0/27.5/321.0 |
| gbt_net_episode__10 | QQQ | 355 | 119/247 | 0 | -5966.00 | -6673.00 | 0.700 | 3/12 | 1.0/29.0/323.0 |

| Política | Ticker | Salida | Trades | Neto base USD | Neto adverso USD |
|---|---|---|---:|---:|---:|
| gbt_net__0 | SPXW | TARGET | 271 | 184278.40 | 183736.40 |
| gbt_net__0 | SPXW | STOP | 720 | -271011.00 | -272450.00 |
| gbt_net__0 | SPXW | EOD | 146 | 22674.40 | 22388.40 |
| gbt_net__0 | SPY | TARGET | 152 | 11249.80 | 10945.80 |
| gbt_net__0 | SPY | STOP | 368 | -19927.80 | -20663.80 |
| gbt_net__0 | SPY | EOD | 87 | 2295.80 | 2123.80 |
| gbt_net__0 | QQQ | TARGET | 164 | 13255.60 | 12927.60 |
| gbt_net__0 | QQQ | STOP | 431 | -25180.60 | -26040.60 |
| gbt_net__0 | QQQ | EOD | 116 | 4674.40 | 4447.40 |
| gbt_net__5 | SPXW | TARGET | 239 | 170785.60 | 170307.60 |
| gbt_net__5 | SPXW | STOP | 683 | -261950.80 | -263315.80 |
| gbt_net__5 | SPXW | EOD | 141 | 26812.40 | 26536.40 |
| gbt_net__5 | SPY | TARGET | 72 | 7580.80 | 7436.80 |
| gbt_net__5 | SPY | STOP | 236 | -15288.60 | -15760.60 |
| gbt_net__5 | SPY | EOD | 63 | 2304.20 | 2180.20 |
| gbt_net__5 | QQQ | TARGET | 93 | 8288.20 | 8102.20 |
| gbt_net__5 | QQQ | STOP | 339 | -21639.40 | -22315.40 |
| gbt_net__5 | QQQ | EOD | 100 | 5777.00 | 5582.00 |
| gbt_net__10 | SPXW | TARGET | 224 | 169269.60 | 168821.60 |
| gbt_net__10 | SPXW | STOP | 651 | -254714.60 | -256016.60 |
| gbt_net__10 | SPXW | EOD | 139 | 29311.60 | 29039.60 |
| gbt_net__10 | SPY | TARGET | 43 | 4848.20 | 4762.20 |
| gbt_net__10 | SPY | STOP | 158 | -11493.80 | -11809.80 |
| gbt_net__10 | SPY | EOD | 51 | 2357.40 | 2257.40 |
| gbt_net__10 | QQQ | TARGET | 53 | 5436.20 | 5330.20 |
| gbt_net__10 | QQQ | STOP | 242 | -16823.20 | -17306.20 |
| gbt_net__10 | QQQ | EOD | 83 | 5333.20 | 5169.20 |
| gbt_net_episode__0 | SPXW | TARGET | 304 | 166031.60 | 165423.60 |
| gbt_net_episode__0 | SPXW | STOP | 741 | -285703.60 | -287185.60 |
| gbt_net_episode__0 | SPXW | EOD | 138 | 21326.20 | 21051.20 |
| gbt_net_episode__0 | SPY | TARGET | 132 | 10497.80 | 10233.80 |
| gbt_net_episode__0 | SPY | STOP | 357 | -20528.20 | -21242.20 |
| gbt_net_episode__0 | SPY | EOD | 81 | 1921.40 | 1761.40 |
| gbt_net_episode__0 | QQQ | TARGET | 121 | 13957.40 | 13715.40 |
| gbt_net_episode__0 | QQQ | STOP | 413 | -25419.80 | -26244.80 |
| gbt_net_episode__0 | QQQ | EOD | 111 | 4352.40 | 4133.40 |
| gbt_net_episode__5 | SPXW | TARGET | 280 | 155847.00 | 155287.00 |
| gbt_net_episode__5 | SPXW | STOP | 713 | -276964.80 | -278390.80 |
| gbt_net_episode__5 | SPXW | EOD | 141 | 14447.40 | 14166.40 |
| gbt_net_episode__5 | SPY | TARGET | 71 | 7679.40 | 7537.40 |
| gbt_net_episode__5 | SPY | STOP | 220 | -15373.00 | -15813.00 |
| gbt_net_episode__5 | SPY | EOD | 66 | 2405.40 | 2275.40 |
| gbt_net_episode__5 | QQQ | TARGET | 80 | 10597.00 | 10437.00 |
| gbt_net_episode__5 | QQQ | STOP | 299 | -20273.40 | -20870.40 |
| gbt_net_episode__5 | QQQ | EOD | 97 | 3569.80 | 3378.80 |
| gbt_net_episode__10 | SPXW | TARGET | 258 | 146683.20 | 146167.20 |
| gbt_net_episode__10 | SPXW | STOP | 664 | -267944.40 | -269272.40 |
| gbt_net_episode__10 | SPXW | EOD | 141 | 15002.40 | 14721.40 |
| gbt_net_episode__10 | SPY | TARGET | 33 | 4032.20 | 3966.20 |
| gbt_net_episode__10 | SPY | STOP | 159 | -12402.40 | -12720.40 |
| gbt_net_episode__10 | SPY | EOD | 48 | 1750.20 | 1656.20 |
| gbt_net_episode__10 | QQQ | TARGET | 49 | 7766.60 | 7668.60 |
| gbt_net_episode__10 | QQQ | STOP | 229 | -15923.40 | -16380.40 |
| gbt_net_episode__10 | QQQ | EOD | 77 | 2190.80 | 2038.80 |

## test

| Política | Días disponibles sin fill | No evaluables | Viable |
|---|---:|---:|---|
| gbt_net__0 | 36 | 6 | False |
| gbt_net__5 | 75 | 6 | False |
| gbt_net__10 | 109 | 6 | False |
| gbt_net_episode__0 | 39 | 6 | False |
| gbt_net_episode__5 | 83 | 6 | False |
| gbt_net_episode__10 | 111 | 6 | False |

| Política | Ticker | Trades | Días sin fill / disponibles | No evaluables | Neto base USD | Neto adverso USD | PF base | Meses positivos | Hold min/med/max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| gbt_net__0 | SPXW | 627 | 5/123 | 0 | -28731.20 | -29982.20 | 0.833 | 2/6 | 1.0/13.0/316.0 |
| gbt_net__0 | SPY | 389 | 19/120 | 3 | -5074.40 | -5848.40 | 0.657 | 0/6 | 1.0/19.0/324.0 |
| gbt_net__0 | QQQ | 413 | 12/120 | 3 | -643.80 | -1468.80 | 0.963 | 2/6 | 1.0/15.0/324.0 |
| gbt_net__5 | SPXW | 595 | 5/123 | 0 | -24379.00 | -25566.00 | 0.854 | 2/6 | 1.0/15.0/322.0 |
| gbt_net__5 | SPY | 234 | 47/120 | 3 | -3099.40 | -3566.40 | 0.690 | 2/6 | 1.0/22.0/303.0 |
| gbt_net__5 | QQQ | 311 | 23/120 | 3 | 100.40 | -520.60 | 1.007 | 3/6 | 1.0/21.0/324.0 |
| gbt_net__10 | SPXW | 568 | 6/123 | 0 | -20729.80 | -21862.80 | 0.872 | 2/6 | 1.0/16.0/322.0 |
| gbt_net__10 | SPY | 169 | 63/120 | 3 | -1818.40 | -2155.40 | 0.758 | 2/6 | 1.0/23.0/288.0 |
| gbt_net__10 | QQQ | 242 | 40/120 | 3 | 1271.80 | 788.80 | 1.108 | 4/6 | 1.0/24.5/324.0 |
| gbt_net_episode__0 | SPXW | 645 | 5/123 | 0 | -29883.00 | -31169.00 | 0.834 | 2/6 | 1.0/14.0/324.0 |
| gbt_net_episode__0 | SPY | 360 | 25/120 | 3 | -5268.00 | -5988.00 | 0.626 | 1/6 | 1.0/20.0/324.0 |
| gbt_net_episode__0 | QQQ | 393 | 9/120 | 3 | -1172.80 | -1956.80 | 0.932 | 3/6 | 1.0/19.0/324.0 |
| gbt_net_episode__5 | SPXW | 600 | 5/123 | 0 | -24581.00 | -25777.00 | 0.857 | 2/6 | 1.0/15.0/324.0 |
| gbt_net_episode__5 | SPY | 207 | 51/120 | 3 | -2150.20 | -2564.20 | 0.773 | 1/6 | 1.0/24.0/324.0 |
| gbt_net_episode__5 | QQQ | 288 | 27/120 | 3 | 283.20 | -291.80 | 1.020 | 3/6 | 1.0/25.5/324.0 |
| gbt_net_episode__10 | SPXW | 584 | 7/123 | 0 | -29193.40 | -30358.40 | 0.827 | 2/6 | 1.0/15.0/324.0 |
| gbt_net_episode__10 | SPY | 144 | 64/120 | 3 | -292.40 | -580.40 | 0.958 | 4/6 | 1.0/32.5/324.0 |
| gbt_net_episode__10 | QQQ | 237 | 40/120 | 3 | 1920.80 | 1447.80 | 1.168 | 4/6 | 1.0/26.0/324.0 |

| Política | Ticker | Salida | Trades | Neto base USD | Neto adverso USD |
|---|---|---|---:|---:|---:|
| gbt_net__0 | SPXW | TARGET | 130 | 106617.00 | 106357.00 |
| gbt_net__0 | SPXW | STOP | 417 | -148447.20 | -149280.20 |
| gbt_net__0 | SPXW | EOD | 80 | 13099.00 | 12941.00 |
| gbt_net__0 | SPY | TARGET | 64 | 5491.60 | 5363.60 |
| gbt_net__0 | SPY | STOP | 255 | -12651.00 | -13160.00 |
| gbt_net__0 | SPY | EOD | 70 | 2085.00 | 1948.00 |
| gbt_net__0 | QQQ | TARGET | 87 | 8404.80 | 8230.80 |
| gbt_net__0 | QQQ | STOP | 251 | -15889.60 | -16390.60 |
| gbt_net__0 | QQQ | EOD | 75 | 6841.00 | 6691.00 |
| gbt_net__5 | SPXW | TARGET | 121 | 103478.40 | 103236.40 |
| gbt_net__5 | SPXW | STOP | 395 | -144211.00 | -145000.00 |
| gbt_net__5 | SPXW | EOD | 79 | 16353.60 | 16197.60 |
| gbt_net__5 | SPY | TARGET | 33 | 3710.20 | 3644.20 |
| gbt_net__5 | SPY | STOP | 153 | -8506.80 | -8812.80 |
| gbt_net__5 | SPY | EOD | 48 | 1697.20 | 1602.20 |
| gbt_net__5 | QQQ | TARGET | 51 | 6756.40 | 6654.40 |
| gbt_net__5 | QQQ | STOP | 190 | -13034.00 | -13413.00 |
| gbt_net__5 | QQQ | EOD | 70 | 6378.00 | 6238.00 |
| gbt_net__10 | SPXW | TARGET | 113 | 99955.20 | 99729.20 |
| gbt_net__10 | SPXW | STOP | 374 | -138924.40 | -139671.40 |
| gbt_net__10 | SPXW | EOD | 81 | 18239.40 | 18079.40 |
| gbt_net__10 | SPY | TARGET | 25 | 3196.00 | 3146.00 |
| gbt_net__10 | SPY | STOP | 110 | -6526.00 | -6746.00 |
| gbt_net__10 | SPY | EOD | 34 | 1511.60 | 1444.60 |
| gbt_net__10 | QQQ | TARGET | 35 | 5504.00 | 5434.00 |
| gbt_net__10 | QQQ | STOP | 146 | -10295.60 | -10586.60 |
| gbt_net__10 | QQQ | EOD | 61 | 6063.40 | 5941.40 |
| gbt_net_episode__0 | SPXW | TARGET | 139 | 101865.60 | 101587.60 |
| gbt_net_episode__0 | SPXW | STOP | 429 | -162337.40 | -163194.40 |
| gbt_net_episode__0 | SPXW | EOD | 77 | 30588.80 | 30437.80 |
| gbt_net_episode__0 | SPY | TARGET | 59 | 5426.60 | 5308.60 |
| gbt_net_episode__0 | SPY | STOP | 236 | -12306.60 | -12778.60 |
| gbt_net_episode__0 | SPY | EOD | 65 | 1612.00 | 1482.00 |
| gbt_net_episode__0 | QQQ | TARGET | 79 | 8107.60 | 7949.60 |
| gbt_net_episode__0 | QQQ | STOP | 234 | -15442.40 | -15909.40 |
| gbt_net_episode__0 | QQQ | EOD | 80 | 6162.00 | 6003.00 |
| gbt_net_episode__5 | SPXW | TARGET | 126 | 100125.40 | 99873.40 |
| gbt_net_episode__5 | SPXW | STOP | 397 | -155180.20 | -155973.20 |
| gbt_net_episode__5 | SPXW | EOD | 77 | 30473.80 | 30322.80 |
| gbt_net_episode__5 | SPY | TARGET | 30 | 4441.00 | 4381.00 |
| gbt_net_episode__5 | SPY | STOP | 126 | -8001.60 | -8253.60 |
| gbt_net_episode__5 | SPY | EOD | 51 | 1410.40 | 1308.40 |
| gbt_net_episode__5 | QQQ | TARGET | 49 | 7179.60 | 7081.60 |
| gbt_net_episode__5 | QQQ | STOP | 175 | -12557.00 | -12906.00 |
| gbt_net_episode__5 | QQQ | EOD | 64 | 5660.60 | 5532.60 |
| gbt_net_episode__10 | SPXW | TARGET | 115 | 92456.00 | 92226.00 |
| gbt_net_episode__10 | SPXW | STOP | 391 | -152512.60 | -153293.60 |
| gbt_net_episode__10 | SPXW | EOD | 78 | 30863.20 | 30709.20 |
| gbt_net_episode__10 | SPY | TARGET | 22 | 3718.80 | 3674.80 |
| gbt_net_episode__10 | SPY | STOP | 85 | -6046.00 | -6216.00 |
| gbt_net_episode__10 | SPY | EOD | 37 | 2034.80 | 1960.80 |
| gbt_net_episode__10 | QQQ | TARGET | 34 | 5782.60 | 5714.60 |
| gbt_net_episode__10 | QQQ | STOP | 147 | -10050.20 | -10343.20 |
| gbt_net_episode__10 | QQQ | EOD | 56 | 6188.40 | 6076.40 |

## Comparaciones pareadas H1 2026

Diferencias variante menos control; bootstrap de 10.000 muestras de fechas completas. La suma normalizada usa escalas train fijas SPXW680/SPY81/QQQ88 USD. La referencia cero es contabilidad, no una política seleccionable.

| Comparación | Coste | Diferencia normalizada | IC95 normalizado |
|---|---|---:|---|
| same_threshold_0 | base | -10.095 | [-82.146, 63.273] |
| same_threshold_0 | adverse | -9.014 | [-81.543, 64.904] |
| same_threshold_5 | base | 13.499 | [-59.734, 88.166] |
| same_threshold_5 | adverse | 14.663 | [-59.106, 89.781] |
| same_threshold_10 | base | 13.768 | [-60.088, 87.522] |
| same_threshold_10 | adverse | 14.440 | [-59.643, 88.619] |
| best_variant_minus_control | base | -20.994 | [-95.285, 51.658] |
| best_variant_minus_control | adverse | -23.083 | [-97.612, 50.078] |
| best_control_minus_zero | base | -38.482 | [-155.643, 81.751] |
| best_control_minus_zero | adverse | -49.797 | [-167.692, 70.602] |
| best_variant_minus_zero | base | -59.476 | [-182.230, 68.089] |
| best_variant_minus_zero | adverse | -72.880 | [-196.677, 55.061] |
| joint_selected_or_diagnostic_minus_zero | base | -38.482 | [-155.643, 81.751] |
| joint_selected_or_diagnostic_minus_zero | adverse | -49.797 | [-167.692, 70.602] |

## Integridad y alcance

Summary SHA256: `e2380e8dc35f35a845d0cc4c5035ae97137bb3ed280618c32b6fc40cf4f1f9fc`.
Freeze SHA256: `33a7e46f6f76ecbaadf71d2c39de4d78ec6e4f8a17c4f4e8a0904fc38bbc57d5`.
Freeze antes de labels nuevos de test: `True`.

La auditoría económica independiente se informa por su artefacto propio. Estos resultados no prueban recepción histórica observada, paridad live ni rentabilidad futura. El fracaso de esta variante tampoco demuestra que todo uso de niveles carezca de edge: acota esta representación, objetivo, muestra y reglas de ejecución. No hubo cambios de parámetros por resultados, nuevas descargas, órdenes o producción.
