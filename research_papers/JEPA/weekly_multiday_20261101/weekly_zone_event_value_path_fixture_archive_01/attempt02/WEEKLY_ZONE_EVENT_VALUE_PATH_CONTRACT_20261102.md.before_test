# Contrato de admisión de valores y trayectorias weekly por zonas

Fecha de autoridad: 2026-11-02. Estado:
`PREDECLARED_VALUE_PATH_ADMISSION_CONTRACT_NOT_A_RESULT`.

Esta fase B posterior al plan de fuentes auditado admite los Parquets weekly
actuales, congela causalmente un CALL y un PUT a las 10:30, extrae la trayectoria
observada del mismo contrato en D, D1 y H2 y materializa el spot de caches ya
cerrados. Es admisión de datos libre de outcomes: no entrena, predice ni calcula
escenarios, eventos, PnL, EV, costes, riesgo, cantidad o trades.

## 1. Alcance y prohibiciones

La única pregunta autorizada es qué cotizaciones minuteadas del contrato elegido
usando sólo el snapshot de 10:30, y qué spot cacheado, pueden ligarse de forma
estable a cada plan weekly.

Está prohibido:

- abrir cualquier `candidates.jsonl` de H1/Q3/puente: cada objeto mezcla campos
  causales con `status`, `label_available_at`, `scenario`, `exit_bid`,
  `entry_debit_*` y `net_*`;
- leer labels, outcomes, ledgers, scores, modelos, pesos, features B81, features
  NPZ, arrays `state60`, acciones o PnL;
- usar D1, H2, 10:35, completitud o precio futuro para elegir el contrato;
- calcular zonas/touches, targets, stops, exits, scenarios, EV, costes, sizing,
  qty, portfolio, replay o promoción;
- afirmar receipt vivo o ejecutabilidad. Ni el timestamp nativo almacenado es
  receipt time; para el proxy de subyacente también es desconocido.

Todo sigue `SEEN_DEVELOPMENT`; ningún output permite interpretación económica.

## 2. Autoridades compactas inmutables

Antes de footer, raw value o NPZ se exige ruta, bytes y SHA-256 exactos. Una
diferencia aborta sin outputs finales.

### 2.1 Stage A y auditor independiente

Raíz `D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_source_plan_01`:

| archivo | bytes | SHA-256 |
|---|---:|---|
| `entry_plan.jsonl` | 1018910 | `0db0065f2dcdd254122a4c4575ecb9c752318cab3a90666ad8215aef922d91bb` |
| `weekly_sources.jsonl` | 2367532 | `59081a049d11a0403204ca06e62ef4661bb6de3cd042548e081c10f8eaddd1f7` |
| `summary.json` | 1398 | `612ecf1abf18f973656aeda347f21efe563f5c84b9cc06f96e22383ed19b3b39` |
| `manifest.json` | 5094 | `a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161` |

Raíces `weekly_zone_event_source_plan_audit_01` y
`weekly_zone_event_source_plan_audit_observer_01`:

| archivo | bytes | SHA-256 |
|---|---:|---|
| `audit.json` | 9071 | `1b71077525d146cd7e2166076f987afd315fe46e27c15e51c4f7555be06299cd` |
| `manifest.json` | 8945 | `49935941c89b67f2aef69272201d68d089d9499d0fca71838867b5457bf85ba7` |
| observer `exit.json` | 1337 | `bfdf36bfb7f636f27a391ad0b0ed38be5306e69b0c5be144d0c0599de9d65362` |

Se revalidan cross-pins, PASS/exit0 y conteos: 930 sesiones, 2790
ticker-días, 1620 `PLANNED`, 1164 `NO_SERIES`, seis terminales, 4860 refs y
2784 fuentes. Stage A no se reconstruye ni modifica.

### 2.2 Inventarios option históricos

Estas autoridades fijan hash, filas y `projected_schema` de las 2765 fuentes
presentes con binding histórico y el calendario/cierre:

| archivo absoluto | bytes | SHA-256 |
|---|---:|---|
| `D:\GexResearchArtifacts\weekly_multiday_20261101\h2_dataset_v2_01\inventory.json` | 5589855 | `099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12` |
| `...\h2_dataset_v2_01\inventory_manifest.json` | 187 | `c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899` |
| `...\h2_dataset_v2_01\manifest.json` | 1541 | `bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8` |
| `...\h2_dataset_v2_extension_2026q3_partial_01\inventory.json` | 327384 | `f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c` |
| `...\h2_dataset_v2_extension_2026q3_partial_01\inventory_manifest.json` | 197 | `5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f` |
| `...\h2_dataset_v2_extension_2026q3_partial_01\manifest.json` | 6184 | `b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b` |
| `...\h2_boundary_bridge_01\inventory.json` | 14721 | `599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161` |
| `...\h2_boundary_bridge_01\inventory_manifest.json` | 330 | `0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2` |
| `...\h2_boundary_bridge_01\manifest.json` | 4748 | `9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86` |
| `...\h2_boundary_bridge_01\unified_calendar.json` | 232573 | `be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6` |

Aquí `...` es sólo `D:\GexResearchArtifacts\weekly_multiday_20261101`, no glob.

### 2.3 Autoridades spot cache

