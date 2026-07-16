# OPTION_PARITY_PRESSURE_V1 — cierre de desarrollo 2023

## Veredicto

`CLOSED_NO_AGGREGATE_EDGE`.

El one-shot congelado se ejecutó desde `dd9e10ad` con manifest preejecución SHA
`f3819d881fa86c10002f35e943f6b893ddff03cf33f418dea8bca166d6526972`.
Solo abrió underlying 2023. Outer 2024–2025, holdout 2026 y producción no se
abrieron ni modificaron.

## Resultado primario

| Scope | Trades | WR | PF | PnL neto bps | Meses PASS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pooled | 730 | 48,630% | 0,874751 | -1.689,310 | 10/36 |
| QQQ | 240 | 49,167% | 0,946778 | -270,296 | 4/12 |
| SPXW | 248 | 47,984% | 0,842979 | -665,608 | 5/12 |
| SPY | 242 | 48,760% | 0,819330 | -753,406 | 1/12 |

La frecuencia no fue el fallo: los mínimos mensuales ejecutados fueron 18/19/18
para QQQ/SPXW/SPY. Fallaron estabilidad, PF y PnL. Solo pasaron julio–octubre
para QQQ; mayo, julio–septiembre y diciembre para SPXW; octubre para SPY.

La señal también pierde antes de costes: gross bps QQQ `-30,296`, SPXW
`-417,608` y SPY `-511,406`. Los 730 bps de coste solo agravan una dirección ya
negativa.

## Controles no elegibles

| Control | QQQ PF | SPXW PF | SPY PF |
| --- | ---: | ---: | ---: |
| Signo inverso | 0,958469 | 1,044478 | 1,073688 |
| Always-long | 1,328635 | 1,097375 | 1,101088 |

El signo inverso se observa únicamente como diagnóstico congelado: no alcanza
PF>1,20 en ningún ticker y no puede convertirse post-hoc en nueva policy. El
always-long muestra el drift favorable de 2023, especialmente QQQ, pero la
presión de paridad no lo selecciona; tampoco es una familia nueva autorizada.

## Auditoría independiente

- 744 eventos elegibles, exactamente 248 por ticker; dos medias jornadas
  excluidas por calendario.
- 730 operaciones: 14 presiones exactamente cero no pagan coste ni abren trade.
- Signo, retorno logarítmico, entrada 10:36, salida 13:36, hold 180m, coste 1bp,
  payoff neto y ambos controles se recalcularon fila a fila.
- 36/36 celdas ticker-mes fueron recalculadas con desigualdades estrictas.
- 744/744 fuentes underlying se rehashearon; todas pertenecen a 2023.
- El grid completo pasa. Las tres filas SPY 2023-06-05 inválidas antes de 10:19
  permanecen contadas como out-of-scope y no afectan señal/entrada/salida.
- Cero duplicados ticker-día y cero apertura de 2024–2026.

Hashes de evidencia:

- `SUMMARY.json`: `2597ef2f803ad961df4aac39238e02815f8066e69a439811deac023b2fcf498f`.
- `trades.csv`: `31c95f4524ea6a13112282f355b6eaabc4f9670a37e01a7276d25c715494552b`.
- `monthly_metrics.csv`: `d83ff1fbf5a60f4a94a805a16106ec8fd96f845c04371f599b156884692a7a60`.
- `ticker_summary.csv`: `97bfd5da64da476f1cb600b6dbe319894a221a800eb7844731ea64e6b6bbcaaa`.
- `controls_summary.csv`: `3e02e3eaef20a329be792121b977bd15e5af16cec77cfc77a36e5a9ed1e8a087`.
- `source_inventory.csv`: `b4d4c7d193d98dc0b0638e1ac278966768fa09056e86e25867badb9afc92c309`.
- `source_audit.csv`: `8d195345c94ca442971b255afd23d9163da7dd1ad6485d6c6cd30b3c43b726bc`.

## Stop rule

No abrir 2024–2026, invertir signo, escoger los meses favorables, variar radio,
reloj, normalización, threshold o modelo. El mecanismo fijo de cambio de paridad
CALL/PUT 0DTE no aporta dirección agregada en desarrollo y queda cerrado.
