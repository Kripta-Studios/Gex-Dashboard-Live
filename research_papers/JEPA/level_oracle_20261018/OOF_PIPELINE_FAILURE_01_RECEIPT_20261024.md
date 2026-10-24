# OOF intento 01: fallo técnico preservado — 2026-10-24

El intento único publicado desde
`3cca1167a5c48c4f5bef4aa685e20a561dbf229c` terminó con **exit 1**. No se
reintentó ni reanudó; no hay receipt de fase ni replay completado. El
[recibo inicial](OOF_PIPELINE_START_RECEIPT_20261024.md) permanece intacto como
corte histórico anterior al fallo, no como afirmación actual de proceso activo.

El [exit del hijo](continuation_20261024/oof_pipeline_failure_01/supervisor/exit.json)
fue observado por `GetExitCodeProcess_retained_Popen_handle`: PID 29704,
creation time 1792815151.326416, exit 1 a las 04:24:25,474349 UTC.
Root confirmó también el exit 1 de la
sesión supervisora 8704. La [observación terminal](continuation_20261024/oof_pipeline_failure_01/observer/terminal_observation.json)
se preserva con su pin externo. **El cierre no se infiere de la ausencia de
un PID.** Root mantuvo la responsabilidad del handle; este archivo no lanzó
otro proceso del pipeline.

## Punto de fallo y alcance

El [failure del pipeline](continuation_20261024/oof_pipeline_failure_01/pipeline/failures/1792815865339767200.json)
preserva el traceback completo. Tras `prepare_correction` de enero, la cadena
`correction_closure → verify_map → allowed_file` lanzó:

```text
ValueError: Input outside declared roots
```

La comprobación falló en `correction_closure`, línea 348 del código publicado,
al verificar `inputs["files"]`. La ruta concreta rechazada corresponde a un
diagnóstico separado de root; este archivo no la deduce ni altera las raíces
admitidas. El [stderr cerrado](continuation_20261024/oof_pipeline_failure_01/supervisor/stderr.log)
y el [failure del supervisor](continuation_20261024/oof_pipeline_failure_01/supervisor/failure.json)
quedan preservados.

El [marcador de corrección de enero](continuation_20261024/oof_pipeline_failure_01/correction_metadata/202601.complete.json)
ya declara `COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS` para `202601`,
`target_labels_read=false`, `base_models_refitted=false` y `winner_selected=null`.
Son declaraciones del adaptador: **no equivalen a cierre satisfactorio del
pipeline ni a auditoría independiente de la calibración**. La preparación
había generado artefactos de selección, realized histórico, calibración y
scores corregidos; no se describe este fallo como anterior a todo valor.
Sus valores no se inspeccionaron durante este trabajo de archivo.

El árbol de control contiene request, contract, start `00` y un failure;
no contiene receipt o completion. Los seis destinos de replay declarados no
existían en la comprobación de metadatos posterior al fallo. Esta evidencia y
el punto de excepción sitúan el fallo antes del replay, sin ejecutar uno para
comprobarlo. No hay resultado económico OOF interpretado ni nuevo ganador.

## Archivo y límites

El [manifest](continuation_20261024/oof_pipeline_failure_01/MANIFEST.json), SHA
`ab19ddd5432722e63df1411a36bdc6b60d8b17b7d398fc71d480084d1b867c24`,
registra **16 copias exactas, 1.875.522 B**:

- Siete logs/recibos cerrados del supervisor: preflight, process, admission,
  exit, failure, stdout y stderr.
- Cuatro archivos de control: request, contract, start y failure del pipeline.
- Cuatro metadatos de corrección: implementation, run_contract, inputs y
  complete de enero. Sus listas preservan rutas y hashes; no se siguen sus
  referencias para abrir payloads.
- La observación terminal independiente del supervisor.

Se verificaron los cinco pins externos facilitados por root y los hashes de
origen/copia. El inventario por nombres y tamaños encontró 4.868 archivos en
el root de corrección: sólo los cuatro metadatos superiores se copiaron.
Quedaron locales **4.863 JSON de valores** de calibration, realized, scores y
selections, además del `.lock`. No se leyeron ni rehashearon esos payloads y
**no se afirma una auditoría de los 4.868 archivos**. Tampoco se abrieron
matrices, arrays o datos brutos.

Pins del cierre conservados:

| Evidencia | SHA256 |
|---|---|
| Exit retenido | `dfea9d0c8baa1fc606465f8342dd18b9c421d374d3c7b8b4154ebf76ff8c303a` |
| Failure supervisor | `7820bb5cee8e42c525315350f45ce4338dc73e31e56c88a0e1603885fe130373` |
| Stderr | `d302c142059590eb29f947b14411ba1baa71dbe7fcbfaab8ce9c8e6387d0bee2` |
| Failure pipeline | `07d87d84a63ae919e872c8fa711cac04573a5e7b43ca7636c7e9bd0513657b86` |
| Observación terminal | `0b14f696eda05ae918092fe917801083769a9bf5a54216707f82bee8cd15ba9e` |

Todos los originales permanecen bajo
`D:/GexResearchArtifacts/level_oracle_20261018`, en los roots
`oof_pipeline_launch_20261024_01`, `oof_pipeline_runtime_20261024_01`,
`monthly_oof_correction_20261024_01` y
`oof_pipeline_supervisor_observer_20261024_01`. No se modificaron código
congelado, handoffs o artefactos previos. El intento 01 conserva su fallo;
`retry=false`, sin resume y sin replay por esta tarea.
