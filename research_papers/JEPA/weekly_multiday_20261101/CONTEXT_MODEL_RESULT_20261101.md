# Weekly H2 con contexto IB/walls: mejora económica, hipótesis probabilística fallida

La comparación predeclarada terminó: CONTEXT182 obtiene +41.871 USD netos con
costes adversos en enero–junio de 2026, frente a −14.931 USD de BASE18 y
−32.666,20 USD del control CATEGORY30. El presupuesto máximo por entrada es
5.000 USD, incluyendo prima adversa y ambas comisiones, con capital inicial
de 100.000 USD. Son resultados simulados de desarrollo; no acreditan una
estrategia rentable en producción.

La métrica primaria era mejorar logloss de escenarios. **No se cumple:**
CONTEXT182 empeora de 1,204875 a 1,247644. El beneficio de esta cartera no
demuestra que sus probabilidades sean globalmente mejores. No se selecciona
el modelo positivo, ni se modifica la hipótesis primaria después del resultado.

## Comparación cerrada

| Modelo | Neto base USD | Neto adverso USD | Operaciones | PF adverso | DD realizado USD | Meses positivos |
|---|---:|---:|---:|---:|---:|---:|
| BASE18 congelado | −14.126 | −14.931 | 71 | 0,8559 | 28.293,30 | 2/6 |
| CATEGORY30 | −31.817,20 | −32.666,20 | 77 | 0,7330 | 35.651,50 | 1/6 |
| CONTEXT182 | +42.829 | +41.871 | 82 | 1,4241 | 18.020 | 3/6 |

Los controles de riesgo previamente cerrados dan −11.902,20 USD para
ALWAYS_CALL, −69.207,60 USD para ALWAYS_PUT y cero para abstención, con costes
adversos. El modelo BASE18 reproduce exactamente sus dos ledgers congelados
de la comparación de riesgo anterior; no fue reajustado.

CONTEXT182 usa las 18 variables de la opción, 81 variables causales de IB y
walls a las 10:30, las mismas 81 multiplicadas por el signo CALL/PUT y dos
indicadores de disponibilidad. Describe contexto **0DTE** aplicado a opciones
weekly; no toda la masa de opciones weekly. CATEGORY30 sólo representa
ticker × lado × día de la semana. Ambos son regresiones logísticas L2, C=1,
lbfgs, max_iter=2000, random_state=0, sin búsqueda de hiperparámetros.

Se realizaron los dos ajustes previstos sobre 1.752 candidatos elegibles de
2023–2024. Imputación y escalado sólo usan TRAIN. La calibración de 2025 usa
870 candidatos y selecciona alpha 0,3 para CATEGORY30 y 0,6 para CONTEXT182
en la misma cuadrícula predeclarada. EVAL contiene 426 candidatos H1 2026.
Los artefactos no registran warnings de ajuste. El contexto tiene 2.619 fechas
válidas y seis ausencias explícitas; se conservaron las máscaras y el universo.

Las medias condicionales de payoff y el prior siguen congelados del ajuste
original. La decisión usa EV adverso positivo y permite abstenerse. Se mantienen
entrada 10:35, salida a las 10:35 de la segunda sesión posterior, vencimientos
weekly elegibles y guardas de ejecución del contrato H2. No se han implementado
todavía entradas por toque de Fibonacci o salidas dinámicas por walls.

## Probabilidades y concentración

| Modelo | Logloss EVAL, menor es mejor | Brier EVAL, menor es mejor |
|---|---:|---:|
| BASE18 | 1,2048750303 | 0,6422386256 |
| CATEGORY30 | 1,3298413055 | 0,6649681372 |
| CONTEXT182 | 1,2476438661 | 0,6531835336 |

La diferencia pareada BASE18 menos CONTEXT182 es −0,0427688358. El intervalo
exploratorio por bloques de cinco sesiones es [−0,0848794227; −0,0021061808],
con 10.000 remuestras, semilla 20261101 y los 123 días incluidos. Es un
diagnóstico postdesarrollo, no un p-value ni un holdout independiente.

El EV adverso tampoco mejora globalmente: el MAE por candidato es 1.043,78 USD
en BASE18 y 1.063,49 en CONTEXT182; el sesgo (predicho menos realizado) pasa de
+13,97 a +55,17 USD. En sus respectivos candidatos seleccionados, el MAE baja
de 1.142,60 a 979,65 USD, pero son conjuntos distintos y elegidos por cada
modelo (92 frente a 106 candidatos, incluidos rechazos de ejecución). No se
interpreta esa comparación como mejora pareada de la predicción de EV.

La brecha logloss TRAIN–CAL es 0,0724 en BASE18 y 0,1505 en CONTEXT182.
El contexto ajusta mejor TRAIN, pero peor CAL y EVAL; CAL además favorece una
mezcla mayor con el prior. Son señales descriptivas de generalización limitada,
sin identificar por sí solas una causa. Una política con ganancias convexas
puede tener peor puntuación probabilística y aun así capturar mejores payoffs
en este semestre. Probabilidad, magnitud condicional y selección se deben
contrastar por separado, manteniendo filas comunes y parámetros congelados.