| archivo absoluto | bytes | SHA-256 |
|---|---:|---|
| `...\h2_context_1030_01\inventory.json` | 1829496 | `b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e` |
| `...\h2_context_1030_01\inventory_manifest.json` | 197 | `a7547c375a4de723b168ce2983b84ba98a35dd70aef24c82ed08c1e3c5358ea8` |
| `...\h2_context_1030_01\manifest.json` | 612610 | `77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a` |
| `...\h2_context_q3_1030_01\inventory.json` | 1489911 | `25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf` |
| `...\h2_context_q3_1030_01\inventory_manifest.json` | 193 | `2b74c18e98366670e77e3d2a4fc19e260cd404e6959fbd7e140f2e88fd5050be` |
| `...\h2_context_q3_1030_01\manifest.json` | 172889 | `1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66` |

No se abre `index.parquet`, `context.jsonl`, `coverage.json`, features NPZ ni
`state60`.

### 2.4 Semántica congelada, sin imports

| archivo repo | bytes | SHA-256 |
|---|---:|---|
| `build_weekly_h2_dataset_v2.py` | 33142 | `ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945` |
| `weekly_multiday_source_pilot.py` | 31380 | `ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878` |

La implementación nueva reimplementa sólo la normalización causal definida
aquí. No importa esos módulos ni copia rutinas de execution/scenario/net.

## 3. Dos universos distintos

- Weekly: 2784 fuentes únicas/4860 legs; 2768 presentes y 16 missing. Roles:
  1620 ENTRY, 1620 D1, 1620 H2; faltan ocho D1 y dieciséis H2. Tres presentes
  sin binding histórico son 2023-01-04/expiry 2023-01-06, una por ticker.
- Spot: 2790 `(ticker,session_date)`; 2772 disponibles y 18 missing. H1:
  2595 FULL+24 SHORT+6 missing. Q3:153 disponibles+12 missing.
- QQQ/SPY 2026-07-10 son dos missing spot no referidos por legs weekly.

Se conservan conteos `NO_SERIES` y terminales; sólo 1620 `PLANNED` se
seleccionan. Una ausencia nunca permite excluir retrospectivamente un plan.

## 4. Admisión de 2784 fuentes weekly

Raíz única `D:\ThetaData\data_options`. Se repiten controles lexicales/físicos
Stage A: absoluta exacta, sin `..`, alias, symlink, junction, reparse, hardlink
ambiguo ni identidad física compartida; `lstat` de ancestros; archivo regular.

- Las 16 missing deben seguir ausentes; aparición falla.
- Las 2768 presentes conservan bytes Stage A.
- Las 2765 históricas deben igualar SHA, filas y `projected_schema` de todos sus
  bindings.
- Para las tres nuevas se fija primera autoridad de SHA, bytes, filas,
  row-groups y schema Arrow completo, revalidada al cierre.
- Drift de presencia/hash/bytes/schema/filas/identidad aborta.

El footer exige identidades `symbol,expiration,trade_date,strike,right`, valores
`underlying_timestamp,underlying_price,bid,ask,delta,implied_vol,theta,vega,rho`
y un reloj. `gamma`
es opcional: ausente produce null y `gamma_column_present=false`. `interval_used`
es opcional y se guarda sin filtrar. Reloj: `timestamp` si existe
(`NATIVE_STORED_TIMESTAMP`), de lo contrario `underlying_timestamp`
(`UNDERLYING_TIMESTAMP_PROXY`). Para las 2765 históricas se esperan 1562/1203;
las tres nuevas se clasifican por footer.

`source_admission.jsonl`, 2784 objetos ordenados por path:

```text
path:str,ticker:str,trade_date:str,expiration:str,stage_a_exists:bool,
admission_status:PRESENT|MISSING,binding_kind:HISTORICAL|FIRST_AUTHORITY|EXPECTED_MISSING,
bytes:int64?,sha256:str?,rows:int64?,row_groups:int32?,
projected_schema:list<{name,type}>?,
full_schema:{fields:list<{name:str,type:str,nullable:bool,
metadata:list<{key_b64:str,value_b64:str}>}>,
metadata:list<{key_b64:str,value_b64:str}>}?,
clock_column:str?,clock_basis:str?,gamma_column_present:bool?,
expected_binding_authorities:list<str>,before_stat:object?,after_stat:object?,
ignored_reason:str?
```

No contiene valores de mercado.

Población exacta por `binding_kind`:

- `HISTORICAL`: bytes/hash/rows/row_groups, `projected_schema`, clock/gamma y
  ambos stats son no-null; `full_schema=null`.
- `FIRST_AUTHORITY`: bytes/hash/rows/row_groups, `full_schema`, clock/gamma y
  ambos stats son no-null; `projected_schema=null`.
- `EXPECTED_MISSING`: bytes/hash/rows/row_groups, ambos schemas, clock y gamma
  son null; `before_stat` y `after_stat` son exactamente
  `{exists:false,bytes:null,mtime_ns:null,physical_id:null}`;
  `ignored_reason="EXPECTED_MISSING_STAGE_A"`.

Para presentes, cada stat es exactamente
`{exists:true,bytes:int64,mtime_ns:int64,physical_id:[uint64,uint64]}` y
`ignored_reason=null`. No se omiten claves nullable.

