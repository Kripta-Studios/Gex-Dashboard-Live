# Oracle de niveles y aprendizaje causal — 2026-10-18

Orden del usuario: entradas y salidas alrededor de niveles IB/Fibonacci/put-call
walls, sin holding fijo; construir primero un oracle rentable y después investigar
su aprendizaje sin futuro. Aclaración expresa: elegir un nivel objetivo y permitir
atravesar niveles intermedios. Se conserva toda evidencia anterior. Sólo fuentes
locales D:/ThetaData; no API ni producción. La rentabilidad no está garantizada.

## Universo y estados

SPXW/SPY/QQQ, sesiones completas XNYS 2023–2026H1. Los seis ticker-días sin Greeks
siguen ausentes, con cero operaciones en calendario. Caché diaria inmutable y
reanudable por hash, 391 snapshots de un minuto, 09:30–16:00 NY. Preferir timestamp;
si falta, usar underlying_timestamp almacenado. OI sin reloj: supuesto declarado
de disponibilidad 09:30 de información del cierre anterior. Conservar historia OI
y máscaras, precios nulos/cero sin fill. Spot compartido sólo si positivo y
consistente entre contratos y edad de underlying entre 0 y 60 segundos.

IB muestreado: min/max de 09:30–10:29, mínimo 57 muestras válidas y rango positivo.
Índices de minuto: 0=09:30, 60=10:30, 375=15:45, 385=15:55. Estados de entrada
60..375 inclusive, cada minuto. Sólo se permite una posición por ticker.
No se permite información posterior al estado para construir sus features,
contratos ofrecidos, niveles, objetivo o stop. Los datos ya vistos son desarrollo
retrospectivo; ningún tramo se presentará como histórico promocional intacto.

El eje técnico de contratos de la caché es la unión del día y puede contener
contratos que aún no se conocían. Sus índices son claves, nunca features. Conteos,
denominadores y máscaras económicas usan sólo contratos con una fila Greek ya
observada o una identidad OI ya disponible antes del corte. Añadir un contrato
que aparece únicamente después del corte no puede cambiar las features ni las
acciones económicas previas. Este caso se prueba por perturbación explícita.

## Niveles y acciones causales

L(r)=IB_low+r×rango_IB, ratios [-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,
1.272,1.618,2]. Añadir los tres strikes de mayor OI CALL y PUT y los tres de mayor
gamma_modelo×OI CALL y PUT, usando únicamente el snapshot y OI disponible.
Gamma Black–Scholes desde IV válida (0<IV<=5), r=q=0, vencimiento 16:00 y año365;
no se interpreta como inventario neto de dealers. Empates: menor strike.

Tolerancia operativa b=max(0,05×rango_IB, 0,0001×spot_actual), distinta de los
campos suaves de features. Ordenar niveles; agrupar sólo mientras máximo−mínimo
del grupo<=2b, no encadenar grupos mediante vecinos. Centro=media aritmética de
los precios originales; tipo=OR de fuentes FIB1/CALL_OI2/PUT_OI4/CALL_GAMMA8/
PUT_GAMMA16. Conservar procedencia de componentes. Máximo25 niveles antes de
agrupar. Medir fracción de estados elegibles: una banda excesiva no debe ocultarse.

Entrar es elegible sólo si el spot observado está a distancia<=b de algún centro.
Cada CALL ofrece todos los objetivos conocidos por encima, con distancia>2b y
<=3 rangos IB; cada PUT los equivalentes por debajo. El objetivo y su precio se
congelan a la entrada: atravesar otros niveles no cierra la operación. El stop
es el nivel conocido más cercano en el lado opuesto, también separado>2b. Si
falta ese nivel, no se ofrece la acción (dato conocido antes de operar).

Contratos: nearest abs(delta) de 0,35/0,50/0,65 para cada lado, seleccionados en
el estado de decisión con quote válida; desempatar por strike y eliminar duplicados
de contrato. No elegir otro contrato después de observar su fill. Oracle y
aprendiz tienen exactamente las mismas acciones (estado, contrato, objetivo, stop).
El stop, objetivo y b quedan congelados; no hay trailing ni actualización de walls
en esta primera familia. Seguir una identidad móvil sería otra política causal.

