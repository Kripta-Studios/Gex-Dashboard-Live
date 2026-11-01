# Ampliación expresa a opciones semanales y posiciones de varios días

El 1 de noviembre de 2026 el usuario ordena: «pues analiza si operando en weekly
con multi day trades en vez de solo intradía consigues las rentabilidad o no».
Amplía el trabajo activo más allá del objetivo original 0DTE. La autorización
de probabilidades de escenarios/valor esperado y días sin operar sigue vigente.
No es una petición de ejecución en bróker ni de descargas de mercado.

Root mantiene el auditor OOF0DTE ya iniciado hasta su cierre y prepara en
paralelo la nueva investigación. No cambia sus costes, criterios o resultados.
La prioridad de la siguiente evaluación económica pasa a weekly/multiday;
el borrador anterior de escenarios0DTE queda como referencia, no como lanzamiento
obligatorio previo a esta nueva orden.

Alcance inicial de exploración: mismos subyacentes SPY/QQQ/SPXW, compras de calls
y puts, contratos con vencimiento próximo semanal y holding que pueda cruzar
sesiones. Como punto de partida documental se examina disponibilidad de5–10
días naturales hasta vencimiento y trayectorias de2–5 sesiones. Estos rangos
no son una configuración seleccionada por resultados ni un grid ejecutado.
El contrato económico fijará exactamente vencimiento, holding y calendario.

Primero se revisan inventarios y schemas locales, investigaciones históricas
cerradas y supuestos del motor. No se demuestra continuidad del mismo contrato
por el simple hecho de encontrar archivos en días consecutivos. Las identidades
deben incluir raíz, vencimiento, strike y call/put, además de ajustes si aplican.
Se exige evidencia de quotes en entradas/salidas y transiciones entre sesiones.
No sustituir un contrato por otro que conserve aproximadamente la misma delta.

El motor0DTE no se puede prolongar cambiando sólo el cierre obligatorio: su
tiempo a vencimiento y calendario intradía están ligados al día actual. El nuevo
contrato deberá resolver gaps, expiración, sesiones cortas, niveles congelados o
actualizados causalmente, una posición abierta entre días, costes y valoración
de salida. Tampoco se puede utilizar un precio teórico como fill observado.

Las especificaciones oficiales distinguen SPXW con liquidación monetaria y
ejercicio europeo de opciones ETF con ejercicio americano y entrega física.
La admisión verificará la serie concreta; el protocolo decidirá salida antes
del vencimiento y tratamiento explícito de cualquier ausencia de quote.
[Cboe SPX Weeklys](https://www.cboe.com/tradable_products/sp_500/spx_weekly_options/specifications),
[OCC ETF Options](https://www.theocc.com/clearance-and-settlement/clearing/etf-options).

No hay aún resultado de rentabilidad weekly acreditado por esta continuación.
Los intentos históricos, incluso los fallidos, permanecen intactos. La nueva
prueba deberá separar fechas de ajuste/evaluación, reflejar solapamiento entre
trades y decidir con información disponible al entrar. El capital comprometido
y la exposición durante varias sesiones deben acompañar al PnL; sumar netos de
operaciones incompatibles no representa una cartera ejecutable.

Fuentes de mercado sólo locales D:/ThetaData; resultados voluminosos en
D:/GexResearchArtifacts. Sin API, producción, bróker ni VPS. Goal sigue activo;
su descripción inicial0DTE se interpreta junto con esta ampliación del usuario.
