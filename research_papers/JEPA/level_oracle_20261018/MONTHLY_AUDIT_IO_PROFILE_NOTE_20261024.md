# Coste de verificacion mensual: nota de perfil futuro

24 de octubre de 2026. Nota descriptiva, sin cambio de codigo, proceso activo,
contrato, hashes publicados o decisiones economicas. No propone relanzar el test
ni modificar ahora el supervisor revisado. Su publicacion no bloquea el cierre.

Root comunica que el padre del test mensual PID56000 llevaba aproximadamente
24 minutos y130,5GB de lecturas acumuladas, todavia sin child, y que las matrices
y targets2025 suman30,9GB. Son observaciones comunicadas por root, no mediciones nuevas
de este revisor ni un benchmark persistido aqui. Lecturas atribuidas al proceso
no deben presentarse automaticamente como transferencia fisica del disco: puede
haber cache del sistema y lecturas repetidas de los mismos bytes. Tampoco permiten
inferir cuantas pasadas exactas se hicieron sobre todas las matrices.

La inspeccion estatica del nuevo supervisor encuentra fuentes concretas de
lectura repetida. Evidence.file rehashea siempre aunque ese path ya figure con
el mismo digest; Evidence.member comprueba antes y despues de parsear JSON.
producer_closure recorre runtime_members, preserved_checkpoints, final_checkpoints
y snapshots, luego science_closure vuelve a comprobar markers y sus miembros.
Algunos de esos conjuntos se solapan. preflight rehashea tambien el inventario
2025 y finaliza con verify(evidence.files).

launch vuelve a verificar receipt.files antes y despues del import tardio,
reconstruye el cierre bajo lock, verifica su inventario, y repite la verificacion
antes del gate/Popen. Tras el child se rehashean fuentes/evidencias para comprobar
preservacion. El auditor independiente ademas tiene sus propias verificaciones
de lectura y cierre. La frontera preflight→launch y el post-run son checks con
propositos distintos; no deben borrarse globalmente como si todos fueran iguales.

Un perfil futuro, en una version nueva y revisada, podria registrar por fase y
categoria numero de llamadas SHA, paths unicos, bytes totales solicitados y bytes
unicos, duracion monotonic y recursos. Separaria codigo/reviews/JSON compactos,
markers, matrices, sidecars y resultados. Distinguiria lectura logica medida del
proceso de I/O fisico y cache; no usaria duracion de fixtures como estimacion real.
Ese perfil no necesita alterar modelo, thresholds, costes ni seleccion de modos.

Candidatos a evaluar DESPUES de medir: unir mapas solapados y rechazar hashes
conflictivos antes de una sola pasada por fase; separar rehash de codigo post-import
del inventario cientifico grande; y evitar pasadas consecutivas redundantes dentro
de un tramo que mantiene el mismo lock y no modifica evidencia. La admision de
una nueva fase, la lectura efectiva de JSON, los cambios de autoridad, la liberacion
y recuperacion del lock, y la comprobacion final de inputs seguirian teniendo
fronteras explicitas. Un cache global por path o una comparacion solo mtime/tamano
no sustituye SHA ni acredita ausencia de mutacion.

Cualquier optimizacion exigiria nueva spec, implementacion separada, revision
independiente y fixtures de mutacion entre fronteras, conflicto de hashes,
redireccion de rutas, cambio post-import, liberacion/reentrada de locks y fallo
parcial. Debe producir el mismo PASS/fallo y mismos bindings ante esos casos.
Los productores y auditores actuales quedan congelados; ninguna estimacion de
rentabilidad o promocion cambia por esta nota.
