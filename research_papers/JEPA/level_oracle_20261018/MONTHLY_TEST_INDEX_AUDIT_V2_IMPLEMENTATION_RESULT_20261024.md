# Extensión de auditoría mensual V2: integración sintética completa

24 de octubre de 2026. **IMPLEMENTATION_ONLY; MARKET_NOT_EXECUTED.**
La nueva extensión admite las seis ausencias con rutas nulas a través del lector
base V2. Conserva el núcleo económico de la extensión original. No se modificó
el índice, las fuentes, los modelos, el productor, wrappers, launchers u OOF.
Este recibo del autor no sustituye revisión independiente ni autoriza runtime.

## Cambios y preservación

[audit_monthly_walk_forward_test_index_v2.py](audit_monthly_walk_forward_test_index_v2.py)
cambia únicamente el import independiente a `audit_monthly_walk_forward_index_v2`,
`dependencies()`, el nombre de especificación y los dos identificadores de
revisión de implementación/runtime. Las once funciones y clases restantes,
incluidos `TestAudit`, `verify_authorities`, `run` y `main`, tienen AST idéntico.
La prueba compara además todos los nodos de módulo salvo la lista explícita de
cambios. No se alteran fórmulas, cortes, selección, tolerancias ni scheduler.

Las autoridades nuevas deben fijar trece dependencias exactas, incluidos los
originales preservados. La API, status y campos del cierre compuesto económico
siguen siendo compatibles con `MonthlyInputs`. La
[especificación nueva](MONTHLY_TEST_INDEX_AUDIT_V2_SPEC_20261024.md) fija alcance,
campos de índice, autoridades y límites.

| Archivo nuevo | SHA256 |
|---|---|
| Extensión `audit_monthly_walk_forward_test_index_v2.py` | `feea3954b231b18f18384696959d7cdbbcaf4d513dbf3fc4fee8596136483421` |
| Pruebas `test_audit_monthly_walk_forward_test_index_v2.py` | `54a5ab7133705d528774c1ee458989a8acff60dfdef94a69aefd3b6662587194` |
| Especificación `MONTHLY_TEST_INDEX_AUDIT_V2_SPEC_20261024.md` | `5513996a6284c175dd26496ccee645d23f721d097896123280309cc0be327e29` |

Base V2 usada: código `f01a962fcf50a2cc2bb49fd4d3eb597eb07cda47f8d2697b8046ccb9b5721ed3`,
pruebas `f986885706e78a9ecdac5f126502906d7f7637b513fb2f3a8ee16f765ea1c88d`,
especificación `06f0fcd6ac5d60a8e503d5f9df86102683e441d7b00d0a5968142384f4a821f4`.
La extensión original conserva SHA
`ec0ddb99840d5bf380eb7f407de3e1a5bcbdfa352d79ad5d75e24a05750db57b` y sus pruebas
`b3cc6d8225812154da2e4d2c644e426a19f7177d520b9d564826e3a3e4790a00`.

## Resultado del autor

**33 pruebas PASS en 296,19 s**, salida cero. Duración del proceso completo
297,242609 s. Ruff completo y `py_compile` PASS. Las trece dependencias se
rehashearon tras la suite: ningún cambio. Se ejecutó con afinidad CPU `[0]` y
límites OMP/BLAS de un hilo. Gate previo: RAM disponible 8.016.904.192 bytes y
margen de commit 5.663.301.632 bytes, ambos superiores a 2.000.000.000.

Comando ejecutado exclusivamente sobre evidencia sintética:

```text
python -m pytest -q -p no:cacheprovider research_papers/JEPA/level_oracle_20261018/test_audit_monthly_walk_forward_test_index_v2.py
```

La fixture construye 2.625 identidades de calendario, con 2.619 disponibles.
Sus seis MISSING_SOURCE tienen realmente cuatro rutas y seis hashes nulos,
con `evaluation_status=NO_EVALUABLE`; COMPLETE conserva campos válidos. Así
reproduce el formato que la fixture original no representaba. Una prueba vuelve
a obtener `TypeError` al pasar ese índice sintético al constructor original.
El constructor V2 conserva las seis `SourceDay.feature_paths=None`.

La integración reconstruye seis meses H1, doce fits nuevos y trece modelos
usados contando static, con 36 ventanas totales y selección heredada null.
Mantiene 369 ticker-días, 363 disponibles y seis no evaluables. El modo expanding
artificial suma 363 USD base; los otros dos no operan. No crea ledgers para
ausencias, mantiene sus ceros estructurales diarios y
`missing_day_economics=null`, sin convertirlos en PnL observado. Todos los modos
retienen cobertura universal `NO_EVALUABLE_MISSING_SOURCE`.

La suite conserva las pruebas de cierre/freeze, tres fit_keys, autoridad/pins,
scores y dtypes, fuentes acotadas, cortes, scheduler, salida nueva y rehash.
El adaptador `MonthlyInputs` real consume predicciones enero/junio2026 y una
predicción heredada de2025. La autoridad2025 de esta fixture es explícitamente
sintética: no se presenta como una ejecución de la auditoría2025 dentro de la
integración.

Los recibos originales permanecen en
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_test_index_v2_synthetic_20261024_01`.
Se conservaron cuatro [copias exactas y su manifest](continuation_20261024/monthly_test_index_v2_synthetic/manifest.json),
4.551 bytes: intento inicial, resultado final y stdout/stderr. El resultado
final SHA256 es `6f4a9ff5419c3baae1fdcc93f94f2b13a41516e4b22b63eb85ac9c5b958ad5c0`.

Las doce matrices y sus doce targets sintéticos suman 148.727.520 bytes y quedan
locales. Sus [24 rutas, tamaños y hashes verificados](continuation_20261024/monthly_test_index_v2_synthetic/local_fixture_references.json)
se conservan junto a la ruta/SHA del audit sintético completo. El root es
`C:/Users/Álvaro Schwiedop/AppData/Local/Temp/pytest-of-Álvaro Schwiedop/pytest-5748/monthly_test_synthetic0`:
es un directorio temporal de pytest, no un archivo permanente de datos de
investigación. No se copian matrices ni fuentes de mercado al repositorio.

## Siguiente frontera, sin ejecución

El comando siguiente es sólo una plantilla. No existen en este recibo autoridad
de runtime nueva ni permiso implícito para ejecutar mercado:

```text
python -u research_papers/JEPA/level_oracle_20261018/audit_monthly_walk_forward_test_index_v2.py --monthly-root <ROOT_MENSUAL> --source-audit <AUDIT_SESSIONCLOCK> --validation-audit <AUDIT_2025_COMPLETO> --expected-validation-audit-sha256 <SHA_EXTERNO_2025> --implementation-review <REVIEW_EXT_V2> --runtime-review <RUNTIME_EXT_V2> --output <ROOT_NUEVO>
```

Debe cerrarse la revisión independiente de estos bytes y fijarse posteriormente
una autoridad2025 completa y el runtime compuesto externo. No se adapta ahora
ningún launcher o consumidor OOF. Un eventual PASS económico seguirá siendo dado
scores sellados, sin refit o inferencia repetida, ni reconstrucción de features
desde raw, recepción histórica acreditada, paridad live o rentabilidad futura.
