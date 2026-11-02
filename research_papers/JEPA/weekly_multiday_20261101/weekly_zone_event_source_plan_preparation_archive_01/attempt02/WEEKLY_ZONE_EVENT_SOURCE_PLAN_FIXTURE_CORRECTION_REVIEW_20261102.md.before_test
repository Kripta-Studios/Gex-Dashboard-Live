# Corrección de fixtures del planificador weekly

Dictamen de `/root/daily_auditor_review`, materializado por root el 2-nov-2026:
**ship — CLEAR_TEST_ONLY_CORRECTION_FOR_ONE_FINAL_ATTEMPT02**.

El intento formal 01 queda preservado en
D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_event_source_plan_preparation_01/attempt01.
Compile y Ruff terminaron exit0; pytest terminó 21 PASS y 1 FAIL, exit1 retenido
del PID40256 a 10:39:37.783669 UTC. No se ejecutó el planificador real.

El fallo fue exclusivamente una expectativa de mensaje obsoleta: wrong.parquet
se rechaza correctamente antes del control semántico de identidad, por estar
fuera de la raíz de opciones. La corrección sustituye exactamente dos líneas
de fixture por paths nominales válidos SPY/expiry20260702/trade20260630. Así se
supera la validación de forma y se comprueba el rechazo específico de fecha
de entrada y de H2 incorrectas. No cambia ninguna regla del productor.

- Builder intacto: 9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270.
- Tests previos: dd497fc87548b5009c54d43603e13b099756a69183eff519920b6bd0446f4dbf.
- Tests corregidos: ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121.

Root autoriza preparar una única suite formal final en attempt02, con harness
nuevo revisado, snapshots y gates contemporáneos, sin modificar attempt01.
La ejecución queda sujeta a GO de root tras revisión del harness. Este dictamen
no acredita PASS de la suite corregida ni autoriza runtime real. Los 22 casos
deberán pasar con los bytes anteriores; selección null y promoción false.
