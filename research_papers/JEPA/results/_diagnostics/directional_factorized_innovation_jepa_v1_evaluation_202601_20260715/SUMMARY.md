# DIRECTIONAL_FACTORIZED_INNOVATION_JEPA_V1 — cierre

Estado: `CLOSED_ADAPTIVE_DIAGNOSTIC_GATE`

## Resultado mecanístico

La reparación superó todas las gates outcome-free antes de abrir el downstream:

| Geometría | V1 colapsado | Factorized innovation V1 |
| --- | ---: | ---: |
| rango efectivo z/24 | 14–15% | 53,54% |
| rango efectivo dz/24 | 11–12% | 42,67% |
| PC1 z | 35–46% | 15,44% |
| PC1 dz | no sano | 20,97% |
| dimensiones muertas | 0 | 0 |

Los bloques residuales QQQ/SPXW/SPY alcanzaron 93,17%/94,51%/94,91% de rango
efectivo. Common pasó 49,16% y volatility 74,48%. El colapso espectral quedó
reparado sin aumentar las 24 dimensiones ni añadir fuentes.

Desarrollo 2025 eligió `TECH_RESIDUAL` para QQQ y SPX, y
`SEMANTIC_RESIDUAL` solo para SPY. Ningún perfil de desarrollo fue rentable de
forma estable: PF seleccionado 0,942/0,979/1,011 y 7/4/5 meses positivos.

## Evaluación adaptativa 2026

Una decisión diaria, contexto hasta 10:35, open 10:36→13:36, hold 180m, coste
1 bp y cero overlaps:

| Ticker | Perfil congelado | Trades | WR | PF | Net bps | Meses positivos | Min/mes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | TECH | 123 | 54,47% | 0,846 | -492,75 | 2/6 | 19 |
| SPX | TECH | 123 | 50,41% | 0,906 | -202,09 | 3/6 | 19 |
| SPY | JEPA | 123 | 50,41% | 0,835 | -366,82 | 3/6 | 19 |

Julio MTD hasta el 15 contiene 10 decisiones: QQQ/SPX/SPY PF
1,133/1,922/1,888 y net +38/+111/+107 bps. Es incompleto, no pasa frecuencia y
no rescata enero–junio.

## Conclusión

La intervención separa arquitectura de información: una representación sana no
produce una relación direccional estable. QQQ y SPX rechazaron el JEPA en 2025;
SPY lo eligió pero perdió en 2026. Se cierra la familia price-only para este
reloj/horizonte. No ajustar pesos VISReg, bloques, seeds, horizontes o perfiles
post-hoc.

Esto confirma que el colapso perjudicaba V1 pero no era el cuello dominante. El
siguiente trabajo debe exigir una fuente física causal independiente; no otra
variante de representación sobre las mismas barras.

El resultado es adaptativo porque la arquitectura se diseñó después de observar
el V1 de 2026. No es promocionable aunque hubiese pasado la gate.
