# Revisión científica del contrato H2

Revisor independiente `/root/review_weekly_source_pilot`, sólo lectura, sin
outcomes ni fuentes raw. Dictamen final `CLEAR / ship` el 1 de noviembre de 2026.
Primer contrato corregido SHA256:
`9459feaed8a819a53c2e430d8e223884c82d35dbb2ec00bc9a59246599d39ae5`.

Contrato vigente tras la inspección inicial del evaluador:
`245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5`.
La enmienda fija libros TRAIN/CAL/EVAL independientes; EVAL empieza con 100.000
USD sin heredar posiciones o saldos retrospectivos. El mismo revisor confirmó
coherencia de esta enmienda y CLEAR en su revisión final del builder. No cambia
features, etiquetas, selección o costes del dataset.

Primera versión ee72ad37 recibió FIX_FIRST por dos puntos materiales: excluir
salidas ausentes del ajuste de EV omitía su riesgo; y confundir falta de capital
con NO_FILL contaminaba la clase probabilística. Se resolvieron antes de outcomes:
cotas conservadoras entran con flag en TRAIN/CAL/EVAL y métricas observadas aparte;
CAPITAL_BLOCKED queda sólo en replay, con ecuaciones explícitas de cash, reserva
y equity a coste. El EV se interpreta sobre la contabilidad conservadora, no
como un precio/retorno observado cuando falta salida.

No quedan blockers causales o contables del diseño. No es review de código,
auditoría de dataset, ajuste de modelo ni resultado de rentabilidad. El piloto
fuente cerró por separado; implementación, pruebas y revisión siguen pendientes
antes de un único runtime económico.

Documentación técnica primaria consultada por root para la implementación:
[LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html),
[SimpleImputer](https://scikit-learn.org/stable/modules/generated/sklearn.impute.SimpleImputer.html),
[Arrow unique](https://arrow.apache.org/docs/python/generated/pyarrow.compute.unique.html).
Versiones locales observadas por metadata: sklearn1.8.0, numpy2.3.5, scipy1.17.0,
pyarrow23.0.1; la documentación estable consultada no sustituye esas versiones.
