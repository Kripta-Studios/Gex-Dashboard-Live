# Auditoría del experimento direccional JEPA 180m legacy

## Dictamen

`PROMISING_BUT_NOT_VALIDATED`

El ledger walk-forward local muestra que sí existió información direccional
explotable en algunos periodos. Sin embargo, no prueba el objetivo económico
actual ni permite afirmar que el modelo pueda operarse en futuros. Falla por
cuatro razones independientes: muchos holds no son de 180 minutos, la
preformación JEPA solapa parte de los meses reportados, no hay fills de futuros
y la fuente termina el 2026-06-05 sin junio completo ni julio.

## Artefacto auditado

- Resumen versionado:
  `results/jepa_full_pipeline_180m_direction_wf_truncate_for_exit/SUMMARY.md`,
  SHA256 `2e310ea7...8197d9`.
- Ledger local:
  `base_jepa_trades.csv`, SHA256 `26c7735b...20cdb`.
- 1.649 trades de 2025-01-02 a 2026-05-29, coste fijo 1 bp y notional spot
  teórico de 100.000 USD.
- La recomputación independiente del ledger coincide con el resumen agregado:
  WR 57,6%, PF 1,558 y +109.017 USD teóricos.
- Entradas 11:25–15:55; cero overlaps según sus entry/exit registrados.

El ledger grande no está versionado; es evidencia diagnóstica local, no un seal
reproducible desde Git.

## El hold publicado no es 180m fijo

El experimento usa `min(t+180m, último row del día)`. Solo 894/1.649 trades
(54,2%) duran realmente 180 minutos. Hay 755 entradas posteriores a 13:00, 269
posteriores a 14:30 y 50 trades con hold inferior a 30 minutos; el mínimo es 5
minutos. Por ejemplo, existen entradas 15:55 con exit 16:00.

Esta mezcla de horizontes no responde limpiamente a la pregunta de si se puede
predecir el mercado tres horas después. También infla la frecuencia que se
obtendría con una única posición de tres horas.

## Métricas 2026 del ledger publicado

Incluyen los holds EOD truncados y solo enero–mayo:

| Ticker | Trades | WR | PF | Net bps | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 143 | 52,45% | 1,138 | +296,0 | 11 | 3/5 |
| SPX | 189 | 53,44% | 1,451 | +800,2 | 29 | 4/5 |
| SPY | 141 | 53,90% | 1,253 | +378,5 | 17 | 3/5 |

QQQ incumple PF y frecuencia; QQQ pierde enero y mayo, SPX pierde enero y SPY
pierde enero y abril. Por tanto no cumple la gate aunque el agregado pooled sea
positivo.

La sensibilidad de 2026 empeora rápidamente al sustituir 1 bp por 3 bps:
QQQ PF 1,004, SPX 1,216 y SPY 1,059. Son precios spot observados, no bid/ask ni
fills de ES/NQ/MES/MNQ.

## Diagnóstico restringido a 180m exactos

Filtrar los trades después del resultado no constituye una política nueva ni
una validación; sirve solo para aislar el mecanismo direccional. En enero–mayo
2026 quedan:

| Ticker | Trades | WR | PF | Net bps | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 72 | 55,56% | 1,333 | +379,6 | 5 | 5/5 |
| SPX | 96 | 52,08% | 1,619 | +587,1 | 15 | 4/5 |
| SPY | 77 | 54,55% | 1,526 | +428,7 | 10 | 5/5 |

La dirección a tres horas parece más prometedora que la compra de opciones
0DTE: los tres PF agregados superan 1,20 sin theta. Aun así QQQ/SPY fallan
frecuencia y SPX febrero es negativo (PF 0,361). No cumple todos los meses.

## Causalidad de JEPA

El parquet de features actual tiene 223.017 rows, 2022-08-01..2026-06-05, SHA
`8cc2c78e...79e34`. Sus embeddings proceden de `xinput_v3_pipeline`.

Ese encoder se entrenó/seleccionó con el parquet March-2026 de 213.063 rows,
2022-08-01..2026-03-31, SHA `5f7df77d...163b9`. Los pesos se entrenaron con las
primeras 781 fechas hasta 2025-09-11 y el early stopping vio como validación las
138 fechas 2025-09-12..2026-03-31. Además de la pérdida latente, el entrenamiento
incluye cross-entropy sobre `target`.

Consecuencia:

- 2025 y enero–marzo 2026 no son holdout limpio para las features JEPA;
- abril–mayo 2026 sí están temporalmente después de train/validation del
  encoder, pero son solo dos meses;
- el GBT mensual sí usa solo meses anteriores, pero eso no corrige el solape
  anterior del encoder.

Las features base son calculadas por el pipeline legacy y las decisiones
seleccionadas empiezan después de completar el Initial Balance, por lo que no se
ha encontrado el leakage IB pre-10:30 del paquete 0DTE. No obstante, no existe
un contrato live sellado para las 222 features ni una auditoría timestamp por
feature que permita promoverlo.

## Artefacto congelado desincronizado

`jepa_full_pipeline_180m_frozen_march/SUMMARY.md` anuncia 179 trades y PF 1,405,
pero los ficheros locales actuales de esa misma carpeta contienen 20 trades y
PF 0,267. La carpeta fue reutilizada/sobrescrita mientras el resumen versionado
quedó antiguo. El PF 1,405 no es reproducible desde el estado actual y no debe
usarse como evidencia.

## Siguiente experimento autorizado

Una única evaluación nueva debe leer los OHLC subyacentes ya existentes en
memoria, congelar el encoder con datos hasta 2025-12-31 y evaluar 2026 sin
construir otra familia de datasets. Debe usar horizontes/horas exactos,
no-overlap, al menos 1 bp de coste, baselines de persistencia y un modelo
semántico residual. Junio completo y julio MTD están disponibles en
`D:/ThetaData/data_underlying_derived`; los resultados de julio se etiquetarán
MTD hasta que termine el mes.

