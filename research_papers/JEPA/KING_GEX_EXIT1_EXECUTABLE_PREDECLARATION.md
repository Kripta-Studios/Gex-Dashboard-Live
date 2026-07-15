# KING-GEX-EXIT1 — gestión executable de pérdidas y ganancias

Estado: `FROZEN_BEFORE_ALTERNATE_EXIT_REPLAY`. La familia nace después del
cierre de KING-GEX-SLOPE1 y reconoce explícitamente que sus outcomes baseline
2023 ya fueron observados. No es OOS: es desarrollo de gestión. Ningún path
2024/2025/2026 puede abrirse antes de cerrar este desarrollo y congelar una
única configuración global.

## Pregunta económica

K1 baseline no falla por frecuencia. Sus 1.324 trades tienen WR 42,22%, pero
payoff ratio solo 1,0965: ganancia media +66,11% frente a pérdida media -60,29%.
PF es 0,804. Un WR cercano a 44% podría sostener PF 1,30 si el payoff ratio
fuera aproximadamente 1,65-1,78 según el brazo exacto.

El 96,51% del gross loss baseline procede de 693 exits <=-55%. Los 749
negative triggers restan -455,108R, mientras 546 positive triggers suman
+363,076R y solo 29 horizons suman +2,187R. La hipótesis es que el contrato
stop/trail/horizonte, no solo la orientación CALL/PUT, puede estar destruyendo
la asimetría necesaria.

## Universo y direcciones

Se conservan exactamente las 13.286 oportunidades K1 de 2023, sus timestamps,
bucket SPXW d25 / QQQ-SPY d35 y la regla GEX congelada. No hay threshold, fit,
score, filtro, ticker routing ni cambio de entrada.

Se evalúan dos brazos globales solo para atribución de desarrollo:

- `D0_K1`: lado original de K1;
- `D1_INVERTED`: CALL<->PUT en toda oportunidad K1.

D1 fue sugerido y diagnosticado después de ver D0; no es confirmación. Su
baseline exacto también pierde (1.304 trades, WR 43,02%, PF 0,850,
-67,677R). Ambos brazos deben rehacer el scheduler porque el right cambia la
duración de la posición.

## Fuentes y paridad

- master executable SHA
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`;
- wall state SHA
  `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`;
- manifest ThetaData SHA
  `88be8a2ff44c18fb57fca360d31def574ddbb0419a792fc88349942711d2974a`;
- protocolo KING-GEX-SLOPE1 runner SHA
  `c8690db32269e3c8deafdff652cdfd3634d71bc130abfd59a4a02dea0aa03f0f`.

Cada path debe reconstruirse desde los Greeks históricos sellados. La entrada
usa ask del contrato seleccionado en el snapshot exacto y cada salida usa el
bid posterior. No se permite OHLC, midpoint, close, as-of, nearest strike ni
relleno. Antes de calcular una alternativa, el replayer debe reproducir por
evento/right el baseline almacenado: return, exit minutes, status, max return y
min return. Cualquier mismatch detiene el gate.

## Semántica de exit inmutable

Cada configuración mantiene TP `+1000%`, min hold `30m` y orden causal por
quote. Antes de 30m se actualiza peak pero no se sale. Desde 30m:

1. stop si `bid/entry_ask-1 <= -SL`, ejecutando al bid real, no al umbral;
2. trail si peak alcanzó activation y el bid cae al menos drawdown desde peak;
3. actualizar peak y comprobar TP;
4. si no hay trigger, salir al último bid observable hasta el horizonte.

Si falta una quote hasta el forced exit, se conserva la semántica sellada de
mark cero. Stop se comprueba antes que trail. Los horizontes permanecen entre
30 y 180m; no se autoriza hold nocturno ni más allá de RTH.

## Grid cerrado

| ID | SL | Activation | Drawdown | Horizon | Motivo |
| --- | ---: | ---: | ---: | ---: | --- |
| B00 | 0,60 | 0,50 | 0,25 | 180 | contrato actual |
| S30 | 0,30 | 0,50 | 0,25 | 180 | cortar pérdida antes |
| S40 | 0,40 | 0,50 | 0,25 | 180 | cortar pérdida antes |
| S50 | 0,50 | 0,50 | 0,25 | 180 | cortar pérdida antes |
| S80 | 0,80 | 0,50 | 0,25 | 180 | permitir recuperación |
| S100 | 1,00 | 0,50 | 0,25 | 180 | permitir recuperación |
| H60 | 0,60 | 0,50 | 0,25 | 60 | cerrar antes |
| H90 | 0,60 | 0,50 | 0,25 | 90 | cerrar antes |
| H120 | 0,60 | 0,50 | 0,25 | 120 | cerrar antes |
| T30D15 | 0,60 | 0,30 | 0,15 | 180 | lock temprano/estrecho |
| T50D15 | 0,60 | 0,50 | 0,15 | 180 | trail más estrecho |
| T50D40 | 0,60 | 0,50 | 0,40 | 180 | dejar correr ganadoras |
| T75D25 | 0,60 | 0,75 | 0,25 | 180 | activar trail más tarde |
| S40_T30D15 | 0,40 | 0,30 | 0,15 | 180 | stop+lock temprano |
| S40_T50D40 | 0,40 | 0,50 | 0,40 | 180 | stop corto+winner largo |
| S40_H90 | 0,40 | 0,50 | 0,25 | 90 | stop y horizonte cortos |

No se añadirá una configuración tras leer el grid. No se seleccionará un
exit por ticker, mes, signo de GEX o side.

## Evaluación, selección y cierre

Cada pareja dirección/configuración se replayea desde todas las oportunidades
K1 con caps/cooldowns live y `reject_while_open`. Los 36 ticker-meses deben
cumplir simultáneamente PF >=1,30, WR >=50%, >=18 trades, PnL >0 y cada hold
>=30m. Pooled y cada ticker deben pasar top-5 trade <=20% y top-5 day <=30%.

Solo son elegibles las parejas que pasan 36/36. Si hay varias, se elige una
global maximizando lexicográficamente: peor PF mensual, peor WR mensual, PF
pooled y finalmente ID alfabético. Cero elegibles cierra `KING-GEX-EXIT1` sin
outer y sin rescatar subgrupos. Los near-miss se reportan para explicar el PF,
no para promoción.

Si una pareja pasa, su ID y todos los hashes se congelan en commit separado
antes de abrir una sola vez 2024/2025. 2026 y producción permanecen cerrados.

## Checkpoints obligatorios

La preparación persiste manifest-last por `ticker/mes`, sellando inputs, código,
grid, filas y hashes de outcomes de cada config. La evaluación persiste por
`dirección/config`. Un relanzamiento solo reutiliza un checkpoint si identidad,
bytes, rows y SHA coinciden; si no, lo reconstruye o exige target nuevo.