Para históricas, `projected_schema` debe coincidir byte-lógicamente en
nombre/orden/type con upstream; no se inventa nullability ausente de esa
autoridad. Para las tres nuevas, `full_schema` canónico incluye nullability y
metadata Arrow ordenada, codificando bytes key/value en base64, y se compara de
nuevo al cierre. Columnas `underlying_price,bid,ask,delta,implied_vol,theta,
vega,rho` y `gamma`, si existe, deben ser Arrow `double`/float64 como las
autoridades históricas; otro tipo falla, evitando casts silenciosos. Los outputs
reproducen el scalar IEEE-754 leído, incluidos NaN/inf.
`interval_used`, si existe, sólo puede ser scalar integer/floating/decimal o
utf8; en outputs se convierte a null si source null, utf8 intacto si utf8, o
`str(as_py())` para numérico. Otro tipo falla.

## 5. Reloj e identidad options

Sólo datetime Arrow/Python o ISO completo. Numeric/epoch, boolean, date sin hora,
null o malformed son fatales aunque la fila no se seleccione. Naive se interpreta
NY wall-clock; aware se convierte a `America/New_York`; fecha local debe igualar
`trade_date`; hora naive DST ambigua/inexistente es fatal.

Exact-minute exige second/microsecond/nanosecond cero. Subminute válido y
exact-minute fuera de `0..close_i` se cuentan/ignoran, nunca redondean. Null o
malformed nunca se ignora. `minute_i=0` es 09:30; FULL `close_i=390`/391 puntos;
SHORT `close_i=210`/211 puntos.

`clock_local` es siempre cinco caracteres `HH:MM` NY. Para
`underlying_timestamp_raw`, utf8 origen se conserva sin trim; Arrow timestamp se
serializa ISO `YYYY-MM-DDTHH:MM:SS` con exactamente 0/3/6/9 dígitos fraccionales
según unidad s/ms/us/ns, más offset `±HH:MM` si su tipo tiene timezone y sin
sufijo si es naive. Null permanece null. Age se deriva del valor, no del texto.

La fila debe igualar `(symbol.upper(),expiration,trade_date)` de fuente. Right:
`C|CALL -> CALL`, `P|PUT -> PUT`; otro es fatal. Strike es
`Decimal(str(value))`, finito, canonicalizado con
`format(decimal.normalize(),"f")`, en price units sin x1000. Contract key:
`(ticker,expiration,strike_decimal,right)`. Duplicado
`(source_path,contract_key,minute_i)` es fatal, sin dedupe silencioso.

`expiration` y `trade_date` aceptan únicamente scalar Python `date` (no
`datetime`) o string exactamente `YYYY-MM-DD`/`YYYYMMDD`; se normalizan a
`YYYYMMDD` tras validar fecha calendario. Numeric, datetime, whitespace extra u
otro formato fallan. `symbol` y right se trimmean y upper-case; ticker debe
coincidir exactamente después de esa normalización.

## 6. Selector causal 10:30 y gate comparativo real

Por cada `PLANNED` se lee sólo ENTRY y exact-minute 10:30. Arrow batches 65536,
`use_threads=False`, proyección sólo apartado 4. La selección materializa y
evalúa sólo filas 10:30 de la fuente D de cada plan; aunque un mismo archivo
físico pueda ser D de otro plan, no consulta observaciones 10:35/D1/H2 para
elegir. La fase de trayectorias empieza sólo después del fsync de decisiones.

Quote válida: bid/ask reales no bool, finitos, `bid>=0`, `ask>0`, `bid<=ask`.
Candidato además: spot finito `>0`, strike/delta finitos, `ask<=49.95`,
`abs(delta)<=1`; CALL exige `delta>0`, PUT `delta<0`. Sin age/interval filter.
Por side se minimiza:

```text
(abs(abs(delta_float)-0.50),(ask_float-bid_float)/ask_float,strike_float)
```

Las tres cantidades del sort reproducen Python float64 de `ec19`; Decimal se
usa exclusivamente para identidad canónica de strike, no para aritmética.

Se derivan 0..2 por plan sin fabricar ni sustituir. Para el run real, la
comparación predeclarada exige exactamente 3240 decisiones: 3054 H1
(1527x2), 180 Q3 (90x2), seis bridge (3x2). Si el total o reparto no coincide,
se registran conteos y `NO_VALID_CALL|NO_VALID_PUT` y se falla cerrado, sin
outputs finales. Fixtures usan cardinalidad esperada parametrizable. El gate no
lee 10:35, candidates, status, net ni outcomes.

`decision_id` es SHA-256 hex lowercase del JSON compacto UTF-8, sin espacios,
de `[plan_id,ticker,expiration,strike_decimal,right]`; incluye la contract key y
no reutiliza candidate_id histórico. Orden exacto del Parquet:
`(entry_date,ticker_ordinal,right_ordinal)` con ticker `SPY=0,QQQ=1,SPXW=2` y
right `CALL=0,PUT=1`. Schema:

```text
decision_id:utf8,plan_id:utf8,source_authority:utf8(H1|Q3|BRIDGE),
ticker:utf8,entry_date:utf8,expiration:utf8,
right:utf8,strike_decimal:utf8,decision_clock:utf8("10:30"),
decision_minute_i:int16(60),decision_bid:float64,decision_ask:float64,
decision_delta:float64,decision_underlying_price:float64,
relative_spread:float64,selector_distance:float64,source_path:utf8,
source_sha256:utf8,clock_basis:utf8,receipt_time_status:utf8("UNKNOWN"),
interval_used:utf8?,gamma_column_present:bool
```

