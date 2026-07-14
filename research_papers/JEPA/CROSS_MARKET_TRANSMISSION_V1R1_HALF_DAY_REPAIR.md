# CROSS_MARKET_TRANSMISSION_V1R1 — reparación causal de medias jornadas

Estado: `PREDECLARED_DEVELOPMENT_ONLY`. Se congela después del rechazo
outcome-free de V1 y antes de ejecutar desarrollo económico u observar outcomes
2024/2025 de la familia.

## Cambio único

Se omiten completas estas sesiones XNYS de cierre temprano:

```text
20221125
20230703
20231124
20240703
20241129
20241224
20250703
20251128
20251224
```

El criterio es exclusivamente calendario. No consulta return, side, exit,
strike, modelo, feature ni resultado. Se excluye la sesión completa porque el
label builder existente no limita uniformemente los paths al cierre 13:00
SPXW/13:15 QQQ-SPY; seleccionar solo las filas cuyos exits casualmente no cruzan
el cierre usaría outcome futuro.

El master físico conserva 97.625 filas. V1R1 conserva 96.553 filas de sesiones
normales y elimina 1.072 de nueve sesiones no certificables. La capacidad
outcome-free mínima por ticker-mes sigue siendo QQQ 278, SPXW 345 y SPY 349,
muy superior a la gate de 18 trades.

## Invariantes

No cambia nada más: X0 son los 30 Pairwise, X1 añade los mismos 28 campos y en
el mismo orden; las ventanas siguen siendo 30 barras exactas completadas; el
modelo sigue siendo quantile distribution, la rejilla inner, folds, gates,
scheduler, buckets y ask-to-bid contract no cambian. No se añade epsilon,
imputación de fuente, as-of ni un label nuevo.

Desarrollo permanece exactamente 2023-04..2023-12. Tras código, tests, vista y
manifest committed se permite un único outer 2024-2025. 2026 permanece cerrado.
