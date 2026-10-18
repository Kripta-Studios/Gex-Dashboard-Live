# Resultado del primer aprendiz causal por niveles

El productor terminó correctamente el 18 de octubre de 2026 a las 17:47:37 UTC. La política elegida exclusivamente por validación fue `gbt_advantage__10`; en enero–junio de 2026 realizó **cero operaciones**, con neto cero en SPXW, SPY y QQQ. El gate económico falla. No hay rentabilidad acreditada ni promoción.

El score de validación ganador fue +0,06 frente a CASH=0: procedía de sólo dos operaciones SPXW, +40,80 USD base (+36,80 adverso), y ninguna en SPY/QQQ. La muestra es insuficiente para inferir un edge. El target DP es privilegiado y susceptible al sesgo Emax; su predicción causal no hereda la capacidad del oráculo.

El resto de políticas se presenta como diagnóstico predeclarado; ninguna sustituye a la selección congelada por resultados test. El TCN con umbral5 ganó +2.487,80 USD base en SPXW pero sólo hizo17 operaciones, ninguna SPY y dos QQQ; no cumple el gate conjunto. Todo el histórico es SEEN_DEVELOPMENT.

**Auditoría económica independiente: PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT.** Reconstruye las nueve políticas en validación/test, reproduce 54 outputs y la selección congelada. Su alcance es ejecución económica dadas las predicciones; no vuelve a ajustar modelos ni demuestra rentabilidad. Autoridad: [audit.json](D:/GexResearchArtifacts/level_oracle_20261018/learners_v1_economic_audit/audit.json), SHA256 `238e6f0974025edf076d4023f134878340141271547e45e618026042539945bd`. El gate seleccionado sigue false y los cero trades no aportan una estimación informativa de rentabilidad.

## Diseño y recursos

Train2023–2024, validación2025, testenero–junio2026. Exactamente dos GBT de200 árboles y un TCN/CNN de4 épocas; muestra270.377 filas, matriz270.377×1.954. Semilla fija20261018, CASH explícito, umbrales0/5/10 USD y ranking por escalas de prima train SPXW680/SPY81/QQQ88 USD. No hubo recuperación ni ajuste adicional durante esta ejecución.

Entradas y salidas por niveles causales, sin hold fijo. Se puede seleccionar un objetivo atravesando niveles intermedios; stop/target conocidos al decidir, entrada diferida1 minuto y salida tras trigger/EOD. Los holds realizados de las políticas diagnósticas abarcan1–324 minutos. El cierre EOD no se confunde con un objetivo alcanzado.

Tiempo total del supervisor: 1962.70s; privado máximo 6,441,771,008 bytes; RSS máximo 7,861,575,680 bytes. Fuente de tiempos: runtime_v2/completion.json. Todas las fuentes de código finales coinciden. El supervisor y el watcher de snapshots terminaron con exit0.

## Todas las políticas, sin rescate por ticker

PF n/d significa ausencia de operaciones/pérdidas suficientes para definirlo, no un resultado infinito. Los importes son USD netos de un contrato, con escenario base y adverso. En hold se muestran mínimo/mediana/máximo. Las tres cifras de salida son TARGET/STOP/EOD.

### Validación2025

