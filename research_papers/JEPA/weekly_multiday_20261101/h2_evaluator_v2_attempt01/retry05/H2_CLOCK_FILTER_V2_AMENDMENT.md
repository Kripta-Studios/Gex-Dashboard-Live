# H2 V2: filtrar instantes exactos sin rechazar otras rejillas válidas

Enmienda operativa al contrato H2 de SHA245a6df1; antes de cualquier fit nuevo y
sin consultar rentabilidad. Builder01 eb0cba11 queda inmutable: exit1 retenido
a13:58:12.239683UTC, 93,687 segundos; no publicó candidates ni manifest final.
Inventario cb762957 intacto. Copias del fallo en h2_failure_evidence_01.

Diagnóstico sólo de clocks encontró la primera fuente ofensiva en el recorrido:
QQQ_20241004_20241003_greeks.parquet, SHA
`5d2463296c590b702a73dcc2f4e499673d5f7fc43c2df2249b1af9d465dd591c`.
underlying_timestamp contiene dos rejillas:391 instantes :00/96.186 filas y
390 instantes :30/95.940 filas, de09:30:00 a16:00:00. Los clocks10:30:00 y10:35:00
tienen246 filas cada uno; los10:30:30/10:35:30 también246, separados. El primer
rechazo fue2024-10-03T09:30:30. No se abrieron quotes/Greeks/PnL en el diagnóstico.

El fallo proviene de aplicar a todos los timestamps una condición de minuto
exacto antes de filtrar los dos instantes usados por H2. V2 sólo corrige ese orden
conceptual: parsear fecha/zona/tipo válidos y seleccionar exclusivamente10:30:00
y10:35:00, con fracción exactamente cero. Ningún snapshot con segundos o fracción
se redondea, desplaza, rellena ni reutiliza para esos clocks. Incluye precisión
submicrosegundo: una fracción no nula no puede desaparecer por truncamiento del
parser. Clocks válidos no seleccionados se cuentan, incluidos los subminuto.
Clocks de tipo/fecha/zona inválidos continúan siendo error; nativo presente nunca
cae al proxy. Duplicados del contrato en los instantes seleccionados siguen
siendo fatales. Las features, contratos, labels, PnL, costes y modelo no cambian.

Implementación en archivo nuevo `build_weekly_h2_dataset_v2.py`, tests nuevos y
raíz `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_v2_01`.
No reutilizar/adoptar parciales de01. InventarioV2 nuevo liga código, contrato
original, esta enmienda y helper fuente; calendario y plan económico idénticos.
Revisión independiente verificará igualdad de funciones económicas frente a01,
y fixtures demostrarán :00 aceptado/:30 y fracciones excluidas sin alias.
El diagnóstico de clocks no autoriza por sí mismo un lanzamiento. Código, tests,
review y publicación antes del inventarioV2; luego binding real antes de valores.

El evaluador aún no ejecutado necesita admitir explícitamente el nuevo pin V2 y
la enmienda, manteniendo intactos sus nodos de fit/calibración/replay/métricas.
Sus pruebas/revisión se conservarán. No abrir otro horizonte, umbral, ticker,
modelo ni coste por este fallo técnico. Goal activo; producción/API/bróker intactos.
