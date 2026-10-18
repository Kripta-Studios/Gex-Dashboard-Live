# Comparación empírica de timestamp y underlying_timestamp

Fecha: 2026-10-18. Revisión local nueva solicitada por el usuario, sin API, lectura de outcomes ni entrenamiento. Esta nota corrige la conclusión excesivamente restrictiva de `SOURCE_FEASIBILITY.md`: que falte la columna `timestamp` no basta para excluir los archivos de investigación. El usuario señala que ambas columnas contienen el mismo reloj en estos snapshots; la comparación observada lo respalda en las muestras con ambas columnas.

## Resultado

Se proyectaron exclusivamente identidad contractual, intervalo y relojes en **28 archivos de día completo, 4.436.286 filas**. Selección sin resultados: enero/junio/diciembre de 2023 para cada ticker; primer y último archivo 0DTE por nombre de 2024, 2025 y 2026; comparadores conocidos QQQ 2025-01-02 y SPXW 2026-07-01. El primero ya estaba en los límites de año, por lo que no se duplicó. Las últimas fechas disponibles por nombre en 2026 son 2026-09-17.

| Grupo | Archivos | Filas | Resultado |
|---|---:|---:|---|
| Ambos relojes almacenados | 15 | 1.889.312 | Iguales exactamente en el 100% de filas |
| Solo underlying_timestamp | 13 | 2.546.974 | Rejilla 1m completa en los días muestreados |
| Total | 28 | 4.436.286 | Cero null, offset subminuto y duplicados contrato/underlying_timestamp |

En los 15 comparadores, `timestamp - underlying_timestamp` tiene mínimo, mediana, p95, p99 y máximo de **0 ms**; cero edades negativas o superiores a un minuto. Los bins floor y ceil de 1, 5 y 15 minutos coinciden en el 100% de filas. Cada timestamp nativo corresponde a un único underlying_timestamp entre contratos. Esto incluye QQQ 2025-01-02 y 2026-01-02, SPXW 2026-07-01 y los tres tickers el 2026-09-17, además de los nueve archivos de 2023.

En los 28 archivos, los 391 relojes únicos son exactamente 09:30..16:00, intervalo declarado `1m`, y cada contrato tiene 391 filas. Cero relojes fuera de la fecha contractual. Cero diferencias de underlying clock entre filas de un mismo minuto. Por ser todos minutos exactos, aplicar ceil de 1m sería identidad y no crearía duplicados; **no es necesario redondear**. No hubo intervalos 30s o 5m en esta muestra; no se infiere su ausencia del resto del inventario.

La igualdad es un resultado exacto de estas filas almacenadas, no una prueba estadística sobre todos los archivos ni prueba de cuándo se recibió una cotización live. Los 13 archivos sin timestamp carecen del comparador necesario para demostrar igualdad dentro de esos archivos. Su estructura coincide con los días comparables y da una base concreta para la convención de investigación propuesta abajo.

## Evidencia y reproducibilidad

Código: `clock_equivalence.py`. Evidencia nueva e independiente:

```text
D:/GexResearchArtifacts/restart_20261018/clock_equivalence/comparison.json
D:/GexResearchArtifacts/restart_20261018/clock_equivalence/oi_schemas.json
```

`comparison.json` guarda paths, SHA256 de fuentes, selección, tipos, intervalos, cobertura, duplicados y métricas por archivo. Solo se proyectaron las columnas de identidad/reloj; el hash procesa bytes del archivo sin interpretar precios ni retornos. `oi_schemas.json` añade 19 footers OI correspondientes a los días posteriores a 2023, sin abrir valores de OI. Los 13 OI sin timestamp tienen únicamente `symbol, expiration, trade_date, data_type, interval_used, strike, right, open_interest`; no existe `underlying_timestamp` en ellos. Los seis restantes añaden `timestamp`.

## Qué dice realmente el serializador

El `options_bulk.py` actual aplana contrato y datarow, elimina `symbol`, `expiration`, `date`, inserta identidad y graba con `preserve_index=False`. **No elimina ni renombra `timestamp`**. `options_bulk_fix.py` muestra el mismo tratamiento. Por tanto, el código actual no permite atribuir la ausencia de timestamp a esa línea de serialización; puede reflejar otro payload o una versión anterior no acreditada aquí. Tampoco permite recuperar un timestamp nativo desde índice: los footers revisados tienen `index_columns=[]`.

Ambos hechos son compatibles: no se recupera una columna ausente de un índice, pero se puede utilizar el reloj realmente almacenado `underlying_timestamp` como reloj de snapshot bajo una convención declarada y respaldada por comparadores. No hace falta inventar horarios por orden de filas.

## Inclusión propuesta para el siguiente benchmark

**Incluir candidatos 2024–2026**, validando archivo por archivo, con estos dos estados explícitos:

```text
si timestamp existe:
    snapshot_clock = timestamp
    clock_basis = NATIVE_STORED_TIMESTAMP
si no existe y underlying_timestamp es válido:
    snapshot_clock = underlying_timestamp
    clock_basis = ASSUMED_UNDERLYING_SNAPSHOT_CLOCK
research_available_at = snapshot_clock + 1 minuto
availability_basis = ASSUMED_RESEARCH_DELAY_NOT_OBSERVED_RECEIPT
```

Conservar ambos relojes y métricas de edad cuando existan. Usar los valores almacenados sin floor, ceil, secuencia inferida ni relleno. Rechazar o enmascarar valores malformados, duplicados contractuales, intervalos incompatibles, precios imposibles y falta de cobertura según reglas anteriores a resultados. Una columna presente pero inválida no se convierte silenciosamente en el fallback.

Para OI sin reloj, puede declararse `research_available_at=09:30 America/New_York` de la sesión y `oi_basis=ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT`. Esto reconoce la hipótesis de OI previo disponible al abrir; **no afirma haber observado su publicación**. Para OI con timestamp, conservarlo y limitar el uso a datos disponibles antes de la decisión bajo el contrato declarado. OI ausente permanece ausente. Los estados de reloj/OI deben persistir en el dataset y los resultados permitir separar su contribución.

Probar latencias de **1, 2 y 5 minutos** fijadas antes de entrenar. Una sensibilidad de ejecución mantiene señales, predicciones y contratos elegidos congelados y desplaza la entrada al primer instante admisible del escenario; no reescoge el mejor contrato ni el mejor escenario a posteriori. Si se desea estudiar la antigüedad de features, hacerlo como variante distinta y predefinida: a la misma hora de decisión se restringen snapshots a los disponibles con esa demora. Publicar todas las variantes, incluidos costes y cobertura.

Esta comprobación respalda avanzar hacia un benchmark temporal 2023–2024 ajuste, 2025 validación, enero–junio 2026 prueba de desarrollo, con el mismo espacio de modelos y controles de precio/zonas/placebo. La cantidad utilizable final depende del inventario y de la validación de cada día. No convierte 2026 en un periodo nunca visto por el proyecto ni demuestra rentabilidad o paridad live.