No execution/scenario/label/outcome/net/qty/policy.

## 7. Trayectoria del mismo contrato D/D1/H2

Después de congelar/fsync las 3240 decisiones se forma por fuente la unión de
claves solicitadas y cada fuente presente se lee una vez por pasada. Para cada
decisión se busca la misma clave exacta en ENTRY/D, INTERMEDIATE/D1 y H2/D2;
nunca strike cercano ni reselección. Fuente missing produce cobertura explícita,
no observación.

Se consideran exact-minute `0..close_i`. Los valores nullable se preservan sin
imputación: `bid,ask,delta,implied_vol,gamma,theta,vega,rho,underlying_price` e
`interval_used` si existe. No se calcula midpoint/return/max/min/target/outcome.

`option_quote_observations.parquet` es global, único por
`(source_path,ticker,expiration,strike_decimal,right,minute_i)` y no repite por
plan:

```text
observation_id:utf8,source_path:utf8,source_sha256:utf8,ticker:utf8,
trade_date:utf8,expiration:utf8,right:utf8,strike_decimal:utf8,
minute_i:int16,clock_local:utf8,clock_basis:utf8,
receipt_time_status:utf8("UNKNOWN"),interval_used:utf8?,
bid:float64?,ask:float64?,delta:float64?,implied_vol:float64?,
gamma:float64?,theta:float64?,vega:float64?,rho:float64?,
underlying_price:float64?,underlying_timestamp_raw:utf8?,
underlying_age_ms:float64?,
underlying_age_status:NATIVE_DERIVED|MISSING_OR_MALFORMED|PROXY_UNKNOWN,
quote_valid:bool
```

`observation_id` es SHA-256 hex lowercase de JSON compacto UTF-8, sin espacios,
de la lista `[canonical_source_path,ticker,expiration,strike_decimal,right,
minute_i]`. Orden exacto:
`(trade_date,ticker_ordinal,expiration,canonical_source_path,right_ordinal,
Decimal(strike_decimal),minute_i)`; Decimal aquí ordena identidad, no selector.

`quote_valid` aplica únicamente las condiciones históricas finitas de bid/ask
del apartado6; filas inválidas y sus valores se almacenan igualmente. Para reloj
nativo, `underlying_timestamp_raw` conserva una representación ISO y, si puede
parsearse, `underlying_age_ms=(timestamp-underlying_timestamp)` en milisegundos
signed, aun si tiene segundos u otra fecha; no es filtro de frescura. Si falta o
es malformed, age null/status `MISSING_OR_MALFORMED` y la fila no aborta. Para
reloj proxy, age siempre null/status `PROXY_UNKNOWN`. Sólo el clock principal
que ubica la snapshot es fatal cuando está null/malformed.

`segment_coverage.parquet` tiene exactamente 9720 filas (3240xD/D1/H2). Roles
y ordinales exactos: `D=0`, `D1=1`, `H2=2`; nunca `ENTRY_DAY` en este output.
Orden `(entry_date,ticker_ordinal,right_ordinal,role_ordinal)`. Schema:

```text
decision_id:utf8,plan_id:utf8,role:utf8,ticker:utf8,segment_date:utf8,
expiration:utf8,right:utf8,strike_decimal:utf8,source_path:utf8,
source_status:PRESENT|MISSING,source_sha256:utf8?,close_i:int16,
expected_minute_count:int16,observed_exact_minute_count:int16,
missing_minute_count:int16,
missing_ranges:list<struct<start_i:int16,end_i:int16>>,
first_observed_i:int16?,last_observed_i:int16?,
ignored_subminute_rows:int64,ignored_out_of_session_rows:int64,
clock_basis:utf8?,gamma_column_present:bool?
```

`expected_minute_count=close_i+1`; rangos inclusivos, ordenados, maximales. Una
quote con precio inválido sigue siendo observación raw; minute sin fila es
missing. No se supone una quote cada minuto.

## 8. Módulo aislado de spot y su interfaz

El archivo futuro es `weekly_zone_event_spot_paths.py`, con tests separados
`test_weekly_zone_event_spot_paths.py`. No importa el builder ni código productor.
El builder `build_weekly_zone_event_value_paths.py` lo llama exactamente así:

```python
extract_spot_paths(
    calendar_rows,
    output_dir,
    authority_documents,
    authority_pins,
    unit_context,
) -> {
    "outputs": {name: {"path": str, "bytes": int, "sha256": str}},
    "counts": {...},
    "admitted_inputs": {
        canonical_path: {"path": str, "bytes": int, "sha256": str}
    },
}
```

`calendar_rows` es una secuencia ya ordenada, sin duplicados, de exactamente
2790 mappings con sólo tres claves: `ticker` (`SPY|QQQ|SPXW`), `date`
(`YYYYMMDD`) y `close_i` (`390|210`). El orden es fecha ascendente y ordinal
`SPY=0, QQQ=1, SPXW=2`. El módulo vuelve a validar orden, unicidad, dominio,
930 fechas por ticker y deriva `FULL` de390 y `SHORT` de210.

