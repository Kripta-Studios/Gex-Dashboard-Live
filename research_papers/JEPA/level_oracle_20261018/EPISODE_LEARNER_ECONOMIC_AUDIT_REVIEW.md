# Auditoría independiente del learner con episodios

Estado: `PASS_INDEPENDENT_EPISODE_LEARNER_ECONOMIC_AUDIT`. Artefacto:
`D:/GexResearchArtifacts/level_oracle_20261018/episode_learners_v1_economic_audit/audit.json`,
SHA256 `260d08506210e8ff40cd6b3e1dec123c4efba9a943e2dd5bbe81fd8e67190d4a`.

El auditor no importó el scheduler, las métricas económicas ni el motor productor.
Reconstruyó la matriz de entrenamiento270.377×2.024: las1.954 columnas originales
son bit a bit idénticas y las70 columnas de episodios coinciden exactamente con
el join causal por `state_i`. El alcance económico parte de las predicciones ya
selladas; no reproduce el ajuste ni la inferencia de LightGBM.

Se verificaron4.573.153 scores en741 días de validación y2.406.690 en363 días
test observables. Para las seis políticas se reconstruyeron ranking, empate por
menor `action_id`, umbral estricto, WAIT, NO_FILL+1 y fill hasta `exit_i+1`, además
de attempts, ledger, calendarios diarios, métricas mensuales, costes base/adverso,
selección y gates. Validación produjo12.088 fills; test7.006 fills y un intento
NO_FILL adicional.

Ninguna política cumplió al menos un fill por ticker-día disponible en2025. El
freeze correcto es `FAIL_NO_DAILY_COMPLIANT_POLICY`, `selected_policy=null` y
`approved=false`. `gbt_net__10` queda sólo como diagnóstico pretest, con score
normalizado de selección −204,283; no es una política aprobada.

En2026 el diagnóstico tuvo109 de363 ticker-días observables sin fill, más seis
fuentes `NO_EVALUABLE`; el requisito diario y la cobertura fallan. SPXW perdió
USD20.729,80 base, SPY perdió USD1.818,40 y QQQ ganó USD1.271,80, pero QQQ tampoco
alcanzó PF1,2 ni los demás gates conjuntos. `combined_gate_passes=false`,
`technical_ready=false` y `promotion_approved=false`.

La continuación técnica de paths quedó ligada a su script, repair record,
completion y runtime. Conservó el modelo y declaró cero refits. El auditor
verificó esos hashes y el cierre científico original; la reparación no cambia
features, targets, política ni economía.

Todo2026 ya es desarrollo visto. Este PASS acredita identidad de representación
y ejecución económica dadas las predicciones; no acredita generalización futura,
recepción live, entrenamiento independiente ni rentabilidad operable.
