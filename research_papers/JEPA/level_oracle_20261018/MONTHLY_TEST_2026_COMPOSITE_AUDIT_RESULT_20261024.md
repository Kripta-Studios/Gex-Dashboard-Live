# Auditoría mensual compuesta cerrada — 2026-10-24

La auditoría cerró con
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`, scope
`VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1`. Se conservan los dieciocho meses
exactos de enero de 2025 a junio de 2026 y los tres modos `static`, `expanding`
y `rolling12`. **Este PASS verifica la reconstrucción dentro de ese alcance;
no declara rentabilidad ni constituye una promoción.** No se han interpretado
métricas económicas al preparar este archivo.

La reconstrucción de 2025 se hereda de la auditoría fijada por SHA
`ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc`;
el auditor compuesto rehasheó su inventario. La extensión reconstruyó seis
meses y doce ventanas de fit nuevas, con trece modelos usados en H1 incluyendo
el static heredado, 36 ventanas totales. No significa que el auditor haya
reentrenado esos modelos.

H1 conserva **369 ticker-días esperados, 363 disponibles y seis ausentes**:
QQQ y SPY del 1, 9 y 15 de abril de 2026. Las ausencias siguen siendo
NO_EVALUABLE; los ceros estructurales serializados no son retornos observados.
La selección de modo permanece **null**, congelada en 2025 y reutilizada sin
selección sobre H1.

El auditor acreditó la reconstrucción de muestras, targets, pesos y matrices
de las nuevas ventanas; identidad/modelo/escala de scores sellados, precedencia
de sus sellos, scheduler, ledgers, economía y reporte de periodo. El alcance
sigue condicionado a **scores sellados**: no se repitieron fit ni inferencia,
ni se reconstruyeron features o quotes desde raw. Los sellos acreditan orden
de artefactos, no recepción o publicación histórica. Todo el periodo es
desarrollo ya visto y no acredita desempeño prospectivo o paridad live.

## Cierre observado y preservado

- [Audit](continuation_20261024/monthly_test_2026_audit/audit/audit.json):
  `87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e`.
- [Exit retenido](continuation_20261024/monthly_test_2026_audit/supervisor/exit.json):
  `f7fadc58144d9934f38e2f3af81355b322ac45b36430742fbd42230d704cc259`.
- [Completion del supervisor](continuation_20261024/monthly_test_2026_audit/supervisor/completion.json):
  `1045866ea9fdf7d926a51a221e9e5f453ead5146d835197ec99fabe3466b0165`.

El hijo auditor PID 49820, creation time 1792812892.486885, terminó con exit 0
observado mediante handle retenido el 24 de octubre a las 03:57:15,934624 UTC.
El supervisor completó la validación final y sus cinco miembros de cierre a
las 04:00:41,848786 UTC. Los quince snapshots ejecutados —trece dependencias y
dos autoridades— se conservan con hashes exactos. No hay failure coexistente.

La [admisión](continuation_20261024/monthly_test_2026_audit/supervisor/admission.json)
midió RAM libre 7.206.150.144 B y commit libre 4.928.909.312 B, sobre el mínimo
de 2.000.000.000 B. El monitor registró 1.332 muestras durante 1.343,434753 s,
sin errores: pico RSS muestreado 5.445.025.792 B y mínimo de commit libre
1.865.314.304 B. El gate es de admisión, no una reserva permanente; no se
presenta el mínimo posterior como cumplimiento continuo ni se infiere pérdida
de datos por ese descenso. El proceso terminó correctamente y el supervisor
cerró la verificación posterior.

## Archivo compacto

Tras revisión de root y publicación `dd18764d`, se ejecutó una vez el
[copiador](archive_monthly_test_audit_20261024.py), SHA
`c684eb2c6ad6c08811fe39415288d3127f17f0f965416efae6e569882bbbd1cd`,
con los tres pins reales anteriores. Su exit fue 0. El
[manifest](continuation_20261024/monthly_test_2026_audit/MANIFEST.json), SHA
`1584ab1dd71f25f695b503fa2a46b194ccb9f9f48ca6a39e5993b4046db9170e`,
registra **62 copias exactas, 26.247.830 B**: audit, launch, snapshots,
recibos/logs del supervisor y código/autoridades publicados. Orígenes y copias
se rehashearon al cierre. El mayor archivo copiado tiene 16.392.243 B.

Las [referencias locales](continuation_20261024/monthly_test_2026_audit/LOCAL_REFERENCES.json),
SHA `d65ce86e3cb07b9b4927cbf3973a54a66e3bd1b58aa8c03bec068c7b18d6e73e`,
remiten al inventario completo de 48.081 archivos dentro de audit.json y a los
36 modelos ya archivados. Se cotejaron sus hashes de manifest, existencia y
tamaño, sin duplicar modelos ni afirmar un nuevo rehash de esas copias.
Matrices, inputs, targets, raw, features, scores y ledgers permanecen locales;
el copiador no leyó esos payloads ni repitió la auditoría.

Roots originales bajo `D:/GexResearchArtifacts/level_oracle_20261018`:
`monthly_walk_forward_test_audit_20261024_01` y
`monthly_test_index_v2_audit_launch_20261024_01`. El reporter compuesto,
la interpretación de resultados y las gráficas quedan separados de este
archivo y requieren su ejecución posterior desde la autoridad ya cerrada.
