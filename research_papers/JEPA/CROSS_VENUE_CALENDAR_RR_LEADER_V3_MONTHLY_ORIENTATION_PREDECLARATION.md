# CROSS_VENUE_CALENDAR_RR_LEADER_V3 — monthly orientation

**Congelada:** 2026-07-22 Europe/Madrid, después de cerrar y auditar V1/V2R1,
antes de abrir cualquier outcome 2025.

## Naturaleza post-outcome

V3 fue generada después de observar el V1 2024 completo y de explorar V2. Por
ello 2023–2024 son development contaminado y no constituyen evidencia de
promoción. El primer outer intacto de V3 es 2025. Ninguna fila 2025 de 10:36 o
13:36 puede leerse antes de development reproducible, auditoría independiente,
manifest secuencial frozen y commit/push.

El motivo de V3 es reducción de complejidad. V2R1 usó 29 features y falló cinco
de seis ticker-bloques. La regla mensual descrita abajo fue la mejor hipótesis
simple observada en development 2024: PF QQQ/SPXW/SPY
1,231750/1,395967/1,408300, pero solo 8/12 meses positivos. Estas cifras sirven
para formular y verificar V3, no para llamarla OOS.

## Fuente y mapping inmutables

- QQQ ← QQQ;
- SPY ← SPY;
- SPXW ← SPY;
- presión `calendar_rr_pressure` 10:30→10:35 de contratos t0 persistentes;
- Greek∩IV solo en los cuatro repair IDs V1R1;
- una quinta discrepancia de keys falla cerrado;
- entry open10:36, exit open13:36, hold180;
- coste round-trip primario1bp y sensibilidades2/3bps;
- una posición por ticker/día y cero overlap.

Inputs development cerrados:

| Input | SHA-256 |
| --- | --- |
| 2023 sealed trades | `9c5178045e4172e6bfaf6d7bf30eb07a6ae68ff66a3bb8b738965de1e0d0fa66` |
| 2024 sealed V1 trades | `d989f586749738b75bb3c62c69d189d0e6e29b3106d060a1332c956af2917aa4` |
| V1R1 2024–2025 features | `fd2953bd9bc918b95079d494663cf7ca2fc9dfe141604b8e8803cc2bf605d268` |
| V1R1 2024–2025 source inventory | `b63ca25185627528b1bc22ad937dcb834dbb4846d03b451aa395a62003d4c56c` |

## Única regla de estado

Para cada mes objetivo `M`, se toma exclusivamente el mes calendario inmediato
anterior `M-1`. Sobre todas las operaciones QQQ/SPXW/SPY ejecutadas en `M-1` se
calcula:

```text
direct_hit_rate = mean(
  sign(signal_pressure) * underlying_return_10:36_to_13:36 > 0
)
```

Las presiones cero no entran en el denominador y conservan
`NO_TRADE_ZERO_PRESSURE`. El mes previo debe contener más de 12 operaciones por
ticker; si falta una celda o el denominador pooled es incompleto, falla cerrado.

Orientación de todo el mes `M`:

```text
direct_hit_rate >= 0.50  -> +1 (DIRECT)
direct_hit_rate <  0.50  -> -1 (INVERSE)
side = orientation * sign(signal_pressure)
```

El threshold 0,50 es la definición neutral de majority hit, no un parámetro
optimizado. La orientación se calcula una vez al cerrar `M-1` y no cambia
dentro de `M`. Se agrupan los trades físicos, no promedios por ticker: SPXW y
SPY tienen peso separado y ese contrato queda fijo. No hay empate alternativo,
EWMA, ventana N, ticker-specific state, magnitud de PnL, PF, feature cash,
modelo, abstención, threshold de señal ni selección de fechas.

Para enero 2024 el estado procede de diciembre 2023. Para enero 2025 procede de
diciembre 2024. Después de cada mes 2025, el runner outer puede usar únicamente
los outcomes del mes ya completado para fijar el siguiente; nunca mira el mes
objetivo ni recalcula retrospectivamente señales.

## Development reproducible 2024

El evaluator development debe reconstruir los 739 trades ejecutados 2023 y 743
eventos 2024. Exige exactamente dos no-trades cero QQQ 2023 ya congelados y
cero en 2024. La secuencia esperada queda derivada por la regla, no hardcoded:

```text
202401 DIRECT
202402 DIRECT
202403..202412 INVERSE
```

Reporta por ticker/año/mes 1/2/3bps. Gate incremental development, por ticker:
PF>1, WR>45%, neto>0 y más de12 trades cada mes. Gate objetivo:
PF>1,20, WR>45%, más de12 y PnL positivo todos los meses. Solo el incremental
autoriza preparar el outer 2025; el fallo de estabilidad mensual se conserva.

El desarrollo no puede leer fuentes underlying nuevas: reutiliza exclusivamente
los retornos ya sellados 2023/2024. Un auditor separado recompone estados,
acciones, costes y gates antes del freezer 2025.

## Freeze y outer 2025

Tras PASS development auditado y committed, el freezer:

1. revalida el data gate V1R1 y sus hashes;
2. enumera solo eventos económicos 2025 y sus underlying sources hasheados;
3. congela la regla, el estado inicial derivado de 202412 y el orden mensual;
4. registra `outer_2025_opened=false`, `holdout_2026_opened=false`;
5. se committea/pushea antes del único outer.

El outer 2025 se ejecuta secuencialmente enero→diciembre, leyendo únicamente
open10:36/open13:36 del mes corriente. Para abrir 2026, **cada ticker** debe
cumplir PF>1,20, WR>45%, más de12 trades en cada mes y PnL positivo en los 12
meses. Sensibilidades2/3 son diagnósticas y no seleccionan. Un fallo cierra V3
sin abrir 2026.

## 2026, opciones y producción

2026 requiere otro manifest frozen después de PASS 2025. Junio cerrado debe
ser positivo y julio MTD solo shadow, no selección. Aun con PASS cash completo,
la integración necesita una evaluación separada de opciones ask→bid/no-overlap,
paridad backtest/live y primera ejecución paper-only. No modificar `services/`,
`bots/` ni `systemd/` durante V3 cash.
