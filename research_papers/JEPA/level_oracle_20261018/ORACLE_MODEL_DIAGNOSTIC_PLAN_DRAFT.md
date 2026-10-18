# Diagnóstico emparejado modelo–oracle (borrador, sin ejecución)

La petición es localizar decisiones distintas y su causa antes de cambiar el
aprendiz. Este diagnóstico no modifica el experimento de episodios en curso,
sus modelos, selección, reglas, costes o universo. No incluye nuevos fits.

## Alcance propuesto para coordinar

Primario: TRAIN 2023–2024, con control GBT net y GBT net+episodios congelados,
cada uno a sus tres thresholds ya definidos. Los scores de TRAIN no están
materializados para todo el universo: se inferirán todas las acciones de los
días elegidos, usando los mismos modelos/features causales. No se puede comparar
la muestra de entrenamiento con el argmax oracle completo: omite candidatos.

Piloto descriptivo acotado propuesto: un día por ticker-mes TRAIN, elegido por
menor SHA256 de `20261018|ticker|YYYYMMDD`, sin leer sus valores. Son 72 días,
aproximadamente 20–25 mil estados y varios cientos de miles de acciones. El
universo completo TRAIN (1.491 días) queda como alternativa de mayor duración;
el propietario debe fijar cuál se ejecuta antes de generar scores/outcomes.
No se escogerán días por PnL, discrepancia o magnitud de movimientos.

Val2025/test2026 son diagnósticos separados, con scores ya guardados. No se
mezclan sus filas con TRAIN ni se usan para elegir nueva arquitectura, umbral
o cambio de reglas. El test2026 ya es desarrollo observado.

## Dos distribuciones de estados separadas

1. Estados en los que el modelo está libre y realmente puede decidir bajo su
   scheduler (incluye WAIT/NO_FILL, excluye tiempos ocupados).
2. Estados en los que la trayectoria oracle está libre bajo su scheduler.

En cada cohorte se comparan ambos selectores en exactamente el mismo estado y
con exactamente las mismas acciones ofrecidas causalmente. Se reporta además
el conjunto de todos los estados ofrecidos como referencia, sin confundirlo
con una trayectoria ejecutable. Las seis políticas conservan cohortes propias.

## Decisión, recompensa y oportunidad

Para cada estado libre, registrar acción del modelo o WAIT, acción DP del estado
o WAIT, score, threshold, recompensa inmediata neta del modelo y del oracle,
`Q(a)=net(a)+V(next_state(a))`, `Q(WAIT)=V(i+1)` y regret DP
`V(i)-Q(decisión_modelo)`. NO_FILL conserva recompensa cero y siguiente estado
i+1; una ejecución avanza a exit_i+1, como en el motor congelado. WAIT gana
empates, y action_id sólo resuelve empates/joins, nunca es feature.

Descomposición mutuamente excluyente principal: ambos WAIT; modelo WAIT/oracle
TRADE; modelo TRADE/oracle WAIT; ambos TRADE misma acción; ambos TRADE distinta
acción. En la última categoría, separar lado, bucket delta, contrato, objetivo
y stop. Acompañar cada categoría con número de estados/días, net inmediato,
regret DP, coste de oportunidad (`WAIT-value` y continuación tras salida),
medianas/cuantiles y concentración por ticker/mes. El oracle está construido
con el futuro realizado: no es un estimador insesgado de expectativa causal.

Medidas de selección: posición/rango de acción DP por score; score y net de
acción elegida; distancia target/stop en unidades IB y en bandas; distancia
de strike/spot y delta; duración posterior como outcome diagnóstico. Comparar
acción top-score, mejor net inmediato realizado y mejor Q DP permite distinguir
objetivo de una operación frente a valor secuencial. No usar esos outcomes como
features ni cambiar el ranking congelado.

## Timing y bloqueo por posiciones

Para una decisión discordante, diagnosticar relojes i±1/2/5 minutos sin operar
esas alternativas. Reportar disponibilidad exacta de la misma identidad
contractual y misma dirección; si el objetivo/stop físico no está ofrecido en
ese reloj, marcar no comparable, sin nearest, interpolación o ejecución fuera
del universo. Separar análisis de objetivo/stop idénticos de simple dirección/
contrato. Los cambios de PnL son hindsight descriptivo, no mejora ejecutable.

Contabilizar estados oracle TRADE que coinciden con una posición del modelo
abierta, cuánto tiempo bloquea cada trade y oportunidad DP inaccesible durante
ese intervalo. No sumar oportunidades incompatibles como beneficio recuperable.
Separar el regret de elegir una entrada del efecto de ocupar minutos posteriores.

## Entrega e integridad

Plan final y código antes del diagnóstico; paths nuevos, hashes de modelos,
features, engine actions/labels/advantages y de cada predicción. Fixtures para
WAIT ties, NO_FILL, avance exit+1, estados ocupados, cohortes, contrato exacto y
clock bounds. Tablas por ticker y cohorte, ejemplos de discrepancias elegidos
por regla predeclarada y trazas auditables; ningún fit ni tuning en este paso.

Límite de interpretación: en TRAIN los modelos fueron ajustados con una muestra
de estas acciones. Acuerdo con un oracle de futuro realizado puede ser imposible
sin información adicional, incluso si la ejecución y el aprendizaje funcionan.
El diagnóstico debe distinguir error técnico, pérdida de información,
desalineación del objetivo y ruido/optimismo por maximizar labels futuros.
