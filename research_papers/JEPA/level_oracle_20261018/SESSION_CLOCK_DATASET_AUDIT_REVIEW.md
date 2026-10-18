# Auditoría independiente del dataset SessionClock

Estado: `PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT`. Artefacto:
`D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1_audit/audit.json`,
SHA256 `678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9`.

El índice contiene las2.625 identidades esperadas del calendario XNYS:2.619
disponibles, seis ausentes exactas SPY/QQQ de abril2026 y24 ticker-días de cierre
13:00. Las2.595 sesiones completas se ligaron fila por fila al índice y al PASS
independiente del motor original. Se verificaron una vez los bytes y hashes de
sus cuatro referencias de features; no se recalcularon sus15,4 millones de
acciones ni su economía ya auditada.

En las24 sesiones cortas el auditor cargó caches sellados de211 minutos y
reconstruyó independientemente IB, estados60–195, entradas al minuto siguiente,
triggers hasta204, salida/EOD205, quotes válidos, NO_FILL, liquidación faltante
a cero y costes base/adverso. Las49.184 labels coinciden con el productor. También
reconstruyó exactamente las33 action features, comprobó shapes B81/T20×45/maps,
tiempo físico /390, tiempo restante contra close210 y `bar_end_i < state_i`.

Como diagnóstico del auditor, el DP retrospectivo sobre esas labels eligió133
operaciones y sumó USD16.235,20 base y USD15.969,20 adverso en la misma
trayectoria. Por ticker: SPXW60/USD13.384,00; QQQ39/USD1.731,60; SPY34/USD1.119,60
en coste base. El productor no publicó DP, advantages ni ledger oracle corto;
estas cifras son una reconstrucción independiente derivada, no una comparación
contra otro artefacto ni una política predictiva.

El binding final fija root, índice, contratos dataset/features, completion y
cobertura2619+6 para el consumidor mensual. Seis fechas siguen `NO_EVALUABLE`.
Este PASS acredita integridad incremental y aritmética de las sesiones cortas;
no acredita recepción OI real, paridad live, predictibilidad, rentabilidad de
una política ni promoción.
