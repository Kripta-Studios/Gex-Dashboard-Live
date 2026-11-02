# C_GEOMETRY_1030_OPERATIONAL_DRAFT_20261102

**Estado: `DRAFT_NON_EXECUTABLE_PENDING_B_CLOSURE`**  
**Fecha del borrador: 2026-11-02**

Este documento resuelve exclusivamente formatos técnicos pendientes del contrato `C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102.md`, 14.617 bytes, SHA-256 `c28572543c1658ab87b1083d60bfdfbdc059c57960c5240c54f98bef5cdd8027`. No modifica ese contrato, no cambia su ciencia y no autoriza código, fixtures, apertura de NPZ/raw, ejecución ni adopción de datos.

## 1. Dependencias todavía abiertas

La fase B04 está activa mientras se redacta este documento. Sus parciales no se leen, se citan ni se adoptan. Existe un mapa conceptual hacia un productor previamente conocido como cerrado (`a303…`) y una admisión de cache (`e0b4…`), pero esos prefijos no son pins y no constituyen autoridad C. El auditor B04, su cierre independiente y sus hashes finales siguen desconocidos.

Los siguientes bindings continúan `PENDING` y deben sustituirse por SHA-256 completos sólo después de PASS, review y publicación B:

- `B_FINAL_PRODUCER_MANIFEST_SHA256`;
- `B_FINAL_AUDIT_MANIFEST_SHA256`;
- `B_FINAL_CACHE_ADMISSION_SHA256`;
- `B_FINAL_CALENDAR_SHA256`;
- `B_FINAL_AUTHORITY_BUNDLE_SHA256`;
- `B_FINAL_REVIEW_SHA256`.

Mientras cualquiera permanezca pendiente, un launcher C debe rechazar antes de crear output, observer o journal. No se admite una raíz B parcial, fallida, staging, productor sin auditor o manifest reconstruido informalmente.

## 2. Universo, orden y archivos finales

El universo permanece exactamente en 2.790 filas calendario, en el orden sellado por B. Debe reconciliar 2.772 fuentes disponibles y 18 ausentes; las disponibles son 2.595 H1 `FULL`, 24 H1 `SHORT` y 153 Q3, y las ausentes son 6 H1 y 12 Q3. La clave calendario es `(ticker,trade_date)` y es única. `calendar_ordinal` es su posición cero-based en la autoridad B y nunca se recalcula por orden lexicográfico.

La raíz final C, cuyo nombre se fijará en el contrato operativo publicado, contendrá exactamente estos cuatro archivos:

1. `geometry_states_1030.parquet`;
2. `geometry_levels_1030.parquet`;
3. `coverage.json`;
4. `manifest.json`.

Sólo los dos primeros son tablas de datos. No se escribirá NPZ, array auxiliar, tabla de eventos, labels, contratos weekly, matching, acciones o economía. El journal vive en una raíz observer separada y nunca entra en la raíz final.

## 3. Convenciones físicas comunes

Las dos tablas usan Arrow schema explícito, sin inferencia. Parquet: versión 2.6, data page v1, compresión `zstd` nivel 9, `use_dictionary=false`, `write_statistics=true`, sin índice pandas y sin metadata pandas. El writer y PyArrow exactos quedan pendientes de pin de implementación; por ello todavía no existe expectativa de hash Parquet.

Los timestamps locales son `timestamp[ns]` sin timezone porque reproducen el eje NY naive sellado; no se convierten a UTC. `trade_date` es `date32[day]`. Todo SHA-256 almacenado es `utf8` minúsculo de 64 hex. Todo JSON embebido usa UTF-8 y `json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)`. No se permite NaN/Inf en JSON. Los doubles Parquet pueden contener sólo valores finitos cuando no son null.

Orden físico:

