# Diagnóstico emparejado modelo–oracle V1 (plan previo a ejecución)

La petición es localizar decisiones distintas y su causa antes de cambiar el
aprendiz. Este diagnóstico no modifica el experimento de episodios en curso,
sus modelos, selección, reglas, costes o universo. No incluye nuevos fits.

## Alcance autorizado y orden

Primero validación2025 completa:741ticker-días, con scores ya sellados del control
`gbt_net__0` y variante `gbt_net_episode__0`. Es fuera del ajuste2023–2024 pero
sigue siendo desarrollo observado; no se presenta como outer intacto. No se
abren nuevas decisiones test ni se agregan umbrales/políticas.

Segundo TRAIN2023–2024:96ticker-días. Para cada ticker×trimestre se eligen cuatro
fechas disponibles por menor SHA256 de `oracle_model_diagnostic_v1|ticker|date`.
El listado se publica antes de inferir. En esos días se infieren TODOS los
candidatos con ambos GBTs, CPU4 y sinGPU, usando los mismos modelos/features.
No se compara una muestra de acciones con un argmax oracle de universo distinto.

Se separan TRAIN (capacidad/ajuste con exposición previa a parte de labels) y
VAL (generalización observada) en todos los agregados. Se reutilizan labels y DP
existentes; no se cambia el engine ni se ajusta modelo alguno. Las únicas dos
políticas son control0 y episodio0, fijadas antes de este diagnóstico.

## Dos distribuciones de estados separadas

1. Estados en los que el modelo está libre y realmente puede decidir bajo su
   scheduler (incluye WAIT/NO_FILL, excluye tiempos ocupados).
2. Estados en los que la trayectoria oracle está libre bajo su scheduler.

En cada cohorte se comparan ambos selectores en exactamente el mismo estado y
con exactamente las mismas acciones ofrecidas causalmente. Se reporta además
el conjunto de todos los estados ofrecidos como referencia, sin confundirlo
con una trayectoria ejecutable. Las dos políticas conservan cohortes propias.

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

Este plan y código antes del diagnóstico; paths nuevos, hashes de modelos,
features, engine actions/labels/advantages y de cada predicción. Fixtures para
WAIT ties, NO_FILL, avance exit+1, estados ocupados, cohortes, contrato exacto y
clock bounds. Tablas por ticker y cohorte, ejemplos de discrepancias elegidos
por regla predeclarada y trazas auditables; ningún fit ni tuning en este paso.

Límite de interpretación: en TRAIN los modelos fueron ajustados con una muestra
de estas acciones. Acuerdo con un oracle de futuro realizado puede ser imposible
sin información adicional, incluso si la ejecución y el aprendizaje funcionan.
El diagnóstico debe distinguir error técnico, pérdida de información,
desalineación del objetivo y ruido/optimismo por maximizar labels futuros.

## Autoridad, matching y recuperación

El matching exacto exige también la misma banda (`band`) porque cambia las
barreras efectivas. Se separan pares FILLED/FILLED, NO_FILL/FILLED y demás
estados observados; no se atribuye una diferencia de ejecución a timing puro.

VAL puede comenzar con `validation.complete.json` y `freeze.complete.json`
sellados, sin esperar al cierre global del episodio. Se validan esos vínculos,
los modelos y cada fuente/predicción consumida. El diagnóstico no abre test.
La selección TRAIN lee sólo columnas de claves/estado del índice.

Cada día publica atómicamente sus tablas, scores nuevos TRAIN (si procede) y un
marker con hashes de entradas/outputs e identidad del código/plan/modelos. Un
lock exclusivo evita dos escritores; `--resume` reutiliza sólo días completos
verificados, conserva parciales y rechaza identidad o contenido divergente.
Los agregados descriptivos se reconstruyen desde esos días. No hay entrenamiento
ni rescate por resultados. El cierre vuelve a verificar las fuentes consumidas.

Se verifica por día que el regret no sea materialmente negativo y que su suma
en estados alcanzados libres del modelo coincida con el gap de PnL realizado
oracle menos modelo (tolerancia numérica). Las oportunidades bloqueadas se cuentan
por separado; su suma bruta no representa beneficio recuperable.
