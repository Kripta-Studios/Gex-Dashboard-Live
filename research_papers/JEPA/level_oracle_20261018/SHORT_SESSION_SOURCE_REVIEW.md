# Fuentes locales de las ocho sesiones cortas

2026-10-18: **24/24 ticker-días pasan la normalización original y las
comprobaciones de cobertura de la ventana corta**. Los 48 Greek/OI fueron
rehasheados antes y después: cero diferencias. Son candidatos técnicamente
utilizables para una extensión con cierre variable bajo las convenciones de
reloj existentes; no se han incorporado al cache/motor congelado ni se ha
calculado PnL.

Se examinaron exclusivamente los archivos ya inventariados para QQQ, SPXW y
SPY en 20230703, 20231124, 20240703, 20241129, 20241224, 20250703, 20251128 y
20251224. El normalizador congelado se reutilizó en memoria, sin escribir
caches. No hubo API, descargas, modificación de originales ni entrenamiento.

## Cobertura anterior al cierre

- Identidad de contrato 0DTE y reloj de minuto: cero filas Greek inválidas,
  cero duplicados y cero minutos con desacuerdo entre spots válidos.
- QQQ/SPY tienen 60/60 muestras IB válidas; SPXW tiene 59/60 en las ocho
  fechas, con la muestra 09:30 inválida conservada como missing. Los 24 IB
  tienen rango positivo y cumplen el mínimo original de 57 muestras.
- Los 24 días tienen spot válido en todos los minutos 10:30–12:45 y al menos
  una cotización numéricamente válida en cada minuto 10:31–12:55. El mínimo
  observado en esta última ventana es 202 contratos con quote válido. En
  10:30–12:55 hay al menos 111 quotes por minuto con delta finita e IV positiva.
- Entre 09:30 y 12:59, QQQ/SPY tienen 210/210 muestras spot y SPXW 209/210.
  Falta quote válido únicamente a 09:30 en 22 ticker-días; los otros dos son
  SPXW en 2023. Esto se conserva, sin rellenar precios.

Estas comprobaciones describen preparación de fuente. «Quote válido» usa
exactamente la regla original: bid/ask finitos, bid≥0, ask>0 y bid≤ask. No
certifica tamaño disponible, recepción en vivo, ejecución de una orden o
rentabilidad. Las condiciones de cobertura usadas para marcar candidato están
enumeradas en `technical_checks` por día; no son exclusiones económicas.

## Relojes y OI

Siete Greek tienen `timestamp` nativo. Sus **874.276 filas** tienen coincidencia
exacta con `underlying_timestamp`; no se aplicó retraso. Los otros 17 usan
`underlying_timestamp` como reloj de snapshot asumido. Que su edad calculada sea
cero es consecuencia de esa convención, no una observación independiente del
reloj de quote. Se mantiene el filtro de spot con edad entre cero y 60 segundos.

Los 9052 registros OI pasan la validación original, con cero inválidos o
duplicados. Los siete archivos con reloj nativo publican sus registros válidos
antes de apertura. En los otros 17 se aplica la disponibilidad asumida de
09:30; la recepción/prior-close no queda acreditada por estos archivos.
No hay registros OI válidos posteriores a 13:00 en estas fuentes.

A las 10:30 hay, sumando identidades conocidas de los 24 días, **7272 OI
positivos, 1780 ceros válidos y 42 contratos sin OI**. Se preservan los ceros y
los missing por separado. Los 42 faltantes están en seis ticker-días; no se
imputan ni se usa el universo futuro como denominador.

## La cola 13:01–16:00 no es relleno de ceros

Los 24 archivos contienen filas para los 180 minutos estrictamente posteriores
al cierre NYSE: **1.636.920 filas**, todas con spot positivo y quote que pasa la
validación numérica. Los 4320 ticker-minutos también pasan el consenso de spot
del normalizador. No hay spot cero ni bid/ask ambos cero en esa cola.

| Ticker | Filas posteriores a 13:00 | Bid/ask iguales a 13:00, mismo contrato | Bid/ask iguales al minuto anterior |
|---|---:|---:|---:|
| QQQ | 403.560 | 222.169 | 390.126 |
| SPXW | 778.680 | **778.680** | **778.680** |
| SPY | 454.680 | 215.396 | 437.807 |
| Total | **1.636.920** | **1.216.245** | **1.606.613** |

En SPXW, toda la cola conserva exactamente el bid/ask de 13:00 para cada
contrato. El spot y su reloj no presentan necesariamente el mismo patrón:
hay valores positivos repetidos y cambios en la cola. Por ejemplo, el total
de spots iguales al minuto anterior es 768.138 filas SPXW, no 778.680.
La repetición por sí sola no identifica el mecanismo del proveedor; tampoco
los valores positivos y relojes avanzados demuestran negociabilidad después
del cierre. **Es necesario recortar el periodo posterior a 13:00 antes de
construir el universo y las features de la nueva familia**, sin reutilizar
estos últimos quotes como salidas de una sesión corta.

El minuto 13:00 se informa separadamente: tiene 9094 filas y quotes válidos.
La ventana 13:00–16:00 incluye ese límite y tiene 181 slots; la tabla anterior
usa estrictamente 13:01–16:00 para evitar confundir el límite con la cola.
Una futura liquidación 12:55, con el margen actual de cinco minutos, no
necesitaría consumir esa cola. Los horarios contractuales de las opciones no
se deducen de estos datos ni de la etiqueta del calendario del subyacente.

## Evidencia y límites

Root nuevo: `D:/GexResearchArtifacts/level_oracle_20261018/short_session_source_v1/`.
`minute_coverage.csv` contiene **9384 filas**, una por ticker-día/minuto, con
counts de presencia, validez, ceros, repeticiones, consenso de spot y OI causal.
`summary.json` conserva los 24 resúmenes y metadatos de normalización; los dos
`source_hashes_*` contienen los 48 SHA256 antes/después, tamaños y mtimes.
`artifact_hashes.json` sella esos artefactos y la copia exacta del script.

Script SHA256: `b7f7240a5cb67509aa88d78b2dc248e6956a0ce73617676b0d6157fc9489cfe9`.
Dependencias congeladas: cache `985e87dc…180d69f`, motor `70cc5d20…13b7c6`.
Cinco fixtures sintéticos y Ruff correctos; ejecución secuencial de fuente
80,141 segundos. Los fixtures cubren colas positivas/cero, spot antiguo,
reloj proxy duplicado, invalidación OI y denominador de contratos conocidos.

Resultado limitado a viabilidad de fuente bajo hipótesis explícitas. No se
admitió ningún día en los resultados actuales, no se construyó un motor corto,
no se calculó label/payoff ni se lanzó otro fit. La adaptación del reloj y sus
pruebas pertenecen a archivos nuevos y a una revisión separada.
