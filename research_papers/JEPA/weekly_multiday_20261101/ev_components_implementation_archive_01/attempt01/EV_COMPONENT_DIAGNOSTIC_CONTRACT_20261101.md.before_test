# Diagnóstico del error de valor esperado: contrato previo

El turno anterior produjo progreso verificable: comparación mensual/semanal
cerrada, reconstrucción independiente PASS y criterio económico mensual FAIL
en las cinco políticas. Productor, auditores, modelos y ledgers permanecen
inmutables. Este diagnóstico responde a la investigación autorizada sobre EV
y estabilidad; no abre un entrenamiento, una política o una optimización.

## Autoridad y alcance

Autoridades locales D:/GexResearchArtifacts/weekly_multiday_20261101:

- h2_context_adaptation_01/manifest.json:
  e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23.
- h2_context_adaptation_audit_04/audit.json:
  9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a.
- h2_context_adaptation_audit_observer_04/exit.json:
  5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420,
  exit0 retenido. Cierre publicado b6dad71633b3dbec2a44dcd46111372d61659991.

Los pins exactos de payloads se obtienen del manifiesto sellado anterior,
limitados a una lista explícita: candidates.jsonl de h2_dataset_v2_01,
h2_dataset_v2_extension_2026q3_partial_01 y h2_boundary_bridge_01; scores,
states, summary y los cinco ledgers adverse de h2_context_adaptation_01;
model.json/conditional_means.json de h2_ev_v2_01 y
context182_calibration.json de h2_context_model_comparison_01. No se siguen
source_pins hacia D:/ThetaData, no se abren features raw/contexto ni modelos
para inferencia nueva. Manifest/audit/exit externos y contrato se rehashean.
El binding futuro fija code/tests/review y este contrato antes del run único.

Universo: 3240 candidatos originales con IDs únicos; diagnóstico de los
3060 scores ya emitidos =612 candidatos comunes por cinco políticas. Los
42 states adaptativos se usan por model_id activo guardado; el frozen se
reconstruye sólo con prior/calibración/medias sellados, sin refit/inferencia.
Las cinco políticas se conservan: FROZEN_CONTEXT182, MONTHLY_RAW, WEEKLY_RAW,
MONTHLY_GUARDED, WEEKLY_GUARDED. Coste adverse exclusivamente, porque es el
criterio principal ya establecido; los resultados base existentes no cambian.
Cada score pertenece a entrada20260102..20260915 y el estado adaptativo tiene
creation_date/asof no posterior al inicio D00 de esa entrada. Conservar
label_available_at y exigir que esté disponible a más tardar en el cutoff final
2026-09-17T10:35 America/New_York: NO_FILL en su entrada, otros en su salida.
La etiqueta H2 es posterior al score y se usa aquí retrospectivamente; no se
exige que sea conocida al decidir ni se vuelve a decidir con ella. Madurez
de TRAIN/CAL e inferencia causal pertenecen a la auditoría upstream cerrada.

## Identidad algebraica y unidades

Para cada candidato i y estado activo s:
A_i=decision_ask_i*100; m_k=mean_y adverso de ticker:right y clase k en s;
p=p_cal; q=p_model; r=prior; alpha=calibration.selected_alpha;
c=scenario observado o conservador; z=one_hot(c); N=net_adverse por contrato.

```text
p = (1-alpha)*q + alpha*r
EV = A * sum_k(p_k*m_k)
V_clase_realizada = A*m_c
C_prob = EV - V_clase_realizada
C_payoff = V_clase_realizada - N
E = EV - N = C_prob + C_payoff
C_model = A*sum_k(q_k*m_k) - V_clase_realizada
C_cal = A*sum_k((p_k-q_k)*m_k)
C_prob = C_model + C_cal
```

Guardar además cinco contribuciones A*(p_k-z_k)*m_k, soporte TRAIN n_k,
medias/prior/alpha, flags y las identidades residuales. USD por contrato;
n_k significa cell_n de esa célula ticker:right/clase, no soporte global.
no restar comisiones otra vez. No usar entry_debit o entry_ask como escala.
Verificar probabilidades finitas/longitud5/suma1, alpha en[0,1], medias finitas,
coherencia de IDs/fechas/ticker/lado/clase/flags/estado y EV guardado. Tolerancia
absoluta predeclarada 1e-8 USD para identidades por fila, 1e-10 probabilidades;
agregaciones y reconciliación de libro 1e-6 USD. No tolerancia de selección.
Sumas con math.fsum y miembros ordenados canónicamente; IDs, pertenencia,
enums, cantidades y selección tienen igualdad exacta.

