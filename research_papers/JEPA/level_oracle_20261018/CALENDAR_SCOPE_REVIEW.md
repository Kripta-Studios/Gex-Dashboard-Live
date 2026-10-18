# Alcance de «cada día»: sesiones cortas excluidas

Revisión de metadatos del 2026-10-18. **El calendario congelado no incluye todos
los días de apertura de NYSE**: entre 2023-01-03 y 2026-06-30 hay 875 sesiones
XNYS, de las cuales 867 son completas y ocho tienen cierre anticipado. Estas
ocho fechas representan **24 ticker-días excluidos por diseño**, distintos de
los seis ticker-días completos con fuentes ausentes en abril de 2026.

Se leyó `cache_v1/expected_calendar.csv`, que conserva `full_session=false`.
Fechas y apertura/cierre coinciden exactamente con el calendario XNYS de la
biblioteca instalada `exchange_calendars 4.12`. No se consultó ninguna API.

| Periodo | Todas las sesiones | Completas | Cortas excluidas | Ticker-días cortos excluidos |
|---|---:|---:|---:|---:|
| 2023 desde 3 enero | 250 | 248 | 2 | 6 |
| 2024 | 252 | 249 | 3 | 9 |
| 2025 | 250 | 247 | 3 | 9 |
| 2026 enero–junio | 123 | 123 | 0 | 0 |
| Total | **875** | **867** | **8** | **24** |

El denominador de todos los días abiertos de este intervalo sería **2625
ticker-días**: 2595 completos disponibles + 6 completos sin fuente + 24 cortos
excluidos. El índice congelado contiene solamente los primeros 2601; se verificó
que ninguna de las 24 exclusiones cortas aparece en él. No son ausencias
descubiertas después de los resultados ni se han añadido ahora al entrenamiento.

## Fechas y archivos locales

Las ocho sesiones cortas abren a 09:30 y cierran a **13:00 America/New_York**
en este calendario del subyacente: 210 minutos de duración. Las horas UTC
correspondientes están en el CSV de evidencia.

| Fecha | Apertura ET | Cierre ET | Tickers excluidos | Greek 0DTE presentes | OI 0DTE presentes |
|---|---|---|---|---:|---:|
| 2023-07-03 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2023-11-24 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2024-07-03 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2024-11-29 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2024-12-24 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2025-07-03 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2025-11-28 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |
| 2025-12-24 | 09:30 | 13:00 | QQQ, SPXW, SPY | 3/3 | 3/3 |

Existen **48/48 archivos canónicos**, 24 Greek y 24 OI, bajo
`D:/ThetaData/data_options/{ticker}/{greeks|oi}/{YYYY}/{MM}/`, con nombre
`{ticker}_{YYYYMMDD}_{YYYYMMDD}_{greeks|oi}.parquet`. Se inspeccionaron únicamente
nombres, tamaños y footers: tipos/campos, número de filas y grupos, y hash del
schema. No se leyeron precios, cotizaciones, valores OI ni timestamps de filas.

Los 24 Greek incluyen `underlying_timestamp`, `underlying_price`, `bid`, `ask`,
`delta` e `implied_vol`. Siete incluyen además `timestamp`: los seis archivos de
2023 y QQQ 2024-12-24. Los otros 17 son candidatos bajo la hipótesis de reloj
proxy ya declarada, no fuentes nuevas admitidas por esta revisión. Los 24 OI
incluyen `open_interest`; siete tienen `timestamp`, con la misma distribución.
En los otros 17, aplicar la disponibilidad asumida de OI requeriría la misma
convención explícita y verificación de una futura admisión.

Hay cuatro schemas físicos distintos por familia. Los tamaños son 57.954.196
bytes de Greek y 195.359 bytes de OI. Los conteos Greek van de 78.982 a 344.862
filas; los OI de 202 a 882. Los 24 conteos Greek son múltiplos exactos de 391:
**eso no acredita 391 minutos negociables ni cotizaciones válidas después de
las 13:00**. Un footer no permite distinguir rejillas, filas vacías o precios
repetidos. El examen de cobertura temporal y validez por fila sigue pendiente.
La presencia de estos archivos solo demuestra candidatos locales de fuente.

En el inventario, el campo booleano `has_quote_timestamp` representa literalmente
la presencia del campo de schema `timestamp`; en los registros de familia OI se
refiere a su reloj de publicación/disponibilidad, no a una cotización de opción.
Los arrays de campos/tipos completos eliminan esa ambigüedad de etiqueta.

