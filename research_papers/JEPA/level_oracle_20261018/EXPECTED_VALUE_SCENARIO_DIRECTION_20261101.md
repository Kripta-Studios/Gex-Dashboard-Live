# Dirección de investigación: escenarios, valor esperado y abstención

El 1 de noviembre de 2026 el usuario propone centrar la investigación en
«encontrar expected value y poder definir probabilidades de escenarios en base
a los datos presentes, y operar en base a ello». Al aclarar el requisito de
actividad para la siguiente etapa, elige expresamente **«Permitir días sin operar»**.

Esta instrucción actualiza la siguiente etapa del goal. WAIT y días disponibles
completos sin fills serán decisiones legítimas; se elimina para esa etapa el
requisito de al menos un fill por ticker y día y no se introduce una penalización
equivalente por abstenerse. Los días ausentes siguen siendo NO_EVALUABLE.
Una política que siempre espera no demuestra rentabilidad ni satisface por sí
sola el objetivo de encontrar una ventaja económica operable.

El OOF iniciado hoy conserva íntegros su protocolo, costes y criterios previos.
Su cierre y auditoría FULL_H1 siguen pendientes. No se recalifican experimentos
cerrados como aprobados por cambiar ahora el requisito. Esta nota registra
dirección y restricciones, no un contrato de entrenamiento ni un resultado nuevo.

## Qué cambia respecto a los modelos existentes

Los modelos actuales ya incluyen regresión de retorno neto. El cambio propuesto
consiste en representar los resultados posibles y su incertidumbre de forma
explícita, evaluar sus probabilidades y derivar una decisión económica. Estimar
esas probabilidades sigue siendo una tarea predictiva; no elimina la necesidad
de señal informativa, calibración temporal y evaluación fuera del ajuste.

Para información causal X_t y acción ofrecida a, estudiar:

`p_s = P(S=s | X_t,a)`

`mu_s = E[R_neto | S=s,X_t,a]`

`EV_neto(X_t,a) = sum_s p_s * mu_s`

Calcularlo separadamente con costes base y adversos. Las probabilidades suman
uno y los escenarios son excluyentes. El retorno dentro de TARGET/STOP/EOD
también varía: no sustituirlo por un premio fijo supuesto. Cuando los targets
son net_base/net_adverse, los costes ya están incluidos y no se cobran otra vez.
Una mayor probabilidad de TARGET o una mayor accuracy no basta para decidir.

La distribución de retornos contiene información que su media no conserva;
permite estudiar colas y magnitudes de pérdida además de EV. Es una motivación
metodológica, no una garantía de mejora financiera ni una elección automática
de RL. Véanse [Bellemare, Dabney y Munos, 2017](https://proceedings.mlr.press/v70/bellemare17a.html)
y la [introducción de Distributional Reinforcement Learning](https://www.distributional-rl.org/contents/chapter1).

## Soporte ya definido en el motor

Lectura estática de `level_engine.py`, `session_clock.py`, `FEATURES.md`,
`features.py`, `causal_rollout.py` y `AGENTIC_FEASIBILITY.md`, sin leer nuevos
outcomes. La nota de factibilidad ya contemplaba eventos y distribución económica;
no se presenta esa preparación histórica como un modelo ahora entrenado.

| Escenario de acción | Semántica actual |
| --- | --- |
| NO_FILL | Quote de entrada inválida; no hay fill, neto0 y avance al minuto siguiente. |
| TARGET | Primer snapshot válido activa target; salida posterior del mismo contrato. |
| STOP | Primer snapshot válido activa stop; tiene prioridad si coincide con target en ese snapshot. |
| EOD | No hay trigger previo; salida en el cierre de liquidación definido por SessionClock. |

`status` distingue FILLED/NO_FILL; `reason` contiene NO_FILL/TARGET/STOP/EOD.
`trigger_i`, `exit_i`, `hold_minutes`, `missing_exit`, `missing_spot_count`,
`entry_ask`, `exit_bid`, `net_base` y `net_adverse` permiten caracterizar resultados.
Son etiquetas o diagnósticos posteriores, nunca features disponibles al decidir.
TARGET no garantiza neto positivo: el precio de la opción, spread y salida
posterior siguen determinando el resultado. Una quote de salida ausente conserva
FILLED y la liquidación conservadora a cero; no se convierte en NO_FILL.

Los eventos corresponden al motor de snapshots de un minuto, no a una secuencia
intraminuto reconstruida. Se conservan prioridad STOP, latencia, costes,
liquidación y calendario full/short. No se inventan toques entre muestras.

## WAIT y valor de esperar

WAIT es una decisión de la política, no una quinta etiqueta de acción ejecutada.
Tiene retorno inmediato cero y avanza t+1. NO_FILL también avanza t+1 sin permitir
rescatar otra oferta del mismo estado. FILLED bloquea hasta exit_i+1.

En un primer control de EV por operación, WAIT es la alternativa de retorno
inmediato cero. Eso no significa que el valor de esperar durante toda la sesión
sea cero: conserva oportunidades futuras. Una acción de EV positivo puede
impedir otra mejor. Una futura política secuencial deberá estimar continuaciones
causalmente, sin introducir V-oracle clarividente en inferencia. Primero se
definirá un control simple comparable; no se fija aquí arquitectura o algoritmo.

## Fronteras de la futura prueba

1. Admitir soporte e identidad de todas las ofertas, con joins1:1 y orden
   explícito. Las muestras mensuales o sólo trades elegidos no sustituyen
   automáticamente ese universo. IDs son claves, no features.
2. Usar únicamente información disponible al decidir: features y máscaras
   causales, `bar_end_i < state_i`; preservar máscaras fraccionales e historia
   válida. No entrar ask real de entrada futura, motivos, duración, salida,
   retornos o elección del oracle como inputs.
3. Definir antes del fit las clases, objetivos probabilísticos y económicos,
   calibración, regla de decisión/abstención, riesgos, splits y presupuesto.
   Una regla de puntuación propia permite evaluar pronósticos probabilísticos;
   esa evaluación no sustituye el replay económico. Referencia metodológica:
   [Gneiting y Raftery, 2007](https://doi.org/10.1198/016214506000001437).
4. Comparar retorno directo y escenarios/distribución bajo la misma información,
   capacidad y presupuesto que se predeclaren, incluyendo CASH. No asumir que
   añadir cabezas probabilísticas crea señal o supera al control.
5. Evaluar todas las ofertas y por separado las seleccionadas; agrupar la
   incertidumbre por sesiones/bloques, dado que acciones del mismo día están
   correlacionadas. Conservar pérdidas, abstención, ambos costes y todos los
   meses/tickers. No confundir calibración de probabilidades con calibración de EV.
6. Completar primero OOF y su auditoría. Después preparar el contrato de la
   siguiente familia con esta abstención autorizada. No se ha fijado ni ejecutado
   un nuevo fit, arquitectura, threshold o evaluación económica.

2025/2026 siguen SEEN_DEVELOPMENT. La nueva orientación no recupera un holdout
intacto ni acredita recepción live. Sólo datos locales existentes; producción,
API, bróker y VPS permanecen fuera del alcance. El goal continúa activo.
