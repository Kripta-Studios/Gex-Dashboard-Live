# TCN row-mixed: evaluación temporal completa y auditada

Fecha de cierre: 23 de octubre de 2026. Estado económico:
`FAILED_DEVELOPMENT_NO_DAILY_COMPLIANT_POLICY`. No se encontró una política
causal elegible ni rentable que cumpla el objetivo conjunto. La selección
congelada es `selected_policy=null` y
`eligible=[]`. El diagnóstico
`control__5` conserva cero operaciones en H1 2026;
no es una política aprobada. Las tres variantes row-mixed pierden dinero agregado
en 2025 y H1 2026. El oracle retrospectivo sigue siendo un resultado separado.

El productor terminó una vez desde código publicado `c1d92f26`, sin refit:
cuarta época fija, mismos normalizadores, entradas y seis políticas:
control/variant × umbral estricto 0/5/10 USD. El único cambio de entrenamiento
precedente era mezclar filas de distintos días; no se escogió época por resultado.
Se completó validación 2025 antes del freeze y de cualquier salida test de esta
comparación. Todos estos periodos son `SEEN_DEVELOPMENT`, no holdout intacto.

## Todas las políticas, ambos periodos

| Periodo | Política | Trades | Base USD | Adverso USD | PF base | Sin fill observable | Ausentes |
|---|---|---|---|---|---|---|---|
| 2025 | control__0 | 3 | -22.80 | -28.80 | 0.418367 | 749/750 | 0 |
| 2025 | control__5 | 0 | 0.00 | 0.00 | — | 750/750 | 0 |
| 2025 | control__10 | 0 | 0.00 | 0.00 | — | 750/750 | 0 |
| 2025 | variant__0 | 2488 | -138,838.80 | -143,809.80 | 0.673187 | 63/750 | 0 |
| 2025 | variant__5 | 2141 | -131,174.60 | -135,451.60 | 0.675087 | 91/750 | 0 |
| 2025 | variant__10 | 1848 | -126,398.80 | -130,090.80 | 0.675116 | 141/750 | 0 |
| 2026H1 | control__0 | 0 | 0.00 | 0.00 | — | 363/363 | 6 |
| 2026H1 | control__5 | 0 | 0.00 | 0.00 | — | 363/363 | 6 |
| 2026H1 | control__10 | 0 | 0.00 | 0.00 | — | 363/363 | 6 |
| 2026H1 | variant__0 | 1205 | -34,199.00 | -36,608.00 | 0.830847 | 20/363 | 6 |
| 2026H1 | variant__5 | 1021 | -40,962.60 | -43,001.60 | 0.793614 | 44/363 | 6 |
| 2026H1 | variant__10 | 920 | -42,491.00 | -44,328.00 | 0.781012 | 72/363 | 6 |

PnL simulado en USD por operaciones de un contrato; no es rentabilidad porcentual
de cuenta ni beneficio real. El agregado de tickers es descriptivo y no dimensiona
capital ni exposición de una cartera. Las políticas son alternativas: no se suman
entre sí. PF `—` significa indefinido por ausencia de ganancias/pérdidas; no PF cero.
«Sin fill» cuenta días observables sin operación; los ausentes se registran como
`NO_EVALUABLE` por separado. Las tablas usan punto decimal y coma de millares.

## Desglose 2025, sin selección por ticker

| Política | Ticker | Trades | Base USD | Adverso USD | PF base | Meses positivos | Sin fill/observables | Ausentes |
|---|---|---|---|---|---|---|---|---|
| control__0 | SPXW | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__0 | SPY | 3 | -22.80 | -28.80 | 0.418367 | 0 | 249/250 | 0 |
| control__0 | QQQ | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__5 | SPXW | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__5 | SPY | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__5 | QQQ | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__10 | SPXW | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__10 | SPY | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| control__10 | QQQ | 0 | 0.00 | 0.00 | — | 0 | 250/250 | 0 |
| variant__0 | SPXW | 960 | -114,425.00 | -116,344.00 | 0.680990 | 3 | 12/250 | 0 |
| variant__0 | SPY | 700 | -9,498.00 | -10,898.00 | 0.667856 | 2 | 35/250 | 0 |
| variant__0 | QQQ | 828 | -14,915.80 | -16,567.80 | 0.602692 | 1 | 16/250 | 0 |
| variant__5 | SPXW | 911 | -107,579.60 | -109,400.60 | 0.689443 | 3 | 14/250 | 0 |
| variant__5 | SPY | 538 | -8,612.80 | -9,687.80 | 0.639360 | 2 | 49/250 | 0 |
| variant__5 | QQQ | 692 | -14,982.20 | -16,363.20 | 0.551852 | 1 | 28/250 | 0 |
| variant__10 | SPXW | 877 | -105,508.20 | -107,261.20 | 0.690345 | 3 | 16/250 | 0 |
| variant__10 | SPY | 417 | -9,107.20 | -9,940.20 | 0.547814 | 2 | 79/250 | 0 |
| variant__10 | QQQ | 554 | -11,783.40 | -12,889.40 | 0.581995 | 1 | 46/250 | 0 |

