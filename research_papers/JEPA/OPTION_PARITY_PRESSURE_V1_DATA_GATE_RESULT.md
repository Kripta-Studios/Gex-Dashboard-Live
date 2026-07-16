# OPTION_PARITY_PRESSURE_V1 — data gate V1R1

## Veredicto

`PASS_DATA_GATE` desde el commit `e560d0262a91b01c7c7c4c03bf5c922d459d0531`.
El relanzamiento inmutable V1R1 valida la medición física 2023–2025 antes de
leer labels, retornos o cualquier dato 2026. No existe todavía PF, WR o PnL de
esta familia.

## Resultado sellado

- 2.256/2.256 sesiones válidas, 752 por ticker y cero errores.
- Dataset físico: 2.256 filas y 28 columnas.
- Cobertura anual mínima: `1.0`.
- Capacidad mensual mínima: 18 eventos válidos; 108/108 celdas ticker-mes
  superan la restricción estricta de más de 12 operaciones potenciales.
- Mínimo observado de strikes comunes válidos: 4, por encima del gate de 3.
- Mínimo de estados distintos por ticker-año: 199.
- Máxima fracción de ceros exactos: `0.044534412955465584`.
- 1.441 sesiones revalidadas contra el sidecar de timestamp nativo sellado.
- Inventario de 5.953 fuentes: 2.256 underlying derivados, 2.256 Greek vintage
  y 1.441 sidecars nativos.
- `outcome_accessed=false`, `production_changed=false` y 2026 cerrado.

## Hashes autoritativos

- Feature parquet: `45bca098588fa7bafefaf9a134e2f7de19f5d5d256d5d388766b5d33a38d5100`.
- Source inventory: `4a1fe920dd0b01cb140d999cdc74c3e1d3e0b4216afdde7bd9bcb96595b0f556`.
- Session audit: `efcc173e3ad3a82e3980a2e1c568998bf97590428796c70e89236e2283a2b4ac`.
- Coverage: `db4e815039939d72b49abf88fec7900830ac8530e89fc9ede7f53fc3b7751352`.
- Distinctness: `cc9d11c54ab3dcb8a35f95a1dc90cf77a3b5cc1b8b093e965c1849c74a3712b7`.
- Monthly capacity: `65f531b6c346f4408a8e848ac7cac0e12c880c58b71a232ec21b42d39680938b`.
- Errors: `0f8f4995b83c9769d308a873f208c12ec9350eec0ff79a4f21fcc279dac1ea1c`.
- Builder: `c796b5e9f25a154794d7f066e06cabeb8aad729722e73d4f1962802fe42a9f62`.
- Manifest file: `2b36e5765ee56677225437bd60c3a24e443e8b2c1e32ff35d3f6a493b665fbc7`.

Los compactos autoritativos viven en
`results/_diagnostics/option_parity_pressure_v1_202301_202512_v1r1_data_gate/`.

## Próxima acción única

Implementar y congelar, todavía pre-outcome, el runner determinista de desarrollo
2023: signo de `parity_pressure`, entrada `open(10:36)`, salida `open(13:36)`,
hold 180 minutos y coste de 1 bp. Se ejecutará una sola vez sobre 2023. Solo un
PASS de las 36 celdas ticker-mes puede autorizar el freeze y la apertura outer
2024–2025; 2026 seguirá cerrado hasta un PASS outer independiente.
