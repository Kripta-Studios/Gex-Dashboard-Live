# Investigación 0DTE por niveles

**Estado actual: REANUDADA por orden del usuario el23 de octubre de2026.**
La [autoridad de reanudación](RESUMPTION_20261023.md) sustituye la pausa
operativa indicada abajo. Se continúa con las líneas incompletas y auditorías;
la rentabilidad causal sigue sin demostrarse y no hay promoción autorizada.
Las ejecuciones y pendientes actuales se registran en
[continuación del 23 de octubre](CONTINUATION_PROGRESS_20261023.md).

El [resultado TCN temporal del 23 de octubre](TCN_ROW_MIXED_CALENDAR_RESULT_20261023.md)
ya está auditado: selección nula y pérdidas en las tres variantes, sin cumplir
actividad diaria. Se conservan [55 artefactos con hashes](continuation_20261023/TCN_ARTIFACTS.md)
y el desglose de todos los meses y tickers. La auditoría reproduce economía
sobre scores sellados; no repite entrenamiento o inferencia. Las líneas Greeks,
mensual y OOF siguen pendientes según el registro de continuación.
La [interpretación del fallo TCN](TCN_FAILURE_INTERPRETATION_20261023.md)
distingue inactividad, pérdidas y mejora del ajuste TRAIN, y delimita las
hipótesis pendientes sin atribuir una causa económica demostrada.

## Cierre documental conservado del18 de octubre de2026

**Estado: PAUSADA POR ORDEN DEL USUARIO.** No iniciar entrenamientos, evaluaciones, auditores económicos ni subagentes por instrucciones antiguas de esta carpeta. Los planes y mensajes anteriores que dicen «siguiente», «GO» o «en ejecución» son historia; la orden de detener prevalece. Sólo se ha continuado con conservación, documentación y publicación en GitHub.

Se construyó y auditó un oracle retrospectivo rentable dentro de un motor explícito de zonas Fibonacci del IB y put/call walls. **No se consiguió demostrar un modelo causal rentable que opere al menos una vez al día por ticker.** Algunos diagnósticos aislados tienen PnL positivo; ninguno acredita el objetivo conjunto. El oracle utiliza el futuro y no es una estrategia operable.

Esta carpeta incluye código, pruebas, especificaciones previas, resultados negativos, auditorías, correcciones y propuestas incompletas. La primera exploración e inventario están en [restart_20261018](../restart_20261018/README.md). El cierre siguiente permite entender el trabajo sin reconstruir la conversación:

1. [Parada, estado final y pendientes](closure_20261018/01_STOP_AND_HANDOFF.md).
2. [Datos, causalidad, motor y oracle](closure_20261018/02_DATA_ENGINE_ORACLE.md).
3. [Arquitecturas, experimentos y resultados](closure_20261018/03_MODELS_AND_RESULTS.md).
4. [Hallazgos, auditorías, fallos y límites](closure_20261018/04_AUDITS_AND_LESSONS.md).
5. [Artefactos, reproducción y publicación](closure_20261018/05_REPRODUCTION_AND_PUBLICATION.md).
6. [Índice de todos los documentos](closure_20261018/DOCUMENT_INDEX.md).
7. [Evidencia archivada con hashes](closure_20261018/ARTIFACTS.md).
8. [Gráficas existentes, con copias consultables en GitHub](closure_20261018/FIGURES.md).
9. [Inventario de código y pruebas](closure_20261018/CODE_INDEX.md) y [comprobaciones de publicación](closure_20261018/PUBLICATION_CHECKS.md).

Los documentos de cierre son la autoridad del **estado operativo final**. Los informes de cada experimento y sus artefactos sellados conservan la autoridad sobre sus resultados concretos. No se reescribieron los fallos anteriores para convertirlos en éxitos.

## Resultados principales

| Trabajo | Resultado conocido al parar |
|---|---|
| Oracle DP, 2595 ticker-días completos | 36019 trades; +9190416.60 USD base, +9118378.60 adverso; retrospectivo y auditado |
| Primer selector causal | Seleccionó `gbt_advantage__10`; cero trades en 2026 H1 |
| GBT con episodios de contacto/rechazo | No hay política elegible diaria; empeora el control en el contraste fijo |
| TCN FLAGS64 | No hay política diaria elegible; variante sin operaciones en 2026 |
| Continuación de política causal | Cumple fills en todos los días disponibles, pero pierde: -42279.20 USD en 2025 incluyendo cortas y -46085.80 en 2026 H1 |
| Representación compacta de 152 variables | -76834.40 USD en 2025; -43482.20 en 2026 H1; no cumple actividad diaria |
| Griegas sobre contratos comunes, 424 variables | Un fit TRAIN completado; evaluación temporal no iniciada |
| TCN con filas de distintos días mezcladas | Cuatro épocas completadas; R² TRAIN final 0.231789; sin evaluación temporal |
| Walk-forward mensual | Parado con tres modelos y enero 2025 cerrado por el productor; año y auditoría incompletos |
| Calibración OOF de máximos | Código y pruebas sintéticas parciales; sin ejecución de mercado |

Las cifras son sumas de dólares netos de operaciones de un contrato. No representan rendimiento porcentual de una cuenta, cartera con capital dimensionado ni beneficio real. Los periodos temporales posteriores al ajuste ya habían sido explorados: son **SEEN_DEVELOPMENT**, no un holdout histórico intacto. Los seis ticker-días sin datos de 2026 se identifican como NO_EVALUABLE, separados de las pérdidas y de los días disponibles sin fill.
