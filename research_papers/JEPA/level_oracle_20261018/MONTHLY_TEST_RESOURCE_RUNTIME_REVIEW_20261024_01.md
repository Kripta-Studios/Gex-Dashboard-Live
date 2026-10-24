# Binding real para test mensual 2026, intento 01

El JSON companero fija una ejecucion initial concreta del wrapper y launcher
congelados, condicionada a revision independiente, publicacion y admision real.
No se ha lanzado el test ni invocado admit/preflight al redactar este binding.
El campo PASS_MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW es el estado contractual
que consume el wrapper; este documento no sustituye la revision independiente
de los bytes por tcn_economic_auditor ni el preflight posterior de root.

JSON SHA256: `1c6072a871d7d4cbcabc7e82dbbbbdb28d5767ff083571638f956d92250b557b`.

La autoridad es el audit2025 V2 terminado, con 12 meses, 24 ventanas de ajuste,
750 ticker-dias y tres modos. Su PASS es condicional a scores sellados. El
productor PID11852 tiene exit0 observado por handle retenido y completion real.
El auditor PID52304 tiene exit0 observado a 2026-10-23T23:50:32.495581+00:00,
seguido de completion del supervisor que fija el audit.json. La verificacion
previa de root de los vinculos de cierre se complementa aqui con hashes de
JSON compactos y comprobaciones de esquema; no se repite la auditoria economica.

El freeze permanece FAIL_NO_DAILY_COMPLIANT_MODE, selected_mode=null, approved=false.
No se elige un modo a partir de este binding ni se altera el resultado de 2025.
La continuation test conserva el diagnostico predeclarado de los tres modos.

## Fuentes exactas

| Papel | Ruta | SHA256 |
|---|---|---|
| validation.audit | D:\GexResearchArtifacts\level_oracle_20261018\monthly_walk_forward_validation_audit_20261024_02\audit.json | `ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc` |
| validation.freeze | D:\GexResearchArtifacts\level_oracle_20261018\monthly_walk_forward_v1\validation_freeze.json | `df9a490d310d86a040e0ca9e6ad5b07c64d3474b9c71ce83e445309511fa9237` |
| validation.process_binding | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resume_20261023_01_logs\process_monitor_binding.json | `21588f13e2fac83e4522eb848753a2431c509fb5e6a1b0627221c6d60b1714eb` |
| validation.monitor_open | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resume_20261023_01_logs\monitor_open.json | `3ee627e3200e6488dadf6882d61f013021dbd270f90ac4a8613e4674d29faef5` |
| validation.monitored_exit | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resume_20261023_01_logs\monitored_exit.json | `918964c6474df52067db5fb6eecb1c07339cb9bca262e8cab560f22ba3b00e93` |
| validation.monitor_code | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resume_20261023_01_logs\monitor_existing_process_20261023.py | `96189a5f805113ab9d94ddc72b075a683048b79a13da8f680cbb80b4935b602b` |
| validation.runtime_launch | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resource_overlay_resume_20261023_01\launch.json | `22b1119e08f814a2b76c016d119bc8db9abe6aaa1eb13edb9af54dfd0c5fa69b` |
| validation.runtime_completion | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resource_overlay_resume_20261023_01\completion.json | `ccce687bfa850d894606ff29ef6014add9e39a142fd84c3dd0d76e2a2a5c185b` |
| validation.source_launch | D:\GexResearchArtifacts\level_oracle_20261018\monthly_resume_20261023_01_logs\process.json | `056a155c06153e6dce6c9686b27cd2ed47f59ad93e2e228c81bcd0a1ac8ca8c2` |
| supporting_evidence.audit_process | D:\GexResearchArtifacts\level_oracle_20261018\monthly_validation_audit_launch_20261024_02\process.json | `5ba38a789e035e25cf67984f2db94c4eaf2f09158eab24df8ec532a5316bc763` |
| supporting_evidence.audit_exit | D:\GexResearchArtifacts\level_oracle_20261018\monthly_validation_audit_launch_20261024_02\exit.json | `7c7f24743f961707dbfe330b2a0f61b92ad849fe75862ca94c991f802ef21e21` |
| supporting_evidence.audit_supervisor_completion | D:\GexResearchArtifacts\level_oracle_20261018\monthly_validation_audit_launch_20261024_02\completion.json | `07839f7f7437b87d0a8c011fe4ba6032eec16a21637f2c5b84f233d4d77c663b` |
| supporting_evidence.validation_chain_verification | D:\GexResearchArtifacts\level_oracle_20261018\monthly_validation_runtime_chain_verification_20261024_01\verification.json | `b7b64e2a3d8dd1751287f0530151a09100e2949aa4295b1f52a246855a5d3730` |

