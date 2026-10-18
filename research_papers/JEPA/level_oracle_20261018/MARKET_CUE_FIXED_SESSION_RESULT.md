# Evidencia previa a la entrada: SPY, 2 de enero de 2025

Ilustración fija, no test de rentabilidad ni selección de un patrón ganador.
La fecha es la primera sesión SPY de validación, elegida anteriormente para el
gráfico de trayectorias. El extractor procesó las 5.630 acciones ofrecidas en
123 estados antes de añadir qué seleccionó cada trayectoria. Después se unieron
sólo identidades: 14 acciones oracle y 10 del control gbt_net__0, ninguna idéntica
entre ambas selecciones. No se leyeron columnas de resultados económicos en
esta extracción o resumen.

## Diferencias observadas

Medianas convencionales sobre las operaciones seleccionadas (promedio de las dos
centrales para muestras pares), calculadas desde selected_action_evidence.csv:

| Evidencia en la decisión | Oracle, 14 acciones | Modelo, 10 acciones |
|---|---:|---:|
| Distancia al componente visible más próximo, /IB | 0,02288 | 0,02034 |
| Distancia al objetivo, /IB | 0,17320 | 0,91667 |
| Distancia al stop, /IB | 0,22576 | 0,19545 |
| Ratio distancia objetivo / distancia stop | 0,66886 | 6,08726 |
| Spread / ask de la opción | 1,48573% | 1,49523% |
| Delta absoluta de la opción | 0,66425 | 0,60915 |
| IV almacenada, unidades decimales | 0,31160 | 0,28045 |
| CALL / PUT elegidos | 6 / 8 | 7 / 3 |
| Confluencia visible Fib-wall en la banda | 3 / 14 | 3 / 10 |

La mediana del ratio se calcula por acción; no es el cociente de las medianas
de las dos distancias. Tampoco representa beneficio/riesgo monetario de una
opción. Las estadísticas de summary.json usan, por separado, cuantiles empíricos
ponderados con igual peso por estado; para las muestras pares su percentil50
no interpola entre las dos observaciones centrales. No confundir ambas
convenciones ni atribuir a una diferencia de convención un cambio de resultados.

En esta sesión la proximidad de entrada y el coste relativo de la cotización
eran parecidos. La selección de objetivos fue distinta: el control aspiró a
recorridos bastante más largos con stops de tamaño comparable. Es una hipótesis
para el diagnóstico completo, no una razón para sustituir ya los objetivos del
modelo por los más próximos o imponer un ratio determinado.

## Un contraste en exactamente el mismo estado

A las 10:30 NYSE, el cambio de spot observado durante los 15 minutos anteriores
era aproximadamente −0,606IB. El control eligió CALL, delta+0,6735, objetivo a
2,654IB y stop a0,106IB. El oracle eligió PUT, delta−0,6127, objetivo a0,106IB y
stop a0,208IB. Ambos tenían exactamente el mismo contexto de mercado disponible;
no escogieron la misma dirección, opción ni recorrido.

La geometría de aceptación/retest definida antes de extraer estos datos coincide
con ese PUT. No demuestra que la regla prediga resultados, ni que un nivel
calculado a las10:30 existiera cuando se formaron las velas anteriores. Se trata
de geometría de historia observada respecto al ancla conocida en la decisión.
No conocemos la explicación interna de la elección CALL del GBT: una operación
contraria al movimiento previo también puede obedecer a una hipótesis de giro.

## Qué todavía no justifica las operaciones

La regla descriptiva estrecha de rechazo no coincidió con ninguna de las14
acciones oracle ni las10 del modelo; aceptación/retest coincidió con2 y0.
Sobre todas las ofertas, con igual peso por estado, las frecuencias respectivas
fueron0,3794% y9,3984%. Esto describe estas fórmulas particulares en una sesión.
No demuestra que no hubiera rechazos visibles, que las griegas no importen, o
que esos14 aciertos puedan explicarse con las reglas escritas. No ampliar la
regla hasta hacerla coincidir con los aciertos conocidos.

La cuota PUT del OI observado fue constante,43,4305%, en las ofertas de esta
sesión. Por sí sola no explica su timing. La cuota PUT de gamma unsigned sí
varió: percentiles25/75 ponderados por estado41,2109%/74,9232%. Esa variación
puede incorporar spot, IV y tiempo restante; no prueba flujo nuevo ni posición
firmada de dealers, y aquí no se le atribuye dirección predictiva.

Las variables continuas, las máscaras y las contradicciones se conservan. No se
han aplicado estas etiquetas como filtro, modificado el oracle ni entrenado un
modelo nuevo. Siguiente contraste: distancias, calibración de scores y decisiones
en todas las sesiones ya fijadas del diagnóstico TRAIN/VAL; después valorar un
predictor compacto de conceptos de mercado con el mismo objetivo y muestra que
el control. Ningún día sin operación podrá eliminarse para mejorar cobertura.

## Evidencia y verificación

- Extractor y runner:10 fixtures PASS, Ruff PASS, revisión independiente CLEAR.
- Resumen:3 fixtures PASS, Ruff PASS; conserva ausencias, ponderación por estado,
  universo completo de identidades y grupos sin operaciones.
- Directorio productor: D:/GexResearchArtifacts/level_oracle_20261018/market_cue_diagnostic_v1.
- Directorio resumen: D:/GexResearchArtifacts/level_oracle_20261018/market_cue_summary_v1.
- Completion productor SHA256:1582f65bde4489fe1bdb75ec515ceaa711be9cb1e6ec47bdd032a19debfa29b5.
- Summary SHA256:6783f6a9967f843b58632c48740fd0f1b6922b88048b431db617cbfc040825c4.
- Datos y autoridad previa rehasheados; las condiciones fueron selladas antes
  del overlay oracle/modelo. La pertenencia oracle sigue siendo retrospectiva.

Los valores de la tabla son evidencia descriptiva de este día. La rentabilidad
fuera de ajuste, la cobertura diaria universal y la paridad live no se prueban
mediante esta ilustración.
