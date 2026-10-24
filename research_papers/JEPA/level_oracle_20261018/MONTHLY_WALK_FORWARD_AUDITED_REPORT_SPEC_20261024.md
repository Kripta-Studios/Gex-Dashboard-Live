# Reporter descriptivo mensual desde auditoría cerrada — 2026-10-24

Estado: implementación y fixtures sintéticas antes de uso. La publicación y la
revisión independiente preceden a cualquier ejecución real, que requiere además
que root confirme el exit y el SHA externo de la auditoría. No leer resultados
parciales ni ejecutar el reporter durante una auditoría activa.

## Entrada y autoridad

`report_monthly_walk_forward_audited.py --monthly-root ROOT --audit AUDIT.json
--audit-sha256 SHA256 --out NUEVO_ROOT` acepta exclusivamente el status
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES` y:

- Los doce meses exactos de 2025, con reconstrucción de selección y reporte de
  validación acreditadas por el auditor original o su variante index V2.
- Los dieciocho meses exactos enero de 2025–junio de 2026, con scope
  `VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1`, auditoría previa de 2025 fijada
  por SHA, inventario previo contenido en el compuesto y bindings iguales.

Las autoridades de esquema son `audit_monthly_walk_forward_index_v2.py` y
`audit_monthly_walk_forward_test_index_v2.py`, equivalentes económicos de sus
predecesores. No se importan productor, auditor, modelo, sampler o scheduler.
Se verifica el SHA externo antes de interpretar el JSON y de nuevo al cierre.
Se exigen modos `static`, `expanding`, `rolling12`, `development_seen=true` y
`promotion_approved=false`. El freeze se cita, incluido `selected_mode=null`;
no se vuelve a seleccionar ni se añade un gate económico.

El audit de 2025 debe declarar 24 ventanas de fit y 750 ticker-días. El
compuesto debe declarar 12 ventanas nuevas, 36 totales, 13 modelos usados en
test y cobertura H1 369/363/6; las seis identidades ausentes deben coincidir
exactamente. Campos ausentes o conteos incoherentes fallan cerrado.

Los bindings enlazan root mensual, contrato de ejecución, auditoría de fuentes,
root de sesiones e índice. Se normalizan paths absolutos sin hashes conflictivos.
Los archivos mensuales consumidos deben pertenecer al root mensual y al
inventario auditado. Los únicos consumos externos son autoridades explícitas e
índice del root de sesiones. Los sellos de cada artefacto deben ser COMPLETE,
tener el binding del contrato y contener el miembro con su hash auditado. El
inventario heredado se coteja completo como mapa, sin volver a leer sus valores.
Los roots engine/feature del contrato y de su auditoría de fuente deben
coincidir; el destino nuevo no puede estar dentro de ningún root mensual,
engine, session o feature. Esta protección se comprueba antes de crear salida.

## Calendario y cálculos

Se proyectan sólo `ticker/date/status` del índice sellado: 2.625 filas, 2.619
COMPLETE; 2025 contiene 750 ticker-días disponibles; 2026 H1 contiene 369
esperados, 363 disponibles y las seis ausencias QQQ/SPY del 1, 9 y 15 de abril.
No se regeneran sesiones mediante una librería de calendario. Se exigen claves
únicas y todas las claves exactas del índice en cada modo y mes, sin omisiones.

Para cada día disponible se consumen attempts y ledger sellados completos. Los
FILLED de attempts deben coincidir con el ledger, sin filas descartadas. Se
cotejan identidad, trades y netos diarios. Se agregan los ledgers en orden
estable `date, exit_i, ticker`, igual que el contrato, y se contrastan todos los
campos de economics mensual y reports de 2025/2026, incluidos PF, WR, drawdown,
holding y motivos de salida. PF se calcula del ledger conjunto, nunca como
promedio mensual: sin pérdidas es null, con flag `pf_infinite` separado. No se
serializan NaN ni Infinity en JSON.

Los netos base/adverse ya incluyen el contrato ask→bid, multiplicador 100,
comisión 1,30 USD por lado y slippage base 0,01/adverse 0,02 por lado, con suelo
cero del bid de salida después de slippage. Se citan los netos auditados, sin
reconstruir quotes, labels ni costes desde raw ni cambiar sus supuestos.

Se publican todos los modos y tickers, todos los meses del scope y los periodos
2025 y, sólo si corresponde, 2026 H1. El pooled `ALL` es una agregación
descriptiva adicional y no sustituye las tablas por ticker ni constituye gate.
Cobertura: esperados, disponibles, ausentes, disponibles con/sin fill y NO_FILL
attempts. Los ceros estructurales de missing en daily se validan pero se muestran
como `NO_EVALUABLE`, trades/netos/attempts null; `missing_day_economics=null`.
Los días disponibles sin fill conservan cero observado. Si un grupo no tiene
días disponibles, su economía mostrada es null, aunque el cotejo con el formato
histórico conserve internamente sus ceros estructurales.

## Salida, preservación y límites

Root nuevo, sin overwrite. `summary.json`, `monthly.csv`, `periods.csv`,
`daily.csv`, `attempts.parquet`, `ledger.parquet`, `source_inventory.json` y
`output_manifest.json`. JSON/CSV tienen orden y representación deterministas;
Parquet conserva todas las columnas, sin promesa de bytes iguales entre
versiones de librerías. El manifest final se escribe sólo después de reconciliar
todo y rehashear fuentes. Un fallo conserva el root y un recibo FAILED; nunca
deja un manifest COMPLETE. El status de summary exige siempre ese manifest,
incluso si un fallo tardío deja tablas parciales escritas. También se comprueba
que el código del reporter no haya cambiado durante su ejecución. No genera
gráficos en esta fase.

El inventario de salida distingue archivos realmente consumidos/rehasheados
antes y después de mapas auditados meramente referenciados. Matrices, features,
modelos y raw permanecen locales con paths/hashes del inventario; no se copian.
Este reporter no es una segunda auditoría de fits, inferencia, scheduler o
procedencia. Hereda el límite «given sealed scores», el desarrollo ya visto y
la ausencia de evidencia prospectiva o autorización de promoción.

Fixtures sintéticas: ambos scopes, los tres modos/tickers y todos sus meses;
calendario completo con ausencias, días disponibles sin fills, NO_FILL attempts,
PF indefinido/infinito y orden de drawdown; SHA/status/bindings/inventario/sellos
incorrectos, duplicados/omisiones, discrepancias económicas y cambios de fuente
durante lectura. Ningún fixture consume mercado.
