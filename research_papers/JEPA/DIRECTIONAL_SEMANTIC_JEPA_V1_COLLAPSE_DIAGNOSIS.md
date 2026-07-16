# DIRECTIONAL_SEMANTIC_JEPA_V1 — diagnóstico de colapso

Estado: `POST_HOLDOUT_DIAGNOSTIC_NOT_PROMOTABLE`

Este análisis se hizo después de abrir 2026. Sirve para decidir qué mecanismo
está fallando, no para seleccionar o promocionar una policy sobre ese periodo.
No crea un dataset nuevo: relee las fuentes y el encoder sellados y opera en
memoria.

## 1. Existe colapso espectral, no colapso constante

El contexto normalizado de 66 minutos × 18 canales tiene rango efectivo `86,77`;
requiere 87 componentes para explicar 90% de su varianza y sus primeras 24
componentes conservan 52,76%. Por tanto la entrada contiene muchos más grados de
libertad que el embedding.

| Periodo | N | Rango efectivo z/24 | Ratio | PC1 | Std mediana por dimensión | Dims casi constantes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022-08..2024 | 602 | 3,72 | 15,52% | 38,62% | 1,086 | 0 |
| 2025 | 247 | 3,44 | 14,32% | 45,98% | 1,139 | 0 |
| 2026–07-15 | 133 | 3,70 | 15,40% | 35,47% | 1,078 | 0 |

`dz` es aún más pobre: ratio de rango efectivo `11,18–11,76%`. Los pesos no
están algebraicamente colapsados: la proyección 24×64 tiene rango matricial 24 y
rango efectivo 19,24 (80,15%); GRU input/hidden también pasan 83–94%. El cuello
es la geometría aprendida de los estados, no una matriz singular ni dimensiones
literalmente muertas.

La regularización actual explica el falso positivo de salud: fuerza desviación
estándar por coordenada cercana a uno, pero su penalización de covarianza es
demasiado débil para impedir que las 24 coordenadas sean combinaciones
correlacionadas de unos 3–4 factores.

## 2. El colapso no es la única causa

Un probe Ridge fijo sobre las 54 features JEPA dio correlación predicción/target
positiva pero mínima en 2025 (`0,046–0,052`) y negativa en 2026
(`-0,041..-0,068`). El R² es negativo en todos los casos. Los desplazamientos
predichos, que en 2025 tenían Spearman `+0,16..+0,20` con el retorno futuro,
cambian a aproximadamente `-0,10..-0,14` en 2026. La relación semántica no solo
es débil: cambia de signo.

| Ticker | Probe JEPA PF 2025 | Probe JEPA PF 2026 | Corr 2026 |
| --- | ---: | ---: | ---: |
| QQQ | 1,183 | 0,788 | -0,068 |
| SPX | 1,195 | 0,930 | -0,041 |
| SPY | 1,176 | 0,927 | -0,045 |

Control diagnóstico post-hoc, no promocionable: un Ridge sobre el contexto raw
completo retuvo señal en QQQ (PF 1,330 en 2025 y 1,337 en 2026), pero no en SPX
ni SPY durante 2026 (PF 0,857/0,869). Su R² 2026 fue muy negativo
(`-0,66/-1,06/-1,07`), señal de magnitudes mal calibradas y dimensionalidad alta.
Esto indica que el encoder sí descarta información útil para QQQ, pero que las
fuentes actuales tampoco contienen una relación robusta común para los tres
tickers.

El overlay VIX/term structure refuerza el diagnóstico: frente al JEPA padre solo
cambió el lado en 3/133 días QQQ, 2/133 SPX y 1/133 SPY. La aparente mejora
agregada procede de seis flips aislados; 98,5% de las decisiones son idénticas.

## 3. ¿Aplicar VISReg?

VISReg está justificado como reparación de geometría, no como hipótesis de alpha.
Un experimento anterior sobre SMM elevó el ratio mediano de rango efectivo de
`10,73%` a `14,68%`, pero siguió muy por debajo de la gate histórica de 40% y no
creó lado causal rentable. El JEPA direccional actual ya está en ese mismo rango
14–15%; añadir la misma configuración VISReg sin rediseñar el objetivo es muy
probable que repita el resultado.

Una prueba nueva solo tendría sentido con gates outcome-free antes de payoff:

1. rango efectivo z y dz >=40%, ninguna PC >70% y cero dimensiones muertas;
2. bloques latentes separados `market/common`, `QQQ residual`, `SPX residual`,
   `SPY residual` y `volatility`, evitando comprimir los tres tickers a un único
   factor común;
3. predecir innovaciones/residuos futuros normalizados, no el nivel completo de
   una ventana futura dominado por componentes suaves;
4. corruption por bloques semánticos completos —ticker, modalidad y tramo
   temporal— y targets de cross-modal reconstruction, sin borrar de forma
   indiscriminada los canales que definen el signo;
5. VISReg/SIGReg o whitening como constraint de salud, con stop antes de labels
   si no pasa rango; solo después un probe físico predeclarado.

Diagnóstico final: `PARTIAL_SPECTRAL_COLLAPSE_PLUS_OBJECTIVE_MISALIGNMENT`.
VISReg puede reparar parte del primer término; no resuelve por sí solo la pobreza
e inestabilidad de la información direccional, especialmente en SPX/SPY.

