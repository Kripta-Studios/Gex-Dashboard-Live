# Auditorías, problemas encontrados y límites de las conclusiones

## Qué se verificó y qué no

El trabajo separó productor, auditor independiente y reporte. Los auditores comparten el contrato pero reconstruyen decisiones/contabilidad de forma separada. Cada PASS tiene alcance concreto; una prueba sintética no equivale a histórico, una igualdad de scores no equivale a refit y un PnLpositivo del oracle no equivale a señal causal.

| Auditoría | Evidencia principal | Límite relevante |
|---|---|---|
| Benchmarks iniciales | Fuentes rehasheadas, seis refits por experimento, predicciones exactas, ledger y controles raw seleccionados | No reconstrucción de todas las features raw ni receipt live |
| Oracle completo | Motor de acciones, barreras/quotes/DP y resultados sobre el universo completo | Información futura autorizada sólo para oracle; no predictor |
| IB temporal/features | 2595días,820020estados, extremos0..59, barras cerradas y cuatro columnas base exactas | No prueba universal de ausencia de cualquier otra fuga |
| SessionClock | 2619disponibles+6ausentes,24cortos, arraysfullintactos | No convierte timestamps proxy en recepción live |
| Aprendiz original | Nueve políticas,54outputs y selección | Dadas predicciones; sin refit/reinferencia |
| Episodios | Matriz270377×2024, seis políticas, selector nulo y recuperación sin refit | No prueba de utilidad de todos los posibles episodios |
| FLAGS64 | Seis políticas, compatibilidad, selección/freeze, costes | Sin refit neuronal independiente |
| Continuación causal | Etiquetas, muestreo/IPW, matrices, economía y selección | Dadas predicciones; sin reproducción de inferencia ni rawfeatures |
| Extensión corta causal | Nueve sesiones y unión750, seis políticas,2394archivos | No reauditó2026 ni rawquote/barrier replay |
| Compacta152 | 1104controlesfullbitexact+9cortos,1119días, costes y calibración | Sin refit/reinferencia |
| 424 | Implementación y13fixtures, fit/export/readbackTRAIN | Evaluación temporal no iniciada |
| Mensual | Implementación/auditor sintético y revisiones | Año interrumpido; no auditoría económica real completa |

Hashes y copias exactas disponibles en [ARTIFACTS](ARTIFACTS.md). No se ha ejecutado una suite general nueva tras la orden de parada. Las cifras de pruebas en documentos individuales corresponden a sus revisiones en ese momento; no se suman como tests únicos de una única versión.

## IB y Fibonacci: fuga revisada expresamente

Se comprobó el uso exclusivo de09:30–10:29 para el IB y decisiones≥10:30. Para estado60 las últimas barras5m/15m terminan en59; la barra60..64 no entra hasta65. Ni extrema posterior ni barrafutura se usa como feature. Se recomputaron columnas `spot_ib`, `ib_range_over_spot`, `ib_valid` e `ib_valid_fraction`. Cero diferencias en2595días y820020estados.

La auditoría de export no recomputó cada celda de los20tensores por estado. Los hashes de los manifests y arrays/columnas leídos se distinguen de hashes de grandes fuentes reportados por manifests. Esta precisión evita afirmar una auditoría más amplia que la realizada. Las fixtures de prefijo y contratos tardíos refuerzan la causalidad del código, pero no eliminan incertidumbre de recepción original.

## Por qué la brecha oracle–modelo no se arregla con más arquitectura sin diagnóstico

El oracle observa el resultado antes de escoger. El learner tiene que predecirlo. En los estados elegidos por el oracle, la mayoría de alternativas pierde; por ello copiar aspecto geométrico o ladoCALL/PUT no basta. En la comparación de validación, los modelos coincidían con su lado aproximadamente la mitad de las veces y raramente con contrato/objetivo. El modelo buscaba con frecuencia recorridos más lejanos y holds más largos que el oracle.

El primer target de ventaja usa continuación óptima futura. Se detectó el problema de usar esa ventaja como si fuera la de una política causal realizable; un contraejemplo y el diseño de continuación fija separan ambas cantidades. La corrección causal permitió actividad diaria observada pero no beneficio. Eso refuta la suficiencia de esa corrección concreta, no la posibilidad matemática de toda estrategia.

La degradaciónTRAIN→VAL y la sobreestimación tras argmax están medidas. IPW corrige el objetivo de muestreo, no elimina dependencia temporal, sobreajuste o sesgo de selección. Miles de acciones del mismo día no son miles de observaciones independientes. No se usó una partición aleatoria por acción para acreditar rentabilidad temporal.

