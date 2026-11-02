# Goal vigente y vías para continuar

Estado persistente al detener: **paused**, confirmado por herramienta el2-nov-2026 a18:01:52UTC. Pausa solicitada por el usuario, no objetivo alcanzado ni bloqueo automático.

## 1. Texto literal del goal persistente

> Investigar con datos locales D:/ThetaData una estrategia 0DTE SPY/QQQ/SPXW con entradas y salidas por zonas Fibonacci IB y put/call walls: construir y auditar un oracle retrospectivo rentable bajo reglas y costes explícitos, luego investigar modelos causales que lo imiten sin futuro, buscando rentabilidad temporal fuera de ajuste y documentando todos los intentos sin confundir oracle con evidencia operable. Retomar desde el cierre 20261029: completar OOF mayo/junio preservando enero–abril, auditoría independiente FULL_H1 y reporte antes de decidir la siguiente hipótesis causal. Sin API ni producción.

Ese texto es histórico y no recoge todas las ampliaciones posteriores del usuario. OOF H1 y su informe ya terminaron; **no son el siguiente paso**. La autoridad práctica incorpora las instrucciones posteriores: weekly/multi-day, escenarios/EV, WAIT permitido, comparación de adaptación y revisitas a zonas. No interpretar la palabra0DTE del texto antiguo como prohibición de weekly ni volver a empezar el OOF.

## 2. Objetivo actualizado por las instrucciones del usuario

Encontrar evidencia de una política causal de SPY/QQQ/SPXW que opere opciones weekly durante varias sesiones cuando los datos presentes indiquen EV neto favorable. Puede abstenerse. Debe utilizar zonas IB/Fibonacci/walls cuando aporten información y medir la incertidumbre de escenarios, los costes, riesgo y estabilidad temporal.

El usuario exige neto positivo en cada mes completo evaluado: enero–agosto8/8; septiembre parcial aparte. Esto es un criterio de aceptación de investigación sobre el histórico, no una garantía matemática de que el futuro ganará cada mes. No se ha cumplido. No seleccionar retrospectivamente el ticker, mes, lado o trade favorable para aparentarlo.

Mantener diferencias explícitas entre oracle retrospectivo, política mecánica causal y modelo probabilístico causal. Los datos de desarrollo ya vistos no se convierten en holdout nuevo por cambiar la etiqueta o el split. Los informes2025/2026 y la nueva evaluación hasta17-sep siguen SEEN_DEVELOPMENT; no se encontró una extensión futura limpia en las raíces examinadas.

## 3. Por qué se cambió de vía

La frecuencia diaria apenas cambió las decisiones del semanal y empeoró200USD. El contextual que ganó41.871USD enH1 perdió58.128,60USD enQ3. La calibración/filtro EV posterior a selección también perdió dinero. Por tanto, no existe evidencia para seguir multiplicando fits de la misma receta esperando estabilidad.

La nueva pregunta es si **la secuencia observada alrededor de una zona y el momento de entrada/salida** ofrecen una ventaja medible. Hasta ahora IB/walls eran contexto a10:30, y la ejecución principal era entrada10:35 y salidaH2 a10:35; no se había probado la revisita como disparador.

H2 es la segunda sesión oficial posterior aD, no necesariamente48 horas naturales y no la expiración weekly. El horizonte de esta nueva prueba sigue limitado aD/D1/H2. No se ha abierto un ensayo de tenencia arbitraria de una semana entera.

## 4. Vía inmediata: replay mecánico de revisita

El [borrador D](../WEEKLY_ZONE_REVISIT_MECHANICAL_REPLAY_DRAFT_20261102.md) es documental, con revisión favorable, y aún no ejecutable. Describe una única receta sin barrido de parámetros:

