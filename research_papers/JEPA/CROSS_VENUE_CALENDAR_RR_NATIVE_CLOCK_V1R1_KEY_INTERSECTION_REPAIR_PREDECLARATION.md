# CROSS_VENUE_CALENDAR_RR native-clock V1R1 — key-intersection repair

Status: `FROZEN_PRE_OUTCOME`

Fecha de congelación: 2026-07-21. Esta aclaración se escribe después de que
terminase el intento full V1, pero antes de abrir un solo retorno 2024, 2025 o
2026. No cambia la señal, mapping, reloj, horizonte, costes ni gates de
`CROSS_VENUE_CALENDAR_RR_LEADER_V1`.

## Motivo exacto

El run V1 procesó las 3.012 unidades y preservó 3.008 capturas atómicas
completas. Cuatro unidades fallaron antes de escribir raw/parquet/manifest
porque la key-set vintage de Greeks e IV no era idéntica. No fueron fallos de
red. Cada fallo contiene una sola clave unilateral repetida exactamente en los
dos relojes 10:30 y 10:35:

| Capture ID | Ticker/date/role/expiry | Diferencia unilateral | Shared rows |
| --- | --- | --- | ---: |
| `4b5b53cd7bce4944364d631d` | QQQ/20250828/front/20250828 | IV-only CALL 650 | 406 |
| `839ad0588cc9ee1309cd8c6f` | QQQ/20251121/back/20251128 | Greek-only PUT 680 | 706 |
| `207459dd60dbfe7dd06da8cf` | SPXW/20240122/back/20240126 | IV-only CALL 4575 | 858 |
| `8993033a23f2068d7a25d3c2` | SPXW/20250225/front/20250225 | IV-only CALL 6045 | 858 |

No existe `*.staging`. Los conteos materializados son raw=3.008,
parquet=3.008 y manifest=3.008: QQQ1.002, SPXW1.002 y SPY1.004.

Estado V1 congelado:

- root:
  `D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1`;
- capture contract SHA256:
  `f40947b52dd8923e785eb4f3d65d2ff8c5fba1720418b94ba5d50b36a40ea623`;
- universe SHA256:
  `98d416ea810c5bde657b6c23a9d7c599885d5eedfef3e332cd1885f6ddee45f4`;
- errors SHA256:
  `01c6c2f39d0dd5bab09284827aaafb9036c836127be0b28a31e17b44e22795f2`;
- root contract commit: `d013a299153ce6a4c611a7402c208fd2bf1b14a8`.

## Regla V1R1

Una feature calendar-RR necesita simultáneamente delta Greek y bid/ask-IV.
Por ello, para estas cuatro capturas y solo para ellas, el universo signable es
la intersección exacta

```text
Greek keys ∩ IV keys
```

en `(symbol, expiration, trade_date, timestamp, strike, right)`. Las ocho rows
unilaterales se conservan en el audit, pero nunca pueden seleccionar contrato,
aportar feature ni ampliar retrospectivamente el universo. No se hace as-of,
nearest strike, imputación, copia entre fuentes o sustitución por la respuesta
nativa actual.

La respuesta quote nativa debe cubrir el 100% de las keys compartidas a 10:30
y 10:35. Sus extras se archivan, no entran en features. Delta, bid/ask e IV
económicos siguen procediendo de los parquets vintage; el sidecar solo certifica
timestamp/key. Cualquier quinta discrepancia, cambio de hashes o diferencia
respecto a la tabla congelada hace fallar cerrado.

## Captura y composición inmutables

- No modificar, borrar ni recapturar las 3.008 unidades V1.
- Capturar solo los cuatro IDs anteriores a un root nuevo V1R1, con raw HTTP,
  parquet, manifest, JAR/runtime/source/code hashes y provenance remota.
- El capturador debe ser atómico, resumible y producir seal solo 4/4, cero
  errores, shared-key coverage exacta y diferencias unilaterales exactas.
- Un composite sealer posterior revalida las 3.008 capturas V1 con el código y
  manifests originales, las cuatro reparaciones V1R1 con su contrato nuevo y el
  universo lógico original de 3.012. No mueve ni reescribe ningún fichero V1.
- El full auditor y el data-gate builder aceptarán overlay solo si el composite
  seal committed referencia exactamente ambos roots/hashes y esta
  predeclaración.

Los 1.506 ticker-days permanecen en el universo; no se excluyen los cuatro días
ni se reduce la gate de frecuencia. El contrato SPY→SPXW exact-date y todas las
gates económicas permanecen iguales.

## Secuencia autorizada

1. Commit/push de esta predeclaración y los handoffs.
2. Implementar capturador/auditor V1R1 y tests sin outcomes.
3. Commit/push del código; capturar exactamente 4/4 a output nuevo.
4. Versionar seal/compactos; implementar y ejecutar composite audit/seal.
5. Solo entonces ejecutar full audit → data gate → auditor data gate →
   frozen outer-2024 runner.

No se abre 2025 si 2024 no supera la gate incremental por ticker. No se abre
2026 si 2024/2025 no pasan su secuencia. Producción y systemd continúan
intactos.