## Griegas, unidades y composición

Se revisaron gamma modelada desdeIV, unidades de vega/rho y límites de theta/TTE. En la fuente usada vega/rho requieren escalado raw/100 para la convención documentada; la semántica temporal histórica de theta no se declaró universalmente resuelta. SPXW0DTE y ETF0DTE no justifican asumir idéntica expiración legal: el cierre de sesión es una convención de valoración declarada.

La dinámica de gamma exigía demasiada validez y dejaba escasa información utilizable. Se distinguió cambio de la griega dentro de contratos comunes, cambio deOIreportado y entradas/salidas de composición. La mejora de cobertura no representa reconstrucción de datos ausentes ni exposición real de dealers. El nuevo fit424 terminó, pero la petición de parar llegó antes de comprobar rentabilidad temporal.

## Calidad de quotes y percepción visual

Se revisaron discrepancias entre spot y payoff, cotizaciones respecto a intrínseco aproximado y residuos de paridad. Un panel de837días/744926observaciones no halló ask de entrada por debajo de la referencia intrínseca aproximada; apareció un caso oracleSPY con bidcero/spreadamplio. Los residuosSPX también aparecen fuera de tradesoracle. No se concluyó que hubiera arbitraje ejecutable ni se filtraron retrospectivamente operaciones para mejorar PnL.

El supuesto de llegada un minuto después, el ask/bid almacenado y un contrato no modelan colas, profundidad, impacto, recepción real, margen ni todas las reglas operativas del bróker. Las velas son muestreadas; una percepción visual basada en tape completo puede ver movimientos intraminuto ausentes. El fallo de estos modelos no demuestra que todos los niveles sean inútiles.

## Incidentes técnicos preservados

- Intentos previos de auditoría del motor tuvieron correcciones y perfiles sucesivos; el cierre autoritativo es `engine_v1_audit_v4`, sin borrar versiones fallidas.
- Tras el fit de episodios hubo errores de cuatro rutas de metadata; wrapper separado corrigió sólo rutas y reutilizó el modelo, sin segundo fit.
- La inferenciaTCN necesitó compatibilidad exacta de `unique/inverse` y multiplicaciónfloat32 antes de asignarfloat64; se probó antes de evaluar la variante.
- Los dos primeros intentos del auditorcompacto fallaron por normalización Windows/POSIX antes de métricas; v3 pasó sin cambiar scores ni ledger.
- El primer launcher424 con límites conservadores se canceló antes de crear hijo/fit; nuevo wrapper2GB ejecutó el único fit efectivo.
- La primera transición mensual detectó que el tercer fit había comenzado y lo dejó terminar. Después se verificaron6084hashes, se cerró el proceso antiguo y se reanudó sólo la fase de validación con gate2GB. La parada actual del usuario termina esa continuación.
- El adaptador/evaluadorOOF recibió un guard de recuperación: una raíz con outputs sin contrato debe fallar antes de labels. Revisión estática completa; rerun final pendiente por recursos primero y por parada después.

## Evidencia de literatura y límites

[ORACLE_LEARNING_RESEARCH](../ORACLE_LEARNING_RESEARCH.md), [RECENT_METHODS_REVIEW](../RECENT_METHODS_REVIEW.md), [AGENTIC_FEASIBILITY](../AGENTIC_FEASIBILITY.md) y el diseño inicial contienen fuentes primarias y las inferencias propias. Incluyen representación temporal/visual, JEPA, agentes financieros y simuladores de mercado. No se reprodujeron sus resultados ni se transfirieron sus backtests a0DTE.

Un sistema agéntico puede organizar experimentos y revisar causalidad; no obtiene por ello información de mercado ausente. UnLLMpuede recordar hechos posteriores si evalúa fechas históricas, aunque sus herramientas sólo muestren un prefijo. Buscar sobre el futuro realizado del backtest vuelve a crear el oracle; una búsqueda operable necesita un modelo condicional de futuros y su incertidumbre.

## Conclusión científica al parar

Se ha demostrado un techo retrospectivo rentable en el simulador y se han identificado fallos concretos de representación, objetivo y optimización. Se han obtenido políticas con actividad diaria observada, pero pérdidas. Se han mejorado ajustesTRAIN, pero faltan sus pruebas temporales. **Ni imposibilidad universal ni rentabilidad causal demostrada.** La parada es una decisión del usuario, no una conclusión de éxito ni un bloqueo por falta de autorización para seguir investigando.
