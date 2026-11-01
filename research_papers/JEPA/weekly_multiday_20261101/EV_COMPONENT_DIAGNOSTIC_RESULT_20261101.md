# Diagnóstico EV cerrado: el error global oculta el de las operaciones elegidas

**El reentrenamiento no resolvió la sobreestimación del EV de las operaciones de Q3.** En las cinco políticas, la suma del EV de las entradas ejecutadas en julio–septiembre parcial era positiva y su resultado neto terminó negativo. La descomposición retrospectiva concentra el error firmado principalmente en el componente probabilístico, usando las medias de pago originales. No identifica una causa estadística única ni prueba una corrección operable.

Esta etapa reutiliza las predicciones y decisiones cerradas: no entrena, recalibra, vuelve a inferir ni simula otra política. Reconstrucción independiente de 3.060 filas y 810 grupos: cero discrepancias en los campos comparados. El fallo del criterio de ocho meses completos positivos permanece intacto.

## Lo que se mide

Error = EV estimado − neto del candidato, en USD por un contrato. Un error positivo indica sobreestimación. Los promedios asignan el mismo peso a cada candidato/operación; no equivalen al PnL de cartera, que depende también de las cantidades.

La identidad separa el error entre `probabilidades` y `pago condicional`: el primero compara el EV con el pago histórico medio de la clase que acabó ocurriendo; el segundo compara ese pago medio con el neto final. La clase realizada sólo se utiliza después del cierre para diagnosticar. No se usa para decidir.

Universos: ALL son las 612 oportunidades comunes; SELECTED son intentos elegidos, incluidos rechazos de ejecución/riesgo; FILLED son operaciones ejecutadas y cerradas. NO_FILL del candidato tiene neto0; NO_FILL del ledger puede rechazar un candidato con resultado potencial distinto de0. Ese resultado potencial no se cuenta como pérdida de cartera.

Periodos por fecha de entrada, de enero a15septiembre2026, con salidas hasta17septiembre. H1/Q3 aquí son cohortes de entrada; el criterio mensual económico anterior se atribuye por fecha de salida. No se mezclan ambas convenciones.

## Error medio global y después de seleccionar

### Con todas las cotas conservadoras

| Política | ALL error (n) | SELECTED error (n) | FILLED error (n) |
|---|---:|---:|---:|
| Congelado | 63,79 (612) | 217,29 (153) | 214,86 (124) |
| Mensual inmediato | 9,15 (612) | 169,30 (110) | 141,20 (89) |
| Semanal inmediato | 3,50 (612) | 148,59 (105) | 115,27 (83) |
| Mensual con filtro | -1,22 (612) | 106,21 (122) | 103,20 (100) |
| Semanal con filtro | 4,14 (612) | 205,46 (123) | 210,42 (100) |

### Sin cotas por salida ausente; conserva NO_FILL

| Política | ALL error (n) | SELECTED error (n) | FILLED error (n) |
|---|---:|---:|---:|
| Congelado | 30,44 (578) | 190,90 (145) | 195,49 (120) |
| Mensual inmediato | -25,64 (578) | 155,82 (108) | 123,82 (87) |
| Semanal inmediato | -31,38 (578) | 134,05 (103) | 95,96 (81) |
| Mensual con filtro | -37,00 (578) | 89,37 (119) | 82,44 (97) |
| Semanal con filtro | -31,24 (578) | 190,85 (120) | 197,23 (98) |

El semanal inmediato parece casi insesgado al promediar las612 oportunidades: +3,50 USD/contrato. En sus105 intentos seleccionados el error sube a+148,59; en sus83 operaciones ejecutadas, +115,27. El promedio global incluye compensación entre sobreestimaciones y subestimaciones; su MAE sigue siendo1.079,72 USD/contrato. Un sesgo global pequeño no acredita precisión individual ni EV fiable al seleccionar.

## Deterioro entre H1 y Q3 en operaciones ejecutadas

| Política | Error medio H1 | Error medio Q3 parcial | N H1/Q3 |
|---|---:|---:|---:|
| Congelado | -60,99 | 773,28 | 83/41 |
| Mensual inmediato | -218,81 | 814,77 | 58/31 |
| Semanal inmediato | -200,10 | 890,56 | 59/24 |
| Mensual con filtro | -279,67 | 783,85 | 64/36 |
| Semanal con filtro | -154,49 | 859,17 | 64/36 |

Todos los modelos subestimaron en promedio el neto de sus fills H1 y lo sobreestimaron en Q3. Eso describe estas muestras; no separa por sí solo cambios del mercado, azar, selección o errores estructurales.