## Todas las políticas por ticker en H1 2026

| Política | Ticker | Trades | Base USD | Adverso USD | PF base | Meses positivos | Sin fill/observables | Ausentes |
|---|---|---|---|---|---|---|---|---|
| control__0 | SPXW | 0 | 0.00 | 0.00 | — | 0 | 123/123 | 0 |
| control__0 | SPY | 0 | 0.00 | 0.00 | — | 0 | 120/120 | 3 |
| control__0 | QQQ | 0 | 0.00 | 0.00 | — | 0 | 120/120 | 3 |
| control__5 | SPXW | 0 | 0.00 | 0.00 | — | 0 | 123/123 | 0 |
| control__5 | SPY | 0 | 0.00 | 0.00 | — | 0 | 120/120 | 3 |
| control__5 | QQQ | 0 | 0.00 | 0.00 | — | 0 | 120/120 | 3 |
| control__10 | SPXW | 0 | 0.00 | 0.00 | — | 0 | 123/123 | 0 |
| control__10 | SPY | 0 | 0.00 | 0.00 | — | 0 | 120/120 | 3 |
| control__10 | QQQ | 0 | 0.00 | 0.00 | — | 0 | 120/120 | 3 |
| variant__0 | SPXW | 447 | -30,785.20 | -31,678.20 | 0.815544 | 2 | 5/123 | 0 |
| variant__0 | SPY | 365 | -4,731.00 | -5,461.00 | 0.683630 | 0 | 6/120 | 3 |
| variant__0 | QQQ | 393 | 1,317.20 | 531.20 | 1.064802 | 4 | 9/120 | 3 |
| variant__5 | SPXW | 442 | -35,437.20 | -36,320.20 | 0.789582 | 2 | 5/123 | 0 |
| variant__5 | SPY | 246 | -3,528.60 | -4,019.60 | 0.697012 | 2 | 23/120 | 3 |
| variant__5 | QQQ | 333 | -1,996.80 | -2,661.80 | 0.891574 | 2 | 16/120 | 3 |
| variant__10 | SPXW | 434 | -35,170.40 | -36,037.40 | 0.789336 | 2 | 6/123 | 0 |
| variant__10 | SPY | 184 | -3,580.40 | -3,947.40 | 0.623591 | 2 | 47/120 | 3 |
| variant__10 | QQQ | 302 | -3,740.20 | -4,343.20 | 0.787145 | 1 | 19/120 | 3 |

El criterio económico original por ticker exige netos base y adverso > 0,
PF base ≥ 1,20, al menos 60 operaciones y al menos 3 de 6 meses con neto base
positivo. Se añade la frecuencia de al menos un fill por ticker-día. No se añadió
umbral de win rate. La elegibilidad se decide en 2025 y el gate global conservado es
`{"passes": false, "reason": "NO_VALIDATION_DAILY_COMPLIANT_POLICY"}`. Los criterios H1
de las 18 filas quedan también en el CSV por ticker, como diagnóstico sin reselección.

QQQ con umbral cero tiene neto positivo en H1, pero PF 1,064802, nueve días
observables sin fill y tres ausencias. No cumple el criterio conjunto y no rescata
esta política, sus otros tickers ni la selección nula de validación.

Las seis ausencias son SPY/QQQ en 20260401, 20260409 y 20260415. El calendario H1
espera 369 ticker-días; 363 son observables. Esas ausencias impiden acreditar cobertura
universal y no se imputan como trades, pérdidas o retornos cero. 2025 sí cubre 750
ticker-días, incluidos los nueve cierres cortos predefinidos.

## Comparaciones al mismo umbral

Δ = variante − control; no se elige un umbral por estas diferencias.

| Periodo | Umbral USD | Δ base USD | Δ adverso USD | Δ trades |
|---|---|---|---|---|
| 2025 | 0 | -138,816.00 | -143,781.00 | 2485 |
| 2025 | 5 | -131,174.60 | -135,451.60 | 2141 |
| 2025 | 10 | -126,398.80 | -130,090.80 | 1848 |
| 2026H1 | 0 | -34,199.00 | -36,608.00 | 1205 |
| 2026H1 | 5 | -40,962.60 | -43,001.60 | 1021 |
| 2026H1 | 10 | -42,491.00 | -44,328.00 | 920 |