- states: `calendar_ordinal` ascendente;
- levels: `(calendar_ordinal,cluster_ordinal)` ascendente;
- un row group para states; levels usa row groups consecutivos de como máximo 65.536 filas, sin dividir o reordenar una identidad para lograr el límite.

## 4. Schema exacto de `geometry_states_1030.parquet`

Debe contener exactamente 2.790 filas y estas columnas, en este orden:

| # | campo | Arrow | null | regla |
|---:|---|---|:---:|---|
| 1 | `calendar_ordinal` | `int32` | no | 0..2789, único |
| 2 | `ticker` | `utf8` | no | `SPY`, `QQQ` o `SPXW` |
| 3 | `trade_date` | `date32[day]` | no | clave calendario |
| 4 | `authority_period` | `utf8` | no | `H1` o `Q3` |
| 5 | `session_kind` | `utf8` | no | `FULL` o `SHORT`, desde calendario |
| 6 | `close_i` | `int16` | no | 390 FULL, 210 SHORT |
| 7 | `source_status` | `utf8` | no | `AVAILABLE` o `MISSING` |
| 8 | `geometry_status` | `utf8` | no | enum del apartado 6 |
| 9 | `missing_reason` | `utf8` | sí | no null sólo para missing |
| 10 | `state_i` | `int16` | no | siempre 60 |
| 11 | `state_clock_local` | `timestamp[ns]` | no | fecha + 10:30 NY naive |
| 12 | `formed_from_start` | `timestamp[ns]` | sí | null sólo si missing |
| 13 | `formed_from_end` | `timestamp[ns]` | sí | null sólo si missing |
| 14 | `first_available_at` | `timestamp[ns]` | sí | 10:30 sólo si geometry available |
| 15 | `spot_1030` | `float64` | sí | finito positivo si available geometry |
| 16 | `ib_observed` | `int16` | sí | 57..60 sólo si `ib_bounds` devuelve tupla |
| 17 | `ib_low` | `float64` | sí | IB válido: available o invalid state60 |
| 18 | `ib_high` | `float64` | sí | IB válido; mayor que low |
| 19 | `ib_range` | `float64` | sí | IB válido; `high-low`, positivo |
| 20 | `band` | `float64` | sí | fórmula congelada |
| 21 | `tau_years` | `float64` | sí | fórmula FULL/SHORT congelada |
| 22 | `level_count` | `int16` | no | 0 para missing/invalid |
| 23 | `known_contract_count` | `int32` | sí | sólo geometry available |
| 24 | `oi_known_count` | `int32` | sí | sólo geometry available |
| 25 | `oi_missing_count` | `int32` | sí | sólo geometry available |
| 26 | `fib_component_count` | `int16` | sí | 13 si geometry available |
| 27 | `call_oi_wall_count` | `int8` | sí | 0..3 si geometry available |
| 28 | `put_oi_wall_count` | `int8` | sí | 0..3 si geometry available |
| 29 | `call_gamma_wall_count` | `int8` | sí | 0..3 si geometry available |
| 30 | `put_gamma_wall_count` | `int8` | sí | 0..3 si geometry available |
| 31 | `cache_metadata_path` | `utf8` | sí | canonical; null si missing |
| 32 | `cache_metadata_sha256` | `utf8` | sí | null si missing |
| 33 | `cache_npz_path` | `utf8` | sí | canonical; null si missing |
| 34 | `cache_npz_sha256` | `utf8` | sí | null si missing |
| 35 | `clock_basis` | `utf8` | sí | literal de metadata, null si missing |
| 36 | `oi_clock_basis` | `utf8` | sí | literal de metadata, null si missing |
| 37 | `oi_assumed_availability` | `utf8` | sí | literal o null |
| 38 | `clock_delay_applied` | `bool` | sí | literal o null |
| 39 | `receipt_status` | `utf8` | no | `UNVERIFIED` o `NOT_APPLICABLE` |

