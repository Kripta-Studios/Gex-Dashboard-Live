# Criterio de aceptación mensual solicitado por el usuario

Durante el ensayo activo del1noviembre el usuario exige rentabilidad cada mes,
y descarta como útil el modelo congelado que ganó en H1 pero perdió en Q3.
Root incorpora esta instrucción sin cambiar los cinco métodos, fechas, modelos,
gates21, costes, datos o reglas de trading ya fijados.

Para el informe de esta comparación, condición necesaria de aceptación:
neto adverso de la cartera agregada estrictamente positivo en cada mes completo
evaluado, enero–agosto2026. Se usa la atribución canónica por fecha de salida,
ya documentada. Mes sin operaciones/neto cero no cumple beneficio positivo.
Septiembre hasta el17 se informa como parcial, separado del conteo8meses.
No inventar un umbral adicional de DD/capital: ambos se reportan como estaban
previstos. Mostrar también cohortes por entrada y concentración, sin sustituir
el resultado canónico cuando otro desglose favorezca al modelo.

Si ningún método cumple, informar ninguno válido para el criterio del usuario,
aunque exista alguno positivo en total. No elegir frecuencia/ticker/mes ni
ajustar hiperparámetros a posteriori para convertir un fallo en aprobación.
El modelo congelado previo ya incumple estabilidad y no es candidato operativo.

El guard causal de21sesiones evalúa actualizaciones sólo con información
disponible entonces; no recibe la rentabilidad futura del mes para decidir.
Este criterio de reporte no altera dicho mecanismo ni causa refits adicionales.
No se cambia el código congelado por una condición de presentación/aceptación.

Todos estos meses ya son SEEN_DEVELOPMENT. Cumplirlos sería necesario para el
objetivo solicitado, pero no demuestra estabilidad futura ni autoriza producción.
No puede garantizarse beneficio todos los meses futuros a partir del backtest.
Goal continúa activo, sólo datos locales, promotion_approved=false.
