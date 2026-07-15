# Cierre KING-GEX-SLOPE1 executable

Estado: `CLOSED_FAILED_ECONOMIC`. Esta familia solo abrió enero-diciembre de
2023 para desarrollo. No se abrieron 2024/2025 ni 2026 y no se modificó
producción.

## Resultado económico

La pendiente de net GEX no convierte la regla de régimen gamma en una policy
rentable. Ambos brazos usan ask de entrada, bid de salida, hold 30-180m,
caps/cooldowns live y rechazo mientras hay una posición abierta.

| Brazo | Trades | WR | PF | PnL | Meses que pasan | Min trades/mes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| K0 nivel | 1.443 | 43,10% | 0,810 | -94,144R | 3/36 | 19 |
| K1 nivel+pendiente alineada | 1.324 | 42,22% | 0,804 | -89,845R | 2/36 | 19 |

K1 pasa frecuencia en 36/36 celdas y concentración en pooled y los tres
tickers. Falla PF en 34/36, WR en 28/36 y PnL en 24/36. Las únicas celdas que
pasan simultáneamente son QQQ 2023-10 (42 trades, WR 54,76%, PF 1,704,
+8,499R) y SPY 2023-07 (19, 73,68%, 3,281, +5,914R). Seleccionarlas post-hoc
está prohibido. SPXW no pasa ningún mes.

| Ticker K1 | Trades | WR | PF | PnL | Meses que pasan |
| --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | 436 | 45,18% | 0,906 | -13,597R | 1/12 |
| SPXW | 644 | 38,82% | 0,736 | -62,713R | 0/12 |
| SPY | 244 | 45,90% | 0,824 | -13,535R | 1/12 |

K1 mejora PF y PnL frente a K0 en 21/36 ticker-meses, pero la mediana de mejora
es solo `+0,055712` PF y `+0,733422R`; la mediana de WR empeora `-0,005226`.
Es reducción parcial de pérdidas, no edge.

## Diagnóstico de dirección

Sobre los mismos 1.324 timestamps seleccionados por K1, el lado elegido supera
al contrario solo el 49,02%. El lado contrario también pierde: PF 0,904,
WR 44,71% y -42,624R. Por tanto invertir la regla no la rescata.

El oracle que escoge el mejor right después del outcome alcanza PF 7,320,
WR 83,16% y +657,492R; en 83,16% de las entradas al menos uno de CALL/PUT es
positivo. Esto no es una policy, pero localiza el cuello de botella: hay
movimiento/opciones ganadoras en muchos timestamps y el problema principal es
orientar el lado de forma causal.

K1 queda muy sesgado a PUT (75,3%). QQQ CALL aislado da PF 1,338 y SPY CALL
1,220, pero SPXW CALL pierde con PF 0,718 y escoger CALL/ticker tras ver 2023
sería un rescate post-hoc. Tampoco se autoriza seleccionar signo de GEX: los
regímenes positivo y negativo pierden en los tres tickers.

La siguiente hipótesis, si se abre, debe atacar el payoff direccional como una
familia nueva y congelada. No se permiten thresholds GEX, inversión por ticker,
CALL-only ni selección de los dos meses favorables dentro de KING-GEX-SLOPE1.

## Auditoría y checkpoints

Auditoría independiente: 72/72 manifests `COMPLETE`, hashes/bytes/rows
revalidados, 72/72 métricas recalculadas desde trades y scheduler validado por
brazo. El CSV final concatena K0 y K1; el cap diario debe auditarse por brazo,
no sobre ambos experimentos simultáneamente.

Los checkpoints son atómicos manifest-last por `mes/ticker/brazo` y están
incluidos en este seal. Hashes finales:

- protocolo runner: `c8690db32269e3c8deafdff652cdfd3634d71bc130abfd59a4a02dea0aa03f0f`;
- monthly: `fcf8f40eded1d45721369aa538cedbf44c586969052c56ba8fd36a5709156009`;
- trades: `72f779ce6d08ead5f796aac86348c98342550f8034f388fbb5b9a8b01281534e`;
- portfolio: `60d3b50e42b69e5f11ec1bce51c1e55659d2ed936788f2bf3933f2fbf11b62a5`;
- concentración: `a66ce65b24000fe8a0e55bee50e70a501b4f1f99865efe7f479499551b95c207`;
- summary JSON: `4e5686185232a8b5a12d8ad570e453ddeb876a69a85855cfb6ca6321923290cb`.

`live_king_node.py` sí sirvió para formular una regla falsable de nivel y
pendiente GEX. No valida su runtime completo: el proxy histórico, el cálculo de
IV/Greeks, el reloj y las convenciones de dealer no tienen paridad exacta. El
workbook `MASTER_KING_NODE_RECORD_V5.xlsx` sigue sin inspección de celdas porque
el runtime de spreadsheet requerido no está disponible; no se atribuye ningún
resultado a ese fichero.