| Política | Q3 EV por tamaños USD | Q3 neto ejecutado USD | Cotas incluidas |
|---|---:|---:|---:|
| Congelado | 17.385,97 | -58.128,60 | 2 |
| Mensual inmediato | 9.528,45 | -48.720,60 | 0 |
| Semanal inmediato | 4.818,22 | -33.458,40 | 0 |
| Mensual con filtro | 11.747,29 | -64.224,00 | 1 |
| Semanal con filtro | 16.325,72 | -55.722,80 | 0 |

El EV por tamaños es la suma del EV guardado multiplicado por la cantidad real de cada entrada. Es una comparación con lo que estimaba el modelo, no otro backtest. Los netos son los mismos ledgers ya auditados.

## Descomposición Q3 en fills: USD/contrato

| Política | EV medio | Neto medio | Error | Componente probabilidades | Componente pago | Cambio de EV por calibración |
|---|---:|---:|---:|---:|---:|---:|
| Congelado | 162,99 | -610,28 | 773,28 | 835,81 | -62,53 | -342,71 |
| Mensual inmediato | 146,66 | -668,12 | 814,77 | 870,29 | -55,52 | -215,91 |
| Semanal inmediato | 108,04 | -782,52 | 890,56 | 996,08 | -105,52 | -356,40 |
| Mensual con filtro | 152,59 | -631,27 | 783,85 | 802,86 | -19,00 | -164,71 |
| Semanal con filtro | 200,63 | -658,54 | 859,17 | 828,86 | 30,31 | -191,06 |

En semanal inmediato, +996,08 del componente probabilístico y−105,52 del pago condicional suman el error de+890,56 USD/contrato. En esta muestra, la media de pago por escenario no explica el optimismo dominante: su residual lo compensa parcialmente. Las24 operaciones Q3 de esa política tienen salida observada, sin cotas por datos ausentes.

La calibración ya aplicada baja el EV medio de esas mismas24 entradas en356,40 USD/contrato respecto a sus probabilidades sin mezclar con el prior. Aun así persiste el error. La selección se mantiene fija para esta identidad: no se probó qué habría operado una política sin calibración ni se eligió otro alpha.

### Q3 fills sin cotas conservadoras

| Política | N | Error medio | Probabilidades | Pago condicional | Neto por tamaños USD |
|---|---:|---:|---:|---:|---:|
| Congelado | 39 | 776,61 | 854,76 | -78,15 | -48.694,60 |
| Mensual inmediato | 31 | 814,77 | 870,29 | -55,52 | -48.720,60 |
| Semanal inmediato | 24 | 890,56 | 996,08 | -105,52 | -33.458,40 |
| Mensual con filtro | 35 | 788,85 | 813,30 | -24,45 | -60.061,80 |
| Semanal con filtro | 36 | 859,17 | 828,86 | 30,31 | -55.722,80 |

Los grupos sin cotas también pierden. Esta vista es un diagnóstico de sensibilidad y no sustituye al resultado principal ni permite excluir pérdidas retrospectivamente.

## Particiones predeclaradas de SELECTED

Cada celda muestra error medio USD/contrato y número de candidatos. Son cortes descriptivos de todos los modelos, no reglas para elegir un ticker, lado, clase o mes. Las familias se reconcilian por separado con TOTAL; no se suman familias entre sí. Los componentes y métricas de ALL/FILLED, ambas vistas y cada partición están completos en los810 grupos del archivo adjunto.

### Mes de entrada (septiembre parcial) — Con cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| 202601 | 162,32 (16) | 3,00 (6) | 99,40 (3) | 162,32 (16) | 162,32 (16) |
| 202602 | -101,21 (14) | — (0) | 64,12 (3) | -129,48 (4) | -129,48 (4) |
| 202603 | 5,49 (23) | -96,06 (21) | -34,09 (19) | -311,08 (18) | -311,08 (18) |
| 202604 | -577,72 (21) | -214,58 (19) | -222,54 (19) | -412,73 (17) | -412,73 (17) |
| 202605 | -94,56 (17) | -649,34 (14) | -532,74 (17) | -937,19 (12) | -692,55 (14) |
| 202606 | 711,12 (17) | 497,69 (16) | 420,00 (17) | 378,59 (16) | 876,09 (16) |
| 202607 | 587,76 (15) | 535,92 (15) | 529,59 (13) | 868,76 (17) | 932,55 (16) |
| 202608 | 803,00 (24) | 1.044,41 (17) | 1.147,41 (13) | 666,92 (14) | 742,00 (16) |
| 202609 | 916,88 (6) | 16,59 (2) | 103,17 (1) | 572,10 (8) | 782,25 (6) |