## Consecuencia para el requisito diario

El criterio aplicado hasta ahora sobre `expected_full_calendar` cubre sesiones
de duración completa. **Un PASS allí no acreditaría operar todos los días NYSE**
si se omiten cierres anticipados. En particular, 2025 tiene 750 ticker-días
NYSE, pero la validación congelada tiene 741: faltan nueve por exclusión de
sesiones cortas. Debe informarse ese alcance aunque una política llegue a
cumplir los 741. No cambia ni rescata resultados existentes.

En 2026 H1 no hay sesiones cortas en este calendario: las 369 combinaciones
esperadas sí cubren todas las sesiones XNYS del periodo, pero seis siguen
`NO_EVALUABLE_MISSING_SOURCE` (QQQ y SPY, 2026-04-01/09/15). Los 24 casos cortos
de años anteriores son `EXCLUDED_SHORT_SESSION_NOT_EVALUATED`, no cero trades
observados ni ausencia de oportunidades en el mercado.

Para el método causal de tres fits, las exclusiones por bloque son: teacher
2023 H1, cero; training final 2023 H2 + 2024, quince ticker-días; validación
2025, nueve; test 2026 H1, cero. Incorporarlos alteraría el universo y sus pesos
por día, por lo que no deben insertarse en el intento congelado en marcha.

## Viabilidad técnica de un cierre variable, sin implementación

La lectura del código muestra dependencias explícitas de la sesión larga:

- `build_cache.py` construye 391 slots 09:30–16:00 y el CLI selecciona únicamente
  `full_session=true`. El motor valida arrays de longitud 391.
- `level_engine.py` fija decisiones hasta índice 375 (15:45), liquidación EOD
  en 385 (15:55) y horizonte 390 para su proxy gamma. El IB usa los primeros
  60 snapshots; su definición seguiría siendo anterior a la primera decisión
  en una sesión corta, siempre que los datos resultasen válidos.
- Features/exportadores, cuatro franjas de muestreo, rollouts, scheduler,
  fixtures y auditorías contienen límites 60..375 o tamaños derivados de ellos.
  Cambiar solo el CSV del calendario no cambia esas dependencias.

Una ruta futura necesitaría un reloj de sesión por día que se propague a todos
esos consumidores y enmascare el periodo posterior al cierre, sin rellenar
precios. Si se mantuvieran los márgenes actuales respecto al cierre del
subyacente, una sesión 09:30–13:00 tendría índice de cierre 210, última decisión
195 (12:45) y EOD 205 (12:55); esto es una ilustración de la adaptación, **no un
nuevo contrato ejecutado**. Los horarios de negociación/expiración de las
opciones y el horizonte usado por gamma deben tratarse explícitamente: el
calendario XNYS del subyacente no los certifica por sí solo.

Habría que verificar cobertura y cotizaciones observadas en la ventana corta,
límites de salida/terminal, máscaras de barras y las franjas/pesos de muestreo
antes de cualquier entrenamiento de una nueva variante. Reutilizar el cierre
15:55 de la sesión larga podría tratar una cola no negociable como si fuese
mercado o como missing-exit; esta revisión no afirma que tal error se haya
producido, porque las sesiones cortas están excluidas del intento actual.
No se modificó código congelado, protocolo, cache, modelo o resultado.

## Evidencia

Root: `D:/GexResearchArtifacts/level_oracle_20261018/calendar_scope_review_v1/`.
`excluded_sessions.csv` conserva las ocho fechas y relojes; `source_footers.csv`
las 48 entradas; `summary.json` añade schemas completos, checks y conteos;
`artifact_hashes.json` sella esos artefactos y la copia exacta del ejecutable.

- Calendario SHA256: `70caddcff8cde0e03c6819f03b7d2eebc8da4b30c9ace24d37a7738b856e4318`.
- Índice motor SHA256: `8d0c6e27bdaf7d47ef2a9888505294b8f3186da3a6927e780ce9e517e660e8e5`.
- Script SHA256: `b8f3d35f12b18170cce14637ed7afca438ec09df7333986499106e74b1473cc7`.

Ejecución secuencial de metadatos: 4,975 segundos, 48 footers, sin valores de
fuente, economía, API ni reconstrucción. Ruff correcto. No se rehashearon bytes
completos de los 48 raw ni se sustituyó la auditoría previa de fuentes.
