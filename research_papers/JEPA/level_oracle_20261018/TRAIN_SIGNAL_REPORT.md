# Qué está aprendiendo cada modelo: diagnóstico de ajuste

2026-10-18. Inferencia de los tres GBT ya entrenados sobre sus mismas270.377
filas TRAIN2023–2024. Sin refit, cambio de modelo ni selección por resultados.
Matrices, muestras, modelos y normalización rehasheados antes/después sin cambios;
igualdad exacta de las muestras control/episodio y alineación sample_i comprobadas.
Código: inspect_training_signal.py. Resultado completo:
D:/GexResearchArtifacts/level_oracle_20261018/train_signal_diagnostic_v1/summary.json.

| Modelo | Target | R² ponderado TRAIN | Predicciones positivas (peso IPW) |
|---|---|---:|---:|
| GBT net | Neto de operación / escala ticker |0,251588|10,4706%|
| GBT episodio | Mismo neto, añade contactos |0,251070|10,4312%|
| GBT advantage | Ventaja respecto a esperar con continuación oracle |0,419892|0,007665%|

No son PnL ni generalización: son medidas dentro de la muestra de ajuste y usan
sus pesos originales de población de acciones, no peso uniforme por sesión.
El GBT sí ajusta parte de la variación TRAIN; no está simplemente congelado en
una constante. Su R² fuera de ajuste previamente diagnosticado es negativo.
La diferencia hace pertinente estudiar generalización/calibración y decisiones
del scheduler, no atribuir todo el fallo a que el árbol no recibió señal.

Las70 columnas de episodio no mejoran el ajuste agregado: R²0,251070 frente a
0,251588. Aportan aproximadamente0,67% de la ganancia total de splits; esto
describe el uso del modelo, no demuestra ausencia de información causal en esas
features. Su validación2025 también fue peor. No se corrige este resultado
eligiendo un mes, ticker o umbral retrospectivamente.

La regresión de ventaja ajusta más su etiqueta y, aun así, casi nunca predice
ventaja positiva. La propia etiqueta es positiva sólo en3,22369% del peso TRAIN;
su media es−1,28611 escalas. Incluso su decil de predicción más alto tiene target
medio−0,299915. Es evidencia de que ajustar mejor esa etiqueta no garantiza
aprender una política que opere, ni una política económicamente óptima causal.

## Contraejemplo exacto del objetivo privilegiado

oracle_target_counterexample.py y su fixture muestran un caso de dos momentos,
sin datos de mercado. Entrar ahora da+1 y ocupa la sesión. Esperar permite una
operación posterior que da+3 o−3 con probabilidades iguales e inputs causales
indistinguibles. Esperar vale0 para una política causal; el oracle evita el−3 y
atribuye valor esperado1,5 a esperar. Por eso la etiqueta de ventaja oracle de
entrar ahora tiene media−0,5 y un regresor perfecto escogería WAIT, perdiendo el
beneficio causal+1. FixturePASS; el oracle logra2 en promedio, otra cota superior.

Este ejemplo prueba una limitación del objetivo, no cuánto explica de las
pérdidas reales. La corrección causal ya en preparación compara contra una
política de continuación fijada con datos anteriores, sin máximo futuro. Su
eficacia económica sigue sin evaluar y la comparación emparejada de trayectorias
modelo/oracle debe cuantificar los errores reales de entrada, dirección,
contrato, objetivo y ocupación temporal.

## Acciones siguientes ligadas a evidencia

- Medir regret y desacuerdos en los mismos estados alcanzables:741ticker-días
  VAL y96TRAIN elegidos por hash antes de inferir, en diagnóstico separado.
- Completar el control/residual causal ya autorizado; distinguir corrección del
  objetivo de cualquier eventual mejora del PnL.
- Mantener comparación mensual fija para estudiar actualización temporal.
- Para TCN, cuyo ajuste TRAIN original fue casi constante, completar la prueba
  de flags y comprobar capacidad de memorizar un bloqueTRAIN pequeño antes de
  atribuir el resultado a falta de señal de mercado o pedir más arquitectura.

Ninguna de estas observaciones constituye todavía una estrategia rentable.

## Relación con literatura primaria

Choudhury et al., *Data-driven Planning via Imitation Learning* (2018),
sección4.3, analizan la diferencia de información al imitar un oracle
clarividente: la política aprendida puede comportarse como una aproximación
que sobrevalora la información disponible en decisiones posteriores. El trabajo
es de planificación robótica, no de trading, y no acredita rentabilidad aquí.
La conexión con nuestro target de continuación es una inferencia metodológica;
el contraejemplo anterior se verifica independientemente en código.
[Artículo original](https://journals.sagepub.com/doi/10.1177/0278364918781001).
