# Contrato propuesto — diagnóstico de robustez EV H2

Estado: **BORRADOR PRE-CÁLCULO; NO AUTORIZA EJECUCIÓN**.  
Fecha: 2026-11-01.  
Alcance: sensibilidad descriptiva del libro `EV_TOP1_H2 / EVAL / adverse` ya cerrado. No es una nueva política, backtest, selección, auditoría independiente ni autorización de promoción.

## 1. Autoridades e inputs inmutables

- Dataset: `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_v2_01`.
- SHA-256 externo de `manifest.json`: `bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8`.
- Evaluación: `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_ev_v2_01`.
- SHA-256 externo de `manifest.json`: `54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96`.
- Archivos necesarios, siempre mediante los pins internos de esos manifests:
  `candidates.jsonl`, `coverage.json`, `summary.json` y
  `ledger_ev_top1_h2_eval_adverse.jsonl`.

El programa futuro debe verificar los dos manifests por SHA externo, cruzar el
pin del dataset contenido en el manifest de evaluación, verificar cada archivo
antes de leerlo y rehashearlo al final antes de publicar. No leerá DTheta ni
ninguna fuente de mercado.

## 2. Universo congelado

El conjunto y orden de decisiones/trades son los del ledger sellado. Se unen
`ENTRY` y `EXIT` uno-a-uno por `candidate_id` y se reconcilian con las filas de
`candidates.jsonl`. No se vuelve a puntuar, calibrar, seleccionar, filtrar,
ordenar, dimensionar ni simular bloqueos de capital. `WAIT`, `NO_FILL`,
`NO_OPPORTUNITY` y `CAPITAL_BLOCKED` no se reinterpretan.

Toda sensibilidad conserva exactamente los 75 trades cerrados observados en el
libro adverso EVAL. No se permite rescate por ticker, mes, lado, slippage o
resultado.

## 3. Barrido de slippage predeclarado

Se reportan todos, en este orden, los puntos por lado:

`0.02, 0.05, 0.10, 0.25, 0.50, 1.00` puntos de prima por opción y por lado.
Cada punto se multiplica por 100 en el flujo de caja; no son importes USD por
contrato.

Para cada trade con `ask` de entrada y `bid` de salida del candidato sellado:

- `entry_debit_s = 100 * (ask + s) + 1.30`
- `exit_credit_s = 100 * max(bid - s, 0) - 1.30`
- `net_s = exit_credit_s - entry_debit_s`

Si el exit está ausente, `bid = 0`, conservando su carácter de cota inferior.
La comisión queda fija en 1,30 USD por lado. Para cada `s` se publican, sin gate
ni búsqueda de umbral: neto, PF, trades, ganancias/pérdidas brutas, máximo
drawdown realizado y neto por ticker/mes. El drawdown no es mark-to-market.

## 4. Diagnóstico de igual riesgo

Este bloque usa sólo el coste adverso sellado `s=0.02`:

- `r_i = net_adverse_i / entry_debit_adverse_i`.
- Por ticker: soporte, promedio y mediana de `r_i`, y retorno agregado compensado
  por débito `sum(net_i) / sum(entry_debit_i)`.
- Resumen de ticker con ponderación igual: media aritmética de los tres retornos
  agregados por débito de SPY, QQQ y SPXW.

No se alteran contratos ni capital. Es una normalización diagnóstica, **no una
cartera ejecutable**: implicaría cantidades fraccionarias y omite la trayectoria
de capital; no puede utilizarse para reclamar rentabilidad ni para rescatar un
ticker.

## 5. Concentración, no contrafactuales de política

Sobre el PnL adverso sellado se publican sensibilidades mecánicas:

- retirar las mayores 1, 3 y 5 ganancias globales, con desempate estable por
  `(-net_usd, exit_date, candidate_id)`;
- excluir, por separado, cada mes de salida de enero a junio de 2026.

Se reportan soporte y neto restantes. Estos cálculos no reejecutan la política,
no cambian las decisiones y no son políticas alternativas.

## 6. Block bootstrap predeclarado

Si la revisión confirma que el calendario común puede reconciliarse sin
ambigüedad, se usa únicamente Python estándar:

- unidad: fecha oficial de entrada; todos los tickers de la misma fecha se
  agregan juntos;
- universo: sesiones oficiales EVAL comunes a SPY/QQQ/SPXW, incluyendo PnL cero;
- PnL del trade atribuido a su `entry_date`;
- moving block bootstrap circular de bloques contiguos de 5 sesiones;
- `seed = 20261101`, `10_000` remuestras;
- cada remuestra concatena bloques hasta longitud `N` y se trunca a `N`;
- estadístico: PnL total H1; se reportan mediana, media e intervalo percentil
  empírico `[2.5 %, 97.5 %]`; 0 USD se muestra sólo como referencia económica.

No se optimiza semilla, longitud, estadístico ni intervalo; no se publica
p-value. El remuestreo supone estacionariedad aproximada y que la dependencia
temporal relevante queda acotada por bloques de cinco sesiones. El intervalo es
exploratorio, no una prueba estadística ni una distribución bajo el nulo. Si el
calendario común, los ceros o la correlación por fecha no pueden
reconciliarse exactamente, el bootstrap se omite con estado
`OMITTED_FAIL_CLOSED`, sin sustituirlo por remuestreo de trades independientes.

## 7. Salida y afirmaciones prohibidas

Raíz futura propuesta, que debe estar ausente:
`D:/GexResearchArtifacts/weekly_multiday_20261101/h2_ev_robustness_diagnostic_01`.

Archivos futuros: `diagnostic.json` y `manifest.json`; opcionalmente una figura
descriptiva sólo después de revisión. El manifest pineará inputs, implementación
y outputs y marcará `descriptive_only=true`, `development_seen=true`,
`selection_performed=false`, `refit_performed=false`,
`independently_audited=false` y `promotion_approved=false`.

Queda prohibido afirmar robustez, significancia, independencia, audit PASS,
rentabilidad futura, selección o preparación técnica a partir de este diagnóstico.

