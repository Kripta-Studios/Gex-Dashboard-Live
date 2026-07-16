# OPTION_PARITY_PRESSURE_V1 — aclaración de serialización del reloj nativo

**Estado:** `PRE_OUTCOME_OPERATIONAL_FIX`

**Fecha:** 2026-07-17 Europe/Madrid

**Runner base:** `b0cbba80`

## Fallo observado

El primer full gate inmutable terminó `REJECTED_DATA_GATE` con 104 errores antes
de labels/outcomes: 103 QQQ y uno SPXW. Todos reportaron
`target native Greek timestamps are empty/invalid`. El output V1 se preserva en
`tmp/option_parity_pressure_v1_data_gate_202301_202512_v1`; manifest SHA
`47cb9ad20bb68663f1fc1ccadb487e1bb14a0935f4a0a4f0afeebf765cc91869` y
errors SHA `ee68d9ebc18140dad65691750a949f5f1889828257b7c9f620a9763f0bfd235c`.

## Causa demostrada

No faltan timestamps nativos. Los Parquets afectados serializan el minuto como
`YYYY-MM-DDTHH:MM:SS.000`; el pushdown filter pedía únicamente
`YYYY-MM-DDTHH:MM:SS`. Al leer la columna y parsearla como datetime, las muestras
QQQ 2023-01-10 y SPXW 2023-03-09 contienen exactamente 170 y 292 filas en cada
uno de 10:30 y 10:35. El mismo problema afecta la selección provisional de
Greek vintage en algunas sesiones que después usan el sidecar sellado.

## Fix permitido

El lector puede solicitar exclusivamente estas dos codificaciones equivalentes:

```text
YYYY-MM-DDTHH:MM:SS
YYYY-MM-DDTHH:MM:SS.000
```

Después debe parsear a datetime y seguir exigiendo igualdad exacta con 10:30 y
10:35. En sesiones sidecar, `underlying_timestamp` solo localiza filas Greek y
nunca se acepta como reloj: las keys completas deben existir one-to-one en el
timestamp nativo sellado antes de conservar bid/ask vintage.

No se permite as-of, nearest, truncation, timezone shift, tolerancia, fallback
sin sidecar, cambio de clocks o inclusión de otra fracción de segundo.

## Relaunch

Añadir una regresión Parquet con `.000`, commit/push del fix y relanzar a target
nuevo `tmp/option_parity_pressure_v1_data_gate_202301_202512_v1r1`. No reutilizar
ni editar V1. Señal, strikes, radio, spreads, coverage y distinctness no cambian.
2026, labels, PnL y producción siguen cerrados.
