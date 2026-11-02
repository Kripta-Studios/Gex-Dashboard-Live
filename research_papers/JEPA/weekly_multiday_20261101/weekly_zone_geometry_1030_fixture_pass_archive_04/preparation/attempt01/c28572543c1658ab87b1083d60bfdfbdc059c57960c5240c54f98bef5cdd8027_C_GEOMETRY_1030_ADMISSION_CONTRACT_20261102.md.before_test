# C_GEOMETRY_1030_ADMISSION_CONTRACT_20261102

**Estado: `NON_EXECUTABLE_PENDING_REVIEW`**  
**Fecha de autoridad documental: 2026-11-02**

Este documento predeclara una admisión uniforme de geometría causal de zonas a las 10:30 NY. No autoriza implementación, fixtures, apertura de arrays, ejecución ni adopción de resultados. Tampoco autoriza eventos, etiquetas, selección de contratos weekly, probabilidades, EV, PnL o cantidades de riesgo. Su publicación y revisión byte-exactas, y el cierre real independiente de la fase B, son condiciones previas a cualquier código C.

## 1. Autoridad, objetivo y límites

La dirección científica es `WEEKLY_MULTIDAY_ZONE_REVISIT_RESEARCH_DIRECTION_20261102.md`, 16.596 bytes, SHA-256 `6850f559c25d5d6d3352109e0bc7b33d0d48aa14e0d097fa7cfdbe8c9ac1f011`. Este contrato concreta sólo su capa de geometría `state_i=60`.

El universo es el calendario uniforme ya fijado de 2.790 identidades ticker-sesión: 2.772 caches disponibles y 18 ausentes. La población disponible se divide en 2.595 H1 `FULL`, 24 H1 `SHORT` y 153 Q3; las ausencias son 6 H1 y 12 Q3. No se descarta una identidad por no tener paredes, nivel cercano o evento posterior.

La salida permitirá en una fase futura dos semánticas sin escoger entre ellas: `ENTRY_FROZEN`, que conserva el anchor causal de 10:30 para una entrada posterior, y `SESSION_1030_RESET`, que vuelve a formar la geometría al inicio de otra sesión. No se adopta `INTRADAY_WALL_UPDATED`. Tampoco se adopta una regla de visita, revisita, salida, q90 ni partida a dos bandas. La aparición de `2*band` abajo pertenece exclusivamente a la deduplicación geométrica.

## 2. Prerequisitos que mantienen este contrato no ejecutable

La fase B02 de valores debe cerrar antes de C con productor y auditor independientes, manifiestos finales, cierres de inputs/outputs y publicación remota byte-exacta. Estos bindings quedan deliberadamente sin resolver:

- `<B02_FINAL_PRODUCER_MANIFEST_SHA256_PENDING_CLOSURE>`;
- `<B02_FINAL_AUDIT_MANIFEST_SHA256_PENDING_CLOSURE>`;
- `<B02_FINAL_VALUE_PATHS_OUTPUT_MANIFEST_SHA256_PENDING_CLOSURE>`;
- `<B02_FINAL_CACHE_ADMISSION_SHA256_PENDING_CLOSURE>`;
- `<B02_FINAL_AUTHORITY_BUNDLE_SHA256_PENDING_CLOSURE>`.

Ninguna raíz parcial, staging, intento fallido o salida B sin auditoría puede satisfacer esos símbolos. C admitirá exactamente el calendario, las identidades, los paths de cache y los pins sellados por el cierre B; no redescubrirá fuentes y no ampliará sus autoridades.

Las funciones puras que una implementación futura deberá fijar byte a byte son:

- `level_engine.py`, SHA-256 `70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6`;
- `session_level_engine.py`, SHA-256 `f93d3be334a2326dbec5d742e217bce63449e1beaf46b35fa46be83f25548883`;
- `session_clock.py`, SHA-256 `1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9`;
- `session_cache.py`, SHA-256 `6300a7f8e5c6c99101d32d642081f4b8dec170d3c40f2751c27f1642d55466f1`;
- `build_cache.py`, SHA-256 `985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f`.

