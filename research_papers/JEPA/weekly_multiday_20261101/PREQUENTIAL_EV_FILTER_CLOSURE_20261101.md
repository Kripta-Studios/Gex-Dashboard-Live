# Cierre del filtro de valor esperado y siguiente comparación

Los tres filtros fallan el requisito de beneficio neto adverso positivo en cada
mes completo. Esta familia queda cerrada; no se ajustan ahora su buffer, mínimo
de historia o regularización para rescatar el resultado. El goal general sigue
activo y no existe un modelo aceptado para operar.

| Padre | Control, USD netos | Filtro, USD netos | Mejora del neto | Meses positivos control→filtro |
|---|---:|---:|---:|---:|
| Congelado | −20.204,20 | −17.691,20 | +2.513,00 | 3/8→2/8 |
| Mensual | −12.625,40 | −17.044,60 | −4.419,20 | 2/8→2/8 |
| Semanal | +2.693,80 | −38.255,80 | −40.949,60 | 3/8→1/8 |

Netos continuos enero2–septiembre17, con costes adversos. Los ocho meses son
enero–agosto completos; septiembre parcial se informa separado. DD realizado
del filtro:44.154,00/23.394,30/38.255,80USD para congelado/mensual/semanal.
Reducir ese DD no equivale a rentabilidad estable ni mide el riesgo MTM intratrade.

En el semanal, abril y mayo pasan de +37.076,00/+25.355,20 a −1.584,40/−1.456,60;
junio empeora de −10.124,40 a −20.165,40. Julio–septiembre quedan en cero por
ausencia de fills. La abstención evita pérdidas posteriores, pero pierde las
grandes ganancias anteriores. No es una resta mecánica de operaciones: ambos
libros pueden tener posiciones distintas y liberar capital en fechas distintas.

El error optimista medio de EV en intenciones ACCEPTED se reduce, pero sigue
positivo. En todo INTENTIONS, el score descontado pasa a sesgo negativo. Esto
es evidencia de que esta regla conservadora no mejoró suficientemente la
selección económica; no identifica una causa única ni prueba que toda
calibración o abstención sea inútil. No se elige ticker, mes o frecuencia.

Auditor independiente PID47400 exit0 retenido19:54:51.170550UTC del1nov:
audit2012cc51c56b043b9c973dcb3c514a5d7a0fb158134a403963decc17d17713e2,
exitbc2fef5ec296d57dc078cf43d4a15399254b122a7df6088b003a38fe35cb4e0a.
Reconstruye515intenciones,1584estados,12libros y216diagnósticos, máximo error0.
Revisor read-only reconcilió108valores mensuales y12totales contra los ledgers,
sin diferencias. Productor10716/manifest4c166202/exit76962d8c permanece inmutable.
Archivo auditor7copias22844B, receipt8e3791561b579c565d93661cf7ce88811b1d662090687a037258c76b1d5df528.

Reporte descriptivo generado desde artefactos auditados, sin fit/inferencia/replay:
[informe y gráfico](prequential_ev_filter_result_01/PREQUENTIAL_EV_FILTER_RESULT_20261101.md).
Reporte3a4ae27e/receipt554338fb, PNGfa9d34d3 ySVG1dfd5d40 fueron copiados exactos;
archivo4copias238197B, receiptb3ad41b22e82783e2b13a61a1e790629451e77607e1572a80cdcd5fe941e7ad3.
Root inspeccionó el PNG completo y el texto. Review final CLEAR_REPORT:
285comparaciones de tablas frente a datos sellados, cero diferencias;
conserva ENTRY/EXIT, payoff potencial/PnL, cotas, septiembre y ausencia de garantía.
Base/adverse completos están en el summary y los12ledgers auditados del
[archivo productor](prequential_ev_filter_producer_archive_01/payload/summary.json).

Limitación operativa explícita del renderer: el autor ejecutó la herramienta
con exit0 observado y guardó gate CPU[0]/8vars/RAM/commit en report_receipt,
pero no creó observer, logs separados o recibo de exit porPopen externo como
se había solicitado. No se fabrica esa evidencia ni se confunde el recibo de
artefactos con un exit. No se repitió el render. Productor y auditor científicos
sí conservan sus procesos/logs/exits porhandle; la revisión de tablas/imagen
del informe permanece válida. Un helper root posterior buscó erróneamente un
manifest del auditor inexistente; sólo existe audit.json. Falló antes de leer
métricas, se corrigió la lectura y nunca se relanzó el auditor.

La aclaración pedida por el usuario sobre el control semanal es:
64.948,20USD de tres meses ganadores −59.497,20USD de cinco meses perdedores
−2.757,20USD de septiembre parcial =2.693,80USD netos. Son dos mil seiscientos
noventa y tres dólares con ochenta centavos, no millones. El drawdown de46.860,80
es una caída desde un máximo anterior de la cuenta, no el saldo final.

Siguiente hipótesis por la pregunta del usuario: actualización diaria frente
a mensual/semanal y congelado, manteniendo receta/riesgo/costes y todo el periodo.
Inspección read-only de q3_frozen_scorer:178sesiones y42estados únicos existentes
(4mensuales exclusivos,33semanales exclusivos,5compartidos). Una agenda diaria
completa supone136fechas nuevas; los42estados coincidentes pueden reutilizarse
byte a byte. No se ha escrito contrato ejecutable ni hecho fit diario.
Todos conservan CAL63 y TRAIN anterior aCAL: mayor frecuencia no hace que los
coeficientes aprendan de esas63sesiones recientes; CAL sólo actualiza la mezcla
probabilística. Esta frontera debe conservarse y explicarse en el diseño.
No combinar el filtro fallido ni escoger subperiodos. Primero contrato y
revisión de nueva familia, luego implementación/fixtures/binding y comparación
causal completa. Todo2026 sigue SEEN_DEVELOPMENT; promotion_approved=false.
