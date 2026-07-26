# CROSS_VENUE_CALENDAR_RR_LEADER_V4R2 — causa del fallo 2026

**Fecha:** 2026-07-26 Europe/Madrid. Este documento es un diagnóstico
`post-outcome`: se escribió después del único outer V4R2 y no constituye una
validación OOS ni autoriza producción.

## Qué se entrenó realmente

V4R2 no se entrenó sobre 2026. El manifest `e826eb1e` fijó un único logistic
pooled con 2.217 filas de 2023-01-03 a 2025-12-31. Sus predicciones para los 394
eventos enero–julio2026 se congelaron antes de abrir 10:36/13:36. El modelo no
se actualizó entre meses.

## Descomposición de la pérdida

El contrafactual `direct` conserva `base_side=sign(signal_pressure)` y resta
1bp; `model` es la orientación V4R2 congelada. En H1:

| Ticker | Direct PF | Direct net bps | V4R2 PF | V4R2 net bps |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 0,844704 | -477,069 | 0,969729 | -86,880 |
| SPXW | 1,025110 | +48,364 | 0,950957 | -97,917 |
| SPY | 1,013096 | +25,273 | 0,955718 | -87,839 |

La logística rescata parte de QQQ, pero destruye el pequeño edge directo de
SPXW/SPY. La relación cambia además dentro del semestre:

| Mes | Direct pooled net bps | Modelo pooled net bps | AUC orientación | Fracción invertida |
| --- | ---: | ---: | ---: | ---: |
| 202601 | +270,712 | -188,175 | 0,6529 | 80,00% |
| 202602 | -592,177 | -199,520 | 0,5895 | 47,37% |
| 202603 | +518,604 | -273,230 | 0,5919 | 74,60% |
| 202604 | -90,622 | +477,511 | 0,5481 | 85,19% |
| 202605 | -213,269 | -367,363 | 0,3927 | 66,67% |
| 202606 | -296,679 | +278,141 | 0,6144 | 54,84% |
| 202607 MTD | -95,474 | +179,460 | 0,4944 | 57,89% |

Marzo es el ejemplo más claro: la regla directa ganó +518,604bps pooled,
pero el modelo, cuyo `mean_probability` fue 0,4556, invirtió el 74,60% de los
eventos y terminó en -273,230bps. En abril y junio la inversión sí ayudó. No
existe por tanto un signo global estable que pueda corregirse post hoc.

## Drift de covariables frente a drift de concepto

El desplazamiento medio absoluto de las 29 features respecto al scaler
2023–2025 fue de 0,0795–0,2856 desviaciones estándar según mes. El máximo fue
`back_rr_t0` en febrero/marzo (-1,4617/-1,5843 sigma), pero el desplazamiento
medio del logit causado por los cambios de medias fue solo -0,1529 a +0,0535.
No es suficiente para explicar por sí solo los cambios de PnL.

La evidencia dominante es drift de concepto:

- correlación de coeficientes entre fits independientes 2023/2024/2025:
  `-0,143`, `0,095` y `0,146`;
- AUC de `fit2023` sobre 2024/2025: `0,499/0,517`;
- AUC de `fit2024` sobre 2023/2025: `0,535/0,535`;
- AUC de `fit2025` sobre 2023/2024: `0,543/0,542`;
- seis features cambian de signo dos veces entre los tres fits anuales,
  incluyendo `spy_return_1000_1035_bps`, `qqq_return_1020_1035_bps` y
  `back_rr_change`.

El problema débil es, por tanto, la memoria multianual de una orientación que
supone coeficientes estables. No es un problema de frecuencia, de los cuatro
sensor-fecha omitidos ni de falta de requery.

## Consecuencia experimental

La única falsificación posterior autorizada es V7: mismo sensor, features,
clocks, coste, eventos y logistic, pero con un fit pooled de los doce meses
completos inmediatamente anteriores a cada mes evaluado. Desde febrero el fit
incorpora outcomes 2026 exclusivamente de meses ya cerrados. No se barren
ventanas, thresholds, tickers, horas ni hiperparámetros.

V7 es development sobre outcomes ya vistos. Aunque pasase, 2026 no puede volver
a ser outer ni autorizar payoff físico/live; haría falta un periodo futuro
intacto.
