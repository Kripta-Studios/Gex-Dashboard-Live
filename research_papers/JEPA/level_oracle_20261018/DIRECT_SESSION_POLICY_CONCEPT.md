# Actor causal optimizado por sesión: hipótesis posterior, no ejecutada

2026-10-18. Revisión científica de /root/oracle_design_audit favorable a preparar
esta alternativa después de los resultados actuales. No es un cuarto experimento
en marcha ni modifica las tres familias activas. No hay fit, política o resultado
económico de este concepto.

El objetivo sería aprender directamente el resultado de toda la sesión bajo
las decisiones del propio actor. Para un tape histórico de TRAIN, un actor
feedforward causal recibe únicamente features disponibles y el flag h de fill
previo. Produce probabilidades de WAIT y acciones ofrecidas. La DP evalúa esa
distribución, sin maximizar los beneficios futuros ni usar el oracle como policy.

```
V(s,h) = p_WAIT(s,h) V(s+1,h) + sum_a p_a(s,h) Q(s,h,a)
Q_FILLED(s,h,a) = net_a + V(min(exit_a+1,terminal),1)
Q_NO_FILL(s,h,a) = V(s+1,h)
V(terminal,h) = -lambda * (1-h)
```

La esperanza es exacta respecto a la aleatoriedad de las decisiones sobre cada
tape del simulador. No es una esperanza exacta sobre todos los futuros del
mercado, ni corrige sus supuestos de impacto, disponibilidad o ejecución. El
uso de futuros históricos para evaluar consecuencias en TRAIN encaja con el
marco de [MDP con entradas exógenas, Sinclair et al., ICML2023](https://proceedings.mlr.press/v202/sinclair23a.html).

En inferencia sólo se ejecutaría el actor en el instante actual; no se calcula
esta DP con datos futuros. Durante TRAIN, las features de un minuto posterior
se usan únicamente para las decisiones de ese minuto dentro del objetivo.
Compartir pesos y retropropagar sus consecuencias no introduce por sí mismo
features futuras en la decisión anterior. Esta es una conclusión condicional
de diseño, no una validación de un runner todavía inexistente.

Para evitar retener todas las activaciones, la ocupación d(s,h) y los valores
permiten un adjunto exacto de cada logit:

`dJ/dz(s,h,a) = d(s,h) * p(a|s,h) * [Q(s,h,a) - V(s,h)]`.

Se puede recalcular el actor por bloques con los mismos pesos y estado
determinista, aplicando esos adjuntos. Es la estructura del
[gradiente de política, Sutton et al., NeurIPS1999](https://papers.neurips.cc/paper_files/paper/1999/hash/464d828b85b0bed98e80ade0a5c43b0f-Abstract.html),
con Q/V exactos bajo este tape. Antes de datos reales habría que comparar DP,
enumeración de trayectorias, autograd y diferencias finitas en casos pequeños.

Condiciones necesarias para concretar el experimento:

- Usar todo el soporte de acciones, incluidos futuros NO_FILL. El muestreo de
  128acciones/día con IPW no preserva exactamente softmax y ocupaciones.
- Promediar el objetivo por ticker-día. Las ocupaciones ya ponderan ambos h;
  no duplicarlos artificialmente con peso mitad como en regresión supervisada.
- Una puerta WAIT/TRADE separada de la selección de contrato/target evita que
  añadir acciones aumente automáticamente la probabilidad inicial de operar.
  Hay que definir y probar sus gradientes; la fórmula anterior describe la
  parametrización softmax plana.
- Congelar cómo se convierte el actor estocástico en política ejecutable.
  Su esperanza puede mejorar mientras su elección greedy empeora. No presentar
  esperanza de trades>=1 como mínimo diario cumplido.
- La penalización equivale a restar lambda por probabilidad de terminar sin
  fill; nunca se incluye en PnL. Una lambda finita y WAIT con probabilidad
  positiva no garantizan operar todos los días.
- El estado(t,h) sólo basta para consecuencias propias si no existen límites
  de capital/pérdidas, tamaños variables u otra memoria dependiente de acciones.
  Añadirlos exigiría ampliar estado y recurrencia, no reutilizar esta prueba.

La comparación futura necesitaría controlar capacidad, información, calendario,
normalización y scheduler. No se fijan ahora hiperparámetros ni se utiliza un
resultado parcial2025/2026 para escogerlos. La decisión de implementarlo depende
de lo que enseñen las ejecuciones actuales, manteniendo el requisito diario y
las limitaciones del calendario expresamente visibles.
