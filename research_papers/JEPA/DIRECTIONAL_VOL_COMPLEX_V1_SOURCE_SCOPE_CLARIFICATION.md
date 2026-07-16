# DIRECTIONAL_VOL_COMPLEX_V1 — aclaración de scope OHLC

Estado: `PRE_OUTCOME_SOURCE_CLARIFICATION`

El primer capture attempt se detuvo en memoria y no creó output, staging ni
manifest. `VIX_History.csv` contiene 47 filas con envelope OHLC inconsistente en
su historia antigua; los ejemplos empiezan en 1992. Auditoría de los cuatro CSV
con historia larga:

| Fichero | Fallos historia completa | Fallos 2022-08-01..2026-07-15 |
| --- | ---: | ---: |
| VIX | 47 | 0 |
| VIX3M | 1 | 0 |
| VIX6M | 1 | 0 |
| VIX1Y | 1 | 0 |

V1 solo consume 2022-08-01..2026-07-15. Se aclara antes de materializar un byte
y antes de leer outcomes:

- preservar el CSV oficial completo exactamente como llega;
- contar y reportar los envelopes inválidos históricos;
- exigir cero envelopes inválidos dentro del scope consumible;
- no corregir, eliminar o reescribir ninguna fila raw;
- mantener validación de fechas únicas y valores positivos/finitos completa.

Esto no modifica features, fechas consumidas, modelo, selección, reloj, label o
gate económica. Si aparece un fallo in-scope, la captura se detiene.

