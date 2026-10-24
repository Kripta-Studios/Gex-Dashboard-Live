# Validación mensual 2025: auditoría cerrada y selección nula

La auditoría independiente V2 terminó con `PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`: reconstruyó doce meses, tres modos, 24 ventanas de fit y 750 ticker-días. Los tres modos pierden dinero en 2025 y ninguno cumple el requisito diario. El freeze conserva `FAIL_NO_DAILY_COMPLIANT_MODE`, `selected_mode=null` y `approved=false`. No se realizó una nueva selección.

Autoridades: [audit.json](continuation_20261024/monthly_validation_2025/audit/audit.json), SHA256 `ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc`; [freeze](continuation_20261024/monthly_validation_2025/validation_freeze.json); [report 2025](continuation_20261024/monthly_validation_2025/reports/2025.json), SHA256 `d7e5215889a796af5bc46e52f9754f60d36c82d4556c9085695ad3dcf1171d4e`. El contrato científico original permanece en `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`.

## Resultado económico auditado

La tabla reproduce los campos finales de `modes.<modo>.overall` y `modes.<modo>.tickers.<ticker>` del [report auditado](continuation_20261024/monthly_validation_2025/reports/2025.json). Solo redondea su presentación; no recalcula el ledger, barre filtros o cambia la política. `ALL` comprende 750 ticker-días y cada ticker, 250. No hay fuentes ausentes en este periodo. Los días sin fill son sesiones disponibles sin operación, no días ausentes imputados.

| Modo | Grupo | Trades | Neto base USD | PF base | WR base | Neto adverso USD | Días sin fill |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| static | ALL | 2.994 | −49.152,40 | 0,875 | 25,65 % | −55.127,40 | 72 |
| static | SPXW | 1.291 | −27.401,60 | 0,917 | 28,04 % | −29.981,60 | 2 |
| static | SPY | 856 | −10.084,60 | 0,649 | 23,13 % | −11.793,60 | 37 |
| static | QQQ | 847 | −11.666,20 | 0,639 | 24,56 % | −13.352,20 | 33 |
| expanding | ALL | 3.043 | −75.243,80 | 0,825 | 28,03 % | −81.319,80 | 99 |
| expanding | SPXW | 1.361 | −53.452,60 | 0,854 | 30,71 % | −56.171,60 | 10 |
| expanding | SPY | 724 | −8.652,40 | 0,682 | 26,24 % | −10.097,40 | 59 |
| expanding | QQQ | 958 | −13.138,80 | 0,647 | 25,57 % | −15.050,80 | 30 |
| rolling12 | ALL | 3.529 | −122.081,40 | 0,730 | 23,80 % | −129.124,40 | 45 |
| rolling12 | SPXW | 1.465 | −93.080,00 | 0,755 | 26,83 % | −96.006,00 | 3 |
| rolling12 | SPY | 1.027 | −15.080,20 | 0,558 | 22,20 % | −17.130,20 | 26 |
| rolling12 | QQQ | 1.037 | −13.921,20 | 0,633 | 21,12 % | −15.988,20 | 16 |

Los nueve grupos modo×ticker pierden tanto con costes base como adversos y fallan el requisito diario. El resultado no acredita rentabilidad operable. Los costes, niveles, scheduler y reglas permanecen en el [plan científico ejecutado](continuation_20261024/monthly_validation_2025/code/scientific_producer/MONTHLY_WALK_FORWARD_PLAN.md) y el [contrato](continuation_20261024/monthly_validation_2025/run_contract.json).

## Cierre de procesos y recursos

El productor de validación PID 11852 terminó con salida 0 observada mediante handle retenido el 23-oct-2026 a las 23:15:39.501243 UTC. Su completion del overlay precede al exit, a las 23:15:37.281501 UTC. Se conservaron los 6.084 checkpoints anteriores y se cerró un inventario final de 11.699. Véanse [completion de validación](continuation_20261024/monthly_validation_2025/runtime/validation/completion.json) y [exit del monitor](continuation_20261024/monthly_validation_2025/runtime/validation_monitor/monitored_exit.json).

