# Informe — cadencia early causal 1m frente a control 5m

## Veredicto

La cadencia de candidatos 1m no alcanza el objetivo y no se promociona. `production_live_ready=false`; junio 2026 permaneció sellado y el paquete live no cambió.

| Ticker | Folds seleccionados | Trades | WR | PF | PnL | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1/5 | 20 | 40,00% | 1,220 | +1,700R | 0 | 20% |
| QQQ | 0/5 | 0 | — | — | 0R | 0 | — |
| SPY | 0/5 | 0 | — | — | 0R | 0 | — |

Hold mínimo observado en SPXW: 30m. Ningún ticker cumple simultáneamente PF>=1,3, WR>=50%, 18 trades en cada mes, todos los meses positivos y hold>=30m.

## Integridad de la comparación

- Control base 5m: 18.684 filas, SHA `5E916EFAAEA2D89B195E481FFD5948273E1D362F146EA4E8C05C3C61EFBBEF49`.
- Candidato 1m: 80.964 filas, SHA `66018CEE932F39BCDF42B4A9B7E0DB7F6F3D22DD701F8706BF83507DA49BCBD6`.
- Filas nuevas intermedias: 62.280.
- Las 18.684 filas de minutos múltiplos de cinco reproducen las 239 columnas base del control con `max_numeric_abs_diff=0`, mismas claves y ninguna columna distinta.
- Auditor de dataset y auditor final pasan; no hay features futuras/outcome, IB/Fib/nearest pre-10:30, junio ni quotes no ejecutables.

## Por qué falla

Más timestamps no crearon señal causal estable. QQQ y SPY no encuentran ningún perfil/threshold del contrato congelado que pase conjuntamente las gates en las tres ventanas internas para ninguno de los cinco folds. SPXW solo valida el fold de enero: octubre–diciembre obtiene 62 trades, WR 56,45%, PF 2,535, +22,359R, mínimo 18/mes y 100% meses positivos; aplicado a enero baja a 20 trades, WR 40,00% y PF 1,220. Al entrar enero en la siguiente ventana interna ya no existe selección válida. Es inestabilidad de régimen/generalización, no escasez de candidatos.

Frente al control 5m, 1m empeora: 5m seleccionó dos folds SPXW y sumó 39 trades, WR 43,59%, PF 1,109; 1m solo uno. Ambos fallan todas las gates completas. No se barrerán cadencias 2m/3m/4m ni se escogerá un minuto usando enero–mayo OOS.

## Nota diagnóstica

La corrida primaria usó el selector congelado SHA `95279496...B8C2AA`. Cuando todas las configuraciones eran inválidas, el resumen podía mostrar una fila vacía porque `-1e18 + trades` pierde resolución IEEE-754 y empata con `-1e18`. Esto no puede convertir una configuración inválida en válida ni cambia trades/OOS; solo oculta el mejor near-miss. Se corrige después de cerrar la corrida mediante un desempate `(score, trades)` y no se relanza el experimento primario.

## Artefactos y hashes

```text
metrics          FF0430539F25D8F04E8E9473BCC336AE0CA441CBD84626C0C90083BEB3DAF231
selected_folds   41E2D1593104C19792E12CBF1ECDD09A4A3534ACABB390CB79C4467FBF3F455D
audit trades     46DF23280BB09E0060ABA020C4A394AAD86087296CDBF2CB545B01AB5BF734D3
base parquet     66018CEE932F39BCDF42B4A9B7E0DB7F6F3D22DD701F8706BF83507DA49BCBD6
physics parquet  804BF0CC98576351126926C2B6A3C0DB1A195E9A6D51CB6306F49B3377B7CBE9
```