| Política | Ticker | Trades | Neto base | Neto adverso | PF base | Hold min/med/max | TARGET/STOP/EOD |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| gbt_net__0 | SPXW | 1137 | -64058.20 | -66325.20 | 0.7962 | 1/16/324 | 271/720/146 |
| gbt_net__0 | SPY | 607 | -6382.20 | -7594.20 | 0.7271 | 1/19/324 | 152/368/87 |
| gbt_net__0 | QQQ | 711 | -7250.60 | -8665.60 | 0.7566 | 1/20/324 | 164/431/116 |
| gbt_net__5 | SPXW | 1063 | -64352.80 | -66471.80 | 0.7883 | 1/17/324 | 239/683/141 |
| gbt_net__5 | SPY | 371 | -5403.60 | -6143.60 | 0.6852 | 1/23/321 | 72/236/63 |
| gbt_net__5 | QQQ | 532 | -7574.20 | -8631.20 | 0.7009 | 1/22/324 | 93/339/100 |
| gbt_net__10 | SPXW | 1014 | -56133.40 | -58155.40 | 0.8098 | 1/17/324 | 224/651/139 |
| gbt_net__10 | SPY | 252 | -4288.20 | -4790.20 | 0.6692 | 1/24/304 | 43/158/51 |
| gbt_net__10 | QQQ | 378 | -6053.80 | -6806.80 | 0.7028 | 1/24.5/324 | 53/242/83 |
| gbt_advantage__0 | SPXW | 2 | 40.80 | 36.80 | 2.6585 | 3/3.5/4 | 2/0/0 |
| gbt_advantage__0 | SPY | 11 | -32.60 | -54.60 | 0.5630 | 1/6/9 | 5/3/3 |
| gbt_advantage__0 | QQQ | 8 | -9.80 | -25.80 | 0.7888 | 3/9/9 | 1/1/6 |
| gbt_advantage__5 | SPXW | 2 | 40.80 | 36.80 | 2.6585 | 3/3.5/4 | 2/0/0 |
| gbt_advantage__5 | SPY | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__5 | QQQ | 1 | -13.60 | -15.60 | 0.0000 | 9/9/9 | 0/0/1 |
| gbt_advantage__10 | SPXW | 2 | 40.80 | 36.80 | 2.6585 | 3/3.5/4 | 2/0/0 |
| gbt_advantage__10 | SPY | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__10 | QQQ | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| tcn_teacher__0 | SPXW | 94 | -6290.40 | -6476.40 | 0.6306 | 1/17/203 | 10/61/23 |
| tcn_teacher__0 | SPY | 5 | -63.00 | -72.00 | 0.3396 | 15/69/206 | 0/3/2 |
| tcn_teacher__0 | QQQ | 3 | 24.20 | 18.20 | 1.1075 | 7/10/18 | 0/2/1 |
| tcn_teacher__5 | SPXW | 48 | -1944.80 | -2039.80 | 0.7327 | 1/16/146 | 9/25/14 |
| tcn_teacher__5 | SPY | 2 | -44.20 | -47.20 | 0.0000 | 15/42/69 | 0/1/1 |
| tcn_teacher__5 | QQQ | 2 | -225.20 | -229.20 | 0.0000 | 7/8.5/10 | 0/2/0 |
| tcn_teacher__10 | SPXW | 21 | 483.40 | 441.40 | 1.1631 | 1/30/146 | 4/13/4 |
| tcn_teacher__10 | SPY | 1 | -5.60 | -6.60 | 0.0000 | 15/15/15 | 0/1/0 |
| tcn_teacher__10 | QQQ | 2 | -225.20 | -229.20 | 0.0000 | 7/8.5/10 | 0/2/0 |

### Test de desarrollo H1 2026

| Política | Ticker | Trades | Neto base | Neto adverso | PF base | Hold min/med/max | TARGET/STOP/EOD |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| gbt_net__0 | SPXW | 627 | -28731.20 | -29982.20 | 0.8329 | 1/13/316 | 130/417/80 |
| gbt_net__0 | SPY | 389 | -5074.40 | -5848.40 | 0.6565 | 1/19/324 | 64/255/70 |
| gbt_net__0 | QQQ | 413 | -643.80 | -1468.80 | 0.9634 | 1/15/324 | 87/251/75 |
| gbt_net__5 | SPXW | 595 | -24379.00 | -25566.00 | 0.8541 | 1/15/322 | 121/395/79 |
| gbt_net__5 | SPY | 234 | -3099.40 | -3566.40 | 0.6904 | 1/22/303 | 33/153/48 |
| gbt_net__5 | QQQ | 311 | 100.40 | -520.60 | 1.0068 | 1/21/324 | 51/190/70 |
| gbt_net__10 | SPXW | 568 | -20729.80 | -21862.80 | 0.8715 | 1/16/322 | 113/374/81 |
| gbt_net__10 | SPY | 169 | -1818.40 | -2155.40 | 0.7583 | 1/23/288 | 25/110/34 |
| gbt_net__10 | QQQ | 242 | 1271.80 | 788.80 | 1.1082 | 1/24.5/324 | 35/146/61 |
| gbt_advantage__0 | SPXW | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__0 | SPY | 4 | -8.40 | -16.40 | 0.7021 | 1/5.5/11 | 0/2/2 |
| gbt_advantage__0 | QQQ | 6 | -63.60 | -75.60 | 0.3470 | 1/3/7 | 3/3/0 |
| gbt_advantage__5 | SPXW | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__5 | SPY | 2 | -22.20 | -26.20 | 0.0177 | 2/5.5/9 | 0/1/1 |
| gbt_advantage__5 | QQQ | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__10 | SPXW | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__10 | SPY | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| gbt_advantage__10 | QQQ | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| tcn_teacher__0 | SPXW | 45 | -1511.00 | -1600.00 | 0.8630 | 1/23/283 | 5/25/15 |
| tcn_teacher__0 | SPY | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| tcn_teacher__0 | QQQ | 3 | 8.20 | 3.20 | 1.7736 | 61/132/231 | 0/1/2 |
| tcn_teacher__5 | SPXW | 17 | 2487.80 | 2454.80 | 1.5469 | 2/20/283 | 1/8/8 |
| tcn_teacher__5 | SPY | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| tcn_teacher__5 | QQQ | 2 | 2.80 | -1.20 | 1.5000 | 4/68/132 | 0/1/1 |
| tcn_teacher__10 | SPXW | 5 | -1732.00 | -1741.00 | 0.3626 | 18/47/283 | 0/0/5 |
| tcn_teacher__10 | SPY | 0 | 0.00 | 0.00 | n/d | n/d/n/d/n/d | 0/0/0 |
| tcn_teacher__10 | QQQ | 2 | 2.80 | -1.20 | 1.5000 | 4/68/132 | 0/1/1 |

