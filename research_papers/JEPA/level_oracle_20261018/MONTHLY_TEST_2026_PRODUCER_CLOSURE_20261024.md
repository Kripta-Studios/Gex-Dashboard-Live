# Cierre del productor mensual 2026 H1, pendiente de auditoría

El productor y su overlay terminaron; **esto no es un PASS de auditoría
económica o causal de 2026 H1**. Este archivo conserva el cierre y sus artefactos
sin interpretar métricas, escoger modos ni emitir una conclusión de rentabilidad.

El [completion del runtime](continuation_20261024/monthly_test_2026/runtime/overlay/completion.json)
declara `COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY` a las 03:00:01,169447 UTC del
24 de octubre, duración 7.629,082347 s y `scientific_inputs_changed=false`.
SHA `1c4bbf6fe6671b962d1404e145025d06ea8d4d196bd2166c7eb6f836d73e402e`.
Después se observó **exit 0** por el handle retenido, a las
03:00:02,352144 UTC: PID 34680, creation time 1792802016.462489.
El [recibo de exit](continuation_20261024/monthly_test_2026/runtime/launcher/monitored_exit.json)
tiene SHA `31851168f5837e1ff837faa815b3e02090f4a3b783d55cd990b6795ca6e0c7b4`.
Ese recibo acredita el proceso, no certifica por sí solo el resultado científico.
La [cadena de proceso](continuation_20261024/monthly_test_2026/runtime/launcher/process_chain.json)
se conserva con SHA `8a1898ae2c3e64025ec6c6611f7989e8b747ef0ded6a679dad324fb115c23ebc`.

La [verificación independiente del cierre](MONTHLY_TEST_PRODUCER_CLOSURE_INDEPENDENT_20261024.json),
SHA `b0fadc0f1800fad63cff8b8f354f1c857e85d6b3c23818ef426d2ae90151624d`,
documenta veinte checks de identidad, cadena, cronología y hashes. Distingue
este cierre operativo de la auditoría H1 aún pendiente. El runner ya había
terminado antes de que el wrapper acabara sus comprobaciones; la ausencia
temporal de completion/exit no se trató como éxito anticipado.

Se conservan los **doce modelos nuevos** de expanding y rolling12,
9.475.658 B de modelos, con sus starts y seals. El modelo static se reutiliza
del cierre anterior: no se añadió un fit estático. El cierre global corresponde
a 36 ventanas/modelos y 18 meses contando los 24 modelos y doce meses de 2025;
no son 36 fits nuevos de esta etapa. Se incluyen los seis cierres mensuales,
el report2026 y completion científico, autoridades, snapshots de código y
recibos/logs de runtime y launcher. Report2026 y modelos se copiaron como bytes:
sus valores no se parsearon para este trabajo.

El [manifest del archivo compacto](continuation_20261024/monthly_test_2026/MANIFEST.json)
registra **136 copias exactas**, 26.039.485 B, con SHA de origen y copia:
`75a8ad57bb4fc58c3e649f7fa53e6efaa3d9f1b3b773188095e886de2b8aaa2f`.
El [preparador reproducible](archive_monthly_test_producer_20261024.py) exigió
los pins externos de completion y exit antes de crear el directorio, comprobó
los sellos y rehasheó las copias y originales al cierre. Terminó con exit 0;
Ruff y compile pasan. No modificó archivos congelados ni lanzó fits/evaluaciones.

Las [referencias locales](continuation_20261024/monthly_test_2026/LOCAL_REFERENCES.json),
SHA `92fa946ef48f1d981dca0236be3db1a7eba6b21505312579cdc4bcf7e2a83942`,
conservan:

- Doce `inputs.json`, 41.151.403 B: permanecen locales. Sus archivos se
  rehashearon una vez tras el cierre, sin parsearlos ni seguir los payloads
  referenciados dentro de ellos. Los hashes coincidieron con sus seals.
- Doce matrices y doce targets, 18.772.346.332 B: sólo se verificaron existencia
  y tamaño. El SHA procede del sello del productor; **no se leyeron, copiaron
  ni rehashearon esos payloads durante este archivo**.

Las fuentes brutas, features, scores y labels permanecen locales. Sus rutas y
hashes están en los checkpoints y metadatos originales; este archivo no los
reconstruye ni afirma haberlos auditado. El report2026 copiado conserva SHA
`76b8b1f72a569fc5327c009b6b554b7c8193797cc380be70b3d94be0e6248071`,
y completion científico `04a66e0a2d871b7471c2f18edb834a871b8f47c1147eee3221f08fbf9f2db144`.

Root científico: `D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_v1`.
Runtime y launcher originales: `monthly_test_resource_overlay_20261024_01` y
`monthly_test_launch_20261024_01`, bajo el mismo directorio de artefactos.
La siguiente frontera es la auditoría independiente H1 con sus autoridades
publicadas. Este cierre no autoriza promoción ni acredita evidencia prospectiva.
