# Continuación mensual: cambio exclusivo de recursos

18 de octubre de 2026, posterior al inicio de la validación mensual. El usuario
ha sustituido el margen operativo anterior por **2.000.000.000 bytes libres**
tanto de RAM física como de commit. Es GB decimal, no GiB. No es una cota medida
del pico futuro ni garantiza que el sistema no cambie mientras se ajusta.

`run_monthly_resource_overlay.py` sustituye únicamente la función global
`train_causal_rollout.wait_resources` durante la llamada al `main` mensual
original. Lee los mismos contadores reales, espera 30 segundos si falta cualquiera
de los dos recursos y admite exactamente el umbral. Cada observación, incluida
la admisión, se conserva en el directorio externo. Restaura la función y `sys.argv`
en `finally`, también tras un fallo. No modifica modelos, CONFIG, muestras,
targets, pesos, matrices, normalizadores, calendarios, scheduler ni selección.

El alcance es exclusivamente `--stage validation`; se conserva la CLI original
de fuentes, auditor y revisión. El contrato original está fijado por SHA
`7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`.
Sus once dependencias y snapshots científicos no reciben el wrapper. La revisión
independiente debe tener status `PASS_MONTHLY_RESOURCE_OVERLAY_REVIEW` y los
campos exactos de `review_expectations()`: hashes de wrapper, fixtures y este
documento; once dependencias originales; contrato; umbral; scope y declaración
`scientific_inputs_changed=false`.

La transición del proceso previo es una operación coordinada separada. No se
detiene aquí ningún proceso. Antes de detenerlo se debe suspender y comprobar
que no empezó un fit; si empezó, se reanuda y se deja terminar. El wrapper exige
que el PID anterior ya no exista y rechaza cualquier fit_started sin completion
verificable. No se eliminan markers ni se reintentan fits interrumpidos. Un PID
reutilizado también provoca rechazo conservador.

Los dos modelos ya completos, enero y la matriz/targets/inputs preparados para
febrero se preservan. El resume original revalida fuentes y chunks y carga los
modelos completos; no hay ruta rápida alternativa. Se registran hashes de todos
los markers completos previos, modelos, fit_started, snapshots y contrato; tras
la ejecución deben permanecer idénticos. Los payloads de chunks y matrices se
validan mediante el resume original, no se acredita una segunda reconstrucción
económica desde este wrapper.

Un directorio externo nuevo por intento contiene snapshots del overlay,
`launch.json`, observaciones y `completion.json`, o `failure.json`. El cierre
liga todos los miembros runtime, la revisión y los checkpoints científicos
finales. Un directorio existente se rechaza: si hubo interrupción se preserva y
se utiliza otro intento, sujeto a la misma prohibición de refit incompleto. El
auditor económico puede incorporar este manifest como autoridad runtime separada;
no debe atribuirle regeneración de predicciones o demostración de recursos
históricos. No se altera el binding científico para ocultar el cambio operativo.

Fixtures exclusivamente sintéticos: bordes decimales para cada contador,
restauración normal/excepcional, identidad de fit_once/main intacta, CLI limitada,
rechazo de proceso vivo/fit incompleto, conservación de hashes y manifest de
continuación con un main doble. Ningún benchmark, ajuste o nuevo outcome real
forma parte de esta implementación/revisión.
