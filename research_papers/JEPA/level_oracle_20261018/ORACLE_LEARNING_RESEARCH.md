# Oracle de niveles y aprendizaje causal

Revisión de fuentes primarias: 18 de octubre de 2026. Propuesta técnica; este documento no ejecuta entrenamiento ni acredita rentabilidad. Usa exclusivamente el histórico local para el trabajo posterior.

La dirección útil es separar tres cosas: cuánto habría ganado un operador que conoce el futuro bajo nuestras restricciones, qué decisiones se pueden anticipar usando el pasado y cuánto gana la política causal completa después de costes. La imitación de un oracle puede ayudar a aprender patrones y decisiones; una gran rentabilidad del oracle por sí sola no demuestra que esas decisiones sean predecibles.

## Qué aporta la literatura

| Fuente primaria | Aplicación y límite en este proyecto |
|---|---|
| [Fang et al., Imitation from Learning-based Oracle for Universal Order Execution, 2021](https://drl4ir.github.io/paper3.pdf) | Precedente financiero directo de profesor con información perfecta y alumno limitado al pasado. Resuelve la ejecución de una orden ya decidida; no demuestra selección rentable de entradas direccionales 0DTE. |
| [Chen et al., Learning by Cheating, CoRL 2019](https://arxiv.org/abs/1912.12294) | Profesor privilegiado seguido de alumno sensorial. El privilegio es el estado del entorno de conducción; no equivale a conocer la realización futura de un mercado. |
| [Cai et al., Provable Partially Observable RL with Privileged Information, NeurIPS 2024](https://arxiv.org/abs/2412.00985) | Analiza dificultades de destilar expertos privilegiados y condiciones necesarias para sus garantías. Refuerza que la información del profesor puede no ser recuperable por el alumno. |
| [Ross et al., DAgger, AISTATS 2011](https://proceedings.mlr.press/v15/ross11a) | Agregar estados visitados por el alumno reduce el desajuste frente a entrenar solo en trayectorias del profesor. Aquí cambian inventario, precio de entrada y objetivo aunque el tape de mercado sea exógeno. |
| [Kostrikov et al., IQL, 2021](https://arxiv.org/abs/2110.06169) y [Kumar et al., CQL, NeurIPS 2020](https://arxiv.org/abs/2006.04779) | Alternativas para aprender políticas desde transiciones offline: IQL evita consultar acciones ausentes y CQL penaliza valores excesivos fuera del soporte. Sus resultados no constituyen evidencia de edge financiero. |
| [Park et al., Flow Q-Learning, ICML 2025](https://arxiv.org/abs/2502.02538) | Referencia moderna de offline RL con políticas expresivas y buenos resultados en 73 tareas OGBench/D4RL. Para un conjunto pequeño de acciones discretas añade complejidad poco justificada inicialmente. |

Es una selección práctica de métodos pertinentes, no una afirmación de que exista un SOTA demostrado para estos datos de SPY/QQQ/SPXW.

## No enseñar el máximo futuro como valor alcanzable

Si `H` es el historial observable y `R(a, ω)` el retorno realizado de la acción `a` en el futuro `ω`, entonces:

`E[max_a R(a, ω) | H] >= max_a E[R(a, ω) | H]`.

Ejemplo propio: elegir retrospectivamente la cara ganadora de una moneda permite ganar siempre; predecirla desde un historial sin información no produce beneficio esperado antes de costes. Una regresión del beneficio máximo retrospectivo puede predecir perfectamente que hay grandes oportunidades y seguir siendo incapaz de elegir la correcta.

Un oracle que relaja la obligación de decidir sin conocer el futuro sirve como cota superior **dentro del mismo universo de acciones y ejecución**. Esta interpretación corresponde a las [relajaciones de información de Brown, Smith y Sun, Operations Research 2010](https://doi.org/10.1287/opre.1090.0796). No es una cota para toda estrategia imaginable. [Double Q-learning](https://arxiv.org/abs/1509.06461) reduce otro problema, la sobreestimación al maximizar estimaciones ruidosas; no elimina el privilegio de conocer el futuro.

Recomendación propia: guardar por separado el `oracle_value`, la acción ganadora retrospectiva y **los retornos de todas las alternativas causales evaluables**. Entrenar el estimador económico con estos últimos. Usar la imitación como objetivo auxiliar contrastable; nunca identificar automáticamente el valor del profesor con la expectativa del alumno.

## Acciones de entrada, espera y salida por niveles

El estado causal contiene el prefijo de precios, griegas y zonas disponibles, máscaras de datos, reloj, contrato e inventario. Durante una operación incorpora entrada, tiempo transcurrido, objetivo, invalidación y valoración actual observable. Las coordenadas y fuerza de niveles futuros nunca forman parte del estado de entrada.

- Estando fuera: `WAIT` o `ENTER(side, contrato, objetivo, invalidación)`. El objetivo puede ser un nivel lejano. Cruzar niveles intermedios no obliga a salir.
- Estando dentro: `HOLD` o `EXIT`; una variante posterior puede permitir `RETARGET` como decisión causal explícita. Para una primera versión interpretable, congelar las coordenadas del objetivo y la invalidación al entrar.
- Salida por llegada a la zona objetivo, invalidación o liquidación de fin de sesión. No imponer un hold de 30 minutos. Si se permite una salida discrecional aprendida, mantener los niveles y su evolución en el estado y declarar esa variante por separado.

Una zona aproximada puede definirse por anchura relativa al IB/volatilidad observable. Debe conservarse su regla durante la evaluación. Los máximos/mínimos intrabar no observados no permiten inventar el orden de contacto: con spot muestreado se evalúan contactos muestreados y la ejecución ocurre en el siguiente instante permitido. Un salto que cruza una zona no garantiza haber negociado una opción al precio ideal del nivel.

El motor usa ask de entrada y bid de salida del **mismo contrato**, comisiones, slippage, retraso y reglas explícitas de ausencia de cotización. Alcanzar un objetivo de spot puede perder dinero en la opción. El oracle y el alumno deben compartir este motor, no solo la trayectoria de spot. La disponibilidad retrospectiva de una cotización no puede convertirse en una feature ni seleccionar otra acción al descubrir un fill ausente.

## Construcción recomendada

1. **Oracle diagnóstico mediante programación dinámica.** Enumerar únicamente objetivos/invalidaciones disponibles en cada decisión y transiciones permitidas, incluida espera; optimizar el PnL neto con no solapamiento y liquidación final. El futuro interviene en el optimizador y las etiquetas. Conservar también operaciones perdedoras y alternativas no elegidas, no solo los ganadores. La programación dinámica evita aprender un modelo de mercado para este techo retrospectivo.
2. **Primer alumno de políticas completas de objetivo/stop.** Para cada entrada candidata, etiquetar el retorno que produce ejecutar su regla fija hasta objetivo, invalidación o cierre. Ajustar retorno esperado y, si interesa, distribución/riesgo condicionado al prefijo. Elegir entre alternativas por valor estimado neto. La política de esperar y reevaluar necesita reproducción cronológica: el cero representa quedarse en efectivo, no el valor exacto de toda espera futura.
3. **Alumno secuencial de espera/salida.** Construir transiciones de estados planos y abiertos, incluidos estados visitados por el alumno en sesiones de entrenamiento. Para un crítico causal usar objetivos Bellman `r + gamma * Q_target(H_siguiente, a_elegida_por_modelo)`, con continuación seleccionada por una política causal y redes/estimadores separados. No sustituir esa continuación por el mejor beneficio futuro del oracle. También es viable evaluar continuaciones de una política congelada mediante Monte Carlo. Hacer ajuste cruzado por sesiones para reducir el uso circular de la misma trayectoria al construir y ajustar estos objetivos.
4. **Imitación auxiliar.** Preentrenar clasificación de acciones/objetivos del oracle y después comparar con el alumno económico sin esa pérdida. Etiquetas blandas entre acciones casi equivalentes pueden reducir empates arbitrarios. No sustituir retornos por recompensas positivas recortadas ni equilibrar clases sin corregir cómo cambia la distribución de decisiones. Adaptar DAgger únicamente a sesiones de entrenamiento; mejora cobertura de estados, no vuelve predecible la información futura.

La enumeración de alternativas es plausible para un contrato pequeño bajo el supuesto de no impacto propio en el tape. No permite observar profundidad, fills de órdenes límite ni impacto inexistentes en las fuentes. Para acciones discretas con transiciones enumerables, GBT/fitted Q o una TCN resultan más sencillos de inspeccionar que offline RL generativo. IQL/CQL quedan como comparación si la cobertura de acciones/transiciones es realmente parcial.

## Representación temporal y equipo local

Equipo observado mediante consultas locales: Ryzen 9 9955HX, 16 núcleos/32 hilos; RAM física 31,18 GiB; RTX 5070 Ti Laptop, 12.227 MiB reportados por `nvidia-smi`. No se ha verificado aquí la compatibilidad CUDA del entorno Python ni medido entrenamiento.

Propuesta inicial propia: GBT sobre contexto y descriptores de secuencia como referencia; TCN causal pequeña con 4–6 bloques dilatados y 64 canales, dos ramas 5m/15m, máscara de observación y representación de campos suaves de niveles. Preserva aproximación, velocidad de llegada, rechazo, permanencia y migración de walls. La [evaluación original de TCN](https://arxiv.org/abs/1803.01271) fundamenta el encoder de convoluciones causales; no demuestra rendimiento financiero.

Como comparación GPU, transformer de 2–4 bloques, dimensión 128, con patches formados solo dentro del prefijo observable, inspirado en [PatchTST](https://arxiv.org/abs/2211.14730). El encoder completo del prefijo puede atender dentro de ese prefijo; ningún patch ni normalización debe incluir el futuro de la decisión. Entrenar por minibatches y sesiones para evitar cargar todas las cadenas de opciones simultáneamente. Estos tamaños son propuestas viables para probar, no mediciones de memoria o velocidad.

[Decision Transformer](https://arxiv.org/abs/2106.01345) es una comparación posterior: el retorno deseado es una instrucción, no información observada. Darle el retorno futuro realizado o exigirle el retorno del oracle en evaluación produce fuga o condicionamiento fuera de distribución. Una búsqueda tipo AlphaZero solo sería causal si ramifica sobre un modelo predictivo aprendido con datos pasados; ramificar sobre el futuro realizado reproduce el oracle, y no añade poder predictivo.

## Evidencia que distinguiría aprendizaje de clarividencia

Evaluar la política completa en sesiones cronológicas posteriores a su ajuste, con inventario propio y sin llamar al oracle durante inferencia. Separar días entre entrenamiento/selección/evaluación; no repartir ventanas solapadas del mismo día entre conjuntos. Ajustar escaladores y políticas solo con el bloque pasado. Los periodos ya explorados siguen siendo desarrollo, aunque se cambie la arquitectura.

Comparaciones mínimas: efectivo, alumno económico sin imitación, alumno con imitación y oracle; añadir ablación de niveles y control de niveles desplazados para saber qué aporta su ubicación. Publicar todos los tickers/meses, cobertura, costes, drawdown y sensibilidad al reloj, no solo precisión contra el profesor. La fracción del techo capturada es descriptiva; el criterio económico es el PnL neto del alumno. Repetir hasta encontrar un resultado positivo en el mismo test no constituye validación nueva. La siguiente iteración debe registrar lo aprendido y reservar una evaluación posterior antes de volver a seleccionar.