CONTEXT182 cierra 67 CALL y 15 PUT, 485 contratos en total. Su neto adverso por
ticker es SPY +29.454,40, SPXW +19.971,60 y QQQ −7.555 USD. Por mes: enero
−11.721,20; febrero +8.324,80; marzo −3.644,80; abril +44.379,20; mayo
+16.881,40; junio −12.348,40 USD. Sin abril, la suma mecánica es −2.508,20 USD.

La mayor operación aporta +12.232,80 USD; sin ella quedan +29.638,20 USD.
Estas restas describen concentración, no políticas alternativas ni autorizan
excluir meses, tickers u operaciones. Hay dos salidas ausentes tratadas como
cotas conservadoras; 14 rechazos por quote y 10 por riesgo de entrada.

El drawdown refleja resultados realizados, no valoración intradía o nocturna.
Se supone ejecución completa a los precios almacenados para hasta 14 contratos;
no hay simulación de profundidad, fills parciales o capacidad. El beneficio
debe contrastarse temporalmente antes de atribuirle estabilidad.

## Ejecución y estado de la auditoría

Contrato 8a535acd67ae36e6854ccf3aa02ab0f4f699c08be91bbeae5e17f7925e670ca4.
Productor evaluate_weekly_context_models.py
bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f,
publicado en e3a988fec28b7b6919806a6889af591496361838 antes del único run.
PID43220, inicio 15:45:56.917868 UTC, exit0 por handle retenido a
15:46:32.740348 UTC, duración 35,861 s; stdout y stderr vacíos. CPU0/hilo1,
gate de RAM y commit libre de 2 GB. No relanzar ni repetir los fits.

Raíz local: D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_model_comparison_01.
Manifest 662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a;
summary 0c98e712d4a6f5f8a06a16b494a819fc70dafbe6c43e413518dc6f5412103e09.
Root archivó 20 copias exactas, 3.450.823 bytes, en
context_model_result_evidence_01; recibo
8722a334d3ca52008c2486c0f12b08ebdde17777efa411e967f84dc6102aaba4.

Review_producer_exit comprobó 14 inputs y 14 outputs sin diferencias y la
identidad de los dos ledgers BASE18. Una reconstrucción aritmética efímera de
sólo lectura verificó seis ledgers y 8.860 comprobaciones, sin diferencias;
su fuente reportada tiene SHA e7cbaca0… y no se presenta como script persistido.
Las declaraciones de dos fits y su orden se apoyan en artefactos y flujo del
código pineado, no en instrumentación independiente o mtimes como prueba.

La auditoría independiente de matrices TRAIN, transformaciones, inferencia
desde coeficientes guardados, calibración, EV, seis libros y métricas terminó
**PASS_INDEPENDENT_NUMERIC_AUDIT_SEEN_DEVELOPMENT**. Código3eb6b979, revisión
CLEAR y nueve fixtures finales PASS publicados en ea401924 antes del único
run. PID30092, inicio16:05:00.338747UTC, exit0retenido16:05:14.863882UTC,
14,565s, stdout/stderr vacíos. Gate RAM6.543.953.920/commit5.194.399.744 bytes,
CPU0/hilo1. Auditbb661fe916f65ed6ee40dd3cf684650a8d318447005a7f224edec6a4b814b3eb;
manifest7d6e360edf648bde5633e8f7d5f20ebc55da8ad47616b14718acc4d09cd96eb2;
exit1d658aaa36f01aef0064c89342de1bca5e8c631d8d0c474ca4e9679a9caf31a0.

Review_producer_exit verificó identidad, cierre, flags, ocho pins y publicación;
CLEAR limitado al cierre, sin volver a ejecutar la auditoría. Root archivó
siete copias exactas, 175.201 bytes, en context_model_audit_result_evidence_01,
receipt90e99c0e89ec11fbb386634c1e87e859b7494148e56b693cfa012c70f0afb4aa.
La auditoría no importó el productor ni ajustó coeficientes; las medias y
scores BASE18 se apoyan en sus autoridades previas. Acredita reproducción
numérica dados parámetros, no reconstrucción raw o entrenamiento independiente.
Los intentos sintéticos anteriores, incluidos fallos de gate y una aserción
del fixture, permanecen preservados. No relanzar productor ni auditor cerrados.

## Continuación

Con la auditoría numérica cerrada, preparar y revisar una extensión
causal del contexto a julio–17 de septiembre, conservar los tres modelos y
aplicar sus parámetros sin refit, recalibración o selección. La inspección
estructural de Q3 encontró 318 de 330 fuentes 0DTE presentes y reloj nativo;
faltan 12 Greeks (SPY/QQQ en seis fechas). Esto no valida todavía sus valores
ni state_valid y no es una extracción ejecutada.

Todo 2026 permanece SEEN_DEVELOPMENT. Goal activo; selección nula,
technical_ready=false, promotion_approved=false. Sólo datos locales;
producción, API, bróker, VPS y cambios ajenos intactos.
