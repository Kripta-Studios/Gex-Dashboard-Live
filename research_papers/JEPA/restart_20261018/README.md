# Investigación local de zonas IB, opciones y relojes

Fecha: 18 de octubre de 2026. Fuentes de mercado exclusivamente locales en
`D:/ThetaData`; no se utilizó la API ni se descargaron datos nuevos. Esta carpeta
contiene investigación nueva y conserva los intentos anteriores. No cambia bots,
servicios, órdenes ni modelos de producción.

## Datos disponibles y corrección sobre los timestamps

El censo completo encontró **366.555 archivos, 260,373 GiB y 235.018 parquets**,
con 37 schemas estructurales y ningún error de lectura de footers. El inventario
describe existencia y estructura; no certifica la calidad de todos sus valores.

| Greek 0DTE | 2022 | 2023 | 2024 | 2025 | 2026, hasta 17 de septiembre | Total |
|---|---:|---:|---:|---:|---:|---:|
| QQQ | 170 | 250 | 252 | 250 | 169 | 1.091 |
| SPY | 170 | 250 | 252 | 250 | 169 | 1.091 |
| SPXW | 220 | 250 | 252 | 250 | 178 | 1.150 |

Los 3.332 archivos Greek 0DTE contienen `underlying_timestamp`,
`underlying_price`, bid y ask; 1.816 contienen además `timestamp`. La observación
del usuario era relevante: **la ausencia del nombre `timestamp` no justifica
excluir 2024–2026 de la investigación**. En 15 archivos completos con ambos
campos, las 1.889.312 filas tienen igualdad exacta de relojes. Otros 13 archivos,
con 2.546.974 filas, conservan una rejilla de un minuto sin duplicados usando
`underlying_timestamp`.

El experimento ampliado utiliza el reloj nativo cuando existe y el
`underlying_timestamp` almacenado cuando falta, registrando la procedencia. La
comparación respalda esta convención de investigación; no demuestra cuándo se
recibió cada cotización en tiempo real. El OI sin reloj requiere otro supuesto:
información de cierre previo disponible a las 09:30 de Nueva York.

La construcción completa del experimento amplió esa comprobación inicial:
**1.096 archivos con ambos relojes, 141.978.747 filas comparadas y cero
discrepancias**. Otros 1.499 archivos Greek utilizan el reloj almacenado de
underlying. Hay también 1.096 archivos OI con reloj nativo y 1.499 con el supuesto
de disponibilidad matinal. Los 2.595 pares diarios producen 25.950 decisiones;
no hubo exclusiones por identidad, duplicados o schema. Se conservan máscaras de
precios inválidos y contratos sin OI; la igualdad de relojes no valida por sí sola
esos otros valores.

El spot derivado tiene una transformación histórica que puede reparar ceros y
rellenar valores. Por eso estas pruebas reconstruyen el spot desde los snapshots
Greek y conservan huecos. Sus velas y extremos son **muestreados a un minuto**,
no el máximo/mínimo de todas las transacciones intraminuto. SPXW tiene muestras de
apertura cero que se enmascaran. Gamma se calcula desde IV como aproximación de
modelo; OI no identifica la posición neta de los dealers.

## Qué se está contrastando

IB entre 09:30 y 10:29, conocido después de las 10:30, con
`nivel(r) = IB_low + r × (IB_high − IB_low)`. El cero es el low y el uno el high.
Los niveles se representan con campos suaves de anchura 0,10 y 0,25 rangos IB,
distancia, aproximación, confluencia y migración de concentraciones CALL/PUT.

Cada experimento compara tres representaciones con el mismo presupuesto:

1. Precio y contexto agregado de griegas/OI.
2. Ese contexto más las zonas IB/Fibonacci/OI/gamma aproximada auténticas.
3. El mismo conjunto con zonas desplazadas por una cantidad distinta cada día,
   fijada mediante hash antes de resultados. Es un control diagnóstico, no un
   null estadístico completo: conserva estructura correlacionada.

Se ajustan dos regresores LightGBM por representación, uno para CALL y otro para
PUT. Seleccionan una opción cercana a delta absoluta 0,50 con información anterior
a la decisión, entrada un minuto después y salida treinta minutos después.
Se negocia un contrato, pagando ask y cobrando bid, con comisión de 1,30 USD por
lado y deslizamiento de 0,01 USD por lado; el escenario adverso usa 0,02 USD.
No se solapan posiciones dentro del mismo ticker. El modelo puede abstenerse.
La selección del umbral sólo usa validación y se congela antes del cálculo de
payoffs test. La alternativa de no operar tiene beneficio cero.

| Experimento | Ajuste | Selección | Evaluación posterior |
|---|---|---|---|
| Reloj nativo 2023 | Enero–junio 2023 | Julio–septiembre 2023 | Octubre–diciembre 2023 |
| Ampliado | 2023–2024 | 2025 | Enero–junio 2026 |

