# La TCN puede ajustar el bloque TRAIN pequeño

Una ejecución fija de 500 actualizaciones CPU sobre128 acciones TRAIN elegidas
por hash produjo R² ponderado **0,99941146** y MSE **0,000262013**, frente al
MSE de la predicción constante **0,44518917**. El MSE sin ponderar fue0,000620204.
Se informa el update500 fijado, aunque otros pasos dieron menor error.

Las128 entradas normalizadas fueron distintas; no aparecieron inputs idénticos
con targets incompatibles. El suelo calculado por esa condición fue numéricamente
cero (4,8e-17). Ninguna de las500 normas superó el clip1; máximo0,809063.

Esto prueba capacidad de ajuste para este bloque y estos targets. No prueba que
la red pueda generalizar ni explica por sí solo el ajuste casi constante sobre
TRAIN completo. Tampoco valida la estrategia ni permite seleccionar una política.
El entrenamiento principal de cuatro épocas permaneció intacto y no se leyó
validación/test en este diagnóstico. La siguiente medida autorizada compara
gradientes por día y mezclados, sin updates, en el checkpoint4 ya fijado.

El productor terminó las500 actualizaciones y guardó pesos, Adam, métricas y
normas. Falló después al serializar un escalar NumPy en el resumen. El finalizador
separado pasó una fixture y publicó los artefactos existentes con cero updates
e inferencias adicionales; `publication_recovery.json` conserva hashes previos.
Los cuatro tests iniciales y Ruff pasaron. No se realizó auditoría independiente
de este diagnóstico; sus afirmaciones son de capacidad TRAIN, no económicas.

Artefactos: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_memorization_v1`.
SHA summary `e04cbd249292dcab7ef1d9911dd148c20d1038a9b751c8f2698ea413ac9cd4b8`;
completion `c5c22701b2d6240b14bd5be9da105a58f075999b1578f6c14ea14f009029aa53`;
productor ejecutado `f368d65db7db802a3a2175b9ad340f778e9a556da08a986726d1f1a07172b1f5`.
