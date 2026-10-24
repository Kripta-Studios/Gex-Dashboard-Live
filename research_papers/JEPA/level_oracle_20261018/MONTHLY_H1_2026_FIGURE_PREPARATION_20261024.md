# Preparación de la reconciliación y gráfica de H1 2026

24 de octubre de 2026. **Preparado; sin ejecución sobre resultados reales.**
El nuevo script `reconcile_plot_monthly_h1_2026_20261024.py` adapta sólo la
reconciliación documental y la figura del reporter consolidado de 18 meses.
No se cambia el reporter congelado ni el script/artefactos cerrados de 2025.
Root revisará y publicará esta preparación antes de usarla, y confirmará por
separado el PASS y exit 0 de la auditoría compuesta y del reporter.

## Alcance y ausencia explícita

La entrada futura debe tener manifest COMPLETE fijado externamente y recibo
de exit 0 fijado externamente, sin cambios de audit/pins ni error de monitor.
Se exigen sus siete outputs exactos y se rehashean todos antes y después.
Summary debe declarar el scope compuesto, enero de 2025–junio de 2026 exactos,
los tres modos y tickers, desarrollo visto y selected_mode=null. No se abre
ningún path referenciado por source_inventory: sólo se rehashea ese archivo.

Se cotejan CSV contra JSON y los ledgers consolidados contra las tablas:

| Cobertura | Cantidad |
|---|---:|
| Grupos ticker-mes-modo de los 18 meses | 162 |
| Agregados mensuales ALL | 54 |
| Grupos de periodo, 2025 y 2026 H1 | 24 |
| Filas diarias, incluidos los tres modos | 3.357 |
| Ticker-días de 2026 H1 esperados/disponibles/ausentes | 369 / 363 / 6 |
| Filas diarias ausentes, repetidas en los tres modos | 18 |

Las ausencias son QQQ/SPY en 20260401, 20260409 y 20260415. Deben conservar
NO_EVALUABLE y null en trades, netos y attempts. Se rechaza un cero observado
en esas celdas, cualquier ledger/attempt en una fecha ausente, duplicados y
fechas fuera del soporte diario disponible. Los días disponibles sin fills
conservan cero. El neto medio por día usa exclusivamente días disponibles;
el status de calendario conserva NO_EVALUABLE_MISSING_SOURCE donde corresponda.

El periodo documental `2026H1` se traduce al prefijo de fechas `2026` para
reconciliar; no se usa literalmente como prefijo de YYYYMMDD. Trades, netos,
PF/flag infinito, WR, drawdown, holding, razones de salida y cobertura se
cotejan por todos los grupos, sin seleccionar tickers, modos o meses.

## Figura futura

PNG y SVG de nueve paneles: tres modos por tres tickers, con todos los seis
meses de H1 2026 y barras separadas base/adverse. Mantiene la misma escala
vertical entre modos dentro de cada ticker. Título SEEN DEVELOPMENT y
selección congelada null; nota explícita de netos sobre días disponibles y
seis ausencias no equivalentes a PnL cero. Los paneles QQQ/SPY indican las
tres ausencias de abril para cada ticker. No se ha renderizado una figura real
en esta preparación; la inspección visual queda pendiente del cierre admitido.

La salida debe ser una raíz nueva distinta del reporte de entrada. Conserva
snapshot del script, PNG/SVG, reconciliation.json y manifest final. El código
se rehashea al cierre. Sin manifest COMPLETE no hay entrega cerrada.

CLI futuro, sólo después de revisión/publicación y confirmación de root:

```text
python reconcile_plot_monthly_h1_2026_20261024.py --report ABS_CLOSED_18_MONTH_REPORT --manifest-sha256 EXTERNAL_MANIFEST_SHA --exit-receipt ABS_REPORT_EXIT_JSON --exit-sha256 EXTERNAL_EXIT_SHA --out ABS_FRESH_FIGURE_ROOT
```

## Validación artificial de la adaptación

**15 pruebas PASS en 1,14 s**, proceso 2,172352 s, exit 0. Se usaron tablas
artificiales pequeñas: calendario de 3.357 filas, nulls/ausencias, duplicados,
periodo H1, denominador disponible y métricas literales de dos trades (+5/−2
base, +3/−4 adverse). No se importó matplotlib ni se leyó reporte o dato real.
Ruff y py_compile pasaron. Los hashes se registraron antes del proceso y
coincidieron después.

Gate Windows anterior a pytest, 2026-10-24 03:46:08,884495 UTC: RAM disponible
4.381.196.288 bytes y commit libre 3.409.231.872 bytes, ambos sobre el mínimo
decimal de 2.000.000.000 bytes. No representa una reserva de recursos.
[Admisión](continuation_20261024/monthly_h1_figure_preparation/admission.json),
[resultado](continuation_20261024/monthly_h1_figure_preparation/result.json),
[stdout](continuation_20261024/monthly_h1_figure_preparation/stdout.txt) y
[stderr](continuation_20261024/monthly_h1_figure_preparation/stderr.txt) preservados.

| Archivo | SHA256 |
|---|---|
| reconcile_plot_monthly_h1_2026_20261024.py | `658e0f9d23a83c1c7400b684525c87fd50f706b34023beb33cce42401e66e3e4` |
| test_reconcile_plot_monthly_h1_2026_20261024.py | `576bd20f0bdf34f1ff4823ad6f302d44fa46d98653a889b9613d3f134ecbdf26` |
| Original 2025 intacto | `5b5cf477eaf9fdef7aa7d9db8fc638dcb2aeefec1b9db06208955e6f26a61c0f` |

No se entrenó, infirió, modificó una política ni abrió una familia científica.
Esta adaptación representa resultados documentales ya auditados y no repite
la auditoría económica. Todo sigue condicionado a scores sellados y desarrollo
visto; no prueba paridad live, evidencia prospectiva o promoción.
