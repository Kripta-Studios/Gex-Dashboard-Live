# Contrato: extensión weekly H2 parcial julio–septiembre de 2026

Estado: **AUTORIZADO PARA IMPLEMENTACIÓN, FIXTURES Y REVISIÓN; RUNTIME DE
VALORES NO AUTORIZADO**. Este contrato reemplaza como autoridad operativa al
borrador `WEEKLY_H2_2026Q3_FROZEN_EXTENSION_DRAFT.md`, que permanece histórico.

La extensión aplica sin ajuste el estado H2 congelado a un tramo posterior. No
es un nuevo holdout limpio, no permite selección y no modifica H1.

## Calendario y universo cerrados

Universo: `SPY`, `QQQ`, `SPXW`. El calendario de admisión contiene exactamente
55 sesiones por ticker, 165 filas, todas con cierre regular `close_i=390`:

```text
20260701 20260702 20260706 20260707 20260708 20260709 20260710
20260713 20260714 20260715 20260716 20260717 20260720 20260721
20260722 20260723 20260724 20260727 20260728 20260729 20260730
20260731 20260803 20260804 20260805 20260806 20260807 20260810
20260811 20260812 20260813 20260814 20260817 20260818 20260819
20260820 20260821 20260824 20260825 20260826 20260827 20260828
20260831 20260901 20260902 20260903 20260904 20260908 20260909
20260910 20260911 20260914 20260915 20260916 20260917
```