- Geometría ENTRY_FROZEN formada aD10:30, conservada duranteD/D1/H2. Confluencia Fibonacci+wall.
- Secuencia: aproximación desde fuera de2bandas, visita a banda interior, salida por el mismo lado, revisita y dos minutos RTH consecutivos de confirmación fuera de2bandas. Salida al lado opuesto invalida la secuencia; gaps no inventan toques.
- Cada(plan,anchor) emite como máximo una confirmación terminal. Se elige la primera intención por ticker/día físico entre planes activos con desempates definidos. Si falla, no se rescata otra zona.
- CALL para confirmación hacia arriba, PUT hacia abajo, contrato weekly ya elegido a10:30. Primera quote válida estrictamente posterior; se cancela si el stop/target se observó antes o al mismo tiempo. Sin mirar el futuro para seleccionar.
- Stop al otro lado de la zona; target en el siguiente anchor disponible favorable. Sin target: no trade. No extender expiry ni H2.
- Cantidad calculada una vez con la ask del evento, presupuesto5.000USD, multiplicador100, comisión1,30USD/lado/contrato y slippage0,01/0,02 puntos según libro. Este reloj de qty es nuevo y debe declararse, no atribuirse al contrato antiguo10:30.
- Ausencias y salidas faltantes permanecen registradas; bid0 como cota conservadora cuando corresponde. Se observan muestras por minuto, no toques continuos intraminuto.

Tres comparaciones exactas:

| Rama | Entrada | Salida | Pregunta |
|---|---|---|---|
| A | Evento de revisita | Primera salida por zona o terminalH2 | Política mecánica principal. |
| B | Idéntica entrada, contrato y qty queA | H2 | A−B mide el cambio de salida con entradas emparejadas. |
| C | Política original10:35 ya cerrada | H2 | Referencia descriptiva; B−C mezcla timing, dirección, elegibilidad y exposición. |

La admisión deA/B es común, incluidos capital y bloqueo hastaH2, para que una salida temprana no permita aA otra entrada queB no pueda tomar. No hay cuarto brazo duplicado de B. La autoridad exacta de la política/libroC todavía debe fijarse; no inventarla.

Escenarios operativos: TARGET_FIRST, STOP_FIRST y TIMEOUT_H2, donde first significa primero observado. Missing exit y ambigüedad son flags ortogonales, no motivos para eliminar una operación o crear una clase ganadora. El replay inicial no entrena un modelo ni filtra por un EV nuevo.

Un RAW negativo no demuestra que toda señal condicional sea inútil. Por eso no se exige beneficio RAW para permitir investigación EV futura; sí se exige entender la cobertura, pérdidas y coste, y un contrato causal nuevo antes de modelar. No cambiar reglas D tras ver su PnL para rescatarla.

## 5. Vía posterior: probabilidades y EV condicional

Todavía no está contratada ni entrenada para estos eventos. Se ha discutido una familia pequeña con probabilidades de escenarios y payoffs de opciones condicionados, calibración sobre predicciones históricas prequential/OOF y WAIT cuando no haya evidencia suficiente de EV adverso positivo.

Antes de ejecutar hay que fijar schema de features disponible al decidir, madurez de labels, separación TRAIN/CAL, mínimos de historia, regularización y estimador de incertidumbre. Las cifras sugeridas en conversación para tamaños mínimos o márgenes **no son parámetros adoptados**. No probar una colección de umbrales y escoger la que mejora los meses vistos.

Medir logloss/calibración sobre candidatos elegibles y por separado sobre seleccionados; reconciliar probabilidades, payoff estimado y neto real. El diagnóstico anterior mostró que promedios globales pueden ocultar errores precisamente en lo que se opera.

## 6. Regresión y olvido: qué queda abierto

Ya se probaron TRAIN expansivo y promoción shadow con incumbente; no resolvieron la rentabilidad. No se ensayaron en esta etapa EWC, replay neuronal o adaptación online de JEPA. No afirmar que esos mecanismos se han validado.

Una futura actualización debe competir contra el modelo congelado mediante decisiones realmente futuras y labels maduros, conservar snapshots y posibilidad de mantener incumbente, e informar degradación económica y probabilística. Más frecuencia no es por sí sola una mejora. Esta vía queda subordinada a demostrar que las nuevas entradas/escenarios contienen información útil.

## 7. Próximo resultado que debe entregar el agente

Primero: B06 PASS completo o fallo explícito, sin confundirlo con beneficio. Después: C real admitido y replayD auditado. El informeD deberá mostrar neto mensual, DD realizado, cobertura/abstenciones, concentración por operación/mes/ticker y comparaciónA/B/C con costes comunes. Sólo entonces habrá una cifra económica nueva de revisitas.

Durante la pausa no se ejecuta ninguna de estas etapas. Para reanudarlas, utilizar el [mensaje preparado](PROMPT_PARA_RETOMAR.md).
