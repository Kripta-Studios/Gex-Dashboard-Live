# CROSS_VENUE CALENDAR-RR — aclaración del universo full

**Estado:** `PRE_OUTCOME_COUNT_CORRECTION`

**Fecha:** 2026-07-17 Europe/Madrid

## Discrepancia

El seal de preflight proyectó `1.503` sesiones y `3.006` capturas mediante una
constante manual. Al implementar el discovery completo, un censo independiente
de nombres de fichero Greek/IV encontró `502` sesiones front+back por ticker:

| Ticker | 2024 | 2025 | Total | Capturas front/back |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 252 | 250 | 502 | 1.004 |
| SPXW | 252 | 250 | 502 | 1.004 |
| SPY | 252 | 250 | 502 | 1.004 |
| Total | 756 | 750 | 1.506 | 3.012 |

La proyección anterior subestimó tres sesiones/seis requests, un `0,200%`. No
se leyó quote, feature, retorno o outcome para encontrarlo.

## Corrección autoritativa

El full capturer debe descubrir y exigir exactamente `1.506` sesiones/`3.012`
capturas. No se modifica el seal histórico ya hasheado; esta aclaración lo
supersede exclusivamente para el conteo full.

Proyección corregida desde las 24 capturas:

- `8.111.316` filas;
- `1.533.335.030` raw bytes, `1,4280 GiB`;
- `109.567.775` parquet bytes, `0,1020 GiB`.

La cost gate de 50M filas/20GiB sigue pasando con amplio margen. Hashes del
censo ordenado:

- IDs `ticker|date|role|expiry` (3.012):
  `447e771b391f12dcfd7cba3692e65a7586dd4db2f3205311034616ddc7de5ce4`;
- inventario lógico Greek/IV relativo (6.024):
  `e685affdc09715085e80f9828a36e71ebbd52d5e5da4a25e43f7e8ff2f4b07b0`.

No se permite excluir una sesión para reproducir la constante errónea. Las
medias jornadas pueden capturarse y auditarse; el data gate económico las
excluirá exclusivamente por calendario porque 13:36 queda fuera de RTH.