`authority_documents` es mapping in-memory con las seis autoridades de 2.3 ya
parseadas, bajo claves `h1_inventory`, `h1_inventory_manifest`, `h1_manifest`,
`q3_inventory`, `q3_inventory_manifest`, `q3_manifest`. `authority_pins` usa
las mismas claves y valores `{path,bytes,sha256}` exactos de 2.3. El módulo no
reabre ni rehashea una serialización parseada: valida schema/conteos/cross-pins
internos y valores exactos de `authority_pins`. El builder ya validó los bytes y
los incluye en closing rehash.

`output_dir` es staging compartido y puede contener outputs options; sólo
`cache_admission.jsonl`, `spot_paths.parquet` y `spot_coverage.jsonl` deben estar
ausentes. El módulo los crea, cierra/fsync y devuelve pines; no promociona raíz.

`unit_context(kind:str, identity:str, paths:list[str])` es context manager
inyectado. Cada una de las 2790 identidades entra una vez con
`kind="CACHE_SPOT_PATH"`, `identity="{ticker}:{date}"` y paths canónicos. H1
AVAILABLE usa `[features_metadata_json,raw_cache_metadata_json,raw_cache_npz]`;
Q3 AVAILABLE `[raw_cache_metadata_json,raw_cache_npz]`; missing lista vacía. Su
`__enter__` persiste gate oficial, STARTED y fsync antes de cualquier open; el
mapping mutable producido por `yield` recibe counts/pins pre/post; `__exit__`
persiste COMPLETED o ERROR y fsync. El módulo no puede abrir nada fuera del
contexto ni anidar contextos. El módulo no introspecciona una implementación
arbitraria del context manager; garantiza el orden llamándolo antes de open y
rellenando el mapping antes de salir. Fixtures observables prueban ese orden.
Antes de salir, el módulo debe fijar `details["substeps"]` exactamente a
`["ADMIT_SPOT_METADATA","LOAD_SPOT_TRIPLETS"]` para AVAILABLE y a
`["DECLARED_MISSING"]` para missing. El `CACHE_SPOT_PATH` único persiste esos
details al completar; los substeps no crean contexts, gates ni children nuevos.

El módulo posee sus validaciones de path/stat/hash. Hace hash before/after por
unidad. `admitted_inputs` contiene exactamente los archivos que abrió el módulo
(features-metadata H1, cache-metadata y NPZ), indexados por path absoluto
canónico; no incluye authorities parseadas ni rutas missing/no abiertas. El
builder hace rehash global al cierre. No hay pools/workers.

## 9. Cadena y lectura spot

H1 (2625 identidades) se resuelve:

```text
h2_context_1030_01/inventory.json
 -> COMPLETE.features_metadata.path + .sha256
 -> features-metadata JSON compacto
 -> source_path raw cache NPZ + sibling raw-cache metadata JSON
 -> binding.source_sha256 + binding.source_metadata_sha256
```

El features-metadata JSON es la primera ruta H1; el raw-cache metadata JSON se
deriva únicamente como sibling nominal del `source_path` NPZ y su hash debe ser
`binding.source_metadata_sha256`. El NPZ debe igualar `binding.source_sha256`.
La identidad del inventario debe tener `status="COMPLETE"`, ticker/date exactos
y pin exacto de `features_metadata`. El features-metadata exige
`version="SESSION_CLOCK_FEATURES_V1"`, ticker/date exactos,
`outcomes_read=false`, `source_path` en uno de los dos layouts permitidos y
`binding.source_sha256`/`binding.source_metadata_sha256` exactos. Su pin a un
features NPZ se valida como metadata pero ese NPZ no se abre.

El cache-metadata exige versión/ticker/date exactos, `npz_bytes` igual al NPZ,
campo `sha256` igual al SHA del NPZ y `array_schema` con al menos
`time_ns:{shape:[n],dtype:"int64"}`, `spot:{shape:[n],dtype:"float64"}` y
`spot_valid:{shape:[n],dtype:"bool"}`, donde n=391/211. Puede declarar arrays
adicionales, que no se acceden. Q3 aplica las mismas comprobaciones desde el par
pinneado por `raw_cache_files`, salvo que no existe features-metadata intermedio.

Layouts únicos: FULL
`D:\GexResearchArtifacts\level_oracle_20261018\cache_v1\{ticker}\{date}.{json,npz}`,
versión `LEVEL_DAILY_CACHE_V1`; SHORT
`D:\GexResearchArtifacts\level_oracle_20261018\session_clock_dataset_v1\short\{ticker}\{date}\cache.{json,npz}`,
versión `SESSION_CLOCK_CACHE_V1`. Nunca se abre el features NPZ.

Q3 se resuelve sólo desde 306 `raw_cache_files` del manifest: un JSON y un NPZ
para cada una de 153 identidades, versión `LEVEL_DAILY_CACHE_V1`; nunca
`state60`. Cada AVAILABLE exige un par único. Duplicado, par incompleto,
identidad/version/path/binding/bytes/hash discordante es fatal.

