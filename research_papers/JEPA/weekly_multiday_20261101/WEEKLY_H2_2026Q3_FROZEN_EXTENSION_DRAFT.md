# Borrador: extensión weekly H2 julio–septiembre de 2026 con estado congelado

Estado: diseño de implementación únicamente. No autoriza inventario, lectura de
quotes/outcomes, scoring ni replay. La extensión mide la misma estrategia con
estado estadístico congelado; no es un nuevo ajuste ni un periodo nunca visto
por el proyecto.

## Alcance fijo

- Entradas: sesiones oficiales desde `20260701` hasta `20260930`, inclusive.
- Universo, H2, selector, clocks, expiración 1–8 DTE, costes y políticas:
  idénticos a H2 V2.
- El calendario de contexto debe incluir las dos sesiones oficiales posteriores
  a `20260930`; sólo las entradas hasta septiembre pueden producir candidatos.
  No marcar las últimas sesiones `HORIZON_OUTSIDE_CALENDAR` por cortar el índice
  artificialmente el 30 de septiembre.
- Estado congelado: transformer TRAIN, modelo multinomial, prior TRAIN,
  `alpha=0.3` y medias condicionales TRAIN. Prohibidos `fit`, `fit_transform`,
  selección de alpha, recálculo de prior/medias, threshold, lado, ticker,
  horizonte o costes.
- Libro nuevo de 100.000 USD para esta extensión, sin cash, posiciones ni equity
  arrastrados de TRAIN/CAL/H1. Etiqueta de split propuesta:
  `EXTENSION_2026Q3_SEEN_DEVELOPMENT`.

## Admisión metadata disponible y dependencias

El censo metadata-only coordinado encontró:

- El índice existente, SHA `7124d981...b60b4`, y el builder V2 terminan el 30 de
  junio. Sirven como semántica de `SessionClock`, no como membresía Q3.
- `exchange_calendars 4.12`/XNYS está disponible como fuente local de metadata.
  La verificación oficial separada fija cierres el 3 de julio y 7 de septiembre
  de 2026, sin sesiones cortas en julio–septiembre.
- Nombres 1–8 DTE: SPY y QQQ tienen 49 fechas comunes, `20260702..20260917`.
  SPXW tiene 55; añade `0701,0707,0710,0716,0826,0901`.
- Las últimas fechas comunes son 11, 14, 15, 16 y 17 de septiembre con expiry
  18. La última entrada con fuente física H2 completa es el 15, con salida el
  17. Entradas posteriores deben conservar fuentes de salida nominales ausentes
  y su cobertura/lower bound; no se finge Q3 completo.
- Q3 no es holdout limpio: julio ya aparece en resultados diagnósticos hasta el
  15; agosto/septiembre aparecen en recuperación/fuentes y su exposición previa
  no está auditada. Clasificación fija prudente: forward continuation
  `SEEN_DEVELOPMENT` de linaje mixto.

Dependencias pendientes antes de código/runtime:

1. Generar, revisar y sellar un índice Q3+buffer desde metadata XNYS, con as-of,
   versión y SHA nuevos. No reutilizar `7124...` como si contuviera Q3.
2. Publicar el censo filename-only y sus pins, incluidas todas las ausencias y
   aliases/links, antes de cualquier batch de valores.
3. Revisión independiente de que las fechas de entrada quedan acotadas a Q3,
   aunque el calendario incluya el buffer de octubre, y de que el reporte no
   denomina al periodo holdout/OOS limpio.

## Builder de extensión mínimo

Archivo futuro sugerido: `build_weekly_h2_extension_2026q3.py`. Debe importar
`build_weekly_h2_dataset_v2.py` por SHA, envolver funciones congeladas y no
copiar el builder completo.

Interfaz de dos fases:

```text
--build-reviewed-inventory
--execute-reviewed-extension --inventory PATH --inventory-sha256 SHA
```

El wrapper fija dos rangos distintos:

```text
calendar_context_start = 20260701
calendar_context_end   = segunda sesión oficial posterior a 20260930
entry_start            = 20260701
entry_end              = 20260930
```

Primero usa el lector/calendario y planificador V2 pineados sobre el contexto;
después filtra el plan por `entry_date <= 20260930` **antes** de inventariar
fuentes. Las funciones congeladas de clock, selector, features, identidad,
labels, escenarios y costes no cambian. El inventario persiste antes de valores
y liga plan, fuentes nominales, calendario extendido, wrapper y builder V2.

