# Factibilidad de datos para un objetivo exacto de sesión

23 de octubre de 2026. **Inspección documental y de código, sin activar un
experimento.** Se consultaron contratos e inventarios existentes y código sin
cambios respecto a `9ddcb9a8fa681db7fecd4c3a3153ae683a3897e2`. No se abrieron
arrays, parquets, modelos, scores ni nuevos outcomes. Los conteos siguientes
proceden de resultados ya publicados; las cuentas de memoria son estimaciones
aritméticas, no perfiles medidos del actor.

**Existe soporte diario completo reutilizable bajo los contratos actuales;
los chunks muestreados no lo sustituyen.** Falta demostrar que un consumidor
nuevo conserva ese soporte, sus máscaras, sus relojes y la separación entre
features y consecuencias futuras. El PASS del [laboratorio matemático](EXACT_SESSION_ACTOR_MATH_VALIDATION_RESULT_20261023.md)
no admite automáticamente ese consumidor ni los datos para un experimento nuevo.

## Inputs existentes y límites de reutilización

| Artefacto | Utilidad y límite |
|---|---|
| Índice y contratos SessionClock | Identifican 2.625 ticker-días: 2.619 disponibles, 24 cortos incluidos y seis `NO_EVALUABLE`. Dan rutas directas, cierre y hashes; las sesiones completas referencian sus originales. No reconstruir el universo desde carpetas encontradas. |
| Packs diarios de estado y acción | Conservan B81, 20×45 velas, mapas 20×5×64, máscaras y A33 por oferta, con IDs para joins. Son candidatos a reutilización sin reconstrucción de features ni expansión por acción de todo el tensor de estado. |
| `states.parquet`, `actions.parquet` y `labels.parquet` separados | Los estados y ofertas definen el soporte causal; las labels auditadas proporcionan status, salida y netos base/adverso para la transición offline. Status o rentabilidad futuros no pueden decidir qué ofertas existen. |
| Muestras y chunks mensuales | Seleccionan 332.472 identidades de 15.445.024 ofertas, aproximadamente 2,15 %. El IPW corrige la muestra para el objetivo anterior; no reconstruye exactamente el softmax ni las ocupaciones sobre ofertas omitidas. |
| Caché TCN row-mixed | Contiene 270.377 acciones de 1.491 días TRAIN de su propio contrato. Sus chunks normalizados son un subconjunto ligado a ese entrenamiento, no sesiones completas de un actor nuevo. |

Fuentes: [dataset](SESSION_CLOCK_DATASET_RESULT.md), [auditoría](SESSION_CLOCK_DATASET_AUDIT_REVIEW.md),
[features](FEATURES.md), [preparación mensual](MONTHLY_PREPARE_RESULT.md),
[muestreo](SAMPLING_SPEC.md) y [caché TCN](TCN_ROW_MIXED_PREPARATION_RESULT.md).
La auditoría SessionClock liga las referencias full a la auditoría original y
reconstruye los cortos; no vuelve a calcular toda la economía full. Cualquier
admisión nueva debe conservar ese alcance, verificar membresía y hashes de las
fuentes consumidas y rechazar sustituciones de arrays o metadata.

## Soporte, reloj y estado propio

El [reloj](session_clock.py) fija decisiones 60–375 y liquidación hasta 385 en
sesión completa; 60–195 y hasta 205 en sesión corta. WAIT conserva `h` y avanza
un minuto. Una oferta FILLED entra en `t+1`, sale como pronto en `t+2` y permite
otra decisión desde `exit+1`, con `h=1`. NO_FILL conserva `h` y avanza a `t+1`,
sin probar otra oferta en el mismo instante. Hay que preservar una diferencia
de representación: la label real NO_FILL guarda `exit_i=t+1`, mientras el
laboratorio abstracto usa `exit=None`; tratarla como FILLED saltaría un minuto.
[Motor](level_engine.py), [validación de labels](run_monthly_walk_forward.py).

Los estados sin ofertas, incluidos los inválidos, deben permanecer como pasos
WAIT; no se comprime el reloj a estados elegibles. Un día disponible sin ofertas
también tendría trayectoria WAIT y penalización terminal, no exclusión. El
sampler mensual rechaza ese caso: su admisión no se puede trasladar sin examen.
Una fuente ausente es distinta y sigue siendo `NO_EVALUABLE`, nunca una sesión
WAIT artificial con PnL cero.

