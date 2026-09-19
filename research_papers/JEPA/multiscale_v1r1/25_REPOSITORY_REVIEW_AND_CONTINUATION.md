# Revisión del repositorio y decisión de continuación

Fecha: 2026-09-19. Base inspeccionada: `4eb44536`, rama
`research/multiscale-v1r1-net-usd`. Cinco revisiones independientes por subagentes:
fuentes, motor económico, features/SSL, evidencia científica y ejecución.
El objetivo del usuario es llegar a day trading rentable; este informe distingue
lo comprobado de las dependencias aún necesarias para intentarlo.

## Estado real

| Área | Evidencia | Conclusión |
|---|---|---|
| Motor real | Informe21, 72 LightGBM y 72 refits exactos en un fold sintético | Software ejercitado, no rentabilidad de mercado |
| Histórico original | Informe11, intento INVALIDATED/FAILED_AUDIT | No se reabre ni se reemplaza su sello |
| Fuente reconstruida22 | Tres primeras barras, una reparación, 866 OI, audit mismatch0 | Admisión de componentes, no de sesión o economía |
| IB23 | SPXW/SPY sellados; QQQ sin manifest; sin summary global | Intento interrumpido, completitud QQQ desconocida |
| Economía multiescala | No hay ledger histórico admitido | NOT_EVALUATED |
| Shadow/cuenta | OFFLINE_FIXTURE/SYNTHETIC_ONLY | Sin evidencia prospectiva ni órdenes |
| Producción versionada | Política legacy con paper-order-intents | No es multiscale ni prueba de fills de bróker |

El catálogo de 23 artefactos de componentes22 fue rehasheado: 23 coincidencias,
cero diferencias. Sus copias compactas existían sin seguimiento Git. Los 688 OI
elegibles del componente (278/217/193) no son el mismo conteo que el join previo
Greek válido + OI (179/199/162); las condiciones de ambas tablas son distintas.

La suite inicial de esta revisión pasó 97 tests en 214,93 s. Ese resultado no
incluye los nuevos fixes ni certifica valores históricos. El informe de cierre
registrará por separado la suite posterior y la revisión offline24.

## Hallazgos y correcciones acotadas

### Identidad y delta de cotización

`payoff.py` distinguía el texto del strike al detectar duplicados. Dos filas
`100` y `100.0` del mismo contrato e instante podían sobrevivir y elegirse por
spread. El auditor tampoco rechazaba ese duplicado. Se exige ahora identidad
numérica del strike y equivalencia temporal del instante, con comprobación
independiente en el auditor. Contratos realmente distintos siguen permitidos.

El auditor económico aceptaba una entrada con delta NaN que el productor
descartaba. Ambos deben exigir delta finito para entradas; las salidas del mismo
contrato no necesitan delta. Un delta malformado se clasifica como quote no
elegible y no genera un fill. Estos casos se verifican con fixtures, sin afirmar
que ocurrieron en mercado ni modificar resultados sellados anteriores.

### Adaptador histórico ausente

`runner.require_gate` rechaza deliberadamente toda ejecución histórica. El gate
actual es una admisión negativa de procedencia, no el builder positivo completo.
No se arregla cambiando un booleano o conectando el runner a parquet antiguos.
Se necesita un adaptador de fuentes admitidas, manifests por alcance, lectura
por corte temporal y sidecars mensuales posteriores al freeze.

El lector OI entrega columnas de fuente, pero `levels.wall_snapshot` exige
`as_of`, `available_at` y `provenance_ref`. Esos campos deberán provenir del
ledger de admisión sellado, no de constantes inventadas a las 06:30.

### Alcance temporal de estados de 15 minutos

En D=11:35, los buckets completos de 15m alineados a D empiezan a09:35. El
fragmento09:30–09:35 no está en los contadores de estado; para D=11:40 ocurre
lo mismo con diez minutos iniciales. El código y el auditor hacen el mismo
recorte, mientras el contrato utiliza también la expresión «en la sesión».

La revisión inicial señaló una posible ambigüedad, pero el contraste con
`12_AUTHORIZED_CONTINUATION.md`, NUM-001, la resuelve: la autoridad posterior
excluye el fragmento parcial y exige la rejilla alineada a D. El revisor retiró
el hallazgo. Productor y auditor cumplen esa convención; no cambiar estados ni
introducir buckets parciales en el tensor 12x5m+8x15m. Los resultados sintéticos
sellados conservan su interpretación.

### Sensibilidad SSL

Existen encoder/predictor/NCE/VIS y proyección del reloj, pero no un entrenador
TCR-VIS completo conectado al runner ni su auditor de entrenamiento. Mantener
`NOT_IMPLEMENTED_IN_HISTORICAL_PIPELINE`, no PASS ni FAIL económico. Su futuro
entrenamiento deberá conservar las semillas, 50 épocas, permutaciones y barrera
train del contrato. Nunca rescatará un fallo del árbol.

### Operación

El systemd versionado carga la política legacy; el bot registra
`broker_submission=false` y `paper_filled_by_tracker`. La nueva API de
elegibilidad no está conectada a bots/services. El recorder prospectivo y la
cuenta son fixtures offline. No se consultó VPS o cuenta de bróker ni se
modificaron esos consumidores. Un flag production_live_ready no resuelve esto.

## Decisión de continuación

1. Corregir y probar identidad/delta; preservar artefactos anteriores.
2. Publicar24 y su código; cerrar offline el piloto IB interrumpido. Incluso
   dos componentes PASS no convierten QQQ o el piloto global en PASS.
3. Ejecutar la solicitud QQQ única del contrato 26, autorizada por el usuario
   el 19 de septiembre, tras publicar código y pruebas. El intento 23 sigue
   incompleto y la excepción no habilita otro retry.
4. Diseñar admisión de fuente reconstruida por alcance: D1–D5, prior-close,
   prefijo completo, walls y ejecución. Declarar vintage original desconocido.
   Medir volumen/tiempo antes de una captura masiva; no extrapolar un minuto.
5. Conservar la semántica NUM-001 y adaptar OI mediante evidencia sellada; completar
   runner y sensibilidad con pruebas sintéticas y auditor separado.
6. Solo tras admisión, código publicado y freeze, una evaluación económica
   mensual con el presupuesto ya fijado y ablación. Histórico favorable máximo:
   DEVELOPMENT_PASS_REQUIRES_SHADOW.
7. Política congelada y periodo prospectivo futuro completo, luego contabilidad
   compartida y aprobación explícita antes de integrar cualquier ejecución.

No hay fundamento para añadir ahora otro JEPA o un barrido. El selector exhaustivo,
V4R2 y V7 fallaron sus gates; GroupDRO/V6 no fueron evaluados económicamente;
V5 se bloqueó por fuente. AdaJEPA mejoró MAE pero no produjo política elegible.
Ninguna de esas conclusiones demuestra que todas las estrategias sean inviables.

## Criterio de avance

La prioridad es alcanzar una primera evaluación de mercado cuya fuente y
contabilidad sean verificables. Si la fuente no puede admitirse, se registra el
bloqueo. Si el primario no añade utilidad o falla los gates, se cierra esa
formulación. Repetir variantes hasta encontrar un positivo en datos vistos no
cumple el objetivo de demostrar rentabilidad operativa.
