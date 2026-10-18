# Control compacto: preparación y fit completados

El 18 de octubre de 2026 se completaron una preparación y un único fit del control compacto autorizado. No se ejecutó su evaluación 2025/2026. No se acredita rentabilidad ni generalización con este resultado técnico.

Se conservaron exactamente 270377 filas de la muestra original de 1491 ticker-días TRAIN, su orden, objetivos net_base, pesos IPW y escalas por ticker (SPXW680, SPY81, QQQ88USD). La representación cambia de1954 a152 columnas:76 valores numéricos de cues y76 flags de validez. LightGBM conserva200 árboles solicitados,31 hojas,máxima profundidad6 y la configuración original,4threads y seed20261018. El modelo original no se refitteó. Las15 sesiones cortas TRAIN no forman parte de la muestra original; se conserva esa limitación para aislar el cambio de representación.

Antes de preparar se verificó la revisión independiente `MARKET_CUE_CONTROL_IMPLEMENTATION_REVIEW.json` (SHA256 `a1bbb9a939c0449e468b614b429325f52ccbb762fc9afcaf70ad253e8e632bff`), que ata código y auditorías de learner/engine.19 fixtures sintéticos y Ruff pasaron. Se copiaron código, revisión y autoridades; se mantienen snapshots además de hashes.

Preparación: exit0,209.19s,1491 chunks y matriz270377×152float32 (156.8MiB de valores). Monitor de proceso cada1s: pico RSS357261312bytes, pico private945893376bytes; RAM disponible mínima16030629888bytes. Antes del fit se rehashearon1492 checkpoints,1493 archivos derivados y7481 fuentes, sin diferencias. La revisión, matriz, escalas y dependencias permanecían exactas. Los gates de12GiB RAM disponible y16GiB commit libre se mantuvieron.

Fit: exit0,30.04s incluyendo arranque/verificación,4threads,sin GPU. Pico RSS752410624bytes y private1234886656bytes; RAM disponible mínima16096927744bytes. Los picos proceden del monitor de1s y del peak working set que expone Windows; no se presentan como una traza continua de todas las asignaciones. El entrenamiento terminó antes de liberar la ventana del primer fit mensual.

Artefactos en `D:/GexResearchArtifacts/level_oracle_20261018/market_cue_control_v1`:

| Artefacto | SHA256 |
|---|---|
| run_contract.json | ea296e2de576b91594697579c3f642e251526224213a651fbf6fbb409addf534 |
| matrix.complete.json | dc12c6a194c535e5c12ac3319ea592c6de6f03608e13a08919c4bb4440ae31e2 |
| cue_net.txt | a457176f12df8ab44964f1b595c75439320c8ee27db9da7a740b95f29fa016c7 |
| fit_started.json | 65fcec9cd46619ec1f5c4e9b87de21e4640f69dfa69667b177f21822e463ec06 |
| model.complete.json | 9d5e0bbc5744fbdbf909e4f43c11796b9aa42c418cfcf7c0e85018a82783f97a |

Modelo, fit_started y matrixmarker se rehashearon después del exit0 y coinciden. Registros operativos/snapshots: `market_cue_control_v1_launch` (prepare) y `market_cue_control_v1_fit_launch` (fit). El último contiene `prepare_rehash.json`, SHA256 `0a03c5249e9763a1d13fca5b30705761e6a5cb3e7c60b1b25d9d94b9de549e36`.

La comparación económica separada está definida en `MARKET_CUE_COMPARISON_PLAN.md`: dos políticas fijas, sin selección de ganador ni ajuste de umbral; calendario completo750/369; control original bitexact en sesiones completas; calibración de todas las ofertas frente a intentos/fills elegidos. Su revisión y auditor independiente preceden cualquier evaluación real. El diagnóstico TRAIN posterior del parent es descriptivo del ajuste y no cambia representación, target o configuración.
