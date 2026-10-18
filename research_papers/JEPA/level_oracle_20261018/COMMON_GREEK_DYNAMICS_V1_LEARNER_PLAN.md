# Comparación fija futuro ajuste424 frente al control compacto152

2026-10-18. Se fija antes de construir TRAIN272, ajustar o predecir esta familia.
No autoriza ejecución: builder feature-only revisado primero, después review y
coordinación de recursos para fit y evaluación. Ningún modelo anterior se cambia.

Control primario: cue_net.txt ya existente,152features, SHA
a457176f12df8ab44964f1b595c75439320c8ee27db9da7a740b95f29fa016c7.
Variante: mismo LightGBM y target netUSD dividido por escala TRAIN, sobre424
features (152prefijo idéntico+272dinámicas COMMON_GREEK_DYNAMICS_V1_DESIGN.md).
Mismos270377IDs/orden, IPW, semillas, escalas QQQ88/SPXW680/SPY81 y labels del
entrenamiento original. Ningún remuestreo, filtro de outcomes ni target nuevo.
El control no se refittea y no se cambia según sus métricas todavía pendientes.

CONFIG exacta: objective regression,n_estimators200,num_leaves31,max_depth6,
min_child_samples100,learning_rate0.04,reg_lambda10,max_bin63,random_state20261018,
n_jobs4,deterministic=true,force_col_wise=true,verbosity−1. Un solo fit, sin sweep,
early stopping, calibración ni selección de épocas. Checkpoint modelo/inputs
completo antes de inferencia; continuación no repite un fit completo existente.

Políticas primarias: control152 y variante424, umbral fijo estricto score>0USD.
No selector de umbral ni ganador posthoc; ambos se reportan, con diferencia
pareada. Ninguna rentabilidad o ajusteTRAIN decide si se publica la evaluación:
siempre se informa el resultado de la política fijada, incluidas cero operaciones.

Mismos candidatos, validación temporal, scheduler y contrato económico de la
comparación compacta existente: snapshots causales, targets/stops congelados,
samecontract ask→bid, costes base/adversos, NO_FILL, posición no solapada,
salida por target/stop/cierre de la sesión. No force-first, duración fija ni
filtros adicionales. Cierre de calendario210/390 explícito para features nuevas;
la versión histórica de las griegasTheta y su TTE no se presenta como verificada.

Validación2025:750 ticker-días NYSE, incluidas9medias sesiones. Test desarrollo
2026H1:369 ticker-días,363observables y6missing NO_EVALUABLE. Mismos gates
económicos y de frecuencia diarios de la comparación compacta; los seis días
faltantes no se eliminan ni cuentan como cash aprobado. Se separa economía y
frecuencia observables de cobertura universal. No se afirma promoción aunque
un agregado favorable aparezca en desarrollo visto.

Predicciones de cada día se sellan antes de abrir labels de ese día; antes de
test se congela política/config/modelos/selección fija y evidencia validación.
No se decide ningún cambio por2026. Control reconstruido exactamente desde
scores/modelo congelado, horarios y fuentes con hashes, incluidos cierres cortos.
Auditor independiente given-sealed-predictions verifica IDs, ambos schedulers,
fills/costes, agregados, missingness y bindings. Fit/inferencia requieren revisión
propia; una auditoría económica no se llama refit ni prueba de rentabilidad live.