V_clase_realizada usa información posterior únicamente para diagnóstico.
No es un oracle de trading, una señal operable ni prueba de rentabilidad con
probabilidades perfectas. C_prob depende también de las medias estimadas;
C_payoff incluye variación individual, heterogeneidad y error de esas medias.
No atribuir causalidad pura ni declarar causas estadísticas identificadas.
Sólo componentes firmados son aditivos; sus MAE no se suman a MAE(E).

## Ejecución, cotas y grupos completos

NO_FILL del candidato es clase0/net0, sin operación; NO_FILL del ledger es
una decisión de ejecución/riesgo y puede acompañar a un candidato con payoff
potencial distinto de cero. CAPITAL_BLOCKED también conserva payoff potencial,
no PnL ejecutado. WAIT/NO_OPPORTUNITY sin candidate_id sólo aportan conteos de
eventos/razones, nunca etiquetas inventadas. Entrada y salida se unen 1:1 por
candidate_id/model_id/quantity; no múltiples decisiones por candidato/política.

MISSING_EXIT_SOURCE/QUOTE llevan clase1 y net conservador con bid0, no una
pérdida observada. Publicar conservative_all y without_lower_bounds (esta
segunda conserva NO_FILL); la identidad en cotas compara con el proxy. El error
firmado es cota superior del error real, pero su valor absoluto no es una cota.

Tres universos fijos por política: ALL (612); SELECTED (IDs de ENTRY, NO_FILL,
CAPITAL_BLOCKED); FILLED (IDs de ENTRY/EXIT). Validar SELECTED/FILLED contra
summary sellado. Mismos universos en ambas vistas de cotas; no rescatar ninguna.

Particiones separadas, no producto cartesiano entre ellas: TOTAL(1),
ENTRY_MONTH(enero–septiembre,9), ENTRY_BLOCK(H1 y Q3 parcial,2), SCENARIO(0..4,5),
STATUS(NO_FILL/OBSERVED_EXIT/MISSING_EXIT_QUOTE/MISSING_EXIT_SOURCE,4),
TICKER_RIGHT(SPY/QQQ/SPXW por CALL/PUT,6). Emitir todas las celdas, incluyendo
vacías: 27×5políticas×3universos×2vistas=810. Meses por entrada para diagnóstico;
no confundir con el criterio económico mensual por salida. Septiembre parcial.

Cada celda: n, lower_bound_n, sum/mean EV,N,E,C_prob,C_payoff,C_model,C_cal;
MAE/RMSE(E), mean_abs(C_prob/C_payoff), sum de cinco contribuciones, soporte
TRAIN mínimo/promedio por clase y max_abs_residual. Vacíos n0/sumas0/mediasnull.
Añadir logloss/Brier para reconciliar TOTAL ALL/SELECTED con summary; no buscar
bins, umbrales, ventanas ni significancia estadística. Para FILLED añadir
sum(quantity*EV), sum(quantity*N) y net de EXIT, separados de promedios por
contrato y de no ejecutados. Reconciliar con el libro adverse completo; no
reinterpretar sum(EV) de candidatos como beneficio de cartera.
Cada familia ENTRY_MONTH/ENTRY_BLOCK/SCENARIO/STATUS/TICKER_RIGHT particiona
TOTAL de forma exhaustiva y disjunta: unión exacta, conteos y sumas aditivas
reconciliados. Las cinco sumas de contribuciones suman sum(C_prob). Medias,
MAE/RMSE, mínimos y promedios de soporte se recomputan desde miembros; no se
suman como métricas aditivas. Soporte mínimo/promedio de celdas vacías es null.

## Implementación y cierre

Código nuevo diagnose_weekly_ev_components.py, tests sintéticos de identidad,
calibración, escala, cotas, no-fill candidato/ledger, joins/duplicados y celdas
vacías. Publicar contrato revisado antes de fixtures; código/tests/evidencia
y binding revisados/publicados antes de un único runtime. Gate oficial
RAM y free_commit>=2e9, CPU0/un hilo, proceso oculto y exit por handle retenido.
No acceder a API/bróker ni modificar producción. Sin refit/replay/inferencia.

Raíz nueva ev_components_diagnostic_01 y observer separado bajo el mismo BASE.
Guardar filas3060, agregados810, conteos/reconciliaciones, informe y manifest
con pins antes/después. Revisor independiente reconstruirá las identidades
y agregados desde entradas selladas, sin importar funciones de agregación del
productor. Un fallo se preserva y no autoriza retry automático o overwrite.

Informe compara las cinco políticas y H1/Q3, los tres universos, ambas vistas,
clases/status/lados/meses completos; distingue evidencia, descripción e
hipótesis. No selección, nuevos gates o rescate por ticker. El requisito8/8
mensual permanece fallido e intacto. Todo es SEEN_DEVELOPMENT; el goal general
sigue activo, technical_ready=false y promotion_approved=false.
