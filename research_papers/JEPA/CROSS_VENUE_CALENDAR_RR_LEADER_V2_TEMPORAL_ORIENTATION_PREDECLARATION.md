# CROSS_VENUE_CALENDAR_RR_LEADER_V2 — temporal orientation

**Congelada:** 2026-07-22 Europe/Madrid, después del cierre completo V1 2024
y antes de leer filas cash pre-entry adicionales o ejecutar este V2.

## Condición epistemológica

V1 ya abrió todo el agregado 2024 y cerró con PF0,761071. Por ello esta familia
es post-outcome y no puede presentar 2024, ni una partición suya, como outer
virgen. 2023–2024 son exclusivamente development. El primer outer intacto es
2025 y solo puede abrirse después de un development PASS, auditoría, runner
2025 frozen y commit/push. 2026 permanece holdout final.

La exploración que motivó V2 quedó limitada a los ledgers ya abiertos y a las
features de opciones ya selladas. El signo fijo perdió los tres tickers en
2024. Una orientación global determinada por el hit-rate directo del mes
anterior habría alcanzado PF1,231750/1,395967/1,408300 en QQQ/SPXW/SPY, pero
solo 8/12 meses positivos y QQQ PF0,942178 en 2024-H2. Regresiones logísticas y
árboles shallow sobre la superficie de opciones no estabilizaron SPXW/SPY.
Esto autoriza una sola prueba nueva: estimar **directo frente a inverso** con
un estado cash temprano compacto; no autoriza un sweep posterior.

## Identidad de fuente y mapping

Se mantienen sin excepción:

- QQQ ← sensor QQQ;
- SPY ← sensor SPY;
- SPXW ← sensor SPY;
- la intersección Greek∩IV solo en los cuatro capture IDs V1R1 ya sellados;
- cualquier quinta discrepancia de keys falla cerrado;
- feature de opciones a 10:30→10:35 y contratos t0 persistentes;
- cash target QQQ/QQQ, SPY/SPY y SPXW/SPXW.

V2 consume únicamente artefactos committed. Sus seis inputs lógicos quedan
cerrados por SHA-256:

| Input | SHA-256 |
| --- | --- |
| 2023 feature parquet | `de0ec4b3251505b763dff3dc8baee2f3462ca7a5833d70ed6db014b03112858b` |
| 2023 source inventory | `6f81e4f8cc102f63c60e23c04d0c13d7a5be4af535c745f2dc5ec2646a2184d8` |
| 2023 sealed trades | `9c5178045e4172e6bfaf6d7bf30eb07a6ae68ff66a3bb8b738965de1e0d0fa66` |
| 2024–2025 V1R1 feature parquet | `fd2953bd9bc918b95079d494663cf7ca2fc9dfe141604b8e8803cc2bf605d268` |
| 2024–2025 V1R1 source inventory | `b63ca25185627528b1bc22ad937dcb834dbb4846d03b451aa395a62003d4c56c` |
| 2024 sealed V1 trades | `d989f586749738b75bb3c62c69d189d0e6e29b3106d060a1332c956af2917aa4` |

Para development se filtra físicamente `year==2024` antes de materializar la
vista V1R1. No se lee ningún outcome 2025.

## Features observables

La decisión ocurre a las 10:35:00 ET y la entrada sigue siendo el open de
10:36. Ninguna feature puede usar el close/high/low del bar 10:35. Los cash
features usan exclusivamente los 66 `open` nativos de 09:30:00 a 10:35:00,
ambos inclusive, y sus 65 retornos open-to-open completos.

Bloque option-sensor, ocho valores:

1. `signal_pressure`;
2. `abs(signal_pressure)`;
3. `calendar_rr_t0`;
4. `front_rr_t0`;
5. `back_rr_t0`;
6. `front_rr_t1-front_rr_t0`;
7. `back_rr_t1-back_rr_t0`;
8. `log(spot_t1/spot_t0)*10000`.

Cada bloque cash tiene exactamente seis valores:

1. `log(open_10:35/open_09:30)*10000`;
2. `log(open_10:35/open_10:00)*10000`;
3. `log(open_10:35/open_10:30)*10000`;
4. desviación estándar poblacional de los 65 retornos open-to-open;
5. `log(max(open_09:30..10:35)/min(...))*10000`;
6. fracción de los 65 retornos estrictamente positivos.

