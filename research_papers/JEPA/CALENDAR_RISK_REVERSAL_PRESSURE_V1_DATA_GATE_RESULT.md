# CALENDAR_RISK_REVERSAL_PRESSURE_V1 — data gate 2023

## Veredicto

`PASS_DATA_GATE` desde el commit `ef489baceb164de89ce40f1c86278d094c553570`.

El gate construyó únicamente la feature física hasta 10:35. No leyó entrada,
salida, retorno, label, PnL, 2024–2026 ni producción.

## Resultado

- Universo: 750 sesiones, 250 por ticker.
- Válidas: 747/750.
- Cobertura: QQQ 249/250 (99,6%), SPXW 248/250 (99,2%), SPY 250/250 (100%).
- Mínimo mensual económico: 19 eventos por ticker.
- Estados distintos mínimos: 233.
- Máxima fracción de cero exacto: 0,8097%.
- Inventario: 3.750 fuentes hasheadas, cinco por ticker/día.
- Los cuatro contratos se seleccionan en t0 y persisten exactamente hasta t1.

Tres sesiones se preservan inválidas:

1. QQQ 2023-06-26: el CALL más cercano a 25d está crossed en t0 (`0,41/0,37`)
   y no queda otro CALL persistente dentro de gap 0,10.
2. SPXW 2023-06-28: Greeks contiene PUT 4285 en ambos relojes, ausente en IV.
3. SPXW 2023-08-14: IV contiene CALL 4760 en ambos relojes, ausente en Greeks.

No se eliminaron por outcome ni se relajó el join. El contrato permitía hasta
10% de pérdida de cobertura; el mínimo observado es 99,2% y todos los meses
mantienen más de 12 eventos.

## Hashes autoritativos

- Feature: `de0ec4b3251505b763dff3dc8baee2f3462ca7a5833d70ed6db014b03112858b`.
- Session audit: `52df87c674d79ebe4f0a0de6f1ae4825e67f16c9e89131b271a63ce3dbab5605`.
- Source inventory: `6f81e4f8cc102f63c60e23c04d0c13d7a5be4af535c745f2dc5ec2646a2184d8`.
- Coverage: `ba6d270a559877bad366c734737935eaf331847efc044bb16cd7c99c69710aab`.
- Distinctness: `75b0f6e419fbf3cd9e0d5db0b760f9a0b5bfa9c3736f1981b5837ddfaca41a6e`.
- Monthly capacity: `665697dda996af79ac25723aa66b4d73e59e6c9e8d7e8acbfcf9a2dfd2c77119`.
- Errors: `fb2345e2e2d83acbccbf0f5911fe6d0cd7c3124def0499b6b975fd1a27084fea`.
- Manifest file: `604f53b2f036d0ac7743883b1ae9fe21e0cab2f9405a8facd4ebe2720615a9c1`.
- Builder: `c2f07b4ed175127717261a717b254914e595333b210572633853d51eec34cb49`.

## Siguiente acción única

Commit/push de este gate y sus compactos. Después implementar y congelar un
runner 2023 que verifique estos hashes y aplique exclusivamente signo de
`calendar_rr_pressure`, entrada open10:36, salida open13:36, hold180 y coste1bp.
No se puede leer el primer retorno hasta que ese runner y su manifest estén
committed. Outer 2024–2025 y 2026 siguen cerrados.