Antes de abrir cualquiera de features-metadata JSON, cache-metadata JSON o NPZ,
se valida ruta absoluta nominal bajo su root/layout exacto, componentes lexicales
sin `..`, `lstat` de todos los ancestros, archivo regular, no symlink/junction/
reparse/hardlink ambiguo/alias ni identidad física compartida, y stat/bytes/hash.
Los mismos controles se repiten al cierre de la unidad. Sólo entonces el NPZ se
abre con `numpy.load(path,allow_pickle=False)`. Consultar
`npz.files` para comprobar nombres no lee arrays y está permitido; el único
acceso `npz[name]` permitido es `time_ns`, `spot`, `spot_valid`. Otras arrays
pueden existir pero no se acceden.

- `time_ns`: int64, NY wall-clock naive (nunca UTC), longitud 391 FULL/211
  SHORT, inicio `YYYY-MM-DDT09:30`, paso 60000000000 ns, fin 16:00/13:00;
  índice59=10:29 e índice60=10:30.
- `spot`: float64 misma shape.
- `spot_valid`: bool misma shape. True implica spot finito y positivo. False
  puede codificar edad/desacuerdo además de no-finito y se conserva; no se exige
  la equivalencia inversa y no se rellena/arrastra.

Tras lectura se repiten stat/bytes/hash. Los seis H1 y doce Q3 missing son estado
declarado por autoridades upstream: no se resuelve, abre ni inspecciona ninguna
ruta nominal no admitida, aunque pudiera existir un archivo extra. Esto difiere
de los 16 Parquets weekly de apartado4, cuya ausencia física sí se comprueba.
Calendario obligatorio: 2766
FULL (2748 available+18 missing) y24 SHORT available; total2790/available2772.

`cache_admission.jsonl`, exactamente 2790 objetos ordenados fecha/ticker:

```text
ticker:str,ticker_ordinal:int,date:str,session_kind:FULL|SHORT,close_i:int,
cache_status:AVAILABLE|MISSING,missing_reason:str?,authority:H1|Q3,
feature_metadata_path:str?,feature_metadata_bytes:int?,
feature_metadata_sha256:str?,cache_metadata_path:str?,
cache_metadata_bytes:int?,cache_metadata_sha256:str?,
npz_path:str?,npz_bytes:int?,npz_sha256:str?,cache_version:str?,
binding_source_sha256:str?,binding_source_metadata_sha256:str?,
stats:{feature_metadata:{before:stat,after:stat}?,
cache_metadata:{before:stat,after:stat},npz:{before:stat,after:stat}}?
```

En este schema `stat` es exactamente
`{exists:bool,bytes:int64?,mtime_ns:int64?,physical_id:[uint64,uint64]?}`.
`cache_metadata_*` siempre designa el sidecar del raw cache, nunca el
features-metadata H1.
Para missing, paths, pins y `stats` son null sin `stat` físico. Para available,
`exists=true` y los nullable del stat son no-null; regular/no-link se valida como
guard pero no añade otra forma de stat.

La lista missing es cerrada: H1 QQQ/SPY en 20260401, 20260409 y 20260415;
Q3 QQQ/SPY en 20260701, 20260707, 20260710, 20260716, 20260826 y 20260901.
Otro reparto falla.

`spot_paths.parquet` es LONG y tiene exactamente 1086570 filas: 1079532
AVAILABLE y7038 densas de 18 FULL missing. Orden: fecha, ticker ordinal
`SPY,QQQ,SPXW`, `minute_i`:

```text
ticker:utf8,ticker_ordinal:int8,date:utf8,session_kind:utf8,
cache_status:AVAILABLE|MISSING,minute_i:int16,time_ns:int64,
spot:float64?,spot_valid:bool,missing_reason:utf8?,authority:H1|Q3,
feature_metadata_path:utf8?,feature_metadata_sha256:utf8?,
cache_metadata_path:utf8?,cache_metadata_sha256:utf8?,
cache_npz_path:utf8?,cache_npz_sha256:utf8?,cache_version:utf8?
```

AVAILABLE reproduce exactamente eje, valor y mask. Si `spot_valid=false`, el
spot almacenado se preserva incluso NaN/inf; la mask no se reinterpreta. MISSING
crea eje determinista con spot null y mask false: no inventa observación.

`spot_coverage.jsonl`, exactamente 2790 objetos ordenados, schema:

```text
ticker:str,ticker_ordinal:int,date:str,session_kind:FULL|SHORT,
cache_status:AVAILABLE|MISSING,missing_reason:str?,expected_count:int,
valid_count:int,invalid_count:int,first_valid_i:int?,last_valid_i:int?,
invalid_ranges:list<{start_i:int,end_i:int}>,metadata_path:str?,
metadata_sha256:str?,npz_path:str?,npz_sha256:str?
```

No contiene agregados de precio.

## 10. Outputs y publicación atómica

Raíz final exclusiva:
`D:\GexResearchArtifacts\weekly_multiday_20261101\weekly_zone_event_value_paths_01`;
observer exclusivo `...\weekly_zone_event_value_paths_observer_01`. Ambas deben
estar ausentes; no resume ni adopta staging.

Outputs finales:

1. `source_admission.jsonl` — 2784.
2. `decision_contracts.parquet` — 3240.
3. `option_quote_observations.parquet` — unión global deduplicada.
4. `segment_coverage.parquet` — 9720.
5. `cache_admission.jsonl` — 2790.
6. `spot_paths.parquet` — 1086570.
7. `spot_coverage.jsonl` — 2790.
8. `summary.json`.
9. `manifest.json`.

