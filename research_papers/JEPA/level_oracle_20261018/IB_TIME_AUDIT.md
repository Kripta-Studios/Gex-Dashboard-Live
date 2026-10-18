# Auditoría de reloj del IB y Fibonacci

Fecha: 2026-10-18. Revisión independiente de lectura de código y proyección de relojes de fuentes locales. **No se detecta uso del minuto 10:30 ni de minutos posteriores para calcular el IB**, ni mezcla de spot de minutos futuros en la agregación de caché. Resultado limitado: `PASS_CLOCK_MAPPING_DST_SAMPLE`; no acredita recepción en tiempo real ni exactitud de máximos/mínimos intraminuto.

No se ha modificado el productor congelado, calculado métricas económicas, consultado APIs ni abierto columnas de precios, griegas, cotizaciones, labels o predicciones. Los NPZ se rehashearon como bytes y únicamente se decodificó `time_ns`. De los raw se leyeron exclusivamente `timestamp`/`underlying_timestamp`.

## Fronteras temporales efectivas

`build_cache.py:83` genera 391 marcas del mismo día, de 09:30 a 16:00 con paso exacto de un minuto. Índices: 0=09:30, 59=10:29, 60=10:30. El campo `time_ns` representa fecha/hora **NY sin zona incorporada**, no epoch UTC de recepción. Usarlo después como UTC sin localizar sería incorrecto; el código inspeccionado no lo hace.

`level_engine.py:204–210` calcula mínimos/máximos únicamente sobre `spot[:60]` y su máscara, requiere al menos 57 observaciones y rango positivo. `features.py:97–104` utiliza la misma frontera. **La observación de 10:30 está fuera del IB.** `level_engine.py:248` calcula Fibonacci como `IB_low + ratio × (IB_high−IB_low)`: cero corresponde al low y uno al high.

El primer estado del motor es índice 60, 10:30 (`FIRST_STATE` y bucle en línea 340), y las ofertas ejecutan en índice `minute+1` (línea 406). `features.encode_state` rechaza índices anteriores a 60 y posteriores a 375. Por tanto, el IB terminado puede utilizarse en las decisiones autorizadas. Expresar barras históricas de 09:30–10:29 en coordenadas del IB completo **no es fuga respecto a una decisión desde 10:30**: sus coordenadas se calculan con información ya conocida al decidir. Esas mismas representaciones no serían admisibles para decisiones anteriores a 10:30.

## Parsing y agregación de spot

`parse_time` usa ISO8601, convierte errores a NaT y rechaza relojes con zona explícita; no convierte automáticamente UTC a NY ni utiliza la zona del ordenador. Se exige identidad ticker/expiración/trade_date del día. Si existe `timestamp`, se usa esa columna; si falta, se usa `underlying_timestamp` **tal como está almacenado**. Una columna nativa presente pero inválida no se sustituye silenciosamente.

Las filas deben tener fecha correcta, minuto exacto y encontrarse entre 09:30 y 16:00. El test de igualdad con `floor('min')` es una validación, **no un redondeo hacia atrás**: una fila de 10:30:59 se rechaza, no entra en 10:30. Tras esa validación se calcula el índice del minuto. Duplicados contrato/minuto provocan error, no selección arbitraria.

Para el spot, `good_spot` exige precio finito positivo y edad `timestamp−underlying_timestamp` entre 0 y 60 segundos. Un spot fechado después del reloj elegido se descarta. `np.minimum.at`/`maximum.at` agrupan exclusivamente por el índice de ese minuto y solo se acepta un valor cuando todos los spot válidos coinciden exactamente. No hay rolling hacia delante, nearest/as-of, interpolación, forward-fill o backward-fill. La lectura del archivo completo y la asignación de un eje completo de contratos no hacen que los precios de otro minuto entren en esta reducción.

Con reloj underlying como fallback, la edad resulta cero por construcción: **esto no verifica de forma independiente cuándo estuvo disponible la cotización de la opción**. Esa convención está señalada en metadatos y no debe presentarse como recepción observada.

## Comprobación DST predeterminada

