# Revisión del contrato del filtro EV prequential

Revisión estática completa: **CLEAR_DOCUMENT_ONLY**. Contrato final revisado:
`PREQUENTIAL_EV_FILTER_CONTRACT_20261101.md`, 13155 bytes, SHA256
`0b81b77b0f058248e5e55b004c263dd0f97e5089cabb96336ae5c74f622312aa`.
No se ejecutaron runtime, tests, replay, fits ni inferencia; tampoco se abrieron
nuevas fuentes o resultados de mercado.

La revisión anterior leyó el borrador de 11071 bytes, SHA256
`23d1c5f4234bd7306e71a9d8c277820c0234f84b4601e0b3711f3dc0ee29f553`.
Ese borrador nunca se ejecutó. La versión final conserva intactas familia,
fórmula, reloj, constantes, libros y criterio económico; sólo añade controles
operativos de admisión, schema, finitud, helper, campos de ledger y cierre.

La familia está cerrada antes de resultados: tres padres FROZEN_CONTEXT182,
MONTHLY_RAW y WEEKLY_RAW; CONTROL/FILTER para cada padre; seis políticas y doce
libros base/adverse. No hay elección posterior de frecuencia. El criterio sigue
siendo necesario por cada FILTER por separado: neto adverse por EXIT mayor que
cero en cada mes completo enero-agosto; cero o ausencia de trades falla, y
septiembre parcial sólo describe. Cumplirlo no selecciona ni promociona.

La unidad causal y el reloj son coherentes. La intención se forma con el top1
adverse raw único y estrictamente positivo por padre/ticker/fecha a las 10:30,
antes de filtro, cantidad, quote 10:35, posiciones o capital. El historial
expanding empieza en 2026 sin seed TRAIN/CAL y contiene todas las intenciones
anteriores ya maduras con `label_available_at < D 00:00 America/New_York`,
incluidas las no ejecutadas, rechazadas, bloqueadas, NO_FILL y cotas. No se
selecciona historia por fill o resultado, no entran intenciones contemporáneas
y no se usa el ledger para construirla.

La fórmula tiene unidades correctas. Para `A=decision_ask*100`, el residuo
normalizado `(N-EV)/A` se estima con n mínimo20, shrinkage20 y buffer unilateral
heurístico1.645. Warmup usa raw; después `correction=min(0,w*mean)` y el buffer
no negativo garantizan `EV_gate<=EV_raw`. FILTER exige simultáneamente
`EV_raw>0` y `EV_gate>0`: no rescata abstenciones, no cambia ranking/lado y no
recalibra probabilidades. `math.fsum`, orden canónico, s muestral y casos n19/20
o s0 quedan definidos y probables mediante fixtures. El buffer no se presenta
como intervalo de confianza, coste ni EV insesgado.

La separación entre intención y ejecución es correcta. Las intenciones FILTER
aceptadas deben ser subconjunto exacto de top1 raw positivos, pero sus fills no
tienen que ser subconjunto de CONTROL: la abstención previa puede cambiar el
estado posterior de posiciones y capital. Los libros son independientes,
continuos desde enero hasta septiembre, sin reinicio mensual, y conservan
sizing, prioridad, overlaps, salida H2, comisiones y slippage. Los controles
se reconcilian exactamente con los seis ledgers upstream; cantidades, caja y
economía conservan sus tolerancias predeclaradas.

Las precisiones operativas finales son coherentes con los artefactos sellados.
El manifest productor tiene schema `weekly_context_adaptation_walkforward_v1`,
status `PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES`, 17599 bytes
y los flags exactos declarados. El audit tiene schema
`weekly_context_adaptation_audit_v1`, status
`PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT`, flags
exactos y `inputs.producer_manifest` enlazado por path, bytes y SHA al productor;
el observer conserva exit_code0. El schema cerrado de scores, unicidad por
policy/candidate_id, 612 IDs comunes por política, probabilidades finitas y
puente junio29/30 están definidos sin ampliar universo.

Los guardas numéricos exigen A, EV, N, residuos, estadísticos y EV_gate finitos,
además de sus signos e inecuaciones. Si el adaptador usa scores privados para
admitir, cada `ENTRY` restaura determinísticamente `ev_base` y `ev_adverse` raw
y guarda `ev_gate` aparte; no contamina pronósticos ni economía. El helper debe
ser archivo regular sin links/reparse, con SHA antes/después del import y al
cierre. El cierre rehashea todas las autoridades e inputs y exige una salida
nueva exclusiva, sin adoptar o sobrescribir parciales. Estos controles son
materialmente suficientes y no introducen una nueva regla científica.

Las vistas conservative y without_lower_bounds, los payoffs potenciales de
intenciones no ejecutadas y los resultados de cartera están separados. Las
cotas alimentan únicamente la serie conservadora de decisión; la vista sin
cotas nunca crea otra política. El contrato reconoce que 2026 es
SEEN_DEVELOPMENT, que la regla nace tras observar el sesgo SELECTED y que un
PASS sólo justificaría una futura prueba untouched, no mejora futura ni uso
operativo.

Se rehashearon y coincidieron las autoridades documentales y helpers locales
citados: resultado diagnóstico EV `980611e2...832c`, criterio mensual
`806f7728...ee5b`, replay `e4f42a9f...9d5b`, auditor económico
`3eb6b979...d99` y helper de gate `3cfe55a6...d046`. No quedan hallazgos
materiales para publicar el contrato y comenzar fixtures artificiales. El
runtime real sigue condicionado a implementación, pruebas, evidencia, review y
binding publicados, cierre del productor y auditoría independiente.