JSON compacto UTF-8, claves ordenadas, JSONL LF final. Todo Parquet usa schema
fijo, orden determinista, `use_threads=False`, batches y row groups máximos de
65536, `version="2.6"`, `data_page_version="1.0"`, `compression="zstd"`,
`compression_level=3`, `use_dictionary=True`, `write_statistics=True` y
metadata de versión. Además, observations cierra un row group por source/day y
spot cierra uno por ticker/day (211 o391 filas); nunca mezcla unidades en un
row group. No se exige hash Parquet reproducible entre versiones de librería:
sí se exige pin del entorno, schema, filas, orden y hash de los bytes producidos.
Staging hermano, close+fsync+hash y replace atómico de raíz completa. No copia
raw/cache. Antes de staging y cada output se exigen >=2000000000 bytes libres D:.

Summary reconcilia Stage A 1620/1164/6, admission 2784, bases de reloj, selector
3240 por autoridad/side, lecturas únicas, observaciones/cobertura, ignored rows y
spot identities2790=2772+18, con1086570 path rows=1079532+7038. Manifest pinea
contrato, código/tests/reviews/launcher,
autoridades, todos los admitted inputs y outputs.

Flags exactas:

```json
{"actions_read":false,"candidates_read":false,
"context_feature_arrays_read":false,"economic_evaluation_performed":false,
"fit_performed":false,"inference_performed":false,"labels_read":false,
"models_read":false,"option_raw_values_read":true,"outcomes_read":false,
"parquet_footers_read":true,"pnl_computed":false,
"promotion_approved":false,"replay_performed":false,
"risk_or_qty_computed":false,"selected_policy":null,
"spot_cache_arrays_read":true,"technical_ready":false}
```

`summary.json` no admite claves top-level adicionales:

```text
schema="weekly_zone_event_value_paths_summary_v1"
status="COMPLETE_OUTCOME_FREE_VALUE_PATHS"
created_utc:str
stage_a:{sessions:930,ticker_days:2790,planned:1620,no_series:1164,
terminal:6,references:4860,unique_sources:2784}
option_admission:{present:2768,missing:16,historical:2765,
first_authority:3,native_historical:1562,proxy_historical:1203,
native_new:int,proxy_new:int}
selector:{plans:1620,decisions:3240,h1:3054,q3:180,bridge:6,
calls:1620,puts:1620,no_valid_call:0,no_valid_put:0}
option_paths:{segments:9720,observations:int,selector_source_reads:1620,
trajectory_source_reads:2768,
ignored_subminute_rows:int,ignored_out_of_session_rows:int,
missing_minutes:int}
spot:{identities:2790,available:2772,missing:18,full:2766,short:24,
available_rows:1079532,missing_rows:7038,path_rows:1086570,
valid_rows:int,invalid_rows:int}
outputs:{name:{path:str,bytes:int,sha256:str,rows:int}}
flags:<objeto exacto anterior>
limitations:[str]
```

`limitations` contiene exactamente, en este orden: timestamps almacenados no
prueban receipt vivo; proxy tiene age desconocida; samples minute no prueban
touch intraminute; no se leyó outcomes; no se hizo evaluación económica.

`manifest.json` tampoco admite claves top-level adicionales:

```text
schema="weekly_zone_event_value_paths_manifest_v1"
status="COMPLETE_OUTCOME_FREE_VALUE_PATHS"
created_utc:str
implementation_pins:{builder,spot_module,builder_tests,spot_tests,contract,
builder_final_review,spot_final_review,runtime_binding,launcher,
resource_helper}:pin
authority_inputs:{stage_a_entry_plan,stage_a_weekly_sources,stage_a_summary,
stage_a_manifest,stage_a_audit,stage_a_audit_manifest,stage_a_audit_exit,
h1_inventory,h1_inventory_manifest,h1_manifest,q3_inventory,
q3_inventory_manifest,q3_manifest,bridge_inventory,bridge_inventory_manifest,
bridge_manifest,unified_calendar,h1_context_inventory,
h1_context_inventory_manifest,h1_context_manifest,q3_context_inventory,
q3_context_inventory_manifest,q3_context_manifest,selector_builder_v2,
normalization_pilot}:pin
admitted_option_sources:{canonical_path:pin}
admitted_spot_inputs:{canonical_path:pin}
outputs:{name:{path:str,bytes:int,sha256:str,rows:int}}
counts:{option_sources:2784,decisions:3240,segments:9720,
spot_identities:2790,spot_rows:1086570}
flags:<objeto exacto anterior>
environment:{python:str,numpy:"2.3.5",pyarrow:"23.0.1",ruff:"0.15.20",
pytest:"9.0.2"}
```

`pin` es exactamente `{path:str,bytes:int,sha256:str}`. En summary, `outputs`
usa sólo los siete data outputs (1–7). En manifest usa esos siete más
`summary.json`; manifest nunca se autopinnea. `rows` es1 para summary y número
de objetos para JSONL. Los maps por path se ordenan por canonical path.