El tipo de `oi_assumed_availability` no es inferido: el `build_cache.py` pineado por C lo escribe como `None` cuando el reloj OI es nativo y como `str(time[0])` en el fallback, por lo que `utf8` nullable es la representación exacta. Se valida sin stringify/coercion: `oi_clock_basis=NATIVE_STORED_TIMESTAMP` exige null; `oi_clock_basis=ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT` exige el string literal exacto de `time_ns[0]` según metadata. `clock_delay_applied` es booleano en esa misma metadata.

No se agregan campos. Para `INVALID_IB`, `ib_bounds` devuelve `None`: `ib_observed`, spot y los campos 17–21 son null; este draft no inventa cero ni reimplementa un contador alternativo. Para `INVALID_STATE60`, `ib_observed`, low, high y range se conservan, pero spot, band y tau son null. Los campos 23–30 son null en ambos estados porque el grafo se detiene antes de paredes. Para `MISSING_SOURCE`, todos los campos nullable son null salvo `missing_reason`; `receipt_status=NOT_APPLICABLE`.

## 5. Schema exacto de `geometry_levels_1030.parquet`

Sólo contiene clusters de estados `AVAILABLE_GEOMETRY`. Columnas exactas y orden:

| # | campo | Arrow | null | regla |
|---:|---|---|:---:|---|
| 1 | `calendar_ordinal` | `int32` | no | FK a states |
| 2 | `cluster_ordinal` | `int16` | no | `level_id`, cero-based por identidad |
| 3 | `anchor_id` | `utf8` | no | SHA-256 canónico del contrato C |
| 4 | `ticker` | `utf8` | no | igual a states |
| 5 | `trade_date` | `date32[day]` | no | igual a states |
| 6 | `session_kind` | `utf8` | no | FULL/SHORT |
| 7 | `close_i` | `int16` | no | parte del anchor payload |
| 8 | `state_i` | `int16` | no | 60 |
| 9 | `first_available_at` | `timestamp[ns]` | no | fecha + 10:30 NY naive |
| 10 | `center` | `float64` | no | finito |
| 11 | `band` | `float64` | no | finito positivo |
| 12 | `source_mask` | `int16` | no | OR de 1,2,4,8,16 |
| 13 | `n_components` | `int16` | no | positivo |
| 14 | `semantic_components_json` | `utf8` | no | componentes exactos usados por ID |
| 15 | `provenance_components_json` | `utf8` | no | puede incluir `contract_i` crudo |
| 16 | `cache_npz_path` | `utf8` | no | canonical |
| 17 | `cache_npz_sha256` | `utf8` | no | provenance, fuera del ID |
| 18 | `clock_basis` | `utf8` | no | literal admitido |
| 19 | `oi_clock_basis` | `utf8` | no | literal admitido |
| 20 | `receipt_status` | `utf8` | no | siempre `UNVERIFIED` |

`anchor_id` y `(calendar_ordinal,cluster_ordinal)` son únicos. Cada identidad tiene ordinales contiguos `0..level_count-1`, y el conteo coincide con states. En cada state disponible, `oi_known_count+oi_missing_count=known_contract_count`; la suma de los cuatro wall counts es el número de componentes de pared antes de clustering. `semantic_components_json` excluye `contract_i` y pins. `provenance_components_json` preserva el grupo crudo normalizado, incluido `contract_i` cuando existe, pero nunca interviene en digest, ranking o matching.

## 6. Estados y 16 arrays admitidos

El productor futuro puede abrir exactamente estos 16 arrays y ninguno más:

`time_ns`, `strike`, `right`, `bid`, `ask`, `delta`, `iv`, `vega`, `theta`, `row_flags`, `spot`, `spot_valid`, `oi_contract_idx`, `oi_value`, `oi_available_ns`, `oi_valid`.

`underlying_age_ms` no se abre en esta versión; su presencia física está permitida si el schema upstream la declara y su existencia/schema se registran desde metadata. Cualquier array adicional no declarado por el schema exacto es fatal. No se abren features, state arrays derivados, labels, outcomes, oracle, actions ni selección weekly.

