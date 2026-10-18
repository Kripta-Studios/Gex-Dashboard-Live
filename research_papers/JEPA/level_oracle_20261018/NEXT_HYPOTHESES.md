# Siguiente hipótesis: memoria causal de interacción con una zona

Estado: **PROPUESTA NO ACTIVA**. Revisión estática del código del 18 de octubre de 2026; sin leer modelos, predicciones, métricas ni nuevos valores de mercado. No modifica los tres aprendices fijados, su protocolo ni sus fuentes. Su eventual fracaso aún no se presupone. La propuesta se formula por propiedades de la representación, no para ajustar resultados observados.

La hipótesis concreta es que el estado de una interacción —llegada rápida o lenta, primer contacto, rechazo completado, permanencia, penetración y retorno— puede ser más fácil de aprender si se representa explícitamente en coordenadas de una zona persistente. Se puede contrastar con un único cambio de representación y el mismo alumno de retorno directo; no hace falta comenzar otra búsqueda de arquitecturas.

## Qué contiene realmente la representación actual

En [features.py](features.py), `BASE_NAMES` tiene 81 canales: 13 de reloj/IB/spot y cambios, 32 de contexto actual y 36 de top-3 walls. Hay 20 tokens de 45 canales: 12 barras completas de 5m y 8 de 15m, cada una con 13 descriptores geométricos y 32 contextuales. Los mapas son `20×5×64`, con Fibonacci, CALL/PUT OI y CALL/PUT gamma. La acción tiene 33 canales, incluidos contrato, griegas, costes observables, geometría y procedencia de objetivo/stop. Referencias: definiciones líneas 37–67; construcción líneas 96–188; codificación líneas 192–243; acciones líneas 265–307.

Esto ya permite ver aproximación general, tendencia, mechas, intensidad y desplazamiento de las exposiciones. No sería correcto atribuir un posible fallo a que el modelo no recibe secuencias o no conoce niveles aproximados.

| Aspecto | Preservado | Información ausente o comprimida |
|---|---|---|
| Velocidad de aproximación | Cambios de spot a 1/5/15m; geometría completa de barras; distancias actuales a objetivo/stop. | No hay velocidad relativa a una zona de entrada persistente ni cambios de signo de esa velocidad. La trayectoria del último tramo incompleto de 5m no entra como secuencia; solo hay cambios puntuales y contexto actual. |
| Rechazos/contactos | OHLC, cuerpo, mechas, posición IB y secuencia entre barras. | Dos recorridos con iguales OHLC pueden tener diferente orden y número de contactos. No hay contador de rechazos, tiempo dentro de banda o penetración seguida de recuperación. |
| Migración de walls | Mapas históricos, top-3 actuales y contexto de masas. | Promediar snapshots dentro de cada barra borra el orden intrabar de migración y su sincronía con el precio. No se conserva una serie explícita por identidad de strike/familia ni del rango de una wall. |
| Intensidad | `oi_logsum`, `gamma_logsum`, top-3 con `log_mass`, fracciones fuera del mapa y máscaras. | La normalización de cada mapa por su máximo borra su escala propia. El contexto conserva información agregada, pero no permite recuperar exactamente cada masa por strike y su evolución a partir de medias de log-sumas. |
| Zona de entrada | Elegibilidad impuesta por el motor, spot/IB y top-3 actuales. | `action_features` no incluye centro, distancia, componentes ni procedencia de la zona de entrada. Sí incluye los tipos de objetivo y stop. Parte de la zona puede inferirse del resto del estado, pero su identificación no es explícita. |

## Coordenadas: no confundir recentrado con normalización

El código actual usa `(strike−IB_low)/IB_range` para todos los mapas de la sesión (`features.py:104`). El IB está completo cuando se toman las decisiones, que empiezan a las 10:30. Los mapas históricos se expresan en ese **mismo sistema de coordenadas**, no en el IB parcial ni alrededor del spot de cada barra. El pasado anterior a las 10:30 queda representado con el IB ya conocido en el momento de decisión; esto no afirma que el IB final fuera conocido antes.

Las barras incluyen OHLC relativo al spot actual, además de `close_ib`; el estado incluye `spot_ib`. Por ello se puede recuperar la posición de la vela frente al mapa IB. La ubicación relativa entre precio y niveles no está completamente perdida. La operación local a cada barra es dividir la amplitud de su mapa por su propio máximo (`features.py:180–186`), no cambiar su eje espacial.

La compresión espacial sí merece una prueba específica: GBT promedia bloques de 8 puntos para pasar de 64 a 8 bins (`features.py:258`). Con una malla de −2 a 3 IB, el paso original es aproximadamente 0,079 IB y el paso entre centros de bins agrupados aproximadamente 0,635 IB. Es considerable frente a una banda operativa mínima de 0,05 IB y sigma espacial 0,08 IB. Quedan señales suaves y top-3 precisos, así que tampoco equivale a eliminar todos los niveles.

