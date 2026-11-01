# Diagnóstico descriptivo de las probabilidades congeladas

Análisis posthoc de outputs cerrados, sin nuevos fits, scores, replay o selección.
No es un holdout limpio. El beneficio de H1/Q3 no demuestra por sí solo que
la probabilidad de escenarios y su magnitud condicional estén bien estimadas.

Ev_decision_sources comprobó en memoria los candidatos/scores sellados. Para
cada lado: EV positivo es ev_adverse>0; predicción es media p_cal[4]; frecuencia
es media(scenario==4). La clase4 representa retorno bruto>=25%. Las frecuencias
incluyen la contabilidad conservadora y NO_FILL de todo el universo, no sólo
salidas observadas ni sólo las operaciones seleccionadas.

| Periodo/lado | Candidatos | EV positivo | Probabilidad media clase4 | Frecuencia clase4 |
|---|---:|---:|---:|---:|
| H1 CALL | 213 | 124 | 0,288989 | 0,276995 |
| H1 PUT | 213 | 1 | 0,216560 | 0,220657 |
| Q3 CALL | 90 | 46 | 0,291595 | 0,188889 |
| Q3 PUT | 90 | 0 | 0,226382 | 0,255556 |

En Q3 el orden predicho CALL>PUT para clase4 no coincide con su frecuencia.
No es una prueba de significancia ni una recomendación de invertir el lado.
El scheduler y las señales resultaron en75CALL/0PUT en H1 y28CALL/0PUT en Q3.
La clase superior no acota la ganancia: usar una media por clase mezcla la
probabilidad del evento con variación muy grande de la magnitud dentro de él.

Control algebraico PRIOR_ONLY: sumar por clase el priorTRAIN almacenado por
la misma media TRAIN adversa de ticker/lado. Retornos esperados normalizados
por prima de decisión: SPY CALL−0,0447066971/PUT−0,0432043556;
QQQ CALL−0,0474717531/PUT−0,0535007728;
SPXW CALL−0,0350044447/PUT−0,0280777989. Son negativos los seis: con askpositivo
el control implicaría WAIT. Esto se deduce de la fórmula, no de un replay nuevo.

Por tanto las features desplazan probabilidades lo suficiente para producir
EV positivo casi exclusivamente enCALL; todavía debe demostrarse que ese
desplazamiento añade información temporal útil frente a lado/ticker/weekday.
La hipótesis siguiente es información incremental de contexto IB/walls sobre
controles simples. La economía deberá contrastarse con riesgo comparable.

Pins de fuentes cerradas bajo D:/GexResearchArtifacts/weekly_multiday_20261101:
model.json68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4;
conditional_means.jsona8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90;
H1 candidate_scores.jsonl812d92db1206e6b5df9c3c4037c6cf6a68d3a5196ebd70be9ef2fd89adcb4ae9;
manifestH154dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96.
Q3scores9458c8dfa75983784af0e7514feec1ded43a42adadecfb07c0406aee3f284ca6;
manifest7bd50a5a1fe5214df2c4281e785313f0fb016ca73d725d682788dcb78b283d8e.
El lector usó sus copias exactas del repositorio h2_v2_evaluation_evidence_01 y
q3_partial_scoring_evidence_01. No acceso D:/ThetaData ni evidencia live.
