# Clarificación de latencia conservadora y alcance del auditor V4

Audit03 PID27748 terminóexit1 retenido18:40:36.657668UTC,25,875s,
desde d517dd7b6d84bc96de997f9a18ba34dbfe39b7a1. Exit
e92485e70bf5e3e41607ef6cf13250633c2fd2071907da1191c80fd9f5c1e897;
stderr13346a7100975b8b7a9b096239a278e81e1b19b7ec5a9057a2d5216def2c7e52.
Falló 'proposal independent maturity', después de comparar los libros, sin
audit.json/PASS final. Observer03 y código1eff2409 se conservan intactos;
cinco copias6662B,receipt3db51a1950d12cc8aba663724f6496f1e978c9fde4ae05fe341087b78add3bfd.

## Discrepancia semántica, no reparación cosmética

Productor d03494bf fija resolución en la tercera sesión oficial posterior al
fin del gate21: salida H2 estructural en final+2 a10:35 y siguiente as-of00
en final+3. Además exige todas las etiquetas reales maduras antes deese as-of.
AuditorV3 buscaba la primera sesión posterior al gate con las etiquetas de los
candidatos realmente existentes ya maduras. Si al final no hubo candidatos,
esa segunda fecha puede ser anterior. Ambas reglas son causales; no equivalen
y pueden cambiar activaciones/staleness/trades. No se permite intercambiarlas
según rentabilidad.

Diagnóstico de metadatos por prepare_audit_package:47propuestas,9diferencias
(3mensuales/6semanales), todas con retraso conservador del productor de1–2
sesiones. Productor coincide47/47 con regla fija+3. Gates parciales5; una cola
completa también puede carecer de sesión de resolución antes del cutoff.

| Propuesta | Fin gate | Primera fecha por etiquetas | Fecha fija del productor |
|---|---:|---:|---:|
| MONTHLY_20260401 |20260430|20260501|20260505|
| MONTHLY_20260601 |20260630|20260702|20260706|
| MONTHLY_20260701 |20260730|20260731|20260804|
| WEEKLY_20260120 |20260218|20260220|20260223|
| WEEKLY_20260518 |20260616|20260618|20260622|
| WEEKLY_20260526 |20260624|20260626|20260629|
| WEEKLY_20260601 |20260630|20260702|20260706|
| WEEKLY_20260608 |20260708|20260710|20260713|
| WEEKLY_20260615 |20260715|20260717|20260720|

## Autoridad explícita elegida por root

Se conserva la regla fija+3 que ya estaba en la implementación y tests antes
del run. No se cambian productor, pesos, decisiones, promociones ni fechas.
Contrato608dae37 publicado7839a555 a17:25:57UTC dice resolver 'sólo' posterior
al gate y con etiquetas maduras; no dice 'primera' o 'earliest'. Ese texto
establece condiciones necesarias, pero dejaba ambigua la fecha exacta.
Código d03494bf y test2f44f17d publicados11279c14 a17:58:57UTC fijan+3:
gate days[10:31]→days[33]. Run inició18:09:54UTC. La elección algorítmica
precede a los42fits y a sus resultados.

audit_requirements revisó contrato/código/tests/cronología y concluye que el
productor no queda invalidado: el auditor imponía earliest adicional no
exigido por el texto. review_producer_exit identificó correctamente que es una
ambigüedad que requiere autoridad explícita; root adopta la interpretación
conservadora prepublicada, no una nueva fecha optimizada. El informe final
debe nombrarla y reconocer que esta clarificación textual ocurre después
del run. No presentar el ensayo como evaluación de activación earliest.

Incidente declarado: root imprimió accidentalmente el primer proposal completo
al inspeccionar fechas, mostrando una comparación económica; el revisor mostró
un estado de proposal. Summary no se interpretó. La decisión aquí depende de
la cronología y el algoritmo previo, no de esos valores. Todo es SEEN_DEVELOPMENT.

## V4 y comprobaciones

Nueva audit_weekly_context_adaptation_v4.py/tests, salida audit04. Única función
modificada respecto V3: proposal_resolution_day. Reconstruir final+3 desde el
calendario independiente; gate incompleto o fecha fuera de cutoff→None. Para
fecha válida, exigir por separado cada label_available_at válido y estrictamente
anterior a fecha00NY; no aceptar etiquetas posteriores ni buscar otro día.
Un gate sin candidatos conserva la fecha fija (después será rechazado por vacío).
No cambiar selección, comparación de gates, scores, libros o tolerancias.

Fixtures: cola del gate sin candidatos conserva+3 aunque earliest sea anterior;
gate vacío conserva+3; etiqueta a10:35 del mismo día de resolución falla;
gate completo cuyo+3 queda fuera del cutoff sigue pendiente. AST sólo cambia
proposal_resolution_day yOUTPUT04. Conservar suites anteriores y fallos01–03.
Publicar clarificación revisada antes de fixtures; evidencia gate2GB/CPU0/env1,
review/binding/launcher publicados antes de único audit04. Ningún refit ni
variante earliest adicional. PASS sólo si toda reconstrucción final coincide.
