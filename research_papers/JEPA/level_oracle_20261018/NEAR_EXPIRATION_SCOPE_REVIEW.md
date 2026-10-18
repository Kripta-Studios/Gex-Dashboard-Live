# Alcance 0DTE y vencimientos próximos disponibles

**Las features actuales usan exclusivamente contratos 0DTE.** `build_cache.py:71–74` exige `expiration == trade_date == día solicitado`, tanto para Greeks como para OI. Los niveles, mapas y agregados consumen ese eje de contratos; no incluyen exposición de vencimientos posteriores. Operar opciones 0DTE no obliga conceptualmente a limitar así el contexto, pero ampliar el contexto sería otra variante: no se cambia ningún run activo.

Inventario de nombres y schemas ya censados, sin recorrer nuevamente D:/ThetaData ni leer valores de parquets. Intervalo comparable: **20230103–20260630, 875 sesiones NYSE**. DTE significa diferencia entre fechas de vencimiento y negociación en días naturales, 1–7 inclusive. Familia canónica `data_options`; una pareja Greek/OI comparte ticker, fecha y vencimiento.

| Ticker | Parejas 2023 / 250 días | 2024 / 252 | 2025 / 250 | 2026 H1 / 123 | Total / 875 |
|---|---:|---:|---:|---:|---:|
| SPY | 249 | 251 | 248 | 118 | 866 |
| QQQ | 249 | 251 | 248 | 118 | 866 |
| SPXW | 249 | 251 | 248 | 121 | 869 |

Hay **2601 archivos Greek, 2607 OI, 2601 IV y 2601 OHLC** de 1–7DTE: 10410 archivos, 19038015198 bytes según el censo. En cada ticker-día cubierto existe sólo **un vencimiento adicional**, no la cadena completa de vencimientos 1,2,3,4,5,6,7DTE simultáneos. El código actual `options_bulk.py:113–127` selecciona el vencimiento semanal de la semana y, en su último día, el de la semana siguiente; esto concuerda con el patrón de nombres, sin demostrar el linaje histórico de todos los archivos. Los DTE encontrados son 1,2,3,4,6,7; no5 en este intervalo.

Las seis fechas sin pareja1–7DTE en los tres tickers son **20230406,20240328,20250417,20250703,20260402,20260618**. El censo sí contiene Greek+OI a **8DTE** para los18ticker-días correspondientes: son ausencia de ese bucket, no ausencia de toda fuente posterior. SPY/QQQ añaden **20260401,20260409,20260415**, las seis ausencias de Greeks ya conocidas; OI sí tiene archivos esos días. Esta distinción evita confundir un corte de DTE con un fallo de descarga.

| Tipo | Archivos con `timestamp` | Sólo `underlying_timestamp` | Sin ambos relojes |
|---|---:|---:|---:|
| Greek | 1398 | 1203 | 0 |
| IV | 1398 | 1203 | 0 |
| OI | 1404 | 0 | 1203 |
| OHLC | 2601 | 0 | 0 |

Son **campos observados en schemas**, no validación de disponibilidad o valores. Todas las parejas2023 tienen timestamp; posteriormente conviven ambos formatos. El acuerdo de relojes medido antes para muestras0DTE no valida automáticamente estos vencimientos. La hipótesis de reloj proxy Greek y disponibilidad supuesta de OI sin timestamp requerirían declararse y comprobarse en esta fuente. Tampoco se han validado aquí quotes, strikes, ceros, duplicados, intervalos reales, identidad interna ni versión/unidades de Greeks. No hay gamma observada en los schemas censados: cualquier gamma adicional seguiría siendo una aproximación explícita.

Fuera del intervalo de evaluación, el inventario contiene otros612archivos1–7DTE durante2026: Greek48QQQ/48SPY (20260706–20260917) y54SPXW (20260701–20260917), con sus familias complementarias. No se incorporan a los entrenamientos ni se interpretan como holdout nuevo. Las familias de capturas con nombres `normalized.parquet` sin vencimiento en el nombre no se clasifican por DTE usando sus etiquetas de carpeta: faltaría leer identidades internas en una tarea posterior.

**Qué omiten los walls actuales:** masa OI y sensibilidades de esos contratos semanales y de vencimientos aún más lejanos, posible estructura temporal y diferencias entre niveles dominantes de hoy y del resto de la cadena. Los datos encontrados permitirían investigar un contexto0DTE+semanal parcial, conservando vencimiento y tiempo restante por contrato. No equivalen a exposición total del mercado ni inventario firmado de dealers; su presencia no demuestra edge. No se amplió la familia, no se añadió una feature y no se entrenó nada como parte de este inventario.

Evidencia reproducible: `inventory_near_expirations.py` (Ruff PASS), salida `D:/GexResearchArtifacts/level_oracle_20261018/near_expiration_inventory_v1/summary.json`, SHA **9eec56a42c9b9277e9a84756765e236d86c770d9a385cbc864ba46b235c86b3c**. Contiene hashes del censo y schemas de entrada, calendario, script y listado nuevo de archivos. Suplemento de nombres8DTE `eight_dte_calendar_explanation.json`, SHA `e8201c986478e94b32f7c71a3b5e8ad50691c53cec8bdb4d4ae86a3a911a3cf1`. Los originales no se rehashearon ni se tocaron; ésta es evidencia descriptiva del censo existente, no admisión de valores.