La segunda especificación se fijó antes de ver resultados económicos de la
primera. Añade entradas retrasadas dos y cinco minutos con las mismas predicciones
y umbrales. Eso mide sensibilidad de ejecución, no verifica recepción histórica.
El calendario ampliado contiene 2.601 ticker-sesiones completas esperadas y 2.595
parejas Greek/OI presentes; faltan SPY y QQQ en 1, 9 y 15 de abril de 2026.

Los modelos actuales consumen resúmenes numéricos de trayectoria y zonas. **No
consumen imágenes ni la secuencia completa de cuerpos/mechas de todas las velas.**
Una prueba negativa aquí no demostraría que toda percepción visual de niveles
carece de utilidad. Los gráficos adjuntos ilustran datos visibles antes de una
decisión; no son un resultado de entrenamiento visual.

## Resultados y estado

La ejecución 2023 y su auditoría han terminado. Resultados octubre–diciembre,
en USD netos por operaciones de un contrato:

| Representación | Operaciones | Neto base | Neto adverso | Profit factor base |
|---|---:|---:|---:|---:|
| Precio y contexto | 429 | −9.963,40 | −10.820,40 | 0,713 |
| Zonas auténticas | 433 | −13.123,80 | −13.988,80 | 0,624 |
| Zonas desplazadas | 509 | −10.533,40 | −11.549,40 | 0,697 |

Los tres tickers pierden con las tres representaciones. La variante auténtica
pierde 10.635,40 USD en SPXW, 994,60 en SPY y 1.493,80 en QQQ. Ya perdía
8.505,40 USD en validación; las otras dos variantes también eran negativas.
El selector predefinido elegía el mejor umbral con suficiente número de
operaciones, sin exigir beneficio de validación positivo. Por eso el benchmark
mantiene operaciones para comparar representaciones: **ninguna de estas
políticas habría justificado operar; no operar daba cero**.

La diferencia auténticas menos precio es −3.160,40 USD, con intervalo bootstrap
pareado de bloques de cinco sesiones del 95% [−12.256,91; +5.434,82]. Frente al
control desplazado es −2.590,40 USD [−9.997,55; +5.914,29]. Ambos incluyen cero:
no hay evidencia fiable de mejora incremental en este experimento, y tampoco
prueba de que cualquier posible representación de niveles sea inútil.

Auditoría 2023: **PASS**. Se verificaron 1.488 hashes fuente, la contabilidad de
14.880 etiquetas de acciones a partir de sus cotizaciones guardadas, seis ajustes
independientes con 44.640 predicciones idénticas, selección
de umbrales, 2.676 filas de operaciones de validación/evaluación, 793 selecciones
de contrato y cotizaciones originales, y las dos comparaciones bootstrap sobre
62 sesiones. No reconstruye independientemente todas las features ni todas las
cotizaciones de ajuste/validación desde raw, ni certifica recepción/fills live.
Evidencia: `zone_benchmark_parallel_v3/independent_audit_01/audit.json`.

La ejecución ampliada también terminó. Resultados enero–junio de 2026, ajustando
en 2023–2024 y seleccionando umbrales en 2025:

| Representación | Operaciones | Neto base USD | Neto adverso USD | Profit factor base |
|---|---:|---:|---:|---:|
| Precio y contexto | 644 | −18.796,40 | −20.084,40 | 0,799 |
| Zonas auténticas | 693 | −34.135,80 | −35.521,80 | 0,685 |
| Zonas desplazadas | 836 | −36.986,60 | −38.658,60 | 0,701 |

Resultados base por ticker de las tres políticas separadas:

| Ticker | Precio/contexto USD | Zonas auténticas USD | Zonas desplazadas USD | PF zonas auténticas |
|---|---:|---:|---:|---:|
| SPXW | −16.246,40 | −32.309,00 | −33.945,40 | 0,663 |
| SPY | −623,80 | −737,20 | −814,00 | 0,848 |
| QQQ | −1.926,20 | −1.089,60 | −2.227,20 | 0,859 |

Las zonas auténticas pierden menos en QQQ que ambos controles, pero siguen
perdiendo; ese resultado aislado no rescata la política. En el conjunto, su
diferencia frente al contexto es −15.339,40 USD, intervalo 95%
[−47.934,74; +14.428,26]; frente al placebo es +2.850,80 USD
[−18.561,59; +23.178,89]. Ambos incluyen cero. Las tres variantes ya perdían en
validación: −53.118,80, −33.711,20 y −52.389,60 USD, respectivamente.

Las sensibilidades predefinidas tampoco producen beneficio agregado:

| Entrada tras decisión | Precio/contexto USD | Zonas auténticas USD | Zonas desplazadas USD |
|---|---:|---:|---:|
| 1 minuto, principal | −18.796,40 | −34.135,80 | −36.986,60 |
| 2 minutos | −18.337,40 | −33.419,80 | −41.098,60 |
| 5 minutos | −4.871,80 | −36.146,20 | −43.714,00 |

