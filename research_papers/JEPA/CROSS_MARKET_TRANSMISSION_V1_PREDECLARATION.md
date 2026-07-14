# CROSS_MARKET_TRANSMISSION_V1 — predeclaración

Estado: `PREDECLARED_DEVELOPMENT_ONLY`. Este documento se congela antes de
inspeccionar cualquier outcome 2024/2025 de la familia. Enero-mayo y junio de
2026 permanecen cerrados; producción no se modifica.

## Hipótesis falsable

Un impulso del mercado líder que todavía no fue absorbido por un mercado
rezagado puede cambiar la distribución executable ask-to-bid de CALL frente a
PUT. Beta, residuo beta-neutral, volatilidad relativa, liderazgo temporal y
desviación del basis deben distinguir transmisión de una divergencia
contemporánea espuria.

Esto no reabre el bloque cross-market de
`EXISTING_DATA_EXECUTABLE_UTILITY_V1`: aquel ya contenía returns y spreads
contemporáneos de SPXW/SPY/QQQ, VIX y TLT. No contenía beta rolling, residuo
beta-neutral, lead/lag, relative RV ni basis z-score.

La familia falla si no produce una policy completa que pase todas las gates en
cada ticker y cada mes outer. Un resultado positivo pooled o un ticker aislado
no basta.

## Fuentes y join causal

Se reutilizan únicamente:

```text
tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet
D:/ThetaData/data_underlying_derived/{SPXW,SPY,QQQ,TLT}/YYYY/MM/*.parquet
```

El master aporta keys y el E0 Pairwise congelado. Del subyacente se usan
`timestamp` y `close`; `tick_count` no se interpreta como volumen. Para cada
decisión en `t` se exigen exactamente las 30 barras cerradas con timestamps
`t-30m,...,t-1m`. Se prohíben `asof`, floor-time, nearest, forward fill y
sustitución. Falta de una barra o valor no finito falla cerrado.

La vista outcome-free temporal puede existir solo bajo
`tmp/existing_data_edge_sprint_v1/cross_market_transmission_v1/`. No es una
fuente nueva y no contiene labels, outcomes, exits ni paths.

## Definiciones congeladas

Sobre los 30 closes se forman 29 retornos
`r_i(u)=10000*log(close_i(u)/close_i(u-1))`. Para los pares ordenados fijos
`SPXW_SPY`, `QQQ_SPY`, `QQQ_SPXW` y el par dinámico `TARGET_TLT`:

- `beta_30 = sum((ri-mean(ri))*(rj-mean(rj))) / sum((rj-mean(rj))^2)`;
- `residual_h = 10000*log(ci[t-1]/ci[t-1-h]) - beta_30 *
  10000*log(cj[t-1]/cj[t-1-h])`, para `h=1,5,15`;
- `relative_rv_30 = log(sqrt(sum(ri^2))/sqrt(sum(rj^2)))`;
- `lead_score_30 = corr(rj[:-1],ri[1:]) - corr(ri[:-1],rj[1:])`;
- `basis_z_30` es el último `log(ci/cj)` menos su media de 30, dividido por su
  desviación estándar poblacional de 30.

Denominadores nulos, correlaciones indefinidas o cualquier no-finito fallan
cerrado; no se imputan durante el build.

## Brazos congelados

- `X0`: exactamente los 30 features ordenados E0 Pairwise V1, SHA ordenado
  `b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38`.
- `X1`: X0 más el bloque entero de 28 features de transmisión. No hay selección
  por feature, ticker, importance, SHAP, ablation ni outcome.

El orden del bloque es cada prefijo, en orden `spxw_spy`, `qqq_spy`,
`qqq_spxw`, `target_tlt`, seguido por `beta_30`, `residual_1m`,
`residual_5m`, `residual_15m`, `relative_rv_30`, `lead_score_30` y
`basis_z_30`. El manifest outcome-free debe congelar el allowlist exacto y su
SHA antes de desarrollo económico.

## Modelo económico único

`lightgbm_quantile_distribution_utility_v1` ajusta por ticker y lado nueve
regresiones LightGBM pinball con alphas `0.1..0.9`. Parámetros fijos: 300
árboles, learning rate 0,05, 31 hojas, min child 20,
subsample/colsample 0,8, lambda L2 1 y semillas deterministas. La imputación de
mediana se ajusta solo en train; no hay clipping de target.

Los cuantiles predichos se reordenan por fila. La utilidad es
`0.15*q10 + 0.10*sum(q20..q80) + 0.15*q90`. La probabilidad de ganar se deriva
por interpolación del CDF en cero y debe ser al menos 0,50 para el lado elegido.
No hay calibración con inner u outer.

CALL se elige si su utilidad es mayor, PUT si es menor y empate exacto abstiene.
Se exigen además utility threshold y side margin de la rejilla congelada:
percentiles utility `50,60,70,80,85,90,95` y margin
`0,10,20,30,40,50`, calculados exclusivamente de predictions de train.

## Nested walk-forward y ejecución

Desarrollo usa únicamente outer 2023-04..2023-12 con historia 2022-2023. Para
cada outer, inner son los tres meses inmediatamente anteriores y train termina
antes del primero de esos inner. Tras tests y manifest frozen se permite una
única evaluación 2024-01..2025-12.

Un mismo threshold/margin debe pasar cada mes inner: PF >=1,30, WR >=50%,
>=18 trades, PnL >0 y hold mínimo >=30m. Si ninguno pasa, el outer completo es
`ABSTAIN_OUTER`; no existe least-bad.

El payoff es SPXW d25 y QQQ/SPY d35, entry ask, exit bid, stop -60%, TP +1000%,
trail +50%/25% y hold 30-180m. Scheduler live-equivalente: una posición por
ticker; SPXW 4/día/0m, QQQ 2/día/30m, SPY 1/día/0m. No ranking diario ni
backfill del cap.

## Gate y rotación

Solo X1 puede ser candidato. Deben pasar los 72 ticker-month outer cells y no
depender de concentración extrema top-5. Stress y 2026 solo se abren después
de ese PASS completo. Si falla, la familia se cierra sin rescate y se rota a
una hipótesis materialmente distinta ya registrada; no se retunean alphas,
ventanas, pares, grid, tickers ni features.
