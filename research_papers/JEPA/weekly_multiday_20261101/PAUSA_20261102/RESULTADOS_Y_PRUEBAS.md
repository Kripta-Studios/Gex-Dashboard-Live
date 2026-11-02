# Resultados, modelos y pruebas al 2 de noviembre de 2026

Estado: PAUSADO por el usuario. Este documento reúne la cadena de investigación relevante y enlaza los informes completos, que conservan los ledgers, manifiestos, cifras mensuales y limitaciones. No sustituye sus evidencias ni convierte una revisión técnica en un resultado científico.

## 1. Objetivo que ha guiado el trabajo

La investigación comenzó con 0DTE e intradía, Fibonacci del Initial Balance y put/call walls. El usuario la amplió a opciones weekly con operaciones de varias sesiones, probabilidades de escenarios y valor esperado neto. Permitió días sin operar y pidió comparar reentrenamiento mensual, semanal y diario, evitar regresión y comprobar si las revisitas a zonas ofrecen mejores entradas/salidas.

El criterio económico solicitado es beneficio neto en **cada uno de los ocho meses completos enero–agosto de 2026**. Septiembre sólo llega al día 17 y se informa aparte. Un agregado positivo no sustituye ese criterio. Una prueba sobre meses ya vistos tampoco acredita rentabilidad futura.

## 2. Qué modelos se entrenaron realmente

La rama weekly reciente utiliza una **regresión logística multinomial con regularización L2**, no una nueva red JEPA entrenada en esta etapa. La receta inicial fija C=1, max_iter=2000 y random_state=0. Estima cinco clases contables: NO_FILL y cuatro intervalos del retorno bruto `r=(exit_bid-entry_ask)/entry_ask`: r<−0,25; −0,25<=r<0; 0<=r<0,25; r>=0,25. El escalado se ajusta sólo en TRAIN. Los bins del escenario y el payoff neto normalizado usado para EV son magnitudes distintas.

Las probabilidades se calibran mezclando la salida del modelo con el prior de TRAIN; alpha se elige en la rejilla predeclarada 0,0.1,…,1 por logloss de CAL. Los payoffs condicionales se estiman en TRAIN, con contracción hacia la media de clase. El EV suma probabilidades calibradas por payoffs condicionales. La política elige CALL o PUT sólo con EV adverso positivo; en otro caso WAIT. No obliga a operar a diario.

Se compararon BASE18, CATEGORY30 y CONTEXT182. El contextual contiene 18 variables base, 81 de contexto IB/walls, otras 81 multiplicadas por el signo del lado y dos flags de disponibilidad/validez. Usar contexto como feature no equivale a entrar cuando se produce una revisita.

El entrenamiento inicial emplea 2023–2024 y CAL 2025. En adaptación se entrenan estados nuevos desde cero con TRAIN expansivo, manteniendo historia antigua. CAL usa 63 sesiones maduras separadas de TRAIN y se purgan labels que invaden el periodo de calibración. Reentrenar cada día **no incorpora esos 63 días a los coeficientes**.

Fuentes: [contrato económico H2](../ECONOMIC_H2_CONTRACT.md), [contrato de adaptación](../ADAPTATION_WALKFORWARD_CONTRACT_20261101.md).

## 3. Experimentos económicos cerrados

No sumar cifras de tablas distintas: cambian periodos, tamaño de posición o reglas. Los cierres se conservan y no deben relanzarse para escoger un resultado favorable.

