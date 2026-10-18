# Auditoría económica independiente del aprendiz de episodios

Estado: **PRE-EJECUCIÓN**. Este contrato se publica antes del único fit de
`gbt_net_episode` y antes de leer sus predicciones o resultados económicos.
El auditor será un programa separado y no importará `train_episode_model.py`,
`episode_policy.py`, `run_policy.py`, `level_engine.py` ni sus cálculos de
métricas. No refitteará modelos ni regenerará predicciones: su alcance es la
ejecución económica **dadas** las predicciones selladas.

## Autoridad e identidad

El auditor exigirá terminación exitosa del productor y vinculará por SHA256 el
plan y código congelados, modelo nuevo, control original, muestra de270.377
filas, matriz2024, escalas, freeze, manifests de predicción, índice/completion y
auditoría FULL del motor, build de episodios y fuentes consumidas. Verificará
que la matriz conserve exactamente las1954 columnas originales, que las70
nuevas sean35 valores seguidos de35 máscaras unidos por
`(ticker,date,state_i)`, y que muestra, orden, `sample_i`, target y pesos sean
los del control. Estas comprobaciones de identidad no equivalen a un refit.

Cada NPZ de validación2025 y test enero–junio2026 debe aparecer exactamente una
vez en su manifest y contener `action_ids`, `gbt_net` y `gbt_net_episode`,
alineados al universo sellado de acciones. Los scores deben ser finitos. El
control debe ser byte-idéntico al vector original correspondiente y conservar
su manifest; no se admitirá un control refitteado.

El primer intento técnico terminó después de sellar matriz y modelo y antes de
publicar la primera predicción: trató `Day.features`, que ya es el NPZ, como un
directorio al formar cuatro rutas de manifest. La continuación externa sólo
cambia esas cuatro rutas a su directorio padre, exige el marker del modelo,
prohíbe todo constructor de fit y conserva su SHA. El auditor exigirá el fallo,
script/record/completion de reparación y runtime de salida0, incluida la prueba
de cero refits. Esta reparación de procedencia no cambia features ni scores.

## Reconstrucción independiente

Para cada uno de los dos modelos y umbrales0/5/10 USD, el auditor reconstruirá
sin imports del productor:

1. En cada estado, máximo score y desempate por menor `action_id`.
2. WAIT salvo `score > threshold` estricto.
3. NO_FILL avanza a `state_i+1`, sin rescatar otra acción del mismo estado.
4. FILLED avanza a `exit_i+1`; no puede haber solapamiento.

Comparará identidad y contenido de attempts y ledger, calendario diario completo
con ceros, resúmenes pooled/ticker/mes, costes base/adverso, PF e indefinición,
win rate, drawdown por orden realizado, TARGET/STOP/EOD y duraciones. También
reconstruirá las diferencias emparejadas y bootstrap si el productor las
publica, usando exactamente fechas completas,10.000 muestras y seed20261018.

## Restricción diaria y selección

CASH no es candidato. Para cada política se contarán fills por cada combinación
ticker-fecha del calendario. En2025 sólo son seleccionables las políticas con al
menos un FILLED en **cada** ticker-día disponible y cobertura completa. Entre
ellas se maximiza la suma por ticker de neto base dividido por la escala train;
los empates conservan el orden control antes de variante y umbral menor.

Si ninguna política es viable, el auditor exigirá
`FAIL_NO_DAILY_COMPLIANT_POLICY`, `selected_policy=null` y `approved=false`.
Podrá reproducir un `diagnostic_policy` por el ranking normal congelado antes
del test, pero nunca lo convertirá en selección o rescate. El freeze debe
preceder todos los NPZ de test y contener las seis opciones, su viabilidad y la
decisión o diagnóstico.

En2026 se audita de nuevo el mínimo diario. Un día disponible con cero fills es
incumplimiento. Los seis ticker-días sin fuente permanecen en el calendario como
`NO_EVALUABLE` y causan un fallo de cobertura separado; no se contabilizan como
cero oportunidades de mercado ni se excluyen. El gate conjunto exige selección
viable2025, cobertura, mínimo diario2026 y el gate económico original por los
tres tickers: netos base/adverso positivos, PF base≥1,2, al menos60 trades y al
menos3 meses positivos.

## Límites

Un PASS acreditará integridad y reproducción de la ejecución económica dadas
las predicciones. No acreditará reproducción independiente del fit/inferencia,
edge causal, recepción real, fills live o promoción. 2026 ya es desarrollo visto.