Son los días laborables de `20260701..20260917`, excluidos `20260703` y
`20260907`. No hay sesiones cortas en este intervalo. La verificación de root
usó las páginas oficiales [Cboe U.S. Options Hours & Holidays](https://www.cboe.com/about/hours/us-options)
y [Nasdaq U.S. Trading Calendar](https://nasdaqtrader.com/Trader.aspx?id=Calendar):
ambas señalan cierre el 3 de julio y el 7 de septiembre de 2026; Cboe muestra
`Regular Trading Hours: None` y Nasdaq `Closed`. Estas URLs y el calendario
explícito son metadata de admisión, no evidencia de disponibilidad de quotes.

No se añadirá calendario de octubre ni sesiones posteriores al 17 de septiembre.
H2 se deriva únicamente por posición en esta lista. Por ello:

- la última fecha de entrada admisible con H2 es `20260915`, cuya salida es
  `20260917`;
- `20260916` y `20260917` se preservan para los tres tickers con razón
  `HORIZON_OUTSIDE_CALENDAR` y sin candidatos;
- cada una de las 55 sesiones se conserva para cada ticker aunque falte la
  fuente nominal, una serie o una quote;
- queda prohibido reducir el universo a la intersección de 49 fechas de
  `SPY`/`QQQ`, desplazar fechas o sustituir una sesión ausente.

La membresía debe publicarse primero en JSON y Parquet nuevos, mutuamente
reconciliados y pineados. El índice H1 SHA
`7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`
sirve sólo de referencia semántica de `SessionClock`; termina el 30 de junio y
no acredita membresía Q3.

## Ciencia y clasificación congeladas

Se conservan exactamente el universo, expiraciones locales weekly 1–8 DTE,
selector 10:30, ejecución 10:35, mismo contrato, H2 estricto pre-expiry,
features, cinco escenarios, lower bounds de fuentes/quotes de salida ausentes,
costes y políticas de H2 V2.

Se congelan transformer TRAIN, modelo multinomial, prior TRAIN, medias
condicionales TRAIN y `alpha=0.3`. Quedan prohibidos `fit`, `fit_transform`,
refit, recalibración, selección de alpha, nuevos thresholds y selección por
ticker, lado, periodo, resultado o disponibilidad.

La clasificación fija del único split es
`Q3_PARTIAL_2026_SEEN_DEVELOPMENT`. Julio ya apareció en diagnósticos y el
linaje previo de agosto/septiembre no está demostrado como virgen. Todo reporte
debe denominarlo `forward continuation / SEEN_DEVELOPMENT mixed`, nunca OOS,
holdout limpio o validación externa. El libro de scoring empieza en 100.000 USD
sin carry de TRAIN, CAL o H1.

## Builder mínimo e interfaz exacta

Archivo nuevo: `build_weekly_h2_q3_partial_extension.py`. Importa por pin el
builder V2 congelado y reutiliza sus funciones puras `plan_calendar`,
`inventory_sources` y `build_candidates`. Añade sólo admisión del calendario,
schemas/manifiestos propios y publicación en dos fases. No copia ni modifica
la ciencia congelada.

CLI:

```text
--build-reviewed-inventory
--execute-reviewed-extension --inventory PATH --inventory-sha256 SHA256
```

Raíz futura, nueva y exclusiva:

```text
D:/GexResearchArtifacts/weekly_multiday_20261101/
  h2_dataset_v2_extension_2026q3_partial_01/
    inventory.json
    inventory_manifest.json
    candidates.jsonl
    coverage.json
    manifest.json
```

`candidates.jsonl` conserva sin adiciones ni omisiones el schema, orden de las
18 features, status, scenario, `payoff_is_lower_bound`, debit/net y semántica de
null de H2 V2. Todos los `entry_date` son `<=20260915`; los IDs son únicos.

Schemas nuevos exactos:

- `inventory.json.schema = weekly_h2_q3_partial_inventory_v1`;
- `coverage.json.schema = weekly_h2_q3_partial_coverage_v1`;
- `manifest.json.schema = weekly_h2_q3_partial_dataset_manifest_v1`.

`coverage.json` contiene `scope`, `calendar` con exactamente 165 filas,
`rows` con las 165 combinaciones ticker-fecha y `clock_files`. Las seis filas
de `20260916/20260917` tienen `HORIZON_OUTSIDE_CALENDAR` y `candidate_ids=[]`.
Para toda fila, `candidate_ids` coincide exactamente con el conjunto de IDs de
esa combinación en `candidates.jsonl`; gaps de fuente/serie/quote no se borran.

`manifest.json` usa esta interfaz cerrada:

```text
schema
status = COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED
split = Q3_PARTIAL_2026_SEEN_DEVELOPMENT
scope
files
flags
implementation_pins
source_inventory
calendar_pin
created_utc
```

`files` es un objeto cuyas claves obligatorias son `candidates.jsonl`,
`coverage.json`, `inventory.json` e `inventory_manifest.json`; cada valor tiene
exactamente `bytes` y `sha256`. `flags` contiene, todos booleanos:
`no_fit=true`, `no_refit=true`, `no_recalibration=true`, `no_selection=true`,
`not_oos=true`, `not_promotion=true`, `not_technical_readiness=true`.
`source_inventory` contiene `path`, `bytes` y `sha256` del inventario admitido.
`calendar_pin` contiene pins JSON/Parquet y confirma `session_count=55`,
`ticker_count=3`, `row_count=165`, `first_date=20260701`,
`last_date=20260917`, `last_eligible_entry=20260915`.

`implementation_pins` contiene rutas y SHA-256 exactos para:

1. wrapper de extensión;
2. builder H2 V2;
3. helper source pilot;
4. contrato H2;
5. enmienda de clocks V2;
6. este contrato;
7. calendario JSON y Parquet;
8. modelo, transform, medias, grid y manifest de evaluación H1 congelados.

Inventario y plan se persisten antes del primer valor. La ejecución revalida
inventario, plan, calendario y todos los pins antes de valores y al cierre;
protege aliases, links/reparse points, overwrite y fuentes aparecidas,
desaparecidas o modificadas. Faltantes nominales permanecen explícitos.

## Pins congelados

| Miembro | SHA-256 |
| --- | --- |
| builder H2 V2 | `ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945` |
| source pilot helper | `ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878` |
| evaluator H2 V2 | `8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476` |
| contrato H2 | `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5` |
| enmienda clocks V2 | `9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb` |
| modelo | `68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4` |
| transform TRAIN | `db4be1e1863ab825117fac6278023fe0b5036ba1454d44243266a5eeb3f9736b` |
| medias condicionales TRAIN | `a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90` |
| grid/alpha congelado | `0b587bedbabc1cb405c203f11910e5ed10d7ea025e529a98f4ebf2daa1049ed4` |
| manifest evaluación H1 | `54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96` |
| manifest dataset H1 | `bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8` |
| calendario Q3 JSON | `ac9bd2569d91e9bd9b0475d6f5e2d5400b2816cc1d1d0d9ec98c69e4dbe2e72b` |
| calendario Q3 Parquet | `e16ef041efadc0f6914585540e19e9c04fcb05f1597952137e4f5bcf06de8c78` |
| manifest calendario Q3 | `5a530747f2c97704869d87c04d09bba3cc00125f38a8a78454c2d459a2ea502c` |

El pin del wrapper se fija después de publicar sus bytes y antes de cualquier
runtime. Los dos artefactos de calendario y su manifest ya están fijados arriba.

## Scorer y outputs posteriores

El scorer separado consume sólo el dataset admitido y el estado congelado. No
llama al `run` del evaluator V2 porque ese camino ajusta/calibra. Valida los pins
anteriores, `selected_alpha=0.3`, `fit_scope=TRAIN_ONLY`, orden y dimensiones de
features, y aplica algebraicamente transform, logits, softmax, prior y EV.

Produce un único split `Q3_PARTIAL_2026_SEEN_DEVELOPMENT` y ocho ledgers:
cuatro políticas por coste base/adverso, con libro independiente de 100.000 USD.
No mezcla ledgers H1/Q3 ni usa Q3 para modificar parámetros.

## Gates y autorización pendiente

- CPU 0, un hilo, RAM libre y commit libre >=2 GB.
- Sólo datos locales; sin API, producción, bróker o VPS.
- Fixtures sintéticos únicamente hasta que existan calendario pineado, wrapper,
  tests, revisión independiente, publicación y binding real revisado.
- Este contrato **no autoriza** inventario real, batches de valores, construcción
  real, scoring ni replay.
- `technical_ready=false`, `promotion_approved=false`; cualquier resultado Q3
  permanece descriptivo `SEEN_DEVELOPMENT` y no borra la concentración H1.
