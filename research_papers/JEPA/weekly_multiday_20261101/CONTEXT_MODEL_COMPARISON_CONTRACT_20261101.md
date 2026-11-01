# Prueba de información incremental de IB/walls para weekly H2

Contrato nuevo después del diagnóstico de riesgo y antes de cualquier fit de
esta familia. Los experimentos previos permanecen congelados. No se promete
rentabilidad: se contrasta si contexto causal añade información y mejora EV
con la misma ejecución y presupuesto. Todo2026es SEEN_DEVELOPMENT.

## Tres modelos fijados, dos fits nuevos

1. BASE18_FROZEN: scores y parámetros del modelo weekly original, sin refit.
2. CATEGORY30: regresión logística sobre30celdas one-hot de ticker×lado×weekday.
   Orden SPY,QQQ,SPXW; CALL,PUT; weekday0..4. Sólo la celda correspondiente vale1.
   No quote, nivel o resultado en este control; se ajusta una sola vez.
3. CONTEXT182:18features originales,81B81 del contexto0DTE a10:30, esos81valores
   multiplicados por side_sign(+1CALL/−1PUT), y dos flags source_available y
   state_valid. Orden exacto18+81+81+2=182. La interacción por lado permite que
   la misma posición respecto a un wall tenga efecto distinto en CALL y PUT.
   No selección de columnas por retorno, importancia o correlación.

Contexto AVAILABLE y state_valid=true:81valores originales. AVAILABLE invalid:
vector81cero, flags1/0. MISSING_SOURCE:vector81cero, flags0/0. Las máscaras
internas de B81 se conservan como columnas; no imputar missing como resultado
económico ni eliminar candidatos. No se usan tokens/maps, etiquetas del oracle,
A33 ni información posterior a10:30. B81 describe IB y walls0DTE, no toda la
masa weekly. No se afirma haber implementado entradas por toque Fibonacci.

Join many-to-one exacto por ticker/entry_date a contexto ticker/date/state60.
El contexto contiene2625identidades; candidatos3054. Duplicados, fuentes/hash
alterados o clave sin fila de cobertura fallan. Mantener todos los candidatos.

## Splits, ajuste y decisión

Mismo TRAIN2023–2024, CAL2025 y EVALH12026 del contrato original y misma purga
de disponibilidad de labels:1752TRAIN elegibles,870CAL,426EVAL esperados.
No Q3 para estos modelos: falta extensión causal de contexto. No declarar
un holdout nuevo por usar otra representación de los mismos periodos.

Ambos fits nuevos: LogisticRegression L2 C1,lbfgs,max_iter2000,random_state0,
sin class weighting ni búsqueda. Imputación mediana con indicador y columnas
vacías conservadas, StandardScaler, ajustados sólo en TRAIN. Transform genérico
con nombres/orden guardados; no mutar globals del evaluador original.
Si un warning de convergencia aparece, preservarlo y no retocar parámetros
automáticamente. Coeficientes, interceptos, clases, versiones y transform se
guardan antes de interpretar EVAL. No reentrenamiento después de CAL.

Prior y medias de payoff reutilizan los artefactos TRAIN congelados originales;
verificar que los IDs elegibles y conteos por clase coinciden con ese ajuste.
Cada nuevo modelo calibra sólo alpha en{0,0.1,...,1} por menor loglossCAL,
empate alpha menor. No seleccionar umbral, lado, ticker, periodo o modelo.
Probabilidades×medias TRAIN dan EV con la misma fórmula y costes; top1adverse>0,
empate/EVno positivo WAIT. Guardar scores de todas las ofertas y flags de cota.

Replay H1 EVAL únicamente: mismos5000USD de riesgo, qty fijada10:30, guard10:35,
capital100000, obligaciones de comisiones y scheduler del contrato9c387e9b.
Reutilizar funciones puras del replay e4f42a9f después de verificar SHA, sin
ejecutar su main ni modificarlo. BASE18 debe reproducir exactamente el libro
EVAL ya cerrado50fa6b7a y sus decisiones. Tres modelos×dos costes=seis libros;
CALL/PUT/WAIT se citan desde comparación de riesgo cerrada, sin nuevo ajuste.

## Métricas y evidencia

Primaria: logloss multinomial en los426candidatos EVAL, diferencia pareada
BASE18 menos CONTEXT182; positiva indica mejora descriptiva. También comparar
CATEGORY30 y reportar Brier, reliability bins0,1 por clase, sesgo/MAE de EV,
todos los candidatos y seleccionados por separado. Separar cotas de salida
ausente, sin eliminarlas del resultado principal. CAL es calibración, no test.
TRAIN sólo descriptivo. Economía: net/PF/DDrealizado/mes/ticker, actividad,
cantidades, missing, no-fill y abstención. No presentar DD como MTM.

Reliability: edges0,0.1,...,1; bins[low,high), último[0.9,1], por clase;
reportar número, media predicha y fracción de esa clase; omitir bins vacíos.
EV: por coste base/adverse, error=EV_predicho_por_contrato−net_original_unitario
del candidato; sesgo=media(error),MAE=media(abs(error)). Es exactitud del EV de
la oferta unitaria, no del neto de cartera después de cantidades/guardas.
Seleccionados: IDs únicos de decisiones ENTRY/NO_FILL/CAPITAL_BLOCKED en EVAL,
incluidos rechazos de presupuesto; el rechazo no cambia el label original.
No presentar esta comparación como aislamiento causal de una sola variable:
contrasta el paquete contextual con nuevo ajuste predeclarado frente a BASE18
históricamente congelado, aunque conserve algoritmo, splits y parámetros.

Guardar contribución pareada de logloss por fecha, agrupando tickers/lados.
Incertidumbre exploratoria: bootstrap circular de bloques de5sesiones sobre
123sesionesH1,10000remuestras,seed20261101, percentiles type7 2,5/97,5.
Estadístico por remuestra: suma pérdidas pareadas/suma candidatos muestreados;
días sin candidatos se mantienen como0numerador/0denominador. Fallar si una
remuestra tuviera denominador0, no repetir con otra semilla. No p-value ni
afirmación de validación independiente a partir de este bootstrap postdesarrollo.
Algoritmo exacto: random.Random(20261101) de Python,25inicios independientes
uniformes randrange(123) por remuestra; concatenar para cada inicio sus5índices
circulares y truncar a123sesiones. Repetir10000veces en ese orden. Percentiles
type7 son interpolación lineal sobre los10000estadísticos ordenados.

Inputs: datasetH1bfc7370f, evaluaciónH154dc2d6c, model68712c7c,mediasa8dc3292,
contexto1030sellado con manifest externo real pendiente de binding y
riesgo50fa6b7a. Sólo artefactos locales, sin raw/API. Código nuevo, fixtures
de causalidad/splits/joins/máscaras/riesgo y revisión antes de publicación y
único run. Root fijará manifest concreto de contexto antes de cualquier fit.
CPU0/hilo1, gateRAM/commit2GB, logs/exitretenido. Raíz nueva
h2_context_model_comparison_01 bajo D:/GexResearchArtifacts/weekly_multiday_20261101.
Goal activo y promociónfalse independientemente del signo del resultado.
