# Comparación compacta: resultado económico negativo auditado

2026-10-18. Dos políticas fijas con umbral estricto de 0 USD, sin selección de ganador: `original_net__0` y `cue_net__0` (152 variables). Una posición de un contrato; netos después de los costes base del motor. Los periodos son desarrollo previamente visto, temporalmente posteriores al ajuste, no un holdout intacto.

| Periodo | Política | Operaciones | Neto USD | PF | Días disponibles sin fill |
|---|---|---:|---:|---:|---:|
| 2025 | Original | 2476 | -79189.60 | 0.785788 | 133/750 |
| 2025 | Compacta 152 | 2569 | -76834.40 | 0.829288 | 178/750 |
| 2026 enero–junio | Original | 1429 | -34449.40 | 0.831428 | 36/363 |
| 2026 enero–junio | Compacta 152 | 1442 | -43482.20 | 0.807399 | 37/363 |

En 2025 se incluyen las nueve sesiones cortas. En 2026 hay 369 ticker-días esperados, 363 disponibles y seis sin fuente: estos seis son NO_EVALUABLE, no pérdidas ni sesiones ficticias sin operación. Ambas políticas incumplen también el requisito diario en sesiones observadas. Los netos con costes adversos son, respectivamente, -84125.60/-81963.40 USD en 2025 y -37299.40/-46356.20 USD en 2026.

La reducción a 152 variables mejora ligeramente el agregado de 2025, pero empeora 2026 y no resuelve la sobreestimación de las oportunidades seleccionadas. No es una mejora económica acreditada.

| Compacta 152 | Neto 2025 USD | Meses positivos 2025 | Neto 2026 H1 USD | Meses positivos 2026 H1 |
|---|---:|---:|---:|---:|
| QQQ | -8913.80 | 2/12 | -2737.20 | 2/6 |
| SPXW | -59715.40 | 3/12 | -34448.60 | 2/6 |
| SPY | -8205.20 | 3/12 | -6296.40 | 0/6 |

En las operaciones ejecutadas por la compacta, la predicción media agrupada fue +61.42 USD frente a -29.91 USD realizados en 2025, y +57.03 frente a -30.15 USD en 2026. En SPXW 2026 fue +124.52 frente a -57.32 USD. Estas medias se reconstruyen ponderando por número de fills los bins fijos del informe auditado; son descriptivas, no parámetros de una corrección. Restar un sesgo no arregla por sí solo el orden de oportunidades ni garantiza operar diariamente.

El siguiente experimento de 424 variables ya estaba entrenado y especificado antes de abrir esta comparación: añade cambios de griegas calculados sobre contratos comunes entre extremos temporales. No se modifican sus muestras, costes, modelo, umbral o configuración por estos resultados. La calibración prequential y la evaluación mensual continúan como trabajos separados; todavía no hay evidencia de que resuelvan el problema.

## Evidencia y alcance

- Productor `D:/GexResearchArtifacts/level_oracle_20261018/market_cue_comparison_v1`, completion SHA256 `bc5849f8d29040452037511da4a97720b38135610ff60b1922670d1d5956846b`.
- Auditoría `market_cue_comparison_v1_economic_audit_v3/audit.json`, SHA256 `c16a381bb9c3f88c2e28a92ff3da6549856d960fb3cdf96c847b85ba9009d6c2`, `PASS_INDEPENDENT_MARKET_CUE_COMPARISON_ECONOMIC_AUDIT`.
- El auditor reconstruye calendario, selección/scheduler, intentos, economía base/adversa y calibración dados scores sellados. Comprueba igualdad exacta del control en 1104 sesiones completas y la procedencia explícita de nueve cortas. No refittea modelos ni reproduce la inferencia.
- Informe descriptivo `market_cue_comparison_v1_monthly_report/summary.json`, SHA256 `fbbde92c6110db2e53e53056024ac62fffb40997a12ce29b70a3e9026552db82`: 108 filas de política/ticker/mes, sin modelos, predicciones, selección o reglas nuevas. Rehashea los archivos consumidos al final. El proceso terminó exit0; las advertencias de Pandas sobre concatenación futura no alteraron la validación de identidades, conteos y netos.
- Los dos fallos iniciales del auditor por normalización de rutas Windows/POSIX se preservan; v3 es el cierre satisfactorio. No se reescribieron scores ni resultados económicos.

No hay rentabilidad operable demostrada, paridad live acreditada ni autorización de promoción. Producción y órdenes permanecen fuera de este trabajo.
