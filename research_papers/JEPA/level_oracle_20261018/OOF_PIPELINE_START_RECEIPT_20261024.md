# Inicio OOF: recibos iniciales, sin cierre — 2026-10-24

Root inició el pipeline una vez desde la publicación remota verificada
`3cca1167a5c48c4f5bef4aa685e20a561dbf229c`, sesión exec 8704. Este documento es
un **corte histórico del inicio con proceso activo**, no un certificado de
terminación ni un resultado científico. No acredita que el proceso siga vivo
al consultar después el archivo.

Identidad comunicada por root para ese corte:

- Supervisor PID 3448, creation time 1792815138.5951445.
- Hijo PID 29704, creation time 1792815151.326416.
- Inicio registrado: 2026-10-24 04:12:31,354234 UTC.
- Gate previo: RAM disponible 7.754.047.488 B y commit libre 4.709.642.240 B.

**Root conserva la responsabilidad del handle y del seguimiento del proceso.**
Este trabajo no lanzó otra ejecución del pipeline ni repitió el preflight.
No hubo reintento. No se importaron módulos científicos ni se accedió a arrays,
predicciones, resultados o métricas.

El archivo fresco
`continuation_20261024/oof_pipeline_start_01` contiene sólo cuatro recibos
iniciales inmutables, **42.662 B**. Se copiaron como bytes, sin interpretar su
contenido, y se verificaron SHA256 de origen y copia antes y después:

| Recibo | Bytes | SHA256 |
|---|---:|---|
| [preflight.json](continuation_20261024/oof_pipeline_start_01/preflight.json) | 36.232 | `14b37d4daeb950b178dc6632dd77cd716f24044f8d609093417f9afeaed5b83d` |
| [process.json](continuation_20261024/oof_pipeline_start_01/process.json) | 1.310 | `c499b0949f4c2f2a197968cff47451836cb60c0865572a96eb08bc24b57cf1c2` |
| [admission.json](continuation_20261024/oof_pipeline_start_01/admission.json) | 160 | `1e3f3712c8dd0b21ee61d2ce83c378e99d1b65f144526a684089eb1cf133a33c` |
| [initial_observation.json](continuation_20261024/oof_pipeline_start_01/initial_observation.json) | 4.960 | `c5ff71c90e54ee2d363717d5b9150bd137d43c12c1e66791becb874c67718d9d` |

El pin externo de initial_observation se comprobó contra el SHA facilitado por
root. El [manifest](continuation_20261024/oof_pipeline_start_01/MANIFEST.json)
documenta origen, tamaño y hash de las cuatro copias, el commit y los límites.

Los tres primeros originales permanecen en
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_launch_20261024_01`;
la observación inicial está en
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_supervisor_observer_20261024_01`.
No se copió stdout en crecimiento, ningún resultado, exit o completion.
No se tocaron handoffs, archivos sellados ni fuentes originales. El cierre real
y cualquier interpretación posterior necesitan recibos propios; no se deducen
de estos documentos de inicio.
