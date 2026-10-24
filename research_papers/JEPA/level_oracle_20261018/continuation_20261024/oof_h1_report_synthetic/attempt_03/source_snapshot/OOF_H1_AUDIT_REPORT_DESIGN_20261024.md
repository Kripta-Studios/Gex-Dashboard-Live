# Reporte descriptivo del audit OOF H1

El postprocesador acepta exclusivamente un `audit.json` con SHA256 externo,
status `PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1`, scope de offsets y ejecución
económica dados scores base auditados, enero–junio de 2026 completos y las seis
políticas fijas (`static`, `expanding`, `rolling12`, control/corrected). Exige
`winner_selected=null`, desarrollo visto y las limitaciones false del auditor.

Sin importar productor, auditor o librerías de mercado, valida la coherencia del
propio JSON: 369 ticker-días, seis identidades missing de QQQ/SPY del 1/9/15 de
abril, calendarios iguales en las seis políticas, ausencia sin economía inventada,
108 grupos mensuales y 18 H1. Reconcilia diarios disponibles con meses y seis
meses con H1: trades, netos, ganancias/pérdidas brutas y PF base/adverse. PF sin
pérdidas conserva null y flag infinito separado. Cita los gates emitidos por el
auditor; no selecciona ganador, modifica política ni calcula gates nuevos.

`tables.json` exporta todos los grupos y cobertura. `monthly_net_usd.png/.svg`
muestra nueve paneles modo×ticker con cuatro barras por mes, colores para
control/corrected y trama para coste adverse. La escala es común entre modos de
cada ticker; abril incompleto se anota y sombrea. Los totales son sólo de días
disponibles; missing no equivale a PnL cero. Días sin fills no son el número de
intentos NO_FILL. No se reconstruyen WR, drawdown, holds, carteras, quotes, fits
ni inferencia. El archivo de auditoría es la única fuente científica leída: no se
recorren ni rehashean los payloads de su inventario `verified_files`.

CLI: `python report_oof_h1_audit_20261024.py --audit PATH --audit-sha256 SHA --out NEW_ROOT`.
El destino debe ser nuevo y estar fuera del directorio del audit. El SHA del audit
se verifica antes de leer y al cierre. Sólo tras validación completa se escriben
tablas/figuras; el manifest de éxito es el último archivo. Un fallo no se presenta
como éxito ni se reintenta automáticamente. JSON ordenado y SVG sin fecha embebida;
bytes de figura dependen también de la versión de Matplotlib y fuentes instaladas.

La implementación se verifica sólo con JSON artificial y una figura sintética.
Revisión independiente y publicación preceden cualquier lectura del audit real
y su ejecución única autorizada por root. No es otro contrato económico ni una
segunda auditoría de mercado.

Las fechas de negociación proceden del audit pineado. El reporte comprueba su
coherencia interna y los 369 ticker-días; no reconstruye un calendario bursátil
independiente. El SHA del propio postprocesador se captura al inicio y debe
seguir igual antes del manifest; la prueba de mutación usa un doble del hash,
sin editar código real durante la ejecución.
