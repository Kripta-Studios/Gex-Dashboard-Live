# Ejecución y recuperación del GBT de episodios

El intento autorizado empezó el 18 de octubre de2026 a18:05:56 UTC, PID28416,
desde código revisado y16fixtures PASS. Root:
`D:/GexResearchArtifacts/level_oracle_20261018/episode_learners_v1`.
Runtime: `episode_learners_v1_runtime_v1`. El control permanece inmutable.

Un solo nuevo GBT200árboles, CPU4, sinGPU. Los checkpoints son de matriz, modelo,
predicciones por día, periodos económicos, freeze y cierre. `identity.json` vincula
plan/código/dependencias, muestra y modelo original, episodios y auditorías.
Cada `*.complete.json` verifica hashes de inputs y artefactos antes de reutilizar.
Los NPZ diarios guardan `action_ids`, `gbt_net`, `gbt_net_episode`; su marker
incluye fuentes y reproducción exacta del control.

El scheduler mantiene libertad temporal: no fuerza ninguna entrada. La restricción
de una operación ejecutada por ticker-día se aplica a selección y evaluación.
Si ninguna política2025 es viable, `selected_policy=null`; el mejor diagnóstico
congelado no se transforma en candidato aprobado por su resultado2026.

El primer intento terminó a18:08:39 UTC después del único fit completo. Falló
el registro de cuatro rutas de fuentes en la primera jornada de validación:
`Day.features` ya era el archivo NPZ. No publicó predicciones nuevas ni abrió
labels de validación. Matriz y modelo completos quedaron sellados; se conservan
el fallo, el código original y el runtime.

La continuación revisada usa un wrapper separado que sustituye exclusivamente
esos cuatro joins por `day.features.parent`. Verifica el modelo completo y
prohíbe cualquier constructor de fit. Dos fixtures sintéticos verifican
equivalencia de predicciones/rutas y dos continuaciones sin refit con un fallo
posterior preservado. Conserva el runtime original y comprueba que no hay
proceso vivo antes de ejecutar:

```powershell
python -u research_papers/JEPA/level_oracle_20261018/launch_episode_pathfix.py `
  --root D:/GexResearchArtifacts/level_oracle_20261018 `
  --output D:/GexResearchArtifacts/level_oracle_20261018/episode_learners_v1 `
  --runtime D:/GexResearchArtifacts/level_oracle_20261018/episode_learners_v1_runtime_v2 `
  --resume
```

`technical_repairs/source_path_v1/repair.json` vincula el código original,
el wrapper, las funciones original/reparada, el modelo y el fallo inicial.
Su cierre y el runtime nuevo vinculan la continuación y acreditan cero refits.
El log original imprime `fit_start` al entrar en `fit_variant`, antes de comprobar
su checkpoint. En esta continuación ese marcador significa recarga del modelo
completo; no demuestra un fit. La prohibición del constructor y los hashes antes/
después proporcionan la verificación correspondiente.
En otra interrupción técnica, utiliza una raíz runtime nueva y el mismo wrapper
inmutable. La lista de fallos originales queda congelada; los posteriores se
preservan sin invalidar esa lista.

Un lock exclusivo del sistema operativo impide dos escritores. No hay checkpoint
dentro del ajuste GBT: si su finalización no quedó publicada, el fit incompleto
puede necesitar repetirse. Con marker modelo completo se recarga y no se refittea.
Los outputs sin marker íntegro se preservan bajo `preserved/`; una etapa completa
con hash distinto falla cerrado, sin reconstrucción silenciosa.

Predicciones diarias completas se reutilizan; ledgers/resúmenes de un periodo
interrumpido se vuelven a calcular con esos mismos scores. Un freeze íntegro
conserva la selección. Si test ya existe y falta autoridad de freeze, el proceso
rechaza antes de cualquier etapa entrenable. Fallos causales, nonfinite, cambio
de identidad o resultados desfavorables no son razones de reintento.

El launcher exige10GiB RAM y12GiB commit libres antes de empezar; limita BLAS/MKL/
NumExpr/OMP a1 y mantiene LightGBM4. Registra PID/hora/comando, progreso, tiempos,
picos privados/RSS y hashes finales. No termina procesos ajenos. Los snapshots
están en el mismo disco y no sustituyen un backup independiente.

La continuación terminó con exit0 a19:31:32,746UTC. Runtime2:4553,178s,
pico privado1.341.026.304bytes y RSS933.388.288bytes. El bloque registrado como
test incluye inferencia/evaluación y largos rehashes finales, no sólo cómputo
económico. El cierre de reparación acredita `TECHNICAL_CONTINUATION_COMPLETE_ZERO_REFITS`;
SHA modelo97a82c3f2146af85a924dc4b0de8aed717fc224216b87a339b8d684ddbcdfd46,
invariante antes/después. No queda una continuación pendiente para esta ejecución.
Resultado: ninguna política cumplió el mínimo diario en validación;
`selected_policy=null`, `FAIL_NO_DAILY_COMPLIANT_POLICY`. El informe completo
está en `EPISODE_LEARNER_RESULT.md`; su auditoría se registra por separado.
