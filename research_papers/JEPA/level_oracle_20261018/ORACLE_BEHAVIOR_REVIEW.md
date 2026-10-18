# Revisión del análisis descriptivo del oracle

Fecha: 2026-10-18. Estado: **PASS_REVIEW_AND_EXECUTED_SNAPSHOT**. Verificación final de consistencia de código y artefactos completada tras terminar v2; este estado no es una auditoría independiente de todos sus agregados.

Esta revisión abarca `analyze_oracle_behavior.py`. No modifica el motor, las acciones ofrecidas, los labels, las políticas o las dependencias congeladas. Tampoco sustituye la auditoría económica independiente. La comprobación final solicitada es de código y hashes, sin repetir el mercado.

## Hallazgo y corrección

La versión inicial denominaba `skipped_known_levels` y `crosses_intermediate_known` a un recuento geométrico de centros situados entre el spot del estado y el objetivo. Ese recuento no observaba la trayectoria posterior y podía incluir el centro de la propia zona de entrada. Por ello no justificaba una afirmación sobre niveles efectivamente atravesados ni sobre distancia recorrida.

La revisión inicial encontró un ejemplo en los artefactos ya existentes de SPY, 2023-01-03: las acciones 0 (estado 60, salida STOP) y 6358 (estado 371, salida EOD) tenían un centro contabilizado; en ambos casos era el propio centro de entrada. Esta evidencia procede de la inspección inicial de artefactos, no de una nueva simulación.

El autor ha aplicado antes de v2 estos cambios:

- Excluir `entry_level_id` del recuento y llamarlo `known_nonentry_centers_to_target`.
- Llamar al agregado `has_intermediate_nonentry_centers_to_target`.
- Describir la distancia que se propuso recorrer, con una nota explícita de que la geometría proyectada no prueba cruces realizados y una salida STOP/EOD puede no alcanzar esos centros.
- Aclarar que los bits de procedencia pertenecen a clusters deduplicados, pueden solaparse, y gamma es un proxy Black–Scholes × OI, no gamma observado ni posición de dealers.

La exclusión de la entrada no altera el ranking de objetivos ofrecidos: la entrada está a distancia como máximo una banda, mientras que un objetivo elegible exige más de dos bandas.

## Comprobaciones restantes

No se detectó otro error material en los aspectos revisados:

- Los vecinos temporales exigen el mismo contrato, lado, objetivo, stop y banda; la comparación está declarada como sensibilidad aislada, no como otra política diaria ejecutable.
- El ranking directo compara los payoffs del mismo estado. El margen DP compara las alternativas y WAIT usando el valor de continuación, y el informe distingue ambos conceptos.
- La intención de cinco minutos utiliza dos posiciones respecto de la zona actual. El texto la presenta como clasificación geométrica, sin afirmar rebote confirmado o existencia histórica de la wall actual.
- La atribución por bits OR y las categorías Fib sola / walls solas / mezcla son coherentes con los niveles agrupados del motor. La pertenencia de varios bits no es atribución causal del beneficio.

## Versiones y verificación final

La ejecución inicial se detuvo sin agregados finales, según el autor. Su snapshot está preservado en `D:/GexResearchArtifacts/level_oracle_20261018/oracle_behavior_v1/analyze_oracle_behavior.executed.py`, SHA-256:

`5fab0f4b7161fb413d7a542061fade5e8494240a4b92236d04bb5e4627a8d0e4`

Se revisó el diff completo entre ese snapshot inicial y v2. Además de la corrección descrita, v2 indexa los vecinos mediante las mismas claves económicas exactas, agrupa previamente los niveles por estado, procesa días en orden con dos workers y añade diagnósticos de netos mínimos/cero. No cambia ranking DP, contratos, payoffs o reglas del motor. La explicación añadida de WAIT y los netos positivos es coherente con el objetivo retrospectivo.

Se comprobó igualdad SHA-256 de los siguientes tres elementos:

- `research_papers/JEPA/level_oracle_20261018/analyze_oracle_behavior.py`.
- `D:/GexResearchArtifacts/level_oracle_20261018/oracle_behavior_v2/analyze_oracle_behavior.executed.py`.
- El campo `source_sha256` de `oracle_behavior_v2/execution.json`, con estado `RUNNING`, dos workers y fecha de inicio `2026-10-18T17:03:23.296651+00:00`.

SHA-256 común:

`ff09ae8cdda7848c969416ea70a3d2bf8d42e09947bc54c3a20c995d39ff9ba3`

El autor preservó además `oracle_behavior_v1/performance_equivalence.json`: `PASS_EQUIVALENCE_UNCHANGED_FIELDS` sobre las ocho filas QQQ del piloto 2023-01-03, vinculando ambos hashes y declarando la única diferencia geométrica prevista. Esta revisión leyó esa evidencia y el diff; no repitió esa ejecución ni el mercado.

Tras finalizar v2 se verificó además `summary.json.status=COMPLETE_DESCRIPTIVE_HINDSIGHT` y `execution.json.status=COMPLETE`. El campo `summary.json.analyzer_sha256`, el campo `execution.json.source_sha256`, el snapshot y el script del repositorio coinciden con el SHA común anterior. Este control final no volvió a ejecutar mercado ni recalculó métricas.

El control solicitado de corrección y snapshot ejecutado queda cerrado. La reproducción independiente de todos los agregados descriptivos debe distinguirse de este PASS de revisión y consistencia de código.
