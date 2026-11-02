# Enmienda V2 de calendario para weekly zone-event value paths

Estado: `PREDECLARED_V2_CALENDAR_AMENDMENT_NOT_A_RESULT`  
Fecha: 2026-11-02  
Ámbito: corrección operacional metadata-only; no resultado científico ni económico

## 1. Autoridad incorporada y límite de la enmienda

Esta enmienda incorpora íntegramente, sin sustituir ni debilitar,
[`WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md`](WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md),
36466 bytes, SHA-256
`e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9`.
Cuando haya conflicto, esta enmienda prevalece únicamente para:

1. validar el orden real del `unified_calendar.json` ya pineado;
2. crear en memoria una copia canónica en el orden exigido por el consumidor
   spot;
3. usar nombres V2 para builder, tests, schemas de summary/manifest y raíces;
4. enlazar de forma explícita el fallo cerrado del productor 01.

Todo lo demás del contrato original permanece exacto: 25 autoridades
científicas, fuentes option, selector 10:30, trayectorias D/D1/H2, clocks,
schemas de los siete data outputs, orden de sus filas, spot module, límites,
conteos, seguridad de paths, gates, recursos, streaming, flags y closing rehash.
No se cambia ninguna identidad, fecha, `close_i`, fuente, observación, threshold,
selección ni valor. No se añaden zonas, labels, outcomes, PnL, EV, costes, riesgo,
qty, replay, fit, inferencia o promoción.

Esta enmienda debe publicarse y recibir review documental byte-exact antes de
escribir implementación o fixtures V2. Por sí sola no autoriza ejecución.

## 2. Diagnóstico cerrado del productor 01

El productor original usó:

| autoridad previa | bytes | SHA-256 |
|---|---:|---|
| `build_weekly_zone_event_value_paths.py` | 83817 | `b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe` |
| `test_build_weekly_zone_event_value_paths.py` | 28614 | `ea5c7d0b0848e3cc4dc8fc6a9ac0e59505bf9e5244cbd775308a81b682ae72aa` |

El child retenido PID47576 terminó exit1 antes de abrir footer, raw option,
cache NPZ o valores. El journal sólo completó las dos admisiones de autoridades.
La raíz `weekly_zone_event_value_paths_01`, sus stagings nominales y cualquier
manifest/summary de productor quedaron ausentes. No existe parcial adoptable.

Evidencia original exacta bajo
`D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_observer_01`:

| archivo | bytes | SHA-256 |
|---|---:|---|
| `admission.json` | 12335 | `ff19924932128fa260eb1e450d7de364eed347e9973fa1f86b379a95987fe9c9` |
| `exit.json` | 358 | `48b635e9fbdeef729de7c1be0b24948e21655ceb6cf5a154c02809e8a8a951d3` |
| `failure_receipt.json` | 305 | `6ee1cb2ee3a29b74484c5ed54fe5049eb45da6e299c4fcd9ea8553bc809086fc` |
| `implementation_pins.json` | 3203 | `bb20f523d42421c74f5f9347d3cf73e78f7563fd59470985e3837246a043b7c6` |
| `journal.jsonl` | 6473 | `a12c7f5d5e1171e220cc1bcefd9f3191caf6e414f5c5df1cdeb5b4bc8b36aa08` |
| `pre_child_observation.json` | 10754 | `10fefcef7eaaacc38491a1d25e938c9023ab039e981ecc82769b7eea0a3f718c` |
| `process.json` | 1080 | `6d9f377ee2b76570558a193bd96bb03d884cc9f78821207937ab27fd4e9c3232` |
| `resource_observation.json` | 10645 | `7f3966ba60f3130836e9a5975dbb95cf46ca9f7eb4712a2f9379c8c5d9bbe3db` |
| `stderr.log` | 1718 | `7ac8a8d7cd17a1457649e9e94dcda99c20168319a0b38528de3b514eacb421f6` |
| `stdout.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

La copia cerrada de esta evidencia está en
`weekly_zone_event_value_path_failure01_archive_01`:

| archivo | bytes | SHA-256 |
|---|---:|---|
| `receipt.json` | 1490 | `9550a1a1387694f43c3eca179d490a3f18e892440b2eb1e6adf5f1ae9004baed` |
| `manifest.json` | 18000 | `44bc6a77eb46214d296c1cc23418c81b1a10fb87069b5dfef8616f2deaa8082b` |

El receipt declara `PASS_FAILURE_EVIDENCE_ARCHIVED`, 20 entradas, exit1
retenido, cero raw leído y cero raíz runtime. V2 es una ejecución nueva: nunca
resume, reintenta, adopta, renombra ni borra el intento 01. Sus observer y
archivo son inmutables. El archive es evidencia documental; no amplía las 29
autoridades runtime definidas en la sección 5.

## 3. Hecho metadata-only y causa exacta

La autoridad original sigue siendo:

```text
path=D:\GexResearchArtifacts\weekly_multiday_20261101\h2_boundary_bridge_01\unified_calendar.json
bytes=232573
sha256=be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6
schema=weekly_h2_boundary_unified_calendar_v1
rows=2790
```

El documento tiene exactamente las claves top-level `schema,rows`. Cada row
tiene exactamente `close_i,date,ticker`. Hay 2790 identidades únicas, 930 por
ticker; ticker pertenece a `QQQ|SPXW|SPY`, `date` es una fecha válida
`YYYYMMDD`, y `close_i` pertenece a `210|390`. Hay 24 rows SHORT (`210`) y
2766 FULL (`390`). Cada ticker contiene el mismo conjunto de 930 fechas.

Su orden físico, también validado, es ticker-major lexicográfico
`QQQ,SPXW,SPY`, y dentro de cada ticker `date` asciende estrictamente. El
contrato original entregaba esas rows directamente a un consumidor que exige
`date` ascendente y ordinal `SPY=0,QQQ=1,SPXW=2`. El fallo fue por incompatibilidad
de orden de metadata, no por valores ni por falta de cobertura.

## 4. Normalización canónica obligatoria

`build_weekly_zone_event_value_paths_v2.py` primero admite y rehashea las mismas
25 autoridades. Para `unified_calendar.json`, antes de construir staging y antes
de cualquier footer/raw/cache, hace en este orden:

1. exige el pin, schema, claves, tipos, dominios y conteos de la sección 3;
2. exige unicidad exacta de `(ticker,date)`, 930 fechas por ticker y conjuntos
   de fechas iguales;
3. exige el orden upstream ticker-major `QQQ,SPXW,SPY`, con fecha ascendente;
4. crea una nueva lista de mappings, sin mutar el documento parseado, ordenada
   por `(date, ticker_ordinal)` con `SPY=0,QQQ=1,SPXW=2`;
5. vuelve a exigir las mismas 2790 identidades y que cada triple
   `(ticker,date,close_i)` sea idéntico uno-a-uno al upstream;
6. entrega sólo esa copia al módulo spot sin cambios.

No se permite aceptar silenciosamente otro orden upstream, ordenar antes de
validar, deduplicar, rellenar, cambiar `close_i`, excluir missing o sustituir el
calendario. Cualquier drift aborta antes de valores.

### 4.1 Digest congelado de la copia canónica

El digest no corresponde a un output nuevo. Se calcula en memoria así:

- ordenar por fecha ascendente y ordinal `SPY,QQQ,SPXW`;
- por row emitir exactamente, en UTF-8 y sin espacios,
  `{"close_i":<int>,"date":"<YYYYMMDD>","ticker":"<ticker>"}`;
- claves en ese orden lexicográfico, una row por línea, LF también tras la
  última row, sin BOM.

Resultado exacto para la autoridad pineada:

```text
canonical_rows=2790
canonical_jsonl_bytes=137640
canonical_jsonl_sha256=13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929
first=SPY:20230103:390
last=SPXW:20260917:390
```

No se escribe un `normalized_calendar` en la raíz final ni se lo trata como
fuente científica.

## 5. Archivos, pines y autoridades V2

La implementación nueva se limita a:

- `build_weekly_zone_event_value_paths_v2.py`;
- `test_build_weekly_zone_event_value_paths_v2.py`.

`weekly_zone_event_spot_paths.py`, 40814 bytes, SHA-256
`0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38`,
y sus tests permanecen byte-exactos. V2 no modifica ni duplica el módulo spot.

`implementation_pins` conserva exactamente diez claves:

```text
builder,spot_module,builder_tests,spot_tests,contract,
builder_final_review,spot_final_review,runtime_binding,launcher,resource_helper
```

`builder` y `builder_tests` apuntan a los dos archivos V2; `contract` apunta a
esta enmienda publicada; `spot_module`, `spot_tests` y `spot_final_review`
apuntan a sus autoridades originales; review del builder, binding y launcher
son nuevos y específicos de V2; helper oficial queda sin cambios. No se añaden
claves de implementación.

`authority_inputs` contiene exactamente las 25 claves originales enumeradas en
el contrato incorporado, más estas cuatro:

```text
stage_a_entry_plan,stage_a_weekly_sources,stage_a_summary,stage_a_manifest,
stage_a_audit,stage_a_audit_manifest,stage_a_audit_exit,
h1_inventory,h1_inventory_manifest,h1_manifest,
q3_inventory,q3_inventory_manifest,q3_manifest,
bridge_inventory,bridge_inventory_manifest,bridge_manifest,unified_calendar,
h1_context_inventory,h1_context_inventory_manifest,h1_context_manifest,
q3_context_inventory,q3_context_inventory_manifest,q3_context_manifest,
selector_builder_v2,normalization_pilot,
original_value_path_contract,prior_producer_exit,prior_producer_failure,
prior_producer_journal
```

| clave | path | bytes | SHA-256 |
|---|---|---:|---|
| `original_value_path_contract` | repo `WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md` | 36466 | `e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9` |
| `prior_producer_exit` | observer01 `exit.json` | 358 | `48b635e9fbdeef729de7c1be0b24948e21655ceb6cf5a154c02809e8a8a951d3` |
| `prior_producer_failure` | observer01 `failure_receipt.json` | 305 | `6ee1cb2ee3a29b74484c5ed54fe5049eb45da6e299c4fcd9ea8553bc809086fc` |
| `prior_producer_journal` | observer01 `journal.jsonl` | 6473 | `a12c7f5d5e1171e220cc1bcefd9f3191caf6e414f5c5df1cdeb5b4bc8b36aa08` |

Son exactamente 29 entradas. Las cuatro extras se admiten antes de staging y
se rehashean, junto con todos los demás admitted inputs, una por una en
`CLOSING_REHASH`. V2 exige en ellas exit1, failure no adoptable, ausencia de
ERROR posterior a `PINNED_AUTHORITIES` y ninguna evidencia de apertura de
footer/raw/cache. Una diferencia aborta.

## 6. Roots, journal y atomicidad V2

Raíces exclusivas, inicialmente ausentes:

```text
D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_02
D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_observer_02
```

V2 no puede escribir en roots 01, usar su observer como observer activo ni
adoptar staging previo. Conserva staging hermano nuevo, publicación atómica,
CPU0, diez variables a1, `CUDA_VISIBLE_DEVICES=-1`, gates oficiales RAM/commit
y disco >=2000000000 antes de cada unidad, Popen oculto con args list, handle
retenido, logs, process metadata y exit efectivo.

Tras `ADMIT_AUTHORITIES` y antes de `ADMIT_OPTION_FOOTERS`, el journal añade una
única unidad:

```text
kind=NORMALIZE_CALENDAR
identity=UNIFIED_CALENDAR
paths=[<path absoluto de unified_calendar.json>]
```

`STARTED` persiste gate+fsync antes de operar la normalización sobre el objeto
en memoria ya admitido. No exige reabrir ni volver a leer el calendario;
`COMPLETED.details` tiene exactamente:

```text
raw_pin:{path,bytes,sha256}
raw_schema:"weekly_h2_boundary_unified_calendar_v1"
raw_rows:2790
raw_order:"TICKER_MAJOR_QQQ_SPXW_SPY_DATE_ASC"
canonical_order:"DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW"
canonical_rows:2790
canonical_jsonl_bytes:137640
canonical_jsonl_sha256:"13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929"
identity_set_preserved:true
close_i_preserved:true
```

No contiene precios, agregados, samples ni información económica. ERROR impide
staging/output. Los restantes kinds y unidades del journal son idénticos al
contrato original.

## 7. Summary y manifest V2

Los siete data outputs mantienen nombres, schemas, filas y semántica del
contrato original. `summary.json` y `manifest.json` cambian sólo su envelope
operacional.

Summary usa
`schema="weekly_zone_event_value_paths_summary_v2_calendar_normalized"` y añade
una única clave top-level `calendar_normalization`; las demás claves y valores
son exactamente los de summary v1:

```text
calendar_normalization:{
 raw_pin:{
  path:"D:\\GexResearchArtifacts\\weekly_multiday_20261101\\h2_boundary_bridge_01\\unified_calendar.json",
  bytes:232573,
  sha256:"be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6"
 },
 raw_order:"TICKER_MAJOR_QQQ_SPXW_SPY_DATE_ASC",
 canonical_order:"DATE_ASC_TICKER_ORDINAL_SPY_QQQ_SPXW",
 rows:2790,
 canonical_jsonl_bytes:137640,
 canonical_jsonl_sha256:"13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929",
 identity_set_preserved:true,
 close_i_preserved:true
}
```

Manifest usa
`schema="weekly_zone_event_value_paths_manifest_v2_calendar_normalized"`, las
mismas claves top-level de v1 más `calendar_normalization` con el objeto exacto
anterior, diez `implementation_pins` y 29 `authority_inputs`. Outputs, counts,
flags, environment y status `COMPLETE_OUTCOME_FREE_VALUE_PATHS` conservan su
semántica exacta. Ningún otro agregado o campo está permitido. Manifest no se
autopinnea.

Por tanto los keysets top-level exactos son:

```text
summary:{schema,status,created_utc,stage_a,option_admission,selector,
option_paths,spot,outputs,flags,limitations,calendar_normalization}
manifest:{schema,status,created_utc,implementation_pins,authority_inputs,
admitted_option_sources,admitted_spot_inputs,outputs,counts,flags,environment,
calendar_normalization}
```

## 8. Implementación, fixtures y reviews requeridos

Antes de un run real V2 se exige, en este orden:

1. publicación byte-exact de esta enmienda y review documental independiente;
2. implementación V2 y tests V2 sin tocar builder/test originales ni spot;
3. fixtures sintéticos que cubran: orden upstream exacto, keyset/tipos/dominio,
   duplicado, ticker/fecha/`close_i` drift, conjuntos de fechas distintos,
   canonical digest, preservación uno-a-uno, rechazo antes de valores y roots
   01 intocables;
4. comparación estática/AST que demuestre que fuera de la adaptación de
   calendario, roots, schemas V2 y cuatro autoridades de fallo no cambió código
   científico respecto a builder `b6528622...`; suite formal única con
   compile/Ruff/pytest, CPU0, gates y snapshots;
5. reviews finales separados, binding y launcher V2 publicados y rehasheados;
6. un único run productor 02 desde cero.

No se reutiliza el auditor preparado para un productor 01 exitoso. El auditor
independiente V2 tendrá código/tests/reviews/fixtures/binding/launcher propios y
raíces exclusivas:

```text
D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_audit_02
D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_audit_observer_02
```

Debe validar independientemente el calendar upstream y recalcular el digest
canónico, reconstruir decisiones/observaciones/cobertura/spot como exige el
contrato incorporado, comparar schemas/filas/orden/null/NaN y verificar los 29
authority inputs, diez implementation pins, journal V2 y closing rehash. No
importa builder ni spot. Sus fixtures y review final deben cerrarse antes de su
única ejecución real y sólo después de un productor 02 exit0 adoptable.

## 9. Criterio de cierre

Un productor 02 puede declararse técnicamente cerrado sólo con exit0 retenido,
roots 02 exactas, `NORMALIZE_CALENDAR` completo, 29 autoridades estables,
outputs V2 completos y closing sin diferencias. Incluso entonces seguirá siendo
`SEEN_DEVELOPMENT`, `technical_ready=false`, `promotion_approved=false` y
`selected_policy=null`. Esos flags permanecen así incluso tras un eventual PASS
de auditoría 02: esta fase sigue siendo admisión de datos outcome-free y no
autoriza ninguna afirmación de rentabilidad.