Todos los eventos incluyen los bloques cash QQQ y SPY. Solo SPXW añade su
bloque cash propio; para QQQ/SPY esas seis columnas son cero. Se añaden tres
one-hot de target ticker. Vector total: 29 columnas, nombres y orden fijos.
No IV adicional, volumen, outcome rolling, fecha, mes, threshold, grid, JEPA,
árbol, ensemble, stop ni selección de trades.

Cada fichero underlying se revalida por size/hash contra su inventario antes
de leerlo. Se exigen exactamente 66 clocks, símbolo/fecha exactos, opens finitos
y positivos. Un clock ausente o duplicado invalida la ejecución completa; no
hay nearest, forward-fill ni exclusión post-outcome.

La primera lectura cash encontró una única fuente con dos opens cero antes de
10:00. V2R1 aplica a todas las fechas la reparación de reloj congelada en
`CROSS_VENUE_CALENDAR_RR_LEADER_V2R1_EARLY_CLOCK_REPAIR_CLARIFICATION.md`:
36 opens/35 retornos de 10:00 a 10:35 y horizontes 35m/15m/5m. Este texto
original de 66 clocks queda reemplazado por la aclaración para V2R1.

## Target y modelo único

El target de entrenamiento es:

```text
direct_win = 1[sign(signal_pressure) * return_10:36_to_13:36 > 0]
```

El retorno se toma de los ledgers V1 ya sellados; el builder no vuelve a leer
13:36. Pipeline fijo:

```text
SimpleImputer(strategy="median")
StandardScaler()
LogisticRegression(
  penalty="l2", C=0.1, solver="liblinear", fit_intercept=true,
  class_weight=null, max_iter=2000, random_state=0
)
```

Existe un único modelo pooled con los one-hot ticker. Probabilidad >=0,50 usa
orientación directa; <0,50 invierte el signo. No hay abstención: un evento
válido produce una operación y preserva frecuencia. No se calibra probabilidad
ni se prueba otro C/modelo/feature set después del resultado.

Clarificación pre-cash posterior: dos filas QQQ 2023 tienen presión exactamente
cero y ya eran `NO_TRADE_ZERO_PRESSURE` en el ledger sellado. Directo/inverso no
está definido para ellas. Se congelan y excluyen solo del train según
`CROSS_VENUE_CALENDAR_RR_LEADER_V2_ZERO_PRESSURE_TRAINING_CLARIFICATION.md`;
no existe cero en 2024 y cualquier tercera key inesperada falla cerrado.

Runtime de predeclaración: Python3.14.2, numpy2.3.5, pandas3.0.0,
pyarrow23.0.1 y scikit-learn1.8.0.

## Dos bloques de development

1. `DEV_A` entrena solo con 202301–202312 y predice 202401–202406.
2. `DEV_B` vuelve a entrenar desde cero con 202301–202406 y predice
   202407–202412.

No hay actualización dentro de cada bloque. Las predicciones, scaler,
imputación y modelo de `DEV_B` solo ven labels hasta 20240630. Se reportan 1bp
primario y sensibilidades 2/3bps sin elegir entre ellas. Entry open10:36,
exit open13:36, hold180 y una posición/ticker/día sin overlap.

Cada bloque pasa incrementalmente solo si **cada ticker** cumple PF>1,
WR>45%, neto>0 y mínimo13 trades en cada mes del bloque. El objetivo no se
rebaja: PF>1,20, WR>45%, mínimo13 y PnL positivo en todos los meses. Si
cualquier ticker falla el incremental en cualquier bloque, V2 se cierra y no
abre 2025.

Si ambos bloques pasan incrementalmente, se audita el ledger, se versiona el
resultado, se implementa un freezer que fittea 202301–202412 y congela todos
los coeficientes/medianas/escalas para un único outer 2025. Solo un 2025 con
PF>1,20, WR>45%, mínimo13 y todos los meses positivos por ticker puede abrir
2026 después de otro freeze.

## Producción y payoff

Este experimento es cash proxy. No modifica `services/`, `bots/` ni `systemd/`.
Incluso un PASS 2024→2025→2026 requiere después un payoff de opción
predeclarado ask→bid, no-overlap, paridad backtest/live y primera integración
paper-only. Ningún resultado de development autoriza despliegue.
