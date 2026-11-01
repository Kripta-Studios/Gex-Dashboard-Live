# Fallo de comprobación inicial de caja y reparación V3

AuditorV2 PID33708 terminóexit1 retenido18:33:42.781945UTC,21,337s,
desde d5e9de4fc5191427332d52b370d9eeb9e1af8f07 publicado.
Exit750c816df2dcd27f81f4d9c1cc37cca40880e3eaabbe942044e39173c13cc941;
stderr71dc28b34320615cbfcea00df11c5df79fe05873fbe0b5d878d6b3b4012bb61c.
Observer02 intacto; no audit/PASS. Productor42fits yV1/V2 permanecen inmutables.

KeyError cash en rebuild_continuous_books línea765: ledger[0] puede ser un
evento legítimo sin caja (WAIT/NO_OPPORTUNITY/NO_FILL/CAPITAL_BLOCKED).
Exigir cash en la primera fila no representa el esquema del motor congelado.

V3 copia nueva audit_weekly_context_adaptation_v3.py/tests y destino audit03.
Único cambio de función: localizar el primer evento que sí contenga cash;
si existe, exigir ENTRY y cash<=100000. Si no existe, exigir ausencia de
ENTRY/EXIT, admitiendo carteras sin fills. El helper congelado ya inicializa
100000 y reconcilia caja final/neto/reservas; esas comprobaciones permanecen.
No reducir controles de posiciones, costes, scores o comparación de ledgers.

Fixtures con helper real: espera/nooportunidad antes de primera entrada,
entrada/salida efectivos en ambos costes y cartera sin entradas (también
NO_FILL permitido). Conservar las20 pruebasV2; AST difiere sólo en
rebuild_continuous_books yOUTPUT03. No nuevas métricas/tolerancias ni refit.

Publicar scope antes de fixtures; pruebas con gateRAM/commit2GB,CPU0/env1,
snapshot/logs/exitretenido; review/binding/launcher publicados antes de único
audit03. Fallos01/02 archivados, sin retry automático o sustitución de resultados.
Todavía no se ha interpretado summary ni acreditado rentabilidad adaptativa.