Las consecuencias de cada oferta pueden compartirse entre `h=0/1`; sus
probabilidades y ocupaciones pueden diferir. No aplicar los pesos mitad de las
filas duplicadas del aprendiz anterior: el adjunto ya pondera por ocupación.
La suficiencia de `(t,h)` es condicional a una posición por ticker, tamaños y
reglas fijos y un tape exógeno. Capital acumulado, límites o memoria dependiente
de acciones exigirían otro estado. [Nota científica](EXACT_SESSION_ACTOR_SCIENTIFIC_NOTE.md).

## Orden, máscaras y separación temporal

Un consumidor nuevo necesitaría joins uno a uno por `(ticker, fecha, action_id)`,
igualdad exacta del soporte y orden explícito por estado/acción. No bastan igual
número de filas ni el orden físico de dos archivos. Los IDs y `contract_i` son
claves, no features; la unión diaria de contratos no permite anticipar identidades.

Hay que conservar `state_valid`, `token_mask`, `bar_mask`, `map_mask` y
`bar_end_i < state_i`: cero de sustitución no equivale a observación válida.
Los packs usan float32 numérico, booleanos y enteros de distinta anchura;
la conversión debe ser explícita, sin pérdida de identidad ni promoción mixta
accidental. El float64 del laboratorio no decide la precisión de un futuro
aprendiz. [Esquema y semántica](FEATURES.md), [lector existente](run_monthly_walk_forward.py).

El orden exigible seguiría siendo features/ofertas selladas antes de labels,
transformaciones ajustadas sólo con pasado y freeze de política/scores antes
de outcomes de evaluación. La DP futura de TRAIN sería cálculo del objetivo,
nunca una feature ni una consulta de inferencia. Cutoff lógico histórico y fecha
real de escritura deben registrarse por separado. Persisten los supuestos de
snapshot, reloj proxy y disponibilidad OI; integridad de archivos no acredita
recepción histórica ni paridad live. [Protocolo](PROTOCOL.md),
[extensión de reloj](SESSION_CLOCK_IMPLEMENTATION.md).

## Escala defendible, sin benchmark nuevo

Los inventarios documentan 823.284 estados programados y 15.445.024 ofertas
en 2.619 días disponibles: media de unas 5.897 ofertas por día, no un máximo.
Usando esos conteos y las dimensiones publicadas:

| Cuenta hipotética sin compresión | Bytes |
|---|---:|
| B81 + velas + mapas float32 de todos los estados, sin máscaras | 24.306.636.816 |
| A33 float32 de todas las ofertas | 2.038.743.168 |
| Tensor anterior de estado por día completo / corto | 9.329.584 / 4.015.264 |
| Un escalar float64 por oferta y WAIT, para ambos valores de h, en todo el inventario | 260.292.928 |
| Expandir hipotéticamente 1.954 float32 por cada oferta | 120.718.307.584 |

La última fila ilustra el coste de duplicar contexto; no elige esa representación.
Las tablas excluyen labels, índices, máscaras, objetos, activaciones, gradientes,
buffers y copias. No son RSS ni VRAM y no fijan batch o concurrencia. Como medida
publicada distinta, los NPZ full ocupaban 638.236.340 bytes de estados y
245.794.608 de acciones; el incremento SessionClock de 70.114.315 bytes incluye
metadata y días cortos. Compresión en disco no determina memoria de ejecución.

Procesar días completos y recomputar bloques parece compatible con este formato
por inspección; sigue siendo una inferencia. Faltan distribución por día,
máximo de ofertas por estado y perfil del futuro consumidor, sin abrirlos ahora.

## Dependencias antes de decidir otra hipótesis

La línea [mensual](MONTHLY_WALK_FORWARD_PLAN.md) contrasta actualización temporal;
OOF calibra máximos con historia previa y requiere la auditoría mensual compuesta
y una request revisada, según su [contrato operativo](OOF_PIPELINE_RUNTIME_SPEC_20261023.md).
Esta nota no consume cierres parciales ni sustituye esas dependencias. El actor
investigaría un objetivo de trayectoria distinto, pero eso no autoriza arrancarlo
antes de cerrar e interpretar las líneas actuales.

Permanecen sin elegir arquitectura, penalización real, épocas, semillas,
cardinalidad efectiva, extractor y periodos de otro experimento. Antes de
considerarlo faltaría un contrato de admisión del soporte completo, validación
del consumidor contra los artefactos auditados y reglas de freeze/auditoría
revisadas. El historial visto conserva su condición de desarrollo; esta
factibilidad documental no demuestra rentabilidad ni autoriza promoción.
