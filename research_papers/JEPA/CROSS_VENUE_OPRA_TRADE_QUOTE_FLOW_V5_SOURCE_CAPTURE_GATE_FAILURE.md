# CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5 — source capture gate failure

**Fecha:** 2026-07-26 Europe/Madrid

**Estado:** `FAILED_OUTCOME_FREE_SOURCE_CAPTURE_GATE`

**Commit de captura:** `e6bdac64ffa37f4164024de82f7b535a83ee660b`

## Frontera causal

La captura abrió únicamente `option/history/trade_quote` para QQQ/SPY en
2023–2025 bajo el contrato V5 ya committed. No leyó opens10:36/13:36, labels,
returns, outcomes2026, Greek/IV ni los cinco IDs nuevos de junio2026. No tocó
producción, `services/`, `bots/`, `systemd/` o live.

El proceso se pausó a petición del usuario tras 12 captures y reanudó desde el
mismo HEAD, código, root y contrato inmutables; esas 12 capturas se revalidaron
y no se reconsultaron. No fue un segundo modelo ni una segunda selección.

```text
market_values_accessed=true
outcome_clock_accessed=false
outcome_2026_accessed=false
production_modified=false
feature_gate_built=false
economic_evaluation_started=false
```

## Resultado exacto

El universo frozen contiene 1.504 requests: 752 fechas por cada sensor, con
2023/2024/2025=`250/252/250`. El run procesó las 1.504:

- capturas atómicas completas: `1.364`;
- fallos: `140`;
- stagers al cierre: `0`;
- procesos al cierre: `0`;
- capture seal: ausente;
- error uniforme 140/140:
  `AssertionError: invalid or duplicate V5 trade_quote response`.

El mensaje preserva la disyunción exacta del validator: no afirma
retrospectivamente si cada respuesta violó unicidad u otra condición estructural.
Como el raw inválido no se promovió a directorio atómico, no se reconsulta para
clasificarlo.

| Sensor | 2023 | 2024 | 2025 | Total fallos |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 32 | 25 | 8 | 65 |
| SPY | 38 | 30 | 7 | 75 |
| Total | 70 | 55 | 15 | 140 |

Cobertura pre-feature por sensor-año: QQQ
`218/250=0,872`, `227/252=0,900794`, `242/250=0,968`; SPY
`212/250=0,848`, `222/252=0,880952`, `243/250=0,972`. Enero2024 pierde las 21
sesiones tanto en QQQ como SPY, de modo que el mínimo mensual de fuentes
completas es cero. Incluso la coverage diagnóstica 90% falla en QQQ2023,
SPY2023 y SPY2024; la condición primaria de cero raw ausentes falla en los seis
sensor-año que contienen al menos una discrepancia.

Hashes de autoridad:

| Archivo | SHA-256 |
| --- | --- |
| `_state/errors.json` | `3f5757465d8067c02ef54ae77020c774af449570d7cedd462c460be566fbc3d3` |
| `_state/universe.csv` | `cf6fe71f43e517776ca4b1f98501d02c75e93874e94681854aadc3312be02254` |
| `_state/capture_contract.json` | `210ea579d5278eccc8add95ace703e4c615fa70595ee7662ba303781daa205a6` |
| date inventory lógico | `e7786a1a8861ef8aaaeb8aed5cfe08ccaea50c8bcec575800ec044e88890b8f9` |

## Gate y prohibiciones

La predeclaración exige cero raw faltantes, cero fallos estructurales y al menos
13 eventos válidos por sensor-mes antes de outcomes. Por tanto V5 cierra antes
del builder; no se puede seleccionar fechas/ticker/año, deduplicar, relajar
`exclusive`, cambiar condiciones, recapturar fallos ni evaluar el subconjunto
de 1.364 sesiones.

El auditor independiente de fallo se prepara en
`audit_cross_venue_opra_trade_quote_flow_v5_capture_failure.py`. Debe quedar
committed/pushed antes de ejecutarse; rehasheará y reparseará los 1.364 raw
válidos y probará que los 140 fallos son exactamente el complemento del
universo. Un PASS de auditoría confirmará el cierre, nunca autorizará el feature
gate ni outcomes.

## Dependencia externa

Esta cuenta/proveedor no materializa la fuente bajo el contrato inmutable V5 en
todo 2023–2025. Continuar requiere una fuente externa nueva con tape OPRA
histórico único/auditable y feed live equivalente, credencial y licencia propias.
No se fabrica V5R1 cambiando retrospectivamente el tratamiento de respuestas.