`build_day` queda expresamente prohibido: recorre estados posteriores, selecciona contratos y materializa acciones. Filtrar su resultado a state60 no remedia esa lectura y cálculo fuera de alcance.

## 3. Admisión exacta de cache y reloj

Cada identidad disponible se toma del inventario B, no de un glob. Su metadata y NPZ deben ser archivos regulares, sin symlink, junction, reparse point, alias físico ni hardlink no declarado. Se verifican path nominal, tamaño, SHA-256, identidad física y `stat` antes de abrir, después de cerrar y en el cierre global. Cualquier drift es fatal para la corrida completa; no produce una fila `missing`.

Se admite y valida el conjunto sellado completo requerido por `validate_cache`: `time_ns`, `strike`, `right`, `bid`, `ask`, `delta`, `iv`, `vega`, `theta`, `row_flags`, `spot`, `spot_valid`, `oi_contract_idx`, `oi_value`, `oi_available_ns` y `oi_valid`. `underlying_age_ms`, si existe, se conserva como metadata/proveniencia y sólo se abre si una whitelist de esquema publicada lo exige; no interviene en la geometría. No se abren features state60 precomputadas, labels, outcomes, advantages, oracle, acciones ni arrays extra.

El reloj se determina por el `close_i` admitido, sin inferencia por longitud silenciosa:

| sesión | `close_i` | slots | IB causal | estado | minutos restantes para gamma |
|---|---:|---:|---|---|---:|
| `FULL` | 390 | 391 | 0..59, 09:30–10:29 | 60, 10:30 | 330 |
| `SHORT` | 210 | 211 | 0..59, 09:30–10:29 | 60, 10:30 | 150 |

`time_ns` debe coincidir exactamente con el eje NY naive sellado, con paso de un minuto. El primer instante de disponibilidad es `time_ns[60]`, 10:30 NY; `formed_from_start=time_ns[0]` y `formed_from_end=time_ns[59]`. La tau anual de gamma es `(close_i-60)*60/(365*86400)`: usar la tau `FULL` para una sesión `SHORT` es fatal.

## 4. Receta causal única de state60

La implementación futura sólo podrá ejecutar este grafo:

1. Elegir `FULL` o `SHORT` desde metadata admitida y llamar `validate_cache(cache, clock)`.
2. Calcular `ib_bounds(cache)` con `spot[0:60]` y `spot_valid[0:60]`. Se exigen al menos 57 observaciones finitas positivas y `ib_high>ib_low`.
3. Exigir `spot_valid[60]` y `spot[60]` finito y positivo.
4. Obtener exclusivamente la fila 60 de `available_oi_matrix(cache, clock)`. Un registro OI causal posterior inválido escribe `NaN`; nunca se rellena hacia atrás con un registro viejo.
5. Obtener exclusivamente la fila 60 de `known_contract_matrix(cache)` para cobertura y proveniencia, no para alterar niveles.
6. Fijar `band=max(0.05*(ib_high-ib_low),0.0001*spot[60])`.
7. Llamar `causal_levels(cache, oi60, 60, ib_low, ib_high, band, clock)` y emitir sus clusters exactos.

Los trece Fib son `[-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,1.272,1.618,2]`, con centro `ib_low+ratio*(ib_high-ib_low)` y máscara `FIB=1`.

Las paredes son top 3 de masa estrictamente positiva en cuatro canales: `CALL_OI=2`, `PUT_OI=4`, `CALL_GAMMA=8` y `PUT_GAMMA=16`. El ranking determinista es `(-weight,strike)`, con CALL=0 y PUT=1. La gamma es el proxy BS de dollar-gamma **sin signo**: exige IV finita en `(0,5]`, OI finito no negativo y bit `present` de `row_flags`. No representa inventario dealer ni gamma de la opción weekly seleccionada.

La deduplicación ordena componentes por `(center,source_mask,name)`. Empieza grupo nuevo cuando `center-current_group_first_center>2*band`; por tanto limita el diámetro y no hace chaining transitivo. El cluster usa media aritmética de centros, OR de máscaras, número de componentes y JSON canónico (`sort_keys`, separadores compactos).

## 5. Estados, ausencia e invalidez

