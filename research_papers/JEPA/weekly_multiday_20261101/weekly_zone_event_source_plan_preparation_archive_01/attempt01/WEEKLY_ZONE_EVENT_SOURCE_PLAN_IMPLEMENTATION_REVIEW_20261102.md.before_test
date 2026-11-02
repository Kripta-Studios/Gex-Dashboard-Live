# Revisión estática del planificador de fuentes weekly

Dictamen independiente de `/root/daily_auditor_review`, materializado por root:
**ship — CLEAR_STATIC_PRE_SUITE**. Fecha: 2 de noviembre de 2026.

| Archivo | Bytes | SHA256 |
|---|---:|---|
| build_weekly_zone_event_source_plan.py | 43609 | 9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270 |
| test_build_weekly_zone_event_source_plan.py | 16141 | dd497fc87548b5009c54d43603e13b099756a69183eff519920b6bd0446f4dbf |

Contrato publicado: c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65,
commit 2123cc246fda157a7c7f85025ad17b5a9af2c5fe. La revisión sólo cubre
implementación estática; no se ejecutaron imports, fixtures ni runtime.

Se corrigieron los hallazgos sobre traversal antes de canonicalizar, inspección
de ancestros desde el ancla, rechazo de reparse/nonregular, paths finales de
outputs y normalización de source_root histórico con separadores dobles.
candidate_ids debe estar vacío upstream y no se exporta. Las pruebas corrigen
el control AST de ImportFrom y usan un adaptador determinista para seguridad
de archivos, además de shortdays y pins de salida final.

El revisor contó 20 funciones y 22 casos estáticos: **todavía no ejecutados**.
La metadata compacta inspeccionada confirma H1 2625 = 1527/1092/6; Q3 165 =
90/69/6; overlay de seis filas = 3/3. El resultado esperado es
1620 PLANNED, 1164 NO_SERIES y 6 HORIZON_OUTSIDE_CALENDAR, con 4860 referencias.
D1 se deriva del calendario; D y D2 conservan la identidad upstream.
Presencia futura sólo es diagnóstico y no reselecciona expiración.

La siguiente acción admisible es una suite formal con snapshots, gate oficial,
CPU0, diez variables de threads en 1, logs y exits retenidos. Este dictamen no
autoriza por sí solo un runtime real: faltan suite, revisión final, binding y
publicación verificada. No se leyeron valores de mercado ni se produjo nueva
evidencia económica. Selección null y promoción false.
