# Calibración global frente a selección por máximo — diagnóstico fijo

Sólo datos vistos, sin fits, inferencia nueva, bins, sweeps, thresholds nuevos o
modificación de políticas. Reutilizar exactamente TRAIN96 y VAL741 del diagnóstico
oracle_model_diagnostic_v1, sus modelos control/episode y scores sellados.
TRAIN conserva exposición al ajuste; VAL está fuera del ajuste pero es desarrollo.

Tres cohortes por modelo, ticker y periodo:
1. Todas las acciones ofrecidas causalmente, sin filtrar por resultado o fill.
2. Una acción argmax-score por cada estado con candidatos, ANTES del umbral y
   sin aplicar disponibilidad por posición. Empate por menor action_id. Se incluye
   el máximo aunque sea negativo. No se ofrecen estados inexistentes ni WAIT falso.
3. Trades realmente ejecutados: model_free & model_filled de la trayectoria ya
   sellada. Esta cohorte condiciona la ejecución observada; no es una política nueva.

Labels NO_FILL aportan neto cero a las cohortes1/2. No usar fill futuro para
seleccionar argmax, saltar a otra acción o eliminar candidatos. Verificar IDs
únicos, alineación exacta de scores/action_ids y join labels uno-a-uno. En la
cohorte3 verificar también state_i, status FILLED y score/net contra la traza.

Ponderación: cada día tiene el mismo peso; dentro del día, igual peso por acción
en cohorte1, por estado en cohorte2, por trade ejecutado en cohorte3. Una jornada
sin unidades tiene media indefinida: se publica su conteo y no se inventa una
predicción de cero. Los momentos agregados normalizan entre días con unidades;
se reportan todos los días esperados y días vacíos para hacer visible ese alcance.

Estadísticos fijos: media predicha USD, neto real USD, error pred−real, MAE,
RMSE y correlación ponderada de Pearson (indefinida si varianza cero). Se calculan
desde momentos por día, no promediando correlaciones diarias. Counts de unidades,
FILLED/NO_FILL y días sin unidades acompañan las métricas. No intervalos o bins.

Contrastes descriptivos fijos: argmax menos todasacciones y ejecutados menosargmax,
usando sólo los días con ambas cohortes definidas para el contraste. Reportar
cambios de score medio, neto medio, error medio, MAE y media de error²; no elegir
contraste según signo. Estos contrastes no tienen interpretación causal automática.

Fixtures previos: IDs/estados desalineados y duplicados rechazan; argmax no usa
fill ni umbral, empate estable; NO_FILL neto0; pesos diarios independientes del
número de acciones y correlación por momentos; traza ejecutada exacta.

Publicar código/spec antes de ejecutar. Root nuevo max_score_calibration_diagnostic_v1;
hashes de inputs, identidad de selección anterior, código/spec y outputs; rehash
final. Reporte separado. Causas compatibles incluyen error general de calibración,
error condicionado al argmax, cambios de distribución/composición y generalización;
ninguna queda demostrada causalmente por esta observación.