| Experimento | Resultado adverso principal | Interpretación |
|---|---:|---|
| OOF 0DTE H1: static / expanding / rolling12 | −8.168,60 / −3.502 / −28.889,20 USD | Las políticas agregadas fallan; OOF H1 cerrado y auditado. |
| Weekly H2 inicial, un contrato, H1 | +11.486 USD; 75 fills; 3/6 meses positivos | Positivo frágil: sin mayor operación queda −507,40 USD. |
| Mismo modelo congelado, Q3 parcial | +6.966,20 USD; 28 fills; 1/3 meses positivos | Sin mayor operación queda −9.417,20 USD. |
| H2 con riesgo máximo comparable de 5.000 USD | H1 −14.931; Q3 parcial +9.872,80 USD | El positivo inicial no sobrevive de forma estable a la normalización de riesgo. |
| CONTEXT182 con IB/walls, H1 | +41.871 USD; 82 trades; DD 18.020; 3/6 meses positivos | Sin abril queda −2.508,20 USD y empeora logloss frente a BASE18. |
| Mismo CONTEXT182 congelado, Q3 parcial | −58.128,60 USD; 41 trades; PF 0,2427 | Pierde los tres meses y los tres tickers. No generalizó. |

Informes completos: [OOF H1](../../level_oracle_20261018/OOF_FULL_H1_RESULT_20261101.md), [weekly H2](../H2_WEEKLY_RESULT_20261101.md), [robustez H2](../H2_ROBUSTNESS_RESULT_20261101.md), [Q3 H2](../H2_Q3_PARTIAL_RESULT_20261101.md), [contexto H1](../CONTEXT_MODEL_RESULT_20261101.md), [contexto Q3](../Q3_CONTEXT_MODEL_RESULT_20261101.md).

La sensibilidad H2 a costes también fue desfavorable: el ensayo de 0,50 puntos de slippage por lado dejó +4.430 USD; con 1 punto quedó −2.848 USD. El bootstrap exploratorio no acreditó significancia. Estas comprobaciones no seleccionaron una variante nueva.

### Adaptación continua: último resultado económico

Periodo 2-ene–17-sep de 2026; capital inicial 100.000 USD, riesgo máximo 5.000 USD por entrada, reglas H2 y costes adversos comparables. Drawdown realizado, no curva intradía marcada a mercado.

| Política | Neto USD | Meses positivos enero–agosto | Drawdown realizado USD |
|---|---:|---:|---:|
| Congelada | −20.204,20 | 3/8 | 77.701,60 |
| Mensual RAW | −12.625,40 | 2/8 | 68.767,90 |
| Semanal RAW | +2.693,80 | 3/8 | 46.860,80 |
| Diaria RAW | +2.493,80 | 3/8 | 47.060,80 |

Septiembre parcial es negativo en las cuatro. El diario perdió 200 USD frente al semanal. Ambos realizaron 83 trades y 482 contratos; 82 fills coinciden y sólo cambia un CALL SPXW. Dos de 612 candidatos cambian el top1. Se hicieron 136 fits diarios nuevos y se reutilizaron 42 estados, para cubrir 178 sesiones. El auditor reconstruyó 2.448 scores y ocho libros a partir de pesos guardados.

El neto diario sin el mayor trade sería −9.739 USD; sin abril, −34.582,20 USD. Los filtros de promoción GUARDED mensual/semanal tampoco ayudaron: −37.042,80 / −30.601,20 USD. El mecanismo conservaba incumbente, snapshots y evaluación shadow futura; no eliminó el deterioro.

**Corrección de unidades:** +2.693,80 USD son dos mil seiscientos noventa y tres dólares con ochenta centavos, nunca 2,6 millones. Los meses positivos semanales fueron febrero +2.517, abril +37.076 y mayo +25.355,20; suman +64.948,20. El resto de meses completos suma −59.497,20 y septiembre parcial −2.757,20: neto +2.693,80.

Fuentes: [resultado mensual/semanal](../ADAPTATION_MONTHLY_WEEKLY_RESULT_20261101.md), [resultado diario y mensual completo](../DAILY_ADAPTATION_RESULT_20261101.md), [cierre diario e interpretación](../DAILY_ADAPTATION_CLOSURE_AND_NEXT_STEP_20261102.md).

### Diagnóstico y filtro EV

