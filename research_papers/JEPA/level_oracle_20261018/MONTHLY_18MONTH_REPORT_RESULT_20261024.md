# Reporte consolidado de los 18 meses auditados

24 de octubre de 2026. El reporter congelado terminó `COMPLETE`, con salida real
0, sobre enero de 2025–junio de 2026. Conserva los tres modos, todos los tickers
y meses, los dos escenarios de costes y `selected_mode=null`.
`SEEN_DEVELOPMENT` sigue vigente; no hay promoción ni evidencia prospectiva.

La auditoría compuesta previa tiene SHA
`87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e` y status
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`. Su supervisor
cerró con salida 0 y completion SHA
`1045866ea9fdf7d926a51a221e9e5f453ead5146d835197ec99fabe3466b0165`.
El reporte descriptivo hereda ese alcance; no repite fits, inferencia, selección,
scheduler, auditoría de raw o reconstrucción de labels.

## Economía y cobertura

Las [24 filas por periodo](continuation_20261024/monthly_18month_report/report/periods.csv)
contienen los tres modos × tres tickers y ALL × 2025/H1 2026, incluidos PF,
WR, duración, drawdown, motivos de salida, intentos y cobertura. Las
[216 filas mensuales](continuation_20261024/monthly_18month_report/report/monthly.csv)
presentan las mismas combinaciones durante los 18 meses, sin excluir meses.
Los [3.357 registros diarios](continuation_20261024/monthly_18month_report/report/daily.csv)
conservan también las ausencias. ALL es una suma descriptiva de USD nominales,
no una cartera con riesgo igualado ni un gate adicional.

| Periodo | Modo | Trades | Neto base USD | Neto adverso USD | PF base | Días disponibles sin fill | Ausentes |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025 | static | 2.994 | −49.152,40 | −55.127,40 | 0,8745 | 72/750 | 0 |
| 2025 | expanding | 3.043 | −75.243,80 | −81.319,80 | 0,8252 | 99/750 | 0 |
| 2025 | rolling12 | 3.529 | −122.081,40 | −129.124,40 | 0,7297 | 45/750 | 0 |
| H1 2026 | static | 1.590 | −8.746,00 | −11.921,00 | 0,9568 | 8/363 | 6 |
| H1 2026 | expanding | 1.375 | −20.616,00 | −23.358,00 | 0,9000 | 61/363 | 6 |
| H1 2026 | rolling12 | 1.711 | −47.347,60 | −50.763,60 | 0,7906 | 26/363 | 6 |

El [resultado de 2025](MONTHLY_VALIDATION_2025_AUDIT_RESULT_20261024.md) y su
[interpretación](MONTHLY_VALIDATION_2025_FAILURE_INTERPRETATION_20261024.md)
siguen intactos. El nuevo consolidado conserva sus cifras y añade el semestre
auditado. H1 tiene 369 ticker-días esperados y 363 disponibles por modo:
SPXW 123/123; SPY y QQQ 120/123 cada uno. Faltan SPY y QQQ los días 1, 9 y
15 de abril de 2026. Son seis identidades ausentes, repetidas por los tres modos
en las tablas; no son 18 ausencias de fuente distintas.

| Modo H1 | Ticker | Trades | Neto base USD | Neto adverso USD | PF base | PF adverso | Días disponibles sin fill |
|---|---|---:|---:|---:|---:|---:|---:|
| static | SPXW | 593 | −5.295,80 | −6.479,80 | 0,9685 | 0,9616 | 0/123 |
| static | SPY | 511 | −3.998,60 | −5.018,60 | 0,7507 | 0,7015 | 6/120 |
| static | QQQ | 486 | 548,40 | −422,60 | 1,0301 | 0,9776 | 2/120 |
| expanding | SPXW | 702 | −14.570,20 | −15.970,20 | 0,9195 | 0,9122 | 4/123 |
| expanding | SPY | 301 | −5.442,60 | −6.043,60 | 0,4988 | 0,4657 | 36/120 |
| expanding | QQQ | 372 | −603,20 | −1.344,20 | 0,9577 | 0,9091 | 21/120 |
| rolling12 | SPXW | 698 | −30.927,80 | −32.320,80 | 0,8339 | 0,8273 | 1/123 |
| rolling12 | SPY | 472 | −2.950,20 | −3.893,20 | 0,7911 | 0,7370 | 13/120 |
| rolling12 | QQQ | 541 | −13.469,60 | −14.549,60 | 0,4773 | 0,4523 | 12/120 |

Los seis ausentes tienen economía `null` y status `NO_EVALUABLE`, no retorno
cero observado. El requisito universal del calendario H1 queda no evaluable
para SPY, QQQ y ALL; los días disponibles sin fill se informan por separado.
SPXW `static` sí tiene fill en sus 123 días, pero pierde en ambos escenarios.
QQQ `static` muestra un neto base pequeño positivo, PF 1,0301 y neto adverso
negativo; no rescata el modo ni modifica la selección congelada en 2025.

La falta de actividad y el fallo económico siguen siendo cuestiones distintas.
En H1 sólo hay un intento NO_FILL: QQQ `rolling12`; los otros dos modos no
tienen ninguno, aunque dejan días disponibles sin fill. El agregado pierde
con los tres modos en base y adverso. Los cambios frente a 2025 no identifican
causalmente deriva o mejora de estimación: son periodos de duración distinta,
con decisiones diferentes y entrenamiento actualizado según reglas fijadas.
No se selecciona un ticker o mes favorable ni se añaden filtros.

Los escenarios conservan ask→bid, multiplicador 100, comisión de 1,30 USD por
lado y slippage 0,01 base / 0,02 adverso por lado, con suelo cero del bid de
salida tras slippage. Se agregan netos ya auditados; no se calcula una variante
sin costes, una inversión de señal ni una simulación adicional.

## Ejecución única y copias exactas

Código del reporter publicado en `02cb4f7404abab0564c567d17eeaccd887b22a24`, SHA
`1968aefcba4abf650d5e13cd16435ac74067cfee78ce5752fde6427e5a941146`.
Launcher operativo revisado y autorizado por root, SHA
`c9f83564e7ff154ff274e168a42a193fcd5d0dc6f0f26e56e0b24f1063827e45`.
Su [copia](continuation_20261024/monthly_18month_report/launcher/launch_report.py)
y el [diff de cierre por excepción](continuation_20261024/monthly_18month_report/launcher/exception_handling_revision.diff)
se preservan. No hubo retry ni excepción durante la ejecución.

El proceso 2468, creación `1792815081.9765415`, terminó el
24 de octubre a las 04:14:04.770637 UTC. El wrapper 12796 conservó el handle;
`GetExitCodeProcess` confirmó salida 0, y la sesión del wrapper también cerró
con 0. Duración 162,796 s; 161 muestras; pico RSS muestreado 394.596.352 bytes.
Gate previo: RAM disponible 8.637.067.264 bytes y commit libre 6.823.354.368.
Mínimos observados: RAM 7.365.488.640 y commit 4.179.394.560 bytes. Se usó
una CPU y un thread por librería. `monitor_error=null`, `pins_unchanged=true`
y `audit_unchanged=true`; stderr vacío.

Salida local:
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_18month_consolidated_report_20261024_01`;
recibos en el sibling con sufijo `_logs`. Pins terminales:

- [Manifest COMPLETE](continuation_20261024/monthly_18month_report/report/output_manifest.json):
  `6c104c866c320beea811b7ee295a4b625d56d44a905a352e1d6f34d9cee7932d`.
- [Exit retenido](continuation_20261024/monthly_18month_report/logs/exit.json):
  `eafcea8ed68506731d72ed0890dc84b96169bfde73caf65154328cfa27fabfec`.
- [Summary](continuation_20261024/monthly_18month_report/report/summary.json):
  `e39fe25e7f7947362993595351fd71e804b0fbfcf8985761a400e2c27a07b914`.

Se rehashearon los siete outputs enumerados por el manifest sin diferencias.
Contienen 14.246 intentos y 14.242 filas de ledger entre todos los modos y meses;
sumar modos no representa una estrategia operada conjunta. El
[manifest de archivo compacto](continuation_20261024/monthly_18month_report/MANIFEST.json),
SHA `f477558704924a0c830654aca48cfc88c603bbe5d03b4c58c2d1eac174cfa7ce`,
verifica 16 copias exactas y 13.526.701 bytes, frente a sus fuentes antes y
después de copiar. Incluye tablas, ledgers consolidados, inventario, recibos y
launcher. Las matrices, modelos, features y raw permanecen locales, referenciados
en el inventario; no se copiaron ni se repitió su auditoría masiva.