En [train_models.py](train_models.py), `LevelTCN.spatial` aplica dos convoluciones locales y luego `AvgPool2d((20,4))` sobre todo el eje temporal (líneas 548–556). Puede detectar patrones locales de migración, pero comprime mucho cuándo ocurrieron. Además, la concatenación espacial sitúa la última barra 5m junto a la primera 15m, que no son instantes vecinos; las ramas temporales de velas sí están separadas. Esto es una limitación de representación, no una fuga de futuro ni evidencia de que el resultado económico vaya a mejorar cambiándola.

## Una prueba simple: episodio de zona + el mismo GBT directo

**Intervención única propuesta:** añadir un bloque pequeño de descriptores de episodio causal al estado/acción del GBT de retorno directo. Mantener exactamente las mismas acciones ofrecidas, contratos, target/stop congelados, cierres variables, costes y scheduler. Mantener también todos los atributos existentes. Comparar el GBT directo fijado con su versión enriquecida, con la misma capacidad y presupuesto; ninguna arquitectura adicional en esta prueba.

Un episodio se construye recorriendo minutos en orden. Si no hay episodio abierto y el estado es elegible, se abre usando el centro y banda de la zona más cercana conocida entonces, con el desempate ya definido por el motor. Se congelan centro, banda y componentes iniciales. Se cierra cuando dos observaciones válidas consecutivas quedan a más de dos bandas del ancla, o al terminar la sesión. Los huecos no cuentan como confirmación ni se rellenan. Estas son reglas iniciales propuestas, no parámetros ya autorizados para ajuste; deben fijarse antes de implementar y medir esta variante.

Durante el episodio, que puede persistir aunque cambie la wall dominante, registrar solo estadísticas del prefijo:

- Distancia firmada actual al ancla en bandas; desplazamiento relativo a 1/5m con sus máscaras; lado desde el que se llegó.
- Minutos válidos desde primer contacto, minutos dentro de banda y fracción observada.
- Cruces confirmados de un lado exterior de la banda al otro; máxima penetración por cada lado; distancia recuperada desde esa penetración. Un contacto se cuenta solo al salir y volver a entrar, evitando contar cada minuto dentro como un nuevo toque.
- Centro de la zona elegible actual menos ancla original; tipos de la zona de entrada y distancia actual a ella. Separar esta geometría de la del objetivo/stop.
- Cambios de masa en los strikes/familias presentes al crear el episodio, con máscara si dejan de observarse. La pérdida del top-3 no implica masa cero. Añadir desplazamiento de la wall dominante actual respecto al ancla y máscara de cambio de identidad, sin afirmar que una wall física se haya movido de strike.

El episodio no elimina ofertas del motor ni fuerza una entrada por episodio. Si un estado es elegible para otra zona mientras sigue abierto, conservar ambas geometrías y la distancia entre ellas. Si no existe episodio válido, usar máscara explícita. Las identidades internas de seguimiento no son features numéricas. Antes del primer episodio no se reconstruye retrospectivamente una wall usando información que apareció después.

El target económico sigue siendo el retorno de **cada acción causal completa**, incluyendo pérdidas y entradas sin fill. No se convierte un rechazo bonito en label de éxito ni se utiliza el máximo beneficio posterior. Las etiquetas auxiliares de llegada/rechazo, si se estudiasen más adelante, requerirían otra variante explícita; no forman parte de esta prueba mínima.

## Qué demostraría o refutaría esta propuesta

Primero comprobar con fixtures que dos caminos con iguales OHLC y distinta secuencia de contactos producen distinto estado de episodio; una perturbación posterior a la decisión no debe cambiar sus atributos. Comprobar persistencia de ancla cuando cambia el top-3 y que los huecos no fabrican contacto/rechazo.

Después, si se activa la propuesta, entrenar ambas representaciones con los mismos días y acciones. Comparar selección causal y PnL neto de la política completa, todos los tickers/meses y sensibilidad de costes. Mantener CASH explícito. Una mejora de precisión al imitar el oracle o una mejor descripción visual no demuestra beneficio neto. No cambiar a la vez ventanas, zonas, eventos, contratos o salidas: se perdería la atribución de la comparación.

Esta hipótesis tiene un alcance estrecho: intenta resolver ambigüedad temporal y geometría de entrada, no demostrar que los niveles poseen edge. Si falla, deja evidencia contra esta representación concreta. El histórico 2026 ya visto permanece como desarrollo; una nueva descripción o un nuevo modelo no lo convierten en holdout intacto.

La justificación metodológica general procede de la [revisión previa de fuentes primarias](ORACLE_LEARNING_RESEARCH.md): [DAgger](https://proceedings.mlr.press/v15/ross11a) distingue estados visitados por el alumno y por el profesor, y la [teoría de aprendizaje con información privilegiada](https://arxiv.org/abs/2412.00985) muestra que la destilación no garantiza recuperar decisiones basadas en información ausente. Ninguna de estas fuentes acredita esta hipótesis de niveles; el episodio propuesto es una inferencia de ingeniería a contrastar con los datos locales. No se ha activado ni entrenado aquí.
