# Qué enseña el fallo temporal del TCN y qué sigue abierto

23 de octubre de 2026. Revisión documental posterior al cierre `7a2c5abd`.
No se leyeron nuevos outcomes, recalcularon modelos, seleccionaron umbrales ni
reabrieron familias. Las fuentes citadas son informes y contratos ya existentes.

**El modelo con mezcla de filas obtuvo mejor ajuste TRAIN y actividad temporal,
pero no una política diaria rentable.** Esto descarta que esa ejecución concreta
bastara para resolver el objetivo; no demuestra imposibilidad de aprender una
política causal con esta información. La auditoría verifica cálculos y evidencia
sellada, no identifica por sí sola la causa económica del fracaso.

## Actividad, ajuste y pérdidas son hallazgos distintos

| Evidencia cerrada | Interpretación acotada |
|---|---|
| El control FLAGS64 hizo tres operaciones en un solo ticker-día de 2025 con umbral cero; los otros umbrales hicieron cero. En H1 2026 todos sus umbrales hicieron cero. | El control falla por inactividad. Su PnL cero cuando no opera no demuestra una ventaja económica, ni permite distinguir calibración, discriminación y optimización. |
| Row-mixed, a umbral cero, hizo 2.488 operaciones en 2025 y 1.205 en H1, con −138.838,80 y −34.199,00 USD base. Las otras dos variantes también pierden en ambos periodos. | La variante no permanece simplemente inactiva: ejecuta decisiones perdedoras en agregado bajo estos costes. El fallo económico existe además del incumplimiento diario. |
| La variante de umbral cero deja 63/750 días observables sin fill en 2025 y 20/363 en H1; seis días H1 carecen de fuente. Ningún candidato es elegible y la selección es nula. | No corresponde reducir el umbral después de observar el resultado, forzar operaciones ni confundir ausencia de fuente con un día observado sin fill. |

Las cifras y todos los candidatos están en el
[resultado auditado](TCN_ROW_MIXED_CALENDAR_RESULT_20261023.md). QQQ con umbral
cero tiene un neto H1 positivo, ya visible allí, pero no satisface el conjunto de
criterios ni rescata la selección nula. No se deriva de ese desglose una nueva
elección de ticker, umbral o mes.

El R² ponderado TRAIN de la cuarta época pasó de aproximadamente 0,001436 en
[FLAGS64](TCN_FLAGS_V1_RESULT.md) a 0,231789 en
[row-mixed](closure_20261018/03_MODELS_AND_RESULTS.md), conservando muestra,
objetivo y presupuesto según el [diseño](TCN_ROW_MIXED_DESIGN_DRAFT.md). Esa mejora
de ajuste no se tradujo en rentabilidad temporal. El diagnóstico previo de
[gradientes](TCN_GRADIENT_GROUPING_RESULT.md) sólo midió una reducción de
dispersión en 512 filas de 16 días; la
[memorización de 128 filas](TCN_MEMORIZATION_DIAGNOSTIC_RESULT.md) sólo acreditó
capacidad de ajuste de ese bloque. Ninguno era evidencia de generalización;
ambos informes declararon además que no tuvieron auditoría independiente.

## La pérdida por acción no es el objetivo de toda la sesión

El [diagnóstico de optimización](TCN_OPTIMIZATION_DIAGNOSTIC.md) documenta la
pérdida heredada: error cuadrático del neto normalizado por acción más una
auxiliar BCE de la elección privilegiada del DP, con pesos IPW. La ejecución
usa la cabeza económica para tomar el máximo, aplicar un umbral y bloquear
decisiones hasta salir. El objetivo de entrenamiento no optimiza directamente
el ledger bajo las visitas y decisiones de la propia política. IPW corrige el
muestreo declarado; no convierte acciones correlacionadas del mismo día en
experimentos independientes ni reproduce la ocupación de una política.

Hay evidencia previa pertinente, sin atribuirle más alcance:

- El [diagnóstico de máximos](MAX_SCORE_CALIBRATION_RESULT.md) encontró en dos
  **GBT** degradación general de correlación en validación y mayor error medio
  después del argmax en las seis combinaciones modelo/ticker. Respaldó investigar
  calibración condicionada a selección; no midió ese mecanismo en row-mixed ni
  prueba que un offset vaya a reparar su ranking o sus pérdidas.
