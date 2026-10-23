# Verificación independiente del informe mensual 152 frente a 424

23 de octubre de 2026. **PASS_INDEPENDENT_COMMON_GREEK_MONTHLY_REPORT_RECONCILIATION.**
Revisor: `/root/tcn_completion`. Este PASS corresponde a la coherencia del informe
con los intentos sellados y auditados; los resultados económicos son negativos.

Root confirmó primero la salida cero por handle del auditor02. Esta revisión
verificó su autoridad SHA256
`45caae6c11cdce9306284367e7742d9dbe17e03a8afeb52eff447b3408758a0d`
y el informe mensual SHA256
`6086af9fba7d5a7423a36eda120c9873415a9c3f3f5b61d9fea0bfa3ab47183c`.
No ejecutó el auditor ni volvió a evaluar scheduler, modelos o inferencia.

El [verificador reproducible](verify_common_greek_monthly_report_20261023.py)
lee exclusivamente evidencia sellada y reconstruye sus sumas con PyArrow y
`math.fsum`, sin importar el reporter, productor o auditor. El
[registro JSON](COMMON_GREEK_MONTHLY_REPORT_VERIFICATION_20261023.json) contiene
los hashes de fuentes y los dieciséis agregados anuales reconstruidos.

- 108 grupos mensuales exactos: dos políticas, tres tickers y dieciocho meses.
- 2.238 ledgers de intentos y registros diarios de política: 750 ticker-días de
  2025 y 369 de 2026H1, cada uno con ambas políticas.
- 16 grupos anuales, incluyendo ALL, reconciliados con los informes auditados.
- 3.365 archivos rehasheados antes y después; cero cambios o diferencias de hash.
- 12.064 comparaciones; máxima diferencia numérica `5,820766091346741e-11`.
  Tolerancia de reconciliación numérica `atol=1e-8`, `rtol=1e-12`; no es un gate
  económico ni modifica las reglas del experimento.

La ejecución terminó con salida cero. Gate previo: RAM disponible
16.991.514.624 y margen de commit 21.628.059.648 bytes. Ruff F y compilación del
verificador pasan. SHA256 del verificador:
`b1fd97e025731c57d26b9ab5972f8efe62f237b0480515a4a2bca8c43aa11b17`.

## Lectura económica preservada

| Periodo | Política | PnL base ALL, USD | PnL adverso ALL, USD | Días observables sin fill |
|---|---|---:|---:|---:|
| 2025 | Control 152 | -76.834,40 | -81.963,40 | 178 |
| 2025 | Greek 424 | -93.912,60 | -98.915,60 | 190 |
| 2026H1 | Control 152 | -43.482,20 | -46.356,20 | 37 |
| 2026H1 | Greek 424 | -35.329,40 | -38.102,40 | 47 |

Cada ticker-periodo tiene neto negativo y PF inferior a uno en ambas políticas,
tanto bajo costes base como adversos. Los seis meses de 2026H1 contienen
respectivamente 2/2/0 meses positivos QQQ/SPXW/SPY en el control y 2/1/2 en Greek.
La menor pérdida agregada Greek en 2026H1 no acredita rentabilidad ni estabilidad.
ALL mezcla escalas monetarias de los tres tickers; no representa retorno sobre
capital ni una ponderación de riesgo común.

Se contrastaron además los CSV finales de 108 filas mensuales y 16 anuales:
3.596 campos coinciden con el summary y los agregados reconstruidos. El
[recibo de CSV y gates](COMMON_GREEK_MONTHLY_CSV_VERIFICATION_20261023.json)
fija sus hashes. El gate económico original de [PROTOCOL.md](PROTOCOL.md)
y [LEARNER_PLAN.md](LEARNER_PLAN.md) exige, por ticker en 2026H1, neto base y
adverso positivo, PF base al menos 1,20, al menos 60 trades y tres de seis meses
positivos. Las seis combinaciones política/ticker fallan ese gate y el conjunto
con actividad observable. El CSV no aplica ese gate H1 a 2025 o ALL y no añade
un umbral de WR.

El [control independiente del archivo consolidado](COMMON_GREEK_ARCHIVE_CONTENT_VERIFICATION_20261023.json)
comparó también `all_attempts.parquet` con las 2.238 fuentes originales: 7.908
filas, de las cuales 7.906 FILLED y dos NO_FILL, sin diferencias en columnas,
tipos de las fuentes no vacías, valores ni orden de filas. Las columnas float
coinciden bit a bit. Se conservan las 1.774 fuentes no vacías y las 464 vacías
sin inventar filas; las fuentes vacías tienen schema null y el consolidado toma
los tipos de las fuentes con filas. El CSV diario conserva 2.238 registros y
35.808 campos escalares exactos; las doce filas de política correspondientes a
seis ausencias tienen `observed_net_base/adverse` nulos. Se rehashearon 3.357
fuentes antes y después, sin cambios. Una primera invocación de este control
abortó al abrir el manifest UTF-8 con el encoding CP1252 por defecto, antes de
leer parquets; la invocación final usa UTF-8 explícito y la incidencia permanece
en el recibo. No se modificó ningún archivo de origen o del paquete.

Ambas políticas fallan el requisito de al menos un fill por día observable en
cada ticker y periodo. Las seis ausencias son exactamente QQQ y SPY en
20260401, 20260409 y 20260415; permanecen dentro del calendario, sin intentos ni
outcomes inventados. Por ello la cobertura universal 2026H1 es NO_EVALUABLE
para QQQ, SPY y ALL, además de sus fallos observados de actividad. SPXW, sin
ausencias, tiene FAIL diario observado. No se sustituyó el requisito diario por
un promedio o mínimo mensual.

Se reconciliaron ganancias y pérdidas antes de formar PF, y wins/fills antes de
formar WR; no se promediaron ratios mensuales. El drawdown del reporter es el
recorrido de PnL cash al cierre de sesiones disponibles, sin rellenar ausencias;
no mide drawdown intradía ni de cuenta. Las nueve sesiones cortas y la igualdad
bit a bit del control en 1.113 sesiones son autoridad del auditor02, no una nueva
reproducción de inferencia realizada por este verificador.

Todo el periodo es desarrollo previamente visto. No hay selección de ganador,
nuevo ajuste, cambio de umbral, recalibración, nueva regla, evidencia prospectiva
ni promoción. La revisión económica given-sealed-predictions y esta reconciliación
descriptiva no acreditan rentabilidad operable.

El informe narrativo final
[COMMON_GREEK_COMPARISON_RESULT_20261023.md](COMMON_GREEK_COMPARISON_RESULT_20261023.md),
SHA256 `c031740769e0d44fa3b60f42952f1bb20e5e09e9f026275ecbace9e557a878d2`,
se cotejó tras estabilizar sus bytes: las dieciséis filas de sus tablas coinciden
con el CSV anual, incluidos WR, meses positivos y denominadores diarios. Sus
diecisiete enlaces locales existen. La lectura narrativa conserva el fallo
económico, el historial técnico, las ausencias, los costes y el alcance limitado
de las auditorías. No quedan hallazgos abiertos en este cotejo.