La precedencia por identidad es:

1. `MISSING_SOURCE`: el calendario B declara cache ausente. No se inventa geometría.
2. Error fatal: archivo presente con pin, estructura, schema, reloj o identidad divergente. No se degrada a missing o invalid.
3. `INVALID_IB`: cache válido pero menos de 57 spots IB válidos o rango no positivo.
4. `INVALID_STATE60`: IB válido pero spot60 inválido, no finito o no positivo.
5. `AVAILABLE_GEOMETRY`: IB y state60 válidos; puede contener sólo Fib si OI/IV no soportan paredes.

La falta de OI causal no convierte por sí sola la geometría en inválida. Debe verse en contadores y proveniencia. No se predeclara el número final de niveles ni de estados inválidos: será un resultado auditado, no una expectativa convertida en dato.

## 6. Identidad causal del anchor

Cada cluster recibe `anchor_id=sha256(canonical_payload_bytes).hexdigest()` en ASCII minúsculo. `canonical_payload_bytes` es exactamente `json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")`. Todo double debe ser binary64 finito y se serializa como string `float(x).hex()` en minúscula; si `x==0.0`, tanto `-0.0` como `0.0` se normalizan al string `"0x0.0p+0"`.

El payload tiene exactamente estas claves: `anchor_schema="C_GEOMETRY_1030_ANCHOR_V1"`, `ticker`, `date` en `YYYY-MM-DD`, `state_i=60`, `close_i`, `cluster_ordinal`, `center_f64`, `band_f64`, `source_mask` y `components`. `cluster_ordinal` es el `level_id` entero emitido por `deduplicate_levels` después de su orden exacto `(center,source_mask,name)`. Cada componente se normaliza desde el grupo crudo y se ordena de nuevo por la tupla total `(center numérico,source_mask,name,right,strike numérico,ratio numérico,weight numérico)`, usando `-1` para right ausente y `-inf` sólo como sentinel interno de orden para doubles ausentes; esos sentinels no se serializan. Un componente Fib contiene exactamente `kind="FIB"`, `name`, `source_mask`, `ratio_f64` y `center_f64`. Un componente de pared resuelve la identidad indicada por el `contract_i` crudo y contiene exactamente `kind="WALL"`, `name`, `source_mask`, `right`, `strike_f64`, `weight_f64` y `center_f64`.

`close_i` forma parte del ID porque determina la tau y la aritmética gamma; así, un mismo ticker-fecha no puede reutilizar accidentalmente un anchor bajo otro reloj de sesión.

`contract_i` es un índice de columna del cache de día completo: puede cambiar al permutar columnas o agregar contratos visibles sólo en el futuro. Puede conservarse en `provenance_components_json`, pero queda prohibido en el digest, el desempate y el ordinal causal. También queda prohibido incluir el SHA del NPZ completo en el digest; el SHA se conserva como proveniencia separada. Los componentes se normalizan por identidad semántica antes de ordenar.

Las fixtures futuras deberán probar tres invariancias byte-exactas de geometría e IDs: mutar cualquier sufijo posterior a state60; permutar columnas conservando identidades y valores semánticos; y agregar contratos que sólo aparecen después de state60. Pueden variar los índices crudos de proveniencia, nunca centros, pesos, orden semántico o `anchor_id`.

## 7. Dos tablas de datos, sin arrays adicionales

`geometry_states_1030.parquet` tendrá exactamente 2.790 filas, ordenadas por calendario B. Una fila por identidad incluirá como mínimo:

| grupo | campos obligatorios |
|---|---|
| identidad | `ticker`, `date`, `calendar_ordinal`, `authority_period`, `session_kind`, `close_i` |
| estado | `source_status`, `geometry_status`, `missing_reason?`, `state_i=60`, `state_clock_local`, `formed_from_start?`, `formed_from_end?`, `first_available_at?` |
| geometría | `spot_1030?`, `ib_observed?`, `ib_low?`, `ib_high?`, `ib_range?`, `band?`, `tau_years?`, `level_count` |
| cobertura | `known_contract_count?`, `oi_known_count?`, `oi_missing_count?`, cuatro contadores de paredes y `fib_component_count` |
| proveniencia | paths y SHA-256 de metadata/NPZ admitidos, `clock_basis?`, `oi_clock_basis?`, `oi_assumed_availability?`, `clock_delay_applied?`, `receipt_status` |

