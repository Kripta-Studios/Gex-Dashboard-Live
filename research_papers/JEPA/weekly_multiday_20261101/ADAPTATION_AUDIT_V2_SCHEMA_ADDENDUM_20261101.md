# Complemento de compatibilidad de esquema del auditor V2

Antes de fixturesV2 y sin interpretar resultados económicos, la inspección
comparada de interfaces detecta cinco discrepancias descriptivas adicionales
a `_ev_base` y last_entrySep15 del scope fee823ab publicadof782302a.

1. annotate_books V1 asignaba modelo activo a eventos sin candidate_id. El
   productor sellado usa model_id=null en WAIT/NO_OPPORTUNITY sin candidato;
   ENTRY/EXIT requieren la identidad de su candidato. V2 reproduce ese esquema,
   conservando modelo en NO_FILL/CAPITAL_BLOCKED que sí identifican candidato.
2. IDs de candidatos en gate se guardan ordenados en el productor, pero V1
   devolvía orden de los archivos unidos. V2 ordena sólo esa lista metadata;
   no reordena selección, scores o trading para obtener otro resultado.
3. Concentración: el productor define mayor trade por magnitud absoluta del
   neto; V1 usaba máximo neto firmado. V2 reproduce max(abs(net)), conservando
   signo y resta mecánica. No es una selección alternativa ni cambia neto.
4. El helper probabilístico devuelve log_loss y el productor guarda logloss.
   V2 renombra esa clave en la salida combinada, sin conservar una clave extra,
   y usa logloss al calcular diferencias RAW/GUARDED. No cambia el cálculo.
5. El contador guard_diagnostics.rejections del productor cuenta sólo REJECTED;
   V1 incluía también REJECTED_NO_GATE_ROWS. V2 conserva el contador exacto;
   el mapa global proposal_status_counts sigue registrando todos los estados.

Focales: modelo nulo en evento sin candidato y conservado en posición; inputs
desordenados con IDs guardados ordenados; ganancia+100/pérdida−200 identifica
la pérdida como mayor magnitud y deja+100 al restarla. Se añaden a los focales
helper-real ENTRY/EXIT/EVambos/tailH2 anteriores y esquema exacto de logloss.
Los cinco problemas nuevos son
diagnóstico estático; sólo `_ev_base` fue fallo observado del runtime01.

Delta permitido V2: funciones annotate_books, rebuild_isolated_gate_role,
rebuild_continuous_books, extended_book_metrics, combined_probability_ev,
validate_summary y caller dentro numeric_audit_from_sealed_payloads;
constanteLAST_ENTRY, destino02/nombre nuevo. Todos los otros nodos económicos,
scores/splits/inferencia/gates/tolerancias y helpers conservan AST. No tocar
productor ni reentrenar. Los fixtures validan interoperabilidad del auditor,
sin redefinir reglas para aceptar métricas. IntentoV2preparatorio huérfano fue
detenido por su autor y se conserva inválido, no acredita PASS formal.

La primera revisión de este complemento, SHA676d46c6, está preservada en
bfbdc293. Esta revisión ampliada se publica antes de las fixtures finales;
el whitelist AST debe enumerar exactamente las siete funciones indicadas.