### Escenario realizado — Con cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| 0 | 383,89 (14) | 365,89 (10) | 418,83 (10) | 200,48 (8) | 233,83 (7) |
| 1 | 1.135,70 (65) | 1.145,41 (46) | 1.211,46 (41) | 1.022,99 (56) | 1.153,03 (55) |
| 2 | 383,97 (30) | 308,41 (26) | 282,54 (27) | 283,83 (25) | 296,03 (28) |
| 3 | -97,45 (6) | -150,15 (7) | 19,78 (4) | -233,35 (8) | -136,56 (7) |
| 4 | -1.496,94 (38) | -2.128,22 (21) | -1.998,42 (23) | -2.046,53 (25) | -1.812,11 (26) |

### Estado del candidato — Con cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| NO_FILL | 383,89 (14) | 365,89 (10) | 418,83 (10) | 200,48 (8) | 233,83 (7) |
| OBSERVED_EXIT | 170,27 (131) | 134,38 (98) | 103,43 (93) | 81,36 (111) | 188,19 (113) |
| MISSING_EXIT_QUOTE | 1.019,74 (1) | 1.047,94 (1) | 1.047,94 (1) | 981,29 (1) | 981,29 (1) |
| MISSING_EXIT_SOURCE | 649,44 (7) | 746,54 (1) | 746,54 (1) | 670,65 (2) | 694,18 (2) |

### Ticker y lado — Con cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| SPY:CALL | 84,28 (36) | 148,92 (29) | 107,71 (28) | 165,39 (31) | 184,98 (32) |
| SPY:PUT | -16,09 (16) | 26,45 (7) | 108,80 (8) | -18,04 (11) | -18,55 (11) |
| QQQ:CALL | 90,65 (44) | 134,68 (34) | 36,77 (32) | 90,79 (35) | 84,28 (35) |
| QQQ:PUT | 147,96 (6) | -268,16 (3) | 30,30 (1) | 382,31 (5) | 157,33 (6) |
| SPXW:CALL | 362,99 (48) | 110,42 (32) | 155,58 (31) | 68,96 (38) | 218,10 (36) |
| SPXW:PUT | 2.723,12 (3) | 1.362,23 (5) | 1.137,13 (5) | 159,36 (2) | 2.603,65 (3) |

### Mes de entrada (septiembre parcial) — Sin cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| 202601 | 162,32 (16) | 3,00 (6) | 99,40 (3) | 162,32 (16) | 162,32 (16) |
| 202602 | -101,21 (14) | — (0) | 64,12 (3) | -129,48 (4) | -129,48 (4) |
| 202603 | -40,61 (22) | -153,26 (20) | -94,21 (18) | -387,10 (17) | -387,10 (17) |
| 202604 | -644,01 (20) | -267,97 (18) | -276,38 (18) | -484,29 (16) | -484,29 (16) |
| 202605 | -94,56 (17) | -649,34 (14) | -532,74 (17) | -937,19 (12) | -692,55 (14) |
| 202606 | 713,01 (16) | 497,69 (16) | 420,00 (17) | 378,59 (16) | 890,76 (15) |
| 202607 | 569,23 (13) | 535,92 (15) | 529,59 (13) | 868,76 (17) | 932,55 (16) |
| 202608 | 836,73 (21) | 1.044,41 (17) | 1.147,41 (13) | 671,37 (13) | 742,00 (16) |
| 202609 | 916,88 (6) | 16,59 (2) | 103,17 (1) | 572,10 (8) | 782,25 (6) |

### Escenario realizado — Sin cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| 0 | 383,89 (14) | 365,89 (10) | 418,83 (10) | 200,48 (8) | 233,83 (7) |
| 1 | 1.197,46 (57) | 1.156,69 (44) | 1.227,57 (39) | 1.037,08 (53) | 1.173,98 (52) |
| 2 | 383,97 (30) | 308,41 (26) | 282,54 (27) | 283,83 (25) | 296,03 (28) |
| 3 | -97,45 (6) | -150,15 (7) | 19,78 (4) | -233,35 (8) | -136,56 (7) |
| 4 | -1.496,94 (38) | -2.128,22 (21) | -1.998,42 (23) | -2.046,53 (25) | -1.812,11 (26) |

### Estado del candidato — Sin cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| NO_FILL | 383,89 (14) | 365,89 (10) | 418,83 (10) | 200,48 (8) | 233,83 (7) |
| OBSERVED_EXIT | 170,27 (131) | 134,38 (98) | 103,43 (93) | 81,36 (111) | 188,19 (113) |
| MISSING_EXIT_QUOTE | — (0) | — (0) | — (0) | — (0) | — (0) |
| MISSING_EXIT_SOURCE | — (0) | — (0) | — (0) | — (0) | — (0) |