El diagnóstico reconstruido independientemente mostró que el EV en las oportunidades elegidas podía estar muy sesgado aunque el promedio de todos los candidatos pareciera aceptable. Semanal RAW en Q3: EV por cantidades +4.818,22 frente a −33.458,40 USD realizados. La descomposición fue retrospectiva, no una identificación causal.

Se predeclaró y probó un filtro EV prequential con abstención, sin nuevos fits. Netos adversos frozen/mensual/semanal: −17.691,20 / −17.044,60 / −38.255,80 USD, con 2/2/1 meses positivos de ocho. Eliminó ganadores de abril/mayo y no se retocaron sus umbrales para rescatarlos.

Fuentes: [diagnóstico EV](../EV_COMPONENT_DIAGNOSTIC_RESULT_20261101.md), [cierre del filtro](../PREQUENTIAL_EV_FILTER_CLOSURE_20261101.md).

No se ha aislado experimentalmente olvido catastrófico. Reentrenar desde cero conservando el histórico evita borrar deliberadamente esos datos, pero no garantiza que el modelo se adapte ni que gane en el futuro.

## 4. Nueva vía de revisitas: trabajo técnico conseguido

### A. Inventario: completo y auditado

930 sesiones comunes entre 2023-01-03 y 2026-09-17, 2.790 ticker-días SPY/QQQ/SPXW, 1.620 planes weekly, 1.164 NO_SERIES y seis finales sin H2. Hay 4.860 referencias D/D1/H2 y 2.784 archivos nominales únicos: 2.768 presentes y 16 ausentes. Las ausencias afectan 24 planes y no se excluyen retrospectivamente.

Productor y auditor A cerrados; 22 pruebas del planner y 20 del auditor. La auditoría A es de metadata: no acredita todavía los valores de las quotes. [Informe A](../WEEKLY_ZONE_EVENT_SOURCE_PLAN_RESULT_20261102.md).

### B. Trayectorias: productor completo; auditoría independiente pendiente

El productor B02 terminó exit0 el 2-nov a las 13:46:00 UTC. Declaró 3.240 decisiones CALL/PUT, 3.606.310 observaciones de opción, 9.720 segmentos y 1.086.570 filas de spot, para 2.790 identidades. Hay 2.772 caches disponibles y 18 ausentes. Estos conteos pertenecen al productor y todavía requieren reconstrucción independiente completa.

El productor01 falló antes de valores por adaptación del calendario. Auditor02 falló al exigir el texto genérico PASS en vez del estado específico de la auditoría A. Auditor03 falló al comparar esquema físico completo contra una proyección histórica. Auditor04 y auditor05 avanzaron por los footers y la selección, pero fallaron por el gate RAM/commit. Ninguno produjo un PASS de valores. Todos están cerrados, preservados y no se reanudan.

Auditor05 cerró exit1 a las 16:38:48 UTC después de 2.784 footers y 1.377/1.620 unidades de selección. No llegó a reconstruir las trayectorias completas de opciones/spot ni a cerrar resultados. No se registraron los valores de la observación que rechazó ese gate: no atribuirlo exclusivamente a RAM o exclusivamente a commit.

Se creó R3 con espera acotada de recursos: 600 segundos, cada cinco segundos, mínimos intactos de 2 GB. La espera registra evidencia durable; errores de datos/esquema no se convierten en espera. La suite formal R3 acabó aprobando 136 pruebas. B06 está preparado y revisado, **pero nunca se lanzó**.

Fuentes: [productor B02](../WEEKLY_ZONE_EVENT_VALUE_PATH_V2_PRODUCER_CLOSURE_20261102.md), [fallo productor01](../WEEKLY_ZONE_EVENT_VALUE_PATH_FAILURE01_20261102.md), [auditor02](../WEEKLY_ZONE_EVENT_VALUE_PATH_V2_AUDIT_FAILURE_20261102.md), [auditor03](../WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_FAILURE_20261102.md), [auditor04](../WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_AUDIT_FAILURE_20261102.md), [auditor05](../WEEKLY_ZONE_EVENT_VALUE_PATH_AUDIT05_FAILURE_20261102.md).

