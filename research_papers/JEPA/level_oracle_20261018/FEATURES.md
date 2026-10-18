# Representación causal de velas y exposición

`features.py` está congelado con SHA256
`b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0`.
Usa el engine `70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6`
y el productor de caché
`985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f`.
Las tres identidades se vinculan a cada artefacto. No se leen labels, ventajas,
trayectorias del oracle, precios de entrada futuros ni resultados económicos.

## Tensor y máscaras

Cada día contiene los 316 estados 60..375. Para cada estado:

| Array | Shape por estado | Significado |
|---|---|---|
| `base` | 81 | Tiempo, IB, cambios de spot pasados, contexto actual y top3 walls de cada familia |
| `tokens` | 20×45 | Doce velas 5m y ocho velas 15m, con geometría y contexto de griegas/OI |
| `maps` | 20×5×64 | Historia espacial completa Fib/OI call/OI put/gamma call/gamma put |
| `token_mask` | 20 | Hay al menos un spot válido en esa vela |
| `bar_mask` | 20 | La ventana completa existe después de la apertura y ya terminó |
| `map_mask` | 20×5 | Fracción de minutos de la vela con el canal conocido |
| `bar_end_i` | 20 | Último índice incluido; −1 para historia inexistente |
| `state_valid` | escalar | IB válido y spot actual válido |

Los arrays numéricos de aprendizaje son float32 finitos; los ceros de sustitución
se acompañan de máscaras y fracciones específicas de validez. Delta, IV, vega y
theta tienen indicadores propios. `state_i` y `bar_end_i` son metadata para
alineación/verificación, no columnas introducidas directamente al aprendiz.

Las velas se anclan a 09:30. En el estado60, la última vela5m y15m acaba en59;
en64 sigue acabando en59; sólo en65 entra la vela60..64. A las10:30 existen las
doce velas5m, pero sólo cuatro de las ocho15m: las otras cuatro son izquierda
desconocida con máscaras, sin relleno. Todas las ventanas se conservan, no sólo
la última. Su OHLC es el de los snapshots de spot válidos, no extremos de tape.
Se retienen fracción válida y antigüedad de la última muestra.

La geometría incluye OHLC relativo al spot actual y normalizado por rangoIB,
close en coordenadasIB, cuerpo, mechas y rango. El IB usa exclusivamente0..59,
al menos57 muestras válidas y rango positivo. Reexpresar barras anteriores con
el IB que ya se conoce en el estado>=60 es causal para esa decisión.

## Campos espaciales

Se usan64 posiciones igualmente espaciadas entre−2 y3 en coordenada
`(precio−IB_low)/rangoIB`. Cada nivel/strike genera una gaussiana de sigma0,08IB.
Los cinco canales son Fib, OI call, OI put, gamma call y gamma put. Gamma usa la
misma función del engine: BS con r=q=0 y vencimiento16:00, multiplicada por OI,
100×spot²×0,01. Ese factor común no cambia el ranking de strikes en un snapshot;
la masa se denomina **proxy dollar-gamma**, sin atribuir posiciones a dealers.

Se promedian los mapas de minutos conocidos dentro de cada vela terminada y se
divide cada canal por su propio máximo de esa vela. No se usa el máximo del día,
de estados posteriores ni de validación/test. Los logaritmos de las masas y la
fracción fuera de[-2,3] se conservan en el contexto para que normalizar la forma
no oculte toda la escala o el desbordamiento. Los mapas vacíos permanecen a cero
y sus máscaras distinguen ausencia de información de masa conocida cero.

La unión de contratos de la caché diaria no sirve como denominador. La función
`known_contract_matrix` sólo admite identidades ya vistas en una fila Greek o
reportadas en OI a esa hora, incluso si el valorOI resulta inválido. Un contrato
que aparece por primera vez más tarde no altera las fracciones ni los mapas
anteriores. Un nuevo reporteOI inválido invalida el valor posterior; no se
arrastra silenciosamente el último válido a través de ese reporte.

## API y consumo eficiente

```python
cache = build_day_feature_cache(raw_cache)
encoded = encode_states(cache)                 # todos60..375, orden explícito
gbt_states = flatten_state_features(encoded)    # [316,1921]
vectors = encode_actions(raw_cache, states, actions)  # [N,33]
```

`feature_schema()` publica nombres y dimensiones: base81, token45, acción33.
GBT conserva todas las20×45 celdas temporales, todas las máscaras y los20 mapas
de cinco canales, con64 posiciones reducidas a ocho medias espaciales fijas.
CNN/TCN recibe las20×5×64 celdas espaciales sin esa reducción.

Las33 features de acción son un whitelist causal de contrato ofrecido, target,
stop, banda, fuentes de nivel y bid/ask/delta/IV/vega/theta **en state_i**. No se
usa ask de entry_i, duración, salida, recompensa, target elegido por el oracle,
`action_id` ni `contract_i` como variables de aprendizaje. Los IDs se conservan
solamente para alinear filas. `write_action_feature_cache` guarda estos vectores
una vez por día; el entrenador debe agrupar por día o usar LRU, evitando
descomprimir el NPZ completo por cada acción.

Archivos:

```text
D:/GexResearchArtifacts/level_oracle_20261018/features_v1/{ticker}/{YYYYMMDD}/features.npz
D:/GexResearchArtifacts/level_oracle_20261018/features_v1/{ticker}/{YYYYMMDD}/features.json
D:/GexResearchArtifacts/level_oracle_20261018/features_v1/{ticker}/{YYYYMMDD}/actions.npz
D:/GexResearchArtifacts/level_oracle_20261018/features_v1/{ticker}/{YYYYMMDD}/actions.json
```

