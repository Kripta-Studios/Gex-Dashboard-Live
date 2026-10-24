# H1 2026: reconciliación independiente y figura completa

24 de octubre de 2026. **PASS_INDEPENDENT_DESCRIPTIVE_RECONCILIATION** sobre
los outputs cerrados del reporter de 18 meses. La ejecución única terminó
exit 0; no hubo cambios de parámetros, filtros, políticas o modelos. La
[interpretación inicial](MONTHLY_H1_2026_INITIAL_INTERPRETATION_20261024.md)
permanece intacta como registro anterior a esta consolidación.

- [PNG completo](continuation_20261024/monthly_h1_2026_independent_figure/monthly_net_usd_all_modes_2026_h1.png).
- [SVG completo](continuation_20261024/monthly_h1_2026_independent_figure/monthly_net_usd_all_modes_2026_h1.svg).
- [Reconciliación](continuation_20261024/monthly_h1_2026_independent_figure/reconciliation.json).
- [Manifest de outputs](continuation_20261024/monthly_h1_2026_independent_figure/manifest.json).
- [Archivo exacto con recibos](continuation_20261024/monthly_h1_2026_independent_figure/archive_manifest.json).

Los nueve paneles incluyen todos los seis meses de H1, los tres tickers y los
tres modos, con barras base/adverse separadas. Se usa la misma escala vertical
entre modos dentro de cada ticker. Los títulos identifican las tres ausencias
de abril en SPY y QQQ; el pie aclara que no son PnL cero. SEEN DEVELOPMENT,
selección congelada null y límites prospectivos permanecen visibles. El autor
de esta reconciliación y root inspeccionaron el PNG y lo encontraron legible,
sin recortes; root confirmó PASS visual. No se regeneró tras esa inspección.

## Reconciliación de todo el consolidado

Se verificaron el manifest externo y el recibo externo de exit 0 del reporter,
y se rehashearon sus siete outputs antes y después. CSV y summary coinciden
exactamente. Se cotejaron las 216 filas mensuales —162 ticker-mes-modo y 54
ALL—, las 24 filas de periodo y las 3.357 filas diarias de enero de 2025 a
junio de 2026. La figura representa H1; la comprobación cubre ambos periodos.

Los 14.242 FILLED coinciden con las filas FILLED de los 14.246 attempts.
Trades, netos base/adverse, PF y flag infinito, win rate, drawdown, holding,
motivos de salida, cobertura y attempts se reconciliaron con el ledger
consolidado; también se cotejaron trades y netos de cada día disponible.
Estos conteos agrupan resultados de tres políticas distintas, no una política
ejecutada conjunta. No se repitieron scheduler, fit, inferencia o auditoría raw.

H1 conserva 369 ticker-días esperados, 363 disponibles y seis ausentes por
modo: QQQ/SPY en 20260401, 20260409 y 20260415. Sus 18 filas en las tres
políticas permanecen NO_EVALUABLE con economía null. No hay fills ni attempts
en esos días. Los días disponibles sin fill se conservan como observaciones
cero, y los promedios diarios usan sólo días disponibles.

## Lectura mensual sin selección posterior

Ninguna combinación modo/ticker tiene neto mensual positivo en los seis meses,
en ninguno de los escenarios de costes. La siguiente tabla incluye todos los
grupos, también ALL. «Meses positivos» describe el signo del neto de días
disponibles: abril SPY/QQQ/ALL sigue incompleto por sus fuentes ausentes y no
se presenta como un mes completamente evaluable.

El recuento 6/6 es descriptivo y no introduce un gate nuevo: el protocolo H1
exige al menos 3/6 meses positivos, netos base y adverse >0, PF base >=1,20 y
al menos 60 trades por ticker, junto al requisito diario del usuario.
Expanding QQQ alcanza 3/6 meses positivos base, pero falla los netos y el PF.

