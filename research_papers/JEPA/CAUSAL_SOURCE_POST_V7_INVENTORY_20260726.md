# Inventario causal post-V7 — dependencia externa

**Fecha:** 2026-07-26 Europe/Madrid.

**Estado:** `BLOCKED_EXTERNAL_CAUSAL_SOURCE_POST_V7`.

**Admisión externa condicionada:** la comparación documental posterior
selecciona Massive Options Advanced como único candidato autoservicio con
trades/quotes históricos que cubren todo 2023 y feeds live correspondientes.
No se considera fuente viable todavía: primero debe superar el shadow
live↔REST y la semántica de timestamps/correcciones fijados en
`EXTERNAL_OPRA_SOURCE_INTAKE_PREDECLARATION_20260726.md`.

## Alcance

Inventario read-only por nombres, conteos, schemas Parquet, contratos y
credenciales presentes. No se llamó a ThetaData, no se descargó o regeneró un
dataset, no se leyó un nuevo precio/outcome y no se modificó producción.

```text
market_endpoint_accessed=false
new_market_value_accessed=false
new_outcome_accessed=false
dataset_created=false
production_modified=false
```

`HEAD==origin/main==a0b5e98e` al iniciar. Existen cambios rastreados del usuario
en `services/servidor.py` y `web/templates/*`; se conservaron y quedaron fuera
de este inventario.

## Censo local Standard

Los roots QQQ/SPY de `D:/ThetaData/data_options` contienen cuatro schemas:

| Tipo | Campos materiales | Sesiones 2023/2024/2025/2026 hasta 24-jul por sensor |
| --- | --- | ---: |
| `greeks` | delta/theta/vega/rho/epsilon/lambda, IV, bid/ask, timestamps | 250/252/250/133 |
| `iv` | bid/ask/mid IV, bid/ask, underlying, timestamps | 250/252/250/133 |
| `ohlc` | option OHLC/VWAP, volume, count, bar timestamp | 250/252/250/133 |
| `oi` | prior-close open interest y timestamp | 250/252/250/140 |

El schema de `data_training_input` solo cubre 535 sesiones por ticker,
2024-01-02..2026-02-19. Ya fue rechazado causalmente: agrupa por
`underlying_timestamp`, permite `bfill`, oculta excepciones, define `wk` como
segunda expiración variable y no tiene paridad offline/live.

Fuentes de quote locales adicionales:

- `wall_quote_size_native_complement.../quotes.parquet`: bid/ask y
  bid_size/ask_size top-of-book;
- `wall_quote_tick_dynamics.../ticks.parquet`: secuencia NBBO, sizes,
  exchanges y conditions en ventanas de wall predeclaradas.

No existe otro root local de prints OPRA, MBO/depth, underlying trades firmados,
ES/NQ contract-level, basis, VIX1D/VVIX/term o tape alternativo. El único root
de prints es la captura V5 incompleta.

La única `.env` de ThetaData declara nombres `THETA_USERNAME` y
`THETA_PASSWORD`. No hay nombre de credencial ni cliente local para Databento,
Polygon/Massive, Cboe DataShop, Intrinio u otro proveedor historical/live. Las
importaciones `tastytrade.dxfeed` son broker/live y no materializan un archivo
histórico 2023–2026 bajo el mismo schema.

## Descarte contra el registro económico

| Fuente local | Familia previa | Dictamen |
| --- | --- | --- |
| Greeks/IV y deformación de superficie | H-IVSURF1, calendar-RR V1–V7 | cerrada/falla económica; no renombrar |
| OHLC option volume/count/price | H-FLOW1 y event-option | cerrada; no es tape ejecutado ni nueva microestructura |
| OI | EXACT_EXPIRY_OI_DELTA y walls | frecuencia/economía fallidas |
| NBBO size snapshots | H-QSIZE1R1 | physical gate negativo |
| NBBO tick dynamics en walls | H-QDYN1R1R1/H-IBQDYN1 | causalidad/physical cerradas |
| Cash/underlying derivados | cash-only/price-only/relative value | no transporta 2024–2025/2026 |
| Yahoo futures 60m | cross-asset previo | 2024-07..2026-07, sin contrato broker-grade y familia cerrada |
| OPRA `trade_quote` V5 | V5 | 1.364/1.504 válidas; enero2024=0/21; `BLOCKED_DATA` auditado |

Aplicar otro target, ventana, modelo o selección a cualquiera de esas fuentes
después de V4R2/V7 sería retuning de outcomes vistos, no una fuente causal
nueva. En particular, el hallazgo V7 de que la magnitud domina a la accuracy no
autoriza probar ahora regresiones/weights sobre el mismo 2026.

## Fuente necesaria

Para reabrir una familia única hace falta uno de estos mecanismos realmente
nuevos, con histórico y live del mismo producto/schema:

1. tape OPRA completo y auditable con sequence/corrections y NBBO estrictamente
   anterior;
2. eventos NBBO/full-depth con timestamps de evento y llegada, no snapshots 1m;
3. trades/depth firmados del subyacente o ES/NQ contract-level con roll causal;
4. curva timestamped VIX1D/VIX/VVIX/futuros con archivo y feed live equivalentes.

La dependencia debe aportar credencial/licencia presente, raw inmutable,
cobertura 2023–presente, política de duplicados/correcciones predeclarable y
capacidad live dentro de los caps de la cuenta. Antes de valores económicos se
haría inventario outcome-free, contrato, commit/push, gate y auditor.

## Consecuencia temporal

2026 ya fue abierto por V4R2 y usado como development por V7. Ninguna policy
nacida ahora puede volver a validarse promocionalmente sobre 2026. Si aparece
la fuente externa, 2023–2026 será development visto y el primer outer legítimo
deberá ser un periodo futuro congelado antes de sus outcomes.

No se predeclara V8 sin esa fuente. Payoff físico, live, VPS y systemd continúan
cerrados.

## Resultado de la búsqueda externa

La documentación oficial permite convertir el bloqueo genérico en una
dependencia concreta:

- Massive Options Advanced es el candidato primario por trades tick desde 2014,
  quotes desde 2022-03-07, REST histórico y WebSocket real-time;
- Databento queda descartado para este contrato porque `TCBBO/CMBP-1` empieza
  el 2023-03-28 y enero/febrero no tendría el mismo NBBO estricto;
- Cboe DataShop queda condicionado a una confirmación contractual de paridad
  live con su histórico Option Trades.

No se llamó a ningún endpoint, no se compró un plan y no se leyó un valor. La
dependencia mínima es una suscripción/credencial Massive Options Advanced y
cinco sesiones futuras de shadow outcome-free. El contrato de admisión congela
universo 0DTE QQQ/SPY, schema normalizado, predecessor estrictamente anterior,
correcciones, raw, gates y auditor antes de cualquier captura.
