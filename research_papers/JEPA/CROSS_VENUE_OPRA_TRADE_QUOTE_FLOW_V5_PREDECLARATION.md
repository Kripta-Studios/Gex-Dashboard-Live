# CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5 — predeclaración

**Congelada:** 2026-07-25 Europe/Madrid, después de cerrar V1–V4 y cash-only,
antes de consultar un solo valor `trade_quote`, feature, outcome o reloj de
outcome 2026.

## Hipótesis y novedad económica

La hipótesis única es que el desequilibrio de prints OPRA 0DTE ejecutados
contra el NBBO anterior contiene información direccional que no existe en
OHLC/`volume/count`, snapshots NBBO ni deformación de superficie agregada.

V5 no reutiliza `calendar_rr_pressure`, Greek, IV, OI, walls, VIX, cash
features, breadth, Globex Yahoo ni features de las familias cerradas. Los cinco
IDs Greek/IV de junio 2026 no se intersectan, reparan, excluyen ni recapturan:
V5 no abre esos ficheros.

Todo 2023–2025 ya es development visto. La evaluación 2024→2025 que se define
debajo es solo una falsificación walk-forward exigente. El primer outer posible
sería 2026 y permanece cerrado hasta PASS completo, auditoría, freeze y commit.

## Fuente exacta y paridad live

Histórico: ThetaData v3 Options Standard,
`/v3/option/history/trade_quote`, una captura por `sensor/trade_date`, con:

```text
symbol={QQQ|SPY}
expiration=trade_date
strike=*
right=both
date=trade_date
start_time=09:30:00.000
end_time=10:34:59.999
exclusive=true
format=ndjson
```

Cada raw HTTP se conserva byte-exact, junto a status/headers seguros, params,
Theta Terminal JAR/Java/runtime, hostname de captura, código y SHA-256. No se
acepta `trade` sin quote, quote con timestamp igual/posterior, intervalo 1m,
snapshot, `at_time`, current-provider replacement ni otra fuente.

Live/shadow futuro: antes de 09:30 se enumeran todos los strikes de
`expiration=today`, se suscriben CALL y PUT a Quote Stream y Trade Stream
Standard, y se conservan mensajes nativos append-only. Para cada trade se une
la quote de mayor timestamp estrictamente menor. Solo entran trades
`<10:35:00.000`; el collector espera hasta 10:35:30 ET para absorber orden de
recepción y debe publicar `feature_available_at<=10:35:30`. Si el total supera
10.000 quote streams o 15.000 trade streams, falta un contrato, hay reconnect,
gap o mensaje tardío no reconciliado, la sesión falla; no se seleccionan
strikes ni se usa Full Trade Stream Professional como reparación.

La paridad futura debe reproducir de raw historical y raw live, byte por byte
en contrato/campos y numéricamente en las features, al menos 20 sesiones shadow
consecutivas antes de cualquier integración. Esto no autoriza modificar live.

Documentación primaria congelada por URL y fecha en
`CAUSAL_SOURCE_INVENTORY_20260725.md`.

## Mapping, universo y clocks

Mapping inmutable:

- QQQ ← tape QQQ;
- SPY ← tape SPY;
- SPXW ← tape SPY.

Una decisión por target y sesión normal o media jornada válida. Features usan
solo `[09:30:00.000,10:35:00.000)` ET. Entrada económica posterior: open
10:36 ET; salida open13:36 ET; hold180m; nunca cruza cierre RTH. Las medias
jornadas se excluyen por calendario predeclarado porque 13:36 no existe, no por
datos ni outcome. No hay nearest/as-of/fill ni exclusión posterior de fechas.

El universo de contratos es toda la cadena exact-0DTE de QQQ/SPY. No hay filtro
por strike, delta, moneyness, premium, volumen o resultado.

## Normalización de prints

El raw preserva todos los registros. Alpha usa únicamente condiciones OPRA
`REGULAR=0` y `AUTO_EXECUTION=18`; todas las demás se cuentan audit-only. Una
fila alpha exige:

