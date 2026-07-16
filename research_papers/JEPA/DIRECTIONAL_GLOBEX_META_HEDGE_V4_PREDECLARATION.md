# DIRECTIONAL_GLOBEX_META_HEDGE_V4 — predeclaración

Fecha: 2026-07-16. V4 se congela después de V1 2026 y los cierres de V2/V3 en
desarrollo. Es adaptativo y no confirmatorio.

## Hipótesis

V1 fue rentable en 9/12 meses de 2025 pero cambió de signo en 2026. V3 tuvo PF
agregado >1 en 2025 sin estabilidad mensual. V4 prueba si un meta-experto causal
puede conservar el predictor apropiado y rotar cuando su eficacia cambia, sin
elegir por el outcome del mes o día actual.

## Expertos congelados

Para cada ticker y W1/W2 se usan las señales LONG/SHORT causales de los ocho
perfiles ya congelados:

- V1: control breadth y Globex LightGBM;
- V2: lineal 63, 126 y expanding;
- V3: Hedge crudo 21, 42 y 63.

Se añade la inversa de cada uno y las constantes LONG/SHORT: 18 expertos. No se
reinterpreta la probabilidad ni se selecciona un componente con todo 2025.

Antes de cada decisión, la recompensa histórica de cada experto es
`clip(side * future_return_bps / 50, -1, 1)`. Hedge usa pesos exponenciales con
`eta=sqrt(2*log(18)/N)` y solo fechas anteriores en el mismo ticker/ventana. El
voto ponderado siempre emite LONG/SHORT. Memorias candidatas únicas: 21, 42, 63.

Clarificación cold-start outcome-free tras el primer lanzamiento fail-closed:
los ledgers de predicciones componentes comienzan en enero de 2025 y no existe
una señal componente común anterior. Antes de llenar N, Hedge usa todas las
observaciones anteriores disponibles; con cero observaciones parte de pesos
uniformes. `eta` conserva el denominador N congelado. No se elimina enero ni se
abre un outcome actual para inicializar pesos.

No hay dataset ni descarga nueva. W1/W2, intersección estricta, coste 1 bp,
no-solape y fills proxy cash no cambian. Gate 2025 por ticker: PF>1,10, WR>45%,
>=8/12 meses positivos y >12 trades/mes. La memoria global se ordena por peor y
total de meses positivos, peor PF, peor cuartil y nombre.

Solo tras commit de la selección se permite reconstruir causalmente los ocho
componentes de enero–15 julio 2026 y ejecutar el meta-Hedge una vez. Gate final:
PF>1,20, WR>45%, >12 trades en cada mes y PnL positivo en los siete meses para
QQQ/SPX/SPY. Un PASS requeriría shadow/live porque el diseño conoce el fallo V1.
