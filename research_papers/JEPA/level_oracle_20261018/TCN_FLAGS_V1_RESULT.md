# FLAGS64 no produjo una política diaria aprobable

El entrenamiento y la evaluación terminaron con exit0. **Ninguna de las seis
políticas cumplió la frecuencia diaria en validación2025**; la selección congelada
es `null`, con `NO_VALIDATION_DAILY_COMPLIANT_POLICY`. La variante FLAGS64 hizo
tres operaciones en un solo ticker-día de validación y ninguna en el test2026,
con cualquiera de los tres umbrales. No constituye una solución rentable para
el objetivo del usuario. Auditoría económica independiente: **PASS**, condicionada
a las predicciones selladas; reproduce seis políticas, control original, scheduler,
costes, agregados, selección/freeze/test y binding del wrapper. No afirma un refit
neuronal independiente ni equivalencia de ejecución live.

Se cambiaron únicamente64 canales semánticos de flags/cobertura a escala natural
0–1. El resto de normalizadores,270377 filas TRAIN2023–24, IPW, arquitectura,
targets, loss, AdamW, clipping, seed y cuatro épocas permanecieron fijados. No se
eligió la mejor época: se exportó siempre la cuarta. Los checkpoints guardan
pesos, optimizer y cinco estados RNG; el fit no se repitió.

| Época | R² ponderado TRAIN | MSE ponderado | Desviación predicción | Updates con clipping |
|---|---:|---:|---:|---:|
| 1 | 0,001175 | 0,592544 | 0,028098 | 3,286% |
| 2 | −0,003692 | 0,595431 | 0,006168 | 1,140% |
| 3 | 0,000703 | 0,592824 | 0,070235 | 0,671% |
| 4 | 0,001436 | 0,592389 | 0,020650 | 0,604% |

El ajuste TRAIN siguió siendo débil: el diagnóstico del TCN original daba
R²≈0,00355. Cambiar estos flags/coberturas no resolvió el problema. No existe
registro de gradientes del fit original para atribuir causalmente una reducción
del clipping respecto a aquel modelo.

Resultados monetarios descriptivos, un contrato por posición, dólares netos tras
ask→bid, comisiones y slippage del protocolo. Control reutiliza las predicciones
selladas del TCN original; no se reentrenó. Los seis resultados test se muestran
como diagnóstico, sin seleccionar retrospectivamente el umbral rentable.

| Política | Operaciones val | Neto val base | Operaciones test | Neto test base | Neto test adverso | Ticker-días test con operación |
|---|---:|---:|---:|---:|---:|---:|
| Control >0 | 102 | −6329,20 | 48 | −1502,80 | −1596,80 | 28 |
| Control >5 | 52 | −2214,20 | 19 | +2490,60 | +2453,60 | 14 |
| Control >10 | 24 | +252,60 | 7 | −1729,20 | −1742,20 | 7 |
| FLAGS64 >0 | 3 | −22,80 | 0 | 0,00 | 0,00 | 0 |
| FLAGS64 >5 | 0 | 0,00 | 0 | 0,00 | 0,00 | 0 |
| FLAGS64 >10 | 0 | 0,00 | 0 | 0,00 | 0,00 | 0 |

La variante >0 sólo operó SPY en validación. En test, SPY no registró operaciones
en ninguno de los seis controles/variantes; los detalles por ticker y mes están
en `validation/summary.json` y `test/summary.json`. El mejor diagnóstico2025 por
brazo quedó congelado como Control>10 y FLAGS64>5; ninguno aprobó el requisito
diario. El beneficio test de Control>5 no permite rescatarlo después del test.
Las diferencias pareadas FLAGS64−Control a igual umbral son respectivamente
+1502,80 / −2490,60 / +1729,20 dólares base; reflejan abstención total de FLAGS64,
no evidencia de una señal rentable aprendida.

Validación incluye741 ticker-días de sesiones completas, frente a750 de todas
las sesiones NYSE2025: nueve ticker-días de cierres cortos están fuera del
calendario congelado. Test2026H1 tiene369 previstos,363 observables y seis
`NO_EVALUABLE`; las ausencias fallan cobertura y no se consideran días sin pérdidas.
El requisito universal de operar todos los días NYSE no queda acreditado por un
gate limitado a sesiones completas. Todo el histórico ya es desarrollo visto;
no hubo evaluación prospectiva ni promoción live.

Antes de la primera predicción2025 se corrigió técnicamente la inferencia mediante
un wrapper separado: reproduce `unique/inverse` y multiplicación float32 original
antes de asignar float64. Entrenamiento intacto, tres fixtures de equivalencia y
recuperación PASS y revisión independiente del wrapper. Su snapshot, modelo y
runtime están vinculados al freeze; no hubo una evaluación anterior reemplazada.

Diagnósticos TRAIN separados:128 ejemplos elegidos por hash se memorizaron con
R²=0,999411 tras500 updates fijos, sin inputs idénticos contradictorios. En512 filas,
mezclar días redujo63,4% la dispersión de gradientes, conservando su promedio con
error relativo2,48e-8 y cero updates. Informan capacidad/optimización, no rentabilidad;
véanse `TCN_MEMORIZATION_DIAGNOSTIC_RESULT.md` y `TCN_GRADIENT_GROUPING_RESULT.md`.
La implementación row-mixed está preparada, sin caché real ni entrenamiento.

Raíz: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1`.
SHA modelo `98b614b4c0c7aeb9fd9540231de7684be453f2759c0da58e716913db1cf25c79`;
summary `77cb300d9f5866316506cb8b13a284badaa99bbcea8f06f1d972eb53acf4a271`;
completion `3fb9a6751340978f70c800b733fc6d7c981773f67e11028a6732e69dde9e52df`;
freeze `d71d500fa955609d2ca0ff75b08c5c2d608624c755870bf78326e6b1dd20e6e2`;
runtime certificate `3611ccda018bd97587305249046633b3b0ebb5b6a15dc2609fa14f7960c5df9b`.
Auditoría: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1_economic_audit/audit.json`,
SHA `9911ed97caf16f18802366dd14cb30ddeef68bdbfe05a28f3dc6711dccadb53f`.
Revisión: `TCN_FLAGS_ECONOMIC_AUDIT_REVIEW.md`.