```text
expiration == trade_date
trade_timestamp in [09:30,10:35)
quote_timestamp < trade_timestamp
size > 0
price > 0
bid > 0
ask > bid
right in {CALL,PUT}
finite(price,bid,ask,size,strike)
```

No se afirma aggressor observado. Se define `print_side` de forma mecánica:

```text
+1 si price >= ask
-1 si price <= bid
+1 si bid < price < ask y price > midpoint
-1 si bid < price < ask y price < midpoint
 0 si price == midpoint
```

`premium_dollars = price * size * 100`. Duplicados exactos por
`(symbol,expiration,strike,right,trade_timestamp,sequence,exchange,price,size)`
fallan cerrado; no se deduplican silenciosamente. Quote age, condiciones
excluidas, rows no firmables y crossed/locked se reportan solo como calidad y
no entran al modelo.

## Features fijas

Tres ventanas exactas:

```text
FULL = [09:30,10:35)
W15  = [10:20,10:35)
W5   = [10:30,10:35)
```

Para cada ventana se calculan ocho campos, con denominador cero como fallo de
evento, nunca imputado:

1. `directional_premium_imbalance` =
   `(sum(side*premium)_CALL - sum(side*premium)_PUT) / sum(premium)`;
2. `directional_contract_imbalance` =
   `(sum(side*size)_CALL - sum(side*size)_PUT) / sum(size)`;
3. `directional_print_imbalance` =
   `(sum(side)_CALL - sum(side)_PUT) / n_prints`;
4. `call_put_premium_imbalance` =
   `(premium_CALL-premium_PUT)/(premium_CALL+premium_PUT)`;
5. `call_put_contract_imbalance` =
   `(size_CALL-size_PUT)/(size_CALL+size_PUT)`;
6. `call_put_print_imbalance` =
   `(prints_CALL-prints_PUT)/(prints_CALL+prints_PUT)`;
7. `log_total_contracts = log1p(sum(size))`;
8. `log_total_premium = log1p(sum(premium_dollars))`.

Son 24 features sensor en orden `FULL`, `W15`, `W5`, más one-hot target
`QQQ/SPXW/SPY`: 27 columnas. No se añaden quality flags, Greeks, cash returns,
spot, strike statistics, lags, interactions o selección de features.

## Modelo y acción

Un único modelo pooled por fold:

```text
Pipeline(
  StandardScaler(),
  LogisticRegression(
    penalty="l2", C=0.1, solver="liblinear",
    class_weight=None, max_iter=2000, random_state=0
  )
)
```

No hay imputación: solo filas completas selladas. Target de train:
`open_13:36/open_10:36 > 1`. Probabilidad `>=0.5` produce LONG y `<0.5` SHORT.
No hay abstención, confidence filter, sample weights, grid, calibración,
modelo por ticker, ensemble, refit mensual ni selección de signo.

## Folds development y costes

- Fold D2024: fit pooled con 2023 completo; test 2024 completo.
- Fold D2025: fit pooled con 2023+2024 completos; test 2025 completo.

El fold 2025 solo se calcula después de persistir D2024, pero ambos son
development ya visto. Entrada/salida cash son opens exactos 10:36/13:36,
retorno logarítmico firmado y coste round-trip primario1bp. Costes2/3bps son
sensibilidades no selectivas. Una posición por ticker/día; no overlap.

## Gates outcome-free del data gate

Antes de cualquier outcome se exige:

- exactamente QQQ/SPY, 2023-01-01..2025-12-31 y expiration==trade date;
- raw/parquet/session manifests atómicos y reanudables, todos rehasheados;
- schema y params exactos; timestamps ET nativos y quote estrictamente previa;
- cero raw faltantes, HTTP no-200, stagers o source-hash mismatches;
- coverage de evento válido >=90% por sensor-año;
- al menos 13 eventos válidos en cada sensor-mes;
- CALL y PUT presentes en FULL/W15/W5;
- 24 features finitas y al menos dos valores distintos por sensor-año;
- valor modal de cada feature <99,5%; cero columnas constantes;
- coverage firmable por premium y por contratos >=80% por sensor-año;
- source inventory, feature view, runtime, builder y manifests con SHA-256.

