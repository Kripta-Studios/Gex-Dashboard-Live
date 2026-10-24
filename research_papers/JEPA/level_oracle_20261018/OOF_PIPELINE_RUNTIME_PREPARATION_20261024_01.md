# Request y binding OOF: preparación después del cierre mensual

24 de octubre de 2026. Los archivos concretos están preparados para revisión
independiente de bytes exactos y publicación por root. **No se ejecutó preflight
OOF, Request, MonthlyInputs, calibración, replay ni pipeline.** No se abrieron
métricas; el audit compuesto se leyó como bytes para comprobar su SHA externo.

| Candidato final | SHA256 |
| --- | --- |
| [OOF_PIPELINE_RUNTIME_REQUEST_20261024_01.json](OOF_PIPELINE_RUNTIME_REQUEST_20261024_01.json) | 9399f791e0dc34d62c272ba4bd2fc150fdd4c1c2608ca036718c8adb0c82cd71 |
| [OOF_PIPELINE_LAUNCH_RUNTIME_BINDING_20261024_01.json](OOF_PIPELINE_LAUNCH_RUNTIME_BINDING_20261024_01.json) | b4f6eb47ffa841ce4510d18b34e560b6d66d22c4cfe34364a838596f4c769326 |

La request contiene los status y `runtime_authorized=true` exigidos por el
schema congelado para los bytes candidatos. Prepararlos no autoautoriza un
proceso: el recibo externo mantiene revisión/publicación/decisión de root
pendientes. El binding fija el SHA de la request; su propio SHA se suministra
externamente para evitar circularidad. No se alterarán esos bytes tras revisión.

## Evidencia de entrada

Root confirmó el PASS compuesto y la salida real del auditor. La preparación
verificó los pins externos y la cadena de metadata, sin repetir la auditoría
ni interpretar resultados económicos:

| Autoridad original | SHA256 |
| --- | --- |
| Audit mensual compuesto | 87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e |
| Exit 0 retenido del auditor | f7fadc58144d9934f38e2f3af81355b322ac45b36430742fbd42230d704cc259 |
| Completion del supervisor mensual | 1045866ea9fdf7d926a51a221e9e5f453ead5146d835197ec99fabe3466b0165 |

PID del auditor: 49820. El exit fue observado a las 03:57:15.934624 UTC;
la completion supervisora se publicó a las 04:00:41.848786 UTC. Se comprobaron
identidad/creación coincidentes, status/exit entero cero, UTC y orden de tiempos,
enlace de process a preflight y de exit a process, y los cinco hashes exactos
de closure_files: preflight, process, exit, launch del auditor y audit. No
había failure coexistente en las dos raíces. El cierre previo del productor
permanece separado y conservado, sin inferir salida a partir de ausencia de PID.

## Contenido fijado

La request conserva enero–junio 2026 y doce fases seriales: correction seguida
de replay por mes. Sus 17 dependencias coinciden con la revisión OOF congelada.
El supervisor publicado en `dd18764dc1537092bde947060f704c2b97651989` tiene
48 archivos fijados por su review independiente `a78c2ef9…3ec95`.
El binding contiene 55 miembros de publicación: esos 48, seis autoridades
de código/review y la request nueva. El binding se añade externamente al chequeo
Git. No se cambiaron fuentes, modelos, políticas o parámetros según métricas.

Siete raíces de lectura acotadas cubren código, monthly, SessionClock, su audit,
audit2025, audit compuesto y logs del supervisor mensual. Nueve destinos nuevos
y disjuntos se comprobaron ausentes, sin crearlos:

- `BASE/oof_pipeline_runtime_20261024_01`
- `BASE/monthly_oof_correction_20261024_01`, compartida entre los seis meses.
- `BASE/oof_calibrated_policy_202601_20261024_01` hasta
  `BASE/oof_calibrated_policy_202606_20261024_01`, uno por mes.
- `BASE/oof_pipeline_launch_20261024_01`, para logs externos.

BASE es `D:/GexResearchArtifacts/level_oracle_20261018`. El padre sólo usa
`oof_pipeline_launch.lock`; el pipeline toma su propio `oof_pipeline_runtime.lock`.
Los gates de RAM/commit vigente, publicación exacta, exclusión y ejecución única
corresponden al supervisor publicado y no se sustituyen por esta preparación.
Un futuro cierre OOF seguirá siendo pendiente de auditoría independiente,
sin selección de ganador ni promoción automática.

## Borradores y recibo preservados

El [borrador original](OOF_PIPELINE_RUNTIME_REQUEST_DRAFT_20261024_01.json),
SHA `c2c8dd7ab2d662e81d1d2626f3e18bab08791490590dd749d6c0cc8efbe7c925`,
permanece intacto. Después del audit/exit se creó otro borrador no autorizante,
SHA `2cfd8024438b30cd98784ad7a054a8b949f9381d4ddc941e9c8061db912f1e57`,
que todavía dejaba null la completion supervisora y el SHA de request final.
Sólo tras recibir y verificar la completion1045866… se materializaron los dos
candidatos. Ningún hash de cierre futuro se inventó o autoaprobó.

El recibo separado de materialización tiene SHA
`4981e32d06fc22e1d52b67964ecca505f37013ec28b55d83944d58d5d53adc5c`.
El [manifiesto compacto](continuation_20261024/oof_pipeline_runtime_preparation/manifest.json)
conserva cuatro copias exactas, 43.701 bytes, SHA
`f8839eb250a0e7402f8a61e75e77234294e6106a625bb49af094397adf2f0e2e`.
Originales de preparación en
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_runtime_preparation_20261024_01`.
Las autoridades mensuales originales siguen en sus raíces previas y se ligan
por rutas/hash; no se duplican aquí los grandes inventarios de checkpoints.

La revisión independiente corresponde a oof_reviewer. Root publicará los
bytes revisados antes de decidir el lanzamiento. Esta nota acredita preparación
de metadata, no ejecución, rentabilidad, generalización o paridad live.