Se eligieron los viernes y lunes inmediatamente anteriores/posteriores a los cambios de horario de EE. UU., para los tres tickers. Cuarenta y dos sesiones-ticker, 5.891.588 filas de reloj raw, sin selección por rentabilidad:

| Año / cambio | Viernes | Lunes | Apertura UTC antes → después |
|---|---|---|---|
| 2023 marzo | 2023-03-10 | 2023-03-13 | 14:30 → 13:30 |
| 2023 noviembre | 2023-11-03 | 2023-11-06 | 13:30 → 14:30 |
| 2024 marzo | 2024-03-08 | 2024-03-11 | 14:30 → 13:30 |
| 2024 noviembre | 2024-11-01 | 2024-11-04 | 13:30 → 14:30 |
| 2025 marzo | 2025-03-07 | 2025-03-10 | 14:30 → 13:30 |
| 2025 noviembre | 2025-10-31 | 2025-11-03 | 13:30 → 14:30 |
| 2026 marzo | 2026-03-06 | 2026-03-09 | 14:30 → 13:30 |

En las 42, el array coincide exactamente con 391 minutos de 09:30–16:00; 09:30–10:29 son los primeros 60. Las marcas raw elegidas tienen exactamente esos mismos 391 minutos únicos, sin nulos. La apertura/cierre UTC del calendario de metadatos, convertida con `America/New_York`, coincide con 09:30/16:00 y cambia correctamente entre UTC−5 y UTC−4. El calendario no sigue el cambio de hora europeo.

Veinte archivos tienen ambas columnas nativas (2.588.420 filas): igualdad exacta de ambos relojes, sin edades negativas ni no-cero. Veintidós usan fallback underlying. Todos los campos inspeccionados son strings sin zona. Esta muestra amplía la evidencia de compatibilidad del reloj almacenado; no demuestra una semántica universal de recepción. Noviembre de 2026 queda fuera del periodo de caché, que termina el 30 de junio.

Los 42 SHA de NPZ coinciden con sus metadatos; tamaños y mtime de raw coinciden con los registros sellados. En esta revisión no se volvió a rehashear cada raw completo: se conservaron sus SHA registrados, con lectura proyectada de relojes. La verificación general de caché previa sí documenta los hashes realizados al producir/reanudar.

## Supuestos y límites que permanecen

1. Interpretar strings naive como hora NY es una convención de fuente compatible con los datos y el calendario, no un atributo de zona explícito ni un recibo histórico observado. Los archivos no prueban que la captura estuviera disponible instantáneamente a esa hora.
2. El IB es **muestreado**: máximo/mínimo de hasta 60 spot instantáneos. No incluye extremos entre muestras ni demuestra el high/low continuo de toda la primera hora. Puede ser distinto al IB de velas de mercado, especialmente en 10:29:01–10:29:59. Esto es error de aproximación posible, no fuga futura.
3. Se admiten 57–60 observaciones válidas. No se rellenan las ausentes; una sesión incompleta puede producir un rango distinto del que habría dado una cinta completa.
4. La antigüedad admitida de hasta 60 segundos permite spot anterior al timestamp nativo; no admite posterior. En la muestra la edad fue cero. El fallo de disponibilidad real no puede descartarse solo con estos relojes.
5. Esta auditoría verifica el reloj y la frontera IB/Fib del pipeline inspeccionado. No reemplaza la auditoría separada de etiquetas, splits, selección, entrenamiento o ejecución de opciones.

## Evidencia reproducible

Artefactos nuevos: `D:/GexResearchArtifacts/level_oracle_20261018/ib_time_audit/probe.py` y `results.json`. La ejecución terminó con código 0. `results.json` incluye fechas, clocks, schemas, offsets, cantidades, SHA de caché y referencias raw de cada muestra.

- Cache producer SHA256: `985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f`.
- Engine SHA256: `70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6`.
- Features SHA256: `b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0`.
- Probe SHA256: `1f3338a7f05aad4104a05a6446ee297160d30bc5748a7b0d795932c28417ebe5`.
- Results SHA256: `fec23e8e734ad897cb2384a7c8b54b35621c802213e7c233c515d88a36efff1f`.
