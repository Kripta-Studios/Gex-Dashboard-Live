# Continuación autorizada: completar Fibonacci IB y walls

El usuario ordena corregir los problemas, continuar y buscar rentabilidad,
señalando las extensiones Fibonacci del initial balance y las walls de griegas.
Esta autorización sustituye la instrucción de detener el trabajo de implementación
del cierre anterior. No convierte el intento `run_20260917_01` en válido ni borra
su FAILED_AUDIT. No se ha observado un resultado económico de esta familia.

Se mantiene la hipótesis, los 59 slots, 39 canales, costes, acciones, modelos,
thresholds, calendario y gates de 01_PREDECLARATION.md. Los Fibonacci 1.272,
1.618 y 2.0 de D0–D5 ya forman parte de ella. No se añade una búsqueda de
ratios/modelos para conseguir un resultado favorable. El objetivo es comprobar
rentabilidad ejecutable y aportación incremental, sin garantía de conseguirla.

La nueva implementación completará primero las fórmulas de niveles, estados y
tensor con fixtures sintéticos. Se mantienen las barreras de datos, auditoría,
publicación y freeze antes de cualquier label real. La implementación incompleta
es trabajo pendiente, no un bloqueo de datos que permita declararla terminada.

## Recuperación de procedencia y evidencia estable

REC-001: un nuevo intento usa un root nuevo y referencias nuevas. El anterior
permanece íntegro. Los logs/scripts son evidencia documental que se copia en bytes
al root nuevo mediante staging, hashes antes/después y comprobación de igualdad.
El auditor lee esas copias selladas. Cambios posteriores en el log operativo se
registran como drift externo, sin sustituir la copia. Una mutación de la copia,
de su manifest o de los datos raw sí invalida el intento. No se crea retrospectivamente
una copia supuestamente perteneciente al primer intento.

REC-002: no encontrar logs no demuestra un repair indebido. Para admitir precios
se exige linaje o una cota causal reproducible. Se buscará evidencia disponible
en los archivos locales autorizados; se ha preguntado al usuario por los originales
de 1 segundo o logs históricos. No se inventa la hora de disponibilidad, no se
reconstruye OHLC de 1 segundo a partir de snapshots de 1 minuto ni se sustituye
silenciosamente el subyacente. Continúa la prohibición de descarga y modificación raw.

REC-003: el código completo se puede implementar y probar sintéticamente mientras
se resuelve la dependencia de fuente. technical_ready permanece false hasta superar
el paquete completo; el registro histórico del intento fallido no se renombra PASS.

## Convenciones numéricas antes de outcomes

NUM-001: realized_vol_15m usa desviación poblacional (ddof=0) de quince retornos
simples de cierre, en bps; necesita el cierre precedente a esos quince minutos.
El primer TR de sesión necesita el prior-close, disponible como control estático.
No se usa una barra parcial para completar el primer bucket de la escala 15m:
su historia retrocede sobre la misma rejilla alineada a D hasta el primer bucket
íntegro dentro de RTH. El resto inicial no se rellena.

NUM-002: un touch geométrico cuenta en prior_touches y fija el reloj del primer
touch. first_touch solo se activa en ese primer touch si cumple approach.
Un touch cualificado inicia la historia de pierce/reclaim/retest; reclaim exige
un pierce de un bucket anterior, retest exige acceptance anterior. Los canales de
estados seleccionados respetan la precedencia única; pierce y first_touch son
indicadores de evento separados. Los ceros válidos conservan máscara true.

NUM-003: niveles ausentes enmascaran únicamente los canales dependientes del nivel.
Los doce controles y sus máscaras se replican idénticos en todos los slots,
incluidos los ausentes; de ese modo la ablación no recibe presencia de walls.
Los ocho estáticos son finitos. El ancla D no se presenta como conocida en todos
los endpoints anteriores; los snapshots de fuerza/persistencia sí respetan cada endpoint.

Este documento aclara convenciones pendientes antes de leer features/outcomes;
no cambia ningún resultado histórico ni relaja los gates económicos.
