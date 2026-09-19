# Resultado del primer piloto local

Fecha: 2026-09-19. Ejecución desde código y contrato publicados en
`2755d19858b8128dd689e1d44049e9b4d5d9b437`.
Root: `D:/GexResearchArtifacts/local_snapshot_v1/source_pilot_20260919_01`.

## Resultado comprobado

`LOCAL_SOURCE_DIAGNOSTIC_COMPLETE`, con auditor independiente
`PASS_LOCAL_SOURCE_DIAGNOSTIC_AUDIT`, seis fuentes y cero discrepancias.
Se trabajó sin API con los seis parquets fijados del 3 de enero de 2023.
El rehash posterior verificó seis originales y seis snapshots; no hubo cambios.

| Ticker | Filas Greek primera hora | Muestras válidas | OI leído | OI positivo reportado preapertura | OI cero | Contratos Greek sin OI |
|---|---:|---:|---:|---:|---:|---:|
| SPXW | 17.280 | 59/60 | 288 | 269 | 19 | 0 |
| SPY | 14.640 | 60/60 | 242 | 168 | 74 | 2 |
| QQQ | 11.280 | 60/60 | 186 | 126 | 60 | 2 |

SPXW conserva enmascarada la muestra de09:30, con motivo INVALID_PRICE. No se
insertó a esa hora un precio posterior ni se alteró el archivo derivado que
usaba la reparación histórica autorizada. Las dos faltas OI de SPY y de QQQ
permanecen en el diagnóstico. No hubo filas OI AFTER_OPEN en este piloto.

El número de filas Greek no equivale a operaciones o volumen del subyacente.
59/60 muestras SPXW tampoco equivale a59/60 minutos con OHLC intraminuto completo.
Cada muestra válida acredita concordancia entre los contratos observados a ese
reloj bajo el contrato local, sin reconstruir valores entre muestras.

## Lecturas y auditoría

El productor validó primero la columna completa de reloj. Después leyó las
columnas de identidad/subyacente en09:30–10:30 y OI del archivo diario. El
auditor volvió a leer las copias y reconstruyó las clasificaciones por otra
implementación. No se leyeron columnas bid/ask/delta/IV para este piloto ni
payoffs. El access log identifica las lecturas de reloj y las proyecciones.

Los timestamps naive se interpretan en America/New_York. La disponibilidad
de investigación usa quote_timestamp+1min por contrato; no se observó recepción
histórica y no se presenta esa demora como una garantía del proveedor.
`prior_close_semantics_verified=false`: una hora reportada anterior a apertura
no demuestra por sí sola que el OI represente el cierre anterior.

## Evidencia y verificación

- [Summary](pilot_evidence/summary.json), [auditoría](pilot_evidence/audit.json)
  y [manifest](pilot_evidence/manifest.json).
- [Conteos sin precios](pilot_evidence/quality_summary.json) y
  [access log](pilot_evidence/access_log.jsonl).
- [Catálogo de hashes](pilot_evidence/artifact_catalog.json): incluye el
  source_diagnostic local y seis snapshots; esos valores/raw no se publican en Git.
- Los cuatro archivos de manifest/audit/summary/access se copian sin cambiar bytes.
- Tests nuevos de fuente/auditor: 56 PASS. Suite completa: 185 PASS en34,60s.
  Ruff, compile y revisión de código: PASS antes de ejecutar.
- Runtime: Python3.14.2, PyArrow23.0.1, Windows.

## Alcance de la conclusión

El piloto demuestra que se pueden construir muestras locales verificables en
esa fecha, conservando sus faltas y con un oráculo independiente. No admite
por extrapolación todas las fechas2023, no resuelve el vacío de relojes2024–2025
y no recupera el vintage original. Sigue sin existir un resultado económico
de esta familia.

```text
historical_economic_admission = false
original_vintage_verified = false
economic_evidence_state = NOT_EVALUATED
prospective_validation_state = NOT_STARTED
technical_ready = false
promotion_approved = false
```

## Siguiente decisión de investigación

Conservar este piloto; no relanzarlo como si necesitara conseguir60/60 en todos
los tickers. El siguiente alcance debe fijar cobertura multisesión, semántica
documental del OI y reglas de features muestreadas antes de nuevos valores.
Después necesita un contrato económico nuevo, calendario de desarrollo compatible
con los huecos, baseline/ablación, costes y simulación de quotes con latencia.
El [runbook](01_IMPLEMENTATION_AND_RESEARCH_RUNBOOK.md) ordena esos requisitos.

Con la restricción actual a archivos descargados no se pueden observar precios
futuros ni fills de bróker. Por ello, el objetivo de un modelo rentable operando
en day trade sigue sin cumplirse. Los resultados de este piloto permiten seguir
investigando, no declarar ese objetivo conseguido.