`admitted_option_sources` contiene exactamente las 2768 fuentes PRESENT; las16
missing carecen de pin y existen sólo en `source_admission.jsonl`/counts.
`admitted_spot_inputs` contiene exactamente 8163 paths abiertos por el módulo:
7857 H1 (2619 x features-metadata/cache-metadata/NPZ) y306 Q3
(153 x cache-metadata/NPZ). Authorities parseadas y missing no pertenecen a ese
map. `selector_source_reads` y `trajectory_source_reads` cuentan unidades de
fuente abiertas en su pasada, no batches ni filas.

## 11. Recursos, journal y estabilidad

Un único child productor iterativo en CPU lógica0; sin pool/workers. Helper
oficial exacto
`C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\research_papers\JEPA\level_oracle_20261018\launch_monthly_test_index_v2_audit_20261024.py`,
SHA-256 `3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046`.
El gate se ejecuta antes de cada pasada global, cada unidad raw/footer/source,
cada una de las exactamente 2790 identidades `CACHE_SPOT_PATH` (sus dos o tres
inputs se abren dentro de ese único contexto), cada output y cada archivo del
closing rehash. No se crea un gate/context adicional por sidecar/NPZ. Se exige
RAM física disponible y `free_commit`, ambos >=2000000000 bytes;
disk free D: también >=2000000000. Variables en `1`:
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS`, `BLIS_NUM_THREADS`,
`ARROW_NUM_THREADS`, `POLARS_MAX_THREADS`, `TBB_NUM_THREADS`,
`NUMBA_NUM_THREADS`; además `CUDA_VISIBLE_DEVICES=-1`.

El wrapper retiene handles y espera al child. Journal append-only en observer
con `STARTED`/`COMPLETED` o `ERROR` por stage y unidad, identidad, pins pre/post,
gate y counts; cada append flush+fsync. Stages mínimos:
`ADMIT_AUTHORITIES`, `ADMIT_OPTION_FOOTERS`, `SELECT_1030`,
`STREAM_OPTION_PATHS`, el único `CACHE_SPOT_PATH` por identidad con substeps
`ADMIT_SPOT_METADATA`/`LOAD_SPOT_TRIPLETS` o `DECLARED_MISSING`,
`WRITE_OUTPUTS`, `CLOSING_REHASH`.

Cada raw/sidecar/NPZ tiene stat+hash before/after; `CLOSING_REHASH` recalcula
todos los admitted inputs, no muestra. Cambio => exit efectivo no cero, sin raíz
final. Observer conserva stdout/stderr, metadata de proceso, snapshots, journal
y `exit.json`.

## 12. Secuencia de implementación y fixtures

Este contrato se publica y verifica byte-exact antes de fixtures. Luego se crean
por separado módulo spot+tests y builder+tests; reviews estáticas, una suite formal
CPU0/10-vars/gate, reviews finales, binding/launcher publicados, y sólo entonces
un run real. Dependencias runtime permitidas: stdlib, NumPy2.3.5 y PyArrow23.0.1
con APIs estables de esa versión; sin pandas necesario, instalaciones ni imports
de productores cerrados.

Fixtures focales:

- clock naive/aware NY, offsets/DST/date mismatch, epoch/null/malformed,
  seconds/fractions, subminute contado/ignorado, FULL391/SHORT211/out-session;
- right aliases, Decimal price units, quotes inválidas, dirección delta explícita,
  ask49.95/>, desempate; expected decision count parametrizado;
- independencia al mutar 10:35/D1/H2 y label-trap; guard de apertura prohibida
  candidates/outcomes/features/state60/cuarta array;
- duplicado source/key/minute fatal, unión multi-plan leída una vez, missing
  source/minute, `interval_used` sin filtro y gamma ausente/null;
- 2765 hashes históricos, tres primeras autoridades, presencia/hash/schema drift,
  traversal/symlink/reparse/hardlink/alias y población exacta de los tres
  `binding_kind`, incluido stat missing;
- H1 FULL/SHORT y Q3 pair, versión/binding/par incompleto/duplicado, eje60e9,
  dtype/shape/mask, 6+12 missing y dos Jul10 no-weekly;
- interfaz `extract_spot_paths`, unit context begin-before-open/end/error, outputs
  y admitted_inputs exactos, 1086570 long/2790 coberturas, staging interrumpido;
- schemas/orden/cardinalidades/flags y closing rehash total.

## 13. Auditor independiente

Implementación separada que no importa productor: revalida autoridades/security,
relee footers y proyecciones raw, rederiva las 3240 decisiones sólo10:30 y unión
de keys, reconstruye observaciones/9720 coberturas, y recarga sólo las tres arrays
spot. Compara fila/schema/orden/hash/summary; no basta manifest o hash-only.

Verifica rutas prohibidas no abiertas, no dependencia 10:35/D1/H2, source una
vez por pasada, 18 spot missing explícitos, protocolos unit context y rehash
total. Requiere su código/tests/reviews/binding/launcher, publicación y único run
observado. Sólo PASS+exits0 permite llamarlo auditado; nunca rentable.

## 14. Cierre

Productor y auditor exit0 retenido, pins estables, raíces exclusivas, conteos
reconciliados y flags prohibidas false. Aparición/ausencia inesperada, drift,
clock inválido, duplicado o decisión no reproducible falla sin fallback,
reselección, imputación o adopción parcial. Eventos/escenarios/EV requieren otro
contrato previo y no se infieren de estos paths.