### C. Geometría causal: código y 69 pruebas cerrados

Productor y auditor independientes implementan IB, niveles Fibonacci y walls de OI/gamma disponibles a las 10:30. Incluyen sesiones cortas, clocks, fuentes ausentes, confluencias, agrupación de niveles y hashes de identidad. El gamma es la definición explícita del contrato, no una inferencia garantizada de posición neta de dealers.

La suite C04 cerró compile0/Ruff0/69PASS a las 17:17:27 UTC. **No se ha extraído C con datos reales**, porque antes debe admitirse B. [Revisión final C](../C_GEOMETRY_FINAL_IMPLEMENTATION_REVIEW_20261102.md).

### D. Eventos y economía: sólo borrador documental

Existe un borrador revisado de revisita confirmada, tres comparaciones y costes/riesgo explícitos. No hay implementación D, eventos calculados, labels nuevos, fits de eventos ni PnL de esa política. [Borrador D](../WEEKLY_ZONE_REVISIT_MECHANICAL_REPLAY_DRAFT_20261102.md).

## 5. Registro de intentos técnicos recientes

| Intento | Resultado real | Corrección posterior |
|---|---|---|
| C01 | Compile0, Ruff21 errores; sin pytest | E402 por imports tras fijar entorno y dos lambdas de test. |
| C02 | Compile/Ruff0; 65PASS,4FAIL,1ERROR | Expectativas de fixtures: int16, nombres OI/gamma, 18 claves; helper recogido como test. |
| C03 | Rechazo por recursos antes del hijo | No se bajó el umbral ni se ejecutaron pruebas. |
| C04 | Compile/Ruff0; 69PASS en 66,08s | Cerrado. No repetir. |
| R3-01 | Compile0, Ruff1 F401; sin pytest | Import no usado eliminado de test. |
| R3-02 | Hijo compile exit0, observación inválida por PID ya desaparecido | Lectura por handle Win32 retenido; no se aceptó ese intento como PASS. |
| R3-03 | Gate previo al compile: commit1.969.106.944 bytes | Espera acotada añadida también al ejecutor formal. |
| R3-04 | Compile/Ruff0; 127PASS,9FAIL en 32,52s | Nueve fixtures heredados no enlazaban el waiter; corregido sólo el binding sintético. |
| R3-05 | Compile/Ruff0; 136PASS en 14,24s | Cerrado, 52 pins y snapshots exactos. No repetir. |

Las pruebas R3 ejercitan espera con observaciones artificiales y el gate oficial real como función. R3-05 tuvo recursos reales suficientes desde el principio; **no acredita haber atravesado una espera real por baja memoria**. La observación del hijo por handle sí se ejercitó en los procesos reales de compile/Ruff/pytest.

Durante una verificación root se comparó erróneamente un hash con un objeto `{bytes,sha256}`; se inspeccionó el schema y se corrigió la lectura, confirmando los 52 pins. No hubo deriva de fuente ni repetición de la suite.

## 6. Qué se consiguió y qué sigue sin conseguirse

Se cerraron y auditaron resultados, se descartó que la frecuencia diaria resolviera esta receta, se identificó sesgo EV entre seleccionados, y se preparó infraestructura causal para medir revisitas con precios de opciones. También se preservaron fallos y limitaciones de cada intento.

**No se consiguió una estrategia con 8/8 meses positivos, una demostración fuera de muestra limpia ni un backtest nuevo rentable de revisitas.** selected_policy sigue null; technical_ready y promotion_approved siguen false. Las horas recientes se dedicaron mayoritariamente a integración, memoria y pruebas. No deben presentarse como mejora económica.
