# CALENDAR_RISK_REVERSAL_PRESSURE_V1 — cierre de desarrollo 2023

## Veredicto

`CLOSED_PARTIAL_INCREMENTAL_EDGE`.

El one-shot congelado se ejecutó desde `8fe170d1` con manifest preejecución SHA
`f00a7ef096a70c6bb3dd9496c84137d54dcef6da163f2762dc3b3a7193d35f79`.
La señal logra PF agregado mayor que uno y PnL positivo, pero no cumple la gate
conjunta. Outer 2024–2025, holdout 2026 y producción no se abrieron.

## Resultado

| Scope | Trades | WR | PF | PnL neto bps | Meses PASS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pooled | 739 | 50,068% | 1,058294 | +729,690 | 12/36 |
| QQQ | 245 | 52,245% | 1,173476 | +812,500 | 5/12 |
| SPXW | 246 | 47,561% | 0,912372 | -356,808 | 4/12 |
| SPY | 248 | 50,403% | 1,072835 | +273,999 | 3/12 |

La frecuencia pasa en las 36 celdas, con mínimo 19 trades. QQQ y SPY alcanzan
PF>1 y neto positivo; SPXW no. Ningún ticker alcanza simultáneamente PF>1,20 y
los doce meses positivos. Los meses que pasan todos los gates son:

- QQQ: enero, marzo, septiembre, octubre y diciembre;
- SPXW: abril, julio, septiembre y diciembre;
- SPY: febrero, octubre y diciembre.

Antes de costes, QQQ gana `+1.057,500` bps, SPY `+521,999` y SPXW pierde
`-110,808`. Pooled gross es `+1.468,690` bps; 739 bps de coste dejan
`+729,690`. Por tanto existe información agregada parcial, pero no una policy
estable por ticker/mes.

## Controles no elegibles

| Control | QQQ PF | SPXW PF | SPY PF |
| --- | ---: | ---: | ---: |
| Signo inverso | 0,773815 | 0,965782 | 0,820483 |
| Always-long | 1,363241 | 1,098200 | 1,101088 |

El inverso pierde en los tres tickers, lo que apoya que el signo directo contiene
algo de información. Always-long refleja el drift favorable de 2023, pero era
solo control y no puede sustituir la policy ni autorizar selección post-hoc.

## Diagnóstico SPXW frente a SPY

El fallo de SPXW no procede de que su subyacente se mueva de forma materialmente
distinta a SPY. En las 246 fechas comunes:

- la correlación de retornos 10:36→13:36 es `0,999733`;
- el signo del retorno coincide en 246/246 y la diferencia absoluta mediana es
  solo `0,523` bps;
- la correlación de las presiones calendar-RR es bastante menor, `0,580247`;
- las acciones emitidas coinciden solo en 148/246 fechas, `60,163%`.

Cuando las acciones coinciden, ambos ledgers son casi idénticos: SPXW PF
`1,022360`/+53,925bps y SPY PF `1,021306`/+51,472bps. En las 98 fechas de
desacuerdo, SPXW cae a PF `0,752601`/-410,733bps mientras SPY alcanza PF
`1,170042`/+226,215bps. La diferencia económica se origina en el signo producido
por las dos superficies de opciones, no en el path del cash subyacente.

Copiar retrospectivamente la señal SPY a SPXW es diagnóstico de desarrollo, no
validación: habría producido PF `1,071604`, WR `50,0%`, +268,657bps, mínimo 19
trades/mes y 5/12 meses positivos. Cualquier arquitectura compartida debe
predeclararse como familia nueva y validarse por primera vez en 2024–2025.

## Sensibilidad al coste

El edge pooled también es pequeño frente a ejecución. Sobre los 739 trades, el
gross sin coste es PF `1,120868` y +1.468,690bps. Con 1bp queda el resultado
reportado PF `1,058294`; con 2bps pasa a PF `0,999278` y -9,310bps; con 3bps a
PF `0,943579` y -748,310bps. Esta fragilidad refuerza que PF>1 agregado a 1bp no
es una base suficiente para promover.

## Auditoría independiente

- 741 eventos válidos/normales y 739 trades; dos presiones cero no operan.
- Fechas, signo, opens 10:36/13:36, retorno log, hold180, coste1bp y controles
  fueron recalculados fila a fila.
- 36/36 celdas se recalcularon con desigualdades estrictas.
- 741/741 fuentes underlying se rehashearon y pertenecen únicamente a 2023.
- Cero duplicados ticker-día; los grids completos pasan.
- Las tres filas inválidas SPY 2023-06-05 anteriores a 10:19 siguen fuera de la
  ventana consumida y no se reparan.
- 2024–2026 y producción permanecen cerrados.

Hashes:

- `SUMMARY.json`: `7b92f182eacb5c6b69a0f3d20c7a2deb84d6e2b1c61fd8b94ecc2db5654629b6`.
- `trades.csv`: `9c5178045e4172e6bfaf6d7bf30eb07a6ae68ff66a3bb8b738965de1e0d0fa66`.
- `monthly_metrics.csv`: `8eb7d6299537c3d5efd714f3b5bb648c9c0018f7c559a1c35f38d63e3db938fa`.
- `ticker_summary.csv`: `dfc0d9cab68825db309c313f46a7fbb0c94dfb5118e3f5503a2a862dc9156d0c`.
- `controls_summary.csv`: `8b62b18ea5c66c090f133ae737dfbbfa423a1455c8bd7c3da1d248c97d7571a7`.
- `source_inventory.csv`: `92e40d2bafe0a38db5f6c5e99a63122dba6f788ae1caf0abfdb42cccbcac60c8`.
- `source_audit.csv`: `a44ae67e2a3e19f84d747e9a276df55db6d9c04079c9a4278d7cc14952c0460c`.

## Stop rule

No abrir 2024–2026, seleccionar QQQ/SPY, invertir SPXW, escoger meses, cambiar
delta/expiry/reloj, añadir threshold o entrenar un modelo sobre esta señal. El
resultado sí se registra como progreso desde PF<1 a PF pooled1,058 y dos tickers
rentables, pero la familia queda cerrada por estabilidad insuficiente.
