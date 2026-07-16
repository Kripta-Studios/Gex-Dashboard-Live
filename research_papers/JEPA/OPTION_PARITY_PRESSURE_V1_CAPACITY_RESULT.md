# OPTION_PARITY_PRESSURE_V1 — resultado de capacidad outcome-free

**Estado:** `PASS_FREQUENCY_CAPACITY`

**Fecha:** 2026-07-17 Europe/Madrid

El auditor congelado en `314d16e1` recorrió únicamente nombres/tamaños de
fuentes exact-0DTE 2023–2025. No abrió contenido de quotes, labels, retornos,
2026 ni producción.

## Resultado

- 2.256 ficheros exactos; 752 por QQQ/SPXW/SPY.
- 36 meses completos por ticker.
- Ocho medias jornadas excluidas por el reloj fijo 10:36→13:36.
- Mínimo mensual elegible: 18 sesiones para cada ticker.
- Cero celdas bajo la gate estricta `>12`.

Este PASS demuestra capacidad, no cobertura de pares CALL/PUT ni alpha. La fase
siguiente sigue siendo un data gate outcome-free sobre timestamps, strikes,
bid/ask vintage, spot exacto y distinctness de `parity_pressure`.

## Evidencia

Directorio:
`results/_diagnostics/option_parity_pressure_v1_capacity_202301_202512/`.

- manifest: `eebdc7d9f31ff623aef95d3e1b5b93c0c3957ec8bad4950f1e1c61f7eab4f590`;
- monthly: `e8dfc2e404adc0dee130e4d5bc81480b0df6ee697cd2e18aed04598d0485c5e7`;
- inventory: `9c6ddb40dd1e90fdde5c89222103a0b3b6e446dbdb7b0e834e150ca6d009392d`;
- predeclaración: `96d100e901fb44c3d7858447b590258fbec10bd2ca15fe05321e090e5be114cf`;
- amendment: `9c41da4c1eec7e39151a6a617c9d97219f695a7cf097b01fe8ae41a7d5937e3c`;
- runner: `da5e513aa5ad06fc469a4338e8ba8efb2127ac9d9c4e222edd6e4541e7694dae`.

2024–2026 siguen sin outcomes abiertos y producción no cambió.