Cualquier fallo cierra V5 sin retirar features, relajar condiciones, cambiar
ventanas, excluir fechas, seleccionar strikes o consultar outcomes. Un auditor
independiente debe reparsear raw, rehashear fuentes y recomputar todas las
features/gates sin importar el builder. Gate y auditor se versionan antes del
evaluator.

## Gates económicas development

Se reportan los 72 ticker-año-meses 2024–2025 y también agregados, pero solo
autoriza avance el criterio conjuntivo. Para cada ticker en cada año:

- PF `>1,20` a1bp;
- WR `>45%`;
- neto `>0`;
- `>=13` trades en cada mes;
- PnL `>0` en cada uno de los doce meses.

QQQ, SPXW y SPY, y 2024 y 2025, deben pasar simultáneamente. No se selecciona
por ticker, sensor, año, ventana, feature, signo o coste. Un solo fallo produce
`CLOSED_DEVELOPMENT_GATE` y prohíbe abrir 2026.

## Hashes y fronteras de versión

Autoridades outcome-free exactas sobre las que se congela esta familia:

| Autoridad | SHA-256 antes de V5 |
| --- | --- |
| `main` / `origin/main` | `8ba155f34c58a9e206ae132bc1b3161f9bc8c449` |
| `CAUSAL_SOURCE_INVENTORY_20260725.md` | `bd673f74c7be365a1ef5204176beea7fb719ec93692aebf236fa7037ec9fbcfc` |
| `ECONOMIC_FAMILY_REGISTRY.md` base | `be5bdedb01b18b77c96ae5aea8202a32ad3c5d12a0e43e26e6dc621012342519` |
| gate V4 2026 fail-closed | `cf4e8312d58f32960bc85650a3508492bb930bb65d61ded11c12391ee47bb2b2` |
| diagnóstico cash-only post-V4 | `0035419f357689c6fc1c0f171dfbd93ae7ca4ea15a3522adfb5d1c78370840fe` |

La documentación web se consultó el 2026-07-25. Sus semánticas relevantes
quedan transcritas en este contrato; una modificación posterior del proveedor
no cambia silenciosamente V5 y debe fallar en la validación de schema/params.

La predeclaración debe quedar committed/pushed desde HEAD limpio antes de:

- llamar a `list/strikes`, `list/dates`, `history/trade_quote` o un stream;
- leer cualquier valor de fuente;
- implementar una transformación que haya visto valores;
- leer opens10:36/13:36 2024–2025 para V5.

El capture/data gate sellará SHA-256 de cada raw, parquet, manifest, response
inventory, Terminal JAR, Java, Python lock, builder, predeclaración e
inventario. El freezer económico sellará además feature view, auditoría,
event IDs, underlying sources, modelo/scaler/coefs y evaluator. Cualquier hash
distinto falla antes del primer outcome de su fase.

## 2026, opción física y producción

Solo un PASS development completo y auditado autoriza: data gate OPRA 2026
outcome-free, auditor independiente, final fit 2023–2025, runner 2026 frozen y
commit/push. Entonces 2026 se ejecutaría una sola vez y se auditaría; no hay
refit mensual ni reparación de fechas.

Un PASS cash 2026 tampoco autoriza live. Después se exige payoff de opción
ask→bid, hold30–180m, no-overlap, `reject_while_open` y paridad raw/features/
acción historical-live. La primera integración, si el usuario la autoriza,
mantendrá `paper_order_intents=true`. Durante V5 no se modifica ni despliega
`services/`, `bots/`, `systemd/` o el paquete live.
