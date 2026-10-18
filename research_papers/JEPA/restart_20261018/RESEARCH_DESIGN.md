# Reinicio local: percepción de zonas y economía de opciones

Fecha: 2026-10-18. Petición del usuario: revisar las descargas locales, usar
subagentes y explorar nuevas representaciones/modelos, sin suscripción ThetaData.
Esta carpeta es investigación nueva; no modifica los resultados ni modelos viejos.
No se activa producción. El usuario ha dispensado los flujos de skills/AGENTS;
eso no convierte fuentes inciertas o resultados retrospectivos en evidencia live.

## Pregunta que sí podemos comprobar

¿La geometría y evolución de zonas IB/Fibonacci y concentraciones de opciones
mejora la selección de operaciones 0DTE, sobre la información del precio y de la
opción, después de spread y costes? Que haya reacciones cerca de líneas es una
pregunta diferente de que se puedan anticipar y monetizar.

Para el IB solicitado: L(r)=IB_low+r*(IB_high-IB_low), con cero en low y uno en
high. Primera hora 09:30–10:30 America/New_York; el IB completo sólo existe
después de terminar esa ventana. Los extremos de snapshots de un minuto son
**IB muestreado**, no los extremos verdaderos de todas las transacciones.

Una hipótesis visual razonable utiliza distancia continua, pendiente de
aproximación, velocidad, amplitud y cuerpo/mechas de velas, tiempo cerca del
nivel, rechazo previo, confluencias y desplazamiento de concentraciones. El
contexto debe ser visible antes de decidir; el tramo posterior de un gráfico
no puede entrar en el estado, la escala ni la selección de ejemplos.

La primera prueba económica se especifica en BENCHMARK_SPEC.md antes de ejecutar.
Compara precio/contexto, niveles auténticos y un control de niveles desplazados,
con calendario, acciones, costes y presupuesto de ajuste compartidos. El control
desplazado usa un desplazamiento distinto por ticker y sesión, determinado por
hash antes de resultados, de signo aleatorio y magnitud 0,2–0,8 rangos IB.
Un desplazamiento constante se descartó antes de ejecutar: un árbol podría
deshacerlo moviendo sus umbrales. Aun con el desplazamiento variable, el control
conserva estructura correlacionada y no es un test causal ni un null completo.

## Ampliación de relojes a petición del usuario

La ausencia de una columna llamada timestamp no basta para descartar un archivo.
Tras la observación del usuario se compararon 28 archivos de Greeks completos:
en los 15 que contienen ambos relojes, las 1.889.312 filas coinciden exactamente;
en los otros 13, 2.546.974 filas conservan una rejilla regular de un minuto en
underlying_timestamp, sin duplicados contrato/reloj. Son muestras, no una prueba
universal de todo el archivo histórico. Evidencia: CLOCK_EQUIVALENCE.md y su JSON.

Por tanto, el benchmark ampliado usa timestamp cuando existe y, en su ausencia,
underlying_timestamp tal como está almacenado, identificando este segundo caso
como convención de investigación. Cada archivo debe validar identidad, rejilla,
duplicados y spot; no se inventan tiempos por posición de fila o redondeo. La
primera prueba 2023 sirve de referencia con reloj explícito, no de exclusión
general de 2024–2026. WIDE_BENCHMARK_SPEC.md fija una prueba separada con ajuste
2023–2024, selección 2025 y evaluación enero–junio de 2026, antes de consultar los
resultados de la primera prueba. Las dos siguen siendo desarrollo visto.

En cambio, 13 de los 19 OI posteriores inspeccionados no contienen ningún reloj.
Para usarlos se declara por separado OI de cierre previo disponible a las 09:30
de la sesión como supuesto de investigación; no como recepción verificada. Se
registran estas diferencias y sensibilidades de demora, sin modificar el raw.

## Qué dice la investigación consultada

Se consultaron fuentes primarias el 18 de octubre de 2026. Son resultados en sus
propios dominios, no evidencia de rentabilidad para SPY/QQQ/SPXW 0DTE.

