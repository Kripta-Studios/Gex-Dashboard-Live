# Revisión de la enmienda de acceso D

Estado: CLEAR_DOCUMENTARY_D_SCALE_ACCESS_AMENDMENT.

Revisor independiente /root/d_integration_harness_review: SHIP.
Objeto revisado: D_REVISIT_SCALE_ACCESS_AMENDMENT_20261102.md,
8850B, SHA256161f947bbf7a6b3e16b2bd79d7add486db0b78f892ece7ed49681f2dec332304.

La causa material es el acceso repetido al histórico global por evento y,
según el análisis separado del autor del auditor, por consulta de quote.
Las cotas son estáticas; no se declara OOM observado ni duración/RSS medidos.
Los conteos B02 motivan escala sin adoptar sus valores aún no auditados.

V1, tests, cierres y fallos quedan intactos. V2 se limita a índices, ventanas,
agrupación y validación sin colecciones redundantes; mantiene FSM, target,
cola global, cuatro libros continuos, capital compartido y lockout B.
La validación completa precede a las ventanas: no se ocultan entradas
malformadas externas al periodo local. Se conservan tipos y comparación
exacta de floats, JSON, IDs, relojes, labels y Decimal.

La equivalencia requiere resultados públicos completos contra V1 sobre
inputs artificiales nuevos, incluidos cruces de plan/ticker/sesión y capital.
Productor y auditor deben cerrar sus nuevas pruebas por separado antes de
la integración conjunta. El autor del auditor mantiene aislamiento de los
algoritmos y tests del productor. El revisor documental no abrió el auditor.

Una prueba de millones de registros necesita protocolo/presupuesto/revisión
y gates separados. Esta revisión no autoriza tal carga mientras B06 sigue
activo. Tampoco autoriza datos, benchmark, Arrow, binding o ejecución D real.
La secuencia Bfull, C productor/auditor y adaptación real D sigue intacta.

Tras publicación byte-exacta de enmienda y revisión puede comenzar sólo la
implementación pura V2 descrita. Antes de ejecutar cualquier fixture nuevo
faltan revisión estática, publicación, harness observado y gates actuales.
No se repiten suites cerradas. No hay PnL nuevo ni modelo seleccionado.
