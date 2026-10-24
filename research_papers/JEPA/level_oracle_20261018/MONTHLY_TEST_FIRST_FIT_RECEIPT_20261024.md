# Runtime test y primer modelo completado: recibo técnico

El primer fit nuevo del test mensual, `train_20230101_20260101_exclusive`, comenzó a las **01:14:49.983321 UTC del 24-oct-2026** y publicó su marker `COMPLETE` a las **01:16:16.624000 UTC**. La matriz declarada tiene **286.008 filas × 1.954 columnas**. El modelo y su `fit_started` se rehashearon y coinciden con el sello. Este es un cierre técnico de un modelo; todavía no acredita resultado económico ni auditoría independiente de 2026.

El [fit_started](continuation_20261024/monthly_test_preparation_01/models/train_20230101_20260101_exclusive.fit_started.json) conserva el contrato `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`, la configuración original y el SHA de la matriz sellada. Su hash es `e765493b82c94be41d6edb2a4fe6543aab61cf3a1501ab99baee1d6561166425`. El [marker del modelo](continuation_20261024/monthly_test_preparation_01/models/train_20230101_20260101_exclusive.complete.json) tiene SHA `814e41120550dae406c34203d26327cf875baad0093989091b3b63dc1daf82c4`; el [modelo](continuation_20261024/monthly_test_preparation_01/models/train_20230101_20260101_exclusive.txt), `147e4c912d48fdd9e0d0206193b536eb28dd4c8354e5b7ced5ecbdbf36dfe494`.

## Runtime y preparación anterior al fit

El child PID 34680 publicó `MONTHLY_TEST_RESOURCE_OVERLAY_STARTED` a las **00:52:52.035237 UTC**. El [launch del runtime](continuation_20261024/monthly_test_preparation_01/runtime/launch.json), SHA `dce4a9ab8ab3edd1da90ef82feb59e83a74a5a4f4f8fd230258abad274bc49f3`, fija stage `test`, 11.699 checkpoints preservados y cinco snapshots. Los cinco snapshots copiados coinciden exactamente con sus hashes del launch. El código científico permanece congelado.

La preparación del primer fit publicó estos sellos, todos bajo el mismo contrato:

| Artefacto | Sello UTC | Tamaño local del payload |
| --- | --- | ---: |
| Targets | 01:10:17.537698 | 1.302.239 bytes |
| Matriz | 01:11:02.570253 | 2.235.438.656 bytes |
| Inputs | 01:14:47.704773 | 4.903.648 bytes |

Los [sellos de preparación](continuation_20261024/monthly_test_preparation_01/fit_seals) y las [referencias locales](continuation_20261024/monthly_test_preparation_01/LOCAL_REFERENCES.json) preservan rutas, tamaños y hashes declarados por el productor. Se comprobó existencia y tamaño de los payloads, y concordancia del SHA de matriz entre su sello y el `fit_started`. Durante la preparación de este archivo no se copiaron ni se rehashearon de nuevo matriz, targets o inputs. La revisión posterior de root sí rehasheó `inputs.json` y comprobó sus fechas, dimensiones y configuración; no rehasheó sus 27.076 entradas referenciadas ni los payloads de matriz/targets. Estos checks no constituyen una auditoría independiente completa del nuevo fit. El hash de `targets.npz` identifica el contenedor; los hashes de vectores target/weight del `fit_started` tienen otro alcance.

El [gate inmediatamente anterior al fit](continuation_20261024/monthly_test_preparation_01/resource_gate.json), a las **01:14:49.964840 UTC**, registró `RESOURCE_OVERLAY_READY`, RAM disponible de **6.791.708.672 bytes** y margen de commit de **4.082.683.904 bytes**, por encima del umbral fijo de **2.000.000.000 bytes**. No se modificó la configuración del modelo para obtener ese gate.

## Archivo y límite del hito

El [manifest](continuation_20261024/monthly_test_preparation_01/MANIFEST.json) contiene 13 copias compactas: launch, cinco snapshots, tres sellos de preparación, gate, fit_started, modelo y su marker. Originales y copias se rehashearon y coinciden. Los payloads grandes permanecen locales por referencia. No se añaden aquí afirmaciones sobre chunks que no formen parte de esas copias verificadas.

Al corte archivado de **01:16:24.909590 UTC**, había **25 modelos completos en total** —los 24 anteriores y este primero nuevo— y ningún directorio mensual 2026. No se abrieron predicciones, ledgers, PnL ni métricas parciales. No se infiere la salida del child, completion global o PASS económico. El productor y su monitor continúan observados por separado.

El [recibo anterior de inicio](MONTHLY_TEST_START_RECEIPT_20261024.md) y su archivo `monthly_test_start_01` permanecen intactos como observación histórica de 00:35:50 UTC. Este nuevo recibo documenta los hitos posteriores sin reescribirlo. No hubo segundo lanzamiento ni reintento.