## Ejecución común, sin holding fijo

Estado en i; compra al ask de i+1, con 0,01 de deslizamiento y 1,30 USD de comisión
por lado, multiplicador100. Quote válida: bid>=0, ask>0, bid<=ask y valores finitos.
Si falta quote de entrada: no fill, no sustitución por otra acción. El compromiso
de entrada no se cancela gratis si el spot salta durante ese minuto.

Desde j=i+1, observar la banda del target/stop: CALL target cuando spot>=target−b,
stop cuando spot<=stop+b; PUT target spot<=target+b, stop spot>=stop−b. Esto incluye
saltos de todo el ancho de la banda; no se inventan toques intraminuto. Si ambas
condiciones se cumplen, prioridad stop. Primer trigger válido cierra al bid de
j+1, nunca antes de i+2. Los intermedios se ignoran. Si falta spot, no afirmar
toque; mantener hasta próxima observación o EOD y registrar incertidumbre.

Cierre obligatorio al bid de 15:55 (índice385) si no ha ejecutado antes; el último
trigger que puede ejecutar es384. Si falta quote de salida programada, liquidación
conservadora a cero, sin borrar la operación. Neto=(max(bid−slip,0)−ask−slip)×100−2,60.
Escenario adverso slip0,02. No se abren posiciones nuevas hasta estado exit_index+1.
No capital compuesto ni supuesto de rentabilidad porcentual de cuenta.

## Oracle, controles y aprendizaje

Enumerar acciones sin filtrar por reachability futura. Calcular luego resultados
futuros en un sidecar, incluido target/stop/EOD, holding y calidad. Oracle DP por
ticker/día: V(i)=max(V(i+1), net(a)+V(exit(a)+1)), cash=0 y orden de desempate estable
(WAIT primero si empate, luego action_id ascendente). Es un techo retrospectivo
de esta familia, no una política ejecutable ni prueba de edge predictible.
Comparar DP con fuerza bruta en fixtures y guardar sus trayectorias.

No enseñar sólo entradas ganadoras: conservar retorno de TODAS las acciones y
ventaja DP respecto a esperar como etiquetas distintas. El valor del máximo
clarividente no se debe presentar como expectativa causal alcanzable. Primera
comparación: GBT condicionado por acción sobre retorno directo frente a imitación
del teacher/ventajas; encoder CNN/TCN pequeño sobre secuencias completas 12×5m y
8×15m y campos espaciales de niveles. Las velas son OHLC de snapshots, no tape.
Normalizadores y encoders sólo se ajustan con pasado. Nunca pasar target elegido
por oracle, su beneficio, duración o salida futura como features al aprendiz.

Ajuste 2023–2024; selección2025; evaluación2026H1. CASH explícito participa en la
selección de políticas y gana los empates; si todas pierden en validación, la
política seleccionada no opera. Se reportan también las métricas diagnósticas de
candidatos, sin confundirlas con policy seleccionada. Se registran todos los
intentos y cambios de diseño; repetir investigación sobre este historial no lo
convierte en holdout nuevo. Modelo/configuración/normalizadores/umbral se congelan
antes de evaluar la política causal en el tramo posterior. Oracle test es techo
descriptivo visto, nunca criterio para seleccionar modelo o rescatar un ticker.

Los parámetros concretos de cada aprendiz se documentarán antes de su ajuste.
Primero cache+tests, oracle+auditor; después entrenamientos causales. La búsqueda
continúa con evidencia y límites explícitos: no fabricar rentabilidad mediante
costes omitidos, futuros ocultos, omisión de pérdidas o selección posthoc.

Antes de los primeros resultados, se fija como señal suficiente para considerar
una política candidata —no promocionarla—: neto positivo base Y adverso, PF base
>=1,20, al menos60 operaciones por ticker en H12026 y al menos3 meses positivos
de6, simultáneamente en SPXW/SPY/QQQ. Una política seleccionada CASH no se considera
rentable: evita pérdidas, pero no satisface el objetivo. Si no aparece candidato,
registrar el fallo y continuar con otra hipótesis explícita, sin redefinir estos
resultados ni convertir el mismo histórico en datos no vistos.
