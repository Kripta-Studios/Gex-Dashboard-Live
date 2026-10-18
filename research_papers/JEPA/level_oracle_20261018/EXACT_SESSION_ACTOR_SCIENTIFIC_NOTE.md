# Actor causal con objetivo exacto de sesión: propuesta, no experimento

2026-10-18. Nota científica de `/root/oracle_design_audit`. No modifica los
experimentos existentes, implementa un runner ni autoriza un fit. Merece
preparación después de conocer sus resultados; no presupone rentabilidad.

Para un tape de TRAIN fijo, estados flat `(t,h)` y todas las acciones ofrecidas
causalmente, definir una política parametrizada sobre WAIT y las ofertas.
Conservar el mismo coste, demora, contrato, target y stop del motor auditado.
La recurrencia es:

```
Q(t,h,WAIT) = V(t+1,h)
Q(t,h,a NO_FILL) = V(t+1,h)
Q(t,h,a FILLED) = net(a) + V(exit(a)+1,1)
V(t,h) = sum_a pi_theta(a|x_t,h) * Q(t,h,a)
V(t>last_state,h) = -lambda * (1-h)
J(theta) = mean_ticker_days V(first_state,0)
```

Esto integra exactamente las decisiones estocásticas del actor sobre cada
tape; no maximiza outcomes ni imita elecciones privilegiadas del oracle.
Features de instantes futuros sólo alimentan las decisiones de esos instantes
durante TRAIN. La inferencia ejecuta exclusivamente el actor causal actual,
sin consultar esta DP. Compartir parámetros entre decisiones temporales no
introduce por sí mismo filtración. El uso de consecuencias contrafactuales en
entornos con entradas exógenas tiene precedente en
[Sinclair et al., ICML 2023](https://proceedings.mlr.press/v202/sinclair23a.html).

La exactitud es **condicional al tape y al simulador exógeno**: nuestras órdenes
no alteran precios, quotes, señales o fills futuros. El estado propio `(t,h)`
debe contener todo lo que afecta consecuencias posteriores. Capital, tamaños
variables, límites acumulados o memoria dependiente de acciones requerirían
ampliarlo. El gradiente exacto de este simulador no verifica sus supuestos de
ejecución ni elimina incertidumbre fuera de muestra.

## Adjunto y memoria

Sea `d(t,h)` la probabilidad de visitar ese estado desde `(first_state,0)`,
obtenida propagando probabilidades hacia delante por las mismas transiciones.
Para los logits efectivos `z` del softmax:

```
dJ/dz(t,h,a) = d(t,h) * pi(a|t,h) * [Q(t,h,a) - V(t,h)]
```

La expresión es una especialización finita de la estructura del
[gradiente de política de Sutton et al., 1999](https://papers.neurips.cc/paper_files/paper/1999/hash/464d828b85b0bed98e80ade0a5c43b0f-Abstract.html).
Aquí se calculan Q y V por la recurrencia, sin crítico aprendido. Permite guardar
probabilidades/adjuntos y recalcular la red por bloques: aplicar el adjunto
detenido a sus logits reproduce el gradiente de primer orden. No cambiar theta
entre pasadas; usar red determinista o reproducir exactamente su aleatoriedad.
La ocupación ya pondera h: no duplicar estados con pesos mitad del método previo.

Debe incluirse el soporte completo de acciones, también los NO_FILL futuros.
IPW sobre el subconjunto de acciones anterior no recupera exactamente el
softmax ni las ocupaciones. Minibatches uniformes de días completos sí estiman
el gradiente de su media empírica. Normalizar por escala histórica fija cambia
el objetivo a retorno normalizado; no describirlo como dólares totales.

## Fixture matemático mínimo verificado, sin mercado

Dos decisiones abstractas `t=0,1`, lambda=3. En t0, A termina FILLED con +2;
WAIT lleva a t1 con h0. En t1, B termina FILLED con -1; WAIT termina sin fill
con -3. Definir `p=sigmoid(u)=0.4`, `q=sigmoid(v)=0.25` para A y B.

```
V1 = -3 + 2q = -2.5
J  = 2p + (1-p)V1 = -0.7
d(0,0)=1; d(1,0)=1-p=0.6
dJ/du = p(1-p)(2-V1) = 1.08
dJ/dv = (1-p)q(1-q)(-1-(-3)) = 0.225
```

El PnL esperado es +0.65 y P(sin fill)=0.45: `0.65 - 3*0.45 = -0.7`.
Por tanto la penalización no es una comisión ni PnL. Una acción NO_FILL en t0
tendría exactamente Q=V1 y preservaría h, igual que WAIT; nunca permite rescate
de otra acción en ese mismo instante. Estos dos estados son abstractos, no
sustituyen los fixtures de demora física del motor.

Verificación CPU con diferencias centrales, epsilon=1e-5, funciones escalares
de `math`: du=1.0800000000033005; dv=0.22500000000924555; errores<1e-8.
No hubo modelo, import del motor ni lectura de fuentes/outcomes reales.
Antes de implementar un runner harían falta también equivalencia autograd,
enumeración de todas las trayectorias pequeñas y fixtures de reloj/fills.

## Límites que siguen abiertos

- Un softmax plano con N acciones y WAIT tiene probabilidad inicial de operar
  N/(N+1) si todos los logits son iguales. Separar WAIT/TRADE y elección
  condicional puede evitar ese sesgo de cardinalidad; requiere fijar la regla
  determinista de extracción antes de evaluar test.
- Mejor esperanza estocástica no garantiza mejor ledger greedy. Deben medirse
  ambos y seleccionar/congelar exclusivamente con validación. Annealing no
  prueba equivalencia y una expectativa positiva no es evidencia de un ledger
  determinista positivo.
- Lambda finita optimiza PnL menos lambda por probabilidad de ningún fill;
  no impone el requisito del usuario de >=1 fill cada ticker-día. Con logits
  finitos y WAIT siempre disponible queda probabilidad positiva de esperar
  toda la sesión. Número esperado de trades >=1 tampoco satisface esa regla.
  Mantener la comprobación diaria real, sin forzar la primera operación.
- Los días sin fuente permanecen no evaluables, no éxitos ni exclusiones
  nuevas. Exactitud de TRAIN no evita sobreajuste; los resultados actuales y
  2026 visto siguen siendo desarrollo, sin garantía prospectiva.