Se publican todos los meses de todas las políticas en
[TCN_ROW_MIXED_CALENDAR_RESULT_20261023_monthly.csv](TCN_ROW_MIXED_CALENDAR_RESULT_20261023_monthly.csv): 324 filas = 18 meses × 3 tickers × 6 políticas,
con PnL base/adverso, PF, operaciones y cobertura. El
[TCN_ROW_MIXED_CALENDAR_RESULT_20261023_policy_ticker.csv](TCN_ROW_MIXED_CALENDAR_RESULT_20261023_policy_ticker.csv) contiene 36 filas de ambos
periodos, y [TCN_ROW_MIXED_CALENDAR_RESULT_20261023_pooled.csv](TCN_ROW_MIXED_CALENDAR_RESULT_20261023_pooled.csv) conserva los 12 agregados.
No se elimina ningún mes ni se rescata un ticker o umbral por sus resultados.

## Auditoría y ejecución

`PASS_INDEPENDENT_TCN_ROW_MIXED_CALENDAR_ECONOMIC_AUDIT`. Se verificaron 750 archivos
de predicción de 2025 (4.592.687 filas) y 363 de H1 2026 (2.406.690 filas), y se
reconstruyeron sus ledgers. Se comprobó la copia exacta de los controles de las
1.104 sesiones completas y se identificaron nueve controles cortos de inferencia
nueva realizada por el productor. El auditor no repitió esa inferencia. Los ledgers auditados
contienen 6.480 trades de 2025 y 3.146 de H1
**sumados entre seis políticas alternativas**, no trades de una cartera.

El auditor verifica economía dados scores sellados y labels auditados: rehash,
calendario, controles, sellos de features, freeze, scheduler, selección y
contabilidad ask→bid con slippage de 0,01/0,02 por lado y comisión de 2,60 USD.
No refittea, no reproduce inferencia GPU ni reconstruye cotizaciones raw.
La auditoría PASS acredita este alcance, no rentabilidad, recepción histórica
ni paridad live.

Productor: exit 0 verificado con un handle Windows retenido, 1.305,195 s de extremo
a extremo; pico RSS de 1.587.216.384 bytes y private muestreado de 2.316.120.064 bytes.
Auditor: exit 0 por handle, 1.052,484 s; pico RSS de 384.221.184 bytes y private
muestreado de 346.079.232 bytes. Muestreo cada segundo: el pico RSS incluye
`peak_wset` de Windows; private no es una cota del máximo instantáneo. El supervisor
del productor se adjuntó después de arrancar; su medición de private no cubre
todo el proceso desde el primer instante. Ambos stderr quedaron vacíos.

El preflight del auditor rehasheó 25.684 miembros de completion/source_inputs sin
discrepancias. El propio auditor verificó 36.157 rutas distintas
y las rehasheó al cierre, incluyendo autoridades adicionales. Su inventario
está en `audit.json`; el fichero es la autoridad del alcance exacto.

## Evidencia terminal

- [Copias terminales conservadas y su manifiesto](continuation_20261023/TCN_ARTIFACTS.md).
- Productor: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_calendar_v1_evaluation`.
- Auditor: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_calendar_v1_economic_audit_01/audit.json`.
- Recibos del productor: `tcn_row_mixed_calendar_v1_evaluation_launch_20261023_01/monitored_exit.json`,
  `monitor_open.json`, `monitor_observations.jsonl`, `process.json` y logs.
- Recibos del auditor: `tcn_row_mixed_calendar_v1_economic_audit_01_launch_20261023_01/exit.json`,
  `audit_receipt.json`, `producer_closure_verified.json`, `preflight.json`, `process.json` y logs.
- AuditSHA256:`09b416926fe1da455d8507f0b28e24a8ed8a2ae42845ecbb9326ebf442ca85e5`.
- SummarySHA256:`e8d6b1872381f575ce619bb440ffd149546b9536d3eba88a4a42567cc9c0047a`.
- CompletionSHA256:`2ab4c8aab0c57b7c0237b746f68789d8fd271e9675578a0b56792a3e07cfa5a9`.
- FreezeSHA256:`f1804c67e584dd51a1525932565105f9fa082d2e4f9ca7a79025bab68611ee2f`.
- SourceinputsSHA256:`56b8cf0fe77977fd634c05aafa6495f5d2f05892ba753cd2673cff5d9fd0972f`.
- AuditorSHA256:`7a39395977568193764ae9c4b3e837d05e0d510ac45cc0e5649a77732c4e5b57`.

Los originales, modelos, matrices y raw permanecen locales. Este informe nuevo
no modifica el cierre histórico del 18 de octubre. Se conservan
`technical_ready=false`, `promotion_approved=false` y rentabilidad causal no
demostrada. Producción, bróker, API, servicios y VPS no intervinieron.
