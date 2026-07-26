# Bloqueo de fuente causal externa — 2026-07-26

## Estado

`BLOCKED_EXTERNAL_CAUSAL_SOURCE`.

No queda una familia activa ni una fuente local autorizada capaz de sostener un
contrato causal histórico/live nuevo para QQQ/SPXW/SPY. V1–V4 y cash-only están
cerrados en `ECONOMIC_FAMILY_REGISTRY.md`. V5 fue la única fuente nueva del
inventario del 2026-07-25 y falló antes de features: 140/1.504 respuestas OPRA
`trade_quote` no cumplieron el contrato estructural inmutable; auditoría
independiente reprodujo el cierre con 1.364 fuentes rehasheadas, mismatch0 y
ningún ID sin explicar.

## Frontera de acceso

```text
outcome_clock_accessed=false
outcome_2026_accessed=false
feature_gate_v5_built=false
economic_evaluation_v5_started=false
production_modified=false
```

No se consultaron outcomes 2026, no se tocó Greek/IV ni se modificó live. No se
autoriza una V5R1 que deduplique, reconsulte, excluya fechas o evalúe el
subconjunto completo. Tampoco se repite cash-only, cross-market transmission o
una familia cerrada con otro nombre.

## Dependencia necesaria para reabrir investigación

Hace falta que el usuario aporte o autorice una fuente externa diferente con:

- tape de opciones histórico 2023–2026 con timestamps nativos y raw inmutable;
- feed live del mismo producto/schema y reglas de secuencia documentadas;
- licencia/credencial presentes y auditables en este entorno;
- unicidad o política de correcciones declarable antes de leer valores;
- cobertura de toda la cadena exact-0DTE QQQ/SPY bajo mapping
  QQQ←QQQ, SPY←SPY, SPXW←SPY;
- capacidad de fallar cerrado sin repairs, nearest/as-of o selección de fechas.

Databento OPRA, Cboe DataShop u otro vendor son solo ejemplos de dependencia
externa: este workspace no contiene credencial, licencia o seal histórico/live
para ninguno, por lo que no se inventa una V6. Si aparece una fuente nueva,
2023–2025 siguen siendo development visto y 2026 continúa sellado hasta una
nueva predeclaración, gate, auditor y freeze committed.
