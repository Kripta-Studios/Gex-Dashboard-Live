# Reconciliación y gráfica independiente de 2025

Se verificaron los outputs del reporter cerrado, con exit observado 0, antes
de leer sus tablas. La reconciliación terminó con
`PASS_INDEPENDENT_DESCRIPTIVE_RECONCILIATION`. No se repitió la auditoría
científica, ningún fit, inferencia, selección o replay del scheduler.

La gráfica muestra los doce meses completos, los tres tickers y los tres modos.
Cada panel separa netos base y adverse; la escala vertical se mantiene entre
modos dentro de cada columna de ticker. El título y pie identifican desarrollo
visto, selección congelada null y ausencia de evidencia prospectiva/promoción.
La imagen PNG se inspeccionó visualmente: los nueve paneles, leyenda y notas
son legibles y no están recortados.

- [Gráfica PNG](continuation_20261024/monthly_validation_2025_independent_figure/monthly_net_usd_all_modes_2025.png).
- [Gráfica SVG](continuation_20261024/monthly_validation_2025_independent_figure/monthly_net_usd_all_modes_2025.svg).
- [Recibo de reconciliación](continuation_20261024/monthly_validation_2025_independent_figure/reconciliation.json).
- [Manifest](continuation_20261024/monthly_validation_2025_independent_figure/manifest.json).
- [Script reproducible](reconcile_plot_monthly_validation_20261024.py).

## Qué se verificó

Los siete outputs del reporter se rehashearon, además del manifest y del recibo
de exit externo. `monthly.csv` y `periods.csv` coinciden exactamente con las
tablas correspondientes de summary.json. Se comprobaron 108 grupos
ticker-mes-modo, 36 agregados mensuales ALL y 12 filas de periodo.

Los 9.566 FILLED coinciden exactamente con las filas FILLED de los 9.569
attempts consolidados. Mediante agregación descriptiva independiente se
cotejaron trades, netos base/adverse, PF y su flag infinito, win rate,
drawdown, holding, motivos de salida, cobertura y attempts para los 156 grupos
mensuales/de periodo. Las 2.250 filas diarias también coinciden con los fills
y netos del ledger. Son 750 ticker-días de 2025 representados por cada uno de
los tres modos; no son 2.250 sesiones independientes. No hay fuentes ausentes
en este corte de 2025; los días observados sin fills conservan cero.

La suma anual es negativa en las nueve combinaciones modo/ticker tanto a
coste base como adverse. Se documentan todas, sin elegir una alternativa:

| Modo | Ticker | Neto base USD | Neto adverse USD |
|---|---|---:|---:|
| static | SPXW | -27.401,60 | -29.981,60 |
| static | SPY | -10.084,60 | -11.793,60 |
| static | QQQ | -11.666,20 | -13.352,20 |
| expanding | SPXW | -53.452,60 | -56.171,60 |
| expanding | SPY | -8.652,40 | -10.097,40 |
| expanding | QQQ | -13.138,80 | -15.050,80 |
| rolling12 | SPXW | -93.080,00 | -96.006,00 |
| rolling12 | SPY | -15.080,20 | -17.130,20 |
| rolling12 | QQQ | -13.921,20 | -15.988,20 |

## Identidad y ejecución

Root de entrada:
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_2025_consolidated_report_20261024_01`.
Manifest SHA `66108b5eb4e678569dcc82a46ebaa92f569a3601e160a2ab1ac781725313db0f`.
El recibo sibling `_logs/exit.json`, SHA
`4f4987abc7ca1c4a10d08bbba3af6dcbec92fc5033411049bc33d441930852ef`,
registra PID 20216, exit 0, 109,073846 s, pins/audit sin cambios y stderr vacío.
La autoridad económica heredada conserva el SHA
`ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc`.

Root nuevo de gráfica:
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_2025_independent_figure_20261024_01`.
Se copiaron sus cinco archivos al directorio compacto enlazado arriba,
comprobando igualdad SHA256 de origen y copia.

| Artefacto | SHA256 |
|---|---|
| Script | `5b5cf477eaf9fdef7aa7d9db8fc638dcb2aeefec1b9db06208955e6f26a61c0f` |
| PNG | `5331dcebfd712ecdc02c3dfebdd65e49458c067cddb5305a25d8647f1db0929f` |
| SVG | `f1055f10b729002772989d8d61febd7d16621927dd71f3dab913086aa0edb84c` |
| reconciliation.json | `5f1c87dd083684f2b3e4ce3f43785222ad18b274014e0b8f61dbfe700b02f8f9` |
| manifest.json | `22180177cc8678a6da3e636aa80589fd076fabf363f0bc0f881f77a032c1b49c` |

La invocación del script usó `--report` y `--out` con esos roots,
`--manifest-sha256` con el pin anterior y `--exit-receipt`/`--exit-sha256` con
el recibo externo citado. Ruff y py_compile pasaron. La ejecución finalizó
con exit 0 en 6,1919204 s observados por herramienta; no se creó un log bruto
separado. Su gate Windows previo midió RAM 7.554.551.808 y commit libre
5.294.100.480 bytes, sobre el mínimo decimal de 2.000.000.000 bytes.

El script sólo abrió outputs del reporter. El source_inventory se rehasheó
como archivo, sin seguir sus referencias a features, labels, scores, modelos
o raw. Las cifras siguen condicionadas a la auditoría cerrada y scores
sellados; el gráfico no acredita paridad live ni rentabilidad futura.
