# Ajuste y disponibilidad de las señales compactas

Diagnóstico sólo de TRAIN2023–24 sobre las mismas270377filas, objetivos netos,
escalas y pesos IPW del control original. No hay fit adicional, política nueva,
lectura de2025/2026 ni afirmación de generalización. Matriz, targets, identidad
de muestra, modelo y fuentes verificados antes/después; máscaras binarias,
valores finitos y ausencia representada por cero+valid0 comprobados.

| Medida ponderada en unidades de riesgo TRAIN | Compacto |
|---|---:|
| R² sobre su propia muestra de ajuste | 0,196962 |
| MSE | 0,476396 |
| Media del target / predicción | −0,079321 / −0,079432 |
| Desviación del target / predicción | 0,770222 / 0,201675 |
| Predicciones positivas / targets positivos | 9,9043% / 25,1281% |

El control original obtuvo R²0,251588 en esta misma muestra. La representación
compacta ajusta menos varianza; esto no determina cuál generaliza mejor. Se
conservan objetivo, pesos y muestra para que la comparación posterior pruebe la
representación, sin cambiarla por estos resultados TRAIN.

Las mayores ganancias de división del árbol corresponden a objetivo relativo
al spot, rango IB/spot, stop relativo al spot, proporción de calls con OI positivo,
gamma unsigned put y concentración top3 del OI call. Son variables que el modelo
utilizó al ajustar; la importancia no demuestra causalidad ni explica por sí
sola una operación del oracle. Tampoco equivale a una ablación fuera de ajuste.

Hay una limitación concreta en la representación de cambios de exposición:

| Señal | Fracción válida ponderada |
|---|---:|
| Gamma unsigned actual, call y put | 99,9372% |
| Cambio gamma call respecto a media log de barra5m | 0,0164% |
| Cambio gamma call respecto a media log de barra15m | 0% |
| Cambio gamma put respecto a media log de barra5m | 1,2348% |
| Cambio gamma put respecto a media log de barra15m | 0,5071% |

La regla actual exige cobertura completa de identidades/OI/IV/presencia para
comparar masa agregada. Que la masa actual sea observable en parte no hace
comparable automáticamente su cambio: podría variar la composición cubierta.
Esto merece investigar una comparación causal de las mismas identidades
observadas en ambos instantes, con cobertura explícita. No se modifica la
representación congelada ni se rellena la exposición ausente; tampoco se
concluye que no haya señal en el movimiento de gamma.

Artefacto: `D:/GexResearchArtifacts/level_oracle_20261018/market_cue_train_diagnostic_v1`.
Summary SHA256: `a08e3be1e8d2e9d96c21a931a7223113d52714f7b7c0d4a27576ca06c2680a73`.
Script: `inspect_market_cue_training.py`; Ruff PASS, ejecución4,75s exit0.
Las predicciones TRAIN quedan guardadas para reproducir este diagnóstico.
