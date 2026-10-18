# La condición de IV completa elimina casi toda la señal dinámica

El diagnóstico TRAIN terminó con exit 0 a las 20:23:02 UTC del 2026-10-18:
1.491 ticker-días de 2023–2024, 155.222 estados únicos y las 270.377 acciones
de la muestra original. No leyó outcomes ni validación/test, ni ajustó modelos.
Se rehashearon al final todos los caches, metadatos y fuentes consumidas.
Cinco fixtures sintéticos y Ruff pasan; no se presenta como auditoría externa.

Todos los porcentajes de la tabla usan como peso de cada estado la suma de los
IPW de sus acciones TRAIN. El JSON conserva también medias sin ponderar por
estado y ponderadas por número de acciones, además del desglose ticker/año.

| Lado/intervalo | Cue anterior disponible | Cohorte común disponible | Identidades comunes / conocidas ahora | Gamma observable retenida ahora | Gamma observable retenida antes |
|---|---:|---:|---:|---:|---:|
| CALL 5m | 0,0164% | 99,9364% | 53,0159% | 99,5869% | 99,5464% |
| CALL 15m | 0% | 99,9368% | 52,5480% | 99,5616% | 99,4006% |
| PUT 5m | 1,2348% | 99,9364% | 73,3589% | 99,6508% | 99,5915% |
| PUT 15m | 0,5071% | 99,9368% | 73,1993% | 99,6181% | 99,4139% |

Las fracciones de gamma se promedian sólo donde su denominador observado es
positivo; no estiman la gamma desconocida. La intersección puede conservar casi
toda la masa **observable** aun perdiendo muchas identidades. No implica que
conserve el mismo porcentaje de la exposición real total ni que todos los
estados individuales tengan esta cobertura media. El peor promedio por
ticker/año/intervalo observado fue 98,7988% de la masa previa en SPXW2024 PUT15m.

El bloqueo dominante es exigir IV válida en todos los contratos presentes de
ahora y de cada minuto de la barra. La condición completa de presencia pasa
99,9372% y la de OI aproximadamente 83,12–83,19%; la condición de IV pasa sólo
0,0164%/0% para CALL5/15 y 1,3471%/0,5515% para PUT5/15. Son gates marginales
superpuestos: no sumarlos como causas excluyentes. La cue vigente compara
logmasa actual con media de logmasas de barra, no endpoints separados5/15m.

La hipótesis inicial de que predominaban IV inválidas far OTM no se confirma:

| Promedio IPW de contratos por estado | CALL | PUT |
|---|---:|---:|
| Identidades conocidas | 157,88 | 157,88 |
| IV inválida entre presentes | 60,18 | 33,24 |
| IV <=0 | 53,32 | 26,64 |
| IV >5 bajo la regla existente | 6,86 | 6,60 |
| IV no finita entre presentes | 0 | 0 |
| IV inválida OTM | 0,33 | 6,18 |
| IV inválida ITM o en el dinero | 59,84 | 27,06 |
| IV inválida y distancia absoluta logstrike/spot >2% | 58,15 | 30,01 |
| IV inválida y OI cero reportado | 22,99 | 16,83 |
| OI no reportado en identidad conocida | 1,19 | 1,19 |
| Último reporte OI inválido | 0 | 0 |
| Greek ausente entre conocidos | 0,08 | 0,08 |

Esto describe los valores y máscaras almacenados; no identifica por qué el
proveedor devolvió esas IV. Exigir IV válida a un contrato con OI cero también
puede bloquear el agregado pese a que no aporte masa ponderada. La nueva
comparación no inventa una IV para esos contratos: mantiene su exclusión y
expone cuánta masa observada se retuvo.

No hubo cambio de OI reportado dentro de ninguna pareja de contratos comunes.
Los cambios de gamma de esta cohorte se deben aritméticamente a spot, IV y
tiempo bajo el proxy BS, no a un flujo intradía de OI medido. El diagnóstico
guarda también composición exterior a la cohorte y componentes ordenados
spot→IV→tiempo→OI; ese reparto depende del orden y no identifica causalidad.

La conclusión limitada es que la señal dinámica anterior estaba casi siempre
enmascarada, y que los caches sí permiten otra comparación causal con cobertura
explícita. No demuestra edge, generalización ni rentabilidad. El extractor y
los experimentos existentes permanecen intactos. La extensión a otras griegas
requiere un diseño nuevo, sus unidades y pruebas antes de cualquier fit.

Artefactos: `D:/GexResearchArtifacts/level_oracle_20261018/gamma_common_contract_train_v1`.
Summary SHA `e52e53d2b6a3f1ea6bcc66407210325acf48c7e1dec12f2fb2992868c544759c`.
Logs y exit en `gamma_common_contract_train_v1_logs`.
Diseño de la comparación: GAMMA_COMMON_CONTRACT_DESIGN.md.