| Modo | Ticker | Meses positivos base / adverse, de 6 | Días disponibles sin fill, ene/feb/mar/abr/may/jun |
|---|---|---:|---|
| static | SPXW | 2 / 2 | 0 / 0 / 0 / 0 / 0 / 0 |
| static | SPY | 2 / 1 | 4 / 0 / 0 / 1 / 1 / 0 |
| static | QQQ | 2 / 2 | 0 / 0 / 1 / 0 / 0 / 1 |
| static | ALL | 2 / 2 | 4 / 0 / 1 / 1 / 1 / 1 |
| expanding | SPXW | 2 / 2 | 0 / 0 / 0 / 1 / 3 / 0 |
| expanding | SPY | 0 / 0 | 9 / 2 / 1 / 10 / 9 / 5 |
| expanding | QQQ | 3 / 2 | 5 / 0 / 0 / 6 / 7 / 3 |
| expanding | ALL | 2 / 2 | 14 / 2 / 1 / 17 / 19 / 8 |
| rolling12 | SPXW | 1 / 1 | 0 / 0 / 0 / 0 / 1 / 0 |
| rolling12 | SPY | 1 / 0 | 7 / 1 / 0 / 1 / 4 / 0 |
| rolling12 | QQQ | 0 / 0 | 4 / 2 / 1 / 1 / 2 / 2 |
| rolling12 | ALL | 1 / 1 | 11 / 3 / 1 / 2 / 7 / 2 |

Las tres sumas H1 por modo son negativas con ambos costes: static
−8.746,00/−11.921,00 USD, expanding −20.616,00/−23.358,00 y rolling12
−47.347,60/−50.763,60, respectivamente base/adverse. QQQ static conserva
+548,40 USD base pero −422,60 adverse; no cambia la selección null ni rescata
la familia. SPXW static tiene fills en cada día disponible, pero pierde con
ambos costes: actividad diaria y rentabilidad son requisitos distintos.

Los [216 grupos mensuales con cifras completas](continuation_20261024/monthly_18month_report/report/monthly.csv),
los [24 grupos de periodo](continuation_20261024/monthly_18month_report/report/periods.csv)
y el [resultado consolidado](MONTHLY_18MONTH_REPORT_RESULT_20261024.md)
conservan todos los valores. No se infiere una causa del comportamiento mensual,
se elige un subconjunto favorable ni se introducen nuevas reglas.

## Identidad, recursos y preservación

Script ejecutado una vez: `reconcile_plot_monthly_h1_2026_20261024.py`, SHA
`658e0f9d23a83c1c7400b684525c87fd50f706b34023beb33cce42401e66e3e4`.
Entró desde el reporte cerrado
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_18month_consolidated_report_20261024_01`,
manifest SHA `6c104c866c320beea811b7ee295a4b625d56d44a905a352e1d6f34d9cee7932d`
y recibo sibling `_logs/exit.json` SHA
`eafcea8ed68506731d72ed0890dc84b96169bfde73caf65154328cfa27fabfec`.

Salida nueva:
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_h1_2026_independent_figure_20261024_01`.
PID 6872, inicio 2026-10-24 04:16:05,082485 UTC, salida 0 a las
04:16:11,673127 UTC; 6,590318 s, stderr vacío y pins sin cambios. El
[recibo de ejecución](continuation_20261024/monthly_h1_2026_independent_figure/execution_logs/exit.json)
conserva el comando y hashes completos.

Gate Windows previo del lanzador: RAM 7.722.704.896 y commit libre
4.670.259.200 bytes. El propio script volvió a medir 7.699.922.944 y
4.641.120.256 bytes antes de sus imports numéricos. Ambos exigieron al menos
2.000.000.000 bytes por recurso; son observaciones, no picos ni reservas.

| Artefacto | SHA256 |
|---|---|
| PNG | `b6e62b94cbb0ee591959bdc5225f502740a0d85be600c8fa11a5f82fcd92a08e` |
| SVG | `2eed8c2a4fc04ab348f43e6a5192d8b9208749373ce738af8c587c51b0fa1c4b` |
| reconciliation.json | `a44a929ada34091dc6787e5b227c784a73e9786a8e0090aa990f3154ad153f8a` |
| manifest.json | `473a836e3ac7ed76c1fb148cdac40d76328e47fe55b789a041cb817d3e5c8328` |
| execution_logs/exit.json | `90a9f3d0441594536900351b811620b0f671091ee132a6d9693977233996f608` |
| archive_manifest.json | `658c69bea505308fde845c283e71d299cbc0dc36e576959d5c196c3725276f68` |

El archivo compacto contiene nueve copias exactas, 563.020 bytes, más su propio
manifest. No se sobrescribieron outputs ni handoffs. Sólo se consumieron
outputs del reporter; source_inventory se rehasheó sin seguir referencias a
features, labels, scores, modelos o raw. El alcance sigue siendo desarrollo
visto condicionado a scores sellados, sin evidencia prospectiva ni promoción.
