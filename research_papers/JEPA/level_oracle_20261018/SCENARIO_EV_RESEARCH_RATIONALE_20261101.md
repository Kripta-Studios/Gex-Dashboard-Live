# Qué cambia al investigar escenarios y valor esperado

Nota documental, sin autorización de nuevos fits, lecturas de outcomes o
evaluaciones. El contrato siguiente espera el cierre económico FULL_H1.

La regresión del retorno neto ya formaba parte de esta investigación:
`train_models.py:757-781` ajusta `gbt_net` a `net_base` escalado y
`:928-952` combina regresión neta con imitación binaria del oracle en la TCN.
El mensual también ajusta neto escalado (`run_monthly_walk_forward.py:630-650`)
y elige el máximo positivo por estado (`:734-750`). Son aproximaciones al
retorno condicional medio; no se debe presentar EV como un objetivo nunca probado.

El OOF añade, por ticker, el promedio por día de residuos de máximos elegidos
con información anterior (`oof_maximum_calibration.py:355-379`). El adaptador
suma ese offset sin alterar ranking ni umbral0
(`monthly_oof_calibration_adapter.py:515-568`). Corrige un score monetario;
no estima las cuatro probabilidades de escenarios.

La diferencia sustantiva propuesta es descomponer explícitamente el valor:

`EV_c(X,a) = sum_s P(s|X,a) * E[net_c|s,X,a]`,

con `s=NO_FILL/TARGET/STOP/EOD` y `c=base/adverse`. TARGET no representa un
premio fijo ni necesariamente positivo. La identidad no aporta ventaja por
sí sola: una descomposición estimada puede ser peor que la regresión directa.
El futuro contrato necesita un control directo comparable bajo los mismos
datos, splits, costes y scheduler. El diseño exacto aún no está fijado.

La autorización del usuario permite días sin operar. No se penalizará WAIT
por incumplir un mínimo diario. Su retorno inmediato es cero, pero su valor
de continuación puede ser distinto; por eso el EV por oferta debe contrastarse
con la política secuencial y no sólo con sumas de oportunidades solapadas.
Esperar siempre tampoco demuestra una ventaja rentable. Una fuente ausente
continúa siendo NO_EVALUABLE, no una sesión artificial de abstención.

## Evidencia metodológica consultada

Las reglas de puntuación estrictamente propias incentivan reportar la
distribución creída. Esto justifica evaluar las probabilidades explícitamente,
separando su calidad de la rentabilidad; no establece qué modelo usar ni
garantiza calibración empírica. [Gneiting y Raftery, versión revisada](https://stat.uw.edu/research/tech-reports/strictly-proper-scoring-rules-prediction-and-estimation-revised).

Una decisión de coste esperado usa probabilidades y consecuencias, y puede
diferir de elegir la clase más probable. Las consecuencias deben compartir
una referencia económica coherente. Aquí serán netos por oferta frente a CASH,
sin cobrar dos veces los costes ya incluidos. [Elkan, 2001](https://cseweb.ucsd.edu/~elkan/rescale.pdf).

La calibración por subpoblaciones es una exigencia más fuerte que la global.
**Inferencia para este proyecto:** elegir el máximo crea una subpoblación de
ofertas seleccionadas; una métrica global no basta para acreditar calidad allí.
La futura evaluación debe informar también esa selección, con incertidumbre y
soporte declarado, sin escoger retrospectivamente celdas favorables.
No se atribuye al artículo una demostración específica para trading o top-1.
[Hébert-Johnson et al., 2018](https://proceedings.mlr.press/v80/hebert-johnson18a.html).

Las fuentes anteriores no acreditan rentabilidad, estabilidad temporal ni
observaciones independientes por cada oferta. Los datos 2025/2026 ya vistos
siguen siendo SEEN_DEVELOPMENT. Umbrales, scoring, calibrador, incertidumbre,
capacidad y particiones deberán fijarse en un contrato posterior; esta nota
no los selecciona ni modifica el OOF congelado.

Revisión de código por `/root/scenario_admission_draft`, contrastada por root
en los fragmentos citados. Revisión bibliográfica por `/root/ev_decision_sources`;
root verificó páginas primarias. Sin abrir resultados de mercado nuevos.