### Ticker y lado — Sin cotas

| Grupo | Congelado | Mensual | Semanal | Mensual filtro | Semanal filtro |
|---|---:|---:|---:|---:|---:|
| SPY:CALL | 26,77 (32) | 148,92 (29) | 107,71 (28) | 165,39 (31) | 169,78 (31) |
| SPY:PUT | -16,09 (16) | 26,45 (7) | 108,80 (8) | -18,04 (11) | -18,55 (11) |
| QQQ:CALL | 15,01 (40) | 87,02 (32) | -20,59 (30) | 44,37 (33) | 37,46 (33) |
| QQQ:PUT | 147,96 (6) | -268,16 (3) | 30,30 (1) | 325,63 (4) | 157,33 (6) |
| SPXW:CALL | 362,99 (48) | 110,42 (32) | 155,58 (31) | 68,96 (38) | 218,10 (36) |
| SPXW:PUT | 2.723,12 (3) | 1.362,23 (5) | 1.137,13 (5) | 159,36 (2) | 2.603,65 (3) |

Clases:0=no-fill;1=retorno bruto inferior a−25%;2=[−25%,0%);3=[0%,25%);4≥25%. Las salidas ausentes conservan clase1 y neto de cota. Los errores separados por clase realizada usan información posterior; su signo no identifica por sí mismo una descalibración.

## Qué cambia en la investigación

Esta evidencia reduce la prioridad de explicar Q3 sólo mediante medias de pago demasiado altas. La siguiente hipótesis causal debe probar la calibración de probabilidades/EV sobre el subconjunto que realmente selecciona la política y evaluar abstención con información anterior a cada decisión. La evaluación deberá conservar grupos temporales completos y el criterio mensual; no basta con mejorar logloss o sesgo global.

No se ha diseñado para seleccionar con estos resultados un nuevo umbral, intervalo, ticker ni modelo ganador. La siguiente prueba requiere un contrato previo y predicciones fuera de ajuste dentro del histórico de entrenamiento/calibración. Los datos2026 ya vistos no se convertirán en un holdout nuevo por cambiar de algoritmo. No hay todavía un modelo rentable estable acreditado.

## Cierre, límites y evidencia

Productor diagnóstico f83b42fc,22pruebas sintéticas finales PASS/Ruff0. Run único PID11068,exit0retenido1nov2026 19:15:21.541765UTC, desde28d4656c; manifest420d9b42. Inputs19 antes/después exactos;3060componentes/810grupos, residual máximo3,64e-12USD. Coste adverse, sin nuevo fit/replay/inferencia o cambio de selección.

Reconstrucción independiente conforme: checker1b0ebecf,PID46400,exit0retenido19:21:13.6708577UTC; receipt6fd257205e8e2d68ad4621eac399ac7baf646296ba9d65bfce326f595a467d73. Helperoficial3cfe55a6,CPU0/8variables1, RAM7918579712/commit4614787072. Inputs20 incluyendohelper verificados antes/después. Cero discrepancias de identidad/membresía y diferencias numéricas0 en los campos comparados;810agregados reproducidos byte por byte. No refit independiente ni nueva lectura de quotes raw.

Intentos previos preservados: prueba de autor01 inválida por quoting, descrita en EV_COMPONENT_IMPLEMENTATION_REVIEW; checker01 tuvo tres fallos técnicos y un PASS numérico que no acreditaba afinidadCPU0/gateoficial. Checker02 corrige exclusivamente controles operativos y clipping logloss conforme al contrato, con resultados idénticos. No se relanzó el productor ni se corrigieron resultados para hacerlos positivos.

El valor de clase realizada es retrospectivo. El componente probabilístico también depende del mapa de medias elegido; el residual de pago incluye heterogeneidad y variación individual. Las magnitudes absolutas de componentes no son aditivas. En cotas de salida ausente, el error firmado es cota superior del error real; su MAE no tiene esa interpretación. No se calcula significancia ni se acredita causalidad única, nueva rentabilidad o comportamiento futuro.

[810 grupos completos](ev_components_result_archive_01/ev_components_diagnostic_01/aggregates.jsonl) · [3060 filas](ev_components_result_archive_01/ev_components_diagnostic_01/components.jsonl) · [Resultado económico anterior](ADAPTATION_MONTHLY_WEEKLY_RESULT_20261101.md).

Todo SEEN_DEVELOPMENT; selecciónnull, technical_ready=false, promotion_approved=false. El goal general continúa activo.