## Desglose económico por motivo de salida del test

| Política | Ticker | TARGET neto base/adverso | STOP neto base/adverso | EOD neto base/adverso |
| --- | --- | ---: | ---: | ---: |
| gbt_net__0 | SPXW | 106617.00/106357.00 | -148447.20/-149280.20 | 13099.00/12941.00 |
| gbt_net__0 | SPY | 5491.60/5363.60 | -12651.00/-13160.00 | 2085.00/1948.00 |
| gbt_net__0 | QQQ | 8404.80/8230.80 | -15889.60/-16390.60 | 6841.00/6691.00 |
| gbt_net__5 | SPXW | 103478.40/103236.40 | -144211.00/-145000.00 | 16353.60/16197.60 |
| gbt_net__5 | SPY | 3710.20/3644.20 | -8506.80/-8812.80 | 1697.20/1602.20 |
| gbt_net__5 | QQQ | 6756.40/6654.40 | -13034.00/-13413.00 | 6378.00/6238.00 |
| gbt_net__10 | SPXW | 99955.20/99729.20 | -138924.40/-139671.40 | 18239.40/18079.40 |
| gbt_net__10 | SPY | 3196.00/3146.00 | -6526.00/-6746.00 | 1511.60/1444.60 |
| gbt_net__10 | QQQ | 5504.00/5434.00 | -10295.60/-10586.60 | 6063.40/5941.40 |
| gbt_advantage__0 | SPXW | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| gbt_advantage__0 | SPY | 0.00/0.00 | -28.20/-32.20 | 19.80/15.80 |
| gbt_advantage__0 | QQQ | 15.20/9.20 | -78.80/-84.80 | 0.00/0.00 |
| gbt_advantage__5 | SPXW | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| gbt_advantage__5 | SPY | 0.00/0.00 | -22.60/-24.60 | 0.40/-1.60 |
| gbt_advantage__5 | QQQ | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| gbt_advantage__10 | SPXW | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| gbt_advantage__10 | SPY | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| gbt_advantage__10 | QQQ | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| tcn_teacher__0 | SPXW | 6257.00/6247.00 | -6925.00/-6975.00 | -843.00/-872.00 |
| tcn_teacher__0 | SPY | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| tcn_teacher__0 | QQQ | 0.00/0.00 | -10.60/-11.60 | 18.80/14.80 |
| tcn_teacher__5 | SPXW | 485.40/483.40 | -1911.80/-1927.80 | 3914.20/3899.20 |
| tcn_teacher__5 | SPY | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| tcn_teacher__5 | QQQ | 0.00/0.00 | -5.60/-7.60 | 8.40/6.40 |
| tcn_teacher__10 | SPXW | 0.00/0.00 | 0.00/0.00 | -1732.00/-1741.00 |
| tcn_teacher__10 | SPY | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 |
| tcn_teacher__10 | QQQ | 0.00/0.00 | -5.60/-7.60 | 8.40/6.40 |

## Artefactos e integridad

Root: `D:/GexResearchArtifacts/level_oracle_20261018/learners_v1`. Los ledgers, intentos, calendarios diarios y predicciones de las nueve políticas están en `validation/` y `test/`. Los resúmenes incluyen todos los meses y días esperados, incluso días sin trades.

| Archivo | SHA256 |
| --- | --- |
| summary.json | `e171408b2fd786c68949d1d32adfca6d25a7d38f4342ab2431a8bb32131c09e5` |
| freeze.json | `9b11a08d6b29003389c6a5e9aa2fa3a7561ead153447b1ba285b39a12a1d4f86` |
| validation/summary.json | `c592a6dabc8e24a6bd6e452fbe0537b9e9588302f4408f4a892938a51b23dc51` |
| test/summary.json | `6acca04850730813974c36cafc898a74b25d74ca278365169ff99dcabf459cf6` |
| oracle_sources_final.json | `8b087da2e69fc5da9200faedda89c7c98336e9318a4404c856d4d9239424f1a2` |
| feature_rehash.json | `14cd33e8d0fc344fdf177c150c3661fbec3ff9ba67043463768144adffef5818` |

El guardado/reanudación externo y sus límites están en [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md). Catorce fixtures CPU/dobles pasan; no se ha ejecutado una recuperación CUDA de mercado. Las copias verificadas están en el root hermano `learners_v1_recovery`. Los archivos raw, producción, bróker y servicios permanecen fuera de alcance.
