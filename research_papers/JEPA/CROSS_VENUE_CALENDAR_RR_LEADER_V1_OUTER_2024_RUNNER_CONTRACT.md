# CROSS_VENUE_CALENDAR_RR_LEADER_V1 — runner outer 2024

**Estado:** `PREDECLARED_BEFORE_OUTER_2024_OUTCOMES`

**Fecha:** 2026-07-17 Europe/Madrid

Este contrato congela el único ensayo económico 2024 permitido después de un
`PASS_DATA_GATE` comprometido. No abre 2025/2026 y no autoriza producción.

## Scope y policy

- Solo rows 2024 `economic_event_valid=true` del mapping ya congelado.
- QQQ usa QQQ, SPY usa SPY y SPXW usa SPY del mismo `trade_date`.
- Acción `sign(signal_pressure)`; presión cero es no-trade.
- Decisión después de 10:35, entrada cash proxy `open(10:36)`, salida
  `open(13:36)`, hold exacto 180 minutos.
- Una posición no solapada por ticker y día.
- Coste primario round-trip 1bp; 2bp y 3bp son sensibilidades reportadas y no
  pueden seleccionar ni cambiar la policy.
- Se leen únicamente los dos rows de underlying 10:36/13:36 de 2024 y se
  revalida su hash contra el source inventory del data gate.

No hay modelo, fit, threshold, grid, abstención adicional, signo alternativo,
sensor local alternativo, consenso, selección mensual ni rescate por ticker.

## Gate incremental para abrir 2025

Cada ticker debe cumplir simultáneamente en 2024:

- PF primario `>1,00`;
- WR `>45%`;
- neto agregado `>0`;
- más de 12 trades en cada mes.

Si un ticker falla, V1 no abre 2025. El resultado puede motivar una V2 distinta
solo mediante otra predeclaración previa a outcomes 2025.

## Gate de promoción, sin rebaja

También se reporta, sin usarla para modificar V1, la gate objetivo del usuario:
PF `>1,20`, WR `>45%`, más de 12 trades por mes y PnL positivo en todos los
meses, para cada ticker. Pasarla en 2024 solo permite continuar la secuencia; no
crea `production_live_ready` ni prueba 2026.

## Freeze y outputs

El freezer solo puede ejecutarse después de que manifest, feature view y source
inventory del data gate PASS estén versionados. Congela sus hashes, los hashes
de evaluator/freezer/protocolos, los event IDs 2024 y los counts por mes. Ese
manifest también debe quedar committed antes del único outcome read.

El evaluador produce ledger, métricas mensuales, resumen por ticker,
sensibilidad de costes, source audit y hashes reproducibles. Debe declarar
explícitamente que 2025/2026 y producción permanecen cerrados.
