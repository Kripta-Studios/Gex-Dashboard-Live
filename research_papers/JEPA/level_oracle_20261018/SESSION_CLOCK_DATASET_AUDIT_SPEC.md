# Auditoría independiente del dataset SessionClock

El auditor se publica antes del cierre del dataset. No importa el builder, el
motor ni las features productoras. Vincula las 2.595 sesiones completas a la
auditoría independiente ya aprobada y verifica una vez las referencias de
features. No recalcula sus 15,4 millones de acciones.

Para las 24 sesiones de cierre13:00 reconstruye desde cada cache sellado: IB,
estados60–195, entradas D+1 minuto, triggers hasta12:54, salida/EOD12:55,
NO_FILL, salida faltante a cero y costes base/adverso con Decimal. Repite el DP
base con trayectoria adversa idéntica. Comprueba hashes, universo de acciones,
labels completos, límites temporales y shapes de features; reconstruye exactamente
las33 action features y verifica que toda barra termine antes del estado.

El calendario esperado contiene875 sesiones XNYS, 2.625 ticker-días, 24 filas
de media sesión y seis fuentes ausentes SPY/QQQ en abril2026, conservadas como
NO_EVALUABLE. Un PASS tendrá estado exacto
`PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT` y binding de root, índice,
contratos, completion, feature root y cobertura2619+6.

El DP es un techo retrospectivo, no una política predictiva. Este audit no hace
fits, no repite la economía full ya auditada y no acredita ejecución live,
recepción real de OI ni promoción.
