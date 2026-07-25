# Inventario outcome-free de fuentes causales nuevas — 2026-07-25

## Alcance y frontera de lectura

Este inventario se hizo desde `main`/`8ba155f34c58a9e206ae132bc1b3161f9bc8c449`
con `HEAD == origin/main`. Solo se inspeccionaron nombres, directorios,
metadatos, contratos ya versionados y documentación primaria. No se arrancó
Theta Terminal, no se llamó a un endpoint de mercado, no se leyó un precio,
trade, quote, Greek, IV, open subyacente, label, retorno u outcome 2026.

Flags del inventario:

```text
market_value_accessed=false
outcome_clock_accessed=false
outcome_2026_accessed=false
terminal_started=false
market_endpoint_accessed=false
production_modified=false
```

Los archivos no rastreados del usuario se conservaron intactos. No se tocó
`services/`, `bots/`, `systemd/` ni ningún paquete live.

## Censo local por metadatos

Para QQQ, SPXW y SPY, `D:/ThetaData/data_options` solo contiene `greeks`,
`iv`, `ohlc` y `oi`. `D:/ThetaData/data_underlying_derived` contiene barras
underlying. No existe un archivo local de prints OPRA, `trade_quote`, MBO,
profundidad, order flow de subyacente ni futuros contract-level.

Estas fuentes ya están cerradas en `ECONOMIC_FAMILY_REGISTRY.md` o no son
nuevas:

- Greeks/IV/OI, walls, surface deformation y calendar-RR;
- OHLC `volume/count` de opciones usado por H-FLOW;
- snapshots y ticks NBBO usados por H-QSIZE/H-QDYN/H-IBQDYN;
- barras cash/breadth/relative-value;
- continuos Yahoo 60m, limitados a 2024-07-17..2026-07-15 y sin contrato
  broker-grade;
- estructura Cboe diaria/VIX ya cerrada;
- higher Greeks directos bloqueados por licencia Professional.

El entorno solo declara acceso a ThetaData y Tastytrade. No hay variable de
entorno, cliente Python ni seal local de Databento, Polygon/Massive, Cboe
DataShop, dxFeed, Intrinio o un feed CME/OPRA alternativo. Tastytrade aporta
broker/live, pero no un archivo tick histórico 2023–2026 equivalente.

## Fuente nueva materialmente disponible

### OPRA trade tape emparejado con NBBO — ThetaData Standard

La documentación primaria de ThetaData establece:

- Options Standard ofrece granularidad tick, historia desde 2016-01-01 y
  tiempo real; incluye `Trade` y `Trade Quote` históricos y live, además de
  hasta 10.000 contratos de quote stream y 15.000 de trade stream:
  <https://docs.thetadata.us/Articles/Getting-Started/Subscriptions.html>.
- `/v3/option/history/trade_quote` devuelve cada trade OPRA emparejado con el
  último NBBO y permite `exclusive=true`, que exige
  `quote_timestamp < trade_timestamp`:
  <https://docs.thetadata.us/operations/option_history_trade_quote.html>.
- Los streams Standard por contrato entregan cada quote NBBO y cada trade OPRA
  con fecha, milisegundo, contrato y campos nativos:
  <https://docs.thetadata.us/Streaming/US-Options/Quote-Stream.html> y
  <https://docs.thetadata.us/Streaming/US-Options/Trade-Stream.html>.
- El listado de strikes se actualiza overnight y permite fijar antes de la
  apertura todos los contratos del vencimiento del día:
  <https://docs.thetadata.us/operations/option_list_strikes.html>.
- Los códigos `REGULAR=0` y `AUTO_EXECUTION=18` están definidos en la tabla
  oficial de condiciones:
  <https://docs.thetadata.us/Articles/Errors-Exchanges-Conditions/Trade-Conditions.html>.

La cuenta local/remota ya fue auditada como Options Standard durante el cierre
H-GREEK2WALL. El 403 afectó exclusivamente a higher Greeks Professional; no a
`Trade`, `Trade Quote` ni a los streams Standard.

Esta fuente es materialmente distinta de las familias cerradas. Conserva cada
print ejecutado, tamaño, precio, condición, exchange y sequence, junto al NBBO
anterior. H-FLOW solo observó OHLC/volumen/count agregado y firmó el bar contra
una quote; H-QDYN/H-IBQDYN observaron cambios de quotes, no prints ejecutados.

## Alternativas no activadas

- Databento OPRA y CME Globex publican servicios historical/live, pero no hay
  credencial, licencia ni seal local. Por tanto son dependencias externas, no
  una fuente ejecutable en este workspace.
- Stock `trade_quote` de ThetaData sigue bloqueado por entitlement stocks; no
  se reintentó.
- Full OPRA Trade Stream requiere Professional. V5 no lo usa: la paridad se
  limita a streams Standard por contrato dentro de sus caps documentados.

## Dictamen

`PASS_SOURCE_INVENTORY_PREDECLARATION_REQUIRED`.

Existe una sola fuente nueva con historia 2023–2026 y una traducción live bajo
el mismo feed OPRA: `option/history/trade_quote` más quote/trade streams por
contrato. Antes de leer sus valores se predeclara una única familia
`CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5`. La existencia documental no demuestra
coverage, distinctness, paridad materializada ni alpha; esas propiedades deben
fallar cerrado en data gate y auditor independientes.