`load_day_features` verifica hashes, nombres, shapes y dtypes. La reanudación
comprueba también hashes de fuentes, metadata y dependencias. El runner de
acciones verifica `causal_freeze.json` y proyecta solamente las columnas de
`actions.parquet`; no abre `labels.parquet`, `advantages.parquet` ni el summary
económico. `actions.provenance.json` conserva ese vínculo.

## Verificación y ejecución

Diecisiete fixtures PASS: perturbación de futuro en cinco cutoffs, incorporación
de contratos únicamente futuros en tres cutoffs con equivalencia bit a bit,
todas las ventanas y sus anclajes, barras incompletas, IB57/60, OI tardío e
invalidante, normalización pasada, overflow, cero válido frente a NaN, whitelist
de acciones, reanudación y detección de alteraciones. Dos checks de IO se
repitieron tras reforzar validación de manifests. Un fixture adicional del
runner de acciones verifica proyección y rechazo de un sello alterado. Ruff y
compilación PASS.

Piloto real outcome-free 20230103, tres tickers:948 estados, tres NPZ de estado
que suman753.576 bytes;15.728 acciones causales,251.910 bytes comprimidos. Esta
ejecución demuestra que se generan los tensores completos; no demuestra que
un aprendiz entienda el gráfico o sea rentable. La cobertura completa se
consigna en los manifests de los runners al terminar, no se infiere del piloto.

El primer runner de estados usó dos workers. Un perfil real SPXW20230103 midió
load0,111s, construcción1,743s, encoding1,688s y compresión0,158s, total3,700s
con overhead de cProfile. Por autorización del coordinador se cerraron sólo
ese runner y sus dos hijos y se reanudó con seis workers; no se cambió ninguna
feature ni el código matemático congelado. No había archivos incompletos.
El registro está en `features_v1/_restart_20261018T181012/`.

`run_features_parallel.py` sólo cambia la planificación: llama al mismo escritor
con los mismos hashes, verifica outputs existentes y limita trabajos pendientes.
Un archivo `features_v1/STOP_FEATURE_WRITER` permite terminar los días en curso
antes de una parada controlada. `build_action_features.py` funciona en paralelo
con workers sobre archivos distintos. Ambos conservan manifests separados
y no modifican las fuentes ni los artefactos económicos.

El intento de seis workers de estados y dos de acciones terminó con
`MemoryError` durante lecturas de hash de 8 MiB por agotamiento global del commit
de Windows. El fallo y los progress anteriores se conservaron en
`features_v1/_memory_failure_20261018T161608Z/`: 492 pares de estado y 242 de
acciones estaban completos. Un NPZ de estado QQQ/20230602 sin manifest se
archivó con SHA antes de regenerarlo; no se reemplazó su evidencia.
La reanudación usa el mismo código congelado, verifica cada par existente y
reduce la concurrencia a cuatro workers de estados y uno de acciones.
`features_v1/runs/resource_samples_resume4.jsonl` registra memoria privada de
estos procesos, memoria física disponible y commit global; el primer muestreo
sumó aproximadamente 0,59 GB privados para los siete procesos propios.
La cobertura final sólo puede afirmarse cuando terminen ambos runners.

Tras cinco minutos estables y recuperación de más de 14 GB de commit libre,
el coordinador autorizó cuatro workers de acciones. Un perfil de un día real
midió 2,169 s para 4.836 acciones: encoding 1,366 s, hashes 0,365 s y lectura
del cache 0,132 s. El único reinicio de acciones 1→4 conservó el progreso y
registró cero parciales en `_actions_restart4_20261018T162358Z/`; el código
congelado permanece igual. Las muestras de esta configuración están en
`runs/resource_samples_state4_action4.jsonl`.

Al terminar ambos runners, `verify_feature_coverage.py` comprueba igualdad de
claves con todos los caches completos, schema, bindings causales y hashes de
ambos NPZ por día. Publica `coverage_final.csv` y `coverage_final.json`.
No lee outcomes ni recalcula features independientemente; tampoco vuelve a
hashear los bytes raw, ya comprobados por los productores. El scope de esa
verificación se conserva explícitamente en el resultado.

Los productores terminaron con código de salida cero el 18-oct-2026:
estados a las 16:51:19 UTC y acciones a las 16:57:43 UTC. Exportaron 2.595
días (SPXW 867, SPY 864, QQQ 864), 820.020 estados y 15.395.840 vectores de
acciones. Los NPZ de estado suman 638.236.340 bytes y los de acciones
245.794.608 bytes. Las seis ausencias de fuente permanecen fuera de estos
2.595 días; no se rellenaron. En la última reanudación de estados se verificaron
492 días ya completos y se construyeron los otros 2.103.

La verificación global terminó a las 17:09:35 UTC con
`PASS_FEATURE_COVERAGE_AND_ARTIFACT_HASHES`: 5.190 NPZ rehasheados, cobertura
exacta y schemas/bindings/procedencia coincidentes. Los 820.020 estados tienen
`state_valid=true`. El índice `coverage_final.csv` tiene SHA256
`bdc3f036d83d9e6248aea993ae0a3852d8548b59635021cd024cec17724b7891`.
Esto acredita integridad de la exportación; no es evidencia de rentabilidad.
