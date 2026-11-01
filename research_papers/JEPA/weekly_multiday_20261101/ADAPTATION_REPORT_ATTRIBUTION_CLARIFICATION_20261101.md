# Atribución temporal del informe de adaptación

Aclaración previa a cualquier fit real de la familia ADAPTATION_WALKFORWARD,
cuyo contrato 608dae37c21c19277a36dbcc1eeaa36da0135385a080618d461a4e240855cc61
permanece intacto. No modifica decisiones, etiquetas, gates, costes o selección.

El campo canónico `monthly_net_usd` del replay cerrado atribuye el resultado
completo de cada trade a su fecha de salida. Se conserva esa definición y se
etiqueta como resultado de operaciones cerradas por fecha de salida. No es
una curva diaria marcada a mercado ni un estado de flujo de caja diario.
Los bloques H1/Q3 deben identificarse expresamente como `exit_date` cuando
sumen esos resultados. Las comisiones de entrada ya están incluidas en el
neto total del trade; esta agrupación no cambia su contabilización en el ledger.

Un desglose adicional por `entry_date` representa cohortes de entradas. Se
mantiene separado y se etiqueta como tal. Ambos desgloses deben reconciliar
con el mismo neto total; una posición junio29→julio1 pertenece a H1 por entrada
y a Q3 por salida. Ninguna posición ni capital se reinicia en esa frontera.

La transferencia después de una activación se atribuye al modelo usado al
entrar. Debe cubrir todo su periodo activo hasta la siguiente activación o el
final del ensayo, incluyendo sesiones sin trades y periodos negativos, y
mostrar rango, sesiones, candidatos, trades, métricas probabilísticas/EV y
netos por cohortes de entrada. No reasignar una posición abierta al nuevo
modelo. La comparación no selecciona una política ganadora a posteriori.

Concentración: restar mecánicamente el mayor trade y el mayor mes del mismo
desglose declarado. No fijar abril por el resultado del experimento anterior.
Estas restas describen concentración; no son estrategias alternativas.

El puente contiene seis identidades de cobertura: tres junio30 NO_SERIES y
tres junio29 cuya disponibilidad final depende de la construcción auditada.
Puede añadir de cero a seis candidatos reales. Cuatro presentes y dos ausentes
describen archivos fuente, no filas finales de cobertura ni candidatos.

Persistir estas definiciones en el resumen producido y verificarlas en el
auditor. El resultado sigue siendo SEEN_DEVELOPMENT, con promoción false.