- El [comportamiento del oracle](ORACLE_BEHAVIOR.md) mostró que entre el 42,2% y
  el 45,8% de sus elecciones no maximiza el beneficio aislado: también importa
  cuándo queda libre la posición. Es evidencia retrospectiva de coordinación
  dentro del motor, no de que una política causal pueda anticiparla.
- La [continuación causal fija](CAUSAL_ROLLOUT_RESULT.md) ya reemplazó la
  continuación clarividente por la de un teacher causal. Su
  [extensión a días cortos](CAUSAL_ROLLOUT_SHORT_SESSION_RESULT.md) consiguió fill
  en los 750 días de 2025 y perdió −42.279,20 USD base. Por tanto, parte del
  problema de continuación y frecuencia ya fue ensayada; no basta renombrarlo.
  Ese resultado cerrado se conserva y no se propone repetirlo.

La diferencia entre objetivos es una razón metodológica para formular hipótesis.
**No demuestra que ese desajuste sea la causa de las pérdidas TCN**, frente a
información insuficiente, generalización temporal, calibración u otros factores.

## Qué pregunta añadiría un actor de sesión

| Línea documentada | Pregunta que aborda | Lo que no garantiza |
|---|---|---|
| [Mensual](MONTHLY_WALK_FORWARD_PLAN.md) | Actualizar el ajuste y sus escalas con pasado reciente, manteniendo el objetivo net por acción. Puede cambiar el ranking al cambiar los modelos. | Que un refit encuentre señal o maximice el resultado de la trayectoria completa. |
| [Calibración OOF](PREQUENTIAL_MAX_CALIBRATION_DESIGN.md) y [replay](OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md) | Corregir el valor del máximo con errores temporalmente fuera de ajuste. El offset conserva el ranking dentro del estado, aunque cambie abstención y estados posteriores visitados. | Reparar discriminación, garantizar un fill diario o sustituir un objetivo de sesión. |
| [Actor exacto de sesión](EXACT_SESSION_ACTOR_SCIENTIFIC_NOTE.md) | Optimizar la esperanza de la sesión bajo las decisiones y ocupaciones del propio actor, en vez de regresión por acción o continuación de un teacher fijo. | Que esa esperanza generalice, que el ledger determinista sea rentable o que se cumpla actividad diaria. |

La nota del actor sí plantea una pregunta distinta de mensual/OOF y de la
mejora de un paso respecto a un teacher fijo. **Sigue siendo una hipótesis no
ejecutada, sin autorización nueva en este documento.** Su exactitud sería
condicional al tape y al simulador exógeno, no una expectativa exacta de mercado.
Exige soporte completo de acciones: el subconjunto IPW anterior no reproduce
exactamente softmax y ocupaciones. Antes de un runner quedarían pendientes las
equivalencias entre enumeración, recurrencia, autograd y gradiente, así como la
regla de extracción de la política ejecutable. Una penalización finita por
terminar sin fill no garantiza operar diariamente y no es PnL. Si capital,
tamaño o límites acumulados influyeran en decisiones, el estado propio tendría
que representar esas dependencias. La nota ya reconoce estas limitaciones.

## Supuestos y frontera de la conclusión

Los [datos y el motor](closure_20261018/02_DATA_ENGINE_ORACLE.md) usan extremos
muestreados del IB, demora de un minuto y la convención documentada de relojes
Greek/underlying. Su equivalencia local no acredita recepción live. La
disponibilidad de OI del cierre previo a las 09:30 sigue siendo un supuesto;
gamma × OI es un proxy sin inventario dealer firmado. Ofrecer acciones cerca de
Fibonacci/walls no demuestra causalidad económica de esos niveles. El auditor
TCN tampoco hizo refit, reinferencia GPU ni reconstrucción raw de cotizaciones.

2025 y 2026 siguen siendo desarrollo visto; un nuevo objetivo no crea un holdout
intacto. El resultado sostiene un fracaso acotado y reproducido, no una prueba
universal de ausencia de edge ni una promesa de que otro algoritmo lo encuentre.
La lectura útil es conservar el fallo y distinguir las preguntas pendientes de
las líneas ya autorizadas. No se fijan aquí modelos, penalizaciones, umbrales,
fechas nuevas, ejecuciones ni promoción.
