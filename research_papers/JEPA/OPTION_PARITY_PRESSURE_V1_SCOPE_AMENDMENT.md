# OPTION_PARITY_PRESSURE_V1 — amendment de scope 2023–2026

**Estado:** `AMENDED_PRE_OUTCOME`

**Fecha:** 2026-07-17 Europe/Madrid

**Base predeclarada:** `14a9547c`

## Motivo y autorización

El censo outcome-free de nombres de fuente mostró que febrero de 2022 contiene
exactamente 12 sesiones con vencimiento 0DTE para QQQ, SPXW y SPY. Con una sola
posición diaria es matemáticamente imposible cumplir el requisito estricto de
más de 12 trades. No se leyó quote, feature, label, retorno ni PnL.

El usuario autoriza explícitamente ignorar 2022 y usar 2023–2026. Este amendment
se congela antes de ejecutar el auditor formal o construir la vista de paridad.
No elimina ningún mes después de observar economía.

## Nueva secuencia causal

- Data gate outcome-free: fuentes 2023-01-01..2025-12-31.
- Desarrollo económico: enero–diciembre 2023.
- Outer confirmatorio: enero 2024–diciembre 2025, solo si los 12 meses de 2023
  pasan por ticker.
- Holdout final: 2026 por meses completos disponibles, solo si outer pasa y
  después de un segundo freeze committed.
- Producción permanece intacta en todas las fases.

“Usar 2023 a 2026” no autoriza entrenar/seleccionar con 2026 ni mezclar sus
meses con desarrollo. Los años se abren en orden, cada uno desde un commit
previo inmutable.

## Gates sin cambios

Por ticker y por cada mes abierto siguen siendo obligatorios:

- PF>1,20;
- WR>45%;
- más de 12 trades;
- PnL neto positivo;
- reloj/fills/coste/no-overlap exactos.

La señal, snapshots 10:30/10:35, radio 100bps, mínimo tres strikes, spread
normalization, acción, entry 10:36, exit 13:36 y coste 1bp no cambian.

## Stop rule actualizado

Si 2023 falla, no abrir 2024–2026. Si outer 2024–2025 falla, no abrir 2026. No
se permite retirar otro año/mes, añadir ventanas intradía ni cambiar el universo
después de outcomes. La ausencia estructural de 0DTE en febrero de 2022 queda
registrada como razón única del cambio de scope.