Outputs propuestos en raíz nueva e inmutable:

```text
D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_v2_extension_2026q3_01/
  inventory.json
  inventory_manifest.json
  candidates.jsonl
  coverage.json
  manifest.json
```

`candidates.jsonl` conserva exactamente el schema V2. `coverage.json` conserva
`clock_files` y añade metadata explícita de `entry_range` y
`calendar_context_range`. El manifest usa un schema nuevo, por ejemplo
`weekly_h2_dataset_extension_manifest_v1`, y referencia el schema candidato
V2 sin redefinirlo.

Validaciones obligatorias:

- cero `candidate_id` fuera de Q3 o duplicado;
- H2 posterior a entrada y estrictamente anterior a expiración;
- source/hash/schema antes y después, con gaps nominales preservados;
- igualdad AST o pins de `_decision_candidate`, `_scenario`, `_net`, `_debit`,
  parser V2 y feature order;
- ningún acceso al dataset H1 para elegir serie o contrato;
- calendario, contrato y enmienda rehasheados al cierre.

## Scorer congelado mínimo

Archivo futuro sugerido: `score_weekly_h2_extension_frozen.py`. No debe llamar
`evaluate_weekly_h2_ev_v2.run`, porque esa función ejecuta fitting y calibración.
Puede importar por pin sus validadores puros, selector, replay/metrics adaptados
a un rango explícito y utilidades de escritura. Debe cargar los parámetros
almacenados y aplicar algebraicamente:

1. features V2 en orden fijo;
2. imputación por medianas TRAIN y único missing-indicator almacenado;
3. scaling por `scaler_mean`/`scaler_scale` TRAIN;
4. logits con coeficientes/interceptos congelados y softmax estable;
5. expansión a cinco clases según `classes_present`;
6. `p_cal = 0.7*p_model + 0.3*p_train_prior`;
7. EV base/adverso con `conditional_means.json` congelado;
8. selección EV top1, controles y replay idénticos, con libro Q3 independiente.

El proceso debe fallar si aparece cualquier ruta de fit o si los parámetros no
reconcilian en dimensiones: 18 features, 19 columnas transformadas, cinco
clases completas, alpha exacto 0,3 y shrinkage 20. Una prueba de paridad previa
debe aplicar el scorer congelado a fixtures/predicciones conocidas sin ajustar
nada.

Outputs sugeridos:

```text
D:/GexResearchArtifacts/weekly_multiday_20261101/h2_ev_frozen_extension_2026q3_01/
  candidate_scores_extension.jsonl
  ledgers por política/coste
  summary_extension.json
  manifest.json
```

No mezclar sus ledgers o métricas con H1. Reportar Q3 por separado y, si se
muestra una suma H1+Q3, denominarla composición descriptiva de periodos vistos,
no una única cartera ni validación externa.

## Pins congelados de entrada al scorer

| Miembro | SHA-256 |
| --- | --- |
| builder H2 V2 | `ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945` |
| evaluator H2 V2 | `8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476` |
| contrato H2 | `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5` |
| enmienda clocks V2 | `9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb` |
| modelo | `68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4` |
| transform TRAIN | `db4be1e1863ab825117fac6278023fe0b5036ba1454d44243266a5eeb3f9736b` |
| alpha/grid congelado | `0b587bedbabc1cb405c203f11910e5ed10d7ea025e529a98f4ebf2daa1049ed4` |
| medias condicionales TRAIN | `a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90` |
| manifest evaluación H1 | `54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96` |
| manifest dataset H1 | `bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8` |

El scorer debe comprobar también que `calibration_grid.json` declara
`selected_alpha=0.3`, que `transform.json` declara `fit_scope=TRAIN_ONLY`, que
el orden de features coincide y que los hashes aparecen en el manifest H1.

## Gates y límites

- CPU 0, un hilo, RAM y commit libres >=2 GB.
- Sólo datos locales; sin API, bróker, producción o VPS.
- Inventario persistente antes de valores y binding revisado antes de ejecutar.
- Cero fit, refit, recalibración o selección usando Q3.
- Missing exits conservan escenario 1/lower bound como en H2 V2.
- Resultado `SEEN_DEVELOPMENT_EXTENSION`; promoción y technical readiness false.
- Una ganancia Q3 no elimina la concentración H1 ni acredita robustez; una
  pérdida tampoco autoriza cambiar la política.