Los estados exactos son:

- `MISSING_SOURCE`: ausencia predeclarada por B; `source_status=MISSING` y `missing_reason="SOURCE_PLAN_MISSING"`.
- `INVALID_IB`: cache admitido y estructuralmente válido, pero menos de 57 spots IB válidos o rango no positivo.
- `INVALID_STATE60`: IB válido, spot60 inválido/no finito/no positivo.
- `AVAILABLE_GEOMETRY`: IB y spot60 válidos; Fib13 siempre presentes, paredes de 0 a 3 por canal.

Pin, path, schema, reloj, shape o identidad divergente es error fatal de corrida, nunca un quinto estado. OI ausente o invalidado causalmente reduce paredes y cobertura, no invalida Fib.

## 7. Grafo state60 y no influencia futura

Se conserva sin cambio el grafo puro del contrato C: `validate_cache`; `ib_bounds` sobre 0..59; validación spot60; fila 60 de `available_oi_matrix`; fila 60 de `known_contract_matrix`; band; `causal_levels`. No se llama `build_day` ni se implementa una versión aproximada.

Las funciones selladas inspeccionan estructuras completas y pueden construir matrices completas. La obligación comprobable no es fingir que no abren sufijo, sino demostrar que el sufijo posterior a state60 no influye en la proyección semántica. `STATE_SEMANTIC_COLUMNS` son exactamente las columnas 1–30 de states; `LEVEL_SEMANTIC_COLUMNS` son exactamente las columnas 1–14 de levels. Esas proyecciones, incluidos IDs y contadores as-of, deben ser byte-equivalentes tras normalización Arrow. La perturbación conserva schema, eje, identidades y el conjunto causal disponible a 10:30; ningún registro cruza el límite de `oi_available_ns` de state60. Paths, SHA de cache y `provenance_components_json` siguen la variante física exacta y pueden cambiar; no se exige que mientan para preservar igualdad. La tau sigue siendo `(close_i-60)*60/(365*86400)`: 330 minutos FULL y 150 SHORT.

## 8. IDs, ENTRY_FROZEN y RESET

El `anchor_id` se calcula exactamente como en el contrato C: SHA-256 lowercase del payload JSON canónico, floats binary64 mediante `float.hex`, cero con signo normalizado, `close_i` incluido y `contract_i`/SHA del NPZ excluidos. No se redefine aquí el payload.

Para `ENTRY_FROZEN`, una referencia D, D1 o H2 a la misma geometría de entrada transporta el mismo `anchor_id`; el horizonte no crea otro ID. `available_at` de esa referencia nunca puede ser anterior a las 10:30 de la sesión que formó el anchor.

Para `SESSION_1030_RESET`, cada nueva sesión forma IDs nuevos desde su propio ticker, fecha, reloj y geometría state60. Un futuro matching entre anchor anterior y reset no estará disponible antes de `max(previous_anchor_available_at,current_reset_available_at)`, donde ambos clocks son como mínimo 10:30 de su sesión. Este documento no define el matching, tolerancia, continuidad overnight, conducta ante una sesión missing ni evento resultante: todo ello queda `PENDING_EVENT_CONTRACT`, no adoptado.

## 9. Metadata JSON exacta

