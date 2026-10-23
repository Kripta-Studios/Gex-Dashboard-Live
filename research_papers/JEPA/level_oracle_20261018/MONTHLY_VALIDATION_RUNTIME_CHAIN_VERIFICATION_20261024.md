# Verificación de la cadena final del runtime mensual 2025

24 de octubre de 2026. **Compatible con los requisitos de recibos del wrapper
de test; no es una auditoría económica ni una admisión para ejecutar test.**
Se contrastaron los recibos reales del proceso 11852 con el código congelado de
`run_monthly_test_resource_overlay.py` y su launcher, sin invocar `admit`,
preflight o procesos económicos. No se creó una runtime-review.

## Identidad y cierre real

Los **31 contrastes** del recibo terminaron sin discrepancias. PID 11852 y
`creation_time=1792784053.9282398` coinciden entre binding, apertura del monitor
y salida. El comando coincide entre binding, monitor y argumentos del recibo
original; contiene la raíz de runtime y el wrapper de validation correctos.
El binding normalizado conserva el SHA de `process.json`. El código del monitor
retenido coincide con `monitor_open.monitor_code_sha256`.

| Evento real | UTC |
|---|---|
| Creación del proceso, según `creation_time` | 2026-10-23 19:34:13.9282398 |
| Registro launch del wrapper, tras admisión | 2026-10-23 19:35:47.318900 |
| Apertura del handle retenido, monitor 53508 | 2026-10-23 19:50:39.295694 |
| Completion del wrapper | 2026-10-23 23:15:37.281501 |
| Salida observada por el handle | 2026-10-23 23:15:39.501243 |

`monitored_exit.json` contiene `PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE` y
`exit_code=0` entero. Ambos PID estaban ausentes durante esta comprobación;
la evidencia de salida cero es el recibo del handle, no esa ausencia.
Los relojes son conscientes de zona horaria y respetan el orden exigido.

## Hashes y preservación comprobados

Se rehashearon **45 archivos distintos**, incluidos los 25 miembros de runtime
(launch, código copiado y observaciones), el monitor, sus recibos, los dos
wrappers actuales, la revisión y las once dependencias originales. El inventario
de miembros de runtime coincide con los archivos correspondientes en disco.
El contrato es `7250620e…a27158f`; launch y completion declaran
`scientific_inputs_changed=false` y conservan la misma revisión de runtime.

El mapa de 6.084 checkpoints preservados del completion coincide exactamente
con el del launch. Todos sus hashes están incluidos sin cambios en el mapa final
de 11.699 checkpoints; las rutas finales existen y permanecen dentro de la raíz
científica. **Aquí se comprobaron esos mapas y la existencia de sus rutas, no se
rehashearon los bytes de los checkpoints científicos.** Tampoco se leyeron sus
métricas, selección, modelos o arrays. Su comprobación económica y de fuentes
corresponde a una auditoría independiente de 2025 que cierre satisfactoriamente.

Pins de los cierres reales, sin sustituir una autoridad económica futura:

| Archivo | SHA256 |
|---|---|
| `completion.json` | `ccce687bfa850d894606ff29ef6014add9e39a142fd84c3dd0d76e2a2a5c185b` |
| `monitored_exit.json` | `918964c6474df52067db5fb6eecb1c07339cb9bca262e8cab560f22ba3b00e93` |
| Wrapper test | `f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1` |
| Launcher publicado en `fee235ee` | `3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d` |

## Recibo y frontera pendiente

Recibo nuevo: `D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_runtime_chain_verification_20261024_01/verification.json`.
SHA256: `b7b64e2a3d8dd1751287f0530151a09100e2949aa4295b1f52a246855a5d3730`.
Se conserva una [copia exacta](continuation_20261024/monthly_validation_runtime_chain_verification/verification.json)
con [manifest de fuente y hash](continuation_20261024/monthly_validation_runtime_chain_verification/manifest.json)
para publicación compacta, sin reejecutar la verificación ni alterar el original.
Contiene todos los checks, hashes consumidos, conteos y límites. Status:
`COMPATIBLE_FINAL_RUNTIME_RECEIPT_CHAIN_READ_ONLY`.

La futura request debe incluir `source_launch=process.json`, permitir las raíces
de lectura necesarias y ejecutarse desde el repositorio, porque el comando
histórico guarda la ruta relativa del wrapper. El campo histórico
`source_monitor_sha256` no sustituye el pin del monitor retenido actual.
Durante el cierre de esta nota, el coordinador comunicó un fallo técnico del
auditor 2025: `Path(None)` al consumir metadata, exit 1 del PID 6840. Ese proceso
no se investigó aquí y no produjo un PASS económico. La revisión correctora y
su eventual ejecución son trabajo separado; no cambian esta cadena del productor.
Siguen pendientes una auditoría económica satisfactoria, sus hashes externos
revisados y la admisión operativa completa. Este recibo no autoriza test 2026,
OOF o promoción.