La cadena del productor conserva process_monitor_binding.json normalizado y su
source_launch process.json original, unidos por SHA; no se reemplazan recibos.
El monitor retenido es monitor_existing_process_20261023.py, fijado por el SHA
real de monitor_open. El comando historico contiene ruta relativa: el launcher
debe invocarse desde la raiz del repositorio para la resolucion congelada.

Los cuatro supporting_evidence son procedencia adicional para el revisor/root;
el wrapper congelado no los valida automaticamente. La cadena validation,
audit/freeze y el inventario auditado si son entradas del gate congelado.

## Cobertura de lectura y estado inicial

Las 11 allowed_read_roots son directorios concretos existentes: codigo de esta
investigacion; monthly_walk_forward_v1; session_clock_dataset_v1 y su audit;
engine_v1; features_v1; runtime/logs del productor11852; salida y launcher del
auditor V2; y verificacion previa de la cadena. No se permite una raiz de volumen
ni toda D:/GexResearchArtifacts. Las raices engine_v1/features_v1 proceden de los
paths reales de verified_files, no de una suposicion sobre el nombre del dataset.

Se comprobaron por nombres 38.561 paths unicos del inventario auditado y las
listas runtime_members/final_checkpoints/preserved_checkpoints: todos estan
contenidos en esas raices. No se rehashearon sus payloads. Los hashes de los
recibos compactos, reviews y 20 archivos de publicacion si se comprobaron.

El censo por nombres verifica exactamente las 24 ventanas modelo2025 y cero
archivos test en predictions/months/ledgers2026, fits/models con cutoff2026,
day_chunks2026, reports2026 o completion cientifica. No lee sus valores.
expected_completed_test_fit_keys=[], prior_test_attempts=[] y mode=initial.
La admision real volvera a comprobar cierres, inventarios y hashes; este censo
no acredita por si mismo los bytes de modelos ni toda la integridad cientifica.

Runtime nuevo: `D:\GexResearchArtifacts\level_oracle_20261018\monthly_test_resource_overlay_20261024_01`.
Logs nuevos: `D:\GexResearchArtifacts\level_oracle_20261018\monthly_test_launch_20261024_01`.
Ambos estaban ausentes al redactar; no se crearon directorios de ejecucion.

## Condiciones antes de ejecutar

Revisar estos bytes independientemente y publicar JSON/nota/revision. Root debe
proporcionar SHA de este JSON, SHA audit2025 y commit publicado completo de
40 hex al launcher. El commit se suministra externamente despues de publicar,
para evitar un pin circular dentro del propio JSON. El launcher contrasta los
20 objetos Git y este JSON; root verifica ademas la publicacion remota.

El launcher congelado conserva el Popen handle y la observacion de salida real.
No hay retry automatico. El wrapper mantiene locks y el gate de RAM disponible
y commit libre >=2.000.000.000 bytes, que se mide al ejecutar. No se presenta
ninguna observacion pasada como prueba de disponibilidad futura.

2025/2026 son SEEN_DEVELOPMENT. Este binding no demuestra rentabilidad causal,
no cambia modelos, reglas, costes ni fuentes; technical_ready=false y
promotion_approved=false. Produccion y API permanecen fuera de alcance.