Los campos geométricos son nulos para missing/invalid conforme al estado; las claves e identidad nunca son nulas. `receipt_status` no puede afirmar recepción live observada.

`geometry_levels_1030.parquet` sólo contiene clusters de filas `AVAILABLE_GEOMETRY`, ordenados por calendario y ordinal causal:

| grupo | campos obligatorios |
|---|---|
| anchor | `anchor_id`, `ticker`, `date`, `session_kind`, `state_i=60`, `cluster_ordinal`, `first_available_at` |
| nivel | `center`, `band`, `source_mask`, `n_components`, `semantic_components_json` |
| proveniencia | `provenance_components_json`, path/SHA del NPZ, bases de reloj y limitaciones de OI |

No habrá `eligible`, `entry_level_id`, contrato weekly, visit, depart, action, target, stop, label, outcome, probability, EV, PnL ni quantity. Se permiten sólo un summary compacto, coverage compacta, manifest y journal necesarios para cerrar estas dos tablas; no se produce otro NPZ ni una tabla oculta.

## 8. Procedencia y limitaciones que deben viajar con la salida

El spot es consenso de snapshots finitos positivos cuya edad subyacente admitida fue 0–60 segundos; no es una serie continua ni prueba de toque. Minutos inconsistentes son inválidos y no se rellenan. El OI usa reloj nativo cuando existe; de otro modo puede estar marcado `ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT` con disponibilidad asumida 09:30. Greek clock puede estar marcado `ASSUMED_UNDERLYING_SNAPSHOT_CLOCK`. Un timestamp almacenado no acredita hora de recepción.

Las paredes proceden de opciones 0DTE del cache causal. No equivalen al gamma de contratos weekly D/D1/H2 ni seleccionan uno. Toda la población sigue siendo `SEEN_DEVELOPMENT`.

Para H1 `FULL` se podrá ejecutar, como diagnóstico no vinculante, un comparador strict-whitelist contra estados/niveles/causal freeze históricos, sólo si sus paths, schemas y pins fueron admitidos expresamente. No es requisito de aceptación uniforme, no se extiende a SHORT/Q3 y no autoriza abrir siblings de labels, advantages, oracle o actions.

## 9. Protocolo futuro de ejecución y cierre

Una implementación posterior necesitará contrato operativo y review propios. Como mínimo: un hijo, afinidad CPU0, cero pools/subprocesos por archivo, variables de threads fijadas a 1 y gate oficial contemporáneo de RAM, free commit y disco de al menos 2 GB antes de cada unidad. Cada identidad tendrá journal `start` y `complete/error` con `fsync`; cada input se hashea antes/después y de nuevo al cierre. Los outputs se escriben en staging hermano exclusivo, se cierran, `fsync`, hashean y rehashean antes de un único rename atómico. No hay resume ni adopción parcial.

El auditor independiente no importará el productor. Readmitirá autoridades e inputs, reconstruirá las 2.790 identidades y la descomposición 2.772/18, llamará al mismo grafo puro state60 desde código pineado, recalculará ambas tablas, schemas, nulabilidad, orden, anchors, hashes y cierres, y ejercerá las tres invariancias del apartado 6. La validación estructural y las funciones puras existentes pueden inspeccionar arrays completos; el auditor demostrará que ningún valor del sufijo posterior a state60 influye en los outputs. También probará que no se abrieron acciones, labels, outcomes ni selección weekly.

## 10. Condición de salida documental

Este borrador permanece `NON_EXECUTABLE_PENDING_REVIEW` hasta que: (a) root y reviewer documental lo declaren CLEAR sobre bytes exactos; (b) se publique y verifique remoto; (c) la fase B02 real cierre y sustituya todos los símbolos pendientes por pins auditados; y (d) exista un contrato separado para implementación C. Hasta entonces no hay dataset C, geometría admitida, evento, modelo ni resultado económico nuevo.
