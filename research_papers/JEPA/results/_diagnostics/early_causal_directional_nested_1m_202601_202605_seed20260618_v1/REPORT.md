# Informe — mecanismo direccional nested sobre snapshots 1m

## Veredicto

El mecanismo queda rechazado. La corrida única terminó en 117,9 s con tests, auditoría causal y provenance PASS, pero ninguno de los tres tickers cumple las gates externas; `production_live_ready=false`.

| Ticker | Folds seleccionados | Trades | WR | PF | PnL | Min/mes | Meses positivos | Hold mínimo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1/5 | 20 | 40,00% | 1,220 | +1,700R | 0 | 20% | 30m |
| QQQ | 1/5 | 20 | 30,00% | 0,987 | -0,103R | 0 | 0% | 30m |
| SPY | 1/5 | 20 | 40,00% | 0,721 | -2,169R | 0 | 0% | 30m |
| Overall | 3/15 | 60 | 36,67% | 0,976 | -0,572R | 0 | 0% | 30m |

Junio de 2026 no está en el parquet ni en los folds. El paquete live no cambió.

## Selección inner frente al mes externo

Solo el fold de enero encontró una policy válida para cada ticker usando octubre–diciembre de 2025. Las tres fallaron inmediatamente fuera de esa ventana:

| Ticker | Perfil/dirección seleccionada | Inner trades | Inner WR | Inner PF | Inner min/mes | Inner meses + | Enero trades | Enero WR | Enero PF | Enero PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | d25 win / model | 62 | 56,45% | 2,535 | 18 | 100% | 20 | 40,00% | 1,220 | +1,700R |
| QQQ | d35 return / model | 63 | 50,79% | 1,456 | 19 | 100% | 20 | 30,00% | 0,987 | -0,103R |
| SPY | d35 win / spot 5m trend | 63 | 50,79% | 1,515 | 18 | 100% | 20 | 40,00% | 0,721 | -2,169R |

Cuando enero entra en los tres meses inner del fold siguiente, ningún perfil/dirección/threshold cumple simultáneamente PF>=1,3, WR>=50%, 18 trades por mes y todos los meses positivos. Por eso febrero–mayo abstienen para los tres tickers.

SPXW tuvo además un candidato inner válido d25-return/spot-5m-counter (64 trades, WR 50%, PF 1,718, min19 y todos los meses positivos), pero perdió la selección frente al d25-win/model por score inner. No se evalúa ni rescata retrospectivamente: escogerlo después de ver enero violaría el protocolo.

## Interpretación

La dirección spot simple no resuelve el drift. Solo SPY seleccionó una regla de momentum; SPXW y QQQ prefirieron la dirección del modelo. La señal que parecía fuerte en octubre–diciembre vuelve a romperse al primer mes posterior, igual que en la auditoría inversa del static-union. La frecuencia tampoco es el cuello de botella: el parquet contiene 80.964 candidatos 1m y cada policy inner alcanzó 18–19 trades en su peor mes.

No se retocarán signos, horizontes, thresholds ni el candidato SPXW descartado usando enero. El siguiente trabajo debe cambiar una hipótesis económica predeclarada o ampliar de forma causal la cobertura de sesión a 1m; no repetir reglas 5m/15m sobre este mismo OOS.

## Integridad y hashes

- `24 passed` antes de entrenar; compile y parse PowerShell PASS.
- Auditorías pre/post: PASS, sin issues.
- `policy_selection_provenance.passed=true`, incluidas las abstenciones con cronología explícita.
- Hold observado `>=30m` en todos los trades.

```text
audit.json                       740A3305F6D69D6171D536B1286C23EBE75112418DC5A01EDA938A42E74BD821
metrics.json                     E528CFFE8A677538C5B9FA6455C13B2C496092F376047233125DBDD5A08C2C5A
selected_folds.csv               1C05F036B7EDB8E96D23611F81EF88A445B22F0067C0A739CDBE43FFDEF4C08F
candidate_validation.csv         DC748A65EC535CFDA59EE0A63DB39C228CAD692FF284F280F2AA51AABA02EC9A
event_option_profile_trades.csv  48F6A6274D1FD0B2B81C8D486DBC1489DEF4E52C3CCF03F245E7D383445FC238
policy_selection_provenance.json 4234C5971AABFD1C51E5E9568CD7C7047AC0B7E6960FBD555EABBA9B9802E8BE
```