`coverage.json` es un objeto JSON compacto terminado en LF con exactamente estas claves, ordenadas canónicamente: `status`, `calendar_rows`, `available_sources`, `missing_sources`, `h1_full_available`, `h1_short_available`, `q3_available`, `h1_missing`, `q3_missing`, `geometry_available`, `invalid_ib`, `invalid_state60`, `state_rows`, `level_rows`, `entry_frozen_supported`, `session_1030_reset_supported`, `event_rules_adopted`, `data_scope`. `status="C_GEOMETRY_1030_CLOSED"`. Los primeros ocho conteos estructurales deben ser 2790,2772,18,2595,24,153,6,12 en su correspondencia; los tres conteos geométricos son resultados reales. Debe cumplirse `geometry_available+invalid_ib+invalid_state60=2772`, `missing_sources=18`, `state_rows=calendar_rows=2790` y `level_rows=rows(geometry_levels_1030.parquet)=sum(states.level_count)`. Además, status/source/session/period deben reconciliar por identidad entre tablas y, por agregación, con coverage y `manifest.counts`. `entry_frozen_supported=true`, `session_1030_reset_supported=true`, `event_rules_adopted=false` y `data_scope="SEEN_DEVELOPMENT"`.

`manifest.json` es JSON compacto terminado en LF con exactamente: `status`, `contract`, `implementation`, `authorities`, `authority_pins`, `input_count`, `inputs_digest`, `outputs`, `counts`, `journal_closure`, `resource_policy`, `created_at_utc`, `no_events`, `no_labels`, `no_weekly_selection`, `no_economics`. `status="C_GEOMETRY_1030_CLOSED"`. `outputs` tiene exactamente tres miembros, `geometry_states_1030.parquet`, `geometry_levels_1030.parquet` y `coverage.json`; cada valor es exactamente `{path,bytes,sha256,rows}`, con `rows=null` para coverage. `manifest.json` es el cuarto archivo final y no se autopinea. `inputs_digest` es el SHA-256 del JSON canónico de la lista completa ordenada por path de `{path,bytes,sha256,physical_identity}`.

## 10. Gates, journal y atomicidad

Una implementación futura usará un solo hijo con afinidad CPU0, ningún pool/subproceso por archivo y todas las variables BLAS/OpenMP conocidas fijadas a `1`. Antes de cada unidad se llama al helper oficial pineado y se exigen simultáneamente RAM disponible, free commit y disco libre `>=2_000_000_000` bytes.

El journal es JSONL compacto, append-only, handle único y `fsync` después de cada registro. Cada registro tiene exactamente: `seq`, `utc`, `kind`, `identity`, `phase`, `paths`, `gate`, `details`. `phase` es `START`, `COMPLETE` o `ERROR`. Un `START` durable precede cualquier apertura de la unidad; COMPLETE/ERROR se escribe después de cerrar handles. Kinds permitidos:

- `ADMIT_AUTHORITY`, una por autoridad;
- `GEOMETRY_IDENTITY`, una por cada una de 2.790 identidades, incluida missing;
- `WRITE_OUTPUT`, una por cada uno de los cuatro outputs;
- `CLOSING_INPUT`, una por cada input admitido;
- `CLOSING_OUTPUT`, una por cada output staging;
- `PUBLISH_ROOT`, exactamente una.

Cada identidad disponible recibe stat/hash antes y después; cada input se rehashea de nuevo bajo su propia unidad `CLOSING_INPUT`. Cada output se cierra, hace file-`fsync`, hashea y rehashea en staging. La primitiva concreta para durabilidad del directorio en Windows queda `PENDING_IMPLEMENTATION_BINDING`: el contrato final debe pinear una operación soportada y verificable o rechazar antes de mutar; este draft no promete que POSIX directory-`fsync` sea portable. Staging y final deben estar en el mismo volumen para un único rename atómico.

`manifest.journal_closure` es exactamente `{prepublish_last_seq,prepublish_prefix_sha256}` y liga el prefijo durable del journal hasta e incluyendo `WRITE_OUTPUT/START` de `manifest.json`; es un snapshot precommit, no un hash de cierre final ni un autopin. El cierre journal final sólo existe en el observer externo. Tras escribir/cerrar el manifest y registrar su COMPLETE, se ejecutan todos los checks fallibles y cierres de outputs antes del commit. `PUBLISH_ROOT/START` durable precede al rename terminal y `PUBLISH_ROOT/COMPLETE` lo sigue. No hay resume. Un fallo antes del rename conserva final ausente; una interrupción entre rename y COMPLETE puede dejar final presente, pero queda `UNADOPTABLE_INCOMPLETE_PUBLICATION`, se preserva para auditoría, nunca se autoelimina/reutiliza y nunca se trata como PASS.

