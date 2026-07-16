# CROSS_SESSION_RELATIVE_VALUE_V1 — FAILED_ECONOMIC_DEVELOPMENT

## Veredicto

El único desarrollo congelado 2022-01..2023-12 se ejecutó desde el runner
committed `5e2dc677`. La policy mean-reversion queda cerrada y no se abre
2024–2026.

| Trades | WR | PF | PnL neto | Min trades/mes | Meses positivos | Meses PASS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 496 | 41,532% | 0,627276 | -2.349,329 bps | 19 | 5/24 | 2/24 |

La frecuencia pasa holgadamente. Falla la dirección relative-value: la regla
primaria pierde en agregado y en 19 de 24 meses. Solo 2022-10 y 2023-06 pasan
simultáneamente PF, WR, frecuencia y PnL.

## Controles no elegibles

- Momentum, la acción opuesta: 496 trades, WR 51,210%, PF 1,075340 y
  +365,329 bps. No alcanza PF>1,20 y estaba congelado como control no rescatable.
- Long QQQ / short SPY fijo: 496 trades, WR 47,984%, PF 0,921644 y
  -413,249 bps.

No se invierte la regla ni se seleccionan 2022-10/2023-06. El control momentum
no autoriza una V1R1 porque fue observado después de abrir desarrollo y tampoco
supera la gate agregada.

## Auditoría independiente

La recomputación directa de `trades.csv` confirmó:

- 496 filas ejecutadas, fechas 2022-01-04..2023-12-29;
- cero filas posteriores a 2023, cero días duplicados/overlap;
- hold único 180m y coste único 2 bps;
- WR/PF/PnL exactos al manifest;
- 24 meses presentes, mínimo 19 trades, cinco positivos y dos PASS;
- 501 fuentes por ticker y cinco exclusiones explícitas;
- `outer_2024_2025_opened=false`, `holdout_2026_opened=false` y
  `production_changed=false`.

Hashes compactos:

- source inventory: `0311dc5ce66e09f4af9bda249f3c9e2e377cbe65fa1376229357ffcd75f9eb57`;
- trades: `48459a8c97bfb5b88c3a8b17cebb4ab3655910eeda89a91be0a746da8080dfc0`;
- monthly: `75c76e2aa987368b17fd9f13c658507e236951cde79a329d4fc19aaec915a9af`;
- controls: `c23ecd72963ca07a22bd440f54d199a3f76f2be764d3abcd48a09dafc4600a54`;
- summary JSON: `5d353cc43da354098f0c966470801d75a7ae75ae81b6b8dd28bec7adc6053395`.

Artefactos:
`results/_diagnostics/cross_session_relative_value_v1_development_202201_202312/`.

## Stop rule

No cambiar ancla, señal, coste, reloj, hold, threshold o signo; no añadir beta,
z-score o ML; no abrir outer ni traducir a opciones. La conclusión específica
es que la reversión intradía fija de la divergencia QQQ frente a SPY/SPXW no
tiene edge mensual estable. Producción permanece intacta y el programa vuelve a
`NO_PROFITABLE_CAUSAL_POLICY` sin familia activa.
