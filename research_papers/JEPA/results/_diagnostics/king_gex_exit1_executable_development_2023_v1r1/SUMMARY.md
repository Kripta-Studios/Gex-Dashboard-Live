# KING-GEX-EXIT1 executable development — cierre 2023

Estado: `FAILED_ECONOMIC`. Ninguna de las 32 parejas globales
dirección/salida pasa simultáneamente los 36 ticker-meses. No se abrieron
2024/2025/2026 ni se modificó producción.

## Resultado

| Brazo / salida | Trades | WR | PF | PnL | Celdas que pasan |
| --- | ---: | ---: | ---: | ---: | ---: |
| D0 K1 / B00 | 1.324 | 42,22% | 0,804 | -89,845R | 2/36 |
| D1 invertido / B00 | 1.304 | 43,02% | 0,850 | -67,677R | 1/36 |
| D1 invertido / S30 | 1.496 | 35,96% | 0,925 | -30,131R | 1/36 |
| D1 invertido / S40 | 1.431 | 38,92% | 0,914 | -35,679R | 3/36 |
| D1 invertido / H60 | 1.450 | 40,28% | 0,896 | -41,562R | 2/36 |
| D1 invertido / S50 | 1.364 | 40,32% | 0,873 | -54,885R | 6/36 |
| D1 invertido / T30D15 | 1.392 | 48,13% | 0,799 | -83,808R | 2/36 |

El mejor PF pooled es S30 invertido, 0,925: ni una configuración llega a PF
1,0, mucho menos al gate 1,30. El trail temprano T30D15 aproxima el WR a 50%,
pero recorta tanto la ganancia media que el PF empeora. El stop amplio S100
sube el WR a 47,66%, pero agranda la pérdida media y deja PF 0,797.

## Diagnóstico de payoff

En D1/B00 la ganancia media es 0,6851R y la pérdida media 0,6109R: payoff
ratio 1,1216, insuficiente para WR 43,02%. El stop S30 mejora el payoff ratio a
1,6457 reduciendo pérdidas, pero su WR cae a 35,96%; con ese WR necesitaría
aproximadamente 2,315 de payoff ratio para PF 1,30.

Sobre las 1.083 entradas comunes B00/S30 invertidas, S30 mejora el PnL en
24,275R y reduce el hold medio en 22,5 minutos, pero convierte 96 ganadoras B00
en perdedoras y no convierte ninguna perdedora B00 en ganadora. Un oracle no
causal que eligiera ex post entre B00 y S30 daría WR 43,86%, PF 1,239 y
+61,13R. No es tradable ni alcanza 1,30, pero localiza la siguiente pregunta:
decidir causalmente en +30m si cerrar o continuar, en vez de añadir más stops
fijos.

## Integridad y checkpoints

- 36/36 source checkpoints, 425.152 filas de outcomes por evento/right.
- 32/32 policy checkpoints; el relanzamiento final reutilizó 24 y construyó 8.
- 1.152 métricas ticker-mes recomputadas en auditoría independiente.
- entrada ask, salida bid, min hold 30m, máximo 180m, caps/cooldowns y
  `reject_while_open`.
- source seal SHA-256:
  `432b0fd57067493626582e0a1b63515a433a97c76f0389724eebd097c4cc53e4`.
- protocol SHA-256:
  `228c3651e0d2be24f183683d96a14efaa7d032d998fb0e0ec3217b553e6d901a`.

Conclusión: invertir el King y variar globalmente stop/trail/horizonte no
produce rentabilidad. La familia de exits fijos queda cerrada; no se rescatan
tickers, meses o configuraciones post-hoc.
