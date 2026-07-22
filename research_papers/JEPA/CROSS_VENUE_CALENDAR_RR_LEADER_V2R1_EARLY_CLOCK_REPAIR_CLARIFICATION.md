# CROSS_VENUE_CALENDAR_RR_LEADER_V2R1 — early-clock repair clarification

**Congelada:** 2026-07-22 Europe/Madrid, después del primer censo cash V2 y
antes de cualquier fit/predicción/output económico V2.

## Fallo físico observado

El loader verificó hashes, sizes, símbolos, fechas y 66 timestamps de 1.487
fuentes requeridas. Exactamente una fuente contiene opens no positivos:

```text
SPY|20230605
D:/ThetaData/data_underlying_derived/SPY/2023/06/SPY_20230605.parquet
09:55 open=0.0
09:56 open=0.0
```

Es parte del defecto upstream SPY 2023-06-05 09:54–09:56 ya documentado por el
audit underlying de WALL_SURFACE_FLOW. No se permite forward-fill, nearest,
interpolación, tolerancia, sustitución de ticker ni exclusión de la sesión.

## Reparación uniforme V2R1

Todos los bloques cash, en todas las fechas y tickers, se estrechan de
09:30–10:35 a **10:00–10:35**. Se exigen exactamente 36 opens nativos y 35
retornos open-to-open. El feature de horizonte 09:30→10:35 se elimina y se
reemplaza por 10:20→10:35. Cada bloque conserva seis columnas, ahora:

1. `log(open_10:35/open_10:00)*10000`;
2. `log(open_10:35/open_10:20)*10000`;
3. `log(open_10:35/open_10:30)*10000`;
4. std poblacional de los 35 retornos 10:00–10:35;
5. rango logarítmico de los 36 opens 10:00–10:35;
6. fracción positiva de los 35 retornos.

El vector sigue teniendo 29 columnas. No cambia option-sensor, mapping,
modelo, C, threshold, splits, labels, entry/exit, coste o gates. El ancla 10:20
no se eligió por payoff: coincide con el comienzo del grid causal previamente
auditado de WALL_SURFACE_FLOW y queda después del defecto conocido.

El runner debe exigir que el censo original de fuentes inválidas sea
exactamente `{SPY|20230605}` y que el nuevo censo 10:00–10:35 tenga cero
fuentes inválidas. Cualquier otra fuente, clock o open inválido falla cerrado.
Se añade regresión de índices 10:00/10:20/10:30/10:35 y de 36/35 counts.

No se entrenó ningún modelo, no se produjo prediction/ledger/output V2 y no se
leyó outcome 2025/2026. Código/tests V2R1 se committean después de esta
aclaración; live y systemd permanecen intactos.
