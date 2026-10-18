# Diagnóstico retrospectivo de la política seleccionada

`analyze_learner_regret.py` sólo puede ejecutarse cuando el learner tenga estado
`COMPLETED_CAUSAL_LEARNER_DEVELOPMENT`. Lee la política que ya quedó elegida en
validación y comprueba su igualdad con el freeze. No entrena, predice, selecciona
otras políticas ni abre fuentes raw. Los fixtures usan datos artificiales.

La ejecución se lanza por separado, indicando `--learner-root`, `--engine-root`
y una raíz nueva `--output`. No hay ejecución automática desde el trainer. Procesa
2025 y 2026H1 por separado; conserva días sin fuentes como ceros explícitos.

Para cada estado plano realmente visitado calcula:

`regret(t) = V_oracle(t) - [PnL_base_decisión + V_oracle(siguiente_estado_operable)]`.

WAIT y NO_FILL avanzan un minuto, con PnL cero. Una entrada ejecutada avanza a
`exit_i + 1`; los minutos mientras la posición está abierta no se contabilizan
otra vez. Se comprueba la recurrencia de Bellman en los labels completos, que
los attempts coincidan con acciones/labels y que sus fills reproduzcan el ledger.
La suma diaria debe ser exactamente, dentro de tolerancia numérica,
`PnL_oracle_base - PnL_learner_base`. El diagnóstico no usa el escenario adverso,
porque el V almacenado corresponde al oracle optimizado con costes base.

Los componentes son aditivos:

- `wait`: diferencia retrospectiva al no intentar una entrada.
- `no_fill`: diferencia al intentar una acción que no llegó a ejecutar. No se
  sustituye por otra operación del mismo minuto.
- `entry_timing`: en una entrada llena, ventaja retrospectiva de WAIT sobre la
  mejor entrada disponible, si la hubiera.
- `side`: mejor entrada llena de cualquier lado menos la mejor del lado elegido.
- `contract`: mejor entrada del lado elegido menos la mejor del contrato elegido.
- `target`: mejor objetivo de ese mismo contrato menos el objetivo elegido.

Los tres últimos componentes se basan en Q retrospectivo, que incluye la
continuación óptima del oracle. La asignación depende del orden declarado
lado→contrato→objetivo; no es una atribución causal ni la mejora que conseguiría
cambiar una sola variable dentro de la política real. `hindsight_trade_rank`
ordena la acción elegida entre entradas llenas del mismo estado mediante ese Q.
`hindsight_optimal_value` admite empates de valor: no afirma coincidencia exacta
con el action ID del teacher, cuyo desempate puede preferir WAIT.

Se producen `visited_decisions.parquet`, `daily_regret.parquet`, `summary.json`
y un manifest de hashes. La escritura de eventos es incremental por día. Se
verifican hashes del índice auditado y cada sidecar consumido, identidad del
freeze y todos los archivos de autoridad `oracle_audit.verified_files`. El
resumen test de la política seleccionada debe coincidir con `selected_test`
del resumen terminal; CASH requiere `selected_test=null`. También se contrastan
sumas y número de trades frente al resumen del learner. Los inputs y archivos
de autoridad se rehashan al terminar. Un fallo deja el intento conservado sin
summary terminal.

Un gap grande de WAIT para CASH es esperable: equivale al beneficio del oracle
privilegiado. **No demuestra que esperar fuese una decisión causalmente errónea
ni que el gap pueda recuperarse sin futuro.** El diagnóstico localiza dónde se
separan las trayectorias; no elige un modelo, horario, ticker o parámetro usando
2026 ni altera el resultado de la política congelada.