Son PnL simulados de operaciones de un contrato, no rentabilidades porcentuales
de una cuenta ni resultados reales. No se suman las tres políticas como una
cartera. El escenario de costes adversos empeora todos esos agregados.
El [gráfico comparativo](D:/GexResearchArtifacts/restart_20261018/benchmark_comparison.png)
muestra todas las curvas por ticker y representación.

Auditoría ampliada: **PASS**. Rehasheó 5.190 fuentes sin discrepancias, reprodujo
seis ajustes y sus 155.700 predicciones exactas, comprobó 66.420 contabilidades,
6.214 filas de operaciones principales entre validación/evaluación y 4.343 de
sensibilidad de demora. Contrastó 3.733 filas seleccionadas de evaluación y sus
máscaras OI contra raw, incluidos 62 días seleccionados con reloj de underlying;
reconstruyó el calendario de 123 sesiones y los dos bootstrap. Como en la prueba
nativa, no es reconstrucción independiente de todas las features y cotizaciones
históricas, ni acreditación de recepción o ejecución live. Evidencia:
`D:/GexResearchArtifacts/restart_20261018/wide_zone_benchmark_audit/audit.json`.
SHA256 del resumen auditado:
`e014cab7dca88c41fa0ff494d0736261ec9aa3c5eb6dbc47ba8d225ee780041f`.

**Conclusión económica:** no se encontró una política rentable en estas dos
pruebas, que entrenaron doce regresores LightGBM y compararon tres representaciones
en cada experimento. La prueba
sí incluye zonas aproximadas; no evalúa salidas dinámicas, otros perfiles de
delta, spreads, venta de prima, secuencias visuales completas, Transformers ni
JEPA. No sería correcto convertir este fallo acotado en una prueba universal
contra tu hipótesis visual. La comparación pendiente más directa sería una
representación completa de velas y mapas de concentraciones a varias escalas,
manteniendo costes, controles y particiones; no se ha ejecutado en esta sesión.

Los periodos evaluados ya habían sido explorados en investigaciones anteriores:
las particiones temporales de estas pruebas son **desarrollo retrospectivo**, no un holdout
histórico intacto. Una auditoría puede verificar cálculos y reproducción sin
certificar ejecución live ni rentabilidad futura. No hay promoción autorizada.

## Evidencia y reproducción

- [Inventario completo y cobertura](DATA_INVENTORY.md).
- [Lectores, schemas y límites de las fuentes](SOURCE_FEASIBILITY.md).
- [Comparación de ambos relojes](CLOCK_EQUIVALENCE.md).
- [Revisión de lo que realmente probaron los intentos anteriores](PRIOR_RESEARCH_REVIEW.md).
- [Diseño y literatura primaria: GBT, gráficos, Transformers, JEPA y MuZero](RESEARCH_DESIGN.md).
- [Especificación 2023](BENCHMARK_SPEC.md) y [revisión independiente](BENCHMARK_REVIEW.md).
- [Especificación ampliada](WIDE_BENCHMARK_SPEC.md) y [revisión independiente](WIDE_BENCHMARK_REVIEW.md).
- [Resultados 2023, todos los meses y tickers](BENCHMARK_RESULT.md).
- [Resultados ampliados y sensibilidad de ejecución](WIDE_BENCHMARK_RESULT.md).
- [Seis gráficos causales predeterminados](CAUSAL_CHARTS.md).

Los scripts y pruebas están en esta misma carpeta. Los artefactos voluminosos,
fuentes identificadas por hash, modelos, predicciones, ledgers y auditorías se
conservan bajo `D:/GexResearchArtifacts/restart_20261018/`. El inventario completo
está en su subcarpeta `inventory/`. Algunas extensiones de artefactos están
ignoradas por Git; estar en disco no significa estar versionadas.

Dos intentos técnicos 2023 se conservan por separado: uno interrumpido por coste
de ejecución y otro por `BrokenProcessPool`. Ninguno llegó a ajustes ni métricas
test. La tercera ejecución reduce hilos y añade checkpoints diarios; no cambia
la representación ni los parámetros económicos. Los detalles y hashes están en
la revisión del benchmark y en los directorios de cada intento.

Verificación de código: 11 pruebas sintéticas del benchmark nativo y 17 del
ampliado pasan; los auditores refittean los modelos reales por separado. La
comprobación Ruff de reglas F pasa en toda esta carpeta. El chequeo Ruff estándar
de toda la carpeta conserva avisos E701/E702 por formato compacto y E402 por
configurar hilos antes de importar librerías numéricas en el productor nativo
congelado. No se ha reformateado ese código después de ejecutar para conservar
su identidad exacta. Las imágenes comparativas se generaron y revisaron
visualmente; no intervienen en el entrenamiento.
