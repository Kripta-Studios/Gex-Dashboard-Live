# Predeclaración de admisión de fuente OPRA externa

**Fecha:** 2026-07-26 Europe/Madrid.

**Estado:** `AWAITING_EXTERNAL_CREDENTIAL_AND_PARITY_SHADOW`.

Este documento no predeclara V8, un modelo, features económicas ni una
evaluación. Fija únicamente cómo decidir, sin outcomes, si una fuente externa
puede suministrar la medición causal que falta tras V4R2/V7. No autoriza una
compra, una llamada de mercado, una descarga histórica ni cambios live.

```text
provider_endpoint_accessed=false
provider_credential_present=false
provider_purchase_authorized=false
market_value_accessed=false
outcome_accessed=false
dataset_created=false
model_predeclared=false
production_modified=false
```

## Selección documental

### Candidato primario: Massive Options Advanced

Massive es el único candidato autoservicio encontrado que, según su
documentación oficial, ofrece conjuntamente:

- trades de opciones tick-level desde 2014, con timestamps nanosegundo;
- quotes top-of-book desde 2022-03-07, con timestamps nanosegundo;
- REST histórico de trades, quotes y contratos activos/expirados;
- WebSocket real-time de trades y quotes;
- cinco o más años de histórico en el plan Options Advanced.

Fuentes oficiales:

- [plan Options Advanced](https://massive.com/pricing?product=options);
- [flat files de trades](https://massive.com/docs/flat-files/options/trades);
- [flat files de quotes](https://massive.com/docs/flat-files/options/quotes);
- [REST de trades](https://massive.com/docs/rest/options/trades-quotes/trades);
- [REST de quotes](https://massive.com/docs/rest/options/trades-quotes/quotes);
- [referencia de contratos](https://massive.com/docs/rest/options/contracts);
- [WebSocket de opciones](https://massive.com/docs/websocket/options/overview);
- [trades live](https://massive.com/docs/websocket/options/trades);
- [quotes live](https://massive.com/docs/websocket/options/quotes).

No se da por probada la paridad. REST documenta timestamps SIP/participant en
nanosegundos y correcciones de trade, mientras los mensajes WebSocket
documentan timestamp en milisegundos y no exponen en la misma página un campo
de corrección equivalente. Además, la documentación limita cada conexión live
a 1.000 contratos de opciones. Estas diferencias son gates, no detalles que el
capturador pueda reinterpretar.

### Candidatos no elegidos

Databento OPRA ofrece `TCBBO`, que incorpora el NBBO inmediatamente anterior a
cada trade, y timestamps de evento/recepción. Sin embargo, su propia
documentación sitúa `TCBBO` y `CMBP-1` desde 2023-03-28; antes de esa fecha hay
histórico trade y `CBBO-1m`, pero no el mismo contrato microestructural estricto
para enero/febrero de 2023. No cumple el histórico uniforme exigido.

Fuentes oficiales:

- [dataset OPRA.PILLAR](https://databento.com/docs/venues-and-datasets/opra-pillar);
- [disponibilidad de schemas OPRA](https://databento.com/blog/opra-improvements-coming-soon);
- [migración y profundidad histórica](https://databento.com/blog/opra-migration).

Cboe DataShop documenta Option Trades con NBBO en el momento del trade desde
2012, pero no queda fijada en las páginas públicas consultadas una traducción
live autoservicio con exactamente el mismo schema, correcciones y contrato de
timestamps. Permanece alternativa sujeta a contrato escrito del proveedor, no
fuente admisible hoy.

Fuente oficial:

- [Cboe Option Trades](https://datashop.cboe.com/option-trades).

## Dependencia externa exacta

Para iniciar el preflight se requieren ambos elementos:

1. suscripción Massive Options Advanced activa y autorizada por el usuario;
2. credencial entregada como `MASSIVE_API_KEY`, nunca escrita en Git, logs,
   manifests, raw ni documentación.

El precio publicado consultado el 2026-07-26 es USD 199/mes para uso individual
no profesional. Es información documental, no autorización de compra. Un
cambio de plan, entitlement, límite o schema antes del preflight obliga a
actualizar y versionar este contrato sin leer valores.

Antes del primer mensaje de mercado también debe existir un
`preflight_universe.json` dentro del repositorio, committed y pushed desde
`main`, con exactamente cinco sesiones futuras ordenadas. El capturador exige
la siguiente fecha pendiente y el gate consume las cinco; no se pueden
sustituir o escoger fechas después de ver cobertura, paridad o actividad.

## Universo de admisión

La admisión usa únicamente sensores QQQ y SPY. El mapping económico posterior
queda inmutable:

```text
QQQ  <- QQQ
SPY  <- SPY
SPXW <- SPY
```

Para cada sesión, la referencia de contratos debe enumerar point-in-time todos
los contratos QQQ/SPY con:

- `expiration_date == trade_date`;
- `as_of == trade_date`;
- activo o expirado según corresponda a la consulta histórica;
- ticker OSI, put/call, strike, expiración y subyacente preservados.

No se permite construir el universo desde contratos que hoy sigan listados,
desde una cadena posterior ni desde strikes seleccionados por outcomes. El raw
de referencia y toda la paginación se conservan inmutables.

El preflight no descarga el mercado completo. Consulta REST por cada contrato
0DTE enumerado y limita trades/quotes al intervalo 09:30:00–10:35:00
America/New_York, incluyendo solo el guard temporal mínimo anterior a 09:30
que se predeclare en el capturador para resolver el primer quote. Ese guard no
puede generar features fuera de la sesión.

## Schema canónico de paridad

Cada evento raw conserva el payload íntegro. La vista canónica mínima contiene:

```text
provider
contract_ticker
underlying
trade_date
event_kind
sip_timestamp_raw
sip_timestamp_ms
participant_timestamp_raw
sequence_number
trade_price
trade_size
trade_exchange
trade_conditions
trade_correction
bid_price
ask_price
bid_size
ask_size
bid_exchange
ask_exchange
arrival_timestamp_utc
source_transport
raw_sha256
```

`sip_timestamp_ms` es el timestamp histórico nanosegundo truncado, nunca
redondeado, a milisegundo; el live conserva su timestamp documentado en
milisegundos. Los campos no aplicables son null explícito, no cero.

Un trade solo puede usar el último quote del mismo contrato con
`quote.sip_timestamp_ms < trade.sip_timestamp_ms`. Todo quote en el mismo
milisegundo que el trade queda ambiguo y no es predecessor. No se usa
`sequence_number` para ordenar entre canales trade/quote hasta que el proveedor
certifique o el shadow demuestre que comparten un espacio comparable. No hay
nearest/as-of tolerante, fill, cruce entre contratos, intersección para ocultar
unilaterales, deduplicación económica ni exclusión retrospectiva de fechas.

Correcciones/cancelaciones se preservan. Si el mensaje live no permite
reproducir la semántica histórica de corrección, la fuente falla paridad aunque
la cobertura aparente sea suficiente.

La semántica de correcciones no se acredita con una nota creada por el
investigador. Antes del gate debe existir un manifest JSON acompañado por el
documento oficial raw que declara:

```text
provider=Massive
scope=OPTIONS_TRADES_WEBSOCKET_AND_REST
status=PROVIDER_CERTIFIED
source_url=https://massive.com/...
retrieved_at_utc=<timestamp timezone-aware>
historical_correction_field=correction
live_correction_semantics=
  EXPLICIT_FIELD | REPLAYED_CORRECTED_EVENT_WITH_STABLE_ID
evidence_file=<basename local>
evidence_sha256=<sha256 del raw>
```

Manifest y evidencia quedan hasheados en gate y auditor. Una URL sin raw, una
afirmación local, un schema distinto o ausencia de semántica live falla
cerrado. Cinco sesiones sin correcciones observadas no sustituyen esta prueba.

## Preflight outcome-free

Antes de una captura 2023–presente se implementan y versionan:

1. capturador histórico resumible con raw atómico y cursors;
2. capturador shadow live con timestamp de llegada;
3. normalizador común;
4. source gate outcome-free;
5. auditor independiente que reparsea y rehashea el raw.

Todos deben estar committed/pushed desde HEAD limpio antes del primer valor.
El preflight cubre cinco sesiones futuras consecutivas de shadow QQQ/SPY. Al
día siguiente de cada sesión descarga su equivalente histórico REST y compara
el mismo inventario de contratos y eventos normalizados. No abre clocks
10:36/13:36, labels, underlying outcome, payoff ni PnL.

Gates fail-closed:

- entitlements historical/live y versión de schema identificables;
- inventario point-in-time completo en ambos sensores y cinco sesiones;
- número de contratos suscritos `<=1000` por conexión y acknowledgements antes
  de 09:29:30 America/New_York;
- cero fallos de paginación, cero payloads truncados y cero raw no hasheados;
- timestamps y zonas horarias parseables sin coerción;
- `sequence_number` único y estrictamente creciente dentro del scope que
  documente el proveedor; cualquier reset queda explicado por contrato;
- igualdad exacta live↔REST en identidad de contrato, clase de evento,
  timestamp normalizado, sequence, precios, tamaños, exchanges y conditions;
- política de correcciones reproducible en ambos transportes;
- censo explícito de trades sin predecessor estricto y de empates de
  milisegundo, sin rellenarlos ni eliminarlos del denominador;
- cero sesión/sensor excluida y cero divergencia sin explicación contractual.

Una sola divergencia material cierra el preflight como `BLOCKED_DATA`. No se
relaja el normalizador, no se sustituyen cinco sesiones, no se consulta otra
ventana y no se construyen features.

## Secuencia si el preflight pasa

Solo un PASS auditado autoriza una nueva predeclaración económica única. Como
V4R2 abrió 2026 y V7 lo usó como development, 2023–2026 ya no puede ser outer.
El orden posterior sería:

1. predeclarar fuente, features, modelo, costes, folds y gates antes de leer
   valores económicos;
2. commit/push del contrato;
3. captura histórica 2023–2026, data gate outcome-free y auditoría;
4. development cronológico ya visto, sin selección por ticker/año;
5. freeze/commit de un outer futuro aún intacto;
6. evaluación única y auditoría independiente;
7. solo tras PASS por ticker/mes, payoff físico ask→bid, no-overlap,
   hold30–180m y `reject_while_open`;
8. solo tras ese segundo PASS, integración paper-only con paridad
   backtest/live.

Mientras falte la credencial o falle el shadow, V8, payoff, `services/`,
`bots/`, `systemd/`, VPS y el paquete live permanecen cerrados.
