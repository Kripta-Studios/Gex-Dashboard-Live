# Piloto de continuidad weekly: implementación revisada

El 1 de noviembre de 2026 root inspeccionó completos contrato, consumidor y
tests. La revisión independiente `/root/review_weekly_source_pilot` concluyó
`CLEAR / ship` sobre estos bytes:

- Contrato: `b5ce2cb180676344cab807185bb5b9fc607da93d136a7e16eb44dd9cfb4047f5`.
- Consumidor: `ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878`.
- Tests: `18489a33ecde3e1e00026f8772363d0fd7ebec6494e7994a541282addbfb9a0a`.

Attempt06 conserva copias físicas previas de esos tres archivos, logs directos
y recibos de salida: 16 pruebas sintéticas PASS y Ruff PASS. Gate previo RAM y
commit superior a 2 GB; CPU0 y un hilo. La revisión independiente inspeccionó
código y evidencia, sin repetir tests ni abrir fuentes reales.

La primera versión recibió FIX_FIRST: guard de `forward_fill`, comparación del
inventario posterior al primer batch, ausencia de manifest final y controles de
rutas incompletos. Se corrigieron antes de uso real. También se rechazan quotes
string/bool, aparición/desaparición de archivos y cambios de bytes; el cierre
verifica las 69 identidades y liga código/contrato/inventario/diagnóstico. No se
borran parciales ante fallo. El calendario está fijado en contrato y cotejado
por root contra el índice indicado; el consumidor no reclama esa lectura.

La evidencia inicial de intentos01–04 tiene registros de hashes, no snapshots
físicos completos. No se reconstruyen retroactivamente. Attempt05 conserva sus
15 PASS; attempt06 contiene la versión final y 16 PASS. No se suman versiones
como una sola suite. Los directorios de caché locales no son evidencia.

Tras publicar estos bytes se autoriza dentro de la orden vigente del usuario
un inventario real de las 69 rutas y, si éste cierra correctamente, un único
diagnóstico ligado a su SHA externo. Root conserva comando, gate, logs y salida
por handle. Un error real se preservará y revisará, sin retry automático. Esto
es admisión de fuentes, no resultado económico, fit, autorización de producción
o bróker. La investigación de rentabilidad weekly continúa después del piloto.