El auditor V2 PID 52304 terminó con salida 0 por su handle de `Popen` a las 23:50:32.495581 UTC. El supervisor completó su rehash y publicó el cierre a las 23:51:21.257880 UTC. Las cadenas PID/creación, comando, review externo, admission, exit y audit se comprobaron. Ambos procesos finalizaron, con stderr vacío y sin failure del intento 02. Véanse [exit del auditor](continuation_20261024/monthly_validation_2025/runtime/audit_02/exit.json) y [completion del supervisor](continuation_20261024/monthly_validation_2025/runtime/audit_02/completion.json).

| Proceso | Duración del recibo | RSS informado | Alcance de la medición |
| --- | ---: | ---: | --- |
| Productor de validación reanudado | 13.285,57 s | 7.815.368.704 bytes | El monitor incorpora `peak_wset` de Windows; el pico privado se muestrea desde su conexión. |
| Auditor V2 | 1.082,10 s | 4.762.075.136 bytes | Máximo RSS observado en 1.075 muestras; intervalo de un segundo, no pico exacto de toda la ejecución. |

SHA256 del exit del auditor: `7c7f24743f961707dbfe330b2a0f61b92ad849fe75862ca94c991f802ef21e21`. SHA256 del completion del supervisor: `07839f7f7437b87d0a8c011fe4ba6032eec16a21637f2c5b84f233d4d77c663b`.

## Alcance de la auditoría y fallo preservado

El auditor reconstruyó muestreo, targets/labels/pesos de entrenamiento, matrices desde day chunks, identidad de scores y su modelo/escala, scheduler, ledgers, economía, orden de sellado, selección y report anual. No refitteó modelos ni repitió inferencia. Su PASS sigue condicionado a los scores sellados. La comparación de valores cubre chunks y matrices; las fuentes subyacentes se autentican por sus hashes, sin una reconstrucción nueva de todas las features.

El [intento 01 fallido](continuation_20261024/monthly_validation_audit_01_failure) conserva su salida 1 y sus bytes. Falló en el constructor del auditor al convertir a `Path` una ruta nula de las seis filas `MISSING_SOURCE` de 2026 presentes en el índice completo. V2 admite esa representación y rechaza lecturas de payloads ausentes; conserva esas filas. No se cambió el índice, el productor, los modelos ni el contrato económico. El intento 02 usó código/review nuevos publicados, con el review externo `f45d9dc6e032f9bd5e646ec0fad8059a924e8fed1462f817737b26cfff09d389`. Su [review independiente](continuation_20261024/monthly_validation_2025/code/auditor_runtime/MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_REVIEW_20261024.json) sigue siendo evidencia de implementación; la ejecución real se acredita mediante los recibos y audit separados.

2025 y 2026 conservan su condición de desarrollo visto. Los timestamps acreditan orden de sellado, no publicación histórica en cada corte. `promotion_approved=false`; este cierre no acredita paridad live ni rendimiento prospectivo. El archivo documental no ejecutó el report consolidado, nuevos modelos ni test 2026.

## Archivo compacto y referencias locales

El [manifest](continuation_20261024/monthly_validation_2025/MANIFEST.json) contiene 242 copias exactas, 38.632.476 bytes, con ruta original, destino, tamaño y SHA256. Originales y copias compactos se rehashearon y coinciden. Incluye audit, freeze/report y sellos, contrato, 36 sellos mensuales, código/reviews pertinentes y recibos de cierre. Los 24 modelos `.txt` con sus `fit_started` y `complete` forman 72 archivos y suman 19.146.543 bytes. El [script de archivo](continuation_20261024/monthly_validation_2025/archive_evidence.py) conserva el procedimiento de copia y verificación.

Las [72 referencias locales](continuation_20261024/monthly_validation_2025/LOCAL_REFERENCES.json) cubren inputs, matrices y targets de los 24 fits. Las 48 matrices/targets suman 30.906.728.203 bytes y permanecen locales. Se comprobó concordancia de sus hashes entre la autoridad auditada y los markers sellados, existencia y tamaño actual. **No se rehashearon otra vez esos payloads para este archivo documental**: los hashes se atribuyen explícitamente a la auditoría recién completada. Los inputs grandes, features y raw tampoco se copiaron. El índice local permanece referenciado; el stdout del auditor, que duplica audit.json, se conserva por referencia.

El archivo del fallo 01 permanece separado. No se ha sustituido por el PASS posterior ni se ha duplicado aquí su archivo completo.