## 11. Semántica obligatoria de fixtures futuros

El paquete de implementación deberá probar, sin datos reales:

1. Schema completo, orden, tipos, nulabilidad y rechazo de columnas extra para ambas tablas.
2. Calendario de 2.790 por fixture escalable y cardinalidades FULL/SHORT/Q3/missing sin monkeypatch de expectativas.
3. IB con 57/56 observaciones, rango cero, spot60 inválido y precedencia de estados.
4. Tau y gamma distintas FULL/SHORT; Fib13, cuatro canales top3, desempate `(-weight,strike)` y cluster de diámetro `<=2*band` sin chaining.
5. OI causal: actualización inválida produce NaN y no backfill.
6. Mutación de todo sufijo posterior a state60, preservando schema/eje/identidades y set as-of 10:30, sin cambio de `STATE_SEMANTIC_COLUMNS` ni `LEVEL_SEMANTIC_COLUMNS`; pins/path de la variante pueden cambiar.
7. Permutación de columnas y adición de contratos sólo futuros: proyecciones semánticas, geometría, semantic JSON e IDs iguales; provenance `contract_i` y pins pueden variar.
8. Serialización anchor exacta, normalización `-0.0`, rechazo de NaN/Inf y unicidad/contigüidad de ordinales.
9. ENTRY_FROZEN conserva ID entre referencias D/D1/H2; RESET de otra fecha crea namespace nuevo, sin implementar matching.
10. Presencia declarada de `underlying_age_ms` permitida pero prueba de que no se abre/usa; rechazo de extras no declarados, label/action/outcome, función `build_day` o campo/table extra.
11. Gate antes de apertura, una pareja journal durable por unidad, hash drift, interrupción en cada output, closing total, final ausente si falla antes del rename y final no adoptable si se interrumpe después.
12. Auditor reconstruye tablas desde inputs, verifica todas las ecuaciones de reconciliación del apartado 9 y detecta una alteración de contenido, schema, orden, null o pin.

Estas son obligaciones futuras, no fixtures autorizadas por este borrador.

## 12. Exit y cierre reales

El futuro CLI reservará: exit 0 `PASS_CLOSED`; 2 uso/CLI; 10 binding/autoridad; 11 seguridad/path; 12 gate de recursos; 13 drift/hash; 14 schema/cache/geometría fatal; 15 escritura/fsync/atomicidad; 16 invariantes de cierre o prerequisito B incompleto. Los códigos no convierten un fallo en estado científico.

Exit 0 sólo es posible si: todos los bindings B están resueltos; 2.790 unidades terminaron; los conteos estructurales reconciliaron; ambas tablas y JSON cerraron; todos los inputs y outputs pasaron rehash final; journal cerró sin START pendiente; manifest quedó durable; el rename único publicó una raíz final antes ausente; y `PUBLISH_ROOT/COMPLETE` quedó durable. Una raíz no es adoptable por mera presencia: se exige exit 0 retenido y cierre journal consistente. La adopción científica requiere además auditor C independiente PASS, review de cierre y publicación byte-exacta.

## 13. Condición de no ejecución

Este archivo permanece `DRAFT_NON_EXECUTABLE_PENDING_B_CLOSURE`. No es GO y no debe figurar como binding de un launcher. Para promoverlo se requieren, en orden: cierre B completo y auditado; sustitución de bindings PENDING; review documental del contrato operativo final; publicación/remoto byte-exactos; implementación y fixtures nuevos; review estático; y autorización separada de ejecución. Ninguna regla de eventos, overnight, missing matching, labels o economía queda adoptada aquí.