| Trabajo | Resultado relevante | Aplicación y límite aquí |
|---|---|---|
| [Jiang, Kelly y Xiu, (Re-)Imag(in)ing Price Trends](https://economics.yale.edu/sites/default/files/2023-11/The%20Journal%20of%20Finance%20-%202023%20-%20JIANG%20-%20Re%25E2%2580%2590%20Imag%20in%20ing%20Price%20Trends_0.pdf), Journal of Finance 2023 | Aprende patrones a partir de imágenes de gráficos bursátiles. | Justifica comparar representaciones visuales/geométricas; no demuestra que una CNN sobre velas intradía con walls gane dinero en opciones. |
| [TabArena](https://arxiv.org/abs/2506.16791), 2025 | GBT sigue siendo competitivo; deep learning mejora con ciertos presupuestos y ensembles; advierte sobre sobreajuste de validación. | Baseline GBT pequeño y reproducible antes de grandes búsquedas. El benchmark tabular no decide quién gana en una serie financiera no estacionaria. |
| [PatchTST](https://arxiv.org/abs/2211.14730), ICLR 2023 | Agrupa ventanas temporales en patches para forecasting. | Arquitectura candidata para tokens 5m/15m y relaciones de escala; forecasting genérico no equivale a utilidad de una opción. |
| [Joint Embeddings Go Temporal](https://arxiv.org/abs/2509.25449), 2025 | Adapta JEPA a representación temporal y evalúa clasificación/forecasting. | Preentrenar sólo con el pasado de cada fold; luego medir utilidad incremental y costes, no sólo loss latente. |
| [LeJEPA](https://arxiv.org/abs/2511.08544), 2025 | Objetivo predictivo con regularización SIGReg, evaluado en representación visual. | Puede simplificar el preentrenamiento; no ofrece una política de trading ni un simulador de mercado. |
| [Does JEPA Pretraining Help Time Series Forecasting?](https://arxiv.org/abs/2609.31680), septiembre 2026 | En la instanciación estudiada, el efecto cambia mucho por backbone y puede empeorar resultados. | No asumir que añadir JEPA mejora un modelo; control supervisado con el mismo backbone es obligatorio para atribuir la mejora. |
| [MuZero, DeepMind](https://deepmind.google/blog/muzero-mastering-go-chess-shogi-and-atari-without-rules/), 2020 | Combina búsqueda en árbol con modelo aprendido de valor, política y recompensa. | No es búsqueda binaria. En trading, un rollout puede explotar errores del simulador; primero hay que validar transiciones, incertidumbre y ejecución. |
| [Osler, NY Fed](https://www.newyorkfed.org/research/staff_reports/sr125.html), 2001 | Estudia cómo órdenes de divisas pueden explicar reversión y aceleración en soportes/resistencias. | Ofrece un mecanismo posible, no prueba específica de Fibonacci, IB, índices ni opciones 0DTE. |

## Qué conocemos y qué sólo aproximamos de las opciones

La [documentación ThetaData sobre OI](https://http-docs.thetadata.us/operations/get-snapshot-option-open_interest.html)
describe su reporte matinal y referencia al cierre previo. Esa definición del
proveedor es evidencia documental; no certifica cuándo se recibió cada descarga
local, ni que un valor archivado conserve exactamente su vintage original.

OI cuenta contratos abiertos, no identifica la posición neta de dealers. Una
concentración de calls no significa por definición que dealers estén largos
gamma, ni una concentración de puts que estén cortos. En
[su análisis de mayo de 2025](https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact),
Cboe describe flujos 0DTE equilibrados y una exposición neta de market makers
pequeña en su muestra. Eso tampoco descarta efectos locales o en ciertos días.

Las primeras muestras locales de Greeks contienen delta/vega/theta/IV y bid/ask,
pero no gamma. Si se calcula gamma desde IV, spot, strike y tiempo, el nombre debe
ser gamma de modelo. Mantener CALL y PUT separados evita convertir una convención
de signo en una observación. El cruce de gamma a lo largo de los strikes tampoco
es el spot de gamma agregada cero al repriciar toda la cadena.

## Orden de experimentos y criterios de interpretación

1. Inventariar existencia, schemas y relojes; conservar anomalías y exclusiones.
2. Construir una cohorte con reloj de quote explícito, sin bfill ni selección
   por PnL, y guardar identidad/tiempos/precios de la misma opción negociada.
3. Benchmark GBT acotado con campos suaves y controles. Reportar resultados por
   ticker, mes, coste, cobertura y diferencias pareadas por días.
4. Si la representación requiere mayor capacidad, comparar un CNN/TCN pequeño
   sobre tiempo × precio normalizado y un Transformer de tokens, con el mismo
   universo económico. No llamar fracaso universal a un fallo del GBT.
5. JEPA sería un experimento posterior frente al mismo encoder sin preentrenar.
   Preentrenamiento y normalización sólo en el pasado; no usar todo el histórico
   por considerarlo “sin etiquetas”.
6. Búsqueda de acciones tipo MuZero sólo después de demostrar que su simulador
   no inventa fills, liquidez o escenarios favorables. Reproducir una cinta
   histórica no genera contrafactuales de mercado ilimitados.

Se informa también el NO_TRADE (beneficio cero). No se reinterpreta un resultado
negativo seleccionando el ticker/mes/configuración ganador. Un resultado favorable
necesita estabilidad, incertidumbre razonable y contraste prospectivo congelado.
Todo el histórico ya explorado sigue siendo desarrollo. Con archivos antiguos
podemos entrenar y hacer simulaciones; no acreditar rentabilidad futura ni fills
reales. No existe una obligación estadística de que una búsqueda termine hallando
una estrategia rentable.
